"""Map order models to shared hub stats DTOs."""
from app.models.expense_order import ExpenseOrder
from app.models.purchase_order import PurchaseOrder
from app.models.transfer_order import TransferOrder
from app.schemas.order_hub import OrderHubPendingHighlight, OrderHubRecentSummary


def purchase_order_to_recent_summary(order: PurchaseOrder) -> OrderHubRecentSummary:
    status = order.current_status
    return OrderHubRecentSummary(
        id=order.id,
        order_number=order.po_number,
        status_id=order.current_status_id,
        status_name=status.name if status else None,
        created_at=order.created_at,
        updated_at=order.updated_at,
        account_id=order.account_id,
        invoice_id=order.invoice_id,
        total_amount=order.total_amount,
    )


def expense_order_to_recent_summary(order: ExpenseOrder) -> OrderHubRecentSummary:
    return OrderHubRecentSummary(
        id=order.id,
        order_number=order.expense_number,
        status_id=0,
        status_name=None,
        created_at=order.created_at,
        updated_at=order.updated_at,
        account_id=order.account_id,
        invoice_id=order.invoice_id,
        total_amount=order.total_amount,
        expense_category=order.expense_category,
        expense_date=order.expense_date,
        due_date=order.due_date,
    )


def transfer_order_to_recent_summary(order: TransferOrder) -> OrderHubRecentSummary:
    status = order.current_status
    return OrderHubRecentSummary(
        id=order.id,
        order_number=order.transfer_number,
        status_id=order.current_status_id,
        status_name=status.name if status else None,
        created_at=order.created_at,
        updated_at=order.updated_at,
        source_location_type=order.source_location_type,
        destination_location_type=order.destination_location_type,
    )


def pending_highlight_from_dict(data: dict) -> OrderHubPendingHighlight:
    return OrderHubPendingHighlight(**data)
