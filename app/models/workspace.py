"""Workspace model"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class Workspace(Base):
    """Workspace model - top-level tenant for multi-tenancy"""

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    # Ownership
    owner_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Subscription
    subscription_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True)
    subscription_status = Column(String(50), nullable=False, default='trial', index=True)
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_started_at = Column(DateTime, nullable=True)
    subscription_ends_at = Column(DateTime, nullable=True)
    billing_cycle = Column(String(20), nullable=True)  # 'monthly', 'yearly'

    # Billing
    billing_email = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Current usage (updated by triggers/background jobs)
    current_members_count = Column(Integer, nullable=False, default=1)
    current_storage_mb = Column(Integer, nullable=False, default=0)
    current_orders_this_month = Column(Integer, nullable=False, default=0)
    current_factories_count = Column(Integer, nullable=False, default=0)
    current_machines_count = Column(Integer, nullable=False, default=0)
    current_projects_count = Column(Integer, nullable=False, default=0)
    last_usage_reset_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Settings
    settings = Column(JSON, nullable=False, default={})

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("Profile", foreign_keys=[owner_user_id], backref="owned_workspaces")
    created_by = relationship("Profile", foreign_keys=[created_by_user_id], backref="created_workspaces")
    subscription_plan = relationship("SubscriptionPlan", backref="workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    invitations = relationship("WorkspaceInvitation", back_populates="workspace", cascade="all, delete-orphan")
    audit_logs = relationship("WorkspaceAuditLog", back_populates="workspace", cascade="all, delete-orphan")
