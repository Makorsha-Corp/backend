"""Unit tests for app/dao/financial_audit_log.py.

Implements tests/unit/dao/financial_audit_log.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture). Nothing is mocked
(Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError

from app.dao.financial_audit_log import financial_audit_log_dao
from app.models.financial_audit_log import FinancialAuditLog
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

dao = financial_audit_log_dao

# Convention "MISSING", "T9 … T12", "US", "PLUS6"
MISSING = 999999999
T9 = datetime(2026, 3, 4, 9, 0, 0)
T10 = datetime(2026, 3, 4, 10, 0, 0)
T11 = datetime(2026, 3, 4, 11, 0, 0)
T12 = datetime(2026, 3, 4, 12, 0, 0)
US = timedelta(microseconds=1)
PLUS6 = timezone(timedelta(hours=6))

R2370 = "BUG-2370: Financial audit log pages repeat and miss rows when timestamps tie"
R2371 = "BUG-2371: Financial audit date filter with a time zone depends on the database's time-zone setting"
R2372 = "BUG-2372: A financial audit row written without a time gets the database's local time"


# Convention "zone(z)"
def zone(db, z):
    db.execute(text(f"SET LOCAL TIME ZONE '{z}'"))


# --------------------------------------------------------------------------- #
# Conventions -> standing rows
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def st(db):
    """Standing rows: W0, W1, W2 then U1, U2, U3, ids rising in that order."""
    s = SimpleNamespace()
    s.W0 = make_workspace(db)
    s.W1 = make_workspace(db)
    s.W2 = make_workspace(db)
    s.U1 = make_profile(db)
    s.U2 = make_profile(db)
    s.U3 = make_profile(db)
    return s


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (inserted directly, flushed one at a time)
# --------------------------------------------------------------------------- #

def _log_fields(st, performed_at, cols):
    fields = {"workspace_id": st.W1.id, "entity_type": "invoice", "entity_id": 10, "action_type": "created",
              "performed_by": st.U1.id, "performed_at": performed_at}
    fields.update(cols)
    return fields


def _pay_fields(st, performed_at, cols):
    fields = {"entity_type": "payment", "entity_id": 7, "related_entity_type": "invoice", "related_entity_id": 10}
    fields.update(cols)
    return _log_fields(st, performed_at, fields)


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "log"
def log(db, st, performed_at, **cols):
    return _add(db, FinancialAuditLog(**_log_fields(st, performed_at, cols)))


# Convention "payment row"
def pay(db, st, performed_at, **cols):
    return _add(db, FinancialAuditLog(**_pay_fields(st, performed_at, cols)))


# The "101 logs E1 … E101, built with add_all then one flush" Givens; returns `newest` (Ecount … E1)
def many(db, rows):
    db.add_all(rows)
    db.flush()
    return [r.id for r in reversed(rows)]


# Convention "writes-nothing setup": returns (B, P)
def wn_setup(db, st):
    b = log(db, st, T9, workspace_id=st.W2.id)
    b.description = "Edited"
    p = FinancialAuditLog(workspace_id=st.W1.id, entity_type="invoice", entity_id=10, action_type="created",
                          performed_by=st.U1.id, performed_at=T12)
    db.add(p)
    return b, p


# The tie Givens: "`A.description = "Edited"`, then `db.flush()`", then `db.expire_all()`
def edit_lowest(db, a):
    a.description = "Edited"
    db.flush()
    db.expire_all()


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers
# --------------------------------------------------------------------------- #

def ids(result):
    return [r.id for r in result]


# Convention "unchanged(X)"
def snap(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written"
def stored(db):
    return db.execute(select(func.count()).select_from(FinancialAuditLog.__table__)).scalar_one()


# Convention "re-read X"
def reread(db, row_id):
    db.expire_all()
    return db.get(FinancialAuditLog, row_id)


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
# get_by_entity
# --------------------------------------------------------------------------- #


# [claude] FAL-BE-01
def test_fal_be_01__entity_rows_newest_first(db, st):
    """FAL-BE-01 — the entity's rows, newest first.
    Rules: `get_by_entity` R1, Returns"""
    a = log(db, st, T10)
    b = log(db, st, T11, action_type="status_changed")

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert isinstance(result[0], FinancialAuditLog)


# [claude] FAL-BE-02
def test_fal_be_02__lower_and_higher_entity_ids_not_returned(db, st):
    """FAL-BE-02 — rows of a lower and a higher entity id are not returned.
    Rules: `get_by_entity` R1"""
    log(db, st, T12, entity_id=9)
    a = log(db, st, T10)
    log(db, st, T12, entity_id=11)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BE-03
def test_fal_be_03__other_type_same_id_not_returned(db, st):
    """FAL-BE-03 — a row of another type with the same id is not returned.
    Rules: `get_by_entity` R1"""
    a = log(db, st, T10)
    log(db, st, T12, entity_type="payment")

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BE-04
def test_fal_be_04__related_only_row_not_returned(db, st):
    """FAL-BE-04 — a row naming the entity only as its related entity is not returned.
    Rules: `get_by_entity` R1"""
    a = log(db, st, T10)
    pay(db, st, T12)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BE-05
def test_fal_be_05__other_workspaces_not_returned(db, st):
    """FAL-BE-05 — rows of an earlier and a later workspace are not returned.
    Rules: `get_by_entity` R2"""
    log(db, st, T12, workspace_id=st.W0.id)
    a = log(db, st, T10)
    log(db, st, T12, workspace_id=st.W2.id)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BE-06
def test_fal_be_06__unknown_workspace_returns_empty(db, st):
    """FAL-BE-06 — an unknown workspace returns an empty list.
    Rules: `get_by_entity` R2"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] FAL-BE-07
def test_fal_be_07__capitalised_type_finds_nothing(db, st):
    """FAL-BE-07 — "Invoice" in capitals finds nothing.
    Rules: `get_by_entity` R3"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="Invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-08
def test_fal_be_08__empty_type_finds_nothing(db, st):
    """FAL-BE-08 — an empty type finds nothing.
    Rules: `get_by_entity` R3"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-09
def test_fal_be_09__part_of_type_finds_nothing(db, st):
    """FAL-BE-09 — part of the type finds nothing.
    Rules: `get_by_entity` R3"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="voic", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-10
def test_fal_be_10__underscore_is_no_wildcard(db, st):
    """FAL-BE-10 — `_` is no wildcard in the type.
    Rules: `get_by_entity` R3"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="inv_ice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-11
def test_fal_be_11__leading_space_in_type_finds_nothing(db, st):
    """FAL-BE-11 — a leading space in the type finds nothing.
    Rules: `get_by_entity` R3"""
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type=" invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-12
def test_fal_be_12__stored_side_not_trimmed(db, st):
    """FAL-BE-12 — a stored type with a leading space is not found: the stored side is not trimmed.
    Rules: `get_by_entity` R3"""
    log(db, st, T10, entity_type=" invoice")

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BE-13
def test_fal_be_13__newest_first_whatever_ids_and_actions(db, st):
    """FAL-BE-13 — rows come newest first, whatever their ids and actions.
    Rules: `get_by_entity` R4"""
    a = log(db, st, T10, action_type="updated")
    b = log(db, st, T12, action_type="created")
    c = log(db, st, T11, action_type="voided")

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] FAL-BE-14
def test_fal_be_14__order_before_page(db, st):
    """FAL-BE-14 — the order is applied before the page is cut.
    Rules: `get_by_entity` R4"""
    log(db, st, T10)
    log(db, st, T12)
    c = log(db, st, T11)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [c.id]


# [claude] FAL-BE-15
def test_fal_be_15__tie_rows_between_newer_and_older(db, st):
    """FAL-BE-15 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_by_entity` R4"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T12)
    d = log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-BE-16
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_be_16__tie_highest_id_first_after_lowest_updated(db, st):
    """FAL-BE-16 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_by_entity` R4 [BUG-2370]"""
    a = log(db, st, T11, action_type="voided")
    b = log(db, st, T11, action_type="updated")
    c = log(db, st, T11, action_type="created")
    edit_lowest(db, a)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] FAL-BE-17
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_be_17__tied_rows_paged_neither_repeat_nor_miss(db, st):
    """FAL-BE-17 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: `get_by_entity` R4 [BUG-2370]"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T11)
    d = log(db, st, T11)
    e = log(db, st, T11)
    edit_lowest(db, a)

    pages = [dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=k, limit=1)
             for k in range(5)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [e.id, d.id, c.id, b.id, a.id]


# [claude] FAL-BE-18
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_be_18__orders_by_performed_at_then_id_desc(db, st):
    """FAL-BE-18 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_entity` R4 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-BE-19
def test_fal_be_19__skip_and_limit_cut_a_window(db, st):
    """FAL-BE-19 — skip and limit cut a window.
    Rules: `get_by_entity` R5"""
    log(db, st, T12)
    b = log(db, st, T11)
    c = log(db, st, T10)
    log(db, st, T9)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, c.id]


# [claude] FAL-BE-20
def test_fal_be_20__defaults_give_newest_100(db, st):
    """FAL-BE-20 — with the defaults 101 rows give the newest 100.
    Rules: `get_by_entity` R5"""
    newest = many(db, [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {})) for k in range(1, 102)])

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] FAL-BE-21
def test_fal_be_21__limit_1000_gives_all_101(db, st):
    """FAL-BE-21 — limit=1000 gives all 101.
    Rules: `get_by_entity` R5"""
    newest = many(db, [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {})) for k in range(1, 102)])

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] FAL-BE-22
def test_fal_be_22__limit_zero_returns_empty(db, st):
    """FAL-BE-22 — limit=0 returns an empty list.
    Rules: `get_by_entity` R5"""
    log(db, st, T11)
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-BE-23
def test_fal_be_23__limit_one_returns_one_row(db, st):
    """FAL-BE-23 — limit=1 returns one row.
    Rules: `get_by_entity` R5"""
    a = log(db, st, T11)
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BE-24
def test_fal_be_24__skip_past_end_returns_empty(db, st):
    """FAL-BE-24 — skip past the end returns an empty list.
    Rules: `get_by_entity` R5"""
    log(db, st, T11)
    log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=2)

    # Then 1
    assert result == []


# [claude] FAL-BE-25
def test_fal_be_25__skip_at_last_row_returns_it(db, st):
    """FAL-BE-25 — skip at the last row returns it.
    Rules: `get_by_entity` R5"""
    log(db, st, T11)
    b = log(db, st, T10)

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] FAL-BE-26
def test_fal_be_26__negative_limit_raises(db, st):
    """FAL-BE-26 — a negative limit raises.
    Rules: `get_by_entity` R5, Errors row 1"""
    log(db, st, T11)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored(db) == before


# [claude] FAL-BE-27
def test_fal_be_27__negative_skip_raises(db, st):
    """FAL-BE-27 — a negative skip raises.
    Rules: `get_by_entity` R5, Errors row 2"""
    log(db, st, T11)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored(db) == before


# [claude] FAL-BE-28
def test_fal_be_28__pending_row_stays_pending(db, st):
    """FAL-BE-28 — writes nothing: a newer pending row stays pending and is not returned.
    Rules: `get_by_entity` Side effects"""
    a = log(db, st, T10)
    p = FinancialAuditLog(workspace_id=st.W1.id, entity_type="invoice", entity_id=10, action_type="created",
                          performed_by=st.U1.id, performed_at=T12)
    db.add(p)
    before = stored(db)
    before_a = snap(db, a)

    with StatementRecorder(db) as rec:
        result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert rec.written() == []
    # Then 6
    assert stored(db) == before
    # Then 7
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] FAL-BE-29
def test_fal_be_29__unflushed_edit_left_alone(db, st):
    """FAL-BE-29 — writes nothing: a read leaves the caller's unflushed edit alone.
    Rules: `get_by_entity` Side effects"""
    a = log(db, st, T10)
    b = log(db, st, T9, workspace_id=st.W2.id)
    b.description = "Edited"

    result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1


# --------------------------------------------------------------------------- #
# get_related_logs
# --------------------------------------------------------------------------- #


# [claude] FAL-RL-01
def test_fal_rl_01__own_and_payment_rows_newest_first(db, st):
    """FAL-RL-01 — an invoice's own rows and its payments' rows, newest first.
    Rules: `get_related_logs` R1, Returns"""
    a = log(db, st, T10, action_type="status_changed")
    p1 = pay(db, st, T11)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [p1.id, a.id]


# [claude] FAL-RL-02
def test_fal_rl_02__own_and_related_row_returned_once(db, st):
    """FAL-RL-02 — a row that is both the entity's own and related to it is returned once.
    Rules: `get_related_logs` R1"""
    a = log(db, st, T10, related_entity_type="invoice", related_entity_id=10)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-RL-03
def test_fal_rl_03__one_level_only(db, st):
    """FAL-RL-03 — one level only: an account's invoice and that invoice's payment are not returned.
    Rules: `get_related_logs` R2"""
    c = log(db, st, T9, entity_type="account", entity_id=5)
    log(db, st, T10)
    pay(db, st, T11)

    result = dao.get_related_logs(db, entity_type="account", entity_id=5, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [c.id]


# [claude] FAL-RL-04
def test_fal_rl_04__both_halves_need_type_and_id(db, st):
    """FAL-RL-04 — both halves need type and id: other types and lower or higher ids are not returned.
    Rules: `get_related_logs` R3"""
    a = log(db, st, T9)
    log(db, st, T12, entity_type="payment")
    pay(db, st, T12, related_entity_type="account")
    pay(db, st, T12, related_entity_id=9)
    pay(db, st, T12, related_entity_id=11)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-RL-05
def test_fal_rl_05__other_workspaces_not_returned(db, st):
    """FAL-RL-05 — own and related rows of an earlier and a later workspace are not returned.
    Rules: `get_related_logs` R4"""
    log(db, st, T12, workspace_id=st.W0.id)
    pay(db, st, T12, workspace_id=st.W0.id)
    a = log(db, st, T10)
    log(db, st, T12, workspace_id=st.W2.id)
    pay(db, st, T12, workspace_id=st.W2.id)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-RL-06
def test_fal_rl_06__capitalised_type_finds_nothing(db, st):
    """FAL-RL-06 — "Invoice" in capitals finds neither own nor related rows.
    Rules: `get_related_logs` R4 (exact compare)"""
    log(db, st, T10)
    pay(db, st, T11)

    result = dao.get_related_logs(db, entity_type="Invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-RL-07
def test_fal_rl_07__stored_related_type_compared_exactly(db, st):
    """FAL-RL-07 — a stored related type in capitals, or with a leading space, is not matched.
    Rules: `get_related_logs` R4 (exact compare, stored side)"""
    a = log(db, st, T9)
    pay(db, st, T11, related_entity_type="Invoice")
    pay(db, st, T12, related_entity_type=" invoice")

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-RL-08
def test_fal_rl_08__combined_rows_newest_first(db, st):
    """FAL-RL-08 — the combined rows come newest first, whatever their ids.
    Rules: `get_related_logs` R5"""
    a = log(db, st, T10)
    p1 = pay(db, st, T12)
    b = log(db, st, T11, action_type="updated")

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [p1.id, b.id, a.id]


# [claude] FAL-RL-09
def test_fal_rl_09__window_from_combined_ordered_rows(db, st):
    """FAL-RL-09 — skip and limit cut a window from the combined, ordered rows.
    Rules: `get_related_logs` R4, R5"""
    a = log(db, st, T10)
    pay(db, st, T12)
    b = log(db, st, T11, action_type="updated")
    pay(db, st, T9, entity_id=8)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [b.id, a.id]


def _mixed_101(st):
    """Given of RL-10 / RL-11: Ek = log when k is odd, payment row when k is even."""
    return [FinancialAuditLog(**(_log_fields if k % 2 else _pay_fields)(st, T10 + timedelta(minutes=k), {}))
            for k in range(1, 102)]


# [claude] FAL-RL-10
def test_fal_rl_10__defaults_give_newest_100(db, st):
    """FAL-RL-10 — with the defaults 101 rows give the newest 100.
    Rules: `get_related_logs` R4"""
    newest = many(db, _mixed_101(st))

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] FAL-RL-11
def test_fal_rl_11__limit_1000_gives_all_101(db, st):
    """FAL-RL-11 — limit=1000 gives all 101.
    Rules: `get_related_logs` R4"""
    newest = many(db, _mixed_101(st))

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] FAL-RL-12
def test_fal_rl_12__limit_zero_returns_empty(db, st):
    """FAL-RL-12 — limit=0 returns an empty list.
    Rules: `get_related_logs` R4"""
    log(db, st, T10)
    pay(db, st, T11)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-RL-13
def test_fal_rl_13__skip_past_end_returns_empty(db, st):
    """FAL-RL-13 — skip past the end returns an empty list.
    Rules: `get_related_logs` R4"""
    log(db, st, T10)
    pay(db, st, T11)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=2)

    # Then 1
    assert result == []


# [claude] FAL-RL-14
def test_fal_rl_14__negative_limit_raises(db, st):
    """FAL-RL-14 — a negative limit raises.
    Rules: `get_related_logs` Errors (as `get_by_entity` row 1)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored(db) == before


# [claude] FAL-RL-15
def test_fal_rl_15__negative_skip_raises(db, st):
    """FAL-RL-15 — a negative skip raises.
    Rules: `get_related_logs` Errors (as `get_by_entity` row 2)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored(db) == before


# [claude] FAL-RL-16
def test_fal_rl_16__tie_rows_between_newer_and_older(db, st):
    """FAL-RL-16 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_related_logs` R5"""
    a = log(db, st, T11)
    p1 = pay(db, st, T11)
    c = log(db, st, T12, action_type="updated")
    d = log(db, st, T10, action_type="voided")

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, p1.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-RL-17
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_rl_17__tie_highest_id_first_after_lowest_updated(db, st):
    """FAL-RL-17 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_related_logs` R5 [BUG-2370]"""
    a = log(db, st, T11)
    p1 = pay(db, st, T11)
    c = log(db, st, T11, action_type="updated")
    edit_lowest(db, a)

    result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, p1.id, a.id]


# [claude] FAL-RL-18
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_rl_18__orders_by_performed_at_then_id_desc(db, st):
    """FAL-RL-18 — the query orders by performed_at, then id, both descending.
    Rules: `get_related_logs` R5 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-RL-19
def test_fal_rl_19__writes_nothing(db, st):
    """FAL-RL-19 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `get_related_logs` Side effects"""
    a = log(db, st, T10)
    b, p = wn_setup(db, st)

    with StatementRecorder(db) as rec:
        result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=st.W1.id)

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
    assert rec.written() == []


# --------------------------------------------------------------------------- #
# get_by_action_type
# --------------------------------------------------------------------------- #


# [claude] FAL-AT-01
def test_fal_at_01__every_row_of_the_action_newest_first(db, st):
    """FAL-AT-01 — every row of the action, of any entity type, newest first.
    Rules: `get_by_action_type` R1, Returns"""
    a = log(db, st, T10, action_type="status_changed")
    b = pay(db, st, T11, action_type="status_changed")
    c = log(db, st, T12, entity_type="account", entity_id=5, action_type="status_changed")
    log(db, st, T12, action_type="created")

    result = dao.get_by_action_type(db, action_type="status_changed", workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] FAL-AT-02
def test_fal_at_02__action_in_capitals_finds_nothing(db, st):
    """FAL-AT-02 — the action in capitals finds nothing.
    Rules: `get_by_action_type` R1"""
    log(db, st, T10, action_type="status_changed")

    result = dao.get_by_action_type(db, action_type="STATUS_CHANGED", workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-AT-03
def test_fal_at_03__part_of_action_finds_nothing(db, st):
    """FAL-AT-03 — part of the action finds nothing.
    Rules: `get_by_action_type` R1"""
    log(db, st, T10, action_type="status_changed")

    result = dao.get_by_action_type(db, action_type="tus_chan", workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-AT-04
def test_fal_at_04__underscore_is_no_wildcard(db, st):
    """FAL-AT-04 — `_` is no wildcard in the action.
    Rules: `get_by_action_type` R1"""
    log(db, st, T10, action_type="status_changed")

    result = dao.get_by_action_type(db, action_type="status_chang_d", workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-AT-05
def test_fal_at_05__leading_space_in_action_finds_nothing(db, st):
    """FAL-AT-05 — a leading space in the action finds nothing.
    Rules: `get_by_action_type` R1"""
    log(db, st, T10, action_type="status_changed")

    result = dao.get_by_action_type(db, action_type=" status_changed", workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-AT-06
def test_fal_at_06__stored_action_with_leading_space_not_found(db, st):
    """FAL-AT-06 — a stored action with a leading space is not found.
    Rules: `get_by_action_type` R1"""
    log(db, st, T10, action_type=" status_changed")

    result = dao.get_by_action_type(db, action_type="status_changed", workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-AT-07
def test_fal_at_07__other_workspaces_not_returned(db, st):
    """FAL-AT-07 — rows of an earlier and a later workspace are not returned.
    Rules: `get_by_action_type` R2"""
    log(db, st, T12, workspace_id=st.W0.id)
    a = log(db, st, T10)
    log(db, st, T12, workspace_id=st.W2.id)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-AT-08
def test_fal_at_08__newest_first_whatever_ids(db, st):
    """FAL-AT-08 — rows come newest first, whatever their ids.
    Rules: `get_by_action_type` R3"""
    a = log(db, st, T10)
    b = log(db, st, T12, entity_id=3)
    c = log(db, st, T11, entity_id=20)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] FAL-AT-09
def test_fal_at_09__tie_rows_between_newer_and_older(db, st):
    """FAL-AT-09 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_by_action_type` R3"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T12)
    d = log(db, st, T10)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-AT-10
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_at_10__tie_highest_id_first_after_lowest_updated(db, st):
    """FAL-AT-10 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_by_action_type` R3 [BUG-2370]"""
    a = log(db, st, T11, entity_id=30)
    b = log(db, st, T11, entity_id=20)
    c = log(db, st, T11, entity_id=25)
    edit_lowest(db, a)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] FAL-AT-11
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_at_11__orders_by_performed_at_then_id_desc(db, st):
    """FAL-AT-11 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_action_type` R3 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-AT-12
def test_fal_at_12__window_after_the_order(db, st):
    """FAL-AT-12 — skip and limit cut a window after the order.
    Rules: `get_by_action_type` R2"""
    log(db, st, T12)
    b = log(db, st, T10)
    c = log(db, st, T11)
    log(db, st, T9)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [c.id, b.id]


def _numbered_101(st):
    """Given of AT-13 / AT-14: Ek = log at T10 + k minutes, but entity_id k."""
    return [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {"entity_id": k})) for k in range(1, 102)]


# [claude] FAL-AT-13
def test_fal_at_13__defaults_give_newest_100(db, st):
    """FAL-AT-13 — with the defaults 101 rows give the newest 100.
    Rules: `get_by_action_type` R2"""
    newest = many(db, _numbered_101(st))

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] FAL-AT-14
def test_fal_at_14__limit_1000_gives_all_101(db, st):
    """FAL-AT-14 — limit=1000 gives all 101.
    Rules: `get_by_action_type` R2"""
    newest = many(db, _numbered_101(st))

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] FAL-AT-15
def test_fal_at_15__limit_zero_returns_empty(db, st):
    """FAL-AT-15 — limit=0 returns an empty list.
    Rules: `get_by_action_type` R2"""
    log(db, st, T10)

    result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-AT-16
def test_fal_at_16__negative_limit_raises(db, st):
    """FAL-AT-16 — a negative limit raises.
    Rules: `get_by_action_type` Errors (as `get_by_entity` row 1)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored(db) == before


# [claude] FAL-AT-17
def test_fal_at_17__negative_skip_raises(db, st):
    """FAL-AT-17 — a negative skip raises.
    Rules: `get_by_action_type` Errors (as `get_by_entity` row 2)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored(db) == before


# [claude] FAL-AT-18
def test_fal_at_18__writes_nothing(db, st):
    """FAL-AT-18 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `get_by_action_type` Side effects"""
    a = log(db, st, T10)
    b, p = wn_setup(db, st)

    with StatementRecorder(db) as rec:
        result = dao.get_by_action_type(db, action_type="created", workspace_id=st.W1.id)

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
    assert rec.written() == []


# --------------------------------------------------------------------------- #
# get_by_user
# --------------------------------------------------------------------------- #


# [claude] FAL-BU-01
def test_fal_bu_01__one_person_s_rows(db, st):
    """FAL-BU-01 — one person's rows, not those of a lower or a higher user id.
    Rules: `get_by_user` R1, Returns"""
    log(db, st, T12, performed_by=st.U1.id)
    a = log(db, st, T10, performed_by=st.U2.id)
    b = pay(db, st, T11, performed_by=st.U2.id)
    log(db, st, T12, performed_by=st.U3.id)

    result = dao.get_by_user(db, user_id=st.U2.id, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]


# [claude] FAL-BU-02
def test_fal_bu_02__same_person_other_workspaces_not_returned(db, st):
    """FAL-BU-02 — the same person's rows in an earlier and a later workspace are not returned.
    Rules: `get_by_user` R2"""
    log(db, st, T12, workspace_id=st.W0.id, performed_by=st.U2.id)
    a = log(db, st, T10, performed_by=st.U2.id)
    log(db, st, T12, workspace_id=st.W2.id, performed_by=st.U2.id)

    result = dao.get_by_user(db, user_id=st.U2.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-BU-03
def test_fal_bu_03__unknown_user_returns_empty(db, st):
    """FAL-BU-03 — an unknown user returns an empty list.
    Rules: `get_by_user` R2"""
    log(db, st, T10)

    result = dao.get_by_user(db, user_id=MISSING, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-BU-04
def test_fal_bu_04__newest_first_whatever_ids(db, st):
    """FAL-BU-04 — rows come newest first, whatever their ids.
    Rules: `get_by_user` R3"""
    a = log(db, st, T10)
    b = log(db, st, T12, entity_id=3)
    c = log(db, st, T11, entity_id=20)

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] FAL-BU-05
def test_fal_bu_05__tie_rows_between_newer_and_older(db, st):
    """FAL-BU-05 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_by_user` R3"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T12)
    d = log(db, st, T10)

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-BU-06
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_bu_06__tie_highest_id_first_after_lowest_updated(db, st):
    """FAL-BU-06 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_by_user` R3 [BUG-2370]"""
    a = log(db, st, T11, action_type="voided")
    b = log(db, st, T11, action_type="updated")
    c = log(db, st, T11)
    edit_lowest(db, a)

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] FAL-BU-07
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_bu_07__orders_by_performed_at_then_id_desc(db, st):
    """FAL-BU-07 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_user` R3 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-BU-08
def test_fal_bu_08__window_after_the_order(db, st):
    """FAL-BU-08 — skip and limit cut a window after the order.
    Rules: `get_by_user` R2"""
    log(db, st, T12)
    b = log(db, st, T10)
    c = log(db, st, T11)
    log(db, st, T9)

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id, skip=1, limit=2)

    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] FAL-BU-09
def test_fal_bu_09__defaults_give_newest_100(db, st):
    """FAL-BU-09 — with the defaults 101 rows give the newest 100.
    Rules: `get_by_user` R2"""
    newest = many(db, [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {})) for k in range(1, 102)])

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] FAL-BU-10
def test_fal_bu_10__limit_1000_gives_all_101(db, st):
    """FAL-BU-10 — limit=1000 gives all 101.
    Rules: `get_by_user` R2"""
    newest = many(db, [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {})) for k in range(1, 102)])

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] FAL-BU-11
def test_fal_bu_11__limit_zero_returns_empty(db, st):
    """FAL-BU-11 — limit=0 returns an empty list.
    Rules: `get_by_user` R2"""
    log(db, st, T10)

    result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-BU-12
def test_fal_bu_12__negative_limit_raises(db, st):
    """FAL-BU-12 — a negative limit raises.
    Rules: `get_by_user` Errors (as `get_by_entity` row 1)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored(db) == before


# [claude] FAL-BU-13
def test_fal_bu_13__negative_skip_raises(db, st):
    """FAL-BU-13 — a negative skip raises.
    Rules: `get_by_user` Errors (as `get_by_entity` row 2)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored(db) == before


# [claude] FAL-BU-14
def test_fal_bu_14__writes_nothing(db, st):
    """FAL-BU-14 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `get_by_user` Side effects"""
    a = log(db, st, T10)
    b, p = wn_setup(db, st)

    with StatementRecorder(db) as rec:
        result = dao.get_by_user(db, user_id=st.U1.id, workspace_id=st.W1.id)

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
    assert rec.written() == []


# --------------------------------------------------------------------------- #
# get_by_date_range
# --------------------------------------------------------------------------- #


# [claude] FAL-DR-01
def test_fal_dr_01__between_naive_bounds_inclusive_newest_first(db, st):
    """FAL-DR-01 — rows between two naive bounds, both inclusive, newest first.
    Rules: `get_by_date_range` R1, Returns"""
    log(db, st, T9)
    a = log(db, st, T10)
    b = log(db, st, T11)
    log(db, st, T12)

    result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]


# [claude] FAL-DR-02
def test_fal_dr_02__one_microsecond_outside_not_returned(db, st):
    """FAL-DR-02 — one microsecond outside either bound is not returned.
    Rules: `get_by_date_range` R1"""
    log(db, st, T10 - US)
    a = log(db, st, T10)
    log(db, st, T11 + US)

    result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-03
def test_fal_dr_03__start_equal_to_end(db, st):
    """FAL-DR-03 — start equal to end returns the row at that moment.
    Rules: `get_by_date_range` R1"""
    a = log(db, st, T10)
    log(db, st, T11)

    result = dao.get_by_date_range(db, start_date=T10, end_date=T10, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-04
def test_fal_dr_04__start_after_end_returns_empty(db, st):
    """FAL-DR-04 — start after end returns an empty list, no error.
    Rules: `get_by_date_range` R2"""
    log(db, st, T10)
    log(db, st, T11)

    result = dao.get_by_date_range(db, start_date=T11, end_date=T10, workspace_id=st.W1.id)

    # Then 1
    assert result == []


# [claude] FAL-DR-05
def test_fal_dr_05__other_workspaces_not_returned(db, st):
    """FAL-DR-05 — rows of an earlier and a later workspace in the range are not returned.
    Rules: `get_by_date_range` R4"""
    log(db, st, T11, workspace_id=st.W0.id)
    a = log(db, st, T10)
    log(db, st, T11, workspace_id=st.W2.id)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-06
def test_fal_dr_06__naive_bounds_mean_utc_under_dhaka(db, st):
    """FAL-DR-06 — naive bounds mean UTC, also under Asia/Dhaka.
    Rules: `get_by_date_range` R3"""
    zone(db, "Asia/Dhaka")
    a = log(db, st, T12)

    result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30), end_date=datetime(2026, 3, 4, 12, 30),
                                   workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-07
def test_fal_dr_07__utc_aware_bounds_under_utc(db, st):
    """FAL-DR-07 — UTC-aware bounds find the moment under UTC.
    Rules: `get_by_date_range` R3"""
    zone(db, "UTC")
    a = log(db, st, T12)

    result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30, tzinfo=timezone.utc),
                                   end_date=datetime(2026, 3, 4, 12, 30, tzinfo=timezone.utc), workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-08
def test_fal_dr_08__plus6_bounds_under_utc(db, st):
    """FAL-DR-08 — +06:00 bounds find the same moment under UTC.
    Rules: `get_by_date_range` R3"""
    zone(db, "UTC")
    a = log(db, st, T12)

    result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 17, 30, tzinfo=PLUS6),
                                   end_date=datetime(2026, 3, 4, 18, 30, tzinfo=PLUS6), workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-09
@pytest.mark.xfail(strict=True, reason=R2371)
def test_fal_dr_09__utc_aware_bounds_under_dhaka(db, st):
    """FAL-DR-09 — UTC-aware bounds name the moment under Asia/Dhaka: the 12:00 row, not the 18:00 one.
    Rules: `get_by_date_range` R3 [BUG-2371]"""
    zone(db, "Asia/Dhaka")
    a = log(db, st, T12)
    log(db, st, datetime(2026, 3, 4, 18, 0, 0))

    result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30, tzinfo=timezone.utc),
                                   end_date=datetime(2026, 3, 4, 12, 30, tzinfo=timezone.utc), workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-10
@pytest.mark.xfail(strict=True, reason=R2371)
def test_fal_dr_10__plus6_bounds_under_new_york(db, st):
    """FAL-DR-10 — +06:00 bounds name the moment under America/New_York.
    Rules: `get_by_date_range` R3 [BUG-2371]"""
    zone(db, "America/New_York")
    a = log(db, st, T12)

    result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 17, 30, tzinfo=PLUS6),
                                   end_date=datetime(2026, 3, 4, 18, 30, tzinfo=PLUS6), workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-DR-11
def test_fal_dr_11__newest_first_whatever_ids(db, st):
    """FAL-DR-11 — rows come newest first, whatever their ids.
    Rules: `get_by_date_range` R5"""
    a = log(db, st, T10)
    b = log(db, st, T12)
    c = log(db, st, T11)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [b.id, c.id, a.id]


# [claude] FAL-DR-12
def test_fal_dr_12__tie_rows_between_newer_and_older(db, st):
    """FAL-DR-12 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_by_date_range` R5"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T12)
    d = log(db, st, T10)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-DR-13
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_dr_13__tie_highest_id_first_after_lowest_updated(db, st):
    """FAL-DR-13 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_by_date_range` R5 [BUG-2370]"""
    a = log(db, st, T11, action_type="voided")
    b = log(db, st, T11, action_type="updated")
    c = log(db, st, T11)
    edit_lowest(db, a)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [c.id, b.id, a.id]


# [claude] FAL-DR-14
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_dr_14__orders_by_performed_at_then_id_desc(db, st):
    """FAL-DR-14 — the query orders by performed_at, then id, both descending.
    Rules: `get_by_date_range` R5 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-DR-15
def test_fal_dr_15__range_before_page(db, st):
    """FAL-DR-15 — the range is applied before the page, and skip and limit cut a window.
    Rules: `get_by_date_range` R4"""
    log(db, st, datetime(2026, 3, 4, 13, 0, 0))
    log(db, st, T12)
    b = log(db, st, T11)
    log(db, st, T10)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


def _seconds_101(st):
    """Given of DR-16 / DR-17: Ek = log at T10 + k seconds."""
    return [FinancialAuditLog(**_log_fields(st, T10 + timedelta(seconds=k), {})) for k in range(1, 102)]


# [claude] FAL-DR-16
def test_fal_dr_16__defaults_give_newest_100(db, st):
    """FAL-DR-16 — with the defaults 101 rows give the newest 100.
    Rules: `get_by_date_range` R4"""
    newest = many(db, _seconds_101(st))

    result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]


# [claude] FAL-DR-17
def test_fal_dr_17__limit_1000_gives_all_101(db, st):
    """FAL-DR-17 — limit=1000 gives all 101.
    Rules: `get_by_date_range` R4"""
    newest = many(db, _seconds_101(st))

    result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest


# [claude] FAL-DR-18
def test_fal_dr_18__limit_zero_returns_empty(db, st):
    """FAL-DR-18 — limit=0 returns an empty list.
    Rules: `get_by_date_range` R4"""
    log(db, st, T10)

    result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-DR-19
def test_fal_dr_19__negative_limit_raises(db, st):
    """FAL-DR-19 — a negative limit raises.
    Rules: `get_by_date_range` Errors (as `get_by_entity` row 1)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored(db) == before


# [claude] FAL-DR-20
def test_fal_dr_20__negative_skip_raises(db, st):
    """FAL-DR-20 — a negative skip raises.
    Rules: `get_by_date_range` Errors (as `get_by_entity` row 2)"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id, skip=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored(db) == before


# [claude] FAL-DR-21
def test_fal_dr_21__writes_nothing(db, st):
    """FAL-DR-21 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `get_by_date_range` Side effects"""
    a = log(db, st, T10)
    b, p = wn_setup(db, st)

    with StatementRecorder(db) as rec:
        result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=st.W1.id)

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
    assert rec.written() == []


# --------------------------------------------------------------------------- #
# get_recent_logs
# --------------------------------------------------------------------------- #


# [claude] FAL-RC-01
def test_fal_rc_01__workspace_rows_newest_first(db, st):
    """FAL-RC-01 — the workspace's rows, newest first, whatever their ids.
    Rules: `get_recent_logs` R1, R2, Returns"""
    a = log(db, st, T10)
    b = pay(db, st, T12)
    c = log(db, st, T11, entity_type="account", entity_id=5)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, c.id, a.id]


# [claude] FAL-RC-02
def test_fal_rc_02__other_workspaces_not_returned(db, st):
    """FAL-RC-02 — newer rows of an earlier and a later workspace are not returned.
    Rules: `get_recent_logs` R3"""
    log(db, st, T12, workspace_id=st.W0.id)
    a = log(db, st, T10)
    log(db, st, T12, workspace_id=st.W2.id)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id)

    # Then 1
    assert ids(result) == [a.id]


def _minutes_51(st):
    """Given of RC-03 / RC-04: Ek = log at T10 + k minutes, k = 1 … 51."""
    return [FinancialAuditLog(**_log_fields(st, T10 + timedelta(minutes=k), {})) for k in range(1, 52)]


# [claude] FAL-RC-03
def test_fal_rc_03__default_gives_newest_50_of_51(db, st):
    """FAL-RC-03 — with the default 51 rows give the newest 50.
    Rules: `get_recent_logs` R1"""
    newest = many(db, _minutes_51(st))

    result = dao.get_recent_logs(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 50
    # Then 2
    assert ids(result) == newest[:50]


# [claude] FAL-RC-04
def test_fal_rc_04__limit_1000_gives_all_51(db, st):
    """FAL-RC-04 — limit=1000 gives all 51.
    Rules: `get_recent_logs` R1"""
    newest = many(db, _minutes_51(st))

    result = dao.get_recent_logs(db, workspace_id=st.W1.id, limit=1000)

    # Then 1
    assert len(result) == 51
    # Then 2
    assert ids(result) == newest


# [claude] FAL-RC-05
def test_fal_rc_05__limit_zero_returns_empty(db, st):
    """FAL-RC-05 — limit=0 returns an empty list.
    Rules: `get_recent_logs` R1"""
    log(db, st, T10)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FAL-RC-06
def test_fal_rc_06__limit_one_returns_newest(db, st):
    """FAL-RC-06 — limit=1 returns the newest row.
    Rules: `get_recent_logs` R1"""
    a = log(db, st, T11)
    log(db, st, T10)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id, limit=1)

    # Then 1
    assert ids(result) == [a.id]


# [claude] FAL-RC-07
def test_fal_rc_07__negative_limit_raises(db, st):
    """FAL-RC-07 — a negative limit raises.
    Rules: `get_recent_logs` R1, Errors"""
    log(db, st, T10)
    before = stored(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_recent_logs(db, workspace_id=st.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 4
    assert stored(db) == before


# [claude] FAL-RC-08
def test_fal_rc_08__tie_rows_between_newer_and_older(db, st):
    """FAL-RC-08 — on a tie both rows are returned, between the newer and the older.
    Rules: `get_recent_logs` R2"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T12)
    d = log(db, st, T10)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert result[0].id == c.id
    # Then 3
    assert {r.id for r in result[1:3]} == {a.id, b.id}
    # Then 4
    assert result[3].id == d.id


# [claude] FAL-RC-09
@pytest.mark.xfail(strict=False, reason=R2370)
def test_fal_rc_09__tie_at_cut_off_two_highest_ids(db, st):
    """FAL-RC-09 — with a tie at the cut-off, the latest two are the two highest ids.
    Rules: `get_recent_logs` R2 [BUG-2370]"""
    a = log(db, st, T11)
    b = log(db, st, T11)
    c = log(db, st, T11)
    edit_lowest(db, a)

    result = dao.get_recent_logs(db, workspace_id=st.W1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [c.id, b.id]


# [claude] FAL-RC-10
@pytest.mark.xfail(strict=True, reason=R2370)
def test_fal_rc_10__orders_by_performed_at_then_id_desc(db, st):
    """FAL-RC-10 — the query orders by performed_at, then id, both descending.
    Rules: `get_recent_logs` R2 [BUG-2370]"""
    a = log(db, st, T10)

    with StatementRecorder(db) as rec:
        result = dao.get_recent_logs(db, workspace_id=st.W1.id)
    sql = rec.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "performed_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("performed_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] FAL-RC-11
def test_fal_rc_11__writes_nothing(db, st):
    """FAL-RC-11 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: `get_recent_logs` Side effects"""
    a = log(db, st, T10)
    b, p = wn_setup(db, st)

    with StatementRecorder(db) as rec:
        result = dao.get_recent_logs(db, workspace_id=st.W1.id)

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
    assert rec.written() == []


# [claude] FAL-RC-12
def test_fal_rc_12__skip_keyword_raises_type_error_before_any_query(db, st):
    """FAL-RC-12 — a `skip` keyword raises TypeError before any query.
    Rules: `get_recent_logs` R1a"""
    log(db, st, T10)
    before = stored(db)

    with StatementRecorder(db) as rec:
        with pytest.raises(TypeError) as exc:
            dao.get_recent_logs(db, workspace_id=st.W1.id, skip=1)

    # Then 1
    assert "got an unexpected keyword argument 'skip'" in str(exc.value)
    # Then 2
    assert rec.statements == []
    # Then 3
    assert stored(db) == before


# --------------------------------------------------------------------------- #
# Model fact N1
# --------------------------------------------------------------------------- #


# [claude] FAL-N-01
def test_fal_n_01__row_without_performed_at_gets_a_value(db, st):
    """FAL-N-01 — a row flushed without performed_at gets a value.
    Rules: N1"""
    a = FinancialAuditLog(workspace_id=st.W1.id, entity_type="invoice", entity_id=10, action_type="created",
                          performed_by=st.U1.id)

    db.add(a)
    db.flush()
    db.refresh(a)

    row = reread(db, a.id)
    # Then 1
    assert row.performed_at is not None


# [claude] FAL-N-02
@pytest.mark.xfail(strict=True, reason=R2372)
def test_fal_n_02__row_without_performed_at_gets_naive_utc(db, st):
    """FAL-N-02 — a row flushed without performed_at gets naive UTC, whatever the database's time zone.
    Rules: N1 [BUG-2372]"""
    zone(db, "Asia/Dhaka")
    a = FinancialAuditLog(workspace_id=st.W1.id, entity_type="invoice", entity_id=10, action_type="created",
                          performed_by=st.U1.id)
    before = utcnow()

    db.add(a)
    db.flush()
    db.refresh(a)
    after = utcnow()

    row = reread(db, a.id)
    # Then 1
    assert row.performed_at.tzinfo is None
    # Then 2
    assert before <= row.performed_at <= after
