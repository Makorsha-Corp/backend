"""Schemas for similar item name lookup."""
from typing import Literal

from pydantic import BaseModel, Field


class SimilarItemMatch(BaseModel):
    """A catalog item that closely matches a proposed name."""

    id: int
    name: str
    unit: str
    sku: str | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)
    match_type: Literal["exact_normalized", "fuzzy"]


class SimilarItemsResponse(BaseModel):
    """Response for GET /items/similar/."""

    query: str
    normalized_query: str
    matches: list[SimilarItemMatch]
