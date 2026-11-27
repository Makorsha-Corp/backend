"""Unit tests for app/utils/order_workflow_terminal.py.

Implements tests/unit/utils/order_workflow_terminal.cases.md (revision 2),
one test per case. Real Postgres session (`db` fixture) for
`terminal_status_ids_by_workflow`; `is_order_terminal` is pure (no DB).
Nothing is mocked (spec: no externals, no race simulations, time not mocked).
"""
import copy

import pytest
from sqlalchemy import func, select

from app.models.order_workflow import OrderWorkflow
from app.utils.order_workflow_terminal import (
    is_order_terminal,
    terminal_status_ids_by_workflow,
)
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #


# Convention "W1, W2 = two workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "WF-A / WF-B (W1, type 'purchase' / 'sales'), WF-C (W2, 'purchase');
# non-null name; status_sequence stored as the exact JSON value shown".
def make_order_workflow(db, workspace, *, status_sequence, type="purchase", name=None):
    row = OrderWorkflow(
        workspace_id=workspace.id,
        name=name or f"{type} flow",
        type=type,
        status_sequence=status_sequence,
    )
    db.add(row)
    db.flush()
    return row


def wf_a(db, w1, seq):
    return make_order_workflow(db, w1, status_sequence=seq, type="purchase", name="PO flow")


def wf_b(db, w1, seq):
    return make_order_workflow(db, w1, status_sequence=seq, type="sales", name="SO flow")


def wf_c(db, w2, seq):
    return make_order_workflow(db, w2, status_sequence=seq, type="purchase", name="PO flow")


# Convention "MISSING = an id no order_workflows row has (max existing id + 1000)"
def missing_id(db):
    return (db.scalar(select(func.max(OrderWorkflow.id))) or 0) + 1000


def call(db, workspace, ids):
    # Convention: keyword-only call; every T case asserts result is a dict.
    result = terminal_status_ids_by_workflow(db, workspace_id=workspace.id, workflow_ids=ids)
    assert isinstance(result, dict)
    return result


# --------------------------------------------------------------------------- #
# terminal_status_ids_by_workflow
# --------------------------------------------------------------------------- #


def test_owt_t_01__last_element_is_terminal_and_read_only(db, w1):
    """OWT-T-01 — returns {WF-A.id: 14} and leaves the database unchanged.
    Rules: terminal_status_ids_by_workflow R4; Side effects."""
    a = wf_a(db, w1, [11, 12, 13, 14])
    a_id = a.id

    result = call(db, w1, [a_id])

    assert result == {a_id: 14}
    assert type(result[a_id]) is int
    db.expire_all()
    reread = db.get(OrderWorkflow, a_id)
    assert reread.status_sequence == [11, 12, 13, 14]
    assert reread.name == "PO flow"
    assert reread.type == "purchase"
    assert reread.workspace_id == w1.id
    count = db.scalar(
        select(func.count()).select_from(OrderWorkflow).where(OrderWorkflow.workspace_id == w1.id)
    )
    assert count == 1


def test_owt_t_02__empty_ids_returns_empty(db, w1):
    """OWT-T-02 — empty workflow_ids returns {}.
    Rules: terminal_status_ids_by_workflow R1."""
    wf_a(db, w1, [11, 12, 13, 14])
    assert call(db, w1, []) == {}


def test_owt_t_03__only_none_ids_returns_empty(db, w1):
    """OWT-T-03 — workflow_ids of only None returns {}.
    Rules: terminal_status_ids_by_workflow R1."""
    wf_a(db, w1, [11, 12, 13, 14])
    assert call(db, w1, [None, None]) == {}


def test_owt_t_04__none_entries_ignored(db, w1):
    """OWT-T-04 — [None, WF-A.id] resolves WF-A only.
    Rules: terminal_status_ids_by_workflow R2."""
    a = wf_a(db, w1, [11, 12, 13, 14])
    assert call(db, w1, [None, a.id]) == {a.id: 14}


def test_owt_t_05__duplicate_ids_collapse(db, w1):
    """OWT-T-05 — [WF-A.id, WF-A.id] yields one key.
    Rules: terminal_status_ids_by_workflow R3."""
    a = wf_a(db, w1, [11, 12, 13, 14])
    result = call(db, w1, [a.id, a.id])
    assert result == {a.id: 14}
    assert len(result) == 1


def test_owt_t_06__generator_input(db, w1):
    """OWT-T-06 — a generator of ids is accepted (iterated once).
    Rules: terminal_status_ids_by_workflow Inputs."""
    a = wf_a(db, w1, [11, 12, 13, 14])
    assert call(db, w1, (x for x in [None, a.id])) == {a.id: 14}


def test_owt_t_07__other_workspace_workflow_excluded_w1(db, w1, w2):
    """OWT-T-07 — called for W1, WF-C (W2) is absent, no error.
    Rules: terminal_status_ids_by_workflow R5."""
    a = wf_a(db, w1, [1, 2])
    c = wf_c(db, w2, [3, 4])
    result = call(db, w1, [a.id, c.id])
    assert result == {a.id: 2}
    assert c.id not in result


def test_owt_t_08__other_workspace_workflow_excluded_w2(db, w1, w2):
    """OWT-T-08 — called for W2, WF-A (W1) is absent.
    Rules: terminal_status_ids_by_workflow R5."""
    a = wf_a(db, w1, [1, 2])
    c = wf_c(db, w2, [3, 4])
    result = call(db, w2, [a.id, c.id])
    assert result == {c.id: 4}
    assert a.id not in result


def test_owt_t_09__missing_id_absent(db, w1):
    """OWT-T-09 — an id with no row returns {}, no error.
    Rules: terminal_status_ids_by_workflow R6."""
    wf_a(db, w1, [11, 12, 13, 14])
    assert call(db, w1, [missing_id(db)]) == {}


def test_owt_t_10__empty_sequence_absent(db, w1):
    """OWT-T-10 — status_sequence [] returns {}.
    Rules: terminal_status_ids_by_workflow R7."""
    a = wf_a(db, w1, [])
    assert call(db, w1, [a.id]) == {}


def test_owt_t_11__single_element_sequence(db, w1):
    """OWT-T-11 — status_sequence [5] returns {WF-A.id: 5}.
    Rules: terminal_status_ids_by_workflow R4, R7."""
    a = wf_a(db, w1, [5])
    assert call(db, w1, [a.id]) == {a.id: 5}


def test_owt_t_12__json_object_sequence_absent(db, w1):
    """OWT-T-12 — status_sequence JSON object returns {}, no error.
    Rules: terminal_status_ids_by_workflow R8."""
    a = wf_a(db, w1, {"a": 1})
    assert call(db, w1, [a.id]) == {}


def test_owt_t_13__json_string_sequence_absent(db, w1):
    """OWT-T-13 — status_sequence JSON string "14" returns {}, no error.
    Rules: terminal_status_ids_by_workflow R8."""
    a = wf_a(db, w1, "14")
    assert call(db, w1, [a.id]) == {}


def test_owt_t_14__string_last_element_absent(db, w1):
    """OWT-T-14 — last element "14" (string) returns {}.
    Rules: terminal_status_ids_by_workflow R9."""
    a = wf_a(db, w1, [11, "14"])
    assert call(db, w1, [a.id]) == {}


def test_owt_t_15__float_last_element_absent(db, w1):
    """OWT-T-15 — last element 14.0 (JSON float) returns {}.
    Rules: terminal_status_ids_by_workflow R9."""
    a = wf_a(db, w1, [11, 14.0])
    assert call(db, w1, [a.id]) == {}


def test_owt_t_16__null_last_element_absent(db, w1):
    """OWT-T-16 — last element null returns {}.
    Rules: terminal_status_ids_by_workflow R9."""
    a = wf_a(db, w1, [11, None])
    assert call(db, w1, [a.id]) == {}


def test_owt_t_17__boolean_last_element_kept(db, w1):
    """OWT-T-17 — last element true is kept as True (== 1).
    Rules: terminal_status_ids_by_workflow R9 (boolean note)."""
    a = wf_a(db, w1, [11, True])
    result = call(db, w1, [a.id])
    assert list(result.keys()) == [a.id]
    assert result[a.id] is True
    assert result[a.id] == 1


def test_owt_t_18__earlier_elements_may_be_anything(db, w1):
    """OWT-T-18 — ["x", null, 14.5, 14] returns {WF-A.id: 14}.
    Rules: terminal_status_ids_by_workflow R4."""
    a = wf_a(db, w1, ["x", None, 14.5, 14])
    assert call(db, w1, [a.id]) == {a.id: 14}


def test_owt_t_19__mixed_request_resolved_independently(db, w1, w2):
    """OWT-T-19 — WF-A, None, WF-B, WF-C (other ws), MISSING -> two keys.
    Rules: terminal_status_ids_by_workflow R10, R5, R6, R2."""
    a = wf_a(db, w1, [1, 2, 3])
    b = wf_b(db, w1, [4, 5])
    c = wf_c(db, w2, [7, 8])
    result = call(db, w1, [a.id, None, b.id, c.id, missing_id(db)])
    assert result == {a.id: 3, b.id: 5}


def test_owt_t_20__non_qualifying_workflow_skipped(db, w1):
    """OWT-T-20 — WF-A [1,2,3] and WF-B [] -> only WF-A.
    Rules: terminal_status_ids_by_workflow R10, R7."""
    a = wf_a(db, w1, [1, 2, 3])
    b = wf_b(db, w1, [])
    result = call(db, w1, [a.id, b.id])
    assert result == {a.id: 3}
    assert b.id not in result


def test_owt_t_21__only_requested_workflows_returned(db, w1):
    """OWT-T-21 — unrequested WF-B of same workspace not included.
    Rules: terminal_status_ids_by_workflow R11."""
    a = wf_a(db, w1, [1, 2, 3])
    b = wf_b(db, w1, [4, 5])
    result = call(db, w1, [a.id])
    assert result == {a.id: 3}
    assert b.id not in result


# --------------------------------------------------------------------------- #
# is_order_terminal (pure)
# Convention: assert `is True` / `is False` and map equals a pre-call copy.
# --------------------------------------------------------------------------- #


def check(mapping, workflow_id, current_status_id):
    before = copy.deepcopy(mapping)
    result = is_order_terminal(
        workflow_id=workflow_id,
        current_status_id=current_status_id,
        terminal_by_wf=mapping,
    )
    return result, before


def test_owt_o_01__status_equals_terminal():
    """OWT-O-01 — {7: 14}, wf 7, status 14 -> True.
    Rules: is_order_terminal R4."""
    m = {7: 14}
    result, before = check(m, 7, 14)
    assert result is True
    assert m == before == {7: 14}


def test_owt_o_02__status_differs():
    """OWT-O-02 — {7: 14}, wf 7, status 15 -> False.
    Rules: is_order_terminal R5."""
    m = {7: 14}
    result, before = check(m, 7, 15)
    assert result is False
    assert m == before == {7: 14}


def test_owt_o_03__earlier_status_not_terminal():
    """OWT-O-03 — {7: 14}, wf 7, status 11 -> False.
    Rules: is_order_terminal R5."""
    m = {7: 14}
    result, before = check(m, 7, 11)
    assert result is False
    assert m == before


def test_owt_o_04__none_workflow_id_false():
    """OWT-O-04 — {None: 14, 7: 14}, wf None, status 14 -> False.
    Rules: is_order_terminal R1."""
    m = {None: 14, 7: 14}
    result, before = check(m, None, 14)
    assert result is False
    assert m == before


def test_owt_o_05__none_status_false():
    """OWT-O-05 — {7: 14}, wf 7, status None -> False.
    Rules: is_order_terminal R2."""
    m = {7: 14}
    result, before = check(m, 7, None)
    assert result is False
    assert m == before


def test_owt_o_06__none_status_never_matches_none_value():
    """OWT-O-06 — {7: None}, wf 7, status None -> False.
    Rules: is_order_terminal R2, R7."""
    m = {7: None}
    result, before = check(m, 7, None)
    assert result is False
    assert m == before


def test_owt_o_07__workflow_not_in_map():
    """OWT-O-07 — {7: 14}, wf 8, status 14 -> False; no key 8 added.
    Rules: is_order_terminal R3."""
    m = {7: 14}
    result, before = check(m, 8, 14)
    assert result is False
    assert m == before == {7: 14}


def test_owt_o_08__zero_workflow_id_is_valid():
    """OWT-O-08 — {0: 5}, wf 0, status 5 -> True.
    Rules: is_order_terminal R6."""
    m = {0: 5}
    result, before = check(m, 0, 5)
    assert result is True
    assert m == before


def test_owt_o_09__zero_status_id_is_valid():
    """OWT-O-09 — {7: 0}, wf 7, status 0 -> True.
    Rules: is_order_terminal R6."""
    m = {7: 0}
    result, before = check(m, 7, 0)
    assert result is True
    assert m == before


def test_owt_o_10__none_map_value_never_terminal():
    """OWT-O-10 — {7: None}, wf 7, status 14 -> False.
    Rules: is_order_terminal R7."""
    m = {7: None}
    result, before = check(m, 7, 14)
    assert result is False
    assert m == before
