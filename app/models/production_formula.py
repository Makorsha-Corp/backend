"""Production Formula model - production recipes/BOM"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import backref, relationship
from datetime import datetime
from app.db.base_class import Base
from app.utils.time import utcnow


class ProductionFormula(Base):
    """
    Production Formula model - defines the recipe for producing items.

    Materials and outputs are defined per path step via ProductionFormulaStageItem.
    """

    __tablename__ = "production_formulas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Formula identification
    formula_code = Column(String(50), nullable=False, index=True)  # e.g., "YARN-001"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)  # Track formula revisions

    route_id = Column(Integer, ForeignKey("production_routes.id", ondelete="SET NULL"), nullable=True, index=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)  # Default formula

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", backref="production_formulas")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_production_formulas")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_production_formulas")
    route = relationship(
        "ProductionRoute",
        foreign_keys=[route_id],
        backref=backref("formulas", foreign_keys="ProductionFormula.route_id"),
    )
