"""Recurring work order program — one series created from Add work."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Time

from app.db.base_class import Base
from app.utils.time import utcnow


class WorkOrderProgram(Base):
    __tablename__ = "work_order_programs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    factory_id = Column(
        Integer, ForeignKey("factories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    machine_id = Column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_order_type_id = Column(
        Integer, ForeignKey("work_order_types.id", ondelete="RESTRICT"), nullable=False
    )
    title = Column(String(255), nullable=False)
    work_order_template_id = Column(
        Integer,
        ForeignKey("work_order_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cadence = Column(String(16), nullable=False)
    interval_days = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    shift_id = Column(Integer, ForeignKey("workspace_shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    planned_start_time = Column(Time, nullable=True)
    expected_duration_minutes = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="active", index=True)
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
