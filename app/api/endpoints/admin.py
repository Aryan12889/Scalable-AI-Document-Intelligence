from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import os
import sys
import subprocess
from app.scripts.cleanup_sessions import cleanup_expired_sessions

router = APIRouter()

@router.post("/cleanup", summary="Trigger Physical Cleanup of Expired Sessions")
async def trigger_cleanup(background_tasks: BackgroundTasks):
    """
    Manually trigger the cleanup of expired session files and vectors.
    Runs in the background.
    """
    # We run the function directly in background task
    background_tasks.add_task(cleanup_expired_sessions)
    return {"status": "Cleanup task started in background."}

# Robust Path Resolution (Duplicated from documents.py for self-containment)
import pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
if not DATA_DIR.exists() and pathlib.Path("/app/data").exists():
    DATA_DIR = pathlib.Path("/app/data")

def get_directory_size(path):
    total = 0
    try:
        if not path.exists():
            return 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception as e:
        print(f"Error calculating size: {e}")
    return total

def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 1)
    return f"{s}{size_name[i]}"

@router.get("/storage", summary="Get Storage Usage")
async def get_storage_usage():
    """
    Get current storage usage with formatted units.
    Limit is 5GB.
    """
    used_bytes = get_directory_size(DATA_DIR)
    total_bytes = 5 * 1024 * 1024 * 1024 # 5 GB
    
    return {
        "used_bytes": used_bytes,
        "total_bytes": total_bytes,
        "used_gb": round(used_bytes / (1024**3), 2),
        "total_gb": 5,
        "used_formatted": format_size(used_bytes),
        "percentage": round((used_bytes / total_bytes) * 100, 1)
    }
