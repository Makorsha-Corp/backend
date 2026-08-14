"""Mobile upload session — short-lived QR token for phone-to-desktop file handoff."""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class MobileUploadSession(Base):
    """Staging session for one phone upload before desktop scan/attach."""

    __tablename__ = "mobile_upload_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=False)
    entity_label = Column(String(80), nullable=True)

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="waiting", index=True)

    public_id = Column(String(512), nullable=True)
    asset_folder = Column(String(512), nullable=True)
    resource_type = Column(String(16), nullable=True)
    delivery_type = Column(String(16), nullable=False, default="authenticated")
    format = Column(String(16), nullable=True)
    version = Column(BigInteger, nullable=True)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(128), nullable=True)
    file_size = Column(BigInteger, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace = relationship("Workspace", backref="mobile_upload_sessions")
    creator = relationship("Profile", foreign_keys=[created_by], backref="mobile_upload_sessions")
