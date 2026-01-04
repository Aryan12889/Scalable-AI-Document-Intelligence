import os
from llama_index.core import VectorStoreIndex, Settings, get_response_synthesizer
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.query_engine import TransformQueryEngine
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.llms.gemini import Gemini
import qdrant_client

# --- Config ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator, FilterCondition

def get_rag_engine(session_id: str = None):
    # 1. Setup Client & Store
    if os.getenv("QDRANT_LOCATION"):
        client = qdrant_client.QdrantClient(path=os.getenv("QDRANT_LOCATION"))
    else:
        client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
    vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
    
    # 2. Setup Embeddings & LLM
    # Always use FastEmbed to avoid Torch dependency fallback
    embed_model = FastEmbedEmbedding(model_name="BAAI/bge-base-en-v1.5")
    Settings.embed_model = embed_model
    
    if GEMINI_API_KEY:
        Settings.llm = Gemini(model="models/gemini-2.5-flash", api_key=GEMINI_API_KEY)
    else:
        print("WARNING: GEMINI_API_KEY not found. LLM might fail.")

    # 3. Create Index (from existing store)
    # Pass embed_model explicitly to avoid any global Settings fallback
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=embed_model)

    # 4. Construct Filters
    # Logic: Search "static" files OR "user" files belonging to this session
    filters = None
    if session_id:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="category", value="static", operator=FilterOperator.EQ),
                MetadataFilter(key="session_id", value=session_id, operator=FilterOperator.EQ),
            ],
            condition=FilterCondition.OR
        )
    else:
        # If no session ID, only show static files
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="category", value="static", operator=FilterOperator.EQ)
            ]
        )

    # 5. Retriever: Hybrid Search (if supported by store/client, Qdrant supports it)
    # We use a standard Vector Retriever with High Similarity Top-K 
    # and strong Reranker as the "Advanced RAG" proxy if sparse is too complex for "minutes" deployment.
    
    vector_retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=20,  # Increase to 20 to cast a wider net
        filters=filters # Apply the session isolation filters
    )

    # 6. Response Synthesizer
    response_synthesizer = get_response_synthesizer()

    # 7. Base Query Engine
    query_engine = RetrieverQueryEngine(
        retriever=vector_retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=[], # No heavy reranker for Turbo mode
    )

    return query_engine
