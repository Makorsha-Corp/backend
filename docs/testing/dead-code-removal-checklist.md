# Dead-Code Removal Checklist

> Recreated 2026-09-27 by the test pipeline (the original generated list was fully worked and removed in `7be54d5`).
> Entries below were confirmed unreachable by a human reviewer during spec review. Delete the definition (and its now-orphaned imports / tests), tick the box, and run `pytest -q`.

## Managers

### `app/managers/item_manager.py`

- [ ] [`app/managers/item_manager.py:174`](../../app/managers/item_manager.py#L174) — method `ItemManager.search_items` — only caller of the two DAO methods below; its only caller is `ItemService.get_items` — confirmed unreachable in spec review, reviewer-confirmed as dead code in second review round ([item DAO spec Q4](../../tests/unit/dao/item.spec.md))
- [ ] `app/managers/item_manager.py:52` — kind `branch` — name `ItemManager.create_item` (`hasattr(item_data, 'tag_ids')` fallback to `[]`) — reason: input is always `ItemCreate`, which always has `tag_ids` (per account manager Q11 precedent) — confirmed unreachable in spec review (`tests/unit/managers/item_manager.spec.md` P9; decided by Claude under the reviewer's delegation (2026-10-18))
- [ ] `app/managers/item_manager.py:112` — kind `branch` — name `ItemManager.update_item` (`hasattr(item_data, 'tag_ids')` part of the check) — reason: input is always `ItemUpdate`, which always has `tag_ids` (the `is not None` part stays) — confirmed unreachable in spec review (`tests/unit/managers/item_manager.spec.md` P9; decided by Claude under the reviewer's delegation (2026-10-18))

### `app/managers/account_invoice_manager.py`

- [ ] `app/managers/account_invoice_manager.py:553,577-582` — kind `branch` — name `AccountInvoiceManager.sync_items_from_list(is_manual=True)` — reason: the `is_manual` parameter always defaults to `False` and no caller anywhere in `app/` or `tests/` ever passes `is_manual=True`, so the `item_manually_updated` / "Items updated" event branch (lines 577–582) is unreachable — confirmed unreachable in spec review (`account_invoice_manager.spec.md` Q14). No legacy test (outside `tests/unit/`) exercises this branch either.

### `app/managers/account_manager.py`

- [ ] `app/managers/account_manager.py:57` — kind `branch` — name `AccountManager.create_account` (`hasattr(account_data, 'tag_ids')` fallback to `[]`) — reason: input is always `AccountCreate`, which always has `tag_ids` — confirmed unreachable in spec review (`account_manager.spec.md` Q11; suggested answer applied by default, not yet human-reviewed)
- [ ] `app/managers/account_manager.py:151` — kind `branch` — name `AccountManager.update_account` (`hasattr(account_data, 'tag_ids')` part of the check) — reason: input is always `AccountUpdate`, which always has `tag_ids` (the `is not None` part stays) — confirmed unreachable in spec review (`account_manager.spec.md` Q11; suggested answer applied by default, not yet human-reviewed)

### `app/managers/expense_order_manager.py`

- [ ] `app/managers/expense_order_manager.py:287` — method `ExpenseOrderManager.list_expense_orders` — no caller; the API list endpoint (`app/api/v1/endpoints/expense_orders.py:107`) and `ExpenseOrderService` both go through `list_expense_orders_for_hub` instead — confirmed unreachable in spec review (Q24)

### `app/managers/inventory_manager.py`

- [ ] `app/managers/inventory_manager.py:151` — method `InventoryManager.list_inventory` — only caller is `InventoryService.list_inventory`, which itself has no caller (`GET /inventory/` uses `get_inventory_page`) — confirmed unreachable in spec review ([spec Q11](../../tests/unit/managers/inventory_manager.spec.md)). No legacy test under `tests/` (outside `tests/unit/`) references it.

### `app/managers/invoice_payment_manager.py`

- [ ] `app/managers/invoice_payment_manager.py:207` — method `InvoicePaymentManager.get_payment` — no caller in `app/` (the payment-detail endpoint goes through `InvoicePaymentService.get_payment`, which reads straight from the DAO instead) — confirmed unreachable in spec review ([spec Q6](invoice_payment_manager.spec.md)). No legacy test outside `tests/unit/` references it.

### `app/managers/machine_item_manager.py`

- [ ] [`app/managers/machine_item_manager.py:33`](../../app/managers/machine_item_manager.py#L33) — the `Item #{item_id}` fallback of `MachineItemManager._item_name` — reached today only by stored rows with another workspace's item; remove with BUG-1086, which refuses those rows first — confirmed in spec review ([spec Q11](../../tests/unit/managers/machine_item_manager.spec.md)), decided by Claude under the reviewer's delegation (2026-10-31).

### `app/managers/machine_manager.py`

- [ ] `app/managers/machine_manager.py:306-307` — kind `branch` — name `MachineManager.search_machines` (`if maintenance_window == "all": return True` inside `matches_window`) — reason: `matches_window` is only used under `if maintenance_window != "all"` (line 318), so this can never be true — confirmed unreachable in spec review, decided by Claude under the reviewer's delegation (2026-10-30) ([spec P9](../../tests/unit/managers/machine_manager.spec.md)).

### `app/managers/machine_section_assignment_manager.py`

- [ ] `app/managers/machine_section_assignment_manager.py:51` — kind `method` — name `MachineSectionAssignmentManager.clear_for_section` — reason: its only caller is `FactorySectionManager.delete_factory_section` (`app/managers/factory_section_manager.py:298`), which stops calling it with the fix of BUG-908 ("deleting a section leaves its assignment rows untouched") — **remove together with the fix of BUG-908**, not before: it is reachable today and is specified and tested as it behaves today. Decided by Claude under the reviewer's delegation (2026-10-16) in spec review (`tests/unit/dao/machine_section_assignment.spec.md` P3). In the same change drop the then-unused import of `machine_section_assignment_manager` in `app/managers/factory_section_manager.py:13-15`, and delete the two DAO methods listed under `app/dao/machine_section_assignment.py` below and the unit tests of all three.

### `app/managers/po_machine_inventory.py`

- [ ] `app/managers/po_machine_inventory.py:10` — constant `PO_MACHINE_SOURCE_TYPE` — unused; only referenced by the deleted `post_purchase_order_to_machine` — confirmed unreachable in spec review ([spec Q1](po_machine_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] `app/managers/po_machine_inventory.py:13` — function `_quantity_to_int` — only caller (`post_purchase_order_to_machine`) was deleted as dead code in commit `7be54d5`; receiving now goes through `po_receive_inventory.py`'s own quantity-to-int helper — confirmed unreachable in spec review ([spec Q1](po_machine_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] `app/managers/po_machine_inventory.py:31` — function `_weighted_avg_price` — only caller (`post_purchase_order_to_machine`) was deleted as dead code in commit `7be54d5`; average-price updates on the live receive path do not go through this file — confirmed unreachable in spec review ([spec Q1](po_machine_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] `app/managers/po_machine_inventory.py:45` — function `_ensure_machine_item` — only caller (`post_purchase_order_to_machine`) was deleted as dead code in commit `7be54d5`; `po_receive_inventory.py` has its own get-or-create path for machine stock rows — confirmed unreachable in spec review ([spec Q1](po_machine_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] `app/managers/po_machine_inventory.py:64` — function `_ledger_exists_for_source` — only caller (`post_purchase_order_to_machine`) was deleted as dead code in commit `7be54d5`; `po_receive_inventory.py` has its own ledger-exists check — confirmed unreachable in spec review ([spec Q1](po_machine_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] Every callable above is dead; delete the whole file `app/managers/po_machine_inventory.py` (best-practice default, delegated by reviewer — same precedent as `app/utils/work_order_calendar.py`), along with its now-orphaned imports (`app.dao.machine_item.machine_item_dao`, `app.models.machine_item_ledger.MachineItemLedger`) if nothing else uses them.

### `app/managers/po_storage_inventory.py`

- [ ] `app/managers/po_storage_inventory.py:9` — function `_quantity_to_int` — only caller (`post_purchase_order_to_storage`) was deleted as dead code in commit `7be54d5`; receiving now goes through `po_receive_inventory.py`'s own `_delta_to_int` — confirmed unreachable in spec review ([spec Q1](po_storage_inventory.spec.md)). No legacy test outside `tests/unit/` references it.
- [ ] `app/managers/po_storage_inventory.py:27` — function `_weighted_avg_price` — only caller (`post_purchase_order_to_storage`) was deleted as dead code in commit `7be54d5`; average-price updates on the live receive path go through `inventory_movements.post_stock_in` — confirmed unreachable in spec review ([spec Q2](po_storage_inventory.spec.md)). No legacy test outside `tests/unit/` references it.

### `app/managers/sales_manager.py`

- [ ] `app/managers/sales_manager.py:582-583` — kind `branch` — name `SalesManager.set_section_confirm` (`order.account_id is None` check) — reason: `account_id` is a mandatory, non-nullable column on `sales_orders`, so a saved order always has one — the check can never raise its `Select a customer before confirming` error — confirmed unreachable in spec review (`sales_manager.spec.md` Q17). No legacy test (in or outside `tests/unit/`) exercises this branch.
- [ ] `app/managers/sales_manager.py:584-585` — kind `branch` — name `SalesManager.set_section_confirm` (`order.order_date is None` check) — reason: `order_date` is a mandatory, non-nullable column on `sales_orders`, so a saved order always has one — the check can never raise its `Set the order date before confirming` error — confirmed unreachable in spec review (`sales_manager.spec.md` Q17). No legacy test (in or outside `tests/unit/`) exercises this branch.
- [ ] `app/managers/sales_manager.py:769-770` — kind `method` — name `SalesManager.approvals_met` — reason: no caller anywhere in `app/` (the sales flow calls `approval_summary` directly instead) — confirmed unreachable in spec review (`sales_manager.spec.md` Q20). No legacy test exercises it either: the `approvals_met` references in `tests/test_work_order_complete.py`, `tests/test_work_order_complete_as_planned.py` and `tests/test_work_order_event_workers.py` all patch/call the unrelated `WorkOrderManager.approvals_met`, not this one.
- [ ] `app/managers/sales_manager.py:791` — kind `branch` — name `SalesManager.add_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the member check requires a `workspace_members` row and the new approver row both reference `profiles.id` via NOT NULL FKs with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`sales_manager.spec.md` Gap log G8; case-designer gap G8).
- [ ] `app/managers/sales_manager.py:806` — kind `branch` — name `SalesManager.remove_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the approver row just found references `profiles.id` via a NOT NULL FK with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`sales_manager.spec.md` Gap log G8; case-designer gap G8).

### `app/managers/purchase_order_manager.py`

- [ ] `app/managers/purchase_order_manager.py:930` — method `PurchaseOrderManager.list_purchase_orders` — no caller; `GET /purchase-orders/` uses the hub list — confirmed unreachable in spec review (`tests/unit/dao/purchase_order.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-10))
- [ ] `app/managers/purchase_order_manager.py:1507-1508` — kind `method` — name `PurchaseOrderManager.approvals_met` — reason: no caller in `app/` (the invoice service calls `approval_summary` directly) — confirmed unreachable in spec review (`purchase_order_manager.spec.md` Q5; decided by Claude under the reviewer's delegation (2026-11-19))
- [ ] `app/managers/purchase_order_manager.py:798-805` — kind `branch` — name `PurchaseOrderManager._log_admin_field_updates` (`current_status_id` change → `status_updated` "Changed status" event) — reason: `update_purchase_order` always removes `current_status_id` from the update before this runs, so the branch never fires — confirmed unreachable in spec review (`purchase_order_manager.spec.md` Q5; decided by Claude under the reviewer's delegation (2026-11-19))
- [ ] `app/managers/purchase_order_manager.py:632-633` — kind `branch` — name `PurchaseOrderManager._format_scalar_value` (`required_approvals` `None` → `All assigned`) — reason: `required_approvals` is always formatted by `_format_field_value`, which answers it first — confirmed unreachable in spec review (`purchase_order_manager.spec.md` Q5; decided by Claude under the reviewer's delegation (2026-11-19))

### `app/managers/transfer_order_manager.py`

- [ ] `app/managers/transfer_order_manager.py:348` — kind `method` — name `TransferOrderManager.list_transfer_orders` — reason: no caller; `GET /transfer-orders/` goes through `TransferOrderService.list_transfer_orders` → `list_transfer_orders_page` → the hub list, and the DAO's `get_by_workspace` it calls is already ruled dead (`tests/unit/dao/transfer_order.spec.md` Q3) — confirmed unreachable in spec review (`transfer_order_manager.spec.md` Q3; decided by Claude under the reviewer's delegation, 2026-11-19). No legacy test (in or outside `tests/unit/`) calls it.
- [ ] `app/managers/transfer_order_manager.py:663` — kind `branch` — name `TransferOrderManager.add_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the active-membership check requires a `workspace_members` row and the new approver row both reference `profiles.id` via NOT NULL FKs with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`transfer_order_manager.spec.md` Gap log G4), as `sales_manager.spec.md` G8.
- [ ] `app/managers/transfer_order_manager.py:682` — kind `branch` — name `TransferOrderManager.remove_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the approver row just found references `profiles.id` via a NOT NULL FK with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`transfer_order_manager.spec.md` Gap log G4), as `sales_manager.spec.md` G8.

### `app/managers/work_order_manager.py`

- [ ] `app/managers/work_order_manager.py:1467-1471` — kind `branch` — name `WorkOrderManager.remove_item` (second `COMPLETED` / `VOIDED` status check) — reason: `_guard_item_mutations(wo)` on the line before already refuses a completed or voided order (`Work order is completed` / `Work order is voided`), so `Cannot remove parts from a completed or voided work order` can never be raised — confirmed unreachable in spec review (`work_order_manager.spec.md` Q8; decided by Claude under the reviewer's delegation, 2026-11-19).
- [ ] `app/managers/work_order_manager.py:675` — kind `branch` — name `WorkOrderManager.add_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the active-membership check requires a `workspace_members` row and the new approver row both reference `profiles.id` via NOT NULL FKs with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`work_order_manager.spec.md` `add_approver` R6a / Gap log), as `sales_manager.spec.md` G8.
- [ ] `app/managers/work_order_manager.py:694` — kind `branch` — name `WorkOrderManager.remove_approver` (`f'User #{user_id}'` fallback when `profile_dao.get` returns `None`) — reason: the approver row just found references `profiles.id` via a NOT NULL FK with `ON DELETE CASCADE`, so the profile always exists — found unreachable in fill-gaps (`work_order_manager.spec.md` `add_approver` R6a / Gap log), as `sales_manager.spec.md` G8.

## Services

### `app/services/item_service.py`

- [ ] [`app/services/item_service.py:94`](../../app/services/item_service.py#L94) — method `ItemService.get_items` — no caller; `GET /items/` uses `get_items_page` — confirmed unreachable in spec review, reviewer-confirmed as dead code in second review round ([item DAO spec Q4](../../tests/unit/dao/item.spec.md))
- [ ] `app/services/item_service.py:254-255, 263-265` — kind `branch` — name `ItemService.update_item` (`if not item: raise NotFoundError` after the manager call, and the `except NotFoundError` clause that only catches it) — reason: `ItemManager.update_item` either raises or returns the item it loaded, never `None` (item manager FU-1) — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-04) ([service spec D3](../../tests/unit/services/item_service.spec.md))

### `app/services/project_component_service.py`

- [ ] `app/services/project_component_service.py:100-101` — kind `branch` — name `ProjectComponentService.update_component` (`if not component: return None` after `require_component_access`) — reason: the guard already answers 404 `Project component not found` for a component not in the workspace, so the second lookup always finds it — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-04) ([service spec D1](../../tests/unit/services/project_component_service.spec.md)). Remove with the endpoint's matching `if not …: raise HTTPException(404)` at `app/api/v1/endpoints/project_components.py:76-77`.
- [ ] `app/services/project_component_service.py:134-135` — kind `branch` — name `ProjectComponentService.delete_component` (`if not component: return False`) — same reason — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-04) ([service spec D1](../../tests/unit/services/project_component_service.spec.md)). Remove with `app/api/v1/endpoints/project_components.py:91-92`; the `get_by_id` check at `project_components.py:48-49` goes with it.

### `app/services/inventory_service.py`

- [ ] `app/services/inventory_service.py:54` — method `InventoryService.list_inventory` — no caller; `GET /inventory/` uses `get_inventory_page` — confirmed unreachable in spec review ([spec Q11](../../tests/unit/managers/inventory_manager.spec.md)). No legacy test under `tests/` (outside `tests/unit/`) references it.

### `app/services/machine_work_service.py`

- [ ] `app/services/machine_work_service.py:117-118` — kind `branch` — name `upcoming_work` (`if machine is None: continue`) — reason: the query inner-joins the machine and requires `machine_id IS NOT NULL`, so every bucket has a machine — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec D5](../../tests/unit/services/machine_work_service.spec.md)). The `assert`s at :99, :167, :168 stay (type hints).

### `app/services/account_invoice_service.py`

- [ ] `app/services/account_invoice_service.py:443-445` — kind `branch` — name `AccountInvoiceService.confirm_invoice` (`invoice_pre.invoice_amount = Decimal(str(po.total_amount or 0))` + flush, with the `get_invoice` read at :440-442 that only feeds it) — reason: the manager's confirm always replaces the amount with the line sum (BUG-627), so the write has no visible effect — confirmed in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q7](../../tests/unit/services/account_invoice_service.spec.md))
- [ ] [`app/services/account_invoice_service.py:189`](../../app/services/account_invoice_service.py#L189) — method `AccountInvoiceService.list_accounts_hub_page` (:189-205) — no caller in `app/` or `tests/`; the accounts hub goes through `AccountService` — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q8](../../tests/unit/services/account_invoice_service.spec.md))
- [ ] `app/services/account_invoice_service.py:473-482` — kind `branch` — name `AccountInvoiceService.confirm_invoice` (`else` → newest linked expense order → `notify_invoice_action(entity_type="expense_order")`) — reason: unreachable **once BUG-2969 is fixed** (an expense order's invoice is refused before confirm); remove with that fix, not before — owner OQ-60 (2026-11-21) ([service spec K8](../../tests/unit/services/account_invoice_service.spec.md))

### `app/services/account_service.py`

- [ ] `app/services/account_service.py:72-94` — method `AccountService.get_account` — no caller in `app/`, `scripts/` or `tests/`; every endpoint uses `get_account_with_tags` — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q5](../../tests/unit/services/account_service.spec.md))
- [ ] `app/services/account_service.py:356-357, 365-367` — kind `branch` — name `AccountService.update_account` (`if not account: raise NotFoundError` after the manager call, and the `except NotFoundError` clause that only repeats the general `except`) — reason: `AccountManager.update_account` returns the account or raises `ValueError`, never `None` — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q4](../../tests/unit/services/account_service.spec.md))

### `app/services/ledger_service.py`

- [ ] `app/services/ledger_service.py:354` — method `LedgerService.get_transactions_by_order` — reason: forwards to `LedgerManager.get_transactions_by_order`, which does not exist (any call raises `AttributeError`), and no endpoint, service, script or test calls it — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q2](../../tests/unit/services/ledger_service.spec.md))

### `app/services/purchase_order_service.py`

- [ ] `app/services/purchase_order_service.py:382-386` — kind `branch` — name `PurchaseOrderService.create_purchase_order` (after the 5-attempt PO-number retry loop: `raise last_error` and the 500 `Failed to create purchase order`) — reason: the loop is left only after 5 number clashes (any other error leaves it earlier), so only the 409 branch can run — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q7](../../tests/unit/services/purchase_order_service.spec.md))

### `app/services/sales_service.py`

- [ ] `app/services/sales_service.py:59-63` — kind `branch` — name `SalesService._attach_receivable_invoice_to_sales_order` (`if order.account_id is None: raise 422 "Cannot create invoice: sales order has no customer account"`) — reason: `sales_orders.account_id` is `NOT NULL`, so no stored order reaches it — confirmed unreachable in spec review; decided by Claude under the reviewer's delegation (2026-11-21) ([service spec Q9](../../tests/unit/services/sales_service.spec.md))

## DAOs

### `app/dao/item.py`

- [ ] [`app/dao/item.py:73`](../../app/dao/item.py#L73) — method `ItemDAO.search_by_name_in_workspace` — confirmed unreachable in spec review ([spec Q4](../../tests/unit/dao/item.spec.md))
- [ ] [`app/dao/item.py:101`](../../app/dao/item.py#L101) — method `ItemDAO.get_active_items_in_workspace` — confirmed unreachable in spec review ([spec Q4](../../tests/unit/dao/item.spec.md))

### `app/dao/inventory.py`

- [ ] `app/dao/inventory.py:146` — kind `method` — name `InventoryDAO.get_by_workspace` (override) — reason: its only caller is `InventoryManager.list_inventory` (`app/managers/inventory_manager.py:158`), which is itself listed above as dead code; `GET /inventory/` goes through `list_filtered` / `count_filtered` — confirmed unreachable in spec review (`tests/unit/dao/inventory.spec.md` Q3; reviewer answered `remove` on 2026-10-10). Delete together with `InventoryManager.list_inventory`. No legacy test (in or outside `tests/unit/`) references it.
- [ ] `app/dao/inventory.py:309` — kind `method` — name `InventoryDAO.soft_delete` — reason: no caller anywhere in `app/` or `tests/`; `DELETE /inventory/{id}/` ("clear stock") sets the quantity to zero and never soft-deletes the row — confirmed unreachable in spec review (`tests/unit/dao/inventory.spec.md` Q4; reviewer answered `remove` on 2026-10-10). Keep `InventoryDAO.restore` (used by `ensure_for_factory_item_type` for legacy soft-deleted rows).
- [ ] `app/dao/inventory.py:297,305-306` — kind `parameter` + `branch` — name `InventoryDAO.get_by_item(inventory_type=...)` and its `if inventory_type:` filter — reason: the only caller (`ItemSummaryService._inventory_rows`, `app/services/item_summary_service.py:234`) never passes `inventory_type` — confirmed unreachable in spec review (`tests/unit/dao/inventory.spec.md` Q5; reviewer answered `remove` on 2026-10-10). Legacy test `tests/test_item_summary_empty.py` patches `get_by_item` as a whole and does not pass the parameter.

### `app/dao/inventory_ledger.py`

- [ ] `app/dao/inventory_ledger.py:105` — kind `method` — name `InventoryLedgerDAO.get_by_order` — reason: no caller anywhere in `app/` or `tests/`, and it cannot work: it filters on `InventoryLedger.order_id`, a column the model does not have, so any call raises `AttributeError` before a query is sent — confirmed unreachable in spec review (`tests/unit/dao/inventory_ledger.spec.md` Q1; reviewer answered `remove` on 2026-10-10). No legacy test references it.
- [ ] `app/dao/inventory_ledger.py:44` — kind `method` — name `InventoryLedgerDAO.get_by_id_and_workspace` (override) — reason: no caller anywhere in `app/` or `tests/` (no "show one ledger entry" endpoint); the override is line-for-line the inherited `BaseDAO.get_by_id_and_workspace`, which stays — confirmed unreachable in spec review (`tests/unit/dao/inventory_ledger.spec.md` Q2; reviewer answered `remove` — the override only — on 2026-10-10). No legacy test references it.

### `app/dao/machine.py`

- [ ] `app/dao/machine.py:54` — kind `method` — name `DAOMachine.get_active_by_workspace` — reason: no caller anywhere in `app/` or `tests/` (a search for `get_active_by_workspace` finds only this definition and the same-named methods of `app/dao/production_formula.py` / `app/dao/production_line.py`, which are called on their own DAOs); the machines page goes through `search_advanced` — confirmed unreachable in spec review (`tests/unit/dao/machine.spec.md` Q4; reviewer answered `remove` on 2026-10-10). Keep `DAOMachine.restore` (`app/dao/machine.py:80`): it has no caller yet, but the reviewer decided to keep it (spec Q5, "keep restore") — it is specified and tested, not dead code.
- [ ] `app/dao/machine.py:28,35-36` and `app/dao/machine.py:41,50-51` — kind `parameter` + `branch` — name `DAOMachine.get_by_factory(include_deleted=...)` / `DAOMachine.get_by_section(include_deleted=...)` and their `if not include_deleted:` checks — reason: none of the callers passes it (`app/managers/machine_manager.py:470`, `app/utils/work_order_generation.py:23,28,33`), so the "include deleted" side never runs; after removal the `is_deleted == False` filter becomes unconditional — confirmed unreachable in spec review (`tests/unit/dao/machine.spec.md` Q6; reviewer answered `remove` — the parameter only — on 2026-10-10).

### `app/dao/machine_item.py`

- [ ] `app/dao/machine_item.py:64,73-74` — kind `parameter` — name `DAOMachineItem.get_by_item(skip=..., limit=...)` and its `.offset` / `.limit` — reason: the only caller (`ItemSummaryService._machine_placements`, `app/services/item_summary_service.py:307`) passes neither, so `skip` is always 0 and `limit` always 500 — **remove in the same change as the fix of BUG-982**, which takes the cap away — confirmed unreachable in spec review, decided by Claude under the reviewer's delegation (2026-10-30) (`tests/unit/dao/machine_item.spec.md` P7, per machine DAO Q6 precedent). Legacy test `tests/test_item_summary_empty.py` patches `get_by_item` as a whole and does not pass them.

### `app/dao/machine_item_ledger.py`

- [ ] `app/dao/machine_item_ledger.py:91` — kind `method` — name `MachineItemLedgerDAO.get_by_order` — reason: no caller anywhere in `app/` or `tests/`, and none of the four writers of this table sets `order_id`, so it could only ever return nothing; entries link to their source through `source_type` / `source_id` (same as `InventoryLedgerDAO.get_by_order` above) — confirmed unreachable in spec review, decided by Claude under the reviewer's delegation (2026-10-30) (`tests/unit/dao/machine_item_ledger.spec.md` Q5). No legacy test references it.

### `app/dao/machine_section_assignment.py`

- [ ] `app/dao/machine_section_assignment.py:57` — kind `method` — name `DAOMachineSectionAssignment.clear_for_section` — reason: its only caller is `MachineSectionAssignmentManager.clear_for_section` (listed above under Managers), which loses its only caller with the fix of BUG-908 — **remove together with the fix of BUG-908**, not before: it is reachable today and is specified and tested as it behaves today (`tests/unit/dao/machine_section_assignment.spec.md` `clear_for_section` R1–R8). Decided by Claude under the reviewer's delegation (2026-10-16) in spec review (spec P3). Removing it also closes BUG-907 (its 10 000-row cap) — mark BUG-907 accordingly in `docs/testing/bugs.md`. No legacy test (outside `tests/unit/`) calls it.
- [ ] `app/dao/machine_section_assignment.py:24` — kind `method` — name `DAOMachineSectionAssignment.get_by_section` — reason: its only caller is `DAOMachineSectionAssignment.clear_for_section` (entry above) — **remove together with the fix of BUG-908** and that method. Decided by Claude under the reviewer's delegation (2026-10-16) in spec review (spec P3). Removing it also closes BUG-906 (its missing sort order). Not to be confused with `DAOMachine.get_by_section` (`app/dao/machine.py:39`), which stays. No legacy test (outside `tests/unit/`) calls it.

### `app/dao/item_tag_assignment.py`

- [ ] `app/dao/item_tag_assignment.py:119` — kind `method` — name `ItemTagAssignmentDAO.remove_all_tags_from_item` — reason: its only caller is `ItemManager.update_item` (`app/managers/item_manager.py:133`), which stops removing every link of the item with the fix of BUG-934 (staying tags keep their link; only removed tags lose theirs) and BUG-935 (links to deleted tags are left alone) — **remove together with the fix of BUG-934**, not before: it is reachable today and is specified and tested as it behaves today. Decided by Claude under the reviewer's delegation (2026-10-17) in spec review (`tests/unit/dao/item_tag_assignment.spec.md` P2). Delete its unit tests in the same change.

### `app/dao/subscription_plan.py`

- [ ] `app/dao/subscription_plan.py:13` — kind `method` — name `SubscriptionPlanDAO.get_by_name` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-02)).

### `app/dao/sales_order_item.py`

- [ ] `app/dao/sales_order_item.py:30` — kind `method` — name `DAOSalesOrderItem.get_by_item` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-02))

### `app/dao/project_component_attachment.py`

- [ ] `app/dao/project_component_attachment.py` — kind `module` — name `ProjectComponentAttachmentDAO` with `get_link` and the singleton `project_component_attachment_dao` — reason: not imported anywhere in `app/`, `tests/` or `scripts/`, and nothing writes `project_component_attachments`; confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-02)). The model and table stay: dropping them is a separate migration, after checking production has no rows

### `app/dao/production_line.py`

- [ ] `app/dao/production_line.py:66` — kind `method` — name `ProductionLineDAO.get_by_machine` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; confirmed unreachable in spec review (`tests/unit/dao/production_line.spec.md` P1; decided by Claude under the reviewer's delegation (2026-11-02))

### `app/dao/production_batch.py`

- [ ] `app/dao/production_batch.py:148` — kind `method` — name `ProductionBatchDAO.get_by_date_range` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; the calendar has a query of its own; confirmed unreachable in spec review (`tests/unit/dao/production_batch.spec.md` P1; decided by Claude under the reviewer's delegation (2026-11-02)). Removes the only use of the `date` import
- [ ] `app/dao/production_batch.py:203,216-217` — kind `parameter` + `branch` — name `ProductionBatchDAO.generate_batch_number(year=...)` and its `if year is None:` — reason: the only caller (`create_batch`) never passes it; confirmed unreachable in spec review (`tests/unit/dao/production_batch.spec.md` P2; decided by Claude under the reviewer's delegation (2026-11-02)). Remove with BUG-1334

### `app/dao/production_batch_item.py`

- [ ] `app/dao/production_batch_item.py:67` — kind `method` — name `ProductionBatchItemDAO.get_by_item` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; confirmed unreachable in spec review (`tests/unit/dao/production_batch_item.spec.md` P1; decided by Claude under the reviewer's delegation (2026-11-02))

### `app/dao/product_ledger.py`

- [ ] `app/dao/product_ledger.py:61` — kind `method` — name `ProductLedgerDAO.get_by_id_and_workspace` (override) — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; the override is line-for-line the inherited `BaseDAO.get_by_id_and_workspace`, which stays; confirmed unreachable in spec review (`tests/unit/dao/product_ledger.spec.md` P4; decided by Claude under the reviewer's delegation (2026-11-02))

### `app/dao/refresh_token.py`

- [ ] `app/dao/refresh_token.py:32` — kind `method` — name `RefreshTokenDAO.get_by_id` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (its neighbours `list_active_for_user` and `cleanup_expired` were already removed); confirmed unreachable in spec review (`tests/unit/dao/refresh_token.spec.md` Q3; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/attachment.py`

- [ ] `app/dao/attachment.py:76` — kind `method` — name `AttachmentDAO.restore` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; no restore endpoint for attachments; confirmed unreachable in spec review (`tests/unit/dao/attachment.spec.md` P3; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/attachment_link.py`

- [ ] `app/dao/attachment_link.py:42` — kind `method` — name `AttachmentLinkDAO.get_by_entity` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (the `get_by_entity` calls in `app/` are the discussion and financial audit log DAOs'); confirmed unreachable in spec review (`tests/unit/dao/attachment_link.spec.md` P3; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/attachment_markup_event.py`

- [x] `app/dao/attachment_markup_event.py:18` — kind `parameter` — name `AttachmentMarkupEventDAO.list_for_attachment(limit=200)` and its `.limit(limit)` (line 27) — reason: the only caller (`AttachmentMarkupManager.list_events`) never passes it; **remove together with the fix of BUG-1437** (all entries returned, no cap) (`tests/unit/dao/attachment_markup_event.spec.md` P1; decided by Claude under the reviewer's delegation (2026-11-03)) — removed with the BUG-1437 fix in bugfix/dao-attachment_markup_event (2026-11-28)

### `app/dao/project_attachment.py`

- [ ] `app/dao/project_attachment.py` — kind `module` — name `ProjectAttachmentDAO` with `get_by_project`, `get_link` and the singleton `project_attachment_dao` — reason: not imported anywhere in `app/`, `tests/` or `scripts/`, and nothing writes `project_attachments` (project files are `attachment_links` rows); confirmed unreachable in spec review (`tests/unit/dao/project_attachment.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-03)). The model, its back-references (`Project.attachments`, `Attachment.project_links`, `Profile.project_attachments`) and the table stay: dropping them is a separate migration, after checking production has no rows

### `app/dao/work_order_completer.py`

- [ ] `app/dao/work_order_completer.py:33` — kind `method` — name `WorkOrderCompleterDAO.get_user_ids_by_order` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (only the assignee DAO's twin is used); confirmed unreachable in spec review (`tests/unit/dao/work_order_completer.spec.md` P3; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/account.py`

- [ ] `app/dao/account.py:15` — kind `method` — name `AccountDAO.search_by_name_in_workspace` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (`GET /accounts/` searches through `get_accounts_in_workspace`); confirmed unreachable in spec review (`tests/unit/dao/account.spec.md` P3; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/account_tag.py`

- [ ] `app/dao/account_tag.py:37` — kind `parameter` — name `AccountTagDAO.get_active_tags_in_workspace(skip=0, limit=100)` and its `.offset` / `.limit` (lines 57–58) — reason: the only caller (`AccountTagService.get_tags`) never passes them; **remove together with the fix of BUG-1485** (every active tag returned, no cap) (`tests/unit/dao/account_tag.spec.md` P5; decided by Claude under the reviewer's delegation (2026-11-03))

### `app/dao/account_tag_assignment.py`

- [ ] `app/dao/account_tag_assignment.py:118` — kind `method` — name `AccountTagAssignmentDAO.remove_all_tags_from_account` — reason: its only caller is `AccountManager.update_account` (`app/managers/account_manager.py:173`), which stops removing every link of the account with the fix of BUG-870 (staying tags keep their link) and BUG-1487 (links to deleted tags are left alone) — **remove together with the fix of BUG-870**, not before: it is reachable today and is specified and tested as it behaves today (`tests/unit/dao/account_tag_assignment.spec.md` P2; decided by Claude under the reviewer's delegation (2026-11-03)). `get_account_tag_dao` and the module global `account_tag_dao` (lines 10–19) exist only for it and go with it. Delete its unit tests in the same change.

### `app/dao/invoice_payment.py`

- [ ] `app/dao/invoice_payment.py:58` — kind `method` — name `InvoicePaymentDAO.get_by_date_range` — no caller in `app/`, `scripts/` or `tests/` (its siblings `get_by_payment_method` / `get_recent_payments` were already removed) — confirmed unreachable in spec review (`tests/unit/dao/invoice_payment.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-09))

### `app/dao/sales_order.py`

- [ ] `app/dao/sales_order.py:91` — kind `method` — name `DAOSalesOrder.get_by_factory` — reason: no caller anywhere in `app/`, `tests/` or `scripts/`; confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-09)).
- [ ] `app/dao/sales_order.py:112` — kind `method` — name `DAOSalesOrder.get_by_status` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (filters on the vestigial `current_status_id`); confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-09)).

### `app/dao/sales_delivery.py`

- [ ] `app/dao/sales_delivery.py:116` — kind `method` — name `DAOSalesDelivery.get_by_date_range` — reason: no caller anywhere in `app/`, `tests/` or `scripts/` (the calendar service queries `sales_deliveries` itself); confirmed unreachable in spec review (decided by Claude under the reviewer's delegation (2026-11-09)).

### `app/dao/project_component_item_ledger.py`

- [ ] `app/dao/project_component_item_ledger.py:107` — kind `method` — name `ProjectComponentItemLedgerDAO.get_by_order` — reason: no caller in `app/` or `tests/`; nothing writes the table (OQ-27), and it ignores `order_type` — confirmed unreachable in spec review (`tests/unit/dao/project_component_item_ledger.spec.md` Q2; decided by Claude under the reviewer's delegation (2026-11-09), per machine item ledger DAO Q5 precedent).

### `app/dao/purchase_order.py`

- [ ] `app/dao/purchase_order.py:138` — method `PurchaseOrderDAO.get_by_workspace` — only caller `PurchaseOrderManager.list_purchase_orders`, itself uncalled — confirmed unreachable in spec review (`tests/unit/dao/purchase_order.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-10))
- [ ] `app/dao/purchase_order.py:328` — method `PurchaseOrderDAO.get_next_number` — alias of `allocate_po_number`, no caller — confirmed unreachable in spec review (`tests/unit/dao/purchase_order.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-10))

### `app/dao/transfer_order.py`

- [ ] `app/dao/transfer_order.py:194` — method `TransferOrderDAO.get_by_workspace` (override) — only caller `TransferOrderManager.list_transfer_orders` (`app/managers/transfer_order_manager.py:348`), which nothing calls; the manager method is a candidate too (spec FU-2) — confirmed unreachable in spec review (`tests/unit/dao/transfer_order.spec.md` Q3; decided by Claude under the reviewer's delegation (2026-11-10))

### `app/dao/work_order.py`

- [ ] `app/dao/work_order.py:372` — method `WorkOrderDAO.restore` — no caller in `app/`, `tests/` or `scripts/`; no endpoint restores a work order — confirmed unreachable in spec review (`tests/unit/dao/work_order.spec.md` Q4; decided by Claude under the reviewer's delegation (2026-11-10))

### `app/dao/account_invoice.py`

- [ ] `app/dao/account_invoice.py:468` — method `AccountInvoiceDAO.get_by_order` — no caller in `app/`, `tests/` or `scripts/` (order code finds invoices through the order's own `invoice_id`); it also ignores `order_type` — confirmed unreachable in spec review (`tests/unit/dao/account_invoice.spec.md` Q1; decided by Claude under the reviewer's delegation (2026-11-10))

## Core

### `app/core/exceptions.py`

- [ ] `app/core/exceptions.py:54` — kind class `AuthenticationError` — never raised or imported anywhere in `app/` (auth failures use FastAPI `HTTPException`/security deps); no legacy test outside `tests/unit/` references it — confirmed unreachable in spec review

## Utils

### `app/utils/datetime_serialize.py`

- [ ] `app/utils/datetime_serialize.py:14` — function `serialize_utc_datetime` — no caller in `app/` (responses get `Z` from `ensure_utc_z_in_json`); legacy tests `test_serialize_utc_datetime_naive` and `test_serialize_utc_datetime_aware` in `tests/test_datetime_serialize.py` exercise it and must be deleted with it (also drop it from that file's import) — confirmed unreachable in spec review

### `app/utils/order_catalog_items.py`

- [ ] [`app/utils/order_catalog_items.py:16`](../../app/utils/order_catalog_items.py#L16) — parameter `assert_unique_catalog_item_ids(detail_template=...)` (and the `detail_template or ...` fallback on line 29; hard-code `'{name} appears more than once on this order'` / use an f-string) — no caller passes it (purchase, sales and transfer order managers all omit it) — confirmed unreachable in spec review ([spec Q1](../../tests/unit/utils/order_catalog_items.spec.md)). No legacy test under `tests/` references it.

### `app/utils/work_order_calendar.py`

- [ ] `app/utils/work_order_calendar.py:5` — function `work_order_calendar_date` — no application code imports it; the same rule lives in the `WorkOrder` response schema's `calendar_date` computed field (`app/schemas/work_order.py`) and the DAO's `_work_order_calendar_date_expr` (`app/dao/work_order.py`) — confirmed unreachable in spec review. It is the module's only callable, so delete the whole file `app/utils/work_order_calendar.py` (best-practice default, delegated by reviewer). Legacy test `tests/test_work_order_calendar.py` exercises it and must be deleted in the same change.

### `app/utils/work_order_generation.py`

- [ ] `app/utils/work_order_generation.py:27` — branch `if factory_section_id:` (second section lookup, L27–31 in `resolve_template_machine_ids`) — unreachable: the earlier `if section_id:` branch always returns first when `factory_section_id` is set; duplicates its query — confirmed unreachable in spec review
