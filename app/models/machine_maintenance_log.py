"""Machine maintenance log model"""
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Numeric, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import MaintenanceTypeEnum


class MachineMaintenanceLog(Base):
    """Machine maintenance log for tracking maintenance work done on machines"""

    __tablename__ = "machine_maintenance_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    maintenance_type = Column(Enum(MaintenanceTypeEnum), nullable=False)
    maintenance_date = Column(Date, nullable=False)
    summary = Column(Text, nullable=False)
    cost = Column(Numeric(15, 2), nullable=True)
    performed_by = Column(String(255), nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    machine = relationship("Machine", backref="maintenance_logs")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_maintenance_logs")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_maintenance_logs")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_maintenance_logs")
