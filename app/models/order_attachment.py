"""Order attachment junction model"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class OrderAttachment(Base):
    """Junction table linking orders to attachments"""

    __tablename__ = "order_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    attached_at = Column(DateTime, nullable=False, server_default=func.now())
    attached_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    # Relationships
    order = relationship("Order", backref="attachments")
    attachment = relationship("Attachment", backref="order_links")
    attacher = relationship("Profile", backref="order_attachments")
