"""Pydantic schemas for attachment markup overlays."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MARKUP_POINTS = 50_000


class MarkupPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class MarkupStroke(BaseModel):
    color: str = Field(min_length=1, max_length=32)
    width: float = Field(gt=0, le=1)
    points: List[MarkupPoint] = Field(default_factory=list)


class MarkupText(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    text: str = Field(min_length=1, max_length=500)
    color: str = Field(min_length=1, max_length=32)
    size: float = Field(gt=0, le=1)


class PageMarks(BaseModel):
    strokes: List[MarkupStroke] = Field(default_factory=list)
    texts: List[MarkupText] = Field(default_factory=list)
    scribbles: List[MarkupStroke] = Field(default_factory=list)


class MarkupPayload(BaseModel):
    pages: Dict[str, PageMarks] = Field(default_factory=dict)

    @field_validator("pages")
    @classmethod
    def validate_point_budget(cls, pages: Dict[str, PageMarks]) -> Dict[str, PageMarks]:
        total = 0
        for page in pages.values():
            for stroke in (*page.strokes, *page.scribbles):
                total += len(stroke.points)
            total += len(page.texts)
        if total > MAX_MARKUP_POINTS:
            raise ValueError(f"Markup exceeds maximum of {MAX_MARKUP_POINTS} points.")
        return pages


def is_markup_payload_empty(payload: MarkupPayload) -> bool:
    if not payload.pages:
        return True
    for page in payload.pages.values():
        if page.strokes or page.texts or page.scribbles:
            return False
    return True


class AttachmentMarkupPutRequest(BaseModel):
    payload: MarkupPayload


class AttachmentMarkupLayerResponse(BaseModel):
    user_id: int
    user_name: str
    is_mine: bool
    updated_at: datetime
    payload: MarkupPayload

    model_config = ConfigDict(from_attributes=True)


class AttachmentMarkupListResponse(BaseModel):
    items: List[AttachmentMarkupLayerResponse]
