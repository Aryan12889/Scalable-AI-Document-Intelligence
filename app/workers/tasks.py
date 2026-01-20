import os
from app.workers.celery_app import celery_app
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.google_genai import GoogleGenAI
import qdrant_client
from qdrant_client.http.models import Distance, VectorParams
import base64
import fitz # PyMuPDF
import pathlib

# --- Configuration ---
import logging
logging.basicConfig(filename='ingestion_debug.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LlamaIndex Settings ---
Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-base-en-v1.5")
if GEMINI_API_KEY:
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    # Use standard GoogleGenAI driver
    Settings.llm = GoogleGenAI(model="models/gemini-flash-latest", api_key=GEMINI_API_KEY)

# --- Qdrant Client ---
if os.getenv("QDRANT_LOCATION"):
    client = qdrant_client.QdrantClient(path=os.getenv("QDRANT_LOCATION"))
else:
    client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def ingest_file_logic(file_content_b64: str, filename: str, category: str = "user", session_id: str = None):
    """
    Core ingestion logic, decoupled from Celery for easier local testing/execution.
    """
    logging.info(f"STARTING INGESTION for {filename}, session: {session_id}")
    try:
        # 1. Decode & Persist File
        logging.info("Step 1: Decoding file")
        content_bytes = base64.b64decode(file_content_b64)
        
        # Use relative path for local compatibility (vs Docker /app)
        project_root = pathlib.Path(os.getcwd())
        data_dir = project_root / "data"
        
        if category == "static":
            base_dir = data_dir / "static"
        else:
            if not session_id:
                session_id = "default"
            base_dir = data_dir / "uploads" / session_id
        
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / filename
        with open(file_path, "wb") as f:
            f.write(content_bytes)

        logging.info(f"File saved to {file_path}")

        # 2. Extract Text
        logging.info("Step 2: Extracting Text")
        documents = []
        base_metadata = {
            "filename": filename,
            "category": category,
            "session_id": session_id if session_id else ""
        }
        
        if filename.lower().endswith(".pdf"):
            with fitz.open(file_path) as doc:
                for page in doc:
                    text = page.get_text()
                    meta = base_metadata.copy()
                    meta["page_label"] = str(page.number + 1)
                    documents.append(Document(text=text, metadata=meta))
        else:
            text = content_bytes.decode("utf-8", errors="ignore")
            meta = base_metadata.copy()
            meta["page_label"] = "1"
            documents.append(Document(text=text, metadata=meta))

        logging.info(f"Extracted {len(documents)} document chunks")

        # 3. Setup Qdrant Vector Store
        logging.info("Step 3: Setup Qdrant")
        try:
             client.get_collection(QDRANT_COLLECTION)
        except Exception:
             client.create_collection(
                 collection_name=QDRANT_COLLECTION,
                 vectors_config=VectorParams(size=768, distance=Distance.COSINE),
             )

        vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 4. Ingestion Pipeline
        logging.info("Step 4: Running Ingestion Pipeline (Embedding)...")
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )

        logging.info("SUCCESS: Ingestion Complete")
        return {"status": "success", "filename": filename, "chunks": "processed"}

    except Exception as e:
        logging.error(f"FAILURE: Error processing {filename}: {e}", exc_info=True)
        print(f"Error processing {filename}: {e}")
        raise e

@celery_app.task(bind=True)
def process_document(self, file_content_b64: str, filename: str, category: str = "user", session_id: str = None):
    try:
        return ingest_file_logic(file_content_b64, filename, category, session_id)
    except Exception as e:
        if hasattr(self, 'retry'):
            self.retry(exc=e, countdown=10, max_retries=3)
        return {"status": "failure", "error": str(e)}

@celery_app.task
def run_cleanup_job():
    from app.scripts.cleanup_sessions import cleanup_expired_sessions
    cleanup_expired_sessions()
    return "Cleanup Completed"
