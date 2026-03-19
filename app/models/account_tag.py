"""Account tag model - for categorizing accounts (supplier, client, utility, payroll, etc.)"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class AccountTag(Base):
    """Account tag model for categorizing accounts"""

    __tablename__ = "account_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)  # Display name: "Supplier", "Client"
    tag_code = Column(String(50), nullable=False)  # Internal identifier: "supplier", "client"
    color = Column(String(7), nullable=True)  # Hex color for UI: "#3B82F6"
    icon = Column(String(50), nullable=True)  # Icon name: "package", "users"
    description = Column(Text, nullable=True)  # Helpful description for users

    # System management
    is_system_tag = Column(Boolean, nullable=False, default=False)  # Can't be deleted/renamed
    is_active = Column(Boolean, nullable=False, default=True)  # Soft delete
    usage_count = Column(Integer, nullable=False, default=0)  # Number of accounts with this tag

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_account_tags")
