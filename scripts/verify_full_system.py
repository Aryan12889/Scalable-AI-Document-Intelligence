import os
import sys
import shutil
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())
load_dotenv()

from app.rag.engine import get_rag_engine
from llama_index.core import Document

def verify_system():
    print("==========================================")
    print("       FULL SYSTEM DIAGNOSTIC CHECK       ")
    print("==========================================")

    # 1. LLM CHECK
    print("\n[1] Checking LLM Connectivity (via RAG Engine init)...")
    try:
        engine = get_rag_engine()
        print("SUCCESS: RAG Engine Initialized.")
    except Exception as e:
        print(f"FAILED: Could not initialize RAG Engine. Error: {e}")
        return

    # 2. INGESTION & VECTOR STORE CHECK
    print("\n[2] Checking Ingestion & Vector Store...")
    try:
        # Create a dummy unique document
        test_text = "The code word for the mission is 'Thunderbird'. This is a secret."
        doc = Document(text=test_text, metadata={"filename": "test_verification.txt", "category": "static"})
        
        print("   - Indexing test document...")
        # Access the index from the engine's retriever if possible, or just build a fresh one on same store
        # engine is a RetrieverQueryEngine. retriever is a VectorIndexRetriever.
        # retriever.index is the VectorStoreIndex.
        
        retriever = engine.retriever
        index = retriever._index
        
        index.insert(doc)
        print("SUCCESS: Document Ingested into Qdrant.")
    except Exception as e:
        print(f"FAILED: Ingestion failed. Error: {e}")
        return

    # 3. RAG QUERY CHECK
    print("\n[3] Checking RAG Query Performance...")
    try:
        query = "What is the code word for the mission?"
        print(f"   - Querying: '{query}'")
        
        response = engine.query(query)
        print(f"   - Raw Response: {response}")
        
        if "Thunderbird" in str(response):
            print("SUCCESS: RAG retrieved correct information.")
            print(f"   - Source Node Score: {response.source_nodes[0].score}")
        else:
            print("WARNING: RAG did not return expected content. Check retrieval.")
            print(f"   - Actual Response: {str(response)}")
            
    except Exception as e:
        print(f"FAILED: Query execution failed. Error: {e}")
        return

    print("\n==========================================")
    print("       DIAGNOSTIC COMPLETE: ALL GREEN     ")
    print("==========================================")

if __name__ == "__main__":
    verify_system()
