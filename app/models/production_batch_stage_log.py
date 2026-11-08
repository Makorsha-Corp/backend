"""Production batch stage log — manual per-stage production record."""
from datetime import datetime
from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.utils.time import utcnow


class ProductionBatchStageLog(Base):
    __tablename__ = "production_batch_stage_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_stage_id = Column(
        Integer, ForeignKey("production_formula_stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage_name = Column(String(200), nullable=False)
    stage_order = Column(Integer, nullable=False, default=0)
    production_line_id = Column(Integer, ForeignKey("production_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    route_step_id = Column(Integer, ForeignKey("production_route_steps.id", ondelete="SET NULL"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True)
    expected_duration_minutes = Column(Integer, nullable=True)
    expected_output_quantity = Column(Numeric(15, 2), nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    planned_start_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    logged_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    input_quantity = Column(Numeric(15, 2), nullable=True)
    output_quantity = Column(Numeric(15, 2), nullable=True)
    waste_quantity = Column(Numeric(15, 2), nullable=True)
    rework_quantity = Column(Numeric(15, 2), nullable=True)
    rework_of_log_id = Column(
        Integer, ForeignKey("production_batch_stage_logs.id", ondelete="SET NULL"), nullable=True
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    workspace = relationship("Workspace", backref="production_batch_stage_logs")
    batch = relationship("ProductionBatch", backref="stage_logs")
    formula_stage = relationship("ProductionFormulaStage", backref="batch_logs")
    production_line = relationship("ProductionLine", backref="batch_stage_logs")
    machine = relationship("Machine", backref="batch_stage_logs")
    route_step = relationship("ProductionRouteStep", backref="batch_stage_logs")
    rework_of_log = relationship("ProductionBatchStageLog", remote_side=[id], backref="rework_children")
    logger = relationship("Profile", foreign_keys=[logged_by], backref="production_batch_stage_logs")
