from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from app.models.schemas import IngestResponse
from app.workers.tasks import process_document, celery_app
from app.core.config import settings
import base64
import redis

router = APIRouter()
try:
    redis_client = redis.from_url(settings.REDIS_URL.replace("redis://redis", "redis://localhost") if "localhost" in settings.REDIS_URL else settings.REDIS_URL)
except Exception:
    redis_client = None # Run without Redis

def check_backpressure():
    if not redis_client or "mock" in settings.REDIS_URL:
        return # Skip check in local mode
    
    # Simple check: length of the celery queue
    # Note: Accurately checking Celery queue length can be complex depending on broker.
    # For Redis:
    try:
        queue_len = redis_client.llen("celery")
        if queue_len > 50:
            raise HTTPException(status_code=503, detail="System busy. Ingestion queue full.")
    except Exception as e:
        # If redis check fails, we might warn but proceed or fail safe
        pass

@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Browser Session ID for isolation")
):
    """
    Upload a document (PDF, TXT, MD) for ingestion.
    """
    check_backpressure()
    
    if not file.filename.endswith(('.txt', '.md', '.pdf')):
        raise HTTPException(status_code=400, detail="Only .txt, .md, .pdf files supported")

    content = await file.read()
    file_content_b64 = base64.b64encode(content).decode('utf-8')
    
    # Check if running in local mode (Redis mock)
    if "mock" in settings.REDIS_URL or not redis_client:
        # Local mode direct execution
        process_document.apply(args=[file_content_b64, file.filename, "user", session_id])
        task_id = "local-task"
    else:
        task = process_document.delay(file_content_b64, file.filename, "user", session_id)
        task_id = task.id
    
    return {
        "task_id": task_id,
        "filename": file.filename,
        "message": "File queued for ingestion"
    }
