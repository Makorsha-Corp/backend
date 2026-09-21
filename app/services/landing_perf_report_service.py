"""Landing perf report submission and admin listing."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.landing_perf_report import landing_perf_report_dao
from app.models.landing_perf_report import LandingPerfReport
from app.schemas.landing_perf_report import (
    LandingPerfReportItem,
    LandingPerfReportListResponse,
    LandingPerfReportSubmitRequest,
    LandingPerfReportSubmitResponse,
)
from app.services.base_service import BaseService
from app.services.waitlist_service import hash_client_ip

MAX_REPORT_BYTES = 32_768


class LandingPerfReportService(BaseService):
    def _validate_report_size(self, report: Dict[str, Any]) -> None:
        try:
            encoded = json.dumps(report, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid report payload",
            ) from exc
        if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Report payload too large",
            )

    def _extract_denormalized(self, report: Dict[str, Any]) -> dict:
        device = report.get("device") or {}
        session = report.get("session") or {}
        vitals = report.get("vitals") or {}
        return {
            "viewport": device.get("viewport"),
            "ua_family": device.get("uaFamily") or device.get("ua_family"),
            "is_mobile_tour": bool(device.get("isMobileTour") or device.get("is_mobile_tour")),
            "theme": device.get("theme"),
            "drop_rate_pct": session.get("dropRatePct") or session.get("drop_rate_pct"),
            "session_worst_ms": session.get("worstMs") or session.get("worst_ms"),
            "lcp_ms": vitals.get("lcpMs") or vitals.get("lcp_ms"),
        }

    def submit_report(
        self,
        db: Session,
        *,
        payload: LandingPerfReportSubmitRequest,
        remote_ip: Optional[str],
    ) -> LandingPerfReportSubmitResponse:
        self._validate_report_size(payload.report)
        denorm = self._extract_denormalized(payload.report)

        try:
            landing_perf_report_dao.create_report(
                db,
                report_json=payload.report,
                viewport=denorm["viewport"],
                ua_family=denorm["ua_family"],
                is_mobile_tour=denorm["is_mobile_tour"],
                theme=denorm["theme"],
                drop_rate_pct=denorm["drop_rate_pct"],
                session_worst_ms=denorm["session_worst_ms"],
                lcp_ms=denorm["lcp_ms"],
                ip_hash=hash_client_ip(remote_ip),
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

        return LandingPerfReportSubmitResponse()

    def list_reports(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> LandingPerfReportListResponse:
        items, total = landing_perf_report_dao.list_reports(db, skip=skip, limit=limit)
        return LandingPerfReportListResponse(
            items=[LandingPerfReportItem.model_validate(item) for item in items],
            total=total,
            skip=skip,
            limit=limit,
        )


landing_perf_report_service = LandingPerfReportService()
