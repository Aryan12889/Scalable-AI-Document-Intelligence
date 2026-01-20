import nest_asyncio
nest_asyncio.apply()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.endpoints import ingest, query, documents, admin, analytics, history
from app.api import dependencies
from app.core.events import lifespan
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(query.router, prefix="/api/v1", tags=["Retrieval"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(dependencies.router, tags=["Health"])

# Serve Static UI (Frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static_ui")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

# Serve Document Files (PDFs)
# Mounted at /files. Resolves to ../data from app/main.py
data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
if os.path.exists(data_dir):
    app.mount("/files", StaticFiles(directory=data_dir), name="files")


@app.get("/api")
def root_api():
    return {"message": "RAG Knowledge Base API is running"}
