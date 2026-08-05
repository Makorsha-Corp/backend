"""Sales order approver model - assigned workspace members who approve a sales order."""
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class SalesOrderApprover(Base):
    """
    A workspace member assigned to approve a sales order.
    Approve-only: `approved` flips True with `approved_at` stamped.
    """

    __tablename__ = "sales_order_approvers"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "user_id", name="uq_so_approver_so_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    approved = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime, nullable=True)

    sales_order = relationship("SalesOrder", back_populates="approvers")
    user = relationship("Profile", foreign_keys=[user_id])
    assigner = relationship("Profile", foreign_keys=[assigned_by])
