from fastapi import APIRouter, HTTPException, Query
from typing import List
from pydantic import BaseModel
import datetime
import fitz # PyMuPDF
import pathlib
import base64
import os

router = APIRouter()

# Robust Path Resolution
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent # app/api/endpoints -> app -> root
DATA_DIR = BASE_DIR / "data"

# Fallback for Docker/Production if needed, but relative path is safer for hybrid
if not DATA_DIR.exists() and pathlib.Path("/app/data").exists():
    DATA_DIR = pathlib.Path("/app/data")

UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = DATA_DIR / "static"

class DocumentResponse(BaseModel):
    filename: str
    size: int
    upload_date: str
    session_id: str
    status: str

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents():
    """List all uploaded documents (uploads and static)."""
    print(f"DEBUG: Scanning for documents...")
    print(f"DEBUG: BASE_DIR: {BASE_DIR}")
    print(f"DEBUG: DATA_DIR: {DATA_DIR} (Exists: {DATA_DIR.exists()})")
    print(f"DEBUG: UPLOAD_DIR: {UPLOAD_DIR} (Exists: {UPLOAD_DIR.exists()})")
    print(f"DEBUG: STATIC_DIR: {STATIC_DIR} (Exists: {STATIC_DIR.exists()})")
    
    docs = []
    
    # 1. Scan Static Files (Permanent)
    if STATIC_DIR.exists():
        for file_path in STATIC_DIR.iterdir():
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    docs.append(DocumentResponse(
                        filename=file_path.name,
                        size=stat.st_size,
                        upload_date=datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                        session_id="static", # Special ID for static files
                        status="Ready"
                    ))
                except Exception as e:
                    print(f"Error reading static file {file_path}: {e}")

    # 2. Scan Uploads (Session-based)
    if UPLOAD_DIR.exists():
        for session_dir in UPLOAD_DIR.iterdir():
            if session_dir.is_dir():
                session_id = session_dir.name
                for file_path in session_dir.iterdir():
                    if file_path.is_file():
                        try:
                            stat = file_path.stat()
                            docs.append(DocumentResponse(
                                filename=file_path.name,
                                size=stat.st_size,
                                upload_date=datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                                session_id=session_id,
                                status="Processed"
                            ))
                        except Exception as e:
                            print(f"Error reading upload file {file_path}: {e}")
                            
    return docs

@router.get("/documents/{filename}/context")
async def get_document_context(
    filename: str, 
    page: int = Query(..., description="1-based page number"),
    query: str = Query(None, description="Text to highlight"),
    session_id: str = Query(None, description="Session ID for isolated files")
):
    # Logic: Check Session -> Check Static -> 404
    file_path = None
    
    # 1. Try Session Path
    if session_id:
        session_path = UPLOAD_DIR / session_id / filename
        if session_path.exists():
            file_path = session_path
            
    # 2. Try Static Path (Fallback)
    if not file_path:
        static_path = pathlib.Path("/app/data/static") / filename
        if static_path.exists():
            file_path = static_path
            
    if not file_path or not file_path.exists():
        # Debug info for user
        raise HTTPException(status_code=404, detail=f"Document not found. Checked session '{session_id}' and static.")
    
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        # Adjust 1-based page to 0-based index
        current_idx = page - 1
        
        if current_idx < 0 or current_idx >= total_pages:
             raise HTTPException(status_code=400, detail=f"Page {page} out of range")
             
        def get_page_data(idx):
            if 0 <= idx < total_pages:
                pg = doc[idx]
                text = pg.get_text()
                
                # Highlighting Logic
                if query:
                    # Robust Search Strategy
                    # 1. Try Exact Match first
                    quads = pg.search_for(query)
                    
                    # 2. If exact match fails or query is long, try splitting into smaller chunks
                    # This helps when the PDF has weird newlines or hyphens that break the string
                    pg.add_highlight_annot(quads)
                    
                    # 2. Optimized Fallback: Extract Once, Search In-Memory
                    # Only triggered if exact match fails and query is long enough to justify fuzzy/chunk search
                    if not quads and len(query) > 20:
                        # Extract all words with coordinates: (x0, y0, x1, y1, "word", block, line, word_no)
                        page_words = pg.get_text("words", sort=True)
                        
                        # Prepare Query Tokens
                        q_tokens = [w.strip(".,!?;:\"").lower() for w in query.split()]
                        chunk_size = 4
                        
                        if len(q_tokens) >= chunk_size:
                            # Prepare Document Tokens (normalized)
                            # Keep index mapping to access original rects
                            doc_tokens = [w[4].strip(".,!?;:\"").lower() for w in page_words]
                            doc_rects = [fitz.Rect(w[:4]) for w in page_words]
                            
                            found_rects = []
                            doc_len = len(doc_tokens)
                            
                            # Sliding Window Search (O(M*N) but fast in Python for typical page sizes)
                            # Iterate over Query Chunks
                            for i in range(len(q_tokens) - chunk_size + 1):
                                q_chunk = q_tokens[i : i + chunk_size]
                                
                                # Search this chunk in Document
                                for j in range(doc_len - chunk_size + 1):
                                    # Compare sequence
                                    match = True
                                    for k in range(chunk_size):
                                        if doc_tokens[j+k] != q_chunk[k]:
                                            match = False
                                            break
                                    
                                    if match:
                                        # Add rects for the matched sequence
                                        for k in range(chunk_size):
                                            found_rects.append(doc_rects[j+k])

                            # Deduplicate and highlighting
                            # add_highlight_annot handles lists of rects (even duplicates) reasonably well,
                            # but we can filter unique rects to be clean
                            if found_rects:
                                pg.add_highlight_annot(found_rects)
                
                # Render High-Quality Image
                # Matrix(2, 2) = 2x Zoom (Supersampling) for clear text
                mat = fitz.Matrix(2, 2)
                pix = pg.get_pixmap(matrix=mat)
                
                # Use JPEG for speed (Dimensions are large due to 2x zoom, PNG would be huge)
                # Quality 85 is good balance
                img_bytes = pix.tobytes("jpg", jpg_quality=85)
                
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                
                return {"text": text, "image": img_b64}
            return None

        return {
            "filename": filename,
            "total_pages": total_pages,
            "current_page": {
                "number": page,
                **get_page_data(current_idx)
            },
            "prev_page": {
                "number": page - 1,
                **get_page_data(current_idx - 1)
            } if current_idx > 0 else None,
            "next_page": {
                "number": page + 1,
                **get_page_data(current_idx + 1)
            } if current_idx < total_pages - 1 else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
