"""API endpoints for document ingestion, web scraping, and job status tracking."""

import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.ingestion.models import IngestJob, IngestUrlRequest
from app.ingestion.pipeline import IngestionPipeline, JobStore
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
job_store = JobStore.get_instance()
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx", ".csv", ".html", ".htm"}


def _process_file_background(
    job_id: str, temp_path: Path, filename: str, access_level: str
) -> None:
    """Background task function to process file and update job state."""
    pipeline = IngestionPipeline()
    job_store.update_job(job_id=job_id, status="processing")
    try:
        doc = pipeline.process_file(
            file_path=temp_path,
            source_name=filename,
            access_level=access_level,
        )
        job_store.update_job(
            job_id=job_id,
            status="completed",
            doc_id=doc.doc_id,
            total_chunks=len(doc.chunks),
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Ingest job {job_id} failed: {e}")
        job_store.update_job(job_id=job_id, status="failed", error=str(e))
    finally:
        # Cleanup temporary upload file
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _process_url_background(job_id: str, url: str, access_level: str) -> None:
    """Background task function to scrape, chunk, and ingest a web URL."""
    pipeline = IngestionPipeline()
    job_store.update_job(job_id=job_id, status="processing")
    try:
        doc = pipeline.process_url(url=url, access_level=access_level)
        job_store.update_job(
            job_id=job_id,
            status="completed",
            doc_id=doc.doc_id,
            total_chunks=len(doc.chunks),
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"URL ingest job {job_id} failed: {e}")
        job_store.update_job(job_id=job_id, status="failed", error=str(e))


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestJob)
@router.post("/file", status_code=status.HTTP_202_ACCEPTED, response_model=IngestJob)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    access_level: str = Form(default="default"),
) -> IngestJob:
    """Upload a document file (TXT, MD, PDF, DOCX, PPTX, CSV, HTML) for asynchronous ingestion into Qdrant."""
    filename = file.filename or "unknown.txt"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {sorted(ALLOWED_EXTENSIONS)}",
        )

    job_id = str(uuid.uuid4())
    temp_file_path = UPLOAD_DIR / f"{job_id}_{filename}"

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job = job_store.create_job(job_id=job_id, filename=filename)

    background_tasks.add_task(
        _process_file_background,
        job_id=job_id,
        temp_path=temp_file_path,
        filename=filename,
        access_level=access_level,
    )

    return job


@router.post("/url", status_code=status.HTTP_202_ACCEPTED, response_model=IngestJob)
async def ingest_url(
    background_tasks: BackgroundTasks,
    request: IngestUrlRequest,
) -> IngestJob:
    """Scrape and ingest an external website or article by URL."""
    job_id = str(uuid.uuid4())
    job = job_store.create_job(job_id=job_id, filename=request.url)

    background_tasks.add_task(
        _process_url_background,
        job_id=job_id,
        url=request.url,
        access_level=request.access_level,
    )

    return job


@router.get("/{job_id}", response_model=IngestJob)
async def get_ingest_status(job_id: str) -> IngestJob:
    """Retrieve current processing status and chunk statistics of an ingestion job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found.",
        )
    return job


@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(doc_id: str) -> dict:
    """Delete all chunks for a document from Qdrant vector store."""
    vector_mgr = VectorStoreManager.get_instance()
    vector_mgr.delete_by_doc_id(doc_id=doc_id)
    return {"status": "deleted", "doc_id": doc_id}
