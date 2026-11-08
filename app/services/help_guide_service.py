"""Help guide seen-state on user profile."""
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.schemas.help_guide import (
    HelpGuideMarkSeenRequest,
    HelpGuideResetRequest,
    HelpGuideUnmarkSeenRequest,
)
from app.services.base_service import BaseService
from app.utils.help_guides_seen import (
    append_seen_tour,
    normalize_help_guides_seen,
    remove_seen_tours,
    reset_seen_tours,
)


class HelpGuideService(BaseService):
    def mark_seen(
        self,
        db: Session,
        *,
        user: Profile,
        workspace_id: int,
        body: HelpGuideMarkSeenRequest,
    ) -> Profile:
        try:
            user.help_guides_seen = append_seen_tour(
                user.help_guides_seen,
                workspace_id=workspace_id,
                tour_id=body.tour_id,
            )
            db.add(user)
            self._commit_transaction(db)
            db.refresh(user)
            return user
        except Exception:
            self._rollback_transaction(db)
            raise

    def unmark_seen(
        self,
        db: Session,
        *,
        user: Profile,
        workspace_id: int,
        body: HelpGuideUnmarkSeenRequest,
    ) -> Profile:
        try:
            user.help_guides_seen = remove_seen_tours(
                user.help_guides_seen,
                workspace_id=workspace_id,
                tour_ids=body.tour_ids,
            )
            db.add(user)
            self._commit_transaction(db)
            db.refresh(user)
            return user
        except Exception:
            self._rollback_transaction(db)
            raise

    def reset_seen(
        self,
        db: Session,
        *,
        user: Profile,
        workspace_id: int,
        body: HelpGuideResetRequest,
    ) -> Profile:
        try:
            user.help_guides_seen = reset_seen_tours(
                user.help_guides_seen,
                workspace_id=workspace_id,
                scope=body.scope,
            )
            db.add(user)
            self._commit_transaction(db)
            db.refresh(user)
            return user
        except Exception:
            self._rollback_transaction(db)
            raise

    @staticmethod
    def normalized_seen(user: Profile) -> dict:
        return normalize_help_guides_seen(user.help_guides_seen)


help_guide_service = HelpGuideService()
