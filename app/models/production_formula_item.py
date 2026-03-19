"""Production Formula Item model - formula ingredients"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProductionFormulaItem(Base):
    """
    Production Formula Item model - individual items in a formula.

    Defines inputs, outputs, waste, and byproducts for a production formula.
    Example: "1100 kg Raw Cotton" (input) or "50 kg Cotton Dust" (waste)
    """

    __tablename__ = "production_formula_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_id = Column(Integer, ForeignKey("production_formulas.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Item role in formula
    item_role = Column(String(20), nullable=False, index=True)
    # Valid values: 'input', 'output', 'waste', 'byproduct'
    # 'input' - Raw materials consumed
    # 'output' - Finished goods produced
    # 'waste' - Waste/scrap generated during production
    # 'byproduct' - Secondary products that can be sold/reused

    # Quantity per formula batch
    quantity = Column(Integer, nullable=False)  # Base quantity for this item
    unit = Column(String(20), nullable=True)  # kg, L, pcs, etc. (informational, item has base unit)

    # Optional fields
    is_optional = Column(Boolean, default=False, nullable=False)  # Is this item optional?
    tolerance_percentage = Column(Numeric(5, 2), nullable=True)  # ±% allowed variance (e.g., 5.00 = ±5%)

    # Relationships
    workspace = relationship("Workspace", backref="production_formula_items")
    formula = relationship("ProductionFormula", backref="formula_items")
    item = relationship("Item", backref="production_formula_items")
