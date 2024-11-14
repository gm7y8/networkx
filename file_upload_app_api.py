import streamlit as st
import httpx
import requests
import pyshark
import pandas as pd
import asyncio

# Webhook URL where you want to send the data
WEBHOOK_URL = "https://webhook.site/************************************"

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

# Initialize session state for conversation history and processing state
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "processing" not in st.session_state:
    st.session_state.processing = False

# Limit the conversation history size
MAX_HISTORY = 10

# Function to send data to a webhook server
def send_to_webhook(response):
    try:
        payload = {"response": response}
        result = requests.post(WEBHOOK_URL, json=payload)
        result.raise_for_status()
        st.success("Response sent to webhook successfully!")
    except requests.RequestException as e:
        st.error(f"Failed to send response to webhook: {e}")

# Asynchronous function to interact with the Ollama model via API
async def query_ollama_api(model_name, conversation_history):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    input_text = "\n".join(conversation_history)
    payload = {
        "model": model_name,
        "prompt": input_text,
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No output received from model.")
    except (httpx.HTTPStatusError, httpx.RequestError, Exception) as httpx_err:
        st.warning(f"HTTPX error occurred: {httpx_err}. Falling back to requests.")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No output received from model.")
        except requests.RequestException as req_err:
            st.error(f"Request error: {req_err}")
            return f"Request error: {req_err}"

# Function to process uploaded files with a progress bar and spinner
def process_files(uploaded_files):
    if uploaded_files:
        st.session_state.processing = True  # Set processing state
        with st.spinner("Processing uploaded files..."):
            for uploaded_file in uploaded_files:
                st.write(f"Processing file: {uploaded_file.name}")
                try:
                    if uploaded_file.type in ["application/vnd.tcpdump.pcap", "application/octet-stream", "application/x-pcap"]:
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
                        st.session_state.conversation_history.append(f"File Content: {content[:200]}...")
                except Exception as e:
                    st.error(f"Failed to process file: {e}")
        st.session_state.processing = False  # Reset processing state
        st.success("Processing done!")  # Indicate processing completion

# Streamlit UI Layout
st.title("Enhanced Chat Interface with File Uploads and Ollama API")

# Sidebar for file format selection
st.sidebar.header("Upload and Settings")
st.sidebar.subheader("Select File Formats")
format_options = {
    "JSON": "json",
    "CSV": "csv",
    "PCAP": ["pcap", "cap"],  # Handle both extensions for PCAP files
    "SNMP": "snmp",
    "TDL": "tdl"
}
selected_formats = [fmt for fmt, ext in format_options.items() if st.sidebar.checkbox(fmt)]

# File uploader based on selected formats with multi-file support
if selected_formats:
    file_types = [ext for fmt in selected_formats for ext in (format_options[fmt] if isinstance(format_options[fmt], list) else [format_options[fmt]])]
    uploaded_files = st.sidebar.file_uploader(
        "Choose files",
        type=file_types,
        accept_multiple_files=True,
        help=f"Selected formats: {', '.join(selected_formats)}."
    )
    process_files(uploaded_files)
else:
    st.sidebar.warning("Please select at least one file format.")

# Layout for user input and conversation history
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Conversation")
    
    # Display each prompt and response in a separate text area, with latest at the bottom
    for i, message in enumerate(st.session_state.conversation_history):
        if ": " in message:
            role, text = message.split(': ', 1)
        else:
            role, text = "Info", message
        height = max(100, len(text) // 2)  # Adjust height based on text length
        st.text_area(f"{role} Message {i + 1}", value=text, height=height, key=f"{role}_{i}")

    # User input section for conversation with the model at the bottom
    st.write("Enter your question or follow-up:")
    user_input = st.text_input("Your input here:", placeholder="Type your message here...")

    if st.button("Submit"):
        if user_input.strip():
            with st.spinner('Processing...'):
                st.session_state.conversation_history.append(f"User: {user_input}")
                response = asyncio.run(query_ollama_api("llama3.2:latest", st.session_state.conversation_history))
                st.session_state.conversation_history.append(f"Model: {response}")

                # Send the response to the webhook server
                send_to_webhook(response)

            # Rerun the script to update the UI
            st.rerun()

with col2:
    with st.expander("Conversation History", expanded=False):
        for line in st.session_state.conversation_history:
            st.write(line)

        if st.button("Clear Conversation"):
            st.session_state.conversation_history = []
            st.rerun()  # Rerun to update UI after clearing

        if st.button("Download Conversation History"):
            conversation_text = "\n".join(st.session_state.conversation_history)
            st.download_button(
                label="Download as TXT",
                data=conversation_text,
                file_name='conversation_history.txt',
                mime='text/plain'
            )