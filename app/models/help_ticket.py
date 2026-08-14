"""Help / support ticket model — workspace-scoped support requests."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class HelpTicket(Base):
    """Workspace support ticket (bugs, how-to, billing, etc.)."""

    __tablename__ = "help_tickets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "ticket_number", name="uq_help_tickets_workspace_number"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_number = Column(String(32), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(80), nullable=True)
    status = Column(String(16), nullable=False, default="open", index=True)

    created_by = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    workspace = relationship("Workspace", backref="help_tickets")
    creator = relationship("Profile", foreign_keys=[created_by], backref="help_tickets_created")
    closer = relationship("Profile", foreign_keys=[closed_by], backref="help_tickets_closed")
