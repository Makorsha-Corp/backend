"""Unit tests for app/dao/work_order_template.py.

Implements tests/unit/dao/work_order_template.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is mocked
(Conventions, Externals: None); the commit spy wraps `db.commit` without
replacing it.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, naive datetimes, and `Decimal("1")` as written in the cards)
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.work_order_template import (
    work_order_template_approver_dao,
    work_order_template_dao,
    work_order_template_item_dao,
)
from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.item import Item
from app.models.work_order_template import WorkOrderTemplate
from app.models.work_order_template_approver import WorkOrderTemplateApprover
from app.models.work_order_template_item import WorkOrderTemplateItem
from app.models.work_order_type import WorkOrderType
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao", "idao", "adao"
dao = work_order_template_dao
idao = work_order_template_item_dao
adao = work_order_template_approver_dao

# Convention "MISSING", "T0", "T9 … T12", "DT", "DAY"
MISSING = 999999999
T0 = datetime(2026, 1, 1, 9, 0, 0)
T9 = datetime(2026, 3, 4, 9, 0, 0)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)
DT = date(2026, 3, 10)
DAY = timedelta(days=1)

R2333 = "BUG-2333: A work order template's times depend on the database's time zone"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, this order, each flushed)
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def st(db):
    """Standing rows 1-6 of Conventions, as attributes W0 … SD."""
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db)
    s.U2 = make_profile(db)
    s.U3 = make_profile(db)
    s.TY0 = _add(db, WorkOrderType(workspace_id=s.W0.id, name="Oil"))
    s.TA = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Oil"))
    s.TB = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Belt"))
    s.TC = _add(db, WorkOrderType(workspace_id=s.W1.id, name="Filter"))
    s.TY2 = _add(db, WorkOrderType(workspace_id=s.W2.id, name="Oil"))
    s.IT1 = _add(db, Item(workspace_id=s.W1.id, name="Oil filter", name_normalized="oil filter", unit="pcs"))
    s.F1 = _add(db, Factory(workspace_id=s.W1.id, name="Main Plant", abbreviation="MP"))
    s.F2 = _add(db, Factory(workspace_id=s.W1.id, name="North Yard", abbreviation="NY"))
    s.F3 = _add(db, Factory(workspace_id=s.W1.id, name="East Yard", abbreviation="EY"))
    s.S1 = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=s.F1.id, name="Line A", created_by=s.U1.id))
    s.S2 = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=s.F2.id, name="Line B", created_by=s.U1.id))
    s.S3 = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=s.F3.id, name="Line C", created_by=s.U1.id))
    s.SD = _add(db, FactorySection(workspace_id=s.W1.id, factory_id=s.F2.id, name="Old line", created_by=s.U1.id,
                                   is_deleted=True, deleted_at=T0, deleted_by=s.U1.id))
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (inserted directly, flushed one at a time)
# --------------------------------------------------------------------------- #

def _tpl_fields(st, created_at, cols):
    fields = {"workspace_id": st.W1.id, "template_name": "Oil change", "work_order_type_id": st.TA.id,
              "created_at": created_at}
    fields.update(cols)
    return fields


# Convention "template"
def tpl(db, st, created_at, **cols):
    return _add(db, WorkOrderTemplate(**_tpl_fields(st, created_at, cols)))


# Convention "recurring" = template, created_at T10, is_recurring True, next_generation_date DT
def rec(db, st, **cols):
    fields = {"is_recurring": True, "next_generation_date": DT}
    fields.update(cols)
    return tpl(db, st, T10, **fields)


def _line_fields(st, t, cols):
    fields = {"workspace_id": st.W1.id, "work_order_template_id": t.id, "item_id": st.IT1.id,
              "quantity": Decimal("1")}
    fields.update(cols)
    return fields


# Convention "line on T"
def line(db, st, t, **cols):
    return _add(db, WorkOrderTemplateItem(**_line_fields(st, t, cols)))


# Convention "approver of T for U"
def appr(db, st, t, u, **cols):
    fields = {"workspace_id": st.W1.id, "work_order_template_id": t.id, "user_id": u.id}
    fields.update(cols)
    return _add(db, WorkOrderTemplateApprover(**fields))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers
# --------------------------------------------------------------------------- #

def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written"
def counts(db):
    return tuple(
        db.execute(select(func.count()).select_from(m.__table__)).scalar_one()
        for m in (WorkOrderTemplate, WorkOrderTemplateItem, WorkOrderTemplateApprover)
    )


# Convention "approvers(T)"
def approvers(db, t):
    return db.scalar(select(func.count()).select_from(WorkOrderTemplateApprover).where(
        WorkOrderTemplateApprover.work_order_template_id == t.id))


# Convention "re-read X"
def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


# Convention "Dhaka"
def dhaka(db):
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# Convention "Statement recorder"
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


# Convention "order_part": after the first ORDER BY, before any LIMIT
def order_part_of(sql):
    if "ORDER BY" not in sql:
        return ""
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]


# --------------------------------------------------------------------------- #
# WorkOrderTemplateDAO.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] WOTP-GW-01
def test_wotp_gw_01__defaults_return_active_and_inactive_newest_first(db, st):
    """WOTP-GW-01 — with the defaults: the workspace's rows, active and inactive, newest first.
    Rules: `get_by_workspace` R1, R2, Returns"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], WorkOrderTemplate)


# [claude] WOTP-GW-02
def test_wotp_gw_02__newer_rows_of_other_workspaces_not_returned(db, st):
    """WOTP-GW-02 — newer rows of an earlier and a later workspace are not returned.
    Rules: `get_by_workspace` R1"""
    tpl(db, st, T12, workspace_id=st.W0.id, work_order_type_id=st.TY0.id)
    a = tpl(db, st, T10)
    tpl(db, st, T12, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-GW-03
def test_wotp_gw_03__unknown_workspace_returns_empty_list(db, st):
    """WOTP-GW-03 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R1"""
    tpl(db, st, T10)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] WOTP-GW-04
def test_wotp_gw_04__workspace_with_no_templates_returns_empty_list(db, st):
    """WOTP-GW-04 — a workspace with no templates returns an empty list.
    Rules: `get_by_workspace` R1"""
    tpl(db, st, T10)

    result = dao.get_by_workspace(db, workspace_id=st.W2.id)

    # Then 1
    assert result == []


# [claude] WOTP-GW-05
def test_wotp_gw_05__is_active_none_returns_both(db, st):
    """WOTP-GW-05 — is_active=None returns active and inactive rows.
    Rules: `get_by_workspace` R2"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, is_active=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] WOTP-GW-06
def test_wotp_gw_06__is_active_true_returns_active_only(db, st):
    """WOTP-GW-06 — is_active=True returns the active rows only.
    Rules: `get_by_workspace` R2"""
    a = tpl(db, st, T10)
    tpl(db, st, T11, template_name="Belt check", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, is_active=True)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-GW-07
def test_wotp_gw_07__is_active_false_returns_inactive_only(db, st):
    """WOTP-GW-07 — is_active=False returns the inactive rows only.
    Rules: `get_by_workspace` R2"""
    tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", is_active=False)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, is_active=False)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WOTP-GW-08
def test_wotp_gw_08__type_keeps_its_own_rows(db, st):
    """WOTP-GW-08 — a type keeps its own rows, not those of a lower or a higher type id.
    Rules: `get_by_workspace` R3"""
    tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", work_order_type_id=st.TB.id)
    tpl(db, st, T12, template_name="Filter swap", work_order_type_id=st.TC.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, work_order_type_id=st.TB.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WOTP-GW-09
def test_wotp_gw_09__type_of_another_workspace_returns_empty(db, st):
    """WOTP-GW-09 — a type of another workspace returns an empty list.
    Rules: `get_by_workspace` R3"""
    tpl(db, st, T10)
    tpl(db, st, T11, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, work_order_type_id=st.TY2.id)

    # Then 1
    assert result == []


# [claude] WOTP-GW-10
def test_wotp_gw_10__type_none_applies_no_filter(db, st):
    """WOTP-GW-10 — work_order_type_id=None applies no filter.
    Rules: `get_by_workspace` R4"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", work_order_type_id=st.TB.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, work_order_type_id=None)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] WOTP-GW-11
def test_wotp_gw_11__type_zero_applies_no_filter(db, st):
    """WOTP-GW-11 — work_order_type_id=0 applies no filter.
    Rules: `get_by_workspace` R4"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check", work_order_type_id=st.TB.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, work_order_type_id=0)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] WOTP-GW-12
def test_wotp_gw_12__newest_first_whatever_ids_and_names(db, st):
    """WOTP-GW-12 — rows come newest first, whatever their ids and names.
    Rules: `get_by_workspace` R5"""
    a = tpl(db, st, T10, template_name="Mid")
    b = tpl(db, st, T12, template_name="Abe")
    c = tpl(db, st, T11, template_name="Zed")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] WOTP-GW-13
def test_wotp_gw_13__order_applied_before_page(db, st):
    """WOTP-GW-13 — the order is applied before the page is cut.
    Rules: `get_by_workspace` R5"""
    tpl(db, st, T10, template_name="Mid")
    tpl(db, st, T12, template_name="Abe")
    c = tpl(db, st, T11, template_name="Zed")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] WOTP-GW-14
def test_wotp_gw_14__tie_rows_between_newer_and_older(db, st):
    """WOTP-GW-14 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_by_workspace` R5"""
    a = tpl(db, st, T11)
    b = tpl(db, st, T11, template_name="Belt check")
    c = tpl(db, st, T12, template_name="Filter swap")
    d = tpl(db, st, T10, template_name="Misc")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] WOTP-GW-15
def test_wotp_gw_15__tie_highest_id_first_after_lowest_updated(db, st):
    """WOTP-GW-15 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_by_workspace` R5 [BUG-2330]"""
    a = tpl(db, st, T11)
    b = tpl(db, st, T11, template_name="Belt check")
    c = tpl(db, st, T11, template_name="Filter swap")
    a.template_name = "Oil change two"
    db.flush()
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] WOTP-GW-16
def test_wotp_gw_16__tie_id_decides_over_other_columns(db, st):
    """WOTP-GW-16 — on a tie the id decides, when name, flag, type and cost would each sort otherwise.
    Rules: `get_by_workspace` R5 [BUG-2330]"""
    a = tpl(db, st, T11, template_name="Mid", work_order_type_id=st.TB.id, cost=Decimal("5.00"))
    b = tpl(db, st, T11, template_name="Zed", is_active=False, work_order_type_id=st.TC.id, cost=Decimal("9.00"))
    c = tpl(db, st, T11, template_name="Abe", cost=Decimal("1.00"))
    db.expire_all()

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] WOTP-GW-17
def test_wotp_gw_17__tied_rows_paged_neither_repeat_nor_miss(db, st):
    """WOTP-GW-17 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_workspace` R5 [BUG-2330]"""
    a = tpl(db, st, T11)
    b = tpl(db, st, T11, template_name="Belt check")
    c = tpl(db, st, T11, template_name="Filter swap")
    d = tpl(db, st, T11, template_name="Misc")
    e = tpl(db, st, T11, template_name="Grease")
    a.template_name = "Oil change two"
    db.flush()
    db.expire_all()

    pages = [dao.get_by_workspace(db, workspace_id=st.W1.id, skip=k, limit=1) for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] WOTP-GW-18
def test_wotp_gw_18__query_orders_by_created_at_then_id_desc(db, st):
    """WOTP-GW-18 — the query orders by created_at, then id, both descending.
    Rules: `get_by_workspace` R5 [BUG-2330]"""
    a = tpl(db, st, T10)

    with StatementRecorder(db) as rec_:
        result = dao.get_by_workspace(db, workspace_id=st.W1.id)
    sql = rec_.sql()
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


# [claude] WOTP-GW-19
def test_wotp_gw_19__filters_combine_with_and(db, st):
    """WOTP-GW-19 — filters combine with AND.
    Rules: `get_by_workspace` R6"""
    a = tpl(db, st, T10, work_order_type_id=st.TB.id)
    tpl(db, st, T11, template_name="Belt check", work_order_type_id=st.TB.id, is_active=False)
    tpl(db, st, T12, template_name="Filter swap")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, is_active=True, work_order_type_id=st.TB.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-GW-20
def test_wotp_gw_20__is_active_applied_before_page(db, st):
    """WOTP-GW-20 — is_active is applied before the page: a hidden row takes no place in it.
    Rules: `get_by_workspace` R6"""
    tpl(db, st, T12, template_name="Off", is_active=False)
    tpl(db, st, T11)
    b = tpl(db, st, T10, template_name="Belt check")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, is_active=True, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WOTP-GW-21
def test_wotp_gw_21__type_applied_before_page(db, st):
    """WOTP-GW-21 — the type is applied before the page: a hidden row takes no place in it.
    Rules: `get_by_workspace` R6"""
    tpl(db, st, T12, template_name="Off", work_order_type_id=st.TC.id)
    tpl(db, st, T11, work_order_type_id=st.TB.id)
    b = tpl(db, st, T10, template_name="Belt check", work_order_type_id=st.TB.id)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, work_order_type_id=st.TB.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WOTP-GW-22
def test_wotp_gw_22__skip_and_limit_cut_a_window(db, st):
    """WOTP-GW-22 — skip and limit cut a window.
    Rules: `get_by_workspace` R7"""
    tpl(db, st, T12)
    b = tpl(db, st, T11, template_name="Belt check")
    c = tpl(db, st, T10, template_name="Filter swap")
    tpl(db, st, T9, template_name="Misc")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


def _many_templates(db, st):
    """Given of GW-23 / GW-24: E1 … E101 with add_all then one flush; returns `newest` (E101 … E1)."""
    rows = [WorkOrderTemplate(**_tpl_fields(st, T10 + timedelta(minutes=k), {"template_name": f"Oil {k}"}))
            for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    return [r.id for r in reversed(rows)]


# [claude] WOTP-GW-23
def test_wotp_gw_23__defaults_give_newest_100_of_101(db, st):
    """WOTP-GW-23 — with the defaults 101 rows give the newest 100.
    Rules: `get_by_workspace` R7"""
    newest = _many_templates(db, st)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] WOTP-GW-24
def test_wotp_gw_24__limit_1000_gives_all_101(db, st):
    """WOTP-GW-24 — limit=1000 gives all 101.
    Rules: `get_by_workspace` R7"""
    newest = _many_templates(db, st)

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] WOTP-GW-25
def test_wotp_gw_25__limit_zero_returns_empty(db, st):
    """WOTP-GW-25 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R8"""
    tpl(db, st, T11)
    tpl(db, st, T10, template_name="Belt check")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] WOTP-GW-26
def test_wotp_gw_26__limit_one_returns_one_row(db, st):
    """WOTP-GW-26 — limit=1 returns one row.
    Rules: `get_by_workspace` R8"""
    a = tpl(db, st, T11)
    tpl(db, st, T10, template_name="Belt check")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-GW-27
def test_wotp_gw_27__skip_past_end_returns_empty(db, st):
    """WOTP-GW-27 — skip past the end returns an empty list.
    Rules: `get_by_workspace` R8"""
    tpl(db, st, T11)
    tpl(db, st, T10, template_name="Belt check")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, skip=2)

    # Then 1
    assert result == []


# [claude] WOTP-GW-28
def test_wotp_gw_28__skip_at_last_row_returns_it(db, st):
    """WOTP-GW-28 — skip at the last row returns it.
    Rules: `get_by_workspace` R8"""
    tpl(db, st, T11)
    b = tpl(db, st, T10, template_name="Belt check")

    result = dao.get_by_workspace(db, workspace_id=st.W1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] WOTP-GW-29
def test_wotp_gw_29__negative_limit_raises(db, st):
    """WOTP-GW-29 — a negative limit raises.
    Rules: `get_by_workspace` R8, Errors"""
    tpl(db, st, T11)
    before = counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert counts(db) == before


# [claude] WOTP-GW-30
def test_wotp_gw_30__negative_skip_raises(db, st):
    """WOTP-GW-30 — a negative skip raises.
    Rules: `get_by_workspace` R8, Errors"""
    tpl(db, st, T11)
    before = counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert counts(db) == before


# [claude] WOTP-GW-31
def test_wotp_gw_31__pending_row_stays_pending(db, st):
    """WOTP-GW-31 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_by_workspace` Side effects"""
    a = tpl(db, st, T10)
    p = WorkOrderTemplate(workspace_id=st.W1.id, template_name="Pending", work_order_type_id=st.TA.id, created_at=T12)
    db.add(p)
    before = counts(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as rec_:
        result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert rec_.written() == []
    # Then 6
    assert counts(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] WOTP-GW-32
def test_wotp_gw_32__unflushed_edit_left_alone(db, st):
    """WOTP-GW-32 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_workspace` Side effects"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T10, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)
    b.template_name = "Edited"

    result = dao.get_by_workspace(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# WorkOrderTemplateDAO.list_recurring_due
# --------------------------------------------------------------------------- #


# [claude] WOTP-RD-01
def test_wotp_rd_01__due_on_target_date_returned(db, st):
    """WOTP-RD-01 — a recurring template due on the target date is returned.
    Rules: `list_recurring_due` R1, R2, Returns"""
    a = rec(db, st)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id}
    # Then 3
    assert isinstance(result[0], WorkOrderTemplate)


# [claude] WOTP-RD-02
def test_wotp_rd_02__other_workspaces_not_returned(db, st):
    """WOTP-RD-02 — due templates of an earlier and a later workspace are not returned.
    Rules: `list_recurring_due` R1"""
    rec(db, st, workspace_id=st.W0.id, work_order_type_id=st.TY0.id)
    a = rec(db, st)
    rec(db, st, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-03
def test_wotp_rd_03__inactive_not_returned(db, st):
    """WOTP-RD-03 — an inactive recurring template is not returned.
    Rules: `list_recurring_due` R1"""
    a = rec(db, st)
    rec(db, st, template_name="Off", is_active=False)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-04
def test_wotp_rd_04__non_recurring_not_returned(db, st):
    """WOTP-RD-04 — a non-recurring template with a due date is not returned.
    Rules: `list_recurring_due` R1"""
    a = rec(db, st)
    tpl(db, st, T10, template_name="Once", is_recurring=False, next_generation_date=DT)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-05
def test_wotp_rd_05__equal_is_due_day_after_is_not(db, st):
    """WOTP-RD-05 — next date equal to the target is due; one day after is not.
    Rules: `list_recurring_due` R2"""
    a = rec(db, st)
    rec(db, st, template_name="Tomorrow", next_generation_date=DT + DAY)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-06
def test_wotp_rd_06__day_before_is_due(db, st):
    """WOTP-RD-06 — next date one day before the target is due.
    Rules: `list_recurring_due` R2"""
    a = rec(db, st, next_generation_date=DT - DAY)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-07
def test_wotp_rd_07__no_next_date_never_due(db, st):
    """WOTP-RD-07 — no next date: never due, and the call does not fail.
    Rules: `list_recurring_due` R2"""
    a = rec(db, st)
    rec(db, st, template_name="Unset", next_generation_date=None)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-08
def test_wotp_rd_08__year_late_is_returned(db, st):
    """WOTP-RD-08 — an overdue template, a year late, is returned.
    Rules: `list_recurring_due` R2"""
    a = rec(db, st, next_generation_date=date(2025, 3, 10))

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-RD-09
def test_wotp_rd_09__end_date_boundaries(db, st):
    """WOTP-RD-09 — the end date: none, equal or later is running; one day before has ended.
    Rules: `list_recurring_due` R3"""
    a = rec(db, st)
    b = rec(db, st, template_name="Ends today", recurrence_end_date=DT)
    c = rec(db, st, template_name="Ends later", recurrence_end_date=DT + DAY)
    rec(db, st, template_name="Ended", recurrence_end_date=DT - DAY)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id, b.id, c.id}


# [claude] WOTP-RD-10
def test_wotp_rd_10__section_run_keeps_that_section_only(db, st):
    """WOTP-RD-10 — a section run keeps that section's templates, not a lower or higher section's, nor sectionless ones.
    Rules: `list_recurring_due` R4"""
    rec(db, st, default_factory_section_id=st.S1.id)
    b = rec(db, st, template_name="Line B oil", default_factory_section_id=st.S2.id)
    rec(db, st, template_name="Line C oil", default_factory_section_id=st.S3.id)
    rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_section_id=st.S2.id)

    # Then 1
    assert idset(result) == {b.id}


# [claude] WOTP-RD-11
def test_wotp_rd_11__section_zero_is_a_filter(db, st):
    """WOTP-RD-11 — factory_section_id=0 is a filter, and matches nothing.
    Rules: `list_recurring_due` R4, R5b (Inputs: `0` included)"""
    rec(db, st, default_factory_section_id=st.S1.id)
    rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_section_id=0)

    # Then 1
    assert result == []


# [claude] WOTP-RD-12
def test_wotp_rd_12__factory_run_keeps_its_sections_and_sectionless(db, st):
    """WOTP-RD-12 — a factory run keeps its sections' templates and the sectionless ones, not a lower or higher factory's.
    Rules: `list_recurring_due` R5"""
    rec(db, st, default_factory_section_id=st.S1.id)
    b = rec(db, st, template_name="Line B oil", default_factory_section_id=st.S2.id)
    rec(db, st, template_name="Line C oil", default_factory_section_id=st.S3.id)
    n = rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_id=st.F2.id)

    # Then 1
    assert idset(result) == {b.id, n.id}


# [claude] WOTP-RD-13
def test_wotp_rd_13__factory_run_skips_deleted_default_section(db, st):
    """WOTP-RD-13 — a factory run skips a template whose default section is deleted.
    Rules: `list_recurring_due` R5a [BUG-2332]"""
    b = rec(db, st, template_name="Line B oil", default_factory_section_id=st.S2.id)
    rec(db, st, template_name="Old line oil", default_factory_section_id=st.SD.id)
    n = rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_id=st.F2.id)

    # Then 1
    assert idset(result) == {b.id, n.id}


# [claude] WOTP-RD-14
def test_wotp_rd_14__section_run_naming_deleted_section_returns_nothing(db, st):
    """WOTP-RD-14 — a section run naming a deleted section returns nothing.
    Rules: `list_recurring_due` R5a [BUG-2332]"""
    rec(db, st, template_name="Old line oil", default_factory_section_id=st.SD.id)
    rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_section_id=st.SD.id)

    # Then 1
    assert result == []


# [claude] WOTP-RD-15
def test_wotp_rd_15__section_of_another_factory_gives_nothing(db, st):
    """WOTP-RD-15 — both scopes apply: a section of another factory gives nothing.
    Rules: `list_recurring_due` R6"""
    rec(db, st, default_factory_section_id=st.S1.id)
    rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_section_id=st.S1.id,
                                    factory_id=st.F2.id)

    # Then 1
    assert result == []


# [claude] WOTP-RD-16
def test_wotp_rd_16__section_and_its_factory_give_that_section(db, st):
    """WOTP-RD-16 — both scopes apply: section and its own factory give that section's templates.
    Rules: `list_recurring_due` R6"""
    rec(db, st, default_factory_section_id=st.S1.id)
    b = rec(db, st, template_name="Line B oil", default_factory_section_id=st.S2.id)
    rec(db, st, template_name="Anywhere")

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_section_id=st.S2.id,
                                    factory_id=st.F2.id)

    # Then 1
    assert idset(result) == {b.id}


# [claude] WOTP-RD-17
def test_wotp_rd_17__no_cap_101_due_all_back(db, st):
    """WOTP-RD-17 — no cap: 101 due templates among not-due ones all come back.
    Rules: `list_recurring_due` R7"""
    rec_fields = {"is_recurring": True, "next_generation_date": DT}
    later = [WorkOrderTemplate(**_tpl_fields(st, T10, {**rec_fields, "template_name": f"Later {k}",
                                                       "next_generation_date": DT + DAY}))
             for k in range(1, 6)]
    db.add_all(later)
    rows = [WorkOrderTemplate(**_tpl_fields(st, T10, {**rec_fields, "template_name": f"Due {k}"}))
            for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    due = {r.id for r in rows}

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == due


# [claude] WOTP-RD-18
def test_wotp_rd_18__writes_nothing(db, st):
    """WOTP-RD-18 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `list_recurring_due` Side effects"""
    a = rec(db, st)
    b = rec(db, st, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)
    b.template_name = "Edited"
    p = WorkOrderTemplate(workspace_id=st.W1.id, template_name="Pending", work_order_type_id=st.TA.id,
                          created_at=T12, is_recurring=True, next_generation_date=DT)
    db.add(p)

    with StatementRecorder(db) as rec_:
        result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec_.written() == []


# [claude] WOTP-RD-19
def test_wotp_rd_19__factory_zero_gives_sectionless_only(db, st):
    """WOTP-RD-19 — factory_id=0 is a filter: only the sectionless due template comes back.
    Rules: `list_recurring_due` R5b"""
    rec(db, st, default_factory_section_id=st.S1.id)
    n = rec(db, st, template_name="Anywhere")
    rec(db, st, template_name="Belt", default_factory_section_id=st.S2.id)

    result = dao.list_recurring_due(db, workspace_id=st.W1.id, target_date=DT, factory_id=0)

    # Then 1
    assert idset(result) == {n.id}


# --------------------------------------------------------------------------- #
# WorkOrderTemplateDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] WOTP-GI-01
def test_wotp_gi_01__returns_the_row_with_that_id(db, st):
    """WOTP-GI-01 — returns the row with that id.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R1, Returns"""
    tpl(db, st, T10, template_name="Belt check")
    a = tpl(db, st, T11)
    tpl(db, st, T12, template_name="Filter swap")

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, WorkOrderTemplate)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.template_name == "Oil change"
    assert result.workspace_id == st.W1.id
    assert result.created_at == T11


# [claude] WOTP-GI-02
def test_wotp_gi_02__later_workspace_id_returns_none(db, st):
    """WOTP-GI-02 — a later workspace's id returns None.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R2"""
    tpl(db, st, T10)
    z = tpl(db, st, T11, workspace_id=st.W2.id, work_order_type_id=st.TY2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-GI-03
def test_wotp_gi_03__earlier_workspace_id_returns_none(db, st):
    """WOTP-GI-03 — an earlier workspace's id, built first, returns None.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R2"""
    z = tpl(db, st, T10, workspace_id=st.W0.id, work_order_type_id=st.TY0.id)
    tpl(db, st, T11)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-GI-04
def test_wotp_gi_04__id_under_another_workspace_returns_none(db, st):
    """WOTP-GI-04 — the id asked under another workspace returns None.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R2"""
    a = tpl(db, st, T10)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W2.id)

    # Then 1
    assert result is None


# [claude] WOTP-GI-05
def test_wotp_gi_05__unknown_id_returns_none(db, st):
    """WOTP-GI-05 — an unknown id returns None.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R2"""
    tpl(db, st, T10)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-GI-06
def test_wotp_gi_06__inactive_template_returned(db, st):
    """WOTP-GI-06 — an inactive template is returned.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` R3"""
    a = tpl(db, st, T10, is_active=False)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_active is False


# [claude] WOTP-GI-07
def test_wotp_gi_07__miss_leaves_pending_row_pending(db, st):
    """WOTP-GI-07 — writes nothing: a miss leaves a pending row pending.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` Side effects"""
    tpl(db, st, T10)
    p = WorkOrderTemplate(workspace_id=st.W1.id, template_name="Pending", work_order_type_id=st.TA.id, created_at=T12)
    db.add(p)

    with StatementRecorder(db) as rec_:
        result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert rec_.written() == []


# [claude] WOTP-GI-08
def test_wotp_gi_08__hit_leaves_unflushed_edit_alone(db, st):
    """WOTP-GI-08 — writes nothing: a hit leaves the caller's unflushed edit alone.
    Rules: `WorkOrderTemplateDAO.get_by_id_and_workspace` Side effects"""
    a = tpl(db, st, T10)
    b = tpl(db, st, T11, template_name="Belt check")
    b.template_name = "Edited"

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# WorkOrderTemplateItemDAO.get_by_template
# --------------------------------------------------------------------------- #


# [claude] WOTP-IT-01
def test_wotp_it_01__lines_in_order_added(db, st):
    """WOTP-IT-01 — returns the template's lines in the order they were added, whatever their quantities.
    Rules: item `get_by_template` R1, Returns"""
    t = tpl(db, st, T10)
    a = line(db, st, t, quantity=Decimal("3.00"), action_type="REPLACE")
    b = line(db, st, t, quantity=Decimal("1.00"), action_type="BORROW")
    c = line(db, st, t, quantity=Decimal("2.00"), action_type="CONSUME")

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]
    # Then 3
    assert isinstance(result[0], WorkOrderTemplateItem)
    # Then 4
    assert result[0].quantity == Decimal("3.00")


# [claude] WOTP-IT-02
def test_wotp_it_02__lines_of_other_templates_not_returned(db, st):
    """WOTP-IT-02 — lines of a lower and a higher template are not returned.
    Rules: item `get_by_template` R1"""
    s = tpl(db, st, T9, template_name="Belt check")
    t = tpl(db, st, T10)
    r = tpl(db, st, T11, template_name="Filter swap")
    line(db, st, s)
    a = line(db, st, t)
    line(db, st, r)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-IT-03
def test_wotp_it_03__template_with_no_lines_returns_empty(db, st):
    """WOTP-IT-03 — a template with no lines returns an empty list.
    Rules: item `get_by_template` R1"""
    s = tpl(db, st, T9, template_name="Belt check")
    t = tpl(db, st, T10)
    line(db, st, s)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] WOTP-IT-04
def test_wotp_it_04__no_cap_101_lines_in_id_order(db, st):
    """WOTP-IT-04 — no cap: 101 lines give 101 rows, in id order.
    Rules: item `get_by_template` R1"""
    t = tpl(db, st, T10)
    rows = [WorkOrderTemplateItem(**_line_fields(st, t, {"quantity": Decimal(102 - k)})) for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    in_order = sorted(r.id for r in rows)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == in_order


# [claude] WOTP-IT-05
def test_wotp_it_05__id_order_holds_after_lowest_updated(db, st):
    """WOTP-IT-05 — the id order holds after the lowest line was updated.
    Rules: item `get_by_template` R1"""
    t = tpl(db, st, T10)
    a = line(db, st, t)
    b = line(db, st, t)
    c = line(db, st, t)
    a.notes = "Updated"
    db.flush()
    db.expire_all()

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]


# [claude] WOTP-IT-06
def test_wotp_it_06__lines_of_other_workspaces_not_returned(db, st):
    """WOTP-IT-06 — lines of an earlier and a later workspace on the same template are not returned.
    Rules: item `get_by_template` R2, R3"""
    t = tpl(db, st, T10)
    line(db, st, t, workspace_id=st.W0.id)
    a = line(db, st, t)
    line(db, st, t, workspace_id=st.W2.id)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-IT-07
def test_wotp_it_07__another_workspace_returns_empty(db, st):
    """WOTP-IT-07 — a call with another workspace returns an empty list.
    Rules: item `get_by_template` R2"""
    t = tpl(db, st, T10)
    line(db, st, t)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W2.id)

    # Then 1
    assert result == []


# [claude] WOTP-IT-08
def test_wotp_it_08__w2_line_on_w1_template_returned_for_w2(db, st):
    """WOTP-IT-08 — a line of W2 on a template of W1 is returned for W2.
    Rules: item `get_by_template` R3"""
    t = tpl(db, st, T10)
    a = line(db, st, t, workspace_id=st.W2.id)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W2.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] WOTP-IT-09
def test_wotp_it_09__lines_of_inactive_template_returned(db, st):
    """WOTP-IT-09 — the lines of an inactive template are returned.
    Rules: item `get_by_template` R4"""
    t = tpl(db, st, T10, is_active=False)
    a = line(db, st, t)
    b = line(db, st, t)

    result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] WOTP-IT-10
def test_wotp_it_10__writes_nothing(db, st):
    """WOTP-IT-10 — writes nothing: a pending line stays pending, an unflushed edit stays dirty.
    Rules: item `get_by_template` Side effects"""
    t = tpl(db, st, T10)
    s = tpl(db, st, T9, template_name="Belt check")
    a = line(db, st, t)
    b = line(db, st, s)
    b.notes = "Edited"
    p = WorkOrderTemplateItem(workspace_id=st.W1.id, work_order_template_id=t.id, item_id=st.IT1.id,
                              quantity=Decimal("1"))
    db.add(p)

    with StatementRecorder(db) as rec_:
        result = idao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec_.written() == []


# [claude] WOTP-IT-11
def test_wotp_it_11__unknown_template_returns_empty(db, st):
    """WOTP-IT-11 — an unknown template returns an empty list.
    Rules: item `get_by_template` R1"""
    t = tpl(db, st, T10)
    line(db, st, t)

    result = idao.get_by_template(db, work_order_template_id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# WorkOrderTemplateItemDAO.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] WOTP-II-01
def test_wotp_ii_01__returns_the_line_with_that_id(db, st):
    """WOTP-II-01 — returns the line with that id.
    Rules: item `get_by_id_and_workspace` R1"""
    t = tpl(db, st, T10)
    line(db, st, t)
    a = line(db, st, t, quantity=Decimal("2.50"), action_type="INSTALL")
    line(db, st, t)

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, WorkOrderTemplateItem)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.work_order_template_id == t.id
    assert result.quantity == Decimal("2.50")
    assert result.action_type == "INSTALL"


# [claude] WOTP-II-02
def test_wotp_ii_02__later_workspace_line_returns_none(db, st):
    """WOTP-II-02 — a later workspace's line id returns None.
    Rules: item `get_by_id_and_workspace` R1"""
    t = tpl(db, st, T10)
    line(db, st, t)
    z = line(db, st, t, workspace_id=st.W2.id)

    result = idao.get_by_id_and_workspace(db, id=z.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-II-03
def test_wotp_ii_03__earlier_workspace_line_returns_none(db, st):
    """WOTP-II-03 — an earlier workspace's line id, built first, returns None.
    Rules: item `get_by_id_and_workspace` R1"""
    t = tpl(db, st, T10)
    z = line(db, st, t, workspace_id=st.W0.id)
    line(db, st, t)

    result = idao.get_by_id_and_workspace(db, id=z.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-II-04
def test_wotp_ii_04__id_under_another_workspace_returns_none(db, st):
    """WOTP-II-04 — the id asked under another workspace returns None.
    Rules: item `get_by_id_and_workspace` R1"""
    t = tpl(db, st, T10)
    a = line(db, st, t)

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W2.id)

    # Then 1
    assert result is None


# [claude] WOTP-II-05
def test_wotp_ii_05__unknown_id_returns_none(db, st):
    """WOTP-II-05 — an unknown id returns None.
    Rules: item `get_by_id_and_workspace` R1"""
    t = tpl(db, st, T10)
    line(db, st, t)

    result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result is None


# [claude] WOTP-II-06
def test_wotp_ii_06__line_of_inactive_template_returned(db, st):
    """WOTP-II-06 — a line of an inactive template is returned.
    Rules: item `get_by_id_and_workspace` R2"""
    t = tpl(db, st, T10, is_active=False)
    a = line(db, st, t)

    result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert result.id == a.id


# [claude] WOTP-II-07
def test_wotp_ii_07__writes_nothing(db, st):
    """WOTP-II-07 — writes nothing: a pending line stays pending, an unflushed edit stays dirty.
    Rules: item `get_by_id_and_workspace` Side effects"""
    t = tpl(db, st, T10)
    a = line(db, st, t)
    b = line(db, st, t)
    b.notes = "Edited"
    p = WorkOrderTemplateItem(workspace_id=st.W1.id, work_order_template_id=t.id, item_id=st.IT1.id,
                              quantity=Decimal("1"))
    db.add(p)

    with StatementRecorder(db) as rec_:
        result = idao.get_by_id_and_workspace(db, id=a.id, workspace_id=st.W1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec_.written() == []


# --------------------------------------------------------------------------- #
# WorkOrderTemplateApproverDAO.get_by_template
# --------------------------------------------------------------------------- #


# [claude] WOTP-AG-01
def test_wotp_ag_01__returns_the_template_s_approvers(db, st):
    """WOTP-AG-01 — returns the template's approvers.
    Rules: approver `get_by_template` R1, Returns"""
    t = tpl(db, st, T10)
    a = appr(db, st, t, st.U1)
    b = appr(db, st, t, st.U2)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id}
    # Then 3
    assert len(result) == 2
    # Then 4
    assert isinstance(result[0], WorkOrderTemplateApprover)


# [claude] WOTP-AG-02
def test_wotp_ag_02__approvers_of_other_templates_not_returned(db, st):
    """WOTP-AG-02 — approvers of a lower and a higher template are not returned.
    Rules: approver `get_by_template` R1"""
    s = tpl(db, st, T9, template_name="Belt check")
    t = tpl(db, st, T10)
    r = tpl(db, st, T11, template_name="Filter swap")
    appr(db, st, s, st.U1)
    a = appr(db, st, t, st.U1)
    appr(db, st, r, st.U1)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert len(result) == 1


# [claude] WOTP-AG-03
def test_wotp_ag_03__unknown_template_returns_empty(db, st):
    """WOTP-AG-03 — an unknown template returns an empty list.
    Rules: approver `get_by_template` R1"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1)

    result = adao.get_by_template(db, work_order_template_id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] WOTP-AG-04
def test_wotp_ag_04__rows_of_other_workspaces_not_returned(db, st):
    """WOTP-AG-04 — rows of an earlier and a later workspace on the same template are not returned.
    Rules: approver `get_by_template` R1"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1, workspace_id=st.W0.id)
    a = appr(db, st, t, st.U2)
    appr(db, st, t, st.U3, workspace_id=st.W2.id)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert len(result) == 1


# [claude] WOTP-AG-05
def test_wotp_ag_05__w2_row_on_w1_template_returned_for_w2(db, st):
    """WOTP-AG-05 — a W2 row on a template of W1 is returned for W2, and a call for W2 gets nothing else.
    Rules: approver `get_by_template` R1 (row's own workspace, M4)"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1)
    z = appr(db, st, t, st.U2, workspace_id=st.W2.id)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W2.id)

    # Then 1
    assert idset(result) == {z.id}
    # Then 2
    assert len(result) == 1


# [claude] WOTP-AG-06
def test_wotp_ag_06__approvers_of_inactive_template_returned(db, st):
    """WOTP-AG-06 — approvers of an inactive template are returned.
    Rules: approver `get_by_template` R3"""
    t = tpl(db, st, T10, is_active=False)
    a = appr(db, st, t, st.U1)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {a.id}


# [claude] WOTP-AG-07
def test_wotp_ag_07__non_member_approver_returned(db, st):
    """WOTP-AG-07 — an approver who is no member of the workspace is returned.
    Rules: approver `get_by_template` R3"""
    t = tpl(db, st, T10)
    a = appr(db, st, t, st.U3)

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert result[0].user_id == st.U3.id


# [claude] WOTP-AG-08
def test_wotp_ag_08__out_of_order_ids_come_back_by_id(db, st):
    """WOTP-AG-08 — rows inserted out of id order come back by id, after the lowest was updated.
    Rules: approver `get_by_template` R2 [BUG-2331]"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1, id=1900000002)
    a = appr(db, st, t, st.U2, id=1900000001)
    appr(db, st, t, st.U3, id=1900000003)
    a.approver_slot = "first"
    db.flush()
    db.expire_all()

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [1900000001, 1900000002, 1900000003]


# [claude] WOTP-AG-09
def test_wotp_ag_09__order_is_by_id_not_by_user(db, st):
    """WOTP-AG-09 — on rows built in id order, the order is by id, not by user.
    Rules: approver `get_by_template` R2 [BUG-2331]"""
    t = tpl(db, st, T10)
    a = appr(db, st, t, st.U3)
    b = appr(db, st, t, st.U1)
    c = appr(db, st, t, st.U2)
    db.expire_all()

    result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] WOTP-AG-10
def test_wotp_ag_10__query_orders_by_id_ascending(db, st):
    """WOTP-AG-10 — the query orders by id ascending.
    Rules: approver `get_by_template` R2 [BUG-2331]"""
    t = tpl(db, st, T10)
    a = appr(db, st, t, st.U1)

    with StatementRecorder(db) as rec_:
        result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)
    sql = rec_.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()
    # Then 5
    assert order_part.count(",") == 0


# [claude] WOTP-AG-11
def test_wotp_ag_11__writes_nothing(db, st):
    """WOTP-AG-11 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: approver `get_by_template` Side effects"""
    t = tpl(db, st, T10)
    s = tpl(db, st, T9, template_name="Belt check")
    a = appr(db, st, t, st.U1)
    b = appr(db, st, s, st.U1)
    b.approver_slot = "edited"
    p = WorkOrderTemplateApprover(workspace_id=st.W1.id, work_order_template_id=t.id, user_id=st.U2.id)
    db.add(p)

    with StatementRecorder(db) as rec_:
        result = adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert rec_.written() == []


# --------------------------------------------------------------------------- #
# WorkOrderTemplateApproverDAO.delete_all_for_template
# --------------------------------------------------------------------------- #


# [claude] WOTP-DA-01
def test_wotp_da_01__all_approvers_deleted_at_once_no_flush(db, st):
    """WOTP-DA-01 — every approver of the template is deleted at once, with no flush.
    Rules: `delete_all_for_template` R1, Returns"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1)
    appr(db, st, t, st.U2)

    result = adao.delete_all_for_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, t) == 0
    # Then 3
    assert adao.get_by_template(db, work_order_template_id=t.id, workspace_id=st.W1.id) == []


# [claude] WOTP-DA-02
def test_wotp_da_02__other_templates_untouched(db, st):
    """WOTP-DA-02 — approvers of a lower and a higher template are untouched.
    Rules: `delete_all_for_template` R2"""
    s = tpl(db, st, T9, template_name="Belt check")
    t = tpl(db, st, T10)
    r = tpl(db, st, T11, template_name="Filter swap")
    x = appr(db, st, s, st.U1)
    appr(db, st, t, st.U1)
    y = appr(db, st, r, st.U1)
    before_x = snap(db, x)
    before_y = snap(db, y)

    result = adao.delete_all_for_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, t) == 0
    # Then 3
    assert approvers(db, s) == 1
    # Then 4
    assert approvers(db, r) == 1
    # Then 5
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 6
    assert snap(db, y) == before_y


# [claude] WOTP-DA-03
def test_wotp_da_03__other_workspaces_rows_untouched(db, st):
    """WOTP-DA-03 — rows of that template with an earlier or a later workspace are untouched.
    Rules: `delete_all_for_template` R2"""
    t = tpl(db, st, T10)
    x = appr(db, st, t, st.U1, workspace_id=st.W0.id)
    a = appr(db, st, t, st.U2)
    y = appr(db, st, t, st.U3, workspace_id=st.W2.id)
    a_id = a.id
    before_x = snap(db, x)
    before_y = snap(db, y)

    result = adao.delete_all_for_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert approvers(db, t) == 2
    # Then 3
    assert db.scalar(select(func.count()).select_from(WorkOrderTemplateApprover).where(
        WorkOrderTemplateApprover.id == a_id)) == 0
    # Then 4
    db.expire_all()
    assert snap(db, x) == before_x
    # Then 5
    assert snap(db, y) == before_y


# [claude] WOTP-DA-04
def test_wotp_da_04__no_matching_rows_nothing_happens(db, st):
    """WOTP-DA-04 — no matching rows: nothing happens, no error.
    Rules: `delete_all_for_template` R3"""
    s = tpl(db, st, T9, template_name="Belt check")
    t = tpl(db, st, T10)
    x = appr(db, st, s, st.U1)
    before = counts(db)
    before_x = snap(db, x)

    result = adao.delete_all_for_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)

    # Then 1
    assert result is None
    # Then 2
    assert counts(db) == before
    # Then 3
    db.expire_all()
    assert snap(db, x) == before_x


# [claude] WOTP-DA-05
def test_wotp_da_05__does_not_commit(db, st):
    """WOTP-DA-05 — does not commit: a rolled-back savepoint brings the rows back.
    Rules: `delete_all_for_template` Side effects (nothing committed)"""
    t = tpl(db, st, T10)
    appr(db, st, t, st.U1)
    appr(db, st, t, st.U2)

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = adao.delete_all_for_template(db, work_order_template_id=t.id, workspace_id=st.W1.id)
    sp.rollback()

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    db.expire_all()
    assert approvers(db, t) == 2


# --------------------------------------------------------------------------- #
# Model facts M1
# --------------------------------------------------------------------------- #


# [claude] WOTP-M-01
def test_wotp_m_01__new_template_gets_creation_time_no_update_time(db, st):
    """WOTP-M-01 — a new template gets a creation time, and no update time.
    Rules: M1"""
    a = WorkOrderTemplate(workspace_id=st.W1.id, template_name="Oil change", work_order_type_id=st.TA.id)

    db.add(a)
    db.flush()
    db.refresh(a)

    row = reread(db, WorkOrderTemplate, a.id)
    # Then 1
    assert row.created_at is not None
    # Then 2
    assert row.updated_at is None


# [claude] WOTP-M-02
@pytest.mark.xfail(strict=True, reason=R2333)
def test_wotp_m_02__creation_time_is_naive_utc(db, st):
    """WOTP-M-02 — a new template's creation time is naive UTC, whatever the database's time zone.
    Rules: M1 [BUG-2333]"""
    dhaka(db)
    a = WorkOrderTemplate(workspace_id=st.W1.id, template_name="Oil change", work_order_type_id=st.TA.id)
    before = utcnow()

    db.add(a)
    db.flush()
    db.refresh(a)
    after = utcnow()

    row = reread(db, WorkOrderTemplate, a.id)
    # Then 1
    assert row.created_at.tzinfo is None
    # Then 2
    assert before <= row.created_at <= after


# [claude] WOTP-M-03
@pytest.mark.xfail(strict=True, reason=R2333)
def test_wotp_m_03__update_time_is_naive_utc(db, st):
    """WOTP-M-03 — an updated template's update time is naive UTC, whatever the database's time zone.
    Rules: M1 [BUG-2333]"""
    dhaka(db)
    a = tpl(db, st, T10)
    before = utcnow()

    a.template_name = "Oil change two"
    db.flush()
    db.refresh(a)
    after = utcnow()

    row = reread(db, WorkOrderTemplate, a.id)
    # Then 1
    assert row.updated_at is not None
    # Then 2
    assert before <= row.updated_at <= after
