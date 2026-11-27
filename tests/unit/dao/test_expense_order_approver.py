"""Unit tests for app/dao/expense_order_approver.py.

Implements tests/unit/dao/expense_order_approver.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.expense_order_approver import expense_order_approver_dao
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.workspace_member import WorkspaceMember
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton expense_order_approver_dao" (a module-level name, not a fixture)
dao = expense_order_approver_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T10, T11, T12"
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)


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


# Convention "U1, U2, U3 = three profiles rows", ids rising in that order. None
# of them has a workspace_members row unless the card says `left`.
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


# Convention "O1": every order column is given at insert; no order is updated
def _order(db, workspace, creator, number, **columns):
    fields = {"workspace_id": workspace.id, "expense_number": number, "expense_category": "other",
              "expense_date": date(2026, 3, 1), "subtotal": 0, "total_amount": 0, "created_by": creator.id,
              "description": "Order One"}
    fields.update(columns)
    return _add(db, ExpenseOrder(**fields))


@pytest.fixture
def orders(db, w1, w2, u1):
    """Convention "O1, O2, O9, OC, OV": flushed one at a time in that order."""
    return SimpleNamespace(
        o1=_order(db, w1, u1, "EXP-T-001"),
        o2=_order(db, w1, u1, "EXP-T-002"),
        o9=_order(db, w2, u1, "EXP-T-009"),
        oc=_order(db, w1, u1, "EXP-T-003", completed_at=T12),
        ov=_order(db, w1, u1, "EXP-T-004", voided=True),
    )


@pytest.fixture
def o1(orders):
    return orders.o1


@pytest.fixture
def o2(orders):
    return orders.o2


@pytest.fixture
def o9(orders):
    return orders.o9


@pytest.fixture
def oc(orders):
    return orders.oc


@pytest.fixture
def ov(orders):
    return orders.ov


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3, o1, o2, o9, oc, ov):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "approver": W1, O1, U1; `assigned_by`, `approved`, `approved_at` are not passed
@pytest.fixture
def mk_approver(db, w1, u1, o1):
    """mk_approver(assigned_at=..., **columns) -> ExpenseOrderApprover. Keywords only."""
    def _mk(*, assigned_at, **columns):
        fields = {"workspace_id": w1.id, "expense_order_id": o1.id, "user_id": u1.id, "assigned_at": assigned_at}
        fields.update(columns)
        return _add(db, ExpenseOrderApprover(**fields))
    return _mk


# Convention "left U": the membership of someone removed from W1
@pytest.fixture
def mk_left(db, w1):
    """mk_left(user) -> WorkspaceMember."""
    def _mk(user):
        return _add(db, WorkspaceMember(workspace_id=w1.id, user_id=user.id, role="member", status="inactive"))
    return _mk


# The "101 profiles" and "101 approvers ..., built with add_all" Given of GO-15
@pytest.fixture
def mk_many(db, w1, o1):
    """mk_many(count) -> `in_order`: the ids of E1 ... Ecount, Ek at T10 + k minutes on its own new profile."""
    def _mk(count):
        people = [make_profile(db) for _ in range(count)]
        rows = [ExpenseOrderApprover(workspace_id=w1.id, expense_order_id=o1.id, user_id=person.id,
                             assigned_at=T10 + timedelta(minutes=k))
                for k, person in enumerate(people, start=1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": the number of expense_order_approvers rows stored (all workspaces)
def stored_count(db):
    return db.execute(select(func.count()).select_from(ExpenseOrderApprover.__table__)).scalar_one()


# The `count:` lines: the stored rows of one order and one user (all workspaces)
def pair_count(db, *, expense_order_id, user_id):
    table = ExpenseOrderApprover.__table__
    query = select(func.count()).select_from(table).where(table.c.expense_order_id == expense_order_id, table.c.user_id == user_id)
    return db.execute(query).scalar_one()


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

    def selects(self):
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT from expense_order_approvers; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.selects() if "expense_order_approvers" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# ExpenseOrderApproverDAO.get_by_order
# --------------------------------------------------------------------------- #


# [claude] EOA-GO-01
def test_eoa_go_01__returns_a_list_of_the_order_s_rows_pending_and_approved_alike(db, w1, u2, o1, mk_approver):
    """EOA-GO-01 — returns a list of the order's rows, pending and approved alike.
    Rules: `get_by_order` R1, Returns"""
    a = mk_approver(assigned_at=T10)
    b = mk_approver(assigned_at=T11, user_id=u2.id, approved=True, approved_at=T12)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], ExpenseOrderApprover)
    # Then 4
    assert result[0].approved is False
    # Then 5
    assert result[1].approved is True


# [claude] EOA-GO-02
def test_eoa_go_02__an_earlier_row_of_another_order_of_the_same_workspace_is_not_returned(db, w1, u2, o1, o2, mk_approver):
    """EOA-GO-02 — an earlier row of another order of the same workspace is not returned.
    Rules: `get_by_order` R1"""
    a = mk_approver(assigned_at=T11)
    mk_approver(assigned_at=T10, expense_order_id=o2.id, user_id=u2.id)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] EOA-GO-03
def test_eoa_go_03__the_right_order_under_another_workspace_returns_an_empty_list(db, w2, o1, mk_approver):
    """EOA-GO-03 — the right order under another workspace returns an empty list.
    Rules: `get_by_order` R2"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] EOA-GO-04
def test_eoa_go_04__a_w1_row_on_an_order_of_w2_is_returned_for_w1_only_the_row_s_workspace(db, w1, o9, mk_approver):
    """EOA-GO-04 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared.
    Rules: `get_by_order` R2"""
    a = mk_approver(assigned_at=T10, expense_order_id=o9.id)

    result = dao.get_by_order(db, expense_order_id=o9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] EOA-GO-05
def test_eoa_go_05__a_w1_row_on_an_order_of_w2_is_not_returned_for_w2(db, w2, o9, mk_approver):
    """EOA-GO-05 — a W1 row on an order of W2 is not returned for W2.
    Rules: `get_by_order` R2"""
    mk_approver(assigned_at=T10, expense_order_id=o9.id)

    result = dao.get_by_order(db, expense_order_id=o9.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] EOA-GO-06
def test_eoa_go_06__an_unknown_order_id_returns_an_empty_list(db, w1, mk_approver):
    """EOA-GO-06 — an unknown order id returns an empty list.
    Rules: `get_by_order` R3"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order(db, expense_order_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] EOA-GO-07
def test_eoa_go_07__expense_order_id_0_returns_an_empty_list(db, w1, mk_approver):
    """EOA-GO-07 — expense_order_id=0 returns an empty list.
    Rules: `get_by_order` R3"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order(db, expense_order_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] EOA-GO-08
def test_eoa_go_08__an_unknown_workspace_returns_an_empty_list(db, o1, mk_approver):
    """EOA-GO-08 — an unknown workspace returns an empty list.
    Rules: `get_by_order` R3"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] EOA-GO-09
def test_eoa_go_09__an_order_with_no_approvers_returns_an_empty_list(db, w1, o2, mk_approver):
    """EOA-GO-09 — an order with no approvers returns an empty list.
    Rules: `get_by_order` R3"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order(db, expense_order_id=o2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] EOA-GO-10
def test_eoa_go_10__rows_are_ordered_by_assigned_at_ascending_whatever_their_ids(db, w1, u2, u3, o1, mk_approver):
    """EOA-GO-10 — rows are ordered by assigned_at ascending, whatever their ids.
    Rules: `get_by_order` R4"""
    a = mk_approver(assigned_at=T12)
    b = mk_approver(assigned_at=T11, user_id=u2.id)
    c = mk_approver(assigned_at=T10, user_id=u3.id)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, b.id, a.id]


# [claude] EOA-GO-11
def test_eoa_go_11__on_a_tie_both_rows_are_returned_after_the_earlier_row(db, w1, u2, u3, o1, mk_approver):
    """EOA-GO-11 — on a tie both rows are returned, after the earlier row.
    Rules: `get_by_order` R5, R4"""
    a = mk_approver(assigned_at=T11)
    b = mk_approver(assigned_at=T11, user_id=u2.id)
    c = mk_approver(assigned_at=T10, user_id=u3.id)
    a.approved = True
    a.approved_at = T12
    db.flush()
    db.expire_all()

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:]} == {a.id, b.id}


# [claude] EOA-GO-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1200: Approvers with one `assigned_at` come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_eoa_go_12__on_a_tie_the_lowest_id_comes_first_when_the_lower_id_was_updated(db, w1, u2, o1, mk_approver):
    """EOA-GO-12 — on a tie the lowest id comes first, when the lower id was updated.
    Rules: `get_by_order` R5 [BUG-1200]"""
    a = mk_approver(assigned_at=T11)
    b = mk_approver(assigned_at=T11, user_id=u2.id)
    a.approved = True
    a.approved_at = T12
    db.flush()
    db.expire_all()

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] EOA-GO-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1200: Approvers with one `assigned_at` come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_eoa_go_13__on_a_tie_the_lowest_id_comes_first_with_no_update(db, w1, u2, o1, mk_approver):
    """EOA-GO-13 — on a tie the lowest id comes first, with no update.
    Rules: `get_by_order` R5 [BUG-1200]"""
    a = mk_approver(assigned_at=T11)
    b = mk_approver(assigned_at=T11, user_id=u2.id)
    db.expire_all()

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] EOA-GO-14
@pytest.mark.xfail(strict=True, reason="BUG-1200: Approvers with one `assigned_at` come back in no fixed order")
def test_eoa_go_14__the_query_orders_by_assigned_at_then_id_ascending(db, w1, o1, mk_approver):
    """EOA-GO-14 — the query orders by assigned_at, then id ascending.
    Rules: `get_by_order` R5 [BUG-1200]"""
    a = mk_approver(assigned_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "assigned_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("assigned_at") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()


# [claude] EOA-GO-15
def test_eoa_go_15__there_is_no_cap_101_approvers_give_101_rows(db, w1, o1, mk_many):
    """EOA-GO-15 — there is no cap: 101 approvers give 101 rows.
    Rules: `get_by_order` R6"""
    in_order = mk_many(101)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] EOA-GO-16
def test_eoa_go_16__the_rows_of_people_who_left_the_workspace_are_returned_pending_and_app(db, w1, u2, u3, o1, mk_approver, mk_left):
    """EOA-GO-16 — the rows of people who left the workspace are returned, pending and approved.
    Rules: `get_by_order` R7"""
    mk_left(u2)
    mk_left(u3)
    a = mk_approver(assigned_at=T10, user_id=u2.id)
    b = mk_approver(assigned_at=T11, user_id=u3.id, approved=True, approved_at=T12)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]
    # Then 2
    assert result[0].approved is False
    # Then 3
    assert result[1].approved is True


# [claude] EOA-GO-17
def test_eoa_go_17__the_rows_of_a_completed_order_are_returned(db, w1, u2, oc, mk_approver):
    """EOA-GO-17 — the rows of a completed order are returned.
    Rules: `get_by_order` R8"""
    a = mk_approver(assigned_at=T10, expense_order_id=oc.id)
    b = mk_approver(assigned_at=T11, expense_order_id=oc.id, user_id=u2.id, approved=True, approved_at=T12)

    result = dao.get_by_order(db, expense_order_id=oc.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] EOA-GO-18
def test_eoa_go_18__the_rows_of_a_voided_order_are_returned(db, w1, u2, ov, mk_approver):
    """EOA-GO-18 — the rows of a voided order are returned.
    Rules: `get_by_order` R8"""
    a = mk_approver(assigned_at=T10, expense_order_id=ov.id)
    b = mk_approver(assigned_at=T11, expense_order_id=ov.id, user_id=u2.id, approved=True, approved_at=T12)

    result = dao.get_by_order(db, expense_order_id=ov.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] EOA-GO-19
def test_eoa_go_19__a_row_comes_back_as_stored(db, w1, u1, u3, o1, mk_approver):
    """EOA-GO-19 — a row comes back as stored.
    Rules: `get_by_order` R9"""
    a = mk_approver(assigned_at=T11, assigned_by=u3.id, approved=True, approved_at=T12)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].workspace_id == w1.id
    assert result[0].expense_order_id == o1.id
    assert result[0].user_id == u1.id
    # Then 3
    assert result[0].assigned_by == u3.id
    assert result[0].assigned_at == T11
    # Then 4
    assert result[0].approved is True
    assert result[0].approved_at == T12


# [claude] EOA-GO-20
def test_eoa_go_20__writes_nothing_an_earlier_pending_row_stays_pending_and_is_not_returne(db, w1, u2, o1, mk_approver):
    """EOA-GO-20 — writes nothing: an earlier pending row stays pending and is not returned.
    Rules: `get_by_order` R9, Side effects, Overview"""
    a = mk_approver(assigned_at=T11)
    p = ExpenseOrderApprover(workspace_id=w1.id, expense_order_id=o1.id, user_id=u2.id, assigned_at=T10)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 6
    assert written == []
    # Then 7
    assert len(selects) == 1
    # Then 8
    assert "FOR UPDATE" not in sql.upper()
    # Then 9
    assert "JOIN" not in sql.upper()
    # Then 10
    assert len(db.new) == 1


# [claude] EOA-GO-21
def test_eoa_go_21__an_approved_row_stamped_earlier_comes_before_a_later_pending_row(db, w1, u2, o1, mk_approver):
    """EOA-GO-21 — an approved row stamped earlier comes before a later pending row.
    Rules: `get_by_order` R4"""
    a = mk_approver(assigned_at=T10, approved=True, approved_at=T12)
    b = mk_approver(assigned_at=T11, user_id=u2.id)

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] EOA-GO-22
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1200: Approvers with one `assigned_at` come back in no fixed order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_eoa_go_22__on_a_tie_the_lowest_id_comes_first_when_user_and_approval_would_sort_t(db, w1, u1, u2, u3, o1, mk_approver):
    """EOA-GO-22 — on a tie the lowest id comes first, when user and approval would sort the other way.
    Rules: `get_by_order` R5 [BUG-1200]"""
    a = mk_approver(assigned_at=T11, user_id=u2.id)
    b = mk_approver(assigned_at=T11, user_id=u1.id, approved=True, approved_at=T12, assigned_by=u3.id)
    db.expire_all()

    result = dao.get_by_order(db, expense_order_id=o1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# --------------------------------------------------------------------------- #
# ExpenseOrderApproverDAO.get_by_order_and_user
# --------------------------------------------------------------------------- #


# [claude] EOA-GU-01
def test_eoa_gu_01__returns_the_row_of_that_user_not_the_order_s_first_row(db, w1, u2, o1, mk_approver):
    """EOA-GU-01 — returns the row of that user, not the order's first row.
    Rules: `get_by_order_and_user` R1, R4, Returns"""
    mk_approver(assigned_at=T10)
    b = mk_approver(assigned_at=T11, user_id=u2.id)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id
    # Then 2
    assert isinstance(result, ExpenseOrderApprover)
    # Then 3
    assert result.approved is False


# [claude] EOA-GU-02
def test_eoa_gu_02__returns_the_row_on_that_order_not_the_user_s_first_row(db, w1, u1, o2, mk_approver):
    """EOA-GU-02 — returns the row on that order, not the user's first row.
    Rules: `get_by_order_and_user` R1, R4"""
    mk_approver(assigned_at=T10)
    b = mk_approver(assigned_at=T11, expense_order_id=o2.id)

    result = dao.get_by_order_and_user(db, expense_order_id=o2.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == b.id


# [claude] EOA-GU-03
def test_eoa_gu_03__a_user_with_a_row_only_on_another_order_returns_none_and_nothing_is_cr(db, w1, u1, u2, o1, o2, mk_approver):
    """EOA-GU-03 — a user with a row only on another order returns None and nothing is created.
    Rules: `get_by_order_and_user` R2"""
    mk_approver(assigned_at=T10, expense_order_id=o2.id)
    mk_approver(assigned_at=T11, user_id=u2.id)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] EOA-GU-04
def test_eoa_gu_04__an_unknown_order_id_returns_none_and_nothing_is_created(db, w1, u1, mk_approver):
    """EOA-GU-04 — an unknown order id returns None and nothing is created.
    Rules: `get_by_order_and_user` R2"""
    mk_approver(assigned_at=T10)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=MISSING, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] EOA-GU-05
def test_eoa_gu_05__expense_order_id_0_returns_none_and_nothing_is_created(db, w1, u1, mk_approver):
    """EOA-GU-05 — expense_order_id=0 returns None and nothing is created.
    Rules: `get_by_order_and_user` R2"""
    mk_approver(assigned_at=T10)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=0, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] EOA-GU-06
def test_eoa_gu_06__an_unknown_user_id_returns_none_and_nothing_is_created(db, w1, o1, mk_approver):
    """EOA-GU-06 — an unknown user id returns None and nothing is created.
    Rules: `get_by_order_and_user` R2"""
    mk_approver(assigned_at=T10)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] EOA-GU-07
def test_eoa_gu_07__user_id_0_returns_none_and_nothing_is_created(db, w1, o1, mk_approver):
    """EOA-GU-07 — user_id=0 returns None and nothing is created.
    Rules: `get_by_order_and_user` R2"""
    mk_approver(assigned_at=T10)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=0, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert stored_count(db) == before


# [claude] EOA-GU-08
def test_eoa_gu_08__the_right_order_and_user_under_another_workspace_return_none(db, w2, u1, o1, mk_approver):
    """EOA-GU-08 — the right order and user under another workspace return None.
    Rules: `get_by_order_and_user` R3"""
    mk_approver(assigned_at=T10)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] EOA-GU-09
def test_eoa_gu_09__a_w1_row_on_an_order_of_w2_is_returned_for_w1_only_the_row_s_workspace(db, w1, u1, o9, mk_approver):
    """EOA-GU-09 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared.
    Rules: `get_by_order_and_user` R3"""
    a = mk_approver(assigned_at=T10, expense_order_id=o9.id)

    result = dao.get_by_order_and_user(db, expense_order_id=o9.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] EOA-GU-10
def test_eoa_gu_10__a_w1_row_on_an_order_of_w2_is_not_returned_for_w2(db, w2, u1, o9, mk_approver):
    """EOA-GU-10 — a W1 row on an order of W2 is not returned for W2.
    Rules: `get_by_order_and_user` R3"""
    mk_approver(assigned_at=T10, expense_order_id=o9.id)

    result = dao.get_by_order_and_user(db, expense_order_id=o9.id, user_id=u1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] EOA-GU-11
def test_eoa_gu_11__a_w1_row_on_an_order_of_w2_still_blocks_a_w2_row_for_that_user(db, w2, u1, o9, mk_approver):
    """EOA-GU-11 — a W1 row on an order of W2 still blocks a W2 row for that user.
    Rules: `get_by_order_and_user` R3"""
    a = mk_approver(assigned_at=T10, expense_order_id=o9.id)
    x = ExpenseOrderApprover(workspace_id=w2.id, expense_order_id=o9.id, user_id=u1.id, assigned_at=T11)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(x)
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_eo_approver_eo_user" in str(exc.value.orig)
    # Then 4
    assert pair_count(db, expense_order_id=o9.id, user_id=u1.id) == 1
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] EOA-GU-12
def test_eoa_gu_12__a_second_row_for_the_same_order_and_user_is_refused(db, w1, u1, o1, mk_approver):
    """EOA-GU-12 — a second row for the same order and user is refused.
    Rules: `get_by_order_and_user` R4, Errors"""
    a = mk_approver(assigned_at=T10)
    x = ExpenseOrderApprover(workspace_id=w1.id, expense_order_id=o1.id, user_id=u1.id, assigned_at=T11)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(x)
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert "uq_eo_approver_eo_user" in str(exc.value.orig)
    # Then 4
    assert pair_count(db, expense_order_id=o1.id, user_id=u1.id) == 1
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] EOA-GU-13
def test_eoa_gu_13__an_approved_row_comes_back_as_stored(db, w1, u1, u3, o1, mk_approver):
    """EOA-GU-13 — an approved row comes back as stored.
    Rules: `get_by_order_and_user` R5, R1"""
    a = mk_approver(assigned_at=T11, assigned_by=u3.id, approved=True, approved_at=T12)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.workspace_id == w1.id
    assert result.expense_order_id == o1.id
    assert result.user_id == u1.id
    # Then 3
    assert result.assigned_by == u3.id
    assert result.assigned_at == T11
    # Then 4
    assert result.approved is True
    assert result.approved_at == T12


# [claude] EOA-GU-14
def test_eoa_gu_14__the_pending_row_of_someone_who_left_the_workspace_is_returned(db, w1, u2, o1, mk_approver, mk_left):
    """EOA-GU-14 — the pending row of someone who left the workspace is returned.
    Rules: `get_by_order_and_user` R5"""
    mk_left(u2)
    a = mk_approver(assigned_at=T10, user_id=u2.id)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.approved is False


# [claude] EOA-GU-15
def test_eoa_gu_15__the_row_on_a_completed_order_is_returned(db, w1, u1, oc, mk_approver):
    """EOA-GU-15 — the row on a completed order is returned.
    Rules: `get_by_order_and_user` R5"""
    a = mk_approver(assigned_at=T10, expense_order_id=oc.id)

    result = dao.get_by_order_and_user(db, expense_order_id=oc.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] EOA-GU-16
def test_eoa_gu_16__the_row_on_a_voided_order_is_returned(db, w1, u1, ov, mk_approver):
    """EOA-GU-16 — the row on a voided order is returned.
    Rules: `get_by_order_and_user` R5"""
    a = mk_approver(assigned_at=T10, expense_order_id=ov.id)

    result = dao.get_by_order_and_user(db, expense_order_id=ov.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] EOA-GU-17
def test_eoa_gu_17__writes_nothing_a_pending_row_stays_pending_and_is_not_returned(db, w1, u2, o1, mk_approver):
    """EOA-GU-17 — writes nothing: a pending row stays pending and is not returned.
    Rules: `get_by_order_and_user` R2, Side effects, Overview"""
    a = mk_approver(assigned_at=T10)
    p = ExpenseOrderApprover(workspace_id=w1.id, expense_order_id=o1.id, user_id=u2.id, assigned_at=T11)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u2.id, workspace_id=w1.id)
    written = recorder.written()
    selects = recorder.selects()
    sql = recorder.sql()

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert stored_count(db) == before
    # Then 5
    db.expire_all()
    assert snap(db, a) == before_a
    # Then 6
    assert written == []
    # Then 7
    assert len(selects) == 1
    # Then 8
    assert "FOR UPDATE" not in sql.upper()
    # Then 9
    assert "JOIN" not in sql.upper()
    # Then 10
    assert len(db.new) == 1


# [claude] EOA-GU-18
def test_eoa_gu_18__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, u1, u2, o1, mk_approver):
    """EOA-GU-18 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `get_by_order_and_user` Side effects"""
    a = mk_approver(assigned_at=T10)
    p = ExpenseOrderApprover(workspace_id=w1.id, expense_order_id=o1.id, user_id=u2.id, assigned_at=T11)
    db.add(p)
    before = stored_count(db)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert stored_count(db) == before


# [claude] EOA-GU-19
def test_eoa_gu_19__the_approved_row_of_someone_who_left_the_workspace_is_returned(db, w1, u2, o1, mk_approver, mk_left):
    """EOA-GU-19 — the approved row of someone who left the workspace is returned.
    Rules: `get_by_order_and_user` R5"""
    mk_left(u2)
    a = mk_approver(assigned_at=T10, user_id=u2.id, approved=True, approved_at=T12)

    result = dao.get_by_order_and_user(db, expense_order_id=o1.id, user_id=u2.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.approved is True
