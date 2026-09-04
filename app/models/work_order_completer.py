"""Workers who actually completed a work order (set at finish)."""
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class WorkOrderCompleter(Base):
    __tablename__ = "work_order_completers"
    __table_args__ = (
        UniqueConstraint("work_order_id", "user_id", name="uq_wo_completer_wo_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    work_order = relationship("WorkOrder", back_populates="completer_links")
    user = relationship("Profile", foreign_keys=[user_id])
