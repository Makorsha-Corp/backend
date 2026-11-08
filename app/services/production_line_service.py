"""Production Line Service for orchestrating production line workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_line_manager import production_line_manager
from app.models.production_line import ProductionLine
from app.core.exceptions import NotFoundError, BusinessRuleError
from app.schemas.production_line import ProductionLineCreate, ProductionLineUpdate, ProductionLineResponse
from app.utils.production_line_response import build_production_line_response, build_production_line_responses


class ProductionLineService(BaseService):
    """
    Service for Production Line workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Production line CRUD operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.production_line_manager = production_line_manager

    def create_production_line(
        self,
        db: Session,
        line_in: ProductionLineCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionLineResponse:
        try:
            production_line = self.production_line_manager.create_production_line(
                session=db,
                line_data=line_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(production_line)

            machines = self.production_line_manager.line_machine_dao.get_machines_by_line_ids(
                db, line_ids=[production_line.id], workspace_id=workspace_id
            ).get(production_line.id, [])
            return build_production_line_response(production_line, machines)

        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_production_line(
        self,
        db: Session,
        line_id: int,
        workspace_id: int
    ) -> ProductionLineResponse:
        production_line = self.production_line_manager.get_production_line(
            db, line_id, workspace_id
        )
        if not production_line:
            raise NotFoundError(f"Production line with ID {line_id} not found")
        machines = self.production_line_manager.line_machine_dao.get_machines_by_line_ids(
            db, line_ids=[production_line.id], workspace_id=workspace_id
        ).get(production_line.id, [])
        return build_production_line_response(production_line, machines)

    def get_production_lines(
        self,
        db: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionLineResponse]:
        lines = self.production_line_manager.get_production_lines(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            active_only=active_only,
            skip=skip,
            limit=limit
        )
        return build_production_line_responses(db, lines, workspace_id)

    def update_production_line(
        self,
        db: Session,
        line_id: int,
        line_in: ProductionLineUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionLineResponse:
        try:
            production_line = self.production_line_manager.update_production_line(
                session=db,
                line_id=line_id,
                line_data=line_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(production_line)

            machines = self.production_line_manager.line_machine_dao.get_machines_by_line_ids(
                db, line_ids=[production_line.id], workspace_id=workspace_id
            ).get(production_line.id, [])
            return build_production_line_response(production_line, machines)

        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_production_line(
        self,
        db: Session,
        line_id: int,
        workspace_id: int
    ) -> None:
        try:
            self.production_line_manager.delete_production_line(
                session=db,
                line_id=line_id,
                workspace_id=workspace_id
            )

            self._commit_transaction(db)

        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
production_line_service = ProductionLineService()
