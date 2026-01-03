import os
from app.workers.celery_app import celery_app
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.gemini import Gemini
import qdrant_client
from qdrant_client.http.models import Distance, VectorParams
import base64
import fitz # PyMuPDF
import pathlib

# --- Configuration ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LlamaIndex Settings ---
# We need to set the global settings or pass them explicitly
# Always use FastEmbed (ONNX) for 5x faster CPU inference
Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-base-en-v1.5")

if GEMINI_API_KEY:
    
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
        # 1. Decode & Persist File
        content_bytes = base64.b64decode(file_content_b64)
        
        # Ensure upload directory exists
        upload_dir = pathlib.Path("/app/data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / filename
        with open(file_path, "wb") as f:
            f.write(content_bytes)

        # 2. Extract Text using PyMuPDF (Turbo Mode)
        documents = []
        if filename.lower().endswith(".pdf"):
            with fitz.open(file_path) as doc:
                for page in doc:
                    text = page.get_text()
                    # Create LlamaIndex Document
                    # Metadata for citation and context retrieval
                    llama_doc = Document(
                        text=text, 
                        metadata={
                            "filename": filename,
                            "page_label": str(page.number + 1)
                        }
                    )
                    documents.append(llama_doc)
        else:
            # Fallback for TXT/MD
            text = content_bytes.decode("utf-8", errors="ignore")
            documents.append(Document(text=text, metadata={"filename": filename, "page_label": "1"}))

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
