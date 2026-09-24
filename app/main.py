"""FastAPI application entrypoint for AMCH-RAG."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_query import router as query_router
from app.config import get_settings
from app.retrieval.vector_store import VectorStoreManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown procedures."""
    # Initialize and ensure Qdrant collections exist
    vector_mgr = VectorStoreManager.get_instance()
    try:
        vector_mgr.ensure_collections()
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Failed to ensure collections on startup: {e}")
    yield


settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Agentic Multi-Modal Corrective Hybrid RAG (AMCH-RAG) Production API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root status greeting."""
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "docs_url": "/docs",
    }
