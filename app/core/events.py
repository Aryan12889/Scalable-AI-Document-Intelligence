from contextlib import asynccontextmanager
from fastapi import FastAPI
from phoenix.trace.llama_index import OpenInferenceTraceCallbackHandler
from llama_index.core import Settings as LlamaSettings
from llama_index.core.callbacks import CallbackManager
from app.core.config import settings
import phoenix as px
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Phoenix Tracing
    # This assumes Phoenix is running or we start a local one. 
    # For production with Docker, we might point to a collector.
    # Here we stick to basic setup for "deep tracing".
    
    # Check if we should enable tracing
    if os.getenv("ENABLE_TRACING", "True").lower() == "true":
        # Launch Phoenix app locally or configure exporter
        try:
            # session = px.launch_app() # Launches local server, good for dev
            # print(f"Phoenix UI: {session.url}")
            
            # Hook into LlamaIndex
            callback_handler = OpenInferenceTraceCallbackHandler()
            LlamaSettings.callback_manager = CallbackManager([callback_handler])
        except Exception as e:
            print(f"Failed to initialize Phoenix: {e}")
            
    yield
    # Shutdown
    pass
