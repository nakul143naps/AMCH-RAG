"""FastAPI application entrypoint for AMCH-RAG."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_documents import router as documents_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_query import router as query_router
from app.config import get_settings
from app.observability import setup_tracer
from app.retrieval.vector_store import VectorStoreManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown procedures."""
    # Initialize OpenTelemetry tracer
    setup_tracer()

    # Initialize and ensure Qdrant collections exist
    vector_mgr = VectorStoreManager.get_instance()
    try:
        vector_mgr.ensure_collections()
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Failed to ensure collections on startup: {e}")

    # Ensure all ingested documents have high-level summaries cached for summary-guided routing
    try:
        import asyncio
        from app.ingestion.summarizer import DocumentSummarizer

        asyncio.create_task(
            DocumentSummarizer.get_instance().ensure_all_documents_summarized()
        )
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Failed to trigger document summarization: {e}")

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
app.include_router(documents_router)
app.include_router(feedback_router)
app.include_router(metrics_router)
app.include_router(admin_router)

# Production SPA Static Files Mounting (Optimized for AWS Free Tier Deployment)
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

DIST_DIR = Path("frontend/dist")
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Allow internal docs / schema to pass
        if full_path in ("docs", "redoc", "openapi.json"):
            return None
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root status greeting."""
        return {
            "project": settings.PROJECT_NAME,
            "status": "online",
            "docs_url": "/docs",
        }
