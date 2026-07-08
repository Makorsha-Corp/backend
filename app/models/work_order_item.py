"""Work order item model - items consumed/used in a work order"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class WorkOrderItem(Base):
    """Items consumed or moved during a work order."""

    __tablename__ = "work_order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    work_order = relationship("WorkOrder", back_populates="items")
    item = relationship("Item", backref="work_order_items", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_work_order_items")
