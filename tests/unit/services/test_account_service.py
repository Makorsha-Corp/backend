"""Unit tests for app/services/account_service.py.

Implements tests/unit/services/account_service.cases.md (revision 2), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()`
only releases a savepoint, so the test's own "commit point" and the service's
commits are safe and the fixture's outer rollback discards everything.

Patched, as Conventions name them: the commit / rollback spies (they still call
the real method), the failing commit / refresh, "mgr raises E on m"
(`svc.account_manager.<m>`), the hub manager (`mod.account_invoice_manager`)
in ASV-H-01, the instance read `svc.get_account_with_tags` in ASV-A-12 … A-14,
and the one race simulation of ASV-D-12. Nothing else is mocked.

Standing rows are attributes of the namespace `s` (`s.W1`, `s.U1`);
`# Then N` marks the checks of the card's Then line N.
"""

# ruff: noqa: SIM117, FURB157  (Conventions prescribe the nested `with`; cards write Decimal("0"))
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

import app.services.account_service as mod
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.financial_audit_log import FinancialAuditLog
from app.models.workspace import Workspace
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.account_service import AccountService, account_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

svc = account_service

MISSING = 999999999
T0 = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001  (naive, as the DateTime columns)
# em dash U+2014
OPEN = "Account has open invoices — settle or void them first"

KEYS = {
    "id",
    "workspace_id",
    "name",
    "account_code",
    "primary_contact_person",
    "primary_email",
    "primary_phone",
    "secondary_contact_person",
    "secondary_email",
    "secondary_phone",
    "address",
    "city",
    "country",
    "postal_code",
    "payment_preferences",
    "bank_details",
    "allow_invoices",
    "is_active",
    "created_at",
    "account_tags",
}
TAGKEYS = {"id", "name", "tag_code", "color", "icon", "is_system_tag"}

UNCHANGED_COLS = (
    "name",
    "account_code",
    "city",
    "is_active",
    "is_deleted",
    "deleted_at",
    "deleted_by",
    "updated_by",
)

BUG_871 = "BUG-871: Unknown tag ids silently dropped on account create / update"
BUG_874 = "BUG-874: Account code is not unique per workspace"
BUG_2987 = (
    "BUG-2987: Creating or updating an account accepts a deleted (inactive) tag "
    'that "assign tag" refuses'
)
BUG_140 = "BUG-140: Financial audit rows never record IP address or user agent"
BUG_862 = "BUG-862: `get_account` returns soft-deleted accounts"
BUG_865 = "BUG-865: `get_tags_for_account` returns deleted tags"
BUG_1486 = "BUG-1486: An account's tags have no sort order"
BUG_878 = "BUG-878: Deactivated accounts cannot be listed"
BUG_2986 = (
    "BUG-2986: Editing a missing account, or deleting an account twice, answers 500"
)
BUG_2982 = 'BUG-2982: "Accounts with tag N" answers 200 for a deleted tag'
BUG_863 = "BUG-863: Soft-deleted accounts can still be edited and tagged / untagged"
BUG_879 = "BUG-879: Removing an unassigned tag answers 422, API documents 404"
BUG_873 = (
    "BUG-873: Single-tag assign / unassign leave no audit row or `updated_by` stamp"
)
BUG_876 = "BUG-876: Account with open invoices can be deleted"
BUG_2984 = "BUG-2984: Refused account delete does not say which invoices block it"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test): W0, W1, W2, U1, U2
# --------------------------------------------------------------------------- #


@pytest.fixture
def s(db):
    n = SimpleNamespace()
    n.W0 = make_workspace(db)
    n.W1 = make_workspace(db)
    n.W2 = make_workspace(db)
    n.U1 = make_profile(db)
    n.U2 = make_profile(db)
    return n


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #


# Convention "gone" (after "but")
def gone(s):
    return {
        "is_deleted": True,
        "is_active": False,
        "deleted_at": T0,
        "deleted_by": s.U2.id,
    }


# Convention "account"; "but" overrides columns
def account(db, s, **but):
    fields = {"workspace_id": s.W1.id, "name": "Acme Ltd", "created_by": s.U2.id}
    fields.update(but)
    return _add(db, Account(**fields))


# Convention "tag"; "but" overrides columns
def tag(db, s, **but):
    fields = {"workspace_id": s.W1.id, "name": "Supplier", "tag_code": "supplier"}
    fields.update(but)
    return _add(db, AccountTag(**fields))


# Convention "account" as an unflushed row, for "by `add_all`" Given lines
def account_row(s, **but):
    fields = {"workspace_id": s.W1.id, "name": "Acme Ltd", "created_by": s.U2.id}
    fields.update(but)
    return Account(**fields)


# Convention "link(A, T)" as an unflushed row, for "by `add_all`" Given lines
def link_row(s, a, t, **but):
    fields = {
        "account_id": a.id,
        "tag_id": t.id,
        "workspace_id": s.W1.id,
        "assigned_by": s.U2.id,
        "assigned_at": T0,
    }
    fields.update(but)
    return AccountTagAssignment(**fields)


# Convention "link(A, T)"; "but" overrides columns
def link(db, s, a, t, **but):
    fields = {
        "account_id": a.id,
        "tag_id": t.id,
        "workspace_id": s.W1.id,
        "assigned_by": s.U2.id,
        "assigned_at": T0,
    }
    fields.update(but)
    return _add(db, AccountTagAssignment(**fields))


# Convention "invoice on A, state S": (invoice_status, paid_amount, payment_status, extra)
STATES = {
    "draft": {
        "invoice_status": "draft",
        "paid_amount": Decimal("0.00"),
        "payment_status": "unpaid",
    },
    "unpaid": {
        "invoice_status": "confirmed",
        "paid_amount": Decimal("0.00"),
        "payment_status": "unpaid",
    },
    "partial": {
        "invoice_status": "confirmed",
        "paid_amount": Decimal("400.00"),
        "payment_status": "partial",
    },
    "settled": {
        "invoice_status": "confirmed",
        "paid_amount": Decimal("1000.00"),
        "payment_status": "paid",
    },
    "voided": {
        "invoice_status": "voided",
        "paid_amount": Decimal("0.00"),
        "payment_status": "unpaid",
        "void_note": "x",
    },
}


def invoice(db, s, a, state, **but):
    fields = {
        "workspace_id": s.W1.id,
        "account_id": a.id,
        "invoice_type": "payable",
        "invoice_amount": Decimal("1000.00"),
        "invoice_date": date(2025, 3, 1),
    }
    fields.update(STATES[state])
    fields.update(but)
    return _add(db, AccountInvoice(**fields))


# Convention "commit point": the test commits; "nothing written" snapshot taken here
def commit_point(db):
    db.commit()
    return written(db)


# Convention "X": a pending row of another table, flushed, not committed
def mk_x(db):
    x = make_workspace(db)
    return x, x.id


# Named check "x_gone"
def x_gone(db, x_id):
    return db.get(Workspace, x_id) is None


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #


def _count(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


# Named check "nothing written": row counts (all workspaces) + every tag's usage_count
def written(db):
    return (
        _count(db, Account),
        _count(db, AccountTagAssignment),
        _count(db, FinancialAuditLog),
        tuple(
            db.execute(
                select(AccountTag.id, AccountTag.usage_count).order_by(AccountTag.id)
            ).all()
        ),
    )


# Named check "unchanged(A)": database values of the listed columns
def snap(db, account_id):
    db.expire_all()
    cols = [getattr(Account, c) for c in UNCHANGED_COLS]
    row = db.execute(select(*cols).where(Account.id == account_id)).one_or_none()
    return None if row is None else tuple(row)


# Named check "re-read A"
def reread(db, model, row_id):
    db.expire_all()
    return db.get(model, row_id)


# Named check "audit(A)"
def audit(db, entity_id):
    db.expire_all()
    return (
        db.execute(
            select(FinancialAuditLog)
            .where(
                FinancialAuditLog.entity_type == "account",
                FinancialAuditLog.entity_id == entity_id,
            )
            .order_by(FinancialAuditLog.id)
        )
        .scalars()
        .all()
    )


# rows of account_tag_assignments matching the filters, fresh query
def links(db, *where):
    db.expire_all()
    return db.execute(select(AccountTagAssignment).where(*where)).scalars().all()


# count of accounts matching the filters, fresh query
def acc_count(db, *where):
    return _count(db, Account, *where)


# Named check "loaded(r)"
def loaded(r):
    return inspect(r).expired_attributes.isdisjoint(
        {c.key for c in inspect(type(r)).column_attrs}
    )


# Named check "usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies"
@contextmanager
def spies(db):
    with (
        patch.object(db, "commit", wraps=db.commit) as cm,
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield cm, rb


# Convention "failing commit": the rollback spy is yielded
@contextmanager
def failing_commit(db):
    with (
        patch.object(db, "commit", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "failing refresh"
@contextmanager
def failing_refresh(db):
    with (
        patch.object(db, "refresh", side_effect=RuntimeError("boom")),
        patch.object(db, "rollback", wraps=db.rollback) as rb,
    ):
        yield rb


# Convention "mgr raises E on m"
@contextmanager
def mgr_raises(m, e):
    with patch.object(svc.account_manager, m, side_effect=e):
        yield


# Convention "Statement recorder": SQL text of every statement sent during the When
class record_sql:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.stmts = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.stmts.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False


# Race simulation of ASV-D-12: get_account hides deleted accounts unless include_deleted=True
@contextmanager
def hidden_deleted():
    real = svc.account_manager.get_account

    def hidden(*a, **k):
        return real(*a, **k) if k.get("include_deleted") else None

    with patch.object(svc.account_manager, "get_account", side_effect=hidden):
        yield


# --------------------------------------------------------------------------- #
# create_account
# --------------------------------------------------------------------------- #


# [claude] ASV-C-01
def test_asv_c_01__new_account_committed_and_returned(db, s):
    """ASV-C-01 — a new account is committed and returned re-read.
    Rules: create_account R1; TC1, TC2."""
    result = svc.create_account(
        db,
        account_in=AccountCreate(name="Acme Ltd", account_code="SUP-001", city="Dhaka"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id is not None
    assert result.created_at is not None
    # Then 3
    assert result.name == "Acme Ltd"
    assert result.workspace_id == s.W1.id
    assert result.created_by == s.U1.id
    # Then 4
    db.rollback()
    row = reread(db, Account, result.id)
    assert row.name == "Acme Ltd"
    assert row.account_code == "SUP-001"
    assert row.city == "Dhaka"
    assert row.is_deleted is False
    # Then 5
    rows = audit(db, result.id)
    assert len(rows) == 1
    assert rows[0].action_type == "created"


# [claude] ASV-C-02
def test_asv_c_02__active_tag_attached(db, s):
    """ASV-C-02 — an active tag in tag_ids is attached and committed.
    Rules: create_account R1 (companion of BUG-871 / BUG-2987)."""
    t = tag(db, s)

    result = svc.create_account(
        db,
        account_in=AccountCreate(name="Acme Ltd", tag_ids=[t.id]),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
    )

    # Then 1
    assert result.id is not None
    # Then 2
    db.rollback()
    rows = links(db, AccountTagAssignment.account_id == result.id)
    assert len(rows) == 1
    assert rows[0].tag_id == t.id
    # Then 3
    assert reread(db, AccountTag, t.id).usage_count == 1


# [claude] ASV-C-03
def test_asv_c_03__db_error_rolls_back_everything(db, s):
    """ASV-C-03 — a database error rolls back the account and every other pending change.
    Rules: create_account R2; TC3."""
    account(db, s)
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(IntegrityError):
        svc.create_account(
            db,
            account_in=AccountCreate(name="Beta Traders"),
            workspace_id=s.W1.id,
            user_id=MISSING,
        )
    # Then 2
    assert acc_count(db, Account.name == "Beta Traders") == 0
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# [claude] ASV-C-04
def test_asv_c_04__failing_commit_rolled_back(db, s):
    """ASV-C-04 — a failing commit is rolled back and re-raised.
    Rules: create_account R2; TC4."""
    before = commit_point(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.create_account(
                db,
                account_in=AccountCreate(name="Acme Ltd"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert acc_count(db, Account.workspace_id == s.W1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] ASV-C-05
def test_asv_c_05__failing_refresh_leaves_account_saved(db, s):
    """ASV-C-05 — a failing re-read after the commit leaves the account saved.
    Rules: create_account R2; TC5."""
    commit_point(db)

    with pytest.raises(RuntimeError) as exc:
        with failing_refresh(db):
            svc.create_account(
                db,
                account_in=AccountCreate(name="Acme Ltd"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert (
        acc_count(db, Account.workspace_id == s.W1.id, Account.name == "Acme Ltd") == 1
    )


# [claude] ASV-C-06
def test_asv_c_06__other_value_error_passes_unchanged(db, s):
    """ASV-C-06 — any other ValueError of the manager passes unchanged, rolled back.
    Rules: create_account R3 (last sentence), R2; TC3."""
    account(db, s)
    before = commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError("something else")

    # Then 1
    with pytest.raises(ValueError) as exc:
        with mgr_raises("create_account", e):
            svc.create_account(
                db,
                account_in=AccountCreate(name="Beta Traders"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value is e
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert written(db) == before


# [claude] ASV-C-07
@pytest.mark.xfail(strict=True, reason=BUG_871)
def test_asv_c_07__translation_unknown_tag_404(db, s):
    """ASV-C-07 — translation: "Account tag N not found" becomes 404.
    Rules: create_account R3 [BUG-871]."""
    commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError("Account tag 77 not found")

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with mgr_raises("create_account", e):
            svc.create_account(
                db,
                account_in=AccountCreate(name="Acme Ltd"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Account tag 77 not found"
    # Then 4
    assert x_gone(db, x_id)


# [claude] ASV-C-08
@pytest.mark.xfail(strict=True, reason=BUG_874)
def test_asv_c_08__translation_duplicate_code_409(db, s):
    """ASV-C-08 — translation: duplicate code becomes 409.
    Rules: create_account R3 [BUG-874]."""
    commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError("Account code 'SUP-001' already exists")

    # Then 1
    with pytest.raises(ConflictError) as exc:
        with mgr_raises("create_account", e):
            svc.create_account(
                db,
                account_in=AccountCreate(name="Beta Traders", account_code="SUP-001"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Account code 'SUP-001' already exists"
    # Then 4
    assert x_gone(db, x_id)


# [claude] ASV-C-09
@pytest.mark.xfail(strict=True, reason=BUG_2987)
def test_asv_c_09__translation_inactive_tag_422(db, s):
    """ASV-C-09 — translation: inactive tag becomes 422.
    Rules: create_account R3 [BUG-2987]."""
    commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError("Account tag 7 is not active")

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        with mgr_raises("create_account", e):
            svc.create_account(
                db,
                account_in=AccountCreate(name="Acme Ltd", tag_ids=[7]),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Account tag 7 is not active"
    # Then 4
    assert x_gone(db, x_id)


# [claude] ASV-C-10
@pytest.mark.xfail(strict=True, reason=BUG_871)
def test_asv_c_10__unknown_tag_id_refused_404(db, s):
    """ASV-C-10 — end to end: an unknown tag id is refused with 404, nothing saved.
    Rules: create_account R3 [BUG-871]."""
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create_account(
            db,
            account_in=AccountCreate(name="Acme Ltd", tag_ids=[MISSING]),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == "Account tag 999999999 not found"
    # Then 3
    assert acc_count(db, Account.workspace_id == s.W1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] ASV-C-11
@pytest.mark.xfail(strict=True, reason=BUG_874)
def test_asv_c_11__duplicate_code_refused_409(db, s):
    """ASV-C-11 — end to end: a duplicate account code is refused with 409.
    Rules: create_account R3 [BUG-874]."""
    account(db, s, account_code="SUP-001")
    before = commit_point(db)

    # Then 1
    with pytest.raises(ConflictError) as exc:
        svc.create_account(
            db,
            account_in=AccountCreate(name="Beta Traders", account_code="SUP-001"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == "Account code 'SUP-001' already exists"
    # Then 3
    assert (
        acc_count(
            db, Account.workspace_id == s.W1.id, Account.account_code == "SUP-001"
        )
        == 1
    )
    # Then 4
    assert written(db) == before


# [claude] ASV-C-12
@pytest.mark.xfail(strict=True, reason=BUG_2987)
def test_asv_c_12__deleted_tag_refused_422(db, s):
    """ASV-C-12 — end to end: a deleted tag is refused with 422.
    Rules: create_account R3 [BUG-2987]."""
    t = tag(db, s, name="Old vendor", tag_code="old", is_active=False)
    before = commit_point(db)

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        svc.create_account(
            db,
            account_in=AccountCreate(name="Acme Ltd", tag_ids=[t.id]),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == f"Account tag {t.id} is not active"
    # Then 3
    assert acc_count(db, Account.workspace_id == s.W1.id) == 0
    # Then 4
    assert written(db) == before


# [claude] ASV-C-13
@pytest.mark.xfail(strict=True, reason=BUG_140)
def test_asv_c_13__ip_and_user_agent_reach_audit(db, s):
    """ASV-C-13 — client IP and user agent reach the audit row.
    Rules: create_account R4 [BUG-140]."""
    # Fails today here: create_account has no ip_address / user_agent parameters (TypeError).
    result = svc.create_account(
        db,
        account_in=AccountCreate(name="Acme Ltd"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        ip_address="203.0.113.7",
        user_agent="UA/1.0",
    )

    # Then 1
    assert result.id is not None
    # Then 2
    db.rollback()
    rows = audit(db, result.id)
    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "UA/1.0"


# --------------------------------------------------------------------------- #
# get_account_with_tags
# --------------------------------------------------------------------------- #


# [claude] ASV-G-01
def test_asv_g_01__live_account_dict_with_tags(db, s):
    """ASV-G-01 — a live account gives the 20-key dict with its tags.
    Rules: get_account_with_tags R1, R4; Facts (account dict)."""
    a = account(db, s, account_code="SUP-001", city="Dhaka")
    t = tag(db, s, color="#ff0000", icon="truck")
    link(db, s, a, t)
    commit_point(db)

    result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert set(result.keys()) == KEYS
    # Then 2
    assert result["id"] == a.id
    assert result["name"] == "Acme Ltd"
    assert result["account_code"] == "SUP-001"
    assert result["city"] == "Dhaka"
    assert result["workspace_id"] == s.W1.id
    # Then 3
    assert len(result["account_tags"]) == 1
    # Then 4
    assert set(result["account_tags"][0].keys()) == TAGKEYS
    # Then 5
    assert result["account_tags"][0] == {
        "id": t.id,
        "name": "Supplier",
        "tag_code": "supplier",
        "color": "#ff0000",
        "icon": "truck",
        "is_system_tag": False,
    }


# [claude] ASV-G-02
def test_asv_g_02__two_tags_listed(db, s):
    """ASV-G-02 — two tags are both listed (compared as a set).
    Rules: get_account_with_tags R4."""
    a = account(db, s)
    t1 = tag(db, s)
    t2 = tag(db, s, name="Client", tag_code="client")
    link(db, s, a, t1)
    link(db, s, a, t2)
    commit_point(db)

    result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert {t["id"] for t in result["account_tags"]} == {t1.id, t2.id}
    # Then 2
    assert len(result["account_tags"]) == 2


# [claude] ASV-G-03
def test_asv_g_03__no_tags_empty_list(db, s):
    """ASV-G-03 — an account without tags has account_tags == [].
    Rules: get_account_with_tags R4."""
    a = account(db, s)
    commit_point(db)

    result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert result["account_tags"] == []


# [claude] ASV-G-04
def test_asv_g_04__inactive_account_returned(db, s):
    """ASV-G-04 — an inactive (not deleted) account is returned.
    Rules: get_account_with_tags R1."""
    a = account(db, s, is_active=False)
    commit_point(db)

    result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert result["id"] == a.id
    assert result["is_active"] is False


# [claude] ASV-G-05
def test_asv_g_05__missing_id_404(db, s):
    """ASV-G-05 — a missing id gets 404.
    Rules: get_account_with_tags R2, Errors."""
    account(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_account_with_tags(db, account_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Account with ID 999999999 not found"


# [claude] ASV-G-06
def test_asv_g_06__w0_account_404(db, s):
    """ASV-G-06 — an account of W0 (built before W1) gets 404.
    Rules: get_account_with_tags R2."""
    z = account(db, s, workspace_id=s.W0.id)
    account(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_account_with_tags(db, account_id=z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"


# [claude] ASV-G-07
def test_asv_g_07__w2_account_404(db, s):
    """ASV-G-07 — an account of W2 (built after W1) gets 404.
    Rules: get_account_with_tags R2."""
    account(db, s)
    z = account(db, s, workspace_id=s.W2.id)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_account_with_tags(db, account_id=z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"


# [claude] ASV-G-08
@pytest.mark.xfail(strict=True, reason=BUG_862)
def test_asv_g_08__deleted_account_404_by_default(db, s):
    """ASV-G-08 — a soft-deleted account gets 404 by default.
    Rules: get_account_with_tags R3 [BUG-862]."""
    a = account(db, s, **gone(s))
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account with ID {a.id} not found"


# [claude] ASV-G-09
@pytest.mark.xfail(strict=True, reason=BUG_862)
def test_asv_g_09__include_deleted_returns_deleted(db, s):
    """ASV-G-09 — include_deleted=True returns the soft-deleted account.
    Rules: get_account_with_tags R3 [BUG-862]."""
    a = account(db, s, **gone(s))
    commit_point(db)

    # Fails today here: get_account_with_tags has no include_deleted parameter (TypeError).
    result = svc.get_account_with_tags(
        db, account_id=a.id, workspace_id=s.W1.id, include_deleted=True
    )

    # Then 1
    assert result["id"] == a.id
    # Then 2
    assert result["is_active"] is False


# [claude] ASV-G-10
def test_asv_g_10__read_does_not_commit_or_rollback(db, s):
    """ASV-G-10 — a read neither commits nor rolls back; a pending edit stays.
    Rules: get_account_with_tags R5; TC6."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    commit_point(db)
    b.city = "Khulna"

    with spies(db) as (cm, rb):
        svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert b in db.dirty
    # Then 4
    assert len(db.dirty) == 1


# [claude] ASV-G-11
@pytest.mark.xfail(strict=True, reason=BUG_865)
def test_asv_g_11__deleted_tag_not_listed(db, s):
    """ASV-G-11 — a deleted tag of the account is not listed.
    Rules: get_account_with_tags R4 [BUG-865]."""
    a = account(db, s)
    t = tag(db, s)
    d = tag(db, s, name="Old vendor", tag_code="old", is_active=False)
    link(db, s, a, t)
    link(db, s, a, d)
    commit_point(db)

    result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert result["id"] == a.id
    # Then 2
    assert [t["id"] for t in result["account_tags"]] == [t.id]


# [claude] ASV-G-12
@pytest.mark.xfail(strict=True, reason=BUG_1486)
def test_asv_g_12__tag_select_has_order_by(db, s):
    """ASV-G-12 — the SELECT reading the account's tags carries an ORDER BY.
    Rules: get_account_with_tags R4 [BUG-1486]."""
    a = account(db, s)
    t1 = tag(db, s, name="Zeta", tag_code="zeta")
    t2 = tag(db, s, name="Alpha", tag_code="alpha")
    link(db, s, a, t1)
    link(db, s, a, t2)
    commit_point(db)

    with record_sql(db) as rec:
        result = svc.get_account_with_tags(db, account_id=a.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result["account_tags"]) == 2
    # Then 2
    hits = [st for st in rec.stmts if "FROM account_tags" in st]
    assert len(hits) == 1
    assert "ORDER BY" in hits[0]


# --------------------------------------------------------------------------- #
# get_accounts_with_tags
# --------------------------------------------------------------------------- #


# [claude] ASV-L-01
def test_asv_l_01__workspace_live_active_accounts(db, s):
    """ASV-L-01 — the workspace's live active accounts, none of W0 or W2 (as a set), each a dict.
    Rules: get_accounts_with_tags R1."""
    account(db, s, workspace_id=s.W0.id)
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    account(db, s, workspace_id=s.W2.id)
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert {r["id"] for r in result} == {a.id, b.id}
    # Then 3
    assert all(set(r.keys()) == KEYS for r in result)


# [claude] ASV-L-02
def test_asv_l_02__search_is_name_filter(db, s):
    """ASV-L-02 — search is passed on as the name filter (text in the middle of the name).
    Rules: get_accounts_with_tags R1."""
    a = account(db, s)
    account(db, s, name="Beta Traders")
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id, search="cme")

    # Then 1
    assert [r["id"] for r in result] == [a.id]


# [claude] ASV-L-03
def test_asv_l_03__tag_code_passed_on(db, s):
    """ASV-L-03 — tag_code is passed on.
    Rules: get_accounts_with_tags R1."""
    account(db, s)
    b = account(db, s, name="Beta Traders")
    t = tag(db, s)
    link(db, s, b, t)
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id, tag_code="supplier")

    # Then 1
    assert [r["id"] for r in result] == [b.id]
    # Then 2
    assert [t["id"] for t in result[0]["account_tags"]] == [t.id]


# [claude] ASV-L-04
def test_asv_l_04__skip_and_limit_passed_on(db, s):
    """ASV-L-04 — skip and limit are passed on: 4 accounts, skip=1, limit=2 give 2 distinct of them.
    Rules: get_accounts_with_tags R1."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    c = account(db, s, name="Gamma Co")
    d = account(db, s, name="Delta Inc")
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id, skip=1, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert {r["id"] for r in result} <= {a.id, b.id, c.id, d.id}
    # Then 3
    assert len({r["id"] for r in result}) == 2


# [claude] ASV-L-05
def test_asv_l_05__no_match_empty(db, s):
    """ASV-L-05 — no match gives [].
    Rules: get_accounts_with_tags R1."""
    account(db, s)
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id, search="Zeta")

    # Then 1
    assert result == []


# [claude] ASV-L-06
def test_asv_l_06__inactive_left_out_by_default(db, s):
    """ASV-L-06 — inactive accounts are left out by default.
    Rules: get_accounts_with_tags R1 (companion of BUG-878)."""
    a = account(db, s)
    account(db, s, name="Beta Traders", is_active=False)
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id)

    # Then 1
    assert [r["id"] for r in result] == [a.id]


# [claude] ASV-L-07
@pytest.mark.xfail(strict=True, reason=BUG_878)
def test_asv_l_07__include_inactive_lists_inactive(db, s):
    """ASV-L-07 — include_inactive=True lists inactive accounts too.
    Rules: get_accounts_with_tags R2 [BUG-878]."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders", is_active=False)
    commit_point(db)

    # Fails today here: get_accounts_with_tags has no include_inactive parameter (TypeError).
    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id, include_inactive=True)

    # Then 1
    assert {r["id"] for r in result} == {a.id, b.id}


# [claude] ASV-L-08
def test_asv_l_08__read_does_not_commit_or_rollback(db, s):
    """ASV-L-08 — a read neither commits nor rolls back; a pending edit stays.
    Rules: get_accounts_with_tags R3; TC6."""
    a = account(db, s)
    commit_point(db)
    a.city = "Khulna"

    with spies(db) as (cm, rb):
        svc.get_accounts_with_tags(db, workspace_id=s.W2.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert a in db.dirty


# [claude] ASV-L-09
def test_asv_l_09__tag_entries_six_keys_and_values(db, s):
    """ASV-L-09 — each list item carries its tag entries with all six keys and stored values.
    Rules: get_accounts_with_tags R1; Facts (account dict)."""
    a = account(db, s)
    t = tag(db, s, color="#ff0000", icon="truck")
    link(db, s, a, t)
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["account_tags"] == [
        {
            "id": t.id,
            "name": "Supplier",
            "tag_code": "supplier",
            "color": "#ff0000",
            "icon": "truck",
            "is_system_tag": False,
        }
    ]


# [claude] ASV-L-10
def test_asv_l_10__default_limit_100(db, s):
    """ASV-L-10 — the default limit is 100: 101 accounts give 100.
    Rules: get_accounts_with_tags R1 (signature default `limit=100`)."""
    db.add_all([account_row(s, name=f"a{k:03d}") for k in range(1, 102)])
    db.flush()
    commit_point(db)

    result = svc.get_accounts_with_tags(db, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100


# --------------------------------------------------------------------------- #
# _account_dict_with_tags
# --------------------------------------------------------------------------- #


# [claude] ASV-M-01
def test_asv_m_01__builds_dict_with_tags(db, s):
    """ASV-M-01 — builds the 20-key dict with the tags read for the given workspace.
    Rules: _account_dict_with_tags R1."""
    a = account(db, s, primary_email="a@acme.test", bank_details="IBAN 1")
    t = tag(db, s)
    link(db, s, a, t)
    commit_point(db)

    result = svc._account_dict_with_tags(db, account=a, workspace_id=s.W1.id)

    # Then 1
    assert set(result.keys()) == KEYS
    # Then 2
    assert result["primary_email"] == "a@acme.test"
    assert result["bank_details"] == "IBAN 1"
    assert result["allow_invoices"] is True
    # Then 3
    assert [t["id"] for t in result["account_tags"]] == [t.id]


# [claude] ASV-M-02
def test_asv_m_02__deleted_account_still_maps(db, s):
    """ASV-M-02 — the account is not re-checked: a deleted account still maps.
    Rules: _account_dict_with_tags R1."""
    a = account(db, s, **gone(s))
    commit_point(db)

    result = svc._account_dict_with_tags(db, account=a, workspace_id=s.W1.id)

    # Then 1
    assert result["id"] == a.id
    assert result["is_active"] is False
    # Then 2
    assert result["account_tags"] == []


# [claude] ASV-M-03
def test_asv_m_03__tag_entries_six_keys_and_values(db, s):
    """ASV-M-03 — the tag entries carry all six keys and stored values.
    Rules: _account_dict_with_tags R1 (used by get_accounts_hub_page R2)."""
    a = account(db, s)
    t = tag(db, s, color="#ff0000", icon="truck")
    link(db, s, a, t)
    commit_point(db)

    result = svc._account_dict_with_tags(db, account=a, workspace_id=s.W1.id)

    # Then 1
    assert result["account_tags"] == [
        {
            "id": t.id,
            "name": "Supplier",
            "tag_code": "supplier",
            "color": "#ff0000",
            "icon": "truck",
            "is_system_tag": False,
        }
    ]


# --------------------------------------------------------------------------- #
# _rollup_from_subquery_row
# --------------------------------------------------------------------------- #


# [claude] ASV-R-01
def test_asv_r_01__none_gives_zeros():
    """ASV-R-01 — None gives (Decimal 0, 0, False).
    Rules: _rollup_from_subquery_row R1."""
    result = AccountService._rollup_from_subquery_row(None)

    # Then 1
    assert result == (Decimal(0), 0, False)
    # Then 2
    assert type(result[0]) is Decimal
    assert type(result[1]) is int
    assert type(result[2]) is bool


# [claude] ASV-R-02
def test_asv_r_02__values_converted_scale_kept():
    """ASV-R-02 — values are converted, the Decimal keeps its scale.
    Rules: _rollup_from_subquery_row R2."""
    row = SimpleNamespace(
        outstanding_total=Decimal("1500.00"), open_count=3, has_overdue=1
    )

    result = AccountService._rollup_from_subquery_row(row)

    # Then 1
    assert str(result[0]) == "1500.00"
    # Then 2
    assert result[1] == 3
    assert type(result[1]) is int
    # Then 3
    assert result[2] is True


# [claude] ASV-R-03
def test_asv_r_03__none_values_give_zeros():
    """ASV-R-03 — None values give zeros.
    Rules: _rollup_from_subquery_row R2."""
    row = SimpleNamespace(outstanding_total=None, open_count=None, has_overdue=None)

    result = AccountService._rollup_from_subquery_row(row)

    # Then 1
    assert result == (Decimal(0), 0, False)
    # Then 2
    assert str(result[0]) == "0"


# [claude] ASV-R-04
def test_asv_r_04__missing_attributes_give_zeros():
    """ASV-R-04 — missing attributes give zeros.
    Rules: _rollup_from_subquery_row R2."""
    row = SimpleNamespace()

    result = AccountService._rollup_from_subquery_row(row)

    # Then 1
    assert result == (Decimal(0), 0, False)
    # Then 2
    assert str(result[0]) == "0"


# [claude] ASV-R-05
def test_asv_r_05__zero_values_and_fraction_kept():
    """ASV-R-05 — zero values stay zero, no rounding of a fraction.
    Rules: _rollup_from_subquery_row R2."""
    row = SimpleNamespace(
        outstanding_total=Decimal("0.005"), open_count=0, has_overdue=False
    )

    result = AccountService._rollup_from_subquery_row(row)

    # Then 1
    assert str(result[0]) == "0.005"
    # Then 2
    assert result[1] == 0
    assert result[2] is False


# --------------------------------------------------------------------------- #
# get_accounts_hub_page
# --------------------------------------------------------------------------- #


# [claude] ASV-H-01
def test_asv_h_01__items_map_manager_rows(db, s):
    """ASV-H-01 — items map the manager's rows in its order, total unchanged.
    Rules: get_accounts_hub_page R1, R2."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    commit_point(db)
    p = SimpleNamespace(
        outstanding_total=Decimal("600.00"), open_count=2, has_overdue=True
    )
    q = SimpleNamespace(outstanding_total=Decimal("0"), open_count=0, has_overdue=False)
    fake = MagicMock(return_value=([(b, p, q), (a, q, p)], 7))

    with patch.object(mod.account_invoice_manager, "list_accounts_hub_page", fake):
        items, total = svc.get_accounts_hub_page(
            db, workspace_id=s.W1.id, section="payable", search="ac", skip=5, limit=2
        )

    # Then 1
    assert total == 7
    # Then 2
    assert [i["id"] for i in items] == [b.id, a.id]
    # Then 3
    assert items[0]["open_balance"] == {
        "payable_outstanding": Decimal("600.00"),
        "receivable_outstanding": Decimal("0"),
        "open_payable_count": 2,
        "open_receivable_count": 0,
        "has_overdue_payable": True,
        "has_overdue_receivable": False,
    }
    # Then 4
    assert items[1]["open_balance"]["receivable_outstanding"] == Decimal("600.00")
    assert items[1]["open_balance"]["has_overdue_receivable"] is True
    # Then 5
    assert set(items[0].keys()) == KEYS | {"open_balance"}
    # Then 6
    kw = fake.call_args.kwargs
    assert kw["workspace_id"] == s.W1.id
    assert kw["section"] == "payable"
    assert kw["search"] == "ac"
    assert kw["skip"] == 5
    assert kw["limit"] == 2


# [claude] ASV-H-02
def test_asv_h_02__no_invoices_zero_balances(db, s):
    """ASV-H-02 — end to end: an account without invoices gets zero balances.
    Rules: get_accounts_hub_page R2."""
    a = account(db, s)
    commit_point(db)

    items, total = svc.get_accounts_hub_page(db, workspace_id=s.W1.id)

    # Then 1
    assert total == 1
    # Then 2
    assert items[0]["id"] == a.id
    # Then 3
    assert items[0]["open_balance"] == {
        "payable_outstanding": Decimal("0"),
        "receivable_outstanding": Decimal("0"),
        "open_payable_count": 0,
        "open_receivable_count": 0,
        "has_overdue_payable": False,
        "has_overdue_receivable": False,
    }


# [claude] ASV-H-03
def test_asv_h_03__confirmed_open_invoices_sum_per_type(db, s):
    """ASV-H-03 — end to end: confirmed open invoices give the outstanding sums per type.
    Rules: get_accounts_hub_page R1, R2."""
    a = account(db, s)
    invoice(db, s, a, "partial")
    invoice(
        db, s, a, "unpaid", invoice_type="receivable", invoice_amount=Decimal("500.00")
    )
    commit_point(db)

    items, total = svc.get_accounts_hub_page(db, workspace_id=s.W1.id)

    # Then 1
    assert total == 1
    # Then 2
    assert items[0]["open_balance"]["payable_outstanding"] == Decimal("600.00")
    assert items[0]["open_balance"]["open_payable_count"] == 1
    # Then 3
    assert items[0]["open_balance"]["receivable_outstanding"] == Decimal("500.00")
    assert items[0]["open_balance"]["open_receivable_count"] == 1


# [claude] ASV-H-04
def test_asv_h_04__read_does_not_commit_or_rollback(db, s):
    """ASV-H-04 — a read neither commits nor rolls back; a pending edit stays.
    Rules: get_accounts_hub_page R3; TC6."""
    a = account(db, s)
    commit_point(db)
    a.city = "Khulna"

    with spies(db) as (cm, rb):
        svc.get_accounts_hub_page(db, workspace_id=s.W2.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert a in db.dirty


# [claude] ASV-H-05
def test_asv_h_05__default_limit_50_total_51(db, s):
    """ASV-H-05 — the default limit is 50: 51 accounts give 50 items, total 51.
    Rules: get_accounts_hub_page R1 (signature default `limit=50`)."""
    db.add_all([account_row(s, name=f"a{k:03d}") for k in range(1, 52)])
    db.flush()
    commit_point(db)

    items, total = svc.get_accounts_hub_page(db, workspace_id=s.W1.id)

    # Then 1
    assert len(items) == 50
    # Then 2
    assert total == 51


# --------------------------------------------------------------------------- #
# update_account
# --------------------------------------------------------------------------- #


# [claude] ASV-U-01
def test_asv_u_01__change_committed_and_returned(db, s):
    """ASV-U-01 — a change is committed and the row returned re-read.
    Rules: update_account R1; TC1, TC2."""
    a = account(db, s, city="Dhaka")
    commit_point(db)

    result = svc.update_account(
        db,
        account_id=a.id,
        account_in=AccountUpdate(name="Acme Limited"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
    )

    # Then 1
    assert loaded(result)
    # Then 2
    assert result.id == a.id
    assert result.name == "Acme Limited"
    assert result.updated_at is not None
    # Then 3
    db.rollback()
    row = reread(db, Account, a.id)
    assert row.name == "Acme Limited"
    assert row.city == "Dhaka"


# [claude] ASV-U-02
def test_asv_u_02__failing_commit_rolled_back(db, s):
    """ASV-U-02 — a failing commit is rolled back and re-raised.
    Rules: update_account R2; TC4."""
    a = account(db, s)
    before = commit_point(db)
    before_a = snap(db, a.id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(name="Acme Limited"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a.id) == before_a
    # Then 4
    assert written(db) == before


# [claude] ASV-U-03
def test_asv_u_03__other_exception_passes_unchanged(db, s):
    """ASV-U-03 — any other exception passes unchanged, every pending change discarded.
    Rules: update_account R2, R3 (last sentence); TC3."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    _x, x_id = mk_x(db)
    e = ValueError("something else")

    # Then 1
    with pytest.raises(ValueError) as exc:
        with mgr_raises("update_account", e):
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(name="Acme Limited"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value is e
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert snap(db, a.id) == before_a


# [claude] ASV-U-04
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_u_04__translation_not_found_404(db, s):
    """ASV-U-04 — translation: "Account N not found" becomes 404 "Account with ID N not found".
    Rules: update_account R3 [BUG-2986]."""
    a = account(db, s)
    commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError(f"Account {a.id} not found")

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with mgr_raises("update_account", e):
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(name="Acme Limited"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Account with ID {a.id} not found"
    # Then 4
    assert x_gone(db, x_id)


# [claude] ASV-U-05
@pytest.mark.xfail(strict=True, reason=BUG_874)
def test_asv_u_05__translation_duplicate_code_409(db, s):
    """ASV-U-05 — translation: duplicate code becomes 409.
    Rules: update_account R3 [BUG-874]."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    e = ValueError("Account code 'SUP-001' already exists")

    # Then 1
    with pytest.raises(ConflictError) as exc:
        with mgr_raises("update_account", e):
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(account_code="SUP-001"),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.detail == "Account code 'SUP-001' already exists"
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-U-06
@pytest.mark.xfail(strict=True, reason=BUG_871)
def test_asv_u_06__translation_unknown_tag_404(db, s):
    """ASV-U-06 — translation: "Account tag N not found" becomes 404 with the manager's text.
    Rules: update_account R3 [BUG-871]."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    e = ValueError("Account tag 77 not found")

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with mgr_raises("update_account", e):
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(tag_ids=[77]),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.detail == "Account tag 77 not found"
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-U-07
@pytest.mark.xfail(strict=True, reason=BUG_2987)
def test_asv_u_07__translation_inactive_tag_422(db, s):
    """ASV-U-07 — translation: inactive tag becomes 422.
    Rules: update_account R3 [BUG-2987]."""
    a = account(db, s)
    commit_point(db)
    e = ValueError("Account tag 7 is not active")

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        with mgr_raises("update_account", e):
            svc.update_account(
                db,
                account_id=a.id,
                account_in=AccountUpdate(tag_ids=[7]),
                workspace_id=s.W1.id,
                user_id=s.U1.id,
            )
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "Account tag 7 is not active"


# [claude] ASV-U-08
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_u_08__missing_id_404(db, s):
    """ASV-U-08 — end to end: a missing id gets 404.
    Rules: update_account R3 [BUG-2986]."""
    a = account(db, s)
    before = commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_account(
            db,
            account_id=MISSING,
            account_in=AccountUpdate(name="Acme Limited"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == "Account with ID 999999999 not found"
    # Then 3
    assert snap(db, a.id) == before_a
    # Then 4
    assert written(db) == before


# [claude] ASV-U-09
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_u_09__w2_account_404(db, s):
    """ASV-U-09 — end to end: an account of W2 gets the same 404.
    Rules: update_account R3 [BUG-2986]."""
    account(db, s)
    z = account(db, s, workspace_id=s.W2.id)
    commit_point(db)
    before_z = snap(db, z.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_account(
            db,
            account_id=z.id,
            account_in=AccountUpdate(name="Taken"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"
    # Then 3
    assert snap(db, z.id) == before_z


# [claude] ASV-U-10
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_u_10__w0_account_404(db, s):
    """ASV-U-10 — end to end: an account of W0 gets the same 404.
    Rules: update_account R3 [BUG-2986]."""
    z = account(db, s, workspace_id=s.W0.id)
    account(db, s)
    commit_point(db)
    before_z = snap(db, z.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_account(
            db,
            account_id=z.id,
            account_in=AccountUpdate(name="Taken"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"
    # Then 3
    assert snap(db, z.id) == before_z


# [claude] ASV-U-11
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_u_11__deleted_account_404(db, s):
    """ASV-U-11 — end to end: a soft-deleted account gets 404, nothing written.
    Rules: update_account R3 [BUG-2986] (manager BUG-863)."""
    a = account(db, s, **gone(s))
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_account(
            db,
            account_id=a.id,
            account_in=AccountUpdate(name="Revived"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == f"Account with ID {a.id} not found"
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-U-12
@pytest.mark.xfail(strict=True, reason=BUG_874)
def test_asv_u_12__duplicate_code_on_update_409(db, s):
    """ASV-U-12 — end to end: a duplicate code on update gets 409.
    Rules: update_account R3 [BUG-874]."""
    account(db, s, account_code="SUP-001")
    b = account(db, s, name="Beta Traders", account_code="SUP-002")
    commit_point(db)

    # Then 1
    with pytest.raises(ConflictError) as exc:
        svc.update_account(
            db,
            account_id=b.id,
            account_in=AccountUpdate(account_code="SUP-001"),
            workspace_id=s.W1.id,
            user_id=s.U1.id,
        )
    # Then 2
    assert exc.value.detail == "Account code 'SUP-001' already exists"
    # Then 3
    assert reread(db, Account, b.id).account_code == "SUP-002"


# [claude] ASV-U-13
@pytest.mark.xfail(strict=True, reason=BUG_140)
def test_asv_u_13__ip_and_user_agent_reach_audit(db, s):
    """ASV-U-13 — client IP and user agent reach the audit row.
    Rules: update_account R4 [BUG-140]."""
    a = account(db, s)
    commit_point(db)

    # Fails today here: update_account has no ip_address / user_agent parameters (TypeError).
    result = svc.update_account(
        db,
        account_id=a.id,
        account_in=AccountUpdate(name="Acme Limited"),
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        ip_address="203.0.113.7",
        user_agent="UA/1.0",
    )

    # Then 1
    assert result.id == a.id
    # Then 2
    db.rollback()
    rows = audit(db, a.id)
    assert len(rows) == 1
    assert rows[0].action_type == "updated"
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "UA/1.0"


# --------------------------------------------------------------------------- #
# get_accounts_by_tag_id
# --------------------------------------------------------------------------- #


# [claude] ASV-T-01
def test_asv_t_01__lists_tag_accounts(db, s):
    """ASV-T-01 — lists the tag's accounts as dicts (as a set).
    Rules: get_accounts_by_tag_id R3."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    c = account(db, s, name="Gamma Co")
    t = tag(db, s)
    st = tag(db, s, name="Client", tag_code="client")
    link(db, s, a, t)
    link(db, s, b, t)
    link(db, s, c, st)
    commit_point(db)

    result = svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert {r["id"] for r in result} == {a.id, b.id}
    # Then 2
    assert len(result) == 2
    # Then 3
    assert all(set(r.keys()) == KEYS for r in result)


# [claude] ASV-T-02
def test_asv_t_02__tag_without_accounts_empty(db, s):
    """ASV-T-02 — a tag without accounts gives [].
    Rules: get_accounts_by_tag_id R3."""
    t = tag(db, s)
    commit_point(db)

    result = svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert result == []


# [claude] ASV-T-03
def test_asv_t_03__skip_and_limit_passed_on(db, s):
    """ASV-T-03 — skip and limit are passed on: 4 accounts, skip=1, limit=2 give 2 distinct of them.
    Rules: get_accounts_by_tag_id R3."""
    t = tag(db, s)
    a = account(db, s)
    link(db, s, a, t)
    b = account(db, s, name="Beta Traders")
    link(db, s, b, t)
    c = account(db, s, name="Gamma Co")
    link(db, s, c, t)
    d = account(db, s, name="Delta Inc")
    link(db, s, d, t)
    commit_point(db)

    result = svc.get_accounts_by_tag_id(
        db, tag_id=t.id, workspace_id=s.W1.id, skip=1, limit=2
    )

    # Then 1
    assert len(result) == 2
    # Then 2
    assert len({r["id"] for r in result}) == 2
    # Then 3
    assert {r["id"] for r in result} <= {a.id, b.id, c.id, d.id}


# [claude] ASV-T-04
def test_asv_t_04__missing_tag_404(db, s):
    """ASV-T-04 — a missing tag gets 404.
    Rules: get_accounts_by_tag_id R1, Errors."""
    tag(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_accounts_by_tag_id(db, tag_id=MISSING, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Account tag 999999999 not found"


# [claude] ASV-T-05
def test_asv_t_05__w0_tag_404(db, s):
    """ASV-T-05 — a tag of W0 (built before W1) gets 404.
    Rules: get_accounts_by_tag_id R1."""
    z = tag(db, s, workspace_id=s.W0.id)
    tag(db, s)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_accounts_by_tag_id(db, tag_id=z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account tag {z.id} not found"


# [claude] ASV-T-06
def test_asv_t_06__w2_tag_404(db, s):
    """ASV-T-06 — a tag of W2 (built after W1) gets 404.
    Rules: get_accounts_by_tag_id R1."""
    tag(db, s)
    z = tag(db, s, workspace_id=s.W2.id)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_accounts_by_tag_id(db, tag_id=z.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account tag {z.id} not found"


# [claude] ASV-T-07
@pytest.mark.xfail(strict=True, reason=BUG_2982)
def test_asv_t_07__deleted_tag_404(db, s):
    """ASV-T-07 — a deleted tag gets 404, nothing listed.
    Rules: get_accounts_by_tag_id R2 [BUG-2982]."""
    a = account(db, s)
    t = tag(db, s, is_active=False)
    link(db, s, a, t)
    commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account tag {t.id} not found"


# [claude] ASV-T-08
def test_asv_t_08__read_does_not_commit_or_rollback(db, s):
    """ASV-T-08 — a read neither commits nor rolls back; a pending edit stays.
    Rules: get_accounts_by_tag_id R4; TC6."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    a.city = "Khulna"

    with spies(db) as (cm, rb):
        svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert cm.call_count == 0
    # Then 2
    assert rb.call_count == 0
    # Then 3
    assert a in db.dirty


# [claude] ASV-T-09
def test_asv_t_09__tag_entries_six_keys_and_values(db, s):
    """ASV-T-09 — each by-tag item carries its tag entries with all six keys and stored values.
    Rules: get_accounts_by_tag_id R3; Facts (account dict)."""
    a = account(db, s)
    t = tag(db, s, color="#ff0000", icon="truck")
    link(db, s, a, t)
    commit_point(db)

    result = svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0]["account_tags"] == [
        {
            "id": t.id,
            "name": "Supplier",
            "tag_code": "supplier",
            "color": "#ff0000",
            "icon": "truck",
            "is_system_tag": False,
        }
    ]


# [claude] ASV-T-10
def test_asv_t_10__default_limit_100(db, s):
    """ASV-T-10 — the default limit is 100: 101 tagged accounts give 100.
    Rules: get_accounts_by_tag_id R3 (signature default `limit=100`)."""
    t = tag(db, s)
    rows = [account_row(s, name=f"a{k:03d}") for k in range(1, 102)]
    db.add_all(rows)
    db.flush()
    db.add_all([link_row(s, ak, t) for ak in rows])
    db.flush()
    commit_point(db)

    result = svc.get_accounts_by_tag_id(db, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert len(result) == 100


# --------------------------------------------------------------------------- #
# assign_tag
# --------------------------------------------------------------------------- #


# [claude] ASV-A-01
def test_asv_a_01__tag_attached_and_listed(db, s):
    """ASV-A-01 — the tag is attached, committed, and listed in the returned dict.
    Rules: assign_tag R1; TC1."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)

    result = svc.assign_tag(
        db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result["id"] == a.id
    # Then 2
    assert [t["id"] for t in result["account_tags"]] == [t.id]
    # Then 3
    db.rollback()
    rows = links(
        db, AccountTagAssignment.account_id == a.id, AccountTagAssignment.tag_id == t.id
    )
    assert len(rows) == 1
    assert rows[0].assigned_by == s.U1.id
    # Then 4
    assert reread(db, AccountTag, t.id).usage_count == 1


# [claude] ASV-A-02
def test_asv_a_02__already_assigned_no_change(db, s):
    """ASV-A-02 — an already-assigned tag: no change, the dict lists it once.
    Rules: assign_tag R1."""
    a = account(db, s)
    t = tag(db, s, usage_count=1)
    link(db, s, a, t)
    commit_point(db)

    result = svc.assign_tag(
        db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert [t["id"] for t in result["account_tags"]] == [t.id]
    # Then 2
    db.rollback()
    rows = links(db, AccountTagAssignment.account_id == a.id)
    assert len(rows) == 1
    assert rows[0].assigned_by == s.U2.id
    assert rows[0].assigned_at == T0
    # Then 3
    assert reread(db, AccountTag, t.id).usage_count == 1


# [claude] ASV-A-03
def test_asv_a_03__missing_account_404(db, s):
    """ASV-A-03 — a missing account gets 404, rolled back.
    Rules: assign_tag R2, Errors row 1."""
    t = tag(db, s)
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.assign_tag(
            db, account_id=MISSING, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.detail == "Account 999999999 not found"
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert written(db) == before


# [claude] ASV-A-04
def test_asv_a_04__w2_account_404(db, s):
    """ASV-A-04 — an account of W2 gets the same 404.
    Rules: assign_tag R2, Errors row 1."""
    t = tag(db, s)
    z = account(db, s, workspace_id=s.W2.id)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.assign_tag(
            db, account_id=z.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.detail == f"Account {z.id} not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-A-05
@pytest.mark.xfail(strict=True, reason=BUG_863)
def test_asv_a_05__deleted_account_404(db, s):
    """ASV-A-05 — a soft-deleted account gets 404.
    Rules: assign_tag R2, Errors row 1 [BUG-863]."""
    a = account(db, s, **gone(s))
    t = tag(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.assign_tag(
            db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.detail == f"Account {a.id} not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-A-06
def test_asv_a_06__missing_tag_404(db, s):
    """ASV-A-06 — a missing tag gets 404 with the tag text.
    Rules: assign_tag R2, Errors row 2."""
    a = account(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.assign_tag(
            db, account_id=a.id, tag_id=MISSING, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.detail == "Account tag 999999999 not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-A-07
def test_asv_a_07__w0_tag_404(db, s):
    """ASV-A-07 — a tag of W0 gets 404.
    Rules: assign_tag R2, Errors row 2."""
    z = tag(db, s, workspace_id=s.W0.id)
    a = account(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.assign_tag(
            db, account_id=a.id, tag_id=z.id, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.detail == f"Account tag {z.id} not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-A-08
def test_asv_a_08__inactive_tag_422(db, s):
    """ASV-A-08 — an inactive tag gets 422, rolled back.
    Rules: assign_tag R2, Errors row 3."""
    a = account(db, s)
    t = tag(db, s, is_active=False)
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        svc.assign_tag(
            db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == f"Account tag {t.id} is not active"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert written(db) == before


# [claude] ASV-A-09
def test_asv_a_09__not_found_match_is_case_sensitive(db, s):
    """ASV-A-09 — the "not found" match is case-sensitive and anywhere in the text.
    Rules: assign_tag R2."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = ValueError("Account 5 Not Found")

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        with mgr_raises("assign_tag", e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.detail == "Account 5 Not Found"


# [claude] ASV-A-10
def test_asv_a_10__not_found_in_middle_gives_404(db, s):
    """ASV-A-10 — "not found" in the middle of the text gives 404 with that text.
    Rules: assign_tag R2."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = ValueError("Row was not found here")

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with mgr_raises("assign_tag", e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.detail == "Row was not found here"


# [claude] ASV-A-11
def test_asv_a_11__other_exception_passes_unchanged(db, s):
    """ASV-A-11 — any other exception passes unchanged, every pending change discarded.
    Rules: assign_tag R3; TC3."""
    a = account(db, s)
    t = tag(db, s)
    before = commit_point(db)
    _x, x_id = mk_x(db)
    e = RuntimeError("boom")

    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with mgr_raises("assign_tag", e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value is e
    # Then 3
    assert x_gone(db, x_id)
    # Then 4
    assert written(db) == before


# [claude] ASV-A-12
def test_asv_a_12__failing_read_assignment_stays_saved(db, s):
    """ASV-A-12 — a failing read after the commit reaches the caller; the assignment stays saved.
    Rules: assign_tag R4, R4a; TC5."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with patch.object(svc, "get_account_with_tags", side_effect=e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )

    # Then 1
    assert exc.value is e
    # Then 2
    db.rollback()
    rows = links(
        db, AccountTagAssignment.account_id == a.id, AccountTagAssignment.tag_id == t.id
    )
    assert len(rows) == 1
    # Then 3
    assert reread(db, AccountTag, t.id).usage_count == 1


# [claude] ASV-A-13
def test_asv_a_13__not_found_from_read_404_saved(db, s):
    """ASV-A-13 — a "not found" ValueError from the read becomes 404; the assignment stays saved.
    Rules: assign_tag R4a."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = ValueError("Account 5 not found")

    with pytest.raises(NotFoundError) as exc:
        with patch.object(svc, "get_account_with_tags", side_effect=e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )

    # Then 1
    assert exc.value.status_code == 404
    # Then 2
    assert exc.value.detail == "Account 5 not found"
    # Then 3
    db.rollback()
    rows = links(
        db, AccountTagAssignment.account_id == a.id, AccountTagAssignment.tag_id == t.id
    )
    assert len(rows) == 1


# [claude] ASV-A-14
def test_asv_a_14__other_value_error_from_read_422_saved(db, s):
    """ASV-A-14 — another ValueError from the read becomes 422; the assignment stays saved.
    Rules: assign_tag R4a."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = ValueError("bad state")

    with pytest.raises(BusinessRuleError) as exc:
        with patch.object(svc, "get_account_with_tags", side_effect=e):
            svc.assign_tag(
                db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
            )

    # Then 1
    assert exc.value.status_code == 422
    # Then 2
    assert exc.value.detail == "bad state"
    # Then 3
    db.rollback()
    assert reread(db, AccountTag, t.id).usage_count == 1


# --------------------------------------------------------------------------- #
# unassign_tag
# --------------------------------------------------------------------------- #


# [claude] ASV-N-01
def test_asv_n_01__tag_removed_and_committed(db, s):
    """ASV-N-01 — the tag is removed and committed.
    Rules: unassign_tag R1; TC1."""
    a = account(db, s)
    t = tag(db, s, usage_count=1)
    link(db, s, a, t)
    commit_point(db)

    result = svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert len(links(db, AccountTagAssignment.account_id == a.id)) == 0
    # Then 3
    assert reread(db, AccountTag, t.id).usage_count == 0


# [claude] ASV-N-02
def test_asv_n_02__missing_account_404(db, s):
    """ASV-N-02 — a missing account gets 404, rolled back.
    Rules: unassign_tag R2, Errors."""
    t = tag(db, s)
    commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.unassign_tag(db, account_id=MISSING, tag_id=t.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == "Account 999999999 not found"
    # Then 3
    assert x_gone(db, x_id)


# [claude] ASV-N-03
def test_asv_n_03__w2_account_404_link_kept(db, s):
    """ASV-N-03 — an account of W2 gets the same 404, its link kept.
    Rules: unassign_tag R2, Errors."""
    z = account(db, s, workspace_id=s.W2.id)
    t = tag(db, s, workspace_id=s.W2.id, usage_count=1)
    link(db, s, z, t, workspace_id=s.W2.id)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.unassign_tag(db, account_id=z.id, tag_id=t.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account {z.id} not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-N-04
@pytest.mark.xfail(strict=True, reason=BUG_879)
def test_asv_n_04__unassigned_tag_404_new_text(db, s):
    """ASV-N-04 — a tag that is not assigned gets 404 with the new text.
    Rules: unassign_tag R2 [BUG-879]."""
    a = account(db, s)
    t = tag(db, s)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Tag {t.id} assignment not found for account {a.id}"
    # Then 3
    assert written(db) == before


# [claude] ASV-N-05
@pytest.mark.xfail(strict=True, reason=BUG_863)
def test_asv_n_05__deleted_account_404_link_kept(db, s):
    """ASV-N-05 — a soft-deleted account gets 404, its link kept.
    Rules: unassign_tag R2, Errors [BUG-863]."""
    a = account(db, s, **gone(s))
    t = tag(db, s, usage_count=1)
    link(db, s, a, t)
    before = commit_point(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)
    # Then 2
    assert exc.value.detail == f"Account {a.id} not found"
    # Then 3
    assert written(db) == before


# [claude] ASV-N-06
def test_asv_n_06__other_exception_passes_unchanged(db, s):
    """ASV-N-06 — any other exception passes unchanged, every pending change discarded.
    Rules: unassign_tag R3; TC3."""
    a = account(db, s)
    t = tag(db, s, usage_count=1)
    link(db, s, a, t)
    before = commit_point(db)
    _x, x_id = mk_x(db)
    e = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with mgr_raises("unassign_tag", e):
            svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)

    # Then 1
    assert exc.value is e
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert written(db) == before


# [claude] ASV-N-07
@pytest.mark.xfail(strict=True, reason=BUG_873)
def test_asv_n_07__user_id_reaches_manager(db, s):
    """ASV-N-07 — user_id reaches the manager: audit row and updated_by.
    Rules: unassign_tag R4 [BUG-873]."""
    a = account(db, s)
    t = tag(db, s, usage_count=1)
    link(db, s, a, t)
    commit_point(db)

    # Fails today here: unassign_tag has no user_id parameter (TypeError).
    result = svc.unassign_tag(
        db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).updated_by == s.U1.id
    # Then 3
    rows = audit(db, a.id)
    assert len(rows) == 1
    assert rows[0].action_type == "updated"
    assert rows[0].performed_by == s.U1.id


# [claude] ASV-N-08
def test_asv_n_08__other_value_error_422_rolled_back(db, s):
    """ASV-N-08 — any other ValueError becomes 422 with the manager's text, rolled back.
    Rules: unassign_tag R2 (as assign_tag R2)."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    _x, x_id = mk_x(db)
    e = ValueError("bad state")

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        with mgr_raises("unassign_tag", e):
            svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)

    # Then 2
    assert exc.value.status_code == 422
    # Then 3
    assert exc.value.detail == "bad state"
    # Then 4
    assert x_gone(db, x_id)


# [claude] ASV-N-09
def test_asv_n_09__not_found_match_case_sensitive_422(db, s):
    """ASV-N-09 — the "not found" match is case-sensitive: "Not Found" gives 422.
    Rules: unassign_tag R2 (as assign_tag R2)."""
    a = account(db, s)
    t = tag(db, s)
    commit_point(db)
    e = ValueError("Tag 5 Not Found")

    # Then 1
    with pytest.raises(BusinessRuleError) as exc:
        with mgr_raises("unassign_tag", e):
            svc.unassign_tag(db, account_id=a.id, tag_id=t.id, workspace_id=s.W1.id)

    # Then 2
    assert exc.value.detail == "Tag 5 Not Found"


# --------------------------------------------------------------------------- #
# delete_account
# --------------------------------------------------------------------------- #


# [claude] ASV-D-01
def test_asv_d_01__live_account_soft_deleted(db, s):
    """ASV-D-01 — a live account is soft-deleted and committed.
    Rules: delete_account R1; TC1."""
    a = account(db, s)
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    row = reread(db, Account, a.id)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_by == s.U1.id
    assert row.deleted_at is not None
    # Then 3
    rows = audit(db, a.id)
    assert len(rows) == 1
    assert rows[0].action_type == "deleted"


# [claude] ASV-D-02
def test_asv_d_02__inactive_account_deleted_too(db, s):
    """ASV-D-02 — an inactive (not deleted) account is deleted too.
    Rules: delete_account R1."""
    a = account(db, s, is_active=False)
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    row = reread(db, Account, a.id)
    assert row.is_deleted is True
    assert row.deleted_by == s.U1.id


# [claude] ASV-D-03
def test_asv_d_03__missing_id_404(db, s):
    """ASV-D-03 — a missing id gets 404, nothing written.
    Rules: delete_account R2, Errors row 1."""
    account(db, s)
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.delete_account(
            db, account_id=MISSING, workspace_id=s.W1.id, user_id=s.U1.id
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Account with ID 999999999 not found"
    # Then 4
    assert x_gone(db, x_id)
    # Then 5
    assert written(db) == before


# [claude] ASV-D-04
def test_asv_d_04__w0_account_404(db, s):
    """ASV-D-04 — an account of W0 gets 404, untouched.
    Rules: delete_account R2."""
    z = account(db, s, workspace_id=s.W0.id)
    account(db, s)
    commit_point(db)
    before_z = snap(db, z.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.delete_account(db, account_id=z.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"
    # Then 3
    assert snap(db, z.id) == before_z


# [claude] ASV-D-05
def test_asv_d_05__w2_account_404(db, s):
    """ASV-D-05 — an account of W2 gets 404, untouched.
    Rules: delete_account R2."""
    account(db, s)
    z = account(db, s, workspace_id=s.W2.id)
    commit_point(db)
    before_z = snap(db, z.id)

    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.delete_account(db, account_id=z.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == f"Account with ID {z.id} not found"
    # Then 3
    assert snap(db, z.id) == before_z


# [claude] ASV-D-06
def test_asv_d_06__failing_commit_rolled_back(db, s):
    """ASV-D-06 — a failing commit is rolled back and re-raised.
    Rules: delete_account R6; TC4."""
    a = account(db, s)
    before = commit_point(db)
    before_a = snap(db, a.id)

    with pytest.raises(RuntimeError) as exc:
        with failing_commit(db) as rb:
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )

    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, a.id) == before_a
    # Then 4
    assert written(db) == before


# [claude] ASV-D-07
def test_asv_d_07__other_exception_passes_unchanged(db, s):
    """ASV-D-07 — any other exception passes unchanged, every pending change discarded.
    Rules: delete_account R6; TC3."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    _x, x_id = mk_x(db)
    e = RuntimeError("boom")

    with pytest.raises(RuntimeError) as exc:
        with mgr_raises("delete_account", e):
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )

    # Then 1
    assert exc.value is e
    # Then 2
    assert x_gone(db, x_id)
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-D-08
def test_asv_d_08__delete_takes_no_row_lock(db, s):
    """ASV-D-08 — the delete takes no row lock.
    Rules: delete_account R4 (manager R7d; HR-10 not applied)."""
    a = account(db, s)
    invoice(db, s, a, "settled")
    commit_point(db)

    with record_sql(db) as rec:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    assert all("FOR UPDATE" not in t.upper() for t in rec.stmts)
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).is_deleted is True


# [claude] ASV-D-09
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_d_09__already_deleted_400(db, s):
    """ASV-D-09 — an already-deleted account gets 400 "already deleted".
    Rules: delete_account R3, Errors row 2 [BUG-2986]."""
    a = account(db, s, **gone(s))
    before = commit_point(db)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Account {a.id} is already deleted"
    # Then 4
    row = reread(db, Account, a.id)
    assert row.deleted_at == T0
    assert row.deleted_by == s.U2.id
    # Then 5
    assert x_gone(db, x_id)
    # Then 6
    assert written(db) == before


# [claude] ASV-D-10
def test_asv_d_10__already_deleted_refusal_writes_nothing(db, s):
    """ASV-D-10 — today's already-deleted refusal still writes nothing.
    Rules: delete_account R3 (companion: nothing written holds before and after)."""
    a = account(db, s, **gone(s))
    before = commit_point(db)

    with pytest.raises(Exception):  # noqa: B017  (the card wraps the When in a bare Exception)
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)

    # Then 1
    row = reread(db, Account, a.id)
    assert row.deleted_at == T0
    assert row.deleted_by == s.U2.id
    assert row.is_deleted is True
    # Then 2
    assert written(db) == before


# [claude] ASV-D-11
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_d_11__already_deleted_with_open_invoice_400(db, s):
    """ASV-D-11 — an already-deleted account with an open invoice still gets "already deleted".
    Rules: delete_account R3 (manager R7c) [BUG-2986]."""
    a = account(db, s, **gone(s))
    invoice(db, s, a, "draft")
    before = commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == f"Account {a.id} is already deleted"
    # Then 3
    assert written(db) == before


# [claude] ASV-D-12
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_d_12__after_bug_862_second_delete_still_400(db, s):
    """ASV-D-12 — after BUG-862 hides deleted accounts, a second delete still gets 400.
    Rules: delete_account R3 (Q3) [BUG-2986]."""
    a = account(db, s, **gone(s))
    before = commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with hidden_deleted():
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.detail == f"Account {a.id} is already deleted"
    # Then 3
    assert written(db) == before


# [claude] ASV-D-13
@pytest.mark.xfail(strict=True, reason=BUG_876)
def test_asv_d_13__draft_invoice_blocks_delete(db, s):
    """ASV-D-13 — a draft invoice blocks the delete; the blocker is listed.
    Rules: delete_account R4, R5, Errors row 3 [BUG-876]."""
    a = account(db, s)
    i = invoice(db, s, a, "draft")
    before = commit_point(db)
    before_a = snap(db, a.id)
    _x, x_id = mk_x(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == OPEN
    # Then 4
    assert exc.value.errors == [{"type": "account_invoice", "id": i.id}]
    # Then 5
    assert snap(db, a.id) == before_a
    # Then 6
    assert len(audit(db, a.id)) == 0
    # Then 7
    assert x_gone(db, x_id)
    # Then 8
    assert written(db) == before


# [claude] ASV-D-14
@pytest.mark.xfail(strict=True, reason=BUG_876)
def test_asv_d_14__unpaid_invoice_blocks_delete(db, s):
    """ASV-D-14 — a confirmed unpaid invoice blocks the delete.
    Rules: delete_account R4, R5 [BUG-876]."""
    a = account(db, s)
    i = invoice(db, s, a, "unpaid")
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == OPEN
    # Then 3
    assert exc.value.errors == [{"type": "account_invoice", "id": i.id}]
    # Then 4
    assert snap(db, a.id) == before_a


# [claude] ASV-D-15
@pytest.mark.xfail(strict=True, reason=BUG_876)
def test_asv_d_15__partial_receivable_blocks_delete(db, s):
    """ASV-D-15 — a partially paid receivable invoice blocks the delete.
    Rules: delete_account R4, R5 [BUG-876]."""
    a = account(db, s)
    i = invoice(db, s, a, "partial", invoice_type="receivable")
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == OPEN
    # Then 3
    assert exc.value.errors == [{"type": "account_invoice", "id": i.id}]
    # Then 4
    assert snap(db, a.id) == before_a


# [claude] ASV-D-16
def test_asv_d_16__settled_invoice_does_not_block(db, s):
    """ASV-D-16 — a settled invoice does not block; the invoice is untouched.
    Rules: delete_account R1, R4 (manager R7b)."""
    a = account(db, s)
    i = invoice(db, s, a, "settled")
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).is_deleted is True
    # Then 3
    inv = reread(db, AccountInvoice, i.id)
    assert inv.invoice_status == "confirmed"
    assert inv.paid_amount == Decimal("1000.00")
    assert inv.payment_status == "paid"


# [claude] ASV-D-17
def test_asv_d_17__voided_invoice_does_not_block(db, s):
    """ASV-D-17 — a voided invoice does not block.
    Rules: delete_account R1, R4 (manager R7b)."""
    a = account(db, s)
    i = invoice(db, s, a, "voided")
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).is_deleted is True
    # Then 3
    assert reread(db, AccountInvoice, i.id).invoice_status == "voided"


# [claude] ASV-D-18
def test_asv_d_18__other_accounts_invoice_does_not_block(db, s):
    """ASV-D-18 — another account's open invoice does not block.
    Rules: delete_account R1, R4 (manager R7b)."""
    a = account(db, s)
    b = account(db, s, name="Beta Traders")
    invoice(db, s, b, "draft")
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).is_deleted is True
    # Then 3
    assert reread(db, Account, b.id).is_deleted is False


# [claude] ASV-D-19
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_19__blockers_by_id_ascending(db, s):
    """ASV-D-19 — two open invoices are listed by id ascending, inserted in reverse.
    Rules: delete_account R5 [BUG-2984]."""
    a = account(db, s)
    invoice(db, s, a, "unpaid", id=900000002)
    invoice(db, s, a, "draft", id=900000001)
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.errors == [
        {"type": "account_invoice", "id": 900000001},
        {"type": "account_invoice", "id": 900000002},
    ]
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-D-20
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_20__only_foreign_invoice_other_workspace(db, s):
    """ASV-D-20 — only an open invoice carrying W2's workspace_id: one other_workspace entry, no id.
    Rules: delete_account R5, R5a [BUG-2984] (HR-16)."""
    a = account(db, s)
    invoice(db, s, a, "draft", workspace_id=s.W2.id)
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == OPEN
    # Then 3
    assert exc.value.errors == [{"type": "other_workspace"}]
    # Then 4
    assert snap(db, a.id) == before_a


# [claude] ASV-D-21
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_21__own_then_other_workspace_last(db, s):
    """ASV-D-21 — own open invoice plus a W2 one: own entry, then other_workspace last.
    Rules: delete_account R5 [BUG-2984]."""
    a = account(db, s)
    i = invoice(db, s, a, "draft")
    invoice(db, s, a, "unpaid", workspace_id=s.W2.id)
    commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.errors == [
        {"type": "account_invoice", "id": i.id},
        {"type": "other_workspace"},
    ]


# [claude] ASV-D-22
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_22__w0_lower_id_other_workspace_still_last(db, s):
    """ASV-D-22 — a W0 invoice with a lower id than the own one: other_workspace still last.
    Rules: delete_account R5 [BUG-2984]."""
    a = account(db, s)
    invoice(db, s, a, "draft", workspace_id=s.W0.id, id=900000011)
    invoice(db, s, a, "draft", id=900000012)
    commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.errors == [
        {"type": "account_invoice", "id": 900000012},
        {"type": "other_workspace"},
    ]


# [claude] ASV-D-23
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_23__two_foreign_one_entry(db, s):
    """ASV-D-23 — two foreign open invoices give one other_workspace entry.
    Rules: delete_account R5, R5a [BUG-2984]."""
    a = account(db, s)
    invoice(db, s, a, "draft", workspace_id=s.W0.id)
    invoice(db, s, a, "partial", workspace_id=s.W2.id)
    commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.errors == [{"type": "other_workspace"}]


# [claude] ASV-D-24
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_24__only_open_one_listed(db, s):
    """ASV-D-24 — open plus settled and voided: only the open one is listed.
    Rules: delete_account R4, R5 [BUG-2984]."""
    a = account(db, s)
    invoice(db, s, a, "settled")
    invoice(db, s, a, "voided")
    i = invoice(db, s, a, "partial")
    before = commit_point(db)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.errors == [{"type": "account_invoice", "id": i.id}]
    # Then 3
    assert written(db) == before


# [claude] ASV-D-25
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_25__translation_open_invoices_carries_blockers(db, s):
    """ASV-D-25 — translation: the manager's open-invoices refusal carries its blockers into errors.
    Rules: delete_account R5 [BUG-2984]."""
    a = account(db, s)
    commit_point(db)
    _x, x_id = mk_x(db)
    b = [{"type": "account_invoice", "id": 118}, {"type": "account_invoice", "id": 131}]
    e = ValueError(OPEN, b)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with mgr_raises("delete_account", e):
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == OPEN
    # Then 4
    assert exc.value.errors == [
        {"type": "account_invoice", "id": 118},
        {"type": "account_invoice", "id": 131},
    ]
    # Then 5
    assert x_gone(db, x_id)


# [claude] ASV-D-26
@pytest.mark.xfail(strict=True, reason=BUG_2986)
def test_asv_d_26__translation_already_deleted_400(db, s):
    """ASV-D-26 — translation: "already deleted" from the manager becomes 400.
    Rules: delete_account R3 [BUG-2986]."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    e = ValueError(f"Account {a.id} is already deleted")

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with mgr_raises("delete_account", e):
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value.detail == f"Account {a.id} is already deleted"
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-D-27
def test_asv_d_27__other_value_error_passes_unchanged(db, s):
    """ASV-D-27 — any other ValueError of the manager passes unchanged.
    Rules: delete_account R6 (Q1: other ValueErrors are not translated)."""
    a = account(db, s)
    commit_point(db)
    before_a = snap(db, a.id)
    e = ValueError("something else")

    # Then 1
    with pytest.raises(ValueError) as exc:
        with mgr_raises("delete_account", e):
            svc.delete_account(
                db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
            )
    # Then 2
    assert exc.value is e
    # Then 3
    assert snap(db, a.id) == before_a


# [claude] ASV-D-28
@pytest.mark.xfail(strict=True, reason=BUG_140)
def test_asv_d_28__ip_and_user_agent_reach_audit(db, s):
    """ASV-D-28 — client IP and user agent reach the audit row.
    Rules: delete_account R7 [BUG-140]."""
    a = account(db, s)
    commit_point(db)

    # Fails today here: delete_account has no ip_address / user_agent parameters (TypeError).
    result = svc.delete_account(
        db,
        account_id=a.id,
        workspace_id=s.W1.id,
        user_id=s.U1.id,
        ip_address="203.0.113.7",
        user_agent="UA/1.0",
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    rows = audit(db, a.id)
    assert len(rows) == 1
    assert rows[0].action_type == "deleted"
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "UA/1.0"


# [claude] ASV-D-29
def test_asv_d_29__voided_foreign_invoice_blocks_nothing(db, s):
    """ASV-D-29 — a voided invoice carrying W2's workspace_id blocks nothing.
    Rules: delete_account R5a, R1."""
    a = account(db, s)
    f = invoice(db, s, a, "voided", workspace_id=s.W2.id)
    commit_point(db)

    result = svc.delete_account(
        db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id
    )

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, Account, a.id).is_deleted is True
    # Then 3
    inv = reread(db, AccountInvoice, f.id)
    assert inv.invoice_status == "voided"
    assert inv.workspace_id == s.W2.id


# [claude] ASV-D-30
@pytest.mark.xfail(strict=True, reason=BUG_2984)
def test_asv_d_30__own_plus_two_foreign(db, s):
    """ASV-D-30 — one own open invoice plus two foreign ones: own entry, then one other_workspace.
    Rules: delete_account R5, R5a [BUG-2984]."""
    a = account(db, s)
    invoice(db, s, a, "unpaid", workspace_id=s.W0.id)
    i = invoice(db, s, a, "draft")
    invoice(db, s, a, "partial", workspace_id=s.W2.id)
    commit_point(db)
    before_a = snap(db, a.id)

    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_account(db, account_id=a.id, workspace_id=s.W1.id, user_id=s.U1.id)
    # Then 2
    assert exc.value.detail == OPEN
    # Then 3
    assert exc.value.errors == [
        {"type": "account_invoice", "id": i.id},
        {"type": "other_workspace"},
    ]
    # Then 4
    assert snap(db, a.id) == before_a
