"""Unit tests for app/managers/order_template_manager.py.

Implements tests/unit/managers/order_template_manager.cases.md (revision 3), one
test per card, in card order. Real Postgres session (`db` fixture), rolled back
after each test. Nothing is patched (Conventions, Externals: none) except the
commit spy of the "rolled back" convention.

How to read these tests:
- The standing rows of Conventions live on the fixture `s`: W0 -> `s.w0`,
  UO -> `s.uo`, UZ -> `s.uz`. Given rows are built with `tpl`, `line`,
  `account`, `factory`, `dept`, each with the card's "but" columns as keywords
  (`INACTIVE(s)`, `CLOSED(s)`, `DELETED(s)` spell the named variants).
- `# Then N` marks the checks of the card's Then line N. Bug cards are strict
  xfails: they describe the intended behaviour and fail today on the Then line
  their card names; when the bug is fixed they XPASS, so remove the marker.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: FURB157  (the cards write decimals as strings, e.g. `Decimal("0")`; kept as written)
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

from app.managers.order_template_manager import order_template_manager
from app.models.account import Account
from app.models.department import Department
from app.models.expense_order import ExpenseOrder
from app.models.factory import Factory
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.models.workspace_member import WorkspaceMember
from app.schemas.order_template import (
    OrderTemplateCreate,
    OrderTemplateItemCreate,
    OrderTemplateItemUpdate,
    OrderTemplateUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "M = the singleton order_template_manager"
M = order_template_manager

# Conventions "MISSING", "T0" ... "T3" (naive)
MISSING = 999999999
T0 = datetime(2026, 3, 1, 9, 0, 0)  # noqa: DTZ001
T1 = datetime(2026, 3, 2, 9, 0, 0)  # noqa: DTZ001
T2 = datetime(2026, 3, 3, 9, 0, 0)  # noqa: DTZ001
T3 = datetime(2026, 3, 4, 9, 0, 0)  # noqa: DTZ001

# Conventions "N255", "N256", "U50", "U51", "R50", "R51"
N255 = "R" * 255
N256 = "R" * 256
U50 = "k" * 50
U51 = "k" * 51
R50 = "w" * 50
R51 = "w" * 51

# Conventions "FORBID", "LTL"
FORBID = "Only the workspace owner can skip approval on a template"
LTL = "Line total is too large"

# Convention "ITEM"
ITEM = OrderTemplateItemCreate(description="Bolt", quantity=Decimal("2.00"), unit_price=Decimal("5.00"))

# Expect lines -> markers ("xfail BUG-n" = strict; the reason carries the bug's title from docs/testing/bugs.md)
BUG_1014 = pytest.mark.xfail(strict=True, reason="BUG-1014: Order template accepts another workspace's account")
BUG_1216 = pytest.mark.xfail(
    strict=True, reason="BUG-1216: Order template accepts another workspace's department and a non-member approver",
)
BUG_1226 = pytest.mark.xfail(strict=True, reason="BUG-1226: Setting a template line's price to 0 leaves the old subtotal")
BUG_2347 = pytest.mark.xfail(
    strict=True, reason="BUG-2347: Any member can make an expense template whose orders skip approval",
)
BUG_2349 = pytest.mark.xfail(
    strict=True, reason="BUG-2349: A template line total too large for Numeric(15, 2) fails with a database error",
)
BUG_2355 = pytest.mark.xfail(strict=True, reason="BUG-2355: Blank order template names accepted, names stored untrimmed")
BUG_2356 = pytest.mark.xfail(strict=True, reason="BUG-2356: Order template updated_by stamped when nothing changed")
BUG_2357 = pytest.mark.xfail(strict=True, reason="BUG-2357: Order template fields cannot be cleared")
BUG_2358 = pytest.mark.xfail(strict=True, reason="BUG-2358: Order template line fields cannot be cleared")
BUG_2359 = pytest.mark.xfail(
    strict=True, reason="BUG-2359: Any text accepted as an order template's expense category",
)
BUG_2360 = pytest.mark.xfail(strict=True, reason="BUG-2360: Order template of category \"other\" keeps a cost centre")
BUG_2361 = pytest.mark.xfail(
    strict=True, reason="BUG-2361: Factory / department template without a cost centre can never make an order",
)
BUG_2362 = pytest.mark.xfail(
    strict=True, reason="BUG-2362: Deleted account, factory or department can be put on an order template",
)
BUG_2363 = pytest.mark.xfail(
    strict=True, reason="BUG-2363: Template line quantity / price accept more than 2 decimals",
)
BUG_2364 = pytest.mark.xfail(
    strict=True, reason="BUG-2364: Template line quantity can be 0 or negative, price negative",
)
BUG_2365 = pytest.mark.xfail(
    strict=True,
    reason="BUG-2365: Over-long order template name, unit or recurrence type fails with a database error",
)
BUG_2366 = pytest.mark.xfail(strict=True, reason="BUG-2366: Lines of a missing order template answer an empty list")


# --------------------------------------------------------------------------- #
# Conventions -> standing rows (every test, in this order)
# --------------------------------------------------------------------------- #

def _member(db, ws, user, role, status="active"):
    row = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=role, status=status)
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def s(db):
    """W0 < W1 < W2; UO, UA, UG, UX, UZ; (W1, UO owner), (W1, UA manager), (W1, UG ground-team), (W2, UX owner)."""
    w0 = make_workspace(db)
    w1 = make_workspace(db)
    w2 = make_workspace(db)
    uo = make_profile(db, name="Olive")
    ua = make_profile(db, name="Ann")
    ug = make_profile(db, name="Gus")
    ux = make_profile(db, name="Xia")
    uz = make_profile(db, name="Zed")
    _member(db, w1, uo, "owner")
    _member(db, w1, ua, "manager")
    _member(db, w1, ug, "ground-team")
    _member(db, w2, ux, "owner")
    return SimpleNamespace(w0=w0, w1=w1, w2=w2, uo=uo, ua=ua, ug=ug, ux=ux, uz=uz)


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (inserted directly, flushed one at a time)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "template"
def tpl(db, s, **but):
    fields = {
        "workspace_id": s.w1.id, "template_name": "Rent", "requires_approval": True,
        "auto_approve": False, "created_by": s.uo.id, "created_at": T0,
    }
    fields.update(but)
    return _add(db, OrderTemplate(**fields))


# Convention "inactive" (template)
def INACTIVE(s):
    return {"is_active": False, "updated_by": s.uo.id, "updated_at": T1}


# Convention "line n on T"
def line(db, s, t, n, **but):
    fields = {
        "workspace_id": s.w1.id, "order_template_id": t.id, "line_number": n, "description": "Line",
        "quantity": Decimal("3.00"), "unit_price": Decimal("10.00"), "line_subtotal": Decimal("30.00"),
    }
    fields.update(but)
    return _add(db, OrderTemplateItem(**fields))


# Convention "account"
def account(db, s, **but):
    fields = {"workspace_id": s.w1.id, "name": "Acme", "is_active": True, "is_deleted": False}
    fields.update(but)
    return _add(db, Account(**fields))


# Convention "closed" (account)
def CLOSED(s):
    return {"is_deleted": True, "is_active": False, "deleted_at": T0, "deleted_by": s.uo.id}


# Convention "factory"
def factory(db, s, **but):
    fields = {"workspace_id": s.w1.id, "name": "Factory One", "abbreviation": "F1"}
    fields.update(but)
    return _add(db, Factory(**fields))


# Convention "department"
def dept(db, s, **but):
    fields = {"workspace_id": s.w1.id, "name": "Sales"}
    fields.update(but)
    return _add(db, Department(**fields))


# Convention "deleted" (factory or department)
def DELETED(s):
    return {"is_deleted": True, "deleted_at": T0, "deleted_by": s.uo.id}


# Convention "pending P"
def pending_p(db, s):
    p = OrderTemplate(
        workspace_id=s.w1.id, template_name="Pending", requires_approval=True, auto_approve=False,
        created_by=s.uo.id, created_at=T3,
    )
    db.add(p)
    return p


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

# Convention "re-read X"
def reread(db, model, row_id):
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def rt(db, row_id):
    """re-read a template"""
    return reread(db, OrderTemplate, row_id)


def rl(db, row_id):
    """re-read a line"""
    return reread(db, OrderTemplateItem, row_id)


# Convention "lines(T)"
def lines(db, tpl_id):
    db.expire_all()
    return list(db.execute(
        select(OrderTemplateItem).where(OrderTemplateItem.order_template_id == tpl_id)
        .order_by(OrderTemplateItem.line_number, OrderTemplateItem.id)
    ).scalars())


# Convention "unchanged(X)": every column, read from the table
def snap(db, row):
    table = type(row).__table__
    row_id = row.id
    db.expire_all()
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines
def count(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar_one()


# Convention "nothing written"
def written(db):
    return (count(db, OrderTemplate), count(db, OrderTemplateItem))


def new_tpl_lines(db, result):
    return lines(db, result.id)


# =========================================================================== #
# OrderTemplateManager.create_template
# =========================================================================== #

# [claude] OTMG-CT-01
def test_otmg_ct_01__create_stores_every_field_sent(db, s):
    """OTMG-CT-01 — create stores every field sent, with the caller as creator, flushed.
    Rules: create_template R1, R6 (valid references), Returns"""
    ac = account(db, s)
    f = factory(db, s)
    result = M.create_template(db, data=OrderTemplateCreate(
        template_name="Office rent", description="Monthly", account_id=ac.id, expense_category="factory",
        cost_center_id=f.id, default_approver_id=s.ua.id, notes="Pay by the 5th",
    ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert isinstance(result, OrderTemplate)
    # Then 2
    assert result.id is not None
    # Then 3
    row = rt(db, result.id)
    assert row.template_name == "Office rent"
    assert row.description == "Monthly"
    assert row.notes == "Pay by the 5th"
    # Then 4
    assert row.account_id == ac.id
    assert row.expense_category == "factory"
    assert row.cost_center_id == f.id
    assert row.default_approver_id == s.ua.id
    # Then 5
    assert row.workspace_id == s.w1.id
    assert row.created_by == s.uo.id
    # Then 6
    assert row.created_at is not None


# [claude] OTMG-CT-02
def test_otmg_ct_02__fields_not_sent_take_the_defaults(db, s):
    """OTMG-CT-02 — fields not sent take the defaults; nothing is stamped as updated.
    Rules: create_template R1, R7"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.is_active is True
    assert row.updated_by is None
    assert row.updated_at is None
    # Then 3
    assert row.next_generation_date is None
    assert row.last_generated_date is None
    # Then 4
    assert row.requires_approval is True
    assert row.auto_approve is False
    # Then 5
    assert row.is_recurring is False
    assert row.generate_days_before == 0
    # Then 6
    assert row.account_id is None
    assert row.expense_category is None
    assert row.cost_center_id is None
    assert row.default_approver_id is None
    # Then 7
    assert row.description is None
    assert row.notes is None
    assert row.created_by == s.ua.id


# [claude] OTMG-CT-03
def test_otmg_ct_03__recurrence_fields_are_stored_unchecked(db, s):
    """OTMG-CT-03 — recurrence fields are stored as sent, unchecked.
    Rules: create_template R2"""
    result = M.create_template(db, data=OrderTemplateCreate(
        template_name="Rent", is_recurring=True, recurrence_type="every odd moon", recurrence_interval=0,
        recurrence_day=31, start_date=date(2026, 5, 1), end_date=date(2026, 4, 1), generate_days_before=-3,
    ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.is_recurring is True
    assert row.recurrence_type == "every odd moon"
    assert row.recurrence_interval == 0
    assert row.recurrence_day == 31
    # Then 3
    assert row.start_date == date(2026, 5, 1)
    assert row.end_date == date(2026, 4, 1)
    # Then 4
    assert row.generate_days_before == -3
    # Then 5
    assert row.next_generation_date is None
    assert row.last_generated_date is None


# [claude] OTMG-CT-04
def test_otmg_ct_04__items_empty_creates_no_line(db, s):
    """OTMG-CT-04 — items=[] creates no line.
    Rules: create_template R10"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == result.id) == 0


# [claude] OTMG-CT-05
def test_otmg_ct_05__items_none_creates_no_line(db, s):
    """OTMG-CT-05 — items=None creates no line.
    Rules: create_template R10"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=None), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == result.id) == 0


# [claude] OTMG-CT-06
def test_otmg_ct_06__lines_are_numbered_in_order_with_own_product(db, s):
    """OTMG-CT-06 — lines are numbered 1, 2, 3 in the order given, each with its own product.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Zinc", unit="kg", quantity=Decimal("2.00"), unit_price=Decimal("3.00"), notes="z"),
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("4.00"), unit_price=Decimal("1.50")),
        OrderTemplateItemCreate(description="Mesh", quantity=Decimal("1.00"), unit_price=Decimal("7.25")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 3
    # Then 3
    assert [x.description for x in ls] == ["Zinc", "Bolt", "Mesh"]
    # Then 4
    assert [x.line_number for x in ls] == [1, 2, 3]
    # Then 5
    assert [x.line_subtotal for x in ls] == [Decimal("6.00"), Decimal("6.00"), Decimal("7.25")]
    # Then 6
    assert all(x.workspace_id == s.w1.id for x in ls)
    assert all(x.order_template_id == result.id for x in ls)
    # Then 7
    assert ls[0].unit == "kg"
    assert ls[0].notes == "z"
    assert ls[0].quantity == Decimal("2.00")
    assert ls[0].unit_price == Decimal("3.00")


# [claude] OTMG-CT-07
def test_otmg_ct_07__product_ending_in_5_rounds_half_up(db, s):
    """OTMG-CT-07 — a product ending in 5 rounds half up: 0.50 x 0.25 = 0.125 gives 0.13.
    Rules: create_template R8 (HR-15)"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Washer", quantity=Decimal("0.50"), unit_price=Decimal("0.25")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].line_subtotal == Decimal("0.13")
    # Then 3
    assert ls[0].quantity == Decimal("0.50")
    assert ls[0].unit_price == Decimal("0.25")


# [claude] OTMG-CT-08
def test_otmg_ct_08__products_just_below_and_above_the_half(db, s):
    """OTMG-CT-08 — products just below and just above the half: 0.123 gives 0.12, 0.126 gives 0.13.
    Rules: create_template R8 (HR-15)"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Low", quantity=Decimal("0.30"), unit_price=Decimal("0.41")),
        OrderTemplateItemCreate(description="High", quantity=Decimal("0.30"), unit_price=Decimal("0.42")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert ls[0].line_subtotal == Decimal("0.12")
    # Then 3
    assert ls[1].line_subtotal == Decimal("0.13")


# [claude] OTMG-CT-09
def test_otmg_ct_09__1_50_times_0_25_gives_0_38(db, s):
    """OTMG-CT-09 — 1.50 x 0.25 = 0.375 gives 0.38.
    Rules: create_template R8 (HR-15)"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Tape", quantity=Decimal("1.50"), unit_price=Decimal("0.25")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].line_subtotal == Decimal("0.38")


# [claude] OTMG-CT-10
def test_otmg_ct_10__no_price_gives_subtotal_0(db, s):
    """OTMG-CT-10 — a line with no price has subtotal 0.00 and keeps its price empty.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Labour", quantity=Decimal("4.00")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].unit_price is None
    # Then 3
    assert ls[0].line_subtotal == Decimal("0.00")


# [claude] OTMG-CT-11
def test_otmg_ct_11__price_0_gives_subtotal_0(db, s):
    """OTMG-CT-11 — a price of 0 gives subtotal 0.00 and is stored as 0.00.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Free", quantity=Decimal("4.00"), unit_price=Decimal("0")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].unit_price == Decimal("0.00")
    assert ls[0].line_subtotal == Decimal("0.00")


# [claude] OTMG-CT-12
def test_otmg_ct_12__quantity_not_sent_is_1(db, s):
    """OTMG-CT-12 — quantity not sent is 1, so the subtotal is the price.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Fee", unit_price=Decimal("12.50")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].quantity == Decimal("1.00")
    assert ls[0].line_subtotal == Decimal("12.50")


# [claude] OTMG-CT-13
def test_otmg_ct_13__13_integer_digits_stored_exactly(db, s):
    """OTMG-CT-13 — 13 integer digits and 2 decimals are stored exactly.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Big", quantity=Decimal("9999999999999.99"), unit_price=Decimal("1.00")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].quantity == Decimal("9999999999999.99")
    assert ls[0].line_subtotal == Decimal("9999999999999.99")


# [claude] OTMG-CT-14
def test_otmg_ct_14__a_255_character_name_is_stored(db, s):
    """OTMG-CT-14 — a 255-character name is stored.
    Rules: create_template R3"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name=N255), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).template_name == N255


# [claude] OTMG-CT-15
def test_otmg_ct_15__name_stored_as_typed_inner_space_and_case_kept(db, s):
    """OTMG-CT-15 — a name without spaces around it is stored as typed, inner space and case kept.
    Rules: create_template R3"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Office  RENT"), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).template_name == "Office  RENT"


# [claude] OTMG-CT-16
@BUG_2355
def test_otmg_ct_16__name_with_spaces_around_is_stored_trimmed(db, s):
    """OTMG-CT-16 — a name with spaces around it is stored trimmed.
    Rules: create_template R3 [BUG-2355]"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="  Rent "), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).template_name == "Rent"


# [claude] OTMG-CT-17
@BUG_2355
def test_otmg_ct_17__whitespace_only_name_refused_by_schema():
    """OTMG-CT-17 — a whitespace-only name is refused by the schema.
    Rules: create_template R3 [BUG-2355]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateCreate(template_name="  ")


# [claude] OTMG-CT-18
@BUG_2355
def test_otmg_ct_18__empty_name_refused_by_schema():
    """OTMG-CT-18 — an empty name is refused by the schema.
    Rules: create_template R3 [BUG-2355]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateCreate(template_name="")


# [claude] OTMG-CT-19
@BUG_2365
def test_otmg_ct_19__256_character_name_refused_by_schema():
    """OTMG-CT-19 — a 256-character name is refused by the schema.
    Rules: create_template R3 [BUG-2365]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateCreate(template_name=N256)


# [claude] OTMG-CT-20
@BUG_2359
def test_otmg_ct_20__unknown_category_refused_by_schema():
    """OTMG-CT-20 — an unknown category is refused by the schema.
    Rules: create_template R4 [BUG-2359]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateCreate(template_name="Rent", expense_category="garbage")


# [claude] OTMG-CT-21
@BUG_2359
def test_otmg_ct_21__category_stored_trimmed_and_lower_cased(db, s):
    """OTMG-CT-21 — a category with spaces and capitals is stored trimmed and lower-cased.
    Rules: create_template R4 [BUG-2359]"""
    f = factory(db, s)
    result = M.create_template(db, data=OrderTemplateCreate(
        template_name="Rent", expense_category=" Factory ", cost_center_id=f.id,
    ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).expense_category == "factory"


# [claude] OTMG-CT-22
def test_otmg_ct_22__department_with_live_department_is_stored(db, s):
    """OTMG-CT-22 — category department with a live department of the workspace is stored.
    Rules: create_template R4, R5, R6"""
    d = dept(db, s)
    result = M.create_template(db, data=OrderTemplateCreate(
        template_name="Rent", expense_category="department", cost_center_id=d.id,
    ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.expense_category == "department"
    assert row.cost_center_id == d.id


# [claude] OTMG-CT-23
@BUG_2360
def test_otmg_ct_23__category_other_drops_the_cost_centre(db, s):
    """OTMG-CT-23 — category other drops the cost centre.
    Rules: create_template R5 [BUG-2360]"""
    f = factory(db, s)
    result = M.create_template(db, data=OrderTemplateCreate(
        template_name="Rent", expense_category="other", cost_center_id=f.id,
    ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.expense_category == "other"
    # Then 3
    assert row.cost_center_id is None


# [claude] OTMG-CT-24
@BUG_2360
def test_otmg_ct_24__no_category_drops_the_cost_centre(db, s):
    """OTMG-CT-24 — no category drops the cost centre.
    Rules: create_template R5 [BUG-2360]"""
    f = factory(db, s)
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", cost_center_id=f.id), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).cost_center_id is None


# [claude] OTMG-CT-25
@BUG_2361
def test_otmg_ct_25__factory_without_cost_centre_is_refused(db, s):
    """OTMG-CT-25 — category factory without a cost centre is refused, nothing written.
    Rules: create_template R5 [BUG-2361], Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this template"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-26
@BUG_2361
def test_otmg_ct_26__department_without_cost_centre_is_refused(db, s):
    """OTMG-CT-26 — category department without a cost centre is refused, nothing written.
    Rules: create_template R5 [BUG-2361], Errors row 2"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a department for this template"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-27
@BUG_1014
def test_otmg_ct_27__account_of_later_workspace_is_refused(db, s):
    """OTMG-CT-27 — an account of a later workspace (W2) is refused.
    Rules: create_template R6 [BUG-1014], Errors row 1"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=ac2.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac2.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-28
@BUG_1014
def test_otmg_ct_28__account_of_earlier_workspace_is_refused(db, s):
    """OTMG-CT-28 — an account of an earlier workspace (W0) is refused.
    Rules: create_template R6 [BUG-1014]"""
    ac0 = account(db, s, workspace_id=s.w0.id, name="Old")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=ac0.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-29
@BUG_2362
def test_otmg_ct_29__closed_account_is_refused(db, s):
    """OTMG-CT-29 — a closed account of the workspace is refused.
    Rules: create_template R6 [BUG-2362]"""
    ac = account(db, s, **CLOSED(s))
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=ac.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-30
@BUG_1014
def test_otmg_ct_30__unknown_account_is_refused_as_not_found(db, s):
    """OTMG-CT-30 — an unknown account is refused as not found.
    Rules: create_template R6 [BUG-1014], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=MISSING), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Account with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-31
@BUG_1216
def test_otmg_ct_31__factory_of_later_workspace_is_refused(db, s):
    """OTMG-CT-31 — a factory of a later workspace (W2) is refused.
    Rules: create_template R6 [BUG-1216]"""
    f2 = factory(db, s, workspace_id=s.w2.id, name="Factory Nine", abbreviation="F9")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=f2.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f2.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-32
@BUG_1216
def test_otmg_ct_32__factory_of_earlier_workspace_is_refused(db, s):
    """OTMG-CT-32 — a factory of an earlier workspace (W0) is refused.
    Rules: create_template R6 [BUG-1216]"""
    f0 = factory(db, s, workspace_id=s.w0.id, name="Factory Zero", abbreviation="F0")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=f0.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-33
@BUG_2362
def test_otmg_ct_33__deleted_factory_is_refused(db, s):
    """OTMG-CT-33 — a deleted factory of the workspace is refused.
    Rules: create_template R6 [BUG-2362]"""
    f = factory(db, s, **DELETED(s))
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=f.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-34
@BUG_1216
def test_otmg_ct_34__department_of_later_workspace_is_refused(db, s):
    """OTMG-CT-34 — a department of a later workspace (W2) is refused.
    Rules: create_template R6 [BUG-1216]"""
    d2 = dept(db, s, workspace_id=s.w2.id, name="Far Sales")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=d2.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Department with ID {d2.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-35
@BUG_1216
def test_otmg_ct_35__department_of_earlier_workspace_is_refused(db, s):
    """OTMG-CT-35 — a department of an earlier workspace (W0) is refused.
    Rules: create_template R6 [BUG-1216]"""
    d0 = dept(db, s, workspace_id=s.w0.id, name="Old Sales")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=d0.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Department with ID {d0.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-36
@BUG_2362
def test_otmg_ct_36__deleted_department_is_refused(db, s):
    """OTMG-CT-36 — a deleted department of the workspace is refused.
    Rules: create_template R6 [BUG-2362]"""
    d = dept(db, s, **DELETED(s))
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=d.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Department with ID {d.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-37
@BUG_1216
def test_otmg_ct_37__department_id_sent_as_factory_is_refused(db, s):
    """OTMG-CT-37 — category factory with the id of a department of the workspace is refused as a factory.
    Rules: create_template R6 [BUG-1216]"""
    dept(db, s, id=880000001)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=880000001, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 880000001 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-38
@BUG_1216
def test_otmg_ct_38__factory_id_sent_as_department_is_refused(db, s):
    """OTMG-CT-38 — category department with the id of a factory of the workspace is refused as a department.
    Rules: create_template R6 [BUG-1216]"""
    factory(db, s, id=880000002)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=880000002, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Department with ID 880000002 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-39
@BUG_1216
def test_otmg_ct_39__approver_of_no_workspace_is_refused(db, s):
    """OTMG-CT-39 — an approver who belongs to no workspace is refused.
    Rules: create_template R6 [BUG-1216]"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=s.uz.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Profile with ID {s.uz.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-40
@BUG_1216
def test_otmg_ct_40__approver_owning_another_workspace_only_is_refused(db, s):
    """OTMG-CT-40 — an approver who is an active owner of another workspace only is refused.
    Rules: create_template R6 [BUG-1216]"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=s.ux.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Profile with ID {s.ux.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-41
@BUG_1216
def test_otmg_ct_41__approver_with_inactive_membership_is_refused(db, s):
    """OTMG-CT-41 — an approver whose membership of the workspace is not active is refused.
    Rules: create_template R6 [BUG-1216]"""
    _member(db, s.w1, s.uz, "manager", status="suspended")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=s.uz.id, items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Profile with ID {s.uz.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-42
@BUG_1216
def test_otmg_ct_42__unknown_approver_is_refused_as_not_found(db, s):
    """OTMG-CT-42 — an unknown approver is refused as not found.
    Rules: create_template R6 [BUG-1216], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=MISSING), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Profile with ID 999999999 not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-43
def test_otmg_ct_43__ground_team_member_accepted_as_approver(db, s):
    """OTMG-CT-43 — a ground-team member of the workspace is accepted as approver.
    Rules: create_template R6"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=s.ug.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).default_approver_id == s.ug.id


# [claude] OTMG-CT-44
@BUG_2363
def test_otmg_ct_44__line_quantity_with_3_decimals_refused():
    """OTMG-CT-44 — line schema: more than 2 decimals in quantity is refused.
    Rules: create_template R8 [BUG-2363]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("1.005"), unit_price=Decimal("10.00"))


# [claude] OTMG-CT-45
@BUG_2363
def test_otmg_ct_45__line_price_with_3_decimals_refused():
    """OTMG-CT-45 — line schema: more than 2 decimals in unit_price is refused.
    Rules: create_template R8 [BUG-2363]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("3"), unit_price=Decimal("0.125"))


# [claude] OTMG-CT-46
@BUG_2363
def test_otmg_ct_46__line_quantity_with_14_integer_digits_refused():
    """OTMG-CT-46 — line schema: 14 integer digits in quantity are refused.
    Rules: create_template R8 [BUG-2363]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("10000000000000"), unit_price=Decimal("1.00"))


# [claude] OTMG-CT-47
@BUG_2363
def test_otmg_ct_47__line_price_with_14_integer_digits_refused():
    """OTMG-CT-47 — line schema: 14 integer digits in unit_price are refused.
    Rules: create_template R8 [BUG-2363]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("1"), unit_price=Decimal("10000000000000"))


# [claude] OTMG-CT-48
@BUG_2364
def test_otmg_ct_48__line_quantity_0_refused():
    """OTMG-CT-48 — line schema: quantity 0 is refused.
    Rules: create_template R8 [BUG-2364]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", quantity=Decimal("0"), unit_price=Decimal("1.00"))


# [claude] OTMG-CT-49
@BUG_2364
def test_otmg_ct_49__line_negative_quantity_refused():
    """OTMG-CT-49 — line schema: a negative quantity is refused.
    Rules: create_template R8 [BUG-2364]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Refund", quantity=Decimal("-2"), unit_price=Decimal("3.00"))


# [claude] OTMG-CT-50
@BUG_2364
def test_otmg_ct_50__line_price_minus_0_01_refused():
    """OTMG-CT-50 — line schema: a price of -0.01 is refused.
    Rules: create_template R8 [BUG-2364]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Refund", quantity=Decimal("1"), unit_price=Decimal("-0.01"))


# [claude] OTMG-CT-51
def test_otmg_ct_51__line_quantity_0_01_and_price_0_accepted():
    """OTMG-CT-51 — line schema: quantity 0.01 and price 0 are accepted.
    Rules: create_template R8; add_item R4"""
    result = OrderTemplateItemCreate(description="Bolt", quantity=Decimal("0.01"), unit_price=Decimal("0"))
    # Then 1
    assert result.quantity == Decimal("0.01")
    assert result.unit_price == Decimal("0")


# [claude] OTMG-CT-52
def test_otmg_ct_52__line_13_integer_digits_accepted():
    """OTMG-CT-52 — line schema: 13 integer digits with 2 decimals are accepted.
    Rules: create_template R8; add_item R4"""
    result = OrderTemplateItemCreate(description="Big", quantity=Decimal("9999999999999.99"), unit_price=Decimal("1.00"))
    # Then 1
    assert result.quantity == Decimal("9999999999999.99")
    assert result.unit_price == Decimal("1.00")


# [claude] OTMG-CT-53
@BUG_2365
def test_otmg_ct_53__line_unit_of_51_characters_refused():
    """OTMG-CT-53 — line schema: a unit of 51 characters is refused.
    Rules: create_template R8 [BUG-2365]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Bolt", unit=U51)


# [claude] OTMG-CT-54
def test_otmg_ct_54__unit_of_50_characters_is_stored(db, s):
    """OTMG-CT-54 — a unit of 50 characters is stored.
    Rules: create_template R8"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Bolt", unit=U50, quantity=Decimal("1.00"), unit_price=Decimal("2.00")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].unit == U50


# [claude] OTMG-CT-55
def test_otmg_ct_55__create_flushes_and_never_commits(db, s):
    """OTMG-CT-55 — create flushes and never commits.
    Rules: create_template Returns, Side effects"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.create_template(db, data=OrderTemplateCreate(template_name="Spy", items=[ITEM]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    result_id = result.id
    # Then 2
    assert count(db, OrderTemplate, OrderTemplate.template_name == "Spy") == 1
    # Then 3
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == result_id) == 1
    # Then 4
    assert cm.call_count == 0
    sp.rollback()
    # Then 5
    assert count(db, OrderTemplate, OrderTemplate.template_name == "Spy") == 0


# [claude] OTMG-CT-56
def test_otmg_ct_56__category_other_without_cost_centre_is_stored(db, s):
    """OTMG-CT-56 — category other without a cost centre is stored.
    Rules: create_template R4, R5"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="other"), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.expense_category == "other"
    assert row.cost_center_id is None


# [claude] OTMG-CT-57
@BUG_2349
def test_otmg_ct_57__line_total_of_10_13_refused():
    """OTMG-CT-57 — line schema: a line total of 10^13 is refused, though each input is valid.
    Rules: create_template R8a [BUG-2349]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Big", quantity=Decimal("10000"), unit_price=Decimal("1000000000"))


# [claude] OTMG-CT-58
@BUG_2349
def test_otmg_ct_58__line_total_rounding_half_up_to_10_13_refused():
    """OTMG-CT-58 — line schema: a total that rounds half up to 10^13 is refused.
    Rules: create_template R8a [BUG-2349]; add_item R4"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemCreate(description="Big", quantity=Decimal("1.01"), unit_price=Decimal("9900990099009.90"))


# [claude] OTMG-CT-59
def test_otmg_ct_59__total_just_below_10_13_is_stored(db, s):
    """OTMG-CT-59 — a total just below 10^13 is stored, rounded half up.
    Rules: create_template R8, R8a"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[
        OrderTemplateItemCreate(description="Big", quantity=Decimal("1.01"), unit_price=Decimal("9900990099009.89")),
    ]), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    ls = new_tpl_lines(db, result)
    assert len(ls) == 1
    assert ls[0].quantity == Decimal("1.01")
    assert ls[0].unit_price == Decimal("9900990099009.89")
    assert ls[0].line_subtotal == Decimal("9999999999999.99")


# [claude] OTMG-CT-60
@BUG_2365
def test_otmg_ct_60__recurrence_type_of_51_refused():
    """OTMG-CT-60 — template schema: a recurrence_type of 51 characters is refused.
    Rules: create_template R3 [BUG-2365]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateCreate(template_name="Rent", recurrence_type=R51)


# [claude] OTMG-CT-61
def test_otmg_ct_61__recurrence_type_of_50_is_stored(db, s):
    """OTMG-CT-61 — a recurrence_type of 50 characters is stored.
    Rules: create_template R2, R3"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", recurrence_type=R50), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rt(db, result.id).recurrence_type == R50


# [claude] OTMG-CT-62
@BUG_2347
def test_otmg_ct_62__non_owner_403_comes_first(db, s):
    """OTMG-CT-62 — order of refusals: a non-owner skipping approval gets 403 before the missing cost centre and the foreign account.
    Rules: create_template R11, R9 [BUG-2347]"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(
            template_name="Rent", requires_approval=False, expense_category="factory", account_id=ac2.id, items=[ITEM],
        ), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-63
@BUG_2361
def test_otmg_ct_63__missing_cost_centre_before_foreign_account(db, s):
    """OTMG-CT-63 — order of refusals: the missing cost centre (400) comes before the foreign account (404).
    Rules: create_template R11, R5 [BUG-2361]"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(
            template_name="Rent", expense_category="factory", account_id=ac2.id, items=[ITEM],
        ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this template"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-64
@BUG_1014
def test_otmg_ct_64__account_404_before_cost_centre_and_approver(db, s):
    """OTMG-CT-64 — order of refusals: the account's 404 comes before the cost centre's and the approver's.
    Rules: create_template R11, R6 [BUG-1014]"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    d2 = dept(db, s, workspace_id=s.w2.id, name="Far")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(
            template_name="Rent", expense_category="department", cost_center_id=d2.id, account_id=ac2.id,
            default_approver_id=s.uz.id, items=[ITEM],
        ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac2.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-CT-65
@BUG_1216
def test_otmg_ct_65__cost_centre_404_before_approver(db, s):
    """OTMG-CT-65 — order of refusals: the cost centre's 404 comes before the approver's.
    Rules: create_template R11, R6 [BUG-1216]"""
    d2 = dept(db, s, workspace_id=s.w2.id, name="Far")
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(
            template_name="Rent", expense_category="department", cost_center_id=d2.id,
            default_approver_id=s.uz.id, items=[ITEM],
        ), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Department with ID {d2.id} not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# =========================================================================== #
# OrderTemplateManager.update_template
# =========================================================================== #

# [claude] OTMG-UT-01
def test_otmg_ut_01__fields_sent_are_applied_and_stamped(db, s):
    """OTMG-UT-01 — fields sent are applied and the update is stamped.
    Rules: update_template R2, R6, Returns"""
    t = tpl(db, s, description="Old", notes="n0", updated_by=s.uo.id, updated_at=T1)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(description="Monthly", notes="n1"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert isinstance(result, OrderTemplate)
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.description == "Monthly"
    assert row.notes == "n1"
    # Then 3
    assert row.updated_by == s.ua.id
    # Then 4
    assert row.updated_at is not None
    assert row.updated_at != T1
    # Then 5
    assert row.template_name == "Rent"
    assert row.created_by == s.uo.id
    assert row.created_at == T0


# [claude] OTMG-UT-02
def test_otmg_ut_02__fields_not_sent_keep_their_values(db, s):
    """OTMG-UT-02 — fields not sent keep their values.
    Rules: update_template R2"""
    ac = account(db, s)
    f = factory(db, s)
    t = tpl(db, s, description="Monthly", account_id=ac.id, expense_category="factory", cost_center_id=f.id,
            default_approver_id=s.ua.id, notes="n0", is_recurring=True, recurrence_type="monthly")
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.template_name == "Lease"
    # Then 3
    assert row.description == "Monthly"
    assert row.notes == "n0"
    # Then 4
    assert row.account_id == ac.id
    assert row.expense_category == "factory"
    assert row.cost_center_id == f.id
    assert row.default_approver_id == s.ua.id
    # Then 5
    assert row.is_recurring is True
    assert row.recurrence_type == "monthly"
    assert row.is_active is True
    # Then 6
    assert row.requires_approval is True
    assert row.auto_approve is False


# [claude] OTMG-UT-03
def test_otmg_ut_03__unknown_id_is_refused(db, s):
    """OTMG-UT-03 — an unknown id is refused, nothing written.
    Rules: update_template R1, Errors"""
    t = tpl(db, s)
    before_t = snap(db, t)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=MISSING, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template with ID 999999999 not found"
    # Then 3
    assert not db.dirty
    assert not db.new
    # Then 4
    assert snap(db, t) == before_t
    # Then 5
    assert written(db) == before


# [claude] OTMG-UT-04
def test_otmg_ut_04__template_of_earlier_workspace_is_refused(db, s):
    """OTMG-UT-04 — a template of an earlier workspace (W0) is refused, nothing written.
    Rules: update_template R1"""
    z = tpl(db, s, workspace_id=s.w0.id)
    tpl(db, s)
    before_z = snap(db, z)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=z.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.dirty
    assert not db.new
    # Then 4
    assert snap(db, z) == before_z
    # Then 5
    assert written(db) == before


# [claude] OTMG-UT-05
def test_otmg_ut_05__template_of_later_workspace_is_refused(db, s):
    """OTMG-UT-05 — a template of a later workspace (W2) is refused, nothing written.
    Rules: update_template R1"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    before_z = snap(db, z)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=z.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.dirty
    assert not db.new
    # Then 4
    assert snap(db, z) == before_z
    # Then 5
    assert written(db) == before


# [claude] OTMG-UT-06
def test_otmg_ut_06__inactive_template_can_be_updated_and_stays_inactive(db, s):
    """OTMG-UT-06 — an inactive template can be updated and stays inactive.
    Rules: update_template R2"""
    t = tpl(db, s, **INACTIVE(s))
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(notes="still here"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.notes == "still here"
    assert row.is_active is False


# [claude] OTMG-UT-07
def test_otmg_ut_07__is_active_true_switches_back_on(db, s):
    """OTMG-UT-07 — is_active true switches an inactive template back on.
    Rules: update_template R2"""
    t = tpl(db, s, **INACTIVE(s))
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(is_active=True), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.is_active is True
    assert row.updated_by == s.ua.id


# [claude] OTMG-UT-08
def test_otmg_ut_08__recurrence_fields_applied_unchecked(db, s):
    """OTMG-UT-08 — recurrence fields and next_generation_date are applied unchecked.
    Rules: update_template R3"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(
        is_recurring=True, recurrence_type="whenever", recurrence_interval=-1, recurrence_day=0,
        start_date=date(2026, 6, 1), end_date=date(2026, 5, 1), next_generation_date=date(2025, 1, 1),
    ), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.is_recurring is True
    assert row.recurrence_type == "whenever"
    assert row.recurrence_interval == -1
    assert row.recurrence_day == 0
    # Then 3
    assert row.start_date == date(2026, 6, 1)
    assert row.end_date == date(2026, 5, 1)
    assert row.next_generation_date == date(2025, 1, 1)


# [claude] OTMG-UT-09
def test_otmg_ut_09__a_255_character_name_is_stored(db, s):
    """OTMG-UT-09 — a 255-character name is stored.
    Rules: update_template R4"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name=N255), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).template_name == N255


# [claude] OTMG-UT-10
@BUG_2355
def test_otmg_ut_10__sent_name_stored_trimmed(db, s):
    """OTMG-UT-10 — a sent name with spaces around it is stored trimmed.
    Rules: update_template R4 [BUG-2355]"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="  Lease "), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).template_name == "Lease"


# [claude] OTMG-UT-11
@BUG_2355
def test_otmg_ut_11__update_schema_whitespace_only_name_refused():
    """OTMG-UT-11 — update schema: a whitespace-only name is refused.
    Rules: update_template R4 [BUG-2355]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(template_name="   ")


# [claude] OTMG-UT-12
@BUG_2365
def test_otmg_ut_12__update_schema_256_character_name_refused():
    """OTMG-UT-12 — update schema: a 256-character name is refused.
    Rules: update_template R4 [BUG-2365]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(template_name=N256)


# [claude] OTMG-UT-13
@BUG_2357
def test_otmg_ut_13__explicit_null_clears_the_description(db, s):
    """OTMG-UT-13 — an explicit null clears the description.
    Rules: update_template R5 [BUG-2357]"""
    t = tpl(db, s, description="d")
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(description=None), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).description is None


# [claude] OTMG-UT-14
@BUG_2357
def test_otmg_ut_14__explicit_null_clears_the_default_approver(db, s):
    """OTMG-UT-14 — an explicit null clears the default approver.
    Rules: update_template R5 [BUG-2357]"""
    t = tpl(db, s, default_approver_id=s.ua.id)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(default_approver_id=None), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).default_approver_id is None


# [claude] OTMG-UT-15
@BUG_2357
def test_otmg_ut_15__explicit_null_clears_the_account(db, s):
    """OTMG-UT-15 — an explicit null clears the account.
    Rules: update_template R5 [BUG-2357]"""
    ac = account(db, s)
    t = tpl(db, s, account_id=ac.id)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(account_id=None), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).account_id is None


# [claude] OTMG-UT-16
@BUG_2357
def test_otmg_ut_16__update_schema_null_name_refused():
    """OTMG-UT-16 — update schema: a null name is refused.
    Rules: update_template R5 [BUG-2357]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(template_name=None)


# [claude] OTMG-UT-17
@BUG_2357
def test_otmg_ut_17__update_schema_null_is_active_refused():
    """OTMG-UT-17 — update schema: a null is_active is refused.
    Rules: update_template R5 [BUG-2357]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(is_active=None)


# [claude] OTMG-UT-18
@BUG_2356
def test_otmg_ut_18__empty_payload_stamps_nothing(db, s):
    """OTMG-UT-18 — an empty payload stamps nothing.
    Rules: update_template R6 [BUG-2356]"""
    t = tpl(db, s)
    t_id = t.id
    before_t = snap(db, t)
    result = M.update_template(db, tpl_id=t_id, data=OrderTemplateUpdate(), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t_id
    # Then 2
    row = rt(db, t_id)
    assert row.updated_by is None
    # Then 3
    assert row.updated_at is None
    # Then 4
    assert snap(db, row) == before_t


# [claude] OTMG-UT-19
@BUG_2356
def test_otmg_ut_19__equal_values_stamp_nothing(db, s):
    """OTMG-UT-19 — values equal to the stored ones stamp nothing.
    Rules: update_template R6 [BUG-2356]"""
    t = tpl(db, s, notes="n0", updated_by=s.uo.id, updated_at=T1)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Rent", notes="n0"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.updated_by == s.uo.id
    # Then 3
    assert row.updated_at == T1


# [claude] OTMG-UT-20
def test_otmg_ut_20__sent_account_of_the_workspace_is_stored(db, s):
    """OTMG-UT-20 — a sent account of the workspace is stored.
    Rules: update_template R7"""
    ac = account(db, s)
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(account_id=ac.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).account_id == ac.id


# [claude] OTMG-UT-21
def test_otmg_ut_21__reference_not_sent_is_not_checked_again(db, s):
    """OTMG-UT-21 — a reference not sent is not checked again.
    Rules: update_template R7"""
    ac = account(db, s, **CLOSED(s))
    t = tpl(db, s, account_id=ac.id)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(notes="kept"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.notes == "kept"
    assert row.account_id == ac.id


# [claude] OTMG-UT-22
@BUG_1014
def test_otmg_ut_22__sent_account_of_later_workspace_is_refused(db, s):
    """OTMG-UT-22 — a sent account of a later workspace (W2) is refused.
    Rules: update_template R7 [BUG-1014]"""
    t = tpl(db, s)
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(account_id=ac2.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac2.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-23
@BUG_1014
def test_otmg_ut_23__sent_account_of_earlier_workspace_is_refused(db, s):
    """OTMG-UT-23 — a sent account of an earlier workspace (W0) is refused.
    Rules: update_template R7 [BUG-1014]"""
    ac0 = account(db, s, workspace_id=s.w0.id, name="Old")
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(account_id=ac0.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac0.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-24
@BUG_2362
def test_otmg_ut_24__sent_closed_account_is_refused(db, s):
    """OTMG-UT-24 — a sent closed account is refused.
    Rules: update_template R7 [BUG-2362]"""
    ac = account(db, s, **CLOSED(s))
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(account_id=ac.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-25
@BUG_1216
def test_otmg_ut_25__sent_factory_of_another_workspace_is_refused(db, s):
    """OTMG-UT-25 — a sent factory of another workspace is refused on a factory template.
    Rules: update_template R7 [BUG-1216]"""
    f = factory(db, s)
    t = tpl(db, s, expense_category="factory", cost_center_id=f.id)
    f2 = factory(db, s, workspace_id=s.w2.id, name="Factory Nine", abbreviation="F9")
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(cost_center_id=f2.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Factory with ID {f2.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-26
@BUG_1216
def test_otmg_ut_26__sent_approver_owning_another_workspace_only_is_refused(db, s):
    """OTMG-UT-26 — a sent approver who is an active owner of another workspace only is refused.
    Rules: update_template R7 [BUG-1216]"""
    t = tpl(db, s, default_approver_id=s.ua.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(default_approver_id=s.ux.id), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Profile with ID {s.ux.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-27
@BUG_1216
def test_otmg_ut_27__sent_approver_of_no_workspace_is_refused(db, s):
    """OTMG-UT-27 — a sent approver who belongs to no workspace is refused.
    Rules: update_template R7 [BUG-1216]"""
    t = tpl(db, s, default_approver_id=s.ua.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(default_approver_id=s.uz.id), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Profile with ID {s.uz.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-28
def test_otmg_ut_28__category_and_cost_centre_sent_together_are_stored(db, s):
    """OTMG-UT-28 — category and cost centre sent together on a template without them are stored.
    Rules: update_template R8"""
    f = factory(db, s)
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="factory", cost_center_id=f.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.expense_category == "factory"
    assert row.cost_center_id == f.id


# [claude] OTMG-UT-29
@BUG_2360
def test_otmg_ut_29__factory_template_changed_to_other_drops_cost_centre(db, s):
    """OTMG-UT-29 — a factory template changed to category other drops its cost centre.
    Rules: update_template R8 [BUG-2360]"""
    f = factory(db, s)
    t = tpl(db, s, expense_category="factory", cost_center_id=f.id)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="other"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.expense_category == "other"
    # Then 3
    assert row.cost_center_id is None


# [claude] OTMG-UT-30
@BUG_2361
def test_otmg_ut_30__factory_sent_without_cost_centre_is_refused(db, s):
    """OTMG-UT-30 — category factory sent on a template with no cost centre is refused.
    Rules: update_template R8 [BUG-2361]"""
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="factory"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this template"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-31
def test_otmg_ut_31__department_template_keeps_cost_centre_on_rename(db, s):
    """OTMG-UT-31 — a department template keeps its stored cost centre when only the name changes.
    Rules: update_template R8 (merged state)"""
    d = dept(db, s)
    t = tpl(db, s, expense_category="department", cost_center_id=d.id)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.template_name == "Lease"
    assert row.expense_category == "department"
    assert row.cost_center_id == d.id


# [claude] OTMG-UT-32
@BUG_2359
def test_otmg_ut_32__update_schema_unknown_category_refused():
    """OTMG-UT-32 — update schema: an unknown category is refused.
    Rules: update_template R8 [BUG-2359]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(expense_category="garbage")


# [claude] OTMG-UT-33
@BUG_2359
def test_otmg_ut_33__sent_category_stored_trimmed_and_lower_cased(db, s):
    """OTMG-UT-33 — a sent category with spaces and capitals is stored trimmed and lower-cased.
    Rules: update_template R8 [BUG-2359]"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category=" Other "), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert rt(db, t.id).expense_category == "other"


# [claude] OTMG-UT-34
def test_otmg_ut_34__lines_are_not_touched(db, s):
    """OTMG-UT-34 — the template's lines are not touched.
    Rules: update_template R10"""
    t = tpl(db, s)
    l1 = line(db, s, t, 1)
    l2 = line(db, s, t, 2, quantity=Decimal("2.00"), line_subtotal=Decimal("20.00"))
    before_l1 = snap(db, l1)
    before_l2 = snap(db, l2)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Lease", is_active=False), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert snap(db, l1) == before_l1
    # Then 3
    assert snap(db, l2) == before_l2
    # Then 4
    assert len(lines(db, t.id)) == 2


# [claude] OTMG-UT-35
def test_otmg_ut_35__update_flushes_and_never_commits(db, s):
    """OTMG-UT-35 — update flushes and never commits.
    Rules: update_template Side effects"""
    t = tpl(db, s)
    t_id = t.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.update_template(db, tpl_id=t_id, data=OrderTemplateUpdate(template_name="Spy"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t_id
    # Then 2
    assert count(db, OrderTemplate, OrderTemplate.template_name == "Spy") == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert rt(db, t_id).template_name == "Rent"


# [claude] OTMG-UT-36
def test_otmg_ut_36__category_other_without_cost_centre_is_stored(db, s):
    """OTMG-UT-36 — category other sent on a template without a cost centre is stored.
    Rules: update_template R8"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="other"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.expense_category == "other"
    assert row.cost_center_id is None


# [claude] OTMG-UT-37
@BUG_2365
def test_otmg_ut_37__update_schema_recurrence_type_of_51_refused():
    """OTMG-UT-37 — update schema: a recurrence_type of 51 characters is refused.
    Rules: update_template R4 [BUG-2365]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateUpdate(recurrence_type=R51)


# [claude] OTMG-UT-38
@BUG_2361
def test_otmg_ut_38__null_cost_centre_on_factory_template_gets_400(db, s):
    """OTMG-UT-38 — a null cost centre on a factory template gets the missing-cost-centre 400.
    Rules: update_template R5, R8 [BUG-2361]"""
    f = factory(db, s)
    t = tpl(db, s, expense_category="factory", cost_center_id=f.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(cost_center_id=None), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this template"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-39
@BUG_2361
def test_otmg_ut_39__null_cost_centre_on_department_template_gets_400(db, s):
    """OTMG-UT-39 — a null cost centre on a department template gets the missing-cost-centre 400.
    Rules: update_template R5, R8 [BUG-2361]"""
    d = dept(db, s)
    t = tpl(db, s, expense_category="department", cost_center_id=d.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(cost_center_id=None), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a department for this template"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-40
@BUG_1216
def test_otmg_ut_40__department_cost_centre_kept_while_moving_to_factory_is_refused(db, s):
    """OTMG-UT-40 — a department cost centre kept while the category moves to factory is refused as no such factory.
    Rules: update_template R8a [BUG-1216]"""
    d = dept(db, s, id=880000001)
    t = tpl(db, s, expense_category="department", cost_center_id=d.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="factory"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Factory with ID 880000001 not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-41
@BUG_1216
def test_otmg_ut_41__factory_cost_centre_kept_while_moving_to_department_is_refused(db, s):
    """OTMG-UT-41 — a factory cost centre kept while the category moves to department is refused as no such department.
    Rules: update_template R8a [BUG-1216]"""
    f = factory(db, s, id=880000002)
    t = tpl(db, s, expense_category="factory", cost_center_id=f.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="department"), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Department with ID 880000002 not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-42
def test_otmg_ut_42__other_workspaces_template_404_before_403(db, s):
    """OTMG-UT-42 — order of refusals: another workspace's template gives 404 before a non-owner's 403.
    Rules: update_template R11, R1"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    before_z = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=z.id, data=OrderTemplateUpdate(requires_approval=False, expense_category="factory"), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, z) == before_z


# [claude] OTMG-UT-43
@BUG_2347
def test_otmg_ut_43__non_owner_403_before_missing_cost_centre(db, s):
    """OTMG-UT-43 — order of refusals: a non-owner's 403 comes before the missing cost centre.
    Rules: update_template R11, R9 [BUG-2347]"""
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(requires_approval=False, expense_category="factory"), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-44
@BUG_2361
def test_otmg_ut_44__missing_cost_centre_before_foreign_account(db, s):
    """OTMG-UT-44 — order of refusals: the missing cost centre (400) comes before the foreign account (404).
    Rules: update_template R11, R8 [BUG-2361]"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="factory", account_id=ac2.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 400
    assert exc.value.detail == "Select a factory for this template"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-45
@BUG_1014
def test_otmg_ut_45__account_404_before_cost_centre(db, s):
    """OTMG-UT-45 — order of refusals: the account's 404 comes before the cost centre's.
    Rules: update_template R11, R7 [BUG-1014]"""
    ac2 = account(db, s, workspace_id=s.w2.id, name="Far")
    d2 = dept(db, s, workspace_id=s.w2.id, name="Far")
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(expense_category="department", cost_center_id=d2.id, account_id=ac2.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Account with ID {ac2.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-UT-46
@BUG_1216
def test_otmg_ut_46__cost_centre_404_before_approver(db, s):
    """OTMG-UT-46 — order of refusals: the cost centre's 404 comes before the approver's.
    Rules: update_template R11, R7 [BUG-1216]"""
    d = dept(db, s)
    d2 = dept(db, s, workspace_id=s.w2.id, name="Far")
    t = tpl(db, s, expense_category="department", cost_center_id=d.id)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(cost_center_id=d2.id, default_approver_id=s.uz.id), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Department with ID {d2.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# =========================================================================== #
# OrderTemplateManager.get_template
# =========================================================================== #

# [claude] OTMG-GT-01
def test_otmg_gt_01__returns_the_workspaces_template(db, s):
    """OTMG-GT-01 — returns the workspace's template.
    Rules: get_template R1"""
    tpl(db, s, workspace_id=s.w0.id)
    t = tpl(db, s, template_name="Lease")
    result = M.get_template(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert isinstance(result, OrderTemplate)
    # Then 2
    assert result.id == t.id
    assert result.template_name == "Lease"
    assert result.workspace_id == s.w1.id


# [claude] OTMG-GT-02
def test_otmg_gt_02__inactive_template_is_returned(db, s):
    """OTMG-GT-02 — an inactive template is returned.
    Rules: get_template R1"""
    t = tpl(db, s, **INACTIVE(s))
    result = M.get_template(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert result.id == t.id
    assert result.is_active is False


# [claude] OTMG-GT-03
def test_otmg_gt_03__unknown_id_raises_404(db, s):
    """OTMG-GT-03 — an unknown id raises 404.
    Rules: get_template R2"""
    tpl(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=MISSING, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template with ID 999999999 not found"


# [claude] OTMG-GT-04
def test_otmg_gt_04__template_of_earlier_workspace_raises_404(db, s):
    """OTMG-GT-04 — a template of an earlier workspace (W0) raises 404.
    Rules: get_template R2"""
    z = tpl(db, s, workspace_id=s.w0.id)
    tpl(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=z.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"


# [claude] OTMG-GT-05
def test_otmg_gt_05__template_of_later_workspace_raises_404(db, s):
    """OTMG-GT-05 — a template of a later workspace (W2) raises 404.
    Rules: get_template R2"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_template(db, tpl_id=z.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"


# [claude] OTMG-GT-06
def test_otmg_gt_06__writes_nothing(db, s):
    """OTMG-GT-06 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: get_template (reader)"""
    t = tpl(db, s)
    b = tpl(db, s, template_name="Lease")
    p = pending_p(db, s)
    b.notes = "edited"
    result = M.get_template(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    assert p in db.new
    assert p.id is None
    assert len(db.new) == 1
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1
    assert not db.deleted


# =========================================================================== #
# OrderTemplateManager.list_templates
# =========================================================================== #

# [claude] OTMG-LT-01
def test_otmg_lt_01__defaults_list_active_and_inactive_newest_first(db, s):
    """OTMG-LT-01 — with the manager's defaults: active and inactive templates of the workspace, newest first.
    Rules: list_templates R1"""
    a = tpl(db, s, created_at=T1)
    b = tpl(db, s, **{**INACTIVE(s), "template_name": "Lease", "created_at": T2})
    result = M.list_templates(db, workspace_id=s.w1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert [t.id for t in result] == [b.id, a.id]


# [claude] OTMG-LT-02
def test_otmg_lt_02__other_workspaces_are_not_listed(db, s):
    """OTMG-LT-02 — templates of an earlier (W0) and a later (W2) workspace are not listed.
    Rules: list_templates R1"""
    tpl(db, s, workspace_id=s.w0.id, created_at=T3)
    a = tpl(db, s, created_at=T1)
    tpl(db, s, workspace_id=s.w2.id, created_at=T2)
    result = M.list_templates(db, workspace_id=s.w1.id)
    # Then 1
    assert [t.id for t in result] == [a.id]


# [claude] OTMG-LT-03
def test_otmg_lt_03__is_active_true_is_passed_through(db, s):
    """OTMG-LT-03 — is_active=True is passed through.
    Rules: list_templates R1"""
    a = tpl(db, s, created_at=T1)
    tpl(db, s, **{**INACTIVE(s), "template_name": "Lease", "created_at": T2})
    result = M.list_templates(db, workspace_id=s.w1.id, is_active=True)
    # Then 1
    assert [t.id for t in result] == [a.id]


# [claude] OTMG-LT-04
def test_otmg_lt_04__is_active_false_and_category_passed_through(db, s):
    """OTMG-LT-04 — is_active=False and the category are passed through together.
    Rules: list_templates R1"""
    a = tpl(db, s, **{**INACTIVE(s), "expense_category": "factory", "created_at": T1})
    tpl(db, s, **{**INACTIVE(s), "template_name": "Lease", "expense_category": "other", "created_at": T2})
    tpl(db, s, template_name="Power", expense_category="factory", created_at=T3)
    result = M.list_templates(db, workspace_id=s.w1.id, is_active=False, expense_category="factory")
    # Then 1
    assert [t.id for t in result] == [a.id]


# [claude] OTMG-LT-05
def test_otmg_lt_05__skip_and_limit_are_passed_through(db, s):
    """OTMG-LT-05 — skip and limit are passed through.
    Rules: list_templates R1"""
    tpl(db, s, created_at=T1)
    tpl(db, s, template_name="Lease", created_at=T3)
    c = tpl(db, s, template_name="Power", created_at=T2)
    result = M.list_templates(db, workspace_id=s.w1.id, skip=1, limit=1)
    # Then 1
    assert [t.id for t in result] == [c.id]


def _e101(db, s):
    """Given of LT-06 / LT-07: 101 templates by add_all; returns `newest` (E101 ... E1 ids)."""
    rows = [
        OrderTemplate(workspace_id=s.w1.id, template_name=f"Rent {k}", requires_approval=True, auto_approve=False,
                      created_by=s.uo.id, created_at=T0 + timedelta(minutes=k))
        for k in range(1, 102)
    ]
    db.add_all(rows)
    db.flush()
    return [r.id for r in reversed(rows)]


# [claude] OTMG-LT-06
def test_otmg_lt_06__default_limit_is_100(db, s):
    """OTMG-LT-06 — the default limit is 100: 101 templates give the newest 100.
    Rules: list_templates R1"""
    newest = _e101(db, s)
    result = M.list_templates(db, workspace_id=s.w1.id)
    # Then 1
    assert len(result) == 100
    # Then 2
    assert [t.id for t in result] == newest[:100]


# [claude] OTMG-LT-07
def test_otmg_lt_07__limit_1000_gives_all_101(db, s):
    """OTMG-LT-07 — limit=1000 gives all 101.
    Rules: list_templates R1"""
    newest = _e101(db, s)
    result = M.list_templates(db, workspace_id=s.w1.id, limit=1000)
    # Then 1
    assert len(result) == 101
    # Then 2
    assert [t.id for t in result] == newest


# [claude] OTMG-LT-08
def test_otmg_lt_08__writes_nothing(db, s):
    """OTMG-LT-08 — writes nothing: a pending row stays pending, an unflushed edit stays dirty.
    Rules: list_templates (reader)"""
    a = tpl(db, s, created_at=T1)
    b = tpl(db, s, workspace_id=s.w2.id, created_at=T1)
    p = pending_p(db, s)
    b.notes = "edited"
    result = M.list_templates(db, workspace_id=s.w1.id)
    # Then 1
    assert [t.id for t in result] == [a.id]
    # Then 2
    assert p in db.new
    assert p.id is None
    assert len(db.new) == 1
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1


# =========================================================================== #
# OrderTemplateManager.delete_template
# =========================================================================== #

# [claude] OTMG-DT-01
def test_otmg_dt_01__active_template_switched_off_and_stamped(db, s):
    """OTMG-DT-01 — an active template is switched off and stamped; it and its lines stay.
    Rules: delete_template R2, Returns"""
    t = tpl(db, s)
    l1 = line(db, s, t, 1)
    line(db, s, t, 2)
    before_l1 = snap(db, l1)
    result = M.delete_template(db, tpl_id=t.id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result is None
    # Then 2
    row = rt(db, t.id)
    assert row.is_active is False
    assert row.updated_by == s.ua.id
    assert row.updated_at is not None
    # Then 3
    assert row.template_name == "Rent"
    assert row.created_by == s.uo.id
    # Then 4
    assert len(lines(db, t.id)) == 2
    # Then 5
    assert snap(db, l1) == before_l1


# [claude] OTMG-DT-02
def test_otmg_dt_02__unknown_id_is_refused(db, s):
    """OTMG-DT-02 — an unknown id is refused, nothing written.
    Rules: delete_template R1"""
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=MISSING, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template with ID 999999999 not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-DT-03
def test_otmg_dt_03__template_of_earlier_workspace_is_refused(db, s):
    """OTMG-DT-03 — a template of an earlier workspace (W0) is refused, nothing written.
    Rules: delete_template R1"""
    z = tpl(db, s, workspace_id=s.w0.id)
    tpl(db, s)
    before_z = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=z.id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, z) == before_z


# [claude] OTMG-DT-04
def test_otmg_dt_04__template_of_later_workspace_is_refused(db, s):
    """OTMG-DT-04 — a template of a later workspace (W2) is refused, nothing written.
    Rules: delete_template R1"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    before_z = snap(db, z)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_template(db, tpl_id=z.id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, z) == before_z


# [claude] OTMG-DT-05
def test_otmg_dt_05__already_inactive_template_writes_nothing(db, s):
    """OTMG-DT-05 — an already inactive template: no error, nothing written, the first deleter kept.
    Rules: delete_template R3"""
    t = tpl(db, s, **INACTIVE(s))
    t_id = t.id
    before_t = snap(db, t)
    result = M.delete_template(db, tpl_id=t_id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result is None
    # Then 2
    assert not db.dirty
    # Then 3
    row = rt(db, t_id)
    assert row.updated_by == s.uo.id
    assert row.updated_at == T1
    assert row.is_active is False
    # Then 4
    assert snap(db, row) == before_t


# [claude] OTMG-DT-06
def test_otmg_dt_06__expense_orders_from_the_template_are_not_touched(db, s):
    """OTMG-DT-06 — expense orders made from the template are not touched.
    Rules: delete_template R4"""
    t = tpl(db, s)
    e = _add(db, ExpenseOrder(workspace_id=s.w1.id, expense_number="EXP-1", expense_category="other",
                              created_by=s.uo.id, order_template_id=t.id))
    e_id = e.id
    before_e = snap(db, e)
    result = M.delete_template(db, tpl_id=t.id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result is None
    # Then 2
    row = reread(db, ExpenseOrder, e_id)
    assert row.order_template_id == t.id
    # Then 3
    assert snap(db, row) == before_e


# [claude] OTMG-DT-07
def test_otmg_dt_07__delete_flushes_and_never_commits(db, s):
    """OTMG-DT-07 — delete flushes and never commits.
    Rules: delete_template Side effects"""
    t = tpl(db, s)
    t_id = t.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.delete_template(db, tpl_id=t_id, workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result is None
    # Then 2
    assert count(db, OrderTemplate, OrderTemplate.id == t_id, OrderTemplate.is_active.is_(False)) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    row = rt(db, t_id)
    assert row.is_active is True
    assert row.updated_by is None


# =========================================================================== #
# OrderTemplateManager.add_item
# =========================================================================== #

# [claude] OTMG-AI-01
def test_otmg_ai_01__first_line_gets_number_1_and_every_field(db, s):
    """OTMG-AI-01 — the first line of a template gets number 1 and every field sent.
    Rules: add_item R2, R3, R4, Returns"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(
        description="Bolt", unit="pcs", quantity=Decimal("2.00"), unit_price=Decimal("5.00"), notes="m6",
    ), workspace_id=s.w1.id)
    # Then 1
    assert isinstance(result, OrderTemplateItem)
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.line_number == 1
    assert row.workspace_id == s.w1.id
    assert row.order_template_id == t.id
    # Then 3
    assert row.description == "Bolt"
    assert row.unit == "pcs"
    assert row.notes == "m6"
    # Then 4
    assert row.quantity == Decimal("2.00")
    assert row.unit_price == Decimal("5.00")
    assert row.line_subtotal == Decimal("10.00")


# [claude] OTMG-AI-02
def test_otmg_ai_02__lines_1_2_3_give_number_4(db, s):
    """OTMG-AI-02 — lines 1, 2, 3 give number 4.
    Rules: add_item R2"""
    t = tpl(db, s)
    line(db, s, t, 1)
    line(db, s, t, 2)
    line(db, s, t, 3)
    result = M.add_item(db, tpl_id=t.id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rl(db, result.id).line_number == 4


# [claude] OTMG-AI-03
def test_otmg_ai_03__highest_number_counts_not_the_count(db, s):
    """OTMG-AI-03 — the highest number counts, not the number of lines: lines 2, 3, 4 give 5.
    Rules: add_item R2"""
    t = tpl(db, s)
    l2 = line(db, s, t, 2)
    line(db, s, t, 3)
    line(db, s, t, 4)
    before_l2 = snap(db, l2)
    result = M.add_item(db, tpl_id=t.id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rl(db, result.id).line_number == 5
    # Then 3
    assert snap(db, l2) == before_l2


# [claude] OTMG-AI-04
def test_otmg_ai_04__highest_number_counts_not_the_newest(db, s):
    """OTMG-AI-04 — the highest number counts, not the newest line: lines built as 3 then 1 give 4.
    Rules: add_item R2"""
    t = tpl(db, s)
    line(db, s, t, 3)
    line(db, s, t, 1)
    result = M.add_item(db, tpl_id=t.id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rl(db, result.id).line_number == 4


# [claude] OTMG-AI-05
def test_otmg_ai_05__other_templates_line_numbers_do_not_count(db, s):
    """OTMG-AI-05 — another template's higher line numbers do not count.
    Rules: add_item R2"""
    sx = tpl(db, s, template_name="Lease")
    t = tpl(db, s)
    line(db, s, sx, 9)
    line(db, s, t, 1)
    result = M.add_item(db, tpl_id=t.id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.line_number == 2
    assert row.order_template_id == t.id


# [claude] OTMG-AI-06
def test_otmg_ai_06__inactive_template_accepts_a_line(db, s):
    """OTMG-AI-06 — an inactive template accepts a line.
    Rules: add_item R3"""
    t = tpl(db, s, **INACTIVE(s))
    t_id = t.id
    result = M.add_item(db, tpl_id=t_id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.order_template_id == t_id
    assert row.line_number == 1
    # Then 3
    assert rt(db, t_id).is_active is False


# [claude] OTMG-AI-07
def test_otmg_ai_07__unknown_template_is_refused(db, s):
    """OTMG-AI-07 — an unknown template is refused, nothing written.
    Rules: add_item R1"""
    tpl(db, s)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=MISSING, data=ITEM, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-AI-08
def test_otmg_ai_08__template_of_earlier_workspace_is_refused(db, s):
    """OTMG-AI-08 — a template of an earlier workspace (W0) is refused, nothing written.
    Rules: add_item R1"""
    z = tpl(db, s, workspace_id=s.w0.id)
    tpl(db, s)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=z.id, data=ITEM, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-AI-09
def test_otmg_ai_09__template_of_later_workspace_is_refused(db, s):
    """OTMG-AI-09 — a template of a later workspace (W2) is refused, nothing written.
    Rules: add_item R1"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.add_item(db, tpl_id=z.id, data=ITEM, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template not found"
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-AI-10
def test_otmg_ai_10__product_ending_in_5_rounds_half_up(db, s):
    """OTMG-AI-10 — a product ending in 5 rounds half up: 0.50 x 0.25 gives 0.13.
    Rules: add_item R4 (HR-15)"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(description="Washer", quantity=Decimal("0.50"), unit_price=Decimal("0.25")), workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rl(db, result.id).line_subtotal == Decimal("0.13")


# [claude] OTMG-AI-11
def test_otmg_ai_11__product_below_the_half_rounds_down(db, s):
    """OTMG-AI-11 — a product below the half rounds down: 0.30 x 0.41 gives 0.12.
    Rules: add_item R4 (HR-15)"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(description="Low", quantity=Decimal("0.30"), unit_price=Decimal("0.41")), workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert rl(db, result.id).line_subtotal == Decimal("0.12")


# [claude] OTMG-AI-12
def test_otmg_ai_12__no_price_gives_subtotal_0(db, s):
    """OTMG-AI-12 — a line with no price has subtotal 0.00 and keeps its price empty.
    Rules: add_item R4"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(description="Labour", quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.unit_price is None
    assert row.line_subtotal == Decimal("0.00")


# [claude] OTMG-AI-13
def test_otmg_ai_13__quantity_not_sent_is_1(db, s):
    """OTMG-AI-13 — quantity not sent is 1, so the subtotal is the price.
    Rules: add_item R4"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(description="Fee", unit_price=Decimal("12.50")), workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.quantity == Decimal("1.00")
    assert row.line_subtotal == Decimal("12.50")


# [claude] OTMG-AI-14
def test_otmg_ai_14__price_0_gives_subtotal_0(db, s):
    """OTMG-AI-14 — a price of 0 gives subtotal 0.00.
    Rules: add_item R4"""
    t = tpl(db, s)
    result = M.add_item(db, tpl_id=t.id, data=OrderTemplateItemCreate(description="Free", quantity=Decimal("4.00"), unit_price=Decimal("0")), workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rl(db, result.id)
    assert row.unit_price == Decimal("0.00")
    assert row.line_subtotal == Decimal("0.00")


# [claude] OTMG-AI-15
def test_otmg_ai_15__add_flushes_and_never_commits(db, s):
    """OTMG-AI-15 — add flushes and never commits.
    Rules: add_item Returns"""
    t = tpl(db, s)
    t_id = t.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.add_item(db, tpl_id=t_id, data=ITEM, workspace_id=s.w1.id)
    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == t_id) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert count(db, OrderTemplateItem, OrderTemplateItem.order_template_id == t_id) == 0


# =========================================================================== #
# OrderTemplateManager.update_item
# =========================================================================== #

# [claude] OTMG-UI-01
def test_otmg_ui_01__quantity_sent_times_stored_price(db, s):
    """OTMG-UI-01 — quantity sent: subtotal is the new quantity x the stored price.
    Rules: update_item R2, R4, Returns"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 1
    assert isinstance(result, OrderTemplateItem)
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("4.00")
    assert row.unit_price == Decimal("10.00")
    # Then 3
    assert row.line_subtotal == Decimal("40.00")


# [claude] OTMG-UI-02
def test_otmg_ui_02__price_sent_times_stored_quantity(db, s):
    """OTMG-UI-02 — price sent: subtotal is the stored quantity x the new price.
    Rules: update_item R4"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("2.50")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("3.00")
    assert row.unit_price == Decimal("2.50")
    # Then 3
    assert row.line_subtotal == Decimal("7.50")


# [claude] OTMG-UI-03
def test_otmg_ui_03__both_sent(db, s):
    """OTMG-UI-03 — both sent: subtotal is the new quantity x the new price.
    Rules: update_item R4"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("2.00"), unit_price=Decimal("1.25")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).line_subtotal == Decimal("2.50")


# [claude] OTMG-UI-04
def test_otmg_ui_04__neither_sent_subtotal_not_recomputed(db, s):
    """OTMG-UI-04 — neither sent: the subtotal is not recomputed, even when it disagrees with the stored values.
    Rules: update_item R2, R4"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, line_subtotal=Decimal("99.00"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(description="Hex bolt"), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.description == "Hex bolt"
    # Then 3
    assert row.line_subtotal == Decimal("99.00")
    assert row.quantity == Decimal("3.00")
    assert row.unit_price == Decimal("10.00")


# [claude] OTMG-UI-05
def test_otmg_ui_05__fields_not_sent_keep_their_values(db, s):
    """OTMG-UI-05 — fields not sent keep their values.
    Rules: update_item R2"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, unit="pcs", notes="n0")
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit="kg"), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.unit == "kg"
    # Then 3
    assert row.notes == "n0"
    assert row.description == "Line"
    assert row.line_number == 1
    assert row.order_template_id == t.id
    # Then 4
    assert row.line_subtotal == Decimal("30.00")


# [claude] OTMG-UI-06
def test_otmg_ui_06__stored_empty_price_counts_as_0(db, s):
    """OTMG-UI-06 — a stored empty price counts as 0 when only the quantity is sent.
    Rules: update_item R4"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, unit_price=None, line_subtotal=Decimal("0.00"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("5.00")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("5.00")
    assert row.unit_price is None
    # Then 3
    assert row.line_subtotal == Decimal("0.00")


# [claude] OTMG-UI-07
def test_otmg_ui_07__new_quantity_on_stored_price_rounds_half_up(db, s):
    """OTMG-UI-07 — a new quantity on a stored price rounds half up: 0.50 x 0.25 gives 0.13.
    Rules: update_item R4 (HR-15)"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, unit_price=Decimal("0.25"), line_subtotal=Decimal("0.75"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("0.50")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).line_subtotal == Decimal("0.13")


# [claude] OTMG-UI-08
def test_otmg_ui_08__new_price_below_the_half_rounds_down(db, s):
    """OTMG-UI-08 — a new price on a stored quantity below the half rounds down: 0.30 x 0.41 gives 0.12.
    Rules: update_item R4 (HR-15)"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("0.30"), line_subtotal=Decimal("3.00"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0.41")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).line_subtotal == Decimal("0.12")


# [claude] OTMG-UI-09
def test_otmg_ui_09__new_price_above_the_half_rounds_up(db, s):
    """OTMG-UI-09 — a new price on a stored quantity above the half rounds up: 0.30 x 0.42 gives 0.13.
    Rules: update_item R4 (HR-15)"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("0.30"), line_subtotal=Decimal("3.00"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0.42")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).line_subtotal == Decimal("0.13")


# [claude] OTMG-UI-10
def test_otmg_ui_10__line_of_inactive_template_is_updated(db, s):
    """OTMG-UI-10 — a line of an inactive template is updated.
    Rules: update_item R2"""
    t = tpl(db, s, **INACTIVE(s))
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("1.00")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("1.00")
    assert row.line_subtotal == Decimal("10.00")


# [claude] OTMG-UI-11
def test_otmg_ui_11__unknown_line_is_refused(db, s):
    """OTMG-UI-11 — an unknown line is refused, nothing written.
    Rules: update_item R1"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    before_l = snap(db, lx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=MISSING, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, lx) == before_l


# [claude] OTMG-UI-12
def test_otmg_ui_12__line_of_earlier_workspace_is_refused(db, s):
    """OTMG-UI-12 — a line of an earlier workspace (W0) is refused, nothing written.
    Rules: update_item R1"""
    z = tpl(db, s, workspace_id=s.w0.id)
    zl = line(db, s, z, 1, workspace_id=s.w0.id)
    t = tpl(db, s)
    line(db, s, t, 1)
    before_zl = snap(db, zl)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=zl.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, zl) == before_zl


# [claude] OTMG-UI-13
def test_otmg_ui_13__line_of_later_workspace_is_refused(db, s):
    """OTMG-UI-13 — a line of a later workspace (W2) is refused, nothing written.
    Rules: update_item R1"""
    t = tpl(db, s)
    line(db, s, t, 1)
    z = tpl(db, s, workspace_id=s.w2.id)
    zl = line(db, s, z, 1, workspace_id=s.w2.id)
    before_zl = snap(db, zl)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=zl.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, zl) == before_zl


# [claude] OTMG-UI-14
def test_otmg_ui_14__price_0_is_stored_as_0(db, s):
    """OTMG-UI-14 — a price of 0 is stored as 0.00.
    Rules: update_item R2, R5"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.unit_price == Decimal("0.00")
    assert row.quantity == Decimal("3.00")


# [claude] OTMG-UI-15
@BUG_1226
def test_otmg_ui_15__price_0_gives_subtotal_0(db, s):
    """OTMG-UI-15 — a price of 0 gives subtotal 0.00.
    Rules: update_item R5 [BUG-1226]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).line_subtotal == Decimal("0.00")


# [claude] OTMG-UI-16
@BUG_2358
def test_otmg_ui_16__explicit_null_clears_the_description(db, s):
    """OTMG-UI-16 — an explicit null clears the description.
    Rules: update_item R3 [BUG-2358]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(description=None), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    assert rl(db, lx.id).description is None


# [claude] OTMG-UI-17
@BUG_2358
def test_otmg_ui_17__explicit_null_clears_the_price(db, s):
    """OTMG-UI-17 — an explicit null clears the price and the subtotal becomes 0.00.
    Rules: update_item R3, R6 [BUG-2358]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=None), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.unit_price is None
    # Then 3
    assert row.line_subtotal == Decimal("0.00")


# [claude] OTMG-UI-18
@BUG_2358
def test_otmg_ui_18__line_update_schema_null_quantity_refused():
    """OTMG-UI-18 — line update schema: a null quantity is refused.
    Rules: update_item R3 [BUG-2358]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemUpdate(quantity=None)


# [claude] OTMG-UI-19
@BUG_2363
def test_otmg_ui_19__line_update_schema_price_with_3_decimals_refused():
    """OTMG-UI-19 — line update schema: more than 2 decimals in the price are refused.
    Rules: update_item R4 [BUG-2363]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemUpdate(unit_price=Decimal("0.125"))


# [claude] OTMG-UI-20
@BUG_2364
def test_otmg_ui_20__line_update_schema_quantity_0_refused():
    """OTMG-UI-20 — line update schema: quantity 0 is refused.
    Rules: update_item R4 [BUG-2364]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemUpdate(quantity=Decimal("0"))


# [claude] OTMG-UI-21
@BUG_2364
def test_otmg_ui_21__line_update_schema_negative_price_refused():
    """OTMG-UI-21 — line update schema: a negative price is refused.
    Rules: update_item R4 [BUG-2364]"""
    # Then 1
    with pytest.raises(ValidationError):
        OrderTemplateItemUpdate(unit_price=Decimal("-0.01"))


# [claude] OTMG-UI-22
def test_otmg_ui_22__line_update_schema_quantity_0_01_and_price_0_accepted():
    """OTMG-UI-22 — line update schema: quantity 0.01 and price 0 are accepted.
    Rules: update_item R4"""
    result = OrderTemplateItemUpdate(quantity=Decimal("0.01"), unit_price=Decimal("0"))
    # Then 1
    assert result.quantity == Decimal("0.01")
    assert result.unit_price == Decimal("0")


# [claude] OTMG-UI-23
def test_otmg_ui_23__update_item_flushes_and_never_commits(db, s):
    """OTMG-UI-23 — update_item flushes and never commits.
    Rules: update_item Returns"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    l_id = lx.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.update_item(db, item_id=l_id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == l_id
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l_id, OrderTemplateItem.quantity == Decimal("4.00")) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    row = rl(db, l_id)
    assert row.quantity == Decimal("3.00")
    assert row.line_subtotal == Decimal("30.00")


# [claude] OTMG-UI-24
@BUG_2349
def test_otmg_ui_24__new_price_making_total_10_13_is_refused(db, s):
    """OTMG-UI-24 — a new price that makes the total 10^13 or more is refused with 422.
    Rules: update_item R4a [BUG-2349]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("10000.00"), line_subtotal=Decimal("100000.00"))
    before_l = snap(db, lx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("1000000000")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 422
    assert exc.value.detail == LTL
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, lx) == before_l


# [claude] OTMG-UI-25
def test_otmg_ui_25__new_price_keeping_total_just_below_10_13_is_stored(db, s):
    """OTMG-UI-25 — a new price that keeps the total just below 10^13 is stored, rounded half up.
    Rules: update_item R4, R4a"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("1.01"), line_subtotal=Decimal("10.10"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("9900990099009.89")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("1.01")
    assert row.unit_price == Decimal("9900990099009.89")
    assert row.line_subtotal == Decimal("9999999999999.99")


# [claude] OTMG-UI-26
@BUG_2349
def test_otmg_ui_26__new_price_whose_total_rounds_to_10_13_is_refused(db, s):
    """OTMG-UI-26 — a new price whose total rounds half up to 10^13 is refused with 422.
    Rules: update_item R4a [BUG-2349]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("1.01"), line_subtotal=Decimal("10.10"))
    before_l = snap(db, lx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(unit_price=Decimal("9900990099009.90")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 422
    assert exc.value.detail == LTL
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, lx) == before_l


# [claude] OTMG-UI-27
@BUG_2349
def test_otmg_ui_27__new_quantity_making_total_10_13_with_stored_price_is_refused(db, s):
    """OTMG-UI-27 — a new quantity that makes the total with the stored price 10^13 or more is refused with 422.
    Rules: update_item R4a [BUG-2349]"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("1.00"), unit_price=Decimal("1000000000.00"), line_subtotal=Decimal("1000000000.00"))
    before_l = snap(db, lx)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("10000")), workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 422
    assert exc.value.detail == LTL
    # Then 3
    assert not db.dirty
    # Then 4
    assert not db.new
    # Then 5
    assert snap(db, lx) == before_l


# [claude] OTMG-UI-28
def test_otmg_ui_28__new_quantity_keeping_total_just_below_10_13_is_stored(db, s):
    """OTMG-UI-28 — a new quantity that keeps the total with the stored price just below 10^13 is stored, rounded half up.
    Rules: update_item R4, R4a"""
    t = tpl(db, s)
    lx = line(db, s, t, 1, quantity=Decimal("1.00"), unit_price=Decimal("9900990099009.89"), line_subtotal=Decimal("9900990099009.89"))
    result = M.update_item(db, item_id=lx.id, data=OrderTemplateItemUpdate(quantity=Decimal("1.01")), workspace_id=s.w1.id)
    # Then 1
    assert result.id == lx.id
    # Then 2
    row = rl(db, lx.id)
    assert row.quantity == Decimal("1.01")
    assert row.unit_price == Decimal("9900990099009.89")
    assert row.line_subtotal == Decimal("9999999999999.99")


# =========================================================================== #
# OrderTemplateManager.remove_item
# =========================================================================== #

# [claude] OTMG-RI-01
def test_otmg_ri_01__line_deleted_others_keep_their_numbers(db, s):
    """OTMG-RI-01 — the line is deleted and flushed; the others keep their numbers; the removed line is returned.
    Rules: remove_item R2"""
    t = tpl(db, s)
    l1 = line(db, s, t, 1)
    l2 = line(db, s, t, 2, description="Middle")
    l3 = line(db, s, t, 3)
    l2_id = l2.id
    result = M.remove_item(db, item_id=l2_id, workspace_id=s.w1.id)
    # Then 1
    assert result.id == l2_id
    assert result.line_number == 2
    assert result.description == "Middle"
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l2_id) == 0
    # Then 3
    ls = lines(db, t.id)
    assert [x.id for x in ls] == [l1.id, l3.id]
    # Then 4
    assert [x.line_number for x in ls] == [1, 3]


# [claude] OTMG-RI-02
def test_otmg_ri_02__unknown_line_is_refused(db, s):
    """OTMG-RI-02 — an unknown line is refused, nothing deleted.
    Rules: remove_item R1"""
    t = tpl(db, s)
    line(db, s, t, 1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=MISSING, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] OTMG-RI-03
def test_otmg_ri_03__line_of_earlier_workspace_is_refused(db, s):
    """OTMG-RI-03 — a line of an earlier workspace (W0) is refused, nothing deleted.
    Rules: remove_item R1"""
    z = tpl(db, s, workspace_id=s.w0.id)
    zl = line(db, s, z, 1, workspace_id=s.w0.id)
    t = tpl(db, s)
    line(db, s, t, 1)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=zl.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] OTMG-RI-04
def test_otmg_ri_04__line_of_later_workspace_is_refused(db, s):
    """OTMG-RI-04 — a line of a later workspace (W2) is refused, nothing deleted.
    Rules: remove_item R1"""
    t = tpl(db, s)
    line(db, s, t, 1)
    z = tpl(db, s, workspace_id=s.w2.id)
    zl = line(db, s, z, 1, workspace_id=s.w2.id)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.remove_item(db, item_id=zl.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Template item not found"
    # Then 3
    assert not db.deleted
    # Then 4
    assert written(db) == before


# [claude] OTMG-RI-05
def test_otmg_ri_05__remove_flushes_and_never_commits(db, s):
    """OTMG-RI-05 — remove flushes and never commits.
    Rules: remove_item R2"""
    t = tpl(db, s)
    lx = line(db, s, t, 1)
    l_id = lx.id
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = M.remove_item(db, item_id=l_id, workspace_id=s.w1.id)
    # Then 1
    assert result.id == l_id
    # Then 2
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l_id) == 0
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert count(db, OrderTemplateItem, OrderTemplateItem.id == l_id) == 1


# =========================================================================== #
# OrderTemplateManager.get_items
# =========================================================================== #

# [claude] OTMG-GI-01
def test_otmg_gi_01__lines_ordered_by_line_number(db, s):
    """OTMG-GI-01 — returns the template's lines ordered by line number.
    Rules: get_items R1"""
    sx = tpl(db, s, template_name="Lease")
    t = tpl(db, s)
    a = line(db, s, t, 3)
    line(db, s, sx, 1)
    b = line(db, s, t, 1)
    c = line(db, s, t, 2)
    result = M.get_items(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert [x.id for x in result] == [b.id, c.id, a.id]


# [claude] OTMG-GI-02
def test_otmg_gi_02__lines_of_inactive_template_are_returned(db, s):
    """OTMG-GI-02 — the lines of an inactive template are returned.
    Rules: get_items R1"""
    t = tpl(db, s, **INACTIVE(s))
    a = line(db, s, t, 1)
    result = M.get_items(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert [x.id for x in result] == [a.id]


# [claude] OTMG-GI-03
def test_otmg_gi_03__template_with_no_lines_gives_empty_list(db, s):
    """OTMG-GI-03 — a template with no lines gives an empty list.
    Rules: get_items R1"""
    t = tpl(db, s)
    result = M.get_items(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert result == []


# [claude] OTMG-GI-04
@BUG_2366
def test_otmg_gi_04__unknown_template_raises_404(db, s):
    """OTMG-GI-04 — an unknown template raises 404.
    Rules: get_items R2 [BUG-2366]"""
    t = tpl(db, s)
    line(db, s, t, 1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, tpl_id=MISSING, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == "Order template with ID 999999999 not found"


# [claude] OTMG-GI-05
@BUG_2366
def test_otmg_gi_05__template_of_earlier_workspace_raises_404(db, s):
    """OTMG-GI-05 — a template of an earlier workspace (W0) raises 404.
    Rules: get_items R2 [BUG-2366]"""
    z = tpl(db, s, workspace_id=s.w0.id)
    line(db, s, z, 1, workspace_id=s.w0.id)
    tpl(db, s)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, tpl_id=z.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"


# [claude] OTMG-GI-06
@BUG_2366
def test_otmg_gi_06__template_of_later_workspace_raises_404(db, s):
    """OTMG-GI-06 — a template of a later workspace (W2) raises 404.
    Rules: get_items R2 [BUG-2366]"""
    tpl(db, s)
    z = tpl(db, s, workspace_id=s.w2.id)
    line(db, s, z, 1, workspace_id=s.w2.id)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.get_items(db, tpl_id=z.id, workspace_id=s.w1.id)
    # Then 2
    assert exc.value.status_code == 404
    assert exc.value.detail == f"Order template with ID {z.id} not found"


# [claude] OTMG-GI-07
def test_otmg_gi_07__writes_nothing(db, s):
    """OTMG-GI-07 — writes nothing: a pending line stays pending, an unflushed edit stays dirty.
    Rules: get_items (reader)"""
    t = tpl(db, s)
    a = line(db, s, t, 2)
    b = line(db, s, t, 3)
    p = OrderTemplateItem(workspace_id=s.w1.id, order_template_id=t.id, line_number=1, description="Pending", quantity=Decimal("1"))
    db.add(p)
    b.description = "Edited"
    result = M.get_items(db, tpl_id=t.id, workspace_id=s.w1.id)
    # Then 1
    assert a.id in [x.id for x in result]
    assert len(result) == 2
    # Then 2
    assert p in db.new
    assert p.id is None
    assert len(db.new) == 1
    # Then 3
    assert b in db.dirty
    assert len(db.dirty) == 1


# =========================================================================== #
# create_template R9, update_template R9 — BUG-2347 (OQ-22, owner 2026-11-07)
# =========================================================================== #

# [claude] OTMG-Q22-01
@BUG_2347
def test_otmg_q22_01__ground_team_may_not_create_template_skipping_approval(db, s):
    """OTMG-Q22-01 — a ground-team member may not create a template that skips approval.
    Rules: create_template R9 [BUG-2347], Errors row 3"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-02
@BUG_2347
def test_otmg_q22_02__ground_team_may_not_create_auto_approving_template(db, s):
    """OTMG-Q22-02 — a ground-team member may not create a template that auto-approves.
    Rules: create_template R9 [BUG-2347]"""
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", auto_approve=True, items=[ITEM]), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-03
def test_otmg_q22_03__owner_member_row_creates_template_skipping_approval(db, s):
    """OTMG-Q22-03 — the owner (active owner member row) creates a template that skips approval and auto-approves; it is stored.
    Rules: create_template R9"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Payroll", requires_approval=False, auto_approve=True), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.requires_approval is False
    assert row.auto_approve is True


# [claude] OTMG-Q22-04
@BUG_2347
def test_otmg_q22_04__ground_team_may_not_switch_requires_approval_off(db, s):
    """OTMG-Q22-04 — a ground-team member may not switch requires_approval off.
    Rules: update_template R9 [BUG-2347]"""
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(requires_approval=False), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-Q22-05
@BUG_2347
def test_otmg_q22_05__ground_team_may_not_switch_auto_approve_on(db, s):
    """OTMG-Q22-05 — a ground-team member may not switch auto_approve on.
    Rules: update_template R9 [BUG-2347]"""
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(auto_approve=True), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-Q22-06
def test_otmg_q22_06__owner_switches_approval_back_on(db, s):
    """OTMG-Q22-06 — the owner switches requires_approval back on and auto_approve off; it is applied.
    Rules: update_template R9"""
    t = tpl(db, s, requires_approval=False, auto_approve=True)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(requires_approval=True, auto_approve=False), workspace_id=s.w1.id, user_id=s.uo.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.requires_approval is True
    assert row.auto_approve is False


# [claude] OTMG-Q22-07
def test_otmg_q22_07__owner_through_owner_user_id_creates_template_skipping_approval(db, s):
    """OTMG-Q22-07 — the owner through owner_user_id (a W1 manager by member row) creates a template that skips approval; it is stored.
    Rules: create_template R9"""
    s.w1.owner_user_id = s.ua.id
    db.flush()
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Payroll", requires_approval=False), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.requires_approval is False
    assert row.created_by == s.ua.id


# [claude] OTMG-Q22-08
@BUG_2347
def test_otmg_q22_08__suspended_owner_row_is_not_the_owner(db, s):
    """OTMG-Q22-08 — a suspended owner row is not the owner.
    Rules: create_template R9 [BUG-2347]"""
    p1 = make_profile(db)
    db.add(WorkspaceMember(workspace_id=s.w1.id, user_id=p1.id, role="owner", status="suspended"))
    db.flush()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=s.w1.id, user_id=p1.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-09
@BUG_2347
def test_otmg_q22_09__owner_of_w2_manager_in_w1_may_not_skip_approval(db, s):
    """OTMG-Q22-09 — the owner of W2 (member row), a manager in W1, may not create a W1 template that skips approval.
    Rules: create_template R9 [BUG-2347]"""
    db.add(WorkspaceMember(workspace_id=s.w1.id, user_id=s.ux.id, role="manager", status="active"))
    db.flush()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=s.w1.id, user_id=s.ux.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-10
@BUG_2347
def test_otmg_q22_10__owner_of_w0_manager_in_w1_may_not_auto_approve(db, s):
    """OTMG-Q22-10 — the owner of W0 (member row), a manager in W1, may not create a W1 template that auto-approves.
    Rules: create_template R9 [BUG-2347]"""
    p1 = make_profile(db)
    db.add(WorkspaceMember(workspace_id=s.w0.id, user_id=p1.id, role="owner", status="active"))
    db.flush()
    db.add(WorkspaceMember(workspace_id=s.w1.id, user_id=p1.id, role="manager", status="active"))
    db.flush()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", auto_approve=True, items=[ITEM]), workspace_id=s.w1.id, user_id=p1.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-11
@BUG_2347
def test_otmg_q22_11__w2_owner_user_id_manager_in_w1_may_not_skip_approval(db, s):
    """OTMG-Q22-11 — W2's owner_user_id, a manager in W1, may not create a W1 template that skips approval.
    Rules: create_template R9 [BUG-2347]"""
    s.w2.owner_user_id = s.ua.id
    db.flush()
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.new
    # Then 4
    assert written(db) == before


# [claude] OTMG-Q22-12
def test_otmg_q22_12__defaults_sent_explicitly_need_no_role(db, s):
    """OTMG-Q22-12 — the defaults sent explicitly need no role: a ground-team member's template is stored.
    Rules: create_template R9"""
    result = M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=True, auto_approve=False), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 1
    assert result.id is not None
    # Then 2
    row = rt(db, result.id)
    assert row.requires_approval is True
    assert row.auto_approve is False
    assert row.created_by == s.ug.id


# [claude] OTMG-Q22-13
@BUG_2347
def test_otmg_q22_13__ground_team_may_not_switch_requires_approval_back_on(db, s):
    """OTMG-Q22-13 — a ground-team member may not switch requires_approval back on either.
    Rules: update_template R9 [BUG-2347]"""
    t = tpl(db, s, requires_approval=False)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(requires_approval=True), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-Q22-14
@BUG_2347
def test_otmg_q22_14__refused_flag_change_writes_none_of_the_other_fields(db, s):
    """OTMG-Q22-14 — a refused flag change writes none of the other fields sent with it.
    Rules: update_template R9 [BUG-2347]"""
    t = tpl(db, s)
    t_id = t.id
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t_id, data=OrderTemplateUpdate(template_name="Lease", requires_approval=False), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t
    # Then 5
    row = rt(db, t_id)
    assert row.template_name == "Rent"
    assert row.requires_approval is True
    assert row.updated_by is None


# [claude] OTMG-Q22-15
def test_otmg_q22_15__re_sending_stored_flags_is_no_change(db, s):
    """OTMG-Q22-15 — re-sending the stored flags is no change: a ground-team member's other field is applied.
    Rules: update_template R9"""
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Lease", requires_approval=True, auto_approve=False), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.template_name == "Lease"
    assert row.requires_approval is True
    assert row.auto_approve is False
    assert row.updated_by == s.ug.id


# [claude] OTMG-Q22-16
def test_otmg_q22_16__ground_team_may_rename_template_that_skips_approval(db, s):
    """OTMG-Q22-16 — a ground-team member may rename a template that already skips approval; the flags stay.
    Rules: update_template R9"""
    t = tpl(db, s, requires_approval=False, auto_approve=True)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=s.w1.id, user_id=s.ug.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.template_name == "Lease"
    assert row.requires_approval is False
    assert row.auto_approve is True


# [claude] OTMG-Q22-17
@BUG_2347
def test_otmg_q22_17__owner_of_w2_manager_in_w1_may_not_switch_requires_approval_off(db, s):
    """OTMG-Q22-17 — the owner of W2 (member row), a manager in W1, may not switch a W1 template's requires_approval off.
    Rules: update_template R9 [BUG-2347]"""
    db.add(WorkspaceMember(workspace_id=s.w1.id, user_id=s.ux.id, role="manager", status="active"))
    db.flush()
    t = tpl(db, s)
    before_t = snap(db, t)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(requires_approval=False), workspace_id=s.w1.id, user_id=s.ux.id)
    # Then 2
    assert exc.value.status_code == 403
    assert exc.value.detail == FORBID
    # Then 3
    assert not db.dirty
    # Then 4
    assert snap(db, t) == before_t


# [claude] OTMG-Q22-18
def test_otmg_q22_18__owner_through_owner_user_id_switches_auto_approve_on(db, s):
    """OTMG-Q22-18 — the owner through owner_user_id switches auto_approve on; it is applied.
    Rules: update_template R9"""
    s.w1.owner_user_id = s.ua.id
    db.flush()
    t = tpl(db, s)
    result = M.update_template(db, tpl_id=t.id, data=OrderTemplateUpdate(auto_approve=True), workspace_id=s.w1.id, user_id=s.ua.id)
    # Then 1
    assert result.id == t.id
    # Then 2
    row = rt(db, t.id)
    assert row.auto_approve is True
    assert row.requires_approval is True
    assert row.updated_by == s.ua.id
