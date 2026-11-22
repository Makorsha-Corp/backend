# Test cases — `app/services/sales_service.py`

> **Spec:** `tests/unit/services/sales_service.spec.md` (source commit e48a092; APPROVED 2026-11-22)
> **Status:** READY
> **Counts:** 352 cases · 219 expected-to-pass · 133 expected-to-fail (bugs; 132 strict, 1 non-strict) · 12 deferred
> **Revision:** 4b (2026-11-22) — DISCREPANCY-5: DD-08, DD-09, SR-53 … SR-58 and the Invoice payment manager calls convention now roll the savepoint back unless it has already been rolled back or committed, not `if sp.is_active` (after a failed flush `is_active` is False but the savepoint stays open and the session refuses queries until `sp.rollback()`). No card added or removed; counts unchanged.
> **Revision:** 4a (2026-11-22) — spec Gap log G19, G20 close Revision 4's Spec gaps 1 and 2. G19 (RK4a): `quantity_delivered 0.00` under a pending return is unreachable, so SS-RK-23 is dropped (Retired IDs) and removed from the RK4 coverage row. G20 (RC3a, A7a, BUG-3220): a line name is trimmed and an empty name (`None`, `""`, spaces) gives `Item <item_id>` for a catalog line, else `Line <line_number>`; SS-A-03 now expects `Line 1` (strict xfail BUG-3220); new SS-RS-26 (free-text `""` → `Line 1`) and SS-RS-27 (free-text `"  Crate  "` → `Crate`, `"   "` → `Line <n>`), both strict xfail BUG-3220. SS-RS-25 stays a pass card (RC3a keeps `Item <item_id>` for a catalog line). Retired: SS-RK-23.
> **Revision:** 4 (2026-11-22) — verifier findings 1–5 (`sales_service.verify.md`, NEEDS WORK). (1) TC3: every write-method card with X (31 cards) checks **X not in db** right after the raise, before any re-read or test rollback; one passing error card per write method (I-06, F-02, C-03, U-27, DC-02, DV-08, DX-04, DU-04, FS-03, RS-07, RK-12, RV-04, MC-03, SC-05, AA-02, AR-02, AP-02; never the failing-commit card) also runs inside **spies** and checks `rb.call_count >= 1`; U-12, DX-02, DU-02, FS-03, RS-19, RV-11 now cite TC3. (2) New RK-22: a second refund return adds to `quantity_returned` / `quantity_refunded` 1.00 → 2.00. (3) New RK-23: `quantity_delivered 0.00` (invalid data) → −1.00 per RK4 as written; whether that state is intended is Spec gaps 1. (4) New RS-24: a 0.00-priced return line gives a 0.00 credit-note line. (5) New RS-25: the `Item <item_id>` fallback for an empty name (catalog item with name `""`, no line description); the free-text-with-empty-description variant is Spec gaps 2. DD-08 / DD-09 and the **Invoice payment manager calls** convention now read "roll the savepoint back unless it is already closed". No ID retired.
> **Revision:** 3 (2026-11-22) — executor discrepancies, spec Gap log G14–G18. G14: C2 is BUG-3219, not BUG-124 (C-02, C-03, coverage). G15: A-01 reads `items_updated_at` after a test-level commit. G16: list order is `id` ascending only after BUG-100 / 2443 / 2442 / 1270 / 1271 / 2425; isolation cards L-01, LD-01 … LD-03, GD-01, GI-01, GDI-01, RS-02 and L-06 now compare sets (or key by id); the paging cards L-02, L-03, LD-05, LD-06 become strict xfail with the new **id order on T** SQL check as the deterministic failure; new order cards L-07, LD-09, GD-04, GI-03, GDI-03, RS-23 (xfail) and paging companions L-08, L-09, LD-10, LD-11 (pass); L-04 keeps only the count. G17: OR-03 is a plain pass. G18: DD-08 and SC-06 become xfail BUG-639 with pass companions DD-09, SC-08 (refused, any error type, everything kept). Cross-cutting `X in db.new` fix: no card here used it (X is checked with `db.get`, **x_kept** / **x_gone**), so nothing changed. No ID retired.
> **Revision 2** (2026-11-22) — spec fill-gaps G1–G13 (Gap log). Messages are `ActionMessage` (`type`, `message`, `details`); amounts in texts are plain two-place `str()`; SR7's `paid_amount` detail is text (SR-20). New BUG-3218 (F6a, RC1a): F-11 and RS-16 keep only what holds today and after the fix; new xfail F-15, F-16, RS-19, RS-20. Lock cards now require a plain `FOR UPDATE` (spec Row locks table; single-table reads); new SR1a lock cards SR-51, SR-52. SR1b: SR-13 now expects the voided-note warning (xfail) with pass companion SR-37 and SR-40, SR-42. SR1c: SR-15, SR-16 now expect the id-free `could not be found` warning (xfail) with pass companions SR-38, SR-39 and SR-41, SR-43. SR3a trail (audit row, `payment_recorded`, `allow_payments` exception): SR-44 … SR-47. SR3c link: SR-48, SR-49. SR3b zero note: SR-50. SR8a no edit / no delete (400): SR-53 … SR-56. SR8c reserved method: SR-57, SR-58. SR8b void: SR-59. Manager refusal texts (G8) added to DV-13, DU-04, MC-03, AA-02, AA-03, AP-02. RS7 sent quantities (G9): RS-21, RS-22. PS5 (G10): PS-07. Imports, `SalesDeliveryCreate` and `DeliveryMethod` (G11) in Conventions. No `Author: claude` card depended on a closed gap, so all six stay (they patch or spy, which the spec does not replace). No ID retired.

## Reviewer summary
- **Per callable:** order response 5 (4 bug) · notifications 4 (4 bug) · `_attach_receivable_invoice_to_sales_order` 18 (7 bug) · `_delete_linked_draft_invoice_for_so` 9 (2) · `_sync_draft_invoice_for_so` 10 · `create_invoice_for_sales_order` 13 (6) · `finalize_sales_order_invoice` 16 (4) · `create_sales_order_from_dict` 6 (1) · `get_sales_order` 6 (3) · `get_sales_orders` 9 (3) · `_attach_invoice_payment_status` 7 (2) · `update_sales_order` 29 (21) · `create_delivery` 5 · `complete_delivery` 15 (5) · `cancel_delivery` 5 · `update_delivery` 5 · `fulfill_service_item` 9 · `_settle_replacement_credit_notes` 59 (36) · `get_deliveries_for_order` 4 (3) · `get_sales_order_items` 3 (2) · `get_delivery` 4 (2) · `get_deliveries` 11 (3) · `get_delivery_items` 3 (2) · `_attach_return_invoice_for_so` 1 (+ 11 RC cards through `start_return`) · `start_return` 27 (9) · `complete_return` 22 (6) · `void_return` 15 (6) · `list_returns` 2 (1) · `get_return` 2 · `mark_order_complete` 4 · `set_section_confirm` 8 (1) · approvers / events 16.
- **Depth:** full (skill step 1a). The service drafts, confirms, deletes and voids invoices, creates and settles credit notes, moves stock on returns and deliveries, and changes order workflow state.
- **Transaction contract:** every public write has a commit card (`committed:` after a test-level rollback, `loaded(result)`), at least one rollback card with an **uncommitted** extra workspace X that must be gone (checked as **X not in db** right after the raise, before any test rollback; one passing error card per write method also spies `rb.call_count >= 1`, Revision 4), and a failing-commit card; TC5 once (C-04). Every read has a spies card (no commit, no rollback, X still there) and, where it can raise, a no-rollback card on its error. The five flush-only helpers (A, DD, Y, RC, SR) each get a helper-spies card (no commit, no rollback).
- **OQ-64 / BUG-3217 (SR1–SR9)** is designed in depth (section `_settle_replacement_credit_notes`, 59 cards): exact payment entry (method, amount, UTC date, actor, delivery or line link, notes, `source_type` / `source_id` link to the settlement event), the normal payment trail (financial audit row, `payment_recorded` invoice event, `allow_payments` lock not applied), paid credit note and return, order event, messages after DV4 / FS7, ledger rows (one `sale` row, none for the settlement), half-up amount, partial redelivery, two-line and two-return cases, the cap (an active payment → warning, nothing written; a voided payment → full settlement), a voided credit note (SR1b warning) and an already refunded one (SR7 warning), W0 / W2 credit notes (SR1c id-free warning, never locked), draft and 0.00 notes, W0 / W2 return rows, warnings repeated on the next delivery, the credit note locked before its payments are read and in return id order, the entry neither deletable nor editable (400) and the method refused by hand, voiding it (owed again, return unpaid), a voided entry reconsidered, an active one never doubled, failure undoes the delivery, no notification, direct fulfilment.
- **Notable design choices:**
  - Lock cards (BUG-3192 ×2, BUG-2764 ×2, BUG-3217 SR1a ×2) check the SQL against the spec's Row locks table: every lock here is a single-table read with a plain `FOR UPDATE` (no `OF`, no `SKIP LOCKED` / `NOWAIT`). The credit-note lock is found by its parameters (`cnlock`), since the order's own invoice is also read. Concurrency itself is deferred to integration tests.
  - Negative settlement cards (nothing settles) are **pass** cards: they hold today and must keep holding after the fix; the positive xfail cards catch a helper that does nothing.
  - `Author: claude`: A-08, RS-06 (spy on `create_invoice` arguments, BUG-627), A-15, A-16 (forced `create_invoice` errors), A-07b (non-strict order), SR-31 (forced settlement failure).
  - Invoices, lines and returns of W0 / W2 linked to W1 rows are invalid data built on purpose (HR-16).
  - "Cap at the outstanding amount": SR3 settles the credit note's full `invoice_amount` only when it has no active payment; any active payment gives the SR7 warning and writes nothing. So the cap is tested as "voided payment → full 3000.00" (SR-24) and "1000.00 / 3000.00 already refunded → warning, nothing written" (SR-20 … SR-23). Sales settles only once every replaced unit is back out (SR2), so a partial redelivery settles nothing (SR-08), unlike the PO twin.
  - SR8a / SR8c refusals live in the invoice payment manager; SR-53 … SR-58 reach them from the settlement side through `ipm` (inside a savepoint), the cash-payment side stays in `invoice_payment_manager.cases.md` (Deferred). SR-25 / SR-26 cover an active entry never doubled and a voided one reconsidered.
  - BUG-3218 changes RS-16's status (404 → 422), so its pass card asserts only `HTTPException`, nothing written and the foreign account untouched; the status and text are in RS-19 / RS-20. F6a keeps 404, so F-11 keeps the status.
  - SR-44 does not assert `performed_at` or the audit `description` (not given by the spec); `changes` money is compared numerically as in `invoice_payment_manager.cases.md`.
  - OR1 for `create_sales_order_from_dict` and `update_sales_order` cannot fail today in a single call (a new order has no invoice; an edit changes no invoice), so its xfail cards are on create invoice and complete delivery; fulfil already answers the status today (G17), so SS-OR-03 is a pass card.
  - List order (G16): a card whose point is isolation or content compares sets; a card whose point is order or paging is strict xfail on the list's order bug, with **id order on T** (the SQL has an `ORDER BY T.id`) as its first Then, so it fails today every time even when the unordered rows happen to come back in insertion order. Each paging xfail has a pass companion that checks only the page size and that every row is of this workspace.
  - BUG-639 (G18): today a draft with payment history is not refused with 400 but hits an `IntegrityError` on delete; the 400 cards are xfail, and their pass companions accept any error and check that nothing changed.
- **Needs a decision:** none. Revision 4's Spec gaps 1 and 2 are closed by the spec's Gap log G19 (RK4a) and G20 (RC3a, A7a, BUG-3220).

## Conventions for this module

**IDs.** `SS` = `app/services/sales_service.py`. `OR` order response · `N` notifications · `A` _attach_receivable_invoice_to_sales_order · `DD` _delete_linked_draft_invoice_for_so · `Y` _sync_draft_invoice_for_so · `I` create_invoice_for_sales_order · `F` finalize_sales_order_invoice · `C` create_sales_order_from_dict · `G` get_sales_order · `L` get_sales_orders · `PS` _attach_invoice_payment_status · `U` update_sales_order (incl. `SalesOrderUpdate` schema) · `DC` create_delivery · `DV` complete_delivery · `DX` cancel_delivery · `DU` update_delivery · `FS` fulfill_service_item · `SR` _settle_replacement_credit_notes · `GD` get_deliveries_for_order · `GI` get_sales_order_items · `GV` get_delivery · `LD` get_deliveries · `GDI` get_delivery_items · `RC` _attach_return_invoice_for_so · `RS` start_return · `RK` complete_return · `RV` void_return (incl. `SalesOrderReturnVoidRequest` schema) · `RL` list_returns · `RG` get_return · `MC` mark_order_complete · `SC` set_section_confirm · `AL` list_approvers · `AS` approval_summary · `AA` add_approver · `AR` remove_approver · `AP` set_approval · `EV` list_events.

**Imports.** `svc` = `sales_service` (`from app.services.sales_service import SalesService, sales_service`). Models from `app.models.<snake_case>`: `SalesOrder`, `SalesOrderItem`, `SalesOrderApprover`, `SalesOrderEvent`, `SalesDelivery`, `SalesDeliveryItem`, `SalesOrderReturn`, `SalesOrderReturnItem`, `AccountInvoice`, `InvoiceItem`, `InvoiceEvent`, `InvoicePayment`, `Account`, `Factory`, `Item`, `Product`, `ProductLedger`, `Workspace`, `WorkspaceMember`, `Notification`, `Status`, `DeliveryMethod` (`app.models.delivery_method`), `FinancialAuditLog` (`app.models.financial_audit_log`). Schemas: `SalesOrderUpdate` (`app.schemas.sales_order`); `SalesDeliveryCreate`, `SalesDeliveryEditRequest` (`app.schemas.sales_delivery`; `SalesDeliveryCreate` requires `sales_order_id` and `delivery_method_id`, the rest optional); `SalesOrderReturnCreate`, `SalesOrderReturnItemCreate`, `SalesOrderReturnVoidRequest` (`app.schemas.sales_order_return`); `InvoicePaymentCreate`, `InvoicePaymentUpdate` (`app.schemas.invoice_payment`, as in `invoice_payment_manager.cases.md`). `ipm` = `invoice_payment_manager` (`app.managers.invoice_payment_manager`). `NotFoundError` = `app.core.exceptions.NotFoundError`. `RM` = `app.services.sales_service.sales_order_return_manager`. `HTTPException` (fastapi), `pydantic.ValidationError`, `inspect`, `select`, `func`, `text` (sqlalchemy), `patch` (unittest.mock), `Decimal`, `date`, `datetime`, `uuid`, `re`. Every call: `db` first, the rest by keyword. `result` = what the When returns. For `complete_delivery` / `fulfill_service_item`: `order, msgs = result`.

**Fixed values.** MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. T0 = `datetime(2026, 9, 1, 8, 0)`, T1 = `datetime(2026, 9, 2, 9, 0)`, T2 = `datetime(2026, 9, 3, 10, 0)`. **NOW** = `datetime(2026, 9, 27, 12, 0, 0)`; **UTCDAY** = `date(2026, 9, 27)`. Long dashes are U+2014; copy them. NF(i) = `f"Sales order with ID {i} not found"`. DNF(i) = `f"Delivery with ID {i} not found"`. RNF(i) = `f"Return with ID {i} not found"`. NOACCT = `"Cannot create invoice: customer account was not found in this workspace"`. NOINV = `"Cannot create invoice: invoicing is disabled for this account"`. PAYHIST = `"Invoice has payment history — confirm and void it instead"`. NEEDCONF = `"Confirm order info and items before creating the invoice"`. INFOLOCK = `"Unconfirm order info before editing it"`. FINV404 = `"The order's invoice was not found in this workspace"`. NOACCTCN = `"Cannot create credit note: customer account was not found in this workspace"`. VOIDCN(R) = `f"Return {R.return_number}: the credit note is voided — no settlement recorded"`. LOSTCN(R) = `f"Return {R.return_number}: the credit note could not be found — no settlement recorded"`. NODEL = `"A settlement by replacement cannot be deleted or edited — void it with a reason instead"`. RESERVED = `'"settled_by_replacement" is recorded by the system and cannot be entered by hand'`. Amounts in texts are `str()` of the two-place Decimal (`3000.00`, `0.13`), no grouping, no currency sign.

**Time.** In every test `app.services.sales_service.utcnow` is patched to return NOW, with the tz-awareness of the real `app.utils.time.utcnow`. Nothing else is mocked unless a card says so.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)`: `"Alice Rahman"`, `"Bob Karim"`, `"Chitra Das"`, `"Dev Paul"`, `"Esha Roy"`.
2. `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…)`: U1, U2, U3 in W1 `"active"`; U4 in W1 `"inactive"`; U5 in **W2 only** `"active"`. U1 creates every Given row; **U2 acts**; `CU` = the U2 profile object (passed as `current_user`).
3. ST = the `statuses` row with id 10 (created if missing). For W0, W1, W2 (suffix `0`, `1`, `9`): Ak = `Account(workspace_id=…, name=…, is_active=True, is_deleted=False, allow_invoices=True)` named `"Zeta West"`, `"Acme Traders"`, `"Xeno Foreign"`, each tagged `client` (an `account_tags` row of that workspace with `tag_code "client"`, `is_active True`, and its `account_tag_assignments` row); Fk = `Factory(workspace_id=…, name="Main Plant", abbreviation=f"MP{k}", is_active=True, is_deleted=False)`.
4. W1: I1 = `Item(workspace_id=W1.id, name="Chair", name_normalized="chair", unit="pcs", is_active=True)`; IS = the same with `"Installation"`, `"installation"`, unit `"hour"`. P1 = `Product(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, qty=100, is_available_for_sale=True, avg_cost=Decimal("1500.00"), created_by=U1.id)`. DM1 = `DeliveryMethod(workspace_id=W1.id, name="Courier")` (`is_active True`, `is_deleted False` by default).

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly.
- **so "n"** = `SalesOrder(workspace_id=W1.id, sales_order_number=f"SO-{TAG}-n", account_id=A1.id, factory_id=F1.id, current_status_id=10, order_date=date(2026, 9, 1), contact_name="Rahim", total_amount=Decimal("12000.00"), created_by=U1.id)`; every flag `False`; `invoice_id`, `required_approvals`, `contact_phone`, `description`, `expected_delivery_date`, `completed_at`, `completed_by`, `updated_by`, `items_updated_at` NULL. **ready** = `order_info_confirmed True`, `items_confirmed True`. **finalized** = ready, `invoice_confirmed True`, `is_invoiced True`. **completed** = `order_completed True`, `completed_at T0`, `completed_by U1.id`. **of W0** / **of W2** = `workspace_id` W0 / W2, `account_id` A0 / A9, `factory_id` F0 / F9.
- **ln(S)** = `SalesOrderItem(workspace_id=S.workspace_id, sales_order_id=S.id, item_id=I1.id, description=None, quantity_ordered=Decimal("4.00"), quantity_delivered=Decimal("4.00"), quantity_returned=Decimal("0.00"), quantity_refunded=Decimal("0.00"), unit_price=Decimal("3000.00"), line_total=Decimal("12000.00"), requires_delivery=True)`. **free "D"** = `item_id None`, `description "D"`. **service** = `item_id IS.id`, `requires_delivery False`.
- **inv(S)** = `AccountInvoice(workspace_id=S.workspace_id, account_id=S.account_id, invoice_type="receivable", invoice_status="draft", payment_status="unpaid", invoice_amount=Decimal("0.00"), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 1), allow_payments=True, created_by=U1.id, order_type="sales_order", order_id=S.id)`. **confirmed** = `invoice_status "confirmed"`, `invoice_amount Decimal("12000.00")`. **voided-inv** = `invoice_status "voided"`, `void_note "dup"`. **of W0** / **of W2** = `workspace_id` W0 / W2, `account_id` A0 / A9. **linked** = after its flush, `S.invoice_id = V.id`, then `db.flush()`.
- **cn(S, a)** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal(a), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 1), allow_payments=True, created_by=U1.id, order_type="sales_order", order_id=S.id)` (a return credit note). Modifiers voided-inv, of W0 / of W2 as for inv; **draft** = `invoice_status "draft"`.
- **invl(V, k, s)** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=k, description="Old line", quantity=Decimal("1"), unit_price=Decimal(s), line_subtotal=Decimal(s), created_by=U1.id)`.
- **ret(S, "n")** = `SalesOrderReturn(workspace_id=S.workspace_id, sales_order_id=S.id, return_number=f"SR-{TAG}-n", return_type="replace", reason="Broken", created_by=U1.id)`; `status` `"pending"`, `paid` `False` (defaults), `invoice_id` NULL. **refund** = `return_type "refund"`. **done** = `status "completed"`, `completed_at T0`, `completed_by U1.id`. **voided** = `status "voided"`. **of C** = `invoice_id C.id`. **of W0** / **of W2** = `workspace_id` W0 / W2.
- **rl(R, L, q)** = `SalesOrderReturnItem(workspace_id=R.workspace_id, return_id=R.id, so_item_id=L.id, item_id=L.item_id, quantity_returned=Decimal(q), unit_price=L.unit_price)`.
- **dlv(S, "n")** = `SalesDelivery(workspace_id=S.workspace_id, sales_order_id=S.id, delivery_number=f"DEL-{TAG}-n", delivery_status="planned", delivery_method_id=DM1.id, created_by=U1.id)`. **delivered** = `delivery_status "delivered"`. **dl(D, L, q)** = `SalesDeliveryItem(workspace_id=D.workspace_id, delivery_id=D.id, sales_order_item_id=L.id, item_id=L.item_id, quantity_delivered=Decimal(q))`.
- **pay(V, a)** = `InvoicePayment(workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(a), payment_date=date(2026, 9, 2), payment_method="cash", is_voided=False, created_by=U1.id)`. **voided pay** = `is_voided True`, `voided_at T0`, `voided_by U1.id`, `void_note "manual void"`. **settle pay** = `payment_method "settled_by_replacement"`. A card that adds a pay row also sets the invoice's `paid_amount` / `payment_status` as it states.
- **appr(S, U)** = `SalesOrderApprover(workspace_id=S.workspace_id, sales_order_id=S.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=T0)`. **approved** = `approved True`, `approved_at T1`.
- **ev(S, t)** = `SalesOrderEvent(workspace_id=S.workspace_id, sales_order_id=S.id, event_type="note", description="n", performed_by=U1.id, created_at=t)`.
- **SCENE** (the replacement scene) = these rows, in this order: (1) S = so "1", but finalized, completed; (2) VR = inv(S), but confirmed, linked; (3) L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`; (4) CN = cn(S, "3000.00"); invl(CN, 1, "3000.00"); (5) R1 = ret(S, "1"), but done, of CN; rl(R1, L1, "1.00"); (6) D1 = dlv(S, "1"); dl(D1, L1, "1.00"). **SCENE-CALL** = `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture); snapshots for `unchanged` / `nothing written` and **MAXLED** = the highest `product_ledger.id` are taken here. **X** (only where listed, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(type(R), R.id)`. **unchanged(R)** = after re-read, every column of R equals its commit-point snapshot. **gone(R)** = after `db.expire_all()`, `db.get(type(R), R.id) is None`. **x_gone** = `db.get(Workspace, X_ID) is None`. **x_kept** = `db.get(Workspace, X_ID) is not None`. **X not in db** (TC3, Revision 4) = the `session:` line every refusal card of a write method with X carries right after the raise, before any re-read and before the test's own rollback; `x_gone` runs after that rollback and alone cannot show the service rolled back. One passing error card per write method (not its failing-commit card, whose rollback comes from `BaseService._commit_transaction`) also runs inside **spies** and checks `rb.call_count >= 1`: SS-I-06, SS-F-02, SS-C-03, SS-U-27, SS-DC-02, SS-DV-08, SS-DX-04, SS-DU-04, SS-FS-03, SS-RS-07, SS-RK-12, SS-RV-04, SS-MC-03, SS-SC-05, SS-AA-02, SS-AR-02, SS-AP-02.
- **EV(S)** = after `db.expire_all()`, S's `sales_order_events` by `id`; **types(S)** = their `event_type` list; metadata is `metadata_json`. **itypes(V)** = `event_type` list of V's `invoice_events` by id. **LINES(V)** = V's `invoice_items` by `line_number`. **PAYS(V)** = V's `invoice_payments` by id; **SETTLE(V)** = those with `payment_method == "settled_by_replacement"`. **AUD(pid)** = `FinancialAuditLog` rows with `entity_type == "payment"` and `entity_id == pid`, by id (money inside `changes` compared numerically, `Decimal(str(v))`). **NEWLED** = `product_ledger` rows with `id > MAXLED`, by id. All after `db.expire_all()`; V or S may be a row or its id.
- **notes()** = after `db.expire_all()`, all `Notification` rows by id.
- **nothing written** = the row counts (all workspaces) of `sales_orders`, `sales_order_items`, `sales_order_approvers`, `sales_order_events`, `sales_deliveries`, `sales_delivery_items`, `sales_order_returns`, `sales_order_return_items`, `account_invoices`, `invoice_items`, `invoice_events`, `invoice_payments`, `products`, `product_ledger`, `notifications` equal their commit-point values.
- **session clean** = right after the call, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted` (three asserts).
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; runs before any attribute of `r` is read.
- **MSG(kind, text)** = one entry of `msgs` (an `ActionMessage`) with `m.type == kind` (a `str` enum, so `"success"`, `"info"`, `"warning"` compare directly) and `m.message == text`; "its details" are `m.details` (a dict, or `None` when the rule names none); `timestamp` is never asserted. **MSGD(kind, text, d)** = the same, and `m.details == d`. `msgs == [M1, M2, …]` compares type and message of each entry in order. Warnings of the settlement (SR1b, SR1c, SR7) are entries with `type == "warning"`, after the success and info messages.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself); `exc.value.status_code` / `exc.value.detail` compared with `==`. A `schema` card wraps only building the schema.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`.
- **Statement recorder** = an `after_cursor_execute` listener records every SQL statement sent during the When only, with its parameters (indexes count from 0 in send order). **first(T)** = the first recorded SELECT whose `FROM` names table T. **row lock on T** = first(T) is not None, names no table but T in its `FROM` (no `JOIN`), its text (trailing spaces stripped) ends with a plain `FOR UPDATE` (regex `FOR UPDATE$`: every lock here is a single-table read, spec Row locks table), and it contains neither `SKIP LOCKED` nor `NOWAIT`. **cnlock(V)** = the index of the first recorded SELECT whose `FROM` names only `account_invoices`, whose text (stripped) ends with a plain `FOR UPDATE` (no `OF`, no `SKIP LOCKED`, no `NOWAIT`) and whose parameter values (flattened) include `V.id`; None when there is none. **payread(V)** = the index of the first recorded SELECT whose `FROM` names `invoice_payments` and whose parameter values include `V.id`; None when there is none. A recorder card ends its Given with `db.expunge_all()` after the commit point; ids come from values taken before.
- **id order on T** = at least one recorded SELECT whose `FROM` names T has an `ORDER BY` whose first key is `T.id` ascending (regex `ORDER BY <T>\.id\b(?!\s+DESC)`, T the table name). Used only in the list-order xfail cards (G16): today these reads have no `ORDER BY T.id`, so the check fails every time.
- **idset(r)** = `{o.id for o in r}`; set compares are used where order is not the point (G16).
- **HOR(S)** = `RM.has_open_return(db, sales_order_id=S.id, workspace_id=W1.id)`, a read used only in Then lines.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")` unless the card says non-strict. Write the call and checks as shown, also when a parameter, method or behaviour does not exist yet.

**Forced errors** (`Author: claude` cards only): A-15 / A-16 patch `app.services.sales_service.SalesService.account_invoice_manager`'s `create_invoice` (via `patch.object(svc.account_invoice_manager, "create_invoice", side_effect=…)`); A-08 / RS-06 wrap it (`wraps=`) to read its keyword arguments; SR-31 patches `SalesService._settle_replacement_credit_notes` with `side_effect=RuntimeError("settle")`.

**Invoice payment manager calls** (SR-53 … SR-59). `ipm` never commits. A call that must raise opens `sp = db.begin_nested()` first; after the `raises:` block, roll the savepoint back unless it has already been rolled back or committed (`sp.rollback()`; do **not** guard it with `if sp.is_active` — after a failed flush `sp.is_active` is False but the savepoint is not closed, and the session refuses every query until `sp.rollback()` is called); the Then's re-reads run after that.

**Race simulations.** None. Concurrency is integration-only; lock cards check the emitted SQL.

## Shared: Order response (OR)

### SS-OR-01 — "Create invoice" answers the new draft's payment status
- **Rules:** OR1 [BUG-3212]
- **Kind:** bug
- **Expect:** xfail BUG-3212
- **Fails today on:** Then 2 (the attribute is attached before the invoice exists: None)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. returns: `getattr(result, "invoice_payment_status", None) == "unpaid"`.

### SS-OR-02 — "Complete delivery" answers the order's payment status, read after the commit
- **Rules:** OR1 [BUG-3212]; DV5
- **Kind:** bug
- **Expect:** xfail BUG-3212
- **Fails today on:** Then 2 (complete_delivery attaches nothing)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "4.00").
5. `db.expire_all()` (after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `getattr(order, "invoice_payment_status", None) == "unpaid"`.

### SS-OR-03 — "Fulfil line" answers the order's payment status
- **Rules:** OR1 (fulfil part, already true today; spec Gap log G17)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.
4. `db.expire_all()` (after the commit point).

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `getattr(order, "invoice_payment_status", None) == "unpaid"`.

### SS-OR-04 — an order with a pending return says so
- **Rules:** OR2 [BUG-2790]; OR3
- **Kind:** bug
- **Expect:** xfail BUG-2790
- **Fails today on:** Then 2 (the attribute does not exist)

**Given**
1. S = so "1", but finalized, completed.
2. L1 = ln(S).
3. R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `result = svc.get_sales_order(db, order_id=S.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S.id`.
2. returns: `getattr(result, "has_open_return", None) is True`.
3. re-read S: `order_completed is True`.

### SS-OR-05 — only a pending return counts as open
- **Rules:** OR2 [BUG-2790]
- **Kind:** bug
- **Expect:** xfail BUG-2790
- **Fails today on:** Then 2 (the attribute does not exist)

**Given**
1. S = so "1", but finalized, completed.
2. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. R1 = ret(S, "1"), but done; rl(R1, L1, "1.00").
4. R2 = ret(S, "2"), but voided.

**When**
- `result = svc.get_sales_order(db, order_id=S.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S.id`.
2. returns: `getattr(result, "has_open_return", None) is False`.

## Shared: Notifications (N) — BUG-1205

### SS-N-01 — adding an approver notifies the new approver
- **Rules:** N1 [BUG-1205]; AA2
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 2 (no notification row is written)

**Given**
1. S = so "1".

**When**
- `result = svc.add_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U3.id`.
2. committed: at least one row of `notes()` has `recipient_user_id == U3.id`, `entity_type == "sales_order"`, `entity_id == S.id`.

### SS-N-02 — confirming the last section notifies (section and draft)
- **Rules:** N2, N3 [BUG-1205]; SC4
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 2 (no notification row is written)

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.
3. appr(S, U3).

**When**
- `result = svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=True)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: `len([n for n in notes() if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1`.

### SS-N-03 — finalizing the invoice notifies
- **Rules:** N4 [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 2 (no notification row is written)

**Given**
1. S = so "1", but ready.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. appr(S, U1), but approved.
4. appr(S, U3), but approved.

**When**
- `result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: `len([n for n in notes() if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1`.

### SS-N-04 — "Create invoice" by hand notifies the draft
- **Rules:** N3 [BUG-1205]; I4
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 2 (no notification row is written)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.
3. appr(S, U3).

**When**
- `result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: `len([n for n in notes() if n.entity_type == "sales_order" and n.entity_id == S.id]) >= 1`.

## `SalesService._attach_receivable_invoice_to_sales_order`

### SS-A-01 — the draft is created with its fields, linked and flushed, not committed
- **Rules:** A4, A6, A8, A9
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready, `description "Blue chairs"`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed (A8, Gap log G15; the first Then that touches the database, before any `expire_all`): `db.commit()` (a savepoint release under the `db` fixture, outside **spies**), then re-read S: `invoice_id is not None`, `is_invoiced is True`, `items_updated_at == NOW`.
5. re-read V = `db.get(AccountInvoice, S.invoice_id)`: `workspace_id == W1.id`, `account_id == A1.id`, `invoice_type == "receivable"`, `invoice_status == "draft"`, `order_type == "sales_order"`, `order_id == S.id`.
6. re-read V: `description == f"Auto-created from sales order SO-{TAG}-1"`, `notes == "Blue chairs"`, `due_date is None`, `allow_payments is True`, `payment_locked_reason is None`.
7. re-read V: `invoice_number is None`, `vendor_invoice_number is None`.
8. re-read V: `invoice_amount == Decimal("12000.00")`.
9. count: `itypes(V).count("items_synced") == 1`.
10. count: `"created" in itypes(V)`.
11. count: S has exactly 0 `sales_order_events` rows.
12. count: `notes() == []`.

### SS-A-02 — each order line becomes one invoice line with the copied values
- **Rules:** A7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. L1 = ln(S), but `quantity_delivered 0.00`, `line_total 11999.99`.
3. L2 = ln(S), but free "Ribbon", `quantity_ordered 0.50`, `quantity_delivered 0.00`, `unit_price 0.25`, `line_total 0.13`.
4. L3 = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `len(LINES(S.invoice_id)) == 3`; `sorted(l.line_number for l in LINES(S.invoice_id)) == [1, 2, 3]`.
2. re-read the line with `source_order_item_id == L1.id`: `description == "Chair"`, `item_id == I1.id`, `source_order_item_type == "so_item"`, `quantity == Decimal("4.00")`, `unit == "pcs"`, `unit_price == Decimal("3000.00")`, `line_subtotal == Decimal("11999.99")`.
3. re-read the line with `source_order_item_id == L2.id`: `description == "Ribbon"`, `item_id is None`, `quantity == Decimal("0.50")`, `unit is None`, `unit_price == Decimal("0.25")`, `line_subtotal == Decimal("0.13")`.
4. re-read the line with `source_order_item_id == L3.id`: `description == "Installation"`, `item_id == IS.id`, `unit == "hour"`, `line_subtotal == Decimal("1000.00")`.
5. re-read the invoice: `invoice_amount == Decimal("13000.12")`.

### SS-A-03 — a free-text line with an empty description is named `Line 1`, never "Item None"
- **Rules:** A7, A7a [BUG-3220]
- **Kind:** bug
- **Expect:** xfail BUG-3220
- **Fails today on:** Then 2 (today `item_name or f"Item {item_id}"` gives `"Item None"`)

**Given**
1. S = so "1", but ready.
2. L1 = ln(S), but free "", `quantity_delivered 0.00` (stored directly: the item schema refuses a blank free-text description, the database allows it).

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `len(LINES(S.invoice_id)) == 1`.
2. re-read that line: `line_number == 1`, `description == "Line 1"`, `"None" not in description`, `item_id is None`, `source_order_item_id == L1.id`.

### SS-A-04 — a W2 line row under the order is not copied
- **Rules:** A7 [BUG-3193]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3193
- **Fails today on:** Then 2 (the relationship copies the W2 row too: 2 lines)

**Given**
1. S = so "1", but ready.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. L9 = ln(S), but `workspace_id W2.id`, `quantity_delivered 0.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read S: `invoice_id is not None`.
2. count: `[l.source_order_item_id for l in LINES(S.invoice_id)] == [L1.id]`.

### SS-A-05 — a W0 line row under the order is not copied
- **Rules:** A7 [BUG-3193]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3193
- **Fails today on:** Then 2 (the W0 row is copied too)

**Given**
1. S = so "1", but ready.
2. L0 = ln(S), but `workspace_id W0.id`, `quantity_delivered 0.00`.
3. L1 = ln(S), but `quantity_delivered 0.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read S: `invoice_id is not None`.
2. count: `[l.source_order_item_id for l in LINES(S.invoice_id)] == [L1.id]`.

### SS-A-06 — the draft is dated with the UTC day
- **Rules:** A4 [BUG-3196]
- **Kind:** bug
- **Expect:** xfail BUG-3196
- **Fails today on:** Then 2 (`date.today()`, the real local date, is used)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read S: `invoice_id is not None`.
2. re-read the invoice `db.get(AccountInvoice, S.invoice_id)`: `invoice_date == UTCDAY`.

### SS-A-07 — the order's lines are read in this workspace, in id order
- **Rules:** A7 [BUG-3193]; HR-6
- **Kind:** bug
- **Expect:** xfail BUG-3193
- **Fails today on:** Then 2 (the lazy relationship load has no ORDER BY)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.
3. ln(S), but `quantity_delivered 0.00`, `quantity_ordered 1.00`, `line_total 3000.00`.
4. After the commit point: `sid = S.id`; `db.expunge_all()`; `S2 = db.get(SalesOrder, sid)`; then Statement recorder on.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S2, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. statement: first(`sales_order_items`) is not None.
2. statement: `"ORDER BY" in first("sales_order_items")`.
3. statement: `"sales_order_items.workspace_id" in first("sales_order_items")`.

### SS-A-07b — invoice line numbers follow line id order after a row is rewritten
- **Rules:** A7 [BUG-3193]
- **Kind:** bug
- **Expect:** xfail BUG-3193 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (physical row order after the rewrite puts L1 last)

**Given**
1. S = so "1", but ready.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. L2 = ln(S), but `quantity_delivered 0.00`, `quantity_ordered 1.00`, `line_total 3000.00`.
4. After the commit point: `db.execute(text("UPDATE sales_order_items SET unit_price = unit_price WHERE id = :i"), {"i": L1.id})`; `db.expire_all()`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=db.get(SalesOrder, S.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `len(LINES(db.get(SalesOrder, S.id).invoice_id)) == 2`.
2. re-read: `[l.source_order_item_id for l in LINES(db.get(SalesOrder, S.id).invoice_id)] == [L1.id, L2.id]`.

### SS-A-08 — no `invoice_amount` is sent to create_invoice
- **Rules:** A4 [BUG-627]
- **Kind:** bug
- **Expect:** xfail BUG-627
- **Author:** claude
- **Fails today on:** Then 2 (`invoice_amount = 0.00` is sent)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside `patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci`.

**Then**
1. mock called: `ci.call_count == 1`.
2. mock called: the invoice data passed to `ci` did not set `invoice_amount` (`"invoice_amount" not in data.model_fields_set` for a schema; key absent for a dict).
3. re-read the invoice `db.get(AccountInvoice, S.invoice_id)`: `invoice_amount == Decimal("12000.00")`.

### SS-A-09 — the account of W2 is not found: 422, nothing written
- **Rules:** A2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but ready, `account_id A9.id`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCT`.
3. session: session clean.
4. nothing written: nothing written.
5. re-read S: `invoice_id is None`, `is_invoiced is False`.

### SS-A-10 — the account of W0 is not found: 422
- **Rules:** A2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but ready, `account_id A0.id`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCT`.
3. nothing written: nothing written.

### SS-A-11 — an account with invoicing disabled: 422
- **Rules:** A3
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.allow_invoices = False`; `db.flush()`.
2. S = so "1", but ready.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOINV`.
3. nothing written: nothing written.

### SS-A-12 — a deleted account: the invoice manager's 400 passes
- **Rules:** A2, A4
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.is_deleted = True`; `db.flush()`.
2. S = so "1", but ready.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot create invoice for deleted account"`.
3. nothing written: nothing written.

### SS-A-13 — an inactive account: the invoice manager's 400 passes
- **Rules:** A4
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.is_active = False`; `db.flush()`.
2. S = so "1", but ready.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot create invoice for inactive account"`.
3. nothing written: nothing written.

### SS-A-14 — invoicing disabled is checked before deleted
- **Rules:** A3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `A1.allow_invoices = False`; `A1.is_deleted = True`; `db.flush()`.
2. S = so "1", but ready.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOINV`.

### SS-A-15 — a 404 from create_invoice becomes the 422, with the 404 as cause
- **Rules:** A5
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. S = so "1", but ready.
2. `nf = HTTPException(status_code=404, detail="Account with ID 1 not found")`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside `patch.object(svc.account_invoice_manager, "create_invoice", side_effect=nf)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCT`.
3. raises: `exc.value.__cause__ is nf`.

### SS-A-16 — any other HTTPException from create_invoice passes as the same object
- **Rules:** A5
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. S = so "1", but ready.
2. `other = HTTPException(status_code=409, detail="x")`.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside `patch.object(svc.account_invoice_manager, "create_invoice", side_effect=other)`.

**Then**
1. raises: `HTTPException`; `exc.value is other`.

### SS-A-17 — an order with no lines gets an empty 0.00 draft
- **Rules:** A7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready.

**When**
- `svc._attach_receivable_invoice_to_sales_order(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read S: `invoice_id is not None`.
2. count: `LINES(S.invoice_id) == []`.
3. re-read the invoice: `invoice_amount == Decimal("0.00")`.

## `SalesService._delete_linked_draft_invoice_for_so`

### SS-DD-01 — no invoice linked: nothing happens
- **Rules:** DD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.

**When**
- `result = svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: session clean.
3. nothing written: nothing written.

### SS-DD-02 — a confirmed invoice stays linked
- **Rules:** DD2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. V = inv(S), but confirmed, linked.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. nothing written: nothing written.
2. re-read S: `invoice_id == V.id`.
3. unchanged: unchanged(V).

### SS-DD-03 — a voided invoice stays linked
- **Rules:** DD2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. V = inv(S), but voided-inv, linked.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. nothing written: nothing written.
2. re-read S: `invoice_id == V.id`.

### SS-DD-04 — a W2 draft linked to the order is not deleted
- **Rules:** DD2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1".
2. V9 = inv(S), but of W2, linked.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. nothing written: nothing written.
2. re-read S: `invoice_id == V9.id`.
3. unchanged: unchanged(V9).

### SS-DD-05 — a W0 draft linked to the order is not deleted
- **Rules:** DD2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1".
2. V0 = inv(S), but of W0, linked.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. nothing written: nothing written.
2. re-read S: `invoice_id == V0.id`.

### SS-DD-06 — a draft is deleted, the order unlinked and the delete logged; nothing committed
- **Rules:** DD3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`, `is_invoiced True`, `paid True`.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. `vid = V.id`.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. re-read: `db.get(AccountInvoice, vid) is None`.
4. count: `invoice_items` rows with `invoice_id == vid`: exactly 0.
5. re-read S: `invoice_id is None`, `invoice_confirmed is False`, `is_invoiced is False`, `paid is False`.
6. event: `types(S) == ["invoice_draft_deleted"]`.
7. event: that row has `description == f"Draft invoice #{vid} deleted"`, `performed_by == U2.id`.

### SS-DD-07 — the delete log entry names the deleted invoice
- **Rules:** DD4 [BUG-3204]
- **Kind:** bug
- **Expect:** xfail BUG-3204
- **Fails today on:** Then 2 (metadata is `{"invoice_id": None}`)

**Given**
1. S = so "1", but `order_info_confirmed True`, `is_invoiced True`.
2. V = inv(S), linked.
3. `vid = V.id`.

**When**
- `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. event: `types(S) == ["invoice_draft_deleted"]`.
2. event: `EV(S)[0].metadata_json == {"invoice_id": vid}`.

### SS-DD-08 — a draft with payment history is refused and kept
- **Rules:** DD3 [BUG-639]
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1 (the delete hits `invoice_payments.invoice_id NOT NULL`: `IntegrityError`; Gap log G18)

**Given**
1. S = so "1", but `is_invoiced True`.
2. V = inv(S), but `paid_amount 100.00`, `payment_status "partial"`, linked.
3. pay(V, "100.00").

**When**
- `sp = db.begin_nested()`; `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`; after the `raises:` block, roll the savepoint back unless it has already been rolled back or committed (`sp.rollback()`, not guarded by `if sp.is_active`: after today's failed flush `sp.is_active` is False but the savepoint is still open and must be rolled back before the re-reads).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == PAYHIST`.
3. re-read: `db.get(AccountInvoice, V.id) is not None`.
4. count: S has exactly 0 `sales_order_events` rows.

### SS-DD-09 — a draft with payment history is refused one way or another; the draft and its payment are kept (today and after the fix)
- **Rules:** DD3 (holds before and after BUG-639)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but `is_invoiced True`.
2. V = inv(S), but `paid_amount 100.00`, `payment_status "partial"`, linked.
3. P = pay(V, "100.00").

**When**
- `sp = db.begin_nested()`; `svc._delete_linked_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`; after the `raises:` block, roll the savepoint back unless it has already been rolled back or committed (`sp.rollback()`, not guarded by `if sp.is_active`: after today's failed flush `sp.is_active` is False but the savepoint is still open and must be rolled back before the re-reads).

**Then**
1. raises: `Exception` (any type: `IntegrityError` today, `HTTPException` 400 after BUG-639).
2. re-read: `db.get(AccountInvoice, V.id) is not None`; `db.get(InvoicePayment, P.id) is not None`.
3. re-read S: `invoice_id == V.id`, `is_invoiced is True`.
4. count: S has exactly 0 `sales_order_events` rows.

## `SalesService._sync_draft_invoice_for_so`

### SS-Y-01 — a financially locked order: nothing happens
- **Rules:** Y1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(V).

### SS-Y-02 — only order info confirmed and a draft linked: the draft is removed
- **Rules:** Y2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`, `is_invoiced True`.
2. V = inv(S), linked.
3. `vid = V.id`.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read: `db.get(AccountInvoice, vid) is None`.
3. event: `types(S) == ["invoice_draft_deleted"]`.

### SS-Y-03 — no section confirmed and no invoice: nothing happens
- **Rules:** Y2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-04 — only items confirmed and no invoice: no draft
- **Rules:** Y2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `items_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-05 — only order info confirmed and no invoice: no draft
- **Rules:** Y2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-06 — both confirmed and a draft already linked: no second draft
- **Rules:** Y3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready, `is_invoiced True`.
2. V = inv(S), linked.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-07 — both confirmed and a voided invoice linked: nothing happens
- **Rules:** Y3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), but voided-inv, linked.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-08 — both confirmed and a W2 invoice linked: nothing happens
- **Rules:** Y3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V9 = inv(S), but of W2, linked.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SS-Y-09 — both confirmed and no invoice: a draft is made, logged and its id returned; nothing committed
- **Rules:** Y4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`, inside **spies**.

**Then**
1. returns: `isinstance(result, int)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read S: `invoice_id == result`.
5. event: `types(S) == ["invoice_draft_created"]`.
6. event: `EV(S)[0].description == f"Draft invoice #{result} linked to SO-{TAG}-1"`, `EV(S)[0].metadata_json == {"invoice_id": result}`, `EV(S)[0].performed_by == U2.id`.

### SS-Y-10 — the draft step's refusal passes on
- **Rules:** Y4, A3
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.allow_invoices = False`; `db.flush()`.
2. S = so "1", but ready.

**When**
- `svc._sync_draft_invoice_for_so(db, order=S, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOINV`.
3. nothing written: nothing written.

## `SalesService.create_invoice_for_sales_order`

### SS-I-01 — the draft is created by hand, committed, and the order returned re-read
- **Rules:** I4, I5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready, `required_approvals 2`.
2. ln(S), but `quantity_delivered 0.00`.
3. appr(S, U3).

**When**
- `result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == S.id`.
3. committed: S has `invoice_id is not None`, `is_invoiced is True`.
4. committed: that invoice has `invoice_type == "receivable"`, `invoice_status == "draft"`, `order_id == S.id`, `invoice_amount == Decimal("12000.00")`.

### SS-I-02 — "Create invoice" logs the draft like the automatic one
- **Rules:** I4 [BUG-3209]
- **Kind:** bug
- **Expect:** xfail BUG-3209
- **Fails today on:** Then 2 (no event is logged)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. event: `types(S) == ["invoice_draft_created"]`.
3. event: `EV(S)[0].description == f"Draft invoice #{result.invoice_id} linked to SO-{TAG}-1"`, `EV(S)[0].metadata_json == {"invoice_id": result.invoice_id}`, `EV(S)[0].performed_by == U2.id`.

### SS-I-03 — only order info confirmed: 400, nothing written
- **Rules:** I3a [BUG-3209]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3209
- **Fails today on:** Then 1 (no error: the draft is made)

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.
3. X (after the commit point).

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NEEDCONF`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. nothing written: nothing written.
5. committed: x_gone.

### SS-I-04 — only items confirmed: 400
- **Rules:** I3a [BUG-3209]
- **Kind:** bug
- **Expect:** xfail BUG-3209
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but `items_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NEEDCONF`.
3. nothing written: nothing written.

### SS-I-05 — neither section confirmed: 400
- **Rules:** I3a [BUG-3209]
- **Kind:** bug
- **Expect:** xfail BUG-3209
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1".
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NEEDCONF`.
3. nothing written: nothing written.

### SS-I-06 — a draft already linked: 409, nothing written, the extra row is gone
- **Rules:** I2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready, `is_invoiced True`.
2. V = inv(S), linked.
3. X (after the commit point).

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Invoice already exists for this sales order"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. session: session clean.
6. nothing written: nothing written.
7. committed: x_gone.

### SS-I-07 — a voided invoice linked: also 409
- **Rules:** I2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), but voided-inv, linked.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Invoice already exists for this sales order"`.
3. nothing written: nothing written.

### SS-I-08 — no invoice linked but `is_invoiced` set: 409
- **Rules:** I3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready, `is_invoiced True`.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Invoice already exists for this sales order"`.
3. nothing written: nothing written.

### SS-I-09 — an unknown order: 404
- **Rules:** I1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError` is raised)

**Given**
1. W1 has no sales orders.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.
3. nothing written: nothing written.

### SS-I-10 — an unknown order is refused and rolled back (today and after the fix)
- **Rules:** I1, G1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no sales orders.
2. X (after the commit point).

**When**
- `svc.create_invoice_for_sales_order(db, order_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `Exception` (any type; the type changes with BUG-3197).
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. nothing written: nothing written.
4. committed: x_gone.

### SS-I-11 — the order is read with a row lock before any check
- **Rules:** I1 [BUG-3192]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3192
- **Fails today on:** Then 2 (plain read, no `FOR UPDATE`)

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.
3. `sid = S.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.create_invoice_for_sales_order(db, order_id=sid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == sid`.
2. statement: row lock on `sales_orders`.

### SS-I-12 — a failing commit leaves no invoice
- **Rules:** I4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `account_invoices` rows with `order_type == "sales_order"` and `order_id == S.id`: exactly 0.
4. re-read S: `invoice_id is None`, `is_invoiced is False`.

### SS-I-13 — the account refusal passes and everything is rolled back
- **Rules:** I4, A2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready, `account_id A9.id`.
2. X (after the commit point).

**When**
- `svc.create_invoice_for_sales_order(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCT`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. nothing written: nothing written.
5. committed: x_gone.

## `SalesService.finalize_sales_order_invoice`

### SS-F-01 — the invoice is confirmed, the order locked and logged; committed
- **Rules:** F6, F7, F8; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. appr(S, U1), but approved.

**When**
- `result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == S.id`; `result.invoice_payment_status == "unpaid"`.
3. committed: V has `invoice_status == "confirmed"`, `invoice_amount == Decimal("12000.00")`.
4. committed: `"confirmed" in itypes(V)`.
5. committed: S has `invoice_confirmed is True`, `order_info_confirmed is True`, `items_confirmed is True`.
6. committed: `types(S)[-1] == "invoice_confirmed"`.
7. committed: that event has `description == f"Invoice #{V.id} confirmed — order locked"`, `metadata_json == {"invoice_id": V.id}`, `performed_by == U2.id`.

### SS-F-02 — only order info confirmed: 400, nothing written, extra row gone
- **Rules:** F2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. V = inv(S), linked.
3. appr(S, U1), but approved.
4. X (after the commit point).

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Confirm order info and items before finalizing"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. unchanged: unchanged(V).
7. committed: x_gone.

### SS-F-03 — only items confirmed: 400
- **Rules:** F2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but `items_confirmed True`.
2. V = inv(S), linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Confirm order info and items before finalizing"`.
3. nothing written: nothing written.

### SS-F-04 — no approval given (all approvers required): 400
- **Rules:** F3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), linked.
3. appr(S, U3).

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Requires 1 approval(s); 0 so far"`.
3. nothing written: nothing written.
4. unchanged: unchanged(V).

### SS-F-05 — one of two required approvals: 400
- **Rules:** F3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready, `required_approvals 2`.
2. V = inv(S), linked.
3. appr(S, U1), but approved.
4. appr(S, U3).

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Requires 2 approval(s); 1 so far"`.
3. nothing written: nothing written.

### SS-F-06 — two of two required approvals: finalized
- **Rules:** F3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready, `required_approvals 2`.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. appr(S, U1), but approved.
4. appr(S, U3), but approved.

**When**
- `result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: V has `invoice_status == "confirmed"`.
3. committed: S has `invoice_confirmed is True`.

### SS-F-07 — already finalized: 409
- **Rules:** F4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Invoice is already finalized"`.
3. nothing written: nothing written.

### SS-F-08 — no invoice linked: a draft is made and confirmed, with no "draft created" event
- **Rules:** F5, F6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.
3. appr(S, U1), but approved.

**When**
- `result = svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `invoice_id is not None`, `invoice_confirmed is True`.
3. committed: that invoice has `invoice_status == "confirmed"`, `invoice_amount == Decimal("12000.00")`.
4. committed: `"invoice_draft_created" not in types(S)`.
5. committed: `types(S)[-1] == "invoice_confirmed"`.

### SS-F-09 — a voided invoice still linked: the confirm refusal passes, nothing written
- **Rules:** F6
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), but voided-inv, linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Voided invoices cannot be confirmed"`.
3. nothing written: nothing written.
4. re-read S: `invoice_confirmed is False`.

### SS-F-10 — an invoice confirmed earlier on the invoice page: 400
- **Rules:** F6
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), but confirmed, linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Invoice is already confirmed"`.
3. nothing written: nothing written.

### SS-F-11 — a W2 invoice linked: 404, nothing written, the W2 invoice untouched (today and after the fix)
- **Rules:** F6, F6a; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V9 = inv(S), but of W2, linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. nothing written: nothing written.
3. unchanged: unchanged(V9); unchanged(S) (still linked to V9).

### SS-F-12 — the order is read with a row lock
- **Rules:** F1 [BUG-3192]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3192
- **Fails today on:** Then 2 (no `FOR UPDATE`)

**Given**
1. S = so "1", but ready.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. appr(S, U1), but approved.
4. `sid = S.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.finalize_sales_order_invoice(db, order_id=sid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == sid`.
2. statement: row lock on `sales_orders`.

### SS-F-13 — a failing commit leaves the invoice a draft
- **Rules:** F7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. V = inv(S), linked; invl(V, 1, "12000.00").
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `invoice_status == "draft"`.
4. re-read S: `invoice_confirmed is False`.

### SS-F-14 — an unknown order: 404
- **Rules:** F1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-F-15 — a W2 invoice linked: the refusal names no id of W2
- **Rules:** F6a [BUG-3218]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3218
- **Fails today on:** Then 2 (detail is `Invoice with ID <V9.id> not found`)

**Given**
1. S = so "1", but ready.
2. V9 = inv(S), but of W2, linked.
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == FINV404`.
3. raises: `str(V9.id) not in exc.value.detail`.
4. nothing written: nothing written.
5. unchanged: unchanged(V9); unchanged(S).

### SS-F-16 — a W0 invoice linked: the same id-free refusal
- **Rules:** F6a [BUG-3218]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3218
- **Fails today on:** Then 2 (detail is `Invoice with ID <V0.id> not found`)

**Given**
1. S = so "1", but ready.
2. V0 = inv(S), but of W0, linked; invl(V0, 1, "12000.00").
3. appr(S, U1), but approved.

**When**
- `svc.finalize_sales_order_invoice(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == FINV404`.
3. nothing written: nothing written.
4. unchanged: unchanged(V0) (still `draft`, not confirmed); `itypes(V0) == []`.

## `SalesService.create_sales_order_from_dict`

### SS-C-01 — a new order is created through the manager, committed and returned re-read
- **Rules:** C1, C4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no sales orders.

**When**
- `result = svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("6000.00")}, items_data=[{"item_id": I1.id, "description": None, "quantity_ordered": Decimal("2"), "unit_price": Decimal("3000.00"), "line_total": Decimal("6000.00"), "requires_delivery": True}], workspace_id=W1.id, current_user=CU)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, SalesOrder)`, `result.id is not None`.
3. committed: the order has `workspace_id == W1.id`, `account_id == A1.id`, `total_amount == Decimal("6000.00")`, `created_by == U2.id`, `invoice_id is None`.
4. committed: its `sales_order_items` are exactly one: `item_id == I1.id`, `quantity_ordered == Decimal("2.00")`, `line_total == Decimal("6000.00")`.
5. committed: its approver rows are exactly one, `user_id == U2.id`.
6. committed: `"created" in types(result)`.
7. committed: `account_invoices` rows with `order_type == "sales_order"` and `order_id == result.id`: exactly 0.
8. committed: P1 has `qty == 100`.
9. committed: `notes() == []`.

### SS-C-02 — an order with no lines: 400 with the manager's message
- **Rules:** C2 [BUG-3219]
- **Kind:** bug
- **Expect:** xfail BUG-3219
- **Fails today on:** Then 1 (the manager's `ValueError` passes untranslated)

**Given**
1. W1 has no sales orders.

**When**
- `svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("0.00")}, items_data=[], workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Sales order must have at least one item"`.
3. nothing written: nothing written.

### SS-C-03 — an order with no lines is refused and rolled back (today and after the fix)
- **Rules:** C2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no sales orders.
2. X (after the commit point).

**When**
- `svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("0.00")}, items_data=[], workspace_id=W1.id, current_user=CU)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `Exception` (any type; it becomes `HTTPException` with BUG-3219).
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
4. nothing written: nothing written.
5. committed: x_gone.

### SS-C-04 — a failing re-read after the commit leaves the order saved
- **Rules:** C1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no sales orders.

**When**
- `svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("6000.00")}, items_data=[{"item_id": I1.id, "description": None, "quantity_ordered": Decimal("2"), "unit_price": Decimal("3000.00"), "line_total": Decimal("6000.00"), "requires_delivery": True}], workspace_id=W1.id, current_user=CU)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `sales_orders` row.
3. committed: that row has `created_by == U2.id`.

### SS-C-05 — a failing commit leaves no order
- **Rules:** C1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no sales orders.

**When**
- `svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("6000.00")}, items_data=[{"item_id": I1.id, "description": None, "quantity_ordered": Decimal("2"), "unit_price": Decimal("3000.00"), "line_total": Decimal("6000.00"), "requires_delivery": True}], workspace_id=W1.id, current_user=CU)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has exactly 0 `sales_orders` rows.
4. nothing written: nothing written.

### SS-C-06 — the service stores line totals and the order total exactly as given
- **Rules:** C3 (service part)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no sales orders.

**When**
- `result = svc.create_sales_order_from_dict(db, order_data={"account_id": A1.id, "factory_id": F1.id, "order_date": date(2026, 9, 1), "contact_name": "Rahim", "total_amount": Decimal("0.39")}, items_data=[{"item_id": None, "description": "Ribbon", "quantity_ordered": Decimal("0.50"), "unit_price": Decimal("0.25"), "line_total": Decimal("0.13"), "requires_delivery": True}, {"item_id": None, "description": "Ribbon", "quantity_ordered": Decimal("0.50"), "unit_price": Decimal("0.25"), "line_total": Decimal("0.13"), "requires_delivery": True}, {"item_id": None, "description": "Ribbon", "quantity_ordered": Decimal("0.50"), "unit_price": Decimal("0.25"), "line_total": Decimal("0.13"), "requires_delivery": True}], workspace_id=W1.id, current_user=CU)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the order has `total_amount == Decimal("0.39")`.
3. committed: its three lines each have `line_total == Decimal("0.13")`.

## `SalesService.get_sales_order`

### SS-G-01 — returns the order with its invoice's payment status; neither commits nor rolls back
- **Rules:** G2, PS2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, `paid_amount 1000.00`, `payment_status "partial"`, linked.
3. X (after the commit point).

**When**
- `result = svc.get_sales_order(db, order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == S.id`.
2. returns: `result.invoice_payment_status == "partial"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. re-read: x_kept.

### SS-G-02 — an order with no invoice has no payment status
- **Rules:** G2, PS1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `result = svc.get_sales_order(db, order_id=S.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S.id`.
2. returns: `result.invoice_payment_status is None`.

### SS-G-03 — a W0 order (lower workspace id): 404
- **Rules:** G1 [BUG-3197]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. S0 = so "0", but of W0.

**When**
- `svc.get_sales_order(db, order_id=S0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S0.id)`.

### SS-G-04 — a W2 order (higher workspace id): 404
- **Rules:** G1 [BUG-3197]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. S9 = so "9", but of W2.

**When**
- `svc.get_sales_order(db, order_id=S9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S9.id)`.

### SS-G-05 — an unknown id: 404
- **Rules:** G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.get_sales_order(db, order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-G-06 — not found neither commits nor rolls back (today and after the fix)
- **Rules:** G1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. X (after the commit point).

**When**
- `svc.get_sales_order(db, order_id=S9.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `Exception` (any type; it becomes `HTTPException` with BUG-3197).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

## `SalesService.get_sales_orders`

### SS-L-01 — the workspace's orders, all of them; W0 and W2 orders never appear
- **Rules:** L1, L2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. Sc = so "3", but `order_date date(2026, 9, 3)`.
3. Sa = so "1", but `order_date date(2026, 9, 1)`.
4. Sb = so "2", but `order_date date(2026, 9, 2)`.
5. S9 = so "9", but of W2.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`; `idset(result) == {Sc.id, Sa.id, Sb.id}` (order in SS-L-07).
2. returns: every order has `invoice_payment_status is None`.

### SS-L-02 — skip and limit are applied after the workspace filter
- **Rules:** L1 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 1 (BaseDAO `get_by_workspace` sends no `ORDER BY`; Gap log G16)

**Given**
1. S0 = so "0", but of W0.
2. O1 … O5 = so "1" … so "5", in that order.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id, skip=1, limit=2)`, Statement recorder on.

**Then**
1. statement: id order on `sales_orders`.
2. returns: `[o.id for o in result] == [O2.id, O3.id]`.

### SS-L-03 — skip alone is applied
- **Rules:** L1 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 1 (BaseDAO `get_by_workspace` sends no `ORDER BY`; Gap log G16)

**Given**
1. O1, O2, O3 = so "1", so "2", so "3", in that order.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id, skip=1)`, Statement recorder on.

**Then**
1. statement: id order on `sales_orders`.
2. returns: `[o.id for o in result] == [O2.id, O3.id]`.

### SS-L-04 — no limit given: at most 100
- **Rules:** L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders so "1" … so "101" in W1.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100` (which 100 is an order question: SS-L-02, SS-L-07).
2. returns: every row has `workspace_id == W1.id`.

### SS-L-05 — limit=1000 is passed on
- **Rules:** L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders so "1" … so "101" in W1.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### SS-L-06 — payment statuses for the page come from one invoice query; neither commits nor rolls back
- **Rules:** L2, PS2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Sa = so "1"; Va = inv(Sa), but confirmed, linked.
2. Sb = so "2"; Vb = inv(Sb), but confirmed, `paid_amount 12000.00`, `payment_status "paid"`, linked.
3. Sc = so "3".
4. X (after the commit point); Statement recorder on; `db.expunge_all()`.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `{o.id: o.invoice_payment_status for o in result} == {Sa.id: "unpaid", Sb.id: "paid", Sc.id: None}`.
2. statement: exactly 1 recorded SELECT names `account_invoices` in its `FROM`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. re-read: x_kept.

### SS-L-07 — the workspace's orders come back in id order
- **Rules:** L1 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 1 (BaseDAO `get_by_workspace` sends no `ORDER BY`; Gap log G16)

**Given**
1. Sc = so "3", but `order_date date(2026, 9, 3)`.
2. Sa = so "1", but `order_date date(2026, 9, 1)`.
3. Sb = so "2", but `order_date date(2026, 9, 2)`.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id)`, Statement recorder on.

**Then**
1. statement: id order on `sales_orders`.
2. returns: `[o.id for o in result] == [Sc.id, Sa.id, Sb.id]` (insertion = id order, not date order).

### SS-L-08 — skip and limit give a page of two orders of this workspace (today and after the fix)
- **Rules:** L1 (holds before and after BUG-100)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. O1 … O5 = so "1" … so "5", in that order.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {O1.id, O2.id, O3.id, O4.id, O5.id}`.

### SS-L-09 — skip alone drops one order (today and after the fix)
- **Rules:** L1 (holds before and after BUG-100)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1, O2, O3 = so "1", so "2", so "3", in that order.

**When**
- `result = svc.get_sales_orders(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {O1.id, O2.id, O3.id}`.

## `SalesService._attach_invoice_payment_status`

### SS-PS-01 — an empty list: no query
- **Rules:** PS1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Statement recorder on (after the commit point).

**When**
- `svc._attach_invoice_payment_status(db, orders=[])`.

**Then**
1. statement: no recorded SELECT names `account_invoices`.

### SS-PS-02 — orders without invoices get None and no query is sent
- **Rules:** PS1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Sa = so "1"; Sb = so "2".
2. Statement recorder on (after the commit point).

**When**
- `svc._attach_invoice_payment_status(db, orders=[Sa, Sb])`.

**Then**
1. returns: `Sa.invoice_payment_status is None`.
2. returns: `Sb.invoice_payment_status is None`.
3. statement: no recorded SELECT names `account_invoices`.

### SS-PS-03 — each order gets its own invoice's status; nothing is written
- **Rules:** PS2, PS4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Sa = so "1"; Va = inv(Sa), but confirmed, linked.
2. Sb = so "2"; Vb = inv(Sb), but confirmed, `payment_status "overdue"`, linked.
3. Sc = so "3".

**When**
- `svc._attach_invoice_payment_status(db, orders=[Sa, Sb, Sc])`.

**Then**
1. returns: `Sa.invoice_payment_status == "unpaid"`.
2. returns: `Sb.invoice_payment_status == "overdue"`.
3. returns: `Sc.invoice_payment_status is None`.
4. session: session clean.

### SS-PS-04 — a W2 invoice linked to a W1 order gives None
- **Rules:** PS2 [BUG-3194]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3194
- **Fails today on:** Then 2 (the W2 invoice's status `"paid"` is shown)

**Given**
1. Sa = so "1"; Va = inv(Sa), but confirmed, linked.
2. Sb = so "2"; V9 = inv(Sb), but of W2, confirmed, `payment_status "paid"`, linked.

**When**
- `svc._attach_invoice_payment_status(db, orders=[Sa, Sb])`.

**Then**
1. returns: `Sa.invoice_payment_status == "unpaid"`.
2. returns: `Sb.invoice_payment_status is None`.

### SS-PS-05 — a W0 invoice linked to a W1 order gives None
- **Rules:** PS2 [BUG-3194]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3194
- **Fails today on:** Then 1 (the W0 invoice's status is shown)

**Given**
1. Sb = so "2"; V0 = inv(Sb), but of W0, confirmed, `payment_status "partial"`, linked.

**When**
- `svc._attach_invoice_payment_status(db, orders=[Sb])`.

**Then**
1. returns: `Sb.invoice_payment_status is None`.

### SS-PS-06 — an invoice id with no invoice row gives None
- **Rules:** PS3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Sa = so "1".
2. After the commit point: `Sa.invoice_id = MISSING` in memory only (not flushed).

**When**
- `svc._attach_invoice_payment_status(db, orders=[Sa])`.

**Then**
1. returns: `Sa.invoice_payment_status is None`.

### SS-PS-07 — the helper returns None; the result is only the attribute
- **Rules:** PS5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Sa = so "1"; Va = inv(Sa), but confirmed, linked.

**When**
- `result = svc._attach_invoice_payment_status(db, orders=[Sa])`.

**Then**
1. returns: `result is None`.
2. returns: `Sa.invoice_payment_status == "unpaid"`.

## `SalesService.update_sales_order`

### SS-U-01 — an edit is committed and the order returned re-read; omitted fields unchanged
- **Rules:** U1, U5, U10; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == S.id`.
3. committed: S has `contact_phone == "01700000000"`.
4. committed: S has `contact_name == "Rahim"`, `description is None`.
5. committed: `notes() == []`.

### SS-U-02 — a real change stamps `updated_by`
- **Rules:** U8 [BUG-3200]; HR-9
- **Kind:** bug
- **Expect:** xfail BUG-3200
- **Fails today on:** Then 2 (`updated_by` stays NULL)

**Given**
1. S = so "1".

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`.

**Then**
1. committed: S has `contact_phone == "01700000000"`.
2. committed: S has `updated_by == U2.id`.

### SS-U-03 — a real change logs one `order_updated` event
- **Rules:** U9 [BUG-3215]
- **Kind:** bug
- **Expect:** xfail BUG-3215
- **Fails today on:** Then 2 (no event)

**Given**
1. S = so "1".

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. event: `types(S) == ["order_updated"]`.
3. event: `EV(S)[0].description == "Order updated (contact phone)"`, `EV(S)[0].metadata_json == {"fields": ["contact_phone"]}`, `EV(S)[0].performed_by == U2.id`.

### SS-U-04 — several fields: labels in the fixed order
- **Rules:** U9 [BUG-3215]
- **Kind:** bug
- **Expect:** xfail BUG-3215
- **Fails today on:** Then 2 (no event)

**Given**
1. S = so "1".

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(description="Blue chairs", contact_name="Karim", expected_delivery_date=date(2026, 10, 1), required_approvals=2), user_id=U2.id)`.

**Then**
1. committed: S has `description == "Blue chairs"`, `contact_name == "Karim"`, `expected_delivery_date == date(2026, 10, 1)`, `required_approvals == 2`.
2. event: `types(S) == ["order_updated"]`.
3. event: `EV(S)[0].description == "Order updated (expected delivery date, contact name, description, required approvals)"`.
4. event: `EV(S)[0].metadata_json == {"fields": ["expected_delivery_date", "contact_name", "description", "required_approvals"]}`.

### SS-U-05 — sending the stored values changes nothing: no event, no stamp
- **Rules:** U8, U9; HR-9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `required_approvals 2`.

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_name="Rahim", required_approvals=2), user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `updated_by is None`, `contact_name == "Rahim"`, `required_approvals == 2`.
3. committed: S has exactly 0 `sales_order_events` rows.

### SS-U-06 — `required_approvals` sent as null clears it
- **Rules:** U5 [BUG-3199]
- **Kind:** bug
- **Expect:** xfail BUG-3199
- **Fails today on:** Then 2 (`null` is dropped; stays 2)

**Given**
1. S = so "1", but `required_approvals 2`.

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=None), user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `required_approvals is None`.

### SS-U-07 — `contact_phone` sent as null clears it
- **Rules:** U5 [BUG-3199]
- **Kind:** bug
- **Expect:** xfail BUG-3199
- **Fails today on:** Then 2 (stays `"017"`)

**Given**
1. S = so "1", but `contact_phone "017"`.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone=None), user_id=U2.id)`.

**Then**
1. committed: S has `contact_name == "Rahim"`.
2. committed: S has `contact_phone is None`.

### SS-U-08 — a completed order cannot be edited
- **Rules:** U2 [BUG-3207]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3207
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but completed.
2. X (after the commit point).

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot edit — order is complete"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. nothing written: nothing written.
5. unchanged: unchanged(S).
6. committed: x_gone.

### SS-U-09 — a financially locked order cannot be edited
- **Rules:** U2 [BUG-3207]
- **Kind:** bug
- **Expect:** xfail BUG-3207
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=5), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot edit — invoice is locked"`.
3. unchanged: unchanged(S).

### SS-U-10 — completed and locked: the completion message wins
- **Rules:** U2 [BUG-3207]
- **Kind:** bug
- **Expect:** xfail BUG-3207
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but finalized, completed.
2. V = inv(S), but confirmed, linked.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot edit — order is complete"`.

### SS-U-11 — "return in progress" (completed with a pending return) cannot be edited
- **Rules:** U2 [BUG-3207]; RP5
- **Kind:** bug
- **Expect:** xfail BUG-3207
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but finalized, completed.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S); R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(description="x"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot edit — order is complete"`.
3. unchanged: unchanged(S).

### SS-U-12 — confirmed order info: changing the contact name is refused
- **Rules:** U3 [BUG-3208]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3208
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. X (after the commit point).

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_name="Karim"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == INFOLOCK`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. unchanged: unchanged(S).
5. committed: x_gone.

### SS-U-13 — confirmed order info: changing the phone is refused
- **Rules:** U3 [BUG-3208]
- **Kind:** bug
- **Expect:** xfail BUG-3208
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but `order_info_confirmed True`, `contact_phone "017"`.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="018"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == INFOLOCK`.
3. unchanged: unchanged(S).

### SS-U-14 — confirmed order info: changing the expected delivery date is refused
- **Rules:** U3 [BUG-3208]
- **Kind:** bug
- **Expect:** xfail BUG-3208
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but `order_info_confirmed True`, `expected_delivery_date date(2026, 10, 1)`.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(expected_delivery_date=date(2026, 10, 2)), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == INFOLOCK`.
3. unchanged: unchanged(S).

### SS-U-15 — confirmed order info: changing the description is refused
- **Rules:** U3 [BUG-3208]
- **Kind:** bug
- **Expect:** xfail BUG-3208
- **Fails today on:** Then 1 (no error)

**Given**
1. S = so "1", but `order_info_confirmed True`, `description "Blue"`.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(description="Red"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == INFOLOCK`.
3. unchanged: unchanged(S).

### SS-U-16 — confirmed order info: sending the stored contact name is not a change
- **Rules:** U3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_name="Rahim"), user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `contact_name == "Rahim"`, `order_info_confirmed is True`.

### SS-U-17 — confirmed order info does not block the required approvals
- **Rules:** U3, U5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.

**When**
- `result = svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=3), user_id=U2.id)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `required_approvals == 3`, `order_info_confirmed is True`.

### SS-U-18 — `total_amount` is not accepted by the edit schema
- **Rules:** U4 [BUG-2404]
- **Kind:** bug
- **Expect:** xfail BUG-2404
- **Fails today on:** Then 1 (the schema accepts it)

**Given**
1. Nothing.

**When**
- build `SalesOrderUpdate(total_amount=Decimal("1"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### SS-U-19 — `is_fully_delivered` is not accepted
- **Rules:** U4 [BUG-2404]
- **Kind:** bug
- **Expect:** xfail BUG-2404
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `SalesOrderUpdate(is_fully_delivered=True)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### SS-U-20 — `is_invoiced` is not accepted
- **Rules:** U4 [BUG-2404]
- **Kind:** bug
- **Expect:** xfail BUG-2404
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `SalesOrderUpdate(is_invoiced=True)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### SS-U-21 — `invoice_id` is not accepted
- **Rules:** U4 [BUG-1019]
- **Kind:** bug
- **Expect:** xfail BUG-1019
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `SalesOrderUpdate(invoice_id=1)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### SS-U-22 — changing the required approvals clears the approvals given
- **Rules:** U7 [BUG-3201]
- **Kind:** bug
- **Expect:** xfail BUG-3201
- **Fails today on:** Then 2 (approvals are kept)

**Given**
1. S = so "1", but `required_approvals 2`.
2. A_1 = appr(S, U1), but approved.
3. A_3 = appr(S, U3), but approved.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=1), user_id=U2.id)`.

**Then**
1. committed: S has `required_approvals == 1`.
2. committed: A_1 has `approved is False`.
3. committed: A_3 has `approved is False`.
4. committed: `types(S).count("approvals_reset") == 1`.

### SS-U-23 — a change from null to a number also clears the approvals
- **Rules:** U7 [BUG-3201]
- **Kind:** bug
- **Expect:** xfail BUG-3201
- **Fails today on:** Then 2 (approval kept)

**Given**
1. S = so "1".
2. A_1 = appr(S, U1), but approved.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=2), user_id=U2.id)`.

**Then**
1. committed: S has `required_approvals == 2`.
2. committed: A_1 has `approved is False`.

### SS-U-24 — sending the stored required approvals keeps the approvals
- **Rules:** U7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `required_approvals 2`.
2. A_1 = appr(S, U1), but approved.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=2), user_id=U2.id)`.

**Then**
1. committed: A_1 has `approved is True`, `approved_at == T1`.
2. committed: `"approvals_reset" not in types(S)`.

### SS-U-25 — the reset event comes before the edit event
- **Rules:** U7, U9 [BUG-3215]
- **Kind:** bug
- **Expect:** xfail BUG-3215
- **Fails today on:** Then 1 (no events)

**Given**
1. S = so "1", but `required_approvals 2`.
2. appr(S, U1), but approved.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(required_approvals=1), user_id=U2.id)`.

**Then**
1. event: `types(S) == ["approvals_reset", "order_updated"]`.
2. event: `EV(S)[1].description == "Order updated (required approvals)"`.

### SS-U-26 — an unknown order: 404
- **Rules:** U1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. S9 = so "9", but of W2.

**When**
- `svc.update_sales_order(db, order_id=S9.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="1"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S9.id)`.
3. unchanged: unchanged(S9).

### SS-U-27 — another workspace's order is refused and rolled back (today and after the fix)
- **Rules:** U1, G1; TC3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. X (after the commit point).

**When**
- `svc.update_sales_order(db, order_id=S9.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="1"), user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `Exception` (any type).
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
4. unchanged: unchanged(S9).
5. committed: x_gone.

### SS-U-28 — a failing commit leaves the order as it was
- **Rules:** U5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(contact_phone="01700000000"), user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `contact_phone is None`.

### SS-U-29 — no invoice step: a linked draft keeps its notes
- **Rules:** U10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but `items_confirmed True`, `description "Blue"`.
2. V = inv(S), but `notes "Blue"`, linked.

**When**
- `svc.update_sales_order(db, order_id=S.id, workspace_id=W1.id, order_update=SalesOrderUpdate(description="Red"), user_id=U2.id)`.

**Then**
1. committed: S has `description == "Red"`.
2. committed: unchanged(V).
3. committed: `notes() == []`.

## `SalesService.create_delivery`

### SS-DC-01 — a delivery is planned, committed, and both rows returned re-read
- **Rules:** DC1; TC1, TC2; N5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.create_delivery(db, delivery_in=SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=DM1.id, scheduled_date=date(2026, 10, 5)), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": Decimal("2")}], workspace_id=W1.id, current_user=CU)`; `delivery, order = result`.

**Then**
1. loaded: `loaded(delivery)`.
2. loaded: `loaded(order)`.
3. returns: `order.id == S.id`; `delivery.sales_order_id == S.id`.
4. committed: the delivery has `delivery_status == "planned"`, `created_by == U2.id`, `workspace_id == W1.id`.
5. committed: its lines are exactly one: `sales_order_item_id == L1.id`, `quantity_delivered == Decimal("2.00")`.
6. committed: `"delivery_planned" in types(S)`.
7. committed: `notes() == []`.

### SS-DC-02 — the manager's `ValueError` becomes a 400 after the rollback
- **Rules:** DC2; TC3 (departure)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. X (after the commit point).

**When**
- `svc.create_delivery(db, delivery_in=SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=DM1.id, scheduled_date=date(2026, 10, 5)), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": Decimal("2")}], workspace_id=W1.id, current_user=CU)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Finalize the invoice before planning a delivery"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### SS-DC-03 — no delivery lines: 400 with the manager's message
- **Rules:** DC2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.

**When**
- `svc.create_delivery(db, delivery_in=SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=DM1.id, scheduled_date=date(2026, 10, 5)), delivery_items_data=[], workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Delivery must have at least one item"`.
3. nothing written: nothing written.

### SS-DC-04 — a completed order with a replacement gap can get a delivery; it stays completed
- **Rules:** DC3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.

**When**
- `result = svc.create_delivery(db, delivery_in=SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=DM1.id, scheduled_date=date(2026, 10, 5)), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": Decimal("1")}], workspace_id=W1.id, current_user=CU)`; `delivery, order = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: the delivery has `delivery_status == "planned"`.
3. committed: S has `order_completed is True`, `completed_at == T0`.
4. committed: V has `invoice_status == "confirmed"`.

### SS-DC-05 — a failing commit leaves no delivery
- **Rules:** DC1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.create_delivery(db, delivery_in=SalesDeliveryCreate(sales_order_id=S.id, delivery_method_id=DM1.id, scheduled_date=date(2026, 10, 5)), delivery_items_data=[{"sales_order_item_id": L1.id, "quantity_delivered": Decimal("2")}], workspace_id=W1.id, current_user=CU)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: S has exactly 0 `sales_deliveries` rows.

## `SalesService.complete_delivery`

### SS-DV-01 — a delivery is completed, stock goes out, messages in order; committed
- **Rules:** DV2, DV3, DV4, DV5, DV6; TC1, TC2; N5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "4.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. loaded: `loaded(order)`.
2. returns: `order.id == S.id`.
3. returns: `msgs == [MSG("success", f"Delivery DEL-{TAG}-1 marked as completed"), MSG("info", "Inventory updated: 1 items, 4.00 units deducted"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")]`.
4. returns: the details of `msgs[1]` have `item_count == 1` and `Decimal(str(total_quantity)) == Decimal("4.00")`.
5. committed: D1 has `delivery_status == "delivered"`.
6. committed: L1 has `quantity_delivered == Decimal("4.00")`; S has `is_fully_delivered is True`.
7. committed: P1 has `qty == 96`.
8. committed: NEWLED is exactly one row: `transaction_type == "sale"`, `quantity == 4`, `source_type == "sales_delivery"`, `source_id == D1.id`.
9. committed: `notes() == []`.

### SS-DV-02 — a partial delivery reports what remains
- **Rules:** DV4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `msgs[2] == MSG("info", "3.00 units remaining to be delivered")`.
3. returns: `len(msgs) == 3`.
4. committed: S has `is_fully_delivered is False`.

### SS-DV-03 — refunded units are not "remaining"
- **Rules:** DV4 [BUG-3206]
- **Kind:** bug
- **Expect:** xfail BUG-3206
- **Fails today on:** Then 2 (today `5.00 units remaining`: refunded ignored)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_ordered 10.00`, `quantity_delivered 6.00`, `quantity_refunded 2.00`, `quantity_returned 2.00`, `line_total 30000.00`.
4. L2 = ln(S), but free "Crate", `quantity_ordered 5.00`, `quantity_delivered 2.00`, `unit_price 100.00`, `line_total 500.00`.
5. D1 = dlv(S, "1"); dl(D1, L1, "2.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `msgs[2] == MSG("info", "3.00 units remaining to be delivered")`.

### SS-DV-04 — an over-delivered line does not lower the remaining count
- **Rules:** DV4 [BUG-3206]
- **Kind:** bug
- **Expect:** xfail BUG-3206
- **Fails today on:** Then 2 (today `1.00`: the over-delivered line subtracts 2)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 6.00`.
4. L2 = ln(S), but free "Crate", `quantity_ordered 5.00`, `quantity_delivered 0.00`, `unit_price 100.00`, `line_total 500.00`.
5. D1 = dlv(S, "1"); dl(D1, L2, "2.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `msgs[2] == MSG("info", "3.00 units remaining to be delivered")`.

### SS-DV-05 — "units deducted" counts only catalog lines
- **Rules:** DV3 [BUG-3216]
- **Kind:** bug
- **Expect:** xfail BUG-3216
- **Fails today on:** Then 2 (today `2 items, 5.00 units deducted`)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. L2 = ln(S), but free "Crate", `quantity_ordered 1.00`, `quantity_delivered 0.00`, `unit_price 100.00`, `line_total 100.00`.
5. D1 = dlv(S, "1"); dl(D1, L1, "4.00"); dl(D1, L2, "1.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[0] == MSG("success", f"Delivery DEL-{TAG}-1 marked as completed")`.
2. returns: `msgs[1] == MSG("info", "Inventory updated: 1 items, 4.00 units deducted")`.
3. returns: the details of `msgs[1]` have `item_count == 1` and `Decimal(str(total_quantity)) == Decimal("4.00")`.

### SS-DV-06 — only free-text lines: "No inventory movement"
- **Rules:** DV3 [BUG-3216]
- **Kind:** bug
- **Expect:** xfail BUG-3216
- **Fails today on:** Then 2 (today `Inventory updated: 1 items, 1.00 units deducted`)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L2 = ln(S), but free "Crate", `quantity_ordered 1.00`, `quantity_delivered 0.00`, `unit_price 100.00`, `line_total 100.00`.
4. D1 = dlv(S, "1"); dl(D1, L2, "1.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[0] == MSG("success", f"Delivery DEL-{TAG}-1 marked as completed")`.
2. returns: `msgs[1] == MSG("info", "No inventory movement")`.
3. returns: the details of `msgs[1]` are `{"item_count": 0, "total_quantity": 0}`.

### SS-DV-07 — two catalog lines: counted and summed (today and after the fix)
- **Rules:** DV3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. L2 = ln(S), but `quantity_ordered 1.00`, `quantity_delivered 0.00`, `line_total 3000.00`.
5. D1 = dlv(S, "1"); dl(D1, L1, "4.00"); dl(D1, L2, "1.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[1] == MSG("info", "Inventory updated: 2 items, 5.00 units deducted")`.
2. committed: P1 has `qty == 95`.

### SS-DV-08 — an unknown delivery: 404, nothing written, extra row gone
- **Rules:** DV1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no deliveries.
2. X (after the commit point).

**When**
- `svc.complete_delivery(db, delivery_id=MISSING, workspace_id=W1.id, current_user=CU)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(MISSING)`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### SS-DV-09 — a W0 delivery: 404, not completed
- **Rules:** DV1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. L0 = ln(S0), but `quantity_delivered 0.00`.
3. D0 = dlv(S0, "0"); dl(D0, L0, "1.00").

**When**
- `svc.complete_delivery(db, delivery_id=D0.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(D0.id)`.
3. unchanged: unchanged(D0).

### SS-DV-10 — a W2 delivery: 404, not completed
- **Rules:** DV1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. L9 = ln(S9), but `quantity_delivered 0.00`.
3. D9 = dlv(S9, "9"); dl(D9, L9, "1.00").

**When**
- `svc.complete_delivery(db, delivery_id=D9.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(D9.id)`.
3. unchanged: unchanged(D9).

### SS-DV-11 — the manager's `ValueError` becomes a 400
- **Rules:** DV2 [BUG-3198]
- **Kind:** bug
- **Expect:** xfail BUG-3198
- **Fails today on:** Then 1 (the `ValueError` passes untranslated)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "0.00").

**When**
- `svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Sale deduction quantity must be positive"`.

### SS-DV-12 — a manager refusal is rolled back (today and after the fix)
- **Rules:** DV2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "0.00").
5. X (after the commit point).

**When**
- `svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `Exception` (any type; it becomes `HTTPException` with BUG-3198).
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. re-read D1: `delivery_status == "planned"`.
4. re-read P1: `qty == 100`.
5. committed: x_gone.

### SS-DV-13 — insufficient stock: the 422 passes unchanged
- **Rules:** DV2
- **Kind:** error
- **Expect:** pass

**Given**
1. `P1.qty = 2`; `db.flush()`.
2. S = so "1", but finalized.
3. V = inv(S), but confirmed, linked.
4. L1 = ln(S), but `quantity_delivered 0.00`.
5. D1 = dlv(S, "1"); dl(D1, L1, "4.00").

**When**
- `svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `re.fullmatch(rf"Insufficient sellable stock for item {I1.id} at factory {F1.id}: requested 4(\.0+)?, available 2(\.0+)?", exc.value.detail)` is not None (the spec does not fix how the two quantities are printed; both are W1 ids).
3. re-read D1: `delivery_status == "planned"`.
4. nothing written: nothing written.

### SS-DV-14 — a replacement delivery on a completed order completes; the order stays completed
- **Rules:** DV6; FU-2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- `result = svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: D1 has `delivery_status == "delivered"`.
3. committed: S has `order_completed is True`, `completed_at == T0`, `completed_by == U1.id`.
4. committed: V has `invoice_status == "confirmed"`, `invoice_amount == Decimal("12000.00")`.

### SS-DV-15 — a failing commit leaves the delivery planned and the stock untouched
- **Rules:** DV5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 0.00`.
4. D1 = dlv(S, "1"); dl(D1, L1, "4.00").

**When**
- `svc.complete_delivery(db, delivery_id=D1.id, workspace_id=W1.id, current_user=CU)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read D1: `delivery_status == "planned"`.
4. re-read P1: `qty == 100`.
5. count: NEWLED is empty.

## `SalesService.cancel_delivery`

### SS-DX-01 — a planned delivery is cancelled, committed and returned re-read
- **Rules:** DX2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- `result = svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == D1.id`.
3. committed: D1 has `delivery_status == "cancelled"`.

### SS-DX-02 — an unknown delivery: 404
- **Rules:** DX1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no deliveries.
2. X (after the commit point).

**When**
- `svc.cancel_delivery(db, delivery_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(MISSING)`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. committed: x_gone.

### SS-DX-03 — a W2 delivery: 404, not cancelled
- **Rules:** DX1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. D9 = dlv(S9, "9").

**When**
- `svc.cancel_delivery(db, delivery_id=D9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. unchanged: unchanged(D9).

### SS-DX-04 — a delivered delivery: the manager's refusal becomes a 400, rolled back
- **Rules:** DX2; TC3 (departure)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D1 = dlv(S, "1"), but delivered.
3. X (after the commit point).

**When**
- `svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only planned deliveries can be cancelled (this delivery is 'delivered')"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(D1).
6. committed: x_gone.

### SS-DX-05 — a failing commit leaves the delivery planned
- **Rules:** DX2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D1 = dlv(S, "1").

**When**
- `svc.cancel_delivery(db, delivery_id=D1.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read D1: `delivery_status == "planned"`.

## `SalesService.update_delivery`

### SS-DU-01 — a planned delivery is edited, committed and returned re-read
- **Rules:** DU2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D1 = dlv(S, "1"), but `tracking_number "TRK-100"`.

**When**
- `result = svc.update_delivery(db, delivery_id=D1.id, workspace_id=W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == D1.id`.
3. committed: D1 has `tracking_number == "TRK-200"`.

### SS-DU-02 — an unknown delivery: 404
- **Rules:** DU1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no deliveries.
2. X (after the commit point).

**When**
- `svc.update_delivery(db, delivery_id=MISSING, workspace_id=W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(MISSING)`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. committed: x_gone.

### SS-DU-03 — a W0 delivery: 404, not edited
- **Rules:** DU1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. D0 = dlv(S0, "0"), but `tracking_number "TRK-100"`.

**When**
- `svc.update_delivery(db, delivery_id=D0.id, workspace_id=W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. unchanged: unchanged(D0).

### SS-DU-04 — a delivered delivery: the manager's refusal becomes a 400, rolled back
- **Rules:** DU2; TC3 (departure)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D1 = dlv(S, "1"), but delivered, `tracking_number "TRK-100"`.
3. X (after the commit point).

**When**
- `svc.update_delivery(db, delivery_id=D1.id, workspace_id=W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only planned deliveries can be edited (this delivery is 'delivered')"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(D1).
6. committed: x_gone.

### SS-DU-05 — a failing commit leaves the old tracking number
- **Rules:** DU2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D1 = dlv(S, "1"), but `tracking_number "TRK-100"`.

**When**
- `svc.update_delivery(db, delivery_id=D1.id, workspace_id=W1.id, data=SalesDeliveryEditRequest(tracking_number="TRK-200"), user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read D1: `tracking_number == "TRK-100"`.

## `SalesService.fulfill_service_item`

### SS-FS-01 — a service line is fulfilled; messages; committed; no stock
- **Rules:** FS4, FS6, FS7; TC1, TC2; N5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. loaded: `loaded(order)`.
2. returns: `order.id == S.id`.
3. returns: `msgs == [MSG("success", "Line item marked as fulfilled"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")]`.
4. committed: LS has `quantity_delivered == Decimal("2.00")`.
5. committed: S has 0 `sales_deliveries` rows.
6. committed: NEWLED is empty; P1 has `qty == 100`.
7. committed: `notes() == []`.

### SS-FS-02 — not the last open line: only the first message
- **Rules:** FS7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.
4. L1 = ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs == [MSG("success", "Line item marked as fulfilled")]`.
2. committed: S has `is_fully_delivered is False`.

### SS-FS-03 — a line of W2: 404
- **Rules:** FS1; HR-16; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. S9 = so "9", but of W2.
3. L9 = ln(S9), but service, `quantity_delivered 0.00`.
4. X (after the commit point).

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=L9.id, workspace_id=W1.id, current_user=CU)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Sales order item {L9.id} not found"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(L9).
6. committed: x_gone.

### SS-FS-04 — a line of W0: 404
- **Rules:** FS1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. L0 = ln(S0), but service, `quantity_delivered 0.00`.
3. S = so "1", but finalized.

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=L0.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Sales order item {L0.id} not found"`.
3. unchanged: unchanged(L0).

### SS-FS-05 — a line of another W1 order: 400, checked before "requires delivery"
- **Rules:** FS2, FS3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. S2 = so "2", but finalized.
3. L2 = ln(S2), but `quantity_delivered 0.00` (requires delivery).

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=L2.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == f"Sales order item {L2.id} does not belong to sales order {S.id}"`.
3. nothing written: nothing written.

### SS-FS-06 — a line that requires delivery: 422, checked before the invoice
- **Rules:** FS3, FS5
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".
2. L1 = ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=L1.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "This line requires delivery — use the delivery workflow, not direct fulfillment"`.
3. nothing written: nothing written.

### SS-FS-07 — the invoice is not finalized: 422
- **Rules:** FS5
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Finalize the invoice before fulfilling this line"`.
3. unchanged: unchanged(LS).

### SS-FS-08 — an already fulfilled line still answers "marked as fulfilled"
- **Rules:** FS7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized, `is_fully_delivered True`.
2. V = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 2.00`, `unit_price 500.00`, `line_total 1000.00`.

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[0] == MSG("success", "Line item marked as fulfilled")`.
2. committed: LS has `quantity_delivered == Decimal("2.00")`.

### SS-FS-09 — a failing commit leaves the line unfulfilled
- **Rules:** FS7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 0.00`, `unit_price 500.00`, `line_total 1000.00`.

**When**
- `svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read LS: `quantity_delivered == Decimal("0.00")`.

## `SalesService._settle_replacement_credit_notes` — BUG-3217 (OQ-64), through `complete_delivery` / `fulfill_service_item`

### SS-SR-01 — the replacement delivery writes the settlement entry with its exact fields; committed
- **Rules:** SR1, SR2, SR3; DV6a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment is written)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN)[0]` has `payment_amount == Decimal("3000.00")`, `payment_method == "settled_by_replacement"`, `is_voided is False`, `workspace_id == W1.id`.
4. committed: `PAYS(CN)[0].payment_date == UTCDAY`.
5. committed: `PAYS(CN)[0].created_by == U2.id`.
6. committed: `PAYS(CN)[0].payment_reference == f"DEL-{TAG}-1"`.
7. committed: `PAYS(CN)[0].notes == f"Settled by replacement — DEL-{TAG}-1 for SR-{TAG}-1"`.

### SS-SR-02 — the credit note becomes paid and the return paid
- **Rules:** SR3 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (`paid_amount` stays 0.00)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: CN has `paid_amount == Decimal("3000.00")`, `payment_status == "paid"`.
3. committed: CN has `invoice_status == "confirmed"`, `invoice_amount == Decimal("3000.00")`.
4. committed: R1 has `paid is True`, `status == "completed"`.

### SS-SR-03 — one `return_replacement_settled` event on the order, with the links
- **Rules:** SR4, SR5 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no such event)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. event: `types(S).count("return_replacement_settled") == 1`.
3. event: that row has `description == f"Return SR-{TAG}-1 settled by replacement — 3000.00 taka credit cleared"`, `performed_by == U2.id`.
4. event: its `metadata_json == {"return_id": R1.id, "invoice_id": CN.id, "payment_id": PAYS(CN)[0].id, "delivery_id": D1.id}`.
5. event: `"delivery_completed" in types(S)`.

### SS-SR-04 — the settlement message is appended after the delivery messages
- **Rules:** SR6, DV6a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (only three messages)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `msgs[0] == MSG("success", f"Delivery DEL-{TAG}-1 marked as completed")`.
2. returns: `len(msgs) == 4`.
3. returns: `msgs[2] == MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")`.
4. returns: `msgs[3] == MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (3000.00)")`.

### SS-SR-05 — what holds today and after the fix: delivery, stock, one ledger row, order stays completed, no notification
- **Rules:** DV2, DV6, SR5, SR9; RK10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `msgs[:3] == [MSG("success", f"Delivery DEL-{TAG}-1 marked as completed"), MSG("info", "Inventory updated: 1 items, 1.00 units deducted"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")]`.
2. committed: D1 has `delivery_status == "delivered"`.
3. committed: L1 has `quantity_delivered == Decimal("4.00")`, `quantity_returned == Decimal("1.00")`.
4. committed: P1 has `qty == 99`.
5. committed: NEWLED is exactly one row: `transaction_type == "sale"`, `quantity == 1`, `source_type == "sales_delivery"`, `source_id == D1.id`.
6. committed: S has `order_completed is True`, `completed_at == T0`.
7. committed: CN has `invoice_status == "confirmed"`, `invoice_amount == Decimal("3000.00")`; R1 has `status == "completed"`.
8. committed: `"delivery_completed" in types(S)`.
9. committed: `notes() == []`.

### SS-SR-06 — the helper on its own: one message, entry flushed, never commits or rolls back
- **Rules:** SR3, SR6; Persistence (flush only) [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (the call raises AttributeError: the helper does not exist)

**Given**
1. SCENE, but L1 also `quantity_delivered 4.00` and D1 also delivered (the gap is already closed).

**When**
- `result = svc._settle_replacement_credit_notes(db, order=S, workspace_id=W1.id, user_id=U2.id, delivery=D1)`, inside **spies**.

**Then**
1. returns: `result == [MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (3000.00)")]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.new` (flushed).
5. count: `db.execute(select(func.count()).select_from(InvoicePayment).where(InvoicePayment.invoice_id == CN.id)).scalar() == 1`.

### SS-SR-07 — the amount is the credit note's half-up total (0.50 × 0.25 → 0.13)
- **Rules:** SR3; RC3; HR-15 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. SCENE, but L1 also free "Ribbon", `quantity_ordered 0.50`, `quantity_delivered 0.00`, `quantity_returned 0.50`, `unit_price 0.25`, `line_total 0.13`; CN = cn(S, "0.13") with invl(CN, 1, "0.13"); R1's line rl(R1, L1, "0.50"); D1's line dl(D1, L1, "0.50").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN)[0].payment_amount == Decimal("0.13")`.
4. returns: `msgs[-1] == MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (0.13)")`.
5. event: the `return_replacement_settled` row has `description == f"Return SR-{TAG}-1 settled by replacement — 0.13 taka credit cleared"`.

### SS-SR-08 — a partial redelivery settles nothing
- **Rules:** SR2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but L1 also `quantity_delivered 2.00`, `quantity_returned 2.00`; CN = cn(S, "6000.00") with invl(CN, 1, "6000.00"); R1's line rl(R1, L1, "2.00"); D1's line dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `msgs[2] == MSG("info", "1.00 units remaining to be delivered")`.
2. returns: `len(msgs) == 3`.
3. committed: L1 has `quantity_delivered == Decimal("3.00")`.
4. committed: `PAYS(CN) == []`.
5. committed: unchanged(CN).
6. committed: R1 has `paid is False`.
7. committed: `"return_replacement_settled" not in types(S)`.

### SS-SR-09 — the delivery that closes the last gap settles the whole credit note
- **Rules:** SR2, SR3 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. SCENE, but L1 also `quantity_delivered 3.00`, `quantity_returned 2.00`; CN = cn(S, "6000.00") with invl(CN, 1, "6000.00"); R1's line rl(R1, L1, "2.00"); D1's line dl(D1, L1, "1.00").
2. D0 = dlv(S, "0"), but delivered; dl(D0, L1, "1.00") (the earlier, partial redelivery).

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN)[0].payment_amount == Decimal("6000.00")`, `PAYS(CN)[0].payment_reference == f"DEL-{TAG}-1"`.
4. returns: `msgs[-1] == MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (6000.00)")`.

### SS-SR-10 — a refund return is never settled
- **Rules:** SR1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_ordered 5.00`, `quantity_delivered 3.00`, `quantity_returned 1.00`, `quantity_refunded 1.00`, `line_total 15000.00`.
4. CN = cn(S, "3000.00"); invl(CN, 1, "3000.00").
5. R1 = ret(S, "1"), but refund, done, of CN; rl(R1, L1, "1.00").
6. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. committed: L1 has `quantity_delivered == Decimal("4.00")`.
3. committed: `PAYS(CN) == []`.
4. committed: unchanged(CN).

### SS-SR-11 — a pending replace return is never settled
- **Rules:** SR1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but R1 also `status "pending"`, `completed_at None`, `completed_by None`; L1 also `quantity_returned 0.00`.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. committed: `PAYS(CN) == []`.
3. committed: unchanged(CN).
4. committed: R1 has `status == "pending"`, `paid is False`.

### SS-SR-12 — a voided replace return is never settled
- **Rules:** SR1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but R1 also voided, `completed_at None`, `completed_by None`.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. committed: `PAYS(CN) == []`.
3. committed: unchanged(CN).

### SS-SR-13 — a voided credit note gets a warning, nothing written
- **Rules:** SR1, SR1b [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (three messages, no warning)

**Given**
1. SCENE, but CN also voided-inv.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 4`.
2. returns: `msgs[3] == MSGD("warning", VOIDCN(R1), {"return_id": R1.id, "invoice_id": CN.id})`.
3. committed: `PAYS(CN) == []`.
4. committed: unchanged(CN).
5. committed: `"return_replacement_settled" not in types(S)`.

### SS-SR-14 — a draft credit note is skipped
- **Rules:** SR1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also draft.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. committed: `PAYS(CN) == []`.
3. committed: unchanged(CN).

### SS-SR-15 — a W0 credit note linked to the W1 return: an id-free warning, nothing paid
- **Rules:** SR1, SR1c [BUG-3217]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (three messages, no warning)

**Given**
1. SCENE, but CN also of W0.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 4`.
2. returns: `msgs[3] == MSGD("warning", LOSTCN(R1), {"return_id": R1.id})`.
3. returns: `str(CN.id) not in msgs[3].message`.
4. count: `invoice_payments` rows (all workspaces): exactly 0.
5. committed: unchanged(CN).
6. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-16 — a W2 credit note linked to the W1 return: an id-free warning, nothing paid
- **Rules:** SR1, SR1c [BUG-3217]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (three messages, no warning)

**Given**
1. SCENE, but CN also of W2.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 4`.
2. returns: `msgs[3] == MSGD("warning", LOSTCN(R1), {"return_id": R1.id})`.
3. returns: `str(CN.id) not in msgs[3].message`.
4. count: `invoice_payments` rows (all workspaces): exactly 0.
5. committed: unchanged(CN).
6. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-17 — a W0 return row under the W1 order is not settled
- **Rules:** SR1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
4. CN0 = cn(S, "3000.00"), but of W0; invl(CN0, 1, "3000.00").
5. R0 = ret(S, "0"), but of W0, done, of CN0; rl(R0, L1, "1.00").
6. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. count: `invoice_payments` rows (all workspaces): exactly 0.
3. committed: unchanged(CN0).
4. committed: unchanged(R0).

### SS-SR-18 — a W2 return row under the W1 order is not settled
- **Rules:** SR1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
4. CN9 = cn(S, "3000.00"), but of W2; invl(CN9, 1, "3000.00").
5. R9 = ret(S, "9"), but of W2, done, of CN9; rl(R9, L1, "1.00").
6. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. count: `invoice_payments` rows (all workspaces): exactly 0.
3. committed: unchanged(CN9).
4. committed: unchanged(R9).

### SS-SR-19 — only this workspace's return is settled when W0 and W2 rows sit beside it
- **Rules:** SR1; HR-16 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (R1 is not settled)

**Given**
1. SCENE.
2. CN0 = cn(S, "3000.00"), but of W0; R0 = ret(S, "0"), but of W0, done, of CN0; rl(R0, L1, "1.00").
3. CN9 = cn(S, "3000.00"), but of W2; R9 = ret(S, "9"), but of W2, done, of CN9; rl(R9, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN0) == []`.
4. committed: `PAYS(CN9) == []`.
5. committed: `types(S).count("return_replacement_settled") == 1`.
6. returns: exactly one entry of `msgs` has a text starting with `"Return "`.

### SS-SR-20 — money already refunded (partly): a warning, nothing written
- **Rules:** SR7 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no warning)

**Given**
1. SCENE, but CN also `paid_amount 1000.00`, `payment_status "partial"`.
2. pay(CN, "1000.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `msgs[-1] == MSG("warning", f"Return SR-{TAG}-1: the credit note already has 1000.00 refunded — the replacement was delivered too; settle it by hand")`.
3. returns: `msgs[-1].details == {"return_id": R1.id, "invoice_id": CN.id, "paid_amount": "1000.00"}` (the amount as two-place text).
4. committed: `len(PAYS(CN)) == 1`.
5. committed: unchanged(CN).

### SS-SR-21 — money already refunded (partly): nothing is written (today and after the fix)
- **Rules:** SR7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also `paid_amount 1000.00`, `payment_status "partial"`.
2. P = pay(CN, "1000.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has kind `"success"` and a text starting with `"Return "`.
2. committed: `[p.id for p in PAYS(CN)] == [P.id]`.
3. committed: unchanged(CN).
4. committed: unchanged(R1).
5. committed: `"return_replacement_settled" not in types(S)`.

### SS-SR-22 — money already refunded in full: a warning with the full amount
- **Rules:** SR7 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no warning)

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`.
2. pay(CN, "3000.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. returns: `msgs[-1] == MSG("warning", f"Return SR-{TAG}-1: the credit note already has 3000.00 refunded — the replacement was delivered too; settle it by hand")`.
3. committed: `len(PAYS(CN)) == 1`.

### SS-SR-23 — money already refunded in full: nothing is written (today and after the fix)
- **Rules:** SR7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`.
2. P = pay(CN, "3000.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. committed: `[p.id for p in PAYS(CN)] == [P.id]`.
2. committed: unchanged(CN).
3. committed: unchanged(R1).
4. committed: `"return_replacement_settled" not in types(S)`.

### SS-SR-24 — a voided refund does not count: the whole outstanding amount is settled
- **Rules:** SR3, SR7 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no new payment)

**Given**
1. SCENE.
2. P = pay(CN, "3000.00"), but voided pay (CN keeps `paid_amount 0.00`, `payment_status "unpaid"`).

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 2`.
3. committed: `PAYS(CN)[1]` has `payment_amount == Decimal("3000.00")`, `payment_method == "settled_by_replacement"`, `is_voided is False`.
4. committed: CN has `paid_amount == Decimal("3000.00")`, `payment_status == "paid"`.
5. returns: `msgs[-1] == MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (3000.00)")`.

### SS-SR-25 — an active settlement entry is never doubled and gives no warning
- **Rules:** SR1, SR8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`; R1 also `paid True`.
2. P = pay(CN, "3000.00"), but settle pay.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 3`.
2. returns: no entry of `msgs` has a text starting with `"Return "`.
3. committed: `[p.id for p in PAYS(CN)] == [P.id]`.
4. committed: unchanged(CN).
5. committed: `"return_replacement_settled" not in types(S)`.

### SS-SR-26 — a voided settlement entry makes the return count again: a new entry
- **Rules:** SR1, SR8 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no new payment)

**Given**
1. SCENE.
2. P = pay(CN, "3000.00"), but settle pay, voided pay (CN keeps `paid_amount 0.00`, `payment_status "unpaid"`).

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 2`.
3. committed: `PAYS(CN)[0].id == P.id`, `PAYS(CN)[0].is_voided is True`.
4. committed: `PAYS(CN)[1]` has `payment_method == "settled_by_replacement"`, `is_voided is False`, `created_by == U2.id`.

### SS-SR-27 — two fully replaced returns: two entries, events and messages, in return id order
- **Rules:** SR1, SR4, SR6 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. SCENE.
2. L2 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. CN2 = cn(S, "3000.00"); invl(CN2, 1, "3000.00").
4. R2 = ret(S, "2"), but done, of CN2; rl(R2, L2, "1.00").
5. dl(D1, L2, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`; `len(PAYS(CN2)) == 1`.
3. committed: `PAYS(CN)[0].id < PAYS(CN2)[0].id`.
4. event: `[e.metadata_json["return_id"] for e in EV(S) if e.event_type == "return_replacement_settled"] == [R1.id, R2.id]`.
5. returns: `msgs[-2:] == [MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (3000.00)"), MSG("success", f"Return SR-{TAG}-2: credit note settled by replacement (3000.00)")]`.

### SS-SR-28 — of two returns only the fully replaced one is settled
- **Rules:** SR2 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (R1 is not settled)

**Given**
1. SCENE.
2. L2 = ln(S), but `quantity_delivered 2.00`, `quantity_returned 2.00`.
3. CN2 = cn(S, "6000.00"); invl(CN2, 1, "6000.00").
4. R2 = ret(S, "2"), but done, of CN2; rl(R2, L2, "2.00").
5. dl(D1, L2, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN2) == []`.
4. returns: exactly one entry of `msgs` has a text starting with `"Return "`, and it names `SR-{TAG}-1`.

### SS-SR-29 — a return with one line still open is not settled
- **Rules:** SR2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN = cn(S, "6000.00") with invl(CN, 1, "6000.00").
2. L2 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. rl(R1, L2, "1.00") (R1's second line; D1 does not deliver L2).

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has a text starting with `"Return "`.
2. committed: `PAYS(CN) == []`.
3. committed: unchanged(CN).

### SS-SR-30 — a two-line return whose both gaps close is settled once, for its full note
- **Rules:** SR2, SR3 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. SCENE, but CN = cn(S, "6000.00") with invl(CN, 1, "3000.00") and invl(CN, 2, "3000.00").
2. L2 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. rl(R1, L2, "1.00").
4. dl(D1, L2, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN)[0].payment_amount == Decimal("6000.00")`.
4. committed: `types(S).count("return_replacement_settled") == 1`.

### SS-SR-31 — a failing settlement undoes the delivery too
- **Rules:** DV6a; TC3 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Author:** claude
- **Fails today on:** Then 1 (the call raises AttributeError: there is no helper to patch)

**Given**
1. SCENE.
2. X (after the commit point).

**When**
- SCENE-CALL inside `with pytest.raises(RuntimeError) as exc:` around `with patch.object(SalesService, "_settle_replacement_credit_notes", side_effect=RuntimeError("settle")):`.

**Then**
1. raises: `str(exc.value) == "settle"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. re-read D1: `delivery_status == "planned"`.
4. re-read L1: `quantity_delivered == Decimal("3.00")`.
5. re-read P1: `qty == 100`.
6. count: NEWLED is empty.
7. committed: x_gone.

### SS-SR-32 — a failing commit saves neither the delivery nor a settlement
- **Rules:** DV6a; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. SCENE.

**When**
- SCENE-CALL, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read D1: `delivery_status == "planned"`.
4. count: `PAYS(CN) == []`.
5. re-read CN: `paid_amount == Decimal("0.00")`.

### SS-SR-33 — direct fulfilment of a replaced service line settles with the line as link
- **Rules:** FS8a, SR3, SR4, SR6 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 1.00`, `quantity_returned 1.00`, `unit_price 500.00`, `line_total 1000.00`.
4. CN = cn(S, "500.00"); invl(CN, 1, "500.00").
5. R1 = ret(S, "1"), but done, of CN; rl(R1, LS, "1.00").

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CN)[0]` has `payment_amount == Decimal("500.00")`, `payment_method == "settled_by_replacement"`, `payment_date == UTCDAY`, `created_by == U2.id`.
4. committed: `PAYS(CN)[0].payment_reference == f"SO-item-{LS.id}"`.
5. committed: `PAYS(CN)[0].notes == f"Settled by replacement — direct fulfilment for SR-{TAG}-1"`.
6. event: the `return_replacement_settled` row's `metadata_json == {"return_id": R1.id, "invoice_id": CN.id, "payment_id": PAYS(CN)[0].id, "delivery_id": None}`.
7. returns: `msgs == [MSG("success", "Line item marked as fulfilled"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered"), MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (500.00)")]`.

### SS-SR-34 — direct refulfilment of a replaced line on a completed order (today and after the fix)
- **Rules:** FS8, FS7
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 1.00`, `quantity_returned 1.00`, `unit_price 500.00`, `line_total 1000.00`.
4. CN = cn(S, "500.00"); invl(CN, 1, "500.00").
5. R1 = ret(S, "1"), but done, of CN; rl(R1, LS, "1.00").

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[:2] == [MSG("success", "Line item marked as fulfilled"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")]`.
2. committed: LS has `quantity_delivered == Decimal("2.00")`.
3. committed: S has `order_completed is True`.
4. committed: NEWLED is empty; S has 0 `sales_deliveries` rows.
5. committed: `notes() == []`.

### SS-SR-35 — refunded units count toward "fully replaced"; the refund return's note is left alone
- **Rules:** SR1, SR2 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 2 (no payment)

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 2.00`, `quantity_returned 2.00`, `quantity_refunded 1.00`.
4. CNr = cn(S, "3000.00"); invl(CNr, 1, "3000.00"); Rr = ret(S, "0"), but refund, done, of CNr; rl(Rr, L1, "1.00").
5. CN = cn(S, "3000.00"); invl(CN, 1, "3000.00"); R1 = ret(S, "1"), but done, of CN; rl(R1, L1, "1.00").
6. D1 = dlv(S, "1"); dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `order.id == S.id`.
2. committed: `len(PAYS(CN)) == 1`.
3. committed: `PAYS(CNr) == []`.
4. committed: unchanged(CNr).

### SS-SR-36 — completing a replace return does not settle its credit note
- **Rules:** RK10, SR2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. CN = cn(S, "3000.00"); invl(CN, 1, "3000.00").
5. R1 = ret(S, "1"), but of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == R1.id`.
2. committed: R1 has `status == "completed"`, `paid is False`.
3. committed: `PAYS(CN) == []`.
4. committed: CN has `invoice_status == "confirmed"`, `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
5. committed: S has `order_completed is True`.

### SS-SR-37 — a voided credit note: nothing is written for it and the delivery goes through (today and after the fix)
- **Rules:** SR1, SR1b; DV2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also voided-inv.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `msgs[:3] == [MSG("success", f"Delivery DEL-{TAG}-1 marked as completed"), MSG("info", "Inventory updated: 1 items, 1.00 units deducted"), MSG("success", f"Sales order SO-{TAG}-1 is now fully delivered")]`.
2. returns: no entry of `msgs` has kind `"success"` and a text starting with `"Return "`.
3. committed: `PAYS(CN) == []`.
4. committed: unchanged(CN).
5. committed: R1 has `paid is False`, `status == "completed"`.
6. committed: `"return_replacement_settled" not in types(S)`.
7. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-38 — a W0 credit note: not locked, not paid, the delivery goes through (today and after the fix)
- **Rules:** SR1, SR1c; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SCENE, but CN also of W0.
2. `cnid, did = CN.id, D1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=did, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has kind `"success"` and a text starting with `"Return "`.
2. statement: cnlock(CN) is None (W0's note is never read for update).
3. count: `invoice_payments` rows (all workspaces): exactly 0.
4. committed: unchanged(CN).
5. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-39 — a W2 credit note: not locked, not paid, the delivery goes through (today and after the fix)
- **Rules:** SR1, SR1c; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SCENE, but CN also of W2.
2. `cnid, did = CN.id, D1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=did, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: no entry of `msgs` has kind `"success"` and a text starting with `"Return "`.
2. statement: cnlock(CN) is None (W2's note is never read for update).
3. count: `invoice_payments` rows (all workspaces): exactly 0.
4. committed: unchanged(CN).
5. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-40 — the voided-note warning is repeated on the next delivery
- **Rules:** SR1b [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no warning)

**Given**
1. SCENE, but CN also voided-inv.
2. L2 = ln(S), but `quantity_delivered 3.00`; D2 = dlv(S, "2"); dl(D2, L2, "1.00").
3. SCENE-CALL (a Given step, after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=D2.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[-1] == MSGD("warning", VOIDCN(R1), {"return_id": R1.id, "invoice_id": CN.id})`.
2. returns: exactly one entry of `msgs` has a text starting with `"Return "`.
3. committed: `PAYS(CN) == []`.

### SS-SR-41 — the lost-note warning is repeated on the next delivery
- **Rules:** SR1c [BUG-3217]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no warning)

**Given**
1. SCENE, but CN also of W2.
2. L2 = ln(S), but `quantity_delivered 3.00`; D2 = dlv(S, "2"); dl(D2, L2, "1.00").
3. SCENE-CALL (a Given step, after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=D2.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. returns: `msgs[-1] == MSGD("warning", LOSTCN(R1), {"return_id": R1.id})`.
2. returns: `str(CN.id) not in msgs[-1].message`.
3. count: `invoice_payments` rows (all workspaces): exactly 0.

### SS-SR-42 — a voided credit note of a return not yet fully replaced: no message
- **Rules:** SR1b, SR2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN = cn(S, "6000.00"), but voided-inv, with invl(CN, 1, "6000.00"); L1 also `quantity_delivered 2.00`, `quantity_returned 2.00`; R1's line rl(R1, L1, "2.00"); D1's line dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 3`.
2. returns: no entry of `msgs` has a text starting with `"Return "`.
3. committed: `PAYS(CN) == []`.
4. committed: unchanged(CN).

### SS-SR-43 — a W2 credit note of a return not yet fully replaced: no message
- **Rules:** SR1c, SR2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SCENE, but CN = cn(S, "6000.00"), but of W2, with invl(CN, 1, "6000.00"); L1 also `quantity_delivered 2.00`, `quantity_returned 2.00`; R1's line rl(R1, L1, "2.00"); D1's line dl(D1, L1, "1.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 3`.
2. returns: no entry of `msgs` has a text starting with `"Return "`.
3. count: `invoice_payments` rows (all workspaces): exactly 0.
4. committed: unchanged(CN).

### SS-SR-44 — the settlement leaves one financial audit row, as any payment
- **Rules:** SR3a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no payment)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`; call it P.
2. committed: `len(AUD(P.id)) == 1`.
3. committed: `AUD(P.id)[0]` has `action_type == "created"`, `related_entity_type == "invoice"`, `related_entity_id == CN.id`, `performed_by == U2.id`, `workspace_id == W1.id`.
4. committed: its `changes["after"]` has `Decimal(str(payment_amount)) == Decimal("3000.00")`, `payment_date == "2026-09-27"`, `payment_method == "settled_by_replacement"`.
5. committed: its `changes["invoice_status_changed"] == {"before": "unpaid", "after": "paid"}`.

### SS-SR-45 — the settlement leaves one `payment_recorded` invoice event
- **Rules:** SR3a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no such event)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. committed: `itypes(CN).count("payment_recorded") == 1`.
2. committed: that row has `description == "Payment recorded"`, `performed_by == U2.id`.
3. committed: its `metadata_json == {"payment_id": SETTLE(CN)[0].id, "payment_amount": "3000.00", "payment_method": "settled_by_replacement", "payment_status_before": "unpaid", "payment_status_after": "paid"}`.

### SS-SR-46 — a payment lock on the credit note does not stop the settlement
- **Rules:** SR3a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no payment)

**Given**
1. SCENE, but CN also `allow_payments False`, `payment_locked_reason "Held by finance"`.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`; `SETTLE(CN)[0].payment_amount == Decimal("3000.00")`.
2. committed: CN has `paid_amount == Decimal("3000.00")`, `payment_status == "paid"`, `allow_payments is False`.
3. returns: `msgs[-1] == MSG("success", f"Return SR-{TAG}-1: credit note settled by replacement (3000.00)")`.
4. returns: no entry of `msgs` has kind `"warning"`.

### SS-SR-47 — a payment-locked credit note: the delivery still completes (today and after the fix)
- **Rules:** SR3a; DV2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN also `allow_payments False`, `payment_locked_reason "Held by finance"`.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `msgs[0] == MSG("success", f"Delivery DEL-{TAG}-1 marked as completed")`.
2. committed: D1 has `delivery_status == "delivered"`.
3. committed: L1 has `quantity_delivered == Decimal("4.00")`.
4. committed: P1 has `qty == 99`.

### SS-SR-48 — the entry is linked to the settlement event (`sales_order_event`)
- **Rules:** SR3c, SR4 [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no payment)

**Given**
1. SCENE.

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`; call it P.
2. committed: E = the one row of EV(S) with `event_type == "return_replacement_settled"`.
3. committed: P has `source_type == "sales_order_event"`, `source_id == E.id`.
4. committed: `E.metadata_json["payment_id"] == P.id`, `E.metadata_json["delivery_id"] == D1.id`.

### SS-SR-49 — a direct fulfilment links the entry the same way, with no delivery
- **Rules:** SR3c, FS8a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no payment)

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. LS = ln(S), but service, `quantity_ordered 2.00`, `quantity_delivered 1.00`, `quantity_returned 1.00`, `unit_price 500.00`, `line_total 1000.00`.
4. CN = cn(S, "500.00"); invl(CN, 1, "500.00").
5. R1 = ret(S, "1"), but done, of CN; rl(R1, LS, "1.00").

**When**
- `result = svc.fulfill_service_item(db, order_id=S.id, order_item_id=LS.id, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`; call it P.
2. committed: E = the one row of EV(S) with `event_type == "return_replacement_settled"`.
3. committed: P has `source_type == "sales_order_event"`, `source_id == E.id`.
4. committed: `E.metadata_json["delivery_id"] is None`.

### SS-SR-50 — a 0.00 credit note: no entry, no event, no message (today and after the fix)
- **Rules:** SR3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SCENE, but CN = cn(S, "0.00"), but `payment_status "paid"`, with invl(CN, 1, "0.00").

**When**
- SCENE-CALL; `order, msgs = result`.

**Then**
1. returns: `len(msgs) == 3`.
2. returns: no entry of `msgs` has a text starting with `"Return "`.
3. committed: `PAYS(CN) == []`.
4. committed: unchanged(CN).
5. committed: `"return_replacement_settled" not in types(S)`.
6. committed: D1 has `delivery_status == "delivered"`.

### SS-SR-51 — the credit note is locked before its payments are looked at
- **Rules:** SR1a [BUG-3217]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no `FOR UPDATE` on `account_invoices`)

**Given**
1. SCENE.
2. `cnid, did = CN.id, D1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=did, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. statement: cnlock(CN) is not None.
2. statement: payread(CN) is None or `cnlock(CN) < payread(CN)`.
3. committed: `len(SETTLE(CN)) == 1`.

### SS-SR-52 — two credit notes are locked in return id order
- **Rules:** SR1a [BUG-3217]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no lock at all)

**Given**
1. S = so "1", but finalized, completed.
2. VR = inv(S), but confirmed, linked.
3. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`; L2 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
4. CNb = cn(S, "3000.00"); invl(CNb, 1, "3000.00") (inserted first, so its id is the lower one).
5. CNa = cn(S, "3000.00"); invl(CNa, 1, "3000.00").
6. R1 = ret(S, "1"), but done, of CNa; rl(R1, L1, "1.00").
7. R2 = ret(S, "2"), but done, of CNb; rl(R2, L2, "1.00").
8. D1 = dlv(S, "1"); dl(D1, L1, "1.00"); dl(D1, L2, "1.00").
9. `did = D1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_delivery(db, delivery_id=did, workspace_id=W1.id, current_user=CU)`; `order, msgs = result`.

**Then**
1. statement: cnlock(CNa) is not None and cnlock(CNb) is not None.
2. statement: `cnlock(CNa) < cnlock(CNb)` (R1's note first: R1.id < R2.id although CNa.id > CNb.id).

### SS-SR-53 — a settlement entry cannot be deleted
- **Rules:** SR8a [BUG-3217] (refusal in the invoice payment manager)
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no error: the entry is deleted) or, once BUG-609 lands, Then 2 (its general text)

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`; R1 also `paid True`.
2. P = pay(CN, "3000.00"), but settle pay.

**When**
- `sp = db.begin_nested()`; `ipm.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NODEL`.
3. count: `invoice_payments` rows with `id == P.id`: exactly 1.
4. re-read CN: `paid_amount == Decimal("3000.00")`, `payment_status == "paid"`.

### SS-SR-54 — a settlement entry's notes cannot be edited
- **Rules:** SR8a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no error: the note is changed)

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`; R1 also `paid True`.
2. P = pay(CN, "3000.00"), but settle pay, `notes "Settled"`.

**When**
- `sp = db.begin_nested()`; `ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(notes="edited"), workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NODEL`.
3. re-read P: `notes == "Settled"`, `payment_method == "settled_by_replacement"`.

### SS-SR-55 — a settlement entry's method cannot be changed to cash
- **Rules:** SR8a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no error: the method is changed)

**Given**
1. SCENE, but CN also `paid_amount 3000.00`, `payment_status "paid"`; R1 also `paid True`.
2. P = pay(CN, "3000.00"), but settle pay, `payment_reference "DEL-X"`.

**When**
- `sp = db.begin_nested()`; `ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(payment_method="cash", payment_reference="CASH-1", payment_date=date(2026, 9, 5)), workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NODEL`.
3. re-read P: `payment_method == "settled_by_replacement"`, `payment_reference == "DEL-X"`, `payment_date == date(2026, 9, 2)`.

### SS-SR-56 — the entry written by a delivery refuses deletion
- **Rules:** SR3, SR8a [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Given 2 (no settlement entry: `SETTLE(CN)[0]` raises IndexError)

**Given**
1. SCENE.
2. SCENE-CALL (a Given step, after the commit point); P = `SETTLE(CN)[0]`.

**When**
- `sp = db.begin_nested()`; `ipm.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == NODEL`.
3. count: `invoice_payments` rows with `id == P.id`: exactly 1.

### SS-SR-57 — the reserved method cannot be entered by hand on a new payment
- **Rules:** SR8c [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no error: the payment is recorded)

**Given**
1. SCENE.

**When**
- `sp = db.begin_nested()`; `ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=CN.id, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, 2), payment_method="settled_by_replacement"), workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == RESERVED`.
3. committed: `PAYS(CN) == []`.
4. re-read CN: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### SS-SR-58 — a cash payment cannot be re-labelled with the reserved method
- **Rules:** SR8c [BUG-3217]
- **Kind:** bug
- **Expect:** xfail BUG-3217
- **Fails today on:** Then 1 (no error: the method is changed)

**Given**
1. SCENE, but CN also `paid_amount 1000.00`, `payment_status "partial"`.
2. P = pay(CN, "1000.00").

**When**
- `sp = db.begin_nested()`; `ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(payment_method="settled_by_replacement"), workspace_id=W1.id, user_id=U2.id)` inside `raises: HTTPException`; then `sp.rollback()` unless the savepoint has already been rolled back or committed (not `if sp.is_active`; see Invoice payment manager calls).

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == RESERVED`.
3. re-read P: `payment_method == "cash"`.

### SS-SR-59 — voiding a settlement entry makes the note owed again and the return unpaid; no stock moves
- **Rules:** SR8, SR8b (holds today and after BUG-3217)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SCENE, but L1 also `quantity_delivered 4.00`, D1 also delivered; CN also `paid_amount 3000.00`, `payment_status "paid"`; R1 also `paid True`.
2. P = pay(CN, "3000.00"), but settle pay.

**When**
- `ipm.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong delivery")`.

**Then**
1. re-read P: `is_voided is True`, `voided_by == U2.id`, `void_note == "Wrong delivery"`, `voided_at is not None`.
2. re-read CN: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`, `invoice_status == "confirmed"`.
3. re-read R1: `paid is False`, `status == "completed"`.
4. event: `itypes(CN).count("payment_voided") == 1`.
5. count: AUD(P.id) has exactly 1 row with `action_type == "voided"`.
6. count: NEWLED is empty; P1 has `qty == 100`.

## `SalesService.get_deliveries_for_order`

### SS-GD-01 — the order's deliveries of every status; W0 / W2 rows left out; no commit or rollback
- **Rules:** GD1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. D0 = dlv(S, "0"), but `workspace_id W0.id`.
3. Da = dlv(S, "1"), but delivered.
4. Db = dlv(S, "2"), but `delivery_status "cancelled"`.
5. Dc = dlv(S, "3").
6. D9 = dlv(S, "9"), but `workspace_id W2.id`.
7. X (after the commit point).

**When**
- `result = svc.get_deliveries_for_order(db, sales_order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `len(result) == 3`; `idset(result) == {Da.id, Db.id, Dc.id}` (order in SS-GD-04).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-GD-02 — another workspace's order: 404
- **Rules:** GD2 [BUG-3213]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3213
- **Fails today on:** Then 1 (`[]` is returned)

**Given**
1. S9 = so "9", but of W2.
2. dlv(S9, "9").

**When**
- `svc.get_deliveries_for_order(db, sales_order_id=S9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S9.id)`.

### SS-GD-03 — an unknown order: 404
- **Rules:** GD2 [BUG-3213]
- **Kind:** bug
- **Expect:** xfail BUG-3213
- **Fails today on:** Then 1 (`[]`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.get_deliveries_for_order(db, sales_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-GD-04 — the order's deliveries come back in id order
- **Rules:** GD1 [BUG-2442]
- **Kind:** bug
- **Expect:** xfail BUG-2442
- **Fails today on:** Then 1 (no `ORDER BY sales_deliveries.id`; Gap log G16)

**Given**
1. S = so "1", but finalized.
2. Da = dlv(S, "1"), but delivered.
3. Db = dlv(S, "2"), but `delivery_status "cancelled"`.
4. Dc = dlv(S, "3").

**When**
- `result = svc.get_deliveries_for_order(db, sales_order_id=S.id, workspace_id=W1.id)`, Statement recorder on.

**Then**
1. statement: id order on `sales_deliveries`.
2. returns: `[d.id for d in result] == [Da.id, Db.id, Dc.id]`.

## `SalesService.get_sales_order_items`

### SS-GI-01 — the order's lines of this workspace only; no commit or rollback
- **Rules:** GI1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. L0 = ln(S), but `workspace_id W0.id`.
3. La = ln(S), but `quantity_ordered 2.00`, `line_total 6000.00`.
4. Lb = ln(S).
5. L9 = ln(S), but `workspace_id W2.id`.
6. X (after the commit point).

**When**
- `result = svc.get_sales_order_items(db, sales_order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `len(result) == 2`; `idset(result) == {La.id, Lb.id}` (order in SS-GI-03).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-GI-02 — another workspace's order: 404
- **Rules:** GI2 [BUG-3213]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3213
- **Fails today on:** Then 1 (`[]`)

**Given**
1. S0 = so "0", but of W0.
2. ln(S0).

**When**
- `svc.get_sales_order_items(db, sales_order_id=S0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S0.id)`.

### SS-GI-03 — the order's lines come back in id order
- **Rules:** GI1 [BUG-1270]
- **Kind:** bug
- **Expect:** xfail BUG-1270
- **Fails today on:** Then 1 (no `ORDER BY sales_order_items.id`; Gap log G16)

**Given**
1. S = so "1".
2. La = ln(S), but `quantity_ordered 2.00`, `line_total 6000.00`.
3. Lb = ln(S).
4. Lc = ln(S), but free "Ribbon".

**When**
- `result = svc.get_sales_order_items(db, sales_order_id=S.id, workspace_id=W1.id)`, Statement recorder on.

**Then**
1. statement: id order on `sales_order_items`.
2. returns: `[l.id for l in result] == [La.id, Lb.id, Lc.id]`.

## `SalesService.get_delivery`

### SS-GV-01 — returns the delivery; no commit or rollback
- **Rules:** GV1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. D1 = dlv(S, "1").
3. X (after the commit point).

**When**
- `result = svc.get_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == D1.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-GV-02 — an unknown delivery: NotFoundError 404
- **Rules:** GV1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no deliveries.

**When**
- `svc.get_delivery(db, delivery_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(MISSING)`.

### SS-GV-03 — a W2 delivery: NotFoundError 404
- **Rules:** GV1 [BUG-3197]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. S9 = so "9", but of W2.
2. D9 = dlv(S9, "9").

**When**
- `svc.get_delivery(db, delivery_id=D9.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(D9.id)`.

### SS-GV-04 — not found neither commits nor rolls back (today and after the fix)
- **Rules:** GV1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. D0 = dlv(S0, "0").
3. X (after the commit point).

**When**
- `svc.get_delivery(db, delivery_id=D0.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `Exception` (any type).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

## `SalesService.get_deliveries`

### SS-LD-01 — a status filter: exact match, this workspace only; no commit or rollback
- **Rules:** LD1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. S0 = so "0", but of W0; dlv(S0, "0"), but delivered.
3. Da = dlv(S, "1"), but delivered.
4. dlv(S, "2").
5. Db = dlv(S, "3"), but delivered.
6. S9 = so "9", but of W2; dlv(S9, "9"), but delivered.
7. X (after the commit point).

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="delivered")`, inside **spies**.

**Then**
1. returns: `len(result) == 2`; `idset(result) == {Da.id, Db.id}` (order in SS-LD-09).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-LD-02 — `None` means no filter
- **Rules:** LD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. Da = dlv(S, "1"), but delivered.
3. Db = dlv(S, "2").
4. S9 = so "9", but of W2; dlv(S9, "9").

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status=None)`.

**Then**
1. returns: `len(result) == 2`; `idset(result) == {Da.id, Db.id}`.

### SS-LD-03 — `""` means no filter
- **Rules:** LD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. Da = dlv(S, "1"), but delivered.
3. Db = dlv(S, "2").

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="")`.

**Then**
1. returns: `len(result) == 2`; `idset(result) == {Da.id, Db.id}`.

### SS-LD-04 — the filter is exact: `"Delivered"` matches nothing at the service
- **Rules:** LD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. dlv(S, "1"), but delivered.

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="Delivered")`.

**Then**
1. returns: `result == []`.

### SS-LD-05 — skip and limit on the filtered list
- **Rules:** LD1 [BUG-2443]
- **Kind:** bug
- **Expect:** xfail BUG-2443
- **Fails today on:** Then 1 (the status-filtered read has no `ORDER BY sales_deliveries.id`; Gap log G16)

**Given**
1. S = so "1".
2. D1 … D4 = dlv(S, "1") … dlv(S, "4"), each but delivered, in that order.
3. dlv(S, "5") (planned).

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="delivered", skip=1, limit=2)`, Statement recorder on.

**Then**
1. statement: id order on `sales_deliveries`.
2. returns: `[d.id for d in result] == [D2.id, D3.id]`.

### SS-LD-06 — skip and limit on the unfiltered list
- **Rules:** LD1 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 1 (BaseDAO `get_by_workspace` sends no `ORDER BY`; Gap log G16)

**Given**
1. S = so "1".
2. D1 … D4 = dlv(S, "1") … dlv(S, "4"), in that order.

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, skip=1, limit=2)`, Statement recorder on.

**Then**
1. statement: id order on `sales_deliveries`.
2. returns: `[d.id for d in result] == [D2.id, D3.id]`.

### SS-LD-07 — no limit given: at most 100
- **Rules:** LD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. 101 deliveries dlv(S, "1") … dlv(S, "101") in W1.

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### SS-LD-08 — limit=1000 is passed on
- **Rules:** LD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. 101 deliveries dlv(S, "1") … dlv(S, "101") in W1.

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### SS-LD-09 — the status-filtered list comes back in id order
- **Rules:** LD1 [BUG-2443]
- **Kind:** bug
- **Expect:** xfail BUG-2443
- **Fails today on:** Then 1 (no `ORDER BY sales_deliveries.id`; Gap log G16)

**Given**
1. S = so "1".
2. Da = dlv(S, "1"), but delivered.
3. dlv(S, "2").
4. Db = dlv(S, "3"), but delivered.
5. Dc = dlv(S, "4"), but delivered.

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="delivered")`, Statement recorder on.

**Then**
1. statement: id order on `sales_deliveries`.
2. returns: `[d.id for d in result] == [Da.id, Db.id, Dc.id]`.

### SS-LD-10 — skip and limit on the filtered list give two delivered rows of this workspace (today and after the fix)
- **Rules:** LD1 (holds before and after BUG-2443)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. D1 … D4 = dlv(S, "1") … dlv(S, "4"), each but delivered, in that order.
3. dlv(S, "5") (planned).

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, delivery_status="delivered", skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {D1.id, D2.id, D3.id, D4.id}`; every row has `delivery_status == "delivered"`.

### SS-LD-11 — skip and limit on the unfiltered list give two rows of this workspace (today and after the fix)
- **Rules:** LD1 (holds before and after BUG-100)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. D1 … D4 = dlv(S, "1") … dlv(S, "4"), in that order.
3. S9 = so "9", but of W2; dlv(S9, "9").

**When**
- `result = svc.get_deliveries(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {D1.id, D2.id, D3.id, D4.id}`.

## `SalesService.get_delivery_items`

### SS-GDI-01 — the delivery's lines of this workspace only; no commit or rollback
- **Rules:** GDI1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. D1 = dlv(S, "1").
4. dl(D1, L1, "9.00"), but `workspace_id W0.id`.
5. Ia = dl(D1, L1, "1.00").
6. Ib = dl(D1, L1, "2.00").
7. dl(D1, L1, "8.00"), but `workspace_id W2.id`.
8. X (after the commit point).

**When**
- `result = svc.get_delivery_items(db, delivery_id=D1.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `len(result) == 2`; `idset(result) == {Ia.id, Ib.id}` (order in SS-GDI-03).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-GDI-02 — another workspace's delivery: NotFoundError 404
- **Rules:** GDI2 [BUG-3213]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3213
- **Fails today on:** Then 1 (`[]` is returned)

**Given**
1. S9 = so "9", but of W2.
2. D9 = dlv(S9, "9").

**When**
- `svc.get_delivery_items(db, delivery_id=D9.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == DNF(D9.id)`.

### SS-GDI-03 — the delivery's lines come back in id order
- **Rules:** GDI1 [BUG-1271]
- **Kind:** bug
- **Expect:** xfail BUG-1271
- **Fails today on:** Then 1 (no `ORDER BY sales_delivery_items.id`; Gap log G16)

**Given**
1. S = so "1".
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. D1 = dlv(S, "1").
4. Ia = dl(D1, L1, "1.00").
5. Ib = dl(D1, L1, "2.00").
6. Ic = dl(D1, L1, "1.00").

**When**
- `result = svc.get_delivery_items(db, delivery_id=D1.id, workspace_id=W1.id)`, Statement recorder on.

**Then**
1. statement: id order on `sales_delivery_items`.
2. returns: `[i.id for i in result] == [Ia.id, Ib.id, Ic.id]`.

## `SalesService._attach_return_invoice_for_so`

### SS-RC-01 — the helper creates, links and confirms the credit note; never commits or rolls back
- **Rules:** RC1, RC2, RC4, RC5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R = ret(S, "1"), but `reason "Broken leg"`; rl(R, L1, "1.00").

**When**
- `svc._attach_return_invoice_for_so(db, order=S, ret=R, workspace_id=W1.id, user_id=U2.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. re-read R: `invoice_id is not None`.
4. re-read C = `db.get(AccountInvoice, R.invoice_id)`: `invoice_type == "payable"`, `invoice_status == "confirmed"`, `account_id == A1.id`, `order_type == "sales_order"`, `order_id == S.id`, `allow_payments is True`.
5. re-read C: `description == f"Return credit note for SO-{TAG}-1 (SR-{TAG}-1)"`, `notes == "Broken leg"`.
6. count: `"confirmed" in itypes(C)`.
7. count: S has exactly 0 `sales_order_events` rows.

## `SalesService.start_return`

### SS-RS-01 — a refund return is created with its line, committed and returned re-read
- **Rules:** RS1, RS5, RS8; TC1, TC2; N5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.sales_order_id == S.id`.
3. committed: the return has `status == "pending"`, `return_type == "refund"`, `reason == "Broken"`, `created_by == U2.id`, `workspace_id == W1.id`, `return_number.startswith("SR-")`.
4. committed: its lines are exactly one: `so_item_id == L1.id`, `quantity_returned == Decimal("1.00")`, `workspace_id == W1.id`.
5. committed: L1 has `quantity_delivered == Decimal("4.00")`, `quantity_returned == Decimal("0.00")`.
6. committed: P1 has `qty == 100`.
7. committed: `notes() == []`.

### SS-RS-02 — the credit note: confirmed payable, linked, one line per return line
- **Rules:** RS6, RC1, RC2, RC3, RC4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. L2 = ln(S), but free "Ribbon", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 0.25`, `line_total 0.25`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00")), SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("0.50"))]))`.

**Then**
1. committed: the return's `invoice_id` names C with `invoice_type == "payable"`, `invoice_status == "confirmed"`, `account_id == A1.id`, `order_id == S.id`, `allow_payments is True`.
2. committed: C has `description == f"Return credit note for SO-{TAG}-1 ({result.return_number})"`, `notes == "Broken"`.
3. committed: `sorted(l.line_number for l in LINES(C)) == [1, 2]` (which line is number 1 is an order question: SS-RS-23).
4. committed: the line of C with `source_order_item_id == L1.id` has `description == "Chair"`, `item_id == I1.id`, `source_order_item_type == "so_item"`, `quantity == Decimal("1.00")`, `unit == "pcs"`, `unit_price == Decimal("3000.00")`, `line_subtotal == Decimal("3000.00")`.
5. committed: the line of C with `source_order_item_id == L2.id` has `description == "Ribbon"`, `item_id is None`, `unit is None`, `quantity == Decimal("0.50")`, `line_subtotal == Decimal("0.13")`.
6. committed: C has `invoice_amount == Decimal("3000.13")`.
7. committed: `"confirmed" in itypes(C)`.

### SS-RS-03 — each credit-note line is rounded half up and the amount is their sum
- **Rules:** RC3; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. La = ln(S), but free "Ribbon", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 0.25`, `line_total 0.25`.
4. Lb = ln(S), but free "Tape", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 0.25`, `line_total 0.25`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=La.id, quantity_returned=Decimal("0.50")), SalesOrderReturnItemCreate(so_item_id=Lb.id, quantity_returned=Decimal("0.50"))]))`.

**Then**
1. committed: both lines of the return's credit note have `line_subtotal == Decimal("0.13")`.
2. committed: the credit note has `invoice_amount == Decimal("0.26")`.

### SS-RS-04 — the credit note is dated with the UTC day
- **Rules:** RC1 [BUG-3196]
- **Kind:** bug
- **Expect:** xfail BUG-3196
- **Fails today on:** Then 2 (`date.today()`)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: the credit note has `invoice_date == UTCDAY`.

### SS-RS-05 — no `invoice_amount` is sent for the credit note
- **Rules:** RC1 [BUG-627]
- **Kind:** bug
- **Expect:** xfail BUG-627
- **Author:** claude
- **Fails today on:** Then 2 (`invoice_amount = 0.00` is sent)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`, inside `patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci`.

**Then**
1. mock called: `ci.call_count == 1`.
2. mock called: the invoice data passed to `ci` did not set `invoice_amount`.

### SS-RS-06 — one `return_started` event
- **Rules:** RS7, RC5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. L2 = ln(S), but `quantity_ordered 2.00`, `quantity_delivered 2.00`, `line_total 6000.00`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00")), SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("2.00"))]))`.

**Then**
1. committed: `types(S) == ["return_started"]`.
2. committed: that event has `description == f"Return {result.return_number} started — refund (3.00 unit(s) across 2 item(s))"`, `performed_by == U2.id`.
3. committed: its `metadata_json == {"return_id": result.id, "invoice_id": result.invoice_id, "return_type": "refund"}`.

### SS-RS-07 — nothing delivered yet: 400, nothing written, extra row gone
- **Rules:** RS2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. X (after the commit point).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "No items have been delivered or fulfilled yet — nothing to return"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### SS-RS-08 — a delivered W2 line under the order does not count as delivered
- **Rules:** RS2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `quantity_delivered 0.00`.
3. L9 = ln(S), but `workspace_id W2.id`.

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "No items have been delivered or fulfilled yet — nothing to return"`.
3. nothing written: nothing written.

### SS-RS-09 — the return manager's refusal passes and nothing is written
- **Rules:** RS3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. S2 = so "2", but finalized; L2 = ln(S2).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == f"Item {L2.id} does not belong to this sales order"`.
3. nothing written: nothing written.

### SS-RS-10 — a return on a completed order keeps it completed
- **Rules:** RS4 [BUG-2790]
- **Kind:** bug
- **Expect:** xfail BUG-2790
- **Fails today on:** Then 2 (the order is reopened)

**Given**
1. S = so "1", but finalized, completed.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="replace", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. returns: `result.status == "pending"`.
2. committed: S has `order_completed is True`, `completed_at == T0`, `completed_by == U1.id`.
3. committed: `"order_reopened" not in types(S)`.
4. committed: `HOR(S) is True`.

### SS-RS-11 — a return on an order that is not completed leaves its completion alone
- **Rules:** RS4, RS8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. returns: `result.status == "pending"`.
2. committed: S has `order_completed is False`, `completed_at is None`.

### SS-RS-12 — a `replace` return gets the same confirmed payable credit note
- **Rules:** RS9, RC1, RC4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="replace", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. returns: `result.return_type == "replace"`.
2. committed: the credit note has `invoice_type == "payable"`, `invoice_status == "confirmed"`, `payment_status == "unpaid"`, `invoice_amount == Decimal("3000.00")`.
3. committed: `PAYS(result.invoice_id) == []`.

### SS-RS-13 — invoices not allowed for the account: 403, the whole start undone
- **Rules:** RC1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. After the commit point: `A1.allow_invoices = False`; `db.flush()`; then X.

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 403`.
2. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. count: S has exactly 0 `sales_order_returns` rows.
5. nothing written: nothing written.
6. committed: x_gone.

### SS-RS-14 — a deleted account: 400, nothing written
- **Rules:** RC1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. `A1.is_deleted = True`; `db.flush()`.

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot create invoice for deleted account"`.
3. nothing written: nothing written.

### SS-RS-15 — an inactive account: 400, nothing written
- **Rules:** RC1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. `A1.is_active = False`; `db.flush()`.

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot create invoice for inactive account"`.
3. nothing written: nothing written.

### SS-RS-16 — the order's account is another workspace's: refused, nothing written, the W2 account untouched (today and after the fix)
- **Rules:** RC1, RC1a; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized, `account_id A9.id`.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException` (404 today, 422 after BUG-3218; see SS-RS-19).
2. nothing written: nothing written.
3. unchanged: unchanged(A9); unchanged(L1).

### SS-RS-17 — an unknown order: 404
- **Rules:** RS1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.start_return(db, order_id=MISSING, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=1, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-RS-18 — a failing commit leaves no return and no credit note
- **Rules:** RS7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written: nothing written.

### SS-RS-19 — the order's account is W2's: 422 with no id
- **Rules:** RC1a [BUG-3218]; HR-16; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3218
- **Fails today on:** Then 1 (404 `Account with ID <A9.id> not found`)

**Given**
1. S = so "1", but finalized, `account_id A9.id`.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. X (after the commit point).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCTCN`.
3. raises: `str(A9.id) not in exc.value.detail`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. unchanged: unchanged(A9).
7. committed: x_gone.

### SS-RS-20 — the order's account is W0's: the same 422
- **Rules:** RC1a [BUG-3218]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3218
- **Fails today on:** Then 1 (404 `Account with ID <A0.id> not found`)

**Given**
1. S = so "1", but finalized, `account_id A0.id`.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="replace", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOACCTCN`.
3. nothing written: nothing written.
4. unchanged: unchanged(A0).

### SS-RS-21 — the event total is the sum of the sent quantities (1.5 + 1.5 → 3.0)
- **Rules:** RS7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. L2 = ln(S), but `quantity_ordered 2.00`, `quantity_delivered 2.00`, `line_total 6000.00`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.5")), SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("1.5"))]))`.

**Then**
1. committed: `types(S) == ["return_started"]`.
2. committed: that event has `description == f"Return {result.return_number} started — refund (3.0 unit(s) across 2 item(s))"`.

### SS-RS-22 — a whole sent quantity prints without decimals (3 → 3)
- **Rules:** RS7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="replace", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("3"))]))`.

**Then**
1. committed: that `return_started` event has `description == f"Return {result.return_number} started — replace (3 unit(s) across 1 item(s))"`.

### SS-RS-23 — credit-note lines are numbered in return-line id order
- **Rules:** RC3 [BUG-2425]
- **Kind:** bug
- **Expect:** xfail BUG-2425
- **Fails today on:** Then 1 (the return lines are read with no `ORDER BY sales_order_return_items.id`; Gap log G16)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. L2 = ln(S), but free "Ribbon", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 0.25`, `line_total 0.25`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00")), SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("0.50"))]))`, Statement recorder on.

**Then**
1. statement: id order on `sales_order_return_items`.
2. committed: C = the return's credit note; `[(l.line_number, l.source_order_item_id) for l in LINES(C)] == [(1, L1.id), (2, L2.id)]` (the return lines are created in the order sent, so L1's return line has the lower id).

### SS-RS-24 — a return line priced 0.00 gets a 0.00 credit-note line, not 1.00
- **Rules:** RC3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L1 = ln(S).
4. L2 = ln(S), but free "Sample", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 0.00`, `line_total 0.00`.

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L1.id, quantity_returned=Decimal("1.00")), SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. committed: C = the return's credit note; the line of C with `source_order_item_id == L2.id` has `description == "Sample"`, `quantity == Decimal("1.00")`, `unit_price == Decimal("0.00")`, `line_subtotal == Decimal("0.00")`.
2. committed: the line of C with `source_order_item_id == L1.id` has `unit_price == Decimal("3000.00")`, `line_subtotal == Decimal("3000.00")`.
3. committed: C has `invoice_amount == Decimal("3000.00")`, `invoice_status == "confirmed"`.

### SS-RS-25 — a catalog item with an empty name and no line description: the credit-note line reads `Item <item_id>`
- **Rules:** RC3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I3 = `Item(workspace_id=W1.id, name="", name_normalized="", unit="pcs", is_active=True)`.
2. S = so "1", but finalized.
3. V = inv(S), but confirmed, linked.
4. L2 = ln(S), but `item_id I3.id`, `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 10.00`, `line_total 10.00` (`description` stays None).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. committed: C = the return's credit note; `len(LINES(C)) == 1`.
2. committed: that line has `description == f"Item {I3.id}"`, `item_id == I3.id`, `source_order_item_id == L2.id`, `unit == "pcs"`, `line_subtotal == Decimal("10.00")`.

### SS-RS-26 — a free-text line with an empty description: the credit-note line reads `Line 1`, never "Item None"
- **Rules:** RC3, RC3a [BUG-3220]
- **Kind:** bug
- **Expect:** xfail BUG-3220
- **Fails today on:** Then 2 (today the fallback is `f"Item {item_id}"` with `item_id None`: `"Item None"`)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. L2 = ln(S), but free "", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 10.00`, `line_total 10.00` (stored directly: the item schema refuses a blank free-text description, the database allows it).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=L2.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. committed: C = the return's credit note; `len(LINES(C)) == 1`.
2. committed: that line has `line_number == 1`, `description == "Line 1"`, `"None" not in description`, `item_id is None`, `source_order_item_id == L2.id`, `line_subtotal == Decimal("10.00")`.

### SS-RS-27 — free-text names are trimmed, and a spaces-only name counts as empty (`Line <line_number>`)
- **Rules:** RC3, RC3a [BUG-3220]
- **Kind:** bug
- **Expect:** xfail BUG-3220
- **Fails today on:** Then 2 (today the name is copied as typed: `"  Crate  "`)

**Given**
1. S = so "1", but finalized.
2. V = inv(S), but confirmed, linked.
3. La = ln(S), but free "  Crate  ", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 10.00`, `line_total 10.00`.
4. Lb = ln(S), but free "   ", `quantity_ordered 1.00`, `quantity_delivered 1.00`, `unit_price 20.00`, `line_total 20.00` (stored directly, as SS-RS-26).

**When**
- `result = svc.start_return(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, data=SalesOrderReturnCreate(return_type="refund", reason="Broken", items=[SalesOrderReturnItemCreate(so_item_id=La.id, quantity_returned=Decimal("1.00")), SalesOrderReturnItemCreate(so_item_id=Lb.id, quantity_returned=Decimal("1.00"))]))`.

**Then**
1. committed: C = the return's credit note; `len(LINES(C)) == 2`.
2. committed: the line of C with `source_order_item_id == La.id` has `description == "Crate"`.
3. committed: the line B of C with `source_order_item_id == Lb.id` has `description == f"Line {B.line_number}"`, `item_id is None` (keyed by `source_order_item_id`; which line is number 1 is an order question, SS-RS-23).

## `SalesService.complete_return`

### SS-RK-01 — a refund return is completed: quantities, stock back, stamps; committed
- **Rules:** RK1, RK4, RK5, RK7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN = cn(S, "3000.00"); R1 = ret(S, "1"), but refund, of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R1.id`.
3. committed: R1 has `status == "completed"`, `completed_at == NOW`, `completed_by == U2.id`.
4. committed: L1 has `quantity_returned == Decimal("1.00")`, `quantity_delivered == Decimal("3.00")`, `quantity_refunded == Decimal("1.00")`.
5. committed: P1 has `qty == 101`.
6. committed: NEWLED is exactly one row: `transaction_type == "return"`, `quantity == 1`, `qty_before == 100`, `qty_after == 101`, `performed_by == U2.id`.

### SS-RK-02 — a replace return: delivered goes down, refunded does not
- **Rules:** RK4, RK10
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN = cn(S, "3000.00"); R1 = ret(S, "1"), but of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == R1.id`.
2. committed: L1 has `quantity_returned == Decimal("1.00")`, `quantity_delivered == Decimal("3.00")`, `quantity_refunded == Decimal("0.00")`.
3. committed: P1 has `qty == 101`.
4. committed: CN has `invoice_status == "confirmed"`, `paid_amount == Decimal("0.00")`.

### SS-RK-03 — a directly fulfilled catalog line puts no stock back
- **Rules:** RK5 [BUG-2791]
- **Kind:** bug
- **Expect:** xfail BUG-2791
- **Fails today on:** Then 2 (stock rises 100 → 101)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `requires_delivery False`.
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: P1 has `qty == 100`.
3. committed: NEWLED is empty.

### SS-RK-04 — a directly fulfilled catalog line still moves its quantities (today and after the fix)
- **Rules:** RK4, RK5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `requires_delivery False`.
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: L1 has `quantity_returned == Decimal("1.00")`, `quantity_delivered == Decimal("3.00")`, `quantity_refunded == Decimal("1.00")`.

### SS-RK-05 — a free-text line moves quantities only
- **Rules:** RK4, RK5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but free "Crate".
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: L1 has `quantity_delivered == Decimal("3.00")`, `quantity_refunded == Decimal("1.00")`.
3. committed: NEWLED is empty; P1 has `qty == 100`.

### SS-RK-06 — the ledger note names the order number once
- **Rules:** RK5a [BUG-3202]
- **Kind:** bug
- **Expect:** xfail BUG-3202
- **Fails today on:** Then 2 (`… for SO-SO-…`)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: NEWLED is exactly one row.
2. committed: that row has `notes == f"Return SR-{TAG}-1 for SO-{TAG}-1"`.

### SS-RK-07 — completion stamps `updated_by`
- **Rules:** RK7 [BUG-3200]
- **Kind:** bug
- **Expect:** xfail BUG-3200
- **Fails today on:** Then 2 (`updated_by` stays NULL)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but free "Crate".
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: R1 has `status == "completed"`.
2. committed: R1 has `updated_by == U2.id`.

### SS-RK-08 — one `return_completed` event for a refund return
- **Rules:** RK8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. L2 = ln(S), but free "Crate", `quantity_ordered 2.00`, `quantity_delivered 2.00`, `unit_price 100.00`, `line_total 200.00`.
4. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00"); rl(R1, L2, "2.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: `types(S) == ["return_completed"]`.
2. committed: that event has `description == f"Return SR-{TAG}-1 completed — refund (3.00 unit(s), 1 inventory line(s) posted)"`, `performed_by == U2.id`.
3. committed: its `metadata_json == {"return_id": R1.id, "return_type": "refund"}`.

### SS-RK-09 — a replace return's event adds "redeliver to close the gap"
- **Rules:** RK8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: `types(S) == ["return_completed"]`.
2. committed: that event has `description == f"Return SR-{TAG}-1 completed — replace (1.00 unit(s), 1 inventory line(s) posted) — redeliver to close the gap"`.

### SS-RK-10 — a replace return with a gap makes the order not fully delivered
- **Rules:** RK9 [BUG-3210]
- **Kind:** bug
- **Expect:** xfail BUG-3210
- **Fails today on:** Then 2 (stays True)

**Given**
1. S = so "1", but finalized, `is_fully_delivered True`.
2. L1 = ln(S).
3. R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: L1 has `quantity_delivered == Decimal("3.00")`.
2. committed: S has `is_fully_delivered is False`.

### SS-RK-11 — a refund return keeps "fully delivered"
- **Rules:** RK9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized, `is_fully_delivered True`.
2. L1 = ln(S).
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: S has `is_fully_delivered is True`.

### SS-RK-12 — a completed return cannot be completed again
- **Rules:** RK3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. R1 = ret(S, "1"), but done; rl(R1, L1, "1.00").
4. X (after the commit point).

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only a pending return can be completed"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. unchanged: unchanged(L1).
7. committed: x_gone.

### SS-RK-13 — a voided return cannot be completed
- **Rules:** RK3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"), but voided; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only a pending return can be completed"`.
3. unchanged: unchanged(L1).

### SS-RK-14 — a return of another W1 order: 404
- **Rules:** RK2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. S2 = so "2", but finalized; L2 = ln(S2); R2 = ret(S2, "2"); rl(R2, L2, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == RNF(R2.id)`.
3. unchanged: unchanged(R2).

### SS-RK-15 — a W2 return row under the order: 404
- **Rules:** RK2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R9 = ret(S, "9"), but of W2; rl(R9, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == RNF(R9.id)`.
3. unchanged: unchanged(L1).

### SS-RK-16 — the return is read with a row lock
- **Rules:** RK2 [BUG-2764]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2764
- **Fails today on:** Then 2 (no `FOR UPDATE`)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but free "Crate".
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").
4. `sid, rid = S.id, R1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_return(db, order_id=sid, return_id=rid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == rid`.
2. statement: row lock on `sales_order_returns`.

### SS-RK-17 — a fractional catalog quantity: 400, the whole completion undone
- **Rules:** RK6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "0.50").
4. X (after the commit point).

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Return line has a fractional quantity; stock requires whole units"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. unchanged: unchanged(L1).
5. unchanged: unchanged(R1).
6. nothing written: nothing written.
7. committed: x_gone.

### SS-RK-18 — a return line naming a line that is not this order's (W2) is skipped but counted
- **Rules:** RK4, RK8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. S9 = so "9", but of W2; L9 = ln(S9).
4. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00"); rl(R1, L9, "1.00"), but `workspace_id W1.id`.

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: L1 has `quantity_delivered == Decimal("3.00")`.
2. committed: unchanged(L9).
3. committed: P1 has `qty == 101`.
4. committed: the `return_completed` event has `description == f"Return SR-{TAG}-1 completed — refund (2.00 unit(s), 1 inventory line(s) posted)"`.

### SS-RK-19 — the last pending return completed: a completed order shows "completed" again
- **Rules:** RK10, RK11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed.
2. L1 = ln(S), but free "Crate".
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: S has `order_completed is True`, `completed_at == T0`.
2. committed: `HOR(S) is False`.

### SS-RK-20 — a failing commit leaves the return pending and the stock untouched
- **Rules:** RK10; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"), but refund; rl(R1, L1, "1.00").

**When**
- `svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R1: `status == "pending"`.
4. re-read P1: `qty == 100`.

### SS-RK-21 — an unknown order: 404
- **Rules:** RK1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.complete_return(db, order_id=MISSING, return_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-RK-22 — a second refund return adds to quantities that are already non-zero
- **Rules:** RK4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but free "Crate", `quantity_delivered 3.00`, `quantity_returned 1.00`, `quantity_refunded 1.00`.
3. CN0 = cn(S, "3000.00"); R0 = ret(S, "0"), but refund, done, of CN0; rl(R0, L1, "1.00").
4. CN = cn(S, "3000.00"); R1 = ret(S, "1"), but refund, of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.complete_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: L1 has `quantity_returned == Decimal("2.00")`, `quantity_refunded == Decimal("2.00")`, `quantity_delivered == Decimal("2.00")`.
3. committed: NEWLED is empty; P1 has `qty == 100` (a free-text line moves no stock).

## `SalesService.void_return`

### SS-RV-01 — a pending return is cancelled with its credit note voided; committed
- **Rules:** RV1, RV3, RV4, RV5, RV7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN = cn(S, "3000.00").
4. R1 = ret(S, "1"), but of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Customer kept it")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R1.id`.
3. committed: R1 has `status == "voided"`, `paid is False`.
4. committed: CN has `invoice_status == "voided"`, `paid_amount == Decimal("0.00")`.
5. committed: `types(S) == ["return_voided"]`.
6. committed: that event has `description == f"Return SR-{TAG}-1 cancelled — Customer kept it"`, `metadata_json == {"return_id": R1.id, "void_note": "Customer kept it"}`, `performed_by == U2.id`.
7. committed: unchanged(L1); P1 has `qty == 100`.
8. committed: `HOR(S) is False`.

### SS-RV-02 — an active refund payment on the credit note is voided with it
- **Rules:** RV3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN = cn(S, "3000.00"), but `paid_amount 1000.00`, `payment_status "partial"`.
4. P = pay(CN, "1000.00").
5. R1 = ret(S, "1"), but of CN; rl(R1, L1, "1.00").

**When**
- `svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Customer kept it")`.

**Then**
1. committed: P has `is_voided is True`.
2. committed: CN has `invoice_status == "voided"`, `paid_amount == Decimal("0.00")`.
3. committed: R1 has `status == "voided"`, `paid is False`.

### SS-RV-03 — cancelling stamps `updated_by`
- **Rules:** RV4 [BUG-3200]
- **Kind:** bug
- **Expect:** xfail BUG-3200
- **Fails today on:** Then 2 (`updated_by` stays NULL)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Customer kept it")`.

**Then**
1. committed: R1 has `status == "voided"`.
2. committed: R1 has `updated_by == U2.id`.

### SS-RV-04 — a completed return cannot be cancelled
- **Rules:** RV2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S), but `quantity_delivered 3.00`, `quantity_returned 1.00`.
3. CN = cn(S, "3000.00").
4. R1 = ret(S, "1"), but done, of CN; rl(R1, L1, "1.00").
5. X (after the commit point).

**When**
- `svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only a pending return can be cancelled"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(CN).
6. nothing written: nothing written.
7. committed: x_gone.

### SS-RV-05 — a voided return cannot be cancelled again
- **Rules:** RV2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. R1 = ret(S, "1"), but voided.

**When**
- `svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only a pending return can be cancelled"`.
3. nothing written: nothing written.

### SS-RV-06 — a credit note already voided does not stop the cancel
- **Rules:** RV3a [BUG-3211]
- **Kind:** bug
- **Expect:** xfail BUG-3211
- **Fails today on:** Then 1 (400 `Invoice is already voided`)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN = cn(S, "3000.00"), but voided-inv.
4. R1 = ret(S, "1"), but of CN; rl(R1, L1, "1.00").

**When**
- `result = svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Old data")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: R1 has `status == "voided"`.
3. committed: CN has `invoice_status == "voided"`, `void_note == "dup"`.

### SS-RV-07 — a W2 credit note linked to the return does not stop the cancel and is not touched
- **Rules:** RV3a [BUG-3211]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3211
- **Fails today on:** Then 1 (404 `Invoice with ID … not found`)

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN9 = cn(S, "3000.00"), but of W2.
4. R1 = ret(S, "1"), but of CN9; rl(R1, L1, "1.00").

**When**
- `result = svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Old data")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: unchanged(CN9).

### SS-RV-08 — a W2 credit note is never changed by the cancel (today and after the fix)
- **Rules:** RV3a; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. CN9 = cn(S, "3000.00"), but of W2.
4. R1 = ret(S, "1"), but of CN9; rl(R1, L1, "1.00").

**When**
- `try: svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="Old data")` / `except HTTPException: pass` (today it refuses; after the fix it succeeds).

**Then**
1. committed: unchanged(CN9).
2. count: `invoice_payments` rows of CN9: exactly 0.

### SS-RV-09 — a return without a credit note is cancelled
- **Rules:** RV3, RV4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. L1 = ln(S).
3. R1 = ret(S, "1"); rl(R1, L1, "1.00").

**When**
- `result = svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: R1 has `status == "voided"`, `paid is False`.

### SS-RV-10 — the return is read with a row lock
- **Rules:** RV1 [BUG-2764]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2764
- **Fails today on:** Then 2 (no `FOR UPDATE`)

**Given**
1. S = so "1", but finalized.
2. R1 = ret(S, "1").
3. `sid, rid = S.id, R1.id`; Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_return(db, order_id=sid, return_id=rid, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. returns: `result.id == rid`.
2. statement: row lock on `sales_order_returns`.

### SS-RV-11 — a return of another order: 404
- **Rules:** RV1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. S2 = so "2", but finalized; R2 = ret(S2, "2").
3. X (after the commit point).

**When**
- `svc.void_return(db, order_id=S.id, return_id=R2.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == RNF(R2.id)`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. unchanged: unchanged(R2).
5. committed: x_gone.

### SS-RV-12 — a spaces-only void note is refused by the schema
- **Rules:** RV6 [BUG-3203]
- **Kind:** bug
- **Expect:** xfail BUG-3203
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `SalesOrderReturnVoidRequest(void_note="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### SS-RV-13 — a void note is stored trimmed
- **Rules:** RV6 [BUG-3203]
- **Kind:** bug
- **Expect:** xfail BUG-3203
- **Fails today on:** Then 1 (kept as typed)

**Given**
1. Nothing.

**When**
- `r = SalesOrderReturnVoidRequest(void_note="  Wrong size  ")` (target `schema`).

**Then**
1. returns: `r.void_note == "Wrong size"`.

### SS-RV-14 — one character is enough; empty is refused
- **Rules:** RV6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `r = SalesOrderReturnVoidRequest(void_note="x")`; then build `SalesOrderReturnVoidRequest(void_note="")` (target `schema`).

**Then**
1. returns: `r.void_note == "x"`.
2. raises: building with `void_note=""` raises `ValidationError`.

### SS-RV-15 — a failing commit leaves the return pending and its credit note confirmed
- **Rules:** RV5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized.
2. CN = cn(S, "3000.00").
3. R1 = ret(S, "1"), but of CN.

**When**
- `svc.void_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R1: `status == "pending"`.
4. re-read CN: `invoice_status == "confirmed"`.

## `SalesService.list_returns` / `SalesService.get_return`

### SS-RL-01 — the order's returns, newest first; W2 rows left out; no commit or rollback
- **Rules:** RL1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. Ra = ret(S, "1"), but `created_at T1`.
3. Rb = ret(S, "2"), but voided, `created_at T2`.
4. ret(S, "9"), but of W2, `created_at T2`.
5. X (after the commit point).

**When**
- `result = svc.list_returns(db, order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[r.id for r in result] == [Rb.id, Ra.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-RL-02 — an unknown order: 404
- **Rules:** RL1, G1 [BUG-3197]
- **Kind:** bug
- **Expect:** xfail BUG-3197
- **Fails today on:** Then 1 (a plain `ValueError`)

**Given**
1. W1 has no sales orders.

**When**
- `svc.list_returns(db, order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(MISSING)`.

### SS-RG-01 — any status is returned; no commit or rollback
- **Rules:** RG1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. R1 = ret(S, "1"), but voided.
3. X (after the commit point).

**When**
- `result = svc.get_return(db, order_id=S.id, return_id=R1.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == R1.id`, `result.status == "voided"`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-RG-02 — a return of another order: 404, no rollback
- **Rules:** RG1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".
2. S2 = so "2"; R2 = ret(S2, "2").
3. X (after the commit point).

**When**
- `svc.get_return(db, order_id=S.id, return_id=R2.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == RNF(R2.id)`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

## `SalesService.mark_order_complete`

### SS-MC-01 — an order is completed, committed, with its payment status
- **Rules:** MC1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but finalized, `is_fully_delivered True`.
2. V = inv(S), but confirmed, linked.
3. ln(S).

**When**
- `result = svc.mark_order_complete(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == S.id`; `result.invoice_payment_status == "unpaid"`.
3. committed: S has `order_completed is True`.
4. committed: `"order_completed" in types(S)`.
5. committed: `notes() == []`.

### SS-MC-02 — an already completed order still goes through one commit
- **Rules:** MC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but finalized, completed, `is_fully_delivered True`.
2. V = inv(S), but confirmed, linked.
3. ln(S).

**When**
- `result = svc.mark_order_complete(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies**.

**Then**
1. returns: `result.id == S.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: S has `completed_at == T0`, `completed_by == U1.id`.

### SS-MC-03 — the manager's 404 passes and the extra row is gone
- **Rules:** MC1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. X (after the commit point).

**When**
- `svc.mark_order_complete(db, order_id=S9.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == NF(S9.id)`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(S9).
6. committed: x_gone.

### SS-MC-04 — a failing commit leaves the order open
- **Rules:** MC1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but finalized, `is_fully_delivered True`.
2. V = inv(S), but confirmed, linked.
3. ln(S).

**When**
- `svc.mark_order_complete(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `order_completed is False`.

## `SalesService.set_section_confirm`

### SS-SC-01 — confirming the second section drafts the invoice; committed with payment status
- **Rules:** SC1, SC2; Y4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=True)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == S.id`; `result.invoice_payment_status == "unpaid"`.
3. committed: S has `items_confirmed is True`, `invoice_id is not None`, `is_invoiced is True`.
4. committed: that invoice has `invoice_status == "draft"`, `invoice_amount == Decimal("12000.00")`.
5. committed: `"invoice_draft_created" in types(S)`.

### SS-SC-02 — confirming only order info makes no draft
- **Rules:** SC2; Y2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1".
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="order_info", confirmed=True)`.

**Then**
1. returns: `result.id == S.id`; `result.invoice_payment_status is None`.
2. committed: S has `order_info_confirmed is True`, `invoice_id is None`.
3. committed: `account_invoices` rows with `order_id == S.id` and `order_type == "sales_order"`: exactly 0.

### SS-SC-03 — unconfirming items deletes the draft
- **Rules:** SC2; Y2, DD3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready, `is_invoiced True`.
2. ln(S), but `quantity_delivered 0.00`.
3. V = inv(S), linked; invl(V, 1, "12000.00").
4. `vid = V.id`.

**When**
- `result = svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=False)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `items_confirmed is False`, `invoice_id is None`, `is_invoiced is False`.
3. committed: `db.get(AccountInvoice, vid) is None`.
4. committed: `"invoice_draft_deleted" in types(S)`.

### SS-SC-04 — a confirm that changes no flag still runs the draft step
- **Rules:** SC2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `result = svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=True)`.

**Then**
1. returns: `result.id == S.id`.
2. committed: S has `invoice_id is not None`.

### SS-SC-05 — invoicing disabled: 422 and the confirm is undone
- **Rules:** SC3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.allow_invoices = False`; `db.flush()`.
2. S = so "1", but `order_info_confirmed True`.
3. ln(S), but `quantity_delivered 0.00`.
4. X (after the commit point).

**When**
- `svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=True)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 422`.
2. raises: `exc.value.detail == NOINV`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. re-read S: `items_confirmed is False`.
6. nothing written: nothing written.
7. committed: x_gone.

### SS-SC-06 — unconfirming with a draft that has payment history: 400, everything kept
- **Rules:** SC3; DD3 [BUG-639]
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1 (the draft's delete raises `IntegrityError`, rolled back and passed on; Gap log G18)

**Given**
1. S = so "1", but ready, `is_invoiced True`.
2. V = inv(S), but `paid_amount 100.00`, `payment_status "partial"`, linked.
3. pay(V, "100.00").

**When**
- `svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=False)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == PAYHIST`.
3. re-read S: `items_confirmed is True`, `invoice_id == V.id`.
4. nothing written: nothing written.

### SS-SC-07 — a failing commit leaves the section unconfirmed and no draft
- **Rules:** SC1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but `order_info_confirmed True`.
2. ln(S), but `quantity_delivered 0.00`.

**When**
- `svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=True)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `items_confirmed is False`, `invoice_id is None`.

### SS-SC-08 — unconfirming with a draft that has payment history is refused and rolled back; everything kept (today and after the fix)
- **Rules:** SC3; DD3; TC3 (holds before and after BUG-639)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready, `is_invoiced True`.
2. V = inv(S), but `paid_amount 100.00`, `payment_status "partial"`, linked.
3. P = pay(V, "100.00").
4. X (after the commit point).

**When**
- `svc.set_section_confirm(db, order_id=S.id, workspace_id=W1.id, user_id=U2.id, section="items", confirmed=False)`.

**Then**
1. raises: `Exception` (any type: `IntegrityError` today, `HTTPException` 400 after BUG-639).
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. re-read S: `items_confirmed is True`, `invoice_id == V.id`.
4. re-read: `db.get(AccountInvoice, V.id) is not None`; `db.get(InvoicePayment, P.id) is not None`.
5. nothing written: nothing written.
6. committed: x_gone.

## Approvers and events

### SS-AL-01 — list_approvers returns the manager's rows; no commit or rollback
- **Rules:** AL1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. A_3 = appr(S, U3).
3. X (after the commit point).

**When**
- `result = svc.list_approvers(db, order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `len(result) == 1`; `result[0][0].id == A_3.id`; `result[0][1].id == U3.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-AL-02 — list_approvers on another workspace's order: the 404 passes, no rollback
- **Rules:** AL1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. S9 = so "9", but of W2.
2. X (after the commit point).

**When**
- `svc.list_approvers(db, order_id=S9.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. mock called: `rb.call_count == 0`.
3. re-read: x_kept.

### SS-AS-01 — approval_summary: one of one approved is met; no commit or rollback
- **Rules:** AS1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. appr(S, U3), but approved.

**When**
- `result = svc.approval_summary(db, order=S)`, inside **spies**.

**Then**
1. returns: `result == (1, 1, True)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

### SS-AS-02 — approval_summary: one of two required is not met
- **Rules:** AS1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = so "1", but `required_approvals 2`.
2. appr(S, U1), but approved.
3. appr(S, U3).

**When**
- `result = svc.approval_summary(db, order=S)`.

**Then**
1. returns: `result == (1, 2, False)`.

### SS-AA-01 — add_approver adds and commits; the row is returned re-read
- **Rules:** AA1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `result = svc.add_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.user_id == U3.id`, `result.sales_order_id == S.id`.
3. committed: S has exactly 1 approver row, `user_id == U3.id`, `approved is False`.
4. committed: `account_invoices` rows with `order_id == S.id`: exactly 0.

### SS-AA-02 — add_approver: a duplicate gets the 409 and the extra row is gone
- **Rules:** AA1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".
2. appr(S, U3).
3. X (after the commit point).

**When**
- `svc.add_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "User is already an approver for this order"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. count: S has exactly 1 approver row.
6. committed: x_gone.

### SS-AA-03 — add_approver: an inactive member gets the 400
- **Rules:** AA1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `svc.add_approver(db, order_id=S.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. nothing written: nothing written.

### SS-AA-04 — add_approver: a failing commit leaves no approver
- **Rules:** AA1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".

**When**
- `svc.add_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: S has exactly 0 approver rows.

### SS-AR-01 — remove_approver removes, commits and returns None
- **Rules:** AR1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. A_3 = appr(S, U3).

**When**
- `result = svc.remove_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `db.get(SalesOrderApprover, A_3.id) is None`.
3. committed: `notes() == []`.

### SS-AR-02 — remove_approver: not an approver gets the 404 and the extra row is gone
- **Rules:** AR1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".
2. X (after the commit point).

**When**
- `svc.remove_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Approver not found"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. committed: x_gone.

### SS-AR-03 — remove_approver: a failing commit keeps the approver
- **Rules:** AR1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1".
2. A_3 = appr(S, U3).

**When**
- `svc.remove_approver(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read: `db.get(SalesOrderApprover, A_3.id) is not None`.

### SS-AP-01 — set_approval approves, commits and returns the row re-read; no notification, no invoice step
- **Rules:** AP1; TC1, TC2; N5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. A_2 = appr(S, U2).

**When**
- `result = svc.set_approval(db, order_id=S.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. loaded: `loaded(result)`.
2. committed: A_2 has `approved is True`.
3. committed: `account_invoices` rows with `order_id == S.id`: exactly 0.
4. committed: `notes() == []`.

### SS-AP-02 — set_approval: not an approver gets the 403 and the extra row is gone
- **Rules:** AP1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. X (after the commit point).

**When**
- `svc.set_approval(db, order_id=S.id, user_id=U3.id, workspace_id=W1.id, approved=True)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 403`.
2. raises: `exc.value.detail == "You are not an assigned approver for this order"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### SS-AP-03 — set_approval: a failing commit keeps the approval unset
- **Rules:** AP1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = so "1", but ready.
2. A_2 = appr(S, U2).

**When**
- `svc.set_approval(db, order_id=S.id, user_id=U2.id, workspace_id=W1.id, approved=True)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A_2: `approved is False`.

### SS-EV-01 — list_events returns the order's events newest first; no commit or rollback
- **Rules:** EV1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so "1".
2. Ea = ev(S, T1).
3. Eb = ev(S, T2).
4. X (after the commit point).

**When**
- `result = svc.list_events(db, order_id=S.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[e.id for (e, p) in result] == [Eb.id, Ea.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. re-read: x_kept.

### SS-EV-02 — list_events on another workspace's order: the 404 passes, no rollback
- **Rules:** EV1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. S0 = so "0", but of W0.
2. X (after the commit point).

**When**
- `svc.list_events(db, order_id=S0.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `HTTPException`; `exc.value.status_code == 404`.
2. mock called: `rb.call_count == 0`.
3. re-read: x_kept.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| L3, LD3 [BUG-3195] | `GET /sales-orders/`, `GET /sales-deliveries/` | `limit=0` and `limit=-1` → 422; `limit=1` accepted |
| C3 [BUG-3205] | `POST /sales-orders/` (`create_sales_order`) | three lines 0.50 × 0.25 → each `line_total` 0.13, `total_amount` 0.39 (half up per line, then summed) |
| LD2 [BUG-3214] | `GET /sales-deliveries/` | `planned`, `delivered`, `cancelled` accepted; `Planned`, `shipped` → 422; omitted / `""` = no filter |
| U6 (BUG-362) | `SalesOrderUpdate` schema / `sales_manager.spec.md` | `required_approvals` 0 → 422; `null` and 1 accepted |
| OR3 | web app sales order panel | "return in progress" / "completed" derived from `order_completed` + `has_open_return`; nothing stored |
| SR8a, SR8c (implementation of the refusals) | `invoice_payment_manager.cases.md` (`delete_payment`, `update_payment`, `create_payment`) | the refusals sit there; SR-53 … SR-58 reach them only from the settlement side. A **cash** payment stays editable (non-amount fields) and gets BUG-609's general delete text; the internal settlement flag of SR3a skips only the `allow_payments` check |
| DC1, DV2, DX2, DU2, FS6, SC1, MC1, AA1, AR1, AP1, AL1, AS1, EV1 (manager rule bodies) | `sales_manager.spec.md` | the manager's own rules and texts; here only pass-through, commit and rollback are tested |
| RS3, RS5, RK2 lookup rules | `sales_order_return_manager.spec.md` | R1–R11 of `validate_and_build_items`, numbering, `get_return` |
| RK6 (stock outcome, ledger labels BUG-2783, cost BUG-2794, lock BUG-2770) | `product_manager.spec.md` `apply_sale_return` | bucket creation / restore, cost fallback, labels |
| N1–N4 recipients and texts | `approval_notification_service.spec.md` | who is notified, texts, active-member filter; here only "a notification row exists" |
| F8 (invoice frozen after completion) | `account_invoice_manager.spec.md` F2 | edits of a completed order's invoice refused |
| BUG-3192, BUG-2764 races; 500 vs 404 HTTP mapping | integration tests | two concurrent "Create invoice" / finalize / complete-return calls; `ValueError` → 500 and `NotFoundError` → RFC 7807 404 through the app |

## Spec gaps
Open: none (Revision 4a).

Closed in Revision 4a by the spec's Gap log (2026-11-22):
| # | Closed by | Where it landed |
|---|---|---|
| R4-1 | G19 (RK4a: `quantity_delivered 0.00` under a pending return is unreachable) | SS-RK-23 retired; the `quantity_delivered or 0` → `or 1` mutant is equivalent |
| R4-2 | G20 (RC3a, A7a, BUG-3220: trimmed name; empty → `Item <item_id>` or `Line <line_number>`) | SS-A-03 (xfail), SS-RS-26, SS-RS-27 (xfail); SS-RS-25 stays pass |

Closed: Revision 1's gaps 1–11 and the executor's discrepancies are closed by the spec's Gap log (2026-11-22, G1–G18):
| # | Closed by | Where it landed |
|---|---|---|
| 1 | G1 (`ActionMessage` shape) | Conventions **MSG** / **MSGD** |
| 2 | G2 (amounts as two-place `str()`; SR `paid_amount` as text) | Conventions fixed values; SR-20 |
| 3 | G3 (settlement through `create_payment`, `allow_payments` skipped; SR3a, SR3b) | SR-44 … SR-47, SR-50 |
| 4 | G4 (voided credit note warns; SR1b) | SR-13, SR-37, SR-40, SR-42 |
| 5 | G5 (no edit, no delete; SR8a, SR8b) | SR-53 … SR-56, SR-59 |
| 6 | G6 (credit note locked; SR1a, Row locks table) | SR-51, SR-52; plain `FOR UPDATE` in **row lock on T** |
| 7 | G7 (BUG-3218; F6a, RC1a) | F-11, F-15, F-16, RS-16, RS-19, RS-20 |
| 8 | G8 (manager refusal texts) | DV-13, DU-04, MC-03, AA-02, AA-03, AP-02 |
| 9 | G9 (RS7 sums sent quantities) | RS-21, RS-22 |
| 10 | G10 (PS5 returns None) | PS-07 |
| 11 | G11 (imports, `SalesDeliveryCreate`, `DeliveryMethod`, `paid_amount` type) | Conventions imports, DM1; SR-20 |
| — | G12 (SR3c link, SR8c reserved method, warnings in `messages`) | SR-48, SR-49, SR-57, SR-58; Conventions **MSG** |
| — | G13 (another workspace's credit note warns; SR1c) | SR-15, SR-16, SR-38, SR-39, SR-41, SR-43 |
| — | G14 (C2 re-cited BUG-3219) | C-02, C-03; coverage C2 |
| — | G15 (A8 `items_updated_at` not flushed by the helper) | A-01 Then 4 |
| — | G16 (list order only after BUG-100 / 2443 / 2442 / 1270 / 1271 / 2425) | Conventions **id order on T**, **idset**; L-01 … L-04, L-06 … L-09, LD-01 … LD-03, LD-05, LD-06, LD-09, LD-10, LD-11, GD-01, GD-04, GI-01, GI-03, GDI-01, GDI-03, RS-02, RS-23 |
| — | G17 (fulfil already answers the payment status) | OR-03 (pass) |
| — | G18 (DD3 payment-history refusal is BUG-639) | DD-08, DD-09, SC-06, SC-08 |

## Retired IDs
- SS-RK-23 (Revision 4a) — asserted RK4 on `quantity_delivered 0.00` under a pending return; spec RK4a (Gap log G19) shows that state is unreachable.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| Order response | OR1 [BUG-3212] | SS-OR-01, SS-OR-02; attached today: SS-OR-03 (fulfil, G17), SS-G-01, SS-F-01, SS-MC-01, SS-SC-01, SS-L-06 |
| | OR2 [BUG-2790] | SS-OR-04, SS-OR-05 |
| | OR3 | SS-OR-04, SS-RS-10, SS-RK-19; Deferred |
| Notifications | N1 [BUG-1205] | SS-N-01 |
| | N2 | SS-N-02 |
| | N3 | SS-N-02, SS-N-04 |
| | N4 | SS-N-03 |
| | N5 | SS-DV-01, SS-FS-01, SS-DC-01, SS-RS-01, SS-AP-01, SS-AR-01, SS-U-01, SS-MC-01, SS-SR-05, SS-SR-34 |
| `_attach_receivable_invoice_to_sales_order` | A2 / Errors A2 | SS-A-09, SS-A-10, SS-A-12, SS-I-13 |
| | A3 / Errors A3 | SS-A-11, SS-A-14, SS-Y-10, SS-SC-05 |
| | A4 [BUG-627, BUG-3196] / Errors A4 | SS-A-01, SS-A-06, SS-A-08, SS-A-12, SS-A-13 |
| | A5 / Errors A5 | SS-A-15, SS-A-16 |
| | A6, A8 (read after the commit, G15), A9 | SS-A-01 |
| | A7 [BUG-3193] | SS-A-02, SS-A-04, SS-A-05, SS-A-07, SS-A-07b, SS-A-17 |
| | A7a [BUG-3220] | SS-A-03 (`Line 1`) |
| `_delete_linked_draft_invoice_for_so` | DD1 | SS-DD-01 |
| | DD2 | SS-DD-02, SS-DD-03, SS-DD-04, SS-DD-05 |
| | DD3 [BUG-639] | SS-DD-06, SS-DD-08, SS-DD-09, SS-SC-03, SS-SC-06, SS-SC-08 |
| | DD4 [BUG-3204] | SS-DD-07 |
| `_sync_draft_invoice_for_so` | Y1 | SS-Y-01 |
| | Y2 | SS-Y-02, SS-Y-03, SS-Y-04, SS-Y-05, SS-SC-02, SS-SC-03 |
| | Y3 | SS-Y-06, SS-Y-07, SS-Y-08 |
| | Y4 | SS-Y-09, SS-Y-10, SS-SC-01 |
| `create_invoice_for_sales_order` | I1 [BUG-3192, BUG-3197] | SS-I-09, SS-I-10, SS-I-11 |
| | I2 | SS-I-06, SS-I-07 |
| | I3 | SS-I-08 |
| | I3a [BUG-3209] | SS-I-03, SS-I-04, SS-I-05 |
| | I4 [BUG-3209, BUG-1205] | SS-I-01, SS-I-02, SS-I-12, SS-I-13, SS-N-04 |
| | I5 | SS-I-01 |
| `finalize_sales_order_invoice` | F1 [BUG-3192] | SS-F-12, SS-F-14 |
| | F2 | SS-F-02, SS-F-03 |
| | F3 | SS-F-04, SS-F-05, SS-F-06 |
| | F4 | SS-F-07 |
| | F5 | SS-F-08 |
| | F6 | SS-F-01, SS-F-09, SS-F-10, SS-F-11 |
| | F6a [BUG-3218] | SS-F-11, SS-F-15, SS-F-16 |
| | F7 [BUG-1205] | SS-F-01, SS-F-13, SS-N-03 |
| | F8 | SS-F-01; Deferred |
| `create_sales_order_from_dict` | C1 | SS-C-01, SS-C-04, SS-C-05 |
| | C2 [BUG-3219] | SS-C-02, SS-C-03 |
| | C3 [BUG-3205] | SS-C-06 (service part); Deferred (endpoint) |
| | C4 | SS-C-01 |
| `get_sales_order` | G1 [BUG-3197] | SS-G-03, SS-G-04, SS-G-05, SS-G-06; via callers SS-I-09, SS-F-14, SS-U-26, SS-RS-17, SS-RK-21, SS-RL-02 |
| | G2 | SS-G-01, SS-G-02 |
| `get_sales_orders` | L1 [BUG-100] | SS-L-01, SS-L-02, SS-L-03, SS-L-04, SS-L-05, SS-L-07, SS-L-08, SS-L-09 |
| | L2 | SS-L-01, SS-L-06 |
| | L3 [BUG-3195] | Deferred |
| `_attach_invoice_payment_status` | PS1 | SS-PS-01, SS-PS-02, SS-G-02 |
| | PS2 [BUG-3194] | SS-PS-03, SS-PS-04, SS-PS-05, SS-G-01, SS-L-06 |
| | PS3 | SS-PS-06 |
| | PS4 | SS-PS-03 |
| | PS5 | SS-PS-07 |
| `update_sales_order` | U1 | SS-U-26, SS-U-27 |
| | U2 [BUG-3207] | SS-U-08, SS-U-09, SS-U-10, SS-U-11 |
| | U3 [BUG-3208] | SS-U-12, SS-U-13, SS-U-14, SS-U-15, SS-U-16, SS-U-17 |
| | U4 [BUG-2404, BUG-1019] | SS-U-18, SS-U-19, SS-U-20, SS-U-21 |
| | U5 [BUG-3199] | SS-U-01, SS-U-06, SS-U-07, SS-U-17 |
| | U6 | Deferred |
| | U7 [BUG-3201] | SS-U-22, SS-U-23, SS-U-24, SS-U-25 |
| | U8 [BUG-3200] | SS-U-02, SS-U-05 |
| | U9 [BUG-3215] | SS-U-03, SS-U-04, SS-U-05, SS-U-25 |
| | U10 | SS-U-29 |
| `create_delivery` | DC1 | SS-DC-01, SS-DC-05 |
| | DC2 | SS-DC-02, SS-DC-03 |
| | DC3 | SS-DC-04 |
| `complete_delivery` | DV1 | SS-DV-08, SS-DV-09, SS-DV-10 |
| | DV2 [BUG-3198] | SS-DV-01, SS-DV-11, SS-DV-12, SS-DV-13 |
| | DV3 [BUG-3216] | SS-DV-01, SS-DV-05, SS-DV-06, SS-DV-07 |
| | DV4 [BUG-3206] | SS-DV-01, SS-DV-02, SS-DV-03, SS-DV-04, SS-SR-08 |
| | DV5 | SS-DV-01, SS-DV-15, SS-OR-02 |
| | DV6 | SS-DV-14, SS-SR-05 |
| | DV6a [BUG-3217] | SS-SR-01, SS-SR-02, SS-SR-03, SS-SR-04, SS-SR-05, SS-SR-31, SS-SR-32 |
| `cancel_delivery` | DX1 | SS-DX-02, SS-DX-03 |
| | DX2 | SS-DX-01, SS-DX-04, SS-DX-05 |
| `update_delivery` | DU1 | SS-DU-02, SS-DU-03 |
| | DU2 | SS-DU-01, SS-DU-04, SS-DU-05 |
| `fulfill_service_item` | FS1 / Errors FS1 | SS-FS-03, SS-FS-04 |
| | FS2 / Errors FS2 | SS-FS-05 |
| | FS3 / Errors FS3 | SS-FS-05, SS-FS-06 |
| | FS4 | SS-FS-01 |
| | FS5 / Errors FS5 | SS-FS-06, SS-FS-07 |
| | FS6 | SS-FS-01; Deferred |
| | FS7 | SS-FS-01, SS-FS-02, SS-FS-08, SS-FS-09 |
| | FS8 | SS-SR-34 |
| | FS8a [BUG-3217] | SS-SR-33, SS-SR-49 |
| `_settle_replacement_credit_notes` | SR1 [BUG-3217] | SS-SR-10, SS-SR-11, SS-SR-12, SS-SR-13, SS-SR-14, SS-SR-15, SS-SR-16, SS-SR-17, SS-SR-18, SS-SR-19, SS-SR-25, SS-SR-26, SS-SR-27, SS-SR-35, SS-SR-37, SS-SR-38, SS-SR-39 |
| | SR1a [BUG-3217] | SS-SR-51, SS-SR-52 |
| | SR1b [BUG-3217] | SS-SR-13, SS-SR-37, SS-SR-40, SS-SR-42 |
| | SR1c [BUG-3217] | SS-SR-15, SS-SR-16, SS-SR-38, SS-SR-39, SS-SR-41, SS-SR-43 |
| | SR2 | SS-SR-08, SS-SR-09, SS-SR-28, SS-SR-29, SS-SR-30, SS-SR-35, SS-SR-36, SS-SR-42, SS-SR-43 |
| | SR3 | SS-SR-01, SS-SR-02, SS-SR-06, SS-SR-07, SS-SR-09, SS-SR-24, SS-SR-30, SS-SR-33, SS-SR-56 |
| | SR3a [BUG-3217] | SS-SR-44, SS-SR-45, SS-SR-46, SS-SR-47 |
| | SR3b | SS-SR-50 |
| | SR3c [BUG-3217] | SS-SR-48, SS-SR-49 |
| | SR4 | SS-SR-03, SS-SR-07, SS-SR-27, SS-SR-33, SS-SR-48 |
| | SR5 | SS-SR-03, SS-SR-05 |
| | SR6 | SS-SR-04, SS-SR-06, SS-SR-07, SS-SR-27, SS-SR-33 |
| | SR7 | SS-SR-20, SS-SR-21, SS-SR-22, SS-SR-23 |
| | SR8 | SS-SR-25, SS-SR-26, SS-SR-59 |
| | SR8a [BUG-3217] | SS-SR-53, SS-SR-54, SS-SR-55, SS-SR-56; Deferred (implementation) |
| | SR8b | SS-SR-59 |
| | SR8c [BUG-3217] | SS-SR-57, SS-SR-58; Deferred (implementation) |
| | SR9 | SS-SR-05 |
| `get_deliveries_for_order` | GD1 [BUG-2442] | SS-GD-01, SS-GD-04 |
| | GD2 [BUG-3213] | SS-GD-02, SS-GD-03 |
| `get_sales_order_items` | GI1 [BUG-1270] | SS-GI-01, SS-GI-03 |
| | GI2 [BUG-3213] | SS-GI-02 |
| `get_delivery` | GV1 [BUG-3197] | SS-GV-01, SS-GV-02, SS-GV-03, SS-GV-04 |
| `get_deliveries` | LD1 [BUG-100, BUG-2443] | SS-LD-01, SS-LD-02, SS-LD-03, SS-LD-04, SS-LD-05, SS-LD-06, SS-LD-07, SS-LD-08, SS-LD-09, SS-LD-10, SS-LD-11 |
| | LD2 [BUG-3214], LD3 [BUG-3195] | Deferred |
| `get_delivery_items` | GDI1 [BUG-1271] | SS-GDI-01, SS-GDI-03 |
| | GDI2 [BUG-3213] | SS-GDI-02 |
| `_attach_return_invoice_for_so` | RC1 [BUG-627, BUG-3196] | SS-RC-01, SS-RS-02, SS-RS-04, SS-RS-05, SS-RS-13, SS-RS-14, SS-RS-15, SS-RS-16 |
| | RC1a [BUG-3218] | SS-RS-16, SS-RS-19, SS-RS-20 |
| | RC2 | SS-RC-01, SS-RS-02 |
| | RC3 [BUG-2425] | SS-RS-02, SS-RS-03, SS-RS-23, SS-RS-24 (0.00 price), SS-RS-25 (`Item <item_id>`) |
| | RC3a [BUG-3220] | SS-RS-25 (catalog line, pass), SS-RS-26 (`""` → `Line 1`), SS-RS-27 (trimmed; spaces → `Line <n>`) |
| | RC4 | SS-RC-01, SS-RS-02, SS-RS-12 |
| | RC5 | SS-RC-01, SS-RS-06 |
| `start_return` | RS1 | SS-RS-01, SS-RS-17 |
| | RS2 | SS-RS-07, SS-RS-08 |
| | RS3 | SS-RS-09; Deferred |
| | RS4 [BUG-2790] | SS-RS-10, SS-RS-11 |
| | RS5 | SS-RS-01 |
| | RS6 | SS-RS-02 |
| | RS7 | SS-RS-06, SS-RS-18, SS-RS-21, SS-RS-22 |
| | RS8 | SS-RS-01, SS-RS-11 |
| | RS9 | SS-RS-12 |
| `complete_return` | RK1 | SS-RK-21 |
| | RK2 [BUG-2764] | SS-RK-14, SS-RK-15, SS-RK-16 |
| | RK3 | SS-RK-12, SS-RK-13 |
| | RK4 | SS-RK-01, SS-RK-02, SS-RK-04, SS-RK-05, SS-RK-18, SS-RK-22 (adds to non-zero) |
| | RK4a (fact: delivered ≥ pending; G19) | no card (unreachable state; SS-RK-23 retired) |
| | RK5 [BUG-2791] | SS-RK-01, SS-RK-03, SS-RK-04, SS-RK-05 |
| | RK5a [BUG-3202] | SS-RK-06 |
| | RK6 | SS-RK-01, SS-RK-17; Deferred |
| | RK7 [BUG-3200] | SS-RK-01, SS-RK-07 |
| | RK8 | SS-RK-08, SS-RK-09, SS-RK-18 |
| | RK9 [BUG-3210] | SS-RK-10, SS-RK-11 |
| | RK10 | SS-RK-02, SS-RK-19, SS-RK-20, SS-SR-36 |
| | RK11 | SS-RK-19 |
| `void_return` | RV1 [BUG-2764] | SS-RV-10, SS-RV-11 |
| | RV2 | SS-RV-04, SS-RV-05 |
| | RV3 | SS-RV-01, SS-RV-02, SS-RV-09 |
| | RV3a [BUG-3211] | SS-RV-06, SS-RV-07, SS-RV-08 |
| | RV4 [BUG-3200] | SS-RV-01, SS-RV-03, SS-RV-09 |
| | RV5 | SS-RV-01, SS-RV-15 |
| | RV6 [BUG-3203] | SS-RV-12, SS-RV-13, SS-RV-14 |
| | RV7 | SS-RV-01 |
| `list_returns` | RL1 | SS-RL-01, SS-RL-02 |
| `get_return` | RG1 | SS-RG-01, SS-RG-02 |
| `mark_order_complete` | MC1 | SS-MC-01, SS-MC-02, SS-MC-03, SS-MC-04 |
| `set_section_confirm` | SC1 | SS-SC-01, SS-SC-07 |
| | SC2 | SS-SC-01, SS-SC-02, SS-SC-03, SS-SC-04 |
| | SC3 | SS-SC-05, SS-SC-06, SS-SC-08 |
| | SC4 [BUG-1205] | SS-N-02 |
| `list_approvers` | AL1 | SS-AL-01, SS-AL-02 |
| `approval_summary` | AS1 | SS-AS-01, SS-AS-02 |
| `add_approver` | AA1 | SS-AA-01, SS-AA-02, SS-AA-03, SS-AA-04 |
| | AA2 [BUG-1205] | SS-N-01 |
| `remove_approver` | AR1 | SS-AR-01, SS-AR-02, SS-AR-03 |
| `set_approval` | AP1 | SS-AP-01, SS-AP-02, SS-AP-03 |
| `list_events` | EV1 | SS-EV-01, SS-EV-02 |
| Transaction contract | TC1 | every write's happy card (SS-I-01, SS-F-01, SS-C-01, SS-U-01, SS-DC-01, SS-DV-01, SS-DX-01, SS-DU-01, SS-FS-01, SS-RS-01, SS-RK-01, SS-RV-01, SS-MC-01, SS-SC-01, SS-AA-01, SS-AR-01, SS-AP-01) |
| | TC2 | `loaded(…)` in the same cards (not SS-AR-01: returns None) |
| | TC3 | SS-I-06, SS-I-10, SS-I-13, SS-F-02, SS-C-03, SS-U-27, SS-DC-02, SS-DV-08, SS-DV-12, SS-DX-02, SS-DX-04, SS-DU-02, SS-DU-04, SS-FS-03, SS-RS-07, SS-RS-13, SS-RK-12, SS-RK-17, SS-RV-04, SS-RV-11, SS-MC-03, SS-SC-05, SS-SC-08, SS-AA-02, SS-AR-02, SS-AP-02, SS-SR-31; **X not in db** right after the raise on every X card, spies `rb.call_count >= 1` on SS-I-06, SS-F-02, SS-C-03, SS-U-27, SS-DC-02, SS-DV-08, SS-DX-04, SS-DU-04, SS-FS-03, SS-RS-07, SS-RK-12, SS-RV-04, SS-MC-03, SS-SC-05, SS-AA-02, SS-AR-02, SS-AP-02 (Revision 4) |
| | TC4 | SS-I-12, SS-F-13, SS-C-05, SS-U-28, SS-DC-05, SS-DV-15, SS-DX-05, SS-DU-05, SS-FS-09, SS-RS-18, SS-RK-20, SS-RV-15, SS-MC-04, SS-SC-07, SS-AA-04, SS-AR-03, SS-AP-03, SS-SR-32 |
| | TC5 | SS-C-04 |
| | TC6 | SS-G-01, SS-G-06, SS-L-06, SS-GD-01, SS-GI-01, SS-GV-01, SS-GV-04, SS-LD-01, SS-GDI-01, SS-RL-01, SS-RG-01, SS-RG-02, SS-AL-01, SS-AL-02, SS-AS-01, SS-EV-01, SS-EV-02 |
| Flush-only helpers | no commit / rollback | SS-A-01, SS-DD-06, SS-Y-09, SS-RC-01, SS-SR-06 |
