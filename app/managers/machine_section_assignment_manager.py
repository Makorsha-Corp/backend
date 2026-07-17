"""Machine Section Assignment Manager - the optional machine -> factory section link"""
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.dao.machine_section_assignment import machine_section_assignment_dao
from app.dao.factory_section import factory_section_dao


class MachineSectionAssignmentManager:
    """Business logic for assigning/unassigning a machine's optional factory section."""

    def __init__(self):
        self.assignment_dao = machine_section_assignment_dao
        self.factory_section_dao = factory_section_dao

    def set_assignment(
        self, session: Session, *, machine_id: int, factory_id: int,
        factory_section_id: Optional[int], workspace_id: int, user_id: int,
    ) -> Optional[MachineSectionAssignment]:
        """Assign a machine to a section, or clear its assignment when
        `factory_section_id` is None. Validates the section belongs to the same
        factory as the machine and isn't deleted."""
        if factory_section_id is not None:
            section = self.factory_section_dao.get_by_id_and_workspace(
                session, id=factory_section_id, workspace_id=workspace_id
            )
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Factory section with ID {factory_section_id} not found"
                )
            if section.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign a machine to a deleted factory section"
                )
            if section.factory_id != factory_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Factory section does not belong to this machine's factory"
                )

        return self.assignment_dao.upsert_for_machine(
            session, machine_id=machine_id, factory_section_id=factory_section_id,
            workspace_id=workspace_id, user_id=user_id,
        )

    def get_for_machine(
        self, session: Session, *, machine_id: int, workspace_id: int
    ) -> Optional[MachineSectionAssignment]:
        return self.assignment_dao.get_by_machine(session, machine_id=machine_id, workspace_id=workspace_id)

    def clear_for_section(
        self, session: Session, *, factory_section_id: int, workspace_id: int
    ) -> list[int]:
        """Unassign every machine currently pointing at this section — used when the
        section itself is deleted, so machines don't reference an invisible section.
        Returns the affected machine_ids."""
        machine_ids = self.assignment_dao.clear_for_section(
            session, factory_section_id=factory_section_id, workspace_id=workspace_id
        )
        for machine_id in machine_ids:
            machine = session.get(Machine, machine_id)
            if machine is not None:
                session.expire(machine, ['section_assignment'])
        return machine_ids


machine_section_assignment_manager = MachineSectionAssignmentManager()
