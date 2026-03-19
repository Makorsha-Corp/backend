"""Production Formula model - production recipes/BOM"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class ProductionFormula(Base):
    """
    Production Formula model - defines the recipe for producing items.

    Inputs and outputs are defined via ProductionFormulaItem with item_role:
    - 'input' - raw materials consumed
    - 'output' - finished goods produced
    - 'waste' - waste/scrap generated during production
    - 'byproduct' - secondary products that can be sold/reused

    Example: To produce 1000 kg Cotton Yarn, need 1100 kg Raw Cotton + 50 L Dye.
    """

    __tablename__ = "production_formulas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Formula identification
    formula_code = Column(String(50), nullable=False, index=True)  # e.g., "YARN-001"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)  # Track formula revisions

    # Estimated timing
    estimated_duration_minutes = Column(Integer, nullable=True)  # Expected production time

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)  # Default formula

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", backref="production_formulas")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_production_formulas")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_production_formulas")
