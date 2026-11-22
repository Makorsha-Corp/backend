"""Unit tests for app/dao/account_tag_assignment.py.

Implements tests/unit/dao/account_tag_assignment.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is patched
(Conventions, Externals: None); the GD cards set the module global with
`monkeypatch.setattr`, and the **rolled back** cards wrap `db.commit` in a spy
that still calls it.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

import app.dao.account_tag_assignment as mod
from app.dao.account_tag import account_tag_dao
from app.dao.account_tag_assignment import account_tag_assignment_dao
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.schemas.account_tag_assignment import AccountTagAssignmentCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton account_tag_assignment_dao"
dao = account_tag_assignment_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

BUG_865 = "BUG-865: `get_tags_for_account` returns deleted tags"
BUG_1486 = "BUG-1486: An account's tags have no sort order"
NON_STRICT = " (non-strict: today's order is the plan's physical order, which can match by accident)"


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (W1, W2, U1, A1, A2, A9; every test, flushed in this order)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def a1(db, w1, u1):
    return _add(db, Account(workspace_id=w1.id, name="Acme"))


@pytest.fixture
def a2(db, w1, a1):
    return _add(db, Account(workspace_id=w1.id, name="Beta"))


@pytest.fixture
def a9(db, w2, a2):
    return _add(db, Account(workspace_id=w2.id, name="Far"))


@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, a1, a2, a9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "tag": W1, not a system tag, active, usage_count 0; name and tag_code from the card
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name=..., tag_code=..., **columns) -> AccountTag, added and flushed."""
    def _mk(*, name, tag_code, **columns):
        return _add(db, AccountTag(**{
            "workspace_id": w1.id, "is_system_tag": False, "is_active": True, "usage_count": 0,
            "name": name, "tag_code": tag_code, **columns,
        }))
    return _mk


# Convention "link": W1, account A1; the card gives the tag and the columns after "but"
@pytest.fixture
def link(db, w1, a1):
    """link(tag, **columns) -> AccountTagAssignment, added and flushed."""
    def _mk(tag, **columns):
        return _add(db, AccountTagAssignment(**{"workspace_id": w1.id, "account_id": a1.id, "tag_id": tag.id, **columns}))
    return _mk


# Convention "close(A)"
def close(db, a, u1):
    a.is_deleted = True
    a.is_active = False
    a.deleted_at = datetime(2026, 3, 1, 9, 0, 0)
    a.deleted_by = u1.id
    db.flush()


# Convention "bumpT(X)"
def bump_t(db, x):
    db.execute(text("UPDATE account_tags SET description = coalesce(description, '') || '!' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# Convention "seqscan": three steps, in this order
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [t.id for t in result]


def _id_of(row):
    return sa_inspect(row).identity[0]


# Convention "links(A, W)"
def links(db, a, w):
    return db.scalar(
        select(func.count()).select_from(AccountTagAssignment).where(
            AccountTagAssignment.account_id == _id_of(a), AccountTagAssignment.workspace_id == _id_of(w)
        )
    )


# Convention "stored_count(T)"
def stored_count(db, t):
    return db.scalar(select(AccountTag.usage_count).where(AccountTag.id == _id_of(t)))


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(type(row)).where(type(row).id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table, after expire_all
def snap(db, row):
    table = type(row).__table__
    row_id = _id_of(row)
    db.expire_all()
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "nothing written": account_tag_assignments and account_tags rows (all workspaces)
def written_counts(db):
    return (
        db.scalar(select(func.count()).select_from(AccountTagAssignment.__table__)),
        db.scalar(select(func.count()).select_from(AccountTag.__table__)),
    )


# Convention "rolled back": the spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# Convention "Statement recorder": SQL the session's connection sends during the When
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
        """The one SELECT from `account_tags`; fails loudly unless there is exactly one."""
        [statement] = [
            s for s in self.statements if s.lstrip().upper().startswith("SELECT") and "FROM account_tags" in s
        ]
        return statement


# Convention "order_part": the text of `sql` after ORDER BY ("" when none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# get_account_tag_dao
# --------------------------------------------------------------------------- #


# [claude] ATA-GD-01
def test_ata_gd_01__the_first_call_imports_the_account_tag_dao_and_stores_it(monkeypatch):
    """ATA-GD-01 — the first call imports the account tag DAO and stores it.
    Rules: `get_account_tag_dao` R1, R2"""
    monkeypatch.setattr(mod, "account_tag_dao", None)

    result = mod.get_account_tag_dao()

    # Then 1
    assert result is account_tag_dao
    # Then 2
    assert mod.account_tag_dao is account_tag_dao


# [claude] ATA-GD-02
def test_ata_gd_02__a_stored_object_is_returned_as_it_is(monkeypatch):
    """ATA-GD-02 — a stored object is returned as it is.
    Rules: `get_account_tag_dao` R2"""
    sentinel = object()
    monkeypatch.setattr(mod, "account_tag_dao", sentinel)

    result = mod.get_account_tag_dao()

    # Then 1
    assert result is sentinel


# --------------------------------------------------------------------------- #
# AccountTagAssignmentDAO.get_tags_for_account
# --------------------------------------------------------------------------- #


# [claude] ATA-TFA-01
def test_ata_tfa_01__returns_the_account_s_active_tags_linked_in_the_workspace_each_once(db, w1, a1, a2, mk_tag, link):
    """ATA-TFA-01 — returns the account's active tags linked in the workspace, each once; another account's link is not returned.
    Rules: `get_tags_for_account` R1, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    t3 = mk_tag(name="Bank", tag_code="bank")
    link(t1)
    link(t2)
    link(t3, account_id=a2.id)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [t1.id, t2.id]
    # Then 3
    assert isinstance(result[0], AccountTag)


# [claude] ATA-TFA-02
def test_ata_tfa_02__a_link_recorded_under_another_workspace_is_not_returned(db, w1, w2, a1, mk_tag, link):
    """ATA-TFA-02 — a link recorded under another workspace is not returned.
    Rules: `get_tags_for_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1, workspace_id=w2.id)
    link(t2)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t2.id]


# [claude] ATA-TFA-03
def test_ata_tfa_03__asking_with_the_other_workspace_returns_only_the_link_recorded_there(db, w2, a1, mk_tag, link):
    """ATA-TFA-03 — asking with the other workspace returns only the link recorded there.
    Rules: `get_tags_for_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1, workspace_id=w2.id)
    link(t2)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [t1.id]


# [claude] ATA-TFA-04
def test_ata_tfa_04__an_unknown_account_returns_an_empty_list(db, w1, mk_tag, link):
    """ATA-TFA-04 — an unknown account returns an empty list.
    Rules: `get_tags_for_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    result = dao.get_tags_for_account(db, account_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] ATA-TFA-05
def test_ata_tfa_05__another_workspace_s_tag_linked_under_this_workspace_is_returned_count(db, w1, w2, a1, mk_tag, link):
    """ATA-TFA-05 — another workspace's tag linked under this workspace is returned; count and system flag play no part.
    Rules: `get_tags_for_account` R2"""
    z1 = mk_tag(name="Far", tag_code="far", workspace_id=w2.id, is_system_tag=True, usage_count=0)
    link(z1)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [z1.id]


# [claude] ATA-TFA-06
@pytest.mark.xfail(strict=True, reason=BUG_865)
def test_ata_tfa_06__a_deleted_tag_is_not_returned(db, w1, a1, mk_tag, link):
    """ATA-TFA-06 — a deleted tag is not returned.
    Rules: `get_tags_for_account` R3 [BUG-865]"""
    td = mk_tag(name="Old", tag_code="old", is_active=False)
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(td)
    link(t1)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert t1.id in ids(result)
    # Then 2
    assert ids(result) == [t1.id]


# [claude] ATA-TFA-07
@pytest.mark.xfail(strict=False, reason=BUG_1486 + NON_STRICT)
def test_ata_tfa_07__ordered_by_name_case_insensitive_then_id_system_tags_not_grouped_first(db, w1, a1, mk_tag, link):
    """ATA-TFA-07 — ordered by name case-insensitive, then id; system tags not grouped first.
    Rules: `get_tags_for_account` R4 [BUG-1486]"""
    t1 = mk_tag(name="bravo", tag_code="bravo")
    t2 = mk_tag(name="Alpha", tag_code="alpha_upper")
    t3 = mk_tag(name="alpha", tag_code="alpha_lower")
    t4 = mk_tag(name="Charlie", tag_code="charlie", is_system_tag=True)
    link(t1)
    link(t2)
    link(t3)
    link(t4)
    seqscan(db)
    bump_t(db, t2)

    result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [t1.id, t2.id, t3.id, t4.id]
    # Then 2
    assert ids(result) == [t2.id, t3.id, t1.id, t4.id]


# [claude] ATA-TFA-08
@pytest.mark.xfail(strict=True, reason=BUG_1486)
def test_ata_tfa_08__the_query_orders_by_name_case_insensitive_then_id_not_by_the_system(db, w1, a1, mk_tag, link):
    """ATA-TFA-08 — the query orders by name case-insensitive, then id, not by the system flag.
    Rules: `get_tags_for_account` R4 [BUG-1486]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(account_tags.name)" in order_part
    # Then 4
    assert "account_tags.id" in order_part
    # Then 5
    assert "is_system_tag" not in order_part


# [claude] ATA-TFA-09
def test_ata_tfa_09__a_closed_account_s_tags_are_returned_the_read_writes_nothing_and(db, w1, u1, a1, mk_tag, link):
    """ATA-TFA-09 — a closed account's tags are returned; the read writes nothing and keeps pending changes.
    Rules: `get_tags_for_account` R5, Side effects"""
    close(db, a1, u1)
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1)
    t2.name = "Client Edited"
    p = AccountTagAssignment(workspace_id=w1.id, account_id=a1.id, tag_id=t2.id)
    db.add(p)

    with StatementRecorder(db) as recorder:
        result = dao.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert t2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []


# --------------------------------------------------------------------------- #
# AccountTagAssignmentDAO.get_assignment
# --------------------------------------------------------------------------- #


# [claude] ATA-GA-01
def test_ata_ga_01__returns_the_link_with_that_account_tag_and_workspace(db, w1, a1, mk_tag, link):
    """ATA-GA-01 — returns the link with that account, tag and workspace.
    Rules: `get_assignment` R1, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1)
    l2 = link(t2)

    result = dao.get_assignment(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, AccountTagAssignment)
    # Then 2
    assert result.id == l2.id


# [claude] ATA-GA-02
def test_ata_ga_02__the_pair_recorded_under_another_workspace_returns_none(db, w1, w2, a1, mk_tag, link):
    """ATA-GA-02 — the pair recorded under another workspace returns None.
    Rules: `get_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1, workspace_id=w2.id)

    result = dao.get_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATA-GA-03
def test_ata_ga_03__another_tag_or_another_account_does_not_match(db, w1, a1, a2, mk_tag, link):
    """ATA-GA-03 — another tag or another account does not match.
    Rules: `get_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1)
    link(t2, account_id=a2.id)

    result = dao.get_assignment(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ATA-GA-04
def test_ata_ga_04__a_link_of_a_closed_account_to_a_deleted_tag_is_found(db, w1, u1, a1, mk_tag, link):
    """ATA-GA-04 — a link of a closed account to a deleted tag is found.
    Rules: `get_assignment` R3 (P1)"""
    close(db, a1, u1)
    td = mk_tag(name="Old", tag_code="old", is_active=False)
    ld = link(td)

    result = dao.get_assignment(db, account_id=a1.id, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result.id == ld.id


# [claude] ATA-GA-05
def test_ata_ga_05__asking_with_the_other_workspace_does_not_find_a_w1_link(db, w2, a1, mk_tag, link):
    """ATA-GA-05 — asking with the other workspace does not find a W1 link.
    Rules: `get_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    result = dao.get_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] ATA-GA-06
def test_ata_ga_06__another_account_with_the_same_tag_does_not_match(db, w1, a2, mk_tag, link):
    """ATA-GA-06 — another account with the same tag does not match.
    Rules: `get_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    result = dao.get_assignment(db, account_id=a2.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# --------------------------------------------------------------------------- #
# AccountTagAssignmentDAO.assignment_exists
# --------------------------------------------------------------------------- #


# [claude] ATA-AE-01
def test_ata_ae_01__true_when_the_link_exists(db, w1, a1, mk_tag, link):
    """ATA-AE-01 — True when the link exists.
    Rules: `assignment_exists` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    result = dao.assignment_exists(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# [claude] ATA-AE-02
def test_ata_ae_02__false_for_the_pair_recorded_under_another_workspace(db, w1, w2, a1, mk_tag, link):
    """ATA-AE-02 — False for the pair recorded under another workspace.
    Rules: `assignment_exists` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1, workspace_id=w2.id)

    result = dao.assignment_exists(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False


# [claude] ATA-AE-03
def test_ata_ae_03__a_link_of_a_closed_account_to_a_deleted_tag_counts(db, w1, u1, a1, mk_tag, link):
    """ATA-AE-03 — a link of a closed account to a deleted tag counts.
    Rules: `assignment_exists` R2 (P1)"""
    close(db, a1, u1)
    td = mk_tag(name="Old", tag_code="old", is_active=False)
    link(td)

    result = dao.assignment_exists(db, account_id=a1.id, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is True


# --------------------------------------------------------------------------- #
# AccountTagAssignmentDAO.delete_assignment
# --------------------------------------------------------------------------- #


# [claude] ATA-DA-01
def test_ata_da_01__the_link_is_hard_deleted_and_flushed_true_the_tag_s_counter_is(db, w1, a1, mk_tag, link):
    """ATA-DA-01 — the link is hard-deleted and flushed; True; the tag's counter is untouched.
    Rules: `delete_assignment` R1, R3"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=4)
    t2 = mk_tag(name="Client", tag_code="client")
    link(t1)
    link(t2)

    result = dao.delete_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is True
    # Then 2
    assert dao.get_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id) is None
    # Then 3
    assert links(db, a1, w1) == 1
    # Then 4
    assert stored_count(db, t1) == 4


# [claude] ATA-DA-02
def test_ata_da_02__the_pair_under_another_workspace_false_nothing_deleted(db, w1, w2, a1, mk_tag, link):
    """ATA-DA-02 — the pair under another workspace: False, nothing deleted.
    Rules: `delete_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    l1 = link(t1, workspace_id=w2.id)
    before = written_counts(db)
    before_l1 = snap(db, l1)

    result = dao.delete_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert written_counts(db) == before
    # Then 3
    assert snap(db, l1) == before_l1


# [claude] ATA-DA-03
def test_ata_da_03__calling_again_after_a_delete_returns_false(db, w1, a1, mk_tag, link):
    """ATA-DA-03 — calling again after a delete returns False.
    Rules: `delete_assignment` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)
    assert dao.delete_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id) is True

    result = dao.delete_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is False
    # Then 2
    assert links(db, a1, w1) == 0


# [claude] ATA-DA-04
def test_ata_da_04__a_link_of_a_closed_account_to_a_deleted_tag_is_deleted(db, w1, u1, a1, mk_tag, link):
    """ATA-DA-04 — a link of a closed account to a deleted tag is deleted.
    Rules: `delete_assignment` R3 (P1)"""
    close(db, a1, u1)
    td = mk_tag(name="Old", tag_code="old", is_active=False, usage_count=2)
    link(td)

    result = dao.delete_assignment(db, account_id=a1.id, tag_id=td.id, workspace_id=w1.id)

    # Then 1
    assert result is True
    # Then 2
    assert links(db, a1, w1) == 0
    # Then 3
    assert stored_count(db, td) == 2


# [claude] ATA-DA-05
def test_ata_da_05__flushed_not_committed_a_rollback_restores_the_link(db, w1, a1, mk_tag, link):
    """ATA-DA-05 — flushed, not committed: a rollback restores the link.
    Rules: `delete_assignment` R1, Side effects"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.delete_assignment(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

        # Then 1
        assert result is True
        # Then 2
        assert links(db, a1, w1) == 0
        # Then 3
        sp.rollback()
        assert links(db, a1, w1) == 1
        # Then 4
        assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# AccountTagAssignmentDAO.remove_all_tags_from_account
# --------------------------------------------------------------------------- #


# [claude] ATA-RA-01
def test_ata_ra_01__every_link_of_the_account_is_removed_and_each_counter_lowered_never(db, w1, w2, a1, mk_tag, link):
    """ATA-RA-01 — every link of the account is removed and each counter lowered, never below 0.
    Rules: `remove_all_tags_from_account` R1, R2, R3, Returns"""
    tz = mk_tag(name="Zulu", tag_code="zulu", usage_count=3)
    to = mk_tag(name="Old", tag_code="old", is_active=False, usage_count=2)
    tw = mk_tag(name="Far", tag_code="far", workspace_id=w2.id, usage_count=5)
    t0 = mk_tag(name="Zero", tag_code="zero", usage_count=0)
    link(tz)
    link(to)
    link(tw)
    link(t0)
    before_a1 = snap(db, a1)

    result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result == 4
    # Then 2
    assert links(db, a1, w1) == 0
    # Then 3
    assert stored_count(db, tz) == 2
    # Then 4
    assert stored_count(db, to) == 1
    # Then 5
    assert stored_count(db, tw) == 5
    # Then 6
    assert stored_count(db, t0) == 0
    # Then 7
    row = reread(db, to)
    assert row.is_active is False
    assert row.name == "Old"
    # Then 8
    assert snap(db, a1) == before_a1


# [claude] ATA-RA-02
def test_ata_ra_02__links_of_another_account_and_links_under_another_workspace_stay(db, w1, w2, a1, a2, mk_tag, link):
    """ATA-RA-02 — links of another account and links under another workspace stay.
    Rules: `remove_all_tags_from_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    t2 = mk_tag(name="Client", tag_code="client", usage_count=2)
    link(t1)
    link(t1, account_id=a2.id)
    link(t2, workspace_id=w2.id)

    result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert links(db, a2, w1) == 1
    # Then 3
    assert links(db, a1, w2) == 1
    # Then 4
    assert stored_count(db, t2) == 2


# [claude] ATA-RA-03
def test_ata_ra_03__no_link_0_nothing_changes(db, w1, a1, a2, mk_tag, link):
    """ATA-RA-03 — no link: 0, nothing changes.
    Rules: `remove_all_tags_from_account` R4"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    link(t1, account_id=a2.id)
    before = written_counts(db)
    before_t1 = snap(db, t1)

    result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert written_counts(db) == before
    # Then 3
    assert snap(db, t1) == before_t1


# [claude] ATA-RA-04
def test_ata_ra_04__an_unflushed_link_is_not_counted_or_removed_the_method_s_flush_inserts(db, w1, a1, mk_tag, link):
    """ATA-RA-04 — an unflushed link is not counted or removed; the method's flush inserts it.
    Rules: `remove_all_tags_from_account` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    t2 = mk_tag(name="Client", tag_code="client", usage_count=2)
    link(t1)
    p = AccountTagAssignment(workspace_id=w1.id, account_id=a1.id, tag_id=t2.id)
    db.add(p)

    result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert links(db, a1, w1) == 1
    # Then 3
    assert dao.get_assignment(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id) is not None
    # Then 4
    assert stored_count(db, t2) == 2


# [claude] ATA-RA-05
def test_ata_ra_05__flushed_not_committed_a_rollback_restores_links_and_counters(db, w1, a1, mk_tag, link):
    """ATA-RA-05 — flushed, not committed: a rollback restores links and counters.
    Rules: `remove_all_tags_from_account` R6, Side effects"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
    link(t1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w1.id)

        # Then 1
        assert result == 1
        # Then 2
        assert links(db, a1, w1) == 0
        # Then 3
        sp.rollback()
        assert links(db, a1, w1) == 1
        # Then 4
        assert stored_count(db, t1) == 3
        # Then 5
        assert spy.call_count == 0


# [claude] ATA-RA-06
def test_ata_ra_06__asking_with_the_other_workspace_removes_nothing(db, w1, w2, a1, mk_tag, link):
    """ATA-RA-06 — asking with the other workspace removes nothing.
    Rules: `remove_all_tags_from_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    link(t1)

    result = dao.remove_all_tags_from_account(db, account_id=a1.id, workspace_id=w2.id)

    # Then 1
    assert result == 0
    # Then 2
    assert links(db, a1, w1) == 1
    # Then 3
    assert stored_count(db, t1) == 2


# [claude] ATA-RA-07
def test_ata_ra_07__another_account_s_call_removes_nothing_of_a1(db, w1, a1, a2, mk_tag, link):
    """ATA-RA-07 — another account's call removes nothing of A1.
    Rules: `remove_all_tags_from_account` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=2)
    link(t1)

    result = dao.remove_all_tags_from_account(db, account_id=a2.id, workspace_id=w1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert links(db, a1, w1) == 1
    # Then 3
    assert stored_count(db, t1) == 2


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on AccountTagAssignment
# --------------------------------------------------------------------------- #


# [claude] ATA-INH-01
def test_ata_inh_01__create_with_a_dict_stores_the_link_with_assigned_at_set(db, w1, a1, mk_tag):
    """ATA-INH-01 — create with a dict stores the link with assigned_at set.
    Rules: inherited R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")

    result = dao.create(db, obj_in={"workspace_id": w1.id, "account_id": a1.id, "tag_id": t1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.account_id == a1.id
    assert row.tag_id == t1.id
    # Then 3
    assert row.assigned_at is not None
    assert row.assigned_by is None


# [claude] ATA-INH-02
def test_ata_inh_02__create_with_an_accounttagassignmentcreate_fails_on_flush_no(db, a1, mk_tag):
    """ATA-INH-02 — create with an AccountTagAssignmentCreate fails on flush (no workspace_id).
    Rules: inherited R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    before = written_counts(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=AccountTagAssignmentCreate(account_id=a1.id, tag_id=t1.id))
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert written_counts(db) == before


# [claude] ATA-INH-03
def test_ata_inh_03__a_second_link_for_the_same_pair_under_another_workspace_is_refused(db, w2, a1, mk_tag, link):
    """ATA-INH-03 — a second link for the same pair under another workspace is refused.
    Rules: inherited R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    link(t1)
    before = written_counts(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w2.id, "account_id": a1.id, "tag_id": t1.id})
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert "uq_account_tag" in str(exc.value.orig)
    # Then 3
    assert written_counts(db) == before


# [claude] ATA-INH-04
def test_ata_inh_04__an_unknown_tag_is_refused_23503(db, w1, a1):
    """ATA-INH-04 — an unknown tag is refused (23503).
    Rules: inherited R2"""
    before = written_counts(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "account_id": a1.id, "tag_id": MISSING})
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert written_counts(db) == before
