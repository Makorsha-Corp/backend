"""Storage item model (renamed from StoragePart)"""
from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class StorageItem(Base):
    """Storage item model - tracks item inventory in storage per factory"""

    __tablename__ = "storage_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False, default=0)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    avg_price = Column(Numeric(15, 2), nullable=True)

    # Relationships
    item = relationship("Item", backref="storage_items")
    factory = relationship("Factory", backref="storage_items")
