from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
import os
# New OpenInference Instrumentation
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Phoenix Tracing
    if os.getenv("ENABLE_TRACING", "True").lower() == "true":
        try:
            # Register Phoenix OTEL provider
            tracer_provider = register()
            # Instrument LlamaIndex
            LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
            print("✅ Phoenix Tracing Initialized")
        except Exception as e:
            print(f"Failed to initialize Phoenix: {e}")
            
    yield
    # Shutdown
    pass
