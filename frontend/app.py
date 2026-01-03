import streamlit as st
import requests
import json
import os

ST_API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="RAG Brain", layout="wide")
st.write(f"DEBUG: API URL is {ST_API_URL}")

st.title("🧠 RAG Knowledge Base")

tab1, tab2 = st.tabs(["📂 Upload Knowledge", "💬 Chat"])

with tab1:
    st.header("Ingest Documents")
    uploaded_file = st.file_uploader("Upload PDF, TXT, MD", type=["pdf", "txt", "md"])
    if st.button("Upload & Process") and uploaded_file:
        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
        try:
            res = requests.post(f"{ST_API_URL}/upload", files=files)
            if res.status_code == 200:
                st.success(f"Uploaded! Task ID: {res.json().get('task_id')}")
            else:
                st.error(f"Error: {res.text}")
        except Exception as e:
            st.error(f"Connection Error: {e}")

with tab2:
    st.header("Ask the Knowledge Base")
    query_text = st.text_input("Enter your query:")
    if st.button("Search") and query_text:
        with st.spinner("Thinking... (HyDE + Reranking in progress)"):
            try:
                payload = {"query_text": query_text}
                res = requests.post(f"{ST_API_URL}/query", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    st.markdown(f"### Answer\n{data['answer']}")
                    
                    st.divider()
                    st.subheader("Sources")
                    for src in data['sources']:
                        page_info = f" (Page {src['page_label']})" if src.get('page_label') else ""
                        with st.expander(f"{src['filename']}{page_info} - Score: {src['score']:.2f}"):
                            st.text(src['text'])
                else:
                    st.error(f"Error: {res.text}")
            except Exception as e:
                st.error(f"Connection Error: {e}")
