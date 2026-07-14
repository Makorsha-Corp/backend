"""DAO operations for MachineSectionAssignment (workspace-scoped)

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.machine_section_assignment import MachineSectionAssignment
from app.schemas.machine_section_assignment import MachineSectionAssignmentCreate


class DAOMachineSectionAssignment(BaseDAO[MachineSectionAssignment, MachineSectionAssignmentCreate, MachineSectionAssignmentCreate]):
    """DAO for the optional machine -> factory section link."""

    def get_by_machine(
        self, db: Session, *, machine_id: int, workspace_id: int
    ) -> Optional[MachineSectionAssignment]:
        return db.query(MachineSectionAssignment).filter(
            MachineSectionAssignment.machine_id == machine_id,
            MachineSectionAssignment.workspace_id == workspace_id,
        ).first()

    def get_by_section(
        self, db: Session, *, factory_section_id: int, workspace_id: int,
        skip: int = 0, limit: int = 500,
    ) -> List[MachineSectionAssignment]:
        return (
            db.query(MachineSectionAssignment)
            .filter(
                MachineSectionAssignment.factory_section_id == factory_section_id,
                MachineSectionAssignment.workspace_id == workspace_id,
            )
            .offset(skip).limit(limit).all()
        )

    def upsert_for_machine(
        self, db: Session, *, machine_id: int, factory_section_id: Optional[int],
        workspace_id: int, user_id: int,
    ) -> Optional[MachineSectionAssignment]:
        """Replace whatever assignment a machine has with `factory_section_id`.
        Passing None clears the assignment entirely (machine becomes unassigned)."""
        existing = self.get_by_machine(db, machine_id=machine_id, workspace_id=workspace_id)
        if existing:
            db.delete(existing)
            db.flush()
        if factory_section_id is None:
            return None
        record = MachineSectionAssignment(
            workspace_id=workspace_id, machine_id=machine_id,
            factory_section_id=factory_section_id, created_by=user_id,
        )
        db.add(record)
        db.flush()
        return record

    def clear_for_section(
        self, db: Session, *, factory_section_id: int, workspace_id: int
    ) -> List[int]:
        """Unassign every machine currently pointing at this section — used when the
        section itself is deleted. Deletes row-by-row (not a bulk DELETE) so any
        already-loaded Machine.section_assignment in this session's identity map
        gets properly invalidated. Returns the affected machine_ids."""
        rows = self.get_by_section(db, factory_section_id=factory_section_id, workspace_id=workspace_id, limit=10000)
        machine_ids = [r.machine_id for r in rows]
        for row in rows:
            db.delete(row)
        db.flush()
        return machine_ids


machine_section_assignment_dao = DAOMachineSectionAssignment(MachineSectionAssignment)
