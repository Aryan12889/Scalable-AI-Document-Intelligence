import streamlit as st
import requests
import uuid
import json
import base64
import os

# --- Configuration ---
ST_API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# --- Page Config ---
st.set_page_config(
    page_title="RAG Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Import Inter Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Minimalist Header */
    .main-header {
        font-weight: 600;
        font-size: 2.5rem;
        color: #1E1E1E;
        margin-bottom: 1rem;
    }

    /* Chat Message Styling */
    .stChatMessage {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    
    /* Upload Section in Sidebar */
    .upload-box {
        border: 1px dashed #ccc;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }

    /* Hide default Streamlit menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- Session State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()
if "uploader_visible" not in st.session_state:
    st.session_state.uploader_visible = True
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

# --- Context Modal ---
@st.dialog("📄 Document Context", width="large")
def view_context(filename, page_label, query_text=None, session_id=None):
    st.caption(f"Viewing: {filename} • Page {page_label}")
    
    with st.spinner("Rendering page with high fidelity..."):
        try:
            # We assume page_label is an integer, or convertible
            p_num = int(page_label)
            # Use passed session_id or fallback to state (but explicit is safer)
            sid = session_id if session_id else st.session_state.get("session_id")
            params = {"page": p_num, "session_id": sid}
            if query_text:
                params["query"] = query_text
                
            res = requests.get(f"{ST_API_URL}/documents/{filename}/context", params=params)

            
            if res.status_code == 200:
                ctx = res.json()
                
                # Tabs for context
                t_prev, t_curr, t_next = st.tabs(["⬅️ Previous Page", "📄 Current Page", "Next Page ➡️"])
                
                def render_page(page_data, role):
                    if not page_data:
                        st.warning("No page data available.")
                        return
                        
                    st.markdown(f"**Page {page_data['number']}**")
                    
                    if "image" in page_data:
                        # Decode base64 image
                        img_bytes = base64.b64decode(page_data["image"])
                        st.image(img_bytes, use_container_width=True)
                    else:
                        # Fallback to text
                        st.info("Image not available, showing text.")
                        st.markdown(page_data.get("text", "No Text Found"))

                with t_prev:
                    if ctx.get("prev_page"):
                        render_page(ctx["prev_page"], "prev")
                    else:
                        st.warning("No previous page (Start of document)")
                        
                with t_curr:
                    render_page(ctx["current_page"], "curr")
                    
                with t_next:
                    if ctx.get("next_page"):
                        render_page(ctx["next_page"], "next")
                    else:
                        st.warning("No next page (End of document)")
            else:
                st.error(f"Could not load context: {res.text}")
        except Exception as e:
            st.error(f"Error fetching context: {e}")

# Call context modal if triggered
if "active_doc" in st.session_state:
    doc = st.session_state["active_doc"]
    q_text = doc.get("text", None)
    sid = st.session_state.get("session_id")
    view_context(doc["filename"], doc["page"], q_text, sid)

def set_active_doc(fname, page, text=None):
    st.session_state["active_doc"] = {"filename": fname, "page": page, "text": text}

# --- Main Layout ---
st.markdown('<div class="main-header">🧠 RAG Brain</div>', unsafe_allow_html=True)

# === SIDEBAR: Knowledge Base ===
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/6009/6009864.png", width=50) # Optional logo placeholder
    st.subheader("📂 Knowledge Base")
    st.caption("Upload documents to make them searchable.")
    
    # Initialize uploader ID for reset functionality
    if "uploader_id" not in st.session_state:
        st.session_state["uploader_id"] = 0

    # Helper to render the uploader logic
    def render_uploader(label="Drop PDF, TXT, MD", visibility="visible", container_border=True, compact=False):
        # Dynamic key based on reset counter
        key = f"uploader_{st.session_state['uploader_id']}"
        
        # Optional: wrapper container
        if container_border:
            wrapper = st.container(border=True)
        else:
            wrapper = st.container()
            
        with wrapper:
            if compact:
                # CSS to Hide the Dropzone Box and Text, showing only the button area
                st.markdown("""
                <style>
                    /* Target the Dropzone container and style IT as the button */
                    [data-testid="stFileUploaderDropzone"] {
                        width: auto !important;
                        height: auto !important;
                        min-height: 40px !important;
                        border-radius: 8px !important; /* Pill/Rounded Rectangle */
                        background-color: #ffffff !important;
                        border: 1px solid #e0e0e0 !important;
                        padding: 8px 16px !important;
                        display: flex !important;
                        justify-content: center !important;
                        align-items: center !important;
                        margin: 0px !important;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
                        cursor: pointer !important;
                    }
                    
                    /* Hide ALL internal elements (instructions, existing buttons, etc.) */
                    [data-testid="stFileUploaderDropzone"] > * {
                        display: none !important;
                    }

                    /* Inject the text and icon into the Dropzone container */
                    [data-testid="stFileUploaderDropzone"]::after {
                        content: '➕ Add More Files' !important;
                        font-size: 14px !important;
                        font-weight: 600 !important;
                        color: #444 !important;
                        display: block !important;
                        line-height: 1 !important;
                    }
                    
                    /* Hover effect */
                    [data-testid="stFileUploaderDropzone"]:hover {
                        border-color: #ff4b4b !important;
                        background-color: #fff5f5 !important;
                        color: #ff4b4b !important;
                    }
                    
                    /* Hover text color change */
                    [data-testid="stFileUploaderDropzone"]:hover::after {
                         color: #ff4b4b !important;
                    }
                </style>
                """, unsafe_allow_html=True)
            
            uploaded_files = st.file_uploader(label, type=["pdf", "txt", "md"], accept_multiple_files=True, key=key, label_visibility=visibility)
            
            if uploaded_files:
                # Filter new files
                new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_files]
                
                # Button is disabled if no new files
                btn_disabled = len(new_files) == 0
                
                # Process Button
                if st.button(f"🚀 Process {len(new_files)} New Document(s)", disabled=btn_disabled, use_container_width=True, key=f"btn_{key}"):
                    with st.spinner("Ingesting..."):
                        success_count = 0
                        errors = []
                        
                        for uploaded_file in new_files:
                            with st.spinner(f"Ingesting {uploaded_file.name}..."):
                                try:
                                    # Prepare multipart form data
                                    files_data = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                                    params = {"session_id": st.session_state["session_id"]}
                                    
                                    uploaded_file.seek(0) # Ensure file pointer is at the beginning
                                    res = requests.post(f"{ST_API_URL}/upload", files=files_data, params=params)
                                    
                                    if res.status_code == 200:
                                        success_count += 1
                                        st.session_state.processed_files.add(uploaded_file.name)
                                        st.toast(f"✅ Indexed: {uploaded_file.name}", icon="🎉")
                                    else:
                                        errors.append(f"{uploaded_file.name}: {res.text}")
                                except Exception as e:
                                    errors.append(f"{uploaded_file.name}: Error ({e})")
                        
                        if success_count > 0:
                            st.session_state.messages.append({"role": "assistant", "content": f"I have processed **{success_count}** new document(s). Ready for questions!"})
                            
                            # Increment uploader ID to reset the widget
                            st.session_state["uploader_id"] += 1
                            st.rerun()
                            
                        if errors:
                            st.error("\n".join(errors))

    # Smart Upload Logic
    if not st.session_state.processed_files:
        # 1. Initial State: Standard View
        render_uploader(label="Drop PDF, TXT, MD", visibility="visible", container_border=True)
    else:
        # 2. Compact State: Direct Browse (No Popover)
        # Minimalist uploader transformed into a "+" button via CSS
        render_uploader(label="Browse to add", visibility="collapsed", container_border=False, compact=True)

    # File List
    if st.session_state.processed_files:
        st.markdown("---")
        st.markdown("**Indexed Documents:**")
        for f in st.session_state.processed_files:
            st.markdown(f"📄 `{f}`")
            
    # Debug & Utilities
    st.divider()
    st.markdown("### 🧠 Debug Info")
    st.caption(f"API Connected: `{ST_API_URL}`")
    if st.button("Clear Chat History", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# === MAIN AREA: Chat Interface ===

# Display Chat History
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Render Sources (if any)
        if "sources" in message and message["sources"]:
            st.divider()
            st.markdown("**🔍 Sources:**")
            for i, src in enumerate(message["sources"]):
                c1, c2 = st.columns([0.85, 0.15])
                score = src.get('score', 0)
                page = src.get('page_label', '?')
                fname = src['filename']
                ctx_text = src.get('text', None) 

                with c1:
                    st.markdown(f"- 📄 `{fname}` (Pg {page}) _(Conf: {score:.2f})_")
                
                with c2:
                    btn_key = f"btn_{idx}_{i}_{fname}_{page}"
                    st.button(
                        " View", 
                        key=btn_key, 
                        help="Read full page context",
                        on_click=set_active_doc,
                        args=(fname, page, ctx_text)
                    )

# Chat Input
if prompt := st.chat_input("Ask about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Pass session_id for isolation
                payload = {
                    "query_text": prompt,
                    "session_id": st.session_state.get("session_id")
                }
                res = requests.post(
                    f"{ST_API_URL}/query", 
                    json=payload
                )
                
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "No answer found.")
                    sources = data.get("sources", [])
                    
                    st.markdown(answer)
                    
                    if sources:
                        st.markdown("---")
                        st.markdown("### 📚 Sources")
                        # Updated Source Rendering (Compact & Clickable)
                        for idx, src in enumerate(sources[:3]):
                            fname = src.get('filename')
                            page = src.get('page_label')
                            score = src.get('score', 0)
                            text = src.get('text', "") # Get text for highlighting
                            
                            # Create columns for better alignment
                            c1, c2 = st.columns([0.8, 0.2])
                            with c1:
                                st.caption(f"**{fname}** (Page {page}) • {score:.2f}")
                            with c2:
                                if st.button("🔍 Context", key=f"src_{idx}"):
                                    view_context(fname, page, query_text=prompt, session_id=st.session_state.get("session_id"))

                    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
                else:
                    err_msg = f"Error: {res.status_code} - {res.text}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except Exception as e:
                st.error(f"Failed to connect: {e}")
