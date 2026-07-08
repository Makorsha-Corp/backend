"""Production batch stage log — manual per-stage production record."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.db.base_class import Base


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
    status = Column(String(20), nullable=False, default="pending", index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    logged_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    input_quantity = Column(Integer, nullable=True)
    output_quantity = Column(Integer, nullable=True)
    waste_quantity = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workspace = relationship("Workspace", backref="production_batch_stage_logs")
    batch = relationship("ProductionBatch", backref="stage_logs")
    formula_stage = relationship("ProductionFormulaStage", backref="batch_logs")
    production_line = relationship("ProductionLine", backref="batch_stage_logs")
    logger = relationship("Profile", foreign_keys=[logged_by], backref="production_batch_stage_logs")
