"""DAO for production line ↔ machine assignments."""
from typing import Dict, List, Sequence

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.machine import Machine
from app.models.production_line_machine import ProductionLineMachine


class ProductionLineMachineDAO(BaseDAO[ProductionLineMachine, dict, dict]):
    def get_machine_ids_for_line(
        self, db: Session, *, production_line_id: int, workspace_id: int
    ) -> List[int]:
        rows = (
            db.query(ProductionLineMachine.machine_id)
            .filter(
                ProductionLineMachine.production_line_id == production_line_id,
                ProductionLineMachine.workspace_id == workspace_id,
            )
            .order_by(ProductionLineMachine.machine_id)
            .all()
        )
        return [row[0] for row in rows]

    def get_machines_by_line_ids(
        self, db: Session, *, line_ids: Sequence[int], workspace_id: int
    ) -> Dict[int, List[Machine]]:
        if not line_ids:
            return {}
        rows = (
            db.query(ProductionLineMachine.production_line_id, Machine)
            .join(Machine, Machine.id == ProductionLineMachine.machine_id)
            .filter(
                ProductionLineMachine.workspace_id == workspace_id,
                ProductionLineMachine.production_line_id.in_(line_ids),
                Machine.is_deleted.is_(False),
            )
            .order_by(Machine.name)
            .all()
        )
        grouped: Dict[int, List[Machine]] = {line_id: [] for line_id in line_ids}
        for line_id, machine in rows:
            grouped.setdefault(line_id, []).append(machine)
        return grouped

    def replace_for_line(
        self,
        db: Session,
        *,
        production_line_id: int,
        workspace_id: int,
        machine_ids: List[int],
    ) -> None:
        db.query(ProductionLineMachine).filter(
            ProductionLineMachine.production_line_id == production_line_id,
            ProductionLineMachine.workspace_id == workspace_id,
        ).delete(synchronize_session=False)
        seen = set()
        for machine_id in machine_ids:
            if machine_id in seen:
                continue
            seen.add(machine_id)
            row = ProductionLineMachine(
                workspace_id=workspace_id,
                production_line_id=production_line_id,
                machine_id=machine_id,
            )
            db.add(row)
        db.flush()


production_line_machine_dao = ProductionLineMachineDAO(ProductionLineMachine)
