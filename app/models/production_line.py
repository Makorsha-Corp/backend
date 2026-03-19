"""Production Line model - where production happens"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProductionLine(Base):
    """
    Production Line model - represents a physical production line.

    Can be attached to a machine OR standalone.
    Each production line can have its own production formulas and batches.
    """

    __tablename__ = "production_lines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id", ondelete="RESTRICT"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True)
    # machine_id nullable: Can attach to existing machine OR standalone production line

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    workspace = relationship("Workspace", backref="production_lines")
    factory = relationship("Factory", backref="production_lines")
    machine = relationship("Machine", backref="production_lines")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_production_lines")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_production_lines")
