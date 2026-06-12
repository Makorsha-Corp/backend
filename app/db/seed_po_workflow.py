"""Seed purchase-order stage statuses and workflow for a workspace."""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.status import Status
from app.models.order_workflow import OrderWorkflow
from app.dao.order_workflow import order_workflow_dao

PO_WORKFLOW_TYPE = 'purchase'

PO_STAGE_STATUSES = [
    {'name': 'Draft', 'comment': 'Purchase order created; sections not yet confirmed'},
    {'name': 'Planning', 'comment': 'At least one order section confirmed'},
    {'name': 'Receiving', 'comment': 'Receiving in progress on linked invoice'},
    {'name': 'Complete', 'comment': 'All line items fully received'},
]


def ensure_po_stage_statuses(db: Session, workspace_id: int) -> dict[str, int]:
    """Return name -> status id for PO stages (creates missing statuses)."""
    ids: dict[str, int] = {}
    for status_data in PO_STAGE_STATUSES:
        existing = (
            db.query(Status)
            .filter(
                Status.workspace_id == workspace_id,
                Status.name == status_data['name'],
            )
            .first()
        )
        if existing:
            ids[status_data['name']] = existing.id
            continue
        status = Status(
            workspace_id=workspace_id,
            name=status_data['name'],
            comment=status_data['comment'],
        )
        db.add(status)
        db.flush()
        ids[status_data['name']] = status.id
    return ids


def _stage_status_sequence(stage_ids: dict[str, int]) -> list[int]:
    return [
        stage_ids['Draft'],
        stage_ids['Planning'],
        stage_ids['Receiving'],
        stage_ids['Complete'],
    ]


def ensure_po_workflow_record(db: Session, workspace_id: int) -> OrderWorkflow | None:
    """
    Ensure the purchase order workflow row exists for a workspace.

    Stage statuses must already exist (call ensure_po_stage_statuses first).
    Uses a savepoint for workflow insert so a constraint failure does not roll back statuses.
    """
    stage_ids = ensure_po_stage_statuses(db, workspace_id)
    sequence = _stage_status_sequence(stage_ids)

    workflow = order_workflow_dao.get_by_type(
        db, workflow_type=PO_WORKFLOW_TYPE, workspace_id=workspace_id
    )
    if workflow:
        workflow.status_sequence = sequence
        db.flush()
        return workflow

    try:
        with db.begin_nested():
            workflow = OrderWorkflow(
                workspace_id=workspace_id,
                name='Purchase Order',
                type=PO_WORKFLOW_TYPE,
                description='Draft → Planning → Receiving → Complete',
                status_sequence=sequence,
                allowed_reverts_json=None,
            )
            db.add(workflow)
            db.flush()
        return workflow
    except IntegrityError:
        workflow = order_workflow_dao.get_by_type(
            db, workflow_type=PO_WORKFLOW_TYPE, workspace_id=workspace_id
        )
        return workflow


def seed_po_workflow(db: Session, workspace_id: int) -> OrderWorkflow:
    """
    Ensure PO stage statuses and purchase order workflow exist for a workspace.

    Does NOT commit — caller must commit.
    """
    workflow = ensure_po_workflow_record(db, workspace_id)
    if workflow is None:
        raise RuntimeError(
            f'Could not create purchase workflow for workspace {workspace_id}; '
            'run migration 022_po_stage_workflow'
        )
    return workflow


def seed_po_workflow_for_all_workspaces(db: Session) -> None:
    """Backfill PO workflow for every existing workspace."""
    from app.models.workspace import Workspace

    workspace_ids = [row[0] for row in db.query(Workspace.id).all()]
    for workspace_id in workspace_ids:
        seed_po_workflow(db, workspace_id)
