"""Work order item model - items consumed/used in a work order"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, Numeric, Boolean, String
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
    quantity = Column(Numeric(15, 2), nullable=False)
    notes = Column(Text, nullable=True)

    # === INVENTORY SOURCE ===
    uses_inventory = Column(Boolean, nullable=False, default=False)
    source_location_type = Column(String(20), nullable=True)  # 'storage' | 'machine'
    source_location_id = Column(Integer, nullable=True)  # factory_id or machine_id depending on type

    # === WHAT HAPPENS TO IT (only meaningful when uses_inventory=True) ===
    # 'CONSUME' (default — deduct from source, nothing tracked as installed, matches pre-existing
    #   behavior), 'INSTALL' (deduct from source at start, add to the target machine's on-hand
    #   stock at completion), 'REPLACE' (deduct new item from source at start; at completion,
    #   remove `replaced_item_id`/qty from the machine into the factory's damaged bucket and add
    #   the new item to the machine — degrades to a plain INSTALL if the machine doesn't have
    #   enough of the replaced item on hand), 'BORROW' (deduct from source at start, return the
    #   same item/qty to the same source at completion — the machine's own stock is never touched).
    action_type = Column(String(20), nullable=False, default='CONSUME')
    # Only set when action_type == 'REPLACE' — the item being removed from the machine.
    replaced_item_id = Column(Integer, ForeignKey("items.id"), nullable=True, index=True)

    # === CONSUMPTION (populated once posted, at the Approved -> In Progress transition) ===
    consumed_at = Column(DateTime, nullable=True)
    consumed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    unit_cost = Column(Numeric(15, 2), nullable=True)
    total_cost = Column(Numeric(15, 2), nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    work_order = relationship("WorkOrder", back_populates="items")
    item = relationship("Item", foreign_keys=[item_id], backref="work_order_items", lazy="joined")
    replaced_item = relationship("Item", foreign_keys=[replaced_item_id], lazy="joined")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_work_order_items")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_work_order_items")
    consumer = relationship("Profile", foreign_keys=[consumed_by], backref="consumed_work_order_items")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None

    @property
    def replaced_item_name(self) -> str | None:
        return self.replaced_item.name if self.replaced_item else None
