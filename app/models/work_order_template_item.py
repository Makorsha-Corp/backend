"""Work order template item model - preset part lines for a work order template"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class WorkOrderTemplateItem(Base):
    """Preset part line for a work order template. Mirrors WorkOrderItem's action_type
    shape, minus the source location — that's resolved dynamically at apply time."""

    __tablename__ = "work_order_template_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_template_id = Column(Integer, ForeignKey("work_order_templates.id", ondelete="CASCADE"), nullable=False, index=True)

    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    quantity = Column(Numeric(15, 2), nullable=False, default=1)
    action_type = Column(String(20), nullable=False, default='CONSUME')
    # Only used when action_type == 'REPLACE'.
    replaced_item_id = Column(Integer, ForeignKey("items.id"), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    template = relationship("WorkOrderTemplate", backref="template_items")
    item = relationship("Item", foreign_keys=[item_id])
    replaced_item = relationship("Item", foreign_keys=[replaced_item_id])

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def replaced_item_name(self) -> str | None:
        return self.replaced_item.name if self.replaced_item else None
