import streamlit as st
import requests
import pyshark
import pandas as pd
import json

# CSS styling
def add_css():
    st.markdown(
        """
        <style>
        /* General layout with blue background */
        .main {
            background-color: #007BFF;
            font-family: 'Arial', sans-serif;
            color: white;
        }
        /* Header styling */
        h1 {
            color: #ffffff;
            text-align: center;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        /* Sidebar styling */
        .css-1aumxhk {
            background-color: rgba(255, 255, 255, 0.8);
            padding: 10px;
            border-radius: 8px;
            backdrop-filter: blur(5px);
        }
        /* Button styling */
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            border: none;
        }
        /* Dataframe styling */
        .css-1d391kg {
            border: 1px solid #ddd;
            border-radius: 8px;
        }
        /* Text input styling */
        .stTextInput>div>div>input {
            background-color: #FFFFFF;
            color: black;
            border: none;
            border-radius: 8px;
            padding: 10px;
            width: 100%;
        }
        /* Chat interface box styling */
        .chat-box {
            background-color: rgba(255, 255, 255, 0.9);
            color: green;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Add custom CSS
add_css()

# Initialize session state for conversation history
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

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

# Function to interact with the Ollama model via API
def query_ollama_api(model_name, conversation_history):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    input_text = "\n".join(conversation_history)

    payload = {
        "model": model_name,
        "prompt": input_text,
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()

        raw_response = response.text

        try:
            data = json.loads(raw_response)
            output = data.get("response", "No output received from model.")
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
        st.write(response.text)
        return f"HTTP error occurred: {http_err}"

    except requests.exceptions.RequestException as req_err:
        st.error(f"An error occurred during API request: {req_err}")
        return f"An error occurred: {req_err}"

    except Exception as e:
        error_message = f"Unexpected error: {e}"
        st.error(error_message)
        return error_message

# Streamlit UI for displaying results
st.title("Network Insights")

# Sidebar for file format selection
st.sidebar.header("Upload and Settings")
st.sidebar.subheader("Select File Formats")
format_options = {
    "JSON": "json",
    "CSV": "csv",
    "PCAP": "pcap",
    "SNMP": "snmp",
    "TDL": "tdl"
}
selected_formats = [fmt for fmt, ext in format_options.items() if st.sidebar.checkbox(fmt)]

# File uploader based on selected formats
if selected_formats:
    file_types = [format_options[fmt] for fmt in selected_formats]
    uploaded_file = st.sidebar.file_uploader(
        "Choose a file",
        type=file_types,
        help=f"Selected formats: {', '.join(selected_formats)}."
    )
    process_file(uploaded_file)
else:
    st.sidebar.warning("Please select at least one file format.")

# Layout for user input and conversation history
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Conversation")
    
    # Display each prompt and response in a separate text area, with latest at the bottom
    for i, message in enumerate(st.session_state.conversation_history):
        role, text = message.split(': ', 1)
        height = max(100, len(text) // 2)  # Adjust height based on text length
        st.text_area(f"{role} Message {i + 1}", value=text, height=height, key=f"{role}_{i}")

    # User input section for conversation with the model at the bottom
    st.write("Enter your question or follow-up:")
    user_input = st.text_input("Your input here:", placeholder="Type your message here...")

    if st.button("Submit"):
        if user_input.strip():
            with st.spinner('Processing...'):
                st.session_state.conversation_history.append(f"User: {user_input}")
                response = query_ollama_api("llama3.2:latest", st.session_state.conversation_history)
                st.session_state.conversation_history.append(f"Model: {response}")

with col2:
    with st.expander("Conversation History", expanded=False):
        for line in st.session_state.conversation_history:
            st.write(line)

        if st.button("Clear Conversation"):
            st.session_state.conversation_history = []

        if st.button("Download Conversation History"):
            conversation_text = "\n".join(st.session_state.conversation_history)
            st.download_button(
                label="Download as TXT",
                data=conversation_text,
                file_name='conversation_history.txt',
                mime='text/plain'
            )
