from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.rag.engine import get_rag_engine

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

@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    try:
        # Get the query engine with retrieval AND session filtering
        # Pass session_id to engine creation
        query_engine = get_rag_engine(session_id=request.session_id)
        
        # Explicit search to get nodes (we need metadata)
        response = query_engine.query(request.query_text)
        
        # Process and Deduplicate Sources
        # Group by (filename, page_label) -> Keep highest score
        unique_sources = {}
        
        for node in response.source_nodes:
            # LlamaIndex nodes have metadata
            meta = node.metadata
            filename = meta.get("filename", "unknown")
            page = meta.get("page_label", "1")
            score = node.score if node.score else 0.0
            content = node.text # The actual content for highlighting
            
            key = (filename, page)
            
            # Logic: If key not in unique_sources or current score is higher
            if key not in unique_sources or score > unique_sources[key]["score"]:
                unique_sources[key] = {
                    "filename": filename,
                    "page_label": page,
                    "text": content,
                    "score": score
                }
        
        # Convert back to list and sort by score desc
        sources_list = sorted(unique_sources.values(), key=lambda x: x["score"], reverse=True)
        
        return {
            "answer": str(response),
            "sources": sources_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
