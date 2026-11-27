"""DAO for platform landing perf reports."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.landing_perf_report import LandingPerfReport


class LandingPerfReportDAO(BaseDAO[LandingPerfReport, dict, dict]):
    def create_report(
        self,
        db: Session,
        *,
        report_json: dict,
        viewport: Optional[str],
        ua_family: Optional[str],
        is_mobile_tour: bool,
        theme: Optional[str],
        drop_rate_pct: Optional[float],
        session_worst_ms: Optional[float],
        lcp_ms: Optional[float],
        ip_hash: Optional[str],
    ) -> LandingPerfReport:
        db_obj = self.model(
            report_json=report_json,
            viewport=viewport,
            ua_family=ua_family,
            is_mobile_tour=is_mobile_tour,
            theme=theme,
            drop_rate_pct=drop_rate_pct,
            session_worst_ms=session_worst_ms,
            lcp_ms=lcp_ms,
            ip_hash=ip_hash,
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def list_reports(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[LandingPerfReport], int]:
        query = db.query(self.model)
        total = query.count()
        items = (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total


landing_perf_report_dao = LandingPerfReportDAO(LandingPerfReport)
