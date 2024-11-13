import streamlit as st
import subprocess
import pyshark
import plotly.express as px
import pandas as pd
import json

# Initialize session state for conversation history
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# Function to interact with the Ollama model
def query_ollama_model(model_name, conversation_history):
    input_text = "\n".join(conversation_history)
    command = f"echo '{input_text}' | ollama run {model_name}"
    try:
        output = subprocess.check_output(command, shell=True, text=True)
        return output.strip()
    except subprocess.CalledProcessError as e:
        st.error(f"An error occurred: {e}")
        st.error(f"Error output: {e.output}")
        return "An error occurred while querying the model."

# Function to read and display file content
def process_file(uploaded_file):
    if uploaded_file is not None:
        st.session_state.conversation_history = []
        st.write(f"Uploaded file type: {uploaded_file.type}")
        if uploaded_file.type in ["application/vnd.tcpdump.pcap", "application/octet-stream"]:
            st.write("Processing PCAP file...")
            pcap_file_path = uploaded_file.name
            with open(pcap_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            capture = pyshark.FileCapture(pcap_file_path)
            packets = []
            for packet in capture:
                try:
                    packets.append({
                        'No': packet.number,
                        'Time': packet.sniff_time,
                        'Source': packet.ip.src,
                        'Destination': packet.ip.dst,
                        'Protocol': packet.transport_layer,
                        'Length': packet.length
                    })
                except AttributeError:
                    continue
            capture.close()
            df = pd.DataFrame(packets)
            st.dataframe(df)
            st.session_state.conversation_history.append(f"PCAP Summary: {df.head().to_string()}")
        else:
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            st.write(f"File Content:\n{content[:200]}...")
            st.session_state.conversation_history.append(f"File Content: {content[:200]}...")

# Function to visualize the response with Plotly
def visualize_response_with_plotly(response_text):
    words = response_text.split()
    word_count = pd.DataFrame({'word': words, 'count': range(len(words))})
    fig = px.bar(word_count, x='word', y='count', title='Word Frequency in Response')
    st.plotly_chart(fig)

# Streamlit UI
st.title("File Upload and Conversational Interaction with Ollama Model")

uploaded_file = st.file_uploader("Choose a file", type=["json", "psv", "cap", "snmp", "tdl"])
process_file(uploaded_file)

st.write("Enter your question or follow-up:")
user_input = st.text_input("Your input here:")

if st.button("Submit"):
    if user_input:
        # Wrap the long-running operation in a spinner
        with st.spinner('Processing...'):
            st.session_state.conversation_history.append(f"User: {user_input}")
            response = query_ollama_model("llama3.2:latest", st.session_state.conversation_history)
            st.session_state.conversation_history.append(f"Model: {response}")
            
            try:
                response_data = json.loads(response)
                st.write("Response from Model (JSON):")
                st.json(response_data)
            except json.JSONDecodeError:
                st.error("Failed to parse JSON. Response might not be in JSON format.")
                st.text(response)
            
            visualize_response_with_plotly(response)

st.write("Conversation History:")
for line in st.session_state.conversation_history:
    st.write(line)

if st.button("Clear Conversation"):
    st.session_state.conversation_history = []