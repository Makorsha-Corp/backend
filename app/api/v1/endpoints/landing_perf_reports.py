"""Public landing perf feedback reports + platform admin listing."""
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.limiter import limiter
from app.core.waitlist_admin import get_waitlist_admin
from app.models.profile import Profile
from app.schemas.landing_perf_report import (
    LandingPerfReportListResponse,
    LandingPerfReportSubmitRequest,
    LandingPerfReportSubmitResponse,
)
from app.services.landing_perf_report_service import landing_perf_report_service

router = APIRouter()


@router.post(
    "",
    response_model=LandingPerfReportSubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit landing page perf feedback report",
)
@limiter.limit("3/minute")
def submit_landing_perf_report(
    request: Request,
    payload: LandingPerfReportSubmitRequest,
    db: Session = Depends(get_db),
) -> LandingPerfReportSubmitResponse:
    remote_ip = request.client.host if request.client else None
    return landing_perf_report_service.submit_report(db, payload=payload, remote_ip=remote_ip)


@router.get(
    "",
    response_model=LandingPerfReportListResponse,
    summary="List landing perf reports (platform admin)",
)
def list_landing_perf_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Profile = Depends(get_waitlist_admin),
) -> LandingPerfReportListResponse:
    return landing_perf_report_service.list_reports(db, skip=skip, limit=limit)
