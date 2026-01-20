from fastapi import APIRouter
from app.core.config import settings
import redis
import qdrant_client
import os
import os
# import google.generativeai as genai # REMOVED: Deprecated and unused here

router = APIRouter()

@router.get("/health")
def health_check():
    status = {"status": "ok", "services": {}}
    
    # Redis
    try:
        r = redis.from_url(settings.REDIS_URL.replace("redis://redis", "redis://localhost") if "localhost" in settings.REDIS_URL else settings.REDIS_URL)
        r.ping()
        status["services"]["redis"] = "up"
    except Exception as e:
        status["services"]["redis"] = f"down: {e}"
        status["status"] = "degraded"

    # Qdrant
    try:
        q = qdrant_client.QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        q.get_collections()
        status["services"]["qdrant"] = "up"
    except Exception as e:
        status["services"]["qdrant"] = f"down: {e}"
        status["status"] = "degraded"

    # Gemini (Optional - just check if API key is present)
    if settings.GEMINI_API_KEY:
        status["services"]["gemini"] = "configured"
    else:
        status["services"]["gemini"] = "missing_key"

    return status
