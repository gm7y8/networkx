import streamlit as st
import requests
import pyshark
import plotly.express as px
import pandas as pd
import json

# Initialize session state for conversation history
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# Function to interact with the Ollama model via API
def query_ollama_api(model_name, conversation_history):
    url = "http://localhost:11434/api/generate"  # Default Ollama API URL
    headers = {"Content-Type": "application/json"}
    input_text = "\n".join(conversation_history)

    payload = {
        "model": model_name,
        "prompt": input_text
    }

    try:
        st.debug("Sending API request to Ollama server...")
        st.json(payload)  # Display the request payload for debugging

        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()  # Raise an error for HTTP status codes 4xx/5xx

        # Clean the response by stripping extra whitespace
        raw_response = response.text.strip()
        st.debug("Raw API Response:", raw_response)

        # Try parsing the response as JSON
        try:
            data = json.loads(raw_response)
            output = data.get("output", "No output received from model.")
        except json.JSONDecodeError:
            st.warning("The response is not in JSON format. Displaying as plain text.")
            output = raw_response

        return output

    except requests.exceptions.Timeout:
        st.error("The request to Ollama API timed out. Please try again.")
        return "API request timed out."

    except requests.exceptions.ConnectionError:
        st.error("Failed to connect to the Ollama API. Ensure the server is running.")
        return "Failed to connect to Ollama API."

    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error occurred: {http_err}")
        st.write(response.text)  # Display the error response for more details
        return f"HTTP error occurred: {http_err}"

    except requests.exceptions.RequestException as req_err:
        st.error(f"An error occurred during API request: {req_err}")
        return f"An error occurred: {req_err}"

    except Exception as e:
        error_message = f"Unexpected error: {e}"
        st.error(error_message)
        return error_message

# Function to read and display file content
def process_file(uploaded_file):
    if uploaded_file is not None:
        st.session_state.conversation_history = []
        st.write(f"Uploaded file type: {uploaded_file.type}")
        try:
            if uploaded_file.type in ["application/vnd.tcpdump.pcap", "application/octet-stream"]:
                st.write("Processing PCAP file...")
                with open("temp.pcap", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                capture = pyshark.FileCapture("temp.pcap")
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
        except Exception as e:
            st.error(f"Failed to process file: {e}")

# Function to visualize the response with Plotly
def visualize_response_with_plotly(response_text):
    try:
        words = response_text.split()
        word_count = pd.DataFrame({'word': words, 'count': range(len(words))})
        fig = px.bar(word_count, x='word', y='count', title='Word Frequency in Response')
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Failed to visualize response: {e}")

# Streamlit UI
st.title("File Upload and Conversational Interaction with Ollama Model")

# File uploader for processing different file types
uploaded_file = st.file_uploader("Choose a file", type=["json", "psv", "cap", "snmp", "tdl"])
process_file(uploaded_file)

# User input section for conversation with the model
st.write("Enter your question or follow-up:")
user_input = st.text_input("Your input here:")

if st.button("Submit"):
    if user_input.strip():  # Prevent submission with empty input
        with st.spinner('Processing...'):
            st.session_state.conversation_history.append(f"User: {user_input}")
            response = query_ollama_api("llama3.2:latest", st.session_state.conversation_history)
            st.session_state.conversation_history.append(f"Model: {response}")

            # Display the response
            st.write("Response from Model:")
            st.text(response)

            # Visualize the model's response using Plotly
            visualize_response_with_plotly(response)

# Display the conversation history
st.write("Conversation History:")
for line in st.session_state.conversation_history:
    st.write(line)

# Button to clear the conversation history
if st.button("Clear Conversation"):
    st.session_state.conversation_history = []
