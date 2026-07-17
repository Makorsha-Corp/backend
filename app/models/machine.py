"""Machine model"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Machine(Base):
    """Machine model"""

    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    is_running = Column(Boolean, nullable=False, default=False)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)

    # Machine metadata
    model_number = Column(String(200), nullable=True)
    manufacturer = Column(String(200), nullable=True)
    # TODO: next_maintenance_* may be driven by machine_maintenance_logs. Design unclear - see progressDesign.md 2026-02-28
    next_maintenance_schedule = Column(Date, nullable=True)
    next_maintenance_note = Column(Text, nullable=True)
    note = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Soft delete
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    factory = relationship("Factory", backref="machines")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_machines")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_machines")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_machines")
    # At most one row (enforced by a unique constraint on machine_id) — populated only
    # when the machine has an organizational section assigned.
    section_assignment = relationship(
        "MachineSectionAssignment", back_populates="machine", uselist=False,
    )

    @property
    def factory_section_id(self) -> int | None:
        return self.section_assignment.factory_section_id if self.section_assignment else None

    @property
    def factory_section_name(self) -> str | None:
        return self.section_assignment.factory_section.name if self.section_assignment else None
