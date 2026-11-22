"""Unit tests for app/dao/miscellaneous_project_cost.py.

Implements tests/unit/dao/miscellaneous_project_cost.cases.md (Revision 2), one
test per case, in card order. Real Postgres session (`db` fixture). Nothing is
mocked and no clock is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117, DTZ001, FURB157, RUF015  (Conventions prescribe `with pytest.raises(...)`
# around `with db.begin_nested()`, naive T0 / T1, the Decimal strings and the
# `[r for r in result if ...][0]` lookups as carded)
import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.miscellaneous_project_cost import miscellaneous_project_cost_dao
from app.models.factory import Factory
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.models.project import Project
from app.models.project_component import ProjectComponent
from app.schemas.miscellaneous_project_cost import (
    MiscellaneousProjectCostCreate,
    MiscellaneousProjectCostUpdate,
)
from app.utils.time import utcnow
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton miscellaneous_project_cost_dao"
dao = miscellaneous_project_cost_dao

# Convention "MISSING", "TAG", "T0", "T1" (naive)
MISSING = 999999999
TAG = uuid.uuid4().hex[:8]
T0 = datetime(2026, 3, 1, 9, 0, 0)
T1 = datetime(2026, 3, 2, 9, 0, 0)

REVISIT = "revisit after launch"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, this order, each flushed)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def s(db):
    """Standing rows W0..W2, U1..U3, F0..F2, the projects and the components."""
    r = SimpleNamespace()
    r.W0, r.W1, r.W2 = make_workspace(db), make_workspace(db), make_workspace(db)
    r.U1, r.U2, r.U3 = make_profile(db), make_profile(db), make_profile(db)
    r.F0 = _add(
        db, Factory(workspace_id=r.W0.id, name="Factory Zero", abbreviation="F0")
    )
    r.F1 = _add(
        db, Factory(workspace_id=r.W1.id, name="Factory One", abbreviation="F1")
    )
    r.F2 = _add(
        db, Factory(workspace_id=r.W2.id, name="Factory Two", abbreviation="F2")
    )

    def project(ws, factory, name, **extra):
        return _add(
            db,
            Project(
                workspace_id=ws.id,
                factory_id=factory.id,
                name=name,
                description="Main",
                **extra,
            ),
        )

    r.PJ0 = project(r.W0, r.F0, "Project Zero")
    r.PJA = project(r.W1, r.F1, "Project A")
    r.PJ1 = project(r.W1, r.F1, "Bridge A")
    r.PJB = project(r.W1, r.F1, "Project B")
    r.PJD = project(
        r.W1, r.F1, "Old Bridge", is_deleted=True, deleted_at=T0, deleted_by=r.U1.id
    )
    r.PJX = project(r.W2, r.F2, "Project X")

    def component(ws, proj, name):
        return _add(
            db, ProjectComponent(workspace_id=ws.id, project_id=proj.id, name=name)
        )

    r.C0 = component(r.W0, r.PJ0, "Zero part")
    r.CA = component(r.W1, r.PJA, "Arch")
    r.C1 = component(r.W1, r.PJ1, "Deck")
    r.C2 = component(r.W1, r.PJ1, "Rail")
    r.CB = component(r.W1, r.PJB, "Pier")
    r.CDL = component(r.W1, r.PJD, "Floor")
    r.CX = component(r.W2, r.PJX, "Deck")
    return r


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


def cost(db, s, **but):
    """Convention "cost": W1, PJ1, "Crane", 100.00, created at T1; `but` overrides."""
    fields = {
        "workspace_id": s.W1.id,
        "project_id": s.PJ1.id,
        "project_component_id": None,
        "name": "Crane",
        "description": None,
        "amount": Decimal("100.00"),
        "created_at": T1,
    }
    fields.update(but)
    return _add(db, MiscellaneousProjectCost(**fields))


def component_only(db, s, comp, **but):
    """Convention "component-only on C": cost, but project_id None, component C."""
    return cost(db, s, **{"project_id": None, "project_component_id": comp.id, **but})


def unlinked(db, s, **but):
    """Convention "unlinked": cost, but project_id None."""
    return cost(db, s, **{"project_id": None, **but})


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "Dhaka"
def dhaka(db):
    db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))


# Convention "dump(S)": the service's create path (spec R2b)
def dump(schema, s):
    return {**schema.model_dump(), "workspace_id": s.W1.id}


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def ids(result):
    return [r.id for r in result]


def idset(result):
    return {r.id for r in result}


def reread(db, cost_id):
    """Convention "re-read X": expire, then SELECT by id."""
    db.expire_all()
    return db.get(MiscellaneousProjectCost, cost_id)


def cost_count(db, *where):
    stmt = select(func.count()).select_from(MiscellaneousProjectCost)
    for clause in where:
        stmt = stmt.where(clause)
    return db.scalar(stmt)


# Convention "nothing written": rows of miscellaneous_project_costs, all workspaces
def total_costs(db):
    return cost_count(db)


class StatementRecorder:
    """Convention "Statement recorder": SQL sent by the session during the block."""

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
        """The one SELECT from miscellaneous_project_costs."""
        (only,) = [
            st
            for st in self.statements
            if st.lstrip().upper().startswith("SELECT")
            and "FROM miscellaneous_project_costs" in st
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


def xfail_bug(bug, strict=True, revisit=True):
    reason = f"{bug} ({REVISIT})" if revisit else bug
    return pytest.mark.xfail(strict=strict, reason=reason)


# --------------------------------------------------------------------------- #
# `DAOMiscellaneousProjectCost.get_by_project`
# --------------------------------------------------------------------------- #


# [claude] MPC-GP-01
def test_mpc_gp_01__returns_project_costs_with_values(db, s):
    """MPC-GP-01 — returns the project's costs with their stored values.
    Rules: get_by_project R1, Returns."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire", description="Two days", amount=Decimal("1200.50"))
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id}
    # Then 3
    assert len(result) == 2
    # Then 4
    assert [r for r in result if r.id == b.id][0].amount == Decimal("1200.50")
    # Then 5
    assert [r for r in result if r.id == b.id][0].description == "Two days"


# [claude] MPC-GP-02
def test_mpc_gp_02__other_projects_not_returned(db, s):
    """MPC-GP-02 — costs of a lower-id and a higher-id project are not returned.
    Rules: get_by_project R2."""
    cost(db, s, project_id=s.PJA.id)
    a = cost(db, s)
    cost(db, s, project_id=s.PJB.id)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]


# [claude] MPC-GP-03
def test_mpc_gp_03__w1_asking_for_w2_project_gets_nothing(db, s):
    """MPC-GP-03 — W1 asking for W2's project gets nothing, though W2 has costs on it.
    Rules: get_by_project R1."""
    cost(db, s)
    cost(db, s, workspace_id=s.W2.id, project_id=s.PJX.id)
    cost(db, s, workspace_id=s.W2.id, project_id=None, project_component_id=s.CX.id)
    result = dao.get_by_project(db, project_id=s.PJX.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GP-04
def test_mpc_gp_04__w1_asking_for_w0_project_gets_nothing(db, s):
    """MPC-GP-04 — W1 asking for W0's project gets nothing, though W0 has costs on it.
    Rules: get_by_project R1."""
    cost(db, s, workspace_id=s.W0.id, project_id=s.PJ0.id)
    cost(db, s, workspace_id=s.W0.id, project_id=None, project_component_id=s.C0.id)
    cost(db, s)
    result = dao.get_by_project(db, project_id=s.PJ0.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GP-05
def test_mpc_gp_05__w2_gets_its_own_project_cost(db, s):
    """MPC-GP-05 — W2 gets its own project's cost, not W0's or W1's.
    Rules: get_by_project R1."""
    cost(db, s, workspace_id=s.W0.id, project_id=s.PJ0.id)
    cost(db, s)
    x2 = cost(db, s, workspace_id=s.W2.id, project_id=s.PJX.id)
    result = dao.get_by_project(db, project_id=s.PJX.id, workspace_id=s.W2.id)
    # Then 1
    assert ids(result) == [x2.id]


# [claude] MPC-GP-06
def test_mpc_gp_06__unknown_project_id_empty(db, s):
    """MPC-GP-06 — an unknown project id returns an empty list.
    Rules: get_by_project R1."""
    cost(db, s)
    result = dao.get_by_project(db, project_id=MISSING, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GP-07
def test_mpc_gp_07__project_id_zero_empty(db, s):
    """MPC-GP-07 — project_id 0 returns an empty list and raises nothing.
    Rules: get_by_project R3."""
    cost(db, s)
    unlinked(db, s)
    result = dao.get_by_project(db, project_id=0, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GP-08
def test_mpc_gp_08__project_without_costs_empty(db, s):
    """MPC-GP-08 — a project without costs returns an empty list.
    Rules: get_by_project R1."""
    cost(db, s)
    result = dao.get_by_project(db, project_id=s.PJB.id, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GP-09
def test_mpc_gp_09__unlinked_and_other_component_not_returned(db, s):
    """MPC-GP-09 — an unlinked cost and a cost on another project's component are not returned.
    Rules: get_by_project R2."""
    unlinked(db, s)
    a = cost(db, s)
    component_only(db, s, s.CB)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]


# [claude] MPC-GP-10
def test_mpc_gp_10__cost_with_project_and_component_once(db, s):
    """MPC-GP-10 — a cost with both the project and its component is returned once.
    Rules: get_by_project R1a (the "once" part, holds today)."""
    a = cost(db, s)
    b = cost(db, s, project_component_id=s.C1.id)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert sorted(ids(result)) == sorted([a.id, b.id])


# [claude] MPC-GP-11
def test_mpc_gp_11__project_id_none_returns_costs_without_project(db, s):
    """MPC-GP-11 — project_id None returns this workspace's costs with no project.
    Rules: get_by_project R3."""
    unlinked(db, s, workspace_id=s.W0.id)
    k = component_only(db, s, s.C1)
    n = unlinked(db, s)
    cost(db, s)
    unlinked(db, s, workspace_id=s.W2.id)
    result = dao.get_by_project(db, project_id=None, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {k.id, n.id}
    # Then 2
    assert len(result) == 2


# [claude] MPC-GP-12
def test_mpc_gp_12__deleted_project_costs_returned(db, s):
    """MPC-GP-12 — a soft-deleted project's costs are still returned.
    Rules: get_by_project R5."""
    d = cost(db, s, project_id=s.PJD.id)
    result = dao.get_by_project(db, project_id=s.PJD.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [d.id]


# [claude] MPC-GP-13
def test_mpc_gp_13__query_does_not_read_projects(db, s):
    """MPC-GP-13 — the query does not read the projects table.
    Rules: get_by_project R5."""
    a = cost(db, s)
    with StatementRecorder(db) as rec:
        result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "projects." not in rec.sql
    # Then 3
    assert "FOR UPDATE" not in rec.sql


# [claude] MPC-GP-14
def test_mpc_gp_14__limit_zero_empty(db, s):
    """MPC-GP-14 — limit=0 returns an empty list.
    Rules: get_by_project R6."""
    cost(db, s)
    cost(db, s, name="Lift hire")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=0)
    # Then 1
    assert result == []


# [claude] MPC-GP-15
def test_mpc_gp_15__limit_one_of_three(db, s):
    """MPC-GP-15 — limit=1 of three costs returns one of them.
    Rules: get_by_project R6."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    c = cost(db, s, name="Scaffold")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=1)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id, c.id}


# [claude] MPC-GP-16
def test_mpc_gp_16__skip_two_of_three(db, s):
    """MPC-GP-16 — skip=2 of three costs returns one of them.
    Rules: get_by_project R6."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    c = cost(db, s, name="Scaffold")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, skip=2)
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {a.id, b.id, c.id}


# [claude] MPC-GP-17
def test_mpc_gp_17__skip_past_end_empty(db, s):
    """MPC-GP-17 — skip past the end returns an empty list.
    Rules: get_by_project R6."""
    cost(db, s)
    cost(db, s, name="Lift hire")
    cost(db, s, name="Scaffold")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, skip=3)
    # Then 1
    assert result == []


# [claude] MPC-GP-18
def test_mpc_gp_18__default_limit_100(db, s):
    """MPC-GP-18 — with the default limit 101 costs give 100.
    Rules: get_by_project R6."""
    for k in range(101):
        db.add(
            MiscellaneousProjectCost(
                workspace_id=s.W1.id,
                project_id=s.PJ1.id,
                name=f"Crane {k}",
                amount=Decimal("100.00"),
                created_at=T1,
            )
        )
        db.flush()
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 100


# [claude] MPC-GP-19
def test_mpc_gp_19__limit_1000_gives_all(db, s):
    """MPC-GP-19 — limit=1000 gives all 101 costs.
    Rules: get_by_project R6."""
    for k in range(101):
        db.add(
            MiscellaneousProjectCost(
                workspace_id=s.W1.id,
                project_id=s.PJ1.id,
                name=f"Crane {k}",
                amount=Decimal("100.00"),
                created_at=T1,
            )
        )
        db.flush()
    result = dao.get_by_project(
        db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=1000
    )
    # Then 1
    assert len(result) == 101


# [claude] MPC-GP-20
def test_mpc_gp_20__negative_limit_data_error(db, s):
    """MPC-GP-20 — a negative limit raises DataError and writes nothing.
    Rules: get_by_project R6, Errors."""
    cost(db, s)
    before = total_costs(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=-1)
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert total_costs(db) == before


# [claude] MPC-GP-21
def test_mpc_gp_21__negative_skip_data_error(db, s):
    """MPC-GP-21 — a negative skip raises DataError and writes nothing.
    Rules: get_by_project R6, Errors."""
    cost(db, s)
    before = total_costs(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, skip=-1)
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert total_costs(db) == before


# [claude] MPC-GP-22
def test_mpc_gp_22__project_filter_before_page(db, s):
    """MPC-GP-22 — the project filter comes before the page: a lower-id cost of another project takes no place.
    Rules: get_by_project R6, R2."""
    cost(db, s, project_id=s.PJA.id)
    unlinked(db, s)
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=2)
    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] MPC-GP-23
def test_mpc_gp_23__workspace_filter_before_page(db, s):
    """MPC-GP-23 — the workspace filter comes before the page: W0 and W2 costs take no place.
    Rules: get_by_project R6, R3."""
    unlinked(db, s, workspace_id=s.W0.id)
    n1 = unlinked(db, s)
    n2 = unlinked(db, s, name="Lift hire")
    unlinked(db, s, workspace_id=s.W2.id)
    result = dao.get_by_project(db, project_id=None, workspace_id=s.W1.id, limit=2)
    # Then 1
    assert idset(result) == {n1.id, n2.id}


# [claude] MPC-GP-24
def test_mpc_gp_24__writes_nothing_pending_stays_pending(db, s):
    """MPC-GP-24 — writes nothing: a pending cost stays pending, an unflushed edit stays unflushed.
    Rules: get_by_project Side effects."""
    a = cost(db, s)
    a.name = "Edited"
    p = MiscellaneousProjectCost(
        workspace_id=s.W1.id,
        project_id=s.PJ1.id,
        name="Pending",
        amount=Decimal("5.00"),
        created_at=T1,
    )
    db.add(p)
    before = total_costs(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert total_costs(db) == before


# [claude] MPC-GP-25
def test_mpc_gp_25__amounts_exact_decimal(db, s):
    """MPC-GP-25 — stored amounts are returned as exact Decimal values.
    Rules: get_by_project Returns."""
    a = cost(db, s, amount=Decimal("2.125"))
    b = cost(db, s, name="Lift hire", amount=Decimal("0.005"))
    db.expire_all()
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert {r.id: r.amount for r in result} == {
        a.id: Decimal("2.13"),
        b.id: Decimal("0.01"),
    }
    # Then 2
    assert all(isinstance(r.amount, Decimal) for r in result)


# [claude] MPC-GP-26
@xfail_bug("BUG-2460", strict=False)
def test_mpc_gp_26__id_ascending_after_edit(db, s):
    """MPC-GP-26 — id ascending, also after the lowest-id cost was edited.
    Rules: get_by_project R4 [BUG-2460]."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    c = cost(db, s, name="Scaffold")
    a.name = "Crane two"
    db.flush()
    db.expire_all()
    seqscan(db)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] MPC-GP-27
@xfail_bug("BUG-2460", strict=False)
def test_mpc_gp_27__pages_of_one_after_edit(db, s):
    """MPC-GP-27 — pages of one, after an edit, neither repeat nor miss a cost.
    Rules: get_by_project R4, R6 [BUG-2460]."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    c = cost(db, s, name="Scaffold")
    a.name = "Crane two"
    db.flush()
    db.expire_all()
    seqscan(db)
    pages = [
        dao.get_by_project(
            db, project_id=s.PJ1.id, workspace_id=s.W1.id, skip=k, limit=1
        )
        for k in range(3)
    ]
    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [a.id, b.id, c.id]


# [claude] MPC-GP-28
@xfail_bug("BUG-2460")
def test_mpc_gp_28__query_orders_by_id(db, s):
    """MPC-GP-28 — the query orders by id ascending.
    Rules: get_by_project R4 [BUG-2460]."""
    a = cost(db, s)
    with StatementRecorder(db) as rec:
        result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "miscellaneous_project_costs.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0


# [claude] MPC-GP-29
@xfail_bug("BUG-2461")
def test_mpc_gp_29__component_only_cost_returned(db, s):
    """MPC-GP-29 — a cost booked only on a component of the project is returned.
    Rules: get_by_project R1a [BUG-2461]."""
    a = cost(db, s)
    k = component_only(db, s, s.C1)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert a.id in idset(result)
    # Then 2
    assert idset(result) == {a.id, k.id}
    # Then 3
    assert len(result) == 2


# [claude] MPC-GP-30
@xfail_bug("BUG-2461")
def test_mpc_gp_30__two_components_and_both_each_once(db, s):
    """MPC-GP-30 — costs of two components and a cost with both are each returned once.
    Rules: get_by_project R1a [BUG-2461]."""
    k1 = component_only(db, s, s.C1)
    b = cost(db, s, project_component_id=s.C1.id)
    k2 = component_only(db, s, s.C2, amount=Decimal("300.00"))
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert b.id in idset(result)
    # Then 2
    assert idset(result) == {k1.id, b.id, k2.id}
    # Then 3
    assert len(result) == 3


# [claude] MPC-GP-31
@xfail_bug("BUG-2461")
def test_mpc_gp_31__other_project_component_cost_not_returned(db, s):
    """MPC-GP-31 — a cost on another project's component is not returned, the project's own component cost is.
    Rules: get_by_project R1a, R2 [BUG-2461]."""
    ka = component_only(db, s, s.CA)
    k = component_only(db, s, s.C1)
    component_only(db, s, s.CB)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ka.id not in idset(result)
    # Then 2
    assert idset(result) == {k.id}


# [claude] MPC-GP-32
@xfail_bug("BUG-2461")
def test_mpc_gp_32__deleted_project_component_costs_returned(db, s):
    """MPC-GP-32 — a soft-deleted project's component costs are returned.
    Rules: get_by_project R1a, R5 [BUG-2461]."""
    d = cost(db, s, project_id=s.PJD.id)
    kd = component_only(db, s, s.CDL)
    result = dao.get_by_project(db, project_id=s.PJD.id, workspace_id=s.W1.id)
    # Then 1
    assert d.id in idset(result)
    # Then 2
    assert idset(result) == {d.id, kd.id}


# [claude] MPC-GP-33
@xfail_bug("BUG-2461")
def test_mpc_gp_33__other_workspace_component_not_matched(db, s):
    """MPC-GP-33 — a cost on another workspace's component is not matched through the project.
    Rules: get_by_project R1a ("same workspace") [BUG-2461]."""
    cy = ProjectComponent(workspace_id=s.W2.id, project_id=s.PJ1.id, name="Span")
    db.add(cy)
    db.flush()  # invalid data on purpose
    ky = component_only(db, s, cy)
    k = component_only(db, s, s.C1)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert ky.id not in idset(result)
    # Then 2
    assert idset(result) == {k.id}


# [claude] MPC-GP-34
@xfail_bug("BUG-2461")
def test_mpc_gp_34__component_costs_count_before_page(db, s):
    """MPC-GP-34 — component costs count before the page, a lower-id cost of another project does not.
    Rules: get_by_project R1a, R6 [BUG-2461]."""
    xa = cost(db, s, project_id=s.PJA.id)
    a = cost(db, s)
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C2)
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id, limit=3)
    # Then 1
    assert xa.id not in idset(result)
    # Then 2
    assert idset(result) == {a.id, k1.id, k2.id}


# [claude] MPC-GP-35
def test_mpc_gp_35__any_creation_time(db, s):
    """MPC-GP-35 — the project's own costs are returned whatever their creation time.
    Rules: get_by_project R1."""
    a = cost(db, s, created_at=T0)
    b = cost(db, s, name="Lift hire")
    result = dao.get_by_project(db, project_id=s.PJ1.id, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {a.id, b.id}


# [claude] MPC-GP-36
def test_mpc_gp_36__project_id_none_not_through_components(db, s):
    """MPC-GP-36 — project_id None does not match through components: a cost with a project and a component is left out.
    Rules: get_by_project R3 (unchanged by the BUG-2461 fix)."""
    cost(db, s, project_component_id=s.C1.id)
    k = component_only(db, s, s.C2)
    cost(db, s, project_id=s.PJB.id, project_component_id=s.CB.id)
    result = dao.get_by_project(db, project_id=None, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [k.id]


# --------------------------------------------------------------------------- #
# `DAOMiscellaneousProjectCost.get_by_component`
# --------------------------------------------------------------------------- #


# [claude] MPC-GC-01
def test_mpc_gc_01__returns_component_costs(db, s):
    """MPC-GC-01 — returns the component's costs, with or without the project set.
    Rules: get_by_component R1, Returns."""
    cost(db, s)
    k = component_only(db, s, s.C1, amount=Decimal("1200.50"))
    b = cost(db, s, project_component_id=s.C1.id, name="Lift hire")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {k.id, b.id}
    # Then 3
    assert len(result) == 2
    # Then 4
    assert [r for r in result if r.id == k.id][0].amount == Decimal("1200.50")


# [claude] MPC-GC-02
def test_mpc_gc_02__other_components_not_returned(db, s):
    """MPC-GC-02 — costs of a lower-id and a higher-id component are not returned.
    Rules: get_by_component R1."""
    component_only(db, s, s.CA)
    k = component_only(db, s, s.C1)
    component_only(db, s, s.C2)
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [k.id]


# [claude] MPC-GC-03
def test_mpc_gc_03__w1_asking_for_w2_component_gets_nothing(db, s):
    """MPC-GC-03 — W1 asking for W2's component gets nothing, though W2 has costs on it.
    Rules: get_by_component R1."""
    component_only(db, s, s.C1)
    cost(
        db,
        s,
        workspace_id=s.W2.id,
        project_id=s.PJX.id,
        project_component_id=s.CX.id,
    )
    result = dao.get_by_component(
        db, project_component_id=s.CX.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-04
def test_mpc_gc_04__w1_asking_for_w0_component_gets_nothing(db, s):
    """MPC-GC-04 — W1 asking for W0's component gets nothing, though W0 has costs on it.
    Rules: get_by_component R1."""
    cost(db, s, workspace_id=s.W0.id, project_id=None, project_component_id=s.C0.id)
    component_only(db, s, s.C1)
    result = dao.get_by_component(
        db, project_component_id=s.C0.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-05
def test_mpc_gc_05__w2_gets_its_own_component_cost(db, s):
    """MPC-GC-05 — W2 gets its own component's cost.
    Rules: get_by_component R1."""
    cost(db, s, workspace_id=s.W0.id, project_id=None, project_component_id=s.C0.id)
    component_only(db, s, s.C1)
    kx = cost(
        db, s, workspace_id=s.W2.id, project_id=None, project_component_id=s.CX.id
    )
    result = dao.get_by_component(
        db, project_component_id=s.CX.id, workspace_id=s.W2.id
    )
    # Then 1
    assert ids(result) == [kx.id]


# [claude] MPC-GC-06
def test_mpc_gc_06__unknown_component_id_empty(db, s):
    """MPC-GC-06 — an unknown component id returns an empty list.
    Rules: get_by_component R1."""
    component_only(db, s, s.C1)
    result = dao.get_by_component(
        db, project_component_id=MISSING, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-07
def test_mpc_gc_07__component_id_zero_empty(db, s):
    """MPC-GC-07 — project_component_id 0 returns an empty list and raises nothing.
    Rules: get_by_component R2."""
    component_only(db, s, s.C1)
    cost(db, s)
    result = dao.get_by_component(db, project_component_id=0, workspace_id=s.W1.id)
    # Then 1
    assert result == []


# [claude] MPC-GC-08
def test_mpc_gc_08__component_without_costs_empty(db, s):
    """MPC-GC-08 — a component without costs returns an empty list.
    Rules: get_by_component R1."""
    component_only(db, s, s.C1)
    result = dao.get_by_component(
        db, project_component_id=s.C2.id, workspace_id=s.W1.id
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-09
def test_mpc_gc_09__component_id_none_returns_costs_without_component(db, s):
    """MPC-GC-09 — project_component_id None returns this workspace's costs with no component.
    Rules: get_by_component R2."""
    unlinked(db, s, workspace_id=s.W0.id)
    a = cost(db, s)
    component_only(db, s, s.C1)
    n = unlinked(db, s)
    unlinked(db, s, workspace_id=s.W2.id)
    result = dao.get_by_component(db, project_component_id=None, workspace_id=s.W1.id)
    # Then 1
    assert idset(result) == {a.id, n.id}
    # Then 2
    assert len(result) == 2


# [claude] MPC-GC-10
def test_mpc_gc_10__deleted_project_component_costs_returned(db, s):
    """MPC-GC-10 — costs of a component of a soft-deleted project are returned.
    Rules: get_by_component R4."""
    kd = component_only(db, s, s.CDL)
    result = dao.get_by_component(
        db, project_component_id=s.CDL.id, workspace_id=s.W1.id
    )
    # Then 1
    assert ids(result) == [kd.id]


# [claude] MPC-GC-11
def test_mpc_gc_11__query_reads_neither_projects_nor_components(db, s):
    """MPC-GC-11 — the query reads neither projects nor components.
    Rules: get_by_component R4."""
    k = component_only(db, s, s.C1)
    with StatementRecorder(db) as rec:
        result = dao.get_by_component(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [k.id]
    # Then 2
    assert "projects." not in rec.sql
    # Then 3
    assert "project_components." not in rec.sql
    # Then 4
    assert "FOR UPDATE" not in rec.sql


# [claude] MPC-GC-12
def test_mpc_gc_12__limit_zero_empty(db, s):
    """MPC-GC-12 — limit=0 returns an empty list.
    Rules: get_by_component R4."""
    component_only(db, s, s.C1)
    component_only(db, s, s.C1, name="Lift hire")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, limit=0
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-13
def test_mpc_gc_13__limit_one_of_three(db, s):
    """MPC-GC-13 — limit=1 of three costs returns one of them.
    Rules: get_by_component R4."""
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C1, name="Lift hire")
    k3 = component_only(db, s, s.C1, name="Scaffold")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, limit=1
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {k1.id, k2.id, k3.id}


# [claude] MPC-GC-14
def test_mpc_gc_14__skip_two_of_three(db, s):
    """MPC-GC-14 — skip=2 of three costs returns one of them.
    Rules: get_by_component R4."""
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C1, name="Lift hire")
    k3 = component_only(db, s, s.C1, name="Scaffold")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, skip=2
    )
    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in {k1.id, k2.id, k3.id}


# [claude] MPC-GC-15
def test_mpc_gc_15__skip_past_end_empty(db, s):
    """MPC-GC-15 — skip past the end returns an empty list.
    Rules: get_by_component R4."""
    component_only(db, s, s.C1)
    component_only(db, s, s.C1, name="Lift hire")
    component_only(db, s, s.C1, name="Scaffold")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, skip=3
    )
    # Then 1
    assert result == []


# [claude] MPC-GC-16
def test_mpc_gc_16__default_limit_100(db, s):
    """MPC-GC-16 — with the default limit 101 costs give 100.
    Rules: get_by_component R4."""
    for k in range(101):
        db.add(
            MiscellaneousProjectCost(
                workspace_id=s.W1.id,
                project_id=None,
                project_component_id=s.C1.id,
                name=f"Crane {k}",
                amount=Decimal("100.00"),
                created_at=T1,
            )
        )
        db.flush()
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 100


# [claude] MPC-GC-17
def test_mpc_gc_17__limit_1000_gives_all(db, s):
    """MPC-GC-17 — limit=1000 gives all 101 costs.
    Rules: get_by_component R4."""
    for k in range(101):
        db.add(
            MiscellaneousProjectCost(
                workspace_id=s.W1.id,
                project_id=None,
                project_component_id=s.C1.id,
                name=f"Crane {k}",
                amount=Decimal("100.00"),
                created_at=T1,
            )
        )
        db.flush()
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, limit=1000
    )
    # Then 1
    assert len(result) == 101


# [claude] MPC-GC-18
def test_mpc_gc_18__negative_limit_data_error(db, s):
    """MPC-GC-18 — a negative limit raises DataError and writes nothing.
    Rules: get_by_component R4, Errors."""
    component_only(db, s, s.C1)
    before = total_costs(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(
                db, project_component_id=s.C1.id, workspace_id=s.W1.id, limit=-1
            )
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert total_costs(db) == before


# [claude] MPC-GC-19
def test_mpc_gc_19__negative_skip_data_error(db, s):
    """MPC-GC-19 — a negative skip raises DataError and writes nothing.
    Rules: get_by_component R4, Errors."""
    component_only(db, s, s.C1)
    before = total_costs(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_component(
                db, project_component_id=s.C1.id, workspace_id=s.W1.id, skip=-1
            )
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert total_costs(db) == before


# [claude] MPC-GC-20
def test_mpc_gc_20__component_filter_before_page(db, s):
    """MPC-GC-20 — the component filter comes before the page: a lower-id cost of another component takes no place.
    Rules: get_by_component R1, R4."""
    component_only(db, s, s.CA)
    cost(db, s)
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C1, name="Lift hire")
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id, limit=2
    )
    # Then 1
    assert idset(result) == {k1.id, k2.id}


# [claude] MPC-GC-21
def test_mpc_gc_21__writes_nothing_pending_stays_pending(db, s):
    """MPC-GC-21 — writes nothing: a pending cost stays pending, an unflushed edit stays unflushed.
    Rules: get_by_component Side effects."""
    k = component_only(db, s, s.C1)
    k.name = "Edited"
    p = MiscellaneousProjectCost(
        workspace_id=s.W1.id,
        project_id=None,
        project_component_id=s.C1.id,
        name="Pending",
        amount=Decimal("5.00"),
        created_at=T1,
    )
    db.add(p)
    before = total_costs(db)
    with StatementRecorder(db) as rec:
        result = dao.get_by_component(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [k.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert k in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written == []
    # Then 8
    assert total_costs(db) == before


# [claude] MPC-GC-22
@xfail_bug("BUG-2460", strict=False)
def test_mpc_gc_22__id_ascending_after_edit(db, s):
    """MPC-GC-22 — id ascending, also after the lowest-id cost was edited.
    Rules: get_by_component R3 [BUG-2460]."""
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C1, name="Lift hire")
    k3 = component_only(db, s, s.C1, name="Scaffold")
    k1.name = "Crane two"
    db.flush()
    db.expire_all()
    seqscan(db)
    result = dao.get_by_component(
        db, project_component_id=s.C1.id, workspace_id=s.W1.id
    )
    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [k1.id, k2.id, k3.id]


# [claude] MPC-GC-23
@xfail_bug("BUG-2460", strict=False)
def test_mpc_gc_23__pages_of_one_after_edit(db, s):
    """MPC-GC-23 — pages of one, after an edit, neither repeat nor miss a cost.
    Rules: get_by_component R3, R4 [BUG-2460]."""
    k1 = component_only(db, s, s.C1)
    k2 = component_only(db, s, s.C1, name="Lift hire")
    k3 = component_only(db, s, s.C1, name="Scaffold")
    k1.name = "Crane two"
    db.flush()
    db.expire_all()
    seqscan(db)
    pages = [
        dao.get_by_component(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id, skip=k, limit=1
        )
        for k in range(3)
    ]
    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [k1.id, k2.id, k3.id]


# [claude] MPC-GC-24
@xfail_bug("BUG-2460")
def test_mpc_gc_24__query_orders_by_id(db, s):
    """MPC-GC-24 — the query orders by id ascending.
    Rules: get_by_component R3 [BUG-2460]."""
    k = component_only(db, s, s.C1)
    with StatementRecorder(db) as rec:
        result = dao.get_by_component(
            db, project_component_id=s.C1.id, workspace_id=s.W1.id
        )
    # Then 1
    assert ids(result) == [k.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "miscellaneous_project_costs.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()
    # Then 5
    assert rec.order_part.count(",") == 0


# --------------------------------------------------------------------------- #
# Inherited `BaseDAO` facts for this table
# --------------------------------------------------------------------------- #


# [claude] MPC-INH-01
@xfail_bug("BUG-100", revisit=False)
def test_mpc_inh_01__workspace_list_orders_by_id(db, s):
    """MPC-INH-01 — the workspace list orders by id ascending.
    Rules: inherited R1 [BUG-100]."""
    a = cost(db, s)
    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=s.W1.id)
    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in rec.sql
    # Then 3
    assert "miscellaneous_project_costs.id" in rec.order_part
    # Then 4
    assert "DESC" not in rec.order_part.upper()


def _create(db, s, amount, name="Crane", **links):
    """The dict create of the INH / OQ28 cards (project PJ1 unless links given)."""
    fields = {"workspace_id": s.W1.id, **(links or {"project_id": s.PJ1.id})}
    return dao.create(db, obj_in={**fields, "name": name, "amount": amount})


# [claude] MPC-INH-02
def test_mpc_inh_02__create_rounds_2_125_half_up(db, s):
    """MPC-INH-02 — create stores 2.125 as 2.13 (half up, not half even).
    Rules: inherited R2 (create rounding), HR-15."""
    result = _create(db, s, Decimal("2.125"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("2.13")


# [claude] MPC-INH-03
def test_mpc_inh_03__create_rounds_0_005_up(db, s):
    """MPC-INH-03 — create stores 0.005 as 0.01.
    Rules: inherited R2 (create rounding), HR-15."""
    result = _create(db, s, Decimal("0.005"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("0.01")


# [claude] MPC-INH-04
def test_mpc_inh_04__create_rounds_2_124_down(db, s):
    """MPC-INH-04 — create stores 2.124 as 2.12 (control: below the half).
    Rules: inherited R2 (create rounding), HR-15."""
    result = _create(db, s, Decimal("2.124"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("2.12")


# [claude] MPC-INH-05
def test_mpc_inh_05__create_rounds_1000_005_up(db, s):
    """MPC-INH-05 — create stores 1000.005 as 1000.01.
    Rules: inherited R2 (create rounding), HR-15."""
    result = _create(db, s, Decimal("1000.005"), project_component_id=s.C1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.amount == Decimal("1000.01")
    # Then 3
    assert row.project_id is None
    assert row.project_component_id == s.C1.id
    assert row.workspace_id == s.W1.id


# [claude] MPC-INH-06
def test_mpc_inh_06__twelve_digit_amount_exact(db, s):
    """MPC-INH-06 — a 12-digit amount is stored exactly.
    Rules: inherited R2 (integer-digit limit, the side that fits)."""
    result = _create(db, s, Decimal("999999999999.99"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("999999999999.99")


# [claude] MPC-INH-07
def test_mpc_inh_07__fourteen_digits_data_error(db, s):
    """MPC-INH-07 — an amount of 10000000000000.00 (14 integer digits) raises DataError 22003 and stores nothing.
    Rules: inherited R2 (integer-digit limit, the side that fails)."""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            _create(db, s, Decimal("10000000000000.00"))
    assert exc.value.orig.pgcode == "22003"
    # Then 2
    assert cost_count(db, MiscellaneousProjectCost.workspace_id == s.W1.id) == 0


# [claude] MPC-INH-08
def test_mpc_inh_08__created_at_naive_utc(db, s):
    """MPC-INH-08 — created_at defaults to naive UTC, whatever the database's time zone.
    Rules: Model facts (created_at Python utcnow())."""
    dhaka(db)
    before = utcnow()
    result = _create(db, s, Decimal("100.00"))
    after = utcnow()
    # Then 1
    assert result.id is not None
    # Then 2
    result = reread(db, result.id)
    assert result.created_at.tzinfo is None
    # Then 3
    assert before <= result.created_at <= after


# [claude] MPC-INH-09
def test_mpc_inh_09__update_rounds_0_125_keeps_others(db, s):
    """MPC-INH-09 — update from the schema stores amount 0.125 as 0.13 and keeps the other fields.
    Rules: inherited R2 (update), HR-15."""
    b = cost(db, s, name="Lift hire", description="Two days")
    result = dao.update(
        db, db_obj=b, obj_in=MiscellaneousProjectCostUpdate(amount=0.125)
    )
    # Then 1
    assert result is b
    # Then 2
    row = reread(db, b.id)
    assert row.amount == Decimal("0.13")
    # Then 3
    assert row.name == "Lift hire"
    assert row.description == "Two days"
    assert row.project_id == s.PJ1.id


# [claude] MPC-INH-10
def test_mpc_inh_10__update_2_5_stores_2_50(db, s):
    """MPC-INH-10 — update from the schema with amount 2.5 stores 2.50.
    Rules: inherited R2 (update)."""
    b = cost(db, s)
    result = dao.update(db, db_obj=b, obj_in=MiscellaneousProjectCostUpdate(amount=2.5))
    # Then 1
    assert result is b
    # Then 2
    assert reread(db, b.id).amount == Decimal("2.50")


# [claude] MPC-INH-11
def test_mpc_inh_11__update_description_none_keeps_it(db, s):
    """MPC-INH-11 — update from the schema with description None keeps the description.
    Rules: inherited R2 (update drops null fields)."""
    b = cost(db, s, description="Two days")
    result = dao.update(
        db, db_obj=b, obj_in=MiscellaneousProjectCostUpdate(description=None)
    )
    # Then 1
    assert result is b
    # Then 2
    row = reread(db, b.id)
    assert row.description == "Two days"
    assert row.amount == Decimal("100.00")


# [claude] MPC-INH-12
def test_mpc_inh_12__remove_hard_deletes(db, s):
    """MPC-INH-12 — remove hard-deletes the row.
    Rules: inherited R2 (remove)."""
    a = cost(db, s)
    b = cost(db, s, name="Lift hire")
    dao.remove(db, id=a.id)
    db.flush()
    # Then 1
    assert cost_count(db, MiscellaneousProjectCost.id == a.id) == 0
    # Then 2
    assert cost_count(db, MiscellaneousProjectCost.id == b.id) == 1


# [claude] MPC-INH-13
def test_mpc_inh_13__thirteen_digit_amount_exact(db, s):
    """MPC-INH-13 — a 13-digit amount, 9999999999999.99, is stored exactly.
    Rules: inherited R2 (integer-digit limit, the largest value that fits)."""
    result = _create(db, s, Decimal("9999999999999.99"))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("9999999999999.99")


# [claude] MPC-INH-14
def test_mpc_inh_14__rounding_to_fourteen_digits_data_error(db, s):
    """MPC-INH-14 — 9999999999999.995 rounds up to 14 integer digits and raises DataError 22003.
    Rules: inherited R2 (integer-digit limit after rounding), HR-15."""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            _create(db, s, Decimal("9999999999999.995"))
    assert exc.value.orig.pgcode == "22003"
    # Then 2
    assert cost_count(db, MiscellaneousProjectCost.workspace_id == s.W1.id) == 0


# [claude] MPC-INH-15
def test_mpc_inh_15__create_through_schema_1000_005(db, s):
    """MPC-INH-15 — create through the schema (dump plus workspace_id) stores the cost, 1000.005 as 1000.01.
    Rules: inherited R2b, HR-15."""
    schema = MiscellaneousProjectCostCreate(
        project_component_id=s.C1.id, name="Crane", amount=1000.005
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.amount == Decimal("1000.01")
    # Then 3
    assert row.workspace_id == s.W1.id
    assert row.project_id is None
    assert row.project_component_id == s.C1.id
    assert row.name == "Crane"
    assert row.description is None


# [claude] MPC-INH-16
def test_mpc_inh_16__create_through_schema_2_675(db, s):
    """MPC-INH-16 — create through the schema stores the float 2.675 as 2.68 (half up as typed).
    Rules: inherited R2b, HR-15."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Crane", amount=2.675
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("2.68")


# [claude] MPC-INH-17
def test_mpc_inh_17__create_through_schema_0_125(db, s):
    """MPC-INH-17 — create through the schema stores 0.125 as 0.13.
    Rules: inherited R2b, HR-15."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Crane", description="Two days", amount=0.125
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.amount == Decimal("0.13")
    # Then 3
    assert row.description == "Two days"
    assert row.project_id == s.PJ1.id
    assert row.project_component_id is None


# [claude] MPC-INH-18
def test_mpc_inh_18__create_through_schema_2_124(db, s):
    """MPC-INH-18 — create through the schema stores 2.124 as 2.12 (control).
    Rules: inherited R2b, HR-15."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Crane", amount=2.124
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("2.12")


# [claude] MPC-INH-19
def test_mpc_inh_19__create_through_schema_13_digits(db, s):
    """MPC-INH-19 — create through the schema stores 9999999999999.99 as is.
    Rules: inherited R2b, R2 (integer-digit limit)."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Crane", amount=9999999999999.99
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("9999999999999.99")


# [claude] MPC-INH-20
def test_mpc_inh_20__schema_alone_fails_23502(db, s):
    """MPC-INH-20 — the schema object alone has no workspace_id: create fails with IntegrityError 23502 and stores nothing.
    Rules: inherited R2b."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Crane", amount=100.0
    )
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=schema)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert "workspace_id" in str(exc.value.orig)
    # Then 3
    assert cost_count(db, MiscellaneousProjectCost.project_id == s.PJ1.id) == 0


# --------------------------------------------------------------------------- #
# Inherited R2a — negative and zero amounts are stored (OQ-28)
# --------------------------------------------------------------------------- #


# [claude] MPC-OQ28-01
def test_mpc_oq28_01__create_rounds_minus_1_005(db, s):
    """MPC-OQ28-01 — create stores -1.005 as -1.01 (half away from zero); revisit after launch (owner 2026-11-10).
    Rules: inherited R2a, R2 (create rounding), HR-15."""
    result = _create(db, s, Decimal("-1.005"), name="Credit")
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("-1.01")


# [claude] MPC-OQ28-02
def test_mpc_oq28_02__create_stores_zero(db, s):
    """MPC-OQ28-02 — create stores an amount of 0 as 0.00; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a."""
    result = _create(db, s, Decimal("0"), name="Placeholder")
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("0.00")


# [claude] MPC-OQ28-03
def test_mpc_oq28_03__update_schema_accepts_negative():
    """MPC-OQ28-03 — the update schema accepts a negative amount; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a (schema, target schema)."""
    result = MiscellaneousProjectCostUpdate(amount=-5)
    # Then 1
    assert result.amount == -5


# [claude] MPC-OQ28-04
def test_mpc_oq28_04__update_schema_accepts_zero():
    """MPC-OQ28-04 — the update schema accepts an amount of 0; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a (schema, target schema)."""
    result = MiscellaneousProjectCostUpdate(amount=0)
    # Then 1
    assert result.amount == 0


# [claude] MPC-OQ28-05
def test_mpc_oq28_05__update_stores_minus_5(db, s):
    """MPC-OQ28-05 — update from the schema stores -5 as -5.00; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a, R2 (update)."""
    b = cost(db, s)
    result = dao.update(db, db_obj=b, obj_in=MiscellaneousProjectCostUpdate(amount=-5))
    # Then 1
    assert result is b
    # Then 2
    assert reread(db, b.id).amount == Decimal("-5.00")


# [claude] MPC-OQ28-06
def test_mpc_oq28_06__create_through_schema_minus_1_005(db, s):
    """MPC-OQ28-06 — create through the schema stores -1.005 as -1.01; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a, R2b, HR-15."""
    schema = MiscellaneousProjectCostCreate(
        project_id=s.PJ1.id, name="Credit", amount=-1.005
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("-1.01")


# [claude] MPC-OQ28-07
def test_mpc_oq28_07__create_through_schema_zero(db, s):
    """MPC-OQ28-07 — create through the schema stores an amount of 0 as 0.00; revisit after launch (owner 2026-11-10).
    Rules: inherited R2a, R2b."""
    schema = MiscellaneousProjectCostCreate(
        project_component_id=s.C1.id, name="Placeholder", amount=0
    )
    result = dao.create(db, obj_in=dump(schema, s))
    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result.id).amount == Decimal("0.00")
