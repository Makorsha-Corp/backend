"""Order template model - reusable expense order templates"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class OrderTemplate(Base):
    """
    Reusable template for expense orders.
    Can be one-time or recurring for automation (cron-based auto-generation).
    """

    __tablename__ = "order_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    template_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # === ACCOUNT ===
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)

    # === EXPENSE CATEGORY ===
    expense_category = Column(String(100), nullable=True)
    # 'utilities', 'payroll', 'rent', 'services', 'maintenance', etc.

    # === RECURRENCE PATTERN ===
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_type = Column(String(50), nullable=True)  # 'daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'annually', 'custom'
    recurrence_interval = Column(Integer, nullable=True)  # For custom patterns: every X days
    recurrence_day = Column(Integer, nullable=True)  # Day of month (1-31) or day of week (0-6)

    # === SCHEDULE ===
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    next_generation_date = Column(Date, nullable=True)
    last_generated_date = Column(Date, nullable=True)

    # === SETTINGS ===
    is_active = Column(Boolean, nullable=False, default=True)
    generate_days_before = Column(Integer, nullable=False, default=0)
    auto_approve = Column(Boolean, nullable=False, default=False)

    # === WORKFLOW ===
    requires_approval = Column(Boolean, nullable=False, default=True)
    default_approver_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # === RELATIONSHIPS ===
    account = relationship("Account", backref="order_templates")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_templates")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_templates")
    default_approver = relationship("Profile", foreign_keys=[default_approver_id], backref="templates_to_approve")
