"""Purchase order approver model - assigned workspace members who approve a PO."""
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class PurchaseOrderApprover(Base):
    """
    A workspace member assigned to approve a purchase order.
    Approve-only: `approved` flips True with `approved_at` stamped.
    """

    __tablename__ = "purchase_order_approvers"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "user_id", name="uq_po_approver_po_user"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    approved = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime, nullable=True)

    purchase_order = relationship("PurchaseOrder", back_populates="approvers")
    user = relationship("Profile", foreign_keys=[user_id])
    assigner = relationship("Profile", foreign_keys=[assigned_by])
