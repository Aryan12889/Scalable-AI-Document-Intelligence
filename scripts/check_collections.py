
import qdrant_client

def list_cols():
    try:
        client = qdrant_client.QdrantClient(host="localhost", port=6333)
        cols = client.get_collections()
        print("Collections:")
        for c in cols.collections:
            print(f" - {c.name}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_cols()
