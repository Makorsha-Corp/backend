"""WorkspaceAuditLog model"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class WorkspaceAuditLog(Base):
    """Workspace audit log model - tracks workspace administration actions"""

    __tablename__ = "workspace_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # 'member_added', 'member_removed', 'role_changed', etc.
    resource_type = Column(String(50), nullable=True)  # 'order', 'part', 'member', 'settings'
    resource_id = Column(Integer, nullable=True)

    # Request metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 max length is 45 chars
    user_agent = Column(Text, nullable=True)

    # Additional context (column name preserved for DB compatibility)
    metadata_json = Column("metadata", JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="audit_logs")
    user = relationship("Profile", backref="workspace_audit_logs")
