from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.rag.engine import get_rag_engine

router = APIRouter()

class QueryRequest(BaseModel):
    query_text: str

class SourceNode(BaseModel):
    filename: str
    score: float
    text: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceNode]

@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    try:
        engine = get_rag_engine()
        response = engine.query(request.query_text)
        
        sources = []
        for node in response.source_nodes:
            # Metadata might be None if not found
            fname = node.metadata.get("filename", "unknown") if node.metadata else "unknown"
            sources.append(SourceNode(
                filename=fname,
                score=node.score if node.score else 0.0,
                text=node.node.get_content()[:200] + "..." # Snippet
            ))
            
        return {
            "answer": str(response),
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
