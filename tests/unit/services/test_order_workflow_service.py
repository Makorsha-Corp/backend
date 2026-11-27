"""Unit tests for app/services/order_workflow_service.py.

Implements tests/unit/services/order_workflow_service.cases.md (revision 3), one
test per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the test's own "commit point" and the service's
commits are safe and the fixture's outer rollback discards everything.

Patched, as Conventions name them: the commit / rollback spies (they still call
the real method), the failing commit / refresh, and in the two `Author: claude`
cards the DAO object the service imports (`failing dao update` / `remove`).
Nothing else is mocked.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows are attributes of the namespace `s` (`s.W1`, `s.S1`);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117  (Conventions prescribe the nested `with`)
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, inspect, select
from sqlalchemy.exc import IntegrityError

import app.services.order_workflow_service
from app.core.exceptions import ValidationError as AppValidationError
from app.dao.order_workflow import order_workflow_dao
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.workspace import Workspace
from app.schemas.order_workflow import OrderWorkflowCreate, OrderWorkflowUpdate
from app.services.order_workflow_service import order_workflow_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = order_workflow_service
dao = order_workflow_dao

MISSING = 999999999
STEPS = "The purchase workflow's steps are managed by the system"
INUSE = "Order workflow is in use by purchase orders"
NODEL = "The purchase workflow cannot be deleted"
SYSTEM = "The purchase workflow is managed by the system"

BUG_1215 = "BUG-1215: Order workflow accepts another workspace's statuses"
BUG_1222 = "BUG-1222: Deleting an order workflow in use detaches its purchase orders"
BUG_1223 = (
    "BUG-1223: Editing the purchase workflow's steps changes which orders count as finished"
)
BUG_2385 = "BUG-2385: Blank or untrimmed order workflow names accepted"
BUG_2386 = "BUG-2386: An order workflow's description cannot be cleared"
BUG_2348 = "BUG-2348: The purchase workflow can be created through the API with any steps"
BUG_100 = "BUG-100: BaseDAO list methods have no sort order"

WF_COLS = ("workspace_id", "name", "type", "description", "status_sequence", "allowed_reverts_json")
PO_COLS = ("order_workflow_id", "current_status_id")


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db)
    n.T0 = _add(db, Status(workspace_id=n.W0.id, name="Draft", comment="Stage"))
    n.S1 = _add(db, Status(workspace_id=n.W1.id, name="Draft", comment="Stage"))
    n.S2 = _add(db, Status(workspace_id=n.W1.id, name="Approved", comment="Stage"))
    n.S3 = _add(db, Status(workspace_id=n.W1.id, name="Complete", comment="Stage"))
    n.T2 = _add(db, Status(workspace_id=n.W2.id, name="Draft", comment="Stage"))
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def _wf_fields(s, **but):
    fields = {
        "workspace_id": s.W1.id,
        "name": "Flow",
        "type": "PFM",
        "status_sequence": [s.S1.id, s.S2.id],
        "description": "Old",
        "allowed_reverts_json": {"S2": ["S1"]},
    }
    fields.update(but)
    return fields


# Convention "workflow"; "but" overrides columns
def workflow(db, s, **but):
    return _add(db, OrderWorkflow(**_wf_fields(s, **but)))


# Convention "purchase workflow"; "but" overrides columns
def purchase_workflow(db, s, **but):
    fields = {"name": "Purchase", "type": "purchase", "status_sequence": [s.S1.id, s.S2.id, s.S3.id]}
    fields.update(but)
    return workflow(db, s, **fields)


# Convention "order on F"; "but" overrides columns
def order_on(db, s, f, **but):
    fields = {
        "workspace_id": s.W1.id,
        "po_number": "PO-1",
        "destination_type": "storage",
        "destination_id": 1,
        "current_status_id": s.S1.id,
        "created_by": s.U1.id,
        "order_workflow_id": f.id,
    }
    fields.update(but)
    return _add(db, PurchaseOrder(**fields))


# Convention "X": a pending row of another table, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Convention "commit point": the test commits; snapshots are taken here
def commit_point(db):
    db.commit()
    return counts(db)


# Named check "nothing written": row counts of order_workflows and purchase_orders
def counts(db):
    return (
        db.execute(select(func.count()).select_from(OrderWorkflow)).scalar(),
        db.execute(select(func.count()).select_from(PurchaseOrder)).scalar(),
    )


# Named check "unchanged(F)": database values of F's columns
def snap_wf(db, wf_id):
    cols = [getattr(OrderWorkflow, c) for c in WF_COLS]
    row = db.execute(select(*cols).where(OrderWorkflow.id == wf_id)).one_or_none()
    return None if row is None else tuple(row)


# Named check "unchanged(P)": database values of the order's columns
def snap_po(db, po_id):
    cols = [getattr(PurchaseOrder, c) for c in PO_COLS]
    row = db.execute(select(*cols).where(PurchaseOrder.id == po_id)).one_or_none()
    return None if row is None else tuple(row)


# Named check "re-read F"
def reread_wf(db, wf_id):
    db.expire_all()
    return db.get(OrderWorkflow, wf_id)


# re-read an order
def reread_po(db, po_id):
    db.expire_all()
    return db.get(PurchaseOrder, po_id)


# count of order_workflows matching the given filters, fresh query
def wf_count(db, *where):
    return db.execute(select(func.count()).select_from(OrderWorkflow).where(*where)).scalar()


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint(
        {c.key for c in inspect(OrderWorkflow).column_attrs}
    )


# Named check "x_gone"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


# Convention "spies"
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(
        db, "rollback", wraps=db.rollback
    ) as rb:
        yield cm, rb


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(
        db, "rollback", wraps=db.rollback
    ) as rb:
        yield rb


# Convention "failing refresh"
@contextmanager
def failing_refresh(db):
    with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
        yield


# Convention "failing dao m" (Author: claude cards): the DAO object the service imports
@contextmanager
def failing_dao(m, e):
    with patch.object(app.services.order_workflow_service.order_workflow_dao, m, side_effect=e):
        yield


def mk_create(**kw):
    return OrderWorkflowCreate(**kw)


# Convention "Statement recorder": SQL statements the session sends during the When
class record_sql:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    @property
    def sql(self):
        """The text of the SELECT ... FROM order_workflows sent (the last one)."""
        hits = [
            s for s in self.statements
            if s.lstrip().upper().startswith("SELECT") and "FROM order_workflows" in s
        ]
        return hits[-1] if hits else ""

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


# --------------------------------------------------------------------------- #
# get_workflows
# --------------------------------------------------------------------------- #


# [claude] OWFS-GL-01
def test_owfs_gl_01__workspace_rows_as_set(db, s):
    """OWFS-GL-01 — returns the workspace's workflows, none of W0 or W2 (compared as a set).
    Rules: get_workflows R1 (insert-only rows; the order itself is R1a, GL-04 … GL-06)."""
    workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    a = workflow(db, s)
    b = workflow(db, s, name="Sales", type="SFM")
    workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])

    result = svc.get_workflows(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert len(result) == 2
    # Then 3
    assert {r.id for r in result} == {a.id, b.id}


# [claude] OWFS-GL-02
def test_owfs_gl_02__limit_passed_on(db, s):
    """OWFS-GL-02 — limit is passed on: 4 rows, skip=1, limit=2 give 2 of them.
    Rules: get_workflows R1."""
    a = workflow(db, s)
    b = workflow(db, s, type="SFM")
    c = workflow(db, s, type="TFM")
    d = workflow(db, s, type="WFM")

    result = svc.get_workflows(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert {r.id for r in result} <= {a.id, b.id, c.id, d.id}
    # Then 3
    assert len({r.id for r in result}) == 2


# [claude] OWFS-GL-07
def test_owfs_gl_07__skip_passed_on(db, s):
    """OWFS-GL-07 — skip is passed on: 3 rows, skip=2 give 1 of them.
    Rules: get_workflows R1."""
    a = workflow(db, s)
    b = workflow(db, s, type="SFM")
    c = workflow(db, s, type="TFM")

    result = svc.get_workflows(db, workspace_id=s.W1.id, skip=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id, c.id}


# [claude] OWFS-GL-03
def test_owfs_gl_03__default_limit_100_no_commit(db, s):
    """OWFS-GL-03 — with no skip or limit, 101 rows give 100 distinct ones; the read neither commits nor rolls back.
    Rules: get_workflows R1, R2."""
    rows = [OrderWorkflow(**_wf_fields(s, type=f"T{k}")) for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    all_ids = {r.id for r in rows}
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_workflows(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100
    assert len({r.id for r in result}) == 100
    assert {r.id for r in result} <= all_ids
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)


# [claude] OWFS-GL-04
@pytest.mark.xfail(strict=False, reason=BUG_100)
def test_owfs_gl_04__id_order_after_update(db, s):
    """OWFS-GL-04 — after an earlier row is updated, the list is still in id order.
    Rules: get_workflows R1a [BUG-100]."""
    a = workflow(db, s, name="Zed")
    b = workflow(db, s, name="Abe", type="SFM")
    a.description = "x"
    db.flush()
    db.expire_all()

    result = svc.get_workflows(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert [r.id for r in result] == [a.id, b.id]


# [claude] OWFS-GL-05
@pytest.mark.xfail(strict=False, reason=BUG_100)
def test_owfs_gl_05__paged_after_update_no_miss_no_repeat(db, s):
    """OWFS-GL-05 — paged one row at a time after an earlier row is updated, no row is missed or repeated.
    Rules: get_workflows R1a [BUG-100]."""
    a = workflow(db, s, name="Zed")
    b = workflow(db, s, name="Mid", type="SFM")
    c = workflow(db, s, name="Abe", type="TFM")
    a.description = "x"
    db.flush()
    db.expire_all()

    pages = [svc.get_workflows(db, workspace_id=s.W1.id, skip=k, limit=1) for k in range(3)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [a.id, b.id, c.id]


# [claude] OWFS-GL-06
@pytest.mark.xfail(strict=True, reason=BUG_100)
def test_owfs_gl_06__list_query_orders_by_id(db, s):
    """OWFS-GL-06 — the list query orders by id.
    Rules: get_workflows R1a [BUG-100]."""
    a = workflow(db, s, name="Zed")
    b = workflow(db, s, name="Abe", type="SFM")

    with record_sql(db) as rec:
        result = svc.get_workflows(db, workspace_id=s.W1.id)

    # Then 1
    assert {r.id for r in result} == {a.id, b.id}
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert ".id" in rec.order_part
    # Then 4
    assert "name" not in rec.order_part


# --------------------------------------------------------------------------- #
# get_by_id
# --------------------------------------------------------------------------- #


# [claude] OWFS-GI-01
def test_owfs_gi_01__returns_row_no_commit(db, s):
    """OWFS-GI-01 — returns the workflow of that id in the workspace; the read neither commits nor rolls back.
    Rules: get_by_id R1, R2."""
    workflow(db, s, type="SFM")
    f = workflow(db, s)
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, OrderWorkflow)
    # Then 2
    assert result.id == f.id
    assert result.status_sequence == [s.S1.id, s.S2.id]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] OWFS-GI-02
def test_owfs_gi_02__w0_id_none(db, s):
    """OWFS-GI-02 — a W0 workflow's id (lower) returns None.
    Rules: get_by_id R1."""
    z0 = workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    workflow(db, s)

    result = svc.get_by_id(db, workflow_id=z0.id, workspace_id=s.W1.id)

    # Then 1
    assert result is None


# [claude] OWFS-GI-03
def test_owfs_gi_03__w2_id_none(db, s):
    """OWFS-GI-03 — a W2 workflow's id (higher) returns None.
    Rules: get_by_id R1."""
    workflow(db, s)
    z2 = workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])

    result = svc.get_by_id(db, workflow_id=z2.id, workspace_id=s.W1.id)

    # Then 1
    assert result is None


# [claude] OWFS-GI-04
def test_owfs_gi_04__unknown_id_none(db, s):
    """OWFS-GI-04 — an unknown id returns None.
    Rules: get_by_id R1."""
    workflow(db, s)

    result = svc.get_by_id(db, workflow_id=MISSING, workspace_id=s.W1.id)

    # Then 1
    assert result is None


# [claude] OWFS-GI-05
def test_owfs_gi_05__id_zero_none(db, s):
    """OWFS-GI-05 — id 0 returns None.
    Rules: get_by_id R1."""
    workflow(db, s)

    result = svc.get_by_id(db, workflow_id=0, workspace_id=s.W1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# get_by_type
# --------------------------------------------------------------------------- #


# [claude] OWFS-GT-01
def test_owfs_gt_01__type_row_as_dao_no_commit(db, s):
    """OWFS-GT-01 — returns the workspace's row of that type, as the DAO does; the read neither commits nor rolls back.
    Rules: get_by_type R1, R2."""
    workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    f = workflow(db, s)
    workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_type(db, workflow_type="PFM", workspace_id=s.W1.id)

    # Then 1
    assert result.id == f.id
    # Then 2
    assert result.id == dao.get_by_type(db, workflow_type="PFM", workspace_id=s.W1.id).id
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    db.rollback()
    assert x_gone(db, x_id)


# [claude] OWFS-GT-02
def test_owfs_gt_02__other_spelling_none(db, s):
    """OWFS-GT-02 — another spelling of the type returns None.
    Rules: get_by_type R1."""
    workflow(db, s)

    result = svc.get_by_type(db, workflow_type="pfm", workspace_id=s.W1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# create_workflow
# --------------------------------------------------------------------------- #


# [claude] OWFS-C-01
def test_owfs_c_01__create_stores_every_field(db, s):
    """OWFS-C-01 — create stores every field, commits, and returns the row re-read.
    Rules: create_workflow R1, R5, TC1, TC2."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(
            name="Flow", type="PFM", description="Main",
            status_sequence=[s.S1.id, s.S2.id], allowed_reverts_json={"S2": ["S1"]},
        ),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert isinstance(result, OrderWorkflow)
    # Then 3
    assert result.id is not None
    assert result.workspace_id == s.W1.id
    rid = result.id
    # Then 4
    db.rollback()
    row = reread_wf(db, rid)
    assert row.name == "Flow"
    assert row.type == "PFM"
    assert row.description == "Main"
    # Then 5
    row = reread_wf(db, rid)
    assert row.status_sequence == [s.S1.id, s.S2.id]
    assert row.allowed_reverts_json == {"S2": ["S1"]}
    assert row.workspace_id == s.W1.id


# [claude] OWFS-C-02
def test_owfs_c_02__omitted_optionals_none(db, s):
    """OWFS-C-02 — description and allowed_reverts_json left out read back None.
    Rules: create_workflow R1."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.description is None
    assert result.allowed_reverts_json is None
    # Then 2
    db.rollback()
    row = reread_wf(db, rid)
    assert row.description is None
    assert row.allowed_reverts_json is None


# [claude] OWFS-C-03
@pytest.mark.xfail(strict=True, reason=BUG_2385)
def test_owfs_c_03__whitespace_name_refused(db, s):
    """OWFS-C-03 — a whitespace-only name is refused by the schema.
    Rules: create_workflow R2 [BUG-2385], Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        OrderWorkflowCreate(name="  ", type="PFM", status_sequence=[s.S1.id])


# [claude] OWFS-C-04
@pytest.mark.xfail(strict=True, reason=BUG_2385)
def test_owfs_c_04__empty_name_refused(db, s):
    """OWFS-C-04 — an empty name is refused by the schema.
    Rules: create_workflow R2 [BUG-2385], Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        OrderWorkflowCreate(name="", type="PFM", status_sequence=[s.S1.id])


# [claude] OWFS-C-05
@pytest.mark.xfail(strict=True, reason=BUG_2385)
def test_owfs_c_05__name_stored_trimmed(db, s):
    """OWFS-C-05 — the name is stored trimmed.
    Rules: create_workflow R2 [BUG-2385]."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name=" Flow B ", type="PFM", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.id is not None
    # Then 2
    db.rollback()
    assert reread_wf(db, rid).name == "Flow B"


# [claude] OWFS-C-06
def test_owfs_c_06__duplicate_type_integrity_error(db, s):
    """OWFS-C-06 — a second workflow of the type in the workspace: IntegrityError, rolled back with other pending changes.
    Rules: create_workflow R3, R7, TC3, Errors row 1."""
    f = workflow(db, s)
    before = commit_point(db)
    before_f = snap_wf(db, f.id)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(name="Other", type="PFM", status_sequence=[s.S2.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_order_workflows_workspace_type" in str(exc.value)
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before
    # Then 7
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-C-07
def test_owfs_c_07__same_type_other_workspaces_ok(db, s):
    """OWFS-C-07 — the same type in W0 and W2 does not stop a create in W1.
    Rules: create_workflow R3."""
    workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.workspace_id == s.W1.id
    # Then 2
    db.rollback()
    assert wf_count(db, OrderWorkflow.type == "PFM") == 3


# [claude] OWFS-C-08
def test_owfs_c_08__type_exact_lowercase_second_row(db, s):
    """OWFS-C-08 — the type is exact: "pfm" next to "PFM" is a second row.
    Rules: create_workflow R3."""
    workflow(db, s)
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Lower", type="pfm", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.type == "pfm"
    # Then 2
    db.rollback()
    assert wf_count(db, OrderWorkflow.workspace_id == s.W1.id) == 2


# [claude] OWFS-C-09
def test_owfs_c_09__type_exact_leading_space_stored(db, s):
    """OWFS-C-09 — the type is exact: " PFM" next to "PFM" is a second row, stored as sent.
    Rules: create_workflow R3."""
    workflow(db, s)
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Spaced", type=" PFM", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.type == " PFM"
    # Then 2
    db.rollback()
    assert reread_wf(db, rid).type == " PFM"


# [claude] OWFS-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_c_10__w0_status_refused(db, s):
    """OWFS-C-10 — a status of W0 (lower id) in the sequence is refused as not found.
    Rules: create_workflow R4 [BUG-1215], Errors row 2."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Flow", type="PFM", status_sequence=[s.S1.id, s.T0.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Status with ID {s.T0.id} not found"
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] OWFS-C-11
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_c_11__w2_status_refused(db, s):
    """OWFS-C-11 — a status of W2 (higher id) in the sequence is refused as not found.
    Rules: create_workflow R4 [BUG-1215], Errors row 2."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Flow", type="PFM", status_sequence=[s.T2.id, s.S1.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Status with ID {s.T2.id} not found"
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] OWFS-C-12
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_c_12__unknown_status_refused(db, s):
    """OWFS-C-12 — an unknown status id is refused as not found.
    Rules: create_workflow R4 [BUG-1215], Errors row 2."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[MISSING]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Status with ID 999999999 not found"
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert counts(db) == before


# [claude] OWFS-C-13
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_c_13__first_bad_id_named(db, s):
    """OWFS-C-13 — with two bad ids the first one in the list is named.
    Rules: create_workflow R4 [BUG-1215]."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Flow", type="PFM", status_sequence=[s.S1.id, MISSING, s.T0.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.detail == "Status with ID 999999999 not found"
    # Then 3
    assert counts(db) == before


# [claude] OWFS-C-14
def test_owfs_c_14__empty_sequence_stored(db, s):
    """OWFS-C-14 — an empty sequence is stored as [].
    Rules: create_workflow R5."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[]),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.status_sequence == []
    # Then 2
    db.rollback()
    assert reread_wf(db, rid).status_sequence == []


# [claude] OWFS-C-15
def test_owfs_c_15__repeated_ids_stored(db, s):
    """OWFS-C-15 — repeated ids are stored as sent.
    Rules: create_workflow R5."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(
            name="Flow", type="PFM", status_sequence=[s.S2.id, s.S1.id, s.S2.id]
        ),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.status_sequence == [s.S2.id, s.S1.id, s.S2.id]
    # Then 2
    db.rollback()
    assert reread_wf(db, rid).status_sequence == [s.S2.id, s.S1.id, s.S2.id]


# [claude] OWFS-C-16
def test_owfs_c_16__failing_refresh_keeps_saved(db, s):
    """OWFS-C-16 — a failing re-read after the commit leaves the workflow saved.
    Rules: create_workflow R7, TC5."""
    commit_point(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_workflow(
                db,
                workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[s.S1.id]),
                workspace_id=s.W1.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    rows = db.execute(
        select(OrderWorkflow).where(
            OrderWorkflow.workspace_id == s.W1.id, OrderWorkflow.type == "PFM"
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Flow"


# --------------------------------------------------------------------------- #
# update_workflow
# --------------------------------------------------------------------------- #


# [claude] OWFS-U-01
def test_owfs_u_01__sent_fields_set_rest_stay(db, s):
    """OWFS-U-01 — sent fields are set, the rest stay; committed and returned re-read.
    Rules: update_workflow R2, TC1, TC2."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id,
        workflow_in=OrderWorkflowUpdate(name="Flow B", description="New"),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == f.id
    # Then 3
    db.rollback()
    row = reread_wf(db, f.id)
    assert row.name == "Flow B"
    assert row.description == "New"
    # Then 4
    row = reread_wf(db, f.id)
    assert row.type == "PFM"
    assert row.status_sequence == [s.S1.id, s.S2.id]
    assert row.allowed_reverts_json == {"S2": ["S1"]}


# [claude] OWFS-U-02
def test_owfs_u_02__only_name_sent_others_keep(db, s):
    """OWFS-U-02 — only the name sent: description, sequence and reverts keep their values.
    Rules: update_workflow R2, R7 (omitted fields stay)."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(name="Flow B"), workspace_id=s.W1.id
    )

    # Then 1
    assert result.name == "Flow B"
    # Then 2
    db.rollback()
    row = reread_wf(db, f.id)
    assert row.description == "Old"
    assert row.status_sequence == [s.S1.id, s.S2.id]
    assert row.allowed_reverts_json == {"S2": ["S1"]}


# [claude] OWFS-U-03
def test_owfs_u_03__own_sequence_replaces(db, s):
    """OWFS-U-03 — a sent sequence of own statuses replaces the list.
    Rules: update_workflow R9."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id,
        workflow_in=OrderWorkflowUpdate(status_sequence=[s.S3.id, s.S1.id]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.status_sequence == [s.S3.id, s.S1.id]
    # Then 2
    db.rollback()
    row = reread_wf(db, f.id)
    assert row.status_sequence == [s.S3.id, s.S1.id]
    assert row.name == "Flow"


# [claude] OWFS-U-04
def test_owfs_u_04__empty_sequence_stored(db, s):
    """OWFS-U-04 — an empty sequence is stored as [].
    Rules: update_workflow R9."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.status_sequence == []
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).status_sequence == []


# [claude] OWFS-U-05
def test_owfs_u_05__repeated_ids_stored(db, s):
    """OWFS-U-05 — repeated ids are stored as sent.
    Rules: update_workflow R9."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.S2.id, s.S2.id]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.status_sequence == [s.S2.id, s.S2.id]
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).status_sequence == [s.S2.id, s.S2.id]


# [claude] OWFS-U-06
def test_owfs_u_06__reverts_replaced(db, s):
    """OWFS-U-06 — allowed_reverts_json is replaced when sent.
    Rules: update_workflow R2."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id,
        workflow_in=OrderWorkflowUpdate(allowed_reverts_json={"S3": ["S2"]}),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.allowed_reverts_json == {"S3": ["S2"]}
    # Then 2
    db.rollback()
    row = reread_wf(db, f.id)
    assert row.allowed_reverts_json == {"S3": ["S2"]}
    assert row.description == "Old"


# [claude] OWFS-U-07
def test_owfs_u_07__w0_id_none_nothing_written(db, s):
    """OWFS-U-07 — a W0 workflow's id (lower) returns None, nothing written.
    Rules: update_workflow R1."""
    z0 = workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    workflow(db, s)
    before = commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=z0.id, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=s.W1.id
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.new and not db.dirty and not db.deleted
    # Then 3
    db.rollback()
    assert reread_wf(db, z0.id).name == "Flow"
    # Then 4
    assert counts(db) == before


# [claude] OWFS-U-08
def test_owfs_u_08__w2_id_none_nothing_written(db, s):
    """OWFS-U-08 — a W2 workflow's id (higher) returns None, nothing written.
    Rules: update_workflow R1."""
    workflow(db, s)
    z2 = workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    before = commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=z2.id, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=s.W1.id
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.new and not db.dirty and not db.deleted
    # Then 3
    db.rollback()
    assert reread_wf(db, z2.id).name == "Flow"
    # Then 4
    assert counts(db) == before


# [claude] OWFS-U-09
def test_owfs_u_09__unknown_id_none(db, s):
    """OWFS-U-09 — an unknown id returns None.
    Rules: update_workflow R1."""
    f = workflow(db, s)
    before = commit_point(db)
    before_f = snap_wf(db, f.id)

    result = svc.update_workflow(
        db, workflow_id=MISSING, workflow_in=OrderWorkflowUpdate(name="Hacked"),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result is None
    # Then 2
    assert not db.new and not db.dirty and not db.deleted
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-10
def test_owfs_u_10__id_zero_no_commit_no_rollback(db, s):
    """OWFS-U-10 — id 0 returns None with no commit and no rollback: a pending row stays pending.
    Rules: update_workflow R1, R3."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.update_workflow(
            db, workflow_id=0, workflow_in=OrderWorkflowUpdate(name="Hacked"),
            workspace_id=s.W1.id,
        )

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)
    # Then 6
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-11
def test_owfs_u_11__update_schema_has_no_type():
    """OWFS-U-11 — the update schema has no type field.
    Rules: update_workflow R4."""
    # Then 1
    assert "type" not in OrderWorkflowUpdate.model_fields


# [claude] OWFS-U-12
@pytest.mark.xfail(strict=True, reason=BUG_2385)
def test_owfs_u_12__sent_name_stored_trimmed(db, s):
    """OWFS-U-12 — a sent name is stored trimmed.
    Rules: update_workflow R5 [BUG-2385]."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(name=" Flow B "),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.id == f.id
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).name == "Flow B"


# [claude] OWFS-U-13
@pytest.mark.xfail(strict=True, reason=BUG_2385)
def test_owfs_u_13__whitespace_name_refused():
    """OWFS-U-13 — a whitespace-only name is refused by the update schema.
    Rules: update_workflow R5 [BUG-2385], Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        OrderWorkflowUpdate(name="  ")


# [claude] OWFS-U-14
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_u_14__w0_status_refused(db, s):
    """OWFS-U-14 — a sent status of W0 (lower id) is refused as not found.
    Rules: update_workflow R6 [BUG-1215], Errors row 1."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id,
            workflow_in=OrderWorkflowUpdate(status_sequence=[s.S1.id, s.T0.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Status with ID {s.T0.id} not found"
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-15
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_u_15__w2_status_refused(db, s):
    """OWFS-U-15 — a sent status of W2 (higher id) is refused as not found.
    Rules: update_workflow R6 [BUG-1215], Errors row 1."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.T2.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Status with ID {s.T2.id} not found"
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-16
@pytest.mark.xfail(strict=True, reason=BUG_1215)
def test_owfs_u_16__unknown_status_refused_name_not_stored(db, s):
    """OWFS-U-16 — a sent unknown status id is refused, and the name sent with it is not stored.
    Rules: update_workflow R6 [BUG-1215], Errors row 1."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id,
            workflow_in=OrderWorkflowUpdate(name="Flow B", status_sequence=[MISSING]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.detail == "Status with ID 999999999 not found"
    # Then 3
    assert not db.new and not db.dirty and not db.deleted
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-17
@pytest.mark.xfail(strict=True, reason=BUG_2386)
def test_owfs_u_17__null_clears_description(db, s):
    """OWFS-U-17 — an explicit null clears the description.
    Rules: update_workflow R7 [BUG-2386]."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(description=None),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.id == f.id
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).description is None
    # Then 3
    row = reread_wf(db, f.id)
    assert row.name == "Flow"
    assert row.allowed_reverts_json == {"S2": ["S1"]}


# [claude] OWFS-U-18
@pytest.mark.xfail(strict=True, reason=BUG_2386)
def test_owfs_u_18__null_clears_reverts(db, s):
    """OWFS-U-18 — an explicit null clears allowed_reverts_json.
    Rules: update_workflow R7 [BUG-2386]."""
    f = workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(allowed_reverts_json=None),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.id == f.id
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).allowed_reverts_json is None
    # Then 3
    assert reread_wf(db, f.id).description == "Old"


# [claude] OWFS-U-19
@pytest.mark.xfail(strict=True, reason=BUG_2386)
def test_owfs_u_19__null_name_refused():
    """OWFS-U-19 — an explicit null name is refused by the update schema.
    Rules: update_workflow R7 [BUG-2386], Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        OrderWorkflowUpdate(name=None)


# [claude] OWFS-U-20
@pytest.mark.xfail(strict=True, reason=BUG_2386)
def test_owfs_u_20__null_sequence_refused():
    """OWFS-U-20 — an explicit null sequence is refused by the update schema.
    Rules: update_workflow R7 [BUG-2386], Errors row 3."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        OrderWorkflowUpdate(status_sequence=None)


# [claude] OWFS-U-21
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_21__purchase_new_sequence_refused(db, s):
    """OWFS-U-21 — on purchase, a new sequence is refused.
    Rules: update_workflow R8 [BUG-1223], Errors row 2."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.S1.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STEPS
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-22
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_22__purchase_same_sequence_refused(db, s):
    """OWFS-U-22 — on purchase, the current sequence sent again is refused too.
    Rules: update_workflow R8 [BUG-1223]."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id,
            workflow_in=OrderWorkflowUpdate(status_sequence=[s.S1.id, s.S2.id, s.S3.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STEPS
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-23
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_23__purchase_sequence_with_name_neither_stored(db, s):
    """OWFS-U-23 — on purchase, a sequence with a name: neither is stored.
    Rules: update_workflow R8 [BUG-1223]."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id,
            workflow_in=OrderWorkflowUpdate(name="Buying", status_sequence=[s.S1.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.detail == STEPS
    # Then 3
    assert not db.new and not db.dirty and not db.deleted
    # Then 4
    db.rollback()
    assert reread_wf(db, f.id).name == "Purchase"
    # Then 5
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-24
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_24__purchase_empty_sequence_refused(db, s):
    """OWFS-U-24 — on purchase, an empty sequence is refused.
    Rules: update_workflow R8 [BUG-1223]."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.detail == STEPS
    # Then 3
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-25
def test_owfs_u_25__purchase_other_fields_change(db, s):
    """OWFS-U-25 — on purchase, name, description and reverts alone may still change.
    Rules: update_workflow R8, R2."""
    f = purchase_workflow(db, s)
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id,
        workflow_in=OrderWorkflowUpdate(
            name="Buying", description="New", allowed_reverts_json={"S3": ["S2"]}
        ),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.id == f.id
    # Then 2
    db.rollback()
    row = reread_wf(db, f.id)
    assert row.name == "Buying"
    assert row.description == "New"
    assert row.allowed_reverts_json == {"S3": ["S2"]}
    # Then 3
    row = reread_wf(db, f.id)
    assert row.status_sequence == [s.S1.id, s.S2.id, s.S3.id]
    assert row.type == "purchase"


# [claude] OWFS-U-26
def test_owfs_u_26__capital_purchase_sequence_may_change(db, s):
    """OWFS-U-26 — type "Purchase" in capitals is not the purchase row: its sequence may change.
    Rules: update_workflow R8, R9."""
    f = workflow(db, s, type="Purchase")
    commit_point(db)

    result = svc.update_workflow(
        db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )

    # Then 1
    assert result.status_sequence == [s.S1.id]
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id).status_sequence == [s.S1.id]


# [claude] OWFS-U-27
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_27__refusal_rolls_back_pending(db, s):
    """OWFS-U-27 — a refusal rolls back other pending changes in the session too.
    Rules: update_workflow R10, TC3 [BUG-1223]."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException):
        svc.update_workflow(
            db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.S1.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert x not in db
    # Then 3
    db.rollback()
    assert x_gone(db, x_id)
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-28
def test_owfs_u_28__failing_commit_one_rollback(db, s):
    """OWFS-U-28 — a failing commit gives exactly one rollback, and nothing is saved.
    Rules: update_workflow R10, TC4."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    _x, x_id = mk_x(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_workflow(
                db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(name="Flow B"),
                workspace_id=s.W1.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count == 1
    # Then 3
    db.rollback()
    assert x_gone(db, x_id)
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-29
def test_owfs_u_29__dao_error_rolls_back_same_object(db, s):
    """OWFS-U-29 — an error inside the update rolls back, reaches the caller as the same object, and discards other pending changes.
    Rules: update_workflow R10, TC3."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    x, x_id = mk_x(db)
    e = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with failing_dao("update", e):
            svc.update_workflow(
                db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(name="Flow B"),
                workspace_id=s.W1.id,
            )

    # Then 1
    assert exc.value is e
    # Then 2
    assert x not in db
    # Then 3
    assert db.execute(select(func.count()).select_from(OrderWorkflow)).scalar() >= 1
    # Then 4
    db.rollback()
    assert x_gone(db, x_id)
    # Then 5
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-U-30
@pytest.mark.xfail(strict=True, reason=BUG_1223)
def test_owfs_u_30__purchase_foreign_status_400_before_404(db, s):
    """OWFS-U-30 — on purchase, a sequence with a status of W2 gets the 400, not the status 404.
    Rules: update_workflow R8 [BUG-1223], R6."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_workflow(
            db, workflow_id=f.id, workflow_in=OrderWorkflowUpdate(status_sequence=[s.T2.id]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == STEPS
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert snap_wf(db, f.id) == before_f


# --------------------------------------------------------------------------- #
# delete_workflow
# --------------------------------------------------------------------------- #


# [claude] OWFS-D-01
def test_owfs_d_01__unused_workflow_deleted(db, s):
    """OWFS-D-01 — a workflow no order uses is deleted and committed.
    Rules: delete_workflow R2, TC1."""
    b = workflow(db, s, type="SFM")
    f = workflow(db, s)
    commit_point(db)

    result = svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id) is None
    # Then 3
    assert reread_wf(db, b.id) is not None


# [claude] OWFS-D-02
def test_owfs_d_02__w0_id_false(db, s):
    """OWFS-D-02 — a W0 workflow's id (lower) returns False and deletes nothing.
    Rules: delete_workflow R1."""
    z0 = workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    workflow(db, s)
    before = commit_point(db)

    result = svc.delete_workflow(db, workflow_id=z0.id, workspace_id=s.W1.id)

    # Then 1
    assert result is False
    # Then 2
    assert not db.deleted
    # Then 3
    db.rollback()
    assert reread_wf(db, z0.id) is not None
    # Then 4
    assert counts(db) == before


# [claude] OWFS-D-03
def test_owfs_d_03__w2_id_false(db, s):
    """OWFS-D-03 — a W2 workflow's id (higher) returns False and deletes nothing.
    Rules: delete_workflow R1."""
    workflow(db, s)
    z2 = workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    before = commit_point(db)

    result = svc.delete_workflow(db, workflow_id=z2.id, workspace_id=s.W1.id)

    # Then 1
    assert result is False
    # Then 2
    assert not db.deleted
    # Then 3
    db.rollback()
    assert reread_wf(db, z2.id) is not None
    # Then 4
    assert counts(db) == before


# [claude] OWFS-D-04
def test_owfs_d_04__unknown_id_false(db, s):
    """OWFS-D-04 — an unknown id returns False.
    Rules: delete_workflow R1."""
    workflow(db, s)
    before = commit_point(db)

    result = svc.delete_workflow(db, workflow_id=MISSING, workspace_id=s.W1.id)

    # Then 1
    assert result is False
    # Then 2
    assert not db.deleted
    # Then 3
    assert counts(db) == before


# [claude] OWFS-D-05
def test_owfs_d_05__id_zero_no_commit_no_rollback(db, s):
    """OWFS-D-05 — id 0 returns False with no commit and no rollback: a pending row stays pending.
    Rules: delete_workflow R1, R3."""
    f = workflow(db, s)
    commit_point(db)
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.delete_workflow(db, workflow_id=0, workspace_id=s.W1.id)

    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert x in db
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)
    # Then 6
    assert reread_wf(db, f.id) is not None


# [claude] OWFS-D-06
def test_owfs_d_06__order_on_other_workflow_no_block(db, s):
    """OWFS-D-06 — an order on another workflow does not block the delete.
    Rules: delete_workflow R2, R4."""
    g = workflow(db, s, type="SFM")
    f = workflow(db, s)
    p = order_on(db, s, g)
    commit_point(db)

    result = svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id) is None
    # Then 3
    assert reread_po(db, p.id).order_workflow_id == g.id


# [claude] OWFS-D-07
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_07__in_use_refused_order_listed(db, s):
    """OWFS-D-07 — a workflow one order uses is refused, the order listed.
    Rules: delete_workflow R4 [BUG-1222], Errors row 1."""
    f = workflow(db, s)
    p = order_on(db, s, f)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == INUSE
    # Then 4
    assert exc.value.errors == [{"type": "purchase_order", "id": p.id}]
    # Then 5
    assert not db.deleted and not db.dirty
    # Then 6
    assert snap_wf(db, f.id) == before_f
    # Then 7
    assert reread_po(db, p.id).order_workflow_id == f.id


# [claude] OWFS-D-08
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_08__two_orders_listed_in_id_order(db, s):
    """OWFS-D-08 — two orders, one at the last (finished) step: both listed, in id order.
    Rules: delete_workflow R4 [BUG-1222]."""
    f = workflow(db, s)
    p1 = order_on(db, s, f)
    p2 = order_on(db, s, f, po_number="PO-2", current_status_id=s.S2.id)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == INUSE
    # Then 3
    assert exc.value.errors == [
        {"type": "purchase_order", "id": p1.id},
        {"type": "purchase_order", "id": p2.id},
    ]
    # Then 4
    assert snap_wf(db, f.id) == before_f
    # Then 5
    assert reread_po(db, p2.id).order_workflow_id == f.id


# [claude] OWFS-D-09
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_09__only_w2_order_other_workspace_entry(db, s):
    """OWFS-D-09 — only an order of W2 points at it: one other_workspace entry, no id.
    Rules: delete_workflow R4 [BUG-1222] (HR-16)."""
    f = workflow(db, s)
    p = order_on(db, s, f, workspace_id=s.W2.id, current_status_id=s.T2.id)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == INUSE
    # Then 3
    assert exc.value.errors == [{"type": "other_workspace"}]
    # Then 4
    assert snap_wf(db, f.id) == before_f
    # Then 5
    assert reread_po(db, p.id).order_workflow_id == f.id


# [claude] OWFS-D-10
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_10__only_w0_order_other_workspace_entry(db, s):
    """OWFS-D-10 — only an order of W0 points at it: one other_workspace entry, no id.
    Rules: delete_workflow R4 [BUG-1222] (HR-16)."""
    f = workflow(db, s)
    p = order_on(db, s, f, workspace_id=s.W0.id, current_status_id=s.T0.id)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.errors == [{"type": "other_workspace"}]
    # Then 3
    assert snap_wf(db, f.id) == before_f
    # Then 4
    assert reread_po(db, p.id).order_workflow_id == f.id


# [claude] OWFS-D-11
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_11__own_and_w2_order_foreign_last(db, s):
    """OWFS-D-11 — an own order and an order of W2: the own entry, then the foreign one without id, last.
    Rules: delete_workflow R4 [BUG-1222] (HR-16)."""
    f = workflow(db, s)
    p1 = order_on(db, s, f)
    order_on(db, s, f, po_number="PO-2", workspace_id=s.W2.id, current_status_id=s.T2.id)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == INUSE
    # Then 3
    assert exc.value.errors == [{"type": "purchase_order", "id": p1.id}, {"type": "other_workspace"}]
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-D-12
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_12__purchase_never_deleted(db, s):
    """OWFS-D-12 — the purchase workflow is never deleted, even with no orders.
    Rules: delete_workflow R5 [BUG-1222], Errors row 2."""
    f = purchase_workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == NODEL
    # Then 4
    assert exc.value.errors == []
    # Then 5
    assert not db.deleted
    # Then 6
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-D-13
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_13__purchase_with_order_purchase_answer(db, s):
    """OWFS-D-13 — the purchase workflow with an order gets the purchase answer, not the in-use one.
    Rules: delete_workflow R5 [BUG-1222]."""
    f = purchase_workflow(db, s)
    p = order_on(db, s, f)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == NODEL
    # Then 3
    assert exc.value.errors == []
    # Then 4
    assert snap_wf(db, f.id) == before_f
    # Then 5
    assert reread_po(db, p.id).order_workflow_id == f.id


# [claude] OWFS-D-14
def test_owfs_d_14__failing_commit_rolls_back(db, s):
    """OWFS-D-14 — a failing commit rolls back: the workflow stays, other pending changes go.
    Rules: delete_workflow R6, TC4."""
    f = workflow(db, s)
    commit_point(db)
    _x, x_id = mk_x(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    db.rollback()
    assert x_gone(db, x_id)
    # Then 4
    assert reread_wf(db, f.id) is not None


# [claude] OWFS-D-15
def test_owfs_d_15__capital_purchase_deleted(db, s):
    """OWFS-D-15 — type "Purchase" in capitals is not the purchase row: it is deleted.
    Rules: delete_workflow R2, R5."""
    f = workflow(db, s, type="Purchase")
    commit_point(db)

    result = svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id) is None


# [claude] OWFS-D-16
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_16__refusal_rolls_back_pending(db, s):
    """OWFS-D-16 — a refusal rolls back other pending changes in the session too.
    Rules: delete_workflow R6, TC3 [BUG-1222]."""
    f = workflow(db, s)
    order_on(db, s, f)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(AppValidationError):
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert x not in db
    # Then 3
    db.rollback()
    assert x_gone(db, x_id)
    # Then 4
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-D-17
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_17__refused_delete_keeps_order_link(db, s):
    """OWFS-D-17 — the refused delete leaves the order's link as it was (session side).
    Rules: delete_workflow R4 [BUG-1222]."""
    f = workflow(db, s)
    p = order_on(db, s, f, current_status_id=s.S2.id)
    commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError):
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert not db.dirty and not db.deleted
    # Then 3
    db.rollback()
    row = reread_po(db, p.id)
    assert row.order_workflow_id == f.id
    assert row.current_status_id == s.S2.id


# [claude] OWFS-D-18
def test_owfs_d_18__w2_order_on_w2_workflow_no_block(db, s):
    """OWFS-D-18 — an order of W2 on a W2 workflow does not block deleting a W1 workflow.
    Rules: delete_workflow R2."""
    f = workflow(db, s)
    z2 = workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    p = order_on(db, s, z2, workspace_id=s.W2.id, current_status_id=s.T2.id)
    commit_point(db)

    result = svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert reread_wf(db, f.id) is None
    # Then 3
    assert reread_po(db, p.id).order_workflow_id == z2.id


# [claude] OWFS-D-19
def test_owfs_d_19__delete_commits_once(db, s):
    """OWFS-D-19 — delete commits once.
    Rules: delete_workflow R2, TC1."""
    f = workflow(db, s)
    commit_point(db)

    with spies(db) as (cm, rb):
        result = svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert result is True
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0


# [claude] OWFS-D-20
def test_owfs_d_20__dao_error_rolls_back_same_object(db, s):
    """OWFS-D-20 — an error inside the delete rolls back, reaches the caller as the same object, and discards other pending changes.
    Rules: delete_workflow R6, TC3."""
    f = workflow(db, s)
    commit_point(db)
    before_f = snap_wf(db, f.id)
    x, x_id = mk_x(db)
    e = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with failing_dao("remove", e):
            svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)

    # Then 1
    assert exc.value is e
    # Then 2
    assert x not in db
    # Then 3
    assert db.execute(select(func.count()).select_from(OrderWorkflow)).scalar() >= 1
    # Then 4
    db.rollback()
    assert x_gone(db, x_id)
    # Then 5
    assert reread_wf(db, f.id) is not None
    # Then 6
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-D-21
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_21__w0_lower_id_entry_still_last(db, s):
    """OWFS-D-21 — an order of W0 with a lower id than the own order: its entry is still last.
    Rules: delete_workflow R4 [BUG-1222] (HR-16)."""
    f = workflow(db, s)
    p0 = order_on(db, s, f, po_number="PO-0", workspace_id=s.W0.id, current_status_id=s.T0.id)
    p1 = order_on(db, s, f)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.errors == [{"type": "purchase_order", "id": p1.id}, {"type": "other_workspace"}]
    # Then 3
    assert not db.dirty and not db.deleted
    # Then 4
    assert snap_wf(db, f.id) == before_f
    # Then 5
    assert reread_po(db, p0.id).order_workflow_id == f.id


# [claude] OWFS-D-22
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_22__w0_and_w2_orders_one_entry_last(db, s):
    """OWFS-D-22 — orders of W0 and of W2 beside an own order: one other_workspace entry, last.
    Rules: delete_workflow R4 [BUG-1222] (HR-16)."""
    f = workflow(db, s)
    order_on(db, s, f, po_number="PO-0", workspace_id=s.W0.id, current_status_id=s.T0.id)
    p1 = order_on(db, s, f)
    p2 = order_on(db, s, f, po_number="PO-2", workspace_id=s.W2.id, current_status_id=s.T2.id)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.errors == [{"type": "purchase_order", "id": p1.id}, {"type": "other_workspace"}]
    # Then 3
    assert snap_wf(db, f.id) == before_f
    # Then 4
    assert reread_po(db, p2.id).order_workflow_id == f.id


# [claude] OWFS-D-23
@pytest.mark.xfail(strict=True, reason=BUG_1222)
def test_owfs_d_23__voided_order_blocks(db, s):
    """OWFS-D-23 — a voided order blocks the delete and is listed.
    Rules: delete_workflow R4 [BUG-1222]."""
    f = workflow(db, s)
    p = order_on(db, s, f, voided=True)
    commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_workflow(db, workflow_id=f.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == INUSE
    # Then 3
    assert exc.value.errors == [{"type": "purchase_order", "id": p.id}]
    # Then 4
    assert not db.dirty and not db.deleted
    # Then 5
    assert snap_wf(db, f.id) == before_f
    # Then 6
    row = reread_po(db, p.id)
    assert row.order_workflow_id == f.id
    assert row.voided is True


# --------------------------------------------------------------------------- #
# OQ-24 answered — BUG-2348 (create_workflow R6)
# --------------------------------------------------------------------------- #


# [claude] OWFS-Q24-01
@pytest.mark.xfail(strict=True, reason=BUG_2348)
def test_owfs_q24_01__purchase_refused_beside_foreign(db, s):
    """OWFS-Q24-01 — purchase is refused where W1 has none, beside W0's and W2's; pending changes discarded.
    Rules: create_workflow R6 [BUG-2348], Errors row 4, R7."""
    purchase_workflow(db, s, workspace_id=s.W0.id, status_sequence=[s.T0.id])
    purchase_workflow(db, s, workspace_id=s.W2.id, status_sequence=[s.T2.id])
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Purchase", type="purchase", status_sequence=[s.S1.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SYSTEM
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    db.rollback()
    assert x_gone(db, x_id)
    # Then 6
    assert counts(db) == before
    # Then 7
    assert wf_count(db, OrderWorkflow.type == "purchase") == 2


# [claude] OWFS-Q24-02
@pytest.mark.xfail(strict=True, reason=BUG_2348)
def test_owfs_q24_02__purchase_empty_list_refused(db, s):
    """OWFS-Q24-02 — purchase with an empty list is refused.
    Rules: create_workflow R6 [BUG-2348]."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[]),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SYSTEM
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


# [claude] OWFS-Q24-03
@pytest.mark.xfail(strict=True, reason=BUG_2348)
def test_owfs_q24_03__existing_purchase_400_before_duplicate(db, s):
    """OWFS-Q24-03 — where W1 already has purchase: the 400, not the duplicate error.
    Rules: create_workflow R6 [BUG-2348], R3."""
    f = purchase_workflow(db, s)
    before = commit_point(db)
    before_f = snap_wf(db, f.id)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Purchase", type="purchase", status_sequence=[s.S1.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SYSTEM
    # Then 4
    assert not db.new and not db.dirty and not db.deleted
    # Then 5
    assert counts(db) == before
    # Then 6
    assert snap_wf(db, f.id) == before_f


# [claude] OWFS-Q24-04
@pytest.mark.xfail(strict=True, reason=BUG_2348)
def test_owfs_q24_04__purchase_foreign_status_400_before_404(db, s):
    """OWFS-Q24-04 — purchase with a status of W2: the 400, not the status 404.
    Rules: create_workflow R6 [BUG-2348], R4."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Purchase", type="purchase", status_sequence=[s.T2.id]
            ),
            workspace_id=s.W1.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == SYSTEM
    # Then 4
    assert not db.new
    # Then 5
    assert counts(db) == before


# [claude] OWFS-Q24-05
def test_owfs_q24_05__capital_purchase_ordinary(db, s):
    """OWFS-Q24-05 — type "Purchase" in capitals is an ordinary type and is created.
    Rules: create_workflow R6, R3."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(name="Purchase", type="Purchase", status_sequence=[s.S1.id]),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.id is not None
    assert result.type == "Purchase"
    # Then 2
    db.rollback()
    row = reread_wf(db, rid)
    assert row.type == "Purchase"
    assert row.status_sequence == [s.S1.id]


# [claude] OWFS-Q24-06
def test_owfs_q24_06__leading_space_purchase_ordinary(db, s):
    """OWFS-Q24-06 — type " purchase" with a leading space is an ordinary type, stored as sent.
    Rules: create_workflow R6, R3."""
    commit_point(db)

    result = svc.create_workflow(
        db,
        workflow_in=OrderWorkflowCreate(
            name="Purchase", type=" purchase", status_sequence=[s.S1.id]
        ),
        workspace_id=s.W1.id,
    )
    rid = result.id

    # Then 1
    assert result.id is not None
    assert result.type == " purchase"
    # Then 2
    db.rollback()
    assert reread_wf(db, rid).type == " purchase"


# [claude] OWFS-Q24-07
def test_owfs_q24_07__second_purchase_never_stored(db, s):
    """OWFS-Q24-07 — a second purchase row in W1 is never stored, whichever refusal answers.
    Rules: create_workflow R6, R3, R7."""
    f = purchase_workflow(db, s)
    before = commit_point(db)
    before_f = snap_wf(db, f.id)

    with pytest.raises((IntegrityError, HTTPException)) as exc:
        svc.create_workflow(
            db,
            workflow_in=OrderWorkflowCreate(
                name="Purchase", type="purchase", status_sequence=[s.S1.id]
            ),
            workspace_id=s.W1.id,
        )

    # Then 1
    assert isinstance(exc.value, (IntegrityError, HTTPException))
    # Then 2
    assert not db.new and not db.dirty and not db.deleted
    # Then 3
    assert counts(db) == before
    # Then 4
    assert snap_wf(db, f.id) == before_f
