"""Production formula stage item — materials per route step on a recipe."""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductionFormulaStageItem(Base):
    __tablename__ = "production_formula_stage_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_stage_id = Column(
        Integer, ForeignKey("production_formula_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_role = Column(String(20), nullable=False, index=True)
    quantity = Column(Numeric(15, 2), nullable=False)
    unit = Column(String(20), nullable=True)
    is_optional = Column(Boolean, default=False, nullable=False)
    tolerance_percentage = Column(Numeric(5, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("formula_stage_id", "item_id", "item_role", name="uq_formula_stage_item_role"),
    )

    workspace = relationship("Workspace", backref="production_formula_stage_items")
    formula_stage = relationship("ProductionFormulaStage", backref="stage_items")
    item = relationship("Item", backref="production_formula_stage_items")
