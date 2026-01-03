# RAG Knowledge Base

A high-performance, async-first Retrieval Augmented Generation system.

## System Architecture

```mermaid
graph TD
    User[Client] -->|Upload| API[FastAPI]
    API -->|Queue| Redis
    Redis -->|Process| Worker[Celery Worker]
    Worker -->|FastEmbed (ONNX)| Qdrant[Vector DB]
    Worker -->|PyMuPDF (Images)| Storage[Disk]
    
    User -->|Query| API
    API -->|Dense Search| Qdrant
    Qdrant -->|Context| Gemini[Gemini 2.5 Flash]
    Gemini -->|Answer| User
    User -->|View Context| API
    API -->|Get Page Image| User
```

## Features
- **Turbo Backend**: 
    - **Embeddings**: FastEmbed (BAAI/bge-base-en-v1.5) running on CPU (ONNX). No Torch dependency.
    - **Parsing**: PyMuPDF (Fitz) for 10x faster PDF processing.
- **High-Fidelity UI**: 
    - **Context Popup**: View actual **PDF page images** (screenshots) instead of raw text.
    - **Persistent Chat**: Robust state management using Streamlit Callbacks.
- **Scalability**: 
    - **Dockerized**: Full hot-reloading support (`docker-compose.yml` with mounts).
    - **Async**: Celery + Redis for background ingestion.

## Setup

1. **Environment**:
   Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`.
   ```bash
   cp .env.example .env
   ```

2. **Docker**:
   Start the stack.
   ```bash
   docker-compose up --build -d
   ```

3. **Frontend**:
   Run the Streamlit dashboard on host (or access via docker if added to compose).
   ```bash
   streamlit run frontend/app.py
   ```
   Access at `http://localhost:8501`.

## Security & Testing
- Run security scan: `bandit -r app`
- Run tests: `pytest`

## API Endpoints
- `POST /api/v1/upload`: Upload PDF/MD/TXT.
- `POST /api/v1/query`: Ask questions.
- `GET /health`: System health status.
