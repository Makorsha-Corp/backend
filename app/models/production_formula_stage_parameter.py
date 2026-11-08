"""Free-form step conditions on a recipe stage (planned values)."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductionFormulaStageParameter(Base):
    __tablename__ = "production_formula_stage_parameters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    formula_stage_id = Column(
        Integer, ForeignKey("production_formula_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = Column(String(120), nullable=False)
    planned_value = Column(Text, nullable=False)
    planned_value_numeric = Column(Numeric(18, 6), nullable=True)
    unit = Column(String(40), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    workspace = relationship("Workspace", backref="production_formula_stage_parameters")
    formula_stage = relationship("ProductionFormulaStage", backref="stage_parameters")

