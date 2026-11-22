"""Unit tests for app/dao/order_workflow.py.

Implements tests/unit/dao/order_workflow.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.order_workflow import order_workflow_dao
from app.db.seed_po_workflow import seed_po_workflow
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton order_workflow_dao" (a module-level name, not a fixture)
dao = order_workflow_dao


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1 = a profiles row"
@pytest.fixture
def u1(db):
    return make_profile(db)


# Convention "They exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "workflow": description and allowed_reverts_json are not passed unless the card lists them
@pytest.fixture
def mk_workflow(db, w1):
    """mk_workflow(**columns) -> OrderWorkflow. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "name": "Flow", "type": "PFM", "status_sequence": [11, 22, 33]}
        fields.update(columns)
        return _add(db, OrderWorkflow(**fields))
    return _mk


# Convention "order on F": a status S, flushed, then the purchase order
@pytest.fixture
def mk_order(db, w1, u1):
    """mk_order(workflow) -> PurchaseOrder."""
    def _mk(workflow):
        status = _add(db, Status(workspace_id=w1.id, name="Draft", comment="Stage"))
        return _add(db, PurchaseOrder(workspace_id=w1.id, po_number="PO-1", destination_type="storage", destination_id=1,
                                      current_status_id=status.id, created_by=u1.id, order_workflow_id=workflow.id))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one()


# Convention "nothing written": the number of `order_workflows` rows stored (all workspaces)
def stored_count(db):
    return db.scalar(select(func.count()).select_from(OrderWorkflow.__table__))


# The `count:` lines: SELECT count(*) through db.scalar(text(...)), with the filter stated
def count_rows(db, table, **filters):
    where = " AND ".join(f"{column} = :{column}" for column in filters) or "TRUE"
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {where}"), filters)


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
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

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


# --------------------------------------------------------------------------- #
# DAOOrderWorkflow.get_by_type
# --------------------------------------------------------------------------- #


# [claude] OWF-GT-01
def test_owf_gt_01__returns_the_row_of_that_type_with_the_sequence_as_a_list_of_ints(db, w1, mk_workflow):
    """OWF-GT-01 — returns the row of that type, with the sequence as a list of ints.
    Rules: `get_by_type` R1, Returns"""
    mk_workflow(type="STM")
    a = mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, OrderWorkflow)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.type == "PFM"
    assert result.workspace_id == w1.id
    # Then 4
    assert result.status_sequence == [11, 22, 33]
    # Then 5
    assert isinstance(result.status_sequence, list)
    # Then 6
    assert all(isinstance(x, int) for x in result.status_sequence)


# [claude] OWF-GT-02
def test_owf_gt_02__the_seeded_purchase_workflow_comes_back_with_its_four_stages_in_order(db, w1):
    """OWF-GT-02 — the seeded purchase workflow comes back with its four stages in order.
    Rules: `get_by_type` R1, Overview"""
    seed_po_workflow(db, w1.id)
    db.flush()

    result = dao.get_by_type(db, workflow_type="purchase", workspace_id=w1.id)

    # Then 1
    assert result.type == "purchase"
    assert result.workspace_id == w1.id
    # Then 2
    assert len(result.status_sequence) == 4
    # Then 3
    assert [db.get(Status, i).name for i in result.status_sequence] == ["Draft", "Planning", "Receiving", "Complete"]
    # Then 4
    assert {db.get(Status, i).workspace_id for i in result.status_sequence} == {w1.id}


# [claude] OWF-GT-03
def test_owf_gt_03__two_workspaces_with_one_type_the_first_gets_its_own_past_an_earlier_ro(db, w1, w2, mk_workflow):
    """OWF-GT-03 — two workspaces with one type: the first gets its own, past an earlier row.
    Rules: `get_by_type` R2"""
    mk_workflow(workspace_id=w2.id, status_sequence=[44])
    a = mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status_sequence == [11, 22, 33]


# [claude] OWF-GT-04
def test_owf_gt_04__two_workspaces_with_one_type_the_second_gets_its_own(db, w2, mk_workflow):
    """OWF-GT-04 — two workspaces with one type: the second gets its own.
    Rules: `get_by_type` R2"""
    mk_workflow()
    z = mk_workflow(workspace_id=w2.id, status_sequence=[44])

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w2.id)

    # Then 1
    assert result.id == z.id
    # Then 2
    assert result.status_sequence == [44]


# [claude] OWF-GT-05
def test_owf_gt_05__a_workspace_without_the_type_returns_none(db, w1, mk_workflow):
    """OWF-GT-05 — a workspace without the type returns None.
    Rules: `get_by_type` R2"""
    mk_workflow(type="STM")

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-06
def test_owf_gt_06__the_type_under_another_workspace_returns_none(db, w2, mk_workflow):
    """OWF-GT-06 — the type under another workspace returns None.
    Rules: `get_by_type` R2"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-07
def test_owf_gt_07__workspace_id_0_returns_none(db, mk_workflow):
    """OWF-GT-07 — workspace_id=0 returns None.
    Rules: `get_by_type` R2"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=0)

    # Then 1
    assert result is None


# [claude] OWF-GT-08
def test_owf_gt_08__lower_case_does_not_find_an_upper_case_type(db, w1, mk_workflow):
    """OWF-GT-08 — lower case does not find an upper-case type.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="pfm", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-09
def test_owf_gt_09__a_leading_space_finds_nothing(db, w1, mk_workflow):
    """OWF-GT-09 — a leading space finds nothing.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type=" PFM", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-10
def test_owf_gt_10__a_trailing_space_finds_nothing(db, w1, mk_workflow):
    """OWF-GT-10 — a trailing space finds nothing.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM ", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-11
def test_owf_gt_11__is_no_wildcard(db, w1, mk_workflow):
    """OWF-GT-11 — % is no wildcard.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="P%", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-12
def test_owf_gt_12__an_empty_type_returns_none(db, w1, mk_workflow):
    """OWF-GT-12 — an empty type returns None.
    Rules: `get_by_type` R4"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-13
def test_owf_gt_13__a_none_type_returns_none(db, w1, mk_workflow):
    """OWF-GT-13 — a None type returns None.
    Rules: `get_by_type` R4"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type=None, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-14
def test_owf_gt_14__an_empty_sequence_is_returned_as_stored(db, w1, mk_workflow):
    """OWF-GT-14 — an empty sequence is returned as stored.
    Rules: `get_by_type` R5"""
    a = mk_workflow(status_sequence=[])

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status_sequence == []


# [claude] OWF-GT-15
def test_owf_gt_15__ids_of_statuses_that_do_not_exist_are_returned_as_stored(db, w1, mk_workflow):
    """OWF-GT-15 — ids of statuses that do not exist are returned as stored.
    Rules: `get_by_type` R5"""
    a = mk_workflow(status_sequence=[999999999, 999999998])

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.status_sequence == [999999999, 999999998]
    # Then 3
    assert count_rows(db, "statuses", id=999999999) == 0


# [claude] OWF-GT-16
def test_owf_gt_16__allowed_reverts_are_stored_and_returned(db, w1, mk_workflow):
    """OWF-GT-16 — allowed reverts are stored and returned.
    Rules: `get_by_type` O3"""
    a = mk_workflow(allowed_reverts_json={"Received": ["Purchased"]})

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.allowed_reverts_json == {"Received": ["Purchased"]}


# [claude] OWF-GT-17
def test_owf_gt_17__allowed_reverts_left_out_read_back_as_none(db, w1, mk_workflow):
    """OWF-GT-17 — allowed reverts left out read back as None.
    Rules: `get_by_type` O3"""
    a = mk_workflow()

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.allowed_reverts_json is None


# [claude] OWF-GT-18
def test_owf_gt_18__writes_nothing_a_pending_row_stays_pending_and_is_not_found(db, w1, mk_workflow):
    """OWF-GT-18 — writes nothing: a pending row stays pending and is not found.
    Rules: `get_by_type` R2, Side effects"""
    a = mk_workflow()
    p = OrderWorkflow(workspace_id=w1.id, name="Pending", type="PEND", status_sequence=[1])
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_type(db, workflow_type="PEND", workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert stored_count(db) == before
    # Then 6
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 7
    assert written == []


# [claude] OWF-GT-19
def test_owf_gt_19__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, mk_workflow):
    """OWF-GT-19 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_type` Side effects"""
    a = mk_workflow()
    p = OrderWorkflow(workspace_id=w1.id, name="Pending", type="PEND", status_sequence=[1])
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert stored_count(db) == before
    # Then 5
    assert written == []


# [claude] OWF-GT-20
def test_owf_gt_20__the_start_of_a_type_finds_nothing(db, w1, mk_workflow):
    """OWF-GT-20 — the start of a type finds nothing.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="PF", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-21
def test_owf_gt_21__the_end_of_a_type_finds_nothing(db, w1, mk_workflow):
    """OWF-GT-21 — the end of a type finds nothing.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="FM", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-22
def test_owf_gt_22__is_no_wildcard(db, w1, mk_workflow):
    """OWF-GT-22 — _ is no wildcard.
    Rules: `get_by_type` R3"""
    mk_workflow()

    result = dao.get_by_type(db, workflow_type="P_M", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-23
def test_owf_gt_23__a_stored_type_with_a_space_is_not_found_the_stored_side_is_not_trimmed(db, w1, mk_workflow):
    """OWF-GT-23 — a stored type with a space is not found: the stored side is not trimmed.
    Rules: `get_by_type` R3"""
    mk_workflow(type=" PFM")

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OWF-GT-24
def test_owf_gt_24__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_workflow):
    """OWF-GT-24 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_type` Side effects"""
    a = mk_workflow()
    b = mk_workflow(type="STM")
    b.description = "Edited"

    result = dao.get_by_type(db, workflow_type="PFM", workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# Inherited methods on order_workflows
# --------------------------------------------------------------------------- #


# [claude] OWF-IN-01
def test_owf_in_01__a_second_row_of_one_workspace_and_type_is_refused(db, w1, mk_workflow):
    """OWF-IN-01 — a second row of one workspace and type is refused.
    Rules: `inherited` N1"""
    a = mk_workflow()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "New", "type": "PFM", "status_sequence": [1]})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_order_workflows_workspace_type" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "order_workflows", workspace_id=w1.id, type="PFM") == 1
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] OWF-IN-02
def test_owf_in_02__one_type_in_another_workspace_is_stored(db, w2, mk_workflow):
    """OWF-IN-02 — one type in another workspace is stored.
    Rules: `inherited` N1"""
    a = mk_workflow()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w2.id, "name": "New", "type": "PFM", "status_sequence": [1]})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.type == "PFM"
    assert row.status_sequence == [1]
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] OWF-IN-03
def test_owf_in_03__a_second_type_in_one_workspace_is_stored(db, w1, mk_workflow):
    """OWF-IN-03 — a second type in one workspace is stored.
    Rules: `inherited` N1"""
    a = mk_workflow()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "New", "type": "STM", "status_sequence": [1]})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.type == "STM"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] OWF-IN-04
def test_owf_in_04__status_sequence_none_is_refused(db, w1):
    """OWF-IN-04 — status_sequence=None is refused.
    Rules: `inherited` N2"""

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "New", "type": "PFM", "status_sequence": None})
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "status_sequence" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "order_workflows", workspace_id=w1.id) == 0


# [claude] OWF-IN-05
@pytest.mark.xfail(strict=True, reason="BUG-1222: Deleting an order workflow in use detaches its purchase orders")
def test_owf_in_05__removing_a_workflow_a_purchase_order_uses_is_refused(db, mk_workflow, mk_order):
    """OWF-IN-05 — removing a workflow a purchase order uses is refused.
    Rules: `inherited` N3 [BUG-1222]"""
    f = mk_workflow()
    o = mk_order(f)
    db.expire_all()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.remove(db, id=f.id)
    # Then 2
    assert exc.value.orig.pgcode == "23001"
    # Then 3
    assert count_rows(db, "order_workflows", id=f.id) == 1
    # Then 4
    row = reread(db, o)
    assert row.order_workflow_id == f.id


# [claude] OWF-IN-06
def test_owf_in_06__the_same_delete_in_raw_sql_raises_23001_and_changes_nothing(db, mk_workflow, mk_order):
    """OWF-IN-06 — the same delete in raw SQL raises 23001 and changes nothing.
    Rules: `inherited` N3"""
    f = mk_workflow()
    o = mk_order(f)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM order_workflows WHERE id = :id"), {"id": f.id})
    # Then 2
    assert exc.value.orig.pgcode == "23001"
    # Then 3
    assert count_rows(db, "order_workflows", id=f.id) == 1
    # Then 4
    row = reread(db, o)
    assert row.order_workflow_id == f.id


# [claude] OWF-IN-07
@pytest.mark.xfail(strict=True, reason="BUG-1227: A `status_sequence` changed in place is silently lost")
def test_owf_in_07__a_status_sequence_changed_in_place_is_saved_by_the_next_flush(db, mk_workflow):
    """OWF-IN-07 — a status_sequence changed in place is saved by the next flush.
    Rules: `inherited` N4 [BUG-1227]"""
    a = mk_workflow(status_sequence=[1, 2])
    db.refresh(a)

    a.status_sequence.append(3)
    db.flush()

    # Then 1
    row = reread(db, a)
    assert row.status_sequence == [1, 2, 3]
