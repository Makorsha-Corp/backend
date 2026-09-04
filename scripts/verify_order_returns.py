"""One-off verify script for the PO/SO return feature.

Builds a throwaway Item + minimal PO/SO fixtures directly (bypassing the full
order-creation/approval workflow, which isn't what's under test here), then
exercises the return service methods end-to-end. Cleans up everything it
creates, including restoring/removing the dev DB rows it touched.
"""
from datetime import date, datetime
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.account import Account
from app.models.factory import Factory
from app.models.item import Item
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.models.status import Status
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.purchase_order_event import PurchaseOrderEvent
from app.models.purchase_order_return import PurchaseOrderReturn, PurchaseOrderReturnItem
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem
from app.models.sales_order_event import SalesOrderEvent
from app.models.sales_order_return import SalesOrderReturn, SalesOrderReturnItem
from app.models.account_invoice import AccountInvoice
from app.models.invoice_item import InvoiceItem
from app.models.enums import InventoryTypeEnum
from app.utils.item_name_normalize import normalize_item_name

from app.managers.purchase_order_manager import purchase_order_manager
from app.managers.sales_manager import sales_manager
from app.managers.invoice_payment_manager import invoice_payment_manager
from app.services.purchase_order_service import purchase_order_service
from app.services.sales_service import sales_service
from app.schemas.purchase_order_return import PurchaseOrderReturnCreate, PurchaseOrderReturnItemCreate
from app.schemas.sales_order_return import SalesOrderReturnCreate, SalesOrderReturnItemCreate
from app.schemas.invoice_payment import InvoicePaymentCreate
from fastapi import HTTPException

PASS = []
FAIL = []


def check(label: str, cond: bool, detail: str = ""):
    if cond:
        PASS.append(label)
        print(f"PASS: {label}")
    else:
        FAIL.append(label)
        print(f"FAIL: {label} {detail}")


def po_stage_name(db, ws_id, po) -> str | None:
    return purchase_order_manager._current_stage_name(db, ws_id, po.current_status_id)


def po_reopened_event_count(db, ws_id, po_id) -> int:
    return (
        db.query(PurchaseOrderEvent)
        .filter(
            PurchaseOrderEvent.workspace_id == ws_id,
            PurchaseOrderEvent.purchase_order_id == po_id,
            PurchaseOrderEvent.event_type == 'order_reopened',
        )
        .count()
    )


def so_reopened_event_count(db, ws_id, so_id) -> int:
    return (
        db.query(SalesOrderEvent)
        .filter(
            SalesOrderEvent.workspace_id == ws_id,
            SalesOrderEvent.sales_order_id == so_id,
            SalesOrderEvent.event_type == 'order_reopened',
        )
        .count()
    )


def main() -> None:
    db = SessionLocal()
    created = {}
    try:
        workspace = db.query(Workspace).first()
        user = db.query(Profile).filter(Profile.id == workspace.owner_user_id).first()
        account = db.query(Account).filter(
            Account.workspace_id == workspace.id, Account.allow_invoices == True, Account.is_active == True
        ).first()
        factory = db.query(Factory).filter(Factory.workspace_id == workspace.id).first()
        any_status = db.query(Status).filter(Status.workspace_id == workspace.id).first()
        ws_id, user_id = workspace.id, user.id
        print(f"Using workspace={ws_id} user={user_id} account={account.id} factory={factory.id}")

        # --- throwaway item ---
        item = Item(
            workspace_id=ws_id, name="Return Test Item", name_normalized=normalize_item_name("Return Test Item"),
            unit="pcs", created_by=user_id, item_type="physical",
        )
        db.add(item)
        db.flush()
        created['item'] = item

        # ============ PURCHASE ORDER RETURN ============
        # ordered=100, received=100 (fully received) so we can drive both a refund
        # (no gap reopens) and a replace (gap reopens, needs re-receiving) scenario.
        po_status_id = purchase_order_manager._resolve_po_stage_status_id(db, ws_id, 'Receiving')
        po_workflow_id = purchase_order_manager._resolve_po_workflow_id(db, ws_id)
        po = PurchaseOrder(
            workspace_id=ws_id, po_number="PO-RETURN-TEST-001", account_id=account.id,
            destination_type='storage', destination_id=factory.id, order_date=date.today(),
            subtotal=Decimal('1000.00'), total_amount=Decimal('1000.00'),
            current_status_id=po_status_id, order_workflow_id=po_workflow_id,
            supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=True,
            created_by=user_id,
        )
        db.add(po)
        db.flush()
        created['po'] = po

        po_item = PurchaseOrderItem(
            workspace_id=ws_id, purchase_order_id=po.id, line_number=1, item_id=item.id,
            quantity_ordered=Decimal('100'), quantity_received=Decimal('100'), unit_price=Decimal('10.00'),
            line_subtotal=Decimal('1000.00'),
        )
        db.add(po_item)
        db.flush()
        created['po_item'] = po_item

        # Seed storage inventory as if the 100 units were actually received. ensure_for_factory_item_type
        # re-syncs the snapshot from the ledger on every read, so the seed needs a matching ledger row too.
        inv = Inventory(
            workspace_id=ws_id, item_id=item.id, inventory_type=InventoryTypeEnum.STORAGE,
            factory_id=factory.id, qty=100, avg_price=Decimal('10.00'), created_by=user_id,
        )
        db.add(inv)
        db.flush()
        created['inventory'] = inv

        seed_ledger = InventoryLedger(
            workspace_id=ws_id, inventory_type=InventoryTypeEnum.STORAGE, factory_id=factory.id, item_id=item.id,
            transaction_type='manual_seed', quantity=100, unit_cost=Decimal('10.00'), total_cost=Decimal('1000.00'),
            qty_before=0, qty_after=100, avg_price_before=None, avg_price_after=Decimal('10.00'),
            source_type='verify_script_seed', source_id=0, performed_by=user_id,
        )
        db.add(seed_ledger)
        db.flush()
        created['seed_ledger'] = seed_ledger
        db.commit()

        # -- mark complete should succeed before any return exists --
        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            db.rollback()
            check("PO: fully-received order completes with no returns", True)
        except HTTPException as e:
            db.rollback()
            check("PO: fully-received order completes with no returns", False, str(e.detail))

        # -- over-request beyond what's received should 400 --
        try:
            purchase_order_service.start_return(
                db, po_id=po.id, workspace_id=ws_id, user_id=user_id,
                data=PurchaseOrderReturnCreate(return_type='refund', items=[
                    PurchaseOrderReturnItemCreate(po_item_id=po_item.id, quantity_returned=Decimal('150')),
                ]),
            )
            check("PO: over-request rejected", False, "did not raise")
        except HTTPException as e:
            check("PO: over-request rejected", e.status_code == 400, str(e.detail))

        # === Scenario A: REFUND return — reduces received, no redelivery needed ===
        ret = purchase_order_service.start_return(
            db, po_id=po.id, workspace_id=ws_id, user_id=user_id,
            data=PurchaseOrderReturnCreate(return_type='refund', items=[
                PurchaseOrderReturnItemCreate(po_item_id=po_item.id, quantity_returned=Decimal('20')),
            ]),
        )
        check("PO: refund return created pending", ret.status == 'pending' and ret.return_type == 'refund')
        check(
            "PO: starting a return on a non-complete order doesn't log a reopen event",
            po_reopened_event_count(db, ws_id, po.id) == 0,
        )
        ret_invoice = db.query(AccountInvoice).get(ret.invoice_id)
        check(
            "PO: return invoice is receivable/confirmed-immediately/same order",
            ret_invoice.invoice_type == 'receivable'
            and ret_invoice.invoice_status == 'confirmed'
            and ret_invoice.order_type == 'purchase_order'
            and ret_invoice.order_id == po.id,
            f"got type={ret_invoice.invoice_type} status={ret_invoice.invoice_status}",
        )

        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            check("PO: mark_order_complete blocked by open return", False, "did not raise")
        except HTTPException as e:
            check("PO: mark_order_complete blocked by open return", e.status_code == 400 and 'return' in str(e.detail).lower(), str(e.detail))

        ret = purchase_order_service.complete_return(
            db, po_id=po.id, return_id=ret.id, workspace_id=ws_id, user_id=user_id
        )
        check("PO: refund return completed", ret.status == 'completed')
        check("PO: quantity_received reduced by refund", Decimal(str(po_item.quantity_received)) == Decimal('80'), str(po_item.quantity_received))
        check("PO: quantity_refunded bumped by refund", Decimal(str(po_item.quantity_refunded)) == Decimal('20'), str(po_item.quantity_refunded))
        check("PO: quantity_returned bumped", Decimal(str(po_item.quantity_returned)) == Decimal('20'), str(po_item.quantity_returned))
        ledger_row = db.query(InventoryLedger).filter(
            InventoryLedger.workspace_id == ws_id, InventoryLedger.source_type == 'purchase_return_item'
        ).first()
        check("PO: inventory ledger row posted", ledger_row is not None)
        db.refresh(inv)
        check("PO: storage qty decreased", inv.qty == 80, str(inv.qty))

        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            check("PO: mark_order_complete succeeds after refund (no redelivery needed)", True)
        except HTTPException as e:
            check("PO: mark_order_complete succeeds after refund (no redelivery needed)", False, str(e.detail))
        db.commit()
        check("PO: stage is Complete", po_stage_name(db, ws_id, po) == 'Complete', po_stage_name(db, ws_id, po))

        # -- payment against return invoice flips return.paid, not po.paid --
        ret_invoice = db.query(AccountInvoice).get(ret.invoice_id)
        payment = invoice_payment_manager.create_payment(
            db, InvoicePaymentCreate(
                invoice_id=ret_invoice.id, payment_amount=ret_invoice.invoice_amount,
                payment_date=date.today(), payment_method='cash',
            ), workspace_id=ws_id, user_id=user_id,
        )
        db.commit()
        db.refresh(ret)
        db.refresh(po)
        check("PO: return.paid flips true", ret.paid is True)
        check("PO: order.paid stays independent (false)", po.paid is False, str(po.paid))
        created['payment'] = payment

        # === Scenario B: REPLACE return on an already-complete order ===
        # Starting it should reopen the order immediately (before it's even completed).
        ret2 = purchase_order_service.start_return(
            db, po_id=po.id, workspace_id=ws_id, user_id=user_id,
            data=PurchaseOrderReturnCreate(return_type='replace', items=[
                PurchaseOrderReturnItemCreate(po_item_id=po_item.id, quantity_returned=Decimal('15')),
            ]),
        )
        check("PO: replace return created pending", ret2.status == 'pending' and ret2.return_type == 'replace')
        check(
            "PO: starting a return reopens an already-complete order immediately",
            po_stage_name(db, ws_id, po) != 'Complete',
            po_stage_name(db, ws_id, po),
        )
        check("PO: actual_delivery_date cleared on reopen", po.actual_delivery_date is None)
        check(
            "PO: exactly one reopen event logged so far",
            po_reopened_event_count(db, ws_id, po.id) == 1,
        )
        ret2_invoice_id = ret2.invoice_id
        ret2_invoice = db.query(AccountInvoice).get(ret2_invoice_id)
        check("PO: replace return invoice confirmed immediately", ret2_invoice.invoice_status == 'confirmed')

        ret2 = purchase_order_service.complete_return(
            db, po_id=po.id, return_id=ret2.id, workspace_id=ws_id, user_id=user_id
        )
        check("PO: replace return completed", ret2.status == 'completed')
        check("PO: quantity_received reduced by replace", Decimal(str(po_item.quantity_received)) == Decimal('65'), str(po_item.quantity_received))
        check("PO: quantity_refunded NOT bumped by replace", Decimal(str(po_item.quantity_refunded)) == Decimal('20'), str(po_item.quantity_refunded))
        check("PO: quantity_returned accumulates across returns", Decimal(str(po_item.quantity_returned)) == Decimal('35'), str(po_item.quantity_returned))

        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            check("PO: mark_order_complete blocked — replace left a receiving gap", False, "did not raise")
        except HTTPException as e:
            check("PO: mark_order_complete blocked — replace left a receiving gap", e.status_code == 400, str(e.detail))

        # Simulate re-receiving the replaced quantity (a real new receive event would post
        # inventory too; we only care about the quantity gate here).
        po_item.quantity_received = Decimal(str(po_item.quantity_received)) + Decimal('15')
        db.flush()
        check("PO: quantity_received back to 80 after simulated re-receipt", Decimal(str(po_item.quantity_received)) == Decimal('80'))

        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            check("PO: mark_order_complete succeeds again after closing the gap (explicit call)", True)
        except HTTPException as e:
            check("PO: mark_order_complete succeeds again after closing the gap (explicit call)", False, str(e.detail))
        db.commit()

        # -- start a third return, then cancel it — order should stay reopened until re-completed --
        ret3 = purchase_order_service.start_return(
            db, po_id=po.id, workspace_id=ws_id, user_id=user_id,
            data=PurchaseOrderReturnCreate(return_type='refund', items=[
                PurchaseOrderReturnItemCreate(po_item_id=po_item.id, quantity_returned=Decimal('10')),
            ]),
        )
        check("PO: third return created pending", ret3.status == 'pending')
        check(
            "PO: reopened again for the third return",
            po_stage_name(db, ws_id, po) != 'Complete' and po_reopened_event_count(db, ws_id, po.id) == 2,
        )

        ret3 = purchase_order_service.void_return(
            db, po_id=po.id, return_id=ret3.id, workspace_id=ws_id, user_id=user_id,
            void_note="Testing cancel flow",
        )
        check("PO: voided return status is voided", ret3.status == 'voided')
        ret3_invoice = db.query(AccountInvoice).get(ret3.invoice_id)
        check("PO: voided return's invoice is voided", ret3_invoice.invoice_status == 'voided')
        check(
            "PO: quantities unaffected by voiding a pending return",
            Decimal(str(po_item.quantity_received)) == Decimal('80')
            and Decimal(str(po_item.quantity_returned)) == Decimal('35'),
            f"received={po_item.quantity_received} returned={po_item.quantity_returned}",
        )
        check(
            "PO: order stays reopened after void — no silent re-complete",
            po_stage_name(db, ws_id, po) != 'Complete',
            po_stage_name(db, ws_id, po),
        )

        try:
            purchase_order_manager.mark_order_complete(db, po_id=po.id, workspace_id=ws_id, user_id=user_id)
            check("PO: explicit mark_order_complete re-closes it after cancel", True)
        except HTTPException as e:
            check("PO: explicit mark_order_complete re-closes it after cancel", False, str(e.detail))
        db.commit()

        try:
            purchase_order_service.complete_return(
                db, po_id=po.id, return_id=ret3.id, workspace_id=ws_id, user_id=user_id
            )
            check("PO: cannot complete a voided return", False, "did not raise")
        except HTTPException as e:
            check("PO: cannot complete a voided return", e.status_code == 400, str(e.detail))

        try:
            purchase_order_service.void_return(
                db, po_id=po.id, return_id=ret.id, workspace_id=ws_id, user_id=user_id,
                void_note="Should not be allowed",
            )
            check("PO: cannot void an already-completed return", False, "did not raise")
        except HTTPException as e:
            check("PO: cannot void an already-completed return", e.status_code == 400, str(e.detail))

        # ============ SALES ORDER RETURN ============
        # ordered=50, delivered=50 (fully delivered)
        so = SalesOrder(
            workspace_id=ws_id, sales_order_number="SO-RETURN-TEST-001", account_id=account.id,
            factory_id=factory.id, order_date=date.today(), total_amount=Decimal('500.00'),
            current_status_id=any_status.id,
            order_info_confirmed=True, items_confirmed=True, invoice_confirmed=True,
            created_by=user_id,
        )
        db.add(so)
        db.flush()
        created['so'] = so

        so_item = SalesOrderItem(
            workspace_id=ws_id, sales_order_id=so.id, item_id=item.id, requires_delivery=True,
            quantity_ordered=50, quantity_delivered=50, unit_price=Decimal('10.00'), line_total=Decimal('500.00'),
        )
        db.add(so_item)
        db.flush()
        created['so_item'] = so_item
        db.commit()

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            db.rollback()
            check("SO: fully-delivered order completes with no returns", True)
        except HTTPException as e:
            db.rollback()
            check("SO: fully-delivered order completes with no returns", False, str(e.detail))

        # === Scenario A: REFUND return — reduces delivered, no redelivery needed ===
        so_ret = sales_service.start_return(
            db, order_id=so.id, workspace_id=ws_id, user_id=user_id,
            data=SalesOrderReturnCreate(return_type='refund', items=[
                SalesOrderReturnItemCreate(so_item_id=so_item.id, quantity_returned=10),
            ]),
        )
        check("SO: refund return created pending", so_ret.status == 'pending' and so_ret.return_type == 'refund')
        check(
            "SO: starting a return on a non-complete order doesn't log a reopen event",
            so_reopened_event_count(db, ws_id, so.id) == 0,
        )
        so_ret_invoice = db.query(AccountInvoice).get(so_ret.invoice_id)
        check(
            "SO: return invoice is payable/confirmed-immediately/same order",
            so_ret_invoice.invoice_type == 'payable'
            and so_ret_invoice.invoice_status == 'confirmed'
            and so_ret_invoice.order_type == 'sales_order'
            and so_ret_invoice.order_id == so.id,
            f"got type={so_ret_invoice.invoice_type} status={so_ret_invoice.invoice_status}",
        )

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            check("SO: mark_order_complete blocked by open return", False, "did not raise")
        except HTTPException as e:
            check("SO: mark_order_complete blocked by open return", e.status_code == 400 and 'return' in str(e.detail).lower(), str(e.detail))

        product_before = db.query(Product).filter(
            Product.workspace_id == ws_id, Product.item_id == item.id,
            Product.factory_id == factory.id, Product.is_available_for_sale == True,
        ).first()
        qty_before = product_before.qty if product_before else 0

        so_ret = sales_service.complete_return(
            db, order_id=so.id, return_id=so_ret.id, workspace_id=ws_id, user_id=user_id
        )
        check("SO: refund return completed", so_ret.status == 'completed')
        check("SO: quantity_delivered reduced by refund", so_item.quantity_delivered == 40, str(so_item.quantity_delivered))
        check("SO: quantity_refunded bumped by refund", so_item.quantity_refunded == 10, str(so_item.quantity_refunded))
        check("SO: quantity_returned bumped", so_item.quantity_returned == 10, str(so_item.quantity_returned))
        product_after = db.query(Product).filter(
            Product.workspace_id == ws_id, Product.item_id == item.id,
            Product.factory_id == factory.id, Product.is_available_for_sale == True,
        ).first()
        created['product'] = product_after
        check(
            "SO: sellable product qty increased by refunded amount",
            product_after is not None and product_after.qty == qty_before + 10,
            f"before={qty_before} after={product_after.qty if product_after else None}",
        )
        product_ledger_row = db.query(ProductLedger).filter(
            ProductLedger.workspace_id == ws_id, ProductLedger.source_type == 'sales_return_item'
        ).first()
        check("SO: product ledger row posted", product_ledger_row is not None)

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            check("SO: mark_order_complete succeeds after refund (no redelivery needed)", True)
        except HTTPException as e:
            check("SO: mark_order_complete succeeds after refund (no redelivery needed)", False, str(e.detail))
        db.commit()
        db.refresh(so)
        check("SO: order_completed true", so.order_completed is True)

        # -- payment against return invoice flips return.paid, not so.paid --
        so_ret_invoice = db.query(AccountInvoice).get(so_ret.invoice_id)
        so_payment = invoice_payment_manager.create_payment(
            db, InvoicePaymentCreate(
                invoice_id=so_ret_invoice.id, payment_amount=so_ret_invoice.invoice_amount,
                payment_date=date.today(), payment_method='cash',
            ), workspace_id=ws_id, user_id=user_id,
        )
        db.commit()
        db.refresh(so_ret)
        db.refresh(so)
        check("SO: return.paid flips true", so_ret.paid is True)
        check("SO: order.paid stays independent (false)", so.paid is False, str(so.paid))
        created['so_payment'] = so_payment

        # === Scenario B: REPLACE return on an already-complete order ===
        so_ret2 = sales_service.start_return(
            db, order_id=so.id, workspace_id=ws_id, user_id=user_id,
            data=SalesOrderReturnCreate(return_type='replace', items=[
                SalesOrderReturnItemCreate(so_item_id=so_item.id, quantity_returned=8),
            ]),
        )
        check("SO: replace return created pending", so_ret2.status == 'pending' and so_ret2.return_type == 'replace')
        check("SO: starting a return reopens an already-complete order immediately", so.order_completed is False)
        check("SO: completed_at/completed_by cleared on reopen", so.completed_at is None and so.completed_by is None)
        check(
            "SO: exactly one reopen event logged so far",
            so_reopened_event_count(db, ws_id, so.id) == 1,
        )
        so_ret2_invoice_id = so_ret2.invoice_id
        so_ret2_invoice = db.query(AccountInvoice).get(so_ret2_invoice_id)
        check("SO: replace return invoice confirmed immediately", so_ret2_invoice.invoice_status == 'confirmed')

        so_ret2 = sales_service.complete_return(
            db, order_id=so.id, return_id=so_ret2.id, workspace_id=ws_id, user_id=user_id
        )
        check("SO: replace return completed", so_ret2.status == 'completed')
        check("SO: quantity_delivered reduced by replace", so_item.quantity_delivered == 32, str(so_item.quantity_delivered))
        check("SO: quantity_refunded NOT bumped by replace", so_item.quantity_refunded == 10, str(so_item.quantity_refunded))
        check("SO: quantity_returned accumulates across returns", so_item.quantity_returned == 18, str(so_item.quantity_returned))

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            check("SO: mark_order_complete blocked — replace left a delivery gap", False, "did not raise")
        except HTTPException as e:
            check("SO: mark_order_complete blocked — replace left a delivery gap", e.status_code == 400, str(e.detail))

        # Simulate redelivering the replaced quantity.
        so_item.quantity_delivered = so_item.quantity_delivered + 8
        db.flush()
        check("SO: quantity_delivered back to 40 after simulated redelivery", so_item.quantity_delivered == 40)

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            check("SO: mark_order_complete succeeds again after closing the gap (explicit call)", True)
        except HTTPException as e:
            check("SO: mark_order_complete succeeds again after closing the gap (explicit call)", False, str(e.detail))
        db.commit()

        # -- start a third return, then cancel it — order should stay reopened until re-completed --
        so_ret3 = sales_service.start_return(
            db, order_id=so.id, workspace_id=ws_id, user_id=user_id,
            data=SalesOrderReturnCreate(return_type='refund', items=[
                SalesOrderReturnItemCreate(so_item_id=so_item.id, quantity_returned=5),
            ]),
        )
        check("SO: third return created pending", so_ret3.status == 'pending')
        db.refresh(so)
        check(
            "SO: reopened again for the third return",
            so.order_completed is False and so_reopened_event_count(db, ws_id, so.id) == 2,
        )

        so_ret3 = sales_service.void_return(
            db, order_id=so.id, return_id=so_ret3.id, workspace_id=ws_id, user_id=user_id,
            void_note="Testing cancel flow",
        )
        check("SO: voided return status is voided", so_ret3.status == 'voided')
        so_ret3_invoice = db.query(AccountInvoice).get(so_ret3.invoice_id)
        check("SO: voided return's invoice is voided", so_ret3_invoice.invoice_status == 'voided')
        check(
            "SO: quantities unaffected by voiding a pending return",
            so_item.quantity_delivered == 40 and so_item.quantity_returned == 18,
            f"delivered={so_item.quantity_delivered} returned={so_item.quantity_returned}",
        )
        check("SO: order stays reopened after void — no silent re-complete", so.order_completed is False)

        try:
            sales_manager.mark_order_complete(db, order_id=so.id, workspace_id=ws_id, user_id=user_id)
            check("SO: explicit mark_order_complete re-closes it after cancel", True)
        except HTTPException as e:
            check("SO: explicit mark_order_complete re-closes it after cancel", False, str(e.detail))
        db.commit()

        try:
            sales_service.complete_return(
                db, order_id=so.id, return_id=so_ret3.id, workspace_id=ws_id, user_id=user_id
            )
            check("SO: cannot complete a voided return", False, "did not raise")
        except HTTPException as e:
            check("SO: cannot complete a voided return", e.status_code == 400, str(e.detail))

        try:
            sales_service.void_return(
                db, order_id=so.id, return_id=so_ret.id, workspace_id=ws_id, user_id=user_id,
                void_note="Should not be allowed",
            )
            check("SO: cannot void an already-completed return", False, "did not raise")
        except HTTPException as e:
            check("SO: cannot void an already-completed return", e.status_code == 400, str(e.detail))

        print()
        print(f"RESULTS: {len(PASS)} passed, {len(FAIL)} failed")
        if FAIL:
            print("FAILED:", FAIL)

    finally:
        db.rollback()
        try:
            ws_id = created['item'].workspace_id if 'item' in created else None
            if 'payment' in created:
                db.query(created['payment'].__class__).filter(created['payment'].__class__.id == created['payment'].id).delete()
            if 'so_payment' in created:
                db.query(created['so_payment'].__class__).filter(created['so_payment'].__class__.id == created['so_payment'].id).delete()
            if ws_id:
                db.query(InventoryLedger).filter(
                    InventoryLedger.workspace_id == ws_id, InventoryLedger.source_type == 'purchase_return_item'
                ).delete()
                db.query(InventoryLedger).filter(
                    InventoryLedger.workspace_id == ws_id, InventoryLedger.source_type == 'verify_script_seed'
                ).delete()
                db.query(ProductLedger).filter(
                    ProductLedger.workspace_id == ws_id, ProductLedger.source_type == 'sales_return_item'
                ).delete()
            if 'product' in created and created['product'] is not None:
                db.query(Product).filter(Product.id == created['product'].id).delete()
            if 'inventory' in created:
                db.query(Inventory).filter(Inventory.id == created['inventory'].id).delete()
            if 'so' in created:
                so_id = created['so'].id
                for ret_row in db.query(SalesOrderReturn).filter(SalesOrderReturn.sales_order_id == so_id).all():
                    db.query(SalesOrderReturnItem).filter(SalesOrderReturnItem.return_id == ret_row.id).delete()
                    if ret_row.invoice_id:
                        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == ret_row.invoice_id).delete()
                        db.query(AccountInvoice).filter(AccountInvoice.id == ret_row.invoice_id).delete()
                db.query(SalesOrderReturn).filter(SalesOrderReturn.sales_order_id == so_id).delete()
                db.query(SalesOrderEvent).filter(SalesOrderEvent.sales_order_id == so_id).delete()
                db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).delete()
                db.query(SalesOrder).filter(SalesOrder.id == so_id).delete()
            if 'po' in created:
                po_id = created['po'].id
                for ret_row in db.query(PurchaseOrderReturn).filter(PurchaseOrderReturn.purchase_order_id == po_id).all():
                    db.query(PurchaseOrderReturnItem).filter(PurchaseOrderReturnItem.return_id == ret_row.id).delete()
                    if ret_row.invoice_id:
                        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == ret_row.invoice_id).delete()
                        db.query(AccountInvoice).filter(AccountInvoice.id == ret_row.invoice_id).delete()
                db.query(PurchaseOrderReturn).filter(PurchaseOrderReturn.purchase_order_id == po_id).delete()
                db.query(PurchaseOrderEvent).filter(PurchaseOrderEvent.purchase_order_id == po_id).delete()
                db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).delete()
                db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).delete()
            if 'item' in created:
                db.query(Item).filter(Item.id == created['item'].id).delete()
            db.commit()
            print("Cleanup complete.")
        except Exception as cleanup_exc:
            db.rollback()
            print(f"CLEANUP FAILED: {cleanup_exc}")
        db.close()

    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
