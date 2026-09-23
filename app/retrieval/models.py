"""Data models for retrieval, search queries, and hybrid ranking."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Represents a retrieved document chunk with similarity/fusion score."""

    chunk_id: str = Field(..., description="Unique ID of the point in Qdrant")
    score: float = Field(..., description="Similarity or RRF score")
    content: str = Field(..., description="The chunk text itself")
    doc_id: str = Field(..., description="Stable ID of the source document")
    source: str = Field(..., description="Filename or origin URL")
    source_type: str = Field(..., description="Document source type")
    modality: str = Field(default="text", description="Modality of chunk content")
    section: str | None = Field(
        default=None, description="Heading/section title if known"
    )
    page: int | None = Field(
        default=None, description="Page number within source document"
    )
    chunk_index: int = Field(
        default=0, description="Position index within the source document"
    )
    access_level: str = Field(
        default="default", description="Access level for tenant filtering"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional chunk metadata"
    )


class RetrievalQuery(BaseModel):
    """Encapsulates parameters for a retrieval operation."""

    query: str = Field(..., min_length=1, description="Search query string")
    limit: int = Field(
        default=10, ge=1, le=100, description="Max final chunks to return"
    )
    mode: Literal["hybrid", "dense", "sparse"] = Field(
        default="hybrid",
        description="Retrieval mode: hybrid (dense+sparse RRF), dense only, or sparse only",
    )
    access_levels: list[str] | None = Field(
        default=None, description="Allowed access levels for tenant isolation"
    )
    doc_ids: list[str] | None = Field(
        default=None, description="Optional doc_id filter"
    )
    source_types: list[str] | None = Field(
        default=None, description="Optional source_type filter"
    )
    prefetch_limit: int = Field(
        default=40,
        ge=1,
        le=200,
        description="Number of candidates to prefetch per branch",
    )
    score_threshold: float | None = Field(
        default=None, description="Minimum score cutoff"
    )
