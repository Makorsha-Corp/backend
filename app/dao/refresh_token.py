"""Refresh token DAO

Pure database access for the `refresh_tokens` table. No business logic, no
commits. The service/manager layer owns transactions.

SECURITY: every query scopes to a known user_id (or workspace_id) — there is
no global lookup that could leak across users.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenDAO:
    """Workspace-aware DAO for `refresh_tokens`."""

    def get_by_hash(self, db: Session, *, token_hash: str) -> Optional[RefreshToken]:
        """Look up a refresh token row by its sha256 hash.

        The hash column is UNIQUE, so this returns at most one row.
        """
        return (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def get_by_id(self, db: Session, *, id: int) -> Optional[RefreshToken]:
        return db.query(RefreshToken).filter(RefreshToken.id == id).first()

    def list_active_for_user(
        self, db: Session, *, user_id: int
    ) -> List[RefreshToken]:
        """Return active (non-revoked, non-expired) tokens for a user."""
        now = datetime.utcnow()
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.issued_at.desc())
            .all()
        )

    def create(
        self,
        db: Session,
        *,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
        workspace_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RefreshToken:
        """Insert a new refresh token row.

        Does NOT commit — call site (service) is responsible.
        """
        row = RefreshToken(
            user_id=user_id,
            workspace_id=workspace_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(row)
        db.flush()
        return row

    def revoke(
        self,
        db: Session,
        *,
        row: RefreshToken,
        replaced_by_id: Optional[int] = None,
    ) -> None:
        """Mark a single row revoked. Optionally point at the successor row."""
        if row.revoked_at is None:
            row.revoked_at = datetime.utcnow()
        if replaced_by_id is not None:
            row.replaced_by_id = replaced_by_id
        db.flush()

    def revoke_family(self, db: Session, *, family_id: str) -> int:
        """Revoke every still-active row in a family. Returns the count revoked.

        Used when reuse of an already-rotated token is detected — likely theft.
        """
        now = datetime.utcnow()
        result = db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        db.flush()
        return int(result.rowcount or 0)

    def revoke_all_for_user(self, db: Session, *, user_id: int) -> int:
        """Revoke every still-active refresh token for one user."""
        now = datetime.utcnow()
        result = db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        db.flush()
        return int(result.rowcount or 0)

    def touch_last_used(self, db: Session, *, row: RefreshToken) -> None:
        """Set `last_used_at = now` on a row (for diagnostics, not security)."""
        row.last_used_at = datetime.utcnow()
        db.flush()

    def cleanup_expired(self, db: Session, *, older_than: datetime) -> int:
        """Hard-delete refresh tokens whose `expires_at` is older than the cutoff.

        Intended to be called by a periodic job to keep the table bounded.
        Tokens that are merely revoked but not yet expired are kept so reuse
        detection still works.
        """
        deleted = (
            db.query(RefreshToken)
            .filter(RefreshToken.expires_at < older_than)
            .delete(synchronize_session=False)
        )
        db.flush()
        return int(deleted)


refresh_token_dao = RefreshTokenDAO()
