# Test cases — `app/services/purchase_order_service.py`

> **Spec:** `tests/unit/services/purchase_order_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4a (2026-11-22) — spec Gap log G20 closes gap 13 with new rule CR3a [BUG-3186] (completing a return must not drive a line's received quantity below 0): new strict xfails CR-18 (receive 4, start a return of 4, correct the receipt to 0 through Receive goods, complete → 400, nothing written) and CR-19 (two lines, only the second short → nothing written on either); new pass CR-20 (a line that ends at exactly 0 completes). CR-17 re-checked against CR3a (8 − 4 = 4 ≥ 0, unchanged). No IDs retired.
> **Revision 4 (2026-11-22)** — verifier findings (`purchase_order_service.verify.md`, NEEDS WORK, case-missing only). (1) TC3: every write-method error card with X (30 cards: C-06, C-07, U-02, U-09, U-10, MC-02, RE-20, SR-06, SR-12, CR-07, CR-12, VR-05, X-02, AI-04, AI-05, UI-03, RI-03, RI-05, SY-08, SY-10, SY-12, AA-03, RA-02, SA-02, V-05, V-10, CI-02, CI-05, RX-24, RX-29, plus new SY-14) checks `X not in db` right after the raise, before any test rollback; one non-failing-commit error card per write method runs inside spies with `rb.call_count >= 1`: C-07, U-09, MC-02, RE-20, SR-06, CR-07, VR-05, X-02, AI-04, UI-03, RI-05, SY-10, AA-03, RA-02, SA-02, V-05, CI-05 (CI-09 also), RX-24. (2) Held-today texts moved out of strict xfails: DD-04 and V-02 keep only the BUG-3185 `invoice_id`; new pass companions DD-06 (draft-deleted event description) and V-21 (reset reason, `invoice_voided` description and `changes`, `po_voided` description and metadata, event order). (3) RX-47, RX-49: fail today in the Given with ImportError. (4) New cards for surviving mutants: IE-24 … IE-32 (pgcode-only branches, one-word check texts, `financial_audit_logs` not-null, `{loc}` with one of table / column in the invoice phase, `account_invoices` FK in the items phase); C-12 (collision text naming only `uq_po_workspace_number`); U-12 (explicit `null` is not an unconfirm); PG-08, PG-09, HS-06 (page and hub-stats defaults); RE-43 … RE-45 (`all_received` edges); AR-08 (return line priced 0.00); SR-15 (exactly 1 received); CR-17 (adds to returned / refunded); AO-23 … AO-25 (machine and component scopes with transfers, one-stage workflow); SY-14 (line-phase non-HTTP error); V-22 (one reversed posting); SD-13 adds the reset reason and the notification's `entity_type`. One new spec gap (CR on a line at 0 received). No IDs retired.
> **Revision 3 (2026-11-22)** — executor discrepancies resolved by the spec's Gap log G13–G19 and the coordinator's list: IC-04 → xfail BUG-3184 (IC1a); DD-04, V-02 → xfail BUG-3185 (DD2a, V5a); C-09 rebuilt with a marker row and same-session checks before any test-level rollback, still strict xfail BUG-3175 (G14); AR-05 → plain pass on AR3, checks the stored lines (BUG-3163 withdrawn, G13); PT-03, PT-04 read the tuple rows (PT2, G17); G-01 reads `item_count` through `PurchaseOrderResponse` and checks the ORM order has none (G18); AO-11, AO-12 vary WF1's sequence instead of adding a second purchase workflow (G19); every stock count and STOCK use the `inventory` table (G19); DD-05, V-10 → xfail BUG-639 (PAYHIST check added); X-01 → xfail BUG-2888. New cards for uncovered lines: AO-22 (1176–1177, other component skipped), RI-05 (1269–1270, remove_item IntegrityError), SY-10 (1293–1294, line-phase IntegrityError), SY-11, SY-12, SY-13 (1311–1316, invoice-phase IntegrityError, its BUG-3179 half, other error); X-08 a plain delete commit card (X-01 is now xfail). Convention fix: read cards check `X in db` instead of `X in db.new` (X is flushed), and `not db.new` instead of `len(db.new) == 1`. No IDs retired.
> **Revision 2 (2026-11-22)** — spec fill-gaps closed gaps 1–12 (Gap log G1–G12), added RX1a and RX8j–RX8m; coordinator decisions applied: the order read locks `FOR UPDATE OF purchase_orders` (RE-05, V-06, CI-03, new RX-63), single-table reads plain `FOR UPDATE` (CR-09, VR-06, RX-17, RX-52); a voided (or any non-confirmed) credit note gets its own warning (RX-41, new RX-53); `warnings: list[str]` on the return response, `[]` elsewhere (RX-30, new SR-14, CR-16, VR-14); foreign or missing credit note left alone with a warning (RX-51 rewritten, new RX-54, RX-55, RX-61); settlement through `create_payment` (new RX-59, RX-60); the payments API refuses the reserved method (new RX-56, RX-57, pass RX-58); void re-syncs `paid` (RX-48, RX-49); return event log (RX-44, new RX-62); settled 0.00 when no entry (RX-42); link columns (RX-35); ledger `transaction_type` (RE-01, RX-02); texts as sent / stored (SR-02, CR-02, CR-03, RX-23, RX-26); receive-event lines (BR-01, BR-04, BR-05); other order kinds (AO-17 … AO-20); V3 netting corrections (new V-20). `Author: claude` dropped on BR-01, BR-04, BR-05, AO-17, RX-44, RX-51. No IDs retired.
> **Counts:** 444 cases · 321 expected-to-pass · 123 expected-to-fail (bugs; 2 of them non-strict) · 14 deferred

## Reviewer summary
- **Per callable:** `create_purchase_order` 12 (1 bug) · `update_purchase_order` 12 · `get_purchase_order` 7 · `mark_order_complete` 4 · `list_purchase_orders` 4 · `_hub_filter_kwargs` 6 · `_prepare_listed_orders` 5 (1) · `list_purchase_orders_page` 9 · hub stats 6 · `_attach_invoice_payment_status` 5 (2) · `_attach_item_summaries` 3 (1) · `_integrity_context` 5 (1) · `_handle_item_integrity_error` 32 · `_build_invoice_items_from_po` 4 · `_delete_linked_draft_invoice_for_po` 6 (2) · `_sync_draft_invoice_for_po` 18 (1) · `_emit_po_invoice_draft_notification` 2 · return-in-progress flag 7 (6) · `create_receive_event` 45 (6) · `list_receive_events` 6 (2) · `_build_receive_event_response` 5 (2) · `_attach_return_invoice_for_po` 8 (1) · `start_return` 15 (3) · `complete_return` 20 (5) · `void_return` 14 (6) · `list_returns` / `get_return` 5 · `list_active_orders_for_context` 25 (2) · `delete_purchase_order` 8 (3) · `add_item` 7 · `update_item` 6 (1) · `remove_item` 5 · `sync_items` 14 (4) · get_items / list_events / list_approvers 4 (1) · `approval_summary_for` 2 · `add_approver` 5 · `remove_approver` 3 · `set_approval` 4 · `void_purchase_order` 22 (9) · `create_invoice_for_purchase_order` 11 (2) · `receive_replacements` 63 (61; RX-48 and RX-58 pass today).
- **Depth:** full (skill step 1a): the service moves stock (receive, returns, replacements, void), writes money (draft invoices, credit notes, the replacement settlement) and order workflow state. Manager, invoice-manager, posting-module and notification rules are not re-tested; each one the service reaches gets one pass-through card.
- **Transaction contract:** every public write has a commit card (`committed:` after a test-level rollback), a rollback card with an **uncommitted** extra workspace X that must be gone from the session right after the raise (`X not in db`, before any test rollback; Revision 4) and, after the test's rollback, from the database, one non-failing-commit error card per method with a rollback spy, and a failing-commit card; TC5 once (C-11). `create_receive_event` refusals run before the `try` (spec): their card checks X is **still in the session** (`X in db`) and no rollback ran, and a separate card (RE-20) covers the rollback of a posting failure. The flush-only helpers (DD, SD, AR, EN) each get a spy card (no commit, no rollback). Every read checks no commit, no rollback and X still in the session, on success and on a 404; G and the list page commit only when a stage repair changed something (Q8, intended), checked both ways.
- **OQ-63 / BUG-3176 (replacement settlement, RX8a–RX8m):** 36 cards (plus SR-14, CR-16, VR-14 for `warnings == []` elsewhere) — entry fields (method, amount with per-line half-up rounding, UTC date, actor, workspace, receipt link `source_type 'purchase_order_event'` / `source_id`), credit-note balance and return `paid`, partial receipt and its second half, cap at the outstanding amount (cash already collected, 0.01 boundary), nothing outstanding (fully collected in cash → NOSETTLE; voided or draft credit note → VOIDW) with the receipt still going ahead, foreign (W0, W2) or missing credit note → NOTFOUND, not locked, no entry; return event row (`purchase_order_return_events`, 0.00 when no entry), PO activity entry, stock-in ledger rows, through `create_payment` (audit row, `payment_recorded`, `allow_payments` skipped), delete / edit refused (400), the payments API refuses the reserved method on create and update, void allowed and re-opens the balance and the return's `paid` without touching stock, isolation with W0 and W2 groups on both sides of W1, lock order order → return → credit note, failing commit.
- **Bugs:** strict xfail for every bug rule; the two non-strict cards are LR-03 and BR-05 (tie / heap order, no ORDER BY today), with their strict SQL alarms LR-04 and BR-04. Passing companions hold today and after each fix (e.g. RE-19 duplicate lines within the limit, SY-04 the invoice-step refusal still reaches the caller, VR-08 a return with no credit note cancels, X-08 a plain delete, SY-11 the invoice-phase translation, RX-48 voiding a settlement entry, RX-58 a hand-entered cash payment, V-20 a netted correction reversed on void).
- **Notable design choices:**
  - Concurrency is not simulated. Lock cards check the emitted SQL with the exact clause of the spec's Row locks table: `FOR UPDATE OF purchase_orders` for the order read (RE-05, V-06, CI-03, RX-63), plain `FOR UPDATE` on `purchase_order_returns` (CR-09, VR-06, RX-17) and `account_invoices` (RX-52); never `NOWAIT` / `SKIP LOCKED`; each sent before the first read of the rows the first state check needs.
  - One race simulation (SD-10, SD8's "invoice linked meanwhile" branch) and the forced `IntegrityError` / retry cards patch the service's own collaborators; all `Author: claude`.
  - Cross-workspace links (W0 / W2 invoices, events, lines, credit notes attached to W1 rows) are invalid data built on purpose (HR-16).
  - `receive_replacements` does not exist yet: every RX card that calls it is strict xfail and "fails today on: Then 1 (the call raises AttributeError)". Cards whose **Given** needs the new column `quantity_replaced` or calls the new method (RX-23, RX-37, RX-47, RX-49) fail in the Given today (RX-47, RX-49 with ImportError: the new schema is imported to build `RQ(...)` before the call); they are `Author: claude`.
  - `warnings` is read through the response schema, WARN(r) = `PurchaseOrderReturnResponse.model_validate(r).warnings`, since the spec puts the field on `PurchaseOrderReturnResponse`.
  - AO-18 … AO-20 stay `Author: claude`: the spec now names the work-order and transfer columns the service reads, but not the other NOT NULL columns of `work_orders` (type, factory) or the project row behind a component.
  - Return / receive flows that are not about stock use a **project** order (`proj`), so no stock rows are needed (*revisit after launch* behaviour, tested as today).
- **Needs a decision:** None (gaps 1–12 closed in Revision 2; executor discrepancies G13–G19 applied in Revision 3; gap 13 closed by Gap log G20 in Revision 4a).

## Conventions for this module

**IDs.** `POS` = `app/services/purchase_order_service.py`. `IC` _integrity_context · `IE` _handle_item_integrity_error · `BI` _build_invoice_items_from_po · `DD` _delete_linked_draft_invoice_for_po · `SD` _sync_draft_invoice_for_po · `EN` _emit_po_invoice_draft_notification · `RF` return-in-progress flag · `C` create · `U` update · `G` get · `MC` mark_order_complete · `LP` list_purchase_orders · `HF` _hub_filter_kwargs · `PL` _prepare_listed_orders · `PG` list_purchase_orders_page · `HS` hub stats · `AP` _attach_invoice_payment_status · `IS` _attach_item_summaries · `RE` create_receive_event (incl. its schema) · `LR` list_receive_events · `BR` _build_receive_event_response · `AR` _attach_return_invoice_for_po · `SR` start_return · `CR` complete_return · `VR` void_return (incl. its schema) · `LRT` list_returns / get_return · `AO` list_active_orders_for_context · `X` delete · `AI` add_item · `UI` update_item · `RI` remove_item · `SY` sync_items · `PT` get_items / list_events / list_approvers · `AS` approval_summary_for · `AA` add_approver · `RA` remove_approver · `SA` set_approval · `V` void (incl. its schema) · `CI` create_invoice_for_purchase_order · `RX` receive_replacements.

**Imports.** `svc` = `purchase_order_service` (`from app.services.purchase_order_service import PurchaseOrderService, purchase_order_service`). `mgr` = `svc.manager`; `aim` = `svc.account_invoice_manager`; `ipm` = `invoice_payment_manager` (`app.managers.invoice_payment_manager`). Models from `app.models.<snake_case>`: `PurchaseOrder`, `PurchaseOrderItem`, `PurchaseOrderApprover`, `PurchaseOrderEvent`, `PurchaseOrderReturn`, `PurchaseOrderReturnItem`, `PurchaseOrderReturnEvent` (all three `app.models.purchase_order_return`; the event model is new, BUG-3176), `PoReceiveEvent`, `PoReceiveEventItem`, `AccountInvoice`, `InvoiceItem`, `InvoiceEvent`, `InvoicePayment`, `Account`, `Item`, `Factory`, `Status`, `OrderWorkflow`, `Notification`, `WorkspaceMember`, `WorkspaceAuditLog`, `Workspace`, `Inventory` (table `inventory`), `Department` (C-09's marker row only). Schemas: `PurchaseOrderCreate`, `PurchaseOrderUpdate`, `PurchaseOrderItemCreate`, `PurchaseOrderItemUpdate`, `PurchaseOrderVoidRequest`, `PurchaseOrderItemSyncRequest` (with `PurchaseOrderItemSyncUpdate`) from `app.schemas.purchase_order`; `PoReceiveEventCreate` (with `PoReceiveEventItemCreate`) from `app.schemas.po_receive_event` (spec Overview, Input schemas); `PurchaseOrderReturnCreate`, `PurchaseOrderReturnItemCreate`, `PurchaseOrderReturnVoidRequest`, `PurchaseOrderReturnResponse` (`app.schemas.purchase_order_return`); `PurchaseOrderResponse` (`app.schemas.purchase_order`, G-01); `PurchaseOrderReturnReplacementCreate` is imported **inside** each RX test (it does not exist yet); `InvoicePaymentCreate`, `InvoicePaymentUpdate` (`app.schemas.invoice_payment`). `HTTPException` (fastapi), `pydantic.ValidationError`, `IntegrityError` (sqlalchemy.exc), `inspect`, `select`, `func`, `text`, `patch`, `SimpleNamespace`, `Decimal`, `date`, `datetime`, `timedelta`, `uuid`, `contextlib`. Every call: `db` first, the rest by keyword. `result` = what the When returns.

**Fixed values.** MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. T0 = `datetime(2026, 9, 1, 8, 0)`, T1 = `datetime(2026, 9, 2, 9, 0)`, T2 = `datetime(2026, 9, 3, 10, 0)`. Long dashes are U+2014; copy them. NF(i) = `f"Purchase order with ID {i} not found"`. RNF(i) = `f"Return with ID {i} not found"`. FINALIZE = `"Finalize the invoice before recording receiving"`. PAYHIST = `"Invoice has payment history — confirm and void it instead"`. DRAFTP = `"draft|Linked payable invoice is in draft — confirm when details look correct"`. FORCE422 = `"Confirm supplier, order details, and items before creating a draft invoice"`. SUPP422 = `"The selected supplier account was not found. Re-select the supplier."`. NOSETTLE = `"The return's credit note has nothing outstanding — no settlement recorded"`. VOIDW = `"The return's credit note is voided — no settlement recorded"`. NOTFOUND = `"The return's credit note could not be found — no settlement recorded"`. MANUAL = `'"settled_by_replacement" is recorded by the system and cannot be entered by hand'`. NODEL = `"A settlement by replacement cannot be deleted or edited — void it with a reason instead"`. NOTPART(i, R) = `f"Line {i} is not part of return {R.return_number}"`. RTOO(t, n, left) = `f"Cannot receive {t} replacement(s) for line {n} — only {left} still to replace"`.

**Time.** In every test `app.services.purchase_order_service.utcnow` is patched to return **NOW = `datetime(2026, 9, 27, 12, 0, 0)`**, with the tz-awareness of the real `app.utils.time.utcnow`. TODAY_UTC = `date(2026, 9, 27)`. Nothing else is mocked unless a card says so.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U4 = `make_profile(db, name=…)`: `"Rahim Uddin"`, `"Karim Ali"`, `"Nadia Khan"`, `"Esha Roy"`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=…, role="member", status=…)`: U1, U2, U3 `"active"`; U4 `"inactive"`. U1 creates every Given row; **U2 is the acting user**.
3. For W0, W1, W2 (suffix `0`, `1`, `9`): SDk, SPk, SRk, SCk = `Status(workspace_id=…, name=…, comment="po stage")` named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`; WFk = `OrderWorkflow(workspace_id=…, name="Purchase Order", type="purchase", status_sequence=[SDk.id, SPk.id, SRk.id, SCk.id])`; Fk = `Factory(workspace_id=…, name="Main Store", abbreviation=f"MS{k}", is_active=True, is_deleted=False)`; Ak = `Account(workspace_id=…, name=…, is_active=True, is_deleted=False, allow_invoices=True)` named `"Zeta West"`, `"Acme Supplies"`, `"Xeno Foreign"`; Ik = `Item(workspace_id=…, name="Bearing", name_normalized="bearing", unit="pcs", is_active=True)`.
4. I1b = `Item(workspace_id=W1.id, name="Cement", name_normalized="cement", unit="bag", is_active=True)`.

**Given rows.** Inserted directly (never through `svc`, unless a line is written as code), flushed one at a time in the order written. After "but" a line lists every column that differs. "of W0" / "of W2" = that workspace's id and its A, F, SD, WF, I rows.
- **po "n"** = `PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-n", account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=date(2026, 9, 1), description="Bearings for Press 4", subtotal=Decimal("5000.00"), total_amount=Decimal("5000.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id)`; `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed`, `invoice_ever_linked`, `voided`, `paid` False; `invoice_id`, `void_note`, `voided_at`, `voided_by`, `items_updated_at`, `actual_delivery_date`, `updated_by` NULL. **ready** = `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`. **proj** = `destination_type "project"`, `destination_id 4242`. **complete** = `current_status_id SC1.id`. **voided** = `voided True`, `void_note "Duplicate"`, `voided_at T0`, `voided_by U1.id`.
- **poline(O, k)** = `PurchaseOrderItem(workspace_id=O.workspace_id, purchase_order_id=O.id, line_number=k, item_id=<I of O's workspace>.id, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("0.00"), quantity_returned=Decimal("0.00"), quantity_refunded=Decimal("0.00"), unit_price=Decimal("500.00"), line_subtotal=Decimal("5000.00"))`.
- **inv(O)** = `AccountInvoice(workspace_id=O.workspace_id, account_id=<A of O's workspace>.id, invoice_type="payable", invoice_status="draft", payment_status="unpaid", invoice_amount=Decimal("5000.00"), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 1), allow_payments=True, receiving_started=False, created_by=U1.id, order_type="purchase_order", order_id=O.id)`. **finalized** = `invoice_status "confirmed"`. **locked-inv** = `invoice_status "locked"`. **voided-inv** = `invoice_status "voided"`, `void_note "dup"`. **linked to O** = after its flush `O.invoice_id = V.id`, `O.invoice_ever_linked = True`, `db.flush()`; a finalized V linked to a ready O also sets `O.invoice_confirmed = True`.
- **invl(V, k, s)** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=k, description="Old line", quantity=Decimal("1"), unit_price=Decimal(s), line_subtotal=Decimal(s), created_by=U1.id)`.
- **poappr(O, U)** = `PurchaseOrderApprover(workspace_id=O.workspace_id, purchase_order_id=O.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=T0)`. **approved** = `approved True`, `approved_at T1`.
- **ret "n" of O** = `PurchaseOrderReturn(workspace_id=O.workspace_id, purchase_order_id=O.id, return_number=f"PR-{TAG}-n", return_type="refund", reason="Faulty", status="pending", paid=False, created_by=U1.id)`; `invoice_id`, `updated_by`, `completed_at`, `completed_by` NULL. **replace** = `return_type "replace"`. **completed** = `status "completed"`, `completed_at T0`, `completed_by U1.id`. **voided-ret** = `status "voided"`.
- **rline(R, L, q)** = `PurchaseOrderReturnItem(workspace_id=R.workspace_id, return_id=R.id, po_item_id=L.id, item_id=L.item_id, quantity_returned=Decimal(q), unit_price=Decimal("500.00"))`.
- **cn(R, a)** = `AccountInvoice(workspace_id=R.workspace_id, account_id=<A of R's workspace>.id, invoice_type="receivable", invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal(a), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 5), allow_payments=True, receiving_started=False, created_by=U1.id, order_type="purchase_order", order_id=R.purchase_order_id)`; after its flush `R.invoice_id = CN.id`, `db.flush()`.
- **cash(V, a)** = `InvoicePayment(workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(a), payment_date=date(2026, 9, 20), payment_method="cash", is_voided=False, created_by=U1.id)`. **spay(V, a, R)** = the same, but `payment_method "settled_by_replacement"`, `payment_reference R.return_number`.
- **REPL** (a group; names O, V, L, R, RL, CN): O = po "1", but ready, complete, `invoice_confirmed True`, `actual_delivery_date date(2026, 9, 10)`; V = inv(O), but finalized, `paid_amount Decimal("5000.00")`, `payment_status "paid"`, linked to O; L = poline(O, 1), but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`; R = ret "1" of O, but replace, completed; RL = rline(R, L, "4"); CN = cn(R, "2000.00"). **REPL of W0** / **REPL of W2** = the same group in W0 / W2 (names O0, V0, L0, R0, RL0, CN0 / O9, V9, L9, R9, RL9, CN9; po_number / return_number with `-w0` / `-w2` appended).
- **ev(O, t, typ)** = `PurchaseOrderEvent(workspace_id=O.workspace_id, purchase_order_id=O.id, event_type=typ, description="n", performed_by=U1.id, created_at=t)`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture); snapshots for `unchanged` / `nothing written` are taken here. **X** (only where listed, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`. A read card checks `X in db` (X is flushed, so it sits in the identity map and is **not** in `db.new`; Revision 3 convention fix) and, where nothing new may be pending, `not db.new`. Where being pending (unflushed) is the point, the card adds its own unflushed row and says so.

**Requests.** **RCV((L, "d"), …, **k)** = `PoReceiveEventCreate(event_type="receive", items=[{"po_item_id": L.id, "quantity_delta": Decimal("d")}, …], **k)`. **COR((L, "d"), …, note=n)** = the same with `event_type="correction"`, `correction_note=n`. **RQ((RL, "q"), …)** = `PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": RL.id, "quantity": Decimal("q")}, …])`. **RX(req)** = `svc.receive_replacements(db, po_id=O.id, return_id=R.id, workspace_id=W1.id, user_id=U2.id, data=req)`. **SRQ((L, "q"), …, t)** = `PurchaseOrderReturnCreate(return_type=t, reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=L.id, quantity_returned=Decimal("q"), unit_price=Decimal("500.00")), …])`.
**NEWPO(items)** = `PurchaseOrderCreate(account_id=A1.id, destination_type="storage", destination_id=F1.id, order_date=date(2026, 9, 1), description="Bearings", items=items)`. **NI(item, q)** = `PurchaseOrderItemCreate(item_id=item.id, quantity_ordered=Decimal(q), unit_price=Decimal("500.00"))`. Field names per the spec Overview, Input schemas.
**FakeOrig(msg, pgcode, table, column)** = an `Exception` subclass instance whose `str()` is `msg`, with `pgcode` and `diag = SimpleNamespace(table_name=table, column_name=column)`. **IERR(…)** = `IntegrityError("stmt", {}, FakeOrig(…))`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(type(R), R.id)`. **X not in db** (TC3, Revision 4) = the `session:` line every error card of a write method with X carries right after the raise, before any re-read and before the test's own rollback (the service's rollback expunges the flushed, uncommitted X); `committed: x_gone` alone runs after that rollback and cannot show the service rolled back. One error card per write method that is **not** its failing-commit card also runs inside **spies** and checks `rb.call_count >= 1` (`_commit_transaction` rolls back a failing commit itself, so the failing-commit card's own rollback does not count). **unchanged(R)** = after re-read, every column of R equals its commit-point snapshot. **gone(R)** = after `db.expire_all()`, `db.get(type(R), R.id) is None`. **x_gone** = `db.get(Workspace, X_ID) is None`.
- **EV(O)** = after `db.expire_all()`, O's `purchase_order_events` by `id`; **types(O)** = their `event_type` list (metadata in `metadata_json`). **itypes(V)** = `event_type` list of V's `invoice_events` by id. **LINES(V)** = V's `invoice_items` by `line_number`. **PAYS(V)** = V's `invoice_payments` by id; **SETTLE(V)** = those with `payment_method == "settled_by_replacement"`. All after `db.expire_all()`.
- **LEDGER(src)** = `inventory_ledger` rows with `source_type == "purchase_return_replacement"` and `source_id == src`, by id. **RCVLEDGER(O)** = `inventory_ledger` rows with `source_type == "po_receive_event_item"` and `workspace_id == W1.id`. **STOCK(F, I)** = the `inventory` row (model `Inventory`) of (W1, F, I) or None.
- **WARN(r)** = `PurchaseOrderReturnResponse.model_validate(r).warnings` (the new `warnings: list[str]` field, default `[]`, spec RX8d).
- **REVENTS(R)** = after `db.expire_all()`, `PurchaseOrderReturnEvent` rows with `return_id == R.id`, by `id` (metadata in `metadata_json`).
- **AUDIT(V)** = after `db.expire_all()`, `financial_audit_logs` rows (`text` SELECT on the table) with `entity_type = 'payment'`, `action_type = 'created'` in W1.
- **notes()** = all `Notification` rows by id after `db.expire_all()`; **recips()** = `sorted(n.recipient_user_id for n in notes())`.
- **nothing written** = row counts (all workspaces) of `purchase_orders`, `purchase_order_items`, `purchase_order_events`, `purchase_order_approvers`, `purchase_order_returns`, `purchase_order_return_items`, `po_receive_events`, `po_receive_event_items`, `account_invoices`, `invoice_items`, `invoice_events`, `invoice_payments`, `notifications`, `inventory_ledger`, `inventory`, `workspace_audit_logs` equal their commit-point values.
- **session clean** = right after the call, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted` (three asserts).
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; runs before any attribute of `r` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line re-reads with a fresh query. `session: usable` = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself), unless the When names `db.begin_nested()`. `schema` cards wrap only building the schema.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`.
- **Statement recorder** = an `after_cursor_execute` listener records every SQL statement sent during the When. **lock(T)** = the first recorded SELECT whose `FROM` names table T and contains `FOR UPDATE` (None if none). Clauses per the spec's **Row locks** table (Overview): **exact lock(T)** (single-table reads: `purchase_order_returns`, `account_invoices`) = `lock(T)` is not None, its text with trailing spaces stripped **ends with `FOR UPDATE`**, and it contains none of `SKIP LOCKED`, `NOWAIT`, `FOR UPDATE OF`. **exact lock OF(T)** (the joined order read: `purchase_orders`) = `lock(T)` is not None, its text with trailing spaces stripped **ends with `FOR UPDATE OF T`** (e.g. `FOR UPDATE OF purchase_orders`), and it contains neither `SKIP LOCKED` nor `NOWAIT`. **T before U** = `lock(T)` is sent before the first recorded SELECT whose `FROM` names U. **T locked before U** = `lock(T)` and `lock(U)` are both not None and `lock(T)` is recorded before `lock(U)`. **no lock** = no recorded statement contains `FOR UPDATE`. A recorder card ends its Given with `db.expunge_all()` after the commit point; ids come from values taken before.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and checks as shown, also when a method, parameter, column or field does not exist yet.

**Race simulations.** SD-10 only (`_sync_draft_invoice_for_po` SD8, "the order now has an invoice"): `patch.object(aim, "create_invoice", side_effect=…)` whose side effect links a fresh draft to the order, flushes, then raises `HTTPException(404, "Account not found")`. **Forced errors** (`Author: claude`): C-03 … C-07, U-10, AI-05, UI-06, CI-09, CI-10 patch the manager method or `svc._sync_draft_invoice_for_po` named in the card.

## `PurchaseOrderService._integrity_context`

### POS-IC-01 — table and column come from the error's diag
- **Rules:** `_integrity_context` IC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("null value", "23502", "purchase_order_items", "unit_price")`.

**When**
- `result = svc._integrity_context(err)`.

**Then**
1. returns: `result == ("purchase_order_items", "unit_price")`.

### POS-IC-02 — no orig gives (None, None)
- **Rules:** `_integrity_context` IC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IntegrityError("stmt", {}, None)`.

**When**
- `result = svc._integrity_context(err)`.

**Then**
1. returns: `result == (None, None)`.

### POS-IC-03 — an orig without diag gives (None, None)
- **Rules:** `_integrity_context` IC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `orig = Exception("x")` (no `diag` attribute); `err = IntegrityError("stmt", {}, orig)`.

**When**
- `result = svc._integrity_context(err)`.

**Then**
1. returns: `result == (None, None)`.

### POS-IC-04 — an empty column name counts as missing; the table is kept
- **Rules:** `_integrity_context` IC1a [BUG-3184]
- **Kind:** bug
- **Expect:** xfail BUG-3184
- **Fails today on:** Then 1 (the empty string is returned as is: `("account_invoices", "")`)

**Given**
1. `err = IERR("x", "23502", "account_invoices", "")`.

**When**
- `result = svc._integrity_context(err)`.

**Then**
1. returns: `result == ("account_invoices", None)`.

### POS-IC-05 — a falsy diag counts as missing
- **Rules:** `_integrity_context` IC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `FalsyDiag` = a class with `table_name = "account_invoices"`, `column_name = "invoice_date"` and `__bool__` returning `False`.
2. `orig = FakeOrig("x", "23502", None, None)`; then `orig.diag = FalsyDiag()`; `err = IntegrityError("stmt", {}, orig)`.

**When**
- `result = svc._integrity_context(err)`.

**Then**
1. returns: `result == (None, None)`.

## `PurchaseOrderService._handle_item_integrity_error`

### POS-IE-01 — check violation on received quantity → 400 ordered-vs-received, chained
- **Rules:** `_handle_item_integrity_error` IE1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_quantity_received", "23514", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Ordered quantity cannot be less than received quantity"`.
4. raises: `exc.value.__cause__ is err`.

### POS-IE-02 — text-only check violation naming "ordered" and "received" → same 400
- **Rules:** `_handle_item_integrity_error` IE1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("CHECK CONSTRAINT: Ordered must cover Received", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Ordered quantity cannot be less than received quantity"`.

### POS-IE-03 — check violation on paid amount → 400 total-vs-paid
- **Rules:** `_handle_item_integrity_error` IE1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_paid_amount", "23514", "account_invoices", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order total cannot be less than amount already paid on the linked invoice"`.

### POS-IE-04 — other check violation → 400 business rule
- **Rules:** `_handle_item_integrity_error` IE1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_unit_price", "23514", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Update violates a business rule. Check amounts and quantities."`.

### POS-IE-05 — check violation with "duplicate" in the text is still IE1 (IE1 first)
- **Rules:** `_handle_item_integrity_error` IE1, IE6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_x duplicate", "23514", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Update violates a business rule. Check amounts and quantities."`.

### POS-IE-06 — unique violation on the invoices table → 409 draft exists
- **Rules:** `_handle_item_integrity_error` IE2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("violates unique constraint uq_x", "23505", "account_invoices", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "A draft invoice for this order already exists"`.

### POS-IE-07 — unique violation in the invoice phase on a lines table → 409 draft exists
- **Rules:** `_handle_item_integrity_error` IE2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "A draft invoice for this order already exists"`.

### POS-IE-08 — unique violation on lines in the items phase → 409 catalog item
- **Rules:** `_handle_item_integrity_error` IE2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "That catalog item is already on this purchase order"`.

### POS-IE-09 — text "duplicate" without a pgcode → 409 catalog item
- **Rules:** `_handle_item_integrity_error` IE2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("Duplicate key value", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "That catalog item is already on this purchase order"`.

### POS-IE-10 — not-null on an invoice table with column → 400 sync text with location
- **Rules:** `_handle_item_integrity_error` IE3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "account_invoices", "invoice_date")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Could not sync the draft invoice for this order (account_invoices.invoice_date). Save the supplier section again, then retry editing items."`.

### POS-IE-11 — not-null on `invoice_status_tracker` → invoice sync text
- **Rules:** `_handle_item_integrity_error` IE3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "invoice_status_tracker", "status")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not sync the draft invoice for this order (invoice_status_tracker.status). Save the supplier section again, then retry editing items."`.

### POS-IE-12 — not-null on a line in the items phase → line incomplete with location
- **Rules:** `_handle_item_integrity_error` IE3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "purchase_order_items", "unit_price")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."`.

### POS-IE-13 — not-null with the table but no column → no location
- **Rules:** `_handle_item_integrity_error` IE3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Order line data is incomplete. Refresh the page and try again."`.

### POS-IE-14 — text "not-null constraint", invoice phase, no diag → invoice text, no location
- **Rules:** `_handle_item_integrity_error` IE3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates not-null constraint", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."`.

### POS-IE-15 — not-null with "duplicate" in the text is IE2
- **Rules:** `_handle_item_integrity_error` IE6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value duplicate", "23502", "purchase_order_items", "unit_price")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "That catalog item is already on this purchase order"`.

### POS-IE-16 — foreign key on `financial_audit_logs` → supplier or invoice invalid
- **Rules:** `_handle_item_integrity_error` IE4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `err = IERR("violates foreign key", "23503", "financial_audit_logs", "invoice_id")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."`.

### POS-IE-17 — foreign key on lines in the items phase → catalog reference missing
- **Rules:** `_handle_item_integrity_error` IE4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates foreign key", "23503", "purchase_order_items", "item_id")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."`.

### POS-IE-18 — text "foreign key constraint" in the invoice phase → supplier text
- **Rules:** `_handle_item_integrity_error` IE4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates foreign key constraint fk_x", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."`.

### POS-IE-19 — anything else in the invoice phase → fallback invoice text, logged
- **Rules:** `_handle_item_integrity_error` IE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("something odd", "XX000", None, None)`.

**When**
- inside `caplog.at_level(logging.ERROR)`: `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Could not sync the draft invoice after saving items. Refresh and try again."`.
4. count: `caplog.records` has at least 1 record with `levelname == "ERROR"`.

### POS-IE-20 — anything else in the items phase → fallback items text, chained
- **Rules:** `_handle_item_integrity_error` IE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("something odd", "XX000", None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not save order items. Refresh the page and try again."`.
3. raises: `exc.value.__cause__ is err`.

### POS-IE-21 — an unknown phase behaves as items
- **Rules:** `_handle_item_integrity_error` IE7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates unique constraint uq_x", "23505", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="lines")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "That catalog item is already on this purchase order"`.

### POS-IE-22 — the default phase is items
- **Rules:** `_handle_item_integrity_error` IE7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("something odd", "XX000", None, None)`.

**When**
- `svc._handle_item_integrity_error(err)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not save order items. Refresh the page and try again."`.

### POS-IE-23 — the mapper writes nothing and ends no transaction
- **Rules:** `_handle_item_integrity_error` IE8, IE9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".
2. X (after the commit point).
3. `err = IERR("null value in column", "23502", "purchase_order_items", "unit_price")`.

**When**
- spies: `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. session: `not db.dirty`.

### POS-IE-24 — pgcode 23514 alone (no check text) → IE1, ordered-vs-received
- **Rules:** `_handle_item_integrity_error` IE1 (pgcode branch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("new row rejected: quantity_ordered below received", "23514", "purchase_order_items", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Ordered quantity cannot be less than received quantity"`.

### POS-IE-25 — a check violation naming only "ordered" → business-rule text
- **Rules:** `_handle_item_integrity_error` IE1 (both words needed)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_ordered_positive", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Update violates a business rule. Check amounts and quantities."`.

### POS-IE-26 — a check violation naming only "received" → business-rule text
- **Rules:** `_handle_item_integrity_error` IE1 (both words needed)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates check constraint ck_received_nonneg", None, None, None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Update violates a business rule. Check amounts and quantities."`.

### POS-IE-27 — pgcode 23505 alone (no unique text) → IE2, catalog item
- **Rules:** `_handle_item_integrity_error` IE2 (pgcode branch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("row rejected", "23505", "purchase_order_items", "item_id")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "That catalog item is already on this purchase order"`.

### POS-IE-28 — pgcode 23502 alone (no not-null text) → IE3, line incomplete
- **Rules:** `_handle_item_integrity_error` IE3 (pgcode branch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("row rejected", "23502", "purchase_order_items", "unit_price")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."`.

### POS-IE-29 — not-null on `financial_audit_logs` in the items phase → invoice sync text
- **Rules:** `_handle_item_integrity_error` IE3 (table list)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "financial_audit_logs", "invoice_id")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Could not sync the draft invoice for this order (financial_audit_logs.invoice_id). Save the supplier section again, then retry editing items."`.

### POS-IE-30 — not-null in the invoice phase with the table only → no location
- **Rules:** `_handle_item_integrity_error` IE3 (`{loc}` needs both)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", "account_invoices", None)`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."`.

### POS-IE-31 — not-null in the invoice phase with the column only → no location
- **Rules:** `_handle_item_integrity_error` IE3 (`{loc}` needs both)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("null value in column", "23502", None, "invoice_date")`.

**When**
- `svc._handle_item_integrity_error(err, phase="invoice")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."`.

### POS-IE-32 — foreign key on `account_invoices` in the items phase → supplier or invoice invalid
- **Rules:** `_handle_item_integrity_error` IE4 (table list)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `err = IERR("violates foreign key", "23503", "account_invoices", "account_id")`.

**When**
- `svc._handle_item_integrity_error(err, phase="items")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."`.

## `PurchaseOrderService._build_invoice_items_from_po`

### POS-BI-01 — one dict per line, by line number, with every field
- **Rules:** `_build_invoice_items_from_po` BI1, BI2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `l2 = SimpleNamespace(id=72, line_number=2, item_name="Cement", item_id=8, quantity_ordered=Decimal("5.00"), quantity_received=Decimal("1.00"), item_unit="bag", unit_price=Decimal("300.00"), line_subtotal=Decimal("1500.00"))`.
2. `l1 = SimpleNamespace(id=71, line_number=1, item_name="Bearing", item_id=7, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("0.00"), item_unit="pcs", unit_price=Decimal("500.00"), line_subtotal=Decimal("5000.00"))`.
3. `po = SimpleNamespace(line_items=[l2, l1])`.

**When**
- `result = svc._build_invoice_items_from_po(po)`.

**Then**
1. returns: `[d["line_number"] for d in result] == [1, 2]`.
2. returns: `result[0] == {"line_number": 1, "description": "Bearing", "item_id": 7, "source_order_item_id": 71, "source_order_item_type": "po_item", "quantity": Decimal("10.00"), "unit": "pcs", "unit_price": Decimal("500.00"), "line_subtotal": Decimal("5000.00")}`.
3. returns: `result[1]["quantity"] == Decimal("5.00")` (ordered, not received).

### POS-BI-02 — no lines → empty list
- **Rules:** `_build_invoice_items_from_po` BI1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `po = SimpleNamespace(line_items=[])`.

**When**
- `result = svc._build_invoice_items_from_po(po)`.

**Then**
1. returns: `result == []`.

### POS-BI-03 — `line_items` None → empty list
- **Rules:** `_build_invoice_items_from_po` BI1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `po = SimpleNamespace(line_items=None)`.

**When**
- `result = svc._build_invoice_items_from_po(po)`.

**Then**
1. returns: `result == []`.

### POS-BI-04 — an empty item name falls back to `Item <item_id>`
- **Rules:** `_build_invoice_items_from_po` BI2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `l1 = SimpleNamespace(id=71, line_number=1, item_name="", item_id=7, quantity_ordered=Decimal("10.00"), item_unit="pcs", unit_price=Decimal("500.00"), line_subtotal=Decimal("5000.00"))`; `po = SimpleNamespace(line_items=[l1])`.

**When**
- `result = svc._build_invoice_items_from_po(po)`.

**Then**
1. returns: `result[0]["description"] == "Item 7"`.

## `PurchaseOrderService._delete_linked_draft_invoice_for_po`

### POS-DD-01 — no invoice linked → nothing written
- **Rules:** `_delete_linked_draft_invoice_for_po` DD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: session clean.
3. nothing written: nothing written.

### POS-DD-02 — an invoice of another workspace linked → nothing written
- **Rules:** `_delete_linked_draft_invoice_for_po` DD1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. V9 = inv(O), but of W2 (`workspace_id W2.id`, `account_id A9.id`), linked to O.

**When**
- `svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. session: session clean.
2. unchanged: unchanged(V9).
3. re-read O: `invoice_id == V9.id`.

### POS-DD-03 — a confirmed invoice is not deleted
- **Rules:** `_delete_linked_draft_invoice_for_po` DD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. V = inv(O), but finalized, linked to O.

**When**
- `svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. session: session clean.
2. unchanged: unchanged(V).
3. nothing written: nothing written.

### POS-DD-04 — the draft-deleted event records the deleted draft's id
- **Rules:** `_delete_linked_draft_invoice_for_po` DD2a [BUG-3185]
- **Kind:** bug
- **Expect:** xfail BUG-3185
- **Fails today on:** Then 1 (`metadata_json == {"invoice_id": None}`: the delete clears `po.invoice_id` before the unlink reads it)

**Given**
1. O = po "1".
2. V = inv(O), linked to O. `vid = V.id`.

**When**
- `svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. event: `[e.metadata_json for e in EV(O) if e.event_type == "invoice_draft_deleted"] == [{"invoice_id": vid}]`.

### POS-DD-05 — a draft with payment history is refused by the invoice manager and stays
- **Rules:** `_delete_linked_draft_invoice_for_po` DD2 [BUG-639] (pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1–3 (BUG-639 is open: `delete_invoice` does not refuse a draft with payment rows with the PAYHIST 400; executor notes rev 2)

**Given**
1. O = po "1".
2. V = inv(O), but `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O.
3. cash(V, "100.00").

**When**
- `db.begin_nested()`, then `svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == PAYHIST`.
4. count: `account_invoices` with `id == V.id`: 1 (after the savepoint is rolled back).

### POS-DD-06 — a draft is deleted, the order unlinked, one event; flushed, not committed
- **Rules:** `_delete_linked_draft_invoice_for_po` DD2 (the part that holds today and after BUG-3185)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1".
2. V = inv(O), linked to O. `vid = V.id`.

**When**
- spies: `svc._delete_linked_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. re-read O: `invoice_id is None`.
4. count: `account_invoices` with `id == vid`: 0.
5. event: `types(O).count("invoice_draft_deleted") == 1`; that event has `description == f"Draft invoice #{vid} deleted"` and `"invoice_id" in metadata_json` (its value is BUG-3185's, DD-04).

## `PurchaseOrderService._sync_draft_invoice_for_po`

### POS-SD-01 — financially locked → None, nothing written
- **Rules:** `_sync_draft_invoice_for_po` SD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. V = inv(O), but finalized, linked to O.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: session clean.
3. unchanged: unchanged(V).
4. nothing written: nothing written.

### POS-SD-02 — not forced, not confirmed → the linked draft is removed
- **Rules:** `_sync_draft_invoice_for_po` SD2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`.
2. V = inv(O), linked to O. `vid = V.id`.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `account_invoices` with `id == vid`: 0.
3. re-read O: `invoice_id is None`.
4. event: `types(O)[-1] == "invoice_draft_deleted"`.

### POS-SD-03 — not forced, not confirmed, nothing linked → None, nothing written
- **Rules:** `_sync_draft_invoice_for_po` SD2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.
2. L = poline(O, 1).

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: session clean.
3. nothing written: nothing written.

### POS-SD-04 — forced, not confirmed → 422
- **Rules:** `_sync_draft_invoice_for_po` SD3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.
2. L = poline(O, 1).

**When**
- `db.begin_nested()`, then `svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id, force_create=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == FORCE422`.
4. session: session clean.

### POS-SD-05 — confirmed but no supplier → None, nothing written
- **Rules:** `_sync_draft_invoice_for_po` SD4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready, `account_id None`.
2. L = poline(O, 1).

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### POS-SD-06 — confirmed, no invoice → a draft mirroring the order is created and linked
- **Rules:** `_sync_draft_invoice_for_po` SD5, SD6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, int)`.
2. re-read O: `invoice_id == result`, `invoice_ever_linked is True`.
3. re-read invoice `result`: `account_id == A1.id`, `order_id == O.id`, `order_type == "purchase_order"`, `invoice_type == "payable"`, `invoice_status == "draft"`.
4. re-read invoice `result`: `invoice_number is None`, `vendor_invoice_number is None`, `due_date is None`, `payment_locked_reason is None`, `allow_payments is True`.
5. re-read invoice `result`: `description == f"Purchase order {O.po_number}"`, `notes == "Bearings for Press 4"`, `invoice_amount == Decimal("5000.00")`.
6. re-read: `LINES(result)` has 1 row: `source_order_item_id == L.id`, `source_order_item_type == "po_item"`, `quantity == Decimal("10.00")`, `unit_price == Decimal("500.00")`.
7. event: `EV(O)[-1].event_type == "invoice_draft_created"`, `EV(O)[-1].description == f"Draft invoice #{result} linked to {O.po_number}"`, `EV(O)[-1].metadata_json == {"invoice_id": result}`.

### POS-SD-07 — the new draft is dated with the UTC clock
- **Rules:** `_sync_draft_invoice_for_po` SD7 [BUG-3167]
- **Kind:** bug
- **Expect:** xfail BUG-3167
- **Fails today on:** Then 2 (dated `date.today()`, the machine's real date, not the patched UTC date)

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, int)`.
2. re-read invoice `result`: `invoice_date == TODAY_UTC`.

### POS-SD-08 — the supplier is not found in the workspace → 422 re-select
- **Rules:** `_sync_draft_invoice_for_po` SD8; HR-16
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `account_id A9.id` (W2's account; invalid data).
2. L = poline(O, 1).

**When**
- `db.begin_nested()`, then `svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == SUPP422`.

### POS-SD-09 — another refusal of the invoice create passes unchanged
- **Rules:** `_sync_draft_invoice_for_po` SD5, SD8
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = `Account(workspace_id=W1.id, name="No Bills Ltd", is_active=True, is_deleted=False, allow_invoices=False)`.
2. O = po "1", but ready, `account_id A2.id`.
3. L = poline(O, 1).

**When**
- `db.begin_nested()`, then `svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.

### POS-SD-10 — create answers 404 but the order now has an invoice → None, no error
- **Rules:** `_sync_draft_invoice_for_po` SD8
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. Race simulation (Conventions): `aim.create_invoice` patched to link a new draft inv(O) to O, flush, then raise `HTTPException(404, "Account not found")`.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read O: `invoice_id is not None`.

### POS-SD-11 — a linked voided invoice → None, nothing written
- **Rules:** `_sync_draft_invoice_for_po` SD9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. V = inv(O), but voided-inv, linked to O.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(V).
3. nothing written: nothing written.

### POS-SD-12 — a linked invoice of another workspace → None, nothing written
- **Rules:** `_sync_draft_invoice_for_po` SD9; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. V9 = inv(O), but of W2, linked to O.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(V9).
3. nothing written: nothing written.

### POS-SD-13 — draft account changed and invoice confirmed → unconfirm, reset, notify, event
- **Rules:** `_sync_draft_invoice_for_po` SD10, SD11; `PurchaseOrderManager.reset_approvals` R2 (pass-through); Overview (notification `entity_type`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A2 = `Account(workspace_id=W1.id, name="Beta Traders", is_active=True, is_deleted=False, allow_invoices=True)`.
2. O = po "1", but ready, `invoice_confirmed True`.
3. L = poline(O, 1).
4. V = inv(O), but `account_id A2.id`; then `O.invoice_id = V.id`, `O.invoice_ever_linked = True`, flush.
5. P3 = poappr(O, U3), but approved.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read O: `invoice_confirmed is False`.
3. re-read P3: `approved is False`.
4. re-read V: `account_id == A1.id`.
5. notification: `[(n.recipient_user_id, n.notification_type) for n in notes()] == [(U1.id, "section_confirm")]`.
6. notification: `notes()[0].preview == "Draft invoice changed — approvals reset; re-confirm sections"`.
7. event: `"invoice_unconfirmed" in types(O)`; that event's `description == "Draft invoice unconfirmed after order sync"`.
8. event: `types(O).count("approvals_reset") == 1`; that event's `description == "Draft invoice changed after order update (1 approval(s) cleared)"` (SD10 reason, per `reset_approvals` R2).
9. notification: `notes()[0].entity_type == "purchase_order"`, `notes()[0].entity_id == O.id`.

### POS-SD-14 — account changed but invoice not confirmed → account synced, no reset
- **Rules:** `_sync_draft_invoice_for_po` SD10, SD11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A2 = `Account(workspace_id=W1.id, name="Beta Traders", is_active=True, is_deleted=False, allow_invoices=True)`.
2. O = po "1", but ready.
3. L = poline(O, 1).
4. V = inv(O), but `account_id A2.id`; then `O.invoice_id = V.id`, `O.invoice_ever_linked = True`, flush.
5. P3 = poappr(O, U3), but approved.

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read V: `account_id == A1.id`.
3. re-read P3: `approved is True`.
4. notification: `notes() == []`.
5. event: `"invoice_unconfirmed" not in types(O)`.

### POS-SD-15 — description and notes differing are updated; lines re-copied
- **Rules:** `_sync_draft_invoice_for_po` SD11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. V = inv(O), but `description "Old"`, `notes "Old notes"`, linked to O.
4. invl(V, 1, "1.00").

**When**
- `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read V: `description == f"Purchase order {O.po_number}"`, `notes == "Bearings for Press 4"`.
3. re-read: `LINES(V)` has 1 row with `source_order_item_id == L.id`, `unit_price == Decimal("500.00")`.
4. event: `itypes(V).count("items_synced") == 1`.

### POS-SD-16 — nothing differs → no update call, lines still re-copied
- **Rules:** `_sync_draft_invoice_for_po` SD11
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).
3. V = inv(O), but `description f"Purchase order {O.po_number}"`, `notes "Bearings for Press 4"`, linked to O.

**When**
- with `patch.object(aim, "update_invoice", wraps=aim.update_invoice) as up`: `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `up.call_count == 0`.
3. event: `itypes(V).count("items_synced") == 1`.

### POS-SD-17 — empty notes and `None` description count as equal
- **Rules:** `_sync_draft_invoice_for_po` SD11
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready, `description None`.
2. L = poline(O, 1).
3. V = inv(O), but `description f"Purchase order {O.po_number}"`, `notes ""`, linked to O.

**When**
- with `patch.object(aim, "update_invoice", wraps=aim.update_invoice) as up`: `svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `up.call_count == 0`.

### POS-SD-18 — the helper flushes only
- **Rules:** `_sync_draft_invoice_for_po` Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1).

**When**
- spies: `result = svc._sync_draft_invoice_for_po(db, po=O, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, int)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

## `PurchaseOrderService._emit_po_invoice_draft_notification`

### POS-EN-01 — no invoice id → nothing
- **Rules:** `_emit_po_invoice_draft_notification` EN1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. poappr(O, U3).

**When**
- `svc._emit_po_invoice_draft_notification(db, po=O, workspace_id=W1.id, user_id=U2.id, invoice_id=None)`.

**Then**
1. session: `not db.new`.
2. notification: `notes() == []`.

### POS-EN-02 — a new draft notifies the pending approver and the creator; flushed only
- **Rules:** `_emit_po_invoice_draft_notification` EN2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poappr(O, U3).
3. V = inv(O), linked to O.

**When**
- spies: `svc._emit_po_invoice_draft_notification(db, po=O, workspace_id=W1.id, user_id=U2.id, invoice_id=V.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. notification: `recips() == sorted([U1.id, U3.id])`.
4. notification: every row has `notification_type == "invoice_action"`, `entity_type == "purchase_order"`, `entity_id == O.id`, `preview == DRAFTP`.

## Shared: return-in-progress flag (`has_open_return`)

### POS-RF-01 — GET of an order with a pending return carries `has_open_return True`
- **Rules:** RF1 [BUG-2789]
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (the response has no `has_open_return`)

**Given**
1. O = po "1", but proj.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. R = ret "1" of O.

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result.has_open_return is True`.

### POS-RF-02 — only completed and voided returns → `has_open_return False`
- **Rules:** RF1 [BUG-2789]
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (the response has no `has_open_return`)

**Given**
1. O = po "1", but proj.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. ret "1" of O, but completed.
4. ret "2" of O, but voided-ret.

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result.has_open_return is False`.

### POS-RF-03 — another workspace's pending return on the same order id does not count
- **Rules:** RF1 [BUG-2789]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (the response has no `has_open_return`)

**Given**
1. O = po "1", but proj.
2. R9 = ret "9" of O, but `workspace_id W2.id` (invalid data).

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result.has_open_return is False`.

### POS-RF-04 — list rows each carry their own flag
- **Rules:** RF1 [BUG-2789]
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (the list rows have no `has_open_return`)

**Given**
1. O1 = po "1", but proj. O2 = po "2", but proj.
2. ret "1" of O1.

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `sorted(o.id for o in result.items) == sorted([O1.id, O2.id])`.
2. returns: `{o.id: o.has_open_return for o in result.items} == {O1.id: True, O2.id: False}`.

### POS-RF-05 — the update response carries the flag
- **Rules:** RF1 [BUG-2789]; `update_purchase_order` U5
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (the response has no `has_open_return`)

**Given**
1. O = po "1", but proj.
2. ret "1" of O.

**When**
- `result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result.has_open_return is True`.

### POS-RF-06 — completing the last pending return turns the flag off, nothing written on the order
- **Rules:** RF2 [BUG-2789]
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 3 (the response has no `has_open_return`)

**Given**
1. O = po "1", but proj, ready, complete.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. R = ret "1" of O.
4. rline(R, L, "2").
5. `svc.complete_return(db, po_id=O.id, return_id=R.id, workspace_id=W1.id, user_id=U2.id)` (a Given step), then snapshot `status_before = O.current_status_id`.

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `current_status_id == status_before`.
3. returns: `result.has_open_return is False`.

### POS-RF-07 — reading the flag writes nothing
- **Rules:** RF3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but proj.
2. ret "1" of O.
3. X (after the commit point).

**When**
- spies: `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. session: `not db.new` (the read added nothing pending).

## `PurchaseOrderService.create_purchase_order`

### POS-C-01 — a new order is committed and returned re-read; no invoice, no notification
- **Rules:** `create_purchase_order` C1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `result = svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, PurchaseOrder)`, `result.id is not None`.
3. committed: the `purchase_orders` row `result.id` has `workspace_id == W1.id`, `account_id == A1.id`, `created_by == U2.id`, `current_status_id == SD1.id`, `order_workflow_id == WF1.id`, `invoice_id is None`.
4. committed: `purchase_order_items` of `result.id`: exactly 1.
5. committed: `account_invoices` with `order_type == "purchase_order"` and `order_id == result.id`: 0.
6. committed: `notes() == []`.

### POS-C-02 — `current_status_id` / `order_workflow_id` in the body have no effect
- **Rules:** `create_purchase_order` C3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `result = svc.create_purchase_order(db, po_in=PurchaseOrderCreate(**{**NEWPO([NI(I1, "10")]).model_dump(), "current_status_id": SR1.id, "order_workflow_id": None}), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the `purchase_orders` row `result.id` has `current_status_id == SD1.id`, `order_workflow_id == WF1.id`.

### POS-C-03 — a PO-number clash is retried; the second attempt saves the order
- **Rules:** `create_purchase_order` C2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. W1 has no purchase orders.
2. `mgr.create_purchase_order` patched: the first call raises `IERR("duplicate key violates uq_po_workspace_number", "23505", "purchase_orders", "po_number")`, later calls run the real method; `m` = the mock.

**When**
- `result = svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. mock called: `m.call_count == 2`.
3. committed: W1 has exactly 1 `purchase_orders` row.

### POS-C-04 — five clashes → 409, nothing saved
- **Rules:** `create_purchase_order` C2
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. W1 has no purchase orders.
2. `mgr.create_purchase_order` patched to raise `IERR("duplicate key value po_number", "23505", "purchase_orders", "po_number")` on every call; `m` = the mock.

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Could not assign a unique PO number. Please try again."`.
4. raises: `isinstance(exc.value.__cause__, IntegrityError)`.
5. mock called: `m.call_count == 5`.
6. committed: W1 has 0 `purchase_orders` rows.

### POS-C-05 — a first-try success makes one attempt
- **Rules:** `create_purchase_order` C2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `mgr.create_purchase_order` wrapped (`wraps=`, real behaviour); `m` = the mock.

**When**
- `result = svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. mock called: `m.call_count == 1`.

### POS-C-06 — another IntegrityError is rolled back and re-raised as the same object, no retry
- **Rules:** `create_purchase_order` C4; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `err = IERR("violates foreign key fk_items", "23503", "purchase_order_items", "item_id")`; `mgr.create_purchase_order` patched to raise `err`; `m` = the mock.
2. X (after the commit point).

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError`; `exc.value is err`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `m.call_count == 1`.
4. committed: x_gone.

### POS-C-07 — a non-HTTP error is rolled back and re-raised as the same object
- **Rules:** `create_purchase_order` C4; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `err = RuntimeError("manager broke")`; `mgr.create_purchase_order` patched to raise `err`.
2. X (after the commit point).

**When**
- spies: `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `RuntimeError`; `exc.value is err`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
4. committed: x_gone.

### POS-C-08 — the manager's 409 for a repeated item passes unchanged
- **Rules:** `create_purchase_order` C5 (part that holds today)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "5"), NI(I1, "3")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Bearing appears more than once on this order"`.

### POS-C-09 — after the manager's 409 the session is rolled back: nothing pending
- **Rules:** `create_purchase_order` C5 [BUG-3175]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3175
- **Fails today on:** Then 3 (no rollback: the flushed order is still found in the same session, and so is the marker row)

**Given**
1. W1 has no purchase orders.
2. MK = `Department(workspace_id=W1.id, name=f"Marker {TAG}")`, flushed after the commit point, not committed; `MK_ID = MK.id` (spec Notes for the test designer, G14).

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "5"), NI(I1, "3")]), workspace_id=W1.id, user_id=U2.id)` (the duplicate line makes the manager refuse with 409 after it flushed the order). `NEWPO`'s description is `"Bearings"`.

**Then** (checks 3 and 4 run in the same session, **before** any test-level `db.rollback()`)
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. count: `db.query(PurchaseOrder).filter_by(workspace_id=W1.id, description="Bearings").count() == 0`.
4. session: `db.get(Department, MK_ID) is None` (TC3: every pending change discarded; checked after `db.expire_all()`).

### POS-C-10 — a failing commit is rolled back and re-raised; no order saved
- **Rules:** `create_purchase_order` C1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has 0 `purchase_orders` rows.
4. nothing written: nothing written.

### POS-C-11 — a failing re-read after the commit leaves the order saved
- **Rules:** `create_purchase_order` C1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `purchase_orders` row.

### POS-C-12 — clashes naming only `uq_po_workspace_number` are retried too; the 5th → 409
- **Rules:** `create_purchase_order` C2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. W1 has no purchase orders.
2. `mgr.create_purchase_order` patched to raise `IERR('duplicate key value violates unique constraint "uq_po_workspace_number"', "23505", "purchase_orders", None)` on every call (the text has no `po_number`); `m` = the mock.

**When**
- `svc.create_purchase_order(db, po_in=NEWPO([NI(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Could not assign a unique PO number. Please try again."`.
4. mock called: `m.call_count == 5`.
5. committed: W1 has 0 `purchase_orders` rows.

## `PurchaseOrderService.update_purchase_order`

### POS-U-01 — an edit is committed and returned re-read
- **Rules:** `update_purchase_order` U1, U4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. poline(O, 1).

**When**
- `result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(description="Spare bearings"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: O has `description == "Spare bearings"`, `invoice_id is None`.
4. committed: `notes() == []`.

### POS-U-02 — a missing order → 404, rolled back
- **Rules:** `update_purchase_order` U1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. X (after the commit point).

**When**
- `svc.update_purchase_order(db, po_id=MISSING, po_in=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. nothing written: nothing written.

### POS-U-03 — a W0 order id → 404, the W0 order unchanged
- **Rules:** `update_purchase_order` U1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0.
2. O = po "1".

**When**
- `svc.update_purchase_order(db, po_id=O0.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. unchanged: unchanged(O0).

### POS-U-04 — a W2 order id → 404, the W2 order unchanged
- **Rules:** `update_purchase_order` U1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. O9 = po "9", but of W2.

**When**
- `svc.update_purchase_order(db, po_id=O9.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. unchanged: unchanged(O9).

### POS-U-05 — confirming the last section drafts the invoice in the same commit
- **Rules:** `update_purchase_order` U3, U4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.
2. poline(O, 1).
3. poappr(O, U3).

**When**
- `result = svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: O has `items_confirmed is True`, `invoice_id is not None`.
3. committed: that invoice has `invoice_status == "draft"`, `invoice_type == "payable"`, `order_id == O.id`.
4. committed: `"invoice_draft_created" in types(O)`.

### POS-U-06 — not ready → ready: approval-pending and draft notices
- **Rules:** `update_purchase_order` U2, U3; `_emit_po_invoice_draft_notification` EN2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`.
2. poline(O, 1).
3. poappr(O, U3).

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. notification: `sorted((n.recipient_user_id, n.notification_type) for n in notes()) == sorted([(U3.id, "approval_pending"), (U3.id, "invoice_action"), (U1.id, "invoice_action")])`.
2. notification: every `invoice_action` row has `preview == DRAFTP`.

### POS-U-07 — an unconfirm removes the draft and tells the creator approvals were reset
- **Rules:** `update_purchase_order` U2, U3; `_sync_draft_invoice_for_po` SD2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poline(O, 1).
3. V = inv(O), linked to O. `vid = V.id`.
4. poappr(O, U3), but approved.

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: `account_invoices` with `id == vid`: 0.
2. committed: O has `invoice_id is None`, `items_confirmed is False`.
3. notification: some row of `notes()` has `recipient_user_id == U1.id` and `"Approvals were reset — re-confirm sections before approving" in preview` (contains).

### POS-U-08 — an edit of a confirmed, unlocked order re-syncs the draft
- **Rules:** `update_purchase_order` U3; SD11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poline(O, 1).
3. V = inv(O), but `description "Old"`, linked to O.

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: V has `description == f"Purchase order {O.po_number}"`.
2. committed: `"items_synced" in itypes(V)`.
3. committed: O has `expected_delivery_date == date(2026, 10, 1)`.

### POS-U-09 — the manager's refusal passes unchanged and is rolled back
- **Rules:** `update_purchase_order` U1, U4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `details_confirmed True`.
2. X (after the commit point).

**When**
- spies: `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(description="x"), workspace_id=W1.id, user_id=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order details are confirmed"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(O).

### POS-U-10 — an IntegrityError in the invoice step is translated (invoice phase) and rolls back the edit
- **Rules:** `update_purchase_order` U4; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready.
2. poline(O, 1).
3. `svc._sync_draft_invoice_for_po` patched to raise `IERR("null value in column", "23502", None, None)`.
4. X (after the commit point).

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(expected_delivery_date=date(2026, 10, 1)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Could not sync the draft invoice for this order. Save the supplier section again, then retry editing items."`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. committed: O has `expected_delivery_date is None`.

### POS-U-11 — a failing commit is rolled back; the edit is not saved
- **Rules:** `update_purchase_order` U4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(description="Spare bearings"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `description == "Bearings for Press 4"`.

### POS-U-12 — a confirm field sent as explicit `null` is not an unconfirm
- **Rules:** `update_purchase_order` U2 (fields sent and not `null`); `detect_section_unconfirmed` R1 (pass-through)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poline(O, 1).
3. P3 = poappr(O, U3), but approved.

**When**
- `svc.update_purchase_order(db, po_id=O.id, po_in=PurchaseOrderUpdate(items_confirmed=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: O has `items_confirmed is True`, `supplier_confirmed is True`, `details_confirmed is True`.
2. committed: P3 has `approved is True`.
3. notification: no row of `notes()` has `"Approvals were reset" in preview` (contains).

## `PurchaseOrderService.get_purchase_order`

### POS-G-01 — returns the order; no commit, no rollback; summaries keep defaults
- **Rules:** `get_purchase_order` G1, G2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. poline(O, 1).
3. X (after the commit point).

**When**
- spies: `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `not hasattr(result, "item_count")` (the ORM order has no summary attributes, G1).
3. returns: `PurchaseOrderResponse.model_validate(result).item_count == 0`; `result.invoice_payment_status is None`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `X in db`.

### POS-G-02 — a W0 order id → 404; no rollback, X still in the session
- **Rules:** `get_purchase_order` G1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0.
2. X (after the commit point).

**When**
- spies: `svc.get_purchase_order(db, po_id=O0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. mock called: `rb.call_count == 0`.
5. mock called: `cm.call_count == 0`.
6. session: `X in db`.

### POS-G-03 — a W2 order id → 404
- **Rules:** `get_purchase_order` G1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. O9 = po "9", but of W2.

**When**
- `svc.get_purchase_order(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.

### POS-G-04 — a voided order is returned
- **Rules:** `get_purchase_order` G1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = po "1", but voided.

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`, `result.voided is True`.

### POS-G-05 — `invoice_payment_status` comes from the linked invoice
- **Rules:** `get_purchase_order` G1; AP1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poline(O, 1).
3. V = inv(O), but finalized, `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O.

**When**
- `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.invoice_payment_status == "partial"`.

### POS-G-06 — a stale stage is repaired and committed, with one performer-less event
- **Rules:** `get_purchase_order` G2 (Q8 intended)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True` (stage `SD1`, derived `Planning`).

**When**
- spies: `result = svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.current_status_id == SP1.id`.
2. mock called: `cm.call_count == 1`.
3. committed: O has `current_status_id == SP1.id`.
4. committed: `[e for e in EV(O) if e.event_type == "status_updated"]` has 1 row with `performed_by is None`.

### POS-G-07 — a failing repair raises with no rollback
- **Rules:** `get_purchase_order` G2
- **Kind:** error
- **Expect:** pass

**Given**
1. `db.delete(SP1)`, flush.
2. O = po "1", but `supplier_confirmed True`.

**When**
- spies: `svc.get_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Purchase order stage status 'Planning' not found for this workspace"`.
4. mock called: `rb.call_count == 0`.
5. mock called: `cm.call_count == 0`.

## `PurchaseOrderService.mark_order_complete`

### POS-MC-01 — a fully received order is completed and committed; nobody told
- **Rules:** `mark_order_complete` MC1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. poline(O, 1), but `quantity_received Decimal("10.00")`.
3. V = inv(O), but finalized, linked to O.

**When**
- `result = svc.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: O has `current_status_id == SC1.id`.
4. committed: `notes() == []`.
5. unchanged: unchanged(V).

### POS-MC-02 — not fully received → 400, rolled back
- **Rules:** `mark_order_complete` MC1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. poline(O, 1), but `quantity_received Decimal("9.00")`.
3. X (after the commit point).

**When**
- spies: `svc.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "All line items must be fully received before marking the order complete"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(O).

### POS-MC-03 — an open return → 400
- **Rules:** `mark_order_complete` MC1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, proj, `current_status_id SR1.id`.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. ret "1" of O.

**When**
- `svc.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Complete all open returns before marking the order complete"`.

### POS-MC-04 — a failing commit leaves the order not complete
- **Rules:** `mark_order_complete` MC1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. poline(O, 1), but `quantity_received Decimal("10.00")`.

**When**
- `svc.mark_order_complete(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `current_status_id == SR1.id`.

## `PurchaseOrderService.list_purchase_orders`

### POS-LP-01 — returns exactly the page for the same arguments
- **Rules:** `list_purchase_orders` LP1
- **Kind:** happy
- **Expect:** pass

**Given**
1. po "1"; po "2"; po "3".

**When**
- `result = svc.list_purchase_orders(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `[o.id for o in result.items] == [o.id for o in svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=1000).items]`.
2. returns: `result.total == 3`.

### POS-LP-02 — the default limit is 100
- **Rules:** `list_purchase_orders` LP1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders po "1" … po "101".

**When**
- `result = svc.list_purchase_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.limit == 100`.
2. returns: `len(result.items) == 100`.
3. returns: `result.total == 101`, `result.has_more is True`.

### POS-LP-03 — an unknown keyword filter raises TypeError
- **Rules:** `list_purchase_orders` LP1
- **Kind:** error
- **Expect:** pass

**Given**
1. po "1".

**When**
- `svc.list_purchase_orders(db, workspace_id=W1.id, colour="red")`.

**Then**
1. raises: `TypeError`.

### POS-LP-04 — a read: no commit, no rollback
- **Rules:** `list_purchase_orders` LP1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. po "1".
2. X (after the commit point).

**When**
- spies: `result = svc.list_purchase_orders(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `PurchaseOrderService._hub_filter_kwargs`

### POS-HF-01 — defaults give exactly the eleven keys
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs()`.

**Then**
1. returns: `result == {"account_id": None, "invoice_id": None, "date_from": None, "date_to": None, "status_ids": None, "factory_id": None, "destination_type": None, "invoice_filter": None, "search": None, "exclude_complete": False, "exclude_voided": False}`.

### POS-HF-02 — values pass unchanged
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs(account_id=5, invoice_id=6, date_from=date(2026, 9, 1), date_to=date(2026, 9, 30), status_ids=[1, 2], factory_id=7, destination_type="machine", invoice_filter="missing", search="Bear", exclude_complete=True, exclude_voided=True)`.

**Then**
1. returns: `result == {"account_id": 5, "invoice_id": 6, "date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30), "status_ids": [1, 2], "factory_id": 7, "destination_type": "machine", "invoice_filter": "missing", "search": "Bear", "exclude_complete": True, "exclude_voided": True}`.

### POS-HF-03 — `invoice_filter ""` → None
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="")`.

**Then**
1. returns: `result["invoice_filter"] is None`.

### POS-HF-04 — `invoice_filter "all"` → None
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="all")`.

**Then**
1. returns: `result["invoice_filter"] is None`.

### POS-HF-05 — `invoice_filter "All"` is kept
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="All")`.

**Then**
1. returns: `result["invoice_filter"] == "All"`.

### POS-HF-06 — `invoice_filter " all"` is kept
- **Rules:** `_hub_filter_kwargs` HF1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter=" all")`.

**Then**
1. returns: `result["invoice_filter"] == " all"`.

## `PurchaseOrderService._prepare_listed_orders`

### POS-PL-01 — attaches payment status and summaries; same list, same order
- **Rules:** `_prepare_listed_orders` PL1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po "1". O2 = po "2", but ready.
2. poline(O2, 1).
3. V = inv(O2), but finalized, `payment_status "partial"`, `paid_amount Decimal("100.00")`, linked to O2.
4. `orders = [O2, O1]`.

**When**
- `result = svc._prepare_listed_orders(db, workspace_id=W1.id, orders=orders)`.

**Then**
1. returns: `[o.id for o in result] == [O2.id, O1.id]`.
2. returns: `result[0].invoice_payment_status == "partial"`, `result[0].item_count == 1`.
3. returns: `result[1].invoice_payment_status is None`, `result[1].item_count == 0`.

### POS-PL-02 — every stale order on the page is repaired
- **Rules:** `_prepare_listed_orders` PL2 [BUG-3178]
- **Kind:** bug
- **Expect:** xfail BUG-3178
- **Fails today on:** Then 2 (the repair stops after the first stale order)

**Given**
1. O1, O2, O3 = po "1", po "2", po "3", each but `supplier_confirmed True` (stage SD1, derived Planning).

**When**
- `result = svc._prepare_listed_orders(db, workspace_id=W1.id, orders=[O1, O2, O3])`.

**Then**
1. returns: `[o.id for o in result] == [O1.id, O2.id, O3.id]`.
2. committed: O2 has `current_status_id == SP1.id`.
3. committed: O3 has `current_status_id == SP1.id`.

### POS-PL-03 — the first stale order is repaired and one commit is made
- **Rules:** `_prepare_listed_orders` PL2 (part that holds today), PL3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1, O2 = po "1", po "2", each but `supplier_confirmed True`.

**When**
- spies: `svc._prepare_listed_orders(db, workspace_id=W1.id, orders=[O1, O2])`.

**Then**
1. mock called: `cm.call_count == 1`.
2. committed: O1 has `current_status_id == SP1.id`.

### POS-PL-04 — nothing stale → no commit
- **Rules:** `_prepare_listed_orders` PL3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1".

**When**
- spies: `svc._prepare_listed_orders(db, workspace_id=W1.id, orders=[O1])`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.

### POS-PL-05 — an empty list writes nothing
- **Rules:** `_prepare_listed_orders` PL3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X (after the commit point).

**When**
- spies: `result = svc._prepare_listed_orders(db, workspace_id=W1.id, orders=[])`.

**Then**
1. returns: `result == []`.
2. mock called: `cm.call_count == 0`.
3. session: `X in db`.

## `PurchaseOrderService.list_purchase_orders_page`

### POS-PG-01 — `has_more` true while more rows follow; skip and limit echoed
- **Rules:** `list_purchase_orders_page` PG1, PG2
- **Kind:** happy
- **Expect:** pass

**Given**
1. po "1"; po "2"; po "3".

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `result.total == 3`, `len(result.items) == 2`.
2. returns: `result.skip == 0`, `result.limit == 2`, `result.has_more is True`.

### POS-PG-02 — the last page: `has_more` false
- **Rules:** `list_purchase_orders_page` PG2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. po "1"; po "2"; po "3".

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result.items) == 1`, `result.total == 3`, `result.has_more is False`.

### POS-PG-03 — skip past the end: empty, `has_more` false
- **Rules:** `list_purchase_orders_page` PG2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. po "1"; po "2"; po "3".

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=5, limit=2)`.

**Then**
1. returns: `result.items == []`, `result.total == 3`, `result.has_more is False`.

### POS-PG-04 — no orders: total 0
- **Rules:** `list_purchase_orders_page` PG2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=50)`.

**Then**
1. returns: `result.total == 0`, `result.items == []`, `result.has_more is False`.

### POS-PG-05 — W0 and W2 orders are neither listed nor counted
- **Rules:** `list_purchase_orders_page` PG1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. po "0", but of W0.
2. O1 = po "1".
3. po "9", but of W2.

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `[o.id for o in result.items] == [O1.id]`, `result.total == 1`.

### POS-PG-06 — `invoice_filter "all"` lists the same as no filter
- **Rules:** `list_purchase_orders_page` PG1; HF1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1". O2 = po "2", but ready.
2. V = inv(O2), linked to O2.

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=1000, invoice_filter="all")`.

**Then**
1. returns: `sorted(o.id for o in result.items) == sorted([O1.id, O2.id])`, `result.total == 2`.

### POS-PG-07 — a read with nothing stale: no commit, no rollback
- **Rules:** `list_purchase_orders_page` PG1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. po "1".
2. X (after the commit point).

**When**
- spies: `svc.list_purchase_orders_page(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

### POS-PG-08 — the defaults: skip 0, limit 50
- **Rules:** `list_purchase_orders_page` PG2 (signature defaults `skip=0`, `limit=50`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. po "1" … po "51" (51 orders of W1).

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.skip == 0`, `result.limit == 50`.
2. returns: `result.total == 51`, `len(result.items) == 50`, `result.has_more is True`.

### POS-PG-09 — no filter given: fully closed and voided orders are listed
- **Rules:** `list_purchase_orders_page` PG1; `_hub_filter_kwargs` HF1 (defaults `exclude_complete=False`, `exclude_voided=False`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1".
2. O2 = po "2", but complete, `paid True` (fully closed per the DAO).
3. O3 = po "3", but voided.

**When**
- `result = svc.list_purchase_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `{o.id for o in result.items} == {O1.id, O2.id, O3.id}`.

## `PurchaseOrderService.get_purchase_order_hub_stats`

### POS-HS-01 — the five figures are the DAO's, in order
- **Rules:** `get_purchase_order_hub_stats` HS1
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. O1 = po "1". O2 = po "2", but complete, `total_amount Decimal("700.00")`.

**When**
- `result = svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `(result.total_count, result.total_value, result.open_count, result.open_value, result.not_invoiced_count)` equals the five values returned by the manager's / DAO's `purchase_order_hub_stats` for W1 with the normalised default filters, in that order.

### POS-HS-02 — at most 10 recent orders
- **Rules:** `get_purchase_order_hub_stats` HS2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 11 orders po "1" … po "11".

**When**
- `result = svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.recent_orders) == 10`.

### POS-HS-03 — an empty workspace: zero counts and empty lists
- **Rules:** `get_purchase_order_hub_stats` HS1, HS3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no purchase orders.

**When**
- `result = svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total_count == 0`, `result.recent_orders == []`.
2. returns: `result.pending_planning == []`, `result.missing_invoice == []`, `result.oldest_drafts == []`.

### POS-HS-04 — W0 and W2 orders are not counted
- **Rules:** `get_purchase_order_hub_stats` HS1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. po "0", but of W0.
2. po "1".
3. po "9", but of W2.

**When**
- `result = svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total_count == 1`, `len(result.recent_orders) == 1`.

### POS-HS-05 — a read: no commit, no rollback
- **Rules:** `get_purchase_order_hub_stats` HS3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. po "1".
2. X (after the commit point).

**When**
- spies: `svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

### POS-HS-06 — no filter given: fully closed and voided orders are counted
- **Rules:** `get_purchase_order_hub_stats` HS1 (defaults `exclude_complete=False`, `exclude_voided=False`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1".
2. O2 = po "2", but complete, `paid True` (fully closed per the DAO).
3. O3 = po "3", but voided.

**When**
- `result = svc.get_purchase_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total_count == 3`.

## `PurchaseOrderService._attach_invoice_payment_status`

### POS-AP-01 — each order gets its invoice's payment status; none → None; one query
- **Rules:** `_attach_invoice_payment_status` AP1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po "1", O2 = po "2", O3 = po "3".
2. V1 = inv(O1), but finalized, `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O1.
3. V2 = inv(O2), but finalized, `paid_amount Decimal("5000.00")`, `payment_status "paid"`, linked to O2.
4. Statement recorder on (after the commit point).

**When**
- `svc._attach_invoice_payment_status(db, orders=[O1, O2, O3])`.

**Then**
1. returns: `[O1.invoice_payment_status, O2.invoice_payment_status, O3.invoice_payment_status] == ["partial", "paid", None]`.
2. statement: exactly 1 recorded SELECT names `account_invoices` in its `FROM`.

### POS-AP-02 — a voided invoice's status is shown
- **Rules:** `_attach_invoice_payment_status` AP1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1".
2. V1 = inv(O1), but voided-inv, `payment_status "unpaid"`, linked to O1.

**When**
- `svc._attach_invoice_payment_status(db, orders=[O1])`.

**Then**
1. returns: `O1.invoice_payment_status == "unpaid"`.

### POS-AP-03 — no order has an invoice → all None
- **Rules:** `_attach_invoice_payment_status` AP1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1", O2 = po "2".

**When**
- `svc._attach_invoice_payment_status(db, orders=[O1, O2])`.

**Then**
1. returns: `O1.invoice_payment_status is None`, `O2.invoice_payment_status is None`.

### POS-AP-04 — a W2 invoice linked to a W1 order is not read
- **Rules:** `_attach_invoice_payment_status` AP2 [BUG-3164]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3164
- **Fails today on:** Then 2 (read by id only: shows `"paid"`)

**Given**
1. O1 = po "1". O2 = po "2".
2. V1 = inv(O1), but finalized, `payment_status "partial"`, `paid_amount Decimal("100.00")`, linked to O1.
3. V9 = inv(O2), but of W2, finalized, `paid_amount Decimal("5000.00")`, `payment_status "paid"`, linked to O2.

**When**
- `svc._attach_invoice_payment_status(db, orders=[O1, O2])`.

**Then**
1. returns: `O1.invoice_payment_status == "partial"`.
2. returns: `O2.invoice_payment_status is None`.

### POS-AP-05 — a W0 invoice linked to a W1 order is not read
- **Rules:** `_attach_invoice_payment_status` AP2 [BUG-3164]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3164
- **Fails today on:** Then 1 (read by id only: shows `"paid"`)

**Given**
1. O0 = po "0", but of W0 (placeholder so W0 has rows).
2. O1 = po "1".
3. V0 = inv(O1), but of W0, finalized, `paid_amount Decimal("5000.00")`, `payment_status "paid"`, linked to O1.

**When**
- `svc._attach_invoice_payment_status(db, orders=[O1])`.

**Then**
1. returns: `O1.invoice_payment_status is None`.

## `PurchaseOrderService._attach_item_summaries`

### POS-IS-01 — counts, totals and name preview per order
- **Rules:** `_attach_item_summaries` IS1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po "1". O2 = po "2".
2. poline(O1, 1), but `quantity_received Decimal("4.00")`.
3. poline(O1, 2), but `item_id I1b.id`, `quantity_ordered Decimal("5.00")`, `line_subtotal Decimal("2500.00")`.

**When**
- `svc._attach_item_summaries(db, workspace_id=W1.id, orders=[O1, O2])`.

**Then**
1. returns: `O1.item_count == 2`, `O1.quantity_ordered_total == Decimal("15.00")`, `O1.quantity_received_total == Decimal("4.00")`.
2. returns: `sorted(O1.item_names_preview) == ["Bearing", "Cement"]`.
3. returns: `O2.item_count == 0`, `O2.quantity_ordered_total == Decimal(0)`, `O2.quantity_received_total == Decimal(0)`, `O2.item_names_preview == []`.

### POS-IS-02 — a W2 line pointing at a W1 order is not counted
- **Rules:** `_attach_item_summaries` IS1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po "1".
2. poline(O1, 1).
3. poline(O1, 2), but `workspace_id W2.id`, `item_id I9.id` (invalid data).

**When**
- `svc._attach_item_summaries(db, workspace_id=W1.id, orders=[O1])`.

**Then**
1. returns: `O1.item_count == 1`, `O1.quantity_ordered_total == Decimal("10.00")`.

### POS-IS-03 — the refunded total is attached
- **Rules:** `_attach_item_summaries` IS2 [BUG-2641]
- **Kind:** bug
- **Expect:** xfail BUG-2641
- **Fails today on:** Then 2 (no `quantity_refunded_total`)

**Given**
1. O1 = po "1".
2. poline(O1, 1), but `quantity_received Decimal("7.00")`, `quantity_returned Decimal("3.00")`, `quantity_refunded Decimal("3.00")`.

**When**
- `svc._attach_item_summaries(db, workspace_id=W1.id, orders=[O1])`.

**Then**
1. returns: `O1.quantity_received_total == Decimal("7.00")`.
2. returns: `O1.quantity_refunded_total == Decimal("3.00")`.

## `PurchaseOrderService.create_receive_event`

Every card in this section starts from **RCVBASE** unless it says otherwise: O = po "1", but ready, `current_status_id SR1.id`; L = poline(O, 1); V = inv(O), but finalized, linked to O. **RE(req)** = `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id, data=req)`.

### POS-RE-01 — a receive batch is recorded, stock posted, committed
- **Rules:** `create_receive_event` RE6, RE8, RE12; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5")))`.

**Then**
1. returns: `result.event_type == "receive"`, `len(result.items) == 1`, `result.items[0].quantity_delta == Decimal("5")`.
2. committed: `po_receive_events` of O: exactly 1, with `performed_by == U2.id`, `workspace_id == W1.id`, `id == result.id`.
3. committed: `po_receive_event_items` of that event: exactly 1, `quantity_delta == Decimal("5.00")`.
4. committed: L has `quantity_received == Decimal("5.00")`.
5. committed: `len(RCVLEDGER(O)) == 1`, `RCVLEDGER(O)[0].transaction_type == "purchase_order"`.
6. committed: `"received" in types(O)`.

### POS-RE-02 — a missing order → 404 before the `try`: no rollback, X still in the session
- **Rules:** `create_receive_event` RE1; Transaction contract (refusals before the `try`)
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE.
2. X (after the commit point).

**When**
- spies: `svc.create_receive_event(db, po_id=MISSING, workspace_id=W1.id, user_id=U2.id, data=RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. nothing written: nothing written.

### POS-RE-03 — a W0 order id → 404
- **Rules:** `create_receive_event` RE1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0, ready.
2. RCVBASE.

**When**
- `svc.create_receive_event(db, po_id=O0.id, workspace_id=W1.id, user_id=U2.id, data=RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. unchanged: unchanged(L).

### POS-RE-04 — a W2 order id → 404
- **Rules:** `create_receive_event` RE1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RCVBASE.
2. O9 = po "9", but of W2, ready.
3. L9 = poline(O9, 1).

**When**
- `svc.create_receive_event(db, po_id=O9.id, workspace_id=W1.id, user_id=U2.id, data=RCV((L9, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. unchanged: unchanged(L9).

### POS-RE-05 — the order row is locked before the first state check
- **Rules:** `create_receive_event` RE1 [BUG-3162]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3162
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE OF purchase_orders`)

**Given**
1. RCVBASE. `oid, lid = O.id, L.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.create_receive_event(db, po_id=oid, workspace_id=W1.id, user_id=U2.id, data=PoReceiveEventCreate(event_type="receive", items=[{"po_item_id": lid, "quantity_delta": Decimal("5")}]))`.

**Then**
1. returns: `result.event_type == "receive"`.
2. statement: exact lock OF(`purchase_orders`).
3. statement: `purchase_orders` before `account_invoices`.
4. statement: `purchase_orders` before `purchase_order_items`.

### POS-RE-06 — a voided order → 400
- **Rules:** `create_receive_event` RE2
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE, but O voided.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot receive against a voided purchase order"`.
4. nothing written: nothing written.

### POS-RE-07 — a completed order → 400
- **Rules:** `create_receive_event` RE2
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE, but O complete.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot receive against a completed purchase order"`.
4. nothing written: nothing written.

### POS-RE-08 — no invoice linked → 400 finalize first
- **Rules:** `create_receive_event` RE3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. L = poline(O, 1).

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == FINALIZE`.
4. nothing written: nothing written.

### POS-RE-09 — a draft invoice → 400 finalize first
- **Rules:** `create_receive_event` RE3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. L = poline(O, 1).
3. V = inv(O), linked to O.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == FINALIZE`.
3. unchanged: unchanged(L).

### POS-RE-10 — a finalized invoice of W2 linked → 400 finalize first
- **Rules:** `create_receive_event` RE3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. L = poline(O, 1).
3. V9 = inv(O), but of W2, finalized, linked to O.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == FINALIZE`.
3. unchanged: unchanged(V9).

### POS-RE-11 — a `locked` invoice passes the check
- **Rules:** `create_receive_event` RE3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`.
2. L = poline(O, 1).
3. V = inv(O), but locked-inv, linked to O.

**When**
- `result = RE(RCV((L, "5")))`.

**Then**
1. returns: `result.event_type == "receive"`.
2. committed: L has `quantity_received == Decimal("5.00")`.

### POS-RE-12 — a line of another order → 400
- **Rules:** `create_receive_event` RE4
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE.
2. O2 = po "2". L2 = poline(O2, 1).

**When**
- `RE(RCV((L2, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item {L2.id} does not belong to this PO"`.
4. nothing written: nothing written.

### POS-RE-13 — a W2 line → 400
- **Rules:** `create_receive_event` RE4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RCVBASE.
2. O9 = po "9", but of W2. L9 = poline(O9, 1).

**When**
- `RE(RCV((L9, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == f"Item {L9.id} does not belong to this PO"`.
3. unchanged: unchanged(L9).

### POS-RE-14 — a correction going below 0 → 400
- **Rules:** `create_receive_event` RE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("3.00")`.

**When**
- `RE(COR((L, "-4"), note="Miscount"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Resulting received quantity for item {L.id} cannot be negative"`.
4. unchanged: unchanged(L).

### POS-RE-15 — exactly 0 after a correction passes
- **Rules:** `create_receive_event` RE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("3.00")`.

**When**
- `RE(COR((L, "-3"), note="Miscount"))`.

**Then**
1. committed: L has `quantity_received == Decimal("0.00")`.

### POS-RE-16 — above ordered − refunded → 400
- **Rules:** `create_receive_event` RE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("7.00")`, `quantity_refunded Decimal("2.00")`, `quantity_returned Decimal("2.00")`.

**When**
- `RE(RCV((L, "2")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Resulting received quantity for item {L.id} exceeds ordered quantity"`.
4. unchanged: unchanged(L).

### POS-RE-17 — exactly ordered − refunded passes
- **Rules:** `create_receive_event` RE5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("7.00")`, `quantity_refunded Decimal("2.00")`, `quantity_returned Decimal("2.00")`.

**When**
- `RE(RCV((L, "1")))`.

**Then**
1. committed: L has `quantity_received == Decimal("8.00")`.

### POS-RE-18 — the same line twice is checked on the running total
- **Rules:** `create_receive_event` RE5 [BUG-3171]
- **Kind:** bug
- **Expect:** xfail BUG-3171
- **Fails today on:** Then 1 (each repeat is checked alone: no error, received ends at 12)

**Given**
1. RCVBASE.

**When**
- `RE(RCV((L, "6"), (L, "6")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Resulting received quantity for item {L.id} exceeds ordered quantity"`.
4. committed: L has `quantity_received == Decimal("0.00")`.
5. committed: `po_receive_events` of O: 0.

### POS-RE-19 — the same line twice within the limit is accepted and summed
- **Rules:** `create_receive_event` RE5, RE6 (part that holds before and after BUG-3171)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "3"), (L, "3")))`.

**Then**
1. returns: `len(result.items) == 2`.
2. committed: L has `quantity_received == Decimal("6.00")`.

### POS-RE-20 — a posting failure after the writes rolls everything back
- **Rules:** `create_receive_event` RE8, RE12; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE.
2. X (after the commit point).

**When**
- spies: `RE(RCV((L, "2.5")))` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Line 1 has a fractional quantity delta; inventory requires whole units"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. committed: L has `quantity_received == Decimal("0.00")`.
8. nothing written: nothing written.

### POS-RE-21 — texts are stored trimmed
- **Rules:** `create_receive_event` RE7 (part that holds before and after BUG-3180)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5"), rcc=" RCC-77 ", received_by=" Karim "))`.

**Then**
1. committed: the event `result.id` has `rcc == "RCC-77"`, `received_by == "Karim"`.

### POS-RE-22 — a blank text is stored as NULL
- **Rules:** `create_receive_event` RE7 [BUG-3180]
- **Kind:** bug
- **Expect:** xfail BUG-3180
- **Fails today on:** Then 2 (stored as `""`)

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5"), rcc="   ", received_by="Karim"))`.

**Then**
1. committed: the event `result.id` has `received_by == "Karim"`.
2. committed: the event `result.id` has `rcc is None`.

### POS-RE-23 — a project order moves no stock and logs no posting
- **Rules:** `create_receive_event` RE8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: `RCVLEDGER(O) == []`.
2. committed: `"inventory_posted" not in types(O)`.
3. committed: L has `quantity_received == Decimal("5.00")`.

### POS-RE-24 — a storage posting logs `inventory_posted` with its metadata
- **Rules:** `create_receive_event` RE8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5")))`.

**Then**
1. committed: the `inventory_posted` event of O has `description == "1 receive line(s) posted to factory storage"`.
2. committed: its `metadata_json == {"receive_event_id": result.id, "lines_posted": 1, "destination_type": "storage", "destination_id": F1.id}`.

### POS-RE-25 — a machine posting says "machine inventory"
- **Rules:** `create_receive_event` RE8
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. M1 = a live machine of W1 at F1 (as built in `po_machine_inventory` tests).
2. RCVBASE, but O `destination_type "machine"`, `destination_id M1.id`.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: the `inventory_posted` event of O has `description == "1 receive line(s) posted to machine inventory"`.

### POS-RE-26 — receive log text and metadata with RCC and "received by"
- **Rules:** `create_receive_event` RE9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5"), rcc="RCC-77", received_by="Karim"))`.

**Then**
1. committed: the `received` event of O has `description == "Received 5 unit(s) across 1 item(s). RCC: RCC-77. Received by: Karim."`, `performed_by == U2.id`.
2. committed: its `metadata_json == {"receive_event_id": result.id, "rcc": "RCC-77", "received_by": "Karim"}`.

### POS-RE-27 — receive log without the optional texts
- **Rules:** `create_receive_event` RE9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj.
2. L2 = poline(O, 2), but `item_id I1b.id`.

**When**
- `result = RE(RCV((L, "5"), (L2, "2.50")))`.

**Then**
1. committed: the `received` event of O has `description == "Received 7.50 unit(s) across 2 item(s)."`.
2. committed: its `metadata_json == {"receive_event_id": result.id}`.

### POS-RE-28 — correction log is signed and carries the note
- **Rules:** `create_receive_event` RE9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("5.00")`.

**When**
- `result = RE(COR((L, "-2"), note="Miscount"))`.

**Then**
1. committed: the `quantity_correction` event of O has `description == "Quantity correction: -2 unit(s) across 1 item(s). Note: Miscount"`.
2. committed: its `metadata_json == {"receive_event_id": result.id, "correction_note": "Miscount"}`.
3. committed: L has `quantity_received == Decimal("3.00")`.

### POS-RE-29 — a zero correction prints `+0`
- **Rules:** `create_receive_event` RE9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("5.00")`.

**When**
- `RE(COR((L, "0"), note="Recount"))`.

**Then**
1. committed: the `quantity_correction` event of O has `description == "Quantity correction: +0 unit(s) across 1 item(s). Note: Recount"`.

### POS-RE-30 — the log uses the trimmed texts
- **Rules:** `create_receive_event` RE9 [BUG-3180]
- **Kind:** bug
- **Expect:** xfail BUG-3180
- **Fails today on:** Then 2 (the text as sent: ` RCC:  RCC-77 .`)

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5"), rcc=" RCC-77 "))`.

**Then**
1. returns: `result.event_type == "receive"`.
2. committed: the `received` event of O has `description == "Received 5 unit(s) across 1 item(s). RCC: RCC-77."`.
3. committed: its `metadata_json == {"receive_event_id": result.id, "rcc": "RCC-77"}`.

### POS-RE-31 — a blank text is left out of the log
- **Rules:** `create_receive_event` RE9 [BUG-3180]
- **Kind:** bug
- **Expect:** xfail BUG-3180
- **Fails today on:** Then 2 (` RCC:    .` is appended)

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5"), rcc="   "))`.

**Then**
1. returns: `result.event_type == "receive"`.
2. committed: the `received` event of O has `description == "Received 5 unit(s) across 1 item(s)."`.
3. committed: `"rcc" not in` its `metadata_json`.

### POS-RE-32 — the first receipt marks the invoice "receiving started"
- **Rules:** `create_receive_event` RE10 [BUG-3177]
- **Kind:** bug
- **Expect:** xfail BUG-3177
- **Fails today on:** Then 2 (never set by this path)

**Given**
1. RCVBASE.

**When**
- `result = RE(RCV((L, "5")))`.

**Then**
1. returns: `result.event_type == "receive"`.
2. committed: V has `receiving_started is True`.
3. committed: `itypes(V).count("receiving_started_set") == 1`.

### POS-RE-33 — already "receiving started": nothing more on the invoice
- **Rules:** `create_receive_event` RE10 (side that holds today and after BUG-3177)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but V `receiving_started True`.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: V has `receiving_started is True`.
2. committed: `"receiving_started_set" not in itypes(V)`.

### POS-RE-34 — the batch that completes every line logs `all_received`
- **Rules:** `create_receive_event` RE11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RCVBASE, but L `quantity_received Decimal("5.00")`.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: `[e.description for e in EV(O) if e.event_type == "all_received"] == ["All items received"]`.

### POS-RE-35 — `all_received` is logged once per order
- **Rules:** `create_receive_event` RE11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O proj, L `quantity_received Decimal("7.00")`.
2. ev(O, T0, "all_received").

**When**
- `RE(RCV((L, "3")))`.

**Then**
1. committed: `types(O).count("all_received") == 1`.

### POS-RE-36 — not every line done → no `all_received`
- **Rules:** `create_receive_event` RE11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE.
2. poline(O, 2), but `item_id I1b.id`.

**When**
- `RE(RCV((L, "10")))`.

**Then**
1. committed: `"all_received" not in types(O)`.

### POS-RE-37 — the stage is not repaired by a receipt
- **Rules:** `create_receive_event` RE12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but O `current_status_id SP1.id`.

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: O has `current_status_id == SP1.id`.

### POS-RE-38 — a failing commit saves nothing
- **Rules:** `create_receive_event` RE12; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `RE(RCV((L, "5")))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `quantity_received == Decimal("0.00")`.
4. nothing written: nothing written.

### POS-RE-39 — schema: an empty items list is refused
- **Rules:** `create_receive_event` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `PoReceiveEventCreate(event_type="receive", items=[])` (target `schema`).

**Then**
1. raises: `ValidationError`; message contains `"At least one item must have a quantity delta"`.

### POS-RE-40 — schema: a correction with a blank note is refused
- **Rules:** `create_receive_event` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `PoReceiveEventCreate(event_type="correction", correction_note="   ", items=[{"po_item_id": 1, "quantity_delta": Decimal("-1")}])` (target `schema`).

**Then**
1. raises: `ValidationError`; message contains `"correction_note is required for correction events"`.

### POS-RE-41 — schema: a receive with a zero delta is refused
- **Rules:** `create_receive_event` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `PoReceiveEventCreate(event_type="receive", items=[{"po_item_id": 1, "quantity_delta": Decimal("0")}])` (target `schema`).

**Then**
1. raises: `ValidationError`; message contains `"All quantity deltas must be positive for a receive event"`.

### POS-RE-42 — schema: an unknown event type is refused
- **Rules:** `create_receive_event` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `PoReceiveEventCreate(event_type="return", items=[{"po_item_id": 1, "quantity_delta": Decimal("1")}])` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-RE-43 — refunded quantity completes a line for `all_received`
- **Rules:** `create_receive_event` RE11 (received + refunded ≥ ordered)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but L `quantity_refunded Decimal("4.00")`.

**When**
- `RE(RCV((L, "6")))`.

**Then**
1. committed: L has `quantity_received == Decimal("6.00")`.
2. committed: `[e.description for e in EV(O) if e.event_type == "all_received"] == ["All items received"]`.

### POS-RE-44 — a line one unit short → no `all_received`
- **Rules:** `create_receive_event` RE11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE.

**When**
- `RE(RCV((L, "9")))`.

**Then**
1. committed: L has `quantity_received == Decimal("9.00")`, `quantity_refunded == Decimal("0.00")`.
2. committed: `"all_received" not in types(O)`.

### POS-RE-45 — another line still at 0 of 1 ordered → no `all_received`
- **Rules:** `create_receive_event` RE11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RCVBASE, but L `quantity_received Decimal("5.00")`.
2. L2 = poline(O, 2), but `item_id I1b.id`, `quantity_ordered Decimal("1.00")`, `line_subtotal Decimal("500.00")` (received, returned, refunded 0.00).

**When**
- `RE(RCV((L, "5")))`.

**Then**
1. committed: L has `quantity_received == Decimal("10.00")`; L2 has `quantity_received == Decimal("0.00")`.
2. committed: `"all_received" not in types(O)`.

## `PurchaseOrderService.list_receive_events`

**rev(O, t)** = `PoReceiveEvent(workspace_id=O.workspace_id, purchase_order_id=O.id, event_type="receive", performed_by=U1.id, created_at=t)`. **revi(E, L, d)** = `PoReceiveEventItem(receive_event_id=E.id, po_item_id=L.id, quantity_delta=Decimal(d))` (FK `receive_event_id` per the spec Overview; the table has no `workspace_id`). Both are also used by the `_build_receive_event_response` cards.

### POS-LR-01 — a missing order → 404; no rollback, X still in the session
- **Rules:** `list_receive_events` LR1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. X (after the commit point).

**When**
- spies: `svc.list_receive_events(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### POS-LR-02 — newest first; no commit, no rollback
- **Rules:** `list_receive_events` LR2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. E1 = rev(O, T0). E2 = rev(O, T2). E3 = rev(O, T1).
3. X (after the commit point).

**When**
- spies: `result = svc.list_receive_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for e in result] == [E2.id, E3.id, E1.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### POS-LR-03 — equal times: the higher id first
- **Rules:** `list_receive_events` LR2 [BUG-3172]
- **Kind:** bug
- **Expect:** xfail BUG-3172 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; database order)

**Given**
1. O = po "1".
2. E1 = rev(O, T1). E2 = rev(O, T1).

**When**
- `result = svc.list_receive_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for e in result] == [E2.id, E1.id]`.

### POS-LR-04 — the events query breaks ties by id descending
- **Rules:** `list_receive_events` LR2 [BUG-3172]
- **Kind:** bug
- **Expect:** xfail BUG-3172
- **Fails today on:** Then 2 (the ORDER BY has no id key)

**Given**
1. O = po "1". `oid = O.id`.
2. rev(O, T1).
3. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.list_receive_events(db, po_id=oid, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: the SELECT whose `FROM` names `po_receive_events` has an `ORDER BY` whose text after `created_at DESC` contains `id DESC`.

### POS-LR-05 — W0 and W2 events carrying the same order id are not listed
- **Rules:** `list_receive_events` LR2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. rev(O, T0), but `workspace_id W0.id` (invalid data).
3. E1 = rev(O, T1).
4. rev(O, T2), but `workspace_id W2.id` (invalid data).

**When**
- `result = svc.list_receive_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for e in result] == [E1.id]`.

### POS-LR-06 — no events → empty list
- **Rules:** `list_receive_events` LR2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = svc.list_receive_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `PurchaseOrderService._build_receive_event_response`

### POS-BR-01 — columns, performer name and lines with the PO line's name and unit
- **Rules:** `_build_receive_event_response` BR1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).
2. E = rev(O, T1), but `performed_by U2.id`, `rcc "RCC-1"`.
3. revi(E, L, "3").

**When**
- `result = svc._build_receive_event_response(E)`.

**Then**
1. returns: `result.id == E.id`, `result.rcc == "RCC-1"`, `result.performer_name == "Karim Ali"`.
2. returns: `len(result.items) == 1`, `result.items[0].po_item_name == "Bearing"`, `result.items[0].po_item_unit == "pcs"`, `result.items[0].quantity_delta == Decimal("3.00")`.

### POS-BR-02 — no performer → `performer_name None`
- **Rules:** `_build_receive_event_response` BR1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. E = rev(O, T1), but `performed_by None`.

**When**
- `result = svc._build_receive_event_response(E)`.

**Then**
1. returns: `result.performer_name is None`, `result.items == []`.

### POS-BR-03 — a line whose PO line is gone shows `None` name and unit
- **Rules:** `_build_receive_event_response` BR1
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. E = rev(O, T1); one event line of E whose PO line relationship resolves to `None` (set the line's `po_item` to None in memory, or point it at a removed line if the foreign key allows).

**When**
- `result = svc._build_receive_event_response(E)`.

**Then**
1. returns: `result.items[0].po_item_name is None`, `result.items[0].po_item_unit is None`.

### POS-BR-04 — the event's lines are read in id order
- **Rules:** `_build_receive_event_response` BR1 [BUG-3172]
- **Kind:** bug
- **Expect:** xfail BUG-3172
- **Fails today on:** Then 2 (the lines relationship has no ORDER BY)

**Given**
1. O = po "1". L = poline(O, 1). `oid = O.id`.
2. E = rev(O, T1); revi(E, L, "1"), revi(E, L, "2"), revi(E, L, "3").
3. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.list_receive_events(db, po_id=oid, workspace_id=W1.id)`.

**Then**
1. returns: `len(result[0].items) == 3`.
2. statement: the SELECT whose `FROM` names `po_receive_event_items` has an `ORDER BY` containing `id` (ascending).

### POS-BR-05 — the lines come back in id order
- **Rules:** `_build_receive_event_response` BR1 [BUG-3172]
- **Kind:** bug
- **Expect:** xfail BUG-3172 (non-strict)
- **Fails today on:** Then 1 (relationship order)

**Given**
1. O = po "1". L = poline(O, 1).
2. E = rev(O, T1); a = revi(E, L, "1"), b = revi(E, L, "2"), c = revi(E, L, "3") (ids ascending).
3. `db.execute(text("UPDATE po_receive_event_items SET quantity_delta = quantity_delta WHERE id = :i"), {"i": a.id})` (moves row a in the heap), then `db.expire_all()`.

**When**
- `result = svc._build_receive_event_response(E)`.

**Then**
1. returns: `[i.quantity_delta for i in result.items] == [Decimal("1.00"), Decimal("2.00"), Decimal("3.00")]`.

## `PurchaseOrderService._attach_return_invoice_for_po`

**AR(O, R)** = `svc._attach_return_invoice_for_po(db, po=O, ret=R, workspace_id=W1.id, user_id=U2.id)`.

### POS-AR-01 — one finalized receivable credit note, linked to the return only
- **Rules:** `_attach_return_invoice_for_po` AR1, AR4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. R = ret "1" of O.
4. rline(R, L, "4").

**When**
- `AR(O, R)`.

**Then**
1. re-read R: `invoice_id is not None`; call it CNID.
2. re-read invoice CNID: `account_id == A1.id`, `order_id == O.id`, `order_type == "purchase_order"`, `invoice_type == "receivable"`, `allow_payments is True`.
3. re-read invoice CNID: `description == f"Return credit note for {O.po_number} ({R.return_number})"`, `notes == "Faulty"`.
4. re-read invoice CNID: `invoice_status == "confirmed"`, `invoice_amount == Decimal("2000.00")`.
5. event: `itypes(CNID).count("confirmed") == 1`.
6. re-read O: `invoice_id is None`.

### POS-AR-02 — one credit-note line per return line, numbered in id order
- **Rules:** `_attach_return_invoice_for_po` AR2, AR3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
3. L2 = poline(O, 2), but `item_id I1b.id`, `quantity_received Decimal("10.00")`.
4. R = ret "1" of O.
5. rline(R, L, "4").
6. rline(R, L2, "2"), but `unit_price Decimal("300.00")`.

**When**
- `AR(O, R)`.

**Then**
1. re-read: `[(x.line_number, x.source_order_item_id) for x in LINES(R.invoice_id)] == [(1, L.id), (2, L2.id)]`.
2. re-read: `LINES(R.invoice_id)[0]` has `source_order_item_type == "po_item"`, `item_id == I1.id`, `quantity == Decimal("4.00")`, `unit_price == Decimal("500.00")`, `line_subtotal == Decimal("2000.00")`.
3. re-read: `LINES(R.invoice_id)[1]` has `item_id == I1b.id`, `quantity == Decimal("2.00")`, `unit_price == Decimal("300.00")`, `line_subtotal == Decimal("600.00")`.
4. re-read invoice `R.invoice_id`: `invoice_amount == Decimal("2600.00")`.

### POS-AR-03 — a return line without an item name is described `Item <item_id>`
- **Rules:** `_attach_return_invoice_for_po` AR2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
2. R = ret "1" of O. RL = rline(R, L, "4"), with its item name empty (`item_name ""` or `None`, whichever the model stores).

**When**
- `AR(O, R)`.

**Then**
1. re-read: `LINES(R.invoice_id)[0].description == f"Item {I1.id}"`.

### POS-AR-04 — the credit note is dated with the UTC clock
- **Rules:** `_attach_return_invoice_for_po` AR1 [BUG-3167]
- **Kind:** bug
- **Expect:** xfail BUG-3167
- **Fails today on:** Then 2 (`date.today()`, the real date)

**Given**
1. O = po "1", but ready. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
2. R = ret "1" of O. rline(R, L, "4").

**When**
- `AR(O, R)`.

**Then**
1. re-read R: `invoice_id is not None`.
2. re-read invoice `R.invoice_id`: `invoice_date == TODAY_UTC`.

### POS-AR-05 — stored line subtotals are rounded half up and the amount is their sum
- **Rules:** `_attach_return_invoice_for_po` AR3; HR-15 (regression rule; BUG-3163 withdrawn, Gap log G13)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready, proj.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`, `unit_price Decimal("1.25")`, `line_subtotal Decimal("12.50")`.
3. L2 = poline(O, 2), but `item_id I1b.id`, `quantity_received Decimal("10.00")`, `unit_price Decimal("1.25")`, `line_subtotal Decimal("12.50")`.
4. R = ret "1" of O. rline(R, L, "0.10"), but `unit_price Decimal("1.25")`. rline(R, L2, "0.10"), but `unit_price Decimal("1.25")`.

**When**
- `AR(O, R)`.

**Then**
1. re-read R: `invoice_id is not None`.
2. lines: `[l.line_subtotal for l in LINES(<invoice R.invoice_id>)] == [Decimal("0.13"), Decimal("0.13")]` (stored values, after `expire_all`).
3. re-read invoice `R.invoice_id`: `invoice_amount == Decimal("0.26")`.

### POS-AR-06 — 2-place lines: subtotals and amount exact
- **Rules:** `_attach_return_invoice_for_po` AR3 (part that holds today and after BUG-3163)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
2. R = ret "1" of O. rline(R, L, "3"), but `unit_price Decimal("333.33")`.

**When**
- `AR(O, R)`.

**Then**
1. re-read: `LINES(R.invoice_id)[0].line_subtotal == Decimal("999.99")`.
2. re-read invoice `R.invoice_id`: `invoice_amount == Decimal("999.99")`.

### POS-AR-07 — the helper flushes only
- **Rules:** `_attach_return_invoice_for_po` AR4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
2. R = ret "1" of O. rline(R, L, "4").

**When**
- spies: `AR(O, R)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `R.invoice_id is not None`.

### POS-AR-08 — a return line priced 0.00 gives a 0.00 credit-note line
- **Rules:** `_attach_return_invoice_for_po` AR2 (price `0`), AR3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. L = poline(O, 1), but `quantity_received Decimal("10.00")`; L2 = poline(O, 2), but `item_id I1b.id`, `quantity_received Decimal("10.00")`.
3. R = ret "1" of O.
4. rline(R, L, "4"); rline(R, L2, "2"), but `unit_price Decimal("0.00")`.

**When**
- `AR(O, R)`.

**Then**
1. re-read R: `invoice_id is not None`; call it CNID.
2. LINES(CNID): `[(x.line_number, x.unit_price, x.line_subtotal) for x in LINES(CNID)] == [(1, Decimal("500.00"), Decimal("2000.00")), (2, Decimal("0.00"), Decimal("0.00"))]`.
3. re-read invoice CNID: `invoice_amount == Decimal("2000.00")`, `invoice_status == "confirmed"`.

## `PurchaseOrderService.start_return`

**SRBASE** = O = po "1", but ready, `current_status_id SR1.id`, `invoice_confirmed True`; V = inv(O), but finalized, linked to O; L = poline(O, 1), but `quantity_received Decimal("10.00")`. **SR(req)** = `svc.start_return(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id, data=req)`.

### POS-SR-01 — a return starts pending with a finalized credit note; committed; no stock moves
- **Rules:** `start_return` SR3, SR6, SR7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. SRBASE.

**When**
- `result = SR(SRQ((L, "4"), t="refund"))`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.status == "pending"`, `result.invoice_id is not None`.
3. committed: the return `result.id` has `return_type == "refund"`, `reason == "Faulty"`, `purchase_order_id == O.id`, `workspace_id == W1.id`.
4. committed: its return lines: exactly 1, `po_item_id == L.id`, `quantity_returned == Decimal("4.00")`.
5. committed: invoice `result.invoice_id` has `invoice_type == "receivable"`, `invoice_status == "confirmed"`, `invoice_amount == Decimal("2000.00")`.
6. committed: L has `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`.
7. committed: `inventory_ledger` rows of W1: 0.
8. committed: `notes() == []`.

### POS-SR-02 — the `return_started` event
- **Rules:** `start_return` SR6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SRBASE.

**When**
- `result = SR(SRQ((L, "4"), t="replace"))`.

**Then**
1. committed: the `return_started` event of O has `description == f"Return {result.return_number} started — replace (4 unit(s) across 1 item(s))"` (total as sent).
2. committed: its `metadata_json == {"return_id": result.id, "invoice_id": result.invoice_id, "return_type": "replace"}`.

### POS-SR-03 — a W0 order → 404
- **Rules:** `start_return` SR1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0, ready. L0 = poline(O0, 1), but `quantity_received Decimal("10.00")`.
2. SRBASE.

**When**
- `svc.start_return(db, po_id=O0.id, workspace_id=W1.id, user_id=U2.id, data=SRQ((L0, "4"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. nothing written: nothing written.

### POS-SR-04 — a W2 order → 404
- **Rules:** `start_return` SR1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SRBASE.
2. O9 = po "9", but of W2, ready. L9 = poline(O9, 1), but `quantity_received Decimal("10.00")`.

**When**
- `svc.start_return(db, po_id=O9.id, workspace_id=W1.id, user_id=U2.id, data=SRQ((L9, "4"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. nothing written: nothing written.

### POS-SR-05 — a voided order → 400
- **Rules:** `start_return` SR1
- **Kind:** error
- **Expect:** pass

**Given**
1. SRBASE, but O voided.

**When**
- `SR(SRQ((L, "4"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot return items on a voided purchase order"`.
4. nothing written: nothing written.

### POS-SR-06 — nothing received → 400, rolled back
- **Rules:** `start_return` SR2, SR7; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. SRBASE, but L `quantity_received Decimal("0.00")`.
2. X (after the commit point).

**When**
- spies: `SR(SRQ((L, "4"), t="refund"))` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "No items have been received yet — nothing to return"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. nothing written: nothing written.

### POS-SR-07 — the return manager's quantity check passes through
- **Rules:** `start_return` SR3
- **Kind:** error
- **Expect:** pass

**Given**
1. SRBASE.

**When**
- `SR(SRQ((L, "11"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot return 11 of line 1 — only 10.00 available to return"`.
4. nothing written: nothing written.

### POS-SR-08 — a fractional quantity on a storage order → 400
- **Rules:** `start_return` SR4 [BUG-801]
- **Kind:** bug
- **Expect:** xfail BUG-801
- **Fails today on:** Then 1 (accepted)

**Given**
1. SRBASE.

**When**
- `SR(SRQ((L, "4.5"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Return line for PO line 1 has a fractional quantity; inventory requires whole units"`.
4. committed: `purchase_order_returns` of O: 0.

### POS-SR-09 — a fractional quantity on a project order is accepted
- **Rules:** `start_return` SR4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SRBASE, but O proj.

**When**
- `result = SR(SRQ((L, "4.5"), t="refund"))`.

**Then**
1. returns: `result.status == "pending"`.
2. committed: its return line has `quantity_returned == Decimal("4.50")`.

### POS-SR-10 — a completed order accepts a return
- **Rules:** `start_return` SR1, SR5 (part that holds today and after BUG-2789)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SRBASE, but O complete.

**When**
- `result = SR(SRQ((L, "4"), t="replace"))`.

**Then**
1. returns: `result.status == "pending"`.
2. committed: `purchase_order_returns` of O: 1.

### POS-SR-11 — a completed order stays completed while the return is pending
- **Rules:** `start_return` SR5 [BUG-2789]
- **Kind:** bug
- **Expect:** xfail BUG-2789
- **Fails today on:** Then 2 (reopened to `Receiving`)

**Given**
1. SRBASE, but O complete, `actual_delivery_date date(2026, 9, 10)`.

**When**
- `result = SR(SRQ((L, "4"), t="replace"))`.

**Then**
1. returns: `result.status == "pending"`.
2. committed: O has `current_status_id == SC1.id`, `actual_delivery_date == date(2026, 9, 10)`.
3. committed: `"order_reopened" not in types(O)`.

### POS-SR-12 — the credit note refused → the return is rolled back too
- **Rules:** `start_return` SR7; AR1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = `Account(workspace_id=W1.id, name="No Bills Ltd", is_active=True, is_deleted=False, allow_invoices=False)`.
2. SRBASE, but O `account_id A2.id`.
3. X (after the commit point).

**When**
- `SR(SRQ((L, "4"), t="refund"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. committed: `purchase_order_returns` of O: 0.
7. nothing written: nothing written.

### POS-SR-13 — a failing commit saves no return and no credit note
- **Rules:** `start_return` SR7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. SRBASE.

**When**
- `SR(SRQ((L, "4"), t="refund"))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written: nothing written.

### POS-SR-14 — the return response carries empty warnings
- **Rules:** `receive_replacements` RX8d [BUG-3176] (every other return endpoint returns `warnings == []`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the response has no `warnings` field)

**Given**
1. SRBASE.

**When**
- `result = SR(SRQ((L, "4"), t="refund"))`.

**Then**
1. returns: `WARN(result) == []`.

### POS-SR-15 — exactly 1 unit received is enough to start a return
- **Rules:** `start_return` SR2 (boundary: received > 0)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SRBASE, but L `quantity_received Decimal("1.00")`.

**When**
- `result = SR(SRQ((L, "1"), t="refund"))`.

**Then**
1. returns: `result.status == "pending"`, `result.invoice_id is not None`.
2. committed: the return `result.id` has 1 return line, `po_item_id == L.id`, `quantity_returned == Decimal("1.00")`.

## `PurchaseOrderService.complete_return`

**CRBASE** = O = po "1", but proj, ready, `current_status_id SR1.id`, `invoice_confirmed True`; V = inv(O), but finalized, linked to O; L = poline(O, 1), but `quantity_received Decimal("10.00")`; R = ret "1" of O; RL = rline(R, L, "4"); CN = cn(R, "2000.00"). **CR()** = `svc.complete_return(db, po_id=O.id, return_id=R.id, workspace_id=W1.id, user_id=U2.id)`.

### POS-CR-01 — a refund return completes: quantities, status, stamps; committed
- **Rules:** `complete_return` CR3, CR5, CR8; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. CRBASE.

**When**
- `result = CR()`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R.id`, `result.status == "completed"`.
3. committed: L has `quantity_returned == Decimal("4.00")`, `quantity_received == Decimal("6.00")`, `quantity_refunded == Decimal("4.00")`.
4. committed: R has `completed_at == NOW`, `completed_by == U2.id`.
5. unchanged: unchanged(CN).

### POS-CR-02 — the `return_completed` event of a refund
- **Rules:** `complete_return` CR6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CRBASE.
2. `db.expire_all()` (after the commit point, so the stored return quantity is read).

**When**
- `CR()`.

**Then**
1. committed: the `return_completed` event of O has `description == f"Return {R.return_number} completed — refund (4.00 unit(s), 0 inventory line(s) posted)"` (total as stored, 2 places).
2. committed: its `metadata_json == {"return_id": R.id, "return_type": "refund"}`.

### POS-CR-03 — a replace return leaves the gap and says so
- **Rules:** `complete_return` CR3, CR6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CRBASE, but R replace.
2. `db.expire_all()` (after the commit point, so the stored return quantity is read).

**When**
- `CR()`.

**Then**
1. committed: L has `quantity_received == Decimal("6.00")`, `quantity_refunded == Decimal("0.00")`, `quantity_returned == Decimal("4.00")`.
2. committed: the `return_completed` event of O has `description == f"Return {R.return_number} completed — replace (4.00 unit(s), 0 inventory line(s) posted) — re-receive to close the gap"`.

### POS-CR-04 — a return of another order → 404
- **Rules:** `complete_return` CR1
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE.
2. O2 = po "2", but proj. R2 = ret "2" of O2.

**When**
- `svc.complete_return(db, po_id=O.id, return_id=R2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R2.id)`.
4. unchanged: unchanged(R2).

### POS-CR-05 — a W0 return id → 404
- **Rules:** `complete_return` CR1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0, proj. R0 = ret "0" of O0.
2. CRBASE.

**When**
- `svc.complete_return(db, po_id=O.id, return_id=R0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R0.id)`.
4. unchanged: unchanged(R0).

### POS-CR-06 — a W2 return id → 404
- **Rules:** `complete_return` CR1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CRBASE.
2. O9 = po "9", but of W2, proj. R9 = ret "9" of O9.

**When**
- `svc.complete_return(db, po_id=O.id, return_id=R9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R9.id)`.
4. unchanged: unchanged(R9).

### POS-CR-07 — an already completed return → 400, rolled back
- **Rules:** `complete_return` CR2, CR8; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE, but R completed.
2. X (after the commit point).

**When**
- spies: `CR()` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a pending return can be completed"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(L).

### POS-CR-08 — a voided return → 400
- **Rules:** `complete_return` CR2
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE, but R voided-ret.

**When**
- `CR()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Only a pending return can be completed"`.
3. nothing written: nothing written.

### POS-CR-09 — the return row is locked
- **Rules:** `complete_return` CR1 [BUG-2754]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2754
- **Fails today on:** Then 2 (plain read)

**Given**
1. CRBASE. `oid, rid = O.id, R.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_return(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.status == "completed"`.
2. statement: exact lock(`purchase_order_returns`).
3. statement: `purchase_order_returns` before `purchase_order_return_items`.

### POS-CR-10 — completing stamps `updated_by`
- **Rules:** `complete_return` CR7 [BUG-3174]
- **Kind:** bug
- **Expect:** xfail BUG-3174
- **Fails today on:** Then 2 (`updated_by` stays NULL)

**Given**
1. CRBASE.

**When**
- `result = CR()`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: R has `updated_by == U2.id`.

### POS-CR-11 — a storage order posts the stock out
- **Rules:** `complete_return` CR4, CR6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. CRBASE, but O `destination_type "storage"`, `destination_id F1.id`.
2. Stock of I1 at F1 = 10 @ 500.00 (an `inventory` row plus a seed `inventory_ledger` row, as `stock(A, X)` of `po_receive_inventory.cases.md`).

**When**
- `CR()`.

**Then**
1. committed: `inventory_ledger` rows with `source_type == "purchase_return_item"` and `source_id == RL.id`: exactly 1, quantity 4.
2. committed: the `return_completed` event's description ends with `", 1 inventory line(s) posted)"`.

### POS-CR-12 — not enough stock → 400, everything rolled back
- **Rules:** `complete_return` CR4, CR8; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE, but O `destination_type "storage"`, `destination_id F1.id` (no stock rows at F1).
2. X (after the commit point).

**When**
- `CR()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Insufficient stock (0 available, 4 requested)"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. committed: R has `status == "pending"`, `completed_at is None`.
7. committed: L has `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`.

### POS-CR-13 — a failing commit leaves the return pending
- **Rules:** `complete_return` CR8; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE.

**When**
- `CR()`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R: `status == "pending"`.
4. re-read L: `quantity_received == Decimal("10.00")`.

### POS-CR-14 — the order's stage is not changed
- **Rules:** `complete_return` CR6; RF2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CRBASE, but O complete.

**When**
- `CR()`.

**Then**
1. committed: O has `current_status_id == SC1.id`.
2. committed: `types(O) == ["return_completed"]`.

### POS-CR-15 — a return line pointing at another order's line is skipped
- **Rules:** `complete_return` CR3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CRBASE.
2. O2 = po "2", but proj. L2 = poline(O2, 1), but `quantity_received Decimal("10.00")`.
3. rline(R, L2, "1").

**When**
- `CR()`.

**Then**
1. committed: L2 has `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`.
2. committed: L has `quantity_received == Decimal("6.00")`.

### POS-CR-16 — the completed return's response carries empty warnings
- **Rules:** `receive_replacements` RX8d [BUG-3176] (every other return endpoint returns `warnings == []`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the response has no `warnings` field)

**Given**
1. CRBASE.

**When**
- `result = CR()`.

**Then**
1. returns: `WARN(result) == []`.

### POS-CR-17 — completing adds to quantities already returned and refunded
- **Rules:** `complete_return` CR3 (`+=`, not `=`); CR3a (8.00 − 4 = 4.00 ≥ 0, so the floor does not apply; holds before and after BUG-3186)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CRBASE, but L `quantity_received Decimal("8.00")`, `quantity_returned Decimal("2.00")`, `quantity_refunded Decimal("2.00")` (an earlier refund return of 2).

**When**
- `CR()`.

**Then**
1. committed: L has `quantity_returned == Decimal("6.00")`, `quantity_refunded == Decimal("6.00")`, `quantity_received == Decimal("4.00")`.

### POS-CR-18 — a return whose line was corrected to 0 meanwhile is refused, nothing written
- **Rules:** `complete_return` CR3a [BUG-3186], CR8; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3186
- **Fails today on:** Then 1 (no error: the return completes and L stores `quantity_received == Decimal("-4.00")`)

**Given**
1. O = po "1", but proj, ready, `current_status_id SR1.id`, `invoice_confirmed True`; V = inv(O), but finalized, linked to O; L = poline(O, 1).
2. Given steps (code, in this order): `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=RCV((L, "4")))`; `R = svc.start_return(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=SRQ((L, "4"), t="refund"))`; `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=COR((L, "-4"), note="Recount"))` (RE5 allows it: 4 − 4 = 0, pending returns are not counted).
3. `db.expire_all()`; re-read L has `quantity_received == Decimal("0.00")`, `quantity_returned == Decimal("0.00")`; R has `status == "pending"`. `rno = R.return_number`.
4. X (after the commit point).

**When**
- `CR()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Cannot complete return {rno} — line 1 has only 0.00 received; correct the receipt or cancel the return"` (`{quantity_received}` as stored, 2 places).
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. nothing written: nothing written.
7. unchanged: unchanged(L) (`quantity_received == Decimal("0.00")`, `quantity_returned == Decimal("0.00")`, `quantity_refunded == Decimal("0.00")`).
8. unchanged: unchanged(R) (`status == "pending"`, `completed_at is None`); `types(O)` has no `return_completed`.

### POS-CR-19 — one short line refuses the whole return before any line is written
- **Rules:** `complete_return` CR3a [BUG-3186] ("before anything is written, every return line … is checked"); TC3
- **Kind:** bug
- **Expect:** xfail BUG-3186
- **Fails today on:** Then 1 (no error: both lines are written, L2 stores `quantity_received == Decimal("-1.00")`)

**Given**
1. CRBASE (L `quantity_received Decimal("10.00")`, RL = rline(R, L, "4")).
2. L2 = poline(O, 2), but `quantity_received Decimal("2.00")`; rline(R, L2, "3") (invalid data built on purpose: received was lowered after the return started, as in CR-18).
3. X (after the commit point).

**When**
- `CR()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Cannot complete return {R.return_number} — line 2 has only 2.00 received; correct the receipt or cancel the return"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. nothing written: nothing written.
7. unchanged: unchanged(L) (line 1 not written either: `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`), unchanged(L2), unchanged(R).

### POS-CR-20 — a line that ends at exactly 0 completes
- **Rules:** `complete_return` CR3, CR3a ("exactly 0 is allowed"; holds before and after BUG-3186), CR5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CRBASE, but L `quantity_received Decimal("4.00")` (RL returns 4).

**When**
- `result = CR()`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: L has `quantity_received == Decimal("0.00")`, `quantity_returned == Decimal("4.00")`, `quantity_refunded == Decimal("4.00")`.
3. committed: R has `completed_at == NOW`, `completed_by == U2.id`.

## `PurchaseOrderService.void_return`

**VR(note)** = `svc.void_return(db, po_id=O.id, return_id=R.id, workspace_id=W1.id, user_id=U2.id, void_note=note)`; Givens start from **CRBASE** (above).

### POS-VR-01 — cancel voids the credit note and the return; committed; no quantities move
- **Rules:** `void_return` VR3, VR4, VR6; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. CRBASE.

**When**
- `result = VR("Wrong item")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R.id`, `result.status == "voided"`.
3. committed: R has `paid is False`.
4. committed: CN has `invoice_status == "voided"`, `void_note == "Wrong item"`.
5. committed: the `return_voided` event of O has `description == f"Return {R.return_number} cancelled — Wrong item"`, `metadata_json == {"return_id": R.id, "void_note": "Wrong item"}`.
6. unchanged: unchanged(L).

### POS-VR-02 — the credit note's payments are voided with it
- **Rules:** `void_return` VR3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CRBASE, but CN `paid_amount Decimal("500.00")`, `payment_status "partial"`.
2. P = cash(CN, "500.00").

**When**
- `VR("Wrong item")`.

**Then**
1. committed: P has `is_voided is True`.
2. committed: CN has `invoice_status == "voided"`.

### POS-VR-03 — a return of another order → 404
- **Rules:** `void_return` VR1
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE.
2. O2 = po "2", but proj. R2 = ret "2" of O2.

**When**
- `svc.void_return(db, po_id=O.id, return_id=R2.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R2.id)`.
4. unchanged: unchanged(R2).

### POS-VR-04 — a W2 return id → 404
- **Rules:** `void_return` VR1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CRBASE.
2. O9 = po "9", but of W2, proj. R9 = ret "9" of O9.

**When**
- `svc.void_return(db, po_id=O.id, return_id=R9.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R9.id)`.
4. unchanged: unchanged(R9).

### POS-VR-05 — a completed return → 400, rolled back
- **Rules:** `void_return` VR2, VR6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE, but R completed.
2. X (after the commit point).

**When**
- spies: `VR("x")` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a pending return can be cancelled"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(CN).

### POS-VR-06 — the return row is locked
- **Rules:** `void_return` VR1 [BUG-2754]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2754
- **Fails today on:** Then 2 (plain read)

**Given**
1. CRBASE. `oid, rid = O.id, R.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_return(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id, void_note="Wrong item")`.

**Then**
1. returns: `result.status == "voided"`.
2. statement: exact lock(`purchase_order_returns`).
3. statement: `purchase_order_returns` before `account_invoices`.

### POS-VR-07 — cancelling stamps `updated_by`
- **Rules:** `void_return` VR5 [BUG-3174]
- **Kind:** bug
- **Expect:** xfail BUG-3174
- **Fails today on:** Then 2 (unchanged)

**Given**
1. CRBASE.

**When**
- `result = VR("Wrong item")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: R has `updated_by == U2.id`.

### POS-VR-08 — a credit note already voided is skipped and the cancel goes ahead
- **Rules:** `void_return` VR3 [BUG-3182]
- **Kind:** bug
- **Expect:** xfail BUG-3182
- **Fails today on:** Then 1 (the call raises HTTPException 400 `Invoice is already voided`)

**Given**
1. CRBASE, but CN voided-inv.

**When**
- `result = VR("Wrong item")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: R has `status == "voided"`, `paid is False`.
3. committed: CN has `void_note == "dup"`.

### POS-VR-09 — a return with no credit note cancels
- **Rules:** `void_return` VR3, VR4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but proj, ready. L = poline(O, 1), but `quantity_received Decimal("10.00")`.
2. R = ret "1" of O. rline(R, L, "4").

**When**
- `result = VR("Wrong item")`.

**Then**
1. returns: `result.status == "voided"`.
2. committed: `"return_voided" in types(O)`.

### POS-VR-10 — a failing commit leaves the return pending and the note owed
- **Rules:** `void_return` VR6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. CRBASE.

**When**
- `VR("Wrong item")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R: `status == "pending"`.
4. re-read CN: `invoice_status == "confirmed"`.

### POS-VR-11 — schema: a whitespace-only void note is refused
- **Rules:** `void_return` VR7 [BUG-3168]
- **Kind:** bug
- **Expect:** xfail BUG-3168
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `PurchaseOrderReturnVoidRequest(void_note="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-VR-12 — schema: the void note is trimmed
- **Rules:** `void_return` VR7 [BUG-3168]
- **Kind:** bug
- **Expect:** xfail BUG-3168
- **Fails today on:** Then 1 (stored as typed)

**Given**
1. Nothing.

**When**
- `result = PurchaseOrderReturnVoidRequest(void_note=" Wrong item ")` (target `schema`).

**Then**
1. returns: `result.void_note == "Wrong item"`.

### POS-VR-13 — schema: an empty void note is refused
- **Rules:** `void_return` VR7 (holds today and after BUG-3168)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `PurchaseOrderReturnVoidRequest(void_note="")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-VR-14 — the cancelled return's response carries empty warnings
- **Rules:** `receive_replacements` RX8d [BUG-3176] (every other return endpoint returns `warnings == []`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the response has no `warnings` field)

**Given**
1. CRBASE.

**When**
- `result = VR("Wrong item")`.

**Then**
1. returns: `WARN(result) == []`.

## `PurchaseOrderService.list_returns` / `get_return`

### POS-LRT-01 — list: a W2 order → 404 first; no rollback
- **Rules:** `list_returns` LRT1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po "9", but of W2, proj. ret "9" of O9.
2. X (after the commit point).

**When**
- spies: `svc.list_returns(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### POS-LRT-02 — list: the order's returns; a read
- **Rules:** `list_returns` LRT2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but proj. R1 = ret "1" of O. R2 = ret "2" of O, but completed.
2. O2 = po "2", but proj. ret "3" of O2.
3. X (after the commit point).

**When**
- spies: `result = svc.list_returns(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == sorted([R1.id, R2.id])`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### POS-LRT-03 — get: returns the return without a lock
- **Rules:** `get_return` LRT2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but proj. R = ret "1" of O. `oid, rid = O.id, R.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- spies: `result = svc.get_return(db, po_id=oid, return_id=rid, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == rid`.
2. statement: no lock.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.

### POS-LRT-04 — get: a return of another order → 404
- **Rules:** `get_return` LRT2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but proj. O2 = po "2", but proj. R2 = ret "2" of O2.

**When**
- `svc.get_return(db, po_id=O.id, return_id=R2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R2.id)`.

### POS-LRT-05 — get: a W0 order → 404 before the return is read
- **Rules:** `get_return` LRT1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0, proj. R0 = ret "0" of O0.
2. O = po "1".

**When**
- `svc.get_return(db, po_id=O0.id, return_id=R0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.

## `PurchaseOrderService.list_active_orders_for_context`

**AO(**scope)** = `svc.list_active_orders_for_context(db, workspace_id=W1.id, **scope)`.

### POS-AO-01 — no scope → 400
- **Rules:** `list_active_orders_for_context` AO1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `AO()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Provide exactly one of machine_id, factory_id, project_component_id"`.

### POS-AO-02 — two scopes → 400
- **Rules:** `list_active_orders_for_context` AO1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `AO(factory_id=F1.id, project_component_id=5)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Provide exactly one of machine_id, factory_id, project_component_id"`.

### POS-AO-03 — an id of 0 counts as given
- **Rules:** `list_active_orders_for_context` AO1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `AO(machine_id=0, factory_id=F1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.

### POS-AO-04 — a W2 factory → 404
- **Rules:** `list_active_orders_for_context` AO2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. po "9", but of W2.

**When**
- `AO(factory_id=F9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory not found"`.

### POS-AO-05 — a W0 factory → 404
- **Rules:** `list_active_orders_for_context` AO2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. po "0", but of W0.

**When**
- `AO(factory_id=F0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Factory not found"`.

### POS-AO-06 — a missing machine → 404
- **Rules:** `list_active_orders_for_context` AO2
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `AO(machine_id=MISSING)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found"`.

### POS-AO-07 — a missing project component → 404
- **Rules:** `list_active_orders_for_context` AO2
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `AO(project_component_id=MISSING)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Project component not found"`.

### POS-AO-08 — factory scope: the factory's open POs with every row field; another factory's not listed
- **Rules:** `list_active_orders_for_context` AO3, AO4, AO6 (part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1b = `Factory(workspace_id=W1.id, name="Second Store", abbreviation="SS1", is_active=True, is_deleted=False)`.
2. O = po "1", but `current_status_id SP1.id`.
3. po "2", but `destination_id F1b.id`.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].order_kind == "purchase"`, `result[0].id == O.id`, `result[0].number == O.po_number`, `result[0].summary == "Bearings for Press 4"`.
3. returns: `result[0].current_status_id == SP1.id`, `result[0].status_name == "Planning"`, `result[0].total_amount == Decimal("5000.00")`, `result[0].created_at == O.created_at`.

### POS-AO-09 — a PO at the last stage of its workflow is skipped
- **Rules:** `list_active_orders_for_context` AO3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1", but complete.
2. O2 = po "2", but `current_status_id SR1.id`.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O2.id]`.

### POS-AO-10 — a PO with no workflow is never skipped
- **Rules:** `list_active_orders_for_context` AO3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po "1", but complete, `order_workflow_id None`.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.

### POS-AO-11 — a workflow with an empty sequence never skips
- **Rules:** `list_active_orders_for_context` AO3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `WF1.status_sequence = []`, flushed (W1 holds one purchase workflow only, `uq_order_workflows_workspace_type`; spec Facts, G19).
2. O1 = po "1", but complete.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.

### POS-AO-12 — a sequence ending in a non-integer never skips
- **Rules:** `list_active_orders_for_context` AO3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `WF1.status_sequence = [SD1.id, "done"]`, flushed (one purchase workflow per workspace; spec Facts, G19).
2. O1 = po "1", but complete.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.

### POS-AO-13 — a voided PO is not listed
- **Rules:** `list_active_orders_for_context` AO6 [BUG-3173]
- **Kind:** bug
- **Expect:** xfail BUG-3173
- **Fails today on:** Then 1 (the voided PO is listed)

**Given**
1. O1 = po "1", but voided.
2. O2 = po "2".

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O2.id]`.

### POS-AO-14 — W0 and W2 POs pointing at the W1 factory are not listed
- **Rules:** `list_active_orders_for_context` AO3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. po "0", but of W0, `destination_id F1.id` (invalid data).
2. O1 = po "1".
3. po "9", but of W2, `destination_id F1.id` (invalid data).

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.

### POS-AO-15 — a soft-deleted factory still lists its open POs
- **Rules:** `list_active_orders_for_context` AO2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Fd = `Factory(workspace_id=W1.id, name="Old Store", abbreviation="OS1", is_active=False, is_deleted=True)`.
2. O1 = po "1", but `destination_id Fd.id`.

**When**
- `result = AO(factory_id=Fd.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.

### POS-AO-16 — rows are sorted newest first
- **Rules:** `list_active_orders_for_context` AO10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po "1", then `O1.created_at = T2`, flush.
2. O2 = po "2", then `O2.created_at = T0`, flush.
3. O3 = po "3", then `O3.created_at = T1`, flush.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result] == [O1.id, O3.id, O2.id]`.

### POS-AO-17 — transfers touching the scope are listed until completed
- **Rules:** `list_active_orders_for_context` AO5, AO10
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = `TransferOrder(workspace_id=W1.id, transfer_number=f"TO-{TAG}-1", source_location_type="storage", source_location_id=F1.id, destination_location_type="machine", destination_location_id=MISSING, current_status_id=SP1.id, description="To press", created_at=T1, completed_at=None)` (`app.models.transfer_order`).
2. TB = the same, but `transfer_number f"TO-{TAG}-2"`, `source_location_type "machine"`, `source_location_id MISSING`, `destination_location_type "storage"`, `destination_location_id F1.id`, `description "From press"`.
3. TC = the same as TA, but `transfer_number f"TO-{TAG}-3"`, `completed_at T2`.
4. TD = the same as TA, but `workspace_id W2.id`, `transfer_number f"TO-{TAG}-4"`, `source_location_id F9.id`, `current_status_id SP9.id`.
5. O1 = po "1", but `created_at T1`.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `result[0].order_kind == "purchase"`, `result[0].id == O1.id` (equal `created_at`: purchase rows first).
2. returns: `{r.id for r in result if r.order_kind == "transfer"} == {TA.id, TB.id}`.
3. returns: the TA row has `number == TA.transfer_number`, `summary == "To press"`, `current_status_id == SP1.id`, `total_amount is None`.
4. returns: `len(result) == 3`.

### POS-AO-18 — machine scope lists in-flight work orders; factory scope lists none
- **Rules:** `list_active_orders_for_context` AO7
- **Kind:** happy
- **Expect:** pass
- **Author:** claude (a `WorkOrder` needs columns the spec does not describe, e.g. its type and factory; fill them with valid W1 rows)

**Given**
1. M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 4", is_deleted=False)`.
2. **wo(n, st)** = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-n", title="Oil change", status=st, machine_id=M1.id, cost=None, is_deleted=False)` (`app.models.work_order`). WD = wo("1", "DRAFT"); WP = wo("2", "IN_PROGRESS"), but `cost Decimal("1200.00")`, `title "Belt swap"`; wo("3", "COMPLETED"); wo("4", "VOIDED"); wo("5", "IN_PROGRESS"), but `is_deleted True`.

**When**
- `result = AO(machine_id=M1.id)`.

**Then**
1. returns: `{r.id for r in result if r.order_kind == "work"} == {WD.id, WP.id}`.
2. returns: the WP row has `number == WP.work_order_number`, `summary == "Belt swap"`, `current_status_id is None`, `status_name == "In Progress"`, `total_amount == Decimal("1200.00")`.
3. returns: the WD row has `status_name == "Draft"`, `total_amount is None`.
4. returns: `[r for r in AO(factory_id=F1.id) if r.order_kind == "work"] == []`.

### POS-AO-19 — machine scope: an old in-flight work order behind 1,000 newer ones is listed
- **Rules:** `list_active_orders_for_context` AO9 [BUG-3166]; HR-5
- **Kind:** bug
- **Expect:** xfail BUG-3166
- **Author:** claude (a `WorkOrder` needs columns the spec does not describe, e.g. its type and factory; bulk insert for speed)
- **Fails today on:** Then 1 (only the newest 1,000 work orders are read)

**Given**
1. M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 4", is_deleted=False)`.
2. W_old = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-old", title="Old job", status="IN_PROGRESS", machine_id=M1.id, is_deleted=False, created_at=T0)`.
3. 1,000 `WorkOrder` rows of M1, `status "COMPLETED"`, `work_order_number f"WO-{TAG}-{i}"`, `created_at T1 + timedelta(seconds=i)` for i in 0 … 999.

**When**
- `result = AO(machine_id=M1.id)`.

**Then**
1. returns: `[r.id for r in result if r.order_kind == "work"] == [W_old.id]`.

### POS-AO-20 — component scope: in-flight work orders of the component (today's behaviour)
- **Rules:** `list_active_orders_for_context` AO3, AO8 (*revisit after launch*)
- **Kind:** happy
- **Expect:** pass
- **Author:** claude (a `ProjectComponent` needs its project row and a `WorkOrder` its type and factory; the spec does not describe them)

**Given**
1. PC = a `ProjectComponent` of W1 (`app.models.project_component`) with its project.
2. OP = po "1", but `destination_type "project"`, `destination_id PC.id`.
3. WD = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-1", title="Pour", status="DRAFT", project_component_id=PC.id, is_deleted=False)`; WC = the same, but `work_order_number f"WO-{TAG}-2"`, `status "COMPLETED"`.

**When**
- `result = AO(project_component_id=PC.id)`.

**Then**
1. returns: `sorted((r.order_kind, r.id) for r in result) == [("purchase", OP.id), ("work", WD.id)]`.

### POS-AO-22 — component scope: a work order of another component, or of none, is skipped
- **Rules:** `list_active_orders_for_context` AO8 (*revisit after launch*); branch map 1176 (other component → skip)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude (as AO-20: the project row behind a component and the work order's type / factory columns are not described)

**Given**
1. PC, PC2 = two `ProjectComponent` rows of W1 (as AO-20), each with its project.
2. WD = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-1", title="Pour", status="DRAFT", project_component_id=PC.id, is_deleted=False)`.
3. WO2 = the same, but `work_order_number f"WO-{TAG}-2"`, `status "IN_PROGRESS"`, `project_component_id PC2.id`.
4. WN = the same, but `work_order_number f"WO-{TAG}-3"`, `project_component_id None`.

**When**
- `result = AO(project_component_id=PC.id)`.

**Then**
1. returns: `[(r.order_kind, r.id) for r in result if r.order_kind == "work"] == [("work", WD.id)]`.
2. returns: no row has `id` in `{WO2.id, WN.id}` with `order_kind == "work"`.

### POS-AO-21 — a read: no commit, no rollback, nothing written
- **Rules:** `list_active_orders_for_context` AO10; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. po "1".
2. X (after the commit point).

**When**
- spies: `AO(factory_id=F1.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.
4. session: `not db.new` (the read added nothing pending).

### POS-AO-23 — machine scope: POs to the machine and transfers touching it
- **Rules:** `list_active_orders_for_context` AO3 (`machine` → `machine`/id), AO5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 4", is_deleted=False)` (as AO-18).
2. OM = po "1", but `destination_type "machine"`, `destination_id M1.id`.
3. po "2" (storage, F1: not listed for the machine).
4. TM1 = `TransferOrder(workspace_id=W1.id, transfer_number=f"TO-{TAG}-1", source_location_type="storage", source_location_id=F1.id, destination_location_type="machine", destination_location_id=M1.id, current_status_id=SP1.id, description="To press", created_at=T1, completed_at=None)` (as AO-17).
5. TM2 = the same, but `transfer_number f"TO-{TAG}-2"`, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `description "From press"`.
6. TS = the same as TM1, but `transfer_number f"TO-{TAG}-3"`, `destination_location_type "storage"`, `destination_location_id F1.id` (does not touch the machine).

**When**
- `result = AO(machine_id=M1.id)`.

**Then**
1. returns: `{(r.order_kind, r.id) for r in result if r.order_kind != "work"} == {("purchase", OM.id), ("transfer", TM1.id), ("transfer", TM2.id)}`.

### POS-AO-24 — component scope: POs to the component and transfers touching it
- **Rules:** `list_active_orders_for_context` AO3 (component → `project`/id), AO5 (*revisit after launch*)
- **Kind:** happy
- **Expect:** pass
- **Author:** claude (as AO-20: the project row behind a component is not described)

**Given**
1. PC = a `ProjectComponent` of W1 with its project (as AO-20).
2. OP = po "1", but `destination_type "project"`, `destination_id PC.id`.
3. po "2" (storage, F1: not listed for the component).
4. TP1 = `TransferOrder(workspace_id=W1.id, transfer_number=f"TO-{TAG}-1", source_location_type="storage", source_location_id=F1.id, destination_location_type="project", destination_location_id=PC.id, current_status_id=SP1.id, description="To site", created_at=T1, completed_at=None)`.
5. TP2 = the same, but `transfer_number f"TO-{TAG}-2"`, `source_location_type "project"`, `source_location_id PC.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `description "From site"`.

**When**
- `result = AO(project_component_id=PC.id)`.

**Then**
1. returns: `{(r.order_kind, r.id) for r in result if r.order_kind != "work"} == {("purchase", OP.id), ("transfer", TP1.id), ("transfer", TP2.id)}`.

### POS-AO-25 — a one-stage workflow: its only stage is the last, so the PO is skipped
- **Rules:** `list_active_orders_for_context` AO3 (a non-empty sequence of length 1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `WF1.status_sequence = [SC1.id]`, flushed (as AO-11: W1 keeps its one purchase workflow).
2. O1 = po "1", but complete.
3. O2 = po "2", but `current_status_id SR1.id`.

**When**
- `result = AO(factory_id=F1.id)`.

**Then**
1. returns: `[r.id for r in result if r.order_kind == "purchase"] == [O2.id]`.

## `PurchaseOrderService.delete_purchase_order`

### POS-X-01 — an order with a draft invoice is deleted with it; committed
- **Rules:** `delete_purchase_order` X1 [BUG-2888]; TC1
- **Kind:** bug
- **Expect:** xfail BUG-2888
- **Fails today on:** Then 3 (the draft invoice stays when its order is deleted)

**Given**
1. O = po "1", but ready. `oid = O.id`.
2. L = poline(O, 1).
3. V = inv(O), linked to O. `vid = V.id`.

**When**
- `result = svc.delete_purchase_order(db, po_id=oid, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. committed: `purchase_orders` with `id == oid`: 0.
3. committed: `account_invoices` with `id == vid`: 0.

### POS-X-02 — a W2 order → 404, rolled back
- **Rules:** `delete_purchase_order` X1; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1".
2. O9 = po "9", but of W2.
3. X (after the commit point).

**When**
- spies: `svc.delete_purchase_order(db, po_id=O9.id, workspace_id=W1.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(O9).

### POS-X-03 — recorded receiving → 400
- **Rules:** `delete_purchase_order` X1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. poline(O, 1), but `quantity_received Decimal("3.00")`.

**When**
- `svc.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a purchase order with recorded receiving — void the order instead"`.
4. unchanged: unchanged(O).

### POS-X-04 — receiving history → 400
- **Rules:** `delete_purchase_order` X1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. `PoReceiveEvent(workspace_id=W1.id, purchase_order_id=O.id, event_type="receive", performed_by=U1.id, created_at=T0)`.

**When**
- `svc.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Cannot delete a purchase order with receiving history — void the order instead"`.
3. unchanged: unchanged(O).

### POS-X-05 — a finalized invoice blocks the delete
- **Rules:** `delete_purchase_order` X1 [BUG-2888]
- **Kind:** bug
- **Expect:** xfail BUG-2888
- **Fails today on:** Then 1 (the order is deleted)

**Given**
1. O = po "1", but ready.
2. V = inv(O), but finalized, linked to O.

**When**
- `svc.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a purchase order with a finalized invoice — void the order instead"`.
4. unchanged: unchanged(V).

### POS-X-06 — the delete takes `user_id` and leaves an audit row
- **Rules:** `delete_purchase_order` X2 [BUG-1195]
- **Kind:** bug
- **Expect:** xfail BUG-1195
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. O = po "1". `oid = O.id`.

**When**
- `result = svc.delete_purchase_order(db, po_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `workspace_audit_logs` of W1: exactly 1 row.

### POS-X-07 — a failing commit keeps the order
- **Rules:** `delete_purchase_order` X1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `svc.delete_purchase_order(db, po_id=O.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `purchase_orders` with `id == O.id`: 1.

### POS-X-08 — an order with no invoice and no receiving is deleted; committed
- **Rules:** `delete_purchase_order` X1; TC1 (holds today and after BUG-2888)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". `oid = O.id`.
2. L = poline(O, 1). `lid = L.id`.

**When**
- spies: `result = svc.delete_purchase_order(db, po_id=oid, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 1`.
3. committed: `purchase_orders` with `id == oid`: 0.
4. committed: `purchase_order_items` with `id == lid`: 0.

## `PurchaseOrderService.add_item`

**NEWLINE** = `PurchaseOrderItemCreate(item_id=I1b.id, quantity_ordered=Decimal("5"), unit_price=Decimal("300.00"))`.

### POS-AI-01 — the line is added, the order stamped; committed
- **Rules:** `add_item` AI1, AI2, AI3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, PurchaseOrderItem)`, `result.purchase_order_id == O.id`.
3. committed: the line `result.id` has `item_id == I1b.id`, `quantity_ordered == Decimal("5.00")`.
4. committed: O has `items_updated_at == NOW`.

### POS-AI-02 — without `user_id` no invoice step runs
- **Rules:** `add_item` AI2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`.
2. V = inv(O), linked to O.

**When**
- `svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id)`.

**Then**
1. committed: O has `invoice_id == V.id`, `items_updated_at == NOW`.
2. committed: `account_invoices` with `id == V.id`: 1.

### POS-AI-03 — with `user_id` the invoice step runs (an unconfirmed order loses its draft)
- **Rules:** `add_item` AI2; SD2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`.
2. V = inv(O), linked to O. `vid = V.id`.

**When**
- `svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: `account_invoices` with `id == vid`: 0.
2. committed: O has `invoice_id is None`.

### POS-AI-04 — a missing order → 404, rolled back
- **Rules:** `add_item` AI1, AI3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. X (after the commit point).

**When**
- spies: `svc.add_item(db, po_id=MISSING, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Purchase order not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. nothing written: nothing written.

### POS-AI-05 — an IntegrityError is translated with the items phase
- **Rules:** `add_item` AI3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1".
2. `mgr.add_item` patched to raise `IERR("violates foreign key", "23503", "purchase_order_items", "item_id")`.
3. X (after the commit point).

**When**
- `svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.

### POS-AI-06 — items confirmed → the manager's 400
- **Rules:** `add_item` AI1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `items_confirmed True`.

**When**
- `svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order items are confirmed"`.
4. nothing written: nothing written.

### POS-AI-07 — a failing commit saves no line
- **Rules:** `add_item` AI3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `svc.add_item(db, po_id=O.id, item_in=NEWLINE, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `purchase_order_items` of O: 0.
4. re-read O: `items_updated_at is None`.

## `PurchaseOrderService.update_item`

### POS-UI-01 — the line is updated, the order stamped; committed
- **Rules:** `update_item` UI1, UI2, UI3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L = poline(O, 1).

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == L.id`.
3. committed: L has `unit_price == Decimal("450.00")`.
4. committed: O has `items_updated_at == NOW`.

### POS-UI-02 — without `user_id` the order is not stamped
- **Rules:** `update_item` UI2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. L = poline(O, 1).

**When**
- `svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=W1.id)`.

**Then**
1. committed: L has `unit_price == Decimal("450.00")`.
2. committed: O has `items_updated_at is None`.

### POS-UI-03 — a W2 line → 404, rolled back
- **Rules:** `update_item` UI1, UI3; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po "9", but of W2. L9 = poline(O9, 1).
2. X (after the commit point).

**When**
- spies: `svc.update_item(db, item_id=L9.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("1.00")), workspace_id=W1.id, user_id=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Purchase order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(L9).

### POS-UI-04 — schema: a body with `quantity_received` is refused
- **Rules:** `update_item` UI1 [BUG-2887]
- **Kind:** bug
- **Expect:** xfail BUG-2887
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `PurchaseOrderItemUpdate(quantity_received=Decimal("3"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-UI-05 — an IntegrityError is translated with the items phase
- **Rules:** `update_item` UI3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1". L = poline(O, 1).
2. `mgr.update_item` patched to raise `IERR("null value in column", "23502", "purchase_order_items", "unit_price")`.

**When**
- `svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Order line data is incomplete (purchase_order_items.unit_price). Refresh the page and try again."`.

### POS-UI-06 — a failing commit keeps the old price
- **Rules:** `update_item` UI3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).

**When**
- `svc.update_item(db, item_id=L.id, item_in=PurchaseOrderItemUpdate(unit_price=Decimal("450.00")), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `unit_price == Decimal("500.00")`.

## `PurchaseOrderService.remove_item`

### POS-RI-01 — the line is removed and returned readable; the order stamped; committed
- **Rules:** `remove_item` RI1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1). `lid = L.id`.

**When**
- `result = svc.remove_item(db, item_id=lid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == lid`, `result.line_number == 1`.
2. committed: `purchase_order_items` with `id == lid`: 0.
3. committed: O has `items_updated_at == NOW`.

### POS-RI-02 — without `user_id` the order is not stamped
- **Rules:** `remove_item` RI1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).

**When**
- `svc.remove_item(db, item_id=L.id, workspace_id=W1.id)`.

**Then**
1. committed: O has `items_updated_at is None`.

### POS-RI-03 — a missing line → 404, rolled back
- **Rules:** `remove_item` RI1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).
2. X (after the commit point).

**When**
- `svc.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Purchase order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. unchanged: unchanged(L).

### POS-RI-04 — a failing commit keeps the line
- **Rules:** `remove_item` RI1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).

**When**
- `svc.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `purchase_order_items` with `id == L.id`: 1.

### POS-RI-05 — an IntegrityError is rolled back and translated with the items phase
- **Rules:** `remove_item` RI1 (errors as AI3); `_handle_item_integrity_error` IE4; TC3; branch map 1262–1270
- **Kind:** error
- **Expect:** pass
- **Author:** claude (patches the manager, as AI-05)

**Given**
1. O = po "1". L = poline(O, 1).
2. `mgr.remove_item` patched to raise `IERR("violates foreign key", "23503", "purchase_order_items", "item_id")`.
3. X (after the commit point).

**When**
- spies: `svc.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "A linked catalog item or order reference is missing. Refresh the page and try again."`.
4. raises: `isinstance(exc.value.__cause__, IntegrityError)`.
5. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
6. mock called: `rb.call_count >= 1`.
7. committed: x_gone.
8. committed: `purchase_order_items` with `id == L.id`: 1.

## `PurchaseOrderService.sync_items`

**SYNC(remove_ids, updates, additions)** = `PurchaseOrderItemSyncRequest(remove_ids=remove_ids, updates=updates, additions=additions)` (`updates` items are `PurchaseOrderItemSyncUpdate(id=…, quantity_ordered=…, unit_price=…)`). **SY(body, **k)** = `svc.sync_items(db, po_id=O.id, sync_in=body, workspace_id=W1.id, **k)`.

### POS-SY-01 — an addition is saved and the order stamped; committed
- **Rules:** `sync_items` SY1, SY3, SY4 (side that holds today); TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". poline(O, 1).

**When**
- `result = SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: `purchase_order_items` of O: 2.
4. committed: O has `items_updated_at == NOW`.

### POS-SY-02 — the lines and the invoice step are one commit
- **Rules:** `sync_items` SY2 [BUG-3179]
- **Kind:** bug
- **Expect:** xfail BUG-3179
- **Fails today on:** Then 2 (two commits)

**Given**
1. O = po "1". poline(O, 1).

**When**
- spies: `result = SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 1`.

### POS-SY-03 — an invoice-step failure keeps the lines unsaved
- **Rules:** `sync_items` SY2 [BUG-3179]
- **Kind:** bug
- **Expect:** xfail BUG-3179
- **Fails today on:** Then 3 (the added line was already committed)

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. V = inv(O), but `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O.
3. cash(V, "100.00").

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. committed: `purchase_order_items` of O: 1.

### POS-SY-04 — an invoice-step refusal reaches the caller and the draft stays
- **Rules:** `sync_items` SY3 (part that holds today and after BUG-3179)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. V = inv(O), but `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O.
3. cash(V, "100.00").

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. count: `account_invoices` with `id == V.id`: 1.

### POS-SY-05 — an empty request does not stamp the order
- **Rules:** `sync_items` SY4 [BUG-3165]; HR-9
- **Kind:** bug
- **Expect:** xfail BUG-3165
- **Fails today on:** Then 2 (stamped NOW)

**Given**
1. O = po "1". poline(O, 1).

**When**
- `result = SY(SYNC([], [], []), user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: O has `items_updated_at is None`.

### POS-SY-06 — without `user_id`: no invoice step, no stamp
- **Rules:** `sync_items` SY3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. V = inv(O), linked to O.

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]))`.

**Then**
1. committed: `purchase_order_items` of O: 2.
2. committed: O has `items_updated_at is None`, `invoice_id == V.id`.

### POS-SY-07 — no supplier: no invoice step, no stamp
- **Rules:** `sync_items` SY3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `account_id None`. poline(O, 1).

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. committed: `purchase_order_items` of O: 2.
2. committed: O has `items_updated_at is None`.

### POS-SY-08 — the manager's 404 for an unknown removal id; rolled back
- **Rules:** `sync_items` SY1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". poline(O, 1).
2. X (after the commit point).

**When**
- `SY(SYNC([MISSING], [], []), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Purchase order item {MISSING} not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. nothing written: nothing written.

### POS-SY-09 — a failing commit saves no line
- **Rules:** `sync_items` SY1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". poline(O, 1).

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `purchase_order_items` of O: 1.

### POS-SY-10 — a line-phase IntegrityError is rolled back and translated with the items phase
- **Rules:** `sync_items` SY1; `_handle_item_integrity_error` IE3; TC3; branch map 1292–1300
- **Kind:** error
- **Expect:** pass
- **Author:** claude (patches the manager, as AI-05)

**Given**
1. O = po "1". poline(O, 1).
2. `mgr.sync_items` patched to raise `IERR("null value in column", "23502", "purchase_order_items", "quantity_ordered")`.
3. X (after the commit point).

**When**
- spies: `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Order line data is incomplete (purchase_order_items.quantity_ordered). Refresh the page and try again."`.
4. raises: `isinstance(exc.value.__cause__, IntegrityError)`.
5. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
6. mock called: `cm.call_count == 0`.
7. mock called: `rb.call_count >= 1`.
8. committed: x_gone.
9. committed: `purchase_order_items` of O: 1.

### POS-SY-11 — an invoice-step IntegrityError is translated with the invoice phase
- **Rules:** `sync_items` SY3; `_handle_item_integrity_error` IE4 (`phase='invoice'`); branch map 1308–1316 (holds today and after BUG-3179)
- **Kind:** error
- **Expect:** pass
- **Author:** claude (patches `svc._sync_draft_invoice_for_po`)

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. `svc._sync_draft_invoice_for_po` patched to raise `IERR("violates foreign key", "23503", "purchase_order_items", "item_id")` (a lines table, so only the phase picks the invoice message).

**When**
- spies: `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The selected supplier or linked invoice is invalid. Refresh and try again."`.
4. raises: `isinstance(exc.value.__cause__, IntegrityError)`.
5. mock called: `rb.call_count >= 1`.

### POS-SY-12 — an invoice-step IntegrityError undoes the line changes and every pending row
- **Rules:** `sync_items` SY2 [BUG-3179], SY3; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3179
- **Fails today on:** Then 3 (the line phase was committed first, taking the added line and X with it, so X is still in the session)
- **Author:** claude (patches `svc._sync_draft_invoice_for_po`)

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. `svc._sync_draft_invoice_for_po` patched to raise `IERR("violates foreign key", "23503", "purchase_order_items", "item_id")`.
3. X (after the commit point).

**When**
- `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. committed: `purchase_order_items` of O: 1.
5. committed: x_gone.

### POS-SY-13 — any other invoice-step error is rolled back and re-raised as the same object
- **Rules:** `sync_items` SY3; TC2; branch map 1308–1316
- **Kind:** error
- **Expect:** pass
- **Author:** claude (patches `svc._sync_draft_invoice_for_po`)

**Given**
1. O = po "1", but `supplier_confirmed True`. poline(O, 1).
2. `boom = RuntimeError("sync boom")`; `svc._sync_draft_invoice_for_po` patched to raise `boom`.

**When**
- spies: `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)` inside `pytest.raises(RuntimeError)`.

**Then**
1. raises: `exc.value is boom`.
2. mock called: `rb.call_count >= 1`.

### POS-SY-14 — a non-HTTP error in the line phase is rolled back and re-raised as the same object
- **Rules:** `sync_items` SY1; TC3; branch map 1300
- **Kind:** error
- **Expect:** pass
- **Author:** claude (patches the manager, as SY-10)

**Given**
1. O = po "1". poline(O, 1).
2. `boom = RuntimeError("line boom")`; `mgr.sync_items` patched to raise `boom`.
3. X (after the commit point).

**When**
- spies: `SY(SYNC([], [], [NI(I1b, "5")]), user_id=U2.id)` inside `pytest.raises(RuntimeError)`.

**Then**
1. raises: `exc.value is boom`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. committed: x_gone.
6. committed: `purchase_order_items` of O: 1.

## `PurchaseOrderService.get_items` / `list_events` / `list_approvers`

### POS-PT-01 — get_items: lines by line number; a read
- **Rules:** `get_items` PT1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. L2 = poline(O, 2), but `item_id I1b.id`. L1 = poline(O, 1).
3. X (after the commit point).

**When**
- spies: `result = svc.get_items(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[x.id for x in result] == [L1.id, L2.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### POS-PT-02 — get_items: a W2 order → 404
- **Rules:** `get_items` PT1 [BUG-2886]
- **Kind:** bug
- **Expect:** xfail BUG-2886
- **Fails today on:** Then 1 (returns `[]`)

**Given**
1. O9 = po "9", but of W2. poline(O9, 1).

**When**
- `svc.get_items(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.

### POS-PT-03 — list_events: newest first; a read
- **Rules:** `list_events` PT1, PT2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".
2. E1 = ev(O, T0, "note"). E2 = ev(O, T2, "note"). E3 = ev(O, T1, "note").
3. X (after the commit point).

**When**
- spies: `result = svc.list_events(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e[0].id for e in result] == [E2.id, E3.id, E1.id]` (each row is `(PurchaseOrderEvent, Profile | None)`, PT2).
2. returns: `all(e[1] is not None and e[1].id == U1.id for e in result)`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.

### POS-PT-04 — list_approvers: the order's approvers; a read
- **Rules:** `list_approvers` PT1, PT2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". P1 = poappr(O, U1). P3 = poappr(O, U3).
2. O2 = po "2". poappr(O2, U2).
3. X (after the commit point).

**When**
- spies: `result = svc.list_approvers(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(a[0].user_id for a in result) == sorted([U1.id, U3.id])` (each row is `(PurchaseOrderApprover, Profile | None, str | None)`, PT2).
2. returns: `all(len(a) == 3 for a in result)`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.

## `PurchaseOrderService.approval_summary_for`

### POS-AS-01 — the manager's summary tuple; a read
- **Rules:** `approval_summary_for` AS1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poappr(O, U1), but approved. poappr(O, U3).
3. X (after the commit point).

**When**
- spies: `result = svc.approval_summary_for(db, po_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`, `result[0] == 1`.
2. mock called: `cm.call_count == 0`.
3. session: `X in db`.

### POS-AS-02 — a W2 order → 404
- **Rules:** `approval_summary_for` AS1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po "9", but of W2.

**When**
- `svc.approval_summary_for(db, po_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.

## `PurchaseOrderService.add_approver`

### POS-AA-01 — the approver is added and told; committed
- **Rules:** `add_approver` AA1, AA2, AA3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `result = svc.add_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.user_id == U3.id`, `result.purchase_order_id == O.id`.
3. committed: approvers of O: exactly 1, `user_id == U3.id`.
4. committed: `U3.id in recips()`.

### POS-AA-02 — a ready order: the other pending approvers are told again
- **Rules:** `add_approver` AA2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. poappr(O, U1).

**When**
- `svc.add_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. committed: `U3.id in recips()`.
2. committed: some row of `notes()` has `recipient_user_id == U1.id`, `notification_type == "approval_pending"`.

### POS-AA-03 — already an approver → 409, rolled back
- **Rules:** `add_approver` AA1, AA3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". poappr(O, U3).
2. X (after the commit point).

**When**
- spies: `svc.add_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. nothing written: nothing written.

### POS-AA-04 — an inactive member → 400
- **Rules:** `add_approver` AA1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `svc.add_approver(db, po_id=O.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written: nothing written.

### POS-AA-05 — a failing commit saves neither the approver nor the notification
- **Rules:** `add_approver` AA3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".

**When**
- `svc.add_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written: nothing written.

## `PurchaseOrderService.remove_approver`

### POS-RA-01 — removed, committed, returns None, nobody told
- **Rules:** `remove_approver` RA1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1". P3 = poappr(O, U3). `pid = P3.id`.

**When**
- `result = svc.remove_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `purchase_order_approvers` with `id == pid`: 0.
3. committed: `notes() == []`.

### POS-RA-02 — not an approver → 404, rolled back
- **Rules:** `remove_approver` RA1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. X (after the commit point).

**When**
- spies: `svc.remove_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Approver not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### POS-RA-03 — a failing commit keeps the approver
- **Rules:** `remove_approver` RA1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". P3 = poappr(O, U3).

**When**
- `svc.remove_approver(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `purchase_order_approvers` with `id == P3.id`: 1.

## `PurchaseOrderService.set_approval`

### POS-SA-01 — an approval is committed; nobody told, no invoice step
- **Rules:** `set_approval` SA1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready. poline(O, 1).
2. P3 = poappr(O, U3).

**When**
- `result = svc.set_approval(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, approved=True)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == P3.id`, `result.approved is True`.
3. committed: P3 has `approved is True`.
4. committed: `notes() == []`.
5. committed: `account_invoices` with `order_id == O.id`: 0.

### POS-SA-02 — not an approver → 403, rolled back
- **Rules:** `set_approval` SA1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. X (after the commit point).

**When**
- spies: `svc.set_approval(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, approved=True)` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. committed: x_gone.

### POS-SA-03 — approving before the sections are confirmed → 400
- **Rules:** `set_approval` SA1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1". P3 = poappr(O, U3).

**When**
- `svc.set_approval(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm supplier, order details, and items before approving"`.
4. unchanged: unchanged(P3).

### POS-SA-04 — a failing commit keeps the approver unapproved
- **Rules:** `set_approval` SA1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready. P3 = poappr(O, U3).

**When**
- `svc.set_approval(db, po_id=O.id, user_id=U3.id, workspace_id=W1.id, approved=True)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P3: `approved is False`.

## `PurchaseOrderService.void_purchase_order`

**VBASE** = O = po "1", but ready; L = poline(O, 1); V = inv(O), linked to O (`vid = V.id`); P3 = poappr(O, U3), but approved. **VOID(note)** = `svc.void_purchase_order(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note=note)`.

### POS-V-01 — the order is voided, its draft deleted, approvals cleared; committed; nobody told
- **Rules:** `void_purchase_order` V4, V5, V6, V7, V9; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. VBASE.

**When**
- `result = VOID("Duplicate")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`, `result.voided is True`.
3. committed: O has `void_note == "Duplicate"`, `voided_at == NOW`, `voided_by == U2.id`, `invoice_id is None`.
4. committed: O has `current_status_id == SD1.id`, `supplier_confirmed is True`, `items_confirmed is True`.
5. committed: `account_invoices` with `id == vid`: 0.
6. committed: P3 has `approved is False`.
7. committed: `notes() == []`.
8. unchanged: unchanged(L).

### POS-V-02 — the unlink event records the id the order was linked to
- **Rules:** `void_purchase_order` V5a [BUG-3185]
- **Kind:** bug
- **Expect:** xfail BUG-3185
- **Fails today on:** Then 1 (VBASE's invoice is a draft: it is deleted first, so the event records `"invoice_id": None`)

**Given**
1. VBASE.

**When**
- `VOID("Duplicate")`.

**Then**
1. committed: the `invoice_voided` event of O has `metadata_json["invoice_id"] == vid`.

### POS-V-03 — a W0 order → 404
- **Rules:** `void_purchase_order` V1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = po "0", but of W0.
2. VBASE.

**When**
- `svc.void_purchase_order(db, po_id=O0.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. unchanged: unchanged(O0).

### POS-V-04 — a W2 order → 404
- **Rules:** `void_purchase_order` V1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. VBASE.
2. O9 = po "9", but of W2.

**When**
- `svc.void_purchase_order(db, po_id=O9.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. unchanged: unchanged(O9).

### POS-V-05 — already voided → 400, rolled back
- **Rules:** `void_purchase_order` V2, V9; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but voided.
2. X (after the commit point).

**When**
- spies: `VOID("Again")` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Purchase order is already voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. unchanged: unchanged(O).

### POS-V-06 — the order row is locked before the first state check
- **Rules:** `void_purchase_order` V1 [BUG-3162]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3162
- **Fails today on:** Then 2 (plain read)

**Given**
1. VBASE. `oid = O.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_purchase_order(db, po_id=oid, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate")`.

**Then**
1. returns: `result.voided is True`.
2. statement: exact lock OF(`purchase_orders`).
3. statement: `purchase_orders` before `purchase_order_items`.
4. statement: `purchase_orders` before `account_invoices`.

### POS-V-07 — a completed order cannot be voided
- **Rules:** `void_purchase_order` V2a [BUG-2734]
- **Kind:** bug
- **Expect:** xfail BUG-2734
- **Fails today on:** Then 1 (voided)

**Given**
1. O = po "1", but ready, complete. L = poline(O, 1).
2. V = inv(O), but finalized, linked to O.

**When**
- `VOID("Duplicate")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a completed purchase order — record a return instead"`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).

### POS-V-08 — an order with goods received cannot be voided
- **Rules:** `void_purchase_order` V2b, V10 [BUG-2734]
- **Kind:** bug
- **Expect:** xfail BUG-2734
- **Fails today on:** Then 1 (the stock is reversed and the order voided)

**Given**
1. O = po "1", but ready, proj, `current_status_id SR1.id`. L = poline(O, 1), but `quantity_received Decimal("3.00")`.
2. V = inv(O), but finalized, linked to O.

**When**
- `VOID("Duplicate")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a purchase order with goods received — record a return instead"`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).

### POS-V-09 — a finalized invoice is voided with the order's reason; its payments voided
- **Rules:** `void_purchase_order` V2b (other side), V4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`. L = poline(O, 1).
2. V = inv(O), but finalized, `paid_amount Decimal("100.00")`, `payment_status "partial"`, linked to O.
3. P = cash(V, "100.00").

**When**
- `result = VOID("Duplicate")`.

**Then**
1. returns: `result.voided is True`.
2. committed: V has `invoice_status == "voided"`, `void_note == "Purchase order voided: Duplicate"`.
3. committed: P has `is_voided is True`.
4. committed: O has `invoice_id is None`.

### POS-V-10 — a draft with payment history is not deleted; the void is rolled back
- **Rules:** `void_purchase_order` V4 [BUG-639] (pass-through), V9; TC3
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1–3 (BUG-639 is open: the draft with payment rows is not refused with the PAYHIST 400; executor notes rev 2)

**Given**
1. VBASE, but V `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. cash(V, "100.00").
3. X (after the commit point).

**When**
- `VOID("Duplicate")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == PAYHIST`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. committed: O has `voided is False`, `invoice_id == vid`.

### POS-V-11 — a linked voided invoice is left as it is; still unlinked
- **Rules:** `void_purchase_order` V4, V5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VBASE, but V voided-inv.

**When**
- `VOID("Duplicate")`.

**Then**
1. unchanged: unchanged(V).
2. committed: O has `invoice_id is None`, `voided is True`.
3. committed: `"invoice_voided" in types(O)`.

### POS-V-12 — a W2 invoice linked is not touched; the order is unlinked and approvals cleared
- **Rules:** `void_purchase_order` V4, V5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = po "1", but ready. L = poline(O, 1).
2. V9 = inv(O), but of W2, linked to O.
3. P3 = poappr(O, U3), but approved.

**When**
- `VOID("Duplicate")`.

**Then**
1. unchanged: unchanged(V9).
2. committed: O has `invoice_id is None`.
3. committed: P3 has `approved is False`.

### POS-V-13 — without an invoice, approvals are still cleared
- **Rules:** `void_purchase_order` V8 [BUG-3170]
- **Kind:** bug
- **Expect:** xfail BUG-3170
- **Fails today on:** Then 2 (approvals kept)

**Given**
1. O = po "1", but ready. L = poline(O, 1).
2. P3 = poappr(O, U3), but approved.

**When**
- `result = VOID("Duplicate")`.

**Then**
1. returns: `result.voided is True`.
2. committed: P3 has `approved is False`.

### POS-V-14 — without an invoice: voided, no unlink event, `updated_by` untouched
- **Rules:** `void_purchase_order` V3, V5, V6, V11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1". L = poline(O, 1).

**When**
- `VOID("Duplicate")`.

**Then**
1. committed: O has `voided is True`, `updated_by is None`.
2. committed: `"invoice_voided" not in types(O)`.
3. committed: `"inventory_reversed" not in types(O)`.
4. committed: `types(O)[-1] == "po_voided"`.

### POS-V-15 — a failing commit leaves the order and its invoice as they were
- **Rules:** `void_purchase_order` V9; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. VBASE.

**When**
- `VOID("Duplicate")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `voided is False`, `invoice_id == vid`.
4. count: `account_invoices` with `id == vid`: 1.

### POS-V-16 — schema: a whitespace-only void note is refused
- **Rules:** `void_purchase_order` V12 [BUG-3168]
- **Kind:** bug
- **Expect:** xfail BUG-3168
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `PurchaseOrderVoidRequest(void_note="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-V-17 — schema: an empty void note is refused
- **Rules:** `void_purchase_order` V12 [BUG-3168]
- **Kind:** bug
- **Expect:** xfail BUG-3168
- **Fails today on:** Then 1 (accepted)

**Given**
1. Nothing.

**When**
- build `PurchaseOrderVoidRequest(void_note="")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### POS-V-18 — schema: the void note is trimmed
- **Rules:** `void_purchase_order` V12 [BUG-3168]
- **Kind:** bug
- **Expect:** xfail BUG-3168
- **Fails today on:** Then 1 (kept as typed)

**Given**
1. Nothing.

**When**
- `result = PurchaseOrderVoidRequest(void_note=" Duplicate ")` (target `schema`).

**Then**
1. returns: `result.void_note == "Duplicate"`.

### POS-V-19 — schema: a plain void note is accepted
- **Rules:** `void_purchase_order` V12 (holds today and after BUG-3168)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = PurchaseOrderVoidRequest(void_note="Duplicate")` (target `schema`).

**Then**
1. returns: `result.void_note == "Duplicate"`.

### POS-V-20 — a receipt and its full correction are both reversed on void
- **Rules:** `void_purchase_order` V3, V2b [BUG-2734] (other side: nothing left received)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`; L = poline(O, 1); V = inv(O), but locked-inv, linked to O (`vid = V.id`).
2. Given steps (code): `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=RCV((L, "3")))`, then `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=COR((L, "-3"), note="Miscount"))`.
3. At the commit point: `n0` = count of `inventory_ledger` rows of W1; re-read L has `quantity_received == Decimal("0.00")`.

**When**
- `VOID("Duplicate")`.

**Then**
1. committed: O has `voided is True`.
2. committed: `inventory_ledger` rows of W1: `n0 + 2`.
3. committed: the 2 newest of them (by `id`) both have `transaction_type == "inventory_adjustment"` and `sorted(abs(r.quantity) for r in those) == [3, 3]`.
4. committed: `STOCK(F1, I1).qty == 0`.
5. committed: the `inventory_reversed` event of O has `description == "2 inventory posting(s) reversed for void"`, `metadata_json["reversed_count"] == 2`.
6. committed: V `invoice_status == "locked"`.

### POS-V-21 — the void's events: approvals reset, invoice unlinked with its change list, then voided
- **Rules:** `void_purchase_order` V5, V6 (the parts that hold today and after BUG-3185); `PurchaseOrderManager.reset_approvals` R2 (pass-through)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. VBASE.

**When**
- `VOID("Duplicate")`.

**Then**
1. committed: `types(O).count("approvals_reset") == 1`, `types(O).count("invoice_voided") == 1`, `types(O)[-1] == "po_voided"`.
2. committed: `types(O).index("approvals_reset") < types(O).index("invoice_voided") < types(O).index("po_voided")` (V5: reset, then unlink; V6 last).
3. committed: the `approvals_reset` event has `description == "Cleared approvals — PO voided (1 approval(s) cleared)"`.
4. committed: the `invoice_voided` event has `description == f"Invoice unlinked — PO #{O.po_number} voided"`.
5. committed: its `set(metadata_json) == {"invoice_id", "changes"}` and `metadata_json["changes"] == [{"field": "void_note", "label": "Void reason", "from_value": None, "to_value": "Duplicate"}]` (the `invoice_id` value is BUG-3185's, V-02).
6. committed: `EV(O)[-1].description == f"Purchase order #{O.po_number} voided. Reason: Duplicate"`, `EV(O)[-1].metadata_json == {"void_note": "Duplicate"}`.
7. committed: `"inventory_reversed" not in types(O)`.

### POS-V-22 — exactly one reversed posting is still logged
- **Rules:** `void_purchase_order` V3 (`reversed_count` 1 boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready, `current_status_id SR1.id`; L = poline(O, 1); V = inv(O), but locked-inv, linked to O.
2. Given step (code): `svc.create_receive_event(db, po_id=O.id, workspace_id=W1.id, user_id=U1.id, data=RCV((L, "3")))`.
3. Then `L.quantity_received = Decimal("0.00")`, `db.flush()` (constructed state: one receive posting left and nothing received on the line, so V2b lets the void through; no return to net against).
4. At the commit point: `n0` = count of `inventory_ledger` rows of W1; `STOCK(F1, I1).qty == 3`.

**When**
- `VOID("Duplicate")`.

**Then**
1. committed: O has `voided is True`.
2. committed: `inventory_ledger` rows of W1: `n0 + 1`; the newest (by `id`) has `transaction_type == "inventory_adjustment"`, `abs(quantity) == 3`.
3. committed: `STOCK(F1, I1).qty == 0`.
4. committed: `types(O).count("inventory_reversed") == 1`; that event has `description == "1 inventory posting(s) reversed for void"`, `metadata_json["reversed_count"] == 1`.

## `PurchaseOrderService.create_invoice_for_purchase_order`

**CI()** = `svc.create_invoice_for_purchase_order(db, po_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

### POS-CI-01 — a ready order without an invoice gets a draft; committed; nobody told
- **Rules:** `create_invoice_for_purchase_order` CI3, CI4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready. L = poline(O, 1).
2. poappr(O, U3).

**When**
- `result = CI()`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`, `result.invoice_id is not None`.
3. committed: invoice `result.invoice_id` has `invoice_status == "draft"`, `invoice_type == "payable"`, `order_id == O.id`.
4. committed: `notes() == []`.

### POS-CI-02 — a W2 order → 404, rolled back
- **Rules:** `create_invoice_for_purchase_order` CI1, CI5; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = po "9", but of W2, ready. poline(O9, 1).
2. X (after the commit point).

**When**
- `svc.create_invoice_for_purchase_order(db, po_id=O9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.
6. nothing written: nothing written.

### POS-CI-03 — the order row is locked before the first state check
- **Rules:** `create_invoice_for_purchase_order` CI1 [BUG-3162]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3162
- **Fails today on:** Then 2 (plain read)

**Given**
1. O = po "1", but ready. poline(O, 1). `oid = O.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.create_invoice_for_purchase_order(db, po_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. statement: exact lock OF(`purchase_orders`).
3. statement: `purchase_orders` before `account_invoices`.

### POS-CI-04 — a voided order → 400, nothing written
- **Rules:** `create_invoice_for_purchase_order` CI2 [BUG-3169]
- **Kind:** bug
- **Expect:** xfail BUG-3169
- **Fails today on:** Then 1 (a fresh draft is made)

**Given**
1. O = po "1", but ready, voided. poline(O, 1).

**When**
- `CI()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Purchase order is voided"`.
4. nothing written: nothing written.

### POS-CI-05 — sections not all confirmed → 422, rolled back
- **Rules:** `create_invoice_for_purchase_order` CI3, CI5; SD3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but `supplier_confirmed True`, `details_confirmed True`. poline(O, 1).
2. X (after the commit point).

**When**
- spies: `CI()` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == FORCE422`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. nothing written: nothing written.

### POS-CI-06 — a financially locked order is returned unchanged
- **Rules:** `create_invoice_for_purchase_order` CI3; SD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but ready. poline(O, 1).
2. V = inv(O), but finalized, linked to O.

**When**
- `result = CI()`.

**Then**
1. returns: `result.invoice_id == V.id`.
2. unchanged: unchanged(V).
3. count: `account_invoices` with `order_id == O.id`: 1.

### POS-CI-07 — a linked draft is re-synced
- **Rules:** `create_invoice_for_purchase_order` CI3; SD11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready. poline(O, 1).
2. V = inv(O), but `description "Old"`, linked to O.

**When**
- `result = CI()`.

**Then**
1. returns: `result.invoice_id == V.id`.
2. committed: V has `description == f"Purchase order {O.po_number}"`.
3. committed: `"items_synced" in itypes(V)`.

### POS-CI-08 — confirmed sections but no supplier → 422
- **Rules:** `create_invoice_for_purchase_order` CI4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready, `account_id None`. poline(O, 1).

**When**
- `CI()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Assign a supplier before a draft invoice can be created"`.
4. nothing written: nothing written.

### POS-CI-09 — an IntegrityError after which the order has an invoice: returned, no error
- **Rules:** `create_invoice_for_purchase_order` CI6
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready. poline(O, 1).
2. V = inv(O), linked to O.
3. `svc._sync_draft_invoice_for_po` patched to raise `IERR("duplicate key", "23505", "account_invoices", None)`.

**When**
- spies: `result = CI()`.

**Then**
1. returns: `result.id == O.id`, `result.invoice_id == V.id`.
2. mock called: `rb.call_count >= 1`.
3. mock called: `cm.call_count == 0`.

### POS-CI-10 — an IntegrityError with still no invoice is translated (invoice phase)
- **Rules:** `create_invoice_for_purchase_order` CI6
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = po "1", but ready. poline(O, 1).
2. `svc._sync_draft_invoice_for_po` patched to raise `IERR("duplicate key", "23505", "purchase_order_items", None)`.

**When**
- `CI()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "A draft invoice for this order already exists"`.

### POS-CI-11 — a failing commit saves no draft
- **Rules:** `create_invoice_for_purchase_order` CI5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1", but ready. poline(O, 1).

**When**
- `CI()`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written: nothing written.

## `PurchaseOrderService.receive_replacements` (new — BUG-2810, settlement BUG-3176)

Every RX card is strict xfail: the method and `PurchaseOrderReturnReplacementCreate` do not exist today, so each fails on **Then 1 (the call raises AttributeError / ImportError: the method or its request schema does not exist)** unless it says otherwise. Givens start from **REPL** (Conventions). **PO event** = the `return_replacement_received` event of O (from EV(O)). **Return event** = a row of REVENTS(R).

### POS-RX-01 — replacements are received: return line and PO line quantities; committed
- **Rules:** `receive_replacements` RX5, RX7, RX10; TC1, TC2
- **Kind:** happy
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R.id`, `result.status == "completed"`.
3. committed: RL has `quantity_replaced == Decimal("4.00")`, `quantity_returned == Decimal("4.00")`.
4. committed: L has `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("4.00")`.

### POS-RX-02 — one stock-in ledger row per return line, linked to the return
- **Rules:** `receive_replacements` RX6, RX8g [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `len(LEDGER(RL.id)) == 1`.
2. committed: `LEDGER(RL.id)[0]` has `workspace_id == W1.id`, `item_id == I1.id`, `quantity == 4`, `unit_cost == Decimal("500.00")`, `total_cost == Decimal("2000.00")`.
3. committed: `LEDGER(RL.id)[0].notes == f"Replacement for return {R.return_number} — PO {O.po_number} line 1"`.
4. committed: `LEDGER(RL.id)[0].transaction_type == "purchase_order"`.

### POS-RX-03 — two return lines: two ledger rows
- **Rules:** `receive_replacements` RX6
- **Kind:** side-effect
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `invoice_amount Decimal("3000.00")`.
2. L2 = poline(O, 2), but `item_id I1b.id`, `quantity_received Decimal("8.00")`, `quantity_returned Decimal("2.00")`.
3. RL2 = rline(R, L2, "2").

**When**
- `RX(RQ((RL, "4"), (RL2, "2")))`.

**Then**
1. committed: `len(LEDGER(RL.id)) == 1`, `len(LEDGER(RL2.id)) == 1`.
2. committed: `LEDGER(RL2.id)[0]` has `item_id == I1b.id`, `quantity == 2`, `total_cost == Decimal("1000.00")`.
3. committed: L2 has `quantity_received == Decimal("10.00")`.

### POS-RX-04 — the ledger cost is the PO line's price, not the return line's
- **Rules:** `receive_replacements` RX6 (RR6)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but RL `unit_price Decimal("450.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `LEDGER(RL.id)[0]` has `unit_cost == Decimal("500.00")`, `total_cost == Decimal("2000.00")`.

### POS-RX-05 — an unpriced PO line: the return line's price is the cost
- **Rules:** `receive_replacements` RX6 (RR6)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but L `unit_price None`, `line_subtotal None`; RL `unit_price Decimal("450.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `LEDGER(RL.id)[0]` has `unit_cost == Decimal("450.00")`, `total_cost == Decimal("1800.00")`.

### POS-RX-06 — stock rises at the order's factory at the original cost
- **Rules:** `receive_replacements` RX6
- **Kind:** side-effect
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL (no stock rows at F1).

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `STOCK(F1, I1).qty == 4`.
2. committed: `STOCK(F1, I1).avg_price == Decimal("500.00")`.

### POS-RX-07 — a project order moves no stock; quantities still move
- **Rules:** `receive_replacements` RX5, RX6
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but O proj.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `LEDGER(RL.id) == []`.
2. committed: RL has `quantity_replaced == Decimal("4.00")`.
3. committed: L has `quantity_received == Decimal("10.00")`.

### POS-RX-08 — the return stays completed and is stamped `updated_by`
- **Rules:** `receive_replacements` RX7 [BUG-3174]
- **Kind:** bug
- **Expect:** xfail BUG-3174
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `result.status == "completed"`.
2. committed: R has `updated_by == U2.id`, `completed_at == T0`.

### POS-RX-09 — the order, its approvals and its invoice are untouched; no new invoice
- **Rules:** `receive_replacements` RX8
- **Kind:** side-effect
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.
2. P3 = poappr(O, U3), but approved.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: O has `current_status_id == SC1.id`, `actual_delivery_date == date(2026, 9, 10)`, `invoice_id == V.id`.
2. committed: P3 has `approved is True`.
3. unchanged: unchanged(V).
4. committed: `account_invoices` of W1: exactly 2 (V and CN).

### POS-RX-10 — the PO activity entry; nobody told
- **Rules:** `receive_replacements` RX9
- **Kind:** side-effect
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: exactly 1 PO event, `description == f"Replacements received for return {R.return_number} — 4 unit(s)"`, `performed_by == U2.id`.
2. committed: its `metadata_json["return_id"] == R.id`, `metadata_json["total_quantity"] == "4"`.
3. committed: `notes() == []`.

### POS-RX-11 — a missing order → 404
- **Rules:** `receive_replacements` RX1
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.

**When**
- `svc.receive_replacements(db, po_id=MISSING, return_id=R.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. nothing written: nothing written.

### POS-RX-12 — a W0 order id → 404; W0's return untouched
- **Rules:** `receive_replacements` RX1
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL of W0.
2. REPL.

**When**
- `svc.receive_replacements(db, po_id=O0.id, return_id=R0.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL0, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O0.id)`.
4. unchanged: unchanged(RL0).
5. unchanged: unchanged(CN0).

### POS-RX-13 — a W2 order id → 404; W2's return untouched
- **Rules:** `receive_replacements` RX1
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. REPL of W2.

**When**
- `svc.receive_replacements(db, po_id=O9.id, return_id=R9.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL9, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O9.id)`.
4. unchanged: unchanged(RL9).
5. unchanged: unchanged(CN9).

### POS-RX-14 — a return of another W1 order → 404
- **Rules:** `receive_replacements` RX1
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. O2 = po "2", but ready, complete. L2 = poline(O2, 1), but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`. R2 = ret "2" of O2, but replace, completed. RL2 = rline(R2, L2, "4").

**When**
- `svc.receive_replacements(db, po_id=O.id, return_id=R2.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL2, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R2.id)`.
4. unchanged: unchanged(RL2).

### POS-RX-15 — a W0 return id under the W1 order → 404
- **Rules:** `receive_replacements` RX1
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL of W0.
2. REPL.

**When**
- `svc.receive_replacements(db, po_id=O.id, return_id=R0.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL0, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R0.id)`.
4. unchanged: unchanged(RL0).

### POS-RX-16 — a W2 return id under the W1 order → 404
- **Rules:** `receive_replacements` RX1
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. REPL of W2.

**When**
- `svc.receive_replacements(db, po_id=O.id, return_id=R9.id, workspace_id=W1.id, user_id=U2.id, data=RQ((RL9, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == RNF(R9.id)`.
4. unchanged: unchanged(RL9).

### POS-RX-17 — the return row is locked
- **Rules:** `receive_replacements` RX1; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL. `oid, rid, rlid = O.id, R.id, RL.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id, data=PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": rlid, "quantity": Decimal("4")}]))`.

**Then**
1. returns: `result.id == rid`.
2. statement: exact lock(`purchase_order_returns`).
3. statement: `purchase_order_returns` before `purchase_order_return_items`.

### POS-RX-18 — a refund return → 400
- **Rules:** `receive_replacements` RX2 (RR1)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL, but R `return_type "refund"`, L `quantity_refunded Decimal("4.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a replace return can receive replacements"`.
4. nothing written: nothing written.

### POS-RX-19 — a pending return → 400
- **Rules:** `receive_replacements` RX2 (RR2)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL, but R `status "pending"`, `completed_at None`, `completed_by None`; L `quantity_received Decimal("10.00")`, `quantity_returned Decimal("0.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Complete the return before receiving replacements"`.
4. nothing written: nothing written.

### POS-RX-20 — a W2 return line in the request → 400 not part of the return
- **Rules:** `receive_replacements` RX2 (RR4); HR-16
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. REPL of W2.

**When**
- `RX(RQ((RL9, "1")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTPART(RL9.id, R)`.
4. unchanged: unchanged(RL9).
5. nothing written: nothing written.

### POS-RX-21 — a line of another W1 return → 400 not part of the return
- **Rules:** `receive_replacements` RX2 (RR4)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. R2 = ret "2" of O, but replace, completed. RL2 = rline(R2, L, "1").

**When**
- `RX(RQ((RL2, "1")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == NOTPART(RL2.id, R)`.
3. nothing written: nothing written.

### POS-RX-22 — more than went back → 400
- **Rules:** `receive_replacements` RX2 (RR5)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == RTOO("5", 1, "4.00")`.
4. nothing written: nothing written.

### POS-RX-23 — the limit counts what was already replaced
- **Rules:** `receive_replacements` RX2 (RR5)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Author:** claude
- **Fails today on:** Then 1 (the Given fails: no `quantity_replaced` column; or the call raises AttributeError)

**Given**
1. REPL, but RL `quantity_replaced Decimal("3.00")`, L `quantity_received Decimal("9.00")`.

**When**
- `RX(RQ((RL, "2")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == RTOO("2", 1, "1.00")`.

### POS-RX-24 — a fractional quantity on a storage order → 400, rolled back
- **Rules:** `receive_replacements` RX3, RX10; TC3
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL.
2. X (after the commit point).

**When**
- spies: `RX(RQ((RL, "1.5")))` (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Line 1 has a fractional quantity; inventory requires whole units"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.
7. nothing written: nothing written.

### POS-RX-25 — a fractional quantity on a project order is accepted
- **Rules:** `receive_replacements` RX3
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but O proj.

**When**
- `RX(RQ((RL, "1.5")))`.

**Then**
1. committed: RL has `quantity_replaced == Decimal("1.50")`.
2. committed: L has `quantity_received == Decimal("7.50")`.

### POS-RX-26 — a line already re-received the normal way cannot be filled again
- **Rules:** `receive_replacements` RX4 [BUG-3181]
- **Kind:** bug
- **Expect:** xfail BUG-3181
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. REPL, but L `quantity_received Decimal("10.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot receive 4 replacement(s) for line 1 — the line is already fully received"` (`{q}` as sent).
4. unchanged: unchanged(L).
5. nothing written: nothing written.

### POS-RX-27 — the PO line limit: exactly up to ordered − refunded passes
- **Rules:** `receive_replacements` RX4 [BUG-3181] (other side)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but L `quantity_received Decimal("7.00")`; RL `quantity_returned Decimal("4.00")` (as REPL).

**When**
- `RX(RQ((RL, "3")))`.

**Then**
1. committed: L has `quantity_received == Decimal("10.00")`.
2. committed: RL has `quantity_replaced == Decimal("3.00")`.

### POS-RX-28 — a failing commit saves nothing: no quantities, stock, entry or events
- **Rules:** `receive_replacements` RX10; TC4
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not RuntimeError)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `quantity_received == Decimal("6.00")`.
4. nothing written: nothing written.

### POS-RX-29 — a stock-in failure after the writes rolls everything back
- **Rules:** `receive_replacements` RX6, RX10; TC3
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. `F1.is_deleted = True`, `F1.is_active = False`, flush.
2. REPL.
3. X (after the commit point).

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. raises: `HTTPException`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. committed: x_gone.
4. committed: RL has `quantity_replaced == Decimal("0.00")`.
5. nothing written: nothing written.

### POS-RX-30 — the settlement entry: method, amount, UTC date, actor, workspace; no warning
- **Rules:** `receive_replacements` RX8a, RX8d [BUG-3176] (OQ-63)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`; call it P.
2. committed: P has `payment_amount == Decimal("2000.00")`, `payment_method == "settled_by_replacement"`.
3. committed: P has `payment_date == TODAY_UTC`, `created_by == U2.id`, `is_voided is False`.
4. committed: P has `workspace_id == W1.id`, `invoice_id == CN.id`.
5. committed: `len(PAYS(CN)) == 1`.
6. returns: `WARN(result) == []`.

### POS-RX-31 — two lines settle in one entry: the sum of their values
- **Rules:** `receive_replacements` RX8a [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `invoice_amount Decimal("3000.00")`.
2. L2 = poline(O, 2), but `item_id I1b.id`, `quantity_received Decimal("8.00")`, `quantity_returned Decimal("2.00")`.
3. RL2 = rline(R, L2, "2").

**When**
- `RX(RQ((RL, "4"), (RL2, "2")))`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`.
2. committed: `SETTLE(CN)[0].payment_amount == Decimal("3000.00")`.

### POS-RX-32 — the amount uses the return line's price
- **Rules:** `receive_replacements` RX8a [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but RL `unit_price Decimal("450.00")`.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `SETTLE(CN)[0].payment_amount == Decimal("1800.00")`.

### POS-RX-33 — each line is rounded half up before summing
- **Rules:** `receive_replacements` RX8a [BUG-3176]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but O proj, L `unit_price Decimal("1.25")`, `line_subtotal Decimal("12.50")`, `quantity_received Decimal("9.90")`, `quantity_returned Decimal("0.10")`; RL `quantity_returned Decimal("0.10")`, `unit_price Decimal("1.25")`; CN `invoice_amount Decimal("1.00")`.
2. L2 = poline(O, 2), but `item_id I1b.id`, `unit_price Decimal("1.25")`, `line_subtotal Decimal("12.50")`, `quantity_received Decimal("9.90")`, `quantity_returned Decimal("0.10")`.
3. RL2 = rline(R, L2, "0.10"), but `unit_price Decimal("1.25")`.

**When**
- `RX(RQ((RL, "0.10"), (RL2, "0.10")))`.

**Then**
1. committed: `SETTLE(CN)[0].payment_amount == Decimal("0.26")`.

### POS-RX-34 — a full settlement pays the credit note and the return
- **Rules:** `receive_replacements` RX8a, RX8c [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: CN has `paid_amount == Decimal("2000.00")`, `payment_status == "paid"`, `invoice_status == "confirmed"`.
2. committed: R has `paid is True`.

### POS-RX-35 — the entry links to its receipt
- **Rules:** `receive_replacements` RX8b [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `SETTLE(CN)[0].payment_reference == R.return_number`.
2. committed: `SETTLE(CN)[0].notes == f"Settled by replacement — 4 unit(s) received for return {R.return_number}"`.
3. committed: `SETTLE(CN)[0].source_type == "purchase_order_event"`.
4. committed: `SETTLE(CN)[0].source_id == [e.id for e in EV(O) if e.event_type == "return_replacement_received"][0]`.

### POS-RX-36 — a partial receipt settles only its share
- **Rules:** `receive_replacements` RX8c [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "3")))`.

**Then**
1. committed: `[p.payment_amount for p in SETTLE(CN)] == [Decimal("1500.00")]`.
2. committed: CN has `paid_amount == Decimal("1500.00")`, `payment_status == "partial"`.
3. committed: R has `paid is False`.
4. committed: RL has `quantity_replaced == Decimal("3.00")`.

### POS-RX-37 — the rest of a partial receipt settles the remainder
- **Rules:** `receive_replacements` RX8c [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Author:** claude
- **Fails today on:** Then 1 (the Given fails: no `quantity_replaced` column; or the call raises AttributeError)

**Given**
1. REPL, but RL `quantity_replaced Decimal("3.00")`, L `quantity_received Decimal("9.00")`, CN `paid_amount Decimal("1500.00")`, `payment_status "partial"`.
2. spay(CN, "1500.00", R).

**When**
- `RX(RQ((RL, "1")))`.

**Then**
1. committed: `[p.payment_amount for p in SETTLE(CN)] == [Decimal("1500.00"), Decimal("500.00")]`.
2. committed: CN has `paid_amount == Decimal("2000.00")`, `payment_status == "paid"`.
3. committed: R has `paid is True`.

### POS-RX-38 — cash already collected: the entry is capped at what is outstanding
- **Rules:** `receive_replacements` RX8d [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `paid_amount Decimal("500.00")`, `payment_status "partial"`.
2. cash(CN, "500.00").

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `[p.payment_amount for p in SETTLE(CN)] == [Decimal("1500.00")]`.
2. committed: CN has `paid_amount == Decimal("2000.00")`, `payment_status == "paid"`.
3. committed: `len(PAYS(CN)) == 2`.

### POS-RX-39 — the cap one cent below the value
- **Rules:** `receive_replacements` RX8d [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `paid_amount Decimal("0.01")`, `payment_status "partial"`.
2. cash(CN, "0.01").

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `[p.payment_amount for p in SETTLE(CN)] == [Decimal("1999.99")]`.

### POS-RX-40 — already fully refunded in cash: no entry, a warning, the receipt goes ahead
- **Rules:** `receive_replacements` RX8d [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `paid_amount Decimal("2000.00")`, `payment_status "paid"`; R `paid True`.
2. cash(CN, "2000.00").

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [NOSETTLE]`.
2. committed: `SETTLE(CN) == []`.
3. committed: `len(PAYS(CN)) == 1`.
4. committed: CN has `paid_amount == Decimal("2000.00")`.
5. committed: RL has `quantity_replaced == Decimal("4.00")`.
6. committed: `len(LEDGER(RL.id)) == 1`.

### POS-RX-41 — a voided credit note: no entry, a warning, the receipt goes ahead
- **Rules:** `receive_replacements` RX8d [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN voided-inv.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [VOIDW]`.
2. committed: `PAYS(CN) == []`.
3. unchanged: unchanged(CN).
4. committed: RL has `quantity_replaced == Decimal("4.00")`.
5. committed: `len(LEDGER(RL.id)) == 1`.

### POS-RX-42 — with no entry the PO activity entry records 0.00 and a null payment id
- **Rules:** `receive_replacements` RX8d, RX8f [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN voided-inv.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: the PO event's `metadata_json["settled_amount"] == "0.00"`.
2. committed: the PO event's `metadata_json["payment_id"] is None`.

### POS-RX-43 — the PO activity entry carries the settled amount and the payment id
- **Rules:** `receive_replacements` RX8f, RX9 [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: the PO event's `metadata_json["settled_amount"] == "2000.00"`.
2. committed: the PO event's `metadata_json["payment_id"] == SETTLE(CN)[0].id`.

### POS-RX-44 — the return gets its own `replacement_received` event
- **Rules:** `receive_replacements` RX8e [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (`PurchaseOrderReturnEvent` / the method does not exist: ImportError or AttributeError)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "3")))`.

**Then**
1. committed: `len(REVENTS(R)) == 1`; call it E.
2. committed: E has `event_type == "replacement_received"`, `performed_by == U2.id`, `workspace_id == W1.id`.
3. committed: `E.description == "Replacements received — 3 unit(s), 1500.00 settled"`.
4. committed: `E.metadata_json == {"return_id": R.id, "total_quantity": "3", "settled_amount": "1500.00", "payment_id": SETTLE(CN)[0].id}`.

### POS-RX-45 — a settlement entry cannot be deleted
- **Rules:** `receive_replacements` RX8h [BUG-3176] (fix in `invoice_payment_manager`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (no error: the entry is deleted)

**Given**
1. REPL, but CN `paid_amount Decimal("2000.00")`, `payment_status "paid"`.
2. P = spay(CN, "2000.00", R).

**When**
- `db.begin_nested()`, then `ipm.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NODEL`.
4. count: `invoice_payments` with `id == P.id`: 1 (after the savepoint is rolled back).

### POS-RX-46 — a settlement entry cannot be edited
- **Rules:** `receive_replacements` RX8h [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (no error: the note is changed)

**Given**
1. REPL, but CN `paid_amount Decimal("2000.00")`, `payment_status "paid"`.
2. P = spay(CN, "2000.00", R), but `notes "Settled"`.

**When**
- `db.begin_nested()`, then `ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(notes="edited"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NODEL`.
4. re-read P: `notes == "Settled"`.

### POS-RX-47 — the entry made by a receipt refuses deletion
- **Rules:** `receive_replacements` RX8a, RX8h [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Author:** claude
- **Fails today on:** Given 2 (ImportError: `PurchaseOrderReturnReplacementCreate` cannot be imported; `RQ(...)` is built as an argument before `svc.receive_replacements` is looked up, so no Then line runs)

**Given**
1. REPL.
2. `RX(RQ((RL, "4")))` (a Given step); P = `SETTLE(CN)[0]`.

**When**
- `db.begin_nested()`, then `ipm.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == NODEL`.
3. count: `invoice_payments` with `id == P.id`: 1.

### POS-RX-48 — a settlement entry can be voided: owed again, return unpaid, stock untouched
- **Rules:** `receive_replacements` RX8i, RX8l (hold today and after BUG-3176)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. REPL, but CN `paid_amount Decimal("2000.00")`, `payment_status "paid"`; R `paid True`.
2. P = spay(CN, "2000.00", R).

**When**
- `ipm.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong count")`.

**Then**
1. re-read P: `is_voided is True`, `voided_by == U2.id`, `void_note == "Wrong count"`, `voided_at is not None`.
2. re-read CN: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
3. re-read R: `paid is False`, `status == "completed"`, `return_type == "replace"`, `completed_by == U1.id`.
4. count: `inventory_ledger` rows of W1: 0.

### POS-RX-49 — voiding the entry made by a receipt keeps the replacement stock
- **Rules:** `receive_replacements` RX8i, RX8l [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Author:** claude
- **Fails today on:** Given 2 (ImportError: `PurchaseOrderReturnReplacementCreate` cannot be imported; `RQ(...)` is built as an argument before `svc.receive_replacements` is looked up, so no Then line runs)

**Given**
1. REPL.
2. `RX(RQ((RL, "4")))` (a Given step); P = `SETTLE(CN)[0]`.

**When**
- `ipm.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong count")`.

**Then**
1. re-read CN: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
2. re-read: `STOCK(F1, I1).qty == 4`.
3. re-read: `len(LEDGER(RL.id)) == 1`.
4. re-read RL: `quantity_replaced == Decimal("4.00")`.
5. re-read R: `paid is False`.

### POS-RX-50 — workspace isolation: W0 and W2 returns, credit notes and stock untouched
- **Rules:** `receive_replacements` RX8a [BUG-3176]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL of W0.
2. REPL.
3. REPL of W2.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `len(SETTLE(CN)) == 1`, `SETTLE(CN)[0].workspace_id == W1.id`.
2. committed: `PAYS(CN0) == []`.
3. committed: `PAYS(CN9) == []`.
4. unchanged: unchanged(CN0).
5. unchanged: unchanged(CN9).
6. unchanged: unchanged(RL0).
7. unchanged: unchanged(RL9).
8. committed: `LEDGER(RL0.id) == []`, `LEDGER(RL9.id) == []`.

### POS-RX-51 — a W2 credit note linked to the W1 return: left alone, warning, receipt goes ahead
- **Rules:** `receive_replacements` RX8k [BUG-3176]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN built of W2 (`workspace_id W2.id`, `account_id A9.id`; invalid data).

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [NOTFOUND]`.
2. committed: `PAYS(CN) == []`.
3. unchanged: unchanged(CN).
4. committed: RL has `quantity_replaced == Decimal("4.00")`; `len(LEDGER(RL.id)) == 1`.
5. committed: the PO event's `metadata_json["settled_amount"] == "0.00"`, `metadata_json["payment_id"] is None`.

### POS-RX-52 — the credit note is locked before the entry is written
- **Rules:** `receive_replacements` RX8a [BUG-3176]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL. `oid, rid, rlid = O.id, R.id, RL.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id, data=PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": rlid, "quantity": Decimal("4")}]))`.

**Then**
1. statement: exact lock(`account_invoices`).
2. statement: `lock("account_invoices")` is recorded before the first `INSERT INTO invoice_payments`.

### POS-RX-53 — a draft credit note: no entry, the voided warning, the receipt goes ahead
- **Rules:** `receive_replacements` RX8d [BUG-3176] (any status other than `confirmed`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `invoice_status "draft"`.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [VOIDW]`.
2. committed: `PAYS(CN) == []`.
3. unchanged: unchanged(CN).
4. committed: RL has `quantity_replaced == Decimal("4.00")`; `len(LEDGER(RL.id)) == 1`.

### POS-RX-54 — a return with no credit note: no entry, warning, the receipt goes ahead
- **Rules:** `receive_replacements` RX8k [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, then `R.invoice_id = None`, flush (CN stays, unlinked).

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [NOTFOUND]`.
2. committed: `PAYS(CN) == []`.
3. unchanged: unchanged(CN).
4. committed: RL has `quantity_replaced == Decimal("4.00")`; L has `quantity_received == Decimal("10.00")`.
5. committed: the PO event's `metadata_json["settled_amount"] == "0.00"`, `metadata_json["payment_id"] is None`.
6. committed: `len(REVENTS(R)) == 1`, its `description == "Replacements received — 4 unit(s), 0.00 settled"`.

### POS-RX-55 — a W0 credit note linked to the W1 return: left alone, warning
- **Rules:** `receive_replacements` RX8k [BUG-3176]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN built of W0 (`workspace_id W0.id`, `account_id A0.id`; invalid data).

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. returns: `WARN(result) == [NOTFOUND]`.
2. committed: `PAYS(CN) == []`.
3. unchanged: unchanged(CN).
4. committed: RL has `quantity_replaced == Decimal("4.00")`.

### POS-RX-56 — the payments API cannot create a settlement by hand
- **Rules:** `receive_replacements` RX8m [BUG-3176] (fix in `invoice_payment_manager`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (no error: the payment is recorded)

**Given**
1. REPL.

**When**
- `db.begin_nested()`, then `ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=CN.id, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, 20), payment_method="settled_by_replacement"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == MANUAL`.
4. count: after the savepoint is rolled back, `PAYS(CN) == []`.
5. re-read CN: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### POS-RX-57 — the payments API cannot turn a cash payment into a settlement
- **Rules:** `receive_replacements` RX8m [BUG-3176] (fix in `invoice_payment_manager`)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (no error: the method is changed)

**Given**
1. REPL, but CN `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = cash(CN, "100.00").

**When**
- `db.begin_nested()`, then `ipm.update_payment(db, payment_id=P.id, payment_data=InvoicePaymentUpdate(payment_method="settled_by_replacement"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == MANUAL`.
4. re-read P (after the savepoint is rolled back): `payment_method == "cash"`.

### POS-RX-58 — a cash payment on a credit note is still recorded by hand
- **Rules:** `receive_replacements` RX8m (other side: only the reserved method is refused; holds today and after BUG-3176)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. REPL.

**When**
- `result = ipm.create_payment(db, payment_data=InvoicePaymentCreate(invoice_id=CN.id, payment_amount=Decimal("100.00"), payment_date=date(2026, 9, 20), payment_method="cash"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.payment_method == "cash"`, `result.payment_amount == Decimal("100.00")`.
2. re-read CN: `paid_amount == Decimal("100.00")`, `payment_status == "partial"`.

### POS-RX-59 — the settlement goes through the payment path: audit row and invoice event
- **Rules:** `receive_replacements` RX8j [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `len(AUDIT(CN)) == 1`.
2. committed: `itypes(CN).count("payment_recorded") == 1`.
3. committed: that `payment_recorded` event's `metadata_json["payment_method"] == "settled_by_replacement"`, `metadata_json["payment_id"] == SETTLE(CN)[0].id`.

### POS-RX-60 — a credit note with payments locked is still settled
- **Rules:** `receive_replacements` RX8j [BUG-3176] (the `allow_payments` refusal is skipped)
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN `allow_payments False`.

**When**
- `result = RX(RQ((RL, "4")))`.

**Then**
1. committed: `[p.payment_amount for p in SETTLE(CN)] == [Decimal("2000.00")]`.
2. committed: CN has `paid_amount == Decimal("2000.00")`, `payment_status == "paid"`, `allow_payments is False`.
3. returns: `WARN(result) == []`.

### POS-RX-61 — a foreign credit note is not locked
- **Rules:** `receive_replacements` RX8k [BUG-3176]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL, but CN built of W2 (`workspace_id W2.id`, `account_id A9.id`; invalid data). `oid, rid, rlid = O.id, R.id, RL.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id, data=PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": rlid, "quantity": Decimal("4")}]))`.

**Then**
1. returns: `WARN(result) == [NOTFOUND]`.
2. statement: `lock("account_invoices") is None`.
3. statement: no recorded `INSERT INTO invoice_payments`.

### POS-RX-62 — with no entry the return event records 0.00 settled
- **Rules:** `receive_replacements` RX8e [BUG-3176]
- **Kind:** bug
- **Expect:** xfail BUG-3176
- **Fails today on:** Then 1 (`PurchaseOrderReturnEvent` / the method does not exist: ImportError or AttributeError)

**Given**
1. REPL, but CN voided-inv.

**When**
- `RX(RQ((RL, "4")))`.

**Then**
1. committed: `len(REVENTS(R)) == 1`; call it E.
2. committed: `E.description == "Replacements received — 4 unit(s), 0.00 settled"`.
3. committed: `E.metadata_json == {"return_id": R.id, "total_quantity": "4", "settled_amount": "0.00", "payment_id": None}`.

### POS-RX-63 — lock order: the order first, then the return, then the credit note
- **Rules:** `receive_replacements` RX1a, RX1, RX8a [BUG-2810 / BUG-3176]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the call raises AttributeError: no `receive_replacements`)

**Given**
1. REPL. `oid, rid, rlid = O.id, R.id, RL.id`.
2. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.receive_replacements(db, po_id=oid, return_id=rid, workspace_id=W1.id, user_id=U2.id, data=PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": rlid, "quantity": Decimal("4")}]))`.

**Then**
1. returns: `result.id == rid`.
2. statement: exact lock OF(`purchase_orders`).
3. statement: `purchase_orders` locked before `purchase_order_returns`.
4. statement: `purchase_order_returns` locked before `account_invoices`.
5. statement: `purchase_orders` before `purchase_order_items`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| C1, U1, MC1, X1, AI1, UI1, RI1, SY1, PT1, AS1, AA1, RA1, SA1 details (manager rules and errors; BUG-2872 locks, BUG-2874, BUG-2879 … 2888, BUG-1017, BUG-1192, BUG-1200, BUG-1202, BUG-2631 DAO fix) | `purchase_order_manager.cases.md` | every manager rule; here one pass-through per path |
| SR3 / RX2 checks (`validate_and_build_items`, `validate_replacement_receipt` RR1–RR8 incl. RR3 order, RR6, RR7, RR8), BUG-2750 … 2753, 2785, 2787, 2792; `PurchaseOrderReturnReplacementCreate` 422s | `purchase_order_return_manager.cases.md` | each check and schema refusal; here one pass-through per check (RX-18 … RX-23) |
| SD5, SD11, AR1, AR4, V4, VR3, CI3 invoice-manager details (`create_invoice`, `update_invoice`, `delete_invoice` BUG-639, `confirm_invoice`, `void_invoice` R3a–R3c, BUG-2788, `set_receiving_started`, `sync_items_from_list`) | `account_invoice_manager.cases.md` | amounts, events, refusals |
| RX8h / RX8m refusal implementations, RX8j internal flag on `create_payment` (not reachable from the API), RX8l `_sync_linked_order` mechanics; RX8i blank / missing void reason refused (BUG-3168 precedent); a **cash** payment stays deletable and editable after the fix | `invoice_payment_manager.cases.md` | the refusals sit there; RX-45 … RX-49, RX-56 … RX-58 only reach them from the settlement side |
| RE8, CR4, RX6, V3 stock mechanics (ledger columns, averages, insufficient stock, destination not found / soft-deleted R12 / R12a, BUG-680, 682, 684, 800, 801, 802) | `po_receive_inventory.cases.md`, `po_return_inventory.cases.md`, `po_storage_inventory.cases.md`, `po_machine_inventory.cases.md` | every posting rule; the replacement posting module once it exists |
| U2, AA2, SD10, EN2 notification texts and recipient rules | `approval_notification_service.cases.md` | previews, gap text, recipient sets |
| PG1, HS1–HS3 filters, ordering, search escaping, figures (BUG-2639 … 2641 DAO side, OQ-35 … 38) | `tests/unit/dao/purchase_order.cases.md` | what each filter and figure means |
| BUG-3162, BUG-2754, RX1 / RX1a / RX8a lock races (two sessions) | integration tests | the loser sees the new state and gets the normal error; unit cards check only the `FOR UPDATE` SQL |
| X2 the endpoint passes the current user (BUG-1195) | `DELETE /purchase-orders/{id}/` | audit row names the caller |
| V12, VR7 422 at the endpoint (BUG-3168) | `POST /purchase-orders/{id}/void/`, `…/returns/{id}/void/` | 422 body; nothing written |
| RX new route `POST /purchase-orders/{po_id}/returns/{return_id}/receive-replacements/` (BUG-2810); RX8m `POST /invoice-payments/` and its update route | endpoint tests | request → service call, 422 on bad body, response carries `warnings`; the payments routes answer 400 MANUAL for the reserved method |
| UI1 422 at the endpoint (BUG-2887) | `PUT /purchase-orders/items/{item_id}/` | 422, nothing written |
| BUG-3183 return numbers unique across workspaces | return DAO / model cases | a second workspace's first return of the year gets its own `PR-YYYY-001` |
| Permission checks (any member can void, delete, receive, return, settle) | `docs/future/permissions.md` | not a rule today |

## Spec gaps
None. Revision 1's gaps 1–12 are closed by the spec's Gap log (G1–G12, fill-gaps 2026-11-22) and applied in Revision 2:
1. Schemas and the receive-event line FK → Imports, NEWPO / SYNC, revi; BR-01, BR-04, BR-05.
2. Lock clause per table → exact lock / exact lock OF; RE-05, V-06, CI-03, RX-63 (OF), CR-09, VR-06, RX-17, RX-52 (plain).
3. Return event log → REVENTS; RX-44, RX-54, RX-62.
4. Link columns → RX-35.
5. `warnings` field → WARN; RX-30, RX-40, RX-41, RX-53 … RX-55, RX-60, RX-61, SR-14, CR-16, VR-14.
6. `settled_amount "0.00"` when no entry → RX-42, RX-51, RX-54, RX-62.
7. Numbers in texts → SR-02 (as sent), CR-02, CR-03 (stored, 2 places), RX-23, RX-26 (as sent).
8. Ledger `transaction_type` → RE-01, RX-02.
9. Foreign / missing credit note (RX8k) → RX-51, RX-54, RX-55, RX-61.
10. V3 remaining case → V-20.
11. Other order kinds → AO-17 … AO-20 (AO-18 … AO-20 keep `Author: claude` for columns the service does not read).
12. Void re-syncs `paid` (RX8l) → RX-48, RX-49.

Revision 3: the executor's discrepancies are closed by Gap log G13–G19 (AR-05, C-09, IC-04, DD-04, V-02, PT-03, PT-04, G-01, AO-11, AO-12, `inventory`) and applied above; no new gap.

Revision 4 (verifier findings) — one new gap, closed in Revision 4a by Gap log G20 (new rule CR3a [BUG-3186] → CR-18, CR-19 xfail; CR-20 pass; CR-17 re-checked):
13. ~~**CR3 on a line whose received quantity is already 0** (verifier survivor #40, line 984). CR3 says `quantity_received −= q` with no floor, and IE8 says there is no check constraint, so completing a return of 4 on a line corrected to 0 after the return started would store −4.00. The spec does not say whether that is intended, refused (400) or floored at 0. No card pins it; the describer should state the outcome, and the designer then adds a CR card.~~ **Closed (G20):** refused with 400, nothing written; exactly 0 allowed.

Revision 4 notes (not gaps): V-22 builds its one-posting state by rewriting `quantity_received` to 0 after a real receipt (the spec's only reachable examples reverse two postings or none). AR-08 assumes the invoice manager accepts a 0.00-priced line on a confirmed credit note (AR2 gives price 0 when none; no refusal is stated).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_integrity_context` | IC1 | IC-01, IC-02, IC-03, IC-05 |
| | IC1a [BUG-3184] | IC-04 |
| `_handle_item_integrity_error` | IE1 | IE-01 … IE-05, IE-24, IE-25, IE-26 |
| | IE2 | IE-06 … IE-09, IE-27 |
| | IE3 | IE-10 … IE-14, IE-28 … IE-31 |
| | IE4 | IE-16 … IE-18, IE-32 |
| | IE5 | IE-19, IE-20 |
| | IE6 | IE-05, IE-15 |
| | IE7 | IE-21, IE-22 |
| | IE8 | IE-23 (constructed errors throughout) |
| | IE9, Returns (chained) | IE-01, IE-20, IE-23 |
| `_build_invoice_items_from_po` | BI1 | BI-01, BI-02, BI-03 |
| | BI2 | BI-01, BI-04 |
| `_delete_linked_draft_invoice_for_po` | DD1 | DD-01, DD-02, DD-03 |
| | DD2 | DD-04, DD-06 (held today) |
| | DD2a [BUG-3185] | DD-04 |
| | DD2 [BUG-639] (pass-through) | DD-05 |
| `_sync_draft_invoice_for_po` | SD1 | SD-01 |
| | SD2 | SD-02, SD-03 |
| | SD3 | SD-04 |
| | SD4 | SD-05 |
| | SD5, SD6 | SD-06, SD-09 |
| | SD7 [BUG-3167] | SD-07 |
| | SD8 | SD-08, SD-09, SD-10 |
| | SD9 | SD-11, SD-12 |
| | SD10 | SD-13, SD-14, SD-13 (reset reason, `entity_type`) |
| | SD11 | SD-13, SD-14, SD-15, SD-16, SD-17 |
| | Returns (flush only) | SD-18 |
| `_emit_po_invoice_draft_notification` | EN1 | EN-01 |
| | EN2 | EN-02, U-06 |
| Return-in-progress flag | RF1 [BUG-2789] | RF-01 … RF-05 |
| | RF2 | RF-06, CR-14 |
| | RF3 | RF-07 |
| `create_purchase_order` | C1; TC1, TC2 | C-01 |
| | C2 [BUG-2631] | C-03, C-04, C-05, C-12 |
| | C3 | C-02 |
| | C4; TC3 | C-06, C-07 |
| | C5 [BUG-3175] | C-08 (pass part), C-09 (marker row, same-session checks) |
| | TC4, TC5 | C-10, C-11 |
| `update_purchase_order` | U1 | U-01, U-02, U-03, U-04, U-09 |
| | U2 | U-06, U-07, U-12 |
| | U3 | U-05, U-07, U-08 |
| | U4; TC3, TC4 | U-02, U-09, U-10, U-11 |
| | U5 | RF-05 |
| `get_purchase_order` | G1 | G-01 (summaries via the response schema) … G-05 |
| | G2 (Q8) | G-01, G-06, G-07 |
| `mark_order_complete` | MC1 | MC-01 … MC-04 |
| `list_purchase_orders` | LP1 | LP-01 … LP-04 |
| `_hub_filter_kwargs` | HF1 | HF-01 … HF-06, PG-06 |
| `_prepare_listed_orders` | PL1 | PL-01 |
| | PL2 [BUG-3178] | PL-02, PL-03 (pass part) |
| | PL3 | PL-03, PL-04, PL-05 |
| `list_purchase_orders_page` | PG1 | PG-05, PG-06, PG-07 |
| | PG2 | PG-01 … PG-04, PG-08 (defaults) |
| `get_purchase_order_hub_stats` | HS1 | HS-01, HS-03, HS-04 |
| | HS2 | HS-02 |
| | HS3; TC6 | HS-03, HS-05 |
| `_attach_invoice_payment_status` | AP1 | AP-01, AP-02, AP-03, G-05 |
| | AP2 [BUG-3164] | AP-04, AP-05 |
| `_attach_item_summaries` | IS1 | IS-01, IS-02 |
| | IS2 [BUG-2641] | IS-03 |
| `create_receive_event` | Inputs (schema) | RE-39 … RE-42 |
| | RE1 | RE-02, RE-03, RE-04 |
| | RE1 [BUG-3162] | RE-05 |
| | RE2 | RE-06, RE-07 |
| | RE3 | RE-08 … RE-11 |
| | RE4 | RE-12, RE-13 |
| | RE5 | RE-14 … RE-17 |
| | RE5 [BUG-3171] | RE-18, RE-19 (pass part) |
| | RE6 | RE-01, RE-19 |
| | RE7 [BUG-3180] | RE-21 (pass part), RE-22 |
| | RE8 (and Ledgers) | RE-01, RE-20, RE-23, RE-24, RE-25 |
| | RE9 | RE-26 … RE-29 |
| | RE9 [BUG-3180] | RE-30, RE-31 |
| | RE10 [BUG-3177] | RE-32, RE-33 (pass part) |
| | RE11 | RE-34, RE-35, RE-36, RE-43, RE-44, RE-45 |
| | RE12; TC1, TC3, TC4 | RE-01, RE-20, RE-37, RE-38; refusals before the `try`: RE-02 |
| `list_receive_events` | LR1 | LR-01 |
| | LR2; TC6 | LR-02, LR-05, LR-06 |
| | LR2 [BUG-3172] | LR-03 (non-strict), LR-04 |
| `_build_receive_event_response` | BR1 | BR-01, BR-02, BR-03 |
| | BR1 [BUG-3172] | BR-04, BR-05 (non-strict) |
| `_attach_return_invoice_for_po` | AR1 | AR-01 |
| | AR1 [BUG-3167] | AR-04 |
| | AR2 | AR-02, AR-03, AR-08 |
| | AR3 (BUG-3163 withdrawn) | AR-05, AR-06 |
| | AR4 | AR-01, AR-07 |
| `start_return` | SR1 | SR-03, SR-04, SR-05, SR-10 |
| | SR2 | SR-06, SR-15 |
| | SR3 | SR-01, SR-07 |
| | SR4 [BUG-801] | SR-08, SR-09 |
| | SR5 [BUG-2789] | SR-10 (pass part), SR-11 |
| | SR6 | SR-01, SR-02 |
| | SR7; TC1, TC3, TC4 | SR-01, SR-06, SR-12, SR-13 |
| `complete_return` | CR1 | CR-04, CR-05, CR-06 |
| | CR1 [BUG-2754] | CR-09 |
| | CR2 | CR-07, CR-08 |
| | CR3 | CR-01, CR-03, CR-15, CR-17, CR-20 |
| | CR3a [BUG-3186] | CR-18, CR-19 (xfail); CR-17, CR-20 (pass) |
| | CR4 | CR-11, CR-12 |
| | CR5 | CR-01 |
| | CR6 | CR-02, CR-03, CR-11, CR-14 |
| | CR7 [BUG-3174] | CR-10 |
| | CR8; TC3, TC4 | CR-07, CR-12, CR-13, CR-18, CR-19 |
| `void_return` | VR1 | VR-03, VR-04 |
| | VR1 [BUG-2754] | VR-06 |
| | VR2 | VR-05 |
| | VR3 | VR-01, VR-02, VR-09 |
| | VR3 [BUG-3182] | VR-08 |
| | VR4 | VR-01, VR-09 |
| | VR5 [BUG-3174] | VR-07 |
| | VR6; TC3, TC4 | VR-01, VR-05, VR-10 |
| | VR7 [BUG-3168] | VR-11, VR-12, VR-13 (pass part) |
| `list_returns` / `get_return` | LRT1 | LRT-01, LRT-05 |
| | LRT2; TC6 | LRT-02, LRT-03, LRT-04 |
| `list_active_orders_for_context` | AO1 | AO-01, AO-02, AO-03 |
| | AO2 | AO-04 … AO-07, AO-15 |
| | AO3 | AO-08 … AO-12 (WF1's sequence varied), AO-14, AO-20, AO-23, AO-24, AO-25 |
| | AO4 | AO-08 |
| | AO5 | AO-17, AO-23, AO-24 |
| | AO6 [BUG-3173] | AO-08 (pass part), AO-13 |
| | AO7 | AO-18 |
| | AO8 | AO-20, AO-22 |
| | AO9 [BUG-3166] | AO-19 |
| | AO10; TC6 | AO-16, AO-17, AO-21 |
| `delete_purchase_order` | X1; TC1, TC3, TC4 | X-02, X-03, X-04, X-07, X-08 |
| | X1 [BUG-2888] | X-01, X-05 |
| | X2 [BUG-1195] | X-06 |
| `add_item` | AI1 | AI-01, AI-04, AI-06 |
| | AI2 | AI-01, AI-02, AI-03 |
| | AI3; TC3, TC4 | AI-04, AI-05, AI-07 |
| `update_item` | UI1 | UI-01, UI-03 |
| | UI1 [BUG-2887] | UI-04 |
| | UI2 | UI-01, UI-02 |
| | UI3; TC3, TC4 | UI-03, UI-05, UI-06 |
| `remove_item` | RI1; TC1, TC3, TC4 | RI-01 … RI-05 |
| `sync_items` | SY1 | SY-01, SY-08, SY-09, SY-10 |
| | SY2 [BUG-3179] | SY-02, SY-03, SY-12 |
| | SY3 | SY-01, SY-04 (pass part), SY-06, SY-07, SY-11, SY-13 |
| | SY4 [BUG-3165] | SY-01 (pass part), SY-05 |
| `get_items` / `list_events` / `list_approvers` | PT1; TC6 | PT-01, PT-03, PT-04 |
| | PT2 | PT-03, PT-04 |
| | PT1 [BUG-2886] | PT-02 |
| `approval_summary_for` | AS1; TC6 | AS-01, AS-02 |
| `add_approver` | AA1 | AA-01, AA-03, AA-04 |
| | AA2 | AA-01, AA-02 |
| | AA3; TC3, TC4 | AA-01, AA-03, AA-05 |
| `remove_approver` | RA1 | RA-01, RA-02, RA-03 |
| `set_approval` | SA1 | SA-01 … SA-04 |
| `void_purchase_order` | V1 | V-03, V-04 |
| | V1 [BUG-3162] | V-06 |
| | V2 | V-05 |
| | V2a [BUG-2734] | V-07 |
| | V2b [BUG-2734] | V-08, V-09 (pass part), V-20 (other side) |
| | V3 | V-02, V-14, V-20, V-22 |
| | V4 | V-01, V-09, V-11, V-12 |
| | V4 [BUG-639] (pass-through) | V-10 |
| | V5 | V-01, V-02, V-11, V-12, V-14, V-21 |
| | V5a [BUG-3185] | V-02 |
| | V6 | V-01, V-02, V-21 |
| | V7 | V-01 |
| | V8 [BUG-3170] | V-13 |
| | V9; TC3, TC4 | V-01, V-05, V-10, V-15 |
| | V10 | V-08 |
| | V11 | V-14 |
| | V12 [BUG-3168] | V-16, V-17, V-18, V-19 (pass part) |
| `create_invoice_for_purchase_order` | CI1 | CI-02 |
| | CI1 [BUG-3162] | CI-03 |
| | CI2 [BUG-3169] | CI-04 |
| | CI3 | CI-01, CI-05, CI-06, CI-07 |
| | CI4 | CI-01, CI-08 |
| | CI5; TC3, TC4 | CI-02, CI-05, CI-11 |
| | CI6 | CI-09, CI-10 |
| `receive_replacements` [BUG-2810] | RX1 | RX-11 … RX-17, RX-63 |
| | RX1a | RX-63 |
| | RX2 | RX-18 … RX-23 |
| | RX3 | RX-24, RX-25 |
| | RX4 [BUG-3181] | RX-26, RX-27 |
| | RX5 | RX-01, RX-07, RX-25 |
| | RX6 | RX-02 … RX-07, RX-29 |
| | RX7 [BUG-3174] | RX-01, RX-08 |
| | RX8 | RX-09 |
| | RX8a [BUG-3176] | RX-30 … RX-34, RX-50, RX-52, RX-63 |
| | RX8b [BUG-3176] | RX-35 |
| | RX8c [BUG-3176] | RX-34, RX-36, RX-37 |
| | RX8d [BUG-3176] | RX-30, RX-38 … RX-42, RX-53, SR-14, CR-16, VR-14 |
| | RX8e [BUG-3176] | RX-44, RX-54, RX-62 |
| | RX8f [BUG-3176] | RX-42, RX-43, RX-51, RX-54 |
| | RX8g [BUG-3176] | RX-02, RX-03 |
| | RX8h [BUG-3176] | RX-45, RX-46, RX-47 |
| | RX8i [BUG-3176] | RX-48 (pass), RX-49 |
| | RX8j [BUG-3176] | RX-59, RX-60 |
| | RX8k [BUG-3176] | RX-51, RX-54, RX-55, RX-61 |
| | RX8l | RX-48 (pass), RX-49 |
| | RX8m [BUG-3176] | RX-56, RX-57, RX-58 (pass, other side) |
| | RX9 | RX-10, RX-43 |
| | RX10; TC1, TC2, TC3, TC4 | RX-01, RX-24, RX-28, RX-29 |
| Bug tags | BUG-3162 … 3182 (minus 3163, withdrawn, and 3176 counted above), BUG-3184, 3185, BUG-639, 2734, 2754, 2789, 2810, 801, 1195, 2641, 2886, 2887, 2888 | see rows above; BUG-3183 deferred (return DAO) |
