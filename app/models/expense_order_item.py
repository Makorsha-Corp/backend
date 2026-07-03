"""Expense order item model - line items within an expense order"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ExpenseOrderItem(Base):
    """
    Individual line items within an expense order.
    Examples: electricity bill, employee salary, service fees, etc.
    Mirrors order_template_items structure + approved field.
    """

    __tablename__ = "expense_order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    expense_order_id = Column(Integer, ForeignKey("expense_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # === LINE ITEM DETAILS ===
    line_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    # === QUANTITY & PRICING ===
    quantity = Column(Numeric(15, 2), nullable=False, default=1)
    unit = Column(String(50), nullable=True)
    unit_price = Column(Numeric(15, 2), nullable=True)
    line_subtotal = Column(Numeric(15, 2), nullable=True)  # quantity * unit_price

    # === APPROVAL ===
    approved = Column(Boolean, nullable=False, default=False)

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    expense_order = relationship("ExpenseOrder", backref="line_items")
