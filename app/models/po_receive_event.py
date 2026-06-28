from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class PoReceiveEvent(Base):
    __tablename__ = "po_receive_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # 'receive' | 'correction'
    rcc = Column(String(100), nullable=True)
    received_by = Column(String(200), nullable=True)
    correction_note = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    items = relationship("PoReceiveEventItem", back_populates="event", cascade="all, delete-orphan")
    performer = relationship("Profile", foreign_keys=[performed_by], lazy="joined")


class PoReceiveEventItem(Base):
    __tablename__ = "po_receive_event_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receive_event_id = Column(Integer, ForeignKey("po_receive_events.id", ondelete="CASCADE"), nullable=False, index=True)
    po_item_id = Column(Integer, ForeignKey("purchase_order_items.id", ondelete="CASCADE"), nullable=False)
    quantity_delta = Column(Numeric(15, 4), nullable=False)

    event = relationship("PoReceiveEvent", back_populates="items")
    po_item = relationship("PurchaseOrderItem", lazy="joined")
