"""Help guide seen-state API schemas."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.help_guides_seen import TOUR_ID_MAX_LENGTH, validate_tour_id


class HelpGuideMarkSeenRequest(BaseModel):
    tour_id: str = Field(..., min_length=1, max_length=TOUR_ID_MAX_LENGTH)

    @field_validator("tour_id")
    @classmethod
    def check_tour_id(cls, value: str) -> str:
        return validate_tour_id(value)


class HelpGuideResetRequest(BaseModel):
    scope: Literal["workspace", "all"] = "workspace"


class HelpGuideUnmarkSeenRequest(BaseModel):
    tour_ids: list[str] = Field(..., min_length=1, max_length=20)

    @field_validator("tour_ids")
    @classmethod
    def check_tour_ids(cls, value: list[str]) -> list[str]:
        return [validate_tour_id(tid) for tid in value]
