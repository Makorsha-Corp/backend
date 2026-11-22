"""Unit tests for app/dao/status.py.

Implements tests/unit/dao/status.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.dao.status import status_dao
from app.models.order_workflow import OrderWorkflow
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.schemas.status import StatusCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton status_dao" (a module-level name, not a fixture)
dao = status_dao


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1 = a profiles row"
@pytest.fixture
def u1(db):
    return make_profile(db)


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "status"
@pytest.fixture
def mk_status(db, w1):
    """mk_status(**columns) -> Status. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "name": "Feat", "comment": "A note"}
        fields.update(columns)
        return _add(db, Status(**fields))
    return _mk


# Convention "transfer on S": current_status_id is always the card's own row
@pytest.fixture
def mk_transfer(db, w1, u1):
    """mk_transfer(status) -> TransferOrder."""
    def _mk(status):
        return _add(db, TransferOrder(workspace_id=w1.id, transfer_number="TO-1", source_location_type="storage",
                                      source_location_id=1, destination_location_type="storage",
                                      destination_location_id=2, current_status_id=status.id, created_by=u1.id))
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one()


# The `count:` lines: SELECT count(*) through db.scalar(text(...)), with the filter stated
def count_rows(db, table, **filters):
    where = " AND ".join(f"{column} = :{column}" for column in filters) or "TRUE"
    return db.scalar(text(f"SELECT count(*) FROM {table} WHERE {where}"), filters)


# --------------------------------------------------------------------------- #
# Inherited create on statuses
# --------------------------------------------------------------------------- #


# [claude] STS-CR-01
def test_sts_cr_01__a_statuscreate_cannot_create_no_workspace_id(db):
    """STS-CR-01 — a StatusCreate cannot create: no workspace_id.
    Rules: `create` R1"""

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=StatusCreate(name="Feat", comment="A note"))
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "workspace_id" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "statuses", name="Feat") == 0


# [claude] STS-CR-02
def test_sts_cr_02__a_dict_with_workspace_id_name_and_comment_is_stored(db, w1):
    """STS-CR-02 — a dict with workspace_id, name and comment is stored.
    Rules: `create` R1, R2"""

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Feat", "comment": "A note"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Feat"
    assert row.comment == "A note"
    # Then 3
    assert count_rows(db, "statuses", workspace_id=w1.id) == 1


# [claude] STS-CR-03
def test_sts_cr_03__a_dict_without_comment_is_refused(db, w1):
    """STS-CR-03 — a dict without comment is refused.
    Rules: `create` R2"""

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Feat"})
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "comment" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "statuses", workspace_id=w1.id) == 0


# [claude] STS-CR-04
def test_sts_cr_04__a_dict_without_name_is_refused(db, w1):
    """STS-CR-04 — a dict without name is refused.
    Rules: `create` R2"""

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "comment": "A note"})
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "name" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "statuses", workspace_id=w1.id) == 0


# [claude] STS-CR-05
def test_sts_cr_05__the_same_name_in_another_workspace_is_stored(db, w2, mk_status):
    """STS-CR-05 — the same name in another workspace is stored.
    Rules: `create` R2"""
    a = mk_status()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w2.id, "name": "Feat", "comment": "Other"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.name == "Feat"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] STS-CR-06
def test_sts_cr_06__another_name_in_the_same_workspace_is_stored(db, w1, mk_status):
    """STS-CR-06 — another name in the same workspace is stored.
    Rules: `create` R2"""
    a = mk_status()
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Feat two", "comment": "Other"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Feat two"
    # Then 3
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] STS-CR-07
@pytest.mark.xfail(strict=True, reason="BUG-1221: Status names are not unique per workspace")
def test_sts_cr_07__a_second_row_of_one_name_in_one_workspace_is_refused(db, w1, mk_status):
    """STS-CR-07 — a second row of one name in one workspace is refused.
    Rules: `create` R2a [BUG-1221]"""
    a = mk_status()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": "Feat", "comment": "Other"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "statuses", workspace_id=w1.id, name="Feat") == 1
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# [claude] STS-CR-08
@pytest.mark.xfail(strict=True, reason="BUG-1221: Status names are not unique per workspace")
def test_sts_cr_08__the_compare_is_case_insensitive_after_trimming(db, w1, mk_status):
    """STS-CR-08 — the compare is case-insensitive after trimming.
    Rules: `create` R2b [BUG-1221]"""
    a = mk_status()
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "name": " feat ", "comment": "Other"})
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_rows(db, "statuses", workspace_id=w1.id) == 1
    # Then 4
    db.expire_all()
    assert snap(db, a) == before_a


# --------------------------------------------------------------------------- #
# Inherited remove on statuses
# --------------------------------------------------------------------------- #


# [claude] STS-RM-01
def test_sts_rm_01__a_status_no_order_uses_is_deleted(db, mk_status):
    """STS-RM-01 — a status no order uses is deleted.
    Rules: `remove` R3"""
    a = mk_status()
    b = mk_status(name="Done")
    before_b = snap(db, b)

    result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, "statuses", id=a.id) == 0
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] STS-RM-02
def test_sts_rm_02__an_id_listed_in_a_status_sequence_stays_there_and_nothing_else_changes(db, w1, mk_status):
    """STS-RM-02 — an id listed in a status_sequence stays there, and nothing else changes.
    Rules: `remove` R3"""
    a = mk_status()
    b = mk_status(name="Done")
    f = _add(db, OrderWorkflow(workspace_id=w1.id, name="Flow", type="purchase", status_sequence=[a.id, b.id]))
    seq = [a.id, b.id]
    before_f = snap(db, f)
    before_b = snap(db, b)

    result = dao.remove(db, id=a.id)

    # Then 1
    assert result.id == a.id
    # Then 2
    assert count_rows(db, "statuses", id=a.id) == 0
    # Then 3
    row = reread(db, f)
    assert row.status_sequence == seq
    # Then 4
    db.expire_all()
    assert snap(db, f) == before_f
    # Then 5
    db.expire_all()
    assert snap(db, b) == before_b


# [claude] STS-RM-03
def test_sts_rm_03__a_status_an_order_uses_raises_23502_on_current_status_id_and_nothing_i(db, mk_status, mk_transfer):
    """STS-RM-03 — a status an order uses raises 23502 on current_status_id, and nothing is deleted.
    Rules: `remove` R4"""
    a = mk_status()
    t = mk_transfer(a)
    db.expire_all()

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.remove(db, id=a.id)
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert "current_status_id" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "statuses", id=a.id) == 1
    # Then 5
    row = reread(db, t)
    assert row.current_status_id == a.id


# [claude] STS-RM-04
def test_sts_rm_04__the_same_delete_in_raw_sql_raises_23001(db, mk_status, mk_transfer):
    """STS-RM-04 — the same delete in raw SQL raises 23001.
    Rules: `remove` R4"""
    a = mk_status()
    t = mk_transfer(a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM statuses WHERE id = :id"), {"id": a.id})
    # Then 2
    assert exc.value.orig.pgcode == "23001"
    # Then 3
    assert count_rows(db, "statuses", id=a.id) == 1
    # Then 4
    row = reread(db, t)
    assert row.current_status_id == a.id
