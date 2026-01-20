import os
from llama_index.core import VectorStoreIndex, Settings, get_response_synthesizer
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.query_engine import TransformQueryEngine
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.llms.google_genai import GoogleGenAI
import qdrant_client

from dotenv import load_dotenv

# Load env immediately
load_dotenv()

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
    
    # Setup LLM
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment.")
            
        # Use GoogleGenAI (updated driver)
        Settings.llm = GoogleGenAI(
            model="models/gemini-flash-latest", 
            api_key=api_key
        )
    except Exception as e:
        print(f"Error initializing Gemini: {e}")

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
                # IS_EMPTY requires a dummy value validation
                MetadataFilter(key="session_id", value="None", operator=FilterOperator.IS_EMPTY),
            ],
            condition=FilterCondition.OR
        )
    else:
        # If no session ID, show static and unassigned
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="category", value="static", operator=FilterOperator.EQ),
                MetadataFilter(key="session_id", value="None", operator=FilterOperator.IS_EMPTY),
            ],
            condition=FilterCondition.OR
        )

    # 5. Retriever: Hybrid Search (if supported by store/client, Qdrant supports it)
    # We use a standard Vector Retriever with High Similarity Top-K 
    # and strong Reranker as the "Advanced RAG" proxy if sparse is too complex for "minutes" deployment.
    
    print(f"DEBUG ENGINE: Session ID: {session_id}")
    if filters:
        print(f"DEBUG ENGINE: Filters: {filters.json()}")
    
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

def generate_chat_title(text: str) -> str:
    """Generate a short title for the chat based on the first internal message."""
    try:
        print(f"DEBUG: Generating title for '{text}'")
        # Check if LLM is actually available
        if not Settings.llm: 
            print("DEBUG: Settings.llm is MISSING")
            return text[:50] + "..." if len(text) > 50 else text
        
        prompt = (
            f"Generate a very short, concise title (max 6 words) for this chat message. "
            f"Do NOT wrap in quotes. Message: '{text}'"
        )
        response = Settings.llm.complete(prompt)
        content = response.text.strip().strip('"')
        
        print(f"DEBUG: Generated Title: '{content}'")
        
        # If response is empty (API key issue or other), fallback
        if not content:
            return text[:50] + "..." if len(text) > 50 else text
            
        return content
    except Exception as e:
        print(f"Title Gen Error: {e}")
        return text[:50] + "..." if len(text) > 50 else text

def generate_session_summary(history_text: str) -> str:
    """Generate an executive summary for the chat session."""
    try:
        print(f"DEBUG: Generating summary for length {len(history_text)}")
        if not Settings.llm: return "History available. Summary generation unavailable."
        
        prompt = (
            f"Summarize this chat session in 2 concise sentences for an executive dashboard. "
            f"Focus on the main topic and key findings. "
            f"If the chat is short, summarize the user's intent. "
            f"\n\nTranscript:\n{history_text}"
        )
        if len(history_text) > 12000: history_text = history_text[-12000:]
        
        response = Settings.llm.complete(prompt)
        content = response.text.strip()
        
        print(f"DEBUG: Generated Summary: '{content}'")
        if not content:
            return "Summary generation pending..."
            
        return content
    except Exception as e:
        print(f"Summary Gen Error: {e}")
        return "Summary unavailable."
            
        return content
            
        return content
    except Exception as e:
        print(f"Summary Gen Error: {e}")
        return "Summary generation failed."
