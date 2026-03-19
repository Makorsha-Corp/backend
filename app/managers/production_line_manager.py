"""Production Line Manager for business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.production_line import ProductionLine
from app.dao.production_line import production_line_dao
from app.dao.factory import factory_dao
from app.dao.machine import machine_dao
from app.models.factory_section import FactorySection
from app.schemas.production_line import ProductionLineCreate, ProductionLineUpdate


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

        # Validate machine if provided
        if line_data.machine_id is not None:
            machine = machine_dao.get(session, id=line_data.machine_id)
            if not machine:
                raise ValueError(f"Machine {line_data.machine_id} not found")
            if machine.workspace_id != workspace_id:
                raise ValueError(f"Machine {line_data.machine_id} does not belong to workspace {workspace_id}")
            # Ensure machine belongs to the specified factory (via factory_section)
            factory_section = session.query(FactorySection).filter(
                FactorySection.id == machine.factory_section_id
            ).first()
            if not factory_section or factory_section.factory_id != line_data.factory_id:
                raise ValueError(
                    f"Machine {line_data.machine_id} does not belong to factory {line_data.factory_id}"
                )

        # Convert Pydantic model to dict and inject workspace/audit fields
        line_dict = line_data.model_dump()
        line_dict['workspace_id'] = workspace_id
        line_dict['created_by'] = user_id

        # Create the production line
        production_line = self.production_line_dao.create(session, obj_in=line_dict)

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

        # Validate machine if provided in update
        if line_data.machine_id is not None:
            machine = machine_dao.get(session, id=line_data.machine_id)
            if not machine:
                raise ValueError(f"Machine {line_data.machine_id} not found")
            if machine.workspace_id != workspace_id:
                raise ValueError(f"Machine {line_data.machine_id} does not belong to workspace {workspace_id}")
            # Ensure machine belongs to the production line's factory (via factory_section)
            factory_section = session.query(FactorySection).filter(
                FactorySection.id == machine.factory_section_id
            ).first()
            if not factory_section or factory_section.factory_id != production_line.factory_id:
                raise ValueError(
                    f"Machine {line_data.machine_id} does not belong to factory {production_line.factory_id}"
                )

        # Inject updated_by for audit
        line_dict = line_data.model_dump(exclude_unset=True)
        line_dict['updated_by'] = user_id

        # Update the production line
        updated_line = self.production_line_dao.update(session, db_obj=production_line, obj_in=line_dict)

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


# Singleton instance
production_line_manager = ProductionLineManager()
