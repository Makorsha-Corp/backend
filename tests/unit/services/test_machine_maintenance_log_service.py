"""Unit tests for app/services/machine_maintenance_log_service.py.

Implements tests/unit/services/machine_maintenance_log_service.cases.md
(revision 1), one test per case, in card order. Real Postgres session (`db`
fixture): a `commit()` only releases a savepoint, so the service's commits are
safe and the fixture's outer rollback discards everything. Nothing is patched
except what Conventions name: the failing commit / failing refresh wraps and
the clock patch of MLS-D-04.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (M1 -> m1, A -> a,
`W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.models.enums import MaintenanceTypeEnum
from app.models.factory import Factory
from app.models.machine import Machine
from app.models.machine_activity_event import MachineActivityEvent
from app.models.machine_maintenance_log import MachineMaintenanceLog
from app.schemas.machine_maintenance_log import (
    MachineMaintenanceLogCreate,
    MachineMaintenanceLogUpdate,
)
from app.services.machine_maintenance_log_service import machine_maintenance_log_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton machine_maintenance_log_service"
svc = machine_maintenance_log_service

# Convention "LC, LU"
LC = MachineMaintenanceLogCreate
LU = MachineMaintenanceLogUpdate

# Convention "REPAIR", "OTHER"
REPAIR = MaintenanceTypeEnum.REPAIR
OTHER = next(t for t in MaintenanceTypeEnum if t != REPAIR)

MISSING = 999999999
D1 = date(2026, 3, 1)
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001
NOW = datetime(2031, 5, 6, 7, 8, 9)  # noqa: DTZ001


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows, in Conventions order
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 created every Given log; U2 = the acting user; U3 = an earlier editor
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


@pytest.fixture
def f1(db, w1, u3):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


@pytest.fixture
def fd(db, w1, f1):
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True))


@pytest.fixture
def f9(db, w2, fd):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


@pytest.fixture
def m1(db, w1, f1, f9):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 1"))


@pytest.fixture
def m2(db, w1, f1, m1):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 2"))


@pytest.fixture
def md(db, w1, f1, m2):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 4", is_deleted=True, is_active=False))


@pytest.fixture
def mf(db, w1, fd, md):
    return _add(db, Machine(workspace_id=w1.id, factory_id=fd.id, name="Lost Press"))


@pytest.fixture
def m9(db, w2, f9, mf):
    return _add(db, Machine(workspace_id=w2.id, factory_id=f9.id, name="Far Press"))


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(m9):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "gone" (after "but")
def gone(u1):
    return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": u1.id}


def _log_fields(w1, m1, u1, but):
    fields = {
        "workspace_id": w1.id, "machine_id": m1.id, "maintenance_type": REPAIR, "maintenance_date": D1,
        "summary": "Bearing change", "created_by": u1.id,
    }
    fields.update(but)
    return fields


# Convention "log": one row, flushed, then db.refresh(row)
@pytest.fixture
def mk_log(db, w1, m1, u1):
    def _mk(**but):
        row = _add(db, MachineMaintenanceLog(**_log_fields(w1, m1, u1, but)))
        db.refresh(row)
        return row
    return _mk


# Convention "bulk101"
@pytest.fixture
def bulk101(db, w1, m1, u1):
    def _bulk():
        rows = [
            MachineMaintenanceLog(**_log_fields(w1, m1, u1, {"maintenance_date": date(2025, 1, 1) + timedelta(days=k)}))
            for k in range(101)
        ]
        db.add_all(rows)
        db.flush()
    return _bulk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(MachineMaintenanceLog).where(MachineMaintenanceLog.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = MachineMaintenanceLog.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


# Convention "count:" lines on machine_maintenance_logs (all workspaces), with the filter stated
def count_logs(db, **filters):
    query = select(func.count()).select_from(MachineMaintenanceLog)
    for column, value in filters.items():
        query = query.where(getattr(MachineMaintenanceLog, column) == value)
    return db.execute(query).scalar_one()


def count_events(db):
    return db.execute(select(func.count()).select_from(MachineActivityEvent)).scalar_one()


# Convention "nothing written": logs and activity events, all workspaces
def written(db):
    return {"machine_maintenance_logs": count_logs(db), "machine_activity_events": count_events(db)}


# Convention "events_of(M)"
def events_of(db, machine):
    machine_id = _id_of(machine)
    db.expire_all()
    query = select(MachineActivityEvent).where(MachineActivityEvent.machine_id == machine_id)
    return list(db.execute(query.order_by(MachineActivityEvent.id)).scalars())


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogService.create_log
# --------------------------------------------------------------------------- #

# [claude] MLS-C-01
def test_mls_c_01__a_new_log_and_its_entry_are_committed_the_log_is_returned_re_read(db, w1, u2, m1):
    """MLS-C-01 — a new log and its entry are committed; the log is returned re-read.
    Rules: `create_log` R1, Returns; TC1, TC2"""
    commit_point(db)
    result = svc.create_log(
        db,
        log_in=LC(
            machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change",
            cost=Decimal("5.5"), performed_by="Rahim",
        ),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert "cost" not in unloaded(result)
    assert "created_at" not in unloaded(result)
    assert "summary" not in unloaded(result)
    # Then 2
    assert isinstance(result, MachineMaintenanceLog)
    # Then 3
    assert str(result.cost) == "5.50"
    # Then 4
    assert result.created_by == u2.id
    assert result.created_at is not None
    # Then 5
    result_id = result.id
    db.rollback()
    row = db.execute(select(MachineMaintenanceLog).where(MachineMaintenanceLog.id == result_id)).scalar_one_or_none()
    assert row is not None
    assert row.machine_id == m1.id
    assert row.summary == "Bearing change"
    assert row.cost == Decimal("5.50")
    assert row.created_by == u2.id
    # Then 6
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 7
    assert rows[0].event_type == "maintenance_logged"
    assert rows[0].performed_by == u2.id
    assert rows[0].workspace_id == w1.id


# [claude] MLS-C-02
def test_mls_c_02__another_workspaces_machine_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u2, m9, mk_log,
):
    """MLS-C-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back.
    Rules: `create_log` R2, Errors; TC3"""
    mk_log()
    commit_point(db)
    before = written(db)
    mk_log(summary="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_log(
            db, log_in=LC(machine_id=m9.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Machine with ID {m9.id} not found"
    # Then 4
    assert count_logs(db, summary="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert len(events_of(db, m9)) == 0
    # Then 7
    assert usable(db)


# [claude] MLS-C-03
def test_mls_c_03__a_deleted_machine_the_400_passes_unchanged_nothing_saved(db, w1, u2, md):
    """MLS-C-03 — a deleted machine: the 400 passes unchanged, nothing saved.
    Rules: `create_log` R2, Errors"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_log(
            db, log_in=LC(machine_id=md.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MLS-C-04
def test_mls_c_04__a_dataerror_at_the_flush_passes_unchanged_nothing_saved_the_session_is_usable(
    db, w1, u2, m1, mk_log,
):
    """MLS-C-04 — a DataError at the flush passes unchanged; nothing saved; the session is usable.
    Rules: `create_log` R3, Errors; TC3"""
    mk_log()
    data = LC.model_construct(
        machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Long name", cost=None,
        performed_by="x" * 256,
    )
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(DataError) as exc:
        svc.create_log(db, log_in=data, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert count_logs(db, summary="Long name") == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# [claude] MLS-C-05
def test_mls_c_05__a_failing_commit_is_rolled_back_and_re_raised_neither_the_log_nor_the_entry_is_saved(
    db, w1, u2, m1,
):
    """MLS-C-05 — a failing commit is rolled back and re-raised: neither the log nor the entry is saved.
    Rules: `create_log` R4; TC4"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_log(
                db, log_in=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"),
                workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_logs(db) == 0
    # Then 4
    assert len(events_of(db, m1)) == 0


# [claude] MLS-C-06
def test_mls_c_06__a_failing_re_read_after_the_commit_leaves_the_log_and_its_entry_saved(db, w1, u2, m1):
    """MLS-C-06 — a failing re-read after the commit leaves the log and its entry saved.
    Rules: `create_log` R4; TC5"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_log(
                db, log_in=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"),
                workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_logs(db, summary="Bearing change") == 1
    # Then 3
    assert len(events_of(db, m1)) == 1


# [claude] MLS-C-07
@pytest.mark.xfail(strict=True, reason="BUG-1154: A maintenance log can be added to a machine of a soft-deleted factory")
def test_mls_c_07__pass_through_bug_1154_a_live_machine_in_a_soft_deleted_factory_is_refused(db, w1, u2, mf):
    """MLS-C-07 — pass-through BUG-1154: a live machine in a soft-deleted factory is refused.
    Rules: `create_log` R2 [BUG-1154]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_log(
            db, log_in=LC(machine_id=mf.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot create maintenance log for a deleted machine"
    # Then 4
    assert written(db) == before


# [claude] MLS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-1155: Blank maintenance log summaries accepted; stored untrimmed")
def test_mls_c_08__pass_through_bug_1155_a_padded_summary_is_stored_trimmed(db, w1, u2, m1):
    """MLS-C-08 — pass-through BUG-1155: a padded summary is stored trimmed.
    Rules: `create_log` R1 [BUG-1155]"""
    commit_point(db)
    result = svc.create_log(
        db, log_in=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  "),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(MachineMaintenanceLog).where(MachineMaintenanceLog.id == result_id)).scalar_one()
    assert row.summary == "pad"


# [claude] MLS-C-09
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1156: Maintenance log `performed_by` untrimmed, blank counts as a value, over-long crashes",
)
def test_mls_c_09__pass_through_bug_1156_a_padded_performed_by_is_stored_trimmed(db, w1, u2, m1):
    """MLS-C-09 — pass-through BUG-1156: a padded performed_by is stored trimmed.
    Rules: `create_log` R1 [BUG-1156]"""
    commit_point(db)
    result = svc.create_log(
        db,
        log_in=LC(
            machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change",
            performed_by="  Rahim  ",
        ),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    result_id = result.id
    db.rollback()
    row = db.execute(select(MachineMaintenanceLog).where(MachineMaintenanceLog.id == result_id)).scalar_one()
    assert row.performed_by == "Rahim"


# [claude] MLS-C-10
@pytest.mark.xfail(strict=True, reason="BUG-1158: Negative maintenance log cost accepted")
def test_mls_c_10__pass_through_bug_1158_a_negative_cost_is_refused_by_the_schema(db, m1):
    """MLS-C-10 — pass-through BUG-1158: a negative cost is refused by the schema.
    Rules: `create_log` R1 [BUG-1158]"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(ValidationError):
        LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-5"))  # noqa: FURB157 (as the card writes it)
    # Then 2
    assert written(db) == before


# [claude] MLS-C-11
def test_mls_c_11__an_unknown_user_the_integrityerror_passes_unchanged_nothing_saved_the_session_is_usable(
    db, w1, m1, mk_log,
):
    """MLS-C-11 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable.
    Rules: `create_log` R3, Errors; TC3"""
    mk_log()
    commit_point(db)
    before = written(db)
    mk_log(summary="Extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_log(
            db, log_in=LC(machine_id=m1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Ghost"),
            workspace_id=w1.id, user_id=MISSING,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_logs(db, summary="Ghost") == 0
    # Then 4
    assert count_logs(db, summary="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogService.update_log
# --------------------------------------------------------------------------- #

# [claude] MLS-U-01
def test_mls_u_01__a_change_and_its_entry_are_committed_the_log_is_returned_re_read(db, w1, u2, m1, mk_log):
    """MLS-U-01 — a change and its entry are committed; the log is returned re-read.
    Rules: `update_log` R1, Returns; TC1, TC2"""
    a = mk_log()
    commit_point(db)
    result = svc.update_log(db, log_id=a.id, log_in=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert "summary" not in unloaded(result)
    assert "updated_at" not in unloaded(result)
    assert "updated_by" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.summary == "New text"
    assert result.updated_by == u2.id
    assert result.updated_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.summary == "New text"
    assert row.updated_by == u2.id
    # Then 5
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].event_type == "maintenance_updated"
    assert rows[0].performed_by == u2.id


# [claude] MLS-U-02
def test_mls_u_02__another_workspaces_log_the_404_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, w2, u2, m9, mk_log,
):
    """MLS-U-02 — another workspace's log: the 404 passes unchanged and the session is rolled back.
    Rules: `update_log` R2, Errors; TC3"""
    mk_log()
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)
    commit_point(db)
    before_z = snap_before(db, z)
    before = written(db)
    mk_log(summary="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_log(db, log_id=z.id, log_in=LU(summary="Hacked"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {z.id} not found"
    # Then 4
    assert count_logs(db, summary="Extra") == 0
    # Then 5
    assert snap(db, z) == before_z
    # Then 6
    assert written(db) == before


# [claude] MLS-U-03
def test_mls_u_03__a_deleted_log_the_400_passes_unchanged_nothing_saved(db, w1, u1, u2, mk_log):
    """MLS-U-03 — a deleted log: the 400 passes unchanged, nothing saved.
    Rules: `update_log` R2, Errors"""
    a = mk_log(**gone(u1))
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_log(db, log_id=a.id, log_in=LU(summary="New text"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Cannot update a deleted maintenance log"
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert written(db) == before


# [claude] MLS-U-04
@pytest.mark.xfail(strict=True, reason="BUG-1151: `updated_by` stamped on no-op maintenance log updates")
def test_mls_u_04__pass_through_bug_1151_an_empty_body_by_another_user_leaves_the_earlier_stamps(
    db, w1, u2, u3, mk_log,
):
    """MLS-U-04 — pass-through BUG-1151: an empty body by another user leaves the earlier stamps.
    Rules: `update_log` R1 [BUG-1151]"""
    a = mk_log(updated_by=u3.id, updated_at=T0)
    commit_point(db)
    result = svc.update_log(db, log_id=a.id, log_in=LU(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).updated_by == u3.id
    # Then 3
    assert reread(db, a).updated_at == T0


# [claude] MLS-U-05
@pytest.mark.xfail(strict=True, reason="BUG-1153: A maintenance log's cost and performer cannot be cleared")
def test_mls_u_05__pass_through_bug_1153_an_explicit_null_clears_cost(db, w1, u2, mk_log):
    """MLS-U-05 — pass-through BUG-1153: an explicit null clears cost.
    Rules: `update_log` R1 [BUG-1153]"""
    a = mk_log(cost=Decimal("5.00"))
    commit_point(db)
    result = svc.update_log(db, log_id=a.id, log_in=LU(cost=None), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).cost is None


# [claude] MLS-U-06
@pytest.mark.xfail(
    strict=True,
    reason="BUG-1157: Maintenance log `cost` with too many digits or decimals accepted; "
    "the activity entry records it as typed",
)
def test_mls_u_06__pass_through_bug_1157_the_entry_records_cost_in_its_stored_form(db, w1, u2, m1, mk_log):
    """MLS-U-06 — pass-through BUG-1157: the entry records cost in its stored form.
    Rules: `update_log` R1 [BUG-1157]"""
    a = mk_log(cost=Decimal("5.00"))
    commit_point(db)
    result = svc.update_log(db, log_id=a.id, log_in=LU(cost=Decimal("7")), workspace_id=w1.id, user_id=u2.id)  # noqa: FURB157 (as the card writes it)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    assert reread(db, a).cost == Decimal("7.00")
    # Then 3
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 4
    assert rows[0].metadata_json == {
        "maintenance_log_id": a.id,
        "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.00"}],
    }


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogService.get_log
# --------------------------------------------------------------------------- #

# [claude] MLS-G-01
def test_mls_g_01__a_live_log_of_the_workspace_is_returned_as_the_manager_returns_it(db, w1, mk_log):
    """MLS-G-01 — a live log of the workspace is returned as the manager returns it.
    Rules: `get_log` R1"""
    a = mk_log(cost=Decimal("5.00"), performed_by="Rahim")
    commit_point(db)
    result = svc.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineMaintenanceLog)
    # Then 2
    assert result.id == a.id
    assert result.summary == "Bearing change"
    assert result.cost == Decimal("5.00")


# [claude] MLS-G-02
def test_mls_g_02__another_workspaces_log_the_404_passes_unchanged(db, w1, w2, m9, mk_log):
    """MLS-G-02 — another workspace's log: the 404 passes unchanged.
    Rules: `get_log` R1, Errors"""
    mk_log()
    z = mk_log(workspace_id=w2.id, machine_id=m9.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_log(db, log_id=z.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {z.id} not found"


# [claude] MLS-G-03
@pytest.mark.xfail(strict=True, reason="BUG-1150: `get_log` returns soft-deleted maintenance logs")
def test_mls_g_03__a_soft_deleted_log_is_hidden_by_default(db, w1, u1, mk_log):
    """MLS-G-03 — a soft-deleted log is hidden by default.
    Rules: `get_log` R2 [BUG-1150], Errors"""
    a = mk_log(**gone(u1))
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_log(db, log_id=a.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {a.id} not found"


# [claude] MLS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-1150: `get_log` returns soft-deleted maintenance logs")
def test_mls_g_04__include_deleted_true_returns_a_soft_deleted_log(db, w1, u1, mk_log):
    """MLS-G-04 — include_deleted=True returns a soft-deleted log.
    Rules: `get_log` R3 [BUG-1150]"""
    a = mk_log(**gone(u1))
    commit_point(db)
    result = svc.get_log(db, log_id=a.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert result.is_deleted is True


# [claude] MLS-G-05
@pytest.mark.xfail(
    strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id",
)
def test_mls_g_05__pass_through_bug_1101_a_log_on_another_workspaces_machine_gets_the_404(db, w1, m9, mk_log):
    """MLS-G-05 — pass-through BUG-1101: a log on another workspace's machine gets the 404.
    Rules: `get_log` R1 [BUG-1101]"""
    x = mk_log(machine_id=m9.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.get_log(db, log_id=x.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Maintenance log with ID {x.id} not found"


# [claude] MLS-G-06
def test_mls_g_06__the_read_neither_commits_nor_rolls_back(db, w1, mk_log):
    """MLS-G-06 — the read neither commits nor rolls back.
    Rules: `get_log` R4; TC6"""
    a = mk_log()
    b = mk_log(summary="Oil change")
    commit_point(db)
    mk_log(summary="Pending")
    b.summary = "Edited"
    result = svc.get_log(db, log_id=a.id, workspace_id=w1.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_logs(db, summary="Pending") == 1
    # Then 5
    db.rollback()
    assert count_logs(db, summary="Pending") == 0
    # Then 6
    assert reread(db, b).summary == "Oil change"


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogService.list_logs
# --------------------------------------------------------------------------- #

# [claude] MLS-L-01
def test_mls_l_01__machine_id_reaches_the_manager(db, w1, w2, m1, m2, m9, mk_log):
    """MLS-L-01 — machine_id reaches the manager.
    Rules: `list_logs` R1"""
    a = mk_log()
    mk_log(machine_id=m2.id)
    mk_log(workspace_id=w2.id, machine_id=m9.id)
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] MLS-L-02
def test_mls_l_02__maintenance_type_reaches_the_manager(db, w1, mk_log):
    """MLS-L-02 — maintenance_type reaches the manager.
    Rules: `list_logs` R1"""
    mk_log()
    b = mk_log(maintenance_type=OTHER)
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id, maintenance_type=OTHER)

    # Then 1
    assert ids(result) == [b.id]


# [claude] MLS-L-03
def test_mls_l_03__with_the_defaults_101_logs_give_100(db, w1, bulk101):
    """MLS-L-03 — with the defaults 101 logs give 100.
    Rules: `list_logs` R1"""
    bulk101()
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] MLS-L-04
def test_mls_l_04__limit_1000_reaches_the_manager_and_gives_all_101(db, w1, bulk101):
    """MLS-L-04 — limit=1000 reaches the manager and gives all 101.
    Rules: `list_logs` R1"""
    bulk101()
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 101


# [claude] MLS-L-05
def test_mls_l_05__skip_reaches_the_manager(db, w1, bulk101):
    """MLS-L-05 — skip reaches the manager.
    Rules: `list_logs` R1"""
    bulk101()
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id, skip=100)

    # Then 1
    assert len(result) == 1


# [claude] MLS-L-06
def test_mls_l_06__the_list_neither_commits_nor_rolls_back(db, w1, w2, m9, mk_log):
    """MLS-L-06 — the list neither commits nor rolls back.
    Rules: `list_logs` R2; TC6"""
    a = mk_log()
    b = mk_log(workspace_id=w2.id, machine_id=m9.id)
    commit_point(db)
    p = mk_log(summary="Pending")
    b.summary = "Edited"
    result = svc.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == sorted([a.id, p.id])
    # Then 2
    assert b in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    db.rollback()
    assert count_logs(db, summary="Pending") == 0
    # Then 5
    assert reread(db, b).summary == "Bearing change"


# [claude] MLS-L-07
@pytest.mark.xfail(strict=True, reason="BUG-1152: `machine_id=0` lists the whole workspace's maintenance logs")
def test_mls_l_07__pass_through_bug_1152_machine_id_0_returns_nothing(db, w1, mk_log):
    """MLS-L-07 — pass-through BUG-1152: machine_id=0 returns nothing.
    Rules: `list_logs` R1 [BUG-1152]"""
    mk_log()
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id, machine_id=0)

    # Then 1
    assert result == []


# [claude] MLS-L-08
@pytest.mark.xfail(strict=False, reason="BUG-1100: Maintenance logs on the same date have no order")
def test_mls_l_08__pass_through_bug_1100_logs_on_one_date_come_back_highest_id_first(db, w1, mk_log):
    """MLS-L-08 — pass-through BUG-1100: logs on one date come back highest id first.
    Rules: `list_logs` R1 [BUG-1100]"""
    a = mk_log()
    b = mk_log()
    c = mk_log()
    a.summary = "Edited"
    db.flush()
    commit_point(db)
    result = svc.list_logs(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id, b.id, c.id]
    # Then 2
    assert [r.id for r in result] == [c.id, b.id, a.id]


# --------------------------------------------------------------------------- #
# MachineMaintenanceLogService.delete_log
# --------------------------------------------------------------------------- #

# [claude] MLS-D-01
def test_mls_d_01__a_soft_delete_and_its_entry_are_committed_the_log_is_returned_re_read(db, w1, u2, m1, mk_log):
    """MLS-D-01 — a soft delete and its entry are committed; the log is returned re-read.
    Rules: `delete_log` R1, Returns; TC1, TC2"""
    a = mk_log()
    commit_point(db)
    result = svc.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert "is_deleted" not in unloaded(result)
    assert "deleted_at" not in unloaded(result)
    assert "deleted_by" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.is_deleted is True
    assert result.deleted_by == u2.id
    assert result.deleted_at is not None
    # Then 4
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 5
    rows = events_of(db, m1)
    assert len(rows) == 1
    # Then 6
    assert rows[0].event_type == "maintenance_removed"
    assert rows[0].performed_by == u2.id


# [claude] MLS-D-02
def test_mls_d_02__an_already_deleted_log_the_400_passes_unchanged_and_the_session_is_rolled_back(
    db, w1, u1, u2, mk_log,
):
    """MLS-D-02 — an already deleted log: the 400 passes unchanged and the session is rolled back.
    Rules: `delete_log` R2, Errors; TC3"""
    a = mk_log(**gone(u1))
    commit_point(db)
    before_a = snap_before(db, a)
    before = written(db)
    mk_log(summary="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Maintenance log is already deleted"
    # Then 4
    assert count_logs(db, summary="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert written(db) == before
    # Then 7
    assert usable(db)


# [claude] MLS-D-03
def test_mls_d_03__an_unknown_id_the_404_passes_unchanged(db, w1, u2, mk_log):
    """MLS-D-03 — an unknown id: the 404 passes unchanged.
    Rules: `delete_log` R2, Errors"""
    mk_log()
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_log(db, log_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Maintenance log with ID 999999999 not found"
    # Then 4
    assert written(db) == before


# [claude] MLS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-1102: A maintenance log's delete time depends on the database's time zone")
def test_mls_d_04__pass_through_bug_1102_deleted_at_is_the_application_clock(db, w1, u2, mk_log):
    """MLS-D-04 — pass-through BUG-1102: deleted_at is the application clock.
    Rules: `delete_log` R1 [BUG-1102]"""
    a = mk_log()
    commit_point(db)
    with patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW):
        result = svc.delete_log(db, log_id=a.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    row = reread(db, a)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    assert reread(db, a).deleted_at == NOW
