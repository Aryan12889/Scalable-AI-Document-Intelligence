import os
import uvicorn
import threading
import asyncio
from dotenv import load_dotenv

# 1. Force Local Environment Variables
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333" # Not used if location set to path on disk
os.environ["QDRANT_LOCATION"] = "./qdrant_data" # Local disk storage
os.environ["REDIS_URL"] = "redis://mock" # Bypass
os.environ["CELERY_BROKER_URL"] = "redis://mock"

# Load secrets
load_dotenv()

# 2. Patch config/tasks to support local execution
# We will create a small runner that patches the celery task to just run in a thread
from app.workers import tasks as worker_tasks

def start_local_server():
    print("Starting RAG Knowledge Base in LOCAL DEV MODE")
    print("Using local Qdrant storage at ./qdrant_data")
    print("Bypassing Celery/Redis for simple threading")
    
    # Run FastAPI
    # reload=False is required for local Qdrant file locking (multiprocessing issue)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start_local_server()
