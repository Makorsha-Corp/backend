"""Unit tests for app/dao/project_component_item_ledger.py.

Implements tests/unit/dao/project_component_item_ledger.cases.md (Revision 2).
Real Postgres session (`db` fixture). Nothing is mocked and no clock is
patched (Conventions, Externals: None); every Given row sets `performed_at`.

Card numbers 01-16 and 18-22 of the four lists (CI get_by_component_and_item,
CO get_by_component, TT get_by_transaction_type, DR get_by_date_range) are the
same card four times: same Given, same Then, only the When's method differs.
Each such group is one test parametrized over the list, one param id per card
(`PCIL-CI-01`, `PCIL-CO-01`, ...). Every other card is its own test.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)`
# around `with db.begin_nested()`, and naive T1 ... T5 and day bounds as carded)
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from psycopg2.errors import (
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
)
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import ArgumentError, DataError

from app.dao.project_component_item_ledger import project_component_item_ledger_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao"
dao = project_component_item_ledger_dao

# Convention "MISSING"
MISSING = 999999999

# Convention "T1 ... T5": one hour apart, naive (UTC as stored)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
T4 = datetime(2026, 1, 1, 12, 0, 0)
T5 = datetime(2026, 1, 1, 13, 0, 0)

# Convention "Z1130, Z1230"
Z1130 = datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc)
Z1230 = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)

# Convention "P1730, P1830" (the same instants as Z1130, Z1230)
P1730 = datetime(2026, 1, 1, 17, 30, tzinfo=timezone(timedelta(hours=6)))
P1830 = datetime(2026, 1, 1, 18, 30, tzinfo=timezone(timedelta(hours=6)))


# Convention "HIGH_ID": a marker that `entry(..., id=HIGH_ID)` replaces, when
# the row is built, by high_id(db).
class _HighId:
    def __repr__(self):
        return "HIGH_ID"


HIGH_ID = _HighId()


def high_id(db):
    """max(greatest id or 0, last_value of the id sequence) + 1000001."""
    max_id = db.scalar(select(func.max(ProjectComponentItemLedger.id))) or 0
    seq = db.scalar(
        text("SELECT pg_get_serial_sequence('project_component_item_ledger', 'id')")
    )
    last_value = db.scalar(text(f"SELECT last_value FROM {seq}"))
    return max(max_id, last_value) + 1000001


# --------------------------------------------------------------------------- #
# xfail markers (Conventions "xfail cards")
# --------------------------------------------------------------------------- #

REVISIT = "revisit after launch (owner 2026-11-10)"


def bug(bug_id, *, strict=True, revisit=True):
    reason = f"{bug_id} — {REVISIT}" if revisit else bug_id
    return pytest.mark.xfail(strict=strict, reason=reason)


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, this order, each flushed)
# --------------------------------------------------------------------------- #


def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def s(db):
    """W0..W2, U1..U3, F0..F2, PJ0 / PJ1 / PJD / PJ9, components, items."""
    r = SimpleNamespace(TAG=uuid.uuid4().hex[:8])
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2, r.U3 = make_profile(db), make_profile(db), make_profile(db)
    r.F0, r.F1, r.F2 = (
        _add(db, Factory(workspace_id=w.id, name="Plant " + r.TAG, abbreviation=a))
        for w, a in ((r.W0, "P0"), (r.W1, "P1"), (r.W2, "P2"))
    )

    def project(ws, factory, name, **extra):
        return _add(
            db,
            Project(
                workspace_id=ws.id,
                factory_id=factory.id,
                name=name,
                description="x",
                **extra,
            ),
        )

    r.PJ0 = project(r.W0, r.F0, "Zero")
    r.PJ1 = project(r.W1, r.F1, "Bridge A")
    r.PJD = project(
        r.W1, r.F1, "Old bridge", is_deleted=True, deleted_at=T1, deleted_by=r.U1.id
    )
    r.PJ9 = project(r.W2, r.F2, "Nine")

    def component(ws, proj, name):
        return _add(
            db, ProjectComponent(workspace_id=ws.id, project_id=proj.id, name=name)
        )

    r.C0 = component(r.W0, r.PJ0, "Base")
    r.CL = component(r.W1, r.PJ1, "Beam")
    r.C1 = component(r.W1, r.PJ1, "Deck")
    r.C2 = component(r.W1, r.PJ1, "Wall")
    r.CD = component(r.W1, r.PJD, "Floor")
    r.C9 = component(r.W2, r.PJ9, "Nine")

    def item(ws, name, **extra):
        return _add(
            db,
            Item(
                workspace_id=ws.id,
                name=name,
                name_normalized=name.lower(),
                unit="pcs",
                **extra,
            ),
        )

    r.I0 = item(r.W0, "Pin")
    r.IL = item(r.W1, "Washer")
    r.I1 = item(r.W1, "Bolt")
    r.I2 = item(r.W1, "Nut")
    r.IR = item(r.W1, "Old gasket", is_active=False)
    r.I9 = item(r.W2, "Rivet")
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def ENTRY(s):
    """Convention "ENTRY"."""
    return {
        "workspace_id": s.W1.id,
        "project_component_id": s.C1.id,
        "item_id": s.I1.id,
        "transaction_type": "transfer_in",
        "quantity": 1,
        "qty_before": 4,
        "qty_after": 5,
        "unit_cost": Decimal("2.00"),
        "total_cost": Decimal("2.00"),
        "source_type": "manual",
        "performed_by": s.U1.id,
    }


def entry(db, s, performed_at, **but):
    """Convention "entry": ENTRY with `performed_at`; `but` lists what differs."""
    fields = {**ENTRY(s), **but}
    if fields.get("id") is HIGH_ID:
        fields["id"] = high_id(db)
    return _add(db, ProjectComponentItemLedger(**fields, performed_at=performed_at))


def minute_rows(db, s, n, **but):
    """`rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(n)]`,
    each added and flushed in this order (k = 0 is the oldest)."""
    rows = [
        ProjectComponentItemLedger(
            **{**ENTRY(s), **but}, performed_at=T1 + timedelta(minutes=k)
        )
        for k in range(n)
    ]
    for row in rows:
        db.add(row)
        db.flush()
    return rows


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


# Convention "nothing written": ledger rows, all workspaces
def ledger_rows(db):
    return db.scalar(select(func.count()).select_from(ProjectComponentItemLedger))


class StatementRecorder:
    """Convention "Statement recorder" (before_cursor_execute on the connection)."""

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
        """The one SELECT from project_component_item_ledger."""
        (only,) = [
            st
            for st in self.statements
            if st.lstrip().upper().startswith("SELECT")
            and "FROM project_component_item_ledger" in st
        ]
        return only

    @property
    def order_part(self):
        sql = self.sql
        if "ORDER BY" not in sql:
            return ""
        return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]

    @property
    def lock_part(self):
        sql = self.sql
        return sql.split("FOR UPDATE", 1)[1] if "FOR UPDATE" in sql else ""

    @property
    def written(self):
        return [
            st
            for st in self.statements
            if st.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]


# --------------------------------------------------------------------------- #
# The four lists' shared cards (numbers 01-16, 18-22)
# --------------------------------------------------------------------------- #

LIST_BUG = {"CI": "BUG-640", "CO": "BUG-640", "TT": "BUG-2462", "DR": "BUG-2462"}


def list_call(fam, db, s, *, workspace_id=None, **page):
    """The When of card <fam>-NN: C1 / I1 / "transfer_in" / T1..T5, workspace W1
    unless the card names another."""
    ws = s.W1.id if workspace_id is None else workspace_id
    if fam == "CI":
        return dao.get_by_component_and_item(
            db, project_component_id=s.C1.id, item_id=s.I1.id, workspace_id=ws, **page
        )
    if fam == "CO":
        return dao.get_by_component(
            db, project_component_id=s.C1.id, workspace_id=ws, **page
        )
    if fam == "TT":
        return dao.get_by_transaction_type(
            db, transaction_type="transfer_in", workspace_id=ws, **page
        )
    return dao.get_by_date_range(
        db, workspace_id=ws, start_date=T1, end_date=T5, **page
    )


def lists(num, xfail=None):
    """Parametrize over the four lists: one param id per card (PCIL-CI-NN ...)."""
    params = []
    for fam in ("CI", "CO", "TT", "DR"):
        marks = ()
        if xfail is not None:
            marks = bug(LIST_BUG[fam], strict=(xfail == "strict"))
        params.append(pytest.param(fam, id=f"PCIL-{fam}-{num:02d}", marks=marks))
    return pytest.mark.parametrize("fam", params)


# [claude] PCIL-CI-01, PCIL-CO-01, PCIL-TT-01, PCIL-DR-01
@lists(1)
def test_pcil_list_01__newest_first_whatever_insertion_order(db, s, fam):
    """PCIL-CI-01 / CO-01 / TT-01 / DR-01 — returns ledger rows newest first, whatever the insertion order and the ids.
    Rules: R1, R3 (newest first; holds today), Returns of each list (TT: + R2; DR: R1, R5, R4)."""
    e1 = entry(db, s, T2)
    e2 = entry(db, s, T3)
    e3 = entry(db, s, T1, id=HIGH_ID)
    result = list_call(fam, db, s)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert all(isinstance(r, ProjectComponentItemLedger) for r in result)
    # Then 3
    assert ids(result) == [e2.id, e1.id, e3.id]


# [claude] PCIL-CI-02, PCIL-CO-02, PCIL-TT-02, PCIL-DR-02
@lists(2)
def test_pcil_list_02__w0_w2_rows_not_returned(db, s, fam):
    """PCIL-CI-02 / CO-02 / TT-02 / DR-02 — rows of W0 and W2 with the same component and item ids are not returned.
    Rules: R1 (CO, TT: R1, R2; DR: R1, R5)."""
    entry(db, s, T4, workspace_id=s.W0.id)
    e1 = entry(db, s, T1)
    entry(db, s, T5, workspace_id=s.W2.id)
    result = list_call(fam, db, s)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CI-03, PCIL-CO-03, PCIL-TT-03, PCIL-DR-03
@lists(3)
def test_pcil_list_03__asked_for_w2_only_w2_row(db, s, fam):
    """PCIL-CI-03 / CO-03 / TT-03 / DR-03 — asked for W2, only the W2 row is returned, though W0 and W1 rows exist.
    Rules: R1 (CO, TT: R1, R2; DR: R1, R5)."""
    entry(db, s, T4, workspace_id=s.W0.id)
    entry(db, s, T5)
    x2 = entry(db, s, T2, workspace_id=s.W2.id)
    result = list_call(fam, db, s, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [x2.id]


# [claude] PCIL-CI-04, PCIL-CO-04, PCIL-TT-04, PCIL-DR-04
@lists(4)
def test_pcil_list_04__asked_for_w0_only_w0_row(db, s, fam):
    """PCIL-CI-04 / CO-04 / TT-04 / DR-04 — asked for W0, only the W0 row is returned.
    Rules: R1 (CO, TT: R1, R2; DR: R1, R5)."""
    x0 = entry(db, s, T2, workspace_id=s.W0.id)
    entry(db, s, T5)
    entry(db, s, T4, workspace_id=s.W2.id)
    result = list_call(fam, db, s, workspace_id=s.W0.id)
    # Then 1
    assert ids(result) == [x0.id]


# [claude] PCIL-CI-05, PCIL-CO-05, PCIL-TT-05, PCIL-DR-05
@lists(5)
def test_pcil_list_05__unknown_workspace_empty(db, s, fam):
    """PCIL-CI-05 / CO-05 / TT-05 / DR-05 — an unknown workspace id returns an empty list.
    Rules: R1 (CO, TT: R1, R2; DR: R1, R5)."""
    entry(db, s, T1)
    result = list_call(fam, db, s, workspace_id=MISSING)
    # Then 1
    assert result == []


# [claude] PCIL-CI-06, PCIL-CO-06, PCIL-TT-06, PCIL-DR-06
@lists(6)
def test_pcil_list_06__skip_1_limit_1_middle_row(db, s, fam):
    """PCIL-CI-06 / CO-06 / TT-06 / DR-06 — skip 1 and limit 1 return exactly the middle row.
    Rules: paging R5 (DR: R6), order R3 (DR: R4) (newest first; holds today)."""
    entry(db, s, T1)
    entry(db, s, T3)
    e2 = entry(db, s, T2)
    result = list_call(fam, db, s, skip=1, limit=1)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-CI-07, PCIL-CO-07, PCIL-TT-07, PCIL-DR-07
@lists(7)
def test_pcil_list_07__skip_2_limit_1_oldest_row(db, s, fam):
    """PCIL-CI-07 / CO-07 / TT-07 / DR-07 — skip 2 and limit 1 return the oldest row.
    Rules: paging R5 (DR: R6)."""
    e1 = entry(db, s, T1)
    entry(db, s, T3)
    entry(db, s, T2)
    result = list_call(fam, db, s, skip=2, limit=1)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CI-08, PCIL-CO-08, PCIL-TT-08, PCIL-DR-08
@lists(8)
def test_pcil_list_08__skip_equal_to_rows_empty(db, s, fam):
    """PCIL-CI-08 / CO-08 / TT-08 / DR-08 — skip equal to the number of rows returns an empty list.
    Rules: paging R5 (DR: R6)."""
    entry(db, s, T1)
    entry(db, s, T3)
    entry(db, s, T2)
    result = list_call(fam, db, s, skip=3)
    # Then 1
    assert result == []


# [claude] PCIL-CI-09, PCIL-CO-09, PCIL-TT-09, PCIL-DR-09
@lists(9)
def test_pcil_list_09__limit_0_empty(db, s, fam):
    """PCIL-CI-09 / CO-09 / TT-09 / DR-09 — limit 0 returns an empty list.
    Rules: paging R5 (DR: R6)."""
    entry(db, s, T1)
    entry(db, s, T3)
    entry(db, s, T2)
    result = list_call(fam, db, s, limit=0)
    # Then 1
    assert result == []


# [claude] PCIL-CI-10, PCIL-CO-10, PCIL-TT-10, PCIL-DR-10
@lists(10)
def test_pcil_list_10__limit_1_newest_row(db, s, fam):
    """PCIL-CI-10 / CO-10 / TT-10 / DR-10 — limit 1 returns only the newest row.
    Rules: paging R5 (DR: R6)."""
    entry(db, s, T1)
    e3 = entry(db, s, T3)
    entry(db, s, T2)
    result = list_call(fam, db, s, limit=1)
    # Then 1
    assert ids(result) == [e3.id]


# [claude] PCIL-CI-11, PCIL-CO-11, PCIL-TT-11, PCIL-DR-11
@lists(11)
def test_pcil_list_11__default_limit_101_rows_give_100_newest(db, s, fam):
    """PCIL-CI-11 / CO-11 / TT-11 / DR-11 — with the default limit, 101 rows give the 100 newest; the oldest is missing.
    Rules: paging R5 (DR: R6)."""
    rows = minute_rows(db, s, 101)
    result = list_call(fam, db, s)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)
    # Then 3
    assert ids(result)[0] == rows[100].id


# [claude] PCIL-CI-12, PCIL-CO-12, PCIL-TT-12, PCIL-DR-12
@lists(12)
def test_pcil_list_12__default_limit_100_rows_all(db, s, fam):
    """PCIL-CI-12 / CO-12 / TT-12 / DR-12 — with the default limit, exactly 100 rows are all returned.
    Rules: paging R5 (DR: R6)."""
    rows = minute_rows(db, s, 100)
    result = list_call(fam, db, s)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result)[-1] == rows[0].id


# [claude] PCIL-CI-13, PCIL-CO-13, PCIL-TT-13, PCIL-DR-13
@lists(13)
def test_pcil_list_13__limit_1000_no_upper_cap(db, s, fam):
    """PCIL-CI-13 / CO-13 / TT-13 / DR-13 — limit 1000 returns all 101 rows: no upper cap.
    Rules: paging R5 (DR: R6)."""
    rows = minute_rows(db, s, 101)
    result = list_call(fam, db, s, limit=1000)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result)[-1] == rows[0].id


# [claude] PCIL-CI-14, PCIL-CO-14, PCIL-TT-14, PCIL-DR-14
@lists(14)
def test_pcil_list_14__negative_limit_rejected(db, s, fam):
    """PCIL-CI-14 / CO-14 / TT-14 / DR-14 — a negative limit makes the database reject the query.
    Rules: paging R5 (DR: R6), Errors (DR: row 2)."""
    entry(db, s, T1)
    before = ledger_rows(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            list_call(fam, db, s, limit=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert ledger_rows(db) == before


# [claude] PCIL-CI-15, PCIL-CO-15, PCIL-TT-15, PCIL-DR-15
@lists(15)
def test_pcil_list_15__negative_skip_rejected(db, s, fam):
    """PCIL-CI-15 / CO-15 / TT-15 / DR-15 — a negative skip makes the database reject the query.
    Rules: paging R5 (DR: R6), Errors (DR: row 2)."""
    entry(db, s, T1)
    before = ledger_rows(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            list_call(fam, db, s, skip=-1)
    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert ledger_rows(db) == before


# [claude] PCIL-CI-16, PCIL-CO-16, PCIL-TT-16, PCIL-DR-16
@lists(16)
def test_pcil_list_16__workspace_filter_before_page(db, s, fam):
    """PCIL-CI-16 / CO-16 / TT-16 / DR-16 — the workspace filter comes before the page: a newer W2 row takes no place.
    Rules: paging R5 (DR: R6), R1 (CO, TT: + R2; DR: + R5)."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    entry(db, s, T5, workspace_id=s.W2.id)
    result = list_call(fam, db, s, skip=1, limit=1)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-CI-18, PCIL-CO-18, PCIL-TT-18, PCIL-DR-18
@lists(18)
def test_pcil_list_18__tied_rows_between_newer_and_older(db, s, fam):
    """PCIL-CI-18 / CO-18 / TT-18 / DR-18 — tied rows are each returned once, between the newer and the older row.
    Rules: order R3 (DR: R4) (newest first; holds today)."""
    o = entry(db, s, T1)
    n = entry(db, s, T3)
    b = entry(db, s, T2, qty_after=15)
    c = entry(db, s, T2, id=HIGH_ID, qty_after=10)
    a = entry(db, s, T2, qty_after=99)
    result = list_call(fam, db, s)
    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])


# [claude] PCIL-CI-19, PCIL-CO-19, PCIL-TT-19, PCIL-DR-19
@lists(19, xfail="non-strict")
def test_pcil_list_19__tie_highest_id_first_after_update(db, s, fam):
    """PCIL-CI-19 / CO-19 / TT-19 / DR-19 — on a tie the highest id comes first, when the lowest id was updated and other columns would sort otherwise.
    Rules: order R3 (DR: R4) [BUG-640 for CI, CO; BUG-2462 for TT, DR]."""
    b = entry(db, s, T2, performed_by=s.U3.id, notes="Abe", qty_after=15)
    c = entry(db, s, T2, id=HIGH_ID, performed_by=s.U1.id, notes="Mid", qty_after=10)
    a = entry(db, s, T2, performed_by=s.U2.id, notes="Zed", qty_after=99)
    db.execute(
        text(
            "UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"
        ),
        {"i": b.id},
    )
    db.expire_all()
    result = list_call(fam, db, s)
    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]


# [claude] PCIL-CI-20, PCIL-CO-20, PCIL-TT-20, PCIL-DR-20
@lists(20, xfail="non-strict")
def test_pcil_list_20__tied_pages_neither_repeat_nor_miss(db, s, fam):
    """PCIL-CI-20 / CO-20 / TT-20 / DR-20 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: order R3 (DR: R4) [BUG-640 for CI, CO; BUG-2462 for TT, DR], paging R5 (DR: R6)."""
    a = entry(db, s, T2, notes="Zed")
    b = entry(db, s, T2, notes="Abe")
    c = entry(db, s, T2, id=HIGH_ID, notes="Mid")
    d = entry(db, s, T2, notes="Kay")
    db.execute(
        text(
            "UPDATE project_component_item_ledger SET notes = 'Zed two' WHERE id = :i"
        ),
        {"i": a.id},
    )
    db.expire_all()
    pages = [list_call(fam, db, s, skip=k, limit=1) for k in range(4)]
    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [c.id, d.id, b.id, a.id]


# [claude] PCIL-CI-21, PCIL-CO-21, PCIL-TT-21, PCIL-DR-21
@lists(21, xfail="strict")
def test_pcil_list_21__orders_by_performed_at_then_id_desc(db, s, fam):
    """PCIL-CI-21 / CO-21 / TT-21 / DR-21 — the query orders by performed_at newest first, then id highest first.
    Rules: order R3 (DR: R4) [BUG-640 for CI, CO; BUG-2462 for TT, DR]."""
    e1 = entry(db, s, T1)
    with StatementRecorder(db) as rec:
        result = list_call(fam, db, s)
    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "project_component_item_ledger.performed_at DESC" in rec.order_part
    # Then 4
    assert (
        "project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC"
        in rec.order_part
    )


# [claude] PCIL-CI-22, PCIL-CO-22, PCIL-TT-22, PCIL-DR-22
@lists(22)
def test_pcil_list_22__writes_nothing_no_join(db, s, fam):
    """PCIL-CI-22 / CO-22 / TT-22 / DR-22 — writes nothing: a pending row stays pending and unseen, an unflushed edit stays unflushed, no parent is joined.
    Rules: Side effects, R4 (DR: R5)."""
    e1 = entry(db, s, T1)
    b = entry(db, s, T2)
    b.notes = "Edited"
    p = ProjectComponentItemLedger(**ENTRY(s), performed_at=T4)
    db.add(p)
    before = ledger_rows(db)
    with StatementRecorder(db) as rec:
        result = list_call(fam, db, s)
    # Then 1
    assert ids(result) == [b.id, e1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "JOIN" not in rec.sql.upper()
    # Then 9
    assert ledger_rows(db) == before
    # Then 10
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# `get_by_component_and_item` (own cards)
# --------------------------------------------------------------------------- #


def ci_call(db, s, **kw):
    """get_by_component_and_item with the card's arguments (C1, I1, W1 by default)."""
    args = {
        "project_component_id": s.C1.id,
        "item_id": s.I1.id,
        "workspace_id": s.W1.id,
        **kw,
    }
    return dao.get_by_component_and_item(db, **args)


# [claude] PCIL-CI-17
def test_pcil_ci_17__newer_row_of_other_item_takes_no_place(db, s):
    """PCIL-CI-17 — the filter comes before the page: a newer row of another item takes no place.
    Rules: get_by_component_and_item R5, R1."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    entry(db, s, T5, item_id=s.I2.id)
    result = ci_call(db, s, skip=1, limit=1)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-CI-23
def test_pcil_ci_23__other_items_of_component_not_returned(db, s):
    """PCIL-CI-23 — rows of other items of the same component are not returned, the lower and the higher item id.
    Rules: get_by_component_and_item R2."""
    entry(db, s, T4, item_id=s.IL.id)
    e1 = entry(db, s, T1)
    entry(db, s, T5, item_id=s.I2.id)
    result = ci_call(db, s)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CI-24
def test_pcil_ci_24__same_item_other_components_not_returned(db, s):
    """PCIL-CI-24 — rows of the same item on other components are not returned, the lower and the higher component id.
    Rules: get_by_component_and_item R2."""
    entry(db, s, T4, project_component_id=s.CL.id)
    e1 = entry(db, s, T1)
    entry(db, s, T5, project_component_id=s.C2.id)
    result = ci_call(db, s)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CI-25
def test_pcil_ci_25__asked_for_i2_only_i2_row(db, s):
    """PCIL-CI-25 — asked for item I2, only the I2 row is returned.
    Rules: get_by_component_and_item R2."""
    entry(db, s, T4, item_id=s.IL.id)
    entry(db, s, T5)
    eh = entry(db, s, T1, item_id=s.I2.id)
    result = ci_call(db, s, item_id=s.I2.id)
    # Then 1
    assert ids(result) == [eh.id]


# [claude] PCIL-CI-26
def test_pcil_ci_26__asked_for_c2_only_c2_row(db, s):
    """PCIL-CI-26 — asked for component C2, only the C2 row is returned.
    Rules: get_by_component_and_item R2."""
    entry(db, s, T4, project_component_id=s.CL.id)
    entry(db, s, T5)
    eh = entry(db, s, T1, project_component_id=s.C2.id)
    result = ci_call(db, s, project_component_id=s.C2.id)
    # Then 1
    assert ids(result) == [eh.id]


# [claude] PCIL-CI-27
def test_pcil_ci_27__every_type_and_performer_returned(db, s):
    """PCIL-CI-27 — every transaction type and performer of that component and item is returned.
    Rules: get_by_component_and_item R1."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, transaction_type="transfer_out")
    e3 = entry(db, s, T3, performed_by=s.U2.id)
    result = ci_call(db, s)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PCIL-CI-28
def test_pcil_ci_28__unknown_component_empty(db, s):
    """PCIL-CI-28 — an unknown component id returns an empty list.
    Rules: get_by_component_and_item R1."""
    entry(db, s, T1)
    result = ci_call(db, s, project_component_id=MISSING)
    # Then 1
    assert result == []


# [claude] PCIL-CI-29
def test_pcil_ci_29__item_id_0_matches_nothing(db, s):
    """PCIL-CI-29 — item_id 0 is an id that matches nothing.
    Rules: get_by_component_and_item R1."""
    entry(db, s, T1)
    result = ci_call(db, s, item_id=0)
    # Then 1
    assert result == []


# [claude] PCIL-CI-30
def test_pcil_ci_30__other_workspace_component_and_item_empty(db, s):
    """PCIL-CI-30 — a component and item of another workspace, asked under W1, return an empty list.
    Rules: get_by_component_and_item R1."""
    entry(db, s, T1)
    entry(
        db,
        s,
        T2,
        workspace_id=s.W2.id,
        project_component_id=s.C9.id,
        item_id=s.I9.id,
    )
    result = ci_call(db, s, project_component_id=s.C9.id, item_id=s.I9.id)
    # Then 1
    assert result == []


# [claude] PCIL-CI-31
def test_pcil_ci_31__deleted_project_component_row_returned(db, s):
    """PCIL-CI-31 — a row of a component of a soft-deleted project is returned.
    Rules: get_by_component_and_item R4 (P1)."""
    e1 = entry(db, s, T1, project_component_id=s.CD.id)
    result = ci_call(db, s, project_component_id=s.CD.id)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CI-32
def test_pcil_ci_32__inactive_item_row_returned(db, s):
    """PCIL-CI-32 — a row of an inactive item is returned.
    Rules: get_by_component_and_item R4 (P1)."""
    e1 = entry(db, s, T1, item_id=s.IR.id)
    result = ci_call(db, s, item_id=s.IR.id)
    # Then 1
    assert ids(result) == [e1.id]


# --------------------------------------------------------------------------- #
# `get_by_component` (own cards)
# --------------------------------------------------------------------------- #


def co_call(db, s, **kw):
    """get_by_component with the card's arguments (C1, W1 by default)."""
    args = {"project_component_id": s.C1.id, "workspace_id": s.W1.id, **kw}
    return dao.get_by_component(db, **args)


# [claude] PCIL-CO-17
def test_pcil_co_17__newer_row_of_other_component_takes_no_place(db, s):
    """PCIL-CO-17 — the filter comes before the page: a newer row of another component takes no place.
    Rules: get_by_component R5, R1, R2."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    entry(db, s, T5, project_component_id=s.C2.id)
    result = co_call(db, s, skip=1, limit=1)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-CO-23
def test_pcil_co_23__every_item_type_performer_returned(db, s):
    """PCIL-CO-23 — rows of every item, type and performer of the component are returned.
    Rules: get_by_component R1."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, item_id=s.I2.id)
    e3 = entry(
        db,
        s,
        T3,
        item_id=s.IL.id,
        transaction_type="damaged",
        performed_by=s.U2.id,
    )
    result = co_call(db, s)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PCIL-CO-24
def test_pcil_co_24__other_components_not_returned(db, s):
    """PCIL-CO-24 — rows of other components are not returned, the lower and the higher component id.
    Rules: get_by_component R1."""
    entry(db, s, T4, project_component_id=s.CL.id)
    e1 = entry(db, s, T1)
    entry(db, s, T5, project_component_id=s.C2.id)
    result = co_call(db, s)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-CO-25
def test_pcil_co_25__asked_for_c2_only_c2_row(db, s):
    """PCIL-CO-25 — asked for component C2, only the C2 row is returned.
    Rules: get_by_component R1."""
    entry(db, s, T4, project_component_id=s.CL.id)
    entry(db, s, T5)
    eh = entry(db, s, T1, project_component_id=s.C2.id)
    result = co_call(db, s, project_component_id=s.C2.id)
    # Then 1
    assert ids(result) == [eh.id]


# [claude] PCIL-CO-26
def test_pcil_co_26__other_workspace_component_empty(db, s):
    """PCIL-CO-26 — another workspace's component id, asked under W1, returns an empty list.
    Rules: get_by_component R2."""
    entry(db, s, T1)
    entry(
        db,
        s,
        T2,
        workspace_id=s.W2.id,
        project_component_id=s.C9.id,
        item_id=s.I9.id,
    )
    result = co_call(db, s, project_component_id=s.C9.id)
    # Then 1
    assert result == []


# [claude] PCIL-CO-27
def test_pcil_co_27__unknown_component_empty(db, s):
    """PCIL-CO-27 — an unknown component id returns an empty list.
    Rules: get_by_component R2."""
    entry(db, s, T1)
    result = co_call(db, s, project_component_id=MISSING)
    # Then 1
    assert result == []


# [claude] PCIL-CO-28
def test_pcil_co_28__component_id_0_matches_nothing(db, s):
    """PCIL-CO-28 — project_component_id 0 is an id that matches nothing.
    Rules: get_by_component R1."""
    entry(db, s, T1)
    result = co_call(db, s, project_component_id=0)
    # Then 1
    assert result == []


# [claude] PCIL-CO-29
def test_pcil_co_29__deleted_project_component_rows_returned(db, s):
    """PCIL-CO-29 — rows of a component of a soft-deleted project are returned.
    Rules: get_by_component R4 (P1)."""
    e1 = entry(db, s, T1, project_component_id=s.CD.id)
    e2 = entry(db, s, T2, project_component_id=s.CD.id, item_id=s.IR.id)
    result = co_call(db, s, project_component_id=s.CD.id)
    # Then 1
    assert ids(result) == [e2.id, e1.id]


# [claude] PCIL-CO-30
def test_pcil_co_30__inactive_item_row_returned(db, s):
    """PCIL-CO-30 — a row of an inactive item is returned.
    Rules: get_by_component R4 (P1)."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, item_id=s.IR.id)
    result = co_call(db, s)
    # Then 1
    assert ids(result) == [e2.id, e1.id]


# --------------------------------------------------------------------------- #
# `get_by_transaction_type` (own cards)
# --------------------------------------------------------------------------- #


# [claude] PCIL-TT-17
def test_pcil_tt_17__newer_row_of_other_type_takes_no_place(db, s):
    """PCIL-TT-17 — the filter comes before the page: a newer row of another type takes no place.
    Rules: get_by_transaction_type R5, R1, R2."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    entry(db, s, T5, transaction_type="transfer_out")
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_in", workspace_id=s.W1.id, skip=1, limit=1
    )
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-TT-23
def test_pcil_tt_23__look_alike_type_not_returned(db, s):
    """PCIL-TT-23 — a look-alike type is not returned.
    Rules: get_by_transaction_type R1."""
    e1 = entry(db, s, T1)
    entry(db, s, T2, transaction_type="transfer_out")
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_in", workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-TT-24
def test_pcil_tt_24__asked_for_transfer_out(db, s):
    """PCIL-TT-24 — asked for transfer_out, only that row is returned.
    Rules: get_by_transaction_type R1."""
    entry(db, s, T1)
    e2 = entry(db, s, T2, transaction_type="transfer_out")
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_out", workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-TT-25 ... PCIL-TT-33
@pytest.mark.parametrize(
    "argument",
    [
        pytest.param("Transfer_In", id="PCIL-TT-25"),
        pytest.param("TRANSFER_IN", id="PCIL-TT-26"),
        pytest.param("transfer", id="PCIL-TT-27"),
        pytest.param("transfer%", id="PCIL-TT-28"),
        pytest.param("transfer_i_", id="PCIL-TT-29"),
        pytest.param(" transfer_in", id="PCIL-TT-30"),
        pytest.param("transfer_in ", id="PCIL-TT-31"),
        pytest.param("", id="PCIL-TT-32"),
        pytest.param(None, id="PCIL-TT-33"),
    ],
)
def test_pcil_tt_25_33__argument_variant_matches_nothing(db, s, argument):
    """PCIL-TT-25 ... TT-33 — an argument that differs from the stored type (case, part, `%`, `_`, spaces, "", None) matches nothing.
    Rules: get_by_transaction_type R1."""
    entry(db, s, T1)
    entry(db, s, T2, transaction_type="transfer_out")
    result = dao.get_by_transaction_type(
        db, transaction_type=argument, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] PCIL-TT-34 ... PCIL-TT-37
@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("Transfer_In", id="PCIL-TT-34"),
        pytest.param(" transfer_in", id="PCIL-TT-35"),
        pytest.param("transferXin", id="PCIL-TT-36"),
        pytest.param("transfer_in_extra", id="PCIL-TT-37"),
    ],
)
def test_pcil_tt_34_37__stored_variant_not_matched(db, s, stored):
    """PCIL-TT-34 ... TT-37 — a stored type that differs from transfer_in (case, leading space, `_` replaced, longer) is not matched by transfer_in.
    Rules: get_by_transaction_type R1."""
    e1 = entry(db, s, T1)
    entry(db, s, T2, transaction_type=stored)
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_in", workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-TT-38
def test_pcil_tt_38__every_component_item_performer(db, s):
    """PCIL-TT-38 — rows of every component, item and performer of the workspace are returned.
    Rules: get_by_transaction_type R2."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, project_component_id=s.C2.id)
    e3 = entry(db, s, T3, item_id=s.I2.id)
    e4 = entry(db, s, T4, performed_by=s.U2.id)
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_in", workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]


# [claude] PCIL-TT-39
def test_pcil_tt_39__deleted_project_and_inactive_item_rows(db, s):
    """PCIL-TT-39 — rows of a soft-deleted project's component and of an inactive item are returned.
    Rules: get_by_transaction_type R4 (P1)."""
    e1 = entry(db, s, T1, project_component_id=s.CD.id)
    e2 = entry(db, s, T2, item_id=s.IR.id)
    e3 = entry(db, s, T3)
    result = dao.get_by_transaction_type(
        db, transaction_type="transfer_in", workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# --------------------------------------------------------------------------- #
# `get_by_date_range` (own cards)
# --------------------------------------------------------------------------- #


def dr_call(db, s, start_date, end_date, **kw):
    return dao.get_by_date_range(
        db, workspace_id=s.W1.id, start_date=start_date, end_date=end_date, **kw
    )


def e07_e12_e18(db, s):
    """Given E07, E12, E18 of DR-46 ... DR-51."""
    return (
        entry(db, s, datetime(2026, 1, 1, 7, 0, 0)),
        entry(db, s, datetime(2026, 1, 1, 12, 0, 0)),
        entry(db, s, datetime(2026, 1, 1, 18, 0, 0)),
    )


# [claude] PCIL-DR-17
def test_pcil_dr_17__row_just_after_end_takes_no_place(db, s):
    """PCIL-DR-17 — the filter comes before the page: a newer row of a time just after the end bound takes no place.
    Rules: get_by_date_range R6, R1, R5."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    entry(db, s, T5 + timedelta(microseconds=1))
    result = dr_call(db, s, T1, T5, skip=1, limit=1)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-23
def test_pcil_dr_23__both_bounds_inclusive(db, s):
    """PCIL-DR-23 — both bounds are inclusive: T1 to T3 returns all three rows.
    Rules: get_by_date_range R1."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2)
    e3 = entry(db, s, T3)
    result = dr_call(db, s, T1, T3)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PCIL-DR-24
def test_pcil_dr_24__bounds_one_microsecond_inside(db, s):
    """PCIL-DR-24 — bounds one microsecond inside keep only the middle row.
    Rules: get_by_date_range R1."""
    entry(db, s, T1)
    e2 = entry(db, s, T2)
    entry(db, s, T3)
    result = dr_call(
        db, s, T1 + timedelta(microseconds=1), T3 - timedelta(microseconds=1)
    )
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-25
def test_pcil_dr_25__start_at_row_keeps_it(db, s):
    """PCIL-DR-25 — a start exactly at the row keeps it.
    Rules: get_by_date_range R1."""
    e2 = entry(db, s, T2)
    result = dr_call(db, s, T2, T5)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-26
def test_pcil_dr_26__start_after_row_leaves_it_out(db, s):
    """PCIL-DR-26 — a start one microsecond after the row leaves it out.
    Rules: get_by_date_range R1."""
    entry(db, s, T2)
    result = dr_call(db, s, T2 + timedelta(microseconds=1), T5)
    # Then 1
    assert result == []


# [claude] PCIL-DR-27
def test_pcil_dr_27__end_at_row_keeps_it(db, s):
    """PCIL-DR-27 — an end exactly at the row keeps it.
    Rules: get_by_date_range R1."""
    e2 = entry(db, s, T2)
    result = dr_call(db, s, T1, T2)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-28
def test_pcil_dr_28__end_before_row_leaves_it_out(db, s):
    """PCIL-DR-28 — an end one microsecond before the row leaves it out.
    Rules: get_by_date_range R1."""
    entry(db, s, T2)
    result = dr_call(db, s, T1, T2 - timedelta(microseconds=1))
    # Then 1
    assert result == []


# [claude] PCIL-DR-29
def test_pcil_dr_29__equal_bounds_at_row(db, s):
    """PCIL-DR-29 — equal bounds at the row's instant return that row.
    Rules: get_by_date_range R1."""
    e2 = entry(db, s, T2)
    result = dr_call(db, s, T2, T2)
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-30
def test_pcil_dr_30__midnight_to_midnight_misses_row(db, s):
    """PCIL-DR-30 — a midnight-to-midnight range of the same day misses that day's row.
    Rules: get_by_date_range R2."""
    entry(db, s, T2)
    result = dr_call(
        db, s, datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 1, 0, 0, 0)
    )
    # Then 1
    assert result == []


# [claude] PCIL-DR-31
def test_pcil_dr_31__end_at_last_microsecond_keeps_row(db, s):
    """PCIL-DR-31 — an end at the last microsecond of the day keeps that day's row.
    Rules: get_by_date_range R2."""
    e2 = entry(db, s, T2)
    result = dr_call(
        db, s, datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 1, 23, 59, 59, 999999)
    )
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-DR-32
def test_pcil_dr_32__reversed_range_empty(db, s):
    """PCIL-DR-32 — a reversed range returns an empty list and raises nothing.
    Rules: get_by_date_range R2."""
    entry(db, s, T1)
    entry(db, s, T2)
    entry(db, s, T3)
    result = dr_call(db, s, T3, T1)
    # Then 1
    assert result == []


# [claude] PCIL-DR-33
def test_pcil_dr_33__every_component_item_type_performer(db, s):
    """PCIL-DR-33 — rows of every component, item, type and performer inside the window are returned.
    Rules: get_by_date_range R5."""
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, project_component_id=s.C2.id)
    e3 = entry(db, s, T3, item_id=s.I2.id)
    e4 = entry(db, s, T4, transaction_type="damaged", performed_by=s.U2.id)
    result = dr_call(db, s, T1, T5)
    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]


# [claude] PCIL-DR-34
def test_pcil_dr_34__start_none_argument_error_no_query(db, s):
    """PCIL-DR-34 — start_date None raises ArgumentError before any query is sent.
    Rules: get_by_date_range R3, Errors row 1."""
    entry(db, s, T1)
    before = ledger_rows(db)
    with StatementRecorder(db) as rec:
        # Then 1
        with pytest.raises(ArgumentError):
            dr_call(db, s, None, T3)
    # Then 2
    assert rec.statements == []
    # Then 3
    assert ledger_rows(db) == before


# [claude] PCIL-DR-35
def test_pcil_dr_35__end_none_argument_error_no_query(db, s):
    """PCIL-DR-35 — end_date None raises ArgumentError before any query is sent.
    Rules: get_by_date_range R3, Errors row 1."""
    entry(db, s, T1)
    before = ledger_rows(db)
    with StatementRecorder(db) as rec:
        # Then 1
        with pytest.raises(ArgumentError):
            dr_call(db, s, T1, None)
    # Then 2
    assert rec.statements == []
    # Then 3
    assert ledger_rows(db) == before


# [claude] PCIL-DR-36, PCIL-DR-37
@pytest.mark.parametrize(
    "zone",
    [
        pytest.param("SET LOCAL TimeZone = 'America/New_York'", id="PCIL-DR-36"),
        pytest.param("SET LOCAL TimeZone = 'Asia/Dhaka'", id="PCIL-DR-37"),
    ],
)
def test_pcil_dr_36_37__naive_bounds_as_given(db, s, zone):
    """PCIL-DR-36 / DR-37 — naive bounds are compared to the stored value as given, under the session zone America/New_York / Asia/Dhaka.
    Rules: get_by_date_range R1."""
    e1 = entry(db, s, T4)
    db.execute(text(zone))
    result = dr_call(db, s, datetime(2026, 1, 1, 11, 30), datetime(2026, 1, 1, 12, 30))
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-38, PCIL-DR-39
@pytest.mark.parametrize(
    "zone",
    [
        pytest.param(
            "SET LOCAL TimeZone = 'America/New_York'",
            id="PCIL-DR-38",
            marks=bug("BUG-2464"),
        ),
        pytest.param(
            "SET LOCAL TimeZone = 'Asia/Dhaka'", id="PCIL-DR-39", marks=bug("BUG-2464")
        ),
    ],
)
def test_pcil_dr_38_39__aware_utc_bounds_find_row(db, s, zone):
    """PCIL-DR-38 / DR-39 — aware UTC bounds find the row inside the UTC window under the session zone America/New_York / Asia/Dhaka.
    Rules: get_by_date_range R2a [BUG-2464]."""
    e1 = entry(db, s, T4)
    db.execute(text(zone))
    result = dr_call(db, s, Z1130, Z1230)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-40
@bug("BUG-2464")
def test_pcil_dr_40__offset_bounds_find_row_new_york(db, s):
    """PCIL-DR-40 — aware bounds with a +06:00 offset find the row under the session zone America/New_York.
    Rules: get_by_date_range R2a [BUG-2464]."""
    e1 = entry(db, s, T4)
    db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))
    result = dr_call(db, s, P1730, P1830)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-41
@bug("BUG-2464")
def test_pcil_dr_41__aware_bounds_keep_only_utc_row_dhaka(db, s):
    """PCIL-DR-41 — aware UTC bounds keep only the row in the UTC window under the session zone Asia/Dhaka.
    Rules: get_by_date_range R2a [BUG-2464]."""
    e1 = entry(db, s, T4)
    entry(db, s, datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))
    result = dr_call(db, s, Z1130, Z1230)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-42
def test_pcil_dr_42__control_aware_utc_bounds_under_utc(db, s):
    """PCIL-DR-42 — control: aware UTC bounds find the row under the session zone UTC.
    Rules: get_by_date_range R2a."""
    e1 = entry(db, s, T4)
    db.execute(text("SET LOCAL TimeZone = 'UTC'"))
    result = dr_call(db, s, Z1130, Z1230)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-43
def test_pcil_dr_43__control_offset_bounds_converted_under_utc(db, s):
    """PCIL-DR-43 — control: aware bounds with an offset are converted, not cut off, under the session zone UTC.
    Rules: get_by_date_range R2a."""
    e1 = entry(db, s, T4)
    db.execute(text("SET LOCAL TimeZone = 'UTC'"))
    result = dr_call(db, s, P1730, P1830)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-44
def test_pcil_dr_44__control_aware_bounds_leave_out_outside_row(db, s):
    """PCIL-DR-44 — control: aware UTC bounds leave out a row outside the window under the session zone UTC.
    Rules: get_by_date_range R2a."""
    e1 = entry(db, s, T4)
    entry(db, s, T5)
    db.execute(text("SET LOCAL TimeZone = 'UTC'"))
    result = dr_call(db, s, Z1130, Z1230)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-DR-45
def test_pcil_dr_45__deleted_project_and_inactive_item_rows(db, s):
    """PCIL-DR-45 — rows of a soft-deleted project's component and of an inactive item are returned.
    Rules: get_by_date_range R5 (P1)."""
    e1 = entry(db, s, T1, project_component_id=s.CD.id)
    e2 = entry(db, s, T2, item_id=s.IR.id)
    e3 = entry(db, s, T3)
    result = dr_call(db, s, T1, T5)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PCIL-DR-46
@bug("BUG-2464")
def test_pcil_dr_46__aware_start_naive_end_new_york(db, s):
    """PCIL-DR-46 — an aware start and a naive end are each normalised on their own, under America/New_York.
    Rules: get_by_date_range R2b [BUG-2464]."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))
    result = dr_call(db, s, Z1130, datetime(2026, 1, 1, 12, 30, 0))
    # Then 1
    assert ids(result) == [e12.id]


# [claude] PCIL-DR-47
@bug("BUG-2464")
def test_pcil_dr_47__naive_start_aware_end_dhaka(db, s):
    """PCIL-DR-47 — a naive start and an aware end are each normalised on their own, under Asia/Dhaka.
    Rules: get_by_date_range R2b [BUG-2464]."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))
    result = dr_call(db, s, datetime(2026, 1, 1, 11, 30, 0), Z1230)
    # Then 1
    assert ids(result) == [e12.id]


# [claude] PCIL-DR-48
@bug("BUG-2464")
def test_pcil_dr_48__naive_start_aware_end_new_york(db, s):
    """PCIL-DR-48 — a naive start and an aware end, under America/New_York.
    Rules: get_by_date_range R2b [BUG-2464]."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))
    result = dr_call(db, s, datetime(2026, 1, 1, 11, 30, 0), Z1230)
    # Then 1
    assert ids(result) == [e12.id]


# [claude] PCIL-DR-49
@bug("BUG-2464")
def test_pcil_dr_49__aware_start_naive_end_dhaka(db, s):
    """PCIL-DR-49 — an aware start and a naive end, under Asia/Dhaka.
    Rules: get_by_date_range R2b [BUG-2464]."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))
    result = dr_call(db, s, Z1130, datetime(2026, 1, 1, 12, 30, 0))
    # Then 1
    assert ids(result) == [e12.id]


# [claude] PCIL-DR-50
def test_pcil_dr_50__control_aware_start_naive_end_utc(db, s):
    """PCIL-DR-50 — control: an aware start and a naive end under UTC run the query and keep only the row inside.
    Rules: get_by_date_range R2b (holds today and after the fix)."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'UTC'"))
    result = dr_call(db, s, Z1130, datetime(2026, 1, 1, 12, 30, 0))
    # Then 1
    assert ids(result) == [e12.id]


# [claude] PCIL-DR-51
def test_pcil_dr_51__control_naive_start_aware_end_utc(db, s):
    """PCIL-DR-51 — control: a naive start and an aware end under UTC run the query and keep only the row inside.
    Rules: get_by_date_range R2b (holds today and after the fix)."""
    _e07, e12, _e18 = e07_e12_e18(db, s)
    db.execute(text("SET LOCAL TimeZone = 'UTC'"))
    result = dr_call(db, s, datetime(2026, 1, 1, 11, 30, 0), Z1230)
    # Then 1
    assert ids(result) == [e12.id]


# --------------------------------------------------------------------------- #
# `get_by_performer` (to add, BUG-645): every call raises AttributeError today
# --------------------------------------------------------------------------- #

BUG_645 = bug("BUG-645", revisit=False)


# [claude] PCIL-PF-01
@BUG_645
def test_pcil_pf_01__user_rows_newest_first(db, s):
    """PCIL-PF-01 — rows of every component, item and type of that user are returned, newest first.
    Rules: get_by_performer R1 [BUG-645], R2 [BUG-645]."""
    e1 = entry(db, s, T2, performed_by=s.U2.id)
    e2 = entry(db, s, T3, performed_by=s.U2.id, project_component_id=s.C2.id)
    e3 = entry(
        db,
        s,
        T1,
        id=HIGH_ID,
        performed_by=s.U2.id,
        item_id=s.I2.id,
        transaction_type="damaged",
    )
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e2.id, e1.id, e3.id]


# [claude] PCIL-PF-02
@BUG_645
def test_pcil_pf_02__lower_and_higher_profile_not_returned(db, s):
    """PCIL-PF-02 — rows of the lower and the higher profile id are not returned.
    Rules: get_by_performer R1 [BUG-645]."""
    entry(db, s, T4, performed_by=s.U1.id)
    e1 = entry(db, s, T1, performed_by=s.U2.id)
    entry(db, s, T5, performed_by=s.U3.id)
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-PF-03
@BUG_645
def test_pcil_pf_03__same_user_w0_w2_not_returned(db, s):
    """PCIL-PF-03 — the same user's rows in W0 and W2 are not returned.
    Rules: get_by_performer R1 [BUG-645]."""
    entry(db, s, T4, workspace_id=s.W0.id, performed_by=s.U2.id)
    e1 = entry(db, s, T1, performed_by=s.U2.id)
    entry(db, s, T5, workspace_id=s.W2.id, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e1.id]


# [claude] PCIL-PF-04
@BUG_645
def test_pcil_pf_04__asked_for_w2_only_w2_row(db, s):
    """PCIL-PF-04 — asked for W2, only the W2 row is returned.
    Rules: get_by_performer R1 [BUG-645]."""
    entry(db, s, T4, workspace_id=s.W0.id, performed_by=s.U2.id)
    entry(db, s, T5, performed_by=s.U2.id)
    x2 = entry(db, s, T1, workspace_id=s.W2.id, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [x2.id]


# [claude] PCIL-PF-05
@BUG_645
def test_pcil_pf_05__tie_highest_id_first(db, s):
    """PCIL-PF-05 — on a tie the highest id comes first.
    Rules: get_by_performer R2 [BUG-645]."""
    b = entry(db, s, T2, performed_by=s.U2.id, notes="Abe")
    c = entry(db, s, T2, id=HIGH_ID, performed_by=s.U2.id, notes="Mid")
    a = entry(db, s, T2, performed_by=s.U2.id, notes="Zed")
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [c.id, a.id, b.id]


# [claude] PCIL-PF-06
@BUG_645
def test_pcil_pf_06__skip_1_limit_1_middle_row(db, s):
    """PCIL-PF-06 — skip 1 and limit 1 return the middle row; another user's newer row takes no place.
    Rules: get_by_performer R2 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    e2 = entry(db, s, T2, performed_by=s.U2.id)
    entry(db, s, T3, performed_by=s.U2.id)
    entry(db, s, T5, performed_by=s.U1.id)
    result = dao.get_by_performer(
        db, performed_by=s.U2.id, workspace_id=s.W1.id, skip=1, limit=1
    )
    # Then 1
    assert ids(result) == [e2.id]


# [claude] PCIL-PF-07
@BUG_645
def test_pcil_pf_07__default_limit_100_newest(db, s):
    """PCIL-PF-07 — with the default limit, 101 rows give the 100 newest.
    Rules: get_by_performer R2 [BUG-645]."""
    rows = minute_rows(db, s, 101, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert rows[0].id not in ids(result)


# [claude] PCIL-PF-08
@BUG_645
def test_pcil_pf_08__limit_1000_all_rows(db, s):
    """PCIL-PF-08 — limit 1000 returns all 101 rows.
    Rules: get_by_performer R2 [BUG-645]."""
    minute_rows(db, s, 101, performed_by=s.U2.id)
    result = dao.get_by_performer(
        db, performed_by=s.U2.id, workspace_id=s.W1.id, limit=1000
    )
    # Then 1
    assert len(result) == 101


# [claude] PCIL-PF-09
@BUG_645
def test_pcil_pf_09__unknown_profile_empty(db, s):
    """PCIL-PF-09 — an unknown profile id returns an empty list.
    Rules: get_by_performer R1, R4 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PCIL-PF-10
@BUG_645
def test_pcil_pf_10__limit_0_empty(db, s):
    """PCIL-PF-10 — limit 0 returns an empty list.
    Rules: get_by_performer R3 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    result = dao.get_by_performer(
        db, performed_by=s.U2.id, workspace_id=s.W1.id, limit=0
    )
    # Then 1
    assert result == []


# [claude] PCIL-PF-11
@BUG_645
def test_pcil_pf_11__negative_limit_rejected(db, s):
    """PCIL-PF-11 — a negative limit makes the database reject the query.
    Rules: get_by_performer R3 [BUG-645], Errors."""
    entry(db, s, T1, performed_by=s.U2.id)
    before = ledger_rows(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(
                db, performed_by=s.U2.id, workspace_id=s.W1.id, limit=-1
            )
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert ledger_rows(db) == before


# [claude] PCIL-PF-12
@BUG_645
def test_pcil_pf_12__negative_skip_rejected(db, s):
    """PCIL-PF-12 — a negative skip makes the database reject the query.
    Rules: get_by_performer R3 [BUG-645], Errors."""
    entry(db, s, T1, performed_by=s.U2.id)
    before = ledger_rows(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(
                db, performed_by=s.U2.id, workspace_id=s.W1.id, skip=-1
            )
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert ledger_rows(db) == before


# [claude] PCIL-PF-13
@BUG_645
def test_pcil_pf_13__skip_equal_to_rows_empty(db, s):
    """PCIL-PF-13 — a skip equal to the number of rows returns an empty list.
    Rules: get_by_performer R3 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    entry(db, s, T2, performed_by=s.U2.id)
    result = dao.get_by_performer(
        db, performed_by=s.U2.id, workspace_id=s.W1.id, skip=2
    )
    # Then 1
    assert result == []


# [claude] PCIL-PF-14
@BUG_645
def test_pcil_pf_14__performed_by_none_empty(db, s):
    """PCIL-PF-14 — performed_by None returns an empty list and raises nothing.
    Rules: get_by_performer R4 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=None, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PCIL-PF-15
@BUG_645
def test_pcil_pf_15__performed_by_0_empty(db, s):
    """PCIL-PF-15 — performed_by 0 returns an empty list and raises nothing.
    Rules: get_by_performer R4 [BUG-645]."""
    entry(db, s, T1, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=0, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] PCIL-PF-16
@BUG_645
def test_pcil_pf_16__deleted_project_and_inactive_item_listed(db, s):
    """PCIL-PF-16 — rows of a soft-deleted project's component and of an inactive item are listed.
    Rules: get_by_performer R5 [BUG-645]."""
    e1 = entry(db, s, T1, performed_by=s.U2.id, project_component_id=s.CD.id)
    e2 = entry(db, s, T2, performed_by=s.U2.id, item_id=s.IR.id)
    e3 = entry(db, s, T3, performed_by=s.U2.id)
    result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]


# [claude] PCIL-PF-17
@BUG_645
def test_pcil_pf_17__writes_nothing_no_lock(db, s):
    """PCIL-PF-17 — writes nothing and takes no lock: a pending row stays pending and unseen, an unflushed edit stays unflushed.
    Rules: get_by_performer R6 [BUG-645], Side effects."""
    e1 = entry(db, s, T1, performed_by=s.U2.id)
    b = entry(db, s, T2, performed_by=s.U2.id)
    b.notes = "Edited"
    p = ProjectComponentItemLedger(
        **{**ENTRY(s), "performed_by": s.U2.id}, performed_at=T4
    )
    db.add(p)
    before = ledger_rows(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_performer(db, performed_by=s.U2.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [b.id, e1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "FOR UPDATE" not in rec.sql
    # Then 9
    assert ledger_rows(db) == before


# --------------------------------------------------------------------------- #
# `calculate_balance`
# --------------------------------------------------------------------------- #


def balance(db, s, **kw):
    """calculate_balance with the card's arguments (C1, I1, W1 by default)."""
    args = {
        "project_component_id": s.C1.id,
        "item_id": s.I1.id,
        "workspace_id": s.W1.id,
        **kw,
    }
    return dao.calculate_balance(db, **args)


# [claude] PCIL-BAL-01
def test_pcil_bal_01__no_entry_zero(db, s):
    """PCIL-BAL-01 — with no entry the result is (0, Decimal 0.00).
    Rules: calculate_balance R1."""
    result = balance(db, s)
    # Then 1
    assert result == (0, Decimal("0.00"))
    # Then 2
    assert isinstance(result, tuple)
    # Then 3
    assert isinstance(result[1], Decimal)


# [claude] PCIL-BAL-02
def test_pcil_bal_02__latest_entry_not_summed(db, s):
    """PCIL-BAL-02 — the latest entry's quantity and value are returned; earlier entries are not summed.
    Rules: calculate_balance R2, R4."""
    entry(db, s, T1, qty_after=10, value_after=Decimal("50.00"))
    entry(db, s, T2, qty_after=7, value_after=Decimal("35.00"))
    result = balance(db, s)
    # Then 1
    assert result == (7, Decimal("35.00"))
    # Then 2
    assert isinstance(result[1], Decimal)


# [claude] PCIL-BAL-03
def test_pcil_bal_03__latest_wins_with_lowest_id(db, s):
    """PCIL-BAL-03 — the latest entry wins when it has the lowest id.
    Rules: calculate_balance R2."""
    entry(db, s, T3, qty_after=3, value_after=Decimal("6.00"))
    entry(db, s, T1, qty_after=8, value_after=Decimal("16.00"))
    entry(db, s, T2, qty_after=9, value_after=Decimal("18.00"))
    result = balance(db, s)
    # Then 1
    assert result == (3, Decimal("6.00"))


# [claude] PCIL-BAL-04
def test_pcil_bal_04__latest_wins_with_highest_id(db, s):
    """PCIL-BAL-04 — the latest entry wins when it has the highest id.
    Rules: calculate_balance R2."""
    entry(db, s, T1, qty_after=8, value_after=Decimal("16.00"))
    entry(db, s, T2, qty_after=9, value_after=Decimal("18.00"))
    entry(db, s, T3, qty_after=3, value_after=Decimal("6.00"))
    result = balance(db, s)
    # Then 1
    assert result == (3, Decimal("6.00"))


# [claude] PCIL-BAL-05
def test_pcil_bal_05__older_higher_id_does_not_win(db, s):
    """PCIL-BAL-05 — an older entry with a higher id inside the same day does not win.
    Rules: calculate_balance R2."""
    entry(db, s, T2, qty_after=3, value_after=Decimal("6.00"))
    entry(db, s, T1, id=HIGH_ID, qty_after=8, value_after=Decimal("16.00"))
    result = balance(db, s)
    # Then 1
    assert result == (3, Decimal("6.00"))


# [claude] PCIL-BAL-06
def test_pcil_bal_06__empty_value_after_gives_zero(db, s):
    """PCIL-BAL-06 — an empty value_after gives Decimal 0.00 and keeps qty_after.
    Rules: calculate_balance R2."""
    entry(db, s, T1, qty_after=4, value_after=None)
    result = balance(db, s)
    # Then 1
    assert result == (4, Decimal("0.00"))
    # Then 2
    assert isinstance(result[1], Decimal)


# [claude] PCIL-BAL-07
def test_pcil_bal_07__emptied_bucket(db, s):
    """PCIL-BAL-07 — an emptied bucket: qty_after 0 with an empty value_after gives (0, 0.00).
    Rules: calculate_balance R2."""
    entry(db, s, T1, qty_after=0, value_after=None)
    result = balance(db, s)
    # Then 1
    assert result == (0, Decimal("0.00"))
    # Then 2
    assert isinstance(result[1], Decimal)


# [claude] PCIL-BAL-08
def test_pcil_bal_08__stored_zero_value(db, s):
    """PCIL-BAL-08 — a stored value_after of 0.00 gives Decimal 0.00.
    Rules: calculate_balance R2."""
    entry(db, s, T1, qty_after=2, value_after=Decimal("0.00"))
    result = balance(db, s)
    # Then 1
    assert result == (2, Decimal("0.00"))
    # Then 2
    assert isinstance(result[1], Decimal)


# [claude] PCIL-BAL-09
def test_pcil_bal_09__empty_value_no_fallback(db, s):
    """PCIL-BAL-09 — an empty value on the latest entry does not fall back to an earlier entry.
    Rules: calculate_balance R2, R4."""
    entry(db, s, T1, qty_after=10, value_after=Decimal("50.00"))
    entry(db, s, T2, qty_after=6, value_after=None)
    result = balance(db, s)
    # Then 1
    assert result == (6, Decimal("0.00"))


# [claude] PCIL-BAL-10
def test_pcil_bal_10__negative_figures_as_stored(db, s):
    """PCIL-BAL-10 — negative stored figures are returned as they are.
    Rules: calculate_balance R2."""
    entry(db, s, T1, qty_after=-3, value_after=Decimal("-7.50"))
    result = balance(db, s)
    # Then 1
    assert result == (-3, Decimal("-7.50"))


# [claude] PCIL-BAL-11
def test_pcil_bal_11__value_2_125_reads_2_13(db, s):
    """PCIL-BAL-11 — a value_after stored as Decimal("2.125") reads back Decimal("2.13"): half up (half even gives 2.12).
    Rules: calculate_balance R2, HR-15 (database rounding)."""
    entry(db, s, T1, qty_after=1, value_after=Decimal("2.125"))
    db.expire_all()
    result = balance(db, s)
    # Then 1
    assert result == (1, Decimal("2.13"))


# [claude] PCIL-BAL-12
def test_pcil_bal_12__value_0_005_reads_0_01(db, s):
    """PCIL-BAL-12 — a value_after stored as Decimal("0.005") reads back Decimal("0.01"): half up (half even gives 0.00).
    Rules: calculate_balance R2, HR-15 (database rounding)."""
    entry(db, s, T1, qty_after=1, value_after=Decimal("0.005"))
    db.expire_all()
    result = balance(db, s)
    # Then 1
    assert result == (1, Decimal("0.01"))


# [claude] PCIL-BAL-13
def test_pcil_bal_13__value_minus_1_005_reads_minus_1_01(db, s):
    """PCIL-BAL-13 — a value_after stored as Decimal("-1.005") reads back Decimal("-1.01"): half up (half even gives -1.00).
    Rules: calculate_balance R2, HR-15 (database rounding)."""
    entry(db, s, T1, qty_after=1, value_after=Decimal("-1.005"))
    db.expire_all()
    result = balance(db, s)
    # Then 1
    assert result == (1, Decimal("-1.01"))


# [claude] PCIL-BAL-14
def test_pcil_bal_14__control_value_2_124_reads_2_12(db, s):
    """PCIL-BAL-14 — control: a value_after stored as Decimal("2.124") reads back 2.12.
    Rules: calculate_balance R2, HR-15 (database rounding)."""
    entry(db, s, T1, qty_after=1, value_after=Decimal("2.124"))
    db.expire_all()
    result = balance(db, s)
    # Then 1
    assert result == (1, Decimal("2.12"))


# [claude] PCIL-BAL-15
def test_pcil_bal_15__tied_entries_one_of_them(db, s):
    """PCIL-BAL-15 — tied entries: the figures of one of them, never of an older entry.
    Rules: calculate_balance R3 (holds today)."""
    entry(db, s, T1, qty_after=1, value_after=Decimal("1.00"))
    entry(db, s, T2, performed_by=s.U3.id, qty_after=15, value_after=Decimal("150.00"))
    entry(
        db,
        s,
        T2,
        id=HIGH_ID,
        performed_by=s.U1.id,
        qty_after=10,
        value_after=Decimal("100.00"),
    )
    entry(db, s, T2, performed_by=s.U2.id, qty_after=99, value_after=Decimal("990.00"))
    result = balance(db, s)
    # Then 1
    assert result in [
        (15, Decimal("150.00")),
        (10, Decimal("100.00")),
        (99, Decimal("990.00")),
    ]


# [claude] PCIL-BAL-16
@bug("BUG-2463", strict=False)
def test_pcil_bal_16__tie_greatest_id_decides(db, s):
    """PCIL-BAL-16 — among tied entries the greatest id decides, when the lowest id was updated.
    Rules: calculate_balance R3 [BUG-2463]."""
    b = entry(
        db, s, T2, performed_by=s.U3.id, qty_after=15, value_after=Decimal("150.00")
    )
    entry(
        db,
        s,
        T2,
        id=HIGH_ID,
        performed_by=s.U1.id,
        qty_after=10,
        value_after=Decimal("100.00"),
    )
    entry(db, s, T2, performed_by=s.U2.id, qty_after=99, value_after=Decimal("990.00"))
    db.execute(
        text("UPDATE project_component_item_ledger SET notes = 'x' WHERE id = :i"),
        {"i": b.id},
    )
    db.expire_all()
    result = balance(db, s)
    # Then 1
    assert result in [
        (15, Decimal("150.00")),
        (10, Decimal("100.00")),
        (99, Decimal("990.00")),
    ]
    # Then 2
    assert result == (10, Decimal("100.00"))


# [claude] PCIL-BAL-17
@bug("BUG-2463")
def test_pcil_bal_17__orders_by_performed_at_then_id_desc(db, s):
    """PCIL-BAL-17 — the query asks for performed_at newest first, then id highest first.
    Rules: calculate_balance R3 [BUG-2463]."""
    entry(db, s, T1, qty_after=5, value_after=Decimal("10.00"))
    with StatementRecorder(db) as rec:
        result = balance(db, s)
    # Then 1
    assert result == (5, Decimal("10.00"))
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "project_component_item_ledger.performed_at DESC" in rec.order_part
    # Then 4
    assert (
        "project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC"
        in rec.order_part
    )


# [claude] PCIL-BAL-18 ... PCIL-BAL-23
@pytest.mark.parametrize(
    "other",
    [
        pytest.param(lambda s: {"project_component_id": s.CL.id}, id="PCIL-BAL-18"),
        pytest.param(lambda s: {"project_component_id": s.C2.id}, id="PCIL-BAL-19"),
        pytest.param(lambda s: {"item_id": s.IL.id}, id="PCIL-BAL-20"),
        pytest.param(lambda s: {"item_id": s.I2.id}, id="PCIL-BAL-21"),
        pytest.param(lambda s: {"workspace_id": s.W0.id}, id="PCIL-BAL-22"),
        pytest.param(lambda s: {"workspace_id": s.W2.id}, id="PCIL-BAL-23"),
    ],
)
def test_pcil_bal_18_23__newer_entry_elsewhere_ignored(db, s, other):
    """PCIL-BAL-18 ... BAL-23 — a newer entry of a lower / higher component id, a lower / higher item id, W0 or W2 (same ids) does not change the result.
    Rules: calculate_balance R1, R2."""
    entry(db, s, T1, qty_after=5, value_after=Decimal("10.00"))
    entry(db, s, T5, **other(s), qty_after=9, value_after=Decimal("99.00"))
    result = balance(db, s)
    # Then 1
    assert result == (5, Decimal("10.00"))


# [claude] PCIL-BAL-24
def test_pcil_bal_24__only_w0_w2_entries_zero(db, s):
    """PCIL-BAL-24 — when only entries of W0 and W2 exist the result is (0, 0.00).
    Rules: calculate_balance R1."""
    entry(db, s, T1, workspace_id=s.W0.id, qty_after=9, value_after=Decimal("99.00"))
    entry(db, s, T2, workspace_id=s.W2.id, qty_after=8, value_after=Decimal("88.00"))
    result = balance(db, s)
    # Then 1
    assert result == (0, Decimal("0.00"))


# [claude] PCIL-BAL-25
def test_pcil_bal_25__asked_for_w2(db, s):
    """PCIL-BAL-25 — asked for W2, the W2 entry's figures are returned.
    Rules: calculate_balance R1, R2."""
    entry(db, s, T3, workspace_id=s.W0.id, qty_after=9, value_after=Decimal("99.00"))
    entry(db, s, T4, qty_after=5, value_after=Decimal("10.00"))
    entry(db, s, T1, workspace_id=s.W2.id, qty_after=8, value_after=Decimal("88.00"))
    result = balance(db, s, workspace_id=s.W2.id)
    # Then 1
    assert result == (8, Decimal("88.00"))


# [claude] PCIL-BAL-26
def test_pcil_bal_26__other_workspace_ids_under_w1_zero(db, s):
    """PCIL-BAL-26 — another workspace's component and item ids, asked under W1, give (0, 0.00).
    Rules: calculate_balance R1."""
    entry(
        db,
        s,
        T1,
        workspace_id=s.W2.id,
        project_component_id=s.C9.id,
        item_id=s.I9.id,
        qty_after=8,
        value_after=Decimal("88.00"),
    )
    result = balance(db, s, project_component_id=s.C9.id, item_id=s.I9.id)
    # Then 1
    assert result == (0, Decimal("0.00"))


# [claude] PCIL-BAL-27 ... PCIL-BAL-29
@pytest.mark.parametrize(
    "asked",
    [
        pytest.param({"project_component_id": MISSING}, id="PCIL-BAL-27"),
        pytest.param({"item_id": MISSING}, id="PCIL-BAL-28"),
        pytest.param({"project_component_id": 0}, id="PCIL-BAL-29"),
    ],
)
def test_pcil_bal_27_29__unknown_or_zero_id_zero(db, s, asked):
    """PCIL-BAL-27 ... BAL-29 — an unknown component id, an unknown item id, component id 0 give (0, 0.00).
    Rules: calculate_balance R1."""
    entry(db, s, T1, qty_after=5, value_after=Decimal("10.00"))
    result = balance(db, s, **asked)
    # Then 1
    assert result == (0, Decimal("0.00"))


# [claude] PCIL-BAL-30
def test_pcil_bal_30__deleted_project_component_balance(db, s):
    """PCIL-BAL-30 — the balance of a soft-deleted project's component is returned.
    Rules: calculate_balance R5 (P2)."""
    entry(
        db,
        s,
        T1,
        project_component_id=s.CD.id,
        qty_after=30,
        value_after=Decimal("75.00"),
    )
    result = balance(db, s, project_component_id=s.CD.id)
    # Then 1
    assert result == (30, Decimal("75.00"))


# [claude] PCIL-BAL-31
def test_pcil_bal_31__inactive_item_balance(db, s):
    """PCIL-BAL-31 — the balance of an inactive item is returned.
    Rules: calculate_balance R5 (P2)."""
    entry(db, s, T1, item_id=s.IR.id, qty_after=30, value_after=Decimal("75.00"))
    result = balance(db, s, item_id=s.IR.id)
    # Then 1
    assert result == (30, Decimal("75.00"))


# [claude] PCIL-BAL-32
def test_pcil_bal_32__writes_nothing_pending_not_seen(db, s):
    """PCIL-BAL-32 — writes nothing: a newer pending entry is not seen and stays pending, an unflushed edit stays unflushed.
    Rules: calculate_balance Side effects."""
    e1 = entry(db, s, T1, qty_after=5, value_after=Decimal("10.00"))
    e1.notes = "Edited"
    p = ProjectComponentItemLedger(**ENTRY(s), performed_at=T5)
    p.qty_after = 9
    db.add(p)
    with StatementRecorder(db) as rec:
        result = balance(db, s)
    # Then 1
    assert result == (5, Decimal("10.00"))
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "JOIN" not in rec.sql.upper()
    # Then 9
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# `get_latest_entry`
# --------------------------------------------------------------------------- #


def latest(db, s, **kw):
    """get_latest_entry with the card's arguments (C1, I1, W1 by default)."""
    args = {
        "project_component_id": s.C1.id,
        "item_id": s.I1.id,
        "workspace_id": s.W1.id,
        **kw,
    }
    return dao.get_latest_entry(db, **args)


# [claude] PCIL-LE-01
def test_pcil_le_01__no_entry_none(db, s):
    """PCIL-LE-01 — with no entry the result is None.
    Rules: get_latest_entry R1."""
    result = latest(db, s)
    # Then 1
    assert result is None


# [claude] PCIL-LE-02
def test_pcil_le_02__newest_with_middle_id(db, s):
    """PCIL-LE-02 — the newest entry is returned when it has the middle id.
    Rules: get_latest_entry R2."""
    entry(db, s, T2)
    e2 = entry(db, s, T3)
    entry(db, s, T1)
    result = latest(db, s)
    # Then 1
    assert isinstance(result, ProjectComponentItemLedger)
    # Then 2
    assert result.id == e2.id


# [claude] PCIL-LE-03
def test_pcil_le_03__newest_with_lowest_id(db, s):
    """PCIL-LE-03 — the newest entry is returned when it has the lowest id.
    Rules: get_latest_entry R2."""
    e1 = entry(db, s, T3)
    entry(db, s, T1)
    entry(db, s, T2)
    result = latest(db, s)
    # Then 1
    assert isinstance(result, ProjectComponentItemLedger)
    # Then 2
    assert result.id == e1.id


# [claude] PCIL-LE-04
def test_pcil_le_04__newest_with_highest_id(db, s):
    """PCIL-LE-04 — the newest entry is returned when it has the highest id.
    Rules: get_latest_entry R2."""
    entry(db, s, T1)
    entry(db, s, T2)
    e3 = entry(db, s, T3)
    result = latest(db, s)
    # Then 1
    assert isinstance(result, ProjectComponentItemLedger)
    # Then 2
    assert result.id == e3.id


# [claude] PCIL-LE-05
def test_pcil_le_05__older_higher_id_does_not_win(db, s):
    """PCIL-LE-05 — an older entry with a higher id inside the same day does not win.
    Rules: get_latest_entry R2."""
    e1 = entry(db, s, T2)
    entry(db, s, T1, id=HIGH_ID)
    result = latest(db, s)
    # Then 1
    assert result.id == e1.id


# [claude] PCIL-LE-06
def test_pcil_le_06__full_row_money_as_stored(db, s):
    """PCIL-LE-06 — the full row is returned with its money columns as stored.
    Rules: get_latest_entry R2."""
    entry(
        db,
        s,
        T1,
        unit_cost=Decimal("2.50"),
        total_cost=Decimal("7.50"),
        value_before=Decimal("10.00"),
        value_after=Decimal("17.50"),
        avg_price_before=Decimal("2.50"),
        avg_price_after=Decimal("2.50"),
        qty_after=7,
    )
    result = latest(db, s)
    # Then 1
    assert (result.unit_cost, result.total_cost) == (Decimal("2.50"), Decimal("7.50"))
    # Then 2
    assert (result.value_before, result.value_after) == (
        Decimal("10.00"),
        Decimal("17.50"),
    )
    # Then 3
    assert (result.avg_price_before, result.avg_price_after) == (
        Decimal("2.50"),
        Decimal("2.50"),
    )
    # Then 4
    assert result.qty_after == 7


# [claude] PCIL-LE-07
def test_pcil_le_07__empty_value_and_price_none(db, s):
    """PCIL-LE-07 — empty value and price columns come back as None.
    Rules: get_latest_entry R2."""
    entry(db, s, T1)
    result = latest(db, s)
    # Then 1
    assert result.value_before is None
    # Then 2
    assert result.value_after is None
    # Then 3
    assert result.avg_price_before is None
    # Then 4
    assert result.avg_price_after is None


# [claude] PCIL-LE-08
def test_pcil_le_08__tied_entries_one_of_them(db, s):
    """PCIL-LE-08 — tied entries: one of them is returned, never an older entry.
    Rules: get_latest_entry R2 (holds today)."""
    entry(db, s, T1)
    b = entry(db, s, T2, performed_by=s.U3.id, notes="Abe")
    c = entry(db, s, T2, id=HIGH_ID, performed_by=s.U1.id, notes="Mid")
    a = entry(db, s, T2, performed_by=s.U2.id, notes="Zed")
    result = latest(db, s)
    # Then 1
    assert result.id in [b.id, c.id, a.id]


# [claude] PCIL-LE-09
@bug("BUG-2463", strict=False)
def test_pcil_le_09__tie_greatest_id_returned(db, s):
    """PCIL-LE-09 — among tied entries the greatest id is returned, when the lowest id was updated.
    Rules: get_latest_entry R2 [BUG-2463]."""
    b = entry(db, s, T2, performed_by=s.U3.id, notes="Abe")
    c = entry(db, s, T2, id=HIGH_ID, performed_by=s.U1.id, notes="Mid")
    a = entry(db, s, T2, performed_by=s.U2.id, notes="Zed")
    db.execute(
        text(
            "UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"
        ),
        {"i": b.id},
    )
    db.expire_all()
    result = latest(db, s)
    # Then 1
    assert result.id in [b.id, c.id, a.id]
    # Then 2
    assert result.id == c.id


# [claude] PCIL-LE-10
@bug("BUG-2463")
def test_pcil_le_10__orders_by_performed_at_then_id_desc(db, s):
    """PCIL-LE-10 — the query asks for performed_at newest first, then id highest first.
    Rules: get_latest_entry R2 [BUG-2463]."""
    e1 = entry(db, s, T1)
    with StatementRecorder(db) as rec:
        result = latest(db, s)
    # Then 1
    assert result.id == e1.id
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "project_component_item_ledger.performed_at DESC" in rec.order_part
    # Then 4
    assert (
        "project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC"
        in rec.order_part
    )


# [claude] PCIL-LE-11
def test_pcil_le_11__same_entry_as_calculate_balance(db, s):
    """PCIL-LE-11 — it returns the entry whose figures calculate_balance reads.
    Rules: get_latest_entry R3; calculate_balance R2."""
    e1 = entry(db, s, T3, qty_after=4, value_after=Decimal("12.00"))
    entry(db, s, T1, id=HIGH_ID, qty_after=9, value_after=Decimal("27.00"))
    entry(db, s, T2, qty_after=6, value_after=Decimal("18.00"))
    latest_row, bal = latest(db, s), balance(db, s)
    # Then 1
    assert latest_row.id == e1.id
    # Then 2
    assert bal == (latest_row.qty_after, latest_row.value_after)
    # Then 3
    assert bal == (4, Decimal("12.00"))


# [claude] PCIL-LE-12 ... PCIL-LE-17
@pytest.mark.parametrize(
    "other",
    [
        pytest.param(lambda s: {"project_component_id": s.CL.id}, id="PCIL-LE-12"),
        pytest.param(lambda s: {"project_component_id": s.C2.id}, id="PCIL-LE-13"),
        pytest.param(lambda s: {"item_id": s.IL.id}, id="PCIL-LE-14"),
        pytest.param(lambda s: {"item_id": s.I2.id}, id="PCIL-LE-15"),
        pytest.param(lambda s: {"workspace_id": s.W0.id}, id="PCIL-LE-16"),
        pytest.param(lambda s: {"workspace_id": s.W2.id}, id="PCIL-LE-17"),
    ],
)
def test_pcil_le_12_17__newer_entry_elsewhere_ignored(db, s, other):
    """PCIL-LE-12 ... LE-17 — a newer entry of a lower / higher component id, a lower / higher item id, W0 or W2 (same ids) is not considered.
    Rules: get_latest_entry R1, R2."""
    e1 = entry(db, s, T1)
    entry(db, s, T5, **other(s))
    result = latest(db, s)
    # Then 1
    assert result.id == e1.id


# [claude] PCIL-LE-18
def test_pcil_le_18__only_w0_w2_entries_none(db, s):
    """PCIL-LE-18 — when only entries of W0 and W2 exist the result is None.
    Rules: get_latest_entry R1."""
    entry(db, s, T1, workspace_id=s.W0.id)
    entry(db, s, T2, workspace_id=s.W2.id)
    result = latest(db, s)
    # Then 1
    assert result is None


# [claude] PCIL-LE-19
def test_pcil_le_19__asked_for_w0(db, s):
    """PCIL-LE-19 — asked for W0, the W0 entry is returned.
    Rules: get_latest_entry R1."""
    x0 = entry(db, s, T1, workspace_id=s.W0.id)
    entry(db, s, T4)
    entry(db, s, T5, workspace_id=s.W2.id)
    result = latest(db, s, workspace_id=s.W0.id)
    # Then 1
    assert result.id == x0.id


# [claude] PCIL-LE-20
def test_pcil_le_20__other_workspace_ids_under_w1_none(db, s):
    """PCIL-LE-20 — another workspace's component and item ids, asked under W1, give None.
    Rules: get_latest_entry R1."""
    entry(
        db,
        s,
        T1,
        workspace_id=s.W2.id,
        project_component_id=s.C9.id,
        item_id=s.I9.id,
    )
    result = latest(db, s, project_component_id=s.C9.id, item_id=s.I9.id)
    # Then 1
    assert result is None


# [claude] PCIL-LE-21 ... PCIL-LE-23
@pytest.mark.parametrize(
    "asked",
    [
        pytest.param({"project_component_id": MISSING}, id="PCIL-LE-21"),
        pytest.param({"item_id": MISSING}, id="PCIL-LE-22"),
        pytest.param({"item_id": 0}, id="PCIL-LE-23"),
    ],
)
def test_pcil_le_21_23__unknown_or_zero_id_none(db, s, asked):
    """PCIL-LE-21 ... LE-23 — an unknown component id, an unknown item id, item id 0 give None.
    Rules: get_latest_entry R1."""
    entry(db, s, T1)
    result = latest(db, s, **asked)
    # Then 1
    assert result is None


# [claude] PCIL-LE-24
def test_pcil_le_24__deleted_project_component_latest(db, s):
    """PCIL-LE-24 — the latest entry of a soft-deleted project's component is returned.
    Rules: get_latest_entry R4 (P2)."""
    e1 = entry(db, s, T1, project_component_id=s.CD.id)
    result = latest(db, s, project_component_id=s.CD.id)
    # Then 1
    assert result.id == e1.id


# [claude] PCIL-LE-25
def test_pcil_le_25__inactive_item_latest(db, s):
    """PCIL-LE-25 — the latest entry of an inactive item is returned.
    Rules: get_latest_entry R4 (P2)."""
    e1 = entry(db, s, T1, item_id=s.IR.id)
    result = latest(db, s, item_id=s.IR.id)
    # Then 1
    assert result.id == e1.id


# [claude] PCIL-LE-26
def test_pcil_le_26__writes_nothing_pending_not_seen(db, s):
    """PCIL-LE-26 — writes nothing: a newer pending entry is not seen and stays pending, an unflushed edit stays unflushed.
    Rules: get_latest_entry Side effects."""
    e1 = entry(db, s, T1)
    e1.notes = "Edited"
    p = ProjectComponentItemLedger(**ENTRY(s), performed_at=T5)
    db.add(p)
    with StatementRecorder(db) as rec:
        result = latest(db, s)
    # Then 1
    assert result.id == e1.id
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "JOIN" not in rec.sql.upper()
    # Then 9
    assert "FOR UPDATE" not in rec.sql


# --------------------------------------------------------------------------- #
# `calculate_total_cost_for_component`
# --------------------------------------------------------------------------- #


def total(db, s, **kw):
    """calculate_total_cost_for_component with the card's arguments (C1, W1 by default)."""
    args = {"project_component_id": s.C1.id, "workspace_id": s.W1.id, **kw}
    return dao.calculate_total_cost_for_component(db, **args)


def costs(db, s, *rows):
    """Given rows (performed_at, transaction_type, total_cost), in order."""
    for at, kind, amount in rows:
        entry(db, s, at, transaction_type=kind, total_cost=Decimal(amount))


# [claude] PCIL-TC-01
def test_pcil_tc_01__no_rows_zero(db, s):
    """PCIL-TC-01 — with no rows the result is Decimal 0.00.
    Rules: calculate_total_cost_for_component R2."""
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")


# [claude] PCIL-TC-02
def test_pcil_tc_02__added_types_summed_exactly(db, s):
    """PCIL-TC-02 — rows of added types are summed exactly, whatever their item.
    Rules: calculate_total_cost_for_component R1 (added types; holds today), R3."""
    entry(db, s, T1, transaction_type="transfer_in", total_cost=Decimal("50.00"))
    entry(
        db,
        s,
        T2,
        transaction_type="purchase_order",
        item_id=s.I2.id,
        total_cost=Decimal("15.00"),
    )
    entry(db, s, T3, transaction_type="consumption", total_cost=Decimal("0.13"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("65.13")


# [claude] PCIL-TC-03
def test_pcil_tc_03__every_added_type_counts(db, s):
    """PCIL-TC-03 — every added type counts: purchase_order, manual_add, transfer_in, consumption, inventory_adjustment, cost_adjustment.
    Rules: calculate_total_cost_for_component R1 (added types; holds today)."""
    costs(
        db,
        s,
        (T1, "purchase_order", "1.00"),
        (T1, "manual_add", "2.00"),
        (T1, "transfer_in", "4.00"),
        (T1, "consumption", "8.00"),
        (T1, "inventory_adjustment", "16.00"),
        (T1, "cost_adjustment", "32.00"),
    )
    result = total(db, s)
    # Then 1
    assert result == Decimal("63.00")


# [claude] PCIL-TC-04
def test_pcil_tc_04__sum_of_zero(db, s):
    """PCIL-TC-04 — a sum of exactly zero gives Decimal 0.00.
    Rules: calculate_total_cost_for_component R2."""
    costs(db, s, (T1, "transfer_in", "1.00"), (T2, "transfer_in", "-1.00"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")


# [claude] PCIL-TC-05
def test_pcil_tc_05__negative_cost_added_as_is(db, s):
    """PCIL-TC-05 — a negative stored cost is added as it is.
    Rules: calculate_total_cost_for_component R3."""
    costs(db, s, (T1, "transfer_in", "5.00"), (T2, "transfer_in", "-7.25"))
    result = total(db, s)
    # Then 1
    assert result == Decimal("-2.25")


# [claude] PCIL-TC-06
def test_pcil_tc_06__stored_half_up_then_added(db, s):
    """PCIL-TC-06 — costs stored as 2.125, 0.005 and 2.124 sum to 4.26: each is rounded half up when stored, then added exactly.
    Rules: calculate_total_cost_for_component R3, HR-15 (database rounding)."""
    costs(
        db,
        s,
        (T1, "transfer_in", "2.125"),
        (T2, "transfer_in", "0.005"),
        (T3, "transfer_in", "2.124"),
    )
    result = total(db, s)
    # Then 1
    assert result == Decimal("4.26")  # half even 4.24; unrounded 4.25


# [claude] PCIL-TC-07
def test_pcil_tc_07__minus_1_005_counts_as_minus_1_01(db, s):
    """PCIL-TC-07 — a cost stored as -1.005 counts as -1.01, half up away from zero.
    Rules: calculate_total_cost_for_component R3, HR-15 (database rounding)."""
    costs(db, s, (T1, "transfer_in", "5.00"), (T2, "transfer_in", "-1.005"))
    result = total(db, s)
    # Then 1
    assert result == Decimal("3.99")  # half even would give 4.00


# [claude] PCIL-TC-08
def test_pcil_tc_08__large_sum_keeps_two_places(db, s):
    """PCIL-TC-08 — a large sum with cents keeps two places exactly.
    Rules: calculate_total_cost_for_component R3."""
    costs(
        db,
        s,
        (T1, "transfer_in", "0.10"),
        (T1, "transfer_in", "0.20"),
        (T1, "transfer_in", "0.70"),
        (T1, "transfer_in", "9999999999999.99"),
    )
    result = total(db, s)
    # Then 1
    assert result == Decimal("10000000000000.99")
    # Then 2
    assert str(result) == "10000000000000.99"


# [claude] PCIL-TC-09
@bug("BUG-654")
def test_pcil_tc_09__transfer_out_subtracted(db, s):
    """PCIL-TC-09 — transfer_out is subtracted: 50.00 in, 15.00 out, 0.13 consumed give 35.13.
    Rules: calculate_total_cost_for_component R1 [BUG-654]."""
    costs(
        db,
        s,
        (T1, "transfer_in", "50.00"),
        (T2, "transfer_out", "15.00"),
        (T3, "consumption", "0.13"),
    )
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("35.13")


# [claude] PCIL-TC-10
@bug("BUG-654")
def test_pcil_tc_10__damaged_subtracted(db, s):
    """PCIL-TC-10 — damaged is subtracted: 50.00 in, 7.50 damaged give 42.50.
    Rules: calculate_total_cost_for_component R1 [BUG-654]."""
    costs(db, s, (T1, "transfer_in", "50.00"), (T2, "damaged", "7.50"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("42.50")


# [claude] PCIL-TC-11
@bug("BUG-654")
def test_pcil_tc_11__net_of_zero(db, s):
    """PCIL-TC-11 — a net of exactly zero gives Decimal 0.00: 15.00 in, 15.00 out.
    Rules: calculate_total_cost_for_component R1 [BUG-654], R2."""
    costs(db, s, (T1, "transfer_in", "15.00"), (T2, "transfer_out", "15.00"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")


# [claude] PCIL-TC-12
@bug("BUG-654")
def test_pcil_tc_12__only_outgoing_negative(db, s):
    """PCIL-TC-12 — only outgoing rows give a negative net.
    Rules: calculate_total_cost_for_component R1 [BUG-654]."""
    costs(db, s, (T1, "transfer_out", "15.00"), (T2, "damaged", "2.50"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("-17.50")


# [claude] PCIL-TC-13
@bug("BUG-654")
def test_pcil_tc_13__subtracted_2_125_counts_as_2_13(db, s):
    """PCIL-TC-13 — a subtracted cost stored as 2.125 counts as 2.13: 10.00 in, 2.125 out give 7.87.
    Rules: calculate_total_cost_for_component R1 [BUG-654], HR-15 (database rounding)."""
    costs(db, s, (T1, "transfer_in", "10.00"), (T2, "transfer_out", "2.125"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("7.87")  # half even would give 7.88


# [claude] PCIL-TC-14
@bug("BUG-654")
def test_pcil_tc_14__transfer_in_added_next_to_transfer_out(db, s):
    """PCIL-TC-14 — the look-alike transfer_in is added next to a subtracted transfer_out.
    Rules: calculate_total_cost_for_component R1 [BUG-654]."""
    costs(
        db,
        s,
        (T1, "transfer_in", "20.00"),
        (T2, "transfer_out", "5.00"),
        (T3, "transfer_in", "1.00"),
    )
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("16.00")


# [claude] PCIL-TC-15 ... PCIL-TC-18
@pytest.mark.parametrize(
    "other",
    [
        pytest.param(lambda s: {"project_component_id": s.CL.id}, id="PCIL-TC-15"),
        pytest.param(lambda s: {"project_component_id": s.C2.id}, id="PCIL-TC-16"),
        pytest.param(lambda s: {"workspace_id": s.W0.id}, id="PCIL-TC-17"),
        pytest.param(lambda s: {"workspace_id": s.W2.id}, id="PCIL-TC-18"),
    ],
)
def test_pcil_tc_15_18__row_elsewhere_does_not_count(db, s, other):
    """PCIL-TC-15 ... TC-18 — a row of a lower / higher component id, or of W0 / W2 with the same component id, does not count.
    Rules: calculate_total_cost_for_component R1a."""
    entry(db, s, T1, transaction_type="transfer_in", total_cost=Decimal("5.00"))
    entry(db, s, T2, **other(s), total_cost=Decimal("100.00"))
    result = total(db, s)
    # Then 1
    assert result == Decimal("5.00")


# [claude] PCIL-TC-19
def test_pcil_tc_19__asked_for_w2(db, s):
    """PCIL-TC-19 — asked for W2, only the W2 row counts.
    Rules: calculate_total_cost_for_component R1a."""
    entry(db, s, T1, workspace_id=s.W0.id, total_cost=Decimal("1.00"))
    entry(db, s, T1, transaction_type="transfer_in", total_cost=Decimal("5.00"))
    entry(db, s, T1, workspace_id=s.W2.id, total_cost=Decimal("3.00"))
    result = total(db, s, workspace_id=s.W2.id)
    # Then 1
    assert result == Decimal("3.00")


# [claude] PCIL-TC-20
def test_pcil_tc_20__other_workspace_component_under_w1_zero(db, s):
    """PCIL-TC-20 — another workspace's component id, asked under W1, gives Decimal 0.00.
    Rules: calculate_total_cost_for_component R1a."""
    entry(
        db,
        s,
        T1,
        workspace_id=s.W2.id,
        project_component_id=s.C9.id,
        item_id=s.I9.id,
        total_cost=Decimal("3.00"),
    )
    result = total(db, s, project_component_id=s.C9.id)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")


# [claude] PCIL-TC-21
def test_pcil_tc_21__unknown_component_zero(db, s):
    """PCIL-TC-21 — an unknown component id gives Decimal 0.00.
    Rules: calculate_total_cost_for_component R1a, R2."""
    entry(db, s, T1, transaction_type="transfer_in", total_cost=Decimal("5.00"))
    result = total(db, s, project_component_id=MISSING)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("0.00")


# [claude] PCIL-TC-22
def test_pcil_tc_22__deleted_project_and_inactive_item_count(db, s):
    """PCIL-TC-22 — rows of a soft-deleted project's component and of an inactive item count.
    Rules: calculate_total_cost_for_component R1a."""
    entry(db, s, T1, project_component_id=s.CD.id, total_cost=Decimal("4.00"))
    entry(
        db,
        s,
        T2,
        project_component_id=s.CD.id,
        item_id=s.IR.id,
        total_cost=Decimal("6.00"),
    )
    result = total(db, s, project_component_id=s.CD.id)
    # Then 1
    assert result == Decimal("10.00")


# [claude] PCIL-TC-23
def test_pcil_tc_23__writes_nothing_pending_not_counted(db, s):
    """PCIL-TC-23 — writes nothing: a pending row does not count and stays pending, an unflushed edit stays unflushed.
    Rules: calculate_total_cost_for_component Side effects."""
    e1 = entry(db, s, T1, transaction_type="transfer_in", total_cost=Decimal("5.00"))
    e1.total_cost = Decimal("9.00")
    p = ProjectComponentItemLedger(**ENTRY(s), performed_at=T2)
    p.total_cost = Decimal("100.00")
    db.add(p)
    with StatementRecorder(db) as rec:
        result = total(db, s)
    # Then 1
    assert result == Decimal("5.00")
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert e1 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert "JOIN" not in rec.sql.upper()


# [claude] PCIL-TC-24
def test_pcil_tc_24__stored_transfer_out_capitalised_added(db, s):
    """PCIL-TC-24 — a stored "Transfer_Out" is not the outgoing type: it is added.
    Rules: calculate_total_cost_for_component R1b (holds today and after the fix), R1."""
    costs(db, s, (T1, "transfer_in", "50.00"), (T2, "Transfer_Out", "15.00"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("65.00")


# [claude] PCIL-TC-25
def test_pcil_tc_25__stored_damaged_capitals_added(db, s):
    """PCIL-TC-25 — a stored "DAMAGED" is not the outgoing type: it is added.
    Rules: calculate_total_cost_for_component R1b (holds today and after the fix), R1."""
    costs(db, s, (T1, "transfer_in", "50.00"), (T2, "DAMAGED", "7.50"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("57.50")


# [claude] PCIL-TC-26
def test_pcil_tc_26__stored_leading_space_transfer_out_added(db, s):
    """PCIL-TC-26 — a stored " transfer_out" with a leading space is added.
    Rules: calculate_total_cost_for_component R1b (holds today and after the fix), R1."""
    costs(db, s, (T1, "transfer_in", "20.00"), (T2, " transfer_out", "5.00"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("25.00")


# [claude] PCIL-TC-27
def test_pcil_tc_27__stored_trailing_space_damaged_added(db, s):
    """PCIL-TC-27 — a stored "damaged " with a trailing space is added.
    Rules: calculate_total_cost_for_component R1b (holds today and after the fix), R1."""
    costs(db, s, (T1, "transfer_in", "20.00"), (T2, "damaged ", "2.50"))
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("22.50")


# [claude] PCIL-TC-28
@bug("BUG-654")
def test_pcil_tc_28__transfer_out_subtracted_look_alike_added(db, s):
    """PCIL-TC-28 — transfer_out is subtracted while "Transfer_Out" next to it is added: 50.00 in, 15.00 out, 7.00 look-alike give 42.00.
    Rules: calculate_total_cost_for_component R1b, R1 [BUG-654]."""
    costs(
        db,
        s,
        (T1, "transfer_in", "50.00"),
        (T2, "transfer_out", "15.00"),
        (T3, "Transfer_Out", "7.00"),
    )
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("42.00")


# [claude] PCIL-TC-29
@bug("BUG-654")
def test_pcil_tc_29__damaged_subtracted_look_alike_added(db, s):
    """PCIL-TC-29 — damaged is subtracted while "DAMAGED" next to it is added: 50.00 in, 7.50 damaged, 2.50 look-alike give 45.00.
    Rules: calculate_total_cost_for_component R1b, R1 [BUG-654]."""
    costs(
        db,
        s,
        (T1, "transfer_in", "50.00"),
        (T2, "damaged", "7.50"),
        (T3, "DAMAGED", "2.50"),
    )
    result = total(db, s)
    # Then 1
    assert isinstance(result, Decimal)
    # Then 2
    assert result == Decimal("45.00")


# --------------------------------------------------------------------------- #
# Inherited `BaseDAO` methods
# --------------------------------------------------------------------------- #


# [claude] PCIL-INH-01
def test_pcil_inh_01__get_by_workspace_own_rows_only(db, s):
    """PCIL-INH-01 — get_by_workspace returns the workspace's rows only, with W0 and W2 rows present.
    Rules: inherited R1, R2."""
    entry(db, s, T1, workspace_id=s.W0.id)
    e1 = entry(db, s, T1)
    e2 = entry(db, s, T2, project_component_id=s.C2.id)
    entry(db, s, T1, workspace_id=s.W2.id)
    result = dao.get_by_workspace(db, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {e1.id, e2.id}


# [claude] PCIL-INH-02
@bug("BUG-100", strict=False, revisit=False)
def test_pcil_inh_02__get_by_workspace_id_ascending_after_update(db, s):
    """PCIL-INH-02 — get_by_workspace returns rows by id ascending, when the lowest id was updated.
    Rules: inherited R2 [BUG-100]."""
    a = entry(db, s, T3)
    b = entry(db, s, T1, id=HIGH_ID)
    c = entry(db, s, T2)
    db.execute(
        text("UPDATE project_component_item_ledger SET notes = 'x' WHERE id = :i"),
        {"i": a.id},
    )
    db.expire_all()
    result = dao.get_by_workspace(db, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {a.id, b.id, c.id}
    # Then 2
    assert ids(result) == [a.id, c.id, b.id]


# [claude] PCIL-INH-03
@bug("BUG-100", revisit=False)
def test_pcil_inh_03__get_by_workspace_orders_by_id(db, s):
    """PCIL-INH-03 — get_by_workspace orders by id ascending.
    Rules: inherited R2 [BUG-100]."""
    e1 = entry(db, s, T1)
    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "project_component_item_ledger.id" in rec.order_part
