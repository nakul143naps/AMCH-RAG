"""Short-term and Long-term Memory Models."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class UserFact(BaseModel):
    """Represents a durable user preference, constraint, or personal fact."""

    fact_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the stored fact",
    )
    user_id: str = Field(..., description="User ID that owns this fact")
    fact: str = Field(..., description="The factual statement or preference")
    category: str = Field(
        default="preference",
        description="Category (e.g. preference, biographical, project, constraint)",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 timestamp of fact creation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata"
    )


class ExtractedFacts(BaseModel):
    """Payload representing extracted facts from a conversation turn."""

    facts: list[str] = Field(
        default_factory=list,
        description="List of durable facts or preferences explicitly stated by the user",
    )


class ConversationSummary(BaseModel):
    """Summary of historical conversation turns for short-term memory compression."""

    summary: str = Field(..., description="Dense narrative summary of past discussion")
    covered_messages_count: int = Field(
        ..., description="Number of past messages compressed into this summary"
    )
