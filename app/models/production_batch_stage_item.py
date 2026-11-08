"""Per-step material quantities on a production batch."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductionBatchStageItem(Base):
    __tablename__ = "production_batch_stage_log_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_stage_log_id",
            "item_id",
            "item_role",
            name="uq_batch_stage_log_item_role",
        ),
    )

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
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_role = Column(String(20), nullable=False)
    expected_quantity = Column(Numeric(15, 2), nullable=True)
    actual_quantity = Column(Numeric(15, 2), nullable=True)

    workspace = relationship("Workspace", backref="production_batch_stage_items")
    batch = relationship("ProductionBatch", backref="stage_items")
    batch_stage_log = relationship("ProductionBatchStageLog", backref="stage_items")
    item = relationship("Item", backref="production_batch_stage_items")
