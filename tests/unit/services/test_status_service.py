"""Unit tests for app/services/status_service.py.

Implements tests/unit/services/status_service.cases.md (revision 5), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps and the commit / rollback spies (the
spies still call the real method). The statement recorder only listens.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (S -> s, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
import re
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError

from app.core.exceptions import ValidationError as AppValidationError
from app.models.account import Account
from app.models.factory import Factory
from app.models.order_workflow import OrderWorkflow
from app.models.purchase_order import PurchaseOrder
from app.models.sales_order import SalesOrder
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.schemas.status import StatusCreate, StatusResponse, StatusUpdate
from app.services.status_service import status_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton status_service"
svc = status_service

MISSING = 999999999

BUG_035 = "BUG-035: HIGH — statuses API not scoped by workspace"
BUG_1218 = "BUG-1218: A status in use cannot be deleted, and the answer does not say why"
BUG_1220 = "BUG-1220: Statuses the order workflow depends on can be renamed or deleted"
BUG_1221 = "BUG-1221: Status names are not unique per workspace"
BUG_1680 = "BUG-1680: Status names are stored untrimmed, and blank names are accepted"
BUG_1681 = "BUG-1681: Status list has no display order"
BUG_1880 = "BUG-1880: Stage-status protection matches stage names only in their exact spelling"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors (exist in every test)
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture(autouse=True)
def actors(u1):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "status": "but" lists every column that differs
@pytest.fixture
def mk_status(db, w1):
    def _mk(**but):
        fields = {"workspace_id": w1.id, "name": "Feat", "comment": "A note"}
        fields.update(but)
        return _add(db, Status(**fields))
    return _mk


# Convention "transfer on S"
@pytest.fixture
def mk_transfer(db, w1, u1):
    def _mk(s, **but):
        fields = {
            "workspace_id": w1.id, "transfer_number": "TO-1", "source_location_type": "storage",
            "source_location_id": 1, "destination_location_type": "storage", "destination_location_id": 2,
            "current_status_id": s.id, "created_by": u1.id,
        }
        fields.update(but)
        return _add(db, TransferOrder(**fields))
    return _mk


# Convention "purchase on S"
@pytest.fixture
def mk_purchase(db, w1, u1):
    def _mk(s, **but):
        fields = {
            "workspace_id": w1.id, "po_number": "PO-1", "destination_type": "storage", "destination_id": 1,
            "current_status_id": s.id, "created_by": u1.id,
        }
        fields.update(but)
        return _add(db, PurchaseOrder(**fields))
    return _mk


# Convention "sales on S": AC and FA are built just before it
@pytest.fixture
def mk_sales(db, w1, u1):
    def _mk(s, **but):
        ac = _add(db, Account(workspace_id=w1.id, name="Acme"))
        fa = _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))
        fields = {
            "workspace_id": w1.id, "sales_order_number": "SO-1", "account_id": ac.id, "factory_id": fa.id,
            "current_status_id": s.id, "created_by": u1.id,
        }
        fields.update(but)
        return _add(db, SalesOrder(**fields))
    return _mk


# Convention "workflow on [ids]"
@pytest.fixture
def mk_workflow(db, w1):
    def _mk(ids, **but):
        fields = {"workspace_id": w1.id, "name": "Flow", "type": "PFM", "status_sequence": list(ids)}
        fields.update(but)
        return _add(db, OrderWorkflow(**fields))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# Convention "n_all": statuses of every workspace, taken at the commit point
def n_all_of(db):
    return db.scalar(select(func.count()).select_from(Status))


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X" (any model)
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = Status.__table__
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


# Convention "count:" lines: statuses rows (all workspaces), with the filter stated
def count_statuses(db, **filters):
    query = select(func.count()).select_from(Status)
    for column, value in filters.items():
        query = query.where(getattr(Status, column) == value)
    return db.execute(query).scalar_one()


# Convention "ids(x)" / "idset(x)"
def ids(rows):
    return sorted(r.id for r in rows)


def idset(rows):
    return {r.id for r in rows}


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# Convention "Statement recorder": the statements the session sends during the When
@contextmanager
def record_sql(db):
    connection = db.connection()
    sql_log = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        sql_log.append(statement)

    event.listen(connection, "before_cursor_execute", _record)
    try:
        yield sql_log
    finally:
        event.remove(connection, "before_cursor_execute", _record)


# Convention "sql" = the one SELECT from statuses
def the_select(sql_log):
    [sql] = [s for s in sql_log if s.lstrip().upper().startswith("SELECT") and "statuses" in s]
    return sql


# Convention "order_part" = the text after ORDER BY and before LIMIT ("" when there is none)
def order_part_of(sql):
    if "ORDER BY" not in sql:
        return ""
    after = sql.split("ORDER BY", 1)[1]
    return after.split("LIMIT", 1)[0].strip()


# --------------------------------------------------------------------------- #
# StatusService.get_statuses
# --------------------------------------------------------------------------- #

# [claude] SSV-L-01
def test_ssv_l_01__today_every_workspaces_statuses_are_listed(db, w2, mk_status):
    """SSV-L-01 — today every workspace's statuses are listed (documents BUG-035).
    Rules: `get_statuses` R1 (today), R2"""
    z1 = mk_status(workspace_id=w2.id, name="Early")
    a = mk_status()
    z2 = mk_status(workspace_id=w2.id, name="Late")
    commit_point(db)
    n_all = n_all_of(db)
    result = svc.get_statuses(db, skip=0, limit=n_all)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert {z1.id, a.id, z2.id} <= idset(result)
    # Then 3
    assert len(result) == n_all


# [claude] SSV-L-02
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_l_02__only_the_callers_workspaces_statuses_are_listed(db, w1, w2, mk_status):
    """SSV-L-02 — only the caller's workspace's statuses are listed.
    Rules: `get_statuses` R1 [BUG-035]"""
    mk_status(workspace_id=w2.id, name="Early")
    a = mk_status()
    b = mk_status(name="Beta")
    mk_status(workspace_id=w2.id, name="Late")
    commit_point(db)
    result = svc.get_statuses(db, workspace_id=w1.id, skip=0, limit=1000)

    # Then 1
    assert ids(result) == [a.id, b.id]


# [claude] SSV-L-03
def test_ssv_l_03__limit_0_gives_an_empty_list(db, mk_status):
    """SSV-L-03 — limit=0 gives an empty list.
    Rules: `get_statuses` R2"""
    mk_status()
    mk_status(name="Beta")
    commit_point(db)
    result = svc.get_statuses(db, skip=0, limit=0)

    # Then 1
    assert result == []


# [claude] SSV-L-04
def test_ssv_l_04__limit_1_gives_one_status(db, mk_status):
    """SSV-L-04 — limit=1 gives one status.
    Rules: `get_statuses` R2"""
    mk_status()
    mk_status(name="Beta")
    commit_point(db)
    result = svc.get_statuses(db, skip=0, limit=1)

    # Then 1
    assert len(result) == 1


# [claude] SSV-L-05
def test_ssv_l_05__with_the_default_skip_and_limit_101_statuses_give_100(db, w1):
    """SSV-L-05 — with the default skip and limit, 101 statuses give 100.
    Rules: `get_statuses` R2"""
    db.add_all([Status(workspace_id=w1.id, name=f"s{k:03d}", comment="A note") for k in range(101)])
    db.flush()
    commit_point(db)
    result = svc.get_statuses(db)

    # Then 1
    assert len(result) == 100


# [claude] SSV-L-06
def test_ssv_l_06__skip_leaves_out_that_many_rows(db, mk_status):
    """SSV-L-06 — skip leaves out that many rows: skip=n_all-1 with limit=1000 gives one.
    Rules: `get_statuses` R2"""
    mk_status()
    mk_status(name="Beta")
    commit_point(db)
    n_all = n_all_of(db)
    result = svc.get_statuses(db, skip=n_all - 1, limit=1000)

    # Then 1
    assert len(result) == 1


# [claude] SSV-L-07
def test_ssv_l_07__a_negative_limit_raises_dataerror_and_leaves_the_session_aborted(db, mk_status):
    """SSV-L-07 — a negative limit raises DataError and leaves the session aborted.
    Rules: `get_statuses` R2, R4, Errors; S4"""
    mk_status()
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        svc.get_statuses(db, skip=0, limit=-1)
    # Then 2
    with pytest.raises(DBAPIError):
        db.execute(text("SELECT 1"))


# [claude] SSV-L-08
def test_ssv_l_08__a_negative_skip_raises_dataerror(db, mk_status):
    """SSV-L-08 — a negative skip raises DataError.
    Rules: `get_statuses` R2, Errors"""
    mk_status()
    commit_point(db)
    # Then 1
    with pytest.raises(DataError):
        svc.get_statuses(db, skip=-1, limit=10)


# [claude] SSV-L-09
@pytest.mark.xfail(strict=False, reason=BUG_1681)
def test_ssv_l_09__statuses_come_by_name_case_insensitive_ascending(db, w1, mk_status):
    """SSV-L-09 — statuses come by name, case-insensitive ascending.
    Rules: `get_statuses` R3 [BUG-1681]"""
    z = mk_status(name="zeta")
    a = mk_status(name="Alpha")
    b = mk_status(name="beta")
    commit_point(db)
    n_all = n_all_of(db)
    result = svc.get_statuses(db, skip=0, limit=n_all)

    # Then 1
    assert {z.id, a.id, b.id} <= idset(result)
    # Then 2
    assert [r.name for r in result if r.workspace_id == w1.id] == ["Alpha", "beta", "zeta"]


# [claude] SSV-L-10
@pytest.mark.xfail(strict=True, reason=BUG_1681)
def test_ssv_l_10__the_query_orders_by_lower_name_then_id_last_before_the_page(db, mk_status):
    """SSV-L-10 — the query orders by lower(name), then id last, before the page.
    Rules: `get_statuses` R3 [BUG-1681]"""
    mk_status()
    commit_point(db)
    with record_sql(db) as sql_log:
        result = svc.get_statuses(db, skip=0, limit=10)
    sql = the_select(sql_log)
    order_part = order_part_of(sql)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert "lower(" in order_part.lower()
    # Then 3
    assert "ORDER BY" in sql
    # Then 4
    assert order_part.lower().index("name") < order_part.lower().index(".id")
    # Then 5
    assert re.search(r"\.id(\s+asc)?\s*$", order_part, re.IGNORECASE) is not None
    # Then 6
    assert sql.index("ORDER BY") < sql.index("LIMIT")


# [claude] SSV-L-11
def test_ssv_l_11__the_list_neither_commits_nor_rolls_back(db, mk_status):
    """SSV-L-11 — the list neither commits nor rolls back.
    Rules: `get_statuses` R4; S4"""
    a = mk_status()
    b = mk_status(name="Other")
    commit_point(db)
    n_all = n_all_of(db)
    p = mk_status(name="Pending")
    b.comment = "Changed"
    with spies(db) as (cm, rb):
        result = svc.get_statuses(db, skip=0, limit=n_all + 1)

    # Then 1
    assert {a.id, p.id} <= idset(result)
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    db.rollback()
    assert count_statuses(db, name="Pending") == 0

# [claude] SSV-L-12
def test_ssv_l_12__with_no_skip_given_the_list_starts_at_the_first_row(db, mk_status):
    """SSV-L-12 — with no skip given, the list starts at the first row.
    Rules: `get_statuses` R2"""
    mk_status()
    mk_status(name="Beta")
    commit_point(db)
    n_all = n_all_of(db)
    result = svc.get_statuses(db)

    # Then 1
    assert n_all <= 100
    # Then 2
    assert len(result) == n_all


# --------------------------------------------------------------------------- #
# StatusService.get_by_id
# --------------------------------------------------------------------------- #

# [claude] SSV-G-01
def test_ssv_g_01__the_status_with_that_id_is_returned(db, mk_status):
    """SSV-G-01 — the status with that id is returned.
    Rules: `get_by_id` R1"""
    a = mk_status()
    mk_status(name="Other")
    commit_point(db)
    result = svc.get_by_id(db, status_id=a.id)

    # Then 1
    assert isinstance(result, Status)
    # Then 2
    assert result.id == a.id
    assert result.name == "Feat"
    assert result.comment == "A note"


# [claude] SSV-G-02
def test_ssv_g_02__id_0_returns_none_no_error(db, mk_status):
    """SSV-G-02 — id 0 returns None, no error.
    Rules: `get_by_id` R2"""
    mk_status()
    commit_point(db)
    result = svc.get_by_id(db, status_id=0)

    # Then 1
    assert result is None


# [claude] SSV-G-03
def test_ssv_g_03__the_read_neither_commits_nor_rolls_back_an_unknown_id_returns_none(db, mk_status):
    """SSV-G-03 — the read neither commits nor rolls back; an unknown id returns None.
    Rules: `get_by_id` R2, R4; S4"""
    mk_status()
    b = mk_status(name="Other")
    commit_point(db)
    mk_status(name="Pending")
    b.comment = "Changed"
    with spies(db) as (cm, rb):
        result = svc.get_by_id(db, status_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert b in db.dirty
    # Then 5
    db.rollback()
    assert count_statuses(db, name="Pending") == 0


# [claude] SSV-G-04
def test_ssv_g_04__today_another_workspaces_status_is_returned(db, w2, mk_status):
    """SSV-G-04 — today another workspace's status is returned (documents BUG-035).
    Rules: `get_by_id` R3 (today)"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    commit_point(db)
    result = svc.get_by_id(db, status_id=z.id)

    # Then 1
    assert result.id == z.id
    assert result.workspace_id == w2.id


# [claude] SSV-G-05
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_g_05__another_workspaces_status_is_not_found(db, w1, w2, mk_status):
    """SSV-G-05 — another workspace's status is not found.
    Rules: `get_by_id` R3 [BUG-035]"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    commit_point(db)
    result = svc.get_by_id(db, status_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# StatusService.create_status
# --------------------------------------------------------------------------- #

# [claude] SSV-C-01
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_c_01__a_new_status_is_stored_in_the_callers_workspace_committed_and_returned_re_read(db, w1):
    """SSV-C-01 — a new status is stored in the caller's workspace, committed and returned re-read.
    Rules: `create_status` R1, Returns [BUG-035]; S1"""
    commit_point(db)
    result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=w1.id)

    # Then 1
    assert "id" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "comment" not in unloaded(result)
    assert "workspace_id" not in unloaded(result)
    # Then 2
    assert isinstance(result, Status)
    # Then 3
    assert result.workspace_id == w1.id
    assert result.name == "Feat"
    assert result.comment == "A note"
    # Then 4
    result_id = result.id
    db.rollback()
    row = db.execute(select(Status).where(Status.id == result_id)).scalar_one()
    assert row.workspace_id == w1.id
    assert row.name == "Feat"
    assert row.comment == "A note"
    # Then 5
    assert count_statuses(db, workspace_id=w1.id) == 1


# [claude] SSV-C-02
def test_ssv_c_02__today_every_create_fails_on_workspace_id_is_rolled_back_and_discards_other_changes(
    db, mk_status,
):
    """SSV-C-02 — today every create fails on workspace_id, is rolled back, and discards other changes.
    Rules: `create_status` R1 (today), R6; S2"""
    a = mk_status(name="Other")
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with spies(db) as (cm, rb):
            svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert rb.call_count >= 1
    # Then 5
    assert cm.call_count == 0
    # Then 6
    assert count_statuses(db, name="Feat") == 0
    # Then 7
    assert count_statuses(db, name="Extra") == 0
    # Then 8
    assert snap(db, a) == before_a
    # Then 9
    assert usable(db)


# [claude] SSV-C-03
def test_ssv_c_03__no_acting_user_or_audit_column_exists_on_statuses():
    """SSV-C-03 — no acting user or audit column exists on statuses.
    Rules: `create_status` R2; `update_status` R5"""
    # Then 1
    assert {c.name for c in Status.__table__.columns} == {"id", "workspace_id", "name", "comment"}


# [claude] SSV-C-04
def test_ssv_c_04__comment_is_required_by_statuscreate(db):
    """SSV-C-04 — comment is required by StatusCreate.
    Rules: `create_status` R3"""
    commit_point(db)
    n_all = n_all_of(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        StatusCreate.model_validate({"name": "Feat"})
    # Then 2
    assert count_statuses(db) == n_all


# [claude] SSV-C-05
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_c_05__an_empty_comment_is_stored(db, w1):
    """SSV-C-05 — an empty comment is stored.
    Rules: `create_status` R3 [BUG-035]"""
    commit_point(db)
    result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment=""), workspace_id=w1.id)

    # Then 1
    assert result.comment == ""
    # Then 2
    result_id = result.id
    db.rollback()
    assert db.execute(select(Status.comment).where(Status.id == result_id)).scalar_one() == ""


# [claude] SSV-C-06
@pytest.mark.xfail(strict=True, reason=BUG_1680)
def test_ssv_c_06__a_whitespace_only_name_is_refused_by_statuscreate(db):
    """SSV-C-06 — a whitespace-only name is refused by StatusCreate.
    Rules: `create_status` R4 [BUG-1680], Errors"""
    commit_point(db)
    n_all = n_all_of(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        StatusCreate(name="   ", comment="A note")
    # Then 2
    assert count_statuses(db) == n_all


# [claude] SSV-C-07
@pytest.mark.xfail(strict=True, reason=BUG_1680)
def test_ssv_c_07__statuscreate_trims_the_name():
    """SSV-C-07 — StatusCreate trims the name.
    Rules: `create_status` R4 [BUG-1680]"""
    data = StatusCreate(name=" Feat ", comment="A note")

    # Then 1
    assert data.name == "Feat"


# [claude] SSV-C-08
def test_ssv_c_08__the_response_schema_still_reads_a_blank_name():
    """SSV-C-08 — the response schema still reads a blank name.
    Rules: `create_status` R4"""
    data = StatusResponse(id=1, name="   ", comment="A note")

    # Then 1
    assert data.name == "   "


# [claude] SSV-C-09
@pytest.mark.xfail(strict=True, reason=BUG_1221)
def test_ssv_c_09__a_name_already_used_in_the_workspace_is_refused_after_the_rollback(db, w1, mk_status):
    """SSV-C-09 — a name already used in the workspace is refused after the rollback; other changes go too.
    Rules: `create_status` R5 [BUG-1221], Errors"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_status(db, status_in=StatusCreate(name="Feat", comment="Again"), workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_statuses(db, workspace_id=w1.id, name="Feat") == 1
    # Then 4
    assert count_statuses(db, name="Extra") == 0
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert usable(db)


# [claude] SSV-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1221)
def test_ssv_c_10__the_same_name_in_capitals_and_with_spaces_collides_too(db, w1, mk_status):
    """SSV-C-10 — the same name in capitals and with spaces collides too.
    Rules: `create_status` R5 [BUG-1221], Errors"""
    mk_status()
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_status(db, status_in=StatusCreate(name=" FEAT ", comment="Again"), workspace_id=w1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_statuses(db, workspace_id=w1.id) == 1


# [claude] SSV-C-11
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_c_11__the_same_name_in_another_workspace_is_stored(db, w1, w2, mk_status):
    """SSV-C-11 — the same name in another workspace is stored.
    Rules: `create_status` R5 [BUG-035]"""
    z = mk_status(workspace_id=w2.id)
    commit_point(db)
    result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=w1.id)

    # Then 1
    assert result.workspace_id == w1.id
    # Then 2
    db.rollback()
    assert count_statuses(db, name="Feat") == 2
    # Then 3
    row = reread(db, z)
    assert row.workspace_id == w2.id
    assert row.name == "Feat"


# [claude] SSV-C-12
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_c_12__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, mk_status,
):
    """SSV-C-12 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `create_status` R6 [BUG-035]; S2"""
    mk_status(name="Other")
    commit_point(db)
    mk_status(name="Extra")
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_statuses(db, name="Feat") == 0
    # Then 4
    assert count_statuses(db, name="Extra") == 0
    # Then 5
    assert exc.value is boom


# [claude] SSV-C-13
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_c_13__a_failing_re_read_after_the_commit_leaves_the_status_saved(db, w1):
    """SSV-C-13 — a failing re-read after the commit leaves the status saved.
    Rules: `create_status` R6 [BUG-035]; S1"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_statuses(db, workspace_id=w1.id, name="Feat") == 1


# --------------------------------------------------------------------------- #
# StatusService.update_status
# --------------------------------------------------------------------------- #

# [claude] SSV-U-01
def test_ssv_u_01__name_and_comment_are_written_committed_and_returned_re_read(db, w1, mk_status):
    """SSV-U-01 — name and comment are written, committed and returned re-read.
    Rules: `update_status` R3, Returns; S1"""
    a = mk_status()
    commit_point(db)
    result = svc.update_status(db, status_id=a.id, status_in=StatusUpdate(name="Done", comment="Finished"))

    # Then 1
    assert "name" not in unloaded(result)
    assert "comment" not in unloaded(result)
    # Then 2
    assert result.id == a.id
    assert result.name == "Done"
    assert result.comment == "Finished"
    # Then 3
    db.rollback()
    row = reread(db, a)
    assert row.name == "Done"
    assert row.comment == "Finished"
    assert row.workspace_id == w1.id


# [claude] SSV-U-02
def test_ssv_u_02__an_omitted_name_stays(db, mk_status):
    """SSV-U-02 — an omitted name stays.
    Rules: `update_status` R3"""
    a = mk_status()
    commit_point(db)
    result = svc.update_status(db, status_id=a.id, status_in=StatusUpdate(comment="Finished"))

    # Then 1
    assert result.comment == "Finished"
    # Then 2
    db.rollback()
    row = reread(db, a)
    assert row.name == "Feat"
    assert row.comment == "Finished"


# [claude] SSV-U-03
def test_ssv_u_03__fields_sent_as_null_stay_unchanged_the_status_is_returned(db, mk_status):
    """SSV-U-03 — fields sent as null stay unchanged; the status is returned.
    Rules: `update_status` R3"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.update_status(db, status_id=a.id, status_in=StatusUpdate(name=None, comment=None))

    # Then 1
    assert result.id == a.id
    assert result.name == "Feat"
    assert result.comment == "A note"
    # Then 2
    assert snap(db, a) == before_a


# [claude] SSV-U-04
def test_ssv_u_04__id_0_returns_none_writes_nothing_neither_commits_nor_rolls_back(db, mk_status):
    """SSV-U-04 — id 0 returns None, writes nothing, neither commits nor rolls back.
    Rules: `update_status` R1; S3"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    with spies(db) as (cm, rb):
        result = svc.update_status(db, status_id=0, status_in=StatusUpdate(name="Done"))

    # Then 1
    assert result is None
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_statuses(db, name="Extra") == 1
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    db.rollback()
    assert count_statuses(db, name="Extra") == 0


# [claude] SSV-U-05
def test_ssv_u_05__an_unknown_id_returns_none(db, mk_status):
    """SSV-U-05 — an unknown id returns None.
    Rules: `update_status` R1"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.update_status(db, status_id=MISSING, status_in=StatusUpdate(name="Done"))

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, a) == before_a


# [claude] SSV-U-06
def test_ssv_u_06__today_another_workspaces_status_is_changed_and_committed(db, w2, mk_status):
    """SSV-U-06 — today another workspace's status is changed and committed (documents BUG-035).
    Rules: `update_status` R2 (today)"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    commit_point(db)
    result = svc.update_status(db, status_id=z.id, status_in=StatusUpdate(name="Hacked"))

    # Then 1
    assert result.id == z.id
    # Then 2
    db.rollback()
    row = reread(db, z)
    assert row.name == "Hacked"
    assert row.workspace_id == w2.id


# [claude] SSV-U-07
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_u_07__another_workspaces_status_is_not_found_and_stays_unchanged(db, w1, w2, mk_status):
    """SSV-U-07 — another workspace's status is not found and stays unchanged.
    Rules: `update_status` R2 [BUG-035]"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    result = svc.update_status(db, status_id=z.id, status_in=StatusUpdate(name="Hacked"), workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, z) == before_z


# [claude] SSV-U-08
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_08__a_purchase_order_stage_status_refuses_a_rename_naming_purchase_order(db, mk_status):
    """SSV-U-08 — a purchase order stage status refuses a rename, naming 'Purchase Order'.
    Rules: `update_status` R4, R4a, R4b [BUG-1220], Errors row 1"""
    s = mk_status(name="Receiving")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'Receiving' is used by order workflow 'Purchase Order' and cannot be renamed"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-U-09
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_09__a_status_in_the_workspaces_workflow_sequence_refuses_a_rename(db, mk_status, mk_workflow):
    """SSV-U-09 — a status in the workspace's workflow sequence refuses a rename, naming the workflow.
    Rules: `update_status` R4, R4a [BUG-1220], Errors row 1"""
    s = mk_status()
    mk_workflow([s.id])
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Done"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be renamed"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-U-10
def test_ssv_u_10__a_stage_status_may_change_its_comment(db, mk_status):
    """SSV-U-10 — a stage status may change its comment.
    Rules: `update_status` R4"""
    s = mk_status(name="Receiving")
    commit_point(db)
    result = svc.update_status(db, status_id=s.id, status_in=StatusUpdate(comment="Goods arriving"))

    # Then 1
    assert result.comment == "Goods arriving"
    # Then 2
    db.rollback()
    row = reread(db, s)
    assert row.name == "Receiving"
    assert row.comment == "Goods arriving"


# [claude] SSV-U-11
def test_ssv_u_11__a_sequence_status_may_be_sent_with_its_current_name(db, mk_status, mk_workflow):
    """SSV-U-11 — a sequence status may be sent with its current name.
    Rules: `update_status` R4"""
    s = mk_status()
    mk_workflow([s.id])
    commit_point(db)
    result = svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Feat", comment="Kept"))

    # Then 1
    assert result.name == "Feat"
    # Then 2
    db.rollback()
    row = reread(db, s)
    assert row.name == "Feat"
    assert row.comment == "Kept"


# [claude] SSV-U-12
def test_ssv_u_12__a_name_that_only_contains_a_stage_name_is_not_protected(db, mk_status):
    """SSV-U-12 — a name that only contains a stage name is not protected.
    Rules: `update_status` R4, R4b"""
    s = mk_status(name="Receiving Bay")
    commit_point(db)
    result = svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Dock"))

    # Then 1
    assert result.name == "Dock"
    # Then 2
    db.rollback()
    assert reread(db, s).name == "Dock"


# [claude] SSV-U-13
def test_ssv_u_13__a_status_listed_only_in_another_workspaces_workflow_is_not_protected(
    db, w2, mk_status, mk_workflow,
):
    """SSV-U-13 — a status listed only in another workspace's workflow is not protected.
    Rules: `update_status` R4"""
    s = mk_status()
    mk_workflow([s.id], workspace_id=w2.id)
    commit_point(db)
    result = svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Done"))

    # Then 1
    assert result.name == "Done"
    # Then 2
    db.rollback()
    assert reread(db, s).name == "Done"


# [claude] SSV-U-14
@pytest.mark.xfail(strict=True, reason=BUG_1680)
def test_ssv_u_14__a_whitespace_only_new_name_is_refused_by_statusupdate(db, mk_status):
    """SSV-U-14 — a whitespace-only new name is refused by StatusUpdate.
    Rules: `update_status` R6 [BUG-1680], Errors row 3"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    # Then 1
    with pytest.raises(PydanticValidationError):
        StatusUpdate(name="   ")
    # Then 2
    assert snap(db, a) == before_a


# [claude] SSV-U-15
@pytest.mark.xfail(strict=True, reason=BUG_1680)
def test_ssv_u_15__statusupdate_trims_a_new_name():
    """SSV-U-15 — StatusUpdate trims a new name.
    Rules: `update_status` R6 [BUG-1680]"""
    data = StatusUpdate(name=" Done ")

    # Then 1
    assert data.name == "Done"


# [claude] SSV-U-16
@pytest.mark.xfail(strict=True, reason=BUG_1221)
def test_ssv_u_16__a_rename_onto_another_statuss_name_is_refused_after_the_rollback(db, mk_status):
    """SSV-U-16 — a rename onto another status's name is refused after the rollback; other changes go too.
    Rules: `update_status` R7 [BUG-1221], Errors row 2"""
    mk_status()
    b = mk_status(name="Other")
    commit_point(db)
    before_b = snap_before(db, b)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.update_status(db, status_id=b.id, status_in=StatusUpdate(name=" FEAT "))
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert snap(db, b) == before_b
    # Then 4
    assert count_statuses(db, name="Extra") == 0
    # Then 5
    assert usable(db)


# [claude] SSV-U-17
def test_ssv_u_17__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, mk_status,
):
    """SSV-U-17 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `update_status` R8; S2"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_status(db, status_id=a.id, status_in=StatusUpdate(name="Done"))
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert count_statuses(db, name="Extra") == 0
    # Then 5
    assert exc.value is boom


# [claude] SSV-U-18
def test_ssv_u_18__a_failing_re_read_after_the_commit_leaves_the_change_saved(db, mk_status):
    """SSV-U-18 — a failing re-read after the commit leaves the change saved.
    Rules: `update_status` R8; S1"""
    a = mk_status()
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.update_status(db, status_id=a.id, status_in=StatusUpdate(name="Done"))
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert reread(db, a).name == "Done"


# [claude] SSV-U-19
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_19__a_refused_rename_rolls_back_first_other_uncommitted_changes_go(db, mk_status):
    """SSV-U-19 — a refused rename rolls back first: other uncommitted changes go.
    Rules: `update_status` R4 [BUG-1220]; S2a"""
    s = mk_status(name="Receiving")
    commit_point(db)
    before_s = snap_before(db, s)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert count_statuses(db, name="Extra") == 0
    # Then 6
    assert snap(db, s) == before_s


# [claude] SSV-U-20
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_20__two_workflows_both_named_in_id_order_with_order_workflows(db, mk_status, mk_workflow):
    """SSV-U-20 — two workflows: both named, in id order, with "order workflows".
    Rules: `update_status` R4a [BUG-1220], Errors row 1"""
    s = mk_status()
    mk_workflow([s.id])
    mk_workflow([s.id], name="Alt Flow", type="STM")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Done"))
    # Then 2
    assert exc.value.detail == "Status 'Feat' is used by order workflows 'Flow', 'Alt Flow' and cannot be renamed"
    # Then 3
    assert snap(db, s) == before_s


# [claude] SSV-U-21
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_21__a_stage_status_in_no_sequence_names_the_workspaces_purchase_workflow_row(
    db, mk_status, mk_workflow,
):
    """SSV-U-21 — a stage status in no sequence names the workspace's purchase workflow row.
    Rules: `update_status` R4a [BUG-1220], Errors row 1"""
    s = mk_status(name="Receiving")
    mk_workflow([], name="PO Flow", type="purchase")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.detail == "Status 'Receiving' is used by order workflow 'PO Flow' and cannot be renamed"
    # Then 3
    assert snap(db, s) == before_s


# [claude] SSV-U-22
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_22__a_stage_status_in_the_purchase_sequence_names_that_workflow_once(db, mk_status, mk_workflow):
    """SSV-U-22 — a stage status in the purchase sequence names that workflow once.
    Rules: `update_status` R4a [BUG-1220], Errors row 1"""
    s = mk_status(name="Draft")
    mk_workflow([s.id], name="PO Flow", type="purchase")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Started"))
    # Then 2
    assert exc.value.detail == "Status 'Draft' is used by order workflow 'PO Flow' and cannot be renamed"
    # Then 3
    assert snap(db, s) == before_s


# [claude] SSV-U-23
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_u_23__another_workspaces_workflow_is_never_named(db, w2, mk_status, mk_workflow):
    """SSV-U-23 — another workspace's workflow is never named.
    Rules: `update_status` R4a [BUG-1220], Errors row 1"""
    s = mk_status(name="Receiving")
    mk_workflow([s.id], workspace_id=w2.id, name="Far Flow")
    mk_workflow([], workspace_id=w2.id, name="Far PO", type="purchase")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.detail == "Status 'Receiving' is used by order workflow 'Purchase Order' and cannot be renamed"
    # Then 3
    assert snap(db, s) == before_s


# [claude] SSV-U-24
@pytest.mark.xfail(strict=True, reason=f"{BUG_1220}; {BUG_1880}")
def test_ssv_u_24__a_stage_name_in_other_capitals_is_a_stage_status_rename_refused(db, mk_status):
    """SSV-U-24 — a stage name in other capitals is a stage status: rename refused.
    Rules: `update_status` R4, R4a, R4b [BUG-1880], Errors row 1"""
    s = mk_status(name="receiving")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'receiving' is used by order workflow 'Purchase Order' and cannot be renamed"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-U-25
@pytest.mark.xfail(strict=True, reason=f"{BUG_1220}; {BUG_1880}")
def test_ssv_u_25__a_stage_name_with_outer_spaces_is_a_stage_status_rename_refused(db, mk_status):
    """SSV-U-25 — a stage name with outer spaces is a stage status: rename refused.
    Rules: `update_status` R4, R4a, R4b [BUG-1880], Errors row 1"""
    s = mk_status(name=" Receiving ")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status ' Receiving ' is used by order workflow 'Purchase Order' and cannot be renamed"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-U-26
def test_ssv_u_26__a_space_inside_a_stage_name_is_not_a_stage_status_renamed(db, mk_status):
    """SSV-U-26 — a space inside a stage name is not a stage status: renamed.
    Rules: `update_status` R4, R4b"""
    s = mk_status(name="Re ceiving")
    commit_point(db)
    result = svc.update_status(db, status_id=s.id, status_in=StatusUpdate(name="Goods in"))

    # Then 1
    assert result.name == "Goods in"
    # Then 2
    db.rollback()
    assert reread(db, s).name == "Goods in"


# --------------------------------------------------------------------------- #
# StatusService.delete_status
# --------------------------------------------------------------------------- #

# [claude] SSV-D-01
def test_ssv_d_01__a_status_nothing_uses_is_hard_deleted_and_committed_true_is_returned(db, mk_status):
    """SSV-D-01 — a status nothing uses is hard-deleted and committed; True is returned.
    Rules: `delete_status` R5, Returns; S1"""
    a = mk_status()
    b = mk_status(name="Other")
    a_id = a.id
    commit_point(db)
    result = svc.delete_status(db, status_id=a.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert count_statuses(db, id=a_id) == 0
    # Then 3
    assert reread(db, b).name == "Other"


# [claude] SSV-D-02
def test_ssv_d_02__id_0_returns_false_writes_nothing_neither_commits_nor_rolls_back(db, mk_status):
    """SSV-D-02 — id 0 returns False, writes nothing, neither commits nor rolls back.
    Rules: `delete_status` R1; S3"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    with spies(db) as (cm, rb):
        result = svc.delete_status(db, status_id=0)

    # Then 1
    assert result is False
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_statuses(db, name="Extra") == 1
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    db.rollback()
    assert count_statuses(db, name="Extra") == 0


# [claude] SSV-D-03
def test_ssv_d_03__an_unknown_id_returns_false(db, mk_status):
    """SSV-D-03 — an unknown id returns False.
    Rules: `delete_status` R1"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    result = svc.delete_status(db, status_id=MISSING)

    # Then 1
    assert result is False
    # Then 2
    assert snap(db, a) == before_a


# [claude] SSV-D-04
def test_ssv_d_04__today_another_workspaces_status_is_deleted(db, w2, mk_status):
    """SSV-D-04 — today another workspace's status is deleted (documents BUG-035).
    Rules: `delete_status` R2 (today)"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    z_id = z.id
    commit_point(db)
    result = svc.delete_status(db, status_id=z.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert count_statuses(db, id=z_id) == 0


# [claude] SSV-D-05
@pytest.mark.xfail(strict=True, reason=BUG_035)
def test_ssv_d_05__another_workspaces_status_is_not_found_and_stays(db, w1, w2, mk_status):
    """SSV-D-05 — another workspace's status is not found and stays.
    Rules: `delete_status` R2 [BUG-035]"""
    mk_status()
    z = mk_status(workspace_id=w2.id, name="Far")
    commit_point(db)
    before_z = snap_before(db, z)
    result = svc.delete_status(db, status_id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert snap(db, z) == before_z


# [claude] SSV-D-06
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_d_06__an_unused_purchase_order_stage_status_is_refused_naming_purchase_order(db, mk_status):
    """SSV-D-06 — an unused purchase order stage status is refused, naming 'Purchase Order'.
    Rules: `delete_status` R3 [BUG-1220]; `update_status` R4a, R4b; Errors row 1"""
    s = mk_status(name="Complete")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'Complete' is used by order workflow 'Purchase Order' and cannot be deleted"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-D-07
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_d_07__a_status_in_the_workspaces_workflow_sequence_is_refused_naming_the_workflow(
    db, mk_status, mk_workflow,
):
    """SSV-D-07 — a status in the workspace's workflow sequence is refused, naming the workflow.
    Rules: `delete_status` R3 [BUG-1220]; `update_status` R4a; Errors row 1"""
    s = mk_status()
    f = mk_workflow([s.id])
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be deleted"
    # Then 4
    assert snap(db, s) == before_s
    # Then 5
    assert reread(db, f).status_sequence == [s.id]


# [claude] SSV-D-08
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_d_08__the_protection_is_checked_before_the_in_use_refusal(db, mk_status, mk_workflow, mk_transfer):
    """SSV-D-08 — the protection is checked before the in-use refusal.
    Rules: `delete_status` R3 [BUG-1220], Errors row 1"""
    s = mk_status()
    mk_workflow([s.id])
    mk_transfer(s)
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be deleted"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-D-09
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_09__a_status_a_transfer_order_uses_is_refused_listing_the_transfer(db, mk_status, mk_transfer):
    """SSV-D-09 — a status a transfer order uses is refused, listing the transfer.
    Rules: `delete_status` R4 [BUG-1218], Errors row 2"""
    s = mk_status()
    t = mk_transfer(s)
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status is used by orders"
    # Then 4
    assert exc.value.errors == [{"type": "transfer_order", "id": t.id}]
    # Then 5
    assert snap(db, s) == before_s
    # Then 6
    assert reread(db, t).current_status_id == s.id


# [claude] SSV-D-10
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_10__a_status_a_purchase_order_uses_is_refused_listing_the_purchase_order(
    db, mk_status, mk_purchase,
):
    """SSV-D-10 — a status a purchase order uses is refused, listing the purchase order.
    Rules: `delete_status` R4 [BUG-1218], Errors row 2"""
    s = mk_status()
    o = mk_purchase(s)
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status is used by orders"
    # Then 4
    assert exc.value.errors == [{"type": "purchase_order", "id": o.id}]
    # Then 5
    assert snap(db, s) == before_s
    # Then 6
    assert reread(db, o).current_status_id == s.id


# [claude] SSV-D-11
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_11__a_status_used_only_by_another_workspaces_order_is_refused_with_the_generic_entry_alone(
    db, w2, mk_status, mk_transfer,
):
    """SSV-D-11 — a status used only by another workspace's order is refused with the generic entry alone.
    Rules: `delete_status` R4 [BUG-1218], Errors row 2"""
    s = mk_status()
    mk_transfer(s, workspace_id=w2.id, transfer_number="TO-9")
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.errors == [{"type": "other_workspace"}]
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-D-12
def test_ssv_d_12__a_name_that_only_contains_a_stage_name_and_a_status_in_another_workspaces_workflow_are_deleted(
    db, w2, mk_status, mk_workflow,
):
    """SSV-D-12 — a name that only contains a stage name, and a status in another workspace's workflow, are deleted.
    Rules: `delete_status` R3, R5; `update_status` R4b"""
    s = mk_status(name="Completed")
    f9 = mk_workflow([s.id], workspace_id=w2.id)
    s_id = s.id
    commit_point(db)
    result = svc.delete_status(db, status_id=s.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert count_statuses(db, id=s_id) == 0
    # Then 3
    assert reread(db, f9).status_sequence == [s_id]


# [claude] SSV-D-13
def test_ssv_d_13__a_failing_commit_is_rolled_back_and_re_raised_the_status_stays(db, mk_status):
    """SSV-D-13 — a failing commit is rolled back and re-raised: the status stays.
    Rules: `delete_status` R6; S2"""
    a = mk_status()
    commit_point(db)
    before_a = snap_before(db, a)
    mk_status(name="Extra")
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_status(db, status_id=a.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a) == before_a
    # Then 4
    assert count_statuses(db, name="Extra") == 0
    # Then 5
    assert exc.value is boom


# [claude] SSV-D-14
@pytest.mark.xfail(strict=True, reason=BUG_1220)
def test_ssv_d_14__a_refused_stage_status_delete_rolls_back_first_other_uncommitted_changes_go(db, mk_status):
    """SSV-D-14 — a refused stage-status delete rolls back first: other uncommitted changes go.
    Rules: `delete_status` R3 [BUG-1220]; S2a"""
    s = mk_status(name="Complete")
    commit_point(db)
    before_s = snap_before(db, s)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with spies(db) as (cm, rb):
            svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert count_statuses(db, name="Extra") == 0
    # Then 6
    assert snap(db, s) == before_s


# [claude] SSV-D-15
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_15__a_refused_in_use_delete_rolls_back_first_other_uncommitted_changes_go(
    db, mk_status, mk_transfer,
):
    """SSV-D-15 — a refused in-use delete rolls back first: other uncommitted changes go.
    Rules: `delete_status` R4 [BUG-1218]; S2a"""
    s = mk_status()
    mk_transfer(s)
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    mk_status(name="Extra")
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with spies(db) as (cm, rb):
            svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert rb.call_count >= 1
    # Then 4
    assert cm.call_count == 0
    # Then 5
    assert count_statuses(db, name="Extra") == 0
    # Then 6
    assert snap(db, s) == before_s


# [claude] SSV-D-16
@pytest.mark.xfail(strict=True, reason=f"{BUG_1220}; {BUG_1880}")
def test_ssv_d_16__a_stage_name_with_a_leading_space_is_a_stage_status_delete_refused(db, mk_status):
    """SSV-D-16 — a stage name with a leading space is a stage status: delete refused.
    Rules: `delete_status` R3 [BUG-1880]; `update_status` R4a, R4b; Errors row 1"""
    s = mk_status(name=" Complete")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status ' Complete' is used by order workflow 'Purchase Order' and cannot be deleted"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-D-17
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_17__a_status_a_sales_order_uses_is_refused_listing_the_sales_order(db, mk_status, mk_sales):
    """SSV-D-17 — a status a sales order uses is refused, listing the sales order.
    Rules: `delete_status` R4 [BUG-1218], Errors row 2"""
    s = mk_status()
    so = mk_sales(s)
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status is used by orders"
    # Then 4
    assert exc.value.errors == [{"type": "sales_order", "id": so.id}]
    # Then 5
    assert snap(db, s) == before_s


# [claude] SSV-D-18
@pytest.mark.xfail(strict=True, reason=BUG_1218)
def test_ssv_d_18__the_blockers_come_by_type_then_id_then_one_other_workspace_entry_last(
    db, w2, mk_status, mk_transfer, mk_sales, mk_purchase,
):
    """SSV-D-18 — the blockers come by type (purchase, sales, transfer), then id, then one other-workspace entry last.
    Rules: `delete_status` R4 [BUG-1218], Errors row 2"""
    s = mk_status()
    t = mk_transfer(s)
    mk_transfer(s, workspace_id=w2.id, transfer_number="TO-9")
    so = mk_sales(s)
    o1 = mk_purchase(s)
    o2 = mk_purchase(s, po_number="PO-2")
    mk_purchase(s, workspace_id=w2.id, po_number="PO-9")
    db.expire_all()
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.errors == [
        {"type": "purchase_order", "id": o1.id}, {"type": "purchase_order", "id": o2.id},
        {"type": "sales_order", "id": so.id}, {"type": "transfer_order", "id": t.id},
        {"type": "other_workspace"},
    ]
    # Then 3
    assert snap(db, s) == before_s


# [claude] SSV-D-19
@pytest.mark.xfail(strict=True, reason=f"{BUG_1220}; {BUG_1880}")
def test_ssv_d_19__a_stage_name_in_capitals_is_a_stage_status_delete_refused(db, mk_status):
    """SSV-D-19 — a stage name in capitals is a stage status: delete refused.
    Rules: `delete_status` R3 [BUG-1880]; `update_status` R4a, R4b; Errors row 1"""
    s = mk_status(name="COMPLETE")
    commit_point(db)
    before_s = snap_before(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_status(db, status_id=s.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Status 'COMPLETE' is used by order workflow 'Purchase Order' and cannot be deleted"
    # Then 4
    assert snap(db, s) == before_s


# [claude] SSV-D-20
def test_ssv_d_20__a_space_inside_a_stage_name_is_not_a_stage_status_deleted(db, mk_status):
    """SSV-D-20 — a space inside a stage name is not a stage status: deleted.
    Rules: `delete_status` R3, R5; `update_status` R4b"""
    s = mk_status(name="Com plete")
    s_id = s.id
    commit_point(db)
    result = svc.delete_status(db, status_id=s.id)

    # Then 1
    assert result is True
    # Then 2
    db.rollback()
    assert count_statuses(db, id=s_id) == 0
