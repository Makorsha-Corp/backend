"""Machine event model"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import MachineEventTypeEnum


class MachineEvent(Base):
    """Machine event model for tracking machine status changes"""

    __tablename__ = "machine_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    event_type = Column(Enum(MachineEventTypeEnum), nullable=False)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    initiated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)  # NULL = system initiated
    note = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    machine = relationship("Machine", backref="events")
    initiator = relationship("Profile", foreign_keys=[initiated_by], backref="initiated_machine_events")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_machine_events")
