"""Machine section assignment model - optional, at-most-one link from a machine to a
factory section for organizational purposes. Absence of a row means "unassigned"."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class MachineSectionAssignment(Base):
    """Optional machine -> factory section link. Machines belong directly and
    mandatorily to a factory (see Machine.factory_id); a section is purely an
    optional organizational label layered on top."""

    __tablename__ = "machine_section_assignments"
    __table_args__ = (
        UniqueConstraint("machine_id", name="uq_machine_section_assignment_machine"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_section_id = Column(Integer, ForeignKey("factory_sections.id", ondelete="CASCADE"), nullable=False, index=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    machine = relationship("Machine", back_populates="section_assignment")
    factory_section = relationship("FactorySection", backref="machine_assignments")
    creator = relationship("Profile", foreign_keys=[created_by])
    updater = relationship("Profile", foreign_keys=[updated_by])
