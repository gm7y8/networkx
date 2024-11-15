import streamlit as st
import httpx
import requests
import pyshark
import pandas as pd
import asyncio
import os
import io

# Webhook URL where you want to send the data
WEBHOOK_URL = "https://webhook.site/e81a4e42-1586-4c39-8667-833c7e97c6b8"

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
            data = response.json( )
            tim
            return 
            #return data.get("response", "No output received from model.")
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
    st.session_state.processing = True  # Set processing state

    with st.spinner("Processing uploaded files..."):
        for i, uploaded_file in enumerate(uploaded_files):
            st.write(f"Processing file {i + 1}/{len(uploaded_files)}: {uploaded_file.name}")
            progress = st.progress(0)

            try:
                # Determine file extension
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()

                # Check if the file is a supported PCAP format or a renamed pcap.txt
                if file_extension in ['.pcap', '.cap'] or uploaded_file.name.endswith('pcap.txt'):
                    with open("temp.pcap", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    capture = pyshark.FileCapture("temp.pcap")
                    capture.set_debug()  # Enable debugging

                    packets = []
                    for idx, packet in enumerate(capture):
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
                        progress.progress(min((idx + 1) / 100, 1.0))  # Update progress bar

                        if idx >= 99:  # Limit to 100 progress updates
                            break
                    capture.close()
                    df = pd.DataFrame(packets)
                    st.dataframe(df)
                    st.session_state.conversation_history.append(f"PCAP Summary: {df.head().to_string()}")

                # Handle JSON files
                elif file_extension == '.json':
                    content = uploaded_file.read().decode('utf-8')
                    json_content = pd.read_json(io.StringIO(content))
                    st.dataframe(json_content)
                    st.session_state.conversation_history.append(f"JSON Content: {json_content.head().to_string()}")

                # Handle CSV files
                elif file_extension == '.csv':
                    content = uploaded_file.read().decode('utf-8')
                    csv_content = pd.read_csv(io.StringIO(content))
                    st.dataframe(csv_content)
                    st.session_state.conversation_history.append(f"CSV Content: {csv_content.head().to_string()}")

                # Handle PSV files
                elif file_extension == '.psv':
                    content = uploaded_file.read().decode('utf-8')
                    psv_content = pd.read_csv(io.StringIO(content), sep='|')
                    st.dataframe(psv_content)
                    st.session_state.conversation_history.append(f"PSV Content: {psv_content.head().to_string()}")

                else:
                    st.warning(f"File {uploaded_file.name} is not a supported format. Skipping.")
                    continue

                progress.progress(100)

            except Exception as e:
                st.error(f"Failed to process file: {e}")

    st.session_state.processing = False  # Reset processing state
    st.success("Processing done!")  # Indicate processing completion

# Streamlit UI Layout
st.title("AI Powered Network Insights​")

# Sidebar for File Type Selection and Upload
st.sidebar.subheader("Select File Types")
file_types = st.sidebar.multiselect(
    "Choose file types to upload", 
    options=["json", "psv", "cap", "snmp", "tdl", "pcap"],
)

st.sidebar.subheader("Upload Files")
uploaded_files = st.sidebar.file_uploader(
    "Choose files", 
    type=file_types,  # Use selected file types for filtering
    accept_multiple_files=True
)

if uploaded_files:
    process_files(uploaded_files)

# Display Chat History and Input Together
chat_container = st.container()
with chat_container:
    st.subheader("Chat History")

    # Grey out the chat window if processing
    if st.session_state.processing:
        st.markdown("<style>div.stContainer { opacity: 0.5; pointer-events: none; }</style>", unsafe_allow_html=True)

    for message in st.session_state.conversation_history:
        if "User:" in message:
            st.chat_message("user").markdown(message.replace("User: ", ""))
        elif "Model:" in message:
            st.chat_message("assistant").markdown(message.replace("Model: ", ""))

    # Input and Submit Button in a Single Row
    st.subheader("Your Input")
    chat_input_col1, chat_input_col2 = st.columns([5, 1], gap="small")
    with chat_input_col1:
        user_input = st.text_input("Type your message here:", key="chat_input", label_visibility="collapsed", disabled=st.session_state.processing)
    with chat_input_col2:
        submit_button = st.button("Submit", use_container_width=True, key="chat_submit", disabled=st.session_state.processing)

# Handle User Input Submission
if submit_button and user_input:
    with st.spinner('Thinking...'):
        st.session_state.conversation_history.append(f"User: {user_input}")

        # Limit conversation history size
        st.session_state.conversation_history = st.session_state.conversation_history[-MAX_HISTORY:]

        # Get response from the Ollama API
        response = asyncio.run(query_ollama_api("llama3.2:latest", st.session_state.conversation_history))
        st.session_state.conversation_history.append(f"Model: {response}")

        # Send the response to the webhook server
        send_to_webhook(response)

    # Scroll to the bottom of the chat by re-running the script
    st.rerun()

# Clear Conversation Button
clear_button = st.button("Clear Conversation", disabled=st.session_state.processing)
if clear_button:
    st.session_state.conversation_history = []
    st.rerun()