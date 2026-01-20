
import os
from dotenv import load_dotenv
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator, FilterCondition
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.core import VectorStoreIndex
import qdrant_client

load_dotenv()

def verify():
    print("Connecting to Qdrant...")
    client = qdrant_client.QdrantClient(host="localhost", port=6333)
    vector_store = QdrantVectorStore(client=client, collection_name="knowledge_base")
    # Try bge-base (768 dim)
    embed_model = FastEmbedEmbedding(model_name="BAAI/bge-base-en-v1.5")
    
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=embed_model)
    retriever = index.as_retriever(similarity_top_k=5)
    
    # CASE 1: Session Exists (Simulate user in a chat)
    print("\n--- TEST 1: Session '123' Active ---")
    session_id = "123"
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="category", value="static", operator=FilterOperator.EQ),
            MetadataFilter(key="session_id", value=session_id, operator=FilterOperator.EQ),
            MetadataFilter(key="session_id", value="None", operator=FilterOperator.IS_EMPTY),
        ],
        condition=FilterCondition.OR
    )
    

    
    retriever = index.as_retriever(similarity_top_k=5, filters=filters)
    query_str = "Real-Time Detection and Monitoring of PPE Kit Compliance in Construction Sites"
    print(f"Querying: {query_str}")
    nodes = retriever.retrieve(query_str)

    print(f"Retrieved {len(nodes)} nodes.")
    for n in nodes:
        print(f" - Found: {n.metadata.get('filename')} | Session: {n.metadata.get('session_id')} | Category: {n.metadata.get('category')}")

    # CASE 2: No Session (Simulate Fresh Chat / Global Search)
    print("\n--- TEST 2: No Session (Global) ---")
    filters_global = MetadataFilters(
        filters=[
            MetadataFilter(key="category", value="static", operator=FilterOperator.EQ),
            MetadataFilter(key="session_id", value="None", operator=FilterOperator.IS_EMPTY),
        ],
        condition=FilterCondition.OR
    )
    retriever_global = index.as_retriever(similarity_top_k=5, filters=filters_global)
    nodes = retriever_global.retrieve("Project Report")
    print(f"Retrieved {len(nodes)} nodes.")
    for n in nodes:
        print(f" - Found: {n.metadata.get('filename')} | Session: {n.metadata.get('session_id')} | Category: {n.metadata.get('category')}")

if __name__ == "__main__":
    verify()
