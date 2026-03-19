"""Vendor model"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Vendor(Base):
    """Vendor/Supplier model"""

    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    vendor_code = Column(String, nullable=True, unique=True, index=True)

    # Primary contact
    primary_contact_person = Column(String, nullable=True)
    primary_email = Column(String, nullable=True)
    primary_phone = Column(String, nullable=True)

    # Secondary contact
    secondary_contact_person = Column(String, nullable=True)
    secondary_email = Column(String, nullable=True)
    secondary_phone = Column(String, nullable=True)

    # Business address
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)

    # Notes
    note = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_vendors")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_vendors")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_vendors")
