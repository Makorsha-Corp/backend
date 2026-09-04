# Dead-Code Removal Checklist

> Generated 2026-09-03. **Heuristic** static reference scan over `app/`, `tests/`, `alembic/`, `scripts/`. Each entry below is a function / method / class whose name is **never referenced anywhere** outside its own definition — no call, no import, no identifier-string.

**86 candidates across 46 files.** Same items are flagged ⚠️ in the two unit-test checklists; deleting one here means striking its ⚠️ line there too.

## How to work this list (from the IDE)

For each unchecked item:

1. Open `file:line` (click the ref).
2. **Find Usages** on the symbol — PyCharm `Alt+F7`, VS Code `Shift+F12`.
3. Also grep the repo for the name as a **string** (dynamic dispatch, `getattr`, router wiring).
4. Decide:
   - **truly unused** → delete the definition (and its now-orphaned imports / tests); tick the box.
   - **used after all** → tick the box, append `— KEEP: <where it's used>`.
   - **should be used but isn't (bug/regression)** → tick, append `— BUG: <note>`, open a ticket.
5. Run `pytest -q` after each file's worth of deletions.

### Blind spots (why an item might actually be live)
- Dynamic dispatch: `getattr`, string-keyed registries.
- Callers that lived only in Alembic data migrations since squashed.
- Called from the frontend repo or ad-hoc scripts not scanned here.
- Reverse name-collision can *hide* a real dead one — treat this list as a floor.

### Already spot-checked — confirmed dead, safe to delete
- [ ] `app/managers/po_machine_inventory.py` → `post_purchase_order_to_machine` — legacy PO→inventory posting, superseded by po_receive_inventory
- [ ] `app/managers/po_storage_inventory.py` → `post_purchase_order_to_storage` — same; only its PO_INVENTORY_SOURCE_TYPE constant is still imported
- [ ] `app/services/sales_service.py` → `SalesService.create_sales_order` — dead wrapper; endpoint calls create_sales_order_from_dict directly
- [ ] `app/services/account_service.py` → `AccountService.get_accounts` — no caller

---

## Managers — 7 candidate(s), 6 file(s)

### `app/managers/machine_section_assignment_manager.py`

- [ ] [`app/managers/machine_section_assignment_manager.py:51`](app/managers/machine_section_assignment_manager.py#L51) — method `MachineSectionAssignmentManager.get_for_machine`

### `app/managers/po_machine_inventory.py`

- [ ] [`app/managers/po_machine_inventory.py:86`](app/managers/po_machine_inventory.py#L86) — func `post_purchase_order_to_machine`  **← confirmed dead: legacy PO→inventory posting, superseded by po_receive_inventory**

### `app/managers/po_storage_inventory.py`

- [ ] [`app/managers/po_storage_inventory.py:50`](app/managers/po_storage_inventory.py#L50) — func `post_purchase_order_to_storage`  **← confirmed dead: same; only its PO_INVENTORY_SOURCE_TYPE constant is still imported**

### `app/managers/production_formula_manager.py`

- [ ] [`app/managers/production_formula_manager.py:265`](app/managers/production_formula_manager.py#L265) — method `ProductionFormulaManager.get_formula_base_output`

### `app/managers/purchase_order_manager.py`

- [ ] [`app/managers/purchase_order_manager.py:829`](app/managers/purchase_order_manager.py#L829) — method `PurchaseOrderManager.details_complete_for_invoice`
- [ ] [`app/managers/purchase_order_manager.py:844`](app/managers/purchase_order_manager.py#L844) — method `PurchaseOrderManager._all_sections_confirmed` _(private helper)_

### `app/managers/transfer_order_manager.py`

- [ ] [`app/managers/transfer_order_manager.py:125`](app/managers/transfer_order_manager.py#L125) — method `TransferOrderManager._all_items_transferred` _(private helper)_

## Services — 4 candidate(s), 4 file(s)

### `app/services/account_service.py`

- [ ] [`app/services/account_service.py:159`](app/services/account_service.py#L159) — method `AccountService.get_accounts`  **← confirmed dead: no caller**

### `app/services/item_service.py`

- [ ] [`app/services/item_service.py:123`](app/services/item_service.py#L123) — method `ItemService.get_items_with_tags`

### `app/services/machine_work_service.py`

- [ ] [`app/services/machine_work_service.py:189`](app/services/machine_work_service.py#L189) — method `MachineWorkService.has_upcoming_work`

### `app/services/sales_service.py`

- [ ] [`app/services/sales_service.py:278`](app/services/sales_service.py#L278) — method `SalesService.create_sales_order`  **← confirmed dead: dead wrapper; endpoint calls create_sales_order_from_dict directly**

## Core — 3 candidate(s), 1 file(s)

### `app/core/exceptions.py`

- [ ] [`app/core/exceptions.py:110`](app/core/exceptions.py#L110) — class `RateLimitError`
- [ ] [`app/core/exceptions.py:123`](app/core/exceptions.py#L123) — class `InternalServerError`
- [ ] [`app/core/exceptions.py:134`](app/core/exceptions.py#L134) — class `ServiceUnavailableError`

## DAOs — 72 candidate(s), 35 file(s)

### `app/dao/account.py`

- [ ] [`app/dao/account.py:43`](app/dao/account.py#L43) — method `AccountDAO.get_by_account_code_in_workspace`
- [ ] [`app/dao/account.py:67`](app/dao/account.py#L67) — method `AccountDAO.get_active_accounts_in_workspace`
- [ ] [`app/dao/account.py:188`](app/dao/account.py#L188) — method `AccountDAO.get_accounts_with_invoices_enabled`

### `app/dao/account_invoice.py`

- [ ] [`app/dao/account_invoice.py:496`](app/dao/account_invoice.py#L496) — method `AccountInvoiceDAO.get_overdue_invoices`
- [ ] [`app/dao/account_invoice.py:522`](app/dao/account_invoice.py#L522) — method `AccountInvoiceDAO.get_invoices_with_payments_enabled`

### `app/dao/account_tag_assignment.py`

- [ ] [`app/dao/account_tag_assignment.py:48`](app/dao/account_tag_assignment.py#L48) — method `AccountTagAssignmentDAO.get_accounts_for_tag`

### `app/dao/attachment.py`

- [ ] [`app/dao/attachment.py:42`](app/dao/attachment.py#L42) — method `AttachmentDAO.get_multi_active`
- [ ] [`app/dao/attachment.py:64`](app/dao/attachment.py#L64) — method `AttachmentDAO.get_by_uploader`

### `app/dao/base.py`

- [ ] [`app/dao/base.py:195`](app/dao/base.py#L195) — method `BaseDAO.create_in_workspace`

### `app/dao/delivery_method.py`

- [ ] [`app/dao/delivery_method.py:25`](app/dao/delivery_method.py#L25) — method `DAODeliveryMethod.get_active_delivery_methods`

### `app/dao/department.py`

- [ ] [`app/dao/department.py:26`](app/dao/department.py#L26) — method `DAODepartment.get_active_departments`

### `app/dao/inventory_ledger.py`

- [ ] [`app/dao/inventory_ledger.py:52`](app/dao/inventory_ledger.py#L52) — method `InventoryLedgerDAO.get_by_factory_and_item`

### `app/dao/invoice_payment.py`

- [ ] [`app/dao/invoice_payment.py:88`](app/dao/invoice_payment.py#L88) — method `InvoicePaymentDAO.get_by_payment_method`
- [ ] [`app/dao/invoice_payment.py:142`](app/dao/invoice_payment.py#L142) — method `InvoicePaymentDAO.get_recent_payments`

### `app/dao/item.py`

- [ ] [`app/dao/item.py:100`](app/dao/item.py#L100) — method `ItemDAO.get_by_sku_in_workspace`

### `app/dao/item_tag.py`

- [ ] [`app/dao/item_tag.py:58`](app/dao/item_tag.py#L58) — method `ItemTagDAO.get_user_tags_in_workspace`

### `app/dao/item_tag_assignment.py`

- [ ] [`app/dao/item_tag_assignment.py:69`](app/dao/item_tag_assignment.py#L69) — method `ItemTagAssignmentDAO.get_items_with_tag`
- [ ] [`app/dao/item_tag_assignment.py:97`](app/dao/item_tag_assignment.py#L97) — method `ItemTagAssignmentDAO.get_items_with_tags`
- [ ] [`app/dao/item_tag_assignment.py:156`](app/dao/item_tag_assignment.py#L156) — method `ItemTagAssignmentDAO.remove_assignment`

### `app/dao/machine.py`

- [ ] [`app/dao/machine.py:54`](app/dao/machine.py#L54) — method `DAOMachine.get_running_machines`

### `app/dao/machine_item_ledger.py`

- [ ] [`app/dao/machine_item_ledger.py:167`](app/dao/machine_item_ledger.py#L167) — method `MachineItemLedgerDAO.get_consumption_entries`

### `app/dao/production_batch.py`

- [ ] [`app/dao/production_batch.py:42`](app/dao/production_batch.py#L42) — method `ProductionBatchDAO.get_by_batch_number`
- [ ] [`app/dao/production_batch.py:201`](app/dao/production_batch.py#L201) — method `ProductionBatchDAO.get_in_progress_batches`
- [ ] [`app/dao/production_batch.py:224`](app/dao/production_batch.py#L224) — method `ProductionBatchDAO.get_completed_batches`

### `app/dao/production_batch_item.py`

- [ ] [`app/dao/production_batch_item.py:63`](app/dao/production_batch_item.py#L63) — method `ProductionBatchItemDAO.get_inputs_for_batch`
- [ ] [`app/dao/production_batch_item.py:81`](app/dao/production_batch_item.py#L81) — method `ProductionBatchItemDAO.get_outputs_for_batch`
- [ ] [`app/dao/production_batch_item.py:99`](app/dao/production_batch_item.py#L99) — method `ProductionBatchItemDAO.get_waste_for_batch`
- [ ] [`app/dao/production_batch_item.py:117`](app/dao/production_batch_item.py#L117) — method `ProductionBatchItemDAO.get_byproducts_for_batch`

### `app/dao/production_formula.py`

- [ ] [`app/dao/production_formula.py:133`](app/dao/production_formula.py#L133) — method `ProductionFormulaDAO.get_formula_versions`

### `app/dao/production_formula_item.py`

- [ ] [`app/dao/production_formula_item.py:63`](app/dao/production_formula_item.py#L63) — method `ProductionFormulaItemDAO.get_inputs_for_formula`
- [ ] [`app/dao/production_formula_item.py:81`](app/dao/production_formula_item.py#L81) — method `ProductionFormulaItemDAO.get_outputs_for_formula`
- [ ] [`app/dao/production_formula_item.py:99`](app/dao/production_formula_item.py#L99) — method `ProductionFormulaItemDAO.get_waste_for_formula`
- [ ] [`app/dao/production_formula_item.py:117`](app/dao/production_formula_item.py#L117) — method `ProductionFormulaItemDAO.get_byproducts_for_formula`

### `app/dao/production_formula_stage.py`

- [ ] [`app/dao/production_formula_stage.py:34`](app/dao/production_formula_stage.py#L34) — method `ProductionFormulaStageDAO.get_max_stage_order`

### `app/dao/production_line.py`

- [ ] [`app/dao/production_line.py:114`](app/dao/production_line.py#L114) — method `ProductionLineDAO.get_standalone_lines`

### `app/dao/project_attachment.py`

- [ ] [`app/dao/project_attachment.py:46`](app/dao/project_attachment.py#L46) — method `ProjectAttachmentDAO.get_by_attachment`
- [ ] [`app/dao/project_attachment.py:88`](app/dao/project_attachment.py#L88) — method `ProjectAttachmentDAO.link_exists`
- [ ] [`app/dao/project_attachment.py:105`](app/dao/project_attachment.py#L105) — method `ProjectAttachmentDAO.unlink`
- [ ] [`app/dao/project_attachment.py:128`](app/dao/project_attachment.py#L128) — method `ProjectAttachmentDAO.get_attachment_count`

### `app/dao/project_component_attachment.py`

- [ ] [`app/dao/project_component_attachment.py:19`](app/dao/project_component_attachment.py#L19) — method `ProjectComponentAttachmentDAO.get_by_project_component`
- [ ] [`app/dao/project_component_attachment.py:47`](app/dao/project_component_attachment.py#L47) — method `ProjectComponentAttachmentDAO.get_by_attachment`
- [ ] [`app/dao/project_component_attachment.py:89`](app/dao/project_component_attachment.py#L89) — method `ProjectComponentAttachmentDAO.link_exists`
- [ ] [`app/dao/project_component_attachment.py:106`](app/dao/project_component_attachment.py#L106) — method `ProjectComponentAttachmentDAO.unlink`
- [ ] [`app/dao/project_component_attachment.py:129`](app/dao/project_component_attachment.py#L129) — method `ProjectComponentAttachmentDAO.get_attachment_count`

### `app/dao/project_component_item_ledger.py`

- [ ] [`app/dao/project_component_item_ledger.py:158`](app/dao/project_component_item_ledger.py#L158) — method `ProjectComponentItemLedgerDAO.get_consumption_entries`

### `app/dao/project_member.py`

- [ ] [`app/dao/project_member.py:36`](app/dao/project_member.py#L36) — method `ProjectMemberDAO.get_project_ids_for_user`

### `app/dao/refresh_token.py`

- [ ] [`app/dao/refresh_token.py:36`](app/dao/refresh_token.py#L36) — method `RefreshTokenDAO.list_active_for_user`
- [ ] [`app/dao/refresh_token.py:131`](app/dao/refresh_token.py#L131) — method `RefreshTokenDAO.cleanup_expired`

### `app/dao/sales_delivery.py`

- [ ] [`app/dao/sales_delivery.py:138`](app/dao/sales_delivery.py#L138) — method `DAOSalesDelivery.get_pending_deliveries`

### `app/dao/sales_delivery_item.py`

- [ ] [`app/dao/sales_delivery_item.py:29`](app/dao/sales_delivery_item.py#L29) — method `DAOSalesDeliveryItem.get_by_sales_order_item`
- [ ] [`app/dao/sales_delivery_item.py:46`](app/dao/sales_delivery_item.py#L46) — method `DAOSalesDeliveryItem.calculate_total_delivered`

### `app/dao/sales_order.py`

- [ ] [`app/dao/sales_order.py:90`](app/dao/sales_order.py#L90) — method `DAOSalesOrder.get_by_account`
- [ ] [`app/dao/sales_order.py:153`](app/dao/sales_order.py#L153) — method `DAOSalesOrder.get_pending_deliveries`
- [ ] [`app/dao/sales_order.py:168`](app/dao/sales_order.py#L168) — method `DAOSalesOrder.get_uninvoiced_orders`

### `app/dao/sales_order_item.py`

- [ ] [`app/dao/sales_order_item.py:50`](app/dao/sales_order_item.py#L50) — method `DAOSalesOrderItem.get_pending_items`

### `app/dao/subscription_plan.py`

- [ ] [`app/dao/subscription_plan.py:24`](app/dao/subscription_plan.py#L24) — method `SubscriptionPlanDAO.get_active_plans`

### `app/dao/work_order_type.py`

- [ ] [`app/dao/work_order_type.py:25`](app/dao/work_order_type.py#L25) — method `DAOWorkOrderType.get_active_types`

### `app/dao/workspace.py`

- [ ] [`app/dao/workspace.py:16`](app/dao/workspace.py#L16) — method `WorkspaceDAO.get_by_owner`
- [ ] [`app/dao/workspace.py:24`](app/dao/workspace.py#L24) — method `WorkspaceDAO.increment_usage`
- [ ] [`app/dao/workspace.py:42`](app/dao/workspace.py#L42) — method `WorkspaceDAO.decrement_usage`
- [ ] [`app/dao/workspace.py:60`](app/dao/workspace.py#L60) — method `WorkspaceDAO.check_limit`

### `app/dao/workspace_audit_log.py`

- [ ] [`app/dao/workspace_audit_log.py:14`](app/dao/workspace_audit_log.py#L14) — method `WorkspaceAuditLogDAO.get_workspace_logs`
- [ ] [`app/dao/workspace_audit_log.py:44`](app/dao/workspace_audit_log.py#L44) — method `WorkspaceAuditLogDAO.get_user_logs`
- [ ] [`app/dao/workspace_audit_log.py:65`](app/dao/workspace_audit_log.py#L65) — method `WorkspaceAuditLogDAO.get_logs_by_action`

### `app/dao/workspace_invitation.py`

- [ ] [`app/dao/workspace_invitation.py:18`](app/dao/workspace_invitation.py#L18) — method `WorkspaceInvitationDAO.get_by_workspace_and_email`
- [ ] [`app/dao/workspace_invitation.py:57`](app/dao/workspace_invitation.py#L57) — method `WorkspaceInvitationDAO.mark_as_accepted`
- [ ] [`app/dao/workspace_invitation.py:66`](app/dao/workspace_invitation.py#L66) — method `WorkspaceInvitationDAO.mark_as_expired`
- [ ] [`app/dao/workspace_invitation.py:74`](app/dao/workspace_invitation.py#L74) — method `WorkspaceInvitationDAO.mark_as_cancelled`
- [ ] [`app/dao/workspace_invitation.py:104`](app/dao/workspace_invitation.py#L104) — method `WorkspaceInvitationDAO.cleanup_expired_invitations`

### `app/dao/workspace_member.py`

- [ ] [`app/dao/workspace_member.py:25`](app/dao/workspace_member.py#L25) — method `WorkspaceMemberDAO.get_user_workspaces`
- [ ] [`app/dao/workspace_member.py:55`](app/dao/workspace_member.py#L55) — method `WorkspaceMemberDAO.get_workspace_members_count`
- [ ] [`app/dao/workspace_member.py:66`](app/dao/workspace_member.py#L66) — method `WorkspaceMemberDAO.update_role`

