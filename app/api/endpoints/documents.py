from fastapi import APIRouter, HTTPException, Query
import fitz # PyMuPDF
import pathlib
import base64
import os

router = APIRouter()

UPLOAD_DIR = pathlib.Path("/app/data/uploads")

@router.get("/documents/{filename}/context")
async def get_document_context(filename: str, page: int = Query(..., description="1-based page number")):
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found (might be from an old session)")
    
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        # Adjust 1-based page to 0-based index
        current_idx = page - 1
        
        if current_idx < 0 or current_idx >= total_pages:
             raise HTTPException(status_code=400, detail=f"Page {page} out of range (1-{total_pages})")
             
        def get_page_data(idx):
            if 0 <= idx < total_pages:
                pg = doc[idx]
                text = pg.get_text()
                
                # Render page to image (Resolution: 150 DPI for speed/quality balance)
                pix = pg.get_pixmap(dpi=150)
                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")
                # Encode to Base64
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
