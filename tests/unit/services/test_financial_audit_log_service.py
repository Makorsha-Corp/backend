"""Unit tests for app/services/financial_audit_log_service.py.

Implements tests/unit/services/financial_audit_log_service.cases.md (revision 2),
one test per case, in card order. Real Postgres session (`db` fixture). The
service is six read-only pass-throughs to `financial_audit_log_dao`; nothing is
mocked except the commit / rollback spies (they still call the real method).

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Standing rows are attributes of the namespace `s` (`s.W1`, `s.UB`);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, DTZ001  (Conventions prescribe the nested `with` and naive datetimes)
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.exc import DataError

from app.dao.financial_audit_log import financial_audit_log_dao
from app.models.financial_audit_log import FinancialAuditLog
from app.models.workspace import Workspace
from app.services.financial_audit_log_service import financial_audit_log_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = financial_audit_log_service
dao = financial_audit_log_dao
MISSING = 999999999


def H(k):
    """Convention H(k): 2026-04-01 09:00 + k minutes, naive UTC."""
    return datetime(2026, 4, 1, 9, 0, 0) + timedelta(minutes=k)


def ids(r):
    """Named check ids(r): ids in the order returned."""
    return [row.id for row in r]


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.UA = make_profile(db)
    n.UB = make_profile(db)
    n.UC = make_profile(db)
    return n


# Convention "log"; "but" overrides columns. Flushed one at a time.
def _fields(s, performed_at, **but):
    fields = {
        "workspace_id": s.W1.id,
        "entity_type": "invoice",
        "entity_id": 10,
        "action_type": "updated",
        "performed_by": s.UB.id,
        "performed_at": performed_at,
    }
    fields.update(but)
    return fields


def log(db, s, performed_at, **but):
    row = FinancialAuditLog(**_fields(s, performed_at, **but))
    db.add(row)
    db.flush()
    return row


# Given "n logs E1 ... En, built with add_all and one flush: Ek = log, performed_at H(k)"
def many_logs(db, s, n):
    rows = [FinancialAuditLog(**_fields(s, H(k))) for k in range(1, n + 1)]
    db.add_all(rows)
    db.flush()
    return rows


# Convention "X": a pending row of another table, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Convention "spies"
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(
        db, "rollback", wraps=db.rollback
    ) as rb:
        yield cm, rb


# --------------------------------------------------------------------------- #
# get_recent_logs
# --------------------------------------------------------------------------- #


# [claude] FALS-R-01
def test_fals_r_01__recent_newest_first_as_dao(db, s):
    """FALS-R-01 — returns the workspace's latest rows, newest first, as the DAO does.
    Rules: get_recent_logs R1."""
    log(db, s, H(30), workspace_id=s.W0.id)
    a = log(db, s, H(10))
    b = log(
        db, s, H(20), entity_type="payment", entity_id=7, action_type="voided",
        performed_by=s.UA.id,
    )
    log(db, s, H(40), workspace_id=s.W2.id)

    result = svc.get_recent_logs(db, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert ids(result) == ids(dao.get_recent_logs(db, workspace_id=s.W1.id))
    # Then 4
    assert isinstance(result[0], FinancialAuditLog)


# [claude] FALS-R-02
def test_fals_r_02__limit_passed_on(db, s):
    """FALS-R-02 — limit is passed on.
    Rules: get_recent_logs R1."""
    log(db, s, H(10))
    b = log(db, s, H(20))
    c = log(db, s, H(30))

    result = svc.get_recent_logs(db, workspace_id=s.W1.id, limit=2)

    # Then 1
    assert ids(result) == [c.id, b.id]


# [claude] FALS-R-03
def test_fals_r_03__default_limit_50_no_commit(db, s):
    """FALS-R-03 — with no limit, 51 rows give the newest 50; the read neither commits nor rolls back.
    Rules: get_recent_logs R1, R2."""
    rows = many_logs(db, s, 51)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_recent_logs(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 50
    # Then 2
    assert ids(result) == newest[:50]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None


# [claude] FALS-R-04
def test_fals_r_04__limit_zero_empty(db, s):
    """FALS-R-04 — limit=0 is passed on and returns an empty list.
    Rules: get_recent_logs R1."""
    log(db, s, H(10))

    result = svc.get_recent_logs(db, workspace_id=s.W1.id, limit=0)

    # Then 1
    assert result == []


# [claude] FALS-R-05
def test_fals_r_05__negative_limit_data_error(db, s):
    """FALS-R-05 — a negative limit: the DAO's DataError reaches the caller, no rollback by the service.
    Rules: get_recent_logs R1, R2."""
    log(db, s, H(10))
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(DataError) as exc:
            with db.begin_nested():
                svc.get_recent_logs(db, workspace_id=s.W1.id, limit=-1)

    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    db.rollback()
    assert db.get(Workspace, x_id) is None


# [claude] FALS-R-06
def test_fals_r_06__limit_above_default_passed_on(db, s):
    """FALS-R-06 — a limit above the default is passed on: 52 rows with limit=51 give the newest 51.
    Rules: get_recent_logs R1."""
    rows = many_logs(db, s, 52)
    newest = [r.id for r in reversed(rows)]

    result = svc.get_recent_logs(db, workspace_id=s.W1.id, limit=51)

    # Then 1
    assert len(result) == 51
    # Then 2
    assert ids(result) == newest[:51]


# --------------------------------------------------------------------------- #
# get_by_entity
# --------------------------------------------------------------------------- #


# [claude] FALS-E-01
def test_fals_e_01__entity_rows_as_dao(db, s):
    """FALS-E-01 — returns the rows of that entity in the workspace, newest first, as the DAO does.
    Rules: get_by_entity R1."""
    log(db, s, H(50), workspace_id=s.W0.id)
    a = log(db, s, H(10))
    log(db, s, H(60), entity_id=9)
    b = log(db, s, H(20), action_type="status_changed")
    log(db, s, H(70), entity_type="payment")
    log(db, s, H(80), workspace_id=s.W2.id)

    result = svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert ids(result) == ids(
        dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id)
    )


# [claude] FALS-E-02
def test_fals_e_02__skip_limit_positional(db, s):
    """FALS-E-02 — skip and limit are passed on; positional arguments work.
    Rules: get_by_entity R1; Facts (positional-or-keyword)."""
    log(db, s, H(10))
    b = log(db, s, H(20))
    log(db, s, H(30))

    result = svc.get_by_entity(db, "invoice", 10, s.W1.id, 1, 1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] FALS-E-03
def test_fals_e_03__default_limit_100_no_commit(db, s):
    """FALS-E-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back.
    Rules: get_by_entity R1, R2."""
    rows = many_logs(db, s, 101)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None


# [claude] FALS-E-04
def test_fals_e_04__negative_skip_data_error(db, s):
    """FALS-E-04 — a negative skip: the DAO's DataError reaches the caller, no rollback by the service.
    Rules: get_by_entity R2."""
    log(db, s, H(10))
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        # Then 1
        with pytest.raises(DataError) as exc:
            with db.begin_nested():
                svc.get_by_entity(
                    db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id, skip=-1
                )

    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    db.rollback()
    assert db.get(Workspace, x_id) is None


# [claude] FALS-E-05
def test_fals_e_05__limit_above_default_passed_on(db, s):
    """FALS-E-05 — a limit above the default is passed on: 102 rows with limit=101 give the newest 101.
    Rules: get_by_entity R1."""
    rows = many_logs(db, s, 102)
    newest = [r.id for r in reversed(rows)]

    result = svc.get_by_entity(
        db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id, limit=101
    )

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == newest[:101]


# --------------------------------------------------------------------------- #
# get_related_logs
# --------------------------------------------------------------------------- #


# [claude] FALS-L-01
def test_fals_l_01__related_rows_as_dao(db, s):
    """FALS-L-01 — returns the entity's rows and the rows related to it, in the workspace, as the DAO does.
    Rules: get_related_logs R1."""
    log(
        db, s, H(50), workspace_id=s.W0.id, entity_type="payment", entity_id=3,
        related_entity_type="invoice", related_entity_id=10,
    )
    a = log(db, s, H(10))
    p = log(
        db, s, H(20), entity_type="payment", entity_id=3, action_type="created",
        related_entity_type="invoice", related_entity_id=10,
    )
    log(db, s, H(60), entity_type="payment", entity_id=10)
    log(db, s, H(70), workspace_id=s.W2.id)

    result = svc.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [p.id, a.id]
    # Then 3
    assert ids(result) == ids(
        dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id)
    )


# [claude] FALS-L-02
def test_fals_l_02__skip_limit_passed_on(db, s):
    """FALS-L-02 — skip and limit are passed on.
    Rules: get_related_logs R1."""
    log(db, s, H(10))
    b = log(
        db, s, H(20), entity_type="payment", entity_id=3,
        related_entity_type="invoice", related_entity_id=10,
    )
    log(db, s, H(30))

    result = svc.get_related_logs(
        db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] FALS-L-03
def test_fals_l_03__default_limit_100_no_commit(db, s):
    """FALS-L-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back.
    Rules: get_related_logs R1, R2."""
    rows = many_logs(db, s, 101)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_related_logs(
            db, entity_type="invoice", entity_id=10, workspace_id=s.W1.id
        )

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None


# --------------------------------------------------------------------------- #
# get_by_action_type
# --------------------------------------------------------------------------- #


# [claude] FALS-A-01
def test_fals_a_01__action_rows_as_dao(db, s):
    """FALS-A-01 — returns the workspace's rows of that action, newest first, as the DAO does.
    Rules: get_by_action_type R1."""
    log(db, s, H(50), workspace_id=s.W0.id, action_type="voided")
    a = log(db, s, H(10), action_type="voided")
    log(db, s, H(60))
    b = log(db, s, H(20), entity_type="payment", entity_id=3, action_type="voided")
    log(db, s, H(70), workspace_id=s.W2.id, action_type="voided")

    result = svc.get_by_action_type(db, action_type="voided", workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert ids(result) == ids(
        dao.get_by_action_type(db, action_type="voided", workspace_id=s.W1.id)
    )


# [claude] FALS-A-02
def test_fals_a_02__skip_limit_passed_on(db, s):
    """FALS-A-02 — skip and limit are passed on.
    Rules: get_by_action_type R1."""
    log(db, s, H(10))
    b = log(db, s, H(20))
    log(db, s, H(30))

    result = svc.get_by_action_type(
        db, action_type="updated", workspace_id=s.W1.id, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] FALS-A-03
def test_fals_a_03__default_limit_100_no_commit(db, s):
    """FALS-A-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back.
    Rules: get_by_action_type R1, R2."""
    rows = many_logs(db, s, 101)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_action_type(db, action_type="updated", workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None


# --------------------------------------------------------------------------- #
# get_by_user
# --------------------------------------------------------------------------- #


# [claude] FALS-U-01
def test_fals_u_01__user_rows_as_dao(db, s):
    """FALS-U-01 — returns the person's rows in the workspace, newest first, as the DAO does.
    Rules: get_by_user R1."""
    log(db, s, H(50), workspace_id=s.W0.id)
    log(db, s, H(60), performed_by=s.UA.id)
    a = log(db, s, H(10))
    log(db, s, H(70), performed_by=s.UC.id)
    b = log(db, s, H(20), entity_type="account", entity_id=5, action_type="created")
    log(db, s, H(80), workspace_id=s.W2.id)

    result = svc.get_by_user(db, user_id=s.UB.id, workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert ids(result) == ids(dao.get_by_user(db, user_id=s.UB.id, workspace_id=s.W1.id))


# [claude] FALS-U-02
def test_fals_u_02__skip_limit_passed_on(db, s):
    """FALS-U-02 — skip and limit are passed on.
    Rules: get_by_user R1."""
    log(db, s, H(10))
    b = log(db, s, H(20))
    log(db, s, H(30))

    result = svc.get_by_user(db, user_id=s.UB.id, workspace_id=s.W1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] FALS-U-03
def test_fals_u_03__default_limit_100_no_commit(db, s):
    """FALS-U-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back.
    Rules: get_by_user R1, R2."""
    rows = many_logs(db, s, 101)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_user(db, user_id=s.UB.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None


# --------------------------------------------------------------------------- #
# get_by_date_range
# --------------------------------------------------------------------------- #


# [claude] FALS-D-01
def test_fals_d_01__range_inclusive_as_dao(db, s):
    """FALS-D-01 — returns the workspace's rows inside the inclusive range, newest first, as the DAO does.
    Rules: get_by_date_range R1."""
    log(db, s, H(15), workspace_id=s.W0.id)
    log(db, s, H(9))
    a = log(db, s, H(10))
    b = log(db, s, H(20), action_type="created")
    log(db, s, H(21))
    log(db, s, H(16), workspace_id=s.W2.id)

    result = svc.get_by_date_range(db, start_date=H(10), end_date=H(20), workspace_id=s.W1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [b.id, a.id]
    # Then 3
    assert ids(result) == ids(
        dao.get_by_date_range(db, start_date=H(10), end_date=H(20), workspace_id=s.W1.id)
    )


# [claude] FALS-D-02
def test_fals_d_02__start_after_end_empty(db, s):
    """FALS-D-02 — a start after the end is passed on unchecked and returns an empty list.
    Rules: get_by_date_range R1."""
    log(db, s, H(10))
    log(db, s, H(20))

    result = svc.get_by_date_range(db, start_date=H(20), end_date=H(10), workspace_id=s.W1.id)

    # Then 1
    assert result == []


# [claude] FALS-D-03
def test_fals_d_03__skip_limit_passed_on(db, s):
    """FALS-D-03 — skip and limit are passed on.
    Rules: get_by_date_range R1."""
    log(db, s, H(10))
    b = log(db, s, H(20))
    log(db, s, H(30))

    result = svc.get_by_date_range(
        db, start_date=H(0), end_date=H(40), workspace_id=s.W1.id, skip=1, limit=1
    )

    # Then 1
    assert ids(result) == [b.id]


# [claude] FALS-D-04
def test_fals_d_04__default_limit_100_no_commit(db, s):
    """FALS-D-04 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back.
    Rules: get_by_date_range R1, R2."""
    rows = many_logs(db, s, 101)
    newest = [r.id for r in reversed(rows)]
    x, x_id = mk_x(db)

    with spies(db) as (cm, rb):
        result = svc.get_by_date_range(
            db, start_date=H(0), end_date=H(200), workspace_id=s.W1.id
        )

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == newest[:100]
    # Then 3
    assert cm.call_count == 0
    # Then 4
    assert rb.call_count == 0
    # Then 5
    assert x in db
    # Then 6
    assert not db.new and not db.dirty and not db.deleted
    # Then 7
    db.rollback()
    assert db.get(Workspace, x_id) is None
