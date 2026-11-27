"""Platform landing page perf / feedback reports from Share feedback button."""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, func

from app.db.base_class import Base


class LandingPerfReport(Base):
    __tablename__ = "landing_perf_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    report_json = Column(JSON, nullable=False)
    viewport = Column(String(32), nullable=True, index=True)
    ua_family = Column(String(128), nullable=True)
    is_mobile_tour = Column(Boolean, nullable=False, default=False, server_default="false")
    theme = Column(String(16), nullable=True)
    drop_rate_pct = Column(Float, nullable=True)
    session_worst_ms = Column(Float, nullable=True)
    lcp_ms = Column(Float, nullable=True)
    ip_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
