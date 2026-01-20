from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List
import time
from app.rag.engine import get_rag_engine, generate_chat_title, generate_session_summary
from app.db import log_query, init_db, get_session_messages, update_session_title, update_session_summary, get_recent_sessions

# Ensure DB is created on import (or handle in main lifespan)
init_db()

router = APIRouter()

class QueryRequest(BaseModel):
    query_text: str
    session_id: str = None

class SourceNode(BaseModel):
    filename: str
    page_label: str
    score: float
    text: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceNode]
    confidence_score: float = 0.0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

def process_smart_metadata(session_id: str, user_query: str):
    """Background task to generate title and summary."""
    try:
        # 1. Check if we need to generate a title
        # We only do this if title is "New Chat" (default). 
        # We can fetch session to check, or just do it if message count is low.
        # Efficient way: Fetch session (we need to anyway for summary).
        curr_sessions = get_recent_sessions(limit=50) # Assuming active is recent
        session = next((s for s in curr_sessions if s['session_id'] == session_id), None)
        
        # If title is New Chat or missing
        if session and (session['title'] == "New Chat" or not session['title']):
            new_title = generate_chat_title(user_query)
            update_session_title(session_id, new_title)
            print(f"Updated Title: {new_title}")

        # 2. Generate Summary
        # Fetch full history
        msgs = get_session_messages(session_id)
        if msgs:
            # Format history for LLM
            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in msgs])
            summary = generate_session_summary(history_text)
            update_session_summary(session_id, summary)
            print(f"Updated Summary for {session_id}")

    except Exception as e:
        print(f"Smart Metadata Error: {e}")

@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    
    try:
        # Get the query engine with retrieval AND session filtering
        # Pass session_id to engine creation
        query_engine = get_rag_engine(session_id=request.session_id)
        
        # Explicit search to get nodes (we need metadata)
        response = query_engine.query(request.query_text)
        
        # DEBUG: Print response
        print("DEBUG RAW RESPONSE:", response)
        print("DEBUG STR RESPONSE:", str(response))
        if hasattr(response, 'source_nodes'):
            print(f"DEBUG source_nodes count: {len(response.source_nodes)}")
            for idx, node in enumerate(response.source_nodes):
                print(f"  Node {idx}: score={node.score}, text_len={len(node.text)}")
        else:
            print("DEBUG: No source_nodes attribute on response (StreamingResponse?)")
        
        # Extract sources
        sources = []
        if hasattr(response, 'source_nodes'):
            for node in response.source_nodes:
                sources.append(SourceNode(
                    filename=node.metadata.get('filename', 'unknown'),
                    page_label=node.metadata.get('page_label', '1'),
                    score=node.score or 0.0,
                    text=node.text
                ))
        
        # Calculate Latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Get Confidence Score (Top 1)
        confidence_score = sources[0].score if sources else 0.0
        
        # Calculate Token Estimates (Approximation: 1 token ~= 4 chars)
        input_tokens = len(request.query_text) // 4
        output_tokens = len(str(response)) // 4
        
        # Trigger Background Tasks (Title/Description)
        # Only if session_id is present
        if request.session_id:
            print(f"DEBUG: Triggering Smart Metadata for {request.session_id}")
            background_tasks.add_task(process_smart_metadata, request.session_id, request.query_text)
            
        final_answer = str(response)
        
        # Robust Empty Check: If no sources were found, the answer is likely hallucinated or "Empty Response"
        if not sources or "Empty Response" in final_answer:
             final_answer = (
                 "I couldn't find specific details about that in your uploaded documents. "
                 "Try uploading the relevant file (e.g., Project Report) to this chat or ask a general question."
             )
             
        # Serialize sources for DB
        sources_list = [s.dict() for s in sources]

        # Log to DB
        log_query(
            session_id=request.session_id,
            query_text=request.query_text,
            answer_text=final_answer,
            sources=sources_list,
            confidence_score=confidence_score,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        print(f"DEBUG: Returning response with {len(sources_list)} sources.")
        return QueryResponse(
            answer=final_answer,
            sources=sources, # Pydantic handles conversion
            confidence_score=confidence_score,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
