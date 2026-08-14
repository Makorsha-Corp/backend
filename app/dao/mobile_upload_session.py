"""DAO for mobile upload sessions."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.mobile_upload_session import MobileUploadSession
from app.utils.time import utcnow


def _naive_utc(value: datetime) -> datetime:
    """Match app `utcnow()` — DB timestamptz may come back timezone-aware."""
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


class MobileUploadSessionDAO(BaseDAO[MobileUploadSession, dict, dict]):
    """Database access for mobile upload sessions."""

    def get_by_token_hash(self, db: Session, *, token_hash: str) -> Optional[MobileUploadSession]:
        return db.query(self.model).filter(self.model.token_hash == token_hash).first()

    def get_for_creator(
        self,
        db: Session,
        *,
        session_id: int,
        workspace_id: int,
        created_by: int,
    ) -> Optional[MobileUploadSession]:
        return (
            db.query(self.model)
            .filter(
                self.model.id == session_id,
                self.model.workspace_id == workspace_id,
                self.model.created_by == created_by,
            )
            .first()
        )

    def mark_expired_if_needed(self, session: MobileUploadSession) -> MobileUploadSession:
        if session.status == "waiting" and _naive_utc(session.expires_at) <= utcnow():
            session.status = "expired"
        return session


mobile_upload_session_dao = MobileUploadSessionDAO(MobileUploadSession)
