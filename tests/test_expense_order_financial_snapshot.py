"""Tests for expense order hub financial snapshot."""

from datetime import date, timedelta
from decimal import Decimal

from app.dao.expense_order import _due_date_bucket, _due_window_dates
from app.schemas.expense_order import ExpenseOrderHubStatsResponse
from app.schemas.order_hub import (
    ExpenseOrderDueTimelineBucket,
    ExpenseOrderFinancialBucket,
    ExpenseOrderFinancialSample,
    ExpenseOrderFinancialSnapshot,
    ExpenseOrderOpenByAccountBucket,
    ExpenseOrderUnpaidPipelineBucket,
)


def test_expense_order_hub_stats_includes_financial_snapshot() -> None:
    snapshot = ExpenseOrderFinancialSnapshot(
        category_breakdown=[
            ExpenseOrderFinancialBucket(
                key="utilities",
                label="Utilities",
                count=2,
                total_value=Decimal("1500"),
            )
        ],
        stage_pipeline=[
            ExpenseOrderFinancialBucket(
                key="draft",
                label="Draft",
                count=1,
                total_value=Decimal("500"),
            )
        ],
        open_by_account=[
            ExpenseOrderOpenByAccountBucket(
                account_id=1,
                account_name="Acme",
                count=1,
                total_value=Decimal("500"),
            )
        ],
        due_timeline=[
            ExpenseOrderDueTimelineBucket(
                key="overdue",
                label="Overdue",
                count=1,
                total_value=Decimal("100"),
                samples=[
                    ExpenseOrderFinancialSample(
                        id=10,
                        order_number="EXP-2026-001",
                        total_value=Decimal("100"),
                        sublabel="2026-01-01",
                    )
                ],
            )
        ],
        unpaid_pipeline=[
            ExpenseOrderUnpaidPipelineBucket(
                key="unpaid",
                label="Unpaid",
                count=1,
                outstanding_value=Decimal("250"),
                samples=[],
            )
        ],
    )
    result = ExpenseOrderHubStatsResponse(
        total_count=2,
        total_value=Decimal("1500"),
        open_count=1,
        open_value=Decimal("500"),
        not_invoiced_count=1,
        recent_orders=[],
        financial_snapshot=snapshot,
    )
    assert result.financial_snapshot.category_breakdown[0].key == "utilities"
    assert result.financial_snapshot.unpaid_pipeline[0].outstanding_value == Decimal("250")


def test_due_date_bucket_overdue_and_no_due_date() -> None:
    today, end_of_week, end_of_month = _due_window_dates()
    assert _due_date_bucket(None, today=today, end_of_week=end_of_week, end_of_month=end_of_month) == "no_due_date"
    assert (
        _due_date_bucket(today - timedelta(days=1), today=today, end_of_week=end_of_week, end_of_month=end_of_month)
        == "overdue"
    )
    assert (
        _due_date_bucket(today, today=today, end_of_week=end_of_week, end_of_month=end_of_month)
        == "due_this_week"
    )


def test_due_date_bucket_later_this_month() -> None:
    today, end_of_week, end_of_month = _due_window_dates()
    if end_of_week < end_of_month:
        mid = end_of_week + timedelta(days=1)
        if mid <= end_of_month:
            assert (
                _due_date_bucket(mid, today=today, end_of_week=end_of_week, end_of_month=end_of_month)
                == "due_later_this_month"
            )


def test_due_date_bucket_beyond_month_excluded() -> None:
    today, end_of_week, end_of_month = _due_window_dates()
    beyond = end_of_month + timedelta(days=5)
    assert (
        _due_date_bucket(beyond, today=today, end_of_week=end_of_week, end_of_month=end_of_month)
        == "beyond_scope"
    )
