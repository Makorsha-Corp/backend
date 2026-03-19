"""Account tag assignment model - junction table for account-tag many-to-many"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class AccountTagAssignment(Base):
    """Junction table linking accounts to tags (many-to-many)"""

    __tablename__ = "account_tag_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("account_tags.id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    account = relationship("Account", backref="tag_assignments")
    tag = relationship("AccountTag", backref="account_assignments")
    assigner = relationship("Profile", foreign_keys=[assigned_by], backref="account_tag_assignments")

    # Constraints
    __table_args__ = (
        UniqueConstraint('account_id', 'tag_id', name='uq_account_tag'),
    )
