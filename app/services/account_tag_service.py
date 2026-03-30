"""Account tag service for business orchestration"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.dao.account_tag import account_tag_dao
from app.schemas.account_tag import AccountTagCreate, AccountTagUpdate


class AccountTagService:
    """Service for account tag workflows - handles transactions and business logic"""

    def get_tags(self, db: Session, workspace_id: int):
        """Get all active account tags in workspace"""
        return account_tag_dao.get_active_tags_in_workspace(db, workspace_id=workspace_id)

    def get_system_tags(self, db: Session, workspace_id: int):
        """Get system account tags in workspace"""
        return account_tag_dao.get_system_tags_in_workspace(db, workspace_id=workspace_id)

    def create_tag(self, db: Session, tag_in: AccountTagCreate, workspace_id: int, user_id: int):
        """Create account tag with business logic and transaction management"""
        tag_code = tag_in.tag_code
        if not tag_code:
            tag_code = tag_in.name.lower().replace(' ', '_')
            tag_code = ''.join(c for c in tag_code if c.isalnum() or c == '_')

        existing = account_tag_dao.get_by_tag_code_in_workspace(db, workspace_id=workspace_id, tag_code=tag_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tag with code '{tag_code}' already exists"
            )

        try:
            tag_data = tag_in.model_dump()
            tag_data['tag_code'] = tag_code
            tag_data['workspace_id'] = workspace_id
            tag_data['created_by'] = user_id
            tag_data['is_system_tag'] = False
            tag_data['usage_count'] = 0
            tag = account_tag_dao.create(db, obj_in=tag_data)
            db.commit()
            db.refresh(tag)
            return tag
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise

    def update_tag(self, db: Session, tag_id: int, tag_in: AccountTagUpdate, workspace_id: int):
        """Update account tag with business logic and transaction management"""
        tag = account_tag_dao.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        if tag.is_system_tag:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System tags cannot be modified")
        try:
            updated_tag = account_tag_dao.update(db, db_obj=tag, obj_in=tag_in)
            db.commit()
            db.refresh(updated_tag)
            return updated_tag
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise

    def delete_tag(self, db: Session, tag_id: int, workspace_id: int):
        """Delete account tag (soft delete) with business logic and transaction management"""
        tag = account_tag_dao.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        if tag.is_system_tag:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System tags cannot be deleted")
        try:
            account_tag_dao.update(db, db_obj=tag, obj_in={"is_active": False})
            db.commit()
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise


account_tag_service = AccountTagService()
