"""Production Line Service for orchestrating production line workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_line_manager import production_line_manager
from app.models.production_line import ProductionLine
from app.core.exceptions import NotFoundError, BusinessRuleError


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
        line_in: "ProductionLineCreate",
        workspace_id: int,
        user_id: int
    ) -> ProductionLine:
        """
        Create a new production line.

        Args:
            db: Database session
            line_in: Production line creation data
            workspace_id: Workspace ID
            user_id: User ID creating the line

        Returns:
            Created production line

        Raises:
            BusinessRuleError: If factory/machine validation fails
        """
        try:
            production_line = self.production_line_manager.create_production_line(
                session=db,
                line_data=line_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            self._commit_transaction(db)
            db.refresh(production_line)

            return production_line

        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_production_line(
        self,
        db: Session,
        line_id: int,
        workspace_id: int
    ) -> ProductionLine:
        """
        Get production line by ID.

        Args:
            db: Database session
            line_id: Production line ID
            workspace_id: Workspace ID

        Returns:
            Production line

        Raises:
            NotFoundError: If production line not found
        """
        production_line = self.production_line_manager.get_production_line(
            db, line_id, workspace_id
        )
        if not production_line:
            raise NotFoundError(f"Production line with ID {line_id} not found")
        return production_line

    def get_production_lines(
        self,
        db: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionLine]:
        """
        Get production lines with optional filtering.

        Args:
            db: Database session
            workspace_id: Workspace ID
            factory_id: Optional filter by factory
            active_only: If True, only return active lines
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production lines
        """
        return self.production_line_manager.get_production_lines(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            active_only=active_only,
            skip=skip,
            limit=limit
        )

    def update_production_line(
        self,
        db: Session,
        line_id: int,
        line_in: "ProductionLineUpdate",
        workspace_id: int,
        user_id: int
    ) -> ProductionLine:
        """
        Update an existing production line.

        Args:
            db: Database session
            line_id: Production line ID
            line_in: Production line update data
            workspace_id: Workspace ID
            user_id: User ID updating the line

        Returns:
            Updated production line

        Raises:
            NotFoundError: If production line not found
            BusinessRuleError: If validation fails
        """
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

            return production_line

        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_production_line(
        self,
        db: Session,
        line_id: int,
        workspace_id: int
    ) -> None:
        """
        Soft delete a production line (set is_active=False).

        Args:
            db: Database session
            line_id: Production line ID
            workspace_id: Workspace ID

        Raises:
            NotFoundError: If production line not found
        """
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
        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
production_line_service = ProductionLineService()
