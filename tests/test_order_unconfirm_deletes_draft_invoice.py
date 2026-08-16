"""Unconfirming order sections deletes the linked auto-draft invoice."""
from unittest.mock import MagicMock, patch

from app.services.purchase_order_service import PurchaseOrderService
from app.services.sales_service import SalesService


def _draft_invoice(*, invoice_id: int = 42) -> MagicMock:
    invoice = MagicMock()
    invoice.id = invoice_id
    invoice.invoice_status = 'draft'
    return invoice


@patch('app.services.purchase_order_service.account_invoice_dao')
def test_po_sync_deletes_draft_when_base_sections_unconfirmed(mock_invoice_dao) -> None:
    service = PurchaseOrderService()
    service.manager = MagicMock()
    service.account_invoice_manager = MagicMock()
    service.manager.is_po_financially_locked.return_value = False
    service.manager._base_sections_confirmed.return_value = False
    mock_invoice_dao.get_by_id_and_workspace.return_value = _draft_invoice()

    po = MagicMock()
    po.id = 10
    po.workspace_id = 1
    po.invoice_id = 42
    po.po_number = 'PO-2026-001'
    db = MagicMock()

    result = service._sync_draft_invoice_for_po(db, po, workspace_id=1, user_id=7)

    assert result is None
    service.account_invoice_manager.delete_invoice.assert_called_once_with(
        db, 42, 1, 7
    )
    service.manager.unlink_invoice_from_po.assert_called_once()
    assert service.manager.unlink_invoice_from_po.call_args.kwargs['event_type'] == 'invoice_draft_deleted'


@patch('app.services.purchase_order_service.account_invoice_dao')
def test_po_sync_keeps_confirmed_invoice_when_financially_locked(mock_invoice_dao) -> None:
    service = PurchaseOrderService()
    service.manager = MagicMock()
    service.account_invoice_manager = MagicMock()
    service.manager.is_po_financially_locked.return_value = True
    service.manager._base_sections_confirmed.return_value = False

    po = MagicMock()
    po.invoice_id = 42
    db = MagicMock()

    result = service._sync_draft_invoice_for_po(db, po, workspace_id=1, user_id=7)

    assert result is None
    service.account_invoice_manager.delete_invoice.assert_not_called()
    service.manager.unlink_invoice_from_po.assert_not_called()
    mock_invoice_dao.get_by_id_and_workspace.assert_not_called()


@patch('app.services.purchase_order_service.account_invoice_dao')
def test_po_sync_skips_delete_when_no_linked_invoice(mock_invoice_dao) -> None:
    service = PurchaseOrderService()
    service.manager = MagicMock()
    service.account_invoice_manager = MagicMock()
    service.manager.is_po_financially_locked.return_value = False
    service.manager._base_sections_confirmed.return_value = False

    po = MagicMock()
    po.invoice_id = None
    db = MagicMock()

    result = service._sync_draft_invoice_for_po(db, po, workspace_id=1, user_id=7)

    assert result is None
    service.account_invoice_manager.delete_invoice.assert_not_called()
    service.manager.unlink_invoice_from_po.assert_not_called()
    mock_invoice_dao.get_by_id_and_workspace.assert_not_called()


@patch('app.services.sales_service.account_invoice_dao')
def test_so_sync_deletes_draft_when_base_sections_unconfirmed(mock_invoice_dao) -> None:
    service = SalesService()
    service.sales_manager = MagicMock()
    service.account_invoice_manager = MagicMock()
    service.sales_manager.is_so_financially_locked.return_value = False
    service.sales_manager._base_sections_confirmed.return_value = False
    mock_invoice_dao.get_by_id_and_workspace.return_value = _draft_invoice()

    order = MagicMock()
    order.id = 20
    order.invoice_id = 42
    order.sales_order_number = 'SO-2026-001'
    db = MagicMock()

    result = service._sync_draft_invoice_for_so(db, order, workspace_id=1, user_id=7)

    assert result is None
    service.account_invoice_manager.delete_invoice.assert_called_once_with(
        db, 42, 1, 7
    )
    service.sales_manager.unlink_invoice_from_so.assert_called_once()
    assert service.sales_manager.unlink_invoice_from_so.call_args.kwargs['event_type'] == 'invoice_draft_deleted'


@patch('app.services.sales_service.account_invoice_dao')
def test_so_sync_keeps_confirmed_invoice_when_financially_locked(mock_invoice_dao) -> None:
    service = SalesService()
    service.sales_manager = MagicMock()
    service.account_invoice_manager = MagicMock()
    service.sales_manager.is_so_financially_locked.return_value = True
    service.sales_manager._base_sections_confirmed.return_value = False

    order = MagicMock()
    order.invoice_id = 42
    db = MagicMock()

    result = service._sync_draft_invoice_for_so(db, order, workspace_id=1, user_id=7)

    assert result is None
    service.account_invoice_manager.delete_invoice.assert_not_called()
    service.sales_manager.unlink_invoice_from_so.assert_not_called()
    mock_invoice_dao.get_by_id_and_workspace.assert_not_called()
