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
