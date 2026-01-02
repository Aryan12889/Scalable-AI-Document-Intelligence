import os
from app.workers.celery_app import celery_app
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.llms.gemini import Gemini
import qdrant_client
from qdrant_client.http.models import Distance, VectorParams
import base64

# --- Configuration ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LlamaIndex Settings ---
# We need to set the global settings or pass them explicitly
if GEMINI_API_KEY:
    Settings.embed_model = GeminiEmbedding(model_name=os.getenv("EMBEDDING_MODEL", "models/embedding-001"))
    # Semantic splitter needs an embedding model to measure distance
    Settings.node_parser = SemanticSplitterNodeParser(
        buffer_size=1, breakpoint_percentile_threshold=95, embed_model=Settings.embed_model
    )
    Settings.llm = Gemini(model="models/gemini-1.5-pro-latest", api_key=GEMINI_API_KEY) # Needed for potential metadata extraction if added later

# --- Qdrant Client ---
client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

@celery_app.task(bind=True)
def process_document(self, file_content_b64: str, filename: str):
    """
    Process a document: decode, chunk (semantic), embed, and upsert to Qdrant.
    """
    try:
        # 1. Decode content
        content_bytes = base64.b64decode(file_content_b64)
        text = content_bytes.decode("utf-8", errors="ignore") # Simplified for text/md. PDF handling would require pypdf.

        # 2. Create Document
        doc = Document(text=text, metadata={"filename": filename})

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
        index = VectorStoreIndex.from_documents(
            [doc],
            storage_context=storage_context,
            show_progress=True
        )

        return {"status": "success", "filename": filename, "chunks": "processed"}

    except Exception as e:
        # Log error
        print(f"Error processing {filename}: {e}")
        self.retry(exc=e, countdown=10, max_retries=3)
        return {"status": "failure", "error": str(e)}
