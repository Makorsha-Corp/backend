"""Junction: production stations (lines) and machines (many-to-many)."""
from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ProductionLineMachine(Base):
    __tablename__ = "production_line_machines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    production_line_id = Column(
        Integer, ForeignKey("production_lines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("production_line_id", "machine_id", name="uq_production_line_machine"),
    )

    workspace = relationship("Workspace", backref="production_line_machines")
    production_line = relationship("ProductionLine", back_populates="line_machines")
    machine = relationship("Machine", backref="production_line_assignments")
