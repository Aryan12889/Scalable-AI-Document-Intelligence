from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    GEMINI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "models/embedding-001"
    
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "knowledge_base"
    
    REDIS_URL: str = "redis://redis:6379/0"
    
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "RAG Knowledge Base"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
