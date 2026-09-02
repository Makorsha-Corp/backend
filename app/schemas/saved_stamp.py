"""Saved stamp schemas — user-level draw or upload stamp for attachment markup."""
from __future__ import annotations

from typing import List, Literal, Union

from pydantic import BaseModel, Field

from app.schemas.attachment_markup import MarkupPoint, MarkupStroke


class SavedStampViewBox(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SavedStampVector(BaseModel):
    kind: Literal["vector"] = "vector"
    strokes: List[MarkupStroke] = Field(default_factory=list)
    viewBox: SavedStampViewBox


class SavedStampImage(BaseModel):
    kind: Literal["image"] = "image"
    public_id: str = Field(min_length=1, max_length=512)
    url: str = Field(min_length=1, max_length=2048)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


SavedStamp = Union[SavedStampVector, SavedStampImage]


class StampImageSignResponse(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    public_id: str
    asset_folder: str
    display_name: str
    type: str
    signature: str
    resource_type: str
    upload_url: str
