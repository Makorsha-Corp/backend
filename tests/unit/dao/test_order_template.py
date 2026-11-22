"""Unit tests for app/dao/order_template.py.

Implements tests/unit/dao/order_template.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, naive datetimes, and `Decimal("1")`)
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.order_template import order_template_dao, order_template_item_dao
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao, idao = the singletons" (module-level names, not fixtures)
dao = order_template_dao
idao = order_template_item_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T9, T10, T11, T12"
T9 = datetime(2026, 3, 4, 9, 0, 0)
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


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "template": is_active is left to its default; expense_category is not passed unless listed
def _template_fields(workspace, columns):
    fields = {"workspace_id": workspace.id, "template_name": "Rent", "requires_approval": True, "auto_approve": False}
    fields.update(columns)
    return fields


@pytest.fixture
def mk_template(db, w1):
    """mk_template(created_at=..., **columns) -> OrderTemplate. Keywords only."""
    def _mk(*, created_at, **columns):
        return _add(db, OrderTemplate(**_template_fields(w1, {"created_at": created_at, **columns})))
    return _mk


# Convention "line on T"
@pytest.fixture
def mk_line(db, w1):
    """mk_line(template, line_number=..., **columns) -> OrderTemplateItem."""
    def _mk(template, *, line_number, **columns):
        fields = {"workspace_id": w1.id, "order_template_id": template.id, "description": "Line",
                  "quantity": Decimal("1"), "line_number": line_number}
        fields.update(columns)
        return _add(db, OrderTemplateItem(**fields))
    return _mk


# The "101 templates ..., built with add_all" Given of GW-25, GW-26
@pytest.fixture
def mk_many_templates(db, w1):
    """mk_many_templates(count) -> `newest`: the ids of Ecount, ... E1, Ek at T10 + k minutes, named "Rent k"."""
    def _mk(count):
        rows = [OrderTemplate(**_template_fields(w1, {"created_at": T10 + timedelta(minutes=k), "template_name": f"Rent {k}"}))
                for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return [row.id for row in reversed(rows)]
    return _mk


# The "101 lines ..., built with add_all" Given of GT-05
@pytest.fixture
def mk_many_lines(db, w1):
    """mk_many_lines(template, count) -> `in_order`: the ids of E1, ... Ecount, Ek with line_number k."""
    def _mk(template, count):
        rows = [OrderTemplateItem(workspace_id=w1.id, order_template_id=template.id, description="Line",
                                  quantity=Decimal("1"), line_number=k)
                for k in range(1, count + 1)]
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


# Convention "nothing written": the numbers of `order_templates` and `order_template_items` rows stored (all workspaces)
def stored_count(db):
    return (db.scalar(select(func.count()).select_from(OrderTemplate.__table__)),
            db.scalar(select(func.count()).select_from(OrderTemplateItem.__table__)))


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

    def sql(self):
        """The one SELECT sent; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# OrderTemplateDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] OTP-GW-01
def test_otp_gw_01__with_the_defaults_a_list_of_the_workspace_s_rows_active_and_inactive_n(db, w1, mk_template):
    """OTP-GW-01 — with the defaults: a list of the workspace's rows, active and inactive, newest first.
    Rules: `OrderTemplateDAO.get_by_workspace` R1, R2, Returns"""
    a = mk_template(created_at=T10)
    b = mk_template(created_at=T11, template_name="Lease", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], OrderTemplate)


# [claude] OTP-GW-02
def test_otp_gw_02__a_newer_row_of_another_workspace_is_not_returned(db, w1, w2, mk_template):
    """OTP-GW-02 — a newer row of another workspace is not returned.
    Rules: `OrderTemplateDAO.get_by_workspace` R1"""
    a = mk_template(created_at=T10)
    mk_template(created_at=T12, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GW-03
def test_otp_gw_03__an_unknown_workspace_returns_an_empty_list(db, mk_template):
    """OTP-GW-03 — an unknown workspace returns an empty list.
    Rules: `OrderTemplateDAO.get_by_workspace` R1"""
    mk_template(created_at=T10)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] OTP-GW-04
def test_otp_gw_04__a_workspace_with_no_templates_returns_an_empty_list(db, w2, mk_template):
    """OTP-GW-04 — a workspace with no templates returns an empty list.
    Rules: `OrderTemplateDAO.get_by_workspace` R1"""
    mk_template(created_at=T10)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] OTP-GW-05
def test_otp_gw_05__is_active_none_returns_active_and_inactive_rows(db, w1, mk_template):
    """OTP-GW-05 — is_active=None returns active and inactive rows.
    Rules: `OrderTemplateDAO.get_by_workspace` R2"""
    a = mk_template(created_at=T10)
    b = mk_template(created_at=T11, template_name="Lease", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_active=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] OTP-GW-06
def test_otp_gw_06__is_active_true_returns_the_active_rows_only(db, w1, mk_template):
    """OTP-GW-06 — is_active=True returns the active rows only.
    Rules: `OrderTemplateDAO.get_by_workspace` R2"""
    a = mk_template(created_at=T10)
    mk_template(created_at=T11, template_name="Lease", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_active=True)

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GW-07
def test_otp_gw_07__is_active_false_returns_the_inactive_rows_only(db, w1, mk_template):
    """OTP-GW-07 — is_active=False returns the inactive rows only.
    Rules: `OrderTemplateDAO.get_by_workspace` R2"""
    mk_template(created_at=T10)
    b = mk_template(created_at=T11, template_name="Lease", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_active=False)

    # Then 1
    assert ids(result) == [b.id]


# [claude] OTP-GW-08
def test_otp_gw_08__a_category_keeps_the_rows_equal_to_it_exactly_case_sensitive(db, w1, mk_template):
    """OTP-GW-08 — a category keeps the rows equal to it exactly, case-sensitive.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    a = mk_template(created_at=T10, expense_category="factory")
    mk_template(created_at=T11, template_name="Lease", expense_category="Factory")
    mk_template(created_at=T12, template_name="Power", expense_category="department")
    mk_template(created_at=T9, template_name="Misc")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="factory")

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GW-09
def test_otp_gw_09__a_category_is_not_trimmed(db, w1, mk_template):
    """OTP-GW-09 — a category is not trimmed.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")
    mk_template(created_at=T11, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="factory ")

    # Then 1
    assert result == []


# [claude] OTP-GW-10
def test_otp_gw_10__a_blank_category_is_a_filter_and_finds_nothing(db, w1, mk_template):
    """OTP-GW-10 — a blank category is a filter and finds nothing.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")
    mk_template(created_at=T11, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category=" ")

    # Then 1
    assert result == []


# [claude] OTP-GW-11
def test_otp_gw_11__is_no_wildcard_in_a_category(db, w1, mk_template):
    """OTP-GW-11 — % is no wildcard in a category.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")
    mk_template(created_at=T11, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="%")

    # Then 1
    assert result == []


# [claude] OTP-GW-12
def test_otp_gw_12__expense_category_none_applies_no_filter(db, w1, mk_template):
    """OTP-GW-12 — expense_category=None applies no filter.
    Rules: `OrderTemplateDAO.get_by_workspace` R4"""
    a = mk_template(created_at=T10, expense_category="factory")
    b = mk_template(created_at=T11, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] OTP-GW-13
def test_otp_gw_13__expense_category_applies_no_filter(db, w1, mk_template):
    """OTP-GW-13 — expense_category="" applies no filter.
    Rules: `OrderTemplateDAO.get_by_workspace` R4"""
    a = mk_template(created_at=T10, expense_category="factory")
    b = mk_template(created_at=T11, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="")

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] OTP-GW-14
def test_otp_gw_14__rows_come_newest_first_whatever_their_ids_and_names(db, w1, mk_template):
    """OTP-GW-14 — rows come newest first, whatever their ids and names.
    Rules: `OrderTemplateDAO.get_by_workspace` R5"""
    a = mk_template(created_at=T10, template_name="Mid")
    b = mk_template(created_at=T12, template_name="Abe")
    c = mk_template(created_at=T11, template_name="Zed")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] OTP-GW-15
def test_otp_gw_15__the_order_is_applied_before_the_page_is_cut(db, w1, mk_template):
    """OTP-GW-15 — the order is applied before the page is cut.
    Rules: `OrderTemplateDAO.get_by_workspace` R5"""
    mk_template(created_at=T10, template_name="Mid")
    mk_template(created_at=T12, template_name="Abe")
    c = mk_template(created_at=T11, template_name="Zed")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] OTP-GW-16
def test_otp_gw_16__on_a_tie_both_rows_are_returned_between_the_newer_and_the_older(db, w1, mk_template):
    """OTP-GW-16 — on a tie both rows are returned, between the newer and the older.
    Rules: `OrderTemplateDAO.get_by_workspace` R5"""
    a = mk_template(created_at=T11)
    b = mk_template(created_at=T11, template_name="Lease")
    c = mk_template(created_at=T12, template_name="Power")
    d = mk_template(created_at=T10, template_name="Misc")

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] OTP-GW-17
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1210: Template list repeats and misses rows when timestamps tie "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_otp_gw_17__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, w1, mk_template):
    """OTP-GW-17 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]"""
    a = mk_template(created_at=T11)
    b = mk_template(created_at=T11, template_name="Lease")
    c = mk_template(created_at=T11, template_name="Power")
    a.template_name = "Rent two"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] OTP-GW-18
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1210: Template list repeats and misses rows when timestamps tie "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_otp_gw_18__on_a_tie_the_id_decides_when_name_flag_and_category_would_each_sort_ot(db, w1, mk_template):
    """OTP-GW-18 — on a tie the id decides, when name, flag and category would each sort otherwise.
    Rules: `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]"""
    a = mk_template(created_at=T11, template_name="Mid", expense_category="factory")
    b = mk_template(created_at=T11, template_name="Zed", expense_category="other", is_active=False)
    c = mk_template(created_at=T11, template_name="Abe", expense_category="department")
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] OTP-GW-19
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1210: Template list repeats and misses rows when timestamps tie "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_otp_gw_19__tied_rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_template):
    """OTP-GW-19 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]"""
    a = mk_template(created_at=T11, template_name="Rent")
    b = mk_template(created_at=T11, template_name="Lease")
    c = mk_template(created_at=T11, template_name="Power")
    d = mk_template(created_at=T11, template_name="Misc")
    e = mk_template(created_at=T11, template_name="Water")
    a.template_name = "Rent two"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=w1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] OTP-GW-20
@pytest.mark.xfail(strict=True, reason="BUG-1210: Template list repeats and misses rows when timestamps tie")
def test_otp_gw_20__the_query_orders_by_created_at_then_id_both_descending(db, w1, mk_template):
    """OTP-GW-20 — the query orders by created_at, then id, both descending.
    Rules: `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]"""
    a = mk_template(created_at=T10)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "created_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("created_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] OTP-GW-21
def test_otp_gw_21__filters_combine_with_and(db, w1, mk_template):
    """OTP-GW-21 — filters combine with AND.
    Rules: `OrderTemplateDAO.get_by_workspace` R6"""
    a = mk_template(created_at=T10, expense_category="factory")
    mk_template(created_at=T11, template_name="Lease", expense_category="factory", is_active=False)
    mk_template(created_at=T12, template_name="Power", expense_category="department")

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_active=True, expense_category="factory")

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GW-22
def test_otp_gw_22__is_active_is_applied_before_the_page_a_hidden_row_takes_no_place_in_it(db, w1, mk_template):
    """OTP-GW-22 — is_active is applied before the page: a hidden row takes no place in it.
    Rules: `OrderTemplateDAO.get_by_workspace` R6"""
    mk_template(created_at=T12, template_name="Off", is_active=False)
    mk_template(created_at=T11)
    b = mk_template(created_at=T10, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, is_active=True, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] OTP-GW-23
def test_otp_gw_23__the_category_is_applied_before_the_page_a_hidden_row_takes_no_place_in(db, w1, mk_template):
    """OTP-GW-23 — the category is applied before the page: a hidden row takes no place in it.
    Rules: `OrderTemplateDAO.get_by_workspace` R6"""
    mk_template(created_at=T12, template_name="Off", expense_category="department")
    mk_template(created_at=T11, expense_category="factory")
    b = mk_template(created_at=T10, template_name="Lease", expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="factory", skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] OTP-GW-24
def test_otp_gw_24__skip_and_limit_cut_a_window(db, w1, mk_template):
    """OTP-GW-24 — skip and limit cut a window.
    Rules: `OrderTemplateDAO.get_by_workspace` R7"""
    mk_template(created_at=T12)
    b = mk_template(created_at=T11, template_name="Lease")
    c = mk_template(created_at=T10, template_name="Power")
    mk_template(created_at=T9, template_name="Misc")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] OTP-GW-25
def test_otp_gw_25__with_the_defaults_101_rows_give_the_newest_100(db, w1, mk_many_templates):
    """OTP-GW-25 — with the defaults 101 rows give the newest 100.
    Rules: `OrderTemplateDAO.get_by_workspace` R7"""
    newest = mk_many_templates(101)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] OTP-GW-26
def test_otp_gw_26__limit_1000_gives_all_101(db, w1, mk_many_templates):
    """OTP-GW-26 — limit=1000 gives all 101.
    Rules: `OrderTemplateDAO.get_by_workspace` R7"""
    newest = mk_many_templates(101)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] OTP-GW-27
def test_otp_gw_27__limit_0_returns_an_empty_list(db, w1, mk_template):
    """OTP-GW-27 — limit=0 returns an empty list.
    Rules: `OrderTemplateDAO.get_by_workspace` R8"""
    mk_template(created_at=T11)
    mk_template(created_at=T10, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] OTP-GW-28
def test_otp_gw_28__limit_1_returns_one_row(db, w1, mk_template):
    """OTP-GW-28 — limit=1 returns one row.
    Rules: `OrderTemplateDAO.get_by_workspace` R8"""
    a = mk_template(created_at=T11)
    mk_template(created_at=T10, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GW-29
def test_otp_gw_29__skip_past_the_end_returns_an_empty_list(db, w1, mk_template):
    """OTP-GW-29 — skip past the end returns an empty list.
    Rules: `OrderTemplateDAO.get_by_workspace` R8"""
    mk_template(created_at=T11)
    mk_template(created_at=T10, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] OTP-GW-30
def test_otp_gw_30__skip_at_the_last_row_returns_it(db, w1, mk_template):
    """OTP-GW-30 — skip at the last row returns it.
    Rules: `OrderTemplateDAO.get_by_workspace` R8"""
    mk_template(created_at=T11)
    b = mk_template(created_at=T10, template_name="Lease")

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] OTP-GW-31
def test_otp_gw_31__a_negative_limit_raises(db, w1, mk_template):
    """OTP-GW-31 — a negative limit raises.
    Rules: `OrderTemplateDAO.get_by_workspace` R8, Errors row 1"""
    mk_template(created_at=T11)
    mk_template(created_at=T10, template_name="Lease")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] OTP-GW-32
def test_otp_gw_32__a_negative_skip_raises(db, w1, mk_template):
    """OTP-GW-32 — a negative skip raises.
    Rules: `OrderTemplateDAO.get_by_workspace` R8, Errors row 2"""
    mk_template(created_at=T11)
    mk_template(created_at=T10, template_name="Lease")
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored_count(db) == before


# [claude] OTP-GW-33
def test_otp_gw_33__writes_nothing_a_newer_pending_row_stays_pending_and_is_not_returned(db, w1, mk_template):
    """OTP-GW-33 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `OrderTemplateDAO.get_by_workspace` Side effects"""
    a = mk_template(created_at=T10)
    p = OrderTemplate(workspace_id=w1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert ids(result) == [a.id]
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


# [claude] OTP-GW-34
def test_otp_gw_34__a_category_in_capitals_does_not_find_a_lower_case_one(db, w1, mk_template):
    """OTP-GW-34 — a category in capitals does not find a lower-case one.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="FACTORY")

    # Then 1
    assert result == []


# [claude] OTP-GW-35
def test_otp_gw_35__a_leading_space_in_the_category_finds_nothing(db, w1, mk_template):
    """OTP-GW-35 — a leading space in the category finds nothing.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category=" factory")

    # Then 1
    assert result == []


# [claude] OTP-GW-36
def test_otp_gw_36__the_start_of_a_category_finds_nothing(db, w1, mk_template):
    """OTP-GW-36 — the start of a category finds nothing.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="fact")

    # Then 1
    assert result == []


# [claude] OTP-GW-37
def test_otp_gw_37__the_end_of_a_category_finds_nothing(db, w1, mk_template):
    """OTP-GW-37 — the end of a category finds nothing.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="tory")

    # Then 1
    assert result == []


# [claude] OTP-GW-38
def test_otp_gw_38__is_no_wildcard_in_a_category(db, w1, mk_template):
    """OTP-GW-38 — _ is no wildcard in a category.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category="factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="f_ctory")

    # Then 1
    assert result == []


# [claude] OTP-GW-39
def test_otp_gw_39__a_stored_category_with_a_space_is_not_found_the_stored_side_is_not_tri(db, w1, mk_template):
    """OTP-GW-39 — a stored category with a space is not found: the stored side is not trimmed.
    Rules: `OrderTemplateDAO.get_by_workspace` R3"""
    mk_template(created_at=T10, expense_category=" factory")

    result = dao.get_by_workspace(db, workspace_id=w1.id, expense_category="factory")

    # Then 1
    assert result == []


# [claude] OTP-GW-40
def test_otp_gw_40__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, w2, mk_template):
    """OTP-GW-40 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `OrderTemplateDAO.get_by_workspace` Side effects"""
    a = mk_template(created_at=T10)
    b = mk_template(created_at=T10, workspace_id=w2.id)
    b.expense_category = "other"

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# OrderTemplateDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] OTP-GI-01
def test_otp_gi_01__returns_the_row_with_that_id(db, w1, mk_template):
    """OTP-GI-01 — returns the row with that id.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R1, Returns"""
    mk_template(created_at=T10, template_name="Lease")
    a = mk_template(created_at=T11)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, OrderTemplate)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.template_name == "Rent"
    assert result.workspace_id == w1.id
    # Then 4
    assert result.created_at == T11


# [claude] OTP-GI-02
def test_otp_gi_02__another_workspace_s_id_returns_none(db, w1, w2, mk_template):
    """OTP-GI-02 — another workspace's id returns None.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R2"""
    mk_template(created_at=T10)
    z = mk_template(created_at=T11, workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-GI-03
def test_otp_gi_03__the_id_under_another_workspace_returns_none(db, w2, mk_template):
    """OTP-GI-03 — the id under another workspace returns None.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R2"""
    a = mk_template(created_at=T10)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] OTP-GI-04
def test_otp_gi_04__an_unknown_id_returns_none(db, w1, mk_template):
    """OTP-GI-04 — an unknown id returns None.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R2"""
    mk_template(created_at=T10)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-GI-05
def test_otp_gi_05__an_inactive_template_is_returned(db, w1, mk_template):
    """OTP-GI-05 — an inactive template is returned.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R3"""
    a = mk_template(created_at=T10, is_active=False)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_active is False


# [claude] OTP-GI-06
def test_otp_gi_06__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, mk_template):
    """OTP-GI-06 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R2, Side effects"""
    a = mk_template(created_at=T10)
    p = OrderTemplate(workspace_id=w1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)
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


# [claude] OTP-GI-07
def test_otp_gi_07__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, mk_template):
    """OTP-GI-07 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` Side effects"""
    a = mk_template(created_at=T10)
    p = OrderTemplate(workspace_id=w1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
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


# [claude] OTP-GI-08
def test_otp_gi_08__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_template):
    """OTP-GI-08 — another workspace's id returns None, when that row is the earlier one.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` R2"""
    z = mk_template(created_at=T10, workspace_id=w2.id)
    mk_template(created_at=T11)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-GI-09
def test_otp_gi_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_template):
    """OTP-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `OrderTemplateDAO.get_by_id_and_workspace` Side effects"""
    a = mk_template(created_at=T10)
    b = mk_template(created_at=T11)
    b.expense_category = "other"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# OrderTemplateItemDAO.get_by_template
# --------------------------------------------------------------------------- #


# [claude] OTP-GT-01
def test_otp_gt_01__returns_a_list_of_the_template_s_lines_with_their_numbers_as_stored(db, w1, mk_template, mk_line):
    """OTP-GT-01 — returns a list of the template's lines, with their numbers as stored.
    Rules: `OrderTemplateItemDAO.get_by_template` R1, Returns"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1, quantity=Decimal("2.00"), unit_price=Decimal("10.00"), line_subtotal=Decimal("20.00"))

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]
    # Then 3
    assert isinstance(result[0], OrderTemplateItem)
    # Then 4
    assert result[0].quantity == Decimal("2.00")
    assert result[0].unit_price == Decimal("10.00")
    assert result[0].line_subtotal == Decimal("20.00")


# [claude] OTP-GT-02
def test_otp_gt_02__an_earlier_line_of_another_template_is_not_returned(db, w1, mk_template, mk_line):
    """OTP-GT-02 — an earlier line of another template is not returned.
    Rules: `OrderTemplateItemDAO.get_by_template` R1"""
    s = mk_template(created_at=T9, template_name="Lease")
    t = mk_template(created_at=T10)
    mk_line(s, line_number=1)
    a = mk_line(t, line_number=2)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GT-03
def test_otp_gt_03__a_template_with_no_lines_returns_an_empty_list(db, w1, mk_template, mk_line):
    """OTP-GT-03 — a template with no lines returns an empty list.
    Rules: `OrderTemplateItemDAO.get_by_template` R1"""
    s = mk_template(created_at=T9, template_name="Lease")
    t = mk_template(created_at=T10)
    mk_line(s, line_number=1)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] OTP-GT-04
def test_otp_gt_04__an_unknown_template_returns_an_empty_list(db, w1, mk_template, mk_line):
    """OTP-GT-04 — an unknown template returns an empty list.
    Rules: `OrderTemplateItemDAO.get_by_template` R1"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1)

    result = idao.get_by_template(db, order_template_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] OTP-GT-05
def test_otp_gt_05__there_is_no_cap_101_lines_give_101_rows(db, w1, mk_template, mk_many_lines):
    """OTP-GT-05 — there is no cap: 101 lines give 101 rows.
    Rules: `OrderTemplateItemDAO.get_by_template` R1"""
    t = mk_template(created_at=T10)
    in_order = mk_many_lines(t, 101)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] OTP-GT-06
def test_otp_gt_06__lines_stored_out_of_order_come_back_1_2_3(db, w1, mk_template, mk_line):
    """OTP-GT-06 — lines stored out of order come back 1, 2, 3.
    Rules: `OrderTemplateItemDAO.get_by_template` R2"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=3, quantity=Decimal("2"))
    b = mk_line(t, line_number=1, quantity=Decimal("3"))
    c = mk_line(t, line_number=2, quantity=Decimal("1"))

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]
    # Then 2
    assert [r.line_number for r in result] == [1, 2, 3]


# [claude] OTP-GT-07
def test_otp_gt_07__on_a_tie_both_lines_are_returned_between_the_lower_and_the_higher_numb(db, w1, mk_template, mk_line):
    """OTP-GT-07 — on a tie both lines are returned, between the lower and the higher number.
    Rules: `OrderTemplateItemDAO.get_by_template` R2"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=2)
    b = mk_line(t, line_number=2)
    c = mk_line(t, line_number=1)
    d = mk_line(t, line_number=3)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] OTP-GT-08
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1211: Template lines of one line number have no order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_otp_gt_08__on_a_tie_the_lowest_id_comes_first_when_the_lowest_id_was_updated(db, w1, mk_template, mk_line):
    """OTP-GT-08 — on a tie the lowest id comes first, when the lowest id was updated.
    Rules: `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)
    b = mk_line(t, line_number=1)
    c = mk_line(t, line_number=1)
    a.quantity = Decimal("5")
    db.flush()
    db.expire_all()

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] OTP-GT-09
@pytest.mark.xfail(
    strict=False,
    reason="BUG-1211: Template lines of one line number have no order "
    "(non-strict: the tied rows come back in physical order, which can match by accident)",
)
def test_otp_gt_09__on_a_tie_the_id_decides_when_quantity_and_price_would_each_sort_otherw(db, w1, mk_template, mk_line):
    """OTP-GT-09 — on a tie the id decides, when quantity and price would each sort otherwise.
    Rules: `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1, quantity=Decimal("2"), unit_price=Decimal("7.00"))
    b = mk_line(t, line_number=1, quantity=Decimal("3"), unit_price=Decimal("9.00"))
    c = mk_line(t, line_number=1, quantity=Decimal("1"), unit_price=Decimal("5.00"))
    db.expire_all()

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] OTP-GT-10
@pytest.mark.xfail(strict=True, reason="BUG-1211: Template lines of one line number have no order")
def test_otp_gt_10__the_query_orders_by_line_number_then_id_ascending(db, w1, mk_template, mk_line):
    """OTP-GT-10 — the query orders by line_number, then id, ascending.
    Rules: `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)

    with StatementRecorder(db) as recorder:
        result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "line_number" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("line_number") < order_part.index(".id")
    # Then 6
    assert "DESC" not in order_part.upper()
    # Then 7
    assert order_part.count(",") == 1


# [claude] OTP-GT-11
def test_otp_gt_11__a_call_with_another_workspace_returns_an_empty_list(db, w2, mk_template, mk_line):
    """OTP-GT-11 — a call with another workspace returns an empty list.
    Rules: `OrderTemplateItemDAO.get_by_template` R3"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] OTP-GT-12
def test_otp_gt_12__a_line_of_workspace_w2_on_a_template_of_w1_is_returned_for_w2(db, w2, mk_template, mk_line):
    """OTP-GT-12 — a line of workspace W2 on a template of W1 is returned for W2.
    Rules: `OrderTemplateItemDAO.get_by_template` R4"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1, workspace_id=w2.id)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] OTP-GT-13
def test_otp_gt_13__a_line_of_workspace_w2_on_a_template_of_w1_is_not_returned_for_w1(db, w1, w2, mk_template, mk_line):
    """OTP-GT-13 — a line of workspace W2 on a template of W1 is not returned for W1.
    Rules: `OrderTemplateItemDAO.get_by_template` R4"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1, workspace_id=w2.id)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] OTP-GT-14
def test_otp_gt_14__the_lines_of_an_inactive_template_are_returned(db, w1, mk_template, mk_line):
    """OTP-GT-14 — the lines of an inactive template are returned.
    Rules: `OrderTemplateItemDAO.get_by_template` R5"""
    t = mk_template(created_at=T10, is_active=False)
    a = mk_line(t, line_number=1)
    b = mk_line(t, line_number=2)

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] OTP-GT-15
def test_otp_gt_15__writes_nothing_an_earlier_pending_line_stays_pending_and_is_not_return(db, w1, mk_template, mk_line):
    """OTP-GT-15 — writes nothing: an earlier pending line stays pending and is not returned.
    Rules: `OrderTemplateItemDAO.get_by_template` Side effects"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=2)
    p = OrderTemplateItem(workspace_id=w1.id, order_template_id=t.id, line_number=1, description="Pending", quantity=Decimal("1"))
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert ids(result) == [a.id]
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


# [claude] OTP-GT-16
def test_otp_gt_16__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_template, mk_line):
    """OTP-GT-16 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `OrderTemplateItemDAO.get_by_template` Side effects"""
    t = mk_template(created_at=T10)
    s = mk_template(created_at=T9, template_name="Lease")
    a = mk_line(t, line_number=1)
    b = mk_line(s, line_number=1)
    b.description = "Edited"

    result = idao.get_by_template(db, order_template_id=t.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# OrderTemplateItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] OTP-II-01
def test_otp_ii_01__returns_the_line_with_that_id_its_numbers_as_stored(db, w1, mk_template, mk_line):
    """OTP-II-01 — returns the line with that id, its numbers as stored.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R1, Returns"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1)
    a = mk_line(t, line_number=2, quantity=Decimal("2.00"), unit_price=Decimal("10.00"), line_subtotal=Decimal("20.00"))

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, OrderTemplateItem)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.order_template_id == t.id
    assert result.workspace_id == w1.id
    assert result.line_number == 2
    # Then 4
    assert result.quantity == Decimal("2.00")
    assert result.unit_price == Decimal("10.00")
    assert result.line_subtotal == Decimal("20.00")


# [claude] OTP-II-02
def test_otp_ii_02__another_workspace_s_id_returns_none(db, w1, w2, mk_template, mk_line):
    """OTP-II-02 — another workspace's id returns None.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R2"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1)
    z = mk_line(t, line_number=2, workspace_id=w2.id)

    result = idao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-II-03
def test_otp_ii_03__the_id_under_another_workspace_returns_none(db, w2, mk_template, mk_line):
    """OTP-II-03 — the id under another workspace returns None.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R2"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] OTP-II-04
def test_otp_ii_04__an_unknown_id_returns_none(db, w1, mk_template, mk_line):
    """OTP-II-04 — an unknown id returns None.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R2"""
    t = mk_template(created_at=T10)
    mk_line(t, line_number=1)

    result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-II-05
def test_otp_ii_05__a_line_of_an_inactive_template_is_returned(db, w1, mk_template, mk_line):
    """OTP-II-05 — a line of an inactive template is returned.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R3"""
    t = mk_template(created_at=T10, is_active=False)
    a = mk_line(t, line_number=1)

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id


# [claude] OTP-II-06
def test_otp_ii_06__writes_nothing_a_read_that_finds_nothing_leaves_the_session_as_it_was(db, w1, mk_template, mk_line):
    """OTP-II-06 — writes nothing: a read that finds nothing leaves the session as it was.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R2, Side effects"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)
    p = OrderTemplateItem(workspace_id=w1.id, order_template_id=t.id, line_number=1, description="Pending", quantity=Decimal("1"))
    db.add(p)
    before = stored_count(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)
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


# [claude] OTP-II-07
def test_otp_ii_07__writes_nothing_a_read_that_finds_its_row_leaves_the_session_as_it_was(db, w1, mk_template, mk_line):
    """OTP-II-07 — writes nothing: a read that finds its row leaves the session as it was.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` Side effects"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)
    p = OrderTemplateItem(workspace_id=w1.id, order_template_id=t.id, line_number=1, description="Pending", quantity=Decimal("1"))
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)
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


# [claude] OTP-II-08
def test_otp_ii_08__another_workspace_s_id_returns_none_when_that_row_is_the_earlier_one(db, w1, w2, mk_template, mk_line):
    """OTP-II-08 — another workspace's id returns None, when that row is the earlier one.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` R2"""
    t = mk_template(created_at=T10)
    z = mk_line(t, line_number=1, workspace_id=w2.id)
    mk_line(t, line_number=2)

    result = idao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] OTP-II-09
def test_otp_ii_09__writes_nothing_a_read_leaves_the_caller_s_unflushed_edit_alone(db, w1, mk_template, mk_line):
    """OTP-II-09 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `OrderTemplateItemDAO.get_by_id_and_workspace` Side effects"""
    t = mk_template(created_at=T10)
    a = mk_line(t, line_number=1)
    b = mk_line(t, line_number=2)
    b.description = "Edited"

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
