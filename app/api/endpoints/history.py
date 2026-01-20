from fastapi import APIRouter, HTTPException, Path, Body, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Any
from app.db import create_session, get_recent_sessions, add_message, get_session_messages, delete_session
import shutil
import os
import pathlib
from qdrant_client import QdrantClient
from qdrant_client.http import models

router = APIRouter()

# --- Models ---
class SessionCreate(BaseModel):
    session_id: str
    title: Optional[str] = "New Chat"

class MessageCreate(BaseModel):
    role: str
    content: str
    sources: Optional[List[dict]] = None

class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str

class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    sources: Optional[List[dict]] = None
    timestamp: str

# --- Helpers ---
def delete_vectors_background(session_id: str):
    """Background task to delete vectors from Qdrant."""
    try:
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", 6333))
        collection = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
        
        if os.getenv("QDRANT_LOCATION"):
             client = QdrantClient(path=os.getenv("QDRANT_LOCATION"))
        else:
             client = QdrantClient(host=host, port=port)
        
        client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=session_id)
                        )
                    ]
                )
            )
        )
        print(f"Background: Deleted vectors for {session_id}")
    except Exception as e:
        print(f"Background Delete Failed for {session_id}: {e}")

# --- Endpoints ---

@router.post("/sessions", response_model=SessionResponse)
def create_chat_session(session: SessionCreate):
    """Create or register a new chat session."""
    try:
        create_session(session.session_id, session.title)
        return SessionResponse(session_id=session.session_id, title=session.title, created_at="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(limit: int = 10):
    """Get list of recent chat sessions."""
    try:
        rows = get_recent_sessions(limit)
        return [SessionResponse(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/messages")
def append_message(
    session_id: str,
    message: MessageCreate
):
    """Append a message to a session."""
    try:
        add_message(session_id, message.role, message.content, message.sources)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
def get_history(session_id: str):
    """Get messsage history for a session."""
    try:
        rows = get_session_messages(session_id)
        return [MessageResponse(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks
):
    """Delete session from DB immediately. Queue Vector delete in background."""
    try:
        # 1. Delete from DB
        delete_session(session_id)
        
        # 2. Delete from Qdrant (Background)
        background_tasks.add_task(delete_vectors_background, session_id)

        # 3. Files are PRESERVED (Rule: Files and Analytics preserved)
        
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        print(f"Delete error: {e}")
        return {"status": "error", "message": str(e)}
