"""Workspace shift service."""
from typing import List

from sqlalchemy.orm import Session

from app.managers.workspace_shift_manager import workspace_shift_manager
from app.models.workspace_shift import WorkspaceShift
from app.schemas.workspace_shift import WorkspaceShiftCreate, WorkspaceShiftUpdate
from app.services.base_service import BaseService


class WorkspaceShiftService(BaseService):
    def list_shifts(
        self,
        db: Session,
        *,
        workspace_id: int,
        active_only: bool = False,
    ) -> List[WorkspaceShift]:
        try:
            rows = workspace_shift_manager.list_shifts(
                db, workspace_id=workspace_id, active_only=active_only
            )
            self._commit_transaction(db)
            return rows
        except Exception:
            self._rollback_transaction(db)
            raise

    def create_shift(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        data: WorkspaceShiftCreate,
    ) -> WorkspaceShift:
        try:
            row = workspace_shift_manager.create_shift(
                db, workspace_id=workspace_id, user_id=user_id, data=data
            )
            self._commit_transaction(db)
            db.refresh(row)
            return row
        except ValueError as e:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_shift(
        self,
        db: Session,
        *,
        shift_id: int,
        workspace_id: int,
        user_id: int,
        data: WorkspaceShiftUpdate,
    ) -> WorkspaceShift:
        try:
            row = workspace_shift_manager.update_shift(
                db,
                shift_id=shift_id,
                workspace_id=workspace_id,
                user_id=user_id,
                data=data,
            )
            self._commit_transaction(db)
            db.refresh(row)
            return row
        except ValueError as e:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_shift(
        self,
        db: Session,
        *,
        shift_id: int,
        workspace_id: int,
    ) -> None:
        try:
            workspace_shift_manager.delete_shift(db, shift_id=shift_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except ValueError:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise


workspace_shift_service = WorkspaceShiftService()
