"""Unit tests for app/services/base_service.py.

Implements tests/unit/services/base_service.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture): a `commit()` only releases a
savepoint, so the commits under test are safe and the fixture's outer rollback
discards everything. Nothing is patched except the session methods the
Conventions name (failing commit, failing rollback, spies).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models.workspace import Workspace
from app.services.base_service import BaseService
from tests.unit.factories import make_subscription_plan, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> actors
# --------------------------------------------------------------------------- #

# Convention "svc = BaseService()"
svc = BaseService()


# --------------------------------------------------------------------------- #
# Conventions -> Given rows and named checks
# --------------------------------------------------------------------------- #

# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "found(name)": a fresh count query by workspace name
def found(db, name):
    return db.scalar(select(func.count()).select_from(Workspace).where(Workspace.name == name))


# Convention "session: usable"
def usable(db):
    row = make_workspace(db, name="After")
    return row.id is not None


# --------------------------------------------------------------------------- #
# BaseService._commit_transaction
# --------------------------------------------------------------------------- #

# [claude] BSV-C-01
def test_bsv_c_01__added_flushed_and_edited_changes_are_all_committed(db):
    """BSV-C-01 — added, flushed and edited changes are all committed.
    Rules: B1"""
    p = make_subscription_plan(db)
    m = make_workspace(db, name="Before")
    commit_point(db)
    m.name = "Edited"
    make_workspace(db, name="Flushed")
    n = Workspace(name="Added", slug=f"bsv-added-{p.id}", subscription_plan_id=p.id)
    db.add(n)
    result = svc._commit_transaction(db)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert found(db, "Flushed") == 1
    # Then 3
    assert found(db, "Added") == 1
    # Then 4
    assert found(db, "Edited") == 1
    # Then 5
    assert found(db, "Before") == 0


# [claude] BSV-C-02
def test_bsv_c_02__a_failing_commit_rolls_back_once_and_re_raises_the_same_exception(db):
    """BSV-C-02 — a failing commit rolls back once and re-raises the same exception.
    Rules: B2; Errors row 1"""
    m = make_workspace(db, name="Before")
    commit_point(db)
    m.name = "Edited"
    db.flush()
    make_workspace(db, name="Pending")
    e1 = RuntimeError("boom")
    # Then 1
    with pytest.raises(type(e1)) as exc:
        with patch.object(db, "commit", side_effect=e1), patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc._commit_transaction(db)
    assert exc.value is e1
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert found(db, "Pending") == 0
    # Then 4
    assert found(db, "Edited") == 0
    # Then 5
    assert found(db, "Before") == 1


# [claude] BSV-C-03
def test_bsv_c_03__after_a_failed_commit_the_session_is_usable(db):
    """BSV-C-03 — after a failed commit the session is usable.
    Rules: B2"""
    commit_point(db)
    make_workspace(db, name="Pending")
    e1 = RuntimeError("boom")
    # Then 1
    with pytest.raises(type(e1)) as exc:
        with patch.object(db, "commit", side_effect=e1), patch.object(db, "rollback", wraps=db.rollback):
            svc._commit_transaction(db)
    assert str(exc.value) == "boom"
    # Then 2
    assert found(db, "Pending") == 0
    # Then 3
    assert usable(db)
    # Then 4
    assert found(db, "After") == 1


# [claude] BSV-C-04
def test_bsv_c_04__commit_and_rollback_both_fail_the_rollbacks_exception_wins(db):
    """BSV-C-04 — commit and rollback both fail: the rollback's exception wins, the commit's is its context.
    Rules: B3; Errors row 2"""
    commit_point(db)
    make_workspace(db, name="Pending")
    e1 = RuntimeError("boom")
    e2 = ValueError("rb")
    # Then 1
    with pytest.raises(ValueError) as exc:
        with patch.object(db, "commit", side_effect=e1), patch.object(db, "rollback", side_effect=e2):
            svc._commit_transaction(db)
    assert exc.value is e2
    # Then 2
    assert exc.value.__context__ is e1


# [claude] BSV-C-05
def test_bsv_c_05__a_commit_with_nothing_pending_returns_none_and_commits_once(db):
    """BSV-C-05 — a commit with nothing pending returns None and commits once.
    Rules: B4"""
    make_workspace(db, name="Kept")
    commit_point(db)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc._commit_transaction(db)

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 1
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert found(db, "Kept") == 1


# --------------------------------------------------------------------------- #
# BaseService._rollback_transaction
# --------------------------------------------------------------------------- #

# [claude] BSV-R-01
def test_bsv_r_01__flushed_added_and_edited_changes_are_discarded_committed_rows_stay(db):
    """BSV-R-01 — flushed, added and edited changes are discarded; committed rows stay.
    Rules: B5"""
    p = make_subscription_plan(db)
    k = make_workspace(db, name="Kept")
    commit_point(db)
    k.name = "Changed"
    db.flush()
    make_workspace(db, name="Flushed")
    n = Workspace(name="Added", slug=f"bsv-added-{p.id}", subscription_plan_id=p.id)
    db.add(n)
    result = svc._rollback_transaction(db)

    # Then 1
    assert result is None
    # Then 2
    assert found(db, "Flushed") == 0
    # Then 3
    assert found(db, "Added") == 0
    # Then 4
    assert found(db, "Changed") == 0
    # Then 5
    assert found(db, "Kept") == 1


# [claude] BSV-R-02
def test_bsv_r_02__a_rollback_on_a_clean_session_does_nothing_rolls_back_once_never_commits(db):
    """BSV-R-02 — a rollback on a clean session does nothing, rolls back once and never commits.
    Rules: B6"""
    make_workspace(db, name="Kept")
    commit_point(db)
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        result = svc._rollback_transaction(db)

    # Then 1
    assert result is None
    # Then 2
    assert rb.call_count == 1
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert found(db, "Kept") == 1
    # Then 5
    assert usable(db)


# [claude] BSV-R-03
def test_bsv_r_03__a_failing_rollbacks_exception_reaches_the_caller_unchanged(db):
    """BSV-R-03 — a failing rollback's exception reaches the caller unchanged.
    Rules: B7; Errors"""
    commit_point(db)
    e2 = ValueError("rb")
    # Then 1
    with pytest.raises(type(e2)) as exc:
        with patch.object(db, "rollback", side_effect=e2):
            svc._rollback_transaction(db)
    assert exc.value is e2
