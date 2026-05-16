"""Refresh token model

Stores hashed refresh tokens for the OAuth-style rotation flow used by
`AuthService.refresh_access_token` and the `/auth/refresh/` endpoint.

Each row represents one rotation step in a refresh-token "family":
- `family_id` groups every rotation that descends from a single login.
- `replaced_by_id` points to the row that superseded this one when it was
  rotated (set together with `revoked_at`).
- Reuse detection: if a request presents a token whose row is already revoked
  AND already has a `replaced_by_id`, the entire family is revoked (likely
  a stolen token being replayed).

The raw token value is never persisted — we only store sha256(raw).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class RefreshToken(Base):
    """Stateful refresh token row (workspace-aware, family-grouped)."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: a session may exist before workspace selection (immediately
    # after `/auth/login/` and before `/auth/switch-workspace/`).
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # sha256 hex digest of the raw token. Unique so we can look up by hash.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)

    # All rotations from the same login share a family_id (uuid hex string).
    family_id = Column(String(36), nullable=False, index=True)

    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)

    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(
        Integer,
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Diagnostics for "active sessions" UI later.
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(64), nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("Profile", backref="refresh_tokens")
    workspace = relationship("Workspace", backref="refresh_tokens")
    replaced_by = relationship(
        "RefreshToken",
        remote_side="RefreshToken.id",
        post_update=True,
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_family", "user_id", "family_id"),
        Index("ix_refresh_tokens_active", "user_id", "revoked_at", "expires_at"),
    )
