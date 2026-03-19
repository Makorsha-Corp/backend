"""Transfer order item model - items within a transfer order"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class TransferOrderItem(Base):
    """
    Individual line items within a transfer order.
    Tracks items being transferred with quantities and status.
    """

    __tablename__ = "transfer_order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_order_id = Column(Integer, ForeignKey("transfer_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # === LINE ITEM DETAILS ===
    line_number = Column(Integer, nullable=False)

    # === ITEM ===
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === QUANTITY ===
    quantity = Column(Numeric(15, 2), nullable=False)

    # === APPROVAL ===
    approved = Column(Boolean, nullable=False, default=False)
    approved_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # === TRANSFER TRACKING ===
    transferred_by = Column(String(200), nullable=True)  # Free text - person who physically transferred
    transferred_at = Column(DateTime, nullable=True)

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    transfer_order = relationship("TransferOrder", backref="line_items")
    item = relationship("Item", backref="transfer_order_items", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None
    approver = relationship("Profile", foreign_keys=[approved_by], backref="approved_transfer_items")
