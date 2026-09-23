"""Pydantic data models for ingestion, documents, and chunk payloads."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChunkPayload(BaseModel):
    """Payload schema for individual chunk points in Qdrant."""

    doc_id: str = Field(..., description="Stable ID of the source document")
    doc_version: int = Field(default=1, description="Incremented on re-ingestion")
    source: str = Field(..., description="Filename or origin URL")
    source_type: Literal["pdf", "docx", "txt", "md", "html", "csv", "pptx", "image"] = (
        Field(..., description="Document source type")
    )
    modality: Literal["text", "table", "image_caption"] = Field(
        default="text", description="Modality of chunk content"
    )
    section: str | None = Field(
        default=None, description="Heading/section title if known"
    )
    page: int | None = Field(
        default=None, description="Page number within source document"
    )
    chunk_index: int = Field(
        ..., description="Position index within the source document"
    )
    parent_chunk_id: str | None = Field(
        default=None, description="Parent chunk identifier for hierarchical retrieval"
    )
    access_level: str = Field(
        default="default", description="Access level for tenant filtering"
    )
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the chunk was processed",
    )
    content: str = Field(..., description="The chunk text itself")


class ProcessedDocument(BaseModel):
    """Represents a document processed from raw files into normalized chunks."""

    doc_id: str
    source: str
    source_type: Literal["pdf", "docx", "txt", "md", "html", "csv", "pptx", "image"]
    access_level: str = "default"
    chunks: list[ChunkPayload] = Field(default_factory=list)


class IngestJob(BaseModel):
    """Tracking model for async ingestion jobs."""

    job_id: str
    filename: str
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    doc_id: str | None = None
    total_chunks: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
