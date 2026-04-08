"""Account model - unified entity for suppliers, clients, utilities, payroll, etc."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Account(Base):
    """
    Account model - represents any external party we do business with.
    Can be suppliers, clients, utilities, employees, etc.
    Type is determined by tags, not hardcoded flags.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic Info
    name = Column(String(255), nullable=False, index=True)
    account_code = Column(String(50), nullable=True)  # Optional internal reference

    # Consolidated account fields
    contact_details = Column(Text, nullable=True)
    address_fields = Column(Text, nullable=True)
    payment_terms = Column(String(50), nullable=True)
    bank_details = Column(Text, nullable=True)

    # Admin Controls
    allow_invoices = Column(Boolean, nullable=False, default=True)

    # Audit Fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_accounts")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_accounts")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_accounts")
