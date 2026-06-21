"""Universal discussion model — threaded messages on any entity."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, backref as orm_backref
from sqlalchemy.sql import func
from app.db.base_class import Base


class Discussion(Base):
    __tablename__ = "discussions"

    id           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Polymorphic parent entity (see DiscussionEntityType)
    entity_type = Column(String(30), nullable=False, index=True)
    entity_id   = Column(Integer, nullable=False, index=True)

    # Author
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)

    # Content — stored with @[user_id] tokens for mention resolution
    message = Column(Text, nullable=False)

    # One level of replies only — parent_id points to a root discussion
    parent_id = Column(Integer, ForeignKey("discussions.id", ondelete="CASCADE"), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    author  = relationship("Profile", foreign_keys=[user_id], backref="discussions", lazy="selectin")
    # One-to-many: parent → children (replies).
    # remote_side belongs on the backref (child→parent), not here.
    replies = relationship(
        "Discussion",
        foreign_keys=[parent_id],
        backref=orm_backref("parent_discussion", remote_side=[id]),
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_discussions_entity", "workspace_id", "entity_type", "entity_id"),
    )
