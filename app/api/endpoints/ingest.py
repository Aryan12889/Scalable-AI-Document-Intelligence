from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query, BackgroundTasks
from app.models.schemas import IngestResponse
from app.workers.tasks import process_document, ingest_file_logic, celery_app
from app.core.config import settings
import base64
import redis

import logging
# Ensure logging is set up here too, or relies on root logger if configured elsewhere
logging.basicConfig(filename='ingestion_debug.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()
try:
    redis_client = redis.from_url(settings.REDIS_URL.replace("redis://redis", "redis://localhost") if "localhost" in settings.REDIS_URL else settings.REDIS_URL)
except Exception:
    redis_client = None # Run without Redis

def check_backpressure():
    if not redis_client or "mock" in settings.REDIS_URL:
        return # Skip check in local mode
    
    # Simple check: length of the celery queue
    try:
        queue_len = redis_client.llen("celery")
        if queue_len > 50:
            raise HTTPException(status_code=503, detail="System busy. Ingestion queue full.")
    except Exception as e:
        pass

# Wrapper to run Celery task logic synchronously in a thread (for local mode)
def run_ingestion_sync(file_content_b64, filename, category, session_id):
    logging.info(f"Background Task Started: {filename}")
    try:
        ingest_file_logic(file_content_b64, filename, category, session_id)
        print(f"Local Ingestion Complete for {filename}")
    except Exception as e:
        print(f"Local Ingestion Failed for {filename}: {e}")

@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Browser Session ID for isolation")
):
    """
    Upload a document (PDF, TXT, MD) for ingestion.
    """
    logging.info(f"API Request Received: {file.filename} (Session: {session_id})")
    check_backpressure()
    
    if not file.filename.endswith(('.txt', '.md', '.pdf')):
        raise HTTPException(status_code=400, detail="Only .txt, .md, .pdf files supported")

    content = await file.read()
    file_content_b64 = base64.b64encode(content).decode('utf-8')
    
    # Check if running in local mode (Redis mock)
    if not redis_client or "mock" in settings.REDIS_URL:
        # Local mode: Use BackgroundTasks to run in a thread, returning immediately.
        # This fixes the UI hanging issue.
        logging.info("Dispatching to Local Background Thread")
        background_tasks.add_task(run_ingestion_sync, file_content_b64, file.filename, "user", session_id)
        task_id = "local-background"
    else:
        logging.info("Dispatching to Celery")
        task = process_document.delay(file_content_b64, file.filename, "user", session_id)
        task_id = task.id
    
    return {
        "task_id": task_id,
        "filename": file.filename,
        "message": "File queued for ingestion"
    }
