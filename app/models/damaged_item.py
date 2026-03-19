"""Damaged item model (renamed from DamagedPart)"""
from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class DamagedItem(Base):
    """Damaged item model - tracks damaged/defective item inventory per factory"""

    __tablename__ = "damaged_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False, default=0)
    avg_price = Column(Numeric(15, 2), nullable=True)

    # Relationships
    factory = relationship("Factory", backref="damaged_items")
    item = relationship("Item", backref="damaged_items")
