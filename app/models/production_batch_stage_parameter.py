"""Step conditions on a batch stage log (planned snapshot + actual)."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductionBatchStageParameter(Base):
    __tablename__ = "production_batch_stage_parameters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id = Column(
        Integer, ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_stage_log_id = Column(
        Integer,
        ForeignKey("production_batch_stage_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(String(120), nullable=False)
    planned_value = Column(Text, nullable=False)
    planned_value_numeric = Column(Numeric(18, 6), nullable=True)
    actual_value = Column(Text, nullable=True)
    actual_value_numeric = Column(Numeric(18, 6), nullable=True)
    unit = Column(String(40), nullable=True)
    source_parameter_id = Column(
        Integer,
        ForeignKey("production_formula_stage_parameters.id", ondelete="SET NULL"),
        nullable=True,
    )

    workspace = relationship("Workspace", backref="production_batch_stage_parameters")
    batch = relationship("ProductionBatch", backref="stage_parameters")
    batch_stage_log = relationship("ProductionBatchStageLog", backref="stage_parameters")
    source_parameter = relationship("ProductionFormulaStageParameter", backref="batch_snapshots")

