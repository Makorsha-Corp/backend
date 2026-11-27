"""Unit tests for app/utils/work_order_generation.py.

Implements tests/unit/utils/work_order_generation.cases.md (revision 2), one
test per case. Real Postgres session (`db` fixture), nothing mocked (spec:
no externals, no time, no race simulations).
"""
import itertools

import pytest
from sqlalchemy import insert

from app.models.factory import Factory
from app.models.factory_section import FactorySection
from app.models.machine import Machine
from app.models.machine_section_assignment import MachineSectionAssignment
from app.models.work_order_template import WorkOrderTemplate
from app.utils.work_order_generation import resolve_template_machine_ids
from tests.unit.factories import make_workspace

BUG_340 = "BUG-340: Template's default machine used even if deleted, missing or in another workspace"
BUG_341 = "BUG-341: Template's default machine ignores the run's factory/section scope"
BUG_342 = "BUG-342: At most 1000 machines per section/factory get a draft"
BUG_343 = "BUG-343: Section/factory machine list has no sort order"

_seq = itertools.count(1)

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #


# Convention "Workspaces: W1, W2"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


def _make_factory(db, ws):
    n = next(_seq)
    row = Factory(workspace_id=ws.id, name=f"Factory {n}", abbreviation=f"F{n}")
    db.add(row)
    db.flush()
    return row


def _make_section(db, factory):
    n = next(_seq)
    row = FactorySection(workspace_id=factory.workspace_id, factory_id=factory.id, name=f"Section {n}")
    db.add(row)
    db.flush()
    return row


# Convention "Factories: F1, F2 in W1; F3 in W2"
@pytest.fixture
def f1(db, w1):
    return _make_factory(db, w1)


@pytest.fixture
def f2(db, w1):
    return _make_factory(db, w1)


@pytest.fixture
def f3(db, w2):
    return _make_factory(db, w2)


# Convention "Sections: S1, S2 belong to F1 (W1)"
@pytest.fixture
def s1(db, f1):
    return _make_section(db, f1)


@pytest.fixture
def s2(db, f1):
    return _make_section(db, f1)


def mk(db, factory, section=None, *, name=None, **overrides):
    """Convention "Machines": live (is_deleted=False, is_active=True) in the
    factory's workspace unless overridden; "assigned S" = one
    MachineSectionAssignment row to S, "unassigned" = none."""
    fields = {
        "workspace_id": factory.workspace_id,
        "factory_id": factory.id,
        "name": name or f"Machine {next(_seq)}",
        "is_deleted": False,
        "is_active": True,
    }
    fields.update(overrides)
    m = Machine(**fields)
    db.add(m)
    db.flush()
    if section is not None:
        db.add(MachineSectionAssignment(
            workspace_id=m.workspace_id, machine_id=m.id, factory_section_id=section.id,
        ))
        db.flush()
    return m


def mk_bulk(db, factory, count, section=None):
    """1000+ live machines named "Machine 0001"... via one multi-row INSERT."""
    rows = [
        {
            "workspace_id": factory.workspace_id, "factory_id": factory.id,
            "name": f"Machine {i:04d}", "is_running": False,
            "is_deleted": False, "is_active": True,
        }
        for i in range(1, count + 1)
    ]
    ids = list(db.scalars(insert(Machine).returning(Machine.id), rows).all())
    if section is not None:
        db.execute(insert(MachineSectionAssignment), [
            {"workspace_id": factory.workspace_id, "machine_id": mid, "factory_section_id": section.id}
            for mid in ids
        ])
    db.flush()
    assert len(ids) == count
    return ids


def template(default_machine_id=None, default_factory_section_id=None):
    """Convention "Template T": in-memory, never added to the session."""
    return WorkOrderTemplate(
        default_machine_id=default_machine_id,
        default_factory_section_id=default_factory_section_id,
    )


def call(db, t, workspace, **kwargs):
    """Convention "Call"."""
    return resolve_template_machine_ids(db, template=t, workspace_id=workspace.id, **kwargs)


def assert_set_equals(result, ids):
    """Convention "Set equals {...}"."""
    assert sorted(result) == sorted(ids)
    assert len(result) == len(set(ids))


def assert_no_pending(db):
    """Convention "no pending changes"."""
    assert len(db.new) == 0
    assert len(db.dirty) == 0


# --------------------------------------------------------------------------- #
# Default-machine path
# --------------------------------------------------------------------------- #


def test_wog_r_01__default_machine_beats_template_section(db, w1, f1, s1, s2):
    """WOG-R-01 — default machine returned alone; template section not used or compared.
    Rules: R1, R2, R2d."""
    m1 = mk(db, f1, s1)
    mk(db, f1, s2)
    t = template(default_machine_id=m1.id, default_factory_section_id=s2.id)
    result = call(db, t, w1)
    assert result == [m1.id]
    assert_no_pending(db)


def test_wog_r_02__inactive_default_machine_still_returned(db, w1, f1):
    """WOG-R-02 — inactive but not deleted default machine counts as live.
    Rules: R2."""
    m1 = mk(db, f1, is_active=False, is_deleted=False)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1) == [m1.id]


def test_wog_r_03__default_machine_in_run_factory(db, w1, f1):
    """WOG-R-03 — default machine in the run's factory; other factory machines not added.
    Rules: R1, R2, R2c."""
    m1 = mk(db, f1)
    mk(db, f1)
    mk(db, f1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_id=f1.id) == [m1.id]


def test_wog_r_04__default_machine_in_run_section(db, w1, f1, s1):
    """WOG-R-04 — default machine assigned to the run's section; section peers not added.
    Rules: R2, R2c."""
    m1 = mk(db, f1, s1)
    mk(db, f1, s1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_section_id=s1.id) == [m1.id]


def test_wog_r_05__default_machine_matches_factory_and_section(db, w1, f1, s1):
    """WOG-R-05 — default machine satisfying both factory and section scope.
    Rules: R2, R2c."""
    m1 = mk(db, f1, s1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_id=f1.id, factory_section_id=s1.id) == [m1.id]


def test_wog_r_06__unassigned_default_machine_no_run_scope(db, w1, f1, s1):
    """WOG-R-06 — unassigned default machine not filtered by template section without run scope.
    Rules: R2, R2d."""
    m1 = mk(db, f1)
    mk(db, f1, s1)
    t = template(default_machine_id=m1.id, default_factory_section_id=s1.id)
    assert call(db, t, w1) == [m1.id]


@pytest.mark.xfail(strict=True, reason=BUG_340)
def test_wog_r_07__deleted_default_machine_yields_empty(db, w1, f1, s1):
    """WOG-R-07 — soft-deleted default machine yields [] with no fall-through.
    Rules: R2a [BUG-340], R1."""
    m1 = mk(db, f1, is_deleted=True)
    mk(db, f1, s1)
    t = template(default_machine_id=m1.id, default_factory_section_id=s1.id)
    assert call(db, t, w1, factory_id=f1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_340)
def test_wog_r_08__other_workspace_default_machine_yields_empty(db, w1, w2, f3):
    """WOG-R-08 — default machine of another workspace yields [].
    Rules: R2a [BUG-340]."""
    m9 = mk(db, f3)
    t = template(default_machine_id=m9.id)
    assert call(db, t, w1) == []


@pytest.mark.xfail(strict=True, reason=BUG_340)
def test_wog_r_09__missing_default_machine_yields_empty(db, w1, f1, s1):
    """WOG-R-09 — default machine id with no row yields [] with no fall-through to S1.
    Rules: R2b [BUG-340]."""
    mk(db, f1, s1)
    x = 2147483000
    assert db.get(Machine, x) is None
    t = template(default_machine_id=x, default_factory_section_id=s1.id)
    assert call(db, t, w1) == []


@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_wog_r_10__default_machine_outside_run_factory(db, w1, f1, f2):
    """WOG-R-10 — default machine outside the run's factory yields [] (no fall-through to F2).
    Rules: R2c [BUG-341], R1."""
    m1 = mk(db, f1)
    mk(db, f2)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_id=f2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_wog_r_11__default_machine_in_other_section(db, w1, f1, s1, s2):
    """WOG-R-11 — default machine assigned elsewhere yields [] (no fall-through to S2).
    Rules: R2c [BUG-341], R1."""
    m1 = mk(db, f1, s1)
    mk(db, f1, s2)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_section_id=s2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_wog_r_12__unassigned_default_machine_with_run_section(db, w1, f1, s1):
    """WOG-R-12 — unassigned default machine is not in the run's section -> [].
    Rules: R2c [BUG-341]."""
    m1 = mk(db, f1)
    mk(db, f1, s1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_section_id=s1.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_wog_r_13__factory_matches_section_does_not(db, w1, f1, s1, s2):
    """WOG-R-13 — both scopes given; factory matches, section does not -> [].
    Rules: R2c [BUG-341]."""
    m1 = mk(db, f1, s1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_id=f1.id, factory_section_id=s2.id) == []


@pytest.mark.xfail(strict=True, reason=BUG_341)
def test_wog_r_14__section_matches_factory_does_not(db, w1, f1, f2, s1):
    """WOG-R-14 — both scopes given; section matches, factory does not -> [].
    Rules: R2c [BUG-341]."""
    m1 = mk(db, f1, s1)
    t = template(default_machine_id=m1.id)
    assert call(db, t, w1, factory_id=f2.id, factory_section_id=s1.id) == []


# --------------------------------------------------------------------------- #
# Section path (no default machine)
# --------------------------------------------------------------------------- #


@pytest.fixture
def r15_machines(db, f1, s1, s2):
    """Machines of WOG-R-15 (shared by R-16, R-17)."""
    return {
        "M1": mk(db, f1, s1, name="Lathe"),
        "M2": mk(db, f1, s1, name="Mill"),
        "M3": mk(db, f1, s2, name="Press"),
        "M4": mk(db, f1, name="Saw"),
    }


def test_wog_r_15__template_section_machines(db, w1, s1, r15_machines):
    """WOG-R-15 — template default section returns its assigned machines only.
    Rules: R3, R4, R9."""
    m = r15_machines
    t = template(default_factory_section_id=s1.id)
    result = call(db, t, w1)
    assert_set_equals(result, [m["M1"].id, m["M2"].id])
    assert_no_pending(db)


def test_wog_r_16__run_section_used_when_template_has_none(db, w1, s1, r15_machines):
    """WOG-R-16 — run's factory_section_id used when template has no section.
    Rules: R3, R4."""
    m = r15_machines
    t = template()
    assert_set_equals(call(db, t, w1, factory_section_id=s1.id), [m["M1"].id, m["M2"].id])


def test_wog_r_17__template_section_beats_run_section(db, w1, s1, s2, r15_machines):
    """WOG-R-17 — template section wins over a different run section.
    Rules: R3."""
    m = r15_machines
    t = template(default_factory_section_id=s1.id)
    assert_set_equals(call(db, t, w1, factory_section_id=s2.id), [m["M1"].id, m["M2"].id])


def test_wog_r_18__section_excludes_other_workspace_machine(db, w1, f1, f3, s1):
    """WOG-R-18 — machine of W2 assigned to W1's section is excluded.
    Rules: R4."""
    m1 = mk(db, f1, s1)
    mk(db, f3, s1)
    t = template(default_factory_section_id=s1.id)
    assert call(db, t, w1) == [m1.id]


def test_wog_r_19__section_run_in_other_workspace(db, w1, w2, f1, s1):
    """WOG-R-19 — calling with W2 returns nothing for W1's section machines.
    Rules: R4."""
    mk(db, f1, s1)
    mk(db, f1, s1)
    t = template(default_factory_section_id=s1.id)
    assert call(db, t, w2) == []


def test_wog_r_20__section_ignores_factory_id(db, w1, f1, f2, s1):
    """WOG-R-20 — factory_id ignored on the section path.
    Rules: R4, R1."""
    m1 = mk(db, f1, s1)
    m2 = mk(db, f1, s1)
    mk(db, f2)
    t = template(default_factory_section_id=s1.id)
    assert_set_equals(call(db, t, w1, factory_id=f2.id), [m1.id, m2.id])


def test_wog_r_21__section_soft_delete_and_inactive(db, w1, f1, s1):
    """WOG-R-21 — deleted excluded, inactive-not-deleted included.
    Rules: R5."""
    m1 = mk(db, f1, s1)
    mk(db, f1, s1, is_deleted=True)
    m3 = mk(db, f1, s1, is_active=False, is_deleted=False)
    t = template(default_factory_section_id=s1.id)
    assert_set_equals(call(db, t, w1), [m1.id, m3.id])


def test_wog_r_22__empty_section_no_factory_fallback(db, w1, f1, s1):
    """WOG-R-22 — section with only a deleted machine -> [], no factory fallback.
    Rules: R6, R5."""
    mk(db, f1, s1, is_deleted=True)
    mk(db, f1)
    t = template(default_factory_section_id=s1.id)
    assert call(db, t, w1, factory_id=f1.id) == []


def test_wog_r_23__run_section_without_assignments(db, w1, f1, s1):
    """WOG-R-23 — run section with no assignments -> [], no factory fallback.
    Rules: R6."""
    mk(db, f1)
    t = template()
    assert call(db, t, w1, factory_section_id=s1.id, factory_id=f1.id) == []


def test_wog_r_24__single_machine_section(db, w1, f1, s1):
    """WOG-R-24 — one machine in section -> [M1].
    Rules: R4, R9."""
    m1 = mk(db, f1, s1)
    t = template(default_factory_section_id=s1.id)
    assert call(db, t, w1) == [m1.id]


def test_wog_r_25__section_no_duplicates(db, w1, f1, s1):
    """WOG-R-25 — three machines, each once.
    Rules: R9."""
    ms = [mk(db, f1, s1) for _ in range(3)]
    t = template(default_factory_section_id=s1.id)
    result = call(db, t, w1)
    assert len(result) == 3
    assert len(set(result)) == 3
    assert_set_equals(result, [m.id for m in ms])


def _ordering_machines(db, f1, section=None):
    """A "beta", B "Alpha", C "alpha", D "Gamma", E "Drill", F "Drill" — inserted in order."""
    names = ["beta", "Alpha", "alpha", "Gamma", "Drill", "Drill"]
    ms = [mk(db, f1, section, name=n) for n in names]
    ids = [m.id for m in ms]
    assert ids == sorted(ids)  # ids ascend with insertion
    return dict(zip("ABCDEF", ids))


@pytest.mark.xfail(strict=True, reason=BUG_343)
def test_wog_r_26__section_ordering(db, w1, f1, s1):
    """WOG-R-26 — section result ordered by lower(name) asc, then id asc.
    Rules: R5a [BUG-343]."""
    x = _ordering_machines(db, f1, s1)
    t = template(default_factory_section_id=s1.id)
    assert call(db, t, w1) == [x["B"], x["C"], x["A"], x["E"], x["F"], x["D"]]


def test_wog_r_27__section_1000_machines(db, w1, f1, s1):
    """WOG-R-27 — 1000 machines in section -> all 1000 ids.
    Rules: R5b."""
    ids = mk_bulk(db, f1, 1000, s1)
    t = template(default_factory_section_id=s1.id)
    result = call(db, t, w1)
    assert len(result) == 1000
    assert_set_equals(result, ids)


@pytest.mark.xfail(strict=True, reason=BUG_342)
def test_wog_r_28__section_1001_machines(db, w1, f1, s1):
    """WOG-R-28 — 1001 machines in section -> all 1001 ids (no cap).
    Rules: R5b [BUG-342]."""
    ids = mk_bulk(db, f1, 1001, s1)
    t = template(default_factory_section_id=s1.id)
    result = call(db, t, w1)
    assert len(result) == 1001
    assert_set_equals(result, ids)


# --------------------------------------------------------------------------- #
# Factory path (no default machine, no section)
# --------------------------------------------------------------------------- #


def test_wog_r_29__factory_machines(db, w1, f1, f2, s1):
    """WOG-R-29 — factory path returns assigned and unassigned machines of F1 only.
    Rules: R7, R9."""
    m1 = mk(db, f1, s1)
    m4 = mk(db, f1)
    mk(db, f2)
    t = template()
    result = call(db, t, w1, factory_id=f1.id)
    assert_set_equals(result, [m1.id, m4.id])
    assert_no_pending(db)


def test_wog_r_30__factory_soft_delete_and_inactive(db, w1, f1):
    """WOG-R-30 — deleted excluded, inactive-not-deleted included.
    Rules: R7, R5."""
    m1 = mk(db, f1)
    mk(db, f1, is_deleted=True)
    m3 = mk(db, f1, is_active=False, is_deleted=False)
    assert_set_equals(call(db, template(), w1, factory_id=f1.id), [m1.id, m3.id])


def test_wog_r_31__empty_factory(db, w1, f1, f2):
    """WOG-R-31 — factory without machines -> [].
    Rules: R7."""
    mk(db, f1)
    assert call(db, template(), w1, factory_id=f2.id) == []


def test_wog_r_32__factory_only_deleted_machine(db, w1, f1, f2):
    """WOG-R-32 — factory whose only machine is deleted -> [].
    Rules: R7, R5."""
    mk(db, f2, is_deleted=True)
    mk(db, f1)
    assert call(db, template(), w1, factory_id=f2.id) == []


def test_wog_r_33__factory_of_other_workspace(db, w1, f3):
    """WOG-R-33 — W2's factory queried with W1 -> [].
    Rules: R7."""
    mk(db, f3)
    mk(db, f3)
    assert call(db, template(), w1, factory_id=f3.id) == []


def test_wog_r_34__factory_no_duplicates(db, w1, f1, s1):
    """WOG-R-34 — three machines, each once.
    Rules: R9."""
    m1 = mk(db, f1, s1)
    m2 = mk(db, f1)
    m3 = mk(db, f1)
    result = call(db, template(), w1, factory_id=f1.id)
    assert len(result) == 3
    assert len(set(result)) == 3
    assert_set_equals(result, [m1.id, m2.id, m3.id])


@pytest.mark.xfail(strict=True, reason=BUG_343)
def test_wog_r_35__factory_ordering(db, w1, f1):
    """WOG-R-35 — factory result ordered by lower(name) asc, then id asc.
    Rules: R5a [BUG-343], R7."""
    x = _ordering_machines(db, f1)
    assert call(db, template(), w1, factory_id=f1.id) == [x["B"], x["C"], x["A"], x["E"], x["F"], x["D"]]


def test_wog_r_36__factory_1000_machines(db, w1, f1):
    """WOG-R-36 — 1000 machines in factory -> all 1000 ids.
    Rules: R5b, R7."""
    ids = mk_bulk(db, f1, 1000)
    result = call(db, template(), w1, factory_id=f1.id)
    assert len(result) == 1000
    assert_set_equals(result, ids)


@pytest.mark.xfail(strict=True, reason=BUG_342)
def test_wog_r_37__factory_1001_machines(db, w1, f1):
    """WOG-R-37 — 1001 machines in factory -> all 1001 ids (no cap).
    Rules: R5b [BUG-342], R7."""
    ids = mk_bulk(db, f1, 1001)
    result = call(db, template(), w1, factory_id=f1.id)
    assert len(result) == 1001
    assert_set_equals(result, ids)


# --------------------------------------------------------------------------- #
# Nothing set
# --------------------------------------------------------------------------- #


def test_wog_r_38__nothing_set_returns_empty(db, w1, f1, s1):
    """WOG-R-38 — no default machine, no section, no factory -> [].
    Rules: R8."""
    mk(db, f1, s1)
    mk(db, f1)
    t = template()
    result = resolve_template_machine_ids(
        db, template=t, workspace_id=w1.id, factory_section_id=None, factory_id=None,
    )
    assert result == []
    assert_no_pending(db)
