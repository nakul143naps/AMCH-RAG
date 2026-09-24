"""Pydantic models for API requests and responses (Feedback, Documents)."""

from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """User feedback payload linked to a specific query trace_id."""

    trace_id: str = Field(description="Unique trace_id of the query being reviewed")
    rating: Literal["up", "down"] = Field(description="User rating: up (thumbs up) or down (thumbs down)")
    comment: str | None = Field(default=None, description="Optional user comment or explanation")


class FeedbackResponse(BaseModel):
    """Response returned upon capturing feedback."""

    status: str = "received"
    feedback_id: str
    trace_id: str
    rating: str


class DocumentItem(BaseModel):
    """Metadata representing an ingested document stored in Qdrant."""

    doc_id: str
    source_name: str
    source_type: str
    access_level: str
    chunk_count: int
    version: int = 1
    created_at: str | None = None


class DocumentListResponse(BaseModel):
    """Response listing all stored documents."""

    documents: list[DocumentItem]
    total: int


class DocumentDeleteResponse(BaseModel):
    """Response returned after deleting a document and evicting caches."""

    doc_id: str
    status: str = "deleted"
    cache_invalidated: bool = True
