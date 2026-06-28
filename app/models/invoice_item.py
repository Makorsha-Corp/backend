"""Invoice item model — frozen snapshot of an order line item on an invoice."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class InvoiceItem(Base):
    """
    Immutable snapshot of an order line item attached to an invoice.

    Populated from PO/EO/SO items when the invoice is created or synced (draft only).
    Frozen at confirmation — cannot be changed after invoice_status = 'confirmed'.

    source_order_item_id + source_order_item_type trace back to the originating order line.
    item_id is nullable — null for free-text EO lines or manually added items.
    """

    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    line_number = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=False)
    item_id = Column(Integer, nullable=True)                       # nullable FK → items (no constraint — polymorphic)
    source_order_item_id = Column(Integer, nullable=True)          # id of originating PO/EO/SO item
    source_order_item_type = Column(String(30), nullable=True)     # 'po_item' | 'eo_item' | 'so_item'

    quantity = Column(Numeric(15, 2), nullable=False)
    unit = Column(String(50), nullable=True)
    unit_price = Column(Numeric(15, 2), nullable=False)
    line_subtotal = Column(Numeric(15, 2), nullable=False)

    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    invoice = relationship("AccountInvoice", backref="items")
    creator = relationship("Profile", foreign_keys=[created_by])
