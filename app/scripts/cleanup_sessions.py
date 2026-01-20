import os
import shutil
import time
import pathlib
import sys
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Config
DATA_UPLOADS_DIR = "/app/data/uploads"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
import argparse

# Config
DATA_UPLOADS_DIR = "/app/data/uploads"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base")
# 3 Weeks = 21 Days * 24 Hours * 3600 Seconds
DEFAULT_MAX_AGE_SECONDS = 21 * 24 * 3600 

# Ensure app module is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
try:
    from app.db import get_session_last_active, delete_session
except ImportError:
    print("Warning: Could not import app.db, falling back to file mtime only.")
    get_session_last_active = None
    delete_session = None

def cleanup_expired_sessions(max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    """
    Physical cleanup of expired session data (Uploads + Vectors + DB Session).
    """
    print(f"Starting cleanup. Max Age: {max_age_seconds}s")
    
    # Initialize Qdrant Client
    if os.getenv("QDRANT_LOCATION"):
        client = QdrantClient(path=os.getenv("QDRANT_LOCATION"))
    else:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    uploads_path = pathlib.Path(DATA_UPLOADS_DIR)
    if not uploads_path.exists():
        print(f"Directory {uploads_path} does not exist. Skiping.")
        return

    now = time.time()
    deleted_count = 0

    for session_dir in uploads_path.iterdir():
        if session_dir.is_dir():
            session_id = session_dir.name
            
            # Determine Age
            last_active = None
            if get_session_last_active:
                last_active = get_session_last_active(session_id)
            
            if last_active:
                age = now - last_active
                source_type = "DB Activity"
            else:
                # Fallback to file mtime
                mtime = session_dir.stat().st_mtime
                age = now - mtime
                source_type = "File MTime"
            
            if age > max_age_seconds:
                print(f"Session {session_id} is expired ({source_type}, Age: {age/86400:.1f} days). Cleaning up...")
                
                try:
                    # 1. Delete from Qdrant
                    client.delete(
                        collection_name=QDRANT_COLLECTION,
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
                    print(f"  - Deleted vectors for {session_id}")
                    
                    # 2. Delete from Disk
                    shutil.rmtree(session_dir)
                    print(f"  - Deleted files for {session_id}")
                    
                    # 3. Delete from DB (The critical new step)
                    if delete_session:
                        delete_session(session_id)
                        print(f"  - Deleted DB session for {session_id}")
                    
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"  - ERROR cleaning {session_id}: {e}")

    print(f"Cleanup complete. Removed {deleted_count} sessions.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup Expired Sessions")
    parser.add_argument("--force", action="store_true", help="Force cleanup of ALL sessions (ignore time)")
    args = parser.parse_args()
    
    threshold = 0 if args.force else DEFAULT_MAX_AGE_SECONDS
    
    # If force, also clear SQL DB history
    if args.force:
        try:
            # Add parent dir to path to find app module
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
            from app.db import clear_all_history
            clear_all_history()
        except Exception as e:
            print(f"Error clearing DB history: {e}")

    cleanup_expired_sessions(max_age_seconds=threshold)
