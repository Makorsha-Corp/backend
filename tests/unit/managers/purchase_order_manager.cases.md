# Test cases — `app/managers/purchase_order_manager.py`

> **Spec:** `tests/unit/managers/purchase_order_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps G1–G14 applied: G1 sync model named; G2 field labels asserted (CF-01, CF-03, CF-04, UP-20, UP-26, UP-27); G3 UP-42 refused at the schema, plus UP-49 (`null`); G4 check-order cards UP-45 … UP-48, AI-14 … AI-16, CR-20; G5 WF-05, WF-06 (patched seed); G6 CP-02 now xfail BUG-1881, plus CP-05 (outer spaces), CP-06, CS-06; G7 `None` return asserted on one card per method; G8 lock cards cite their own rules; G9 DL-13 also checks `invoice_items`; G10 DL-17 reads `metadata_json`; G11 bounds now spec rules; G12 SS-06 checks the workflow is untouched, plus SS-09; G13 every delete card passes `user_id` (DEL), plus DL-21 (TypeError); G14 lock cards AA-15, RM-10. No IDs retired.
> **Revision:** 3 (2026-11-21) — spec G15: CF-01 … CF-04 pass `fields` as a dict of field → label (`_collect_field_changes` R1), expected values unchanged; BUG-2876 narrowed, so SY-22 is a pass card and RT-01 … RT-03 cite `_recalc_totals` R1a; LS-04/05 and CR-06 stay strict xfail.
> **Revision:** 4 (2026-11-21) — verifier findings 1 and 3–11 (case-missing): GI-04 retired (non-strict, physical order; GI-05 stays). New pass cards UP-50 (order date label), UP-51 (unconfirm the draft invoice, not locked), VC-12 … VC-14 (destination arrives in the update), FV-09 (`None` → `—`), FL-08 and AI-17 (a completed order stays financially locked, RP5), SY-26 … SY-28 (event metadata, additions n+1 / n+2, empty order), AS-07 (one approver, no threshold), AS-08 (threshold 0 with approvers). FV-02 sends `"project"`.
> **Counts:** 467 cases · 364 expected-to-pass · 103 expected-to-fail (bugs) · 12 deferred

## Reviewer summary
- **Per callable:** helpers `_parse_unit_price` 4 · `_line_subtotal` 5 (2 bug) · `_all_items_have_positive_unit_price` 4 · `get_po_by_invoice_id` 4 (1 bug) · `is_po_financially_locked` 8 · `unlink_invoice_from_po` 5 · `unconfirm_sections_after_invoice_void` 4 · `reset_approvals` 6 · `_ensure_po_stage_statuses` 6 (2 bug) · `_raise_po_workflow_setup_error` 2 · `_resolve_po_stage_status_id` 4 (1 bug) · `_resolve_po_workflow_id` 6 · `_all_items_fully_received` 6 · `_current_stage_name` 6 · `_invoice_payment_status` 3 · `sync_po_for_linked_invoice` 4 · `sync_po_paid` 9 · `_is_po_complete_stage` 6 (2 bug) · `_derive_po_stage_name` 8 · `sync_po_stage` 9 (1 bug) · `mark_order_complete` 16 (2 bug) · `reopen_for_return` 4 (1 bug) · `create_purchase_order` 20 (10 bug) · schemas 24 (19 bug) · `update_purchase_order` 51 (19 bug) + `_validate_section_confirm` 14 · formatters (`_format_scalar_value` 7, `_format_destination_id` 13, `_format_field_value` 9 (2 bug)) · change collectors / logger 8 · confirm-field helpers 6 · `apply_post_invoice_confirms` 4 · `get_purchase_order` 4 · hub 6 · `delete_purchase_order` 21 (6 bug) · `_quantity_received_decimal` 2 · `_validate_ordered_vs_received` 3 · `_ensure_catalog_item_not_on_po` 4 · `add_item` 17 (5 bug) · `update_item` 18 (4 bug) · `remove_item` 11 (2 bug) · `sync_items` 28 (3 bug) · `get_items` 5 (2 bug) · `_recalc_totals` 3 · `list_approvers` 5 (2 bug) · `approval_summary` 8 (1 bug) · `add_approver` 15 (4 bug) · `remove_approver` 10 (4 bug) · `set_approval` 13 (5 bug) · `log_event` 5 (2 bug) · `list_events` 4 (1 bug).
- **Expected-to-fail by bug:** BUG-2872 10 · BUG-2873 2 · BUG-2874 8 · BUG-2875 3 · BUG-2876 3 · BUG-2877 8 · BUG-2878 5 · BUG-2879 9 · BUG-2880 2 · BUG-2881 5 · BUG-2882 11 · BUG-2883 2 · BUG-2885 3 · BUG-2886 2 · BUG-2887 3 · BUG-2888 2 · BUG-1017 11 · BUG-1192 2 · BUG-1195 3 · BUG-1200 1 · BUG-1202 1 · BUG-1881 5 · BUG-2637 1 · BUG-2789 1. All are strict (GI-04, the one non-strict card, was retired in Revision 4). BUG-2884 is superseded by BUG-2887 (no card); BUG-2735 (`locked`) is a dead value, so no card writes it; BUG-2631 is integration-only (Deferred).
- **Depth:** full (step 1a): the module writes order state, money totals and approvals.
- **Notable design choices:**
  - **Locks (BUG-2872):** one statement-recorder card per state-checking writer (complete, update, add / update / remove item, sync, set_approval, delete): a `FOR UPDATE` on `purchase_orders`, no `SKIP LOCKED` / `NOWAIT`, before the first write; add and remove approver are included. Each card cites its own rule (`add_item` R7, `remove_item` R4, `sync_items` R9, `delete_purchase_order` R6, `add_approver` R7, `remove_approver` R5). The race itself is Deferred.
  - **BUG-2887** is tested at the schema (SCH-21 … 23, also the stored value and `null`); SCH-24 is the pass side (what the line edit keeps). No manager card sends `quantity_received`.
  - **Rounding (BUG-2876):** the pass side is CR-07 (each stored line 0.13, the database rounds today); the xfails are the create total (CR-06) and the helper (LS-04/05). Since G15, `_recalc_totals` holds today (R1a: lines read back from the database are already rounded), so SY-22 and RT-01 … RT-03 are pass cards. `update_item` / `add_item` cannot show it in one call, because earlier lines come back rounded from the database.
  - **Destinations (BUG-2874):** W0 and W2 factories / machines, a deleted factory and machine, each its own card; live W1 rows are the pass side (CR-12, UP-40). Project components are today's behaviour, *revisit after launch* (CR-18, FD-10/11).
  - **Voided (BUG-2882):** each writer has its card with every other blocker absent (sections unconfirmed, invoice unlinked), so today the call succeeds. `get_purchase_order` (GP-01) and delete (DL-10) are the pass side.
  - **Stage rows:** cards that need a missing or misspelled stage build a fresh workspace WX (Q4: BUG-1220 now stops deleting stages). WE-02 hides every other purchase workflow with an in-test UPDATE (`Author: claude`).
  - **Formatter cards** (FV-01/02/04/05, CU, IS-01, BS-02) call a pure or read-only formatter once per value in one comprehension, so a value table stays one card.
  - **Q7:** CR-08 pins that the 409 for a repeated item comes after the order, approver and `created` event were flushed (the caller rolls back).
  - **BUG-1195:** DL-17, DL-18 pass the new required `user_id` and fail today with TypeError; DL-21 calls without it and expects TypeError. Every other delete card calls through DEL, which adds `user_id=U2.id` once the parameter exists, so they pass today and after the fix.
  - **Check order (spec Overview, G4):** UP-45 (foreign supplier on a supplier-confirmed order → 400, pass), UP-46 (supplier before destination), UP-47 (voided before complete), UP-48 (complete before the lock guard), AI-14 (404 before 409), AI-15 (guard before the item check, pass), AI-16 (voided before the guard), CR-20 (supplier before line items).
  - **Workflow not found (G5):** WF-05, WF-06 patch `app.managers.purchase_order_manager.ensure_po_workflow_record` to return `None` (`Author: claude` on WF-06, which hides the other workflows).
- **Needs a decision:** none. All 13 gaps of revision 1 are closed (spec Gap log G1–G13), and G14 adds the approver lock rules.

## Conventions for this module

**IDs.** `POM` = `app/managers/purchase_order_manager.py`. `PU` _parse_unit_price · `LS` _line_subtotal · `PP` _all_items_have_positive_unit_price · `GI` get_po_by_invoice_id · `FL` is_po_financially_locked · `UL` unlink_invoice_from_po · `UV` unconfirm_sections_after_invoice_void · `RA` reset_approvals · `ES` _ensure_po_stage_statuses · `WE` _raise_po_workflow_setup_error · `RS` _resolve_po_stage_status_id · `WF` _resolve_po_workflow_id · `FR` _all_items_fully_received · `CS` _current_stage_name · `IP` _invoice_payment_status · `SL` sync_po_for_linked_invoice · `SP` sync_po_paid · `CP` _is_po_complete_stage · `DS` _derive_po_stage_name · `SS` sync_po_stage · `MC` mark_order_complete · `RO` reopen_for_return · `CR` create_purchase_order · `UP` update_purchase_order · `VC` _validate_section_confirm (through update) · `SF` _format_scalar_value · `FD` _format_destination_id · `FV` _format_field_value · `CF` _collect_field_changes · `CI` _collect_item_field_changes · `LF` _log_field_change_event · `CU` _confirmed_supplier/detail_update_fields · `IS` _items_structure_confirmed · `BS` _base_sections_confirmed · `AP` apply_post_invoice_confirms · `GP` get_purchase_order · `HUB` hub pass-throughs · `DL` delete_purchase_order · `QR` _quantity_received_decimal · `VO` _validate_ordered_vs_received · `EC` _ensure_catalog_item_not_on_po · `AI` add_item · `UI` update_item · `RI` remove_item · `SY` sync_items · `GT` get_items · `RT` _recalc_totals · `LA` list_approvers · `AS` approval_summary · `AA` add_approver · `RM` remove_approver · `SA` set_approval · `LE` log_event · `LV` list_events · `SCH` schemas (target `schema`).

**Actors and fixed values.**
- `M` = `purchase_order_manager` (`from app.managers.purchase_order_manager import purchase_order_manager`). Module functions `_parse_unit_price`, `_line_subtotal`, `_all_items_have_positive_unit_price` are imported from the same module. `db` = the test's real session, passed first; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<snake_case>`: `PurchaseOrder`, `PurchaseOrderItem`, `PurchaseOrderApprover`, `PurchaseOrderEvent` (JSON attribute `metadata_json`, column `metadata`), `PurchaseOrderReturn`, `PoReceiveEvent`, `Status`, `OrderWorkflow`, `Account`, `Factory`, `Machine`, `Project`, `ProjectComponent`, `Item`, `AccountInvoice`, `WorkspaceMember`, `WorkspaceAuditLog` (JSON attribute `metadata_json`, column `metadata`); `InvoiceItem` from `app.models.invoice_item`. Schemas from `app.schemas.purchase_order`: `PurchaseOrderCreate`, `PurchaseOrderUpdate`, `PurchaseOrderItemCreate` (= **IC**), `PurchaseOrderItemUpdate`, `PurchaseOrderItemSyncUpdate`, `PurchaseOrderItemSyncRequest`. **SYNC(remove_ids=…, updates=…, additions=…)** = `PurchaseOrderItemSyncRequest(remove_ids=…, updates=…, additions=…)` (spec `sync_items` Inputs). DAO: `purchase_order_dao` (`app.dao.purchase_order`). `HTTPException` (fastapi), `ValidationError` (pydantic), `Decimal`, `date`, `datetime`, `text`, `select`, `func`, `patch`, `re`, `uuid` the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. T0 = `datetime(2026, 3, 1, 8, 0)`; T1 … T4 = `datetime(2026, 3, 4, 9, 0)`, `(…, 10, 0)`, `(…, 11, 0)`, `(…, 12, 0)` (naive). D1 = `date(2026, 3, 2)`, D2 = `date(2026, 3, 20)`, D3 = `date(2026, 4, 15)`. TODAY = `date.today()`, read at the start of the test (not mocked). NOW = `datetime(2026, 5, 6, 7, 8, 9)`.
- **clock** (only on cards that say so) = for the When, `patch("app.managers.purchase_order_manager.utcnow", return_value=NOW)`.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)` with names `"Alice Rahman"`, `"Bob Karim"`, `"Chitra Das"`, `"Dev Paul"`, `"Esha Roy"`.
2. Memberships `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…, position=…)`: U1 in W1 `active` / `"Buyer"`; U2 in W1 `active` / `None`; U4 in W1 `invited` / `None`; U5 in W1 `inactive` / `None`; U3 in **W2 only**, `active` / `"Boss"`.
3. For W0, then W1, then W2 (suffix `0`, `1`, `9`): SDk, SPk, SRk, SCk = `Status(workspace_id=…, name=…, comment="po stage")` named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`; WFk = `OrderWorkflow(workspace_id=…, name="Purchase Order", type="purchase", status_sequence=[SDk.id, SPk.id, SRk.id, SCk.id])`; Fk = `Factory(workspace_id=…, name="Main Plant", abbreviation=f"MP{k}")`; Mk = `Machine(workspace_id=…, factory_id=Fk.id, name=f"Press {k}")`; Ak = `Account(workspace_id=…, name=…)` (`"Northwind West"`, `"Northwind Traders"`, `"Northwind East"`); Ik = `Item(workspace_id=…, name="Bolt", name_normalized="bolt", unit="pcs")`.
4. W1 extras: A3 = Account `"Alpha Parts"`; I2 = Item `"Nut"` / `"nut"`; I3 = Item `"Washer"` / `"washer"`; PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project 1", description="Main")`; C1 = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Part 1")`.

**Given rows.** Inserted directly, never through `M`, flushed one at a time in the order written. After "but", a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **po "n"** = `PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-n", account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id)`; every flag (`supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed`, `invoice_ever_linked`, `paid`, `voided`) at its default `False`. "po of W0 / W9" uses that workspace's A, F, SD, WF.
- **stage X** = `current_status_id X.id`. **confirmed** = `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`, stage SP1.
- **locked by V** = `invoice_id V.id`, `invoice_ever_linked True`, all four confirms `True`, stage SR1 (V is a confirmed invoice). **complete by V** = locked by V, but stage SC1, `actual_delivery_date D2`.
- **voided** = `voided True`, `voided_at T4`, `voided_by U1.id`, `void_note "Entered twice"`, `invoice_id None`; the confirms stay as the card gives them.
- **line k of O, I** = `PurchaseOrderItem(workspace_id=O.workspace_id, purchase_order_id=O.id, line_number=k, item_id=I.id, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("0.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("20.00"))`; `quantity_refunded`, `quantity_returned` left at 0.
- **invl(V)** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=1, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"))`.
- **inv(s, p)** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_status=s, payment_status=p, invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=D1, allow_payments=True)`; "of W9" uses W2 and A9. Built before the order that links it.
- **appr(O, U)** = `PurchaseOrderApprover(workspace_id=O.workspace_id, purchase_order_id=O.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=T1)`. **approved** = `approved True`, `approved_at T2`.
- **ret(O, "n")** = `PurchaseOrderReturn(workspace_id=O.workspace_id, purchase_order_id=O.id, return_number=f"PR-{TAG}-n", return_type="refund", created_by=U1.id)` (status default `"pending"`). **completed** = `status "completed"`, `completed_at T3`, `completed_by U1.id`. **cancelled** = `status "voided"`.
- **rev(O)** = `PoReceiveEvent(workspace_id=O.workspace_id, purchase_order_id=O.id, event_type="receive", created_at=T0)`.
- **evt(O, at)** = `PurchaseOrderEvent(workspace_id=O.workspace_id, purchase_order_id=O.id, event_type="created", description="Logged", performed_by=U1.id, created_at=at)`.
- **deleted factory** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **deleted machine** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **WX** = `make_workspace(db)` built in the card, holding only the rows the card lists. **stX(name)** = `Status(workspace_id=WX.id, name=name, comment="po stage")`.
- A row of another workspace hanging on a W1 row is invalid data, inserted directly on purpose.
- **mem(…)** = an in-memory `PurchaseOrderItem(...)` with only the named attributes, never added to the session (pure-helper cards).

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its snapshot taken after the last Given line. **gone(X)** = after `db.expire_all()`, `db.get(type(X), X.id) is None`.
- **EV(O)** = after `db.expire_all()`, the `purchase_order_events` rows with `purchase_order_id == O.id`, ordered by `id`. **types(O)** = `[e.event_type for e in EV(O)]`. **LINES(O)** = O's `purchase_order_items` rows by `line_number`, after `db.expire_all()`.
- **nothing written** = the row counts of `purchase_orders`, `purchase_order_items`, `purchase_order_approvers`, `purchase_order_events`, `statuses`, `order_workflows`, `account_invoices`, `workspace_audit_logs` (all workspaces) equal their values before the call.
- **session clean** = `not db.new`, `not db.dirty`, `not db.deleted`, checked before anything is re-read.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` (no savepoint, it would hide a write); `exc.value.status_code` and `exc.value.detail` are compared with `==`. `raises: ValidationError` = around the schema's construction; "loc" = `exc.value.errors()[0]["loc"]`. Long dashes in texts are U+2014; copy them.
- **Statement recorder** = every SQL statement the session sends during the When is recorded. `selects` = the SELECTs, `written` = the INSERT / UPDATE / DELETE statements, in send order. **locks O first** = some SELECT whose `FROM` names `purchase_orders` contains `FOR UPDATE`, has neither `SKIP LOCKED` nor `NOWAIT`, and is sent before the first statement of `written`. A recorder card ends its Given with `db.expunge_all()` unless it passes a loaded object; ids come from objects built before.
- **DEL(id)** = `M.delete_purchase_order(db, po_id=id, workspace_id=W1.id)`, plus `user_id=U2.id` when `"user_id" in inspect.signature(M.delete_purchase_order).parameters` (`import inspect`). So the card passes `user_id` once the parameter exists (spec R5a) and still runs today. Only DL-17, DL-18 (always `user_id=U2.id`) and DL-21 (never) call the method directly.
- **commit spy** = `sp = db.begin_nested()` directly before the call, inside `with patch.object(db, "commit", wraps=db.commit) as cm:`; after the call `cm.call_count == 0`, then `sp.rollback()`.
- **Stage read:** `current_status_id` is checked on the re-read row; never read `order_completed` / `current_status_name` without `db.expire_all()` first.
- **Return values:** every card where the call returns asserts it. `create_purchase_order`, `update_purchase_order`, `mark_order_complete`, `sync_items` → an order with `.id` of the target (new) order; `add_item`, `update_item` → the line; `remove_item` → the removed line object; `add_approver`, `set_approval` → the approver row; `log_event` → the new event. `delete_purchase_order`, `remove_approver`, `unlink_invoice_from_po`, `unconfirm_sections_after_invoice_void`, `reset_approvals`, `apply_post_invoice_confirms`, `_recalc_totals`, `sync_po_for_linked_invoice`, `_ensure_po_stage_statuses`, `_log_field_change_event` → `None` (spec Overview "Return values"); one card per method asserts it.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown, also when a parameter does not exist yet.

**Externals.** None is mocked (time only via **clock**). **Race simulations.** None.

## Module functions `_parse_unit_price`, `_line_subtotal`, `_all_items_have_positive_unit_price`

### POM-PU-01 — no price gives None
- **Rules:** `_parse_unit_price` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _parse_unit_price(None)`.

**Then**
1. returns: `result is None`.

### POM-PU-02 — a Decimal keeps its scale
- **Rules:** `_parse_unit_price` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _parse_unit_price(Decimal("5.00"))`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `str(result) == "5.00"`.

### POM-PU-03 — zero is a price, not None
- **Rules:** `_parse_unit_price` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _parse_unit_price(0)`.

**Then**
1. returns: `result is not None`.
2. returns: `result == Decimal("0")`.

### POM-PU-04 — a float goes through its text
- **Rules:** `_parse_unit_price` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _parse_unit_price(2.5)`.

**Then**
1. returns: `str(result) == "2.5"`.

### POM-LS-01 — an unpriced line has no subtotal
- **Rules:** `_line_subtotal` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _line_subtotal(Decimal("3.00"), None)`.

**Then**
1. returns: `result is None`.

### POM-LS-02 — whole cents multiply exactly
- **Rules:** `_line_subtotal` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _line_subtotal(Decimal("2"), Decimal("3.50"))`.

**Then**
1. returns: `result == Decimal("7.00")`.

### POM-LS-03 — a zero price gives a zero subtotal, not None
- **Rules:** `_line_subtotal` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _line_subtotal(Decimal("4"), Decimal("0"))`.

**Then**
1. returns: `result is not None`.
2. returns: `result == Decimal("0")`.

### POM-LS-04 — 1.25 × 0.10 is rounded half up to 0.13
- **Rules:** `_line_subtotal` R2 [BUG-2876]
- **Kind:** bug
- **Expect:** xfail BUG-2876
- **Fails today on:** Then 1 (today the value is 0.1250, unrounded)

**Given**
1. Standing rows only.

**When**
- `result = _line_subtotal(Decimal("1.25"), Decimal("0.10"))`.

**Then**
1. returns: `result == Decimal("0.13")`.

### POM-LS-05 — 0.5 × 0.25 is rounded half up to 0.13
- **Rules:** `_line_subtotal` R2 [BUG-2876]
- **Kind:** bug
- **Expect:** xfail BUG-2876
- **Fails today on:** Then 1 (today 0.125)

**Given**
1. Standing rows only.

**When**
- `result = _line_subtotal(Decimal("0.5"), Decimal("0.25"))`.

**Then**
1. returns: `result == Decimal("0.13")`.

### POM-PP-01 — no lines is not "all priced"
- **Rules:** `_all_items_have_positive_unit_price` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _all_items_have_positive_unit_price([])`.

**Then**
1. returns: `result is False`.

### POM-PP-02 — every line priced above zero
- **Rules:** `_all_items_have_positive_unit_price` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = mem(unit_price=Decimal("2.00")); B = mem(unit_price=Decimal("0.01")).

**When**
- `result = _all_items_have_positive_unit_price([A, B])`.

**Then**
1. returns: `result is True`.

### POM-PP-03 — one unpriced line fails the check
- **Rules:** `_all_items_have_positive_unit_price` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = mem(unit_price=Decimal("2.00")); B = mem(unit_price=None).

**When**
- `result = _all_items_have_positive_unit_price([A, B])`.

**Then**
1. returns: `result is False`.

### POM-PP-04 — one line at 0.00 fails the check
- **Rules:** `_all_items_have_positive_unit_price` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(unit_price=Decimal("0.00")); B = mem(unit_price=Decimal("2.00")).

**When**
- `result = _all_items_have_positive_unit_price([A, B])`.

**Then**
1. returns: `result is False`.

## `PurchaseOrderManager.get_po_by_invoice_id`

### POM-GI-01 — the workspace's order for the invoice
- **Rules:** `get_po_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `result = M.get_po_by_invoice_id(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.

### POM-GI-02 — no order links the invoice
- **Rules:** `get_po_by_invoice_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1" (no invoice).

**When**
- `result = M.get_po_by_invoice_id(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### POM-GI-03 — orders of W0 and W2 on the same invoice are never returned
- **Rules:** `get_po_by_invoice_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O0 = po of W0 "0", but `invoice_id V.id` (invalid data).
3. O9 = po of W9 "9", but `invoice_id V.id` (invalid data).

**When**
- `result = M.get_po_by_invoice_id(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### POM-GI-05 — the lookup query has an ORDER BY
- **Rules:** `get_po_by_invoice_id` R1 [BUG-2637]
- **Kind:** bug
- **Expect:** xfail BUG-2637
- **Fails today on:** Then 2 (no ORDER BY today)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.get_po_by_invoice_id(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: the first SELECT whose `FROM` names `purchase_orders` contains `"ORDER BY"`.

## `PurchaseOrderManager.is_po_financially_locked`

### POM-FL-01 — no invoice: not locked
- **Rules:** `is_po_financially_locked` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-02 — an invoice id that does not exist: not locked
- **Rules:** `is_po_financially_locked` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. `O.invoice_id = MISSING` in memory only (not flushed).

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-03 — a confirmed invoice of W2: not locked
- **Rules:** `is_po_financially_locked` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V9 = inv("confirmed", "unpaid") of W9.
2. O = po "1", but `invoice_id V9.id` (invalid data).

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-04 — a confirmed invoice of W0: not locked
- **Rules:** `is_po_financially_locked` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V0 = `AccountInvoice(workspace_id=W0.id, account_id=A0.id, invoice_type="payable", invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=D1, allow_payments=True)`.
2. O = po "1", but `invoice_id V0.id` (invalid data).

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-05 — a confirmed invoice of the workspace locks
- **Rules:** `is_po_financially_locked` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is True`.

### POM-FL-06 — a draft invoice does not lock
- **Rules:** `is_po_financially_locked` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-07 — a voided invoice does not lock
- **Rules:** `is_po_financially_locked` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("voided", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is False`.

### POM-FL-08 — a completed order stays financially locked
- **Rules:** `is_po_financially_locked` R2; RP5 (PO)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but complete by V.

**When**
- `result = M.is_po_financially_locked(db, po=O)`.

**Then**
1. returns: `result is True`.

## `PurchaseOrderManager.unlink_invoice_from_po`

### POM-UL-01 — clears the link and logs the old invoice id
- **Rules:** `unlink_invoice_from_po` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `paid True`.

**When**
- `result = M.unlink_invoice_from_po(db, po=O, user_id=U2.id, reason="Invoice voided")`.

**Then**
1. re-read O: `invoice_id is None`, `invoice_confirmed is False`, `paid is False`.
2. re-read O: `supplier_confirmed is True`, `details_confirmed is True`, `items_confirmed is True`, `invoice_ever_linked is True`.
3. re-read O: `current_status_id == SR1.id`.
4. event: `len(EV(O)) == 1`.
5. event: `EV(O)[0].event_type == "invoice_unlinked"`, `description == "Invoice voided"`, `performed_by == U2.id`.
6. event: `EV(O)[0].metadata_json == {"invoice_id": V.id}`.
7. returns: `result is None`.

### POM-UL-02 — custom event type, extra metadata wins on a clash
- **Rules:** `unlink_invoice_from_po` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- `M.unlink_invoice_from_po(db, po=O, user_id=U2.id, reason="Draft removed", event_type="invoice_deleted", extra_metadata={"invoice_id": 7, "note": "dup"})`.

**Then**
1. event: `len(EV(O)) == 1`.
2. event: `EV(O)[0].event_type == "invoice_deleted"`, `description == "Draft removed"`.
3. event: `EV(O)[0].metadata_json == {"invoice_id": 7, "note": "dup"}`.

### POM-UL-03 — empty extra metadata adds nothing
- **Rules:** `unlink_invoice_from_po` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- `M.unlink_invoice_from_po(db, po=O, user_id=U2.id, reason="Draft removed", extra_metadata={})`.

**Then**
1. event: `EV(O)[0].metadata_json == {"invoice_id": V.id}`.

### POM-UL-04 — an order with no invoice still writes and logs
- **Rules:** `unlink_invoice_from_po` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `paid True`.

**When**
- `M.unlink_invoice_from_po(db, po=O, user_id=None, reason="Cleanup")`.

**Then**
1. re-read O: `paid is False`, `invoice_id is None`.
2. event: `len(EV(O)) == 1`.
3. event: `EV(O)[0].metadata_json == {"invoice_id": None}`, `performed_by is None`.

### POM-UL-05 — unlink never commits
- **Rules:** `unlink_invoice_from_po` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1", but `invoice_id V.id`.

**When**
- commit spy around `M.unlink_invoice_from_po(db, po=O, user_id=U2.id, reason="x")`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.unconfirm_sections_after_invoice_void`

### POM-UV-01 — supplier and items go back, details and invoice stay, stage re-derived
- **Rules:** `unconfirm_sections_after_invoice_void` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`, `invoice_confirmed True`, stage SR1.
2. A = appr(O, U2), but approved.

**When**
- `result = M.unconfirm_sections_after_invoice_void(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read O: `supplier_confirmed is False`, `items_confirmed is False`.
2. re-read O: `details_confirmed is True`, `invoice_confirmed is True`.
3. re-read O: `current_status_id == SP1.id`.
4. re-read A: `approved is True`, `approved_at == T2`.
5. event: `types(O) == ["supplier_unconfirmed", "items_unconfirmed", "status_updated"]`.
6. event: `EV(O)[0].description == "Supplier unconfirmed"`, `performed_by == U2.id`.
7. event: `EV(O)[1].description == "Order items unconfirmed"`, `performed_by == U2.id`.
8. returns: `result is None`.

### POM-UV-02 — only items set: one unconfirm event
- **Rules:** `unconfirm_sections_after_invoice_void` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.

**When**
- `M.unconfirm_sections_after_invoice_void(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read O: `items_confirmed is False`, `current_status_id == SD1.id`.
2. event: `types(O) == ["items_unconfirmed", "status_updated"]`.

### POM-UV-03 — neither set: nothing written, no stage sync
- **Rules:** `unconfirm_sections_after_invoice_void` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `details_confirmed True`, stage SR1 (stage out of step on purpose).

**When**
- `M.unconfirm_sections_after_invoice_void(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. session clean.
2. re-read O: `current_status_id == SR1.id`.
3. event: `EV(O) == []`.

### POM-UV-04 — never commits
- **Rules:** `unconfirm_sections_after_invoice_void` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.

**When**
- commit spy around `M.unconfirm_sections_after_invoice_void(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.reset_approvals`

### POM-RA-01 — approved rows reset, others untouched, one event with the count
- **Rules:** `reset_approvals` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. P1 = appr(O, U1), but approved. P2 = appr(O, U2), but approved. P4 = appr(O, U4), but `assigned_at T3`.

**When**
- `result = M.reset_approvals(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read P1: `approved is False`, `approved_at is None`.
2. re-read P2: `approved is False`, `approved_at is None`.
3. unchanged: unchanged(P4).
4. count: O has 3 `purchase_order_approvers` rows.
5. event: `len(EV(O)) == 1`.
6. event: `EV(O)[0].event_type == "approvals_reset"`, `description == "Cleared approvals after invoice voided (2 approval(s) cleared)"`, `performed_by == U2.id`.
7. returns: `result is None`.

### POM-RA-02 — a given reason is used
- **Rules:** `reset_approvals` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".
2. P = appr(O, U2), but approved.

**When**
- `M.reset_approvals(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, reason="Section unconfirmed")`.

**Then**
1. event: `EV(O)[0].description == "Section unconfirmed (1 approval(s) cleared)"`.

### POM-RA-03 — nothing approved: nothing written, no event
- **Rules:** `reset_approvals` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. P = appr(O, U2).

**When**
- `M.reset_approvals(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. session clean.
2. event: `EV(O) == []`.
3. unchanged: unchanged(P).

### POM-RA-04 — approved rows of W0 and W2 on the order are not reset
- **Rules:** `reset_approvals` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. X0 = appr(O, U3), but approved, `workspace_id W0.id` (invalid data). X9 = appr(O, U5), but approved, `workspace_id W2.id` (invalid data).

**When**
- `M.reset_approvals(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. unchanged: unchanged(X0).
2. unchanged: unchanged(X9).
3. event: `EV(O) == []`.

### POM-RA-05 — an id of no order resets nothing and does not raise
- **Rules:** `reset_approvals` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.reset_approvals(db, po_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. session clean.
2. nothing written.

### POM-RA-06 — never commits
- **Rules:** `reset_approvals` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. P = appr(O, U2), but approved.

**When**
- commit spy around `M.reset_approvals(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager._ensure_po_stage_statuses`

### POM-ES-01 — a workspace with no statuses gets the four stages
- **Rules:** `_ensure_po_stage_statuses` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. WX with no statuses.

**When**
- `result = M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. re-read: the names of WX's `statuses` rows, sorted, `== ["Complete", "Draft", "Planning", "Receiving"]`.
2. returns: `result is None`.

### POM-ES-02 — Draft missing, Planning present: only the missing three are added
- **Rules:** `_ensure_po_stage_statuses` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WX; P = stX("Planning").

**When**
- `M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. count: WX has exactly 1 status named `"Planning"`.
2. count: WX has exactly 4 `statuses` rows.

### POM-ES-03 — Draft present, others missing: nothing is done
- **Rules:** `_ensure_po_stage_statuses` R1 (Q4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WX; D = stX("Draft").

**When**
- `M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. session clean.
2. count: WX has exactly 1 `statuses` row.

### POM-ES-04 — "draft" in other capitals counts as Draft
- **Rules:** `_ensure_po_stage_statuses` R1 [BUG-1881]
- **Kind:** bug
- **Expect:** xfail BUG-1881
- **Fails today on:** Then 1 (today four exact-spelled rows are inserted)

**Given**
1. WX; D = stX("draft").

**When**
- `M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. count: WX has exactly 1 `statuses` row.

### POM-ES-05 — " Draft " with outer spaces counts as Draft
- **Rules:** `_ensure_po_stage_statuses` R1 [BUG-1881]
- **Kind:** bug
- **Expect:** xfail BUG-1881
- **Fails today on:** Then 1 (today four rows are inserted)

**Given**
1. WX; D = stX(" Draft ").

**When**
- `M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. count: WX has exactly 1 `statuses` row.

### POM-ES-06 — never commits
- **Rules:** `_ensure_po_stage_statuses` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. WX with no statuses.

**When**
- commit spy around `M._ensure_po_stage_statuses(db, workspace_id=WX.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager._raise_po_workflow_setup_error`

### POM-WE-01 — another workspace has a purchase workflow: migration hint
- **Rules:** `_raise_po_workflow_setup_error` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. WX with no statuses and no workflow (W0, W1, W2 each have one).

**When**
- `M._raise_po_workflow_setup_error(db, workspace_id=WX.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order workflow requires database migration 022_po_stage_workflow. Run: alembic upgrade head"`.

### POM-WE-02 — no purchase workflow anywhere else: not configured
- **Rules:** `_raise_po_workflow_setup_error` R1
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. WX with no workflow.
2. `db.execute(text("UPDATE order_workflows SET type = 'purchase-hidden' WHERE type = 'purchase'"))` (rolled back with the test).

**When**
- `M._raise_po_workflow_setup_error(db, workspace_id=WX.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order workflow is not configured for this workspace"`.

## `PurchaseOrderManager._resolve_po_stage_status_id`

### POM-RS-01 — returns the workspace's own stage row
- **Rules:** `_resolve_po_stage_status_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (SR0 of W0 was built before SR1, SR9 after).

**When**
- `result = M._resolve_po_stage_status_id(db, workspace_id=W1.id, stage_name="Receiving")`.

**Then**
1. returns: `result == SR1.id`.

### POM-RS-02 — a workspace with no statuses is backfilled first
- **Rules:** `_resolve_po_stage_status_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. WX with no statuses.

**When**
- `result = M._resolve_po_stage_status_id(db, workspace_id=WX.id, stage_name="Planning")`.

**Then**
1. returns: `result` equals the id of WX's status named `"Planning"`, re-read.
2. count: WX has exactly 4 `statuses` rows.

### POM-RS-03 — Draft present but the stage missing: 422
- **Rules:** `_resolve_po_stage_status_id` R2 (Q4)
- **Kind:** error
- **Expect:** pass

**Given**
1. WX; stX("Draft"), stX("Receiving"), stX("Complete").

**When**
- `M._resolve_po_stage_status_id(db, workspace_id=WX.id, stage_name="Planning")`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order stage status 'Planning' not found for this workspace"`.
3. count: WX has exactly 3 `statuses` rows.

### POM-RS-04 — a differently spelled stage row is found and reused
- **Rules:** `_resolve_po_stage_status_id` R1 [BUG-1881]
- **Kind:** bug
- **Expect:** xfail BUG-1881
- **Fails today on:** Then 1 (today exact-spelled rows are inserted and the new "Planning" id is returned)

**Given**
1. WX; DX = stX("draft"); PX = stX("planning "); stX("Receiving"); stX("Complete").

**When**
- `result = M._resolve_po_stage_status_id(db, workspace_id=WX.id, stage_name="Planning")`.

**Then**
1. returns: `result == PX.id`.
2. count: WX has exactly 4 `statuses` rows.

## `PurchaseOrderManager._resolve_po_workflow_id`

### POM-WF-01 — an existing purchase workflow gets the four stages as its sequence
- **Rules:** `_resolve_po_workflow_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `WF1.status_sequence = [SD1.id]`, flushed.

**When**
- `result = M._resolve_po_workflow_id(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == WF1.id`.
2. re-read WF1: `status_sequence == [SD1.id, SP1.id, SR1.id, SC1.id]`.
3. count: W1 has exactly 1 `order_workflows` row with `type "purchase"`.

### POM-WF-02 — an empty workspace gets the stages and a "Purchase Order" workflow
- **Rules:** `_resolve_po_workflow_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. WX with no statuses and no workflow.

**When**
- `result = M._resolve_po_workflow_id(db, workspace_id=WX.id)`.

**Then**
1. re-read: the `order_workflows` row of WX with `type "purchase"` has `id == result`, `name == "Purchase Order"`.
2. re-read: its `status_sequence` == the ids of WX's statuses named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`, in that order.

### POM-WF-03 — other workspaces' workflows are not touched
- **Rules:** `_resolve_po_workflow_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `WF0.status_sequence = [SD0.id]`; `WF9.status_sequence = [SD9.id]`; flushed.

**When**
- `result = M._resolve_po_workflow_id(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == WF1.id`.
2. re-read WF0: `status_sequence == [SD0.id]`.
3. re-read WF9: `status_sequence == [SD9.id]`.

### POM-WF-04 — never commits
- **Rules:** `_resolve_po_workflow_id` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. WX with no statuses and no workflow.

**When**
- commit spy around `M._resolve_po_workflow_id(db, workspace_id=WX.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-WF-05 — the seed returns no workflow: 422 with the migration hint
- **Rules:** `_resolve_po_workflow_id` R2, `_raise_po_workflow_setup_error` R1 (spec Overview, G5)
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only (W0 and W2 each have a `purchase` workflow).

**When**
- with `patch("app.managers.purchase_order_manager.ensure_po_workflow_record", return_value=None)`: `M._resolve_po_workflow_id(db, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order workflow requires database migration 022_po_stage_workflow. Run: alembic upgrade head"`.

### POM-WF-06 — the seed returns no workflow and no workspace has one: not configured
- **Rules:** `_resolve_po_workflow_id` R2, `_raise_po_workflow_setup_error` R1 (spec Overview, G5)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `db.execute(text("UPDATE order_workflows SET type = 'purchase-hidden' WHERE type = 'purchase'"))` (rolled back with the test).

**When**
- with `patch("app.managers.purchase_order_manager.ensure_po_workflow_record", return_value=None)`: `M._resolve_po_workflow_id(db, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order workflow is not configured for this workspace"`.

## `PurchaseOrderManager._all_items_fully_received`

### POM-FR-01 — no lines is not done
- **Rules:** `_all_items_fully_received` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._all_items_fully_received([])`.

**Then**
1. returns: `result is False`.

### POM-FR-02 — received plus refunded reaching ordered is done
- **Rules:** `_all_items_fully_received` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("10.00"), quantity_refunded=Decimal("0.00")).
2. B = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("7.00"), quantity_refunded=Decimal("3.00")).

**When**
- `result = M._all_items_fully_received([A, B])`.

**Then**
1. returns: `result is True`.

### POM-FR-03 — one line a cent short is not done
- **Rules:** `_all_items_fully_received` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("10.00"), quantity_refunded=Decimal("0.00")).
2. B = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("6.99"), quantity_refunded=Decimal("3.00")).

**When**
- `result = M._all_items_fully_received([A, B])`.

**Then**
1. returns: `result is False`.

### POM-FR-04 — over-receipt counts as done
- **Rules:** `_all_items_fully_received` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("12.00"), quantity_refunded=Decimal("0.00")).

**When**
- `result = M._all_items_fully_received([A])`.

**Then**
1. returns: `result is True`.

### POM-FR-05 — None received counts as 0
- **Rules:** `_all_items_fully_received` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(quantity_ordered=Decimal("10.00"), quantity_received=None, quantity_refunded=Decimal("10.00")).
2. B = mem(quantity_ordered=Decimal("10.00"), quantity_received=None, quantity_refunded=Decimal("9.00")).

**When**
- `result = M._all_items_fully_received([A, B])`.

**Then**
1. returns: `result is False`.

### POM-FR-06 — None refunded counts as 0
- **Rules:** `_all_items_fully_received` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(quantity_ordered=Decimal("10.00"), quantity_received=Decimal("10.00"), quantity_refunded=None).

**When**
- `result = M._all_items_fully_received([A])`.

**Then**
1. returns: `result is True`.

## `PurchaseOrderManager._current_stage_name`

### POM-CS-01 — the workspace's status name
- **Rules:** `_current_stage_name` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=SR1.id)`.

**Then**
1. returns: `result == "Receiving"`.

### POM-CS-02 — a status of W2 gives None
- **Rules:** `_current_stage_name` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=SR9.id)`.

**Then**
1. returns: `result is None`.

### POM-CS-03 — a status of W0 gives None
- **Rules:** `_current_stage_name` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=SC0.id)`.

**Then**
1. returns: `result is None`.

### POM-CS-04 — a missing id gives None
- **Rules:** `_current_stage_name` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=MISSING)`.

**Then**
1. returns: `result is None`.

### POM-CS-05 — None gives None
- **Rules:** `_current_stage_name` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=None)`.

**Then**
1. returns: `result is None`.

### POM-CS-06 — the stored name comes back exactly as stored
- **Rules:** `_current_stage_name` R1 (G6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SL = `Status(workspace_id=W1.id, name=" complete ", comment="po stage")`.

**When**
- `result = M._current_stage_name(db, workspace_id=W1.id, status_id=SL.id)`.

**Then**
1. returns: `result == " complete "`.

## `PurchaseOrderManager._invoice_payment_status`

### POM-IP-01 — the linked invoice's payment status
- **Rules:** `_invoice_payment_status` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "partial").
2. O = po "1", but locked by V.

**When**
- `result = M._invoice_payment_status(db, po=O)`.

**Then**
1. returns: `result == "partial"`.

### POM-IP-02 — no invoice gives None
- **Rules:** `_invoice_payment_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M._invoice_payment_status(db, po=O)`.

**Then**
1. returns: `result is None`.

### POM-IP-03 — an invoice of W2 gives None
- **Rules:** `_invoice_payment_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V9 = inv("confirmed", "paid") of W9.
2. O = po "1", but `invoice_id V9.id` (invalid data).

**When**
- `result = M._invoice_payment_status(db, po=O)`.

**Then**
1. returns: `result is None`.

## `PurchaseOrderManager.sync_po_for_linked_invoice`

### POM-SL-01 — the order of a paid invoice is marked paid
- **Rules:** `sync_po_for_linked_invoice` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.

**When**
- `result = M.sync_po_for_linked_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read O: `paid is True`.
2. event: `types(O) == ["payment_status_synced"]`.
3. returns: `result is None`.

### POM-SL-02 — no order for the invoice: nothing written
- **Rules:** `sync_po_for_linked_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").

**When**
- `M.sync_po_for_linked_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. session clean.
2. nothing written.

### POM-SL-03 — a W2 order linked to the invoice is not touched
- **Rules:** `sync_po_for_linked_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O9 = po of W9 "9", but `invoice_id V.id` (invalid data).

**When**
- `M.sync_po_for_linked_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. session clean.
2. unchanged: unchanged(O9).
3. event: `EV(O9) == []`.

### POM-SL-04 — never commits
- **Rules:** `sync_po_for_linked_invoice` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.

**When**
- commit spy around `M.sync_po_for_linked_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.sync_po_paid`

### POM-SP-01 — paid invoice: marked paid, event, True
- **Rules:** `sync_po_paid` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `paid is True`.
3. event: `len(EV(O)) == 1`.
4. event: `EV(O)[0].event_type == "payment_status_synced"`, `description == "Order marked paid from linked invoice"`, `performed_by == U2.id`.
5. event: `EV(O)[0].metadata_json == {"paid": True}`.

### POM-SP-02 — partial invoice on a paid order: marked unpaid
- **Rules:** `sync_po_paid` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "partial").
2. O = po "1", but locked by V, `paid True`.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `paid is False`.
3. event: `EV(O)[0].description == "Order marked unpaid from linked invoice"`.
4. event: `EV(O)[0].metadata_json == {"paid": False}`.

### POM-SP-03 — overdue invoice: unpaid
- **Rules:** `sync_po_paid` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "overdue").
2. O = po "1", but locked by V, `paid True`.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `paid is False`.

### POM-SP-04 — unpaid invoice: unpaid
- **Rules:** `sync_po_paid` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `paid True`.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `paid is False`.

### POM-SP-05 — no invoice and already unpaid: False, nothing written
- **Rules:** `sync_po_paid` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. session clean.
3. event: `EV(O) == []`.

### POM-SP-06 — a paid invoice of W2 does not make the order paid
- **Rules:** `sync_po_paid` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V9 = inv("confirmed", "paid") of W9.
2. O = po "1", but `invoice_id V9.id` (invalid data).

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. session clean.
3. re-read O: `paid is False`.

### POM-SP-07 — already paid: False, no event
- **Rules:** `sync_po_paid` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V, `paid True`.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. session clean.
3. event: `EV(O) == []`.

### POM-SP-08 — no user: the event has no performer
- **Rules:** `sync_po_paid` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.

**When**
- `result = M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result is True`.
2. event: `EV(O)[0].performed_by is None`.

### POM-SP-09 — never commits
- **Rules:** `sync_po_paid` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.

**When**
- commit spy around `M.sync_po_paid(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager._is_po_complete_stage`

### POM-CP-01 — exactly "Complete"
- **Rules:** `_is_po_complete_stage` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._is_po_complete_stage("Complete")`.

**Then**
1. returns: `result is True`.

### POM-CP-02 — lower case counts as complete
- **Rules:** `_is_po_complete_stage` R1a [BUG-1881] (OQ-13)
- **Kind:** bug
- **Expect:** xfail BUG-1881
- **Fails today on:** Then 1 (today `False`: only exactly `Complete` counts)

**Given**
1. Standing rows only.

**When**
- `result = M._is_po_complete_stage("complete")`.

**Then**
1. returns: `result is True`.

### POM-CP-03 — None is not complete
- **Rules:** `_is_po_complete_stage` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._is_po_complete_stage(None)`.

**Then**
1. returns: `result is False`.

### POM-CP-04 — Receiving is not complete
- **Rules:** `_is_po_complete_stage` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._is_po_complete_stage("Receiving")`.

**Then**
1. returns: `result is False`.

### POM-CP-05 — capitals and outer spaces are ignored
- **Rules:** `_is_po_complete_stage` R1a [BUG-1881] (OQ-13)
- **Kind:** bug
- **Expect:** xfail BUG-1881
- **Fails today on:** Then 1 (today `[False, False]`)

**Given**
1. Standing rows only.

**When**
- `result = [M._is_po_complete_stage(s) for s in [" COMPLETE ", "Complete "]]`.

**Then**
1. returns: `result == [True, True]`.

### POM-CP-06 — "Completed" and the empty text are not complete
- **Rules:** `_is_po_complete_stage` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._is_po_complete_stage(s) for s in ["Completed", ""]]`.

**Then**
1. returns: `result == [False, False]`.

## `PurchaseOrderManager._derive_po_stage_name`

### POM-DS-01 — a line received 0.01 makes Receiving, even with nothing confirmed
- **Rules:** `_derive_po_stage_name` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("0.01")`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[L])`.

**Then**
1. returns: `result == "Receiving"`.

### POM-DS-02 — a negative received does not count
- **Rules:** `_derive_po_stage_name` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("-1.00")`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[L])`.

**Then**
1. returns: `result == "Draft"`.

### POM-DS-03 — financially locked with nothing received is Receiving
- **Rules:** `_derive_po_stage_name` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but `invoice_id V.id`.
3. L = line 1 of O, I1.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[L])`.

**Then**
1. returns: `result == "Receiving"`.

### POM-DS-04 — supplier confirmed only is Planning
- **Rules:** `_derive_po_stage_name` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[])`.

**Then**
1. returns: `result == "Planning"`.

### POM-DS-05 — details confirmed only is Planning
- **Rules:** `_derive_po_stage_name` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `details_confirmed True`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[])`.

**Then**
1. returns: `result == "Planning"`.

### POM-DS-06 — items confirmed only is Planning
- **Rules:** `_derive_po_stage_name` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[])`.

**Then**
1. returns: `result == "Planning"`.

### POM-DS-07 — invoice_confirmed alone is still Draft
- **Rules:** `_derive_po_stage_name` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `invoice_confirmed True`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[])`.

**Then**
1. returns: `result == "Draft"`.

### POM-DS-08 — everything done is still Receiving, never Complete
- **Rules:** `_derive_po_stage_name` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.

**When**
- `result = M._derive_po_stage_name(db, po=O, items=[L])`.

**Then**
1. returns: `result == "Receiving"`.

## `PurchaseOrderManager.sync_po_stage`

### POM-SS-01 — Draft with the supplier confirmed moves to Planning and logs it
- **Rules:** `sync_po_stage` R1, R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `current_status_id == SP1.id`.
3. event: `len(EV(O)) == 1`.
4. event: `EV(O)[0].event_type == "status_updated"`, `description == "Stage updated to Planning"`, `performed_by == U2.id`.
5. event: `EV(O)[0].metadata_json == {"changes": [{"field": "current_status_id", "label": "Status", "from_value": "Draft", "to_value": "Planning"}]}`.

### POM-SS-02 — stage and workflow already right: False, nothing written
- **Rules:** `sync_po_stage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but confirmed.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. re-read O: `current_status_id == SP1.id`, `order_workflow_id == WF1.id`.
3. event: `EV(O) == []`.

### POM-SS-03 — Complete stays Complete after a return lowered the received quantity
- **Rules:** `sync_po_stage` R1 (BUG-2810, RP1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("4.00")`, `quantity_returned Decimal("6.00")`.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. re-read O: `current_status_id == SC1.id`.
3. event: `EV(O) == []`.

### POM-SS-04 — a different workflow is replaced by the purchase workflow, no stage event
- **Rules:** `sync_po_stage` R2, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. WFL = `OrderWorkflow(workspace_id=W1.id, name="Old flow", type="legacy", status_sequence=[SD1.id])`.
2. O = po "1", but `order_workflow_id WFL.id`.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `order_workflow_id == WF1.id`, `current_status_id == SD1.id`.
3. event: `EV(O) == []`.

### POM-SS-05 — no user: the stage event has no performer
- **Rules:** `sync_po_stage` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result is True`.
2. event: `EV(O)[0].event_type == "status_updated"`, `performed_by is None`.

### POM-SS-06 — the target stage row is missing: 422, stage not set
- **Rules:** `sync_po_stage` R4, R4a (G12), `_resolve_po_stage_status_id` R2 (Q4)
- **Kind:** error
- **Expect:** pass

**Given**
1. WX; SDX = stX("Draft"); stX("Receiving"); stX("Complete").
2. WFX = `OrderWorkflow(workspace_id=WX.id, name="Purchase Order", type="purchase", status_sequence=[SDX.id])`.
3. OX = `PurchaseOrder(workspace_id=WX.id, po_number=f"PO-{TAG}-X", account_id=None, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SDX.id, order_workflow_id=WFX.id, created_by=U1.id, supplier_confirmed=True)`.

**When**
- `M.sync_po_stage(db, po=OX, workspace_id=WX.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 422`.
2. raises: `detail == "Purchase order stage status 'Planning' not found for this workspace"`.
3. re-read OX: `current_status_id == SDX.id`.
4. event: `EV(OX) == []`.
5. re-read WFX: `status_sequence == [SDX.id]` (the workflow step did not run).
6. count: WX has 0 `statuses` rows named `"Planning"`.

### POM-SS-07 — the old stage is a status of W2: shown as "Status #<id>"
- **Rules:** `sync_po_stage` R3, `_format_field_value` R5 [BUG-2875]
- **Kind:** bug
- **Expect:** xfail BUG-2875
- **Fails today on:** Then 4 (today `from_value` is W2's status name "Receiving")

**Given**
1. O = po "1", but stage SR9 (invalid data), `supplier_confirmed True`.

**When**
- `result = M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read O: `current_status_id == SP1.id`.
3. event: `len(EV(O)) == 1`.
4. event: `EV(O)[0].metadata_json["changes"][0]["from_value"] == f"Status #{SR9.id}"`.

### POM-SS-08 — never commits
- **Rules:** `sync_po_stage` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but `supplier_confirmed True`.

**When**
- commit spy around `M.sync_po_stage(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-SS-09 — Planning missing, target Draft: the workflow step then creates Planning
- **Rules:** `sync_po_stage` R2, R4, R4a (G12)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WX; SDX = stX("Draft"); stX("Receiving"); stX("Complete").
2. WFL = `OrderWorkflow(workspace_id=WX.id, name="Old flow", type="legacy", status_sequence=[SDX.id])`.
3. OX = `PurchaseOrder(workspace_id=WX.id, po_number=f"PO-{TAG}-X", account_id=None, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SDX.id, order_workflow_id=WFL.id, created_by=U1.id)` (no confirms).

**When**
- `result = M.sync_po_stage(db, po=OX, workspace_id=WX.id, user_id=U2.id)`.

**Then**
1. returns: `result is True`.
2. re-read OX: `current_status_id == SDX.id`, `order_workflow_id != WFL.id`.
3. re-read: the names of WX's `statuses` rows, sorted, `== ["Complete", "Draft", "Planning", "Receiving"]`.
4. re-read: the `order_workflows` row of WX with `type "purchase"` has `id == OX.order_workflow_id` and `status_sequence` == the ids of WX's statuses named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`, in that order.
5. event: `EV(OX) == []`.

## `PurchaseOrderManager.mark_order_complete`

### POM-MC-01 — every line done: Complete, delivered today, paid synced, one event
- **Rules:** `mark_order_complete` R5, `sync_po_paid` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but locked by V.
3. L1 = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. L2 = line 2 of O, I2, but `quantity_received Decimal("7.00")`, `quantity_refunded Decimal("3.00")`.

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SC1.id`, `updated_by == U2.id`, `actual_delivery_date == TODAY`.
3. re-read O: `paid is True`.
4. event: `types(O) == ["payment_status_synced", "order_completed"]`.
5. event: `EV(O)[1].description == "Order marked complete"`, `performed_by == U2.id`.

### POM-MC-02 — an existing delivery date is kept
- **Rules:** `mark_order_complete` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `actual_delivery_date D3`.
3. L1 = line 1 of O, I1, but `quantity_received Decimal("10.00")`.

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `actual_delivery_date == D3`, `current_status_id == SC1.id`.

### POM-MC-03 — unpaid invoice and an unapproved approver do not block
- **Rules:** `mark_order_complete` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `required_approvals 2`.
3. L1 = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. P = appr(O, U2).

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SC1.id`, `paid is False`.
3. event: `types(O) == ["order_completed"]`.

### POM-MC-04 — a missing order: 404
- **Rules:** `mark_order_complete` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.mark_order_complete(db, po_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.
3. session clean.
4. nothing written.

### POM-MC-05 — an order of W0: 404
- **Rules:** `mark_order_complete` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po of W0 "0".
2. L = line 1 of O0, I0, but `quantity_received Decimal("10.00")`.

**When**
- `M.mark_order_complete(db, po_id=O0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O0.id} not found"`.
3. unchanged: unchanged(O0).

### POM-MC-06 — an order of W2: 404
- **Rules:** `mark_order_complete` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. L = line 1 of O9, I9, but `quantity_received Decimal("10.00")`.

**When**
- `M.mark_order_complete(db, po_id=O9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.
3. unchanged: unchanged(O9).

### POM-MC-07 — a voided order is refused
- **Rules:** `mark_order_complete` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised; the order is completed)

**Given**
1. O = po "1", but voided, stage SR1.
2. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.

**When**
- `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-MC-08 — already Complete: returned unchanged, no paid sync
- **Rules:** `mark_order_complete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V (`paid` stays False).
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. session clean.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-MC-09 — a line short: 400, nothing written
- **Rules:** `mark_order_complete` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L1 = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. L2 = line 2 of O, I2, but `quantity_received Decimal("9.99")`.

**When**
- `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "All line items must be fully received before marking the order complete"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-MC-10 — an order with no lines: 400
- **Rules:** `mark_order_complete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "All line items must be fully received before marking the order complete"`.
3. unchanged: unchanged(O).

### POM-MC-11 — an open return: 400
- **Rules:** `mark_order_complete` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. R = ret(O, "1").

**When**
- `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete all open returns before marking the order complete"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-MC-12 — short line and open return: the line check answers first
- **Rules:** `mark_order_complete` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("5.00")`.
4. R = ret(O, "1").

**When**
- `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "All line items must be fully received before marking the order complete"`.

### POM-MC-13 — completed and cancelled returns do not block
- **Rules:** `mark_order_complete` R4, RP2 (PO)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. RC = ret(O, "1"), but completed. RV = ret(O, "2"), but cancelled.

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SC1.id`.

### POM-MC-14 — pending returns filed under W0 and W2 do not block
- **Rules:** `mark_order_complete` R4, RP2 (PO)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. R0 = ret(O, "0"), but `workspace_id W0.id` (invalid data). R9 = ret(O, "9"), but `workspace_id W2.id` (invalid data).

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SC1.id`.

### POM-MC-15 — the order row is read FOR UPDATE before the checks
- **Rules:** `mark_order_complete` R6 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: locks O first.

### POM-MC-16 — never commits
- **Rules:** `mark_order_complete` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.

**When**
- commit spy around `M.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.reopen_for_return`

### POM-RO-01 — an order not Complete: False, nothing written
- **Rules:** `reopen_for_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `result = M.reopen_for_return(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. session clean.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-RO-02 — a completed order stays completed
- **Rules:** `reopen_for_return` R2 [BUG-2789], RP1 (PO)
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 1 (today it returns True and moves the order to Receiving)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. R = ret(O, "1").

**When**
- `result = M.reopen_for_return(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. re-read O: `current_status_id == SC1.id`, `actual_delivery_date == D2`, `updated_by is None`.
3. event: `EV(O) == []`.

### POM-RO-03 — on a completed order the invoice, lines and return are untouched
- **Rules:** `reopen_for_return` R2, RP1 (PO)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("10.00")`.
4. R = ret(O, "1").

**When**
- `result = M.reopen_for_return(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, bool)`.
2. unchanged: unchanged(V).
3. unchanged: unchanged(L).
4. unchanged: unchanged(R).
5. re-read O: `invoice_id == V.id`, `paid is False`, `supplier_confirmed is True`, `items_confirmed is True`.

### POM-RO-04 — never commits
- **Rules:** `reopen_for_return` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.

**When**
- commit spy around `M.reopen_for_return(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.create_purchase_order`

### POM-CR-01 — a new order with two lines
- **Rules:** `create_purchase_order` R1, R2, R5, R6, R7, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=D1, expected_delivery_date=D2, description="Steel for line 2", items=[IC(item_id=I1.id, quantity_ordered=Decimal("10"), unit_price=Decimal("2.50")), IC(item_id=I2.id, quantity_ordered=Decimal("4"), unit_price=Decimal("1.25"), notes="Zinc")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `re.fullmatch(r"PO-\d{4}-\d{3,}", po_number)`, `workspace_id == W1.id`, `created_by == U2.id`.
3. re-read result: `current_status_id == SD1.id`, `order_workflow_id == WF1.id`.
4. re-read result: `account_id == A1.id`, `destination_type == "storage"`, `destination_id == F1.id`, `order_date == D1`, `expected_delivery_date == D2`, `description == "Steel for line 2"`.
5. re-read result: `subtotal == Decimal("30.00")`, `total_amount == Decimal("30.00")`.
6. re-read: `[(l.line_number, l.item_id, l.quantity_ordered, l.quantity_received, l.unit_price, l.line_subtotal) for l in LINES(result)] == [(1, I1.id, Decimal("10.00"), Decimal("0.00"), Decimal("2.50"), Decimal("25.00")), (2, I2.id, Decimal("4.00"), Decimal("0.00"), Decimal("1.25"), Decimal("5.00"))]`.
7. re-read: `LINES(result)[1].notes == "Zinc"`.
8. re-read: the order's approvers are exactly one row, `user_id == U2.id`, `assigned_by == U2.id`, `approved is False`.
9. event: `types(result) == ["created"]`.
10. event: `EV(result)[0].description == "Order created"`.

### POM-CR-02 — no order date sent: today
- **Rules:** `create_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `order_date == TODAY`, `account_id is None`.

### POM-CR-03 — a sent stage and workflow are replaced by Draft and the purchase workflow
- **Rules:** `create_purchase_order` R2 (Q6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WFL = `OrderWorkflow(workspace_id=W1.id, name="Old flow", type="legacy", status_sequence=[SC1.id])`.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, current_status_id=SC1.id, order_workflow_id=WFL.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `current_status_id == SD1.id`, `order_workflow_id == WF1.id`.

### POM-CR-04 — no lines: totals 0, no lines stored
- **Rules:** `create_purchase_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `subtotal == Decimal("0.00")`, `total_amount == Decimal("0.00")`.
3. re-read: `LINES(result) == []`.

### POM-CR-05 — an unpriced line has no subtotal and adds 0
- **Rules:** `create_purchase_order` R5, R7, `_line_subtotal` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I1.id, quantity_ordered=Decimal("3")), IC(item_id=I2.id, quantity_ordered=Decimal("2"), unit_price=Decimal("4.00"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `LINES(result)[0].unit_price is None`, `LINES(result)[0].line_subtotal is None`.
3. re-read result: `total_amount == Decimal("8.00")`.

### POM-CR-06 — three lines of 1.25 × 0.10: total is the sum of rounded lines
- **Rules:** `create_purchase_order` R7 [BUG-2876]
- **Kind:** bug
- **Expect:** xfail BUG-2876
- **Fails today on:** Then 2 (today 0.38)

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I1.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I2.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I3.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `subtotal == Decimal("0.39")`, `total_amount == Decimal("0.39")`.

### POM-CR-07 — three lines of 1.25 × 0.10: each stored line is 0.13
- **Rules:** `create_purchase_order` R5, `_line_subtotal` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I1.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I2.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I3.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[l.line_subtotal for l in LINES(result)] == [Decimal("0.13"), Decimal("0.13"), Decimal("0.13")]`.

### POM-CR-08 — the same item twice: 409 after the order was flushed
- **Rules:** `create_purchase_order` R4 (Q7)
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only (W1 has no orders).

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I1.id, quantity_ordered=Decimal("1")), IC(item_id=I1.id, quantity_ordered=Decimal("2"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Bolt appears more than once on this order"`.
3. count: W1 has exactly 1 `purchase_orders` row (flushed before the refusal; the caller rolls back).
4. count: that order has exactly 1 `purchase_order_approvers` row.
5. count: that order has exactly 1 `purchase_order_events` row, `event_type "created"`.

### POM-CR-09 — a supplier of W2 is refused
- **Rules:** `create_purchase_order` R3 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised; A9 is stored)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(account_id=A9.id, destination_type="storage", destination_id=F1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Account with ID {A9.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-10 — a supplier of W0 is refused
- **Rules:** `create_purchase_order` R3 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(account_id=A0.id, destination_type="storage", destination_id=F1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Account with ID {A0.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-11 — a line item of W2 is refused
- **Rules:** `create_purchase_order` R3 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I9.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I9.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-12 — a live factory and a live machine of the workspace are accepted
- **Rules:** `create_purchase_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="machine", destination_id=M1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `destination_type == "machine"`, `destination_id == M1.id`.

### POM-CR-13 — a storage destination of W2 is refused
- **Rules:** `create_purchase_order` R3 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F9.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F9.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-14 — a storage destination of W0 is refused
- **Rules:** `create_purchase_order` R3 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F0.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F0.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-15 — a deleted factory is refused
- **Rules:** `create_purchase_order` R3 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Old Plant", abbreviation="OP")`, but deleted factory.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=FD.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {FD.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-16 — a machine of W2 is refused
- **Rules:** `create_purchase_order` R3 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised; verified for a foreign machine)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="machine", destination_id=M9.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {M9.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-17 — a deleted machine is refused
- **Rules:** `create_purchase_order` R3 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old Press")`, but deleted machine.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="machine", destination_id=MD.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {MD.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

### POM-CR-18 — a project component destination is stored as sent (revisit after launch)
- **Rules:** `create_purchase_order` R3 (projects deferred)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="project", destination_id=C1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `destination_type == "project"`, `destination_id == C1.id`.

### POM-CR-19 — never commits
- **Rules:** `create_purchase_order` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. Standing rows only.

**When**
- commit spy around `M.create_purchase_order(db, data=PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-CR-20 — a foreign supplier and a foreign line item: the supplier answers first
- **Rules:** `create_purchase_order` R3, R4 [BUG-1017] (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised; the order is stored)

**Given**
1. Standing rows only.

**When**
- `M.create_purchase_order(db, data=PurchaseOrderCreate(account_id=A9.id, destination_type="storage", destination_id=F1.id, order_date=D1, items=[IC(item_id=I9.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Account with ID {A9.id} not found"`.
3. count: W1 has 0 `purchase_orders` rows.

## Schemas (`app.schemas.purchase_order`, target `schema`)

### POM-SCH-01 — a line quantity of 0 is refused
- **Rules:** `create_purchase_order` R5, `add_item` R4 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("0"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-02 — a negative line quantity is refused
- **Rules:** `create_purchase_order` R5, `add_item` R4 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("-3"), unit_price=Decimal("2.00"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-03 — a negative price is refused
- **Rules:** `create_purchase_order` R5, `add_item` R4 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("-0.01"))`.

**Then**
1. raises: `ValidationError`, loc `== ("unit_price",)`.

### POM-SCH-04 — quantity 0.01 and price 0 stay allowed
- **Rules:** `create_purchase_order` R5 (P1 edges)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("0.01"), unit_price=Decimal("0"))`.

**Then**
1. returns: `result.quantity_ordered == Decimal("0.01")`, `result.unit_price == Decimal("0")`.

### POM-SCH-05 — an edit to quantity 0 is refused
- **Rules:** `update_item` R7 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(quantity_ordered=Decimal("0"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-06 — an edit to a negative price is refused
- **Rules:** `update_item` R7 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(unit_price=Decimal("-2"))`.

**Then**
1. raises: `ValidationError`, loc `== ("unit_price",)`.

### POM-SCH-07 — a sync update to a negative quantity is refused
- **Rules:** `sync_items` R6 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemSyncUpdate(id=1, quantity_ordered=Decimal("-1"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-08 — a negative approval threshold on create is refused
- **Rules:** `approval_summary` R2 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, required_approvals=-1)`.

**Then**
1. raises: `ValidationError`, loc `== ("required_approvals",)`.

### POM-SCH-09 — a negative approval threshold on update is refused
- **Rules:** `approval_summary` R2 [BUG-2877]
- **Kind:** bug
- **Expect:** xfail BUG-2877
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderUpdate(required_approvals=-1)`.

**Then**
1. raises: `ValidationError`, loc `== ("required_approvals",)`.

### POM-SCH-10 — a threshold of 0 stays allowed on create
- **Rules:** `approval_summary` R2 (BUG-1202 waiver)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = PurchaseOrderCreate(destination_type="storage", destination_id=F1.id, required_approvals=0)`.

**Then**
1. returns: `result.required_approvals == 0`.

### POM-SCH-11 — a threshold of 0 stays allowed on update
- **Rules:** `approval_summary` R2 (BUG-1202 waiver)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = PurchaseOrderUpdate(required_approvals=0)`.

**Then**
1. returns: `result.required_approvals == 0`.

### POM-SCH-12 — a quantity with 3 decimals is refused
- **Rules:** `create_purchase_order` R5, `add_item` R4 [BUG-2878]
- **Kind:** bug
- **Expect:** xfail BUG-2878
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("1.005"), unit_price=Decimal("10"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-13 — a price with 3 decimals is refused
- **Rules:** `create_purchase_order` R5 [BUG-2878]
- **Kind:** bug
- **Expect:** xfail BUG-2878
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("1"), unit_price=Decimal("10.001"))`.

**Then**
1. raises: `ValidationError`, loc `== ("unit_price",)`.

### POM-SCH-14 — a quantity with 14 integer digits is refused
- **Rules:** `create_purchase_order` R5 [BUG-2878]
- **Kind:** bug
- **Expect:** xfail BUG-2878
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("10000000000000"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-15 — 13 integer digits with 2 decimals stay allowed
- **Rules:** `create_purchase_order` R5 (P2 edge)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = PurchaseOrderItemCreate(item_id=I1.id, quantity_ordered=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99"))`.

**Then**
1. returns: `result.quantity_ordered == Decimal("9999999999999.99")`.

### POM-SCH-16 — an edit price with 3 decimals is refused
- **Rules:** `update_item` R7 [BUG-2878]
- **Kind:** bug
- **Expect:** xfail BUG-2878
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(unit_price=Decimal("1.005"))`.

**Then**
1. raises: `ValidationError`, loc `== ("unit_price",)`.

### POM-SCH-17 — a sync update quantity with 3 decimals is refused
- **Rules:** `sync_items` R6 [BUG-2878]
- **Kind:** bug
- **Expect:** xfail BUG-2878
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemSyncUpdate(id=1, quantity_ordered=Decimal("2.345"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-18 — an update sending destination_type null is refused
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderUpdate(destination_type=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_type",)`.

### POM-SCH-19 — an update sending destination_id null is refused
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderUpdate(destination_id=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_id",)`.

### POM-SCH-20 — a line edit sending quantity_ordered null is refused
- **Rules:** `update_item` R1 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(quantity_ordered=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_ordered",)`.

### POM-SCH-21 — a line edit sending quantity_received is refused
- **Rules:** `update_item` R3 [BUG-2887], RP5 (PO)
- **Kind:** bug
- **Expect:** xfail BUG-2887
- **Fails today on:** Then 1 (no error is raised; the field is accepted)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(quantity_received=Decimal("5"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_received",)`.

### POM-SCH-22 — quantity_received 0 (the stored value) is refused too
- **Rules:** `update_item` R3 [BUG-2887]
- **Kind:** bug
- **Expect:** xfail BUG-2887
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(quantity_ordered=Decimal("10"), quantity_received=Decimal("0"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_received",)`.

### POM-SCH-23 — quantity_received null is refused too
- **Rules:** `update_item` R3 [BUG-2887]
- **Kind:** bug
- **Expect:** xfail BUG-2887
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderItemUpdate(quantity_received=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity_received",)`.

### POM-SCH-24 — quantity ordered, price and notes are still accepted
- **Rules:** `update_item` R3 (BUG-2887: what the line edit keeps)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = PurchaseOrderItemUpdate(quantity_ordered=Decimal("12"), unit_price=Decimal("2.50"), notes="Zinc")`.

**Then**
1. returns: `result.quantity_ordered == Decimal("12")`, `result.unit_price == Decimal("2.50")`, `result.notes == "Zinc"`.

## `PurchaseOrderManager.update_purchase_order`

### POM-UP-01 — a missing order: 404
- **Rules:** `update_purchase_order` R1, R10
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.update_purchase_order(db, po_id=MISSING, data=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.
3. session clean.
4. nothing written.

### POM-UP-02 — an order of W0: 404
- **Rules:** `update_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po of W0 "0".

**When**
- `M.update_purchase_order(db, po_id=O0.id, data=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O0.id} not found"`.
3. unchanged: unchanged(O0).

### POM-UP-03 — an order of W2: 404
- **Rules:** `update_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".

**When**
- `M.update_purchase_order(db, po_id=O9.id, data=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.
3. unchanged: unchanged(O9).

### POM-UP-04 — a voided order is refused
- **Rules:** `update_purchase_order` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised; verified)

**Given**
1. O = po "1", but voided, `supplier_confirmed True`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-UP-05 — a completed order refuses a new expected delivery date
- **Rules:** `update_purchase_order` R1b [BUG-2885], RP5 (PO)
- **Kind:** bug
- **Expect:** xfail BUG-2885
- **Fails today on:** Then 1 (no error is raised; the date is saved)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V, `expected_delivery_date D2`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(expected_delivery_date=D3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot edit — purchase order is complete"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-UP-06 — a completed order refuses a new approval threshold
- **Rules:** `update_purchase_order` R1b [BUG-2885]
- **Kind:** bug
- **Expect:** xfail BUG-2885
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(required_approvals=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot edit — purchase order is complete"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-07 — a sent current_status_id is ignored
- **Rules:** `update_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(current_status_id=SC1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SD1.id`.

### POM-UP-08 — locked: unconfirming the supplier is refused
- **Rules:** `update_purchase_order` R3, R10
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot unconfirm supplier after invoice is confirmed"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-UP-09 — locked: unconfirming the details is refused
- **Rules:** `update_purchase_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(details_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot unconfirm order details after invoice is confirmed"`.
3. unchanged: unchanged(O).

### POM-UP-10 — locked: unconfirming the items is refused
- **Rules:** `update_purchase_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot unconfirm order items after invoice is confirmed"`.
3. unchanged: unchanged(O).

### POM-UP-11 — locked: unconfirming the draft invoice is refused
- **Rules:** `update_purchase_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(invoice_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot unconfirm draft invoice after invoice is finalized"`.
3. unchanged: unchanged(O).

### POM-UP-12 — locked: supplier and items both unconfirmed, the supplier answers first
- **Rules:** `update_purchase_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=False, supplier_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot unconfirm supplier after invoice is confirmed"`.

### POM-UP-13 — locked: sending the confirms as true passes and logs nothing
- **Rules:** `update_purchase_order` R3, R7, `_validate_section_confirm` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `supplier_confirmed is True`, `invoice_confirmed is True`, `current_status_id == SR1.id`.
3. event: `EV(O) == []`.

### POM-UP-14 — locked: sending the same supplier is refused
- **Rules:** `update_purchase_order` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. session clean.
4. unchanged: unchanged(O).

### POM-UP-15 — supplier confirmed, not locked: a new supplier is refused
- **Rules:** `update_purchase_order` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A3.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Supplier is confirmed"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-16 — unconfirming the supplier in the same request does not help
- **Rules:** `update_purchase_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A3.id, supplier_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Supplier is confirmed"`.
3. unchanged: unchanged(O).

### POM-UP-17 — locked: a new description is refused
- **Rules:** `update_purchase_order` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `description "Steel"`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. unchanged: unchanged(O).

### POM-UP-18 — details confirmed, not locked: a destination type change is refused
- **Rules:** `update_purchase_order` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `details_confirmed True`, stage SP1.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_type="machine", destination_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order details are confirmed"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-19 — details confirmed: a new order date is refused
- **Rules:** `update_purchase_order` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `details_confirmed True`, stage SP1.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(order_date=D2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order details are confirmed"`.
3. unchanged: unchanged(O).

### POM-UP-20 — locked but not complete: expected delivery and threshold are saved
- **Rules:** `update_purchase_order` R5, R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V, `expected_delivery_date D2`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(expected_delivery_date=D3, required_approvals=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `expected_delivery_date == D3`, `required_approvals == 2`.
3. event: `types(O) == ["details_updated", "approvals_threshold_updated"]`.
4. event: `EV(O)[0].metadata_json["changes"][0]["from_value"] == "2026-03-20"`, `["to_value"] == "2026-04-15"`, `["label"] == "Expected delivery"`.
5. event: `EV(O)[1].description == "Changed approval threshold"`.
6. event: `EV(O)[1].metadata_json["changes"][0]["from_value"] == "All assigned"`, `["to_value"] == "2"`, `["label"] == "Approval threshold"`.

### POM-UP-21 — confirming the supplier: event, then Planning
- **Rules:** `update_purchase_order` R6, R7, R9, `_validate_section_confirm` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `supplier_confirmed is True`, `current_status_id == SP1.id`.
3. event: `types(O) == ["supplier_confirmed", "status_updated"]`.
4. event: `EV(O)[0].description == "Supplier confirmed"`, `performed_by == U2.id`.

### POM-UP-22 — confirming the details logs "Order details confirmed"
- **Rules:** `update_purchase_order` R7, `_validate_section_confirm` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(details_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `details_confirmed is True`.
3. event: `types(O) == ["details_confirmed"]`.
4. event: `EV(O)[0].description == "Order details confirmed"`.

### POM-UP-23 — confirming priced items logs "Order items confirmed"
- **Rules:** `update_purchase_order` R7, `_validate_section_confirm` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.
2. L = line 1 of O, I1.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `items_confirmed is True`.
3. event: `types(O) == ["items_confirmed"]`.
4. event: `EV(O)[0].description == "Order items confirmed"`.

### POM-UP-24 — unconfirming a section resets approvals and the stage
- **Rules:** `update_purchase_order` R7, R9, `reset_approvals` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.
2. P = appr(O, U2), but approved.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `supplier_confirmed is False`, `current_status_id == SD1.id`.
3. re-read P: `approved is False`, `approved_at is None`.
4. event: `types(O) == ["supplier_unconfirmed", "approvals_reset", "status_updated"]`.
5. event: `EV(O)[0].description == "Supplier unconfirmed"`.
6. event: `EV(O)[1].description == "Section unconfirmed (1 approval(s) cleared)"`.

### POM-UP-25 — sending a stored confirm value logs nothing
- **Rules:** `update_purchase_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.
2. P = appr(O, U2), but approved.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=True, details_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `EV(O) == []`.
3. re-read P: `approved is True`, `approved_at == T2`.

### POM-UP-26 — a new supplier logs "Changed supplier" with both names
- **Rules:** `update_purchase_order` R8, `_log_section_field_updates` R1, `_format_field_value` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A3.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `account_id == A3.id`.
3. event: `types(O) == ["supplier_updated"]`.
4. event: `EV(O)[0].description == "Changed supplier"`, `performed_by == U2.id`.
5. event: `[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in EV(O)[0].metadata_json["changes"]] == [("account_id", "Supplier", "Northwind Traders", "Alpha Parts")]`.

### POM-UP-27 — changed details are listed in field order
- **Rules:** `update_purchase_order` R8, `_collect_field_changes` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent", destination_id=M1.id, destination_type="machine", order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `destination_type == "machine"`, `destination_id == M1.id`, `description == "Urgent"`.
3. event: `types(O) == ["details_updated"]`.
4. event: `EV(O)[0].description == "Changed order details"`.
5. event: `[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in EV(O)[0].metadata_json["changes"]] == [("destination_type", "Destination type", "Storage", "Machine"), ("destination_id", "Destination", "Main Plant", "Press 1"), ("description", "Description", "Steel", "Urgent")]`.

### POM-UP-28 — values equal to the stored ones log nothing
- **Rules:** `update_purchase_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`, `required_approvals 2`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A1.id, description="Steel", required_approvals=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `EV(O) == []`.

### POM-UP-29 — an empty body does not stamp updated_by
- **Rules:** `update_purchase_order` R11 [BUG-2873]
- **Kind:** bug
- **Expect:** xfail BUG-2873
- **Fails today on:** Then 2 (today `updated_by == U2.id`; verified)

**Given**
1. O = po "1" (`updated_by` NULL).

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### POM-UP-30 — the same values do not stamp updated_by
- **Rules:** `update_purchase_order` R11 [BUG-2873]
- **Kind:** bug
- **Expect:** xfail BUG-2873
- **Fails today on:** Then 2 (today `updated_by == U2.id`)

**Given**
1. O = po "1", but `description "Steel"`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Steel", order_date=D1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### POM-UP-31 — a real change stamps updated_by
- **Rules:** `update_purchase_order` R9, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "Urgent"`, `updated_by == U2.id`.

### POM-UP-32 — omitted fields stay unchanged
- **Rules:** `update_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`, `expected_delivery_date D2`, `required_approvals 2`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(order_date=D3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `order_date == D3`, `description == "Steel"`, `expected_delivery_date == D2`, `required_approvals == 2`, `account_id == A1.id`.

### POM-UP-33 — an explicit null clears the description
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today the null is dropped; verified)

**Given**
1. O = po "1", but `description "Steel"`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description is None`.

### POM-UP-34 — an explicit null restores "all assigned approvers"
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today the threshold stays 2)

**Given**
1. O = po "1", but `required_approvals 2`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(required_approvals=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals is None`.

### POM-UP-35 — an explicit null clears the supplier while it is not confirmed
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today the supplier stays A1)

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `account_id is None`.

### POM-UP-36 — an explicit null clears the order date and the expected delivery date
- **Rules:** `update_purchase_order` R2 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today both dates stay)

**Given**
1. O = po "1", but `expected_delivery_date D2`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(order_date=None, expected_delivery_date=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `order_date is None`, `expected_delivery_date is None`.

### POM-UP-37 — a new storage destination of W2 is refused
- **Rules:** `update_purchase_order` R12 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1".

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F9.id} not found"`.
3. session clean.
4. unchanged: unchanged(O).

### POM-UP-38 — a new machine destination of W0 is refused
- **Rules:** `update_purchase_order` R12 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1".

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_type="machine", destination_id=M0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {M0.id} not found"`.
3. unchanged: unchanged(O).

### POM-UP-39 — a kept machine type with a deleted machine is refused
- **Rules:** `update_purchase_order` R12 [BUG-2874]
- **Kind:** bug
- **Expect:** xfail BUG-2874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old Press")`, but deleted machine.
2. O = po "1", but `destination_type "machine"`, `destination_id M1.id`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_id=MD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {MD.id} not found"`.
3. unchanged: unchanged(O).

### POM-UP-40 — a new live machine of the workspace is accepted
- **Rules:** `update_purchase_order` R9, R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_type="machine", destination_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `destination_type == "machine"`, `destination_id == M1.id`.

### POM-UP-41 — a supplier of W2 is refused
- **Rules:** `update_purchase_order` R13 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1".

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Account with ID {A9.id} not found"`.
3. unchanged: unchanged(O).

### POM-UP-42 — a sent invoice_id is refused by the schema
- **Rules:** `update_purchase_order` R13, R13a [BUG-1017] (G3)
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error: the schema accepts `invoice_id`)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1".

**When**
- build `PurchaseOrderUpdate(invoice_id=V.id)` (target `schema`; the manager is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `"invoice_id" in exc.value.errors()[0]["loc"]`.
3. unchanged: unchanged(O).

### POM-UP-43 — the order row is read FOR UPDATE before the checks
- **Rules:** `update_purchase_order` R14 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: locks O first.

### POM-UP-44 — never commits
- **Rules:** `update_purchase_order` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-UP-45 — a foreign supplier on a supplier-confirmed order: the section guard answers
- **Rules:** `update_purchase_order` R4, R13 (spec Overview check order, G4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, stage SP1.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Supplier is confirmed"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-46 — a foreign supplier and a foreign destination: the supplier answers first
- **Rules:** `update_purchase_order` R12 [BUG-2874], R13 [BUG-1017] (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised; both are stored)

**Given**
1. O = po "1".

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A9.id, destination_type="storage", destination_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Account with ID {A9.id} not found"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-47 — voided and complete: the voided check answers first
- **Rules:** `update_purchase_order` R1a [BUG-2882], R1b [BUG-2885] (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised; the date is saved)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V, then voided, `expected_delivery_date D2`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(expected_delivery_date=D3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. unchanged: unchanged(O).
4. event: `EV(O) == []`.

### POM-UP-48 — complete and financially locked: the completed check answers before the lock guard
- **Rules:** `update_purchase_order` R1b [BUG-2885], R5 (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-2885
- **Fails today on:** Then 2 (today the lock guard answers: `"Confirmed after invoice creation"`)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V, `description "Steel"`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(description="Urgent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot edit — purchase order is complete"`.
3. unchanged: unchanged(O).

### POM-UP-49 — a sent invoice_id of null is refused by the schema too
- **Rules:** `update_purchase_order` R13a [BUG-1017] (G3)
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error: the schema accepts `invoice_id`)

**Given**
1. Standing rows only.

**When**
- build `PurchaseOrderUpdate(invoice_id=None)` (target `schema`; the manager is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `"invoice_id" in exc.value.errors()[0]["loc"]`.

### POM-UP-50 — a new order date is logged with the label "Order date"
- **Rules:** `update_purchase_order` R8, `_collect_field_changes` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(order_date=D2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `order_date == D2`.
3. event: `types(O) == ["details_updated"]`.
4. event: `EV(O)[0].description == "Changed order details"`, `performed_by == U2.id`.
5. event: `[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in EV(O)[0].metadata_json["changes"]] == [("order_date", "Order date", "2026-03-02", "2026-03-20")]`.

### POM-UP-51 — not locked: unconfirming the draft invoice logs it and resets approvals
- **Rules:** `update_purchase_order` R3 (not locked), R7, `reset_approvals` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but confirmed, `invoice_confirmed True` (no `invoice_id`, so not financially locked).
2. P = appr(O, U2), but approved.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(invoice_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `invoice_confirmed is False`, `supplier_confirmed is True`, `details_confirmed is True`, `items_confirmed is True`, `current_status_id == SP1.id`.
3. re-read P: `approved is False`, `approved_at is None`.
4. event: `types(O) == ["invoice_unconfirmed", "approvals_reset"]` (the stage stays Planning per `_derive_po_stage_name` R3, so no `status_updated`).
5. event: `EV(O)[0].description == "Draft invoice unconfirmed"`, `performed_by == U2.id`.
6. event: `EV(O)[1].description == "Section unconfirmed (1 approval(s) cleared)"`.

## `PurchaseOrderManager._validate_section_confirm` (through `update_purchase_order`)

### POM-VC-01 — confirming the supplier with none set: 400
- **Rules:** `_validate_section_confirm` R1, `update_purchase_order` R6, R10
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `account_id None`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(supplier_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Select a supplier before confirming"`.
3. session clean.
4. unchanged: unchanged(O).
5. event: `EV(O) == []`.

### POM-VC-02 — a supplier sent in the same request satisfies the check
- **Rules:** `_validate_section_confirm` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `account_id None`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(account_id=A1.id, supplier_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `account_id == A1.id`, `supplier_confirmed is True`.

### POM-VC-03 — confirming the details without an order date: 400
- **Rules:** `_validate_section_confirm` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `order_date None`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(details_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete destination, location, and order date before confirming"`.
3. unchanged: unchanged(O).

### POM-VC-04 — confirming the details with an empty destination type: 400
- **Rules:** `_validate_section_confirm` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `destination_type ""`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(details_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete destination, location, and order date before confirming"`.
3. unchanged: unchanged(O).

### POM-VC-05 — an order date sent in the same request satisfies the check
- **Rules:** `_validate_section_confirm` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `order_date None`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(order_date=D2, details_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `order_date == D2`, `details_confirmed is True`.

### POM-VC-06 — confirming items with no lines: 400
- **Rules:** `_validate_section_confirm` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Add at least one line item before confirming"`.
3. unchanged: unchanged(O).

### POM-VC-07 — confirming items with an unpriced line: 400
- **Rules:** `_validate_section_confirm` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2, but `unit_price None`, `line_subtotal None`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Enter unit prices to confirm"`.
3. unchanged: unchanged(O).

### POM-VC-08 — confirming items with a line at 0.00: 400
- **Rules:** `_validate_section_confirm` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `unit_price Decimal("0.00")`, `line_subtotal Decimal("0.00")`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Enter unit prices to confirm"`.

### POM-VC-09 — confirming the draft invoice by hand: 400
- **Rules:** `_validate_section_confirm` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but confirmed.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(invoice_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Draft invoice is confirmed when you finalize the invoice — use Finalize Invoice instead"`.
3. unchanged: unchanged(O).

### POM-VC-10 — supplier and items both invalid: the supplier answers first
- **Rules:** `_validate_section_confirm` R1, R3 (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `account_id None`.

**When**
- `M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True, supplier_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Select a supplier before confirming"`.

### POM-VC-11 — a section already confirmed is not re-validated
- **Rules:** `_validate_section_confirm` (only when stored false)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1 (no lines: legacy data).

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `EV(O) == []`.

### POM-VC-12 — a destination type sent in the same request satisfies the check
- **Rules:** `_validate_section_confirm` R2 ("after the update")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `destination_type ""`.

**When**
- `result = M.update_purchase_order(db, po_id=O.id, data=PurchaseOrderUpdate(destination_type="machine", destination_id=M1.id, details_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `destination_type == "machine"`, `destination_id == M1.id`, `details_confirmed is True`.
3. event: `"details_confirmed" in types(O)`.

### POM-VC-13 — direct call: destination type and id both arrive in the update
- **Rules:** `_validate_section_confirm` R2 ("after the update")
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. R = an in-memory `PurchaseOrder(workspace_id=W1.id, account_id=A1.id, destination_type=None, destination_id=None, order_date=D1, supplier_confirmed=False, details_confirmed=False, items_confirmed=False, invoice_confirmed=False)`, never added to the session. (`destination_type` and `destination_id` are required columns (spec P3), so a stored order cannot have them empty; only the in-memory record reaches the "id arrives in the update" path.)

**When**
- `M._validate_section_confirm(record=R, update_dict={"destination_type": "machine", "destination_id": M1.id, "details_confirmed": True}, session=db, workspace_id=W1.id)`.

**Then**
1. returns: the call returns without raising.
2. session clean.

### POM-VC-14 — direct call: only the type arrives and the id stays empty: 400
- **Rules:** `_validate_section_confirm` R2
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. R = the in-memory order of VC-13 (built the same way in this test).

**When**
- `M._validate_section_confirm(record=R, update_dict={"destination_type": "machine", "details_confirmed": True}, session=db, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete destination, location, and order date before confirming"`.

## `PurchaseOrderManager._format_scalar_value`

### POM-SF-01 — None is a dash
- **Rules:** `_format_scalar_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("notes", None)`.

**Then**
1. returns: `result == "—"`.

### POM-SF-02 — a date is ISO text
- **Rules:** `_format_scalar_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("order_date", date(2026, 3, 4))`.

**Then**
1. returns: `result == "2026-03-04"`.

### POM-SF-03 — a whole Decimal drops its fraction
- **Rules:** `_format_scalar_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("quantity_ordered", Decimal("5.00"))`.

**Then**
1. returns: `result == "5"`.

### POM-SF-04 — a fractional Decimal is normalized
- **Rules:** `_format_scalar_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("unit_price", Decimal("1.50"))`.

**Then**
1. returns: `result == "1.5"`.

### POM-SF-05 — text is trimmed
- **Rules:** `_format_scalar_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("notes", "  Zinc coat ")`.

**Then**
1. returns: `result == "Zinc coat"`.

### POM-SF-06 — blank text is a dash
- **Rules:** `_format_scalar_value` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("notes", "   ")`.

**Then**
1. returns: `result == "—"`.

### POM-SF-07 — an int becomes its text
- **Rules:** `_format_scalar_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_scalar_value("line_number", 7)`.

**Then**
1. returns: `result == "7"`.

## `PurchaseOrderManager._format_destination_id`

### POM-FD-01 — no id is a dash
- **Rules:** `_format_destination_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="storage", destination_id=None)`.

**Then**
1. returns: `result == "—"`.

### POM-FD-02 — storage names the factory, type in any case
- **Rules:** `_format_destination_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="STORAGE", destination_id=F1.id)`.

**Then**
1. returns: `result == "Main Plant"`.

### POM-FD-03 — a factory of W2 falls back to "Factory #<id>"
- **Rules:** `_format_destination_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `F9.name = "East Plant"`, flushed.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="storage", destination_id=F9.id)`.

**Then**
1. returns: `result == f"Factory #{F9.id}"`.

### POM-FD-04 — a factory of W0 falls back too
- **Rules:** `_format_destination_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="storage", destination_id=F0.id)`.

**Then**
1. returns: `result == f"Factory #{F0.id}"`.

### POM-FD-05 — a missing factory id falls back
- **Rules:** `_format_destination_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="storage", destination_id=MISSING)`.

**Then**
1. returns: `result == f"Factory #{MISSING}"`.

### POM-FD-06 — a deleted factory still shows its name
- **Rules:** `_format_destination_id` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Old Plant", abbreviation="OP")`, but deleted factory.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="storage", destination_id=FD.id)`.

**Then**
1. returns: `result == "Old Plant"`.

### POM-FD-07 — machine names the machine
- **Rules:** `_format_destination_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="machine", destination_id=M1.id)`.

**Then**
1. returns: `result == "Press 1"`.

### POM-FD-08 — a machine of W2 falls back to "Machine #<id>"
- **Rules:** `_format_destination_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="machine", destination_id=M9.id)`.

**Then**
1. returns: `result == f"Machine #{M9.id}"`.

### POM-FD-09 — a deleted machine still shows its name
- **Rules:** `_format_destination_id` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old Press")`, but deleted machine.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="machine", destination_id=MD.id)`.

**Then**
1. returns: `result == "Old Press"`.

### POM-FD-10 — project names the component
- **Rules:** `_format_destination_id` R2 (revisit after launch)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="project", destination_id=C1.id)`.

**Then**
1. returns: `result == "Part 1"`.

### POM-FD-11 — a missing project component falls back
- **Rules:** `_format_destination_id` R2 (revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="project", destination_id=MISSING)`.

**Then**
1. returns: `result == f"Project component #{MISSING}"`.

### POM-FD-12 — any other type shows "#<id>"
- **Rules:** `_format_destination_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type="dock", destination_id=F1.id)`.

**Then**
1. returns: `result == f"#{F1.id}"`.

### POM-FD-13 — no type shows "#<id>"
- **Rules:** `_format_destination_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_destination_id(db, workspace_id=W1.id, destination_type=None, destination_id=F1.id)`.

**Then**
1. returns: `result == f"#{F1.id}"`.

## `PurchaseOrderManager._format_field_value`

### POM-FV-01 — account: name, foreign fallback, dash
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._format_field_value(db, workspace_id=W1.id, field="account_id", value=v) for v in (A1.id, A9.id, None)]` (one call per value; the card checks all three).

**Then**
1. returns: `result == ["Northwind Traders", f"Account #{A9.id}", "—"]`.

### POM-FV-02 — destination type labels
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._format_field_value(db, workspace_id=W1.id, field="destination_type", value=v) for v in ("storage", "MACHINE", "project", "dock", "", None)]`.

**Then**
1. returns: `result == ["Storage", "Machine", "Project", "dock", "—", "—"]`.

### POM-FV-03 — destination id uses the given type
- **Rules:** `_format_field_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_field_value(db, workspace_id=W1.id, field="destination_id", value=M1.id, destination_type="machine")`.

**Then**
1. returns: `result == "Press 1"`.

### POM-FV-04 — threshold: none is "All assigned", a number is its text
- **Rules:** `_format_field_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._format_field_value(db, workspace_id=W1.id, field="required_approvals", value=v) for v in (None, 0, 3)]`.

**Then**
1. returns: `result == ["All assigned", "0", "3"]`.

### POM-FV-05 — status: name, missing fallback, dash
- **Rules:** `_format_field_value` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._format_field_value(db, workspace_id=W1.id, field="current_status_id", value=v) for v in (SR1.id, MISSING, None)]`.

**Then**
1. returns: `result == ["Receiving", f"Status #{MISSING}", "—"]`.

### POM-FV-06 — a status of W2 is shown as "Status #<id>"
- **Rules:** `_format_field_value` R5 [BUG-2875]
- **Kind:** bug
- **Expect:** xfail BUG-2875
- **Fails today on:** Then 1 (today the W2 name "Receiving" is shown)

**Given**
1. Standing rows only.

**When**
- `result = M._format_field_value(db, workspace_id=W1.id, field="current_status_id", value=SR9.id)`.

**Then**
1. returns: `result == f"Status #{SR9.id}"`.

### POM-FV-07 — a status of W0 is shown as "Status #<id>"
- **Rules:** `_format_field_value` R5 [BUG-2875]
- **Kind:** bug
- **Expect:** xfail BUG-2875
- **Fails today on:** Then 1 (today the W0 name "Draft" is shown)

**Given**
1. Standing rows only.

**When**
- `result = M._format_field_value(db, workspace_id=W1.id, field="current_status_id", value=SD0.id)`.

**Then**
1. returns: `result == f"Status #{SD0.id}"`.

### POM-FV-08 — any other field is formatted as a scalar
- **Rules:** `_format_field_value` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._format_field_value(db, workspace_id=W1.id, field="expected_delivery_date", value=D2)`.

**Then**
1. returns: `result == "2026-03-20"`.

### POM-FV-09 — None in an ordinary field is a dash
- **Rules:** `_format_field_value` R6, `_format_scalar_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = [M._format_field_value(db, workspace_id=W1.id, field=f, value=None) for f in ("description", "order_date", "expected_delivery_date")]`.

**Then**
1. returns: `result == ["—", "—", "—"]`.

## `PurchaseOrderManager._collect_field_changes`, `_collect_item_field_changes`, `_log_field_change_event`

### POM-CF-01 — changed fields in dict order; equal and absent ones skipped
- **Rules:** `_collect_field_changes` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`, `expected_delivery_date D2`.

**When**
- `result = M._collect_field_changes(db, workspace_id=W1.id, record=O, update_dict={"description": "Urgent", "order_date": D1, "expected_delivery_date": D3}, fields={"destination_type": "Destination type", "order_date": "Order date", "expected_delivery_date": "Expected delivery", "description": "Description"})`.

**Then**
1. returns: `[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in result] == [("expected_delivery_date", "Expected delivery", "2026-03-20", "2026-04-15"), ("description", "Description", "Steel", "Urgent")]`.
2. returns: `set(result[0].keys()) == {"field", "label", "from_value", "to_value"}`.

### POM-CF-02 — nothing changed: an empty list
- **Rules:** `_collect_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `description "Steel"`.

**When**
- `result = M._collect_field_changes(db, workspace_id=W1.id, record=O, update_dict={"description": "Steel"}, fields={"description": "Description", "order_date": "Order date"})`.

**Then**
1. returns: `result == []`.

### POM-CF-03 — a destination id: "from" with the stored type, "to" with the new type
- **Rules:** `_collect_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M._collect_field_changes(db, workspace_id=W1.id, record=O, update_dict={"destination_type": "machine", "destination_id": M1.id}, fields={"destination_id": "Destination"})`.

**Then**
1. returns: `[(c["field"], c["label"], c["from_value"], c["to_value"]) for c in result] == [("destination_id", "Destination", "Main Plant", "Press 1")]`.

### POM-CF-04 — the labels of supplier, order date, status and approval threshold
- **Rules:** `_collect_field_changes` R1 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `required_approvals 1`.

**When**
- `result = M._collect_field_changes(db, workspace_id=W1.id, record=O, update_dict={"account_id": A3.id, "order_date": D2, "current_status_id": SP1.id, "required_approvals": 2}, fields={"account_id": "Supplier", "order_date": "Order date", "current_status_id": "Status", "required_approvals": "Approval threshold"})`.

**Then**
1. returns: `[(c["field"], c["label"]) for c in result] == [("account_id", "Supplier"), ("order_date", "Order date"), ("current_status_id", "Status"), ("required_approvals", "Approval threshold")]`.

### POM-CI-01 — line quantity and price changes with their labels
- **Rules:** `_collect_item_field_changes` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `notes "Zinc"`.

**When**
- `result = M._collect_item_field_changes(record=L, update_dict={"quantity_ordered": Decimal("12"), "unit_price": Decimal("2.50"), "notes": "Brass"})`.

**Then**
1. returns: `result == [{"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "12"}, {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "2.5"}, {"field": "notes", "label": "Notes", "from_value": "Zinc", "to_value": "Brass"}]`.

### POM-CI-02 — equality is numeric; received is never listed
- **Rules:** `_collect_item_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `result = M._collect_item_field_changes(record=L, update_dict={"quantity_ordered": Decimal("10"), "unit_price": Decimal("2.0"), "quantity_received": Decimal("4")})`.

**Then**
1. returns: `result == []`.

### POM-LF-01 — one event with the changes plus extra metadata
- **Rules:** `_log_field_change_event` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M._log_field_change_event(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id, event_type="item_updated", description="Updated item: Bolt", changes=[{"field": "notes"}], extra_metadata={"line_number": 1})`.

**Then**
1. event: `len(EV(O)) == 1`.
2. event: `EV(O)[0].event_type == "item_updated"`, `description == "Updated item: Bolt"`, `performed_by == U2.id`.
3. event: `EV(O)[0].metadata_json == {"changes": [{"field": "notes"}], "line_number": 1}`.
4. returns: `result is None`.

### POM-LF-02 — never commits
- **Rules:** `_log_field_change_event` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M._log_field_change_event(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id, event_type="x", description="y", changes=[])`.

**Then**
1. mock called: `cm.call_count == 0`.

## `_confirmed_supplier_update_fields` / `_confirmed_detail_update_fields`, `_items_structure_confirmed`, `_base_sections_confirmed`

### POM-CU-01 — locked: the supplier field and the four detail fields are blocked
- **Rules:** `_confirmed_supplier_update_fields` / `_confirmed_detail_update_fields` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but `invoice_id V.id` (all confirms False).

**When**
- `result = (M._confirmed_supplier_update_fields(db, record=O), M._confirmed_detail_update_fields(db, record=O))`.

**Then**
1. returns: `set(result[0]) == {"account_id"}`.
2. returns: `set(result[1]) == {"destination_type", "destination_id", "order_date", "description"}`.

### POM-CU-02 — confirmed sections block their fields without a lock
- **Rules:** `_confirmed_supplier_update_fields` / `_confirmed_detail_update_fields` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.

**When**
- `result = (M._confirmed_supplier_update_fields(db, record=O), M._confirmed_detail_update_fields(db, record=O))`.

**Then**
1. returns: `set(result[0]) == {"account_id"}`.
2. returns: `set(result[1]) == {"destination_type", "destination_id", "order_date", "description"}`.

### POM-CU-03 — nothing confirmed, no lock: nothing blocked
- **Rules:** `_confirmed_supplier_update_fields` / `_confirmed_detail_update_fields` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("draft", "unpaid").
2. O = po "1", but `invoice_id V.id`, `items_confirmed True`.

**When**
- `result = (M._confirmed_supplier_update_fields(db, record=O), M._confirmed_detail_update_fields(db, record=O))`.

**Then**
1. returns: `set(result[0]) == set()`.
2. returns: `set(result[1]) == set()`.

### POM-IS-01 — items confirmed, locked, or neither
- **Rules:** `_items_structure_confirmed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. OA = po "1", but `items_confirmed True`. OB = po "2", but `invoice_id V.id`. OC = po "3", but `supplier_confirmed True`, `details_confirmed True`.

**When**
- `result = [M._items_structure_confirmed(db, po=o) for o in (OA, OB, OC)]`.

**Then**
1. returns: `result == [True, True, False]`.

### POM-BS-01 — all three base sections confirmed; invoice flag not read
- **Rules:** `_base_sections_confirmed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but confirmed (`invoice_confirmed` False).

**When**
- `result = M._base_sections_confirmed(O)`.

**Then**
1. returns: `result is True`.

### POM-BS-02 — one base section missing
- **Rules:** `_base_sections_confirmed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = po "1", but `supplier_confirmed True`, `details_confirmed True`, `invoice_confirmed True`.
2. OB = po "2", but `supplier_confirmed True`, `items_confirmed True`.
3. OC = po "3", but `details_confirmed True`, `items_confirmed True`.

**When**
- `result = [M._base_sections_confirmed(o) for o in (OA, OB, OC)]`.

**Then**
1. returns: `result == [False, False, False]`.

## `PurchaseOrderManager.apply_post_invoice_confirms`

### POM-AP-01 — nothing confirmed: all four confirmed, five events in order
- **Rules:** `apply_post_invoice_confirms` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. P = appr(O, U2), but approved.

**When**
- `result = M.apply_post_invoice_confirms(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read O: `supplier_confirmed is True`, `details_confirmed is True`, `items_confirmed is True`, `invoice_confirmed is True`.
2. re-read O: `current_status_id == SD1.id`.
3. unchanged: unchanged(P).
4. event: `types(O) == ["invoice_created", "supplier_confirmed", "details_confirmed", "items_confirmed", "invoice_confirmed"]`.
5. event: `[e.description for e in EV(O)] == ["Invoice created", "Supplier confirmed after invoice created", "Order details confirmed after invoice created", "Order items confirmed after invoice created", "Draft invoice confirmed after invoice finalized"]`.
6. returns: `result is None`.

### POM-AP-02 — sections already confirmed log nothing
- **Rules:** `apply_post_invoice_confirms` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.

**When**
- `M.apply_post_invoice_confirms(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read O: `items_confirmed is True`, `invoice_confirmed is True`.
2. event: `types(O) == ["invoice_created", "items_confirmed", "invoice_confirmed"]`.

### POM-AP-03 — everything confirmed: only "Invoice created"
- **Rules:** `apply_post_invoice_confirms` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but confirmed, `invoice_confirmed True`.

**When**
- `M.apply_post_invoice_confirms(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. event: `types(O) == ["invoice_created"]`.

### POM-AP-04 — never commits
- **Rules:** `apply_post_invoice_confirms` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.apply_post_invoice_confirms(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.get_purchase_order`

### POM-GP-01 — the workspace's order, voided ones included
- **Rules:** `get_purchase_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but voided.

**When**
- `result = M.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`, `result.voided is True`.

### POM-GP-02 — a missing order: 404
- **Rules:** `get_purchase_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.get_purchase_order(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.

### POM-GP-03 — an order of W0: 404
- **Rules:** `get_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po of W0 "0".

**When**
- `M.get_purchase_order(db, po_id=O0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O0.id} not found"`.

### POM-GP-04 — an order of W2: 404
- **Rules:** `get_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".

**When**
- `M.get_purchase_order(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.

## Hub pass-throughs

### POM-HUB-01 — the list returns the DAO's page with the defaults skip 0, limit 50
- **Rules:** hub R1 (`list_purchase_orders_for_hub`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(52): db.add(PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-{k:03d}", account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id))`, then one `db.flush()`.

**When**
- `result = M.list_purchase_orders_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `result == purchase_order_dao.list_for_hub(db, workspace_id=W1.id, skip=0, limit=50)`.

### POM-HUB-02 — skip, limit and filters are passed through
- **Rules:** hub R1 (`list_purchase_orders_for_hub`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `for k in range(6): db.add(PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-{k:03d}", account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id))`, then one `db.flush()`.
2. OA = po "A", but `account_id A3.id`.

**When**
- `result = M.list_purchase_orders_for_hub(db, workspace_id=W1.id, skip=2, limit=3, account_id=A1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result == purchase_order_dao.list_for_hub(db, workspace_id=W1.id, skip=2, limit=3, account_id=A1.id)`.

### POM-HUB-03 — the count is the DAO's count
- **Rules:** hub R1 (`count_purchase_orders_for_hub`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = po "A". OB = po "B", but `account_id A3.id`. O9 = po of W9 "9".

**When**
- `result = M.count_purchase_orders_for_hub(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `result == purchase_order_dao.count_for_hub(db, workspace_id=W1.id, account_id=A1.id)`.
2. returns: `result == 1`.

### POM-HUB-04 — the stats are the DAO's stats
- **Rules:** hub R1 (`purchase_order_hub_stats`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = po "A", but `total_amount Decimal("40.00")`, `subtotal Decimal("40.00")`.

**When**
- `result = M.purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == purchase_order_dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

### POM-HUB-05 — recent returns the DAO's list with the default limit 10
- **Rules:** hub R1 (`list_purchase_orders_recent_for_hub`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(12): db.add(PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-{k:03d}", account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=D1, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id))`, then one `db.flush()`.

**When**
- `result = M.list_purchase_orders_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 10`.
2. returns: `result == purchase_order_dao.list_recent_for_hub(db, workspace_id=W1.id, limit=10)`.

### POM-HUB-06 — pending highlights are the DAO's highlights
- **Rules:** hub R1 (`purchase_order_pending_highlights_for_hub`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = po "A". OB = po "B", but confirmed.

**When**
- `result = M.purchase_order_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == purchase_order_dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

## `PurchaseOrderManager.delete_purchase_order`

### POM-DL-01 — an order with nothing received goes with its lines, approvers and events
- **Rules:** `delete_purchase_order` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2.
3. P = appr(O, U2). E = evt(O, T1).
4. OK = po "2" (another W1 order). LK = line 1 of OK, I1.

**When**
- `result = DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. re-read: gone(L1), gone(L2).
3. re-read: gone(P), gone(E).
4. unchanged: unchanged(OK).
5. unchanged: unchanged(LK).
6. returns: `result is None`.

### POM-DL-02 — a missing order: 404
- **Rules:** `delete_purchase_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `DEL(MISSING)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.
3. session clean.
4. nothing written.

### POM-DL-03 — an order of W0: 404, kept
- **Rules:** `delete_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po of W0 "0".

**When**
- `DEL(O0.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O0.id} not found"`.
3. unchanged: unchanged(O0).

### POM-DL-04 — an order of W2: 404, kept
- **Rules:** `delete_purchase_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".

**When**
- `DEL(O9.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.
3. unchanged: unchanged(O9).

### POM-DL-05 — a receive event blocks the delete
- **Rules:** `delete_purchase_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.
4. RE = rev(O).

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a purchase order with receiving history — void the order instead"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).

### POM-DL-06 — receive events filed under W0 or W2 do not block
- **Rules:** `delete_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. R0 = rev(O), but `workspace_id W0.id` (invalid data). R9 = rev(O), but `workspace_id W2.id` (invalid data).

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).

### POM-DL-07 — a line with something received blocks the delete
- **Rules:** `delete_purchase_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("0.01")`.

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a purchase order with recorded receiving — void the order instead"`.
3. session clean.
4. nothing written.

### POM-DL-08 — a receive event and a received line: the receive event answers first
- **Rules:** `delete_purchase_order` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1, but `quantity_received Decimal("5.00")`.
4. RE = rev(O).

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a purchase order with receiving history — void the order instead"`.

### POM-DL-09 — a negative received quantity does not block
- **Rules:** `delete_purchase_order` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("-1.00")`.

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. re-read: gone(L).

### POM-DL-10 — a voided order with nothing received is deleted
- **Rules:** `delete_purchase_order` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but voided, `supplier_confirmed True`.
2. L = line 1 of O, I1.

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. re-read: gone(L).

### POM-DL-11 — a finalized invoice blocks the delete
- **Rules:** `delete_purchase_order` R3a [BUG-2888]
- **Kind:** bug
- **Expect:** xfail BUG-2888
- **Fails today on:** Then 1 (no error is raised; the order is deleted; verified)

**Given**
1. V = inv("confirmed", "partial"), but `paid_amount Decimal("10.00")`.
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a purchase order with a finalized invoice — void the order instead"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).
6. unchanged: unchanged(V).

### POM-DL-12 — a finalized invoice and a receive event: the receive event answers first
- **Rules:** `delete_purchase_order` R2, R3a (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. RE = rev(O).

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a purchase order with receiving history — void the order instead"`.
3. unchanged: unchanged(V).

### POM-DL-13 — a draft invoice is deleted with the order
- **Rules:** `delete_purchase_order` R4a [BUG-2888]
- **Kind:** bug
- **Expect:** xfail BUG-2888
- **Fails today on:** Then 2 (today the draft invoice stays; verified)

**Given**
1. VD = inv("draft", "unpaid").
2. O = po "1", but `invoice_id VD.id`, `invoice_ever_linked True`.
3. L = line 1 of O, I1.
4. VL = invl(VD).

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. re-read: gone(VD).
3. count: `invoice_items` has 0 rows with `invoice_id == VD.id`.
4. re-read: gone(VL).

### POM-DL-14 — with a draft invoice linked, the order and its lines go
- **Rules:** `delete_purchase_order` R4, R4a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. VD = inv("draft", "unpaid").
2. O = po "1", but `invoice_id VD.id`, `invoice_ever_linked True`.
3. L = line 1 of O, I1.

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. re-read: gone(L).

### POM-DL-15 — a voided invoice still linked stays as it is
- **Rules:** `delete_purchase_order` R3a, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VV = inv("voided", "unpaid").
2. O = po "1", but `invoice_id VV.id` (legacy data: a void normally unlinks).

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. unchanged: unchanged(VV).

### POM-DL-16 — a confirmed invoice of W2 linked by mistake neither blocks nor is touched
- **Rules:** `delete_purchase_order` R3a, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V9 = inv("confirmed", "unpaid") of W9.
2. O = po "1", but `invoice_id V9.id` (invalid data).

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. unchanged: unchanged(V9).

### POM-DL-17 — a delete writes one workspace audit row
- **Rules:** `delete_purchase_order` R5 [BUG-1195]
- **Kind:** bug
- **Expect:** xfail BUG-1195
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. O = po "1", but `total_amount Decimal("25.00")`, `subtotal Decimal("25.00")`.
2. Snapshot `number = O.po_number`, `created_at = O.created_at` (re-read before the call).

**When**
- `M.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read: gone(O).
2. audit: exactly 1 `workspace_audit_logs` row with `resource_type "purchase_order"` and `resource_id == O.id`.
3. audit: that row has `workspace_id == W1.id`, `user_id == U2.id`, `action == "purchase_order_deleted"`.
4. audit: its `metadata_json == {"number": number, "total_amount": "25.00", "created_by": U1.id, "created_at": created_at.isoformat()}`.

### POM-DL-18 — a refused delete writes no audit row
- **Rules:** `delete_purchase_order` R5 [BUG-1195]
- **Kind:** bug
- **Expect:** xfail BUG-1195
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. O = po "1".
2. RE = rev(O).

**When**
- `M.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. count: `workspace_audit_logs` has as many rows as before the call.

### POM-DL-19 — the order row is read FOR UPDATE before the checks
- **Rules:** `delete_purchase_order` R6 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `DEL(O.id)`.

**Then**
1. re-read: gone(O).
2. statement: locks O first.

### POM-DL-20 — never commits
- **Rules:** `delete_purchase_order` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `DEL(O.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-DL-21 — a delete without user_id raises TypeError and deletes nothing
- **Rules:** `delete_purchase_order` R5a [BUG-1195] (G13)
- **Kind:** bug
- **Expect:** xfail BUG-1195
- **Fails today on:** Then 1 (no error: the order is deleted)

**Given**
1. O = po "1".

**When**
- `M.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id)` (no `user_id`).

**Then**
1. raises: `TypeError`.
2. re-read O: the row still exists.
3. count: `workspace_audit_logs` has as many rows as before the call.

## `_quantity_received_decimal`, `_validate_ordered_vs_received`, `_ensure_catalog_item_not_on_po`

### POM-QR-01 — None received is 0
- **Rules:** `_quantity_received_decimal` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = mem(quantity_received=None).

**When**
- `result = M._quantity_received_decimal(A)`.

**Then**
1. returns: `result == Decimal(0)`.

### POM-QR-02 — a value goes through its text
- **Rules:** `_quantity_received_decimal` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = mem(quantity_received=Decimal("2.50")).

**When**
- `result = M._quantity_received_decimal(A)`.

**Then**
1. returns: `str(result) == "2.50"`.

### POM-VO-01 — ordered below a whole received quantity: 400 with "7"
- **Rules:** `_validate_ordered_vs_received` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M._validate_ordered_vs_received(Decimal("6.99"), Decimal("7.00"))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Ordered quantity cannot be less than received (7)"`.

### POM-VO-02 — a fractional received quantity is shown normalized
- **Rules:** `_validate_ordered_vs_received` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M._validate_ordered_vs_received(Decimal("5"), Decimal("7.50"))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Ordered quantity cannot be less than received (7.5)"`.

### POM-VO-03 — equal passes
- **Rules:** `_validate_ordered_vs_received` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = M._validate_ordered_vs_received(Decimal("7"), Decimal("7.00"))`.

**Then**
1. returns: `result is None` (no error).

### POM-EC-01 — an item already on the order: 409 with its name
- **Rules:** `_ensure_catalog_item_not_on_po` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `M._ensure_catalog_item_not_on_po(db, po_id=O.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Bolt is already on this purchase order"`.

### POM-EC-02 — the excluded line does not count
- **Rules:** `_ensure_catalog_item_not_on_po` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `result = M._ensure_catalog_item_not_on_po(db, po_id=O.id, item_id=I1.id, workspace_id=W1.id, exclude_item_id=L.id)`.

**Then**
1. returns: `result is None` (no error).

### POM-EC-03 — the same item on another order does not count
- **Rules:** `_ensure_catalog_item_not_on_po` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OA = po "1". O = po "2". OC = po "3".
2. LA = line 1 of OA, I1. LC = line 1 of OC, I1.

**When**
- `result = M._ensure_catalog_item_not_on_po(db, po_id=O.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None` (no error).

### POM-EC-04 — an item not of the workspace is named "Item #<id>"
- **Rules:** `_ensure_catalog_item_not_on_po` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I9 (invalid data: a W2 item).

**When**
- `M._ensure_catalog_item_not_on_po(db, po_id=O.id, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == f"Item #{I9.id} is already on this purchase order"`.

## `PurchaseOrderManager.add_item`

### POM-AI-01 — a new line after the highest number, totals and event
- **Rules:** `add_item` R4, R5, R6, `_recalc_totals` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("40.00")`, `total_amount Decimal("40.00")`.
2. L1 = line 1 of O, I1. L3 = line 3 of O, I3.

**When**
- `result = M.add_item(db, po_id=O.id, data=IC(item_id=I2.id, quantity_ordered=Decimal("5"), unit_price=Decimal("2.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`, `result.line_number == 4`.
2. re-read result: `purchase_order_id == O.id`, `item_id == I2.id`, `quantity_ordered == Decimal("5.00")`, `quantity_received == Decimal("0.00")`, `unit_price == Decimal("2.50")`, `line_subtotal == Decimal("12.50")`.
3. re-read O: `subtotal == Decimal("52.50")`, `total_amount == Decimal("52.50")`.
4. event: `types(O) == ["item_added"]`.
5. event: `EV(O)[0].description == "Added Nut (line 4)"`, `performed_by == U2.id`.
6. event: `EV(O)[0].metadata_json == {"item_id": I2.id, "item_name": "Nut", "line_number": 4, "quantity_ordered": "5", "unit_price": "2.5"}`.

### POM-AI-02 — an empty order gets line 1; no price shows a dash
- **Rules:** `add_item` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("3")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read result: `unit_price is None`, `line_subtotal is None`.
3. re-read O: `total_amount == Decimal("0.00")`.
4. event: `EV(O)[0].metadata_json["unit_price"] == "—"`.

### POM-AI-03 — with a user the stage is synced
- **Rules:** `add_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (nothing confirmed: out of step on purpose).

**When**
- `result = M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read O: `current_status_id == SD1.id`.
3. event: `types(O) == ["item_added", "status_updated"]`.

### POM-AI-04 — without a user the stage is not synced
- **Rules:** `add_item` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).

**When**
- `result = M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00")), workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read O: `current_status_id == SP1.id`.
3. event: `types(O) == ["item_added"]`.
4. event: `EV(O)[0].performed_by is None`.

### POM-AI-05 — a missing order: 404
- **Rules:** `add_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.add_item(db, po_id=MISSING, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order not found"`.
3. session clean.
4. nothing written.

### POM-AI-06 — an order of W2: 404
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".

**When**
- `M.add_item(db, po_id=O9.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order not found"`.
3. nothing written.

### POM-AI-07 — a voided order is refused
- **Rules:** `add_item` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised; verified)

**Given**
1. O = po "1", but voided.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. nothing written.

### POM-AI-08 — items confirmed: 400
- **Rules:** `add_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order items are confirmed"`.
3. session clean.
4. nothing written.

### POM-AI-09 — financially locked: 400 "Confirmed after invoice creation"
- **Rules:** `add_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. nothing written.

### POM-AI-10 — the item is already on the order: 409
- **Rules:** `add_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Bolt is already on this purchase order"`.
3. count: O has exactly 1 line.

### POM-AI-11 — an item of W2 is refused
- **Rules:** `add_item` R3 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1".

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I9.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I9.id} not found"`.
3. count: O has 0 lines.

### POM-AI-12 — the order row is read FOR UPDATE before the lock check
- **Rules:** `add_item` R7 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. statement: locks O first.

### POM-AI-13 — never commits
- **Rules:** `add_item` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-AI-14 — a foreign item that is also on the order: 404 before 409
- **Rules:** `add_item` R3 [BUG-1017] (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (today 409 `"Bolt is already on this purchase order"`)

**Given**
1. O = po "1".
2. L = line 1 of O, I9 (old data: a line stored before the fix with W2's item).

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I9.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I9.id} not found"`.
3. count: O has exactly 1 line.

### POM-AI-15 — items confirmed and a foreign item: the section guard answers
- **Rules:** `add_item` R2, R3 (spec Overview check order, G4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I9.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order items are confirmed"`.
3. nothing written.

### POM-AI-16 — voided with items confirmed: the voided check answers first
- **Rules:** `add_item` R1a [BUG-2882], R2 (spec Overview check order, G4)
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 2 (today the guard answers: `"Order items are confirmed"`)

**Given**
1. O = po "1", but voided, `items_confirmed True`.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I1.id, quantity_ordered=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. nothing written.

### POM-AI-17 — a completed order: 400 "Confirmed after invoice creation"
- **Rules:** `add_item` R2, `is_po_financially_locked` R2; RP5 (PO)
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but complete by V.

**When**
- `M.add_item(db, po_id=O.id, data=IC(item_id=I2.id, quantity_ordered=Decimal("1"), unit_price=Decimal("1.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. nothing written.

## `PurchaseOrderManager.update_item`

### POM-UI-01 — quantity and price change: subtotal, totals, one event
- **Rules:** `update_item` R5, R6, R8, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("40.00")`, `total_amount Decimal("40.00")`.
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2.

**When**
- `result = M.update_item(db, item_id=L1.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("12"), unit_price=Decimal("2.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. re-read L1: `quantity_ordered == Decimal("12.00")`, `unit_price == Decimal("2.50")`, `line_subtotal == Decimal("30.00")`.
3. re-read O: `subtotal == Decimal("50.00")`, `total_amount == Decimal("50.00")`.
4. event: `types(O) == ["item_updated"]`.
5. event: `EV(O)[0].description == "Updated item: Bolt"`, `performed_by == U2.id`.
6. event: `EV(O)[0].metadata_json == {"changes": [{"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "12"}, {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "2.5"}], "item_id": I1.id, "item_name": "Bolt", "line_number": 1}`.

### POM-UI-02 — only the price: subtotal from the stored quantity
- **Rules:** `update_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("20.00")`, `total_amount Decimal("20.00")`.
2. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(unit_price=Decimal("3.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity_ordered == Decimal("10.00")`, `line_subtotal == Decimal("30.00")`.
3. re-read O: `total_amount == Decimal("30.00")`.

### POM-UI-03 — only the notes: subtotal untouched, "Notes" change logged
- **Rules:** `update_item` R5, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("20.00")`, `total_amount Decimal("20.00")`.
2. L = line 1 of O, I1, but `line_subtotal Decimal("20.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(notes="Zinc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes == "Zinc"`, `line_subtotal == Decimal("20.00")`.
3. event: `EV(O)[0].metadata_json["changes"] == [{"field": "notes", "label": "Notes", "from_value": "—", "to_value": "Zinc"}]`.

### POM-UI-04 — the same values: no event
- **Rules:** `update_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("10"), unit_price=Decimal("2.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. event: `EV(O) == []`.

### POM-UI-05 — without a user: no stage sync, event without performer
- **Rules:** `update_item` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("11")), workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read O: `current_status_id == SP1.id`.
3. event: `types(O) == ["item_updated"]`.
4. event: `EV(O)[0].performed_by is None`.

### POM-UI-06 — with a user the stage is synced
- **Rules:** `update_item` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("11")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read O: `current_status_id == SD1.id`.
3. event: `types(O) == ["item_updated", "status_updated"]`.

### POM-UI-07 — a missing line: 404
- **Rules:** `update_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.update_item(db, item_id=MISSING, data=PurchaseOrderItemUpdate(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order item not found"`.
3. session clean.
4. nothing written.

### POM-UI-08 — a line of W2: 404
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. L9 = line 1 of O9, I9.

**When**
- `M.update_item(db, item_id=L9.id, data=PurchaseOrderItemUpdate(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order item not found"`.
3. unchanged: unchanged(L9).

### POM-UI-09 — a line of a voided order is refused
- **Rules:** `update_item` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1", but voided.
2. L = line 1 of O, I1.

**When**
- `M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("12")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-UI-10 — items confirmed: 400
- **Rules:** `update_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.
2. L = line 1 of O, I1.

**When**
- `M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("12")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order items are confirmed (receiving still allowed)"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-UI-11 — financially locked: 400 "Confirmed after invoice creation (receiving still allowed)"
- **Rules:** `update_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.

**When**
- `M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation (receiving still allowed)"`.
3. unchanged: unchanged(L).

### POM-UI-12 — locked with an empty body: passes and changes nothing
- **Rules:** `update_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. unchanged: unchanged(L).
3. event: `EV(O) == []`.

### POM-UI-13 — ordered below received: 400; equal passes
- **Rules:** `update_item` R4, `_validate_ordered_vs_received` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("6.00")`.

**When**
- `M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("5.99")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Ordered quantity cannot be less than received (6)"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-UI-14 — ordered equal to received passes
- **Rules:** `update_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("6.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("6")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity_ordered == Decimal("6.00")`, `line_subtotal == Decimal("12.00")`.

### POM-UI-15 — an explicit null clears the price and the subtotal
- **Rules:** `update_item` R1, R5 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today the null is dropped)

**Given**
1. O = po "1", but `subtotal Decimal("20.00")`, `total_amount Decimal("20.00")`.
2. L = line 1 of O, I1.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(unit_price=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `unit_price is None`, `line_subtotal is None`.
3. re-read O: `total_amount == Decimal("0.00")`.

### POM-UI-16 — an explicit null clears the notes
- **Rules:** `update_item` R1 [BUG-2879]
- **Kind:** bug
- **Expect:** xfail BUG-2879
- **Fails today on:** Then 2 (today the notes stay)

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `notes "Zinc"`.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(notes=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes is None`.

### POM-UI-17 — the order row is read FOR UPDATE before the checks
- **Rules:** `update_item` R18 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. L = line 1 of O, I1.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("12")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. statement: locks O first.

### POM-UI-18 — never commits
- **Rules:** `update_item` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- commit spy around `M.update_item(db, item_id=L.id, data=PurchaseOrderItemUpdate(quantity_ordered=Decimal("12")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.remove_item`

### POM-RI-01 — the line goes, other numbers keep their gap, totals and event
- **Rules:** `remove_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("60.00")`, `total_amount Decimal("60.00")`.
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2. L3 = line 3 of O, I3.

**When**
- `result = M.remove_item(db, item_id=L2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 2`, `result.purchase_order_id == O.id`.
2. re-read: gone(L2).
3. re-read: `[l.line_number for l in LINES(O)] == [1, 3]`.
4. re-read O: `subtotal == Decimal("40.00")`, `total_amount == Decimal("40.00")`.
5. event: `types(O) == ["item_removed"]`.
6. event: `EV(O)[0].description == "Removed Nut (line 2)"`.
7. event: `EV(O)[0].metadata_json == {"item_id": I2.id, "item_name": "Nut", "line_number": 2}`.

### POM-RI-02 — with a user the stage is synced; without, not
- **Rules:** `remove_item` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read O: `current_status_id == SD1.id`.
3. event: `types(O) == ["item_removed", "status_updated"]`.

### POM-RI-03 — without a user the stage is not synced
- **Rules:** `remove_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read O: `current_status_id == SP1.id`.
3. event: `types(O) == ["item_removed"]`.

### POM-RI-04 — a missing line: 404
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order item not found"`.
3. session clean.
4. nothing written.

### POM-RI-05 — a line of W2: 404
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. L9 = line 1 of O9, I9.

**When**
- `M.remove_item(db, item_id=L9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order item not found"`.
3. unchanged: unchanged(L9).

### POM-RI-06 — a line of a voided order is refused
- **Rules:** `remove_item` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1", but voided.
2. L = line 1 of O, I1.

**When**
- `M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-RI-07 — items confirmed: 400
- **Rules:** `remove_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.
2. L = line 1 of O, I1.

**When**
- `M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order items are confirmed"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-RI-08 — financially locked: 400
- **Rules:** `remove_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.

**When**
- `M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. unchanged: unchanged(L).

### POM-RI-09 — a received line is not checked here
- **Rules:** `remove_item` R2 (Q8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("5.00")`.

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. re-read: gone(L).

### POM-RI-10 — the order row is read FOR UPDATE before the lock check
- **Rules:** `remove_item` R4 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. L = line 1 of O, I1.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. statement: locks O first.

### POM-RI-11 — never commits
- **Rules:** `remove_item` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- commit spy around `M.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.sync_items`

### POM-SY-01 — removals, then updates, then additions, totals once
- **Rules:** `sync_items` R3, R4, R5, R6, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("60.00")`, `total_amount Decimal("60.00")`.
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2. L3 = line 3 of O, I3.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L3.id], updates=[PurchaseOrderItemSyncUpdate(id=L1.id, quantity_ordered=Decimal("5"), unit_price=Decimal("3.00"))], additions=[IC(item_id=I3.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: gone(L3).
3. re-read L1: `quantity_ordered == Decimal("5.00")`, `unit_price == Decimal("3.00")`, `line_subtotal == Decimal("15.00")`.
4. re-read: `[(l.line_number, l.item_id) for l in LINES(O)] == [(1, I1.id), (2, I2.id), (3, I3.id)]`.
5. re-read O: `subtotal == Decimal("37.00")`, `total_amount == Decimal("37.00")`.
6. event: `types(O) == ["item_removed", "item_updated", "item_added"]`.
7. event: `EV(O)[0].description == "Removed Washer (line 3)"`.
8. event: `EV(O)[2].description == "Added Washer (line 3)"`.

### POM-SY-02 — a missing order: 404
- **Rules:** `sync_items` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.sync_items(db, po_id=MISSING, data=SYNC(remove_ids=[], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order not found"`.
3. session clean.

### POM-SY-03 — an order of W2: 404
- **Rules:** `sync_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. L9 = line 1 of O9, I9.

**When**
- `M.sync_items(db, po_id=O9.id, data=SYNC(remove_ids=[L9.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Purchase order not found"`.
3. unchanged: unchanged(L9).

### POM-SY-04 — a voided order is refused
- **Rules:** `sync_items` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1", but voided.
2. L = line 1 of O, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-SY-05 — items confirmed: 400
- **Rules:** `sync_items` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`, stage SP1.
2. L = line 1 of O, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Order items are confirmed"`.
3. session clean.
4. unchanged: unchanged(L).

### POM-SY-06 — financially locked: 400
- **Rules:** `sync_items` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. L = line 1 of O, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I2.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirmed after invoice creation"`.
3. session clean.
4. count: O has exactly 1 line.

### POM-SY-07 — removing a line of another order: 404
- **Rules:** `sync_items` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OA = po "1". O = po "2". OC = po "3".
2. LA = line 1 of OA, I1. L = line 1 of O, I1. LC = line 1 of OC, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[LC.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {LC.id} not found"`.
3. unchanged: unchanged(LC).

### POM-SY-08 — removing a line of W2: 404
- **Rules:** `sync_items` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. O9 = po of W9 "9". L9 = line 1 of O9, I9.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L9.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {L9.id} not found"`.
3. unchanged: unchanged(L9).

### POM-SY-09 — a removal listed twice: 404 on the second
- **Rules:** `sync_items` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L.id, L.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {L.id} not found"`.

### POM-SY-10 — removing a received line: 400 with its name
- **Rules:** `sync_items` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("0.01")`.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L.id], updates=[], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot remove Bolt — receiving has already been recorded"`.
3. unchanged: unchanged(L).

### POM-SY-11 — updating a line removed in the same call: 404
- **Rules:** `sync_items` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L2.id], updates=[PurchaseOrderItemSyncUpdate(id=L2.id, quantity_ordered=Decimal("4"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {L2.id} not found"`.

### POM-SY-12 — updating a line of another order: 404
- **Rules:** `sync_items` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1". OC = po "2".
2. L = line 1 of O, I1. LC = line 1 of OC, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=LC.id, quantity_ordered=Decimal("4"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {LC.id} not found"`.
3. unchanged: unchanged(LC).

### POM-SY-13 — an update with no price makes the line unpriced
- **Rules:** `sync_items` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("20.00")`, `total_amount Decimal("20.00")`.
2. L = line 1 of O, I1.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=L.id, quantity_ordered=Decimal("10"), unit_price=None)], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read L: `unit_price is None`, `line_subtotal is None`.
3. re-read O: `total_amount == Decimal("0.00")`.

### POM-SY-14 — an update below the received quantity: 400
- **Rules:** `sync_items` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1, but `quantity_received Decimal("7.50")`.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=L.id, quantity_ordered=Decimal("7"), unit_price=Decimal("2.00"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Ordered quantity cannot be less than received (7.5)"`.

### POM-SY-15 — an unchanged update logs nothing
- **Rules:** `sync_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=L.id, quantity_ordered=Decimal("10"), unit_price=Decimal("2.00"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `EV(O) == []`.

### POM-SY-16 — a changed update without a user is written but not logged; no stage sync
- **Rules:** `sync_items` R5, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=L.id, quantity_ordered=Decimal("4"), unit_price=Decimal("2.00"))], additions=[]), workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read L: `quantity_ordered == Decimal("4.00")`, `line_subtotal == Decimal("8.00")`.
3. re-read O: `current_status_id == SP1.id`.
4. event: `EV(O) == []`.

### POM-SY-17 — with a user the stage is synced
- **Rules:** `sync_items` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but stage SP1 (out of step on purpose).
2. L = line 1 of O, I1.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[PurchaseOrderItemSyncUpdate(id=L.id, quantity_ordered=Decimal("4"), unit_price=Decimal("2.00"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == SD1.id`.
3. event: `types(O) == ["item_updated", "status_updated"]`.

### POM-SY-18 — an addition of a kept line's item: 409
- **Rules:** `sync_items` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I1.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Bolt is already on this purchase order"`.

### POM-SY-19 — two additions of the same item: 409 on the second
- **Rules:** `sync_items` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I2.id, quantity_ordered=Decimal("1")), IC(item_id=I2.id, quantity_ordered=Decimal("2"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Nut is already on this purchase order"`.

### POM-SY-20 — an addition of a removed line's item is allowed
- **Rules:** `sync_items` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L2.id], updates=[], additions=[IC(item_id=I2.id, quantity_ordered=Decimal("3"), unit_price=Decimal("1.00"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: `[(l.line_number, l.item_id, l.quantity_ordered) for l in LINES(O)] == [(1, I1.id, Decimal("10.00")), (2, I2.id, Decimal("3.00"))]`.

### POM-SY-21 — an addition item of W2 is refused
- **Rules:** `sync_items` R7 [BUG-1017]
- **Kind:** bug
- **Expect:** xfail BUG-1017
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1".

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I9.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I9.id} not found"`.
3. count: O has 0 lines.

### POM-SY-22 — three added lines of 1.25 × 0.10 total 0.39
- **Rules:** `sync_items` R8, `_recalc_totals` R1, R1a (G15)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I1.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I2.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10")), IC(item_id=I3.id, quantity_ordered=Decimal("1.25"), unit_price=Decimal("0.10"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `subtotal == Decimal("0.39")`, `total_amount == Decimal("0.39")`.

### POM-SY-23 — a refusal after a removal leaves the removal flushed for the caller to roll back
- **Rules:** `sync_items` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2.

**When**
- `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L2.id], updates=[PurchaseOrderItemSyncUpdate(id=MISSING, quantity_ordered=Decimal("1"))], additions=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order item {MISSING} not found"`.
3. re-read: gone(L2).
4. unchanged: unchanged(L1).

### POM-SY-24 — the order row is read FOR UPDATE before the lock check
- **Rules:** `sync_items` R9 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I1.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: locks O first.

### POM-SY-25 — never commits
- **Rules:** `sync_items` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I1.id, quantity_ordered=Decimal("1"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-SY-26 — the removal, update and addition events carry their metadata
- **Rules:** `sync_items` R3, R5, R6; `remove_item` R3, `update_item` R8, `add_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("60.00")`, `total_amount Decimal("60.00")`.
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2. L3 = line 3 of O, I3.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[L3.id], updates=[PurchaseOrderItemSyncUpdate(id=L1.id, quantity_ordered=Decimal("5"), unit_price=Decimal("3.00"))], additions=[IC(item_id=I3.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `types(O)[:3] == ["item_removed", "item_updated", "item_added"]`.
3. event: `[e.performed_by for e in EV(O)[:3]] == [U2.id, U2.id, U2.id]`.
4. event: `EV(O)[0].metadata_json == {"item_id": I3.id, "item_name": "Washer", "line_number": 3}`.
5. event: `EV(O)[1].description == "Updated item: Bolt"`.
6. event: `EV(O)[1].metadata_json == {"changes": [{"field": "quantity_ordered", "label": "Quantity ordered", "from_value": "10", "to_value": "5"}, {"field": "unit_price", "label": "Unit price", "from_value": "2", "to_value": "3"}], "item_id": I1.id, "item_name": "Bolt", "line_number": 1}`.
7. event: `EV(O)[2].metadata_json == {"item_id": I3.id, "item_name": "Washer", "line_number": 3, "quantity_ordered": "2", "unit_price": "1"}`.

### POM-SY-27 — two distinct additions are numbered n+1 and n+2 in the order sent
- **Rules:** `sync_items` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("20.00")`, `total_amount Decimal("20.00")`.
2. L2 = line 2 of O, I2.

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I3.id, quantity_ordered=Decimal("1"), unit_price=Decimal("4.00")), IC(item_id=I1.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.50"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: `[(l.line_number, l.item_id) for l in LINES(O)] == [(2, I2.id), (3, I3.id), (4, I1.id)]`.
3. re-read O: `subtotal == Decimal("27.00")`, `total_amount == Decimal("27.00")`.
4. event: `[e.description for e in EV(O) if e.event_type == "item_added"] == ["Added Washer (line 3)", "Added Bolt (line 4)"]`.
5. event: `[e.metadata_json["line_number"] for e in EV(O) if e.event_type == "item_added"] == [3, 4]`.

### POM-SY-28 — additions to an order with no lines start at line 1
- **Rules:** `sync_items` R6, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.sync_items(db, po_id=O.id, data=SYNC(remove_ids=[], updates=[], additions=[IC(item_id=I1.id, quantity_ordered=Decimal("2"), unit_price=Decimal("1.00")), IC(item_id=I2.id, quantity_ordered=Decimal("3"), unit_price=Decimal("2.00"))]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: `[(l.line_number, l.item_id) for l in LINES(O)] == [(1, I1.id), (2, I2.id)]`.
3. re-read O: `subtotal == Decimal("8.00")`, `total_amount == Decimal("8.00")`.
4. event: `[e.description for e in EV(O) if e.event_type == "item_added"] == ["Added Bolt (line 1)", "Added Nut (line 2)"]`.

## `PurchaseOrderManager.get_items`, `_recalc_totals`

### POM-GT-01 — the order's lines by line number
- **Rules:** `get_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". OC = po "2".
2. L3 = line 3 of O, I3. L1 = line 1 of O, I1. L2 = line 2 of O, I2. LC = line 1 of OC, I1.

**When**
- `result = M.get_items(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [L1.id, L2.id, L3.id]`.

### POM-GT-02 — an order with no lines: empty list
- **Rules:** `get_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.get_items(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `list(result) == []`.

### POM-GT-03 — a missing order: 404
- **Rules:** `get_items` R1 [BUG-2886]
- **Kind:** bug
- **Expect:** xfail BUG-2886
- **Fails today on:** Then 1 (today `[]` is returned)

**Given**
1. Standing rows only.

**When**
- `M.get_items(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.

### POM-GT-04 — an order of W2: 404
- **Rules:** `get_items` R1 [BUG-2886]
- **Kind:** bug
- **Expect:** xfail BUG-2886
- **Fails today on:** Then 1 (today `[]` is returned)

**Given**
1. O9 = po of W9 "9".
2. L9 = line 1 of O9, I9.

**When**
- `M.get_items(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.

### POM-GT-05 — lines of W2 are never listed
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. L = line 1 of O, I1. X9 = line 2 of O, I9, but `workspace_id W2.id` (invalid data).

**When**
- `result = M.get_items(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [L.id]`.

### POM-RT-01 — totals are the sum of priced lines
- **Rules:** `_recalc_totals` R1, R1a (G15)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L1 = line 1 of O, I1. L2 = line 2 of O, I2, but `unit_price None`, `line_subtotal None`. L3 = line 3 of O, I3, but `line_subtotal Decimal("5.00")`, `unit_price Decimal("0.50")`.

**When**
- `result = M._recalc_totals(db, po=O)`.

**Then**
1. re-read O: `subtotal == Decimal("25.00")`, `total_amount == Decimal("25.00")`.
2. returns: `result is None`.

### POM-RT-02 — no lines: 0.00
- **Rules:** `_recalc_totals` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `subtotal Decimal("9.00")`, `total_amount Decimal("9.00")`.

**When**
- `M._recalc_totals(db, po=O)`.

**Then**
1. re-read O: `subtotal == Decimal("0.00")`, `total_amount == Decimal("0.00")`.

### POM-RT-03 — never commits
- **Rules:** `_recalc_totals` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. L = line 1 of O, I1.

**When**
- commit spy around `M._recalc_totals(db, po=O)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.list_approvers`

### POM-LA-01 — triples by assigned_at, positions from the workspace membership
- **Rules:** `list_approvers` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. P2 = appr(O, U2), but `assigned_at T3`. P1 = appr(O, U1), but `assigned_at T2`. P3 = appr(O, U3), but `assigned_at T1` (U3 has no W1 membership; "Boss" is a W2 position).

**When**
- `result = M.list_approvers(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(a.id, p.id, pos) for (a, p, pos) in result] == [(P3.id, U3.id, None), (P1.id, U1.id, "Buyer"), (P2.id, U2.id, None)]`.

### POM-LA-02 — a missing order: 404
- **Rules:** `list_approvers` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.list_approvers(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.

### POM-LA-03 — an order of W2: 404
- **Rules:** `list_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. P = appr(O9, U3).

**When**
- `M.list_approvers(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.

### POM-LA-04 — tied assigned_at: the approvers query orders by id too
- **Rules:** `list_approvers` R2 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200
- **Fails today on:** Then 2 (today the ORDER BY is `assigned_at` only)

**Given**
1. O = po "1".
2. P1 = appr(O, U1). P2 = appr(O, U2) (both `assigned_at T1`).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.list_approvers(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `{a.id for (a, p, pos) in result} == {P1.id, P2.id}`.
2. statement: in the SELECT whose `FROM` names `purchase_order_approvers`, the text after `ORDER BY` contains `"purchase_order_approvers.id"`.

### POM-LA-05 — reads are a fixed number, not two per approver
- **Rules:** `list_approvers` R3 [BUG-2883]
- **Kind:** bug
- **Expect:** xfail BUG-2883
- **Author:** claude
- **Fails today on:** Then 2 (today 2 + 2 × 4 SELECTs)

**Given**
1. O = po "1".
2. appr(O, U1), but `assigned_at T1`; appr(O, U2), but `assigned_at T2`; appr(O, U4), but `assigned_at T3`; appr(O, U5), but `assigned_at T4`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.list_approvers(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. statement: `len(selects) <= 4` (order, approvers, profiles, memberships; spec R3, G11).

## `PurchaseOrderManager.approval_summary`

### POM-AS-01 — a threshold of 2 with one approval is not met
- **Rules:** `approval_summary` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `required_approvals 2`.
2. appr(O, U1), but approved. appr(O, U2). appr(O, U4).

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (1, 2, False)`.

### POM-AS-02 — a threshold of 2 with two approvals is met
- **Rules:** `approval_summary` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `required_approvals 2`.
2. appr(O, U1), but approved. appr(O, U2), but approved. appr(O, U4).

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (2, 2, True)`.

### POM-AS-03 — a threshold of 0 is met with nobody
- **Rules:** `approval_summary` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `required_approvals 0`.

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (0, 0, True)`.

### POM-AS-04 — no threshold: every approver is needed
- **Rules:** `approval_summary` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. appr(O, U1), but approved. appr(O, U2), but approved. appr(O, U4).

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (2, 3, False)`.

### POM-AS-05 — no threshold, all approved: met
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. appr(O, U1), but approved. appr(O, U2), but approved.

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (2, 2, True)`.

### POM-AS-06 — no threshold and no approvers is not met
- **Rules:** `approval_summary` R3 [BUG-1202]
- **Kind:** bug
- **Expect:** xfail BUG-1202
- **Fails today on:** Then 1 (today `(0, 0, True)`; verified)

**Given**
1. O = po "1".

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (0, 1, False)`.

### POM-AS-07 — no threshold and exactly one approver: one is needed
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. appr(O, U2).

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (0, 1, False)`.

### POM-AS-08 — a threshold of 0 with unapproved approvers is met
- **Rules:** `approval_summary` R2 ("0 included")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `required_approvals 0`.
2. appr(O, U1). appr(O, U2).

**When**
- `result = M.approval_summary(db, po=O)`.

**Then**
1. returns: `result == (0, 0, True)`.

## `PurchaseOrderManager.add_approver`

### POM-AA-01 — an active member becomes an approver
- **Rules:** `add_approver` R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `purchase_order_id == O.id`, `user_id == U2.id`, `assigned_by == U1.id`, `approved is False`, `approved_at is None`, `workspace_id == W1.id`.
3. event: `types(O) == ["approver_added"]`.
4. event: `EV(O)[0].description == "Added Bob Karim as approver"`, `performed_by == U1.id`.
5. event: `EV(O)[0].metadata_json == {"user_id": U2.id, "user_name": "Bob Karim"}`.

### POM-AA-02 — a missing order: 404
- **Rules:** `add_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.add_approver(db, po_id=MISSING, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.
3. session clean.
4. nothing written.

### POM-AA-03 — an order of W2: 404
- **Rules:** `add_approver` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".

**When**
- `M.add_approver(db, po_id=O9.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.
3. nothing written.

### POM-AA-04 — an invited member is refused
- **Rules:** `add_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `M.add_approver(db, po_id=O.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. session clean.
4. nothing written.

### POM-AA-05 — an inactive member is refused
- **Rules:** `add_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `M.add_approver(db, po_id=O.id, user_id=U5.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. nothing written.

### POM-AA-06 — an active member of W2 only is refused
- **Rules:** `add_approver` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `M.add_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. nothing written.

### POM-AA-07 — an active member of W0 only is refused
- **Rules:** `add_approver` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. U6 = `make_profile(db, name="Farid Hasan")`; `WorkspaceMember(workspace_id=W0.id, user_id=U6.id, role="member", status="active")`.

**When**
- `M.add_approver(db, po_id=O.id, user_id=U6.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. nothing written.

### POM-AA-08 — a voided order is refused
- **Rules:** `add_approver` R2a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1", but voided.

**When**
- `M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. nothing written.

### POM-AA-09 — already an approver: 409
- **Rules:** `add_approver` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. P = appr(O, U2).

**When**
- `M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "User is already an approver for this order"`.
3. nothing written.

### POM-AA-10 — an approver of another order may be added to this one
- **Rules:** `add_approver` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OA = po "1". O = po "2".
2. P = appr(OA, U2).

**When**
- `result = M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.purchase_order_id == O.id`, `result.user_id == U2.id`.

### POM-AA-11 — a completed order refuses new approvers
- **Rules:** `add_approver` R6 [BUG-2881], RP5 (PO)
- **Kind:** bug
- **Expect:** xfail BUG-2881
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.

**When**
- `M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot change approvers — order is complete"`.
3. session clean.
4. nothing written.

### POM-AA-12 — a finalized invoice refuses new approvers
- **Rules:** `add_approver` R6 [BUG-2881]
- **Kind:** bug
- **Expect:** xfail BUG-2881
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.

**When**
- `M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot change approvers — invoice is finalized"`.
3. nothing written.

### POM-AA-13 — a draft invoice does not block new approvers
- **Rules:** `add_approver` R4, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VD = inv("draft", "unpaid").
2. O = po "1", but confirmed, `invoice_id VD.id`.

**When**
- `result = M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.

### POM-AA-14 — never commits
- **Rules:** `add_approver` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-AA-15 — the order row is read FOR UPDATE before the state checks
- **Rules:** `add_approver` R7 [BUG-2872] (G14)
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (no lock today)

**Given**
1. O = po "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.add_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. statement: locks O first.

## `PurchaseOrderManager.remove_approver`

### POM-RM-01 — an approved approver is removed and logged
- **Rules:** `remove_approver` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. P = appr(O, U2), but approved. PK = appr(O, U1).

**When**
- `result = M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. re-read: gone(P).
2. unchanged: unchanged(PK).
3. event: `types(O) == ["approver_removed"]`.
4. event: `EV(O)[0].description == "Removed Bob Karim as approver"`, `performed_by == U1.id`.
5. event: `EV(O)[0].metadata_json == {"user_id": U2.id, "user_name": "Bob Karim"}`.
6. returns: `result is None`.

### POM-RM-02 — the creator can be removed; no performer
- **Rules:** `remove_approver` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1" (created by U1).
2. P = appr(O, U1).

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. re-read: gone(P).
2. event: `EV(O)[0].performed_by is None`.

### POM-RM-03 — not an approver of the order: 404
- **Rules:** `remove_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". OC = po "2".
2. PC = appr(OC, U2).

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Approver not found"`.
3. session clean.
4. unchanged: unchanged(PC).

### POM-RM-04 — a missing order: 404 "Approver not found"
- **Rules:** `remove_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.remove_approver(db, po_id=MISSING, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Approver not found"`.
3. nothing written.

### POM-RM-05 — an approver of a W2 order: 404
- **Rules:** `remove_approver` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. P9 = appr(O9, U3).

**When**
- `M.remove_approver(db, po_id=O9.id, user_id=U3.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Approver not found"`.
3. unchanged: unchanged(P9).

### POM-RM-06 — a voided order is refused
- **Rules:** `remove_approver` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = po "1", but voided.
2. P = appr(O, U2).

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-RM-07 — a completed order refuses removing approvers
- **Rules:** `remove_approver` R4 [BUG-2881], RP5 (PO)
- **Kind:** bug
- **Expect:** xfail BUG-2881
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. P = appr(O, U2), but approved.

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot change approvers — order is complete"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-RM-08 — a finalized invoice refuses removing approvers
- **Rules:** `remove_approver` R4 [BUG-2881]
- **Kind:** bug
- **Expect:** xfail BUG-2881
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. P = appr(O, U2), but approved.

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot change approvers — invoice is finalized"`.
3. unchanged: unchanged(P).

### POM-RM-09 — never commits
- **Rules:** `remove_approver` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. P = appr(O, U2).

**When**
- commit spy around `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. mock called: `cm.call_count == 0`.

### POM-RM-10 — the order row is read FOR UPDATE before the state checks
- **Rules:** `remove_approver` R5 [BUG-2872] (G14)
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (no lock today)

**Given**
1. O = po "1".
2. P = appr(O, U2).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `M.remove_approver(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. re-read: gone(P).
2. statement: locks O first.

## `PurchaseOrderManager.set_approval`

### POM-SA-01 — approving: stamped now, event, row returned
- **Rules:** `set_approval` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but confirmed.
2. P = appr(O, U2).

**When**
- under clock: `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `approved is True`, `approved_at == NOW`.
3. event: `types(O) == ["approved"]`.
4. event: `EV(O)[0].description == "Approved order"`, `performed_by == U2.id`.

### POM-SA-02 — withdrawing: cleared, event
- **Rules:** `set_approval` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1" (sections not confirmed: withdrawal does not need them).
2. P = appr(O, U2), but approved.

**When**
- `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `approved is False`, `approved_at is None`.
3. event: `types(O) == ["approval_withdrawn"]`.
4. event: `EV(O)[0].description == "Withdrew approval"`, `performed_by == U2.id`.

### POM-SA-03 — not an approver of the order: 403
- **Rules:** `set_approval` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but confirmed. OC = po "2", but confirmed.
2. PC = appr(OC, U2).

**When**
- `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 403`.
2. raises: `detail == "You are not an assigned approver for this order"`.
3. session clean.
4. unchanged: unchanged(PC).

### POM-SA-04 — an approver row of a W2 order: 403
- **Rules:** `set_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9", but `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`.
2. P9 = appr(O9, U3).

**When**
- `M.set_approval(db, po_id=O9.id, user_id=U3.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 403`.
2. raises: `detail == "You are not an assigned approver for this order"`.
3. unchanged: unchanged(P9).

### POM-SA-05 — a voided order is refused
- **Rules:** `set_approval` R1a [BUG-2882]
- **Kind:** bug
- **Expect:** xfail BUG-2882
- **Fails today on:** Then 1 (no error is raised; verified for a withdrawal)

**Given**
1. O = po "1", but voided.
2. P = appr(O, U2), but approved.

**When**
- `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Purchase order is voided"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-SA-06 — approving before the three sections are confirmed: 400
- **Rules:** `set_approval` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`, stage SP1.
2. P = appr(O, U2).

**When**
- `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Confirm supplier, order details, and items before approving"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-SA-07 — withdrawing on a completed order: 400
- **Rules:** `set_approval` R3, RP5 (PO)
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv("confirmed", "paid").
2. O = po "1", but complete by V.
3. P = appr(O, U2), but approved.

**When**
- `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot withdraw approval — order is complete"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-SA-08 — withdrawing after the invoice is finalized: 400
- **Rules:** `set_approval` R4 [BUG-2881]
- **Kind:** bug
- **Expect:** xfail BUG-2881
- **Fails today on:** Then 1 (no error is raised; the withdrawal is accepted)

**Given**
1. V = inv("confirmed", "unpaid").
2. O = po "1", but locked by V.
3. P = appr(O, U2), but approved.

**When**
- `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot withdraw approval — invoice is finalized"`.
3. session clean.
4. unchanged: unchanged(P).

### POM-SA-09 — withdrawing with a draft invoice is allowed
- **Rules:** `set_approval` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VD = inv("draft", "unpaid").
2. O = po "1", but confirmed, `invoice_id VD.id`.
3. P = appr(O, U2), but approved.

**When**
- `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `approved is False`.

### POM-SA-10 — approving twice keeps the first stamp and logs nothing
- **Rules:** `set_approval` R6 [BUG-2880]
- **Kind:** bug
- **Expect:** xfail BUG-2880
- **Fails today on:** Then 3 (today `approved_at` moves to NOW)

**Given**
1. O = po "1", but confirmed.
2. P = appr(O, U2), but approved.

**When**
- under clock: `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `approved is True`.
3. re-read P: `approved_at == T2`.
4. event: `EV(O) == []`.

### POM-SA-11 — withdrawing when not approved logs nothing
- **Rules:** `set_approval` R6 [BUG-2880]
- **Kind:** bug
- **Expect:** xfail BUG-2880
- **Fails today on:** Then 3 (today an `approval_withdrawn` event is logged)

**Given**
1. O = po "1".
2. P = appr(O, U2).

**When**
- `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `approved is False`, `approved_at is None`.
3. event: `EV(O) == []`.

### POM-SA-12 — the order row is read FOR UPDATE before the checks
- **Rules:** `set_approval` R7 [BUG-2872]
- **Kind:** bug
- **Expect:** xfail BUG-2872
- **Fails today on:** Then 2 (plain read today)

**Given**
1. O = po "1", but confirmed.
2. P = appr(O, U2).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: locks O first.

### POM-SA-13 — never commits
- **Rules:** `set_approval` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but confirmed.
2. P = appr(O, U2).

**When**
- commit spy around `M.set_approval(db, po_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.log_event`

### POM-LE-01 — one event with the given values
- **Rules:** `log_event` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.log_event(db, po_id=O.id, workspace_id=W1.id, event_type="attachment_added", description="Added drawing.pdf", performed_by=U2.id, metadata={"file": "drawing.pdf"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `purchase_order_id == O.id`, `workspace_id == W1.id`, `event_type == "attachment_added"`, `description == "Added drawing.pdf"`, `performed_by == U2.id`.
3. re-read result: `metadata_json == {"file": "drawing.pdf"}`.

### POM-LE-02 — no performer and no metadata
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = M.log_event(db, po_id=O.id, workspace_id=W1.id, event_type="note", description="x")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `performed_by is None`, `metadata_json is None`.

### POM-LE-03 — an order of W2 is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised; the row is stored under W1)

**Given**
1. O9 = po of W9 "9".

**When**
- `M.log_event(db, po_id=O9.id, workspace_id=W1.id, event_type="note", description="x")`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.
3. session clean.
4. nothing written.

### POM-LE-04 — an order of W0 is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O0 = po of W0 "0".

**When**
- `M.log_event(db, po_id=O0.id, workspace_id=W1.id, event_type="note", description="x")`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O0.id} not found"`.
3. nothing written.

### POM-LE-05 — never commits
- **Rules:** `log_event` (flush only)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".

**When**
- commit spy around `M.log_event(db, po_id=O.id, workspace_id=W1.id, event_type="note", description="x")`.

**Then**
1. mock called: `cm.call_count == 0`.

## `PurchaseOrderManager.list_events`

### POM-LV-01 — newest first, ties by id descending, profile or None
- **Rules:** `list_events` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". OC = po "2".
2. EA = evt(O, T3). EB = evt(O, T1). EC = evt(O, T3), but `performed_by None`. ED = evt(O, T2), but `performed_by U2.id`. EX = evt(OC, T4).

**When**
- `result = M.list_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for (e, p) in result] == [EC.id, EA.id, ED.id, EB.id]`.
2. returns: `[p.id if p else None for (e, p) in result] == [None, U1.id, U2.id, U1.id]`.

### POM-LV-02 — a missing order: 404
- **Rules:** `list_events` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `M.list_events(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {MISSING} not found"`.

### POM-LV-03 — an order of W2: 404
- **Rules:** `list_events` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po of W9 "9".
2. evt(O9, T1).

**When**
- `M.list_events(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Purchase order with ID {O9.id} not found"`.

### POM-LV-04 — reads are a fixed number, not one per event
- **Rules:** `list_events` R2 [BUG-2883]
- **Kind:** bug
- **Expect:** xfail BUG-2883
- **Author:** claude
- **Fails today on:** Then 2 (today one profile read per event)

**Given**
1. O = po "1".
2. evt(O, T1); evt(O, T2), but `performed_by U2.id`; evt(O, T3), but `performed_by U4.id`; evt(O, T4), but `performed_by U5.id`; evt(O, T4), but `performed_by U3.id`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.list_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. statement: `len(selects) <= 3` (order, events, profiles; spec R2, G11).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_purchase_order` R1 [BUG-2631] | integration tests (two sessions) | two creates at once both succeed with distinct `PO-<year>-<nnn>` numbers; the year card belongs to `purchase_order.spec.md` `allocate_po_number` |
| HR-10 line, `mark_order_complete` R6, `update_purchase_order` R14, `update_item` R18, `set_approval` R7, `add_item` R7, `remove_item` R4, `sync_items` R9, `delete_purchase_order` R6, `add_approver` R7, `remove_approver` R5 [BUG-2872] | integration tests (two sessions) | the race itself: the loser waits on the row lock, then sees the new state and gets the normal wrong-state error |
| RP2 (PO), FU-4 | `PurchaseOrderService` / `PurchaseOrderResponse` | `has_open_return: bool` in the response, filled from `PurchaseOrderReturnManager.has_open_return` |
| hub R1 (filters, order, voided / money rules) | `purchase_order.spec.md` (`list_for_hub`, `count_for_hub`, `aggregate_hub_stats`, `list_recent_for_hub`, `get_pending_highlights_for_hub`) | filtering and order (BUG-2639 … 2641); here only the pass-through is checked |
| P1, P2, P3 [BUG-2877, BUG-2878, BUG-2879] | endpoints `POST /purchase-orders/`, `PUT /purchase-orders/{id}/`, `POST /purchase-orders/{id}/items/`, `PUT /purchase-orders/items/{id}/`, `POST /purchase-orders/{id}/items/sync/` | the schema refusals surface as 422 with nothing stored |
| `update_item` R3 [BUG-2887], OQ-53 | `PurchaseOrderService` receive events (`POST /purchase-orders/{id}/receive-events/`) and `PUT /purchase-orders/items/{id}/` | a `PUT` sending `quantity_received` answers 422; receiving moves stock and leaves a receive record only through receive events |
| `create_purchase_order` R4 (Q7), FU-3 | `PurchaseOrderService.create_purchase_order` | the 409 path rolls the transaction back (`except HTTPException: raise` skips it today) |
| P6 background, FU-1 [BUG-2734] | `PurchaseOrderService.void_purchase_order` | a completed or received PO cannot be voided; void leaves the confirms |
| `sync_po_stage` R1 (BUG-2810), FU-2 | `PurchaseOrderService.receive_replacements` / `purchase_order_return_manager.spec.md` | replacement receipts keep the PO `Complete` and log `return_replacement_received` once |
| Q6, FU-5 | `app/schemas/purchase_order.py` spec | `current_status_id`, `order_workflow_id` dropped from `PurchaseOrderCreate` |
| `delete_purchase_order` R5 [BUG-1195] | `DELETE /purchase-orders/{id}/` | the endpoint passes the deleter's `user_id` |
| `reopen_for_return` R2 [BUG-2789] | `PurchaseOrderService.start_return` | if the fix drops the call there instead, the stored completion stays and no `order_reopened` event is written |

## Spec gaps
None. The 13 gaps of revision 1 were closed by the describer's fill-gaps of 2026-11-21 (spec Gap log G1–G13), and G14 added the approver lock rules:

| Old gap | Closed by | What changed here |
|---|---|---|
| 1 | G1 | SYNC is `PurchaseOrderItemSyncRequest` (Conventions). |
| 2 | G2 | Labels asserted in CF-01, CF-03, CF-04, UP-20, UP-26, UP-27. |
| 3 | G3 | UP-42 (and UP-49, `null`) expect a `ValidationError` from `PurchaseOrderUpdate`. |
| 4 | G4 | Check-order cards UP-45 … UP-48, AI-14 … AI-16, CR-20; the `Item #<id>` fallback stays on EC-04 only (old data). |
| 5 | G5 | WF-05, WF-06 patch `ensure_po_workflow_record`. |
| 6 | G6 | CP-02 and CP-05 strict xfail BUG-1881; CP-06 and CS-06 pass. |
| 7 | G7 | `result is None` on UL-01, UV-01, RA-01, AP-01, RT-01, SL-01, ES-01, LF-01, DL-01, RM-01. |
| 8 | G8 | AI-12, RI-10, SY-24, DL-19 cite `add_item` R7, `remove_item` R4, `sync_items` R9, `delete_purchase_order` R6. |
| 9 | G9 | DL-13 also checks the draft invoice's `invoice_items` row. |
| 10 | G10 | DL-17 reads `metadata_json`. |
| 11 | G11 | LA-05, LV-04 bounds are now spec rules. |
| 12 | G12 | SS-06 checks the workflow is untouched; SS-09 covers the Draft target. |
| 13 | G13 | Delete cards pass `user_id` through DEL; DL-21 checks the TypeError. |
| — | G14 | AA-15, RM-10 lock cards. |

## Retired IDs
- **POM-GI-04** (Revision 4, verifier finding 1): a non-strict xfail that rested on physical row order. It XPASSed in some runs and gave no signal. GI-05 pins the ORDER BY of BUG-2637 deterministically.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_parse_unit_price` | R1 | PU-01 … PU-04 |
| `_line_subtotal` | R1 | LS-01, LS-03 |
| `_line_subtotal` | R2 [BUG-2876] | LS-02, LS-03, LS-04, LS-05 |
| `_all_items_have_positive_unit_price` | R1 | PP-01 |
| `_all_items_have_positive_unit_price` | R2 | PP-02, PP-03, PP-04 |
| `get_po_by_invoice_id` | R1 | GI-01, GI-02, GI-03 |
| `get_po_by_invoice_id` | R1 [BUG-2637] | GI-05 (GI-04 retired) |
| `is_po_financially_locked` | R1 | FL-01, FL-02, FL-03, FL-04 |
| `is_po_financially_locked` | R2 (`locked` [BUG-2735]: dead value, no card) | FL-05, FL-06, FL-07, FL-08; RP5 (PO): FL-08, AI-17 |
| `unlink_invoice_from_po` | R1 | UL-01, UL-04 |
| `unlink_invoice_from_po` | R2 | UL-01, UL-02, UL-03, UL-04 |
| `unlink_invoice_from_po` | flush only | UL-05 |
| `unconfirm_sections_after_invoice_void` | R1 | UV-01, UV-02 |
| `unconfirm_sections_after_invoice_void` | R2 | UV-01, UV-02, UV-03, UV-04 |
| `reset_approvals` | R1 | RA-01, RA-04 |
| `reset_approvals` | R2 | RA-01, RA-02, RA-03, RA-05, RA-06 |
| `_ensure_po_stage_statuses` | R1 | ES-01, ES-02, ES-03, ES-06 |
| `_ensure_po_stage_statuses` | R1 [BUG-1881] | ES-04, ES-05 |
| `_raise_po_workflow_setup_error` | R1 | WE-01, WE-02 |
| `_resolve_po_stage_status_id` | R1 | RS-01, RS-02 |
| `_resolve_po_stage_status_id` | R1 [BUG-1881] | RS-04 |
| `_resolve_po_stage_status_id` | R2 | RS-03, SS-06 |
| `_resolve_po_workflow_id` | R1 | WF-01, WF-02, WF-03, WF-04 |
| `_resolve_po_workflow_id` | R2 | WF-05, WF-06 |
| `_all_items_fully_received` | R1 | FR-01 |
| `_all_items_fully_received` | R2 | FR-02 … FR-06 |
| `_current_stage_name` | R1 | CS-01 … CS-06 |
| `_invoice_payment_status` | R1 | IP-01, IP-02, IP-03 |
| `sync_po_for_linked_invoice` | R1 | SL-01, SL-02, SL-03, SL-04 |
| `sync_po_paid` | R1 | SP-01 … SP-06 |
| `sync_po_paid` | R2 | SP-05, SP-06, SP-07 |
| `sync_po_paid` | R3 | SP-01, SP-02, SP-08, SP-09 |
| `_is_po_complete_stage` | R1 | CP-01, CP-03, CP-04, CP-06 |
| `_is_po_complete_stage` | R1a [BUG-1881] | CP-02, CP-05 |
| `_derive_po_stage_name` | R1 | DS-01, DS-02, DS-08 |
| `_derive_po_stage_name` | R2 | DS-03 |
| `_derive_po_stage_name` | R3 | DS-04, DS-05, DS-06, DS-07 |
| `_derive_po_stage_name` | R4 | DS-02, DS-07, DS-08 |
| `sync_po_stage` | R1 (BUG-2810) | SS-01, SS-03 |
| `sync_po_stage` | R2 | SS-04, SS-09 |
| `sync_po_stage` | R3 | SS-01, SS-05, SS-07 |
| `sync_po_stage` | R4 | SS-01, SS-02, SS-04, SS-06, SS-08, SS-09 |
| `sync_po_stage` | R4a | SS-06, SS-09 |
| `mark_order_complete` | R1 | MC-04, MC-05, MC-06 |
| `mark_order_complete` | R1a [BUG-2882] | MC-07 |
| `mark_order_complete` | R2 | MC-08 |
| `mark_order_complete` | R3 | MC-09, MC-10, MC-12 |
| `mark_order_complete` | R4 | MC-11, MC-12, MC-13, MC-14 |
| `mark_order_complete` | R5 | MC-01, MC-02, MC-03, MC-16 |
| `mark_order_complete` | R6 [BUG-2872] | MC-15 |
| `reopen_for_return` | R1 | RO-01 |
| `reopen_for_return` | R2 [BUG-2789] | RO-02 (xfail), RO-03, RO-04 |
| Return in progress (PO) | RP1 | RO-02, RO-03, SS-03 |
| Return in progress (PO) | RP2 | MC-13, MC-14; response field Deferred |
| Return in progress (PO) | RP5 | UP-05, UP-06, SA-07, AA-11, RM-07, SCH-21; receive events Deferred |
| Return in progress (PO) | BUG-2810 | SS-03; write side Deferred |
| `create_purchase_order` | R1 [BUG-2631] | CR-01 (format); race Deferred |
| `create_purchase_order` | R2 (Q6) | CR-01, CR-02, CR-03 |
| `create_purchase_order` | R3 [BUG-1017] | CR-09, CR-10, CR-11, CR-20 |
| `create_purchase_order` | R3 [BUG-2874] | CR-12 (pass), CR-13 … CR-17; project CR-18 |
| `create_purchase_order` | R4 (Q7) | CR-08 |
| `create_purchase_order` | R5 [BUG-2877, BUG-2878] | CR-01, CR-05, CR-07; SCH-01 … SCH-04, SCH-12 … SCH-15 |
| `create_purchase_order` | R6 | CR-01 |
| `create_purchase_order` | R7 [BUG-2876] | CR-01, CR-04, CR-05, CR-06 |
| `create_purchase_order` | R8 | CR-01 |
| `create_purchase_order` | flush only | CR-19 |
| `update_purchase_order` | R1 | UP-01, UP-02, UP-03 |
| `update_purchase_order` | R1a [BUG-2882] | UP-04, UP-47 |
| `update_purchase_order` | R1b [BUG-2885] | UP-05, UP-06, UP-48 |
| `update_purchase_order` | R2 | UP-07, UP-32 |
| `update_purchase_order` | R2 [BUG-2879] | UP-33 … UP-36, SCH-18, SCH-19 |
| `update_purchase_order` | R3 | UP-08 … UP-13, UP-51 (not locked) |
| `update_purchase_order` | R4 | UP-14, UP-15, UP-16 |
| `update_purchase_order` | R5 | UP-17, UP-18, UP-19, UP-20 |
| `update_purchase_order` | R6 | VC-01 … VC-12 |
| `update_purchase_order` | R7 | UP-13, UP-21 … UP-25, UP-51 |
| `update_purchase_order` | R8 | UP-20, UP-26, UP-27, UP-28, UP-50 |
| `update_purchase_order` | R9 | UP-20, UP-21, UP-31, UP-40 |
| `update_purchase_order` | R10 | UP-01, UP-08, VC-01 (and every refusal card) |
| `update_purchase_order` | R11 [BUG-2873] | UP-29, UP-30 (xfail), UP-31 |
| `update_purchase_order` | R12 [BUG-2874] | UP-37, UP-38, UP-39 (xfail), UP-40 |
| `update_purchase_order` | R13 [BUG-1017] | UP-41, UP-45, UP-46 |
| `update_purchase_order` | R13a [BUG-1017] | UP-42, UP-49 |
| `update_purchase_order` | R14 [BUG-2872] | UP-43 |
| `update_purchase_order` | flush only | UP-44 |
| `_format_scalar_value` | R1 … R4 | SF-01 … SF-07 |
| `_format_destination_id` | R1 | FD-01 |
| `_format_destination_id` | R2 | FD-02 … FD-13 |
| `_format_field_value` | R1 | FV-01, UP-26 |
| `_format_field_value` | R2 | FV-02, UP-27 |
| `_format_field_value` | R3 | FV-03, UP-27 |
| `_format_field_value` | R4 | FV-04, UP-20 |
| `_format_field_value` | R5 [BUG-2875] | FV-05, FV-06, FV-07, SS-07 |
| `_format_field_value` | R6 | FV-08, FV-09 |
| `_collect_field_changes` | R1 | CF-01, CF-02, CF-03, CF-04, UP-20, UP-26, UP-27 |
| `_collect_item_field_changes` | R1 | CI-01, CI-02, UI-01 |
| `_log_field_change_event` | R1 | LF-01, LF-02 |
| `_log_section_field_updates` / `_log_admin_field_updates` | R1 | UP-20, UP-26, UP-27 |
| `_confirmed_supplier_update_fields` / `_confirmed_detail_update_fields` | R1 | CU-01, CU-02, CU-03 |
| `_items_structure_confirmed` | R1 | IS-01 |
| `_base_sections_confirmed` | R1 | BS-01, BS-02 |
| `_validate_section_confirm` | R1 | VC-01, VC-02, VC-10, UP-21 |
| `_validate_section_confirm` | R2 | VC-03, VC-04, VC-05, VC-12, VC-13, VC-14, UP-22 |
| `_validate_section_confirm` | R3 | VC-06, VC-07, VC-08, UP-23 |
| `_validate_section_confirm` | R4 | VC-09, UP-13 |
| `apply_post_invoice_confirms` | R1 | AP-01, AP-03 |
| `apply_post_invoice_confirms` | R2 | AP-01, AP-02, AP-04 |
| `get_purchase_order` | R1 | GP-01 … GP-04 |
| hub pass-throughs | R1 | HUB-01 … HUB-06 |
| `delete_purchase_order` | R1 | DL-02, DL-03, DL-04 |
| `delete_purchase_order` | R2 | DL-05, DL-06, DL-08 |
| `delete_purchase_order` | R3 | DL-07, DL-08, DL-09 |
| `delete_purchase_order` | R3a [BUG-2888] | DL-11 (xfail), DL-12, DL-15, DL-16 |
| `delete_purchase_order` | R4 | DL-01, DL-09, DL-10, DL-14, DL-15, DL-16, DL-20 (all through DEL) |
| `delete_purchase_order` | R4a [BUG-2888] | DL-13 (xfail), DL-14 |
| `delete_purchase_order` | R5 [BUG-1195] | DL-17, DL-18 |
| `delete_purchase_order` | R5a [BUG-1195] | DL-21; DEL in every other delete card |
| `delete_purchase_order` | R6 [BUG-2872] | DL-19 |
| `_quantity_received_decimal` | R1 | QR-01, QR-02 |
| `_validate_ordered_vs_received` | R1 | VO-01, VO-02, VO-03, UI-13, UI-14, SY-14 |
| `_ensure_catalog_item_not_on_po` | R1 | EC-01 … EC-04, AI-10, SY-18, SY-19 |
| `add_item` | R1 | AI-05, AI-06 |
| `add_item` | R1a [BUG-2882] | AI-07, AI-16 |
| `add_item` | R2 | AI-08, AI-09, AI-17 |
| `add_item` | R7 [BUG-2872] | AI-12 |
| `add_item` | R3 [BUG-1017] | AI-10, AI-11, AI-14, AI-15 |
| `add_item` | R4 [BUG-2877, BUG-2878] | AI-01, AI-02; SCH-01 … SCH-04, SCH-12, SCH-15 |
| `add_item` | R5 | AI-01, AI-02, AI-04 |
| `add_item` | R6 | AI-01, AI-03, AI-04, AI-13 |
| `update_item` | R1 [BUG-2879] | UI-07, UI-08, UI-15, UI-16, SCH-20 |
| `update_item` | R1a [BUG-2882] | UI-09 |
| `update_item` | R2 | UI-10, UI-11, UI-12 |
| `update_item` | R3 [BUG-2887] | SCH-21, SCH-22, SCH-23 (xfail), SCH-24 |
| `update_item` | R4 | UI-13, UI-14 |
| `update_item` | R5 | UI-01, UI-02, UI-03, UI-15 |
| `update_item` | R6 | UI-01, UI-02, UI-18 |
| `update_item` | R7 [BUG-2877, BUG-2878] | SCH-05, SCH-06, SCH-16, SCH-24 |
| `update_item` | R8 | UI-01, UI-03, UI-04, UI-05 |
| `update_item` | R9 | UI-05, UI-06 |
| `update_item` | R18 [BUG-2872] | UI-17 |
| `remove_item` | R1 | RI-04, RI-05 |
| `remove_item` | R1a [BUG-2882] | RI-06 |
| `remove_item` | R2 (Q8) | RI-07, RI-08, RI-09 |
| `remove_item` | R4 [BUG-2872] | RI-10 |
| `remove_item` | R3 | RI-01, RI-02, RI-03, RI-11 |
| `sync_items` | R1 | SY-02, SY-03 |
| `sync_items` | R1a [BUG-2882] | SY-04 |
| `sync_items` | R2 | SY-05, SY-06 |
| `sync_items` | R9 [BUG-2872] | SY-24 |
| `sync_items` | R3 | SY-01, SY-07 … SY-10, SY-26 |
| `sync_items` | R4 | SY-01, SY-11 … SY-14 |
| `sync_items` | R5 | SY-01, SY-15, SY-16, SY-26 |
| `sync_items` | R6 [BUG-2877, BUG-2878] | SY-01, SY-18, SY-19, SY-20, SY-26, SY-27, SY-28; SCH-07, SCH-17 |
| `sync_items` | R7 [BUG-1017] | SY-21 |
| `sync_items` | R8 | SY-01, SY-16, SY-17, SY-22, SY-23, SY-25 |
| `get_items` | R1 | GT-01, GT-02, GT-05 |
| `get_items` | R1 [BUG-2886] | GT-03, GT-04 |
| `_recalc_totals` | R1, R1a | RT-01, RT-02, RT-03, SY-22 |
| `list_approvers` | R1 | LA-02, LA-03 |
| `list_approvers` | R2 [BUG-1200] | LA-01, LA-04 |
| `list_approvers` | R3 [BUG-2883] | LA-05 |
| `approval_summary` | R1 | AS-01, AS-02 |
| `approval_summary` | R2 [BUG-2877] | AS-01, AS-02, AS-03, AS-08, SCH-08 … SCH-11 |
| `approval_summary` | R3 [BUG-1202] | AS-04, AS-05, AS-06, AS-07 |
| `add_approver` | R1 | AA-02, AA-03 |
| `add_approver` | R2 | AA-04 … AA-07 |
| `add_approver` | R2a [BUG-2882] | AA-08 |
| `add_approver` | R3 | AA-09, AA-10 |
| `add_approver` | R4 | AA-01, AA-13, AA-14 |
| `add_approver` | R5 | AA-01 |
| `add_approver` | R6 [BUG-2881] | AA-11, AA-12 (xfail), AA-13 |
| `add_approver` | R7 [BUG-2872] | AA-15 |
| `remove_approver` | R1 | RM-03, RM-04, RM-05 |
| `remove_approver` | R1a [BUG-2882] | RM-06 |
| `remove_approver` | R2 | RM-01, RM-02, RM-09 |
| `remove_approver` | R3 | RM-01, RM-02 |
| `remove_approver` | R4 [BUG-2881] | RM-07, RM-08 |
| `remove_approver` | R5 [BUG-2872] | RM-10 |
| `set_approval` | R1 | SA-03, SA-04 |
| `set_approval` | R1a [BUG-2882] | SA-05 |
| `set_approval` | R2 | SA-06 |
| `set_approval` | R3 | SA-07 |
| `set_approval` | R4 [BUG-2881] (`locked` [BUG-2735]: dead, no card) | SA-08 (xfail), SA-09 |
| `set_approval` | R5 | SA-01, SA-02, SA-09, SA-13 |
| `set_approval` | R6 [BUG-2880] | SA-10, SA-11 |
| `set_approval` | R7 [BUG-2872] | SA-12 |
| `log_event` | R1 | LE-01, LE-02, LE-05 |
| `log_event` | R2 [BUG-1192] | LE-03, LE-04 |
| `list_events` | R1 | LV-02, LV-03 |
| `list_events` | R2 [BUG-2883] | LV-01, LV-04 |
| Q1 [BUG-2884] | superseded by BUG-2887 | SCH-21 … SCH-23 |
| Overview | Check order after the fixes (G4) | UP-45, UP-46, UP-47, UP-48, AI-14, AI-15, AI-16, CR-20, EC-04 |
| Overview | Return values (G7) | UL-01, UV-01, RA-01, AP-01, RT-01, SL-01, ES-01, LF-01, DL-01, RM-01 |
