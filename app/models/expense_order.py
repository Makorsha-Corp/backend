"""Expense order model - for direct expenses without inventory impact"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.db.base_class import Base


class ExpenseOrder(Base):
    """
    Expense orders for direct expenses that don't involve inventory.
    Examples: utilities, services, rent, payroll, maintenance, etc.
    Can be one-time or generated from recurring templates.
    """

    __tablename__ = "expense_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # === REFERENCE ===
    expense_number = Column(String(100), nullable=False, unique=True, index=True)
    # Auto-generated: EXP-2025-001

    # === TEMPLATE LINKAGE ===
    order_template_id = Column(Integer, ForeignKey("order_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    # Nullable - only set if generated from recurring template

    # === ACCOUNT ===
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)
    # Nullable - can have mixed accounts in line items, or single account here

    # === CATEGORIZATION ===
    expense_category = Column(String(100), nullable=False, index=True)
    # 'utilities', 'payroll', 'rent', 'services', 'maintenance', 'insurance', 'subscription', 'misc'

    # === DATES ===
    expense_date = Column(Date, nullable=False, default=date.today)  # When expense occurred
    due_date = Column(Date, nullable=True)  # When payment is due

    # === TOTALS (calculated from line items) ===
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)  # Sum of all line_subtotals
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Same as subtotal (no tax at line level)

    # === WORKFLOW ===
    current_status_id = Column(Integer, ForeignKey("statuses.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_workflow_id = Column(Integer, ForeignKey("order_workflows.id", ondelete="RESTRICT"), nullable=True, index=True)

    # === INVOICE LINKAGE ===
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    # Nullable - invoice created after approval

    # === DESCRIPTION & NOTES ===
    description = Column(Text, nullable=True)
    expense_note = Column(Text, nullable=True)
    internal_note = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # === RELATIONSHIPS ===
    template = relationship("OrderTemplate", backref="generated_expense_orders")
    account = relationship("Account", backref="expense_orders")
    current_status = relationship("Status", backref="expense_orders")
    workflow = relationship("OrderWorkflow", backref="expense_orders")
    invoice = relationship("AccountInvoice", backref="expense_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_expense_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_expense_orders")
    approver = relationship("Profile", foreign_keys=[approved_by], backref="approved_expense_orders")
