"""Help ticket event model — append-only activity log."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.utils.time import utcnow_aware


class HelpTicketEvent(Base):
    """Append-only activity log for a help ticket."""

    __tablename__ = "help_ticket_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    help_ticket_id = Column(
        Integer, ForeignKey("help_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow_aware)

    performer = relationship("Profile", foreign_keys=[performed_by])
