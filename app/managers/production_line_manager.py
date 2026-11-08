"""Production Line Manager for business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_line import ProductionLine
from app.dao.production_line import production_line_dao
from app.dao.production_line_machine import production_line_machine_dao
from app.dao.factory import factory_dao
from app.dao.machine import machine_dao
from app.schemas.production_line import ProductionLineCreate, ProductionLineUpdate
from app.utils.production_line_response import mirror_machine_id_column


class ProductionLineManager(BaseManager[ProductionLine]):
    """
    STANDALONE MANAGER: Production line business logic.

    Manages: ProductionLine entity with factory/machine validation

    Operations: CRUD with validation

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(ProductionLine)
        self.production_line_dao = production_line_dao
        self.line_machine_dao = production_line_machine_dao

    def _resolve_machine_ids(
        self,
        *,
        machine_ids: Optional[List[int]],
        machine_id: Optional[int],
    ) -> Optional[List[int]]:
        if machine_ids is not None:
            return list(dict.fromkeys(machine_ids))
        if machine_id is not None:
            return [machine_id]
        return None

    def _validate_machines_for_factory(
        self,
        session: Session,
        *,
        machine_ids: List[int],
        factory_id: int,
        workspace_id: int,
    ) -> None:
        for mid in machine_ids:
            machine = machine_dao.get(session, id=mid)
            if not machine:
                raise ValueError(f"Machine {mid} not found")
            if machine.workspace_id != workspace_id:
                raise ValueError(f"Machine {mid} does not belong to workspace {workspace_id}")
            if getattr(machine, "is_deleted", False):
                raise ValueError(f"Machine {mid} not found")
            if machine.factory_id != factory_id:
                raise ValueError(f"Machine {mid} does not belong to factory {factory_id}")

    def _sync_line_machines(
        self,
        session: Session,
        *,
        line: ProductionLine,
        machine_ids: List[int],
        workspace_id: int,
    ) -> None:
        self._validate_machines_for_factory(
            session,
            machine_ids=machine_ids,
            factory_id=line.factory_id,
            workspace_id=workspace_id,
        )
        self.line_machine_dao.replace_for_line(
            session,
            production_line_id=line.id,
            workspace_id=workspace_id,
            machine_ids=machine_ids,
        )
        line.machine_id = mirror_machine_id_column(machine_ids)
        session.flush()

    def create_production_line(
        self,
        session: Session,
        line_data: ProductionLineCreate,
        workspace_id: int,
        user_id: int
    ) -> ProductionLine:
        """
        Create a new production line with validation.

        Args:
            session: Database session
            line_data: Production line creation data
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID creating the line (for audit)

        Returns:
            Created production line (not yet committed)

        Raises:
            ValueError: If factory not found, workspace mismatch, or machine validation fails

        Note:
            This method does NOT commit. The service layer must commit.
        """
        # Validate factory exists and belongs to workspace
        factory = factory_dao.get(session, id=line_data.factory_id)
        if not factory:
            raise ValueError(f"Factory {line_data.factory_id} not found")
        if factory.workspace_id != workspace_id:
            raise ValueError(f"Factory {line_data.factory_id} does not belong to workspace {workspace_id}")

        resolved_ids = self._resolve_machine_ids(
            machine_ids=line_data.machine_ids,
            machine_id=line_data.machine_id,
        )
        if resolved_ids:
            self._validate_machines_for_factory(
                session,
                machine_ids=resolved_ids,
                factory_id=line_data.factory_id,
                workspace_id=workspace_id,
            )

        # Convert Pydantic model to dict and inject workspace/audit fields
        line_dict = line_data.model_dump(exclude={"machine_ids"})
        if resolved_ids is not None:
            line_dict["machine_id"] = mirror_machine_id_column(resolved_ids)
        line_dict['workspace_id'] = workspace_id
        line_dict['created_by'] = user_id

        # Create the production line
        production_line = self.production_line_dao.create(session, obj_in=line_dict)

        if resolved_ids is not None:
            self.line_machine_dao.replace_for_line(
                session,
                production_line_id=production_line.id,
                workspace_id=workspace_id,
                machine_ids=resolved_ids,
            )

        return production_line

    def update_production_line(
        self,
        session: Session,
        line_id: int,
        line_data: ProductionLineUpdate,
        workspace_id: int,
        user_id: int
    ) -> ProductionLine:
        """
        Update an existing production line with validation.

        Args:
            session: Database session
            line_id: Production line ID
            line_data: Production line update data
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID updating the line (for audit)

        Returns:
            Updated production line (not yet committed)

        Raises:
            ValueError: If line not found, workspace mismatch, or validation fails

        Note:
            This method does NOT commit. The service layer must commit.
        """
        # Get existing production line
        production_line = self.production_line_dao.get(session, id=line_id)
        if not production_line:
            raise ValueError(f"Production line {line_id} not found")

        # Validate workspace ownership
        if production_line.workspace_id != workspace_id:
            raise ValueError(f"Production line {line_id} does not belong to workspace {workspace_id}")

        dump = line_data.model_dump(exclude_unset=True)
        machine_ids_to_sync: Optional[List[int]] = None
        if "machine_ids" in dump:
            machine_ids_to_sync = list(dict.fromkeys(dump.pop("machine_ids") or []))
        elif "machine_id" in dump:
            mid = dump.pop("machine_id")
            machine_ids_to_sync = [mid] if mid is not None else []

        if machine_ids_to_sync is not None:
            self._sync_line_machines(
                session,
                line=production_line,
                machine_ids=machine_ids_to_sync,
                workspace_id=workspace_id,
            )

        dump['updated_by'] = user_id
        updated_line = self.production_line_dao.update(session, db_obj=production_line, obj_in=dump)

        return updated_line

    def get_production_line(
        self,
        session: Session,
        line_id: int,
        workspace_id: int
    ) -> Optional[ProductionLine]:
        """
        Get production line by ID within workspace.

        Args:
            session: Database session
            line_id: Production line ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Production line or None if not found or not in workspace

        Note:
            Returns None if line exists but doesn't belong to workspace (security)
        """
        return self.production_line_dao.get_by_id_and_workspace(
            session, id=line_id, workspace_id=workspace_id
        )

    def get_production_lines(
        self,
        session: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionLine]:
        """
        Get production lines with optional filtering.

        Args:
            session: Database session
            workspace_id: Workspace ID (for multi-tenancy)
            factory_id: Optional filter by factory
            active_only: If True, only return active lines
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production lines in workspace
        """
        if factory_id is not None:
            return self.production_line_dao.get_by_factory(
                session, factory_id=factory_id, workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif active_only:
            return self.production_line_dao.get_active_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.production_line_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def delete_production_line(
        self,
        session: Session,
        line_id: int,
        workspace_id: int
    ) -> ProductionLine:
        """
        Delete a production line (soft delete - set is_active=False).

        Args:
            session: Database session
            line_id: Production line ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Deleted production line (not yet committed)

        Raises:
            ValueError: If line not found or workspace mismatch

        Note:
            This method does NOT commit. The service layer must commit.
        """
        production_line = self.production_line_dao.get(session, id=line_id)
        if not production_line:
            raise ValueError(f"Production line {line_id} not found")

        # Validate workspace ownership
        if production_line.workspace_id != workspace_id:
            raise ValueError(f"Production line {line_id} does not belong to workspace {workspace_id}")

        # Soft delete (set is_active = False)
        return self.production_line_dao.update(
            session, db_obj=production_line, obj_in={'is_active': False}
        )

    def get_machine_ids_for_line(
        self, session: Session, *, production_line_id: int, workspace_id: int
    ) -> List[int]:
        return self.line_machine_dao.get_machine_ids_for_line(
            session, production_line_id=production_line_id, workspace_id=workspace_id
        )


# Singleton instance
production_line_manager = ProductionLineManager()
