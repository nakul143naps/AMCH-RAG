"""Ingestion pipeline orchestrating file loading, chunking, embedding, and vector upsert."""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from app.cache.manager import CacheManager
from app.ingestion.chunker import SemanticChunker
from app.ingestion.loaders import RawDocumentPart, get_loader_for_file
from app.ingestion.models import IngestJob, ProcessedDocument
from app.ingestion.vision import VisionCaptioner
from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.vector_store import VectorStoreManager


class IngestionPipeline:
    """Coordinates end-to-end ingestion from file to embedded vector points."""

    def __init__(
        self,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
        cache_mgr: CacheManager | None = None,
        vision_captioner: VisionCaptioner | None = None,
    ):
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()
        self.embedding_engine = embedding_engine or EmbeddingEngine.get_instance()
        self.cache_mgr = cache_mgr or CacheManager.get_instance()
        self.vision_captioner = vision_captioner or VisionCaptioner()

    def process_file(
        self,
        file_path: str | Path,
        source_name: str | None = None,
        access_level: str = "default",
        chunk_size: int = 600,
        chunk_overlap: int = 100,
    ) -> ProcessedDocument:
        """Run full extraction, chunking, embedding, and storage for a single file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        source = source_name or path.name
        source_type = path.suffix.lower().lstrip(".")
        if source_type not in [
            "pdf",
            "docx",
            "txt",
            "md",
            "html",
            "csv",
            "pptx",
            "image",
        ]:
            source_type = "txt"

        # 1. Load document parts
        loader = get_loader_for_file(path)
        raw_parts = loader.load(path)

        # Resolve image captions for embedded charts/images using VisionCaptioner
        resolved_parts: list[RawDocumentPart] = []
        for part in raw_parts:
            if part.modality == "image_caption" and part.image_bytes and not part.content:
                caption = self.vision_captioner.caption_image_sync(
                    image_bytes=part.image_bytes,
                    context_hint=f"Document: {source}, Page: {part.page}",
                )
                part.content = caption
            if part.content.strip():
                resolved_parts.append(part)

        if not resolved_parts:
            # Empty file
            doc_id = hashlib.sha256(path.name.encode()).hexdigest()[:16]
            return ProcessedDocument(
                doc_id=doc_id,
                source=source,
                source_type=source_type,  # type: ignore
                access_level=access_level,
                chunks=[],
            )

        # 2. Generate stable doc_id based on content and source
        combined_text = "".join([p.content for p in resolved_parts])
        doc_id = hashlib.sha256(f"{source}:{combined_text}".encode()).hexdigest()[:16]

        # 3. Chunk parts
        chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = chunker.chunk_document(
            raw_parts=resolved_parts,
            doc_id=doc_id,
            source=source,
            source_type=source_type,
            access_level=access_level,
        )

        if not chunks:
            return ProcessedDocument(
                doc_id=doc_id,
                source=source,
                source_type=source_type,  # type: ignore
                access_level=access_level,
                chunks=[],
            )

        # 4. Generate dense & sparse embeddings
        chunk_texts = [c.content for c in chunks]
        dense_vectors = self.embedding_engine.embed_dense(chunk_texts)
        sparse_vectors = self.embedding_engine.embed_sparse(chunk_texts)

        # 5. Upsert to Qdrant
        self.vector_mgr.upsert_chunks(
            chunks=chunks,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
        )

        # 6. Invalidate relevant caches
        self.cache_mgr.clear()

        return ProcessedDocument(
            doc_id=doc_id,
            source=source,
            source_type=source_type,  # type: ignore
            access_level=access_level,
            chunks=chunks,
        )

    def process_url(
        self,
        url: str,
        access_level: str = "default",
        chunk_size: int = 600,
        chunk_overlap: int = 100,
    ) -> ProcessedDocument:
        """Fetch, extract, and ingest a web page using trafilatura."""
        import trafilatura

        clean_url = url.strip()
        downloaded = trafilatura.fetch_url(clean_url)
        extracted = None
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_tables=True,
                include_links=False,
                output_format="txt",
            )

        if not extracted or not extracted.strip():
            # Fallback using httpx
            try:
                import re

                import httpx

                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(clean_url)
                    text = resp.text
                    extracted = re.sub(r"<[^>]+>", " ", text)
                    extracted = re.sub(r"\s+", " ", extracted).strip()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Fallback URL fetch failed for {clean_url}: {e}")
                extracted = ""

        if not extracted:
            doc_id = hashlib.sha256(clean_url.encode()).hexdigest()[:16]
            return ProcessedDocument(
                doc_id=doc_id,
                source=clean_url,
                source_type="html",
                access_level=access_level,
                chunks=[],
            )

        raw_parts = [RawDocumentPart(content=extracted, page=1, modality="text")]
        doc_id = hashlib.sha256(f"{clean_url}:{extracted}".encode()).hexdigest()[:16]

        chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = chunker.chunk_document(
            raw_parts=raw_parts,
            doc_id=doc_id,
            source=clean_url,
            source_type="html",
            access_level=access_level,
        )

        chunk_texts = [c.content for c in chunks]
        dense_vectors = self.embedding_engine.embed_dense(chunk_texts)
        sparse_vectors = self.embedding_engine.embed_sparse(chunk_texts)

        self.vector_mgr.upsert_chunks(
            chunks=chunks,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
        )

        self.cache_mgr.clear()

        return ProcessedDocument(
            doc_id=doc_id,
            source=clean_url,
            source_type="html",
            access_level=access_level,
            chunks=chunks,
        )


class JobStore:
    """In-memory tracking for async ingestion jobs."""

    _instance: Optional["JobStore"] = None

    @classmethod
    def get_instance(cls) -> "JobStore":
        if cls._instance is None:
            cls._instance = JobStore()
        return cls._instance

    def __init__(self) -> None:
        self.jobs: dict[str, IngestJob] = {}

    def create_job(self, job_id: str, filename: str) -> IngestJob:
        job = IngestJob(job_id=job_id, filename=filename, status="pending")
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> IngestJob | None:
        return self.jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: str,
        doc_id: str | None = None,
        total_chunks: int = 0,
        error: str | None = None,
    ) -> IngestJob | None:
        job = self.jobs.get(job_id)
        if job:
            job.status = status  # type: ignore
            if doc_id:
                job.doc_id = doc_id
            if total_chunks:
                job.total_chunks = total_chunks
            if error:
                job.error = error
            if status in ["completed", "failed"]:
                job.completed_at = datetime.now(UTC)
        return job
