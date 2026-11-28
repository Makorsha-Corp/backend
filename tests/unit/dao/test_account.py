"""Unit tests for app/dao/account.py.

Implements tests/unit/dao/account.cases.md, one test per case, in card order. Real
Postgres session (`db` fixture). Nothing is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`, and naive datetimes)
from datetime import date, datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.account import account_dao
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.schemas.account import AccountCreate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton account_dao"
dao = account_dao

# Convention "MISSING": an id no row of any table has
MISSING = 999999999

BUG_878 = "BUG-878: Deactivated accounts cannot be listed"
BUG_637 = "BUG-637: Whitespace-only search is not treated as no filter (name not trimmed)"
BUG_868 = "BUG-868: `%` and `_` in account name search act as wildcards"
BUG_861 = "BUG-861: Account tag-code filter is exact and case-sensitive"
BUG_864 = "BUG-864: Filtering accounts by a deleted tag still returns them"
BUG_866 = "BUG-866: Account search has no sort order"
NON_STRICT = " (non-strict: today's order is the plan's physical order, which can match by accident)"


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (W1, W2, U1; every test, flushed in this order)
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


@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

# Convention "account": W1, active, not deleted; the card gives name and every other column after "but"
@pytest.fixture
def mk_account(db, w1):
    """mk_account(name=..., **columns) -> Account, added and flushed."""
    def _mk(*, name, **columns):
        return _add(db, Account(**{"workspace_id": w1.id, "is_active": True, "is_deleted": False, "name": name, **columns}))
    return _mk


# Convention "closed": is_deleted True, is_active False, deleted_at, deleted_by U1
@pytest.fixture
def closed(u1):
    return {"is_deleted": True, "is_active": False, "deleted_at": datetime(2026, 3, 1, 9, 0, 0), "deleted_by": u1.id}


# Convention "half-closed": is_deleted True, is_active True
HALF_CLOSED = {"is_deleted": True, "is_active": True}


# Convention "tag": W1, not a system tag, active, usage_count 0; the card gives name and tag_code
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name=..., tag_code=..., **columns) -> AccountTag, added and flushed."""
    def _mk(*, name, tag_code, **columns):
        return _add(db, AccountTag(**{
            "workspace_id": w1.id, "is_system_tag": False, "is_active": True, "usage_count": 0,
            "name": name, "tag_code": tag_code, **columns,
        }))
    return _mk


# Convention "link(A, T)": W1; the columns after "but" as keywords
@pytest.fixture
def link(db, w1):
    """link(a, t, **columns) -> AccountTagAssignment, added and flushed."""
    def _mk(a, t, **columns):
        return _add(db, AccountTagAssignment(**{"workspace_id": w1.id, "account_id": a.id, "tag_id": t.id, **columns}))
    return _mk


# Convention "bumpA(X)"
def bump_a(db, x):
    db.execute(text("UPDATE accounts SET city = coalesce(city, '') || '!' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# Convention "seqscan": three steps, in this order
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# Convention "bulk(n)": accounts "Acct 001" ... built with add_all and flushed
def bulk(db, w1, n):
    rows = [Account(workspace_id=w1.id, is_active=True, is_deleted=False, name=f"Acct {k:03d}") for k in range(1, n + 1)]
    db.add_all(rows)
    db.flush()
    return rows


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)" / "names(result)": in the order returned
def ids(result):
    return [a.id for a in result]


def names(result):
    return [a.name for a in result]


def _id_of(row):
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(type(row)).where(type(row).id == row_id)).scalar_one_or_none()


# Convention "nothing written": accounts and account_tag_assignments rows (all workspaces)
def written_counts(db):
    return (
        db.scalar(select(func.count()).select_from(Account.__table__)),
        db.scalar(select(func.count()).select_from(AccountTagAssignment.__table__)),
    )


# "count:" lines: rows in all workspaces, with the filter stated
def count_rows(db, model, *where):
    return db.scalar(select(func.count()).select_from(model.__table__).where(*where))


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
        """The one SELECT from `accounts`; fails loudly unless there is exactly one."""
        [statement] = [
            s for s in self.statements if s.lstrip().upper().startswith("SELECT") and "FROM accounts" in s
        ]
        return statement


# Convention "order_part": after ORDER BY and before LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AccountDAO.get_accounts_in_workspace
# --------------------------------------------------------------------------- #


# [claude] ACC-IW-01
def test_acc_iw_01__returns_a_list_of_the_workspace_s_live_active_accounts(db, w1, mk_account):
    """ACC-IW-01 — returns a list of the workspace's live, active accounts.
    Rules: `get_accounts_in_workspace` R1, R2 (`name=None`), R4 (`tag_code=None`), Returns"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 3
    assert isinstance(result[0], Account)


# [claude] ACC-IW-02
def test_acc_iw_02__an_inactive_account_is_not_returned(db, w1, mk_account):
    """ACC-IW-02 — an inactive account is not returned.
    Rules: `get_accounts_in_workspace` R1"""
    mk_account(name="Aaa", is_active=False)
    a1 = mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-03
def test_acc_iw_03__a_closed_account_is_not_returned(db, w1, mk_account, closed):
    """ACC-IW-03 — a closed account is not returned.
    Rules: `get_accounts_in_workspace` R1"""
    mk_account(name="Aaa", **closed)
    a1 = mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-04
def test_acc_iw_04__a_deleted_account_still_marked_active_is_not_returned(db, w1, mk_account):
    """ACC-IW-04 — a deleted account still marked active is not returned.
    Rules: `get_accounts_in_workspace` R1"""
    mk_account(name="Aaa", **HALF_CLOSED)
    a1 = mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-05
def test_acc_iw_05__other_workspaces_accounts_before_and_after_by_id_are_not_returned(db, w1, w2, mk_account):
    """ACC-IW-05 — other workspaces' accounts, before and after by id, are not returned.
    Rules: `get_accounts_in_workspace` R1"""
    mk_account(name="Acme Far", workspace_id=w2.id)
    a1 = mk_account(name="Acme Ltd")
    mk_account(name="Acme Far 2", workspace_id=w2.id)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-06
@pytest.mark.xfail(strict=True, reason=BUG_878)
def test_acc_iw_06__include_inactive_true_also_returns_inactive_not_deleted_accounts(db, w1, w2, mk_account, closed):
    """ACC-IW-06 — include_inactive=True also returns inactive, not deleted accounts.
    Rules: `get_accounts_in_workspace` R1a [BUG-878]"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co", is_active=False)
    mk_account(name="Gone Co", **closed)
    mk_account(name="Far Co", workspace_id=w2.id, is_active=False)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, include_inactive=True)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]


# [claude] ACC-IW-07
def test_acc_iw_07__an_empty_name_means_no_name_filter(db, w1, mk_account):
    """ACC-IW-07 — an empty name means no name filter.
    Rules: `get_accounts_in_workspace` R2"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="")

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]


# [claude] ACC-IW-08
@pytest.mark.xfail(strict=True, reason=BUG_637)
def test_acc_iw_08__a_name_of_only_spaces_means_no_name_filter(db, w1, mk_account):
    """ACC-IW-08 — a name of only spaces means no name filter.
    Rules: `get_accounts_in_workspace` R2 [BUG-637]"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="   ")

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]


# [claude] ACC-IW-09
@pytest.mark.xfail(strict=True, reason=BUG_637)
def test_acc_iw_09__the_name_is_trimmed_acme_finds_acme_ltd(db, w1, mk_account):
    """ACC-IW-09 — the name is trimmed: " acme " finds "Acme Ltd".
    Rules: `get_accounts_in_workspace` R2 [BUG-637]"""
    a1 = mk_account(name="Acme Ltd")
    mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name=" acme ")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-10
def test_acc_iw_10__the_name_matches_anywhere_case_insensitively(db, w1, mk_account):
    """ACC-IW-10 — the name matches anywhere, case-insensitively.
    Rules: `get_accounts_in_workspace` R3"""
    a1 = mk_account(name="Acme Ltd")
    mk_account(name="Beta Co")
    mk_account(name="Acme")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="ME L")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-11
@pytest.mark.xfail(strict=True, reason=BUG_868)
def test_acc_iw_11__in_the_text_matches_itself_50_finds_50_off_not_500_ltd(db, w1, mk_account):
    """ACC-IW-11 — "%" in the text matches itself: "50%" finds "50% off", not "500 Ltd".
    Rules: `get_accounts_in_workspace` R3 [BUG-868]"""
    a1 = mk_account(name="50% off")
    mk_account(name="500 Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="50%")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-12
@pytest.mark.xfail(strict=True, reason=BUG_868)
def test_acc_iw_12__alone_finds_only_names_containing(db, w1, mk_account):
    """ACC-IW-12 — "_" alone finds only names containing "_".
    Rules: `get_accounts_in_workspace` R3 [BUG-868]"""
    mk_account(name="Acme Ltd")
    a2 = mk_account(name="a_b Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="_")

    # Then 1
    assert ids(result) == [a2.id]


# [claude] ACC-IW-13
@pytest.mark.xfail(strict=True, reason=BUG_868)
def test_acc_iw_13__a_backslash_matches_itself(db, w1, mk_account):
    """ACC-IW-13 — a backslash matches itself.
    Rules: `get_accounts_in_workspace` R3 [BUG-868]"""
    a1 = mk_account(name="C:\\dir Co")
    mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="\\")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-14
def test_acc_iw_14__an_empty_tag_code_means_no_tag_filter(db, w1, mk_account, mk_tag, link):
    """ACC-IW-14 — an empty tag code means no tag filter.
    Rules: `get_accounts_in_workspace` R4"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="")

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]


# [claude] ACC-IW-15
def test_acc_iw_15__a_tag_code_keeps_only_accounts_with_a_link_to_a_tag_of_that_code(db, w1, mk_account, mk_tag, link):
    """ACC-IW-15 — a tag code keeps only accounts with a link to a tag of that code.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    mk_account(name="Gamma")
    link(a1, t1)
    link(a2, t2)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-16
def test_acc_iw_16__a_link_recorded_under_another_workspace_does_not_count(db, w1, w2, mk_account, mk_tag, link):
    """ACC-IW-16 — a link recorded under another workspace does not count.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1, workspace_id=w2.id)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-17
@pytest.mark.xfail(strict=True, reason=BUG_861)
def test_acc_iw_17__the_tag_code_ignores_case_supplier_matches_supplier(db, w1, mk_account, mk_tag, link):
    """ACC-IW-17 — the tag code ignores case: "Supplier" matches "supplier".
    Rules: `get_accounts_in_workspace` R5 [BUG-861]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="Supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-18
@pytest.mark.xfail(strict=True, reason=BUG_861)
def test_acc_iw_18__the_tag_code_is_trimmed_supplier_matches_supplier(db, w1, mk_account, mk_tag, link):
    """ACC-IW-18 — the tag code is trimmed: "supplier " matches "supplier".
    Rules: `get_accounts_in_workspace` R5 [BUG-861]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier ")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-19
@pytest.mark.xfail(strict=True, reason=BUG_861 + " (stored side: read as covering the stored code too, Spec gap 3)")
def test_acc_iw_19__stored_side_a_stored_code_supplier_is_found_by_supplier(db, w1, mk_account, mk_tag, link):
    """ACC-IW-19 — stored side: a stored code "Supplier" is found by "supplier".
    Rules: `get_accounts_in_workspace` R5 [BUG-861]"""
    t1 = mk_tag(name="Supplier", tag_code="Supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-20
def test_acc_iw_20__a_part_of_the_code_does_not_match(db, w1, mk_account, mk_tag, link):
    """ACC-IW-20 — a part of the code does not match.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supp")

    # Then 1
    assert result == []


# [claude] ACC-IW-21
def test_acc_iw_21__in_the_code_is_not_a_wildcard(db, w1, mk_account, mk_tag, link):
    """ACC-IW-21 — "_" in the code is not a wildcard.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="s_pplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-22
@pytest.mark.xfail(strict=True, reason=BUG_864)
def test_acc_iw_22__an_account_whose_only_tag_with_that_code_is_deleted_is_not_returned(db, w1, mk_account, mk_tag, link):
    """ACC-IW-22 — an account whose only tag with that code is deleted is not returned.
    Rules: `get_accounts_in_workspace` R6 [BUG-864]"""
    td = mk_tag(name="Supplier", tag_code="supplier", is_active=False)
    a1 = mk_account(name="Acme Ltd")
    link(a1, td)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-23
def test_acc_iw_23__with_an_active_and_a_deleted_tag_of_one_code_the_active_one_decides(db, w1, mk_account, mk_tag, link):
    """ACC-IW-23 — with an active and a deleted tag of one code, the active one decides; returned once.
    Rules: `get_accounts_in_workspace` R6, R7"""
    td = mk_tag(name="Supplier old", tag_code="supplier", is_active=False)
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, td)
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-24
def test_acc_iw_24__two_active_tags_of_one_code_on_one_account_the_account_once(db, w1, mk_account, mk_tag, link):
    """ACC-IW-24 — two active tags of one code on one account: the account once.
    Rules: `get_accounts_in_workspace` R7"""
    t1 = mk_tag(name="Supplier A", tag_code="supplier")
    t2 = mk_tag(name="Supplier B", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)
    link(a1, t2)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-25
def test_acc_iw_25__a_link_in_this_workspace_to_another_workspace_s_tag_with_that_code(db, w1, w2, mk_account, mk_tag, link):
    """ACC-IW-25 — a link in this workspace to another workspace's tag with that code matches.
    Rules: `get_accounts_in_workspace` R7"""
    z1 = mk_tag(name="Supplier", tag_code="supplier", workspace_id=w2.id)
    a1 = mk_account(name="Acme Ltd")
    link(a1, z1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-26
def test_acc_iw_26__name_and_tag_code_together_both_must_hold(db, w1, mk_account, mk_tag, link):
    """ACC-IW-26 — name and tag code together: both must hold.
    Rules: `get_accounts_in_workspace` R9"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    mk_account(name="Acme Two")
    a3 = mk_account(name="Beta Co")
    link(a1, t1)
    link(a3, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="acme", tag_code="supplier")

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-27
@pytest.mark.xfail(strict=False, reason=BUG_866 + NON_STRICT)
def test_acc_iw_27__ordered_by_name_case_insensitive_then_id(db, w1, mk_account):
    """ACC-IW-27 — ordered by name case-insensitive, then id.
    Rules: `get_accounts_in_workspace` R8 [BUG-866]"""
    mk_account(name="Zulu")
    a2 = mk_account(name="apple")
    mk_account(name="Banana")
    mk_account(name="mango")
    mk_account(name="Kilo")
    mk_account(name="delta")
    seqscan(db)
    bump_a(db, a2)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 6
    # Then 2
    assert names(result) == ["apple", "Banana", "delta", "Kilo", "mango", "Zulu"]


# [claude] ACC-IW-28
@pytest.mark.xfail(strict=True, reason=BUG_866)
def test_acc_iw_28__the_query_orders_by_name_case_insensitive_then_id(db, w1, mk_account):
    """ACC-IW-28 — the query orders by name case-insensitive, then id.
    Rules: `get_accounts_in_workspace` R8 [BUG-866]"""
    a1 = mk_account(name="Acme Ltd")

    with StatementRecorder(db) as recorder:
        result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(accounts.name)" in order_part
    # Then 4
    assert "accounts.id" in order_part
    # Then 5
    assert "DESC" not in order_part.upper()


# [claude] ACC-IW-29
def test_acc_iw_29__the_default_limit_is_100_107_accounts_give_100(db, w1):
    """ACC-IW-29 — the default limit is 100: 107 accounts give 100.
    Rules: `get_accounts_in_workspace` R10"""
    bulk(db, w1, 107)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100


# [claude] ACC-IW-30
def test_acc_iw_30__limit_1000_returns_all_107(db, w1):
    """ACC-IW-30 — limit=1000 returns all 107.
    Rules: `get_accounts_in_workspace` R10"""
    bulk(db, w1, 107)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, limit=1000)

    # Then 1
    assert len(result) == 107


# [claude] ACC-IW-31
def test_acc_iw_31__limit_0_returns_an_empty_list(db, w1, mk_account):
    """ACC-IW-31 — limit=0 returns an empty list.
    Rules: `get_accounts_in_workspace` R10"""
    mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ACC-IW-32
def test_acc_iw_32__skip_past_the_end_returns_an_empty_list(db, w1, mk_account):
    """ACC-IW-32 — skip past the end returns an empty list.
    Rules: `get_accounts_in_workspace` R10"""
    mk_account(name="Acme Ltd")
    mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] ACC-IW-33
def test_acc_iw_33__a_negative_limit_raises_dataerror_2201w(db, w1, mk_account):
    """ACC-IW-33 — a negative limit raises DataError 2201W.
    Rules: `get_accounts_in_workspace` R10, Errors row 1"""
    mk_account(name="Acme Ltd")
    before = written_counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_accounts_in_workspace(db, workspace_id=w1.id, limit=-1)
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert written_counts(db) == before


# [claude] ACC-IW-34
def test_acc_iw_34__a_negative_skip_raises_dataerror_2201x(db, w1, mk_account):
    """ACC-IW-34 — a negative skip raises DataError 2201X.
    Rules: `get_accounts_in_workspace` R10, Errors row 2"""
    mk_account(name="Acme Ltd")
    before = written_counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_accounts_in_workspace(db, workspace_id=w1.id, skip=-1)
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert written_counts(db) == before


# [claude] ACC-IW-35
def test_acc_iw_35__filters_run_before_paging_a_hidden_account_does_not_take_the_one_place(db, w1, mk_account):
    """ACC-IW-35 — filters run before paging: a hidden account does not take the one place.
    Rules: `get_accounts_in_workspace` R10"""
    mk_account(name="Aaa", is_active=False)
    mk_account(name="Aab", **HALF_CLOSED)
    a1 = mk_account(name="Acme Ltd")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-36
def test_acc_iw_36__the_read_writes_nothing_and_keeps_the_caller_s_pending_changes(db, w1, w2, mk_account):
    """ACC-IW-36 — the read writes nothing and keeps the caller's pending changes.
    Rules: `get_accounts_in_workspace` Side effects"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co", workspace_id=w2.id)
    a2.name = "Beta Edited"
    p = Account(workspace_id=w1.id, name="Pending", is_active=True, is_deleted=False)
    db.add(p)
    before = written_counts(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_accounts_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert written_counts(db) == before


# [claude] ACC-IW-37
def test_acc_iw_37__asking_with_the_other_workspace_returns_only_its_account_not_an(db, w2, mk_account):
    """ACC-IW-37 — asking with the other workspace returns only its account, not an earlier-id W1 account.
    Rules: `get_accounts_in_workspace` R1"""
    mk_account(name="Acme Far")
    a1 = mk_account(name="Acme Ltd", workspace_id=w2.id)

    result = dao.get_accounts_in_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-IW-38
def test_acc_iw_38__a_w2_account_whose_link_is_recorded_in_w1_is_not_found_from_w2(db, w2, mk_account, mk_tag, link):
    """ACC-IW-38 — a W2 account whose link is recorded in W1 is not found from W2.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier", workspace_id=w2.id)
    a1 = mk_account(name="Acme Ltd", workspace_id=w2.id)
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w2.id, tag_code="supplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-39
def test_acc_iw_39__the_end_of_the_code_does_not_match(db, w1, mk_account, mk_tag, link):
    """ACC-IW-39 — the end of the code does not match.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="plier")

    # Then 1
    assert result == []


# [claude] ACC-IW-40
def test_acc_iw_40__stored_side_a_stored_code_that_is_a_part_of_the_argument_does_not_match(db, w1, mk_account, mk_tag, link):
    """ACC-IW-40 — stored side: a stored code that is a part of the argument does not match.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supp")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-41
def test_acc_iw_41__stored_side_in_the_stored_code_is_not_a_wildcard(db, w1, mk_account, mk_tag, link):
    """ACC-IW-41 — stored side: "_" in the stored code is not a wildcard.
    Rules: `get_accounts_in_workspace` R5"""
    t1 = mk_tag(name="Supplier", tag_code="s_pplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result == []


# [claude] ACC-IW-42
def test_acc_iw_42__an_account_with_two_matching_links_takes_one_place_in_the_page(db, w1, mk_account, mk_tag, link):
    """ACC-IW-42 — an account with two matching links takes one place in the page.
    Rules: `get_accounts_in_workspace` R7, R10"""
    t1 = mk_tag(name="Supplier A", tag_code="supplier")
    t2 = mk_tag(name="Supplier B", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    link(a1, t1)
    link(a1, t2)
    link(a2, t1)

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, tag_code="supplier", limit=2)

    # Then 1
    assert sorted(ids(result)) == [a1.id, a2.id]


# [claude] ACC-IW-43
@pytest.mark.xfail(strict=True, reason=BUG_637)
def test_acc_iw_43__a_trailing_space_is_trimmed_ltd_finds_acme_ltd(db, w1, mk_account):
    """ACC-IW-43 — a trailing space is trimmed: "ltd " finds "Acme Ltd".
    Rules: `get_accounts_in_workspace` R2 [BUG-637]"""
    a1 = mk_account(name="Acme Ltd")
    mk_account(name="Beta Co")

    result = dao.get_accounts_in_workspace(db, workspace_id=w1.id, name="ltd ")

    # Then 1
    assert ids(result) == [a1.id]


# --------------------------------------------------------------------------- #
# AccountDAO.count_active_accounts
# --------------------------------------------------------------------------- #


# [claude] ACC-CNT-01
def test_acc_cnt_01__counts_only_live_active_accounts_of_the_workspace(db, w1, w2, mk_account, closed):
    """ACC-CNT-01 — counts only live, active accounts of the workspace.
    Rules: `count_active_accounts` R1, Returns"""
    mk_account(name="Acme Ltd")
    mk_account(name="Beta Co")
    mk_account(name="Idle", is_active=False)
    mk_account(name="Gone", **closed)
    mk_account(name="Half", **HALF_CLOSED)
    mk_account(name="Far", workspace_id=w2.id)

    result = dao.count_active_accounts(db, workspace_id=w1.id)

    # Then 1
    assert type(result) is int
    # Then 2
    assert result == 2


# [claude] ACC-CNT-02
def test_acc_cnt_02__no_cap_107_live_accounts_count_107(db, w1):
    """ACC-CNT-02 — no cap: 107 live accounts count 107.
    Rules: `count_active_accounts` R2"""
    bulk(db, w1, 107)

    result = dao.count_active_accounts(db, workspace_id=w1.id)

    # Then 1
    assert result == 107


# [claude] ACC-CNT-03
def test_acc_cnt_03__an_unknown_workspace_counts_0(db, mk_account):
    """ACC-CNT-03 — an unknown workspace counts 0.
    Rules: `count_active_accounts` R3"""
    mk_account(name="Acme Ltd")

    result = dao.count_active_accounts(db, workspace_id=MISSING)

    # Then 1
    assert result == 0


# --------------------------------------------------------------------------- #
# AccountDAO.get_accounts_by_tag_id
# --------------------------------------------------------------------------- #


# [claude] ACC-BT-01
def test_acc_bt_01__returns_the_live_active_accounts_linked_to_the_tag_in_the_workspace(db, w1, mk_account, mk_tag, link):
    """ACC-BT-01 — returns the live, active accounts linked to the tag in the workspace.
    Rules: `get_accounts_by_tag_id` R1, Returns"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    t2 = mk_tag(name="Client", tag_code="client")
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    a3 = mk_account(name="Gamma")
    link(a1, t1)
    link(a2, t1)
    link(a3, t2)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a1.id, a2.id]
    # Then 3
    assert isinstance(result[0], Account)


# [claude] ACC-BT-02
def test_acc_bt_02__an_inactive_account_is_left_out(db, w1, mk_account, mk_tag, link):
    """ACC-BT-02 — an inactive account is left out.
    Rules: `get_accounts_by_tag_id` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    ai = mk_account(name="Idle", is_active=False)
    a1 = mk_account(name="Acme Ltd")
    link(ai, t1)
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-BT-03
def test_acc_bt_03__a_deleted_account_still_marked_active_is_left_out(db, w1, mk_account, mk_tag, link):
    """ACC-BT-03 — a deleted account still marked active is left out.
    Rules: `get_accounts_by_tag_id` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    ah = mk_account(name="Half", **HALF_CLOSED)
    a1 = mk_account(name="Acme Ltd")
    link(ah, t1)
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-BT-04
def test_acc_bt_04__a_link_recorded_under_another_workspace_does_not_count(db, w1, w2, mk_account, mk_tag, link):
    """ACC-BT-04 — a link recorded under another workspace does not count.
    Rules: `get_accounts_by_tag_id` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1, workspace_id=w2.id)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert result == []


# [claude] ACC-BT-05
def test_acc_bt_05__asking_with_another_workspace_returns_an_empty_list(db, w2, mk_account, mk_tag, link):
    """ACC-BT-05 — asking with another workspace returns an empty list.
    Rules: `get_accounts_by_tag_id` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w2.id, tag_id=t1.id)

    # Then 1
    assert result == []


# [claude] ACC-BT-06
def test_acc_bt_06__an_unknown_tag_returns_an_empty_list(db, w1, mk_account, mk_tag, link):
    """ACC-BT-06 — an unknown tag returns an empty list.
    Rules: `get_accounts_by_tag_id` R2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=MISSING)

    # Then 1
    assert result == []


# [claude] ACC-BT-07
def test_acc_bt_07__a_deleted_tag_gives_an_empty_list_its_links_stay(db, w1, mk_account, mk_tag, link):
    """ACC-BT-07 — a deleted tag gives an empty list; its links stay.
    Rules: `get_accounts_by_tag_id` R3 [BUG-1481]"""
    td = mk_tag(name="Old", tag_code="old", is_active=False)
    a1 = mk_account(name="Acme Ltd")
    link(a1, td)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=td.id)

    # Then 1
    assert count_rows(db, AccountTagAssignment, AccountTagAssignment.tag_id == td.id) == 1
    # Then 2
    assert result == []


# [claude] ACC-BT-08
def test_acc_bt_08__ordered_by_name_case_insensitive_then_id(db, w1, mk_account, mk_tag, link):
    """ACC-BT-08 — ordered by name case-insensitive, then id.
    Rules: `get_accounts_by_tag_id` R4 [BUG-1480]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Zulu")
    a2 = mk_account(name="apple")
    a3 = mk_account(name="Banana")
    link(a1, t1)
    link(a2, t1)
    link(a3, t1)
    seqscan(db)
    bump_a(db, a2)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert names(result) == ["apple", "Banana", "Zulu"]


# [claude] ACC-BT-09
def test_acc_bt_09__the_query_orders_by_name_case_insensitive_then_id(db, w1, mk_account, mk_tag, link):
    """ACC-BT-09 — the query orders by name case-insensitive, then id.
    Rules: `get_accounts_by_tag_id` R4 [BUG-1480]"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    with StatementRecorder(db) as recorder:
        result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(accounts.name)" in order_part
    # Then 4
    assert "accounts.id" in order_part
    # Then 5
    assert "DESC" not in order_part.upper()


# [claude] ACC-BT-10
def test_acc_bt_10__the_default_limit_is_100_101_linked_accounts_give_100(db, w1, mk_tag):
    """ACC-BT-10 — the default limit is 100: 101 linked accounts give 100.
    Rules: `get_accounts_by_tag_id` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    rows = bulk(db, w1, 101)
    for nk in rows:
        db.add(AccountTagAssignment(workspace_id=w1.id, account_id=nk.id, tag_id=t1.id))
    db.flush()

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert len(result) == 100


# [claude] ACC-BT-11
def test_acc_bt_11__limit_1000_returns_all_101_each_once(db, w1, mk_tag):
    """ACC-BT-11 — limit=1000 returns all 101, each once.
    Rules: `get_accounts_by_tag_id` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    rows = bulk(db, w1, 101)
    for nk in rows:
        db.add(AccountTagAssignment(workspace_id=w1.id, account_id=nk.id, tag_id=t1.id))
    db.flush()

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id, limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert len(set(ids(result))) == 101


# [claude] ACC-BT-12
def test_acc_bt_12__limit_0_returns_an_empty_list(db, w1, mk_account, mk_tag, link):
    """ACC-BT-12 — limit=0 returns an empty list.
    Rules: `get_accounts_by_tag_id` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id, limit=0)

    # Then 1
    assert result == []


# [claude] ACC-BT-13
def test_acc_bt_13__a_negative_limit_raises_dataerror_2201w(db, w1, mk_tag):
    """ACC-BT-13 — a negative limit raises DataError 2201W.
    Rules: `get_accounts_by_tag_id` R5, Errors row 1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    before = written_counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id, limit=-1)
    assert exc.value.orig.pgcode == "2201W"
    # Then 2
    assert written_counts(db) == before


# [claude] ACC-BT-14
def test_acc_bt_14__a_negative_skip_raises_dataerror_2201x(db, w1, mk_tag):
    """ACC-BT-14 — a negative skip raises DataError 2201X.
    Rules: `get_accounts_by_tag_id` R5, Errors row 2"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    before = written_counts(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id, skip=-1)
    assert exc.value.orig.pgcode == "2201X"
    # Then 2
    assert written_counts(db) == before


# [claude] ACC-BT-15
def test_acc_bt_15__filters_run_before_paging_a_hidden_account_does_not_take_the_one_place(db, w1, mk_account, mk_tag, link):
    """ACC-BT-15 — filters run before paging: a hidden account does not take the one place.
    Rules: `get_accounts_by_tag_id` R5"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    ai = mk_account(name="Aaa", is_active=False)
    a1 = mk_account(name="Acme Ltd")
    link(ai, t1)
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id, limit=1)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-BT-16
def test_acc_bt_16__the_read_writes_nothing_and_keeps_the_caller_s_pending_changes(db, w1, mk_account, mk_tag, link):
    """ACC-BT-16 — the read writes nothing and keeps the caller's pending changes.
    Rules: `get_accounts_by_tag_id` Side effects"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    link(a1, t1)
    a2.name = "Beta Edited"
    p = AccountTagAssignment(workspace_id=w1.id, account_id=a2.id, tag_id=t1.id)
    db.add(p)

    with StatementRecorder(db) as recorder:
        result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert ids(result) == [a1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a2 in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []


# [claude] ACC-BT-17
def test_acc_bt_17__another_workspace_s_account_linked_under_this_workspace_is_left_out(db, w1, w2, mk_account, mk_tag, link):
    """ACC-BT-17 — another workspace's account linked under this workspace is left out.
    Rules: `get_accounts_by_tag_id` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    z1 = mk_account(name="Far", workspace_id=w2.id)
    a1 = mk_account(name="Acme Ltd")
    link(z1, t1)
    link(a1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=t1.id)

    # Then 1
    assert ids(result) == [a1.id]


# [claude] ACC-BT-18
def test_acc_bt_18__from_w2_neither_a_w1_account_with_a_w2_link_nor_a_w2_account_with_a_w1(db, w2, mk_account, mk_tag, link):
    """ACC-BT-18 — from W2: neither a W1 account with a W2 link nor a W2 account with a W1 link counts.
    Rules: `get_accounts_by_tag_id` R1"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    z1 = mk_account(name="Far", workspace_id=w2.id)
    link(a1, t1, workspace_id=w2.id)
    link(z1, t1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w2.id, tag_id=t1.id)

    # Then 1
    assert result == []


# [claude] ACC-BT-19
def test_acc_bt_19__the_tag_s_own_workspace_is_not_compared_a_w1_link_to_a_w2_tag_counts(db, w1, w2, mk_account, mk_tag, link):
    """ACC-BT-19 — the tag's own workspace is not compared: a W1 link to a W2 tag counts.
    Rules: `get_accounts_by_tag_id` R2"""
    z1 = mk_tag(name="Supplier", tag_code="supplier", workspace_id=w2.id)
    a1 = mk_account(name="Acme Ltd")
    link(a1, z1)

    result = dao.get_accounts_by_tag_id(db, workspace_id=w1.id, tag_id=z1.id)

    # Then 1
    assert ids(result) == [a1.id]


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on Account
# --------------------------------------------------------------------------- #


# [claude] ACC-INH-01
def test_acc_inh_01__create_with_a_dict_stores_an_account_with_the_defaults(db, w1):
    """ACC-INH-01 — create with a dict stores an account with the defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Acme Ltd"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Acme Ltd"
    # Then 3
    assert row.allow_invoices is True
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 4
    assert row.created_at is not None
    # Then 5
    assert row.account_code is None
    assert row.city is None
    assert row.created_by is None
    assert row.deleted_at is None


# [claude] ACC-INH-02
def test_acc_inh_02__create_with_an_accountcreate_raises_typeerror_and_adds_nothing(db):
    """ACC-INH-02 — create with an AccountCreate raises TypeError and adds nothing.
    Rules: inherited R1"""
    before = written_counts(db)

    # Then 1
    with pytest.raises(TypeError) as exc:
        dao.create(db, obj_in=AccountCreate(name="Acme Ltd", tag_ids=[]))
    assert "tag_ids" in str(exc.value)
    # Then 2
    assert len(db.new) == 0
    # Then 3
    assert written_counts(db) == before


# [claude] ACC-INH-03
def test_acc_inh_03__update_with_a_dict_sets_the_column_the_database_sets_updated_at(db, mk_account):
    """ACC-INH-03 — update with a dict sets the column; the database sets updated_at.
    Rules: inherited R2"""
    a1 = mk_account(name="Acme Ltd")

    result = dao.update(db, db_obj=a1, obj_in={"name": "Acme Limited", "city": "Dhaka"})

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Acme Limited"
    assert row.city == "Dhaka"
    # Then 3
    assert row.updated_at is not None


# [claude] ACC-INH-04
def test_acc_inh_04__get_returns_a_closed_account_of_any_workspace(db, w2, mk_account, closed):
    """ACC-INH-04 — get returns a closed account of any workspace.
    Rules: inherited R3"""
    z1 = mk_account(name="Far", workspace_id=w2.id, **closed)

    result = dao.get(db, z1.id)

    # Then 1
    assert result.id == z1.id
    # Then 2
    assert result.is_deleted is True


# [claude] ACC-INH-05
def test_acc_inh_05__get_by_id_and_workspace_returns_a_closed_account(db, w1, mk_account, closed):
    """ACC-INH-05 — get_by_id_and_workspace returns a closed account.
    Rules: inherited R3"""
    ac = mk_account(name="Gone", **closed)

    result = dao.get_by_id_and_workspace(db, id=ac.id, workspace_id=w1.id)

    # Then 1
    assert result.id == ac.id


# [claude] ACC-INH-06
def test_acc_inh_06__get_by_id_and_workspace_returns_none_for_another_workspace_s_account(db, w1, w2, mk_account):
    """ACC-INH-06 — get_by_id_and_workspace returns None for another workspace's account.
    Rules: inherited R3"""
    mk_account(name="Acme Ltd")
    z1 = mk_account(name="Far", workspace_id=w2.id)
    mk_account(name="Beta Co")

    result = dao.get_by_id_and_workspace(db, id=z1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] ACC-INH-07
def test_acc_inh_07__remove_of_an_account_referenced_by_an_invoice_raises_23502_and_deletes(db, w1, mk_account):
    """ACC-INH-07 — remove of an account referenced by an invoice raises 23502 and deletes nothing.
    Rules: inherited R5 (c)"""
    a1 = mk_account(name="Acme Ltd")
    _add(db, AccountInvoice(
        workspace_id=w1.id, account_id=a1.id, invoice_type="payable", invoice_amount=100,
        invoice_date=date(2026, 3, 1),
    ))
    a1_id = a1.id

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.remove(db, id=a1_id)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert count_rows(db, Account, Account.id == a1_id) == 1
    # Then 3
    assert count_rows(db, AccountInvoice, AccountInvoice.account_id == a1_id) == 1


# [claude] ACC-INH-08
def test_acc_inh_08__remove_of_an_account_with_a_tag_link_raises_23502_and_deletes_nothing(db, mk_account, mk_tag, link):
    """ACC-INH-08 — remove of an account with a tag link raises 23502 and deletes nothing.
    Rules: inherited R5 (b)"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)
    a1_id = a1.id

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.remove(db, id=a1_id)
    assert exc.value.orig.pgcode == "23502"
    # Then 2
    assert count_rows(db, Account, Account.id == a1_id) == 1
    # Then 3
    assert count_rows(db, AccountTagAssignment, AccountTagAssignment.account_id == a1_id) == 1


# [claude] ACC-INH-09
def test_acc_inh_09__a_sql_delete_of_an_account_an_invoice_references_is_refused_with_23001(db, w1, mk_account):
    """ACC-INH-09 — a SQL DELETE of an account an invoice references is refused with 23001.
    Rules: inherited R5 (database side)"""
    a1 = mk_account(name="Acme Ltd")
    _add(db, AccountInvoice(
        workspace_id=w1.id, account_id=a1.id, invoice_type="payable", invoice_amount=100,
        invoice_date=date(2026, 3, 1),
    ))
    a1_id = a1.id

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("DELETE FROM accounts WHERE id = :i"), {"i": a1_id})
    assert exc.value.orig.pgcode == "23001"
    # Then 2
    assert count_rows(db, Account, Account.id == a1_id) == 1


# [claude] ACC-INH-10
def test_acc_inh_10__a_sql_delete_of_an_account_with_only_tag_links_cascades_to_the_links(db, mk_account, mk_tag, link):
    """ACC-INH-10 — a SQL DELETE of an account with only tag links cascades to the links.
    Rules: inherited R5 (database side)"""
    t1 = mk_tag(name="Supplier", tag_code="supplier")
    a1 = mk_account(name="Acme Ltd")
    link(a1, t1)
    a1_id = a1.id

    db.execute(text("DELETE FROM accounts WHERE id = :i"), {"i": a1_id})

    # Then 1
    assert count_rows(db, Account, Account.id == a1_id) == 0
    # Then 2
    assert count_rows(db, AccountTagAssignment, AccountTagAssignment.account_id == a1_id) == 0
    # Then 3
    assert count_rows(db, AccountTag, AccountTag.id == t1.id) == 1


# [claude] ACC-INH-11
def test_acc_inh_11__remove_of_an_account_with_no_references_deletes_it_and_returns_it(db, mk_account):
    """ACC-INH-11 — remove of an account with no references deletes it and returns it.
    Rules: inherited R5 (a)"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    a1_id = a1.id

    result = dao.remove(db, id=a1_id)

    # Then 1
    assert result.id == a1_id
    # Then 2
    assert count_rows(db, Account, Account.id == a1_id) == 0
    # Then 3
    assert count_rows(db, Account, Account.id == a2.id) == 1
