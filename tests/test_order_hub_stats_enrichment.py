"""Tests for enriched order hub stats responses."""

from app.schemas.expense_order import ExpenseOrderHubStatsResponse
from app.schemas.purchase_order import PurchaseOrderHubStatsResponse
from app.schemas.transfer_order import TransferOrderHubStatsResponse


def test_purchase_order_hub_stats_includes_recent_and_pending_fields() -> None:
    result = PurchaseOrderHubStatsResponse(
        total_count=1,
        total_value=0,
        open_count=1,
        open_value=0,
        not_invoiced_count=0,
        recent_orders=[],
        pending_planning_count=0,
        pending_planning=[],
        missing_invoice_count=0,
        missing_invoice=[],
        oldest_drafts=[],
    )
    assert result.recent_orders == []
    assert result.pending_planning_count == 0


def test_transfer_order_hub_stats_includes_machine_count_recent_and_pending() -> None:
    result = TransferOrderHubStatsResponse(
        total_count=2,
        open_count=1,
        completed_count=1,
        machine_involved_count=1,
        recent_orders=[],
        pending_planned_count=0,
        pending_planned=[],
        awaiting_setup_count=0,
        awaiting_setup=[],
        oldest_drafts=[],
    )
    assert result.machine_involved_count == 1
    assert result.pending_planned_count == 0


def test_expense_order_hub_stats_includes_recent_orders() -> None:
    result = ExpenseOrderHubStatsResponse(
        total_count=0,
        total_value=0,
        open_count=0,
        open_value=0,
        not_invoiced_count=0,
        recent_orders=[],
    )
    assert result.recent_orders == []
