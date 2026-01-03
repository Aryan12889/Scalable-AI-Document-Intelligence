from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "RAG Knowledge Base API is running"}

def test_health():
    # Note: This might return degraded if Redis/Qdrant not running locally during test
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data

def test_invalid_upload():
    response = client.post("/api/v1/upload", files={"file": ("test.exe", b"fake", "application/octet-stream")})
    assert response.status_code == 400
