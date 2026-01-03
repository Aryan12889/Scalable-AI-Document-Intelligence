import streamlit as st
import requests
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

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar: Knowledge Ingestion ---
with st.sidebar:
    st.markdown("### 📂 Knowledge Base")
    st.markdown("Upload documents to make them searchable.")
    
    with st.container():
        uploaded_files = st.file_uploader("Drop PDF, TXT, MD", type=["pdf", "txt", "md"], accept_multiple_files=True)
        
        if uploaded_files:
            if st.button(f"🚀 Process {len(uploaded_files)} Document(s)", use_container_width=True):
                with st.spinner(f"Ingesting {len(uploaded_files)} document(s)..."):
                    success_count = 0
                    errors = []
                    
                    for uploaded_file in uploaded_files:
                        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                        try:
                            # Reset file pointer for each upload if necessary
                            uploaded_file.seek(0)
                            res = requests.post(f"{ST_API_URL}/upload", files=files)
                            if res.status_code == 200:
                                success_count += 1
                                st.toast(f"✅ Indexed: {uploaded_file.name}", icon="🎉")
                            else:
                                errors.append(f"{uploaded_file.name}: {res.text}")
                        except Exception as e:
                            errors.append(f"{uploaded_file.name}: Connection Failed ({e})")
                    
                    if success_count > 0:
                        st.session_state.messages.append({"role": "assistant", "content": f"I have processed **{success_count}** new document(s). Ready for your questions!"})
                    
                    if errors:
                        error_msg = "**Encountered errors with the following files:**\n" + "\n".join([f"- {e}" for e in errors])
                        st.error(error_msg)
    
    st.divider()
    st.markdown("### 🧠 Debug Info")
    st.caption(f"API Connected: `{ST_API_URL}`")
    if st.button("Clear Chat History", type="secondary"):
        st.session_state.messages = []
        st.experimental_rerun()

# --- Context Modal ---
@st.dialog("📄 Document Context", width="large")
def view_context(filename, page_label):
    st.caption(f"Viewing: {filename} • Page {page_label}")
    
    with st.spinner("Rendering page with high fidelity..."):
        try:
            # We assume page_label is an integer, or convertible
            p_num = int(page_label)
            res = requests.get(f"{ST_API_URL}/documents/{filename}/context", params={"page": p_num})
            
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
    view_context(doc["filename"], doc["page"])
    # Do NOT delete state immediately, dialog handles it.
    # We only delete if we want to force close, which we don't.
    # The dialog function will run and maintain the modal.
    # If the user closes the modal, Streamlit reruns. 
    # To prevent it from reopening immediately, we need to know if it was closed.
    # Current limitation: st.dialog doesn't return "closed" state easily.
    # A safer pattern: Just set the state to None when closed? No.
    # Let's try the SIMPLEST approach: Just call it.
    
    # Actually, standard pattern is:
    # 1. Button click sets state.
    # 2. Check state.
    # 3. Call dialog.
    # 4. Dialog handles "close" by rerun?
    # Let's stick to this, but REMOVE the `del` line which is definitely killing it.

def set_active_doc(fname, page):
    st.session_state["active_doc"] = {"filename": fname, "page": page}

# --- Main Interface ---
st.markdown('<div class="main-header">🧠 RAG Brain</div>', unsafe_allow_html=True)

# Display Chat History
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Render Sources if present (Only for assistant messages)
        if "sources" in message and message["sources"]:
            st.divider()
            st.markdown("**🔍 Sources:**")
            for i, src in enumerate(message["sources"]):
                c1, c2 = st.columns([0.85, 0.15])
                
                score = src.get('score', 0)
                page = src.get('page_label', '?')
                fname = src['filename']
                
                with c1:
                    st.markdown(f"- 📄 `{fname}` (Pg {page}) _(Conf: {score:.2f})_")
                
                with c2:
                    # Use on_click callback
                    btn_key = f"btn_{idx}_{i}_{fname}_{page}"
                    st.button(
                        " View", 
                        key=btn_key, 
                        help="Read full page context",
                        on_click=set_active_doc,
                        args=(fname, page)
                    )

# Chat Input
if prompt := st.chat_input("Ask a question about your documents..."):
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. AI Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("typing...")
        
        try:
            payload = {"query_text": prompt}
            res = requests.post(f"{ST_API_URL}/query", json=payload)
            
            if res.status_code == 200:
                data = res.json()
                answer = data['answer']
                sources = data.get('sources', [])
                
                message_placeholder.markdown(answer)
                
                # Append to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "sources": sources
                })
                
                # Rerun to show sources buttons
                # st.rerun() # No longer needed here, on_click handles reruns
                
            else:
                err_msg = f"⚠️ Error: {res.text}"
                message_placeholder.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
                
        except Exception as e:
            err_msg = f"❌ Connection Failure: {e}"
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
