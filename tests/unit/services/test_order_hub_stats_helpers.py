"""Unit tests for app/services/order_hub_stats_helpers.py.

Implements tests/unit/services/order_hub_stats_helpers.cases.md, one test per
case, in card order. Every order is an unsaved model instance built with the
card's keyword arguments; no test uses the `db` fixture and nothing is patched.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. `# Then N` marks the checks of the card's Then line N.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.expense_order import ExpenseOrder
from app.models.purchase_order import PurchaseOrder
from app.models.status import Status
from app.models.transfer_order import TransferOrder
from app.schemas.order_hub import OrderHubPendingHighlight, OrderHubRecentSummary
from app.services.order_hub_stats_helpers import (
    expense_order_to_recent_summary,
    pending_highlight_from_dict,
    purchase_order_to_recent_summary,
    transfer_order_to_recent_summary,
)

# --------------------------------------------------------------------------- #
# Conventions -> fixed values
# --------------------------------------------------------------------------- #

T1 = datetime(2026, 5, 1, 9, 30, 0)  # noqa: DTZ001
T2 = datetime(2026, 5, 3, 14, 0, 0)  # noqa: DTZ001


# --------------------------------------------------------------------------- #
# purchase_order_to_recent_summary
# --------------------------------------------------------------------------- #

# [claude] OHS-P-01
def test_ohs_p_01__every_field_of_a_full_purchase_order_is_mapped():
    """OHS-P-01 — every field of a full purchase order is mapped.
    Rules: `purchase_order_to_recent_summary` R1, R2"""
    s = Status(id=4, name="Draft")
    o = PurchaseOrder(
        id=11, po_number="PO-0011", current_status_id=4, created_at=T1, updated_at=T2,
        account_id=21, invoice_id=31, total_amount=Decimal("1234.50"),
    )
    o.current_status = s
    result = purchase_order_to_recent_summary(o)

    # Then 1
    assert isinstance(result, OrderHubRecentSummary)
    # Then 2
    assert result.id == 11
    assert result.order_number == "PO-0011"
    assert result.status_id == 4
    # Then 3
    assert result.status_name == "Draft"
    # Then 4
    assert result.created_at == T1
    assert result.updated_at == T2
    # Then 5
    assert result.account_id == 21
    assert result.invoice_id == 31
    # Then 6
    assert result.total_amount == Decimal("1234.50")
    assert isinstance(result.total_amount, Decimal)
    # Then 7
    assert str(result.total_amount) == "1234.50"


# [claude] OHS-P-02
def test_ohs_p_02__a_purchase_order_leaves_the_expense_and_transfer_fields_empty():
    """OHS-P-02 — a purchase order leaves the expense and transfer fields empty.
    Rules: `purchase_order_to_recent_summary` R3"""
    s = Status(id=4, name="Draft")
    o = PurchaseOrder(
        id=11, po_number="PO-0011", current_status_id=4, created_at=T1, updated_at=T2,
        account_id=21, invoice_id=31, total_amount=Decimal("1234.50"),
    )
    o.current_status = s
    result = purchase_order_to_recent_summary(o)

    # Then 1
    assert result.expense_category is None
    assert result.expense_date is None
    assert result.due_date is None
    assert result.source_location_type is None
    assert result.destination_location_type is None


# [claude] OHS-P-03
def test_ohs_p_03__no_status_loaded_status_name_is_none_status_id_still_the_orders():
    """OHS-P-03 — no status loaded: status_name is None, status_id still the order's.
    Rules: `purchase_order_to_recent_summary` R1, R2"""
    o = PurchaseOrder(id=12, po_number="PO-0012", current_status_id=6, created_at=T1)
    result = purchase_order_to_recent_summary(o)

    # Then 1
    assert result.status_name is None
    # Then 2
    assert result.id == 12
    assert result.order_number == "PO-0012"
    assert result.status_id == 6
    assert result.created_at == T1
    # Then 3
    assert result.updated_at is None
    assert result.account_id is None
    assert result.invoice_id is None
    assert result.total_amount is None


# [claude] OHS-P-04
def test_ohs_p_04__no_created_at_is_refused():
    """OHS-P-04 — no created_at is refused.
    Rules: `purchase_order_to_recent_summary` R4; Errors"""
    o = PurchaseOrder(id=13, po_number="PO-0013", current_status_id=4)
    # Then 1
    with pytest.raises(ValidationError):
        purchase_order_to_recent_summary(o)


# [claude] OHS-P-05
def test_ohs_p_05__a_none_po_number_is_refused():
    """OHS-P-05 — a None po_number is refused.
    Rules: `purchase_order_to_recent_summary` R4; Errors"""
    o = PurchaseOrder(id=14, po_number=None, current_status_id=4, created_at=T1)
    # Then 1
    with pytest.raises(ValidationError):
        purchase_order_to_recent_summary(o)


# [claude] OHS-P-06
def test_ohs_p_06__a_none_current_status_id_is_refused():
    """OHS-P-06 — a None current_status_id is refused.
    Rules: `purchase_order_to_recent_summary` R4; Errors"""
    o = PurchaseOrder(id=15, po_number="PO-0015", current_status_id=None, created_at=T1)
    # Then 1
    with pytest.raises(ValidationError):
        purchase_order_to_recent_summary(o)


# --------------------------------------------------------------------------- #
# expense_order_to_recent_summary
# --------------------------------------------------------------------------- #

# [claude] OHS-E-01
def test_ohs_e_01__every_field_of_a_full_expense_order_is_mapped_status_fixed_locations_empty():
    """OHS-E-01 — every field of a full expense order is mapped; status is fixed and location fields are empty.
    Rules: `expense_order_to_recent_summary` R1, R2, R3"""
    o = ExpenseOrder(
        id=22, expense_number="EXP-0022", created_at=T1, updated_at=T2, account_id=23, invoice_id=33,
        total_amount=Decimal("99.90"), expense_category="other",
        expense_date=date(2026, 5, 10), due_date=date(2026, 5, 20),
    )
    result = expense_order_to_recent_summary(o)

    # Then 1
    assert isinstance(result, OrderHubRecentSummary)
    # Then 2
    assert result.id == 22
    assert result.order_number == "EXP-0022"
    # Then 3
    assert result.status_id == 0
    assert result.status_name is None
    # Then 4
    assert result.created_at == T1
    assert result.updated_at == T2
    # Then 5
    assert result.account_id == 23
    assert result.invoice_id == 33
    assert result.total_amount == Decimal("99.90")
    # Then 6
    assert result.expense_category == "other"
    assert result.expense_date == date(2026, 5, 10)
    assert result.due_date == date(2026, 5, 20)
    # Then 7
    assert result.source_location_type is None
    assert result.destination_location_type is None
    # Then 8
    assert str(result.total_amount) == "99.90"


# [claude] OHS-E-02
def test_ohs_e_02__a_minimal_expense_order_optional_fields_are_none():
    """OHS-E-02 — a minimal expense order: optional fields are None.
    Rules: `expense_order_to_recent_summary` R1, R2"""
    o = ExpenseOrder(id=24, expense_number="EXP-0024", created_at=T1)
    result = expense_order_to_recent_summary(o)

    # Then 1
    assert result.id == 24
    assert result.order_number == "EXP-0024"
    assert result.status_id == 0
    assert result.created_at == T1
    # Then 2
    assert result.status_name is None
    assert result.updated_at is None
    assert result.account_id is None
    assert result.invoice_id is None
    assert result.total_amount is None
    assert result.expense_category is None
    assert result.expense_date is None
    assert result.due_date is None


# [claude] OHS-E-03
def test_ohs_e_03__no_created_at_is_refused():
    """OHS-E-03 — no created_at is refused.
    Rules: `expense_order_to_recent_summary` R4; Errors"""
    o = ExpenseOrder(id=25, expense_number="EXP-0025")
    # Then 1
    with pytest.raises(ValidationError):
        expense_order_to_recent_summary(o)


# [claude] OHS-E-04
def test_ohs_e_04__a_none_expense_number_is_refused():
    """OHS-E-04 — a None expense_number is refused.
    Rules: `expense_order_to_recent_summary` R4; Errors"""
    o = ExpenseOrder(id=26, expense_number=None, created_at=T1)
    # Then 1
    with pytest.raises(ValidationError):
        expense_order_to_recent_summary(o)


# --------------------------------------------------------------------------- #
# transfer_order_to_recent_summary
# --------------------------------------------------------------------------- #

# [claude] OHS-T-01
def test_ohs_t_01__every_field_of_a_full_transfer_order_is_mapped():
    """OHS-T-01 — every field of a full transfer order is mapped.
    Rules: `transfer_order_to_recent_summary` R1, R2"""
    s = Status(id=5, name="In Transit")
    o = TransferOrder(
        id=41, transfer_number="TR-0041", current_status_id=5, created_at=T1, updated_at=T2,
        source_location_type="storage", destination_location_type="machine",
    )
    o.current_status = s
    result = transfer_order_to_recent_summary(o)

    # Then 1
    assert isinstance(result, OrderHubRecentSummary)
    # Then 2
    assert result.id == 41
    assert result.order_number == "TR-0041"
    assert result.status_id == 5
    # Then 3
    assert result.status_name == "In Transit"
    # Then 4
    assert result.created_at == T1
    assert result.updated_at == T2
    # Then 5
    assert result.source_location_type == "storage"
    assert result.destination_location_type == "machine"


# [claude] OHS-T-02
def test_ohs_t_02__a_transfer_order_leaves_money_and_expense_fields_empty():
    """OHS-T-02 — a transfer order leaves money and expense fields empty.
    Rules: `transfer_order_to_recent_summary` R3"""
    s = Status(id=5, name="In Transit")
    o = TransferOrder(
        id=41, transfer_number="TR-0041", current_status_id=5, created_at=T1, updated_at=T2,
        source_location_type="storage", destination_location_type="machine",
    )
    o.current_status = s
    result = transfer_order_to_recent_summary(o)

    # Then 1
    assert result.account_id is None
    assert result.invoice_id is None
    assert result.total_amount is None
    assert result.expense_category is None
    assert result.expense_date is None
    assert result.due_date is None


# [claude] OHS-T-03
def test_ohs_t_03__no_status_loaded_status_name_is_none():
    """OHS-T-03 — no status loaded: status_name is None.
    Rules: `transfer_order_to_recent_summary` R1, R2"""
    o = TransferOrder(id=42, transfer_number="TR-0042", current_status_id=7, created_at=T1)
    result = transfer_order_to_recent_summary(o)

    # Then 1
    assert result.status_name is None
    # Then 2
    assert result.id == 42
    assert result.order_number == "TR-0042"
    assert result.status_id == 7
    assert result.created_at == T1
    # Then 3
    assert result.updated_at is None
    assert result.source_location_type is None
    assert result.destination_location_type is None


# [claude] OHS-T-04
def test_ohs_t_04__no_created_at_is_refused():
    """OHS-T-04 — no created_at is refused.
    Rules: `transfer_order_to_recent_summary` R4; Errors"""
    o = TransferOrder(id=43, transfer_number="TR-0043", current_status_id=5)
    # Then 1
    with pytest.raises(ValidationError):
        transfer_order_to_recent_summary(o)


# [claude] OHS-T-05
def test_ohs_t_05__a_none_transfer_number_is_refused():
    """OHS-T-05 — a None transfer_number is refused.
    Rules: `transfer_order_to_recent_summary` R4; Errors"""
    o = TransferOrder(id=44, transfer_number=None, current_status_id=5, created_at=T1)
    # Then 1
    with pytest.raises(ValidationError):
        transfer_order_to_recent_summary(o)


# --------------------------------------------------------------------------- #
# pending_highlight_from_dict
# --------------------------------------------------------------------------- #

# [claude] OHS-H-01
def test_ohs_h_01__a_full_dict_becomes_the_highlight_extra_key_ignored_iso_string_parsed():
    """OHS-H-01 — a full dict becomes the highlight; an extra key is ignored; an ISO string becomes a datetime.
    Rules: `pending_highlight_from_dict` R1"""
    data = {
        "id": 51, "order_number": "PO-0051", "status_name": "Pending approval",
        "created_at": "2026-05-01T09:30:00", "total_amount": "5.00",
    }
    result = pending_highlight_from_dict(data)

    # Then 1
    assert isinstance(result, OrderHubPendingHighlight)
    # Then 2
    assert result.id == 51
    assert result.order_number == "PO-0051"
    # Then 3
    assert result.status_name == "Pending approval"
    # Then 4
    assert result.created_at == T1
    # Then 5
    assert not hasattr(result, "total_amount")


# [claude] OHS-H-02
def test_ohs_h_02__only_the_required_keys_the_optional_fields_are_none():
    """OHS-H-02 — only the required keys: the optional fields are None.
    Rules: `pending_highlight_from_dict` R1"""
    data = {"id": 52, "order_number": "TR-0052"}
    result = pending_highlight_from_dict(data)

    # Then 1
    assert result.id == 52
    assert result.order_number == "TR-0052"
    # Then 2
    assert result.status_name is None
    assert result.created_at is None


# [claude] OHS-H-03
def test_ohs_h_03__a_missing_id_is_refused():
    """OHS-H-03 — a missing id is refused.
    Rules: `pending_highlight_from_dict` R2; Errors"""
    data = {"order_number": "PO-0053", "status_name": "Draft"}
    # Then 1
    with pytest.raises(ValidationError):
        pending_highlight_from_dict(data)


# [claude] OHS-H-04
def test_ohs_h_04__a_none_order_number_is_refused():
    """OHS-H-04 — a None order_number is refused.
    Rules: `pending_highlight_from_dict` R2; Errors"""
    data = {"id": 54, "order_number": None}
    # Then 1
    with pytest.raises(ValidationError):
        pending_highlight_from_dict(data)
