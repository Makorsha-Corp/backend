"""Product model - finished goods available for sale"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, Numeric, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Product(Base):
    """
    Products table for finished goods inventory.
    Tracks qty, production cost, selling price, and sale availability.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint('workspace_id', 'item_id', 'factory_id', 'is_available_for_sale',
                         name='uq_product_workspace_item_factory_available'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False, default=0)
    avg_cost = Column(Numeric(15, 2), nullable=True)
    selling_price = Column(Numeric(15, 2), nullable=True)
    min_order_qty = Column(Integer, nullable=True)
    is_available_for_sale = Column(Boolean, default=False, nullable=False, index=True)
    note = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    item = relationship("Item", backref="product_records", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None

    factory = relationship("Factory", backref="product_records")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_products")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_products")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_products")
