"""Unit tests for app/managers/account_manager.py.

Implements tests/unit/managers/account_manager.cases.md (revision 2), one test
per case. Real Postgres session (`db` fixture). Only mocks: the spec's
externals `app.managers.account_manager.utcnow` and
`app.utils.audit_logger.utcnow` (both -> NOW, every test). No race simulations.

Built in local-coder mode: the scaffold and the exemplar tests in the first
part of this file are hand-written; tests below a `# [local-coder] <ID>`
comment were written by the local model from one case card each, with
tests/unit/managers/account_manager.helpers.md as its only view of this file.
"""
# ruff: noqa: SIM117, DTZ001  (prescribed by the cards: nested with, naive datetimes)
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.managers.account_manager import AccountManager
from app.models.account import Account
from app.models.account_invoice import AccountInvoice
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.financial_audit_log import FinancialAuditLog
from app.schemas.account import AccountCreate, AccountUpdate
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "MISSING / MISSING2": ids that no row of any table has
MISSING = 999999999
MISSING2 = 999999998

# Convention "T0" and "NOW" (both naive)
T0 = datetime(2026, 1, 1, 9, 0, 0)
NOW = datetime(2026, 3, 1, 10, 0, 0)

# Convention "FILLED": the 13 optional fields with their filled values
FILLED = {
    "account_code": "SUP-001",
    "primary_contact_person": "Rahim",
    "primary_email": "rahim@acme.test",
    "primary_phone": "+8801700000001",
    "secondary_contact_person": "Karim",
    "secondary_email": "karim@acme.test",
    "secondary_phone": "+8801700000002",
    "address": "12 Lake Road",
    "city": "Dhaka",
    "country": "Bangladesh",
    "postal_code": "1207",
    "payment_preferences": "Bank transfer, 30 days",
    "bank_details": "City Bank 001-234",
}

# Convention "the 13 optional fields"
OPTIONAL_FIELDS = tuple(FILLED)

# Convention "OPEN_INVOICES": the error text; the dash is an em dash (U+2014)
OPEN_INVOICES = "Account has open invoices — settle or void them first"

# Convention "invoice of A": the five consistent states (all three columns each)
INVOICE_STATES = {
    "draft": ("draft", Decimal("0.00"), "unpaid"),
    "unpaid": ("confirmed", Decimal("0.00"), "unpaid"),
    "partial": ("confirmed", Decimal("400.00"), "partial"),
    "paid": ("confirmed", Decimal("1000.00"), "paid"),
    "voided": ("voided", Decimal("0.00"), "unpaid"),
}

BUG_872 = "BUG-872: Account audit rows omit bank details and many other fields"


# Convention "SNAP(k=v, ...)": the full 17-key audit snapshot with keys replaced
def SNAP(**replaced):
    snapshot = {"name": "Acme Ltd"}
    snapshot.update(dict.fromkeys(OPTIONAL_FIELDS))
    snapshot.update(allow_invoices=True, is_active=True, tag_ids=[])
    for key, value in replaced.items():
        if key not in snapshot:
            raise KeyError(f"SNAP has no key {key!r}")
        snapshot[key] = value
    return snapshot


# --------------------------------------------------------------------------- #
# Conventions -> fixtures
# --------------------------------------------------------------------------- #

# Convention "Externals": every test patches both utcnow names -> NOW
@pytest.fixture(autouse=True)
def clock():
    with patch("app.managers.account_manager.utcnow", return_value=NOW), \
         patch("app.utils.audit_logger.utcnow", return_value=NOW):
        yield


# Convention "W1, W2 = two workspaces rows"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


# Convention "U1 creates every Given row, U2 is the acting user of every call"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db):
    return make_profile(db)


# Convention "M = an AccountManager instance"
@pytest.fixture
def M():
    return AccountManager()


# Convention "default account" / "filled account" / "deleted" / A1, A2, A9
@pytest.fixture
def mk_account(db, w1, u1):
    """mk_account(deleted=False, **columns) -> Account, inserted and flushed."""
    def _mk(deleted=False, **columns):
        fields = {
            "name": "Acme Ltd", "workspace_id": w1.id, "allow_invoices": True,
            "is_active": True, "is_deleted": False, "created_by": u1.id,
        }
        if deleted:
            fields.update(is_deleted=True, is_active=False, deleted_at=T0, deleted_by=u1.id)
        fields.update(columns)
        row = Account(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "default tag" / T1, T2, T3, T9
@pytest.fixture
def mk_tag(db, w1):
    """mk_tag(name, tag_code, **columns) -> AccountTag, inserted and flushed."""
    def _mk(name, tag_code, **columns):
        fields = {
            "name": name, "tag_code": tag_code, "workspace_id": w1.id,
            "is_active": True, "usage_count": 0, "is_system_tag": False,
        }
        fields.update(columns)
        row = AccountTag(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "A has T" (does not change usage_count)
@pytest.fixture
def mk_link(db, u1):
    """mk_link(account, tag, **columns) -> AccountTagAssignment, inserted and flushed."""
    def _mk(account, tag, **columns):
        fields = {
            "account_id": account.id, "tag_id": tag.id,
            "workspace_id": account.workspace_id,
            "assigned_by": u1.id, "assigned_at": T0,
        }
        fields.update(columns)
        row = AccountTagAssignment(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# Convention "invoice of A" (inserted through the model, never through a manager)
@pytest.fixture
def mk_invoice(db):
    """mk_invoice(account, state, **columns) -> AccountInvoice, inserted and flushed.

    `state` is one of "draft", "unpaid", "partial", "paid", "voided".
    """
    def _mk(account, state, **columns):
        invoice_status, paid_amount, payment_status = INVOICE_STATES[state]
        fields = {
            "workspace_id": account.workspace_id, "account_id": account.id,
            "invoice_type": "payable", "invoice_amount": Decimal("1000.00"),
            "invoice_date": date(2026, 1, 15), "allow_payments": True,
            "invoice_status": invoice_status, "paid_amount": paid_amount,
            "payment_status": payment_status,
        }
        fields.update(columns)
        row = AccountInvoice(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (they read only; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of `row` (any model) from the database, or None if it is gone."""
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row` (any model), or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


def count_rows(db, model, **equals):
    """Number of rows of `model` in the database (all workspaces), optionally filtered."""
    table = model.__table__
    stmt = select(func.count()).select_from(table)
    for column, value in equals.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": the three row counts and every tag's usage_count
def written(db):
    return {
        "accounts": count_rows(db, Account),
        "account_tag_assignments": count_rows(db, AccountTagAssignment),
        "financial_audit_logs": count_rows(db, FinancialAuditLog),
        "usage_count": dict(db.execute(
            select(AccountTag.__table__.c.id, AccountTag.__table__.c.usage_count)).all()),
    }


# Convention "tags(A)": sorted tag_id list of the account's assignment rows
def tags(db, account):
    table = AccountTagAssignment.__table__
    return list(db.execute(
        select(table.c.tag_id).where(table.c.account_id == _id_of(account)).order_by(table.c.tag_id)
    ).scalars())


def links(db, account):
    """Fresh assignment rows of the account, ordered by tag_id."""
    account_id = _id_of(account)
    db.expire_all()
    return list(db.execute(
        select(AccountTagAssignment)
        .where(AccountTagAssignment.account_id == account_id)
        .order_by(AccountTagAssignment.tag_id, AccountTagAssignment.id)
    ).scalars())


def link_row(db, account, tag):
    """Fresh assignment row of (account, tag), or None."""
    tag_id = _id_of(tag)
    found = [x for x in links(db, account) if x.tag_id == tag_id]
    return found[0] if found else None


# Convention "audit(A)": financial_audit_logs rows of entity "account" / A.id
def audit(db, account):
    account_id = _id_of(account)
    db.expire_all()
    return list(db.execute(
        select(FinancialAuditLog)
        .where(FinancialAuditLog.entity_type == "account",
               FinancialAuditLog.entity_id == account_id)
        .order_by(FinancialAuditLog.id)
    ).scalars())


# Convention "SQL of the call" / "tags SELECT": every statement the session's
# connection sends while the block runs.
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

    def selects_with(self, text):
        """The recorded SELECT statements whose text contains `text`."""
        return [s for s in self.statements if s.lstrip().upper().startswith("SELECT") and text in s]


# --------------------------------------------------------------------------- #
# Exemplar cases (hand-written; copied verbatim into the helper sheet)
# --------------------------------------------------------------------------- #

def test_acc_u_01__unknown_account_id_rejected(db, M, w1, u2, mk_account):
    """ACC-U-01 — updating an unknown account id raises and writes nothing.
    Rules: update_account R1; Errors row 1"""
    a1 = mk_account()
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=MISSING, account_data=AccountUpdate(name="New Name"),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert snap(db, a1) == before_a1


def test_acc_u_28__tag_list_replaces_tags(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-28 — a tag list replaces the account's tags and adjusts usage counts.
    Rules: update_account R11, R12"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    t4 = mk_tag("Utility", "utility", usage_count=5)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t2.id, t4.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t2.id, t4.id]
    # Then 3
    for x in links(db, a1):
        assert x.workspace_id == w1.id
        assert x.assigned_by == u2.id
        assert x.assigned_at is not None
    # Then 4
    assert reread(db, t1).usage_count == 0
    # Then 5
    assert reread(db, t2).usage_count == 1
    # Then 6
    assert reread(db, t4).usage_count == 6


@pytest.mark.xfail(strict=True, reason=BUG_872)
def test_acc_c_17__audit_full_snapshot(db, M, w1, u2, mk_tag):
    """ACC-C-17 — the audit row holds the full snapshot including tag ids.
    Rules: create_account R9 [BUG-872]"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t2 = mk_tag("Client", "client", usage_count=0)

    result = M.create_account(
        db, account_data=AccountCreate(name="Acme Ltd", **FILLED, allow_invoices=False, tag_ids=[t2.id, t1.id]),
        workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    logs = audit(db, result)
    assert len(logs) == 1
    # Then 3
    assert logs[0].changes == {"after": SNAP(**FILLED, allow_invoices=False, tag_ids=[t1.id, t2.id])}


def test_acc_a_14__db_forbids_second_assignment(db, u2, mk_account, mk_tag, mk_link):
    """ACC-A-14 — a second assignment of the same tag fails on flush.
    Rules: assign_tag R10"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            mk_link(a1, t1, assigned_by=u2.id, assigned_at=NOW)

    # Then 2
    assert tags(db, a1) == [t1.id]


# [local-coder] ACC-C-01
def test_acc_c_01__minimal_create_stores_defaults_and_system_fields(db, M, w1, u2):
    """ACC-C-01 — minimal create stores the account with defaults and system fields.
    Rules: create_account R1, R3, R4, R5"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Acme Ltd"
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) is None
    assert row.allow_invoices is True
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_active is True
    assert row.is_deleted is False
    assert row.created_at is not None
    # Then 4
    assert row.updated_at is None
    assert row.updated_by is None
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 5
    assert count_rows(db, Account) == 1
    # Then 6
    assert count_rows(db, AccountTagAssignment) == 0


# [local-coder] ACC-U-02
def test_acc_u_02__account_of_another_workspace_is_rejected(db, M, w1, w2, u2, mk_account):
    """ACC-U-02 — account of another workspace is rejected and not changed.
    Rules: update_account R2 (error raised, nothing written)"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    before_a9 = snap(db, a9)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError):
        M.update_account(db, account_id=a9.id, account_data=AccountUpdate(name="New Name"),
                         workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert snap(db, a9) == before_a9
    row = reread(db, a9)
    assert row.name == "Zeta Corp"
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-G-01
def test_acc_g_01__live_account_of_workspace_is_returned(db, M, w1, mk_account):
    """ACC-G-01 — a live account of the workspace is returned.
    Rules: get_account R1"""
    a1 = mk_account()
    mk_account(name="Beta Co")

    result = M.get_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result is not None
    assert result.id == a1.id
    assert result.name == "Acme Ltd"


# [local-coder] ACC-G-02
def test_acc_g_02__unknown_id_returns_none(db, M, w1, mk_account):
    """ACC-G-02 — unknown id returns None.
    Rules: get_account R2"""
    mk_account()

    result = M.get_account(db, account_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] ACC-A-01
def test_acc_a_01__assigning_a_tag_creates_one_assignment_and_raises_the_count(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-01 — assigning a tag creates one assignment and raises the count.
    Rules: assign_tag R7"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=2)

    result = M.assign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    x1 = link_row(db, a1, t1)
    assert x1.account_id == a1.id
    assert x1.tag_id == t1.id
    assert x1.workspace_id == w1.id
    assert x1.assigned_by == u2.id
    assert x1.assigned_at is not None
    assert x1.id is not None
    # Then 4
    assert reread(db, t1).usage_count == 3


# [local-coder] ACC-C-02
def test_acc_c_02__every_sent_field_stored_exactly_as_sent(db, M, w1, u2):
    """ACC-C-02 — every sent field is stored exactly as sent.
    Rules: create_account R1"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", **FILLED, allow_invoices=False),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Acme Ltd"
    assert row.allow_invoices is False
    # Then 3
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) == FILLED[f]
    # Then 4
    assert count_rows(db, Account) == 1


# [local-coder] ACC-C-03
def test_acc_c_03__account_created_in_workspace_passed_as_argument(db, M, w1, w2, u2, mk_account):
    """ACC-C-03 — the account is created in the workspace passed as argument.
    Rules: create_account R3"""
    a1 = mk_account()
    before_a1 = snap(db, a1)

    result = M.create_account(db, account_data=AccountCreate(name="Zeta Corp"), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a1.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.name == "Zeta Corp"
    assert row.created_by == u2.id
    # Then 3
    assert count_rows(db, Account, workspace_id=w2.id) == 1
    # Then 4
    assert count_rows(db, Account, workspace_id=w1.id) == 1
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] ACC-C-04
@pytest.mark.xfail(strict=True, reason="BUG-860: Blank / whitespace-only account names accepted and names stored untrimmed")
def test_acc_c_04__name_is_stored_trimmed(db, M, w1, u2):
    """ACC-C-04 — name is stored trimmed.
    Rules: create_account R2 [BUG-860], R8"""
    result = M.create_account(db, account_data=AccountCreate(name="  Acme  Ltd  "), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "Acme  Ltd"
    # Then 3
    logs = audit(db, result)
    assert len(logs) == 1
    assert logs[0].description == "Account 'Acme  Ltd' created"


# [local-coder] ACC-C-05
def test_acc_c_05__inner_whitespace_and_case_of_name_are_kept(db, M, w1, u2):
    """ACC-C-05 — inner whitespace and case of the name are kept
    Rules: create_account R2"""
    result = M.create_account(db, account_data=AccountCreate(name="acme  LTD"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.name == "acme  LTD"


# [local-coder] ACC-C-06
@pytest.mark.xfail(strict=True, reason="BUG-860: Blank / whitespace-only account names accepted and names stored untrimmed")
def test_acc_c_06__whitespace_only_name_rejected(db):
    """ACC-C-06 — whitespace-only name is rejected by the schema
    Rules: create_account R2 [BUG-860]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountCreate(name="   ")

    # Then 2
    assert count_rows(db, Account) == 0


# [local-coder] ACC-C-07
def test_acc_c_07__empty_name_is_rejected_by_the_schema(db):
    """ACC-C-07 — empty name is rejected by the schema.
    Rules: create_account R2"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountCreate(name="")

    # Then 2
    assert count_rows(db, Account) == 0


# [local-coder] ACC-C-08
def test_acc_c_08__valid_tag_ids_are_attached_and_counted(db, M, w1, u2, mk_tag):
    """ACC-C-08 — valid tag ids are attached and counted.
    Rules: create_account R6; _assign_tags_to_account R4"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t2 = mk_tag("Client", "client", usage_count=3)

    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t1.id, t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert tags(db, result) == [t1.id, t2.id]
    # Then 3
    for x in links(db, result):
        assert x.workspace_id == w1.id
        assert x.assigned_by == u2.id
        assert x.assigned_at is not None
    # Then 4
    assert reread(db, t1).usage_count == 1
    # Then 5
    assert reread(db, t2).usage_count == 4


# [local-coder] ACC-C-09
def test_acc_c_09__same_tag_id_twice_gives_one_assignment(db, M, w1, u2, mk_tag):
    """ACC-C-09 — the same tag id twice gives one assignment.
    Rules: create_account R6; _assign_tags_to_account R5"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t1.id, t1.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert tags(db, result) == [t1.id]
    # Then 3
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-C-10
def test_acc_c_10__empty_tag_list_attaches_nothing(db, M, w1, u2, mk_tag):
    """ACC-C-10 — empty tag list attaches nothing.
    Rules: create_account R5"""
    t1 = mk_tag("Supplier", "supplier", usage_count=2)

    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, AccountTagAssignment) == 0
    # Then 3
    assert reread(db, t1).usage_count == 2


# [local-coder] ACC-C-11
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_c_11__unknown_tag_id_rejects_create(db, M, w1, u2):
    """ACC-C-11 — unknown tag id rejects the create.
    Rules: create_account R6a [BUG-871]"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[MISSING]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-C-12
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_c_12__tag_of_another_workspace_rejects_the_create(db, M, w1, w2, u2, mk_tag):
    """ACC-C-12 — tag of another workspace rejects the create
    Rules: create_account R6a [BUG-871]"""
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t9.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t9.id} not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert reread(db, t9).usage_count == 1


# [local-coder] ACC-C-13
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_c_13__one_unknown_id_rejects_the_whole_list_valid_tags_are_not_attached(db, M, w1, u2, mk_tag):
    """ACC-C-13 — one unknown id rejects the whole list, valid tags are not attached.
    Rules: create_account R6a [BUG-871]; _assign_tags_to_account R7 [BUG-871]"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t1.id, MISSING]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-C-14
@pytest.mark.xfail(strict=True, reason="BUG-2987: Creating or updating an account accepts a deleted (inactive) tag that \"assign tag\" refuses")
def test_acc_c_14__inactive_tag_rejects_the_create(db, M, w1, u2, mk_tag):
    """ACC-C-14 — inactive tag rejects the create
    Rules: create_account R6b [BUG-2987]"""
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t3.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert reread(db, t3).usage_count == 0


# [local-coder] ACC-C-15
@pytest.mark.xfail(strict=True, reason="BUG-2987: Creating or updating an account accepts a deleted (inactive) tag that \"assign tag\" refuses")
def test_acc_c_15__one_inactive_tag_rejects_the_whole_list_valid_tags_are_not_attached(db, M, w1, u2, mk_tag):
    """ACC-C-15 — one inactive tag rejects the whole list, valid tags are not attached.
    Rules: create_account R6b [BUG-2987]; _assign_tags_to_account R7"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Acme Ltd", tag_ids=[t1.id, t3.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert reread(db, t1).usage_count == 0
    # Then 4
    assert reread(db, t3).usage_count == 0


# [local-coder] ACC-C-16
def test_acc_c_16__create_writes_one_created_audit_row(db, M, w1, u2):
    """ACC-C-16 — create writes one "created" audit row
    Rules: create_account R8, R9 (keys written today), R10 (not passed)"""

    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", primary_contact_person="Rahim", primary_email="rahim@acme.test", address="12 Lake Road", city="Dhaka", country="Bangladesh"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, FinancialAuditLog) == 1
    logs = audit(db, result)
    assert len(logs) == 1
    log = logs[0]
    # Then 3
    assert log.entity_type == "account"
    assert log.entity_id == result.id
    assert log.workspace_id == w1.id
    assert log.related_entity_type is None
    assert log.related_entity_id is None
    # Then 4
    assert log.action_type == "created"
    assert log.description == "Account 'Acme Ltd' created"
    assert log.performed_by == u2.id
    assert log.performed_at == NOW
    # Then 5
    assert log.ip_address is None
    assert log.user_agent is None
    # Then 6
    assert "after" in log.changes
    assert "before" not in log.changes
    # Then 7
    assert log.changes["after"]["name"] == "Acme Ltd"
    assert log.changes["after"]["primary_contact_person"] == "Rahim"
    assert log.changes["after"]["primary_email"] == "rahim@acme.test"
    assert log.changes["after"]["address"] == "12 Lake Road"
    assert log.changes["after"]["city"] == "Dhaka"
    assert log.changes["after"]["country"] == "Bangladesh"


# [local-coder] ACC-C-18
@pytest.mark.xfail(strict=True, reason="BUG-872: Account audit rows omit bank details and many other fields")
def test_acc_c_18__full_snapshot_shows_unset_fields_as_null_and_an_empty_tag_list(db, M, w1, u2):
    """ACC-C-18 — full snapshot shows unset fields as null and an empty tag list.
    Rules: create_account R9 [BUG-872]"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    logs = audit(db, result)
    assert len(logs) == 1
    # Then 3
    assert logs[0].changes == {"after": SNAP()}


# [local-coder] ACC-C-19
@pytest.mark.xfail(strict=True, reason="BUG-140: Financial audit rows never record IP address or user agent")
def test_acc_c_19__client_ip_and_user_agent_written_to_audit(db, M, w1, u2):
    """ACC-C-19 — client IP and user agent are written to the audit row.
    Rules: create_account R10 [BUG-140]"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd"),
                              workspace_id=w1.id, user_id=u2.id, ip_address="203.0.113.7", user_agent="pytest-agent/1.0")

    # Then 1
    assert result.id is not None
    # Then 2
    logs = audit(db, result)
    assert len(logs) == 1
    # Then 3
    assert logs[0].ip_address == "203.0.113.7"
    assert logs[0].user_agent == "pytest-agent/1.0"


# [local-coder] ACC-C-20
def test_acc_c_20__second_account_same_name_allowed(db, M, w1, u2, mk_account):
    """ACC-C-20 — a second account with the same name is allowed.
    Rules: create_account R11"""
    a1 = mk_account()

    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a1.id
    # Then 2
    assert count_rows(db, Account, workspace_id=w1.id, name="Acme Ltd") == 2


# [local-coder] ACC-C-21
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_21__duplicate_account_code_is_rejected(db, M, w1, u2, mk_account):
    """ACC-C-21 — duplicate account code is rejected.
    Rules: create_account R11a [BUG-874]; Errors row 3"""
    a1 = mk_account(account_code="SUP-001")
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account code 'SUP-001' already exists"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] ACC-C-22
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_22__account_code_is_compared_trimmed_and_case_insensitively(db, M, w1, u2, mk_account):
    """ACC-C-22 — account code is compared trimmed and case-insensitively
    Rules: create_account R11a [BUG-874]; Errors row 3"""
    a1 = mk_account(account_code="SUP-001")
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.create_account(db, account_data=AccountCreate(name="Beta Traders", account_code=" sup-001 "),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account code 'sup-001' already exists"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert snap(db, a1) == before_a1


# [local-coder] ACC-C-23
def test_acc_c_23__soft_deleted_account_code_reused(db, M, w1, u2, mk_account):
    """ACC-C-23 — the code of a soft-deleted account can be reused.
    Rules: create_account R11a (soft-deleted do not count)"""
    a1 = mk_account(deleted=True, account_code="SUP-001")

    result = M.create_account(db, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a1.id
    # Then 2
    row = reread(db, result)
    assert row.account_code == "SUP-001"
    assert row.is_deleted is False
    # Then 3
    assert count_rows(db, Account) == 2


# [local-coder] ACC-C-24
def test_acc_c_24__same_code_in_another_workspace_is_no_conflict(db, M, w1, w2, u2, mk_account):
    """ACC-C-24 — the same code in another workspace is no conflict
    Rules: create_account R11a (per workspace)"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id, account_code="SUP-001")
    before_a9 = snap(db, a9)

    result = M.create_account(db, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a9.id
    # Then 2
    row = reread(db, result)
    assert row.account_code == "SUP-001"
    assert row.workspace_id == w1.id
    # Then 3
    assert snap(db, a9) == before_a9


# [local-coder] ACC-C-25
def test_acc_c_25__empty_string_codes_do_not_conflict(db, M, w1, u2, mk_account):
    """ACC-C-25 — empty-string codes do not conflict
    Rules: create_account R11a (non-empty boundary), R11b (a blank code never conflicts)"""
    a1 = mk_account(account_code="")

    result = M.create_account(db, account_data=AccountCreate(name="Beta Traders", account_code=""),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a1.id
    # Then 2
    assert count_rows(db, Account, workspace_id=w1.id) == 2


# [local-coder] ACC-C-26
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_26__database_forbids_duplicate_account_code(db, mk_account):
    """ACC-C-26 — the database itself forbids two live accounts with the same code.
    Rules: create_account R11a [BUG-874]"""
    mk_account(account_code="SUP-001")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            mk_account(name="Beta Traders", account_code="sup-001")

    # Then 2
    assert count_rows(db, Account) == 1


# [local-coder] ACC-C-27
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_c_27__invalid_primary_email_rejected_by_schema(db):
    """ACC-C-27 — invalid primary email is rejected by the schema.
    Rules: create_account R12 [BUG-875]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountCreate(name="Acme Ltd", primary_email="call me")

    # Then 2
    assert count_rows(db, Account) == 0


# [local-coder] ACC-C-28
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_c_28__invalid_secondary_email_rejected_by_schema(db):
    """ACC-C-28 — invalid secondary email is rejected by the schema.
    Rules: create_account R12 [BUG-875]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountCreate(name="Acme Ltd", secondary_email="not-an-email")

    # Then 2
    assert count_rows(db, Account) == 0


# [local-coder] ACC-C-29
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_c_29__email_fields_are_trimmed_by_the_schema():
    """ACC-C-29 — email fields are trimmed by the schema.
    Rules: create_account R12 [BUG-875]"""
    obj = AccountCreate(name="Acme Ltd", primary_email="  rahim@acme.test  ", secondary_email=" karim@acme.test ")

    # Then 1
    assert isinstance(obj, AccountCreate)
    # Then 2
    assert obj.primary_email == "rahim@acme.test"
    # Then 3
    assert obj.secondary_email == "karim@acme.test"


# [local-coder] ACC-C-30
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_30__account_code_stored_trimmed(db, M, w1, u2):
    """ACC-C-30 — the account code is stored trimmed, case kept
    Rules: create_account R11b [BUG-874]"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", account_code="  Sup-001 "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.account_code == "Sup-001"


# [local-coder] ACC-C-31
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_31__empty_account_code_stored_as_null(db, M, w1, u2):
    """ACC-C-31 — an empty account code is stored as NULL.
    Rules: create_account R11b [BUG-874]"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", account_code=""),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.account_code is None


# [local-coder] ACC-C-32
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_32__whitespace_only_account_code_stored_as_null(db, M, w1, u2):
    """ACC-C-32 — a whitespace-only account code is stored as NULL.
    Rules: create_account R11b [BUG-874]"""
    result = M.create_account(db, account_data=AccountCreate(name="Acme Ltd", account_code="   "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.account_code is None


# [local-coder] ACC-C-33
def test_acc_c_33__whitespace_only_codes_do_not_conflict(db, M, w1, u2, mk_account):
    """ACC-C-33 — whitespace-only codes do not conflict
    Rules: create_account R11b (a blank code never conflicts), R11a (non-empty boundary)"""
    a1 = mk_account(account_code="   ")
    a2 = mk_account(name="Beta Co")
    before_a1 = snap(db, a1)

    result = M.create_account(db, account_data=AccountCreate(name="Gamma Inc", account_code=" "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    assert result.id != a1.id
    assert result.id != a2.id
    # Then 2
    row = reread(db, result)
    assert row.name == "Gamma Inc"
    # Then 3
    assert (row.account_code or "").strip() == ""
    # Then 4
    assert count_rows(db, Account, workspace_id=w1.id) == 3
    # Then 5
    assert snap(db, a1) == before_a1


# [local-coder] ACC-C-34
def test_acc_c_34__blank_account_code_allowed(db, w1, mk_account):
    """ACC-C-34 — the database allows several live accounts with a blank code.
    Rules: create_account R11a (the index covers only non-empty trimmed codes), R11b"""
    mk_account(account_code="")
    mk_account(name="Beta Co")

    new_row = mk_account(name="Gamma Inc", account_code="   ")

    # Then 1
    assert new_row.id is not None
    # Then 2
    assert count_rows(db, Account, workspace_id=w1.id) == 3


# [local-coder] ACC-C-35
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_c_35__the_database_index_ignores_padding(db, mk_account):
    """ACC-C-35 — the database index ignores padding around the code.
    Rules: create_account R11a [BUG-874]"""
    mk_account(account_code="SUP-001")

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            mk_account(name="Beta Traders", account_code=" SUP-001 ")

    # Then 2
    assert count_rows(db, Account) == 1


# [local-coder] ACC-U-03
@pytest.mark.xfail(strict=True, reason="BUG-440: Non-members can enumerate which workspace ids exist")
def test_acc_u_03__account_of_another_workspace_gets_plain_not_found(db, M, w1, w2, u2, mk_account):
    """ACC-U-03 — account of another workspace gets the plain "not found" message.
    Rules: update_account R2 [BUG-440]"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    before_a9 = snap(db, a9)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a9.id, account_data=AccountUpdate(name="New Name"),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a9.id} not found"
    # Then 2
    assert snap(db, a9) == before_a9


# [local-coder] ACC-U-04
@pytest.mark.xfail(strict=True, reason="BUG-863: Soft-deleted accounts can still be edited and tagged / untagged")
def test_acc_u_04__soft_deleted_account_cannot_be_updated(db, M, w1, u2, mk_account):
    """ACC-U-04 — soft-deleted account cannot be updated.
    Rules: update_account R3 [BUG-863]"""
    a1 = mk_account(deleted=True)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="New Name", is_active=True),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a1.id} not found"
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.is_active is False
    assert row.is_deleted is True
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-05
def test_acc_u_05__every_sent_field_is_stored(db, M, w1, u2, mk_account, u1):
    """ACC-U-05 — every sent field is stored.
    Rules: update_account R4, R8 (a value changed), R9, R19"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Beta Co", **FILLED, allow_invoices=False, is_active=False),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Beta Co"
    assert row.allow_invoices is False
    assert row.is_active is False
    # Then 3
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) == FILLED[f]
    # Then 4
    assert row.updated_by == u2.id
    assert row.updated_at is not None
    # Then 5
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, Account) == 1


# [local-coder] ACC-U-06
def test_acc_u_06__fields_that_are_not_sent_keep_their_value(db, M, w1, u2, mk_account):
    """ACC-U-06 — fields that are not sent keep their value.
    Rules: update_account R4"""
    a1 = mk_account(**FILLED)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(city="Chattogram"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.city == "Chattogram"
    # Then 3
    assert row.name == "Acme Ltd"
    assert row.allow_invoices is True
    assert row.is_active is True
    # Then 4
    for f in OPTIONAL_FIELDS:
        if f != "city":
            assert getattr(row, f) == FILLED[f]


# [local-coder] ACC-U-07
def test_acc_u_07__allow_invoices_false_and_is_active_false_are_stored(db, M, w1, u2, mk_account):
    """ACC-U-07 — allow_invoices=False and is_active=False are stored.
    Rules: update_account R4, R7"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(allow_invoices=False, is_active=False),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.allow_invoices is False
    assert row.is_active is False
    # Then 3
    assert row.is_deleted is False
    assert row.deleted_at is None
    assert row.name == "Acme Ltd"


# [local-coder] ACC-U-08
def test_acc_u_08__inactive_account_switched_on(db, M, w1, u2, mk_account):
    """ACC-U-08 — an inactive account can be switched back on.
    Rules: update_account R7, R4"""
    a1 = mk_account(is_active=False)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(is_active=True),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_active is True
    assert row.is_deleted is False


# [local-coder] ACC-U-09
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_u_09__invalid_primary_email_rejected_by_schema():
    """ACC-U-09 — invalid primary email is rejected by the schema.
    Rules: update_account R4a [BUG-875]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(primary_email="call me")


# [local-coder] ACC-U-10
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_u_10__invalid_secondary_email_rejected_by_schema():
    """ACC-U-10 — invalid secondary email is rejected by the schema.
    Rules: update_account R4a [BUG-875]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(secondary_email="not-an-email")


# [local-coder] ACC-U-11
@pytest.mark.xfail(strict=True, reason="BUG-875: Account email fields accept any text")
def test_acc_u_11__sent_email_fields_are_trimmed_by_the_schema():
    """ACC-U-11 — sent email fields are trimmed by the schema.
    Rules: update_account R4a [BUG-875]"""
    obj = AccountUpdate(primary_email="  rahim@acme.test  ", secondary_email=" karim@acme.test ")

    # Then 1
    assert isinstance(obj, AccountUpdate)
    # Then 2
    assert obj.primary_email == "rahim@acme.test"
    # Then 3
    assert obj.secondary_email == "karim@acme.test"


# [local-coder] ACC-U-12
@pytest.mark.xfail(strict=True, reason="BUG-608: Optional payment details cannot be cleared")
def test_acc_u_12__explicit_null_clears_nullable_fields(db, M, w1, u2, mk_account):
    """ACC-U-12 — explicit null clears the nullable fields.
    Rules: update_account R5 [BUG-608]"""
    a1 = mk_account(**FILLED)

    result = M.update_account(
        db,
        account_id=a1.id,
        account_data=AccountUpdate(
            account_code=None,
            primary_contact_person=None,
            primary_email=None,
            primary_phone=None,
            secondary_contact_person=None,
            secondary_email=None,
            secondary_phone=None,
            address=None,
            city=None,
            country=None,
            postal_code=None,
            payment_preferences=None,
            bank_details=None,
        ),
        workspace_id=w1.id,
        user_id=u2.id,
    )

    # Then 1
    assert result.id == a1.id

    # Then 2
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.allow_invoices is True
    assert row.is_active is True

    # Then 3
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) is None


# [local-coder] ACC-U-13
@pytest.mark.xfail(strict=True, reason="BUG-608: Optional payment details cannot be cleared")
def test_acc_u_13__explicit_null_name_rejected():
    """ACC-U-13 — explicit null for `name` is rejected by the schema.
    Rules: update_account R5 [BUG-608]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(name=None)


# [local-coder] ACC-U-14
@pytest.mark.xfail(strict=True, reason="BUG-608: Optional payment details cannot be cleared")
def test_acc_u_14__explicit_null_for_allow_invoices_rejected():
    """ACC-U-14 — explicit null for `allow_invoices` is rejected by the schema.
    Rules: update_account R5 [BUG-608]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(allow_invoices=None)


# [local-coder] ACC-U-15
@pytest.mark.xfail(strict=True, reason="BUG-608: Optional payment details cannot be cleared")
def test_acc_u_15__explicit_null_for_is_active_rejected():
    """ACC-U-15 — explicit null for is_active is rejected by the schema.
    Rules: update_account R5 [BUG-608]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(is_active=None)


def test_acc_u_16__tag_ids_none_leaves_tags_untouched(db, M, w1, u1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-16 — tag_ids=None leaves the tags untouched.
    Rules: update_account R10, R5 (tag_ids: null)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    x1 = mk_link(a1, t1)
    before_x1 = snap(db, x1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(city="Dhaka", tag_ids=None),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert reread(db, a1).city == "Dhaka"
    # Then 3
    assert tags(db, a1) == [t1.id]
    # Then 4
    assert snap(db, x1) == before_x1
    row_x1 = link_row(db, a1, t1)
    assert row_x1.id == x1.id
    assert row_x1.assigned_at == T0
    assert row_x1.assigned_by == u1.id
    # Then 5
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-U-17
def test_acc_u_17__tag_ids_not_sent_leaves_tags_untouched(db, M, w1, u1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-17 — tag_ids not sent leaves the tags untouched.
    Rules: update_account R10"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    x1 = mk_link(a1, t1)

    before_x1 = snap(db, x1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Beta Co"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Beta Co"
    # Then 3
    assert tags(db, a1) == [t1.id]
    # Then 4
    assert snap(db, x1) == before_x1
    row_x1 = link_row(db, a1, t1)
    assert row_x1.id == x1.id
    assert row_x1.assigned_at == T0
    assert row_x1.assigned_by == u1.id
    # Then 5
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-U-18
@pytest.mark.xfail(strict=True, reason="BUG-860: Blank / whitespace-only account names accepted and names stored untrimmed")
def test_acc_u_18__a_sent_name_is_stored_trimmed(db, M, w1, u2, mk_account):
    """ACC-U-18 — a sent name is stored trimmed.
    Rules: update_account R6 [BUG-860], R17"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="  Beta  Co  "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Beta  Co"
    # Then 3
    logs = audit(db, a1)
    assert len(logs) == 1
    assert logs[0].description == "Account 'Beta  Co' updated"


# [local-coder] ACC-U-19
@pytest.mark.xfail(strict=True, reason="BUG-860: Blank / whitespace-only account names accepted and names stored untrimmed")
def test_acc_u_19__whitespace_only_name_rejected():
    """ACC-U-19 — whitespace-only name is rejected by the schema
    Rules: update_account R6 [BUG-860]"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(name="   ")


# [local-coder] ACC-U-20
def test_acc_u_20__empty_name_is_rejected_by_schema():
    """ACC-U-20 — empty name is rejected by the schema.
    Rules: update_account R6"""
    # Then 1
    with pytest.raises(ValidationError):
        AccountUpdate(name="")


# [local-coder] ACC-U-21
def test_acc_u_21__empty_request_changes_no_business_field(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-21 — an empty request changes no business field
    Rules: update_account R4, R10"""
    a1 = mk_account(**FILLED)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.allow_invoices is True
    assert row.is_active is True
    assert row.is_deleted is False
    # Then 3
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) == FILLED[f]
    # Then 4
    assert tags(db, a1) == [t1.id]
    # Then 5
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-U-22
@pytest.mark.xfail(strict=True, reason="BUG-869: updated_by stamped on no-op account updates")
def test_acc_u_22__empty_request_does_not_stamp_updated_by(db, M, w1, u2, mk_account):
    """ACC-U-22 — an empty request does not stamp updated_by.
    Rules: update_account R8 [BUG-869]"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.updated_by is None


# [local-coder] ACC-U-23
@pytest.mark.xfail(strict=True, reason="BUG-632: Update events logged when nothing changed")
def test_acc_u_23__empty_request_writes_no_audit(db, M, w1, u2, mk_account):
    """ACC-U-23 — an empty request writes no audit row.
    Rules: update_account R15 [BUG-632]"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-24
@pytest.mark.xfail(strict=True, reason="BUG-869: updated_by stamped on no-op account updates")
def test_acc_u_24__sending_current_values_does_not_stamp_updated_by(db, M, w1, u2, mk_account, u1):
    """ACC-U-24 — sending the current values does not stamp updated_by.
    Rules: update_account R8 [BUG-869]"""
    a1 = mk_account(city="Dhaka", updated_by=u1.id)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Acme Ltd", city="Dhaka"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.city == "Dhaka"
    # Then 3
    assert row.updated_by == u1.id


# [local-coder] ACC-U-25
@pytest.mark.xfail(strict=True, reason="BUG-632: Update events logged when nothing changed")
def test_acc_u_25__sending_current_values_writes_no_audit_row(db, M, w1, u2, mk_account):
    """ACC-U-25 — sending the current values writes no audit row.
    Rules: update_account R15 [BUG-632]"""
    a1 = mk_account(city="Dhaka")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Acme Ltd", city="Dhaka"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-26
@pytest.mark.xfail(strict=True, reason="BUG-869: updated_by stamped on no-op account updates; BUG-632: Update events logged when nothing changed")
def test_acc_u_26__sending_current_tag_set_is_not_a_change(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-26 — sending the current tag set is not a change.
    Rules: update_account R8 [BUG-869], R15 [BUG-632]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    row = reread(db, a1)
    assert row.updated_by is None
    # Then 4
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-27
def test_acc_u_27__changing_only_the_tag_set_stamps_the_account_and_writes_an_audit_row(db, M, w1, u2, mk_account, mk_tag):
    """ACC-U-27 — changing only the tag set stamps the account and writes an audit row.
    Rules: update_account R8 (tag set changed), R15 (tag set changed)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    row = reread(db, a1)
    assert row.updated_by == u2.id
    # Then 4
    logs = audit(db, a1)
    assert len(logs) == 1
    assert logs[0].action_type == "updated"
    assert logs[0].performed_by == u2.id


# [local-coder] ACC-U-29
def test_acc_u_29__empty_tag_list_removes_all_tags(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-29 — an empty tag list removes all tags.
    Rules: update_account R11, R12"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=4)
    mk_link(a1, t1)
    mk_link(a1, t2)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == []
    # Then 3
    assert reread(db, t1).usage_count == 0
    # Then 4
    assert reread(db, t2).usage_count == 3


# [local-coder] ACC-U-30
def test_acc_u_30__removing_a_tag_never_takes_its_usage_count_below_0(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-30 — removing a tag never takes its usage count below 0.
    Rules: update_account R12"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == []
    # Then 3
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-U-31
def test_acc_u_31__repeated_ids_in_tag_list_count_once(db, M, w1, u2, mk_account, mk_tag):
    """ACC-U-31 — repeated ids in the tag list count once.
    Rules: update_account R11; _assign_tags_to_account R5"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t2 = mk_tag("Client", "client", usage_count=0)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id, t1.id, t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    assert reread(db, t1).usage_count == 1
    # Then 4
    assert reread(db, t2).usage_count == 1


# [local-coder] ACC-U-32
def test_acc_u_32__keeping_one_tag_and_adding_another_gives_the_right_set_and_counts(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-32 — keeping one tag and adding another gives the right set and counts.
    Rules: update_account R11, R12, R13 (set and counts)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id, t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    assert reread(db, t1).usage_count == 1
    # Then 4
    assert reread(db, t2).usage_count == 1


# [local-coder] ACC-U-33
@pytest.mark.xfail(strict=True, reason="BUG-870: Updating an account's tags deletes and re-creates unchanged assignments")
def test_acc_u_33__a_tag_that_stays_keeps_its_assignment_row(db, M, w1, u2, mk_account, mk_tag, mk_link, u1):
    """ACC-U-33 — a tag that stays keeps its assignment row.
    Rules: update_account R13 [BUG-870]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    x1 = mk_link(a1, t1)
    x1_id = x1.id

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id, t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    x = link_row(db, a1, t1)
    assert x.id == x1_id
    assert x.assigned_at == T0
    assert x.assigned_by == u1.id


# [local-coder] ACC-U-34
@pytest.mark.xfail(strict=True, reason="BUG-870: Updating an account's tags deletes and re-creates unchanged assignments")
def test_acc_u_34__kept_tag_count_stays_zero(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-34 — a kept tag whose count is 0 stays at 0.
    Rules: update_account R13 [BUG-870]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-U-35
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_u_35__unknown_tag_id_rejects_the_whole_update(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-35 — unknown tag id rejects the whole update.
    Rules: update_account R14 [BUG-871]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="New Name", tag_ids=[MISSING]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.updated_by is None
    # Then 3
    assert tags(db, a1) == [t1.id]
    # Then 4
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-U-36
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_u_36__tag_of_another_workspace_rejects_the_whole_update(db, M, w1, w2, u2, mk_account, mk_tag, mk_link):
    """ACC-U-36 — tag of another workspace rejects the whole update.
    Rules: update_account R14 [BUG-871]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=0)
    mk_link(a1, t1)

    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t9.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t9.id} not found"
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1
    assert reread(db, t9).usage_count == 0
    # Then 4
    assert snap(db, a1) == before_a1


# [local-coder] ACC-U-37
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_u_37__one_unknown_id_rejects_list_valid_new_tags_not_attached(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-37 — one unknown id rejects the list, valid new tags are not attached.
    Rules: update_account R14 [BUG-871]; _assign_tags_to_account R7 [BUG-871]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    mk_link(a1, t1)

    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t1.id, t2.id, MISSING]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1
    assert reread(db, t2).usage_count == 0
    # Then 4
    assert snap(db, a1) == before_a1


# [local-coder] ACC-U-38
@pytest.mark.xfail(strict=True, reason="BUG-2987: Creating or updating an account accepts a deleted (inactive) tag that \"assign tag\" refuses")
def test_acc_u_38__new_inactive_tag_rejected(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-38 — a newly added inactive tag rejects the update.
    Rules: update_account R11a [BUG-2987]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)
    mk_link(a1, t1)

    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="New Name", tag_ids=[t1.id, t3.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1
    assert reread(db, t3).usage_count == 0
    # Then 4
    assert snap(db, a1) == before_a1
    assert reread(db, a1).name == "Acme Ltd"


# [local-coder] ACC-U-39
def test_acc_u_39__inactive_tag_already_assigned_stays_not_rechecked(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-39 — an inactive tag that is already assigned and stays is not rechecked.
    Rules: update_account R11a (tags staying are not rechecked), R11"""
    a1 = mk_account()
    t2 = mk_tag("Client", "client", usage_count=0)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    mk_link(a1, t3)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t3.id, t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t2.id, t3.id]
    # Then 3
    assert reread(db, t2).usage_count == 1
    # Then 4
    assert reread(db, t3).usage_count == 1


# [local-coder] ACC-U-40
def test_acc_u_40__a_real_change_writes_one_updated_audit_row(db, M, w1, u2, mk_account):
    """ACC-U-40 — a real change writes one "updated" audit row.
    Rules: update_account R15 (changed), R16 (keys written today), R17, R18 (not passed)"""
    a1 = mk_account(city="Dhaka", payment_preferences="Cash")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Beta Co", city="Chattogram", allow_invoices=False),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert count_rows(db, FinancialAuditLog) == 1
    logs = audit(db, a1)
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "account"
    assert log.entity_id == a1.id
    assert log.workspace_id == w1.id
    assert log.related_entity_type is None
    assert log.related_entity_id is None
    # Then 3
    assert log.action_type == "updated"
    assert log.description == "Account 'Beta Co' updated"
    assert log.performed_by == u2.id
    assert log.performed_at == NOW
    # Then 4
    assert log.ip_address is None
    assert log.user_agent is None
    # Then 5
    assert "before" in log.changes
    assert "after" in log.changes
    # Then 6
    assert log.changes["before"]["name"] == "Acme Ltd"
    assert log.changes["before"]["city"] == "Dhaka"
    assert log.changes["before"]["allow_invoices"] is True
    assert log.changes["before"]["payment_preferences"] == "Cash"
    assert log.changes["before"]["primary_contact_person"] is None
    assert log.changes["before"]["primary_email"] is None
    assert log.changes["before"]["address"] is None
    assert log.changes["before"]["country"] is None
    # Then 7
    assert log.changes["after"]["name"] == "Beta Co"
    assert log.changes["after"]["city"] == "Chattogram"
    assert log.changes["after"]["allow_invoices"] is False
    assert log.changes["after"]["payment_preferences"] == "Cash"
    assert log.changes["after"]["primary_contact_person"] is None
    assert log.changes["after"]["primary_email"] is None
    assert log.changes["after"]["address"] is None
    assert log.changes["after"]["country"] is None


# [local-coder] ACC-U-41
@pytest.mark.xfail(strict=True, reason="BUG-872: Account audit rows omit bank details and many other fields")
def test_acc_u_41__audit_row_holds_full_before_after_snapshot(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-41 — audit row holds the full before / after snapshot including tags.
    Rules: update_account R16 [BUG-872]"""
    a1 = mk_account(**FILLED)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(bank_details="DBBL 999-888", is_active=False, tag_ids=[t2.id, t1.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    logs = audit(db, a1)
    assert len(logs) == 1
    # Then 3
    assert logs[0].changes == {"before": SNAP(**FILLED, tag_ids=[t1.id]), "after": SNAP(**{**FILLED, "bank_details": "DBBL 999-888"}, is_active=False, tag_ids=[t1.id, t2.id])}


# [local-coder] ACC-U-42
@pytest.mark.xfail(strict=True, reason="BUG-140: Financial audit rows never record IP address or user agent")
def test_acc_u_42__client_ip_and_user_agent_written_to_audit(db, M, w1, u2, mk_account):
    """ACC-U-42 — client IP and user agent are written to the audit row.
    Rules: update_account R18 [BUG-140]"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Beta Co"),
                              workspace_id=w1.id, user_id=u2.id, ip_address="203.0.113.7", user_agent="pytest-agent/1.0")

    # Then 1
    assert result.id == a1.id
    # Then 2
    logs = audit(db, a1)
    assert len(logs) == 1
    # Then 3
    assert logs[0].ip_address == "203.0.113.7"
    assert logs[0].user_agent == "pytest-agent/1.0"


# [local-coder] ACC-U-43
def test_acc_u_43__rename_to_another_live_accounts_name_is_allowed(db, M, w1, u2, mk_account):
    """ACC-U-43 — renaming to another live account's name is allowed.
    Rules: update_account R20"""
    a1 = mk_account()
    mk_account(name="Beta Co")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="Beta Co"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.name == "Beta Co"
    # Then 3
    assert count_rows(db, Account, workspace_id=w1.id, name="Beta Co") == 2


# [local-coder] ACC-U-44
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_44__taking_another_live_accounts_code_is_rejected(db, M, w1, u2, mk_account):
    """ACC-U-44 — taking another live account's code is rejected.
    Rules: update_account R20a [BUG-874]; Errors row 6"""
    a1 = mk_account()
    mk_account(name="Beta Co", account_code="SUP-001")
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="SUP-001"),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account code 'SUP-001' already exists"
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.account_code is None
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 2
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-45
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_45__code_conflict_check_is_trimmed_and_case_insensitive(db, M, w1, u2, mk_account):
    """ACC-U-45 — the code conflict check is trimmed and case-insensitive.
    Rules: update_account R20a [BUG-874]"""
    a1 = mk_account()
    mk_account(name="Beta Co", account_code="SUP-001")
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code=" sup-001 "),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account code 'sup-001' already exists"
    # Then 2
    assert snap(db, a1) == before_a1
    assert reread(db, a1).account_code is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 2
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-U-46
def test_acc_u_46__an_account_keeping_its_own_code_is_no_conflict(db, M, w1, u2, mk_account):
    """ACC-U-46 — an account keeping its own code is no conflict.
    Rules: update_account R20a (own code)"""
    a1 = mk_account(account_code="SUP-001")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="SUP-001", city="Dhaka"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code == "SUP-001"
    assert row.city == "Dhaka"


# [local-coder] ACC-U-47
def test_acc_u_47__soft_deleted_account_code_taken(db, M, w1, u2, mk_account):
    """ACC-U-47 — the code of a soft-deleted account can be taken.
    Rules: update_account R20a (soft-deleted do not count)"""
    a1 = mk_account()
    a2 = mk_account(name="Beta Co", deleted=True, account_code="SUP-001")
    before_a2 = snap(db, a2)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="SUP-001"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code == "SUP-001"
    # Then 3
    assert snap(db, a2) == before_a2


# [local-coder] ACC-U-48
def test_acc_u_48__same_code_another_workspace_no_conflict(db, M, w1, w2, u2, mk_account):
    """ACC-U-48 — the same code in another workspace is no conflict
    Rules: update_account R20a (per workspace)"""
    a1 = mk_account()
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id, account_code="SUP-001")
    before_a9 = snap(db, a9)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="SUP-001"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code == "SUP-001"
    # Then 3
    assert snap(db, a9) == before_a9


# [local-coder] ACC-U-49
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_49__code_conflict_leaves_other_fields_unchanged(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-49 — a code conflict leaves the other sent fields and the tags unchanged.
    Rules: update_account R20a [BUG-874]; Errors row 6"""
    a1 = mk_account()
    mk_account(name="Beta Co", account_code="SUP-001")
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    x1 = mk_link(a1, t1)

    before_a1 = snap(db, a1)
    before_x1 = snap(db, x1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=a1.id, account_data=AccountUpdate(name="New Name", account_code="SUP-001", tag_ids=[t2.id]),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account code 'SUP-001' already exists"
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.name == "Acme Ltd"
    assert row.account_code is None
    assert row.updated_by is None
    # Then 3
    assert tags(db, a1) == [t1.id]
    # Then 4
    assert snap(db, x1) == before_x1
    # Then 5
    assert written(db) == before
    assert count_rows(db, Account) == 2
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1
    assert reread(db, t2).usage_count == 0


# [local-coder] ACC-U-50
def test_acc_u_50__resend_own_code_with_padding_is_no_conflict(db, M, w1, u2, mk_account):
    """ACC-U-50 — re-sending the own code in another case and with padding is no conflict.
    Rules: update_account R20a (own code, other case / padding)"""
    a1 = mk_account(account_code="SUP-001")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code=" sup-001 ", city="Dhaka"),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.city == "Dhaka"
    # Then 3
    assert row.account_code.strip() == "sup-001"


# [local-coder] ACC-U-51
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_51__sent_account_code_stored_trimmed(db, M, w1, u2, mk_account):
    """ACC-U-51 — a sent account code is stored trimmed, case kept.
    Rules: update_account R20b [BUG-874]"""
    a1 = mk_account()

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="  Sup-001 "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code == "Sup-001"


# [local-coder] ACC-U-52
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_52__empty_account_code_clears_code(db, M, w1, u2, mk_account):
    """ACC-U-52 — sending an empty account code clears the code.
    Rules: update_account R20b [BUG-874]"""
    a1 = mk_account(account_code="SUP-001")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code=""),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code is None


# [local-coder] ACC-U-53
@pytest.mark.xfail(strict=True, reason="BUG-874: Account code is not unique per workspace")
def test_acc_u_53__whitespace_only_account_code_clears_code(db, M, w1, u2, mk_account):
    """ACC-U-53 — sending a whitespace-only account code clears the code.
    Rules: update_account R20b [BUG-874]"""
    a1 = mk_account(account_code="SUP-001")

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code="   "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.account_code is None


# [local-coder] ACC-U-54
def test_acc_u_54__blank_sent_code_never_conflicts_with_other_blank_codes(db, M, w1, u2, mk_account):
    """ACC-U-54 — a blank sent code never conflicts with other blank codes.
    Rules: update_account R20b (a blank code never conflicts), R20a (non-empty boundary)"""
    a1 = mk_account(account_code="SUP-001")
    a2 = mk_account(name="Beta Co", account_code="")
    a3 = mk_account(name="Gamma Inc", account_code="   ")

    before_a2 = snap(db, a2)
    before_a3 = snap(db, a3)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(account_code=" "),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert (row.account_code or "").strip() == ""
    # Then 3
    assert snap(db, a2) == before_a2
    assert snap(db, a3) == before_a3


# [claude] ACC-U-55
@pytest.mark.xfail(strict=True, reason="BUG-1487: Saving an account's tags erases its links to deleted tags")
def test_acc_u_55__link_to_deleted_tag_survives_tag_save(db, M, w1, u1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-55 — a link to a deleted tag survives a tag save.
    Rules: update_account R13a [BUG-1487]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    mk_link(a1, t1)
    x3 = mk_link(a1, t3)
    x3_id = x3.id

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t2.id, t3.id]
    # Then 3
    x = link_row(db, a1, t3)
    assert x.id == x3_id
    assert x.assigned_at == T0
    assert x.assigned_by == u1.id
    # Then 4
    assert reread(db, t3).usage_count == 1


# [claude] ACC-U-56
def test_acc_u_56__live_tag_link_not_in_list_removed_next_to_deleted_tag_link(db, M, w1, u2, mk_account, mk_tag,
                                                                                mk_link):
    """ACC-U-56 — a link to a live tag not in the list is removed, next to a deleted-tag link.
    Rules: update_account R11, R12, R13a (links to active tags are still replaced)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t3)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t2.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert t1.id not in tags(db, a1)
    assert t2.id in tags(db, a1)
    # Then 3
    assert reread(db, t1).usage_count == 0
    # Then 4
    assert reread(db, t2).usage_count == 1


# [local-coder] ACC-G-03
def test_acc_g_03__account_of_another_workspace_returns_none(db, M, w1, w2, mk_account):
    """ACC-G-03 — account of another workspace returns None
    Rules: get_account R3"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)

    result = M.get_account(db, account_id=a9.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] ACC-G-04
@pytest.mark.xfail(strict=True, reason="BUG-862: get_account returns soft-deleted accounts")
def test_acc_g_04__soft_deleted_account_is_hidden_by_default(db, M, w1, mk_account):
    """ACC-G-04 — soft-deleted account is hidden by default.
    Rules: get_account R4 [BUG-862]"""
    a1 = mk_account(deleted=True)

    result = M.get_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [local-coder] ACC-G-05
@pytest.mark.xfail(strict=True, reason="BUG-862: get_account returns soft-deleted accounts")
def test_acc_g_05__include_deleted_returns_soft_deleted_account(db, M, w1, mk_account):
    """ACC-G-05 — include_deleted=True returns a soft-deleted account.
    Rules: get_account R4 [BUG-862]"""
    a1 = mk_account(deleted=True)

    result = M.get_account(db, account_id=a1.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is not None
    assert result.id == a1.id
    assert result.is_deleted is True


# [local-coder] ACC-G-06
@pytest.mark.xfail(strict=True, reason="BUG-862: get_account returns soft-deleted accounts")
def test_acc_g_06__include_deleted_true_still_hides_other_workspaces(db, M, w1, w2, mk_account):
    """ACC-G-06 — include_deleted=True still hides other workspaces
    Rules: get_account R4 [BUG-862], R3"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id, deleted=True)

    result = M.get_account(db, account_id=a9.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result is None


# [local-coder] ACC-G-07
def test_acc_g_07__inactive_not_deleted_account_returned(db, M, w1, mk_account):
    """ACC-G-07 — an inactive, not deleted account is returned.
    Rules: get_account R5; update_account R7"""
    a1 = mk_account(is_active=False, is_deleted=False)

    result = M.get_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result is not None
    assert result.id == a1.id
    assert result.is_active is False


# [local-coder] ACC-S-01
def test_acc_s_01__default_search_returns_only_active_live_accounts(db, M, w1, w2, mk_account):
    """ACC-S-01 — default search returns only active, live accounts of the workspace.
    Rules: search_accounts R1; update_account R7"""
    a1 = mk_account(name="Alpha")
    mk_account(name="Bravo", is_active=False)
    mk_account(name="Charlie", deleted=True)
    mk_account(name="Delta", workspace_id=w2.id)

    result = M.search_accounts(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    assert all(isinstance(a, Account) for a in result)
    assert {a.name for a in result} == {"Alpha"}
    assert len(result) == 1
    # Then 2
    assert result[0].id == a1.id


@pytest.mark.xfail(strict=True, reason="BUG-878: Deactivated accounts cannot be listed")
def test_acc_s_02__include_inactive_adds_inactive_accounts(db, M, w1, w2, mk_account):
    """ACC-S-02 — include_inactive=True adds inactive accounts, never deleted or foreign ones.
    Rules: search_accounts R1a [BUG-878]"""
    mk_account(name="Alpha")
    mk_account(name="Bravo", is_active=False)
    mk_account(name="Charlie", deleted=True)
    mk_account(name="Delta", workspace_id=w2.id, is_active=False)

    # Fails today here: search_accounts has no include_inactive parameter (TypeError).
    result = M.search_accounts(db, workspace_id=w1.id, include_inactive=True)

    # Then 1
    assert {a.name for a in result} == {"Alpha", "Bravo"}
    assert len(result) == 2


# [local-coder] ACC-S-03
def test_acc_s_03__workspace_without_accounts_returns_empty_list(db, M, w1, w2, mk_account):
    """ACC-S-03 — a workspace without accounts gives an empty list.
    Rules: search_accounts R14"""
    mk_account(name="Zeta Corp", workspace_id=w2.id)

    result = M.search_accounts(db, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ACC-S-04
def test_acc_s_04__empty_name_text_means_no_name_filter(db, M, w1, mk_account):
    """ACC-S-04 — empty name text means no name filter.
    Rules: search_accounts R2"""
    mk_account()
    mk_account(name="Beta Co")

    result = M.search_accounts(db, workspace_id=w1.id, name="")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd", "Beta Co"}
    assert len(result) == 2


# [local-coder] ACC-S-05
@pytest.mark.xfail(strict=True, reason="BUG-637: Whitespace-only invoice-number search returns almost nothing")
def test_acc_s_05__whitespace_only_name_means_no_filter(db, M, w1, mk_account):
    """ACC-S-05 — whitespace-only name text means no name filter.
    Rules: search_accounts R2, R5 [BUG-637]"""
    mk_account()
    mk_account(name="Beta Co")

    result = M.search_accounts(db, workspace_id=w1.id, name="   ")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd", "Beta Co"}
    assert len(result) == 2


# [local-coder] ACC-S-06
def test_acc_s_06__name_text_matches_anywhere_in_the_name_ignoring_case(db, M, w1, mk_account):
    """ACC-S-06 — name text matches anywhere in the name, ignoring case.
    Rules: search_accounts R3"""
    mk_account(name="Acme Ltd")
    mk_account(name="Big ACME Traders")
    mk_account(name="Beta Co")

    result = M.search_accounts(db, workspace_id=w1.id, name="acme")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd", "Big ACME Traders"}
    assert len(result) == 2


# [local-coder] ACC-S-07
def test_acc_s_07__name_text_that_matches_nothing_gives_an_empty_list(db, M, w1, mk_account):
    """ACC-S-07 — name text that matches nothing gives an empty list.
    Rules: search_accounts R3, R14"""
    mk_account()
    mk_account(name="Beta Co")

    result = M.search_accounts(db, workspace_id=w1.id, name="zzz")

    # Then 1
    assert result == []


# [local-coder] ACC-S-08
@pytest.mark.xfail(strict=True, reason="BUG-868: % and _ in account name search act as wildcards")
def test_acc_s_08__percent_in_name_matches_literal(db, M, w1, mk_account):
    """ACC-S-08 — % in the name text matches literally.
    Rules: search_accounts R4 [BUG-868]"""
    mk_account(name="100% Cotton")
    mk_account()

    result = M.search_accounts(db, workspace_id=w1.id, name="%")

    # Then 1
    assert {a.name for a in result} == {"100% Cotton"}
    assert len(result) == 1


# [local-coder] ACC-S-09
@pytest.mark.xfail(strict=True, reason="BUG-868: % and _ in account name search act as wildcards")
def test_acc_s_09__underscore_in_name_matches_literal(db, M, w1, mk_account):
    """ACC-S-09 — `_` in the name text matches literally.
    Rules: search_accounts R4 [BUG-868]"""
    mk_account(name="Acme_Ltd")
    mk_account(name="Acme Ltd")

    result = M.search_accounts(db, workspace_id=w1.id, name="_")

    # Then 1
    assert {a.name for a in result} == {"Acme_Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-10
@pytest.mark.xfail(strict=True, reason="BUG-868: % and _ in account name search act as wildcards")
def test_acc_s_10__backslash_in_name_matches_literal(db, M, w1, mk_account):
    """ACC-S-10 — a backslash in the name text matches literally.
    Rules: search_accounts R4 [BUG-868]"""
    mk_account(name="Acme\\Ltd")
    mk_account(name="Acme Ltd")

    result = M.search_accounts(db, workspace_id=w1.id, name="\\")

    # Then 1
    assert len(result) == 1
    assert result[0].name == "Acme\\Ltd"


# [local-coder] ACC-S-11
@pytest.mark.xfail(strict=True, reason="BUG-637: Whitespace-only invoice-number search returns almost nothing")
def test_acc_s_11__name_text_is_trimmed_before_matching(db, M, w1, mk_account):
    """ACC-S-11 — the name text is trimmed before matching.
    Rules: search_accounts R5 [BUG-637]"""
    mk_account()
    mk_account(name="Beta Co")

    result = M.search_accounts(db, workspace_id=w1.id, name=" acme ")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-12
def test_acc_s_12__empty_tag_code_means_no_tag_filter(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-12 — empty tag code means no tag filter.
    Rules: search_accounts R6"""
    a1 = mk_account()
    mk_account(name="Beta Co")
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd", "Beta Co"}
    assert len(result) == 2


# [local-coder] ACC-S-13
def test_acc_s_13__tag_code_returns_only_accounts_carrying_that_tag_in_this_workspace(db, M, w1, w2, mk_account, mk_tag, mk_link):
    """ACC-S-13 — tag code returns only accounts carrying that tag in this workspace.
    Rules: search_accounts R7, R1"""
    a1 = mk_account(name="Acme Ltd")
    a2 = mk_account(name="Beta Co")
    mk_account(name="Gamma Inc")
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=1)
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)
    mk_link(a1, t1)
    mk_link(a2, t2)
    mk_link(a9, t9)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-14
def test_acc_s_14__an_account_matching_through_two_assignments_appears_once(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-14 — an account matching through two assignments appears once.
    Rules: search_accounts R7"""
    a1 = mk_account(name="Acme Ltd")
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t5 = mk_tag("Supplier B", "supplier", usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t5)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id == a1.id


# [local-coder] ACC-S-15
def test_acc_s_15__an_assignment_recorded_under_another_workspace_does_not_match(db, M, w1, w2, mk_account, mk_tag, mk_link):
    """ACC-S-15 — an assignment recorded under another workspace does not match.
    Rules: search_accounts R7"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1, workspace_id=w2.id)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="supplier")

    # Then 1
    assert result == []


# [local-coder] ACC-S-16
@pytest.mark.xfail(strict=True, reason="BUG-861: Account tag-code filter is exact and case-sensitive")
def test_acc_s_16__tag_code_is_compared_case_insensitively(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-16 — tag code is compared case-insensitively
    Rules: search_accounts R8 [BUG-861]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="Supplier")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-17
@pytest.mark.xfail(strict=True, reason="BUG-861: Account tag-code filter is exact and case-sensitive")
def test_acc_s_17__tag_code_is_trimmed_before_comparing(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-17 — tag code is trimmed before comparing.
    Rules: search_accounts R8 [BUG-861]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code=" supplier ")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-18
@pytest.mark.xfail(strict=True, reason="BUG-864: Filtering accounts by a deleted tag still returns them")
def test_acc_s_18__inactive_tag_does_not_match_filter(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-18 — an inactive tag does not match the tag filter.
    Rules: search_accounts R9 [BUG-864]"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    mk_link(a1, t3)

    result = M.search_accounts(db, workspace_id=w1.id, tag_code="legacy")

    # Then 1
    assert result == []


# [local-coder] ACC-S-19
def test_acc_s_19__name_and_tag_code_must_both_match(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-S-19 — name and tag code must both match.
    Rules: search_accounts R10"""
    a1 = mk_account()
    b = mk_account(name="Acme Traders")
    a2 = mk_account(name="Beta Co")
    t1 = mk_tag("Supplier", "supplier", usage_count=2)
    t2 = mk_tag("Client", "client", usage_count=1)
    mk_link(a1, t1)
    mk_link(b, t2)
    mk_link(a2, t1)

    result = M.search_accounts(db, workspace_id=w1.id, name="acme", tag_code="supplier")

    # Then 1
    assert {a.name for a in result} == {"Acme Ltd"}
    assert len(result) == 1


# [local-coder] ACC-S-20
@pytest.mark.xfail(strict=True, reason="BUG-866: Account search has no sort order")
def test_acc_s_20__results_ordered_by_name_ignore_case_then_id(db, M, w1, mk_account):
    """ACC-S-20 — results are ordered by name ignoring case, then id.
    Rules: search_accounts R11 [BUG-866]"""
    mk_account(name="delta")
    mk_account(name="charlie")
    mk_account(name="Bravo")
    L = mk_account(name="alpha")
    H = mk_account(name="ALPHA")
    mk_account(name="Echo")

    result = M.search_accounts(db, workspace_id=w1.id)

    # Then 1
    assert [a.name for a in result] == ["alpha", "ALPHA", "Bravo", "charlie", "delta", "Echo"]
    # Then 2
    assert result[0].id == L.id
    assert result[1].id == H.id


# [local-coder] ACC-S-21
def test_acc_s_21__limit_caps_the_page_size(db, M, w1, mk_account):
    """ACC-S-21 — limit caps the page size.
    Rules: search_accounts R12"""
    mk_account(name="Alpha")
    mk_account(name="Bravo")
    mk_account(name="Charlie")
    mk_account(name="Delta")
    mk_account(name="Echo")

    result = M.search_accounts(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    for a in result:
        assert a.name in {"Alpha", "Bravo", "Charlie", "Delta", "Echo"}
    assert len({a.name for a in result}) == 2


# [local-coder] ACC-S-22
def test_acc_s_22__last_page_short_only_no_more_matches(db, M, w1, mk_account):
    """ACC-S-22 — the last page is short only because no more matches exist.
    Rules: search_accounts R12"""
    for n in ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]:
        mk_account(name=n)

    result = M.search_accounts(db, workspace_id=w1.id, skip=4, limit=2)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].name in {"Alpha", "Bravo", "Charlie", "Delta", "Echo"}


# [local-coder] ACC-S-23
def test_acc_s_23__skip_beyond_the_matches_gives_an_empty_list(db, M, w1, mk_account):
    """ACC-S-23 — skip beyond the matches gives an empty list.
    Rules: search_accounts R12, R14"""
    for n in ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]:
        mk_account(name=n)

    result = M.search_accounts(db, workspace_id=w1.id, skip=5, limit=2)

    # Then 1
    assert result == []


# [local-coder] ACC-S-24
def test_acc_s_24__default_page_size_is_100(db, M, w1, mk_account):
    """ACC-S-24 — the default page size is 100.
    Rules: search_accounts R12"""
    for i in range(1, 102):
        mk_account(name=f"Account {i:03d}")

    result = M.search_accounts(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert len({a.id for a in result}) == 100


# [local-coder] ACC-S-25
def test_acc_s_25__filters_are_applied_before_paging(db, M, w1, mk_account):
    """ACC-S-25 — filters are applied before paging.
    Rules: search_accounts R12, R1, R3"""
    mk_account(name="Acme X1", is_active=False)
    mk_account(name="Acme X2", deleted=True)
    mk_account(name="Zed One")
    mk_account(name="Zed Two")
    mk_account(name="Acme A")
    mk_account(name="Acme B")

    result = M.search_accounts(db, workspace_id=w1.id, name="acme", skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert {a.name for a in result} == {"Acme A", "Acme B"}


# [local-coder] ACC-S-26
@pytest.mark.xfail(strict=True, reason="BUG-866: Account search has no sort order")
def test_acc_s_26__a_page_is_cut_from_the_ordered_result(db, M, w1, mk_account):
    """ACC-S-26 — a page is cut from the ordered result.
    Rules: search_accounts R11 [BUG-866], R12"""
    mk_account(name="Echo")
    mk_account(name="Bravo")
    mk_account(name="Golf")
    mk_account(name="Alpha")
    mk_account(name="Delta")
    mk_account(name="Foxtrot")
    mk_account(name="Charlie")

    result = M.search_accounts(db, workspace_id=w1.id, skip=1, limit=5)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert [a.name for a in result] == ["Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]


# [local-coder] ACC-D-01
def test_acc_d_01__delete_soft_deletes_the_account_and_keeps_everything_else(db, M, w1, u1, u2, mk_account):
    """ACC-D-01 — delete soft-deletes the account and keeps everything else.
    Rules: delete_account R4, R9, R7b (no invoices)"""
    a1 = mk_account(**FILLED)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 3
    assert row.updated_by is None
    assert row.created_by == u1.id
    assert row.workspace_id == w1.id
    # Then 4
    assert row.name == "Acme Ltd"
    assert row.allow_invoices is True
    for f in OPTIONAL_FIELDS:
        assert getattr(row, f) == FILLED[f]
    # Then 5
    assert count_rows(db, Account) == 1


# [local-coder] ACC-D-02
def test_acc_d_02__unknown_account_id_rejected(db, M, w1, u2, mk_account):
    """ACC-D-02 — unknown account id is rejected.
    Rules: delete_account R1; Errors row 1"""
    a1 = mk_account()
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert snap(db, a1) == before_a1
    assert reread(db, a1).is_deleted is False
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-D-03
def test_acc_d_03__account_of_another_workspace_is_rejected_and_not_deleted(db, M, w1, w2, u2, mk_account):
    """ACC-D-03 — account of another workspace is rejected and not deleted.
    Rules: delete_account R2 (error raised, nothing written)"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    before_a9 = snap(db, a9)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError):
        M.delete_account(db, account_id=a9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert snap(db, a9) == before_a9
    row = reread(db, a9)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-D-04
@pytest.mark.xfail(strict=True, reason="BUG-440: Non-members can enumerate which workspace ids exist")
def test_acc_d_04__account_of_another_workspace_gets_plain_not_found(db, M, w1, w2, u2, mk_account):
    """ACC-D-04 — account of another workspace gets the plain "not found" message.
    Rules: delete_account R2 [BUG-440]"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    before_a9 = snap(db, a9)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a9.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a9.id} not found"
    # Then 2
    assert snap(db, a9) == before_a9


# [local-coder] ACC-D-05
def test_acc_d_05__already_deleted_account_rejected(db, M, w1, u1, u2, mk_account):
    """ACC-D-05 — an already deleted account is rejected.
    Rules: delete_account R3; Errors row 3"""
    a1 = mk_account(deleted=True)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a1.id} is already deleted"

    # Then 2
    row = reread(db, a1)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    assert row.is_deleted is True

    # Then 3
    assert snap(db, a1) == before_a1

    # Then 4
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-D-06
def test_acc_d_06__delete_writes_one_deleted_audit_row(db, M, w1, u2, mk_account):
    """ACC-D-06 — delete writes one "deleted" audit row.
    Rules: delete_account R5 (keys written today), R10 (not passed)"""
    a1 = mk_account(primary_contact_person="Rahim", primary_email="rahim@acme.test")

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert count_rows(db, FinancialAuditLog) == 1
    logs = audit(db, a1)
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "account"
    assert log.entity_id == a1.id
    assert log.workspace_id == w1.id
    assert log.related_entity_type is None
    assert log.related_entity_id is None
    # Then 3
    assert log.action_type == "deleted"
    assert log.description == "Account 'Acme Ltd' deleted"
    assert log.performed_by == u2.id
    assert log.performed_at == NOW
    # Then 4
    assert log.ip_address is None
    assert log.user_agent is None
    # Then 5
    assert "before" in log.changes
    assert "after" not in log.changes
    # Then 6
    assert log.changes["before"]["name"] == "Acme Ltd"
    assert log.changes["before"]["primary_contact_person"] == "Rahim"
    assert log.changes["before"]["primary_email"] == "rahim@acme.test"


# [local-coder] ACC-D-07
@pytest.mark.xfail(strict=True, reason="BUG-872: Account audit rows omit bank details and many other fields")
def test_acc_d_07__audit_row_holds_full_before_snapshot(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-D-07 — audit row holds the full "before" snapshot including tags.
    Rules: delete_account R5 [BUG-872]"""
    a1 = mk_account(**FILLED)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    logs = audit(db, a1)
    assert len(logs) == 1
    # Then 3
    assert logs[0].changes == {"before": SNAP(**FILLED, tag_ids=[t1.id])}


# [local-coder] ACC-D-08
def test_acc_d_08__the_accounts_tag_assignment_rows_are_kept(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-D-08 — the account's tag assignment rows are kept.
    Rules: delete_account R6 (assignments stay)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    t2 = mk_tag("Client", "client", usage_count=1)
    x1 = mk_link(a1, t1)
    x2 = mk_link(a1, t2)
    before_x1 = snap(db, x1)
    before_x2 = snap(db, x2)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    assert snap(db, x1) == before_x1
    assert snap(db, x2) == before_x2


# [local-coder] ACC-D-09
@pytest.mark.xfail(strict=True, reason="BUG-877: Deleting an account leaves tag usage_count unchanged")
def test_acc_d_09__delete_lowers_the_usage_count_of_each_assigned_tag(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-D-09 — delete lowers the usage count of each assigned tag.
    Rules: delete_account R6 [BUG-877]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    t2 = mk_tag("Client", "client", usage_count=1)
    t4 = mk_tag("Utility", "utility", usage_count=5)
    mk_link(a1, t1)
    mk_link(a1, t2)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert reread(db, t4).usage_count == 5
    # Then 3
    assert reread(db, t1).usage_count == 2
    # Then 4
    assert reread(db, t2).usage_count == 0


# [local-coder] ACC-D-10
def test_acc_d_10__delete_never_takes_a_usage_count_below_0(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-D-10 — delete never takes a usage count below 0.
    Rules: delete_account R6 (floor 0)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    mk_link(a1, t1)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_deleted is True
    # Then 3
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-D-11
def test_acc_d_11__inactive_account_can_be_deleted(db, M, w1, u2, mk_account):
    """ACC-D-11 — an inactive account can be deleted.
    Rules: delete_account R8"""
    a1 = mk_account(is_active=False)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 3
    logs = audit(db, a1)
    assert len(logs) == 1
    assert logs[0].action_type == "deleted"


# [local-coder] ACC-D-12
@pytest.mark.xfail(strict=True, reason="BUG-140: Financial audit rows never record IP address or user agent")
def test_acc_d_12__client_ip_and_user_agent_are_written_to_the_audit_row(db, M, w1, u2, mk_account):
    """ACC-D-12 — client IP and user agent are written to the audit row.
    Rules: delete_account R10 [BUG-140]"""
    a1 = mk_account()

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id,
                              ip_address="203.0.113.7", user_agent="pytest-agent/1.0")

    # Then 1
    assert result.id == a1.id
    # Then 2
    logs = audit(db, a1)
    assert len(logs) == 1
    # Then 3
    assert logs[0].ip_address == "203.0.113.7"
    assert logs[0].user_agent == "pytest-agent/1.0"


# [local-coder] ACC-D-13
@pytest.mark.xfail(strict=True, reason="BUG-876: Account with open invoices can be deleted")
def test_acc_d_13__an_account_with_a_draft_invoice_cannot_be_deleted(db, M, w1, u2, mk_account, mk_tag, mk_link, mk_invoice):
    """ACC-D-13 — an account with a draft invoice cannot be deleted.
    Rules: delete_account R7 [BUG-876], R7a [BUG-876]; Errors row 4"""
    a1 = mk_account(updated_by=None)
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    mk_link(a1, t1)
    i1 = mk_invoice(a1, "draft")

    before_a1 = snap(db, a1)
    before_i1 = snap(db, i1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == OPEN_INVOICES
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 3
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert count_rows(db, AccountInvoice) == 1


# [local-coder] ACC-D-14
@pytest.mark.xfail(strict=True, reason="BUG-876: Account with open invoices can be deleted")
def test_acc_d_14__account_with_receivable_invoice_cannot_be_deleted(db, M, w1, u2, mk_account, mk_tag, mk_link, mk_invoice):
    """ACC-D-14 — an account with a confirmed, unpaid receivable invoice cannot be deleted.
    Rules: delete_account R7 [BUG-876], R7a [BUG-876] (unpaid; both invoice types count)"""
    a1 = mk_account(updated_by=None)
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    mk_link(a1, t1)
    i1 = mk_invoice(a1, "unpaid", invoice_type="receivable")

    before_a1 = snap(db, a1)
    before_i1 = snap(db, i1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == OPEN_INVOICES
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 3
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert count_rows(db, AccountInvoice) == 1


# [local-coder] ACC-D-15
@pytest.mark.xfail(strict=True, reason="BUG-876: Account with open invoices can be deleted")
def test_acc_d_15__account_with_partial_invoice_cannot_be_deleted(db, M, w1, u2, mk_account, mk_tag, mk_link, mk_invoice):
    """ACC-D-15 — an account with a partially paid invoice cannot be deleted.
    Rules: delete_account R7 [BUG-876], R7a [BUG-876] (partial: paid_amount < invoice_amount)"""
    a1 = mk_account(updated_by=None)
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    mk_link(a1, t1)
    i1 = mk_invoice(a1, "partial")

    before_a1 = snap(db, a1)
    before_i1 = snap(db, i1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == OPEN_INVOICES
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 3
    # Then 4
    assert snap(db, i1) == before_i1
    inv = reread(db, i1)
    assert inv.paid_amount == Decimal("400.00")
    assert inv.payment_status == "partial"
    # Then 5
    assert count_rows(db, AccountInvoice) == 1


# [local-coder] ACC-D-16
@pytest.mark.xfail(strict=True, reason="BUG-876: Account with open invoices can be deleted")
def test_acc_d_16__one_open_invoice_is_enough_among_settled_and_voided(db, M, w1, u2, mk_account, mk_tag, mk_link, mk_invoice):
    """ACC-D-16 — one open invoice is enough among settled and voided ones.
    Rules: delete_account R7 [BUG-876], R7a [BUG-876]"""
    a1 = mk_account(updated_by=None)
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    mk_link(a1, t1)
    i1 = mk_invoice(a1, "paid")
    i2 = mk_invoice(a1, "voided")
    i3 = mk_invoice(a1, "draft", invoice_type="receivable")

    before_a1 = snap(db, a1)
    before_i1 = snap(db, i1)
    before_i2 = snap(db, i2)
    before_i3 = snap(db, i3)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == OPEN_INVOICES
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.is_deleted is False
    assert row.is_active is True
    assert row.deleted_at is None
    assert row.deleted_by is None
    assert row.updated_by is None
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 3
    # Then 4
    assert snap(db, i1) == before_i1
    assert snap(db, i2) == before_i2
    assert snap(db, i3) == before_i3
    # Then 5
    assert count_rows(db, AccountInvoice) == 3


# [local-coder] ACC-D-17
def test_acc_d_17__paid_invoice_allows_delete(db, M, w1, u2, mk_account, mk_invoice):
    """ACC-D-17 — an account whose only invoice is fully paid can be deleted.
    Rules: delete_account R7b, R7a (other side: paid_amount == invoice_amount), R4"""
    a1 = mk_account()
    i1 = mk_invoice(a1, "paid")
    before_i1 = snap(db, i1)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 3
    logs = audit(db, a1)
    assert len(logs) == 1
    assert logs[0].action_type == "deleted"
    # Then 4
    assert snap(db, i1) == before_i1
    inv = reread(db, i1)
    assert inv.invoice_status == "confirmed"
    assert inv.payment_status == "paid"
    # Then 5
    assert count_rows(db, AccountInvoice) == 1


# [local-coder] ACC-D-18
def test_acc_d_18__voided_invoice_allows_delete(db, M, w1, u2, mk_account, mk_invoice):
    """ACC-D-18 — an account whose only invoice is voided can be deleted.
    Rules: delete_account R7b, R7a (other side: voided, although payment_status is "unpaid"), R4"""
    a1 = mk_account()
    i1 = mk_invoice(a1, "voided")
    before_i1 = snap(db, i1)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.is_deleted is True
    assert row.is_active is False
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 3
    logs = audit(db, a1)
    assert len(logs) == 1
    assert logs[0].action_type == "deleted"
    # Then 4
    assert snap(db, i1) == before_i1
    inv = reread(db, i1)
    assert inv.invoice_status == "voided"
    assert inv.payment_status == "unpaid"
    # Then 5
    assert count_rows(db, AccountInvoice) == 1


# [local-coder] ACC-D-19
def test_acc_d_19__open_invoices_of_another_account_do_not_block_deletion(db, M, w1, u2, mk_account, mk_invoice):
    """ACC-D-19 — open invoices of another account do not block the deletion.
    Rules: delete_account R7b (other accounts' invoices), R4"""
    a1 = mk_account()
    a2 = mk_account(name="Beta Co")
    i1 = mk_invoice(a2, "draft")
    i2 = mk_invoice(a2, "unpaid")

    before_a2 = snap(db, a2)
    before_i1 = snap(db, i1)
    before_i2 = snap(db, i2)

    result = M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    row_a1 = reread(db, a1)
    assert row_a1.is_deleted is True
    assert row_a1.is_active is False
    assert row_a1.deleted_by == u2.id
    # Then 3
    assert snap(db, a2) == before_a2
    assert reread(db, a2).is_deleted is False
    # Then 4
    assert snap(db, i1) == before_i1
    assert snap(db, i2) == before_i2


# [local-coder] ACC-D-20
def test_acc_d_20__unknown_account_in_wrong_workspace(db, M, w1, w2, u2, mk_account, mk_invoice):
    """ACC-D-20 — an account of another workspace gets the account error even with an open invoice.
    Rules: delete_account R7c (R2 is checked before the invoices), R2"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    i1 = mk_invoice(a9, "draft")

    before_a9 = snap(db, a9)
    before_i1 = snap(db, i1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a9.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value).startswith(f"Account {a9.id} ")
    # Then 2
    assert str(exc.value) != "Account has open invoices — settle or void them first"
    # Then 3
    assert snap(db, a9) == before_a9
    assert reread(db, a9).is_deleted is False
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-D-21
def test_acc_d_21__already_deleted_account_gets_already_deleted_even_with_open_invoice(db, M, w1, u1, u2, mk_account, mk_invoice):
    """ACC-D-21 — an already deleted account gets "already deleted" even with an open invoice.
    Rules: delete_account R7c (R3 is checked before the invoices), R3"""
    a1 = mk_account(deleted=True)
    i1 = mk_invoice(a1, "draft")

    before_a1 = snap(db, a1)
    before_i1 = snap(db, i1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_account(db, account_id=a1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a1.id} is already deleted"
    # Then 2
    assert snap(db, a1) == before_a1
    row = reread(db, a1)
    assert row.deleted_at == T0
    assert row.deleted_by == u1.id
    # Then 3
    assert snap(db, i1) == before_i1
    # Then 4
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-AT-01
def test_acc_at_01__empty_list_writes_nothing(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-01 — an empty list writes nothing.
    Rules: _assign_tags_to_account R1"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=2)
    before = written(db)

    result = M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 2


# [local-coder] ACC-AT-02
def test_acc_at_02__each_new_tag_gets_one_assignment_row_and_one_increment(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-02 — each new tag gets one assignment row and one increment.
    Rules: _assign_tags_to_account R4, R8"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t2 = mk_tag("Client", "client", usage_count=3)

    result = M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t1.id, t2.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    for x in links(db, a1):
        assert x.account_id == a1.id
        assert x.workspace_id == w1.id
        assert x.assigned_by == u2.id
        assert x.assigned_at is not None
        assert x.id is not None
    # Then 4
    assert reread(db, t1).usage_count == 1
    # Then 5
    assert reread(db, t2).usage_count == 4


# [local-coder] ACC-AT-03
def test_acc_at_03__a_tag_already_assigned_is_skipped(db, M, w1, u1, u2, mk_account, mk_tag, mk_link):
    """ACC-AT-03 — a tag that is already assigned is skipped.
    Rules: _assign_tags_to_account R3, R4"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    x1 = mk_link(a1, t1)

    before_x1 = snap(db, x1)

    result = M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t1.id, t2.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    assert snap(db, x1) == before_x1
    row_x1 = link_row(db, a1, t1)
    assert row_x1.id == x1.id
    assert row_x1.assigned_at == T0
    assert row_x1.assigned_by == u1.id
    # Then 4
    assert reread(db, t1).usage_count == 1
    # Then 5
    assert reread(db, t2).usage_count == 1


# [local-coder] ACC-AT-04
def test_acc_at_04__the_same_id_twice_gives_one_assignment_and_one_increment(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-04 — the same id twice gives one assignment and one increment.
    Rules: _assign_tags_to_account R5"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    result = M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t1.id, t1.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-AT-05
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_at_05__unknown_tag_id_raises(db, M, w1, u2, mk_account):
    """ACC-AT-05 — unknown tag id raises.
    Rules: _assign_tags_to_account R2 [BUG-871]"""
    a1 = mk_account()
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[MISSING], workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-AT-06
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_at_06__tag_of_another_workspace_raises(db, M, w1, w2, u2, mk_account, mk_tag):
    """ACC-AT-06 — tag of another workspace raises.
    Rules: _assign_tags_to_account R2 [BUG-871]"""
    a1 = mk_account()
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t9.id], workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t9.id} not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t9).usage_count == 1


# [local-coder] ACC-AT-07
@pytest.mark.xfail(strict=True, reason="BUG-871: Unknown tag ids silently dropped on account create / update")
def test_acc_at_07__all_ids_are_validated_before_anything_is_attached(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-07 — all ids are validated before anything is attached.
    Rules: _assign_tags_to_account R7 [BUG-871], R2 [BUG-871]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t1.id, MISSING], workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-AT-08
@pytest.mark.xfail(strict=True, reason="BUG-2987: Creating or updating an account accepts a deleted (inactive) tag that \"assign tag\" refuses")
def test_acc_at_08__inactive_tag_not_assigned_raises(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-08 — an inactive tag that is not yet assigned raises.
    Rules: _assign_tags_to_account R6 [BUG-2987]; Errors row 2"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t3.id], workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t3).usage_count == 0


# [local-coder] ACC-AT-09
def test_acc_at_09__inactive_tag_already_assigned_is_skipped(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-AT-09 — an inactive tag that is already assigned is skipped without error.
    Rules: _assign_tags_to_account R6 (already assigned), R3"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    x3 = mk_link(a1, t3)

    before_x3 = snap(db, x3)

    result = M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t3.id], workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t3.id]
    # Then 3
    assert snap(db, x3) == before_x3
    # Then 4
    assert reread(db, t3).usage_count == 1


# [local-coder] ACC-AT-10
@pytest.mark.xfail(strict=True, reason="BUG-2987: Creating or updating an account accepts a deleted (inactive) tag that \"assign tag\" refuses")
def test_acc_at_10__inactive_tag_id_in_list_keeps_valid_tags_attached(db, M, w1, u2, mk_account, mk_tag):
    """ACC-AT-10 — an inactive id in the list keeps valid tags from being attached.
    Rules: _assign_tags_to_account R7, R6 [BUG-2987]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M._assign_tags_to_account(db, account_id=a1.id, tag_ids=[t1.id, t3.id], workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 0
    assert reread(db, t3).usage_count == 0


# [local-coder] ACC-A-02
def test_acc_a_02__unknown_account_id_rejected(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-02 — unknown account id is rejected.
    Rules: assign_tag R1; Errors row 1"""
    mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=MISSING, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-A-03
def test_acc_a_03__account_of_another_workspace_is_rejected_as_not_found(db, M, w1, w2, u2, mk_account, mk_tag):
    """ACC-A-03 — account of another workspace is rejected as not found.
    Rules: assign_tag R2; Errors row 1"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a9.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a9.id} not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-A-04
@pytest.mark.xfail(strict=True, reason="BUG-863: Soft-deleted accounts can still be edited and tagged / untagged")
def test_acc_a_04__soft_deleted_account_cannot_be_tagged(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-04 — a soft-deleted account cannot be tagged.
    Rules: assign_tag R3 [BUG-863]"""
    a1 = mk_account(deleted=True)
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account {a1.id} not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-A-05
def test_acc_a_05__unknown_tag_id_rejected(db, M, w1, u2, mk_account):
    """ACC-A-05 — unknown tag id is rejected.
    Rules: assign_tag R4; Errors row 2"""
    a1 = mk_account()
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a1.id, tag_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account tag 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-A-06
def test_acc_a_06__tag_of_another_workspace_is_rejected_as_not_found(db, M, w1, w2, u2, mk_account, mk_tag):
    """ACC-A-06 — tag of another workspace is rejected as not found.
    Rules: assign_tag R4; Errors row 2"""
    a1 = mk_account()
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a1.id, tag_id=t9.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t9.id} not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t9).usage_count == 1


# [local-coder] ACC-A-07
def test_acc_a_07__when_account_and_tag_are_both_unknown_the_account_error_wins(db, M, w1, u2):
    """ACC-A-07 — when account and tag are both unknown, the account error wins.
    Rules: assign_tag R4 (account checked first), R1"""
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=MISSING, tag_id=MISSING2, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 0
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0


# [local-coder] ACC-A-08
def test_acc_a_08__inactive_tag_rejected(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-08 — an inactive tag is rejected.
    Rules: assign_tag R5; Errors row 3"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=0)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a1.id, tag_id=t3.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t3).usage_count == 0


# [local-coder] ACC-A-09
def test_acc_a_09__inactive_tag_rejected_even_if_assigned(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-A-09 — an inactive tag is rejected even when it is already assigned.
    Rules: assign_tag R5"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    x3 = mk_link(a1, t3)

    before_x3 = snap(db, x3)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.assign_tag(db, account_id=a1.id, tag_id=t3.id, workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == f"Account tag {t3.id} is not active"
    # Then 2
    assert snap(db, x3) == before_x3
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t3).usage_count == 1


# [local-coder] ACC-A-10
def test_acc_a_10__assigning_already_assigned_tag_changes_nothing(db, M, w1, u1, u2, mk_account, mk_tag, mk_link):
    """ACC-A-10 — assigning an already assigned tag changes nothing.
    Rules: assign_tag R6"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    x1 = mk_link(a1, t1)

    before_x1 = snap(db, x1)

    result = M.assign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert snap(db, x1) == before_x1
    row_x1 = link_row(db, a1, t1)
    assert row_x1.id == x1.id
    assert row_x1.assigned_at == T0
    assert row_x1.assigned_by == u1.id
    # Then 4
    assert reread(db, t1).usage_count == 1
    # Then 5
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 6
    assert reread(db, a1).updated_by is None


# [local-coder] ACC-A-11
@pytest.mark.xfail(strict=True, reason="BUG-873: Single-tag assign / unassign leave no audit row or updated_by stamp")
def test_acc_a_11__a_real_assignment_writes_an_updated_audit_row_with_the_tag_ids(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-A-11 — a real assignment writes an "updated" audit row with the tag ids.
    Rules: assign_tag R8 [BUG-873]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    mk_link(a1, t1)

    result = M.assign_tag(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id, t2.id]
    # Then 3
    assert count_rows(db, FinancialAuditLog) == 1
    logs = audit(db, a1)
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "account"
    assert log.entity_id == a1.id
    assert log.workspace_id == w1.id
    assert log.related_entity_type is None
    assert log.related_entity_id is None
    # Then 4
    assert log.action_type == "updated"
    assert log.description == "Account 'Acme Ltd' updated"
    assert log.performed_by == u2.id
    assert log.performed_at == NOW
    # Then 5
    assert log.changes == {"before": {"tag_ids": [t1.id]}, "after": {"tag_ids": [t1.id, t2.id]}}


# [local-coder] ACC-A-12
@pytest.mark.xfail(strict=True, reason="BUG-873: Single-tag assign / unassign leave no audit row or updated_by stamp")
def test_acc_a_12__a_real_assignment_stamps_the_accounts_updated_by(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-12 — a real assignment stamps the account's updated_by.
    Rules: assign_tag R8 [BUG-873]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    result = M.assign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    row = reread(db, a1)
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None


# [local-coder] ACC-A-13
def test_acc_a_13__inactive_account_can_be_tagged(db, M, w1, u2, mk_account, mk_tag):
    """ACC-A-13 — an inactive account can be tagged.
    Rules: assign_tag R9"""
    a1 = mk_account(is_active=False, is_deleted=False)
    t1 = mk_tag("Supplier", "supplier", usage_count=0)

    result = M.assign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-UN-01
def test_acc_un_01__removing_a_tag_deletes_the_assignment_and_lowers_the_count(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-01 — removing a tag deletes the assignment and lowers the count.
    Rules: unassign_tag R5"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=3)
    t2 = mk_tag("Client", "client", usage_count=1)
    mk_link(a1, t1)
    x2 = mk_link(a1, t2)

    before_x2 = snap(db, x2)

    result = M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t2.id]
    # Then 3
    assert reread(db, t1).usage_count == 2
    # Then 4
    assert reread(db, t2).usage_count == 1
    # Then 5
    assert snap(db, x2) == before_x2


# [local-coder] ACC-UN-02
def test_acc_un_02__a_usage_count_of_0_stays_0(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-02 — a usage count of 0 stays 0.
    Rules: unassign_tag R5 (floor 0)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    mk_link(a1, t1)

    result = M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == []
    # Then 3
    assert reread(db, t1).usage_count == 0


# [local-coder] ACC-UN-03
def test_acc_un_03__unknown_account_id_rejected(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-03 — unknown account id is rejected.
    Rules: unassign_tag R1; Errors row 1"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.unassign_tag(db, account_id=MISSING, tag_id=t1.id, workspace_id=w1.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-UN-04
def test_acc_un_04__account_of_another_workspace_is_rejected_as_not_found(db, M, w1, w2, mk_account, mk_tag, mk_link):
    """ACC-UN-04 — account of another workspace is rejected as not found.
    Rules: unassign_tag R2; Errors row 1"""
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)
    mk_link(a9, t9, workspace_id=w2.id)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.unassign_tag(db, account_id=a9.id, tag_id=t9.id, workspace_id=w1.id)

    assert str(exc.value) == f"Account {a9.id} not found"
    # Then 2
    assert tags(db, a9) == [t9.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t9).usage_count == 1


# [local-coder] ACC-UN-05
@pytest.mark.xfail(strict=True, reason="BUG-863: Soft-deleted accounts can still be edited and tagged / untagged")
def test_acc_un_05__a_tag_cannot_be_removed_from_a_soft_deleted_account(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-05 — a tag cannot be removed from a soft-deleted account.
    Rules: unassign_tag R3 [BUG-863]"""
    a1 = mk_account(deleted=True)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    assert str(exc.value) == f"Account {a1.id} not found"
    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-UN-06
def test_acc_un_06__removing_unassigned_tag_rejected(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-06 — removing a tag that is not assigned is rejected and changes nothing.
    Rules: unassign_tag R4 (error raised, nothing changes)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=4)
    mk_link(a1, t1)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError):
        M.unassign_tag(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id)

    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1
    assert reread(db, t2).usage_count == 4


# [local-coder] ACC-UN-07
@pytest.mark.xfail(strict=True, reason="BUG-879: Removing an unassigned tag answers 422, API documents 404")
def test_acc_un_07__not_assigned_uses_assignment_not_found_message(db, M, w1, mk_account, mk_tag):
    """ACC-UN-07 — "not assigned" uses the "assignment not found" message.
    Rules: unassign_tag R4 [BUG-879]"""
    a1 = mk_account()
    t2 = mk_tag("Client", "client", usage_count=4)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.unassign_tag(db, account_id=a1.id, tag_id=t2.id, workspace_id=w1.id)

    assert str(exc.value) == f"Tag {t2.id} assignment not found for account {a1.id}"
    # Then 2
    assert reread(db, t2).usage_count == 4


# [local-coder] ACC-UN-08
def test_acc_un_08__unknown_tag_id_rejected(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-08 — removing an unknown tag id is rejected and changes nothing.
    Rules: unassign_tag R4 (unknown tag id)"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError):
        M.unassign_tag(db, account_id=a1.id, tag_id=MISSING, workspace_id=w1.id)

    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-UN-09
@pytest.mark.xfail(strict=True, reason="BUG-879: Removing an unassigned tag answers 422, API documents 404")
def test_acc_un_09__unknown_tag_id_uses_assignment_not_found_message(db, M, w1, mk_account):
    """ACC-UN-09 — an unknown tag id uses the "assignment not found" message.
    Rules: unassign_tag R4 [BUG-879]"""
    a1 = mk_account()

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.unassign_tag(db, account_id=a1.id, tag_id=MISSING, workspace_id=w1.id)

    assert str(exc.value) == f"Tag 999999999 assignment not found for account {a1.id}"
    # Then 2
    assert count_rows(db, AccountTagAssignment) == 0


# [local-coder] ACC-UN-10
def test_acc_un_10__tag_of_another_workspace_rejected(db, M, w1, w2, mk_account, mk_tag, mk_link):
    """ACC-UN-10 — a tag of another workspace is rejected and not touched.
    Rules: unassign_tag R4"""
    a1 = mk_account()
    a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)
    t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)
    mk_link(a9, t9)

    before = written(db)

    # Then 1
    with pytest.raises(ValueError):
        M.unassign_tag(db, account_id=a1.id, tag_id=t9.id, workspace_id=w1.id)

    # Then 2
    assert tags(db, a9) == [t9.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 2
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t9).usage_count == 1


# [local-coder] ACC-UN-11
def test_acc_un_11__inactive_tag_can_be_removed(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-11 — an inactive tag can be removed from an account.
    Rules: unassign_tag R6, R5"""
    a1 = mk_account()
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=2)
    mk_link(a1, t3)

    result = M.unassign_tag(db, account_id=a1.id, tag_id=t3.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == []
    # Then 3
    assert reread(db, t3).usage_count == 1
    assert reread(db, t3).is_active is False


@pytest.mark.xfail(strict=True, reason="BUG-873: Single-tag assign / unassign leave no audit row or updated_by stamp")
def test_acc_un_12__a_real_removal_writes_an_updated_audit_row_with_the_tag_ids(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-UN-12 — a real removal writes an "updated" audit row with the tag ids.
    Rules: unassign_tag R7 [BUG-873]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t2)

    # Fails today here: unassign_tag has no user_id parameter (TypeError).
    result = M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == [t2.id]
    # Then 3
    assert count_rows(db, FinancialAuditLog) == 1
    logs = audit(db, a1)
    assert len(logs) == 1
    log = logs[0]
    assert log.entity_type == "account"
    assert log.entity_id == a1.id
    assert log.workspace_id == w1.id
    assert log.related_entity_type is None
    assert log.related_entity_id is None
    # Then 4
    assert log.action_type == "updated"
    assert log.description == "Account 'Acme Ltd' updated"
    assert log.performed_by == u2.id
    # Then 5
    assert log.changes == {"before": {"tag_ids": [t1.id, t2.id]}, "after": {"tag_ids": [t2.id]}}


# [local-coder] ACC-UN-13
@pytest.mark.xfail(strict=True, reason="BUG-873: Single-tag assign / unassign leave no audit row or updated_by stamp")
def test_acc_un_13__a_real_removal_stamps_the_accounts_updated_by(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-UN-13 — a real removal stamps the account's `updated_by`.
    Rules: unassign_tag R7 [BUG-873]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    # Then 2
    assert tags(db, a1) == []
    # Then 3
    row = reread(db, a1)
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None


# [local-coder] ACC-UN-14
@pytest.mark.xfail(strict=True, reason="BUG-873: Single-tag assign / unassign leave no audit row or updated_by stamp")
def test_acc_un_14__user_id_is_required(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-UN-14 — user_id is a required argument.
    Rules: unassign_tag Inputs (user_id required, no default) [BUG-873]; R7 [BUG-873]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)
    before = written(db)

    # Then 1
    with pytest.raises(TypeError):
        M.unassign_tag(db, account_id=a1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 2
    assert tags(db, a1) == [t1.id]
    # Then 3
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 1
    assert count_rows(db, FinancialAuditLog) == 0
    assert reread(db, t1).usage_count == 1


# [local-coder] ACC-T-01
def test_acc_t_01__returns_the_accounts_tags_each_once(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-01 — returns the account's tags, each once.
    Rules: get_tags_for_account R1"""
    a1 = mk_account()
    a2 = mk_account(name="Beta Co")
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=1)
    t4 = mk_tag("Utility", "utility", usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t2)
    mk_link(a2, t4)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    assert all(isinstance(t, AccountTag) for t in result)
    assert len(result) == 2
    # Then 2
    assert {t.id for t in result} == {t1.id, t2.id}
    # Then 3
    assert {t.tag_code for t in result} == {"supplier", "client"}


# [local-coder] ACC-T-02
def test_acc_t_02__account_without_tags_returns_empty_list(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-02 — an account without tags gives an empty list.
    Rules: get_tags_for_account R2"""
    a1 = mk_account()
    a2 = mk_account(name="Beta Co")
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a2, t1)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ACC-T-03
def test_acc_t_03__unknown_account_id_gives_empty_list(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-03 — an unknown account id gives an empty list.
    Rules: get_tags_for_account R2"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.get_tags_for_account(db, account_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [local-coder] ACC-T-04
def test_acc_t_04__asking_with_another_workspace_id_gives_an_empty_list(db, M, w2, mk_account, mk_tag, mk_link):
    """ACC-T-04 — asking with another workspace id gives an empty list.
    Rules: get_tags_for_account R3"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [local-coder] ACC-T-05
@pytest.mark.xfail(strict=True, reason="BUG-865: get_tags_for_account returns deleted tags")
def test_acc_t_05__inactive_tags_are_not_returned(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-05 — inactive tags are not returned.
    Rules: get_tags_for_account R4 [BUG-865]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t3)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    assert result[0].id == t1.id


# [local-coder] ACC-T-06 (marker revised by Claude in cases revision 3: BUG-1486, non-strict)
@pytest.mark.xfail(strict=False, reason="BUG-1486: An account's tags have no sort order")
def test_acc_t_06__tags_ordered_by_name_ignoring_case(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-06 — tags are ordered by name ignoring case.
    Rules: get_tags_for_account R5 [BUG-1486]"""
    a1 = mk_account()
    t1 = mk_tag("Bravo", "b1", usage_count=1)
    t2 = mk_tag("charlie", "c1", usage_count=1)
    t3 = mk_tag("alpha", "a1", usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t2)
    mk_link(a1, t3)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert [t.name for t in result] == ["alpha", "Bravo", "charlie"]


# [local-coder] ACC-T-07 (marker revised by Claude in cases revision 3: BUG-1486, non-strict)
@pytest.mark.xfail(strict=False, reason="BUG-1486: An account's tags have no sort order")
def test_acc_t_07__tags_with_same_name_ignoring_case_ordered_by_id(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-07 — tags with the same name ignoring case are ordered by id.
    Rules: get_tags_for_account R5 [BUG-1486]"""
    a1 = mk_account()
    b = mk_tag("beta", "b1", usage_count=1)
    h = mk_tag("ALPHA", "a1", usage_count=1)
    l = mk_tag("alpha", "a2", usage_count=1)
    mk_link(a1, b)
    mk_link(a1, h)
    mk_link(a1, l)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert [t.id for t in result] == [h.id, l.id, b.id]


# [local-coder] ACC-T-08
def test_acc_t_08__the_tags_of_a_soft_deleted_account_are_still_returned(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-08 — the tags of a soft-deleted account are still returned.
    Rules: get_tags_for_account R6"""
    a1 = mk_account(deleted=True)
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    assert result[0].id == t1.id


# [claude] ACC-T-09
@pytest.mark.xfail(strict=False, reason="BUG-1486: An account's tags have no sort order")
def test_acc_t_09__system_tag_not_placed_first(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-09 — a system tag is not placed first.
    Rules: get_tags_for_account R5 [BUG-1486] (system tags not grouped first)"""
    a1 = mk_account()
    z = mk_tag("Zulu", "z1", usage_count=1, is_system_tag=True)
    h = mk_tag("alpha", "a1", usage_count=1)
    k = mk_tag("Mike", "m1", usage_count=1)
    mk_link(a1, z)
    mk_link(a1, h)
    mk_link(a1, k)

    result = M.get_tags_for_account(db, account_id=a1.id, workspace_id=w1.id)

    # Then 1
    assert [t.id for t in result] == [h.id, k.id, z.id]


# [claude] ACC-T-10
@pytest.mark.xfail(strict=True, reason="BUG-1486: An account's tags have no sort order")
def test_acc_t_10__tags_select_carries_an_order_by(db, M, w1, mk_account, mk_tag, mk_link):
    """ACC-T-10 — the tags SELECT carries an ORDER BY.
    Rules: get_tags_for_account R5 [BUG-1486]"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=1)
    mk_link(a1, t1)
    mk_link(a1, t2)
    expected_ids = {t1.id, t2.id}
    a1_id = a1.id
    db.expire_all()

    with StatementRecorder(db) as rec:
        result = M.get_tags_for_account(db, account_id=a1_id, workspace_id=w1.id)

    # Then 1
    assert {t.id for t in result} == expected_ids
    # Then 2
    found = rec.selects_with("account_tags")
    assert len(found) == 1
    # Then 3
    assert "ORDER BY" in found[0]
