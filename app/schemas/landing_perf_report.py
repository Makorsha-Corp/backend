"""Pydantic schemas for landing perf feedback reports."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LandingPerfReportSubmitRequest(BaseModel):
    report: Dict[str, Any] = Field(..., description="Full perf snapshot JSON from landing page")


class LandingPerfReportSubmitResponse(BaseModel):
    message: str = "Thanks — feedback received."


class LandingPerfReportItem(BaseModel):
    id: int
    report_json: Dict[str, Any]
    viewport: Optional[str] = None
    ua_family: Optional[str] = None
    is_mobile_tour: bool = False
    theme: Optional[str] = None
    drop_rate_pct: Optional[float] = None
    session_worst_ms: Optional[float] = None
    lcp_ms: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LandingPerfReportListResponse(BaseModel):
    items: List[LandingPerfReportItem]
    total: int
    skip: int
    limit: int
