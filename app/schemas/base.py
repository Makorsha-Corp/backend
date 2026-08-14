"""Shared Pydantic base models."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_serializer

from app.utils.datetime_serialize import ensure_utc_z_in_json


class AppResponseModel(BaseModel):
    """Base response schema — naive API datetimes serialize with UTC Z suffix."""

    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_with_utc_z(self, handler):
        return ensure_utc_z_in_json(handler(self))
