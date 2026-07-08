"""Production formula stage — ordered route template per formula."""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProductionFormulaStage(Base):
    __tablename__ = "production_formula_stages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_id = Column(Integer, ForeignKey("production_formulas.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_order = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    production_line_id = Column(Integer, ForeignKey("production_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True)
    expected_duration_minutes = Column(Integer, nullable=True)
    expected_output_quantity = Column(Integer, nullable=True)
    expected_output_item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("formula_id", "stage_order", name="uq_formula_stage_order"),
    )

    workspace = relationship("Workspace", backref="production_formula_stages")
    formula = relationship("ProductionFormula", backref="stages")
    production_line = relationship("ProductionLine", backref="formula_stages")
    machine = relationship("Machine", backref="formula_stages")
    expected_output_item = relationship("Item", backref="formula_stage_outputs")
