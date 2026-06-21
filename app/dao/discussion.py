"""Discussion DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.models.discussion import Discussion


class DiscussionDAO:
    def get_by_entity(
        self,
        db: Session,
        workspace_id: int,
        entity_type: str,
        entity_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Discussion], int]:
        """Return root-level discussions (no parent) with their replies eager-loaded."""
        base = (
            db.query(Discussion)
            .filter(
                Discussion.workspace_id == workspace_id,
                Discussion.entity_type == entity_type,
                Discussion.entity_id == entity_id,
                Discussion.parent_id.is_(None),
            )
        )
        total = base.count()
        items = base.order_by(Discussion.created_at.asc()).offset(skip).limit(limit).all()
        return items, total

    def get_by_id(self, db: Session, discussion_id: int, workspace_id: int) -> Discussion | None:
        return (
            db.query(Discussion)
            .filter(Discussion.id == discussion_id, Discussion.workspace_id == workspace_id)
            .first()
        )

    def create(
        self,
        db: Session,
        workspace_id: int,
        entity_type: str,
        entity_id: int,
        user_id: int,
        message: str,
        parent_id: int | None = None,
    ) -> Discussion:
        obj = Discussion(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            message=message,
            parent_id=parent_id,
        )
        db.add(obj)
        db.flush()
        return obj


discussion_dao = DiscussionDAO()
