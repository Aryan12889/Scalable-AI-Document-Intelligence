import os
from app.workers.celery_app import celery_app
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.gemini import Gemini
import qdrant_client
from qdrant_client.http.models import Distance, VectorParams
import base64
import tempfile
import pathlib
from llama_index.core import SimpleDirectoryReader

# --- Configuration ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LlamaIndex Settings ---
# We need to set the global settings or pass them explicitly
if GEMINI_API_KEY:
    # Use Local Embeddings to avoid Rate Limits (Dimension: 768 matches Qdrant config)
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
    
    # Use standard Token splitting for better "needle in haystack" retrieval
    Settings.node_parser = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50
    )
    Settings.llm = Gemini(model="models/gemini-2.5-flash", api_key=GEMINI_API_KEY) # Needed for potential metadata extraction if added later

# --- Qdrant Client ---
# Check if running locally (file-based) or server mode
if os.getenv("QDRANT_LOCATION"):
    client = qdrant_client.QdrantClient(path=os.getenv("QDRANT_LOCATION"))
else:
    client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

@celery_app.task(bind=True)
def process_document(self, file_content_b64: str, filename: str):
    """
    Process a document: decode, chunk (semantic), embed, and upsert to Qdrant.
    """
    try:
        # 1. Decode content to Temp File
        content_bytes = base64.b64decode(file_content_b64)
        
        # Create a temp file with the correct extension to help SimpleDirectoryReader
        suffix = pathlib.Path(filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(content_bytes)
            tmp_path = tmp_file.name

        try:
            # 2. Load Document with Metadata (Page Numbers!)
            # SimpleDirectoryReader automatically handles PDF/TXT/MD and extracts 'page_label'
            reader = SimpleDirectoryReader(input_files=[tmp_path], filename_as_id=True)
            documents = reader.load_data()
            
            # Enrich metadata
            for doc in documents:
                doc.metadata["filename"] = filename
                # Ensure page_label exists (default to 1 if missing)
                if "page_label" not in doc.metadata:
                    doc.metadata["page_label"] = "1"
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 3. Setup Qdrant Vector Store
        # Ensure collection exists
        try:
             client.get_collection(QDRANT_COLLECTION)
        except Exception:
             client.create_collection(
                 collection_name=QDRANT_COLLECTION,
                 vectors_config=VectorParams(size=768, distance=Distance.COSINE),
             )

        vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 4. Ingestion Pipeline
        # VectorStoreIndex.from_documents handles the pipeline: splitting -> embedding -> indexing
        # 4. Ingestion Pipeline
        # VectorStoreIndex.from_documents handles the pipeline: splitting -> embedding -> indexing
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )

        return {"status": "success", "filename": filename, "chunks": "processed"}

    except Exception as e:
        # Log error
        print(f"Error processing {filename}: {e}")
        # Only retry if self is actually a Celery task context (check for retry method)
        if hasattr(self, 'retry'):
            self.retry(exc=e, countdown=10, max_retries=3)
        return {"status": "failure", "error": str(e)}
