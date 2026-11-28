"""Account tag DAO operations"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.dao.base import BaseDAO
from app.models.account_tag import AccountTag
from app.schemas.account_tag import AccountTagCreate, AccountTagUpdate


class AccountTagDAO(BaseDAO[AccountTag, AccountTagCreate, AccountTagUpdate]):
    """DAO operations for AccountTag model"""

    def get_by_tag_code_in_workspace(
        self, db: Session, *, workspace_id: int, tag_code: str
    ) -> AccountTag | None:
        """
        Get tag by tag_code within workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            tag_code: Tag code to search for

        Returns:
            AccountTag with matching code or None
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.tag_code == tag_code
            )
            .first()
        )

    def get_active_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> list[AccountTag]:
        """
        Get all active tags within workspace, system tags first

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of active tags in workspace
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.is_active == True
            )
            .order_by(
                AccountTag.is_system_tag.desc(),
                func.lower(AccountTag.name).asc(),
                AccountTag.id.asc(),
            )
            .all()
        )

    def get_system_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> list[AccountTag]:
        """
        Get system tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of system tags in workspace
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.is_system_tag == True,
                AccountTag.is_active == True
            )
            .order_by(func.lower(AccountTag.name).asc(), AccountTag.id.asc())
            .all()
        )

    def increment_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> AccountTag | None:
        """
        Increment usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag:
            # Relative update in the database: the flush sends
            # SET usage_count = usage_count + 1 and the attribute is reloaded
            # from the stored result, never computed from the loaded object.
            tag.usage_count = AccountTag.usage_count + 1
            db.flush()
        return tag

    def decrement_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> AccountTag | None:
        """
        Decrement usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag:
            # Relative update in the database: the decrease and the
            # "not below 0" check both use the stored value, in one statement.
            # "fetch" registers the tag as changed in the session transaction,
            # so a savepoint roll-back around this call expires it again.
            stored = db.execute(
                update(AccountTag)
                .where(
                    AccountTag.id == tag.id,
                    AccountTag.workspace_id == workspace_id,
                    AccountTag.usage_count > 0,
                )
                .values(usage_count=AccountTag.usage_count - 1)
                .returning(AccountTag.usage_count)
                .execution_options(synchronize_session="fetch", autoflush=False)
            ).scalar_one_or_none()
            if stored is not None:
                # Written: the synchronisation computes "loaded value - 1" in
                # Python, which is stale when the row changed meanwhile, so
                # expire it and let the next access read the stored value.
                # Flush the session's other pending changes like before.
                db.expire(tag, ["usage_count"])
                db.flush()
            else:
                # Stored value is 0 or below: nothing written, nothing
                # flushed; the returned tag shows the stored value.
                stored = db.execute(
                    select(AccountTag.usage_count)
                    .where(AccountTag.id == tag.id)
                    .execution_options(autoflush=False)
                ).scalar_one()
                set_committed_value(tag, "usage_count", stored)
        return tag


account_tag_dao = AccountTagDAO(AccountTag)
