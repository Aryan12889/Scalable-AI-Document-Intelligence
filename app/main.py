from fastapi import FastAPI
from app.api.endpoints import ingest, query
from app.api import dependencies
from app.core.events import lifespan
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

app.include_router(ingest.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(query.router, prefix="/api/v1", tags=["Retrieval"])
app.include_router(dependencies.router, tags=["Health"])

@app.get("/")
def root():
    return {"message": "RAG Knowledge Base API is running"}
