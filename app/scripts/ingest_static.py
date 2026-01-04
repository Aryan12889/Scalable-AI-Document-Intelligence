import os
import pathlib
import sys
import base64
from app.workers.tasks import process_document
from app.core.config import settings

# Ensure we can import from app
sys.path.append(os.getcwd())

def ingest_static_files():
    """
    Ingest all files from data/static directory with category="static".
    These files are Permanent and Shared across all sessions.
    """
    static_dir = pathlib.Path("data/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    files = list(static_dir.glob("*.[tT][xX][tT]")) + \
            list(static_dir.glob("*.[pP][dD][fF]")) + \
            list(static_dir.glob("*.[mM][dD]"))
            
    print(f"Found {len(files)} static files in {static_dir}")
    
    for file_path in files:
        print(f"Ingesting {file_path.name}...")
        
        with open(file_path, "rb") as f:
            content = f.read()
            
        file_content_b64 = base64.b64encode(content).decode('utf-8')
        
        # Call task synchronously or async?
        # For script, sync is easier to debug, but we use the worker logic.
        # We can call process_document.apply() to run locally if worker is not desired,
        # or .delay() to offload to worker.
        # Since this is a script, .delay() is better if worker is running.
        
        try:
             # category="static", session_id=None
            process_document.delay(file_content_b64, file_path.name, "static", None)
            print(f"Example: Queued {file_path.name}")
        except Exception as e:
            print(f"Failed to queue {file_path.name}: {e}")

if __name__ == "__main__":
    ingest_static_files()
