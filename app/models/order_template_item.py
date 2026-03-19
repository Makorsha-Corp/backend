"""Order template item model - line items for expense order templates"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class OrderTemplateItem(Base):
    """
    Line items for order templates.
    Mirrors expense order items for reuse.
    """

    __tablename__ = "order_template_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    order_template_id = Column(Integer, ForeignKey("order_templates.id", ondelete="CASCADE"), nullable=False, index=True)

    # === LINE ITEM DETAILS ===
    line_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    # === QUANTITY & PRICING ===
    quantity = Column(Numeric(15, 2), nullable=False, default=1)
    unit = Column(String(50), nullable=True)  # 'service', 'hours', 'kWh', 'month', etc.
    unit_price = Column(Numeric(15, 2), nullable=True)
    line_subtotal = Column(Numeric(15, 2), nullable=True)  # quantity * unit_price

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    template = relationship("OrderTemplate", backref="template_items")
