# Test cases — `app/managers/invoice_payment_manager.py`

> **Spec:** `tests/unit/managers/invoice_payment_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec Gap log G1–G10 closed all ten earlier gaps. New: `update_payment` R2a [BUG-611] (message becomes "Void and re-create…") → UP-04/UP-06 now assert only the stable prefix, new xfail UP-23 asserts the new text; R3a precedence → new xfail UP-24; `void_payment` R9a precedence → new xfail VP-24; `utcnow` patch target now `app.utils.time.datetime` (G6); table names `account_invoices` / `invoice_payments` used directly (G8). No verify report exists.
> **Revision:** 3 — re-run against the current spec (Gap log G1–G10, Q1–Q7 resolutions, BUG-602/BUG-610 superseded by BUG-609): no rule, error row or BUG tag changed since revision 2; full self-check re-run over the whole file, no case added, changed or retired. No verify report exists.
> **Revision:** 4 (executor, batch mode) — U3's definition ("profile whose `name` is `NULL`") is infeasible: `profiles.name` is `NOT NULL` in the baseline schema and no migration relaxes it. Substituted a normally-named U3 ("Nusrat Jahan"); LP-01's expected name at that position changed from `None` to U3's name. No other case, rule or BUG tag changed. (Best-practice default, delegated by reviewer.)
> **Revision:** 5 — verifier feedback (`invoice_payment_manager.verify.md`, Finding 1 / surviving mutant #107, case-missing): new VP-25 pins the lower boundary of `void_payment` R7 (remaining active total 0.01 → `partial`), so `total > 0` → `total > 1` is caught. Spec Gap log unchanged (G1–G10); no other case changed. Findings 2–4 are routed to the executor (cases already specify U1 and full N0 / SY no-events checks).
> **Counts:** 118 cases · 95 expected-to-pass · 23 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `create_payment` 29 (3 bug, incl. 4 `InvoicePaymentCreate` schema cases) · `update_payment` 24 (9 bug, incl. 2 `InvoicePaymentUpdate` schema cases) · `list_payments_by_invoice` 15 (2 bug) · `delete_payment` 5 (3 bug) · `void_payment` 25 (6 bug, incl. 4 `VoidPaymentRequest` schema cases) · `_sync_linked_order` 20.
- **Notable design choices:**
  - Row locks (create R2, void R9 / BUG-601) are checked by capturing the SQL the call runs and looking for `FOR UPDATE`, as other modules do. The spec's "second connection with NOWAIT" idea cannot work: setup rows are never committed, so another connection cannot see them. The real two-session race is Deferred to integration tests (spec now agrees, G8).
  - Race simulation (void R9 only, VP-19): a statement listener writes "voided by someone else" into the payment row just before the invoice `FOR UPDATE` runs. Today no `FOR UPDATE` runs, so the hook never fires and the case fails as intended. The spec suggests doing the `UPDATE` *before* the call; that would pass today (R2's plain check catches it) and break strict xfail, so the hook stays tied to the lock statement (best-practice default, delegated by reviewer).
  - BUG-611: UP-04/UP-06 (pass) keep the 400 + "nothing changed" checks and assert only the detail prefix `Cannot change payment amount.`; the full new text is asserted only in xfail UP-23.
  - `update_payment` gains a required `user_id` (BUG-607). Passing cases call it through a signature-adaptive wrapper, so they hold today and after the fix (same approach as `po_return_inventory`).
  - `delete_payment` is tested only on its intended behavior (always 404 or 400). The old recompute/audit mechanics in the spec's `Today:` note are not tested, as the spec instructs.
  - Audit snapshot amounts are compared numerically, not by type (float today per BUG-141, a fixed-point string after that fix) — per spec G1.
  - `_sync_linked_order` is tested directly (20 cases); create and void each have one case proving they call it.
- **Needs a decision:** None. All ten earlier gaps were closed by the spec (G1–G10).

## Conventions for this module

**ID prefixes:** `IPM` = invoice_payment_manager. Methods: `CP` = `create_payment` (incl. `InvoicePaymentCreate` schema cases), `UP` = `update_payment` (incl. `InvoicePaymentUpdate` schema cases), `LP` = `list_payments_by_invoice`, `DP` = `delete_payment`, `VP` = `void_payment` (incl. `VoidPaymentRequest` schema cases), `SY` = `_sync_linked_order`. IDs below omit the `IPM-` prefix; the full ID is e.g. `IPM-CP-05`.

**Actors and rows:**
- W1, W2 = two workspaces. U1 = profile, name `"Alice Rahman"` (the acting user unless stated). U2 = profile, name `"Bilal Khan"` (stamps setup rows). U3 = profile, name `"Nusrat Jahan"` — the spec's "profile whose `name` is `NULL`" is infeasible under the current schema (`profiles.name` is `NOT NULL`, baseline migration `100_squashed_baseline.sql`); the executor substitutes a normally-named profile. LP-01's expected `created_by_name` at U3's position is therefore U3's name, not `None` (best-practice default, delegated by reviewer — see Executor note below the Coverage matrix).
- `NOID` = `999999999`, an id that exists in no table used here.
- T0 = `datetime(2026, 9, 20, 9, 0, 0)` — a past time set on setup rows that are already voided.
- **INV** = an account invoice with these defaults (a case states only what differs): workspace W1, `invoice_amount = 1000.00`, `paid_amount = 0.00`, `payment_status = "unpaid"`, `invoice_status = "confirmed"`, `allow_payments = True`, `payment_locked_reason = NULL`, `order_type = NULL`, `order_id = NULL`, `created_by = updated_by = U2`. Any other required columns get fixed, valid values chosen by the executor. **I1** = an INV in W1; **I1b** = a second INV in W1; **I2** = an INV in W2.
- **PAY(inv, amount, date, …)** = an `invoice_payments` row inserted directly (not through the manager): workspace = the invoice's workspace unless stated, `created_by = U2`, `is_voided = False`, `voided_at/voided_by/void_note = NULL`, optional text fields `NULL` unless the case lists them. A "voided PAY" also has `is_voided = True`, `voided_at = T0`, `voided_by = U2`, `void_note = "Duplicate entry"`. Setup never calls the manager; the invoice's `paid_amount`/`payment_status` are set explicitly on insert to the values the case states.
- **PO1** = a purchase order in W1; **SO1** = a sales order in W1; **PR1** = a purchase-order return in W1; **SR1** = a sales-order return in W1. Each has `paid = False` and `invoice_id = NULL` unless the case says otherwise. **POX** = another purchase order in W1 with `invoice_id = NULL`, `paid = False`. Other required columns (e.g. a return's parent order) are fixed valid values chosen by the executor.

**Default call arguments:**
- **D0** (create) = `InvoicePaymentCreate(invoice_id=I1.id, payment_amount=Decimal("250.00"), payment_date=date(2026, 9, 1), payment_method="bank_transfer", payment_reference="TRX-7781", bank_name="City Bank", transaction_id="TXN-001", notes="First instalment")`. "D0 with X" = D0 with field X overridden. `create_payment(db, payment_data=…, workspace_id=W1.id, user_id=U1.id)` — no `ip_address`/`user_agent` unless the case passes them.
- **PA** (update/void) = PAY(I1, `Decimal("250.00")`, `date(2026, 9, 1)`, `payment_method="cheque"`, `payment_reference="CHQ-881"`, `bank_name="City Bank"`, `transaction_id="TXN-001"`, `notes="First instalment"`).
- **Update wrapper `upd(payment_id, data, ws)`** (test-side): calls `update_payment(db, payment_id=…, payment_data=data, workspace_id=ws, user_id=U1.id)` if `user_id` is in the method's signature, else the same call without `user_id`. Every `update_payment` case uses it. `data` is an `InvoicePaymentUpdate` built with exactly the keys the case lists (explicit `None` values are passed, so they count as "set"); omitted keys are not passed.
- `void_payment(db, payment_id=…, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")` — no `ip_address`/`user_agent` unless the case passes them.
- `_sync_linked_order(db, invoice=<I1 re-loaded from the DB>, user_id=U1.id)` on an instance of `InvoicePaymentManager`.

**Time:** every test freezes time at **NOW = `datetime(2026, 9, 27, 12, 0, 0)`** (naive UTC) by patching `app.utils.time.datetime` (the name `utcnow()` resolves at call time), so `utcnow()` returns NOW in the manager (`voided_at`), the audit logger (`performed_at`) and the invoice-event column default (`created_at`) alike (spec Overview, G6). All these columns are `TIMESTAMP WITHOUT TIME ZONE`; compared exactly to the naive NOW. `created_at` of payment rows is a DB default: asserted "not None" only.

**Money:** compared as `Decimal` after re-reading from the DB (`Numeric(15,2)` — two decimals). Error-message amounts are compared as exact strings.

**Audit snapshot values** (`changes` JSON): money compared **numerically** — `Decimal(str(v)) == Decimal("250.00")` — so it passes for `250.0` (float, today per BUG-141) and `"250.00"` (string, after BUG-141's fix); dates compared as ISO strings (`"2026-09-01"`); everything else exactly (spec Overview, G1). All other keys of `changes` are compared exactly (no extra keys).

**Re-read:** `db.expire_all()` then query the rows again from the DB. "Audit rows" = `financial_audit_logs` rows in W1 ∪ W2 (setup inserts none). "Events of X" = `invoice_events` rows with `invoice_id = X.id`. "PO events" / "SO events" = `purchase_order_events` / `sales_order_events` rows in W1 ∪ W2.

**Nothing written (N0):** after the error, re-read shows: (a) the payment rows of every setup invoice are exactly the setup rows, with unchanged field values (incl. void fields); (b) every setup invoice has unchanged `paid_amount`, `payment_status`, `invoice_status`, `allow_payments`, `updated_by`; (c) 0 audit rows; (d) 0 invoice events; (e) every setup PO/SO/return has unchanged `paid`, and 0 PO events and 0 SO events.

**Errors:** "404 D" / "400 D" / "403 D" = raises `HTTPException` with that `status_code` and exact `detail` D. "ValidationError" = `pydantic.ValidationError`.

**SQL capture:** a SQLAlchemy `before_cursor_execute` listener on the test connection records every statement run during the action only (not the setup). "Locks the invoice" = at least one captured statement is a `SELECT` from `account_invoices` containing `FOR UPDATE` (spec Overview, G8). The payment table is `invoice_payments`.

**Race simulations:**
- VP-19 only (`void_payment` R9, BUG-601): SQL capture is on, and the listener has one extra action. The first time a captured statement selects from `account_invoices` **with** `FOR UPDATE`, before that statement runs, the listener runs on the same DBAPI connection, with its own cursor: `UPDATE invoice_payments SET is_voided = true, voided_by = U2.id, voided_at = T0, void_note = 'Voided by other user' WHERE id = PA.id`. This puts the row in the state a concurrent voider would leave it in, while this call waits for the lock. No method of the manager is patched.

---

## `InvoicePaymentManager.create_payment`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CP-01 | R6 | happy | I1 (defaults) | create D0 | returns an `InvoicePayment` P with `P.id` not None; re-read P: `invoice_id=I1.id`, `payment_amount=250.00`, `payment_date=2026-09-01`, `payment_method="bank_transfer"`, `payment_reference="TRX-7781"`, `bank_name="City Bank"`, `transaction_id="TXN-001"`, `notes="First instalment"`, `workspace_id=W1`, `created_by=U1`, `is_voided False`, `voided_at/voided_by/void_note None`, `created_at` not None; I1 has exactly 1 payment | pass |
| CP-02 | R7, R8 | side-effect | I1 (defaults) | create D0 | returns P (id not None); re-read I1: `paid_amount=250.00`, `payment_status="partial"`, `invoice_amount=1000.00`, `invoice_status="confirmed"`, `allow_payments True`, `updated_by=U2` | pass |
| CP-03 | R5, R7 | boundary | I1 with `paid_amount=400.00`, `payment_status="partial"`; PAY(I1, 400.00, 2026-08-15) | create D0 with `payment_amount=Decimal("600.00")` (= outstanding) | no error; returns P with `payment_amount == 600.00`; re-read I1: `paid_amount=1000.00`, `payment_status="paid"`; I1 has 2 payments | pass |
| CP-04 | R7 | boundary | as CP-03 | create D0 with `payment_amount=Decimal("599.99")` | returns P; re-read I1: `paid_amount=999.99`, `payment_status="partial"` | pass |
| CP-05 | R5, R14, Err: amount > outstanding | error | as CP-03 | create D0 with `payment_amount=Decimal("600.01")` | 400 `Payment amount (600.01) exceeds outstanding amount (600.00)`; N0 (I1 still 400.00 / partial, 1 payment) | pass |
| CP-06 | R5, R14 | boundary | I1 with `paid_amount=1000.00`, `payment_status="paid"`; PAY(I1, 1000.00, 2026-08-15) | create D0 with `payment_amount=Decimal("0.01")` | 400 `Payment amount (0.01) exceeds outstanding amount (0.00)`; N0 | pass |
| CP-07 | R5, R14 | boundary | I1 with `paid_amount=1000.50`, `payment_status="paid"`; PAY(I1, 1000.50, 2026-08-15) | create D0 with `payment_amount=Decimal("0.01")` | 400 `Payment amount (0.01) exceeds outstanding amount (-0.50)`; N0 | pass |
| CP-08 | R7 | side-effect | I1 with `payment_status="overdue"` (paid 0.00) | create D0 with `payment_amount=Decimal("100.00")` | returns P; re-read I1: `paid_amount=100.00`, `payment_status="partial"` | pass |
| CP-09 | R1, R14, Err: invoice missing | error | I1 (defaults) | create D0 with `invoice_id=NOID` | 404 `Invoice with ID 999999999 not found`; N0 | pass |
| CP-10 | R1, R14 | isolation | I1 in W1; I2 in W2 (defaults) | create D0 with `invoice_id=I2.id`, `workspace_id=W1.id` | 404 `Invoice with ID {I2.id} not found`; N0 (I2 still 0.00 / unpaid, no payments; I1 no payments) | pass |
| CP-11 | R1, R6, R9 | isolation | I2 in W2 (defaults) | create D0 with `invoice_id=I2.id`, `workspace_id=W2.id`, `user_id=U2.id` | returns P; re-read P: `workspace_id=W2`, `created_by=U2`; I2 `paid_amount=250.00`, `payment_status="partial"`; exactly 1 audit row, with `workspace_id=W2`, `performed_by=U2` | pass |
| CP-12 | R2 | side-effect | I1 (defaults); SQL capture on | create D0 | returns P (id not None); captured SQL locks the invoice | pass |
| CP-13 | R3, R14, Err: not confirmed | error | I1 with `invoice_status="draft"` | create D0 | 400 `Payments can only be recorded against confirmed invoices (current status: 'draft').`; N0 | pass |
| CP-14 | R3, R14 | error | I1 with `invoice_status="voided"` | create D0 | 400 `Payments can only be recorded against confirmed invoices (current status: 'voided').`; N0 | pass |
| CP-15 | R4, R14, Err: allow_payments false | error | I1 with `allow_payments=False`, `payment_locked_reason="Awaiting credit approval"` | create D0 | 403 `Awaiting credit approval`; N0 | pass |
| CP-16 | R4, R14 | boundary | I1 with `allow_payments=False`, `payment_locked_reason=NULL` | create D0 | 403 `Payments are locked for this invoice`; N0 | pass |
| CP-17 | R4, R14 | boundary | I1 with `allow_payments=False`, `payment_locked_reason=""` | create D0 | 403 `Payments are locked for this invoice`; N0 | pass |
| CP-18 | R3, R4 (order) | error | I1 with `invoice_status="draft"`, `allow_payments=False`, `payment_locked_reason="Awaiting credit approval"` | create D0 | 400 `Payments can only be recorded against confirmed invoices (current status: 'draft').` (not 403); N0 | pass |
| CP-19 | R4 | boundary | I1 with `allow_payments=True`, `payment_locked_reason="Old lock, lifted"` | create D0 | no error; returns P (id not None); re-read I1 `paid_amount=250.00` | pass |
| CP-20 | R9, R10, R10a (default), R11 | side-effect | I1 (defaults, unpaid) | create D0 | returns P; exactly 1 audit row: `entity_type="payment"`, `entity_id=P.id`, `action_type="created"`, `performed_by=U1`, `related_entity_type="invoice"`, `related_entity_id=I1.id`, `workspace_id=W1`, `performed_at=NOW`, `ip_address None`, `user_agent None`; `changes == {"after": {"payment_amount": ≈250.00, "payment_date": "2026-09-01", "payment_method": "bank_transfer"}, "invoice_status_changed": {"before": "unpaid", "after": "partial"}}`; `description == f"Payment of $250.00 recorded for invoice ID {I1.id}, status changed to partial"` | pass |
| CP-21 | R10, R11, R12 | side-effect | I1 with `paid_amount=100.00`, `payment_status="partial"`; PAY(I1, 100.00, 2026-08-15) | create D0 with `payment_amount=Decimal("50.5")` | returns P; re-read I1 `paid_amount=150.50`, `payment_status="partial"`; exactly 1 audit row: `changes` has key `"after"` and **no** key `"invoice_status_changed"`; `description == f"Payment of $50.5 recorded for invoice ID {I1.id}"` (no suffix); exactly 1 event of I1 with `metadata_json["payment_amount"] == "50.5"`, `payment_status_before == "partial"`, `payment_status_after == "partial"` | pass |
| CP-22 | R12 | side-effect | I1 (defaults) | create D0 | returns P; exactly 1 event of I1: `event_type="payment_recorded"`, `description="Payment recorded"`, `performed_by=U1`, `created_at=NOW`, `metadata_json == {"payment_id": P.id, "payment_amount": "250.00", "payment_method": "bank_transfer", "payment_status_before": "unpaid", "payment_status_after": "partial"}` | pass |
| CP-23 | R6, R10, R12 | boundary | I1 (defaults) | create D0 with `payment_method=None` | returns P; re-read P `payment_method None`; audit `changes["after"]["payment_method"] is None`; event `metadata_json["payment_method"] is None` (key present) | pass |
| CP-24 | R10a [BUG-603] | bug | I1 (defaults) | `create_payment(db, payment_data=D0, workspace_id=W1.id, user_id=U1.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)")` | returns P; exactly 1 audit row with `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 (Test)"` | xfail BUG-603 — fails today on: `TypeError` (no `ip_address` parameter) |
| CP-25 | R13 | side-effect | I1 with `invoice_amount=250.00`, `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=False` | create D0 (250.00 → fully paid) | returns P; re-read I1 `payment_status="paid"`; PO1 `paid True`; exactly 1 PO event: `event_type="payment_status_synced"`, `description="Order marked paid from linked invoice"`, `performed_by=U1`, `metadata_json == {"paid": True}` | pass |
| CP-26 | R5a [BUG-604] | bug | — (schema) | `InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("9.995"), payment_date=date(2026, 9, 1))` | raises ValidationError (manager never reached, nothing written) | xfail BUG-604 — fails today on: no error raised |
| CP-27 | R5a | boundary | — (schema) | `InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("9.99"), payment_date=date(2026, 9, 1))` | no error; `.payment_amount == Decimal("9.99")` | pass |
| CP-28 | R5a | boundary | — (schema) | `InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("1234567890123.45"), payment_date=date(2026, 9, 1))` (13 integer digits) | no error; `.payment_amount == Decimal("1234567890123.45")` | pass |
| CP-29 | R5a [BUG-604] | bug | — (schema) | `InvoicePaymentCreate(invoice_id=1, payment_amount=Decimal("12345678901234.00"), payment_date=date(2026, 9, 1))` (14 integer digits) | raises ValidationError | xfail BUG-604 — fails today on: no error raised (spec G9: no digit cap today) |

## `InvoicePaymentManager.update_payment`

Given for every case unless stated: I1 with `paid_amount=250.00`, `payment_status="partial"`; **PA** on I1.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| UP-01 | R4 | happy | default | `upd(PA.id, {payment_reference: "CHQ-999", payment_date: date(2026, 1, 1)}, W1.id)` | returns PA (`is PA`); re-read PA: `payment_reference="CHQ-999"`, `payment_date=2026-01-01`; unchanged: `payment_amount=250.00`, `payment_method="cheque"`, `bank_name="City Bank"`, `transaction_id="TXN-001"`, `notes="First instalment"`, `invoice_id=I1.id`, `created_by=U2`, `is_voided False` | pass |
| UP-02 | R6 | side-effect | I1 with `invoice_amount=250.00`, `paid_amount=250.00`, `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; PA on I1; PO1 with `invoice_id=I1.id`, `paid=False` (out of sync on purpose) | `upd(PA.id, {notes: "Revised"}, W1.id)` | returns PA; re-read PA `notes="Revised"`; I1 `paid_amount=250.00`, `payment_status="paid"`, `updated_by=U2`; PO1 `paid False`; 0 PO events | pass |
| UP-03 | R4 | boundary | default | `upd(PA.id, {bank_name: ""}, W1.id)` | returns PA; re-read PA `bank_name == ""` (not None); other fields unchanged | pass |
| UP-04 | R2, Err: amount different | error | default | `upd(PA.id, {payment_amount: Decimal("300.00"), notes: "changed"}, W1.id)` | raises `HTTPException` 400 whose `detail` starts with `Cannot change payment amount.` (full text: UP-23); N0 (PA `payment_amount=250.00`, `notes="First instalment"`) | pass |
| UP-05 | R2 | boundary | default | `upd(PA.id, {payment_amount: Decimal("250.0"), notes: "Corrected"}, W1.id)` | no error; returns PA; re-read `payment_amount=250.00`, `notes="Corrected"` | pass |
| UP-06 | R2 | boundary | default | `upd(PA.id, {payment_amount: Decimal("250.01")}, W1.id)` | raises `HTTPException` 400 whose `detail` starts with `Cannot change payment amount.`; N0 | pass |
| UP-07 | R1, Err: payment missing | error | default | `upd(NOID, {notes: "x"}, W1.id)` | 404 `Payment with ID 999999999 not found`; N0 | pass |
| UP-08 | R1 | isolation | default; I2 in W2 with `paid_amount=250.00`, `payment_status="partial"`; PB = PAY(I2, 250.00, 2026-09-01, `payment_reference="W2-REF"`) | `upd(PB.id, {payment_reference: "HACK"}, W1.id)` | 404 `Payment with ID {PB.id} not found`; N0 (PB `payment_reference="W2-REF"`) | pass |
| UP-09 | R3 [BUG-606], Err: voided | bug | I1 with `paid_amount=0.00`, `payment_status="unpaid"`; PV = voided PAY(I1, 250.00, 2026-09-01, `payment_reference="CHQ-881"`) | `upd(PV.id, {payment_reference: "CHQ-999", payment_date: date(2026, 1, 1)}, W1.id)` | 400 `Voided payments cannot be edited`; N0 (PV `payment_reference="CHQ-881"`, `payment_date=2026-09-01`, void fields as set up) | xfail BUG-606 — fails today on: no exception raised (reference becomes "CHQ-999") |
| UP-10 | R1, R3 (order) | isolation | I2 in W2; PV2 = voided PAY(I2, 250.00, 2026-09-01) | `upd(PV2.id, {notes: "x"}, W1.id)` | 404 `Payment with ID {PV2.id} not found` (not 400); N0 | pass |
| UP-11 | R3 | boundary | I1 with `invoice_status="voided"`, `paid_amount=250.00`; PA active on I1 | `upd(PA.id, {notes: "Revised"}, W1.id)` | no error; returns PA; re-read `notes="Revised"` | pass |
| UP-12 | R5 [BUG-608] | bug | default | `upd(PA.id, {payment_method: None, payment_reference: None, bank_name: None, transaction_id: None, notes: None}, W1.id)` | returns PA; re-read PA: all five fields `None`; `payment_amount=250.00`, `payment_date=2026-09-01` unchanged | xfail BUG-608 — fails today on: `bank_name` still `"City Bank"` |
| UP-13 | R5 [BUG-608] | bug | default | `upd(PA.id, {bank_name: None}, W1.id)` | returns PA; re-read: `bank_name None`; `payment_method="cheque"`, `payment_reference="CHQ-881"`, `transaction_id="TXN-001"`, `notes="First instalment"` unchanged | xfail BUG-608 — fails today on: `bank_name` still `"City Bank"` |
| UP-14 | R5, R6a (no change) | boundary | default | `upd(PA.id, {payment_date: None, payment_amount: None}, W1.id)` | no error; returns PA; re-read `payment_date=2026-09-01`, `payment_amount=250.00`, all other fields unchanged; 0 audit rows; 0 events of I1 | pass |
| UP-15 | R7, R6a (no change) | boundary | default | `upd(PA.id, {}, W1.id)` | returns PA; re-read: every field as set up; 0 audit rows; 0 events of I1 | pass |
| UP-16 | R7, R6a (no change) | boundary | I1 as default; PN = PAY(I1, 250.00, 2026-09-01) with all five optional text fields `NULL` | `upd(PN.id, {payment_method: None, payment_reference: None, bank_name: None, transaction_id: None, notes: None}, W1.id)` | returns PN; re-read: five fields still `None`, amount/date unchanged; 0 audit rows; 0 events of I1 | pass |
| UP-17 | R7, R5, R6a [BUG-608, BUG-607] | bug | I1 as default; PM = PAY(I1, 250.00, 2026-09-01, `notes="Keep?"`, other four text fields `NULL`) | `upd(PM.id, {payment_method: None, payment_reference: None, bank_name: None, transaction_id: None, notes: None}, W1.id)` | returns PM; re-read `notes None`; exactly 1 audit row with `action_type="updated"`, `entity_id=PM.id`, `changes == {"before": {"notes": "Keep?"}, "after": {"notes": None}}`; exactly 1 event of I1, `event_type="payment_updated"`, `metadata_json["changed_fields"] == ["notes"]` | xfail BUG-608 — fails today on: `notes` still `"Keep?"` |
| UP-18 | R6a [BUG-607] | bug | default | `upd(PA.id, {payment_reference: "CHQ-999", payment_date: date(2026, 1, 1)}, W1.id)` | returns PA; exactly 1 audit row: `entity_type="payment"`, `entity_id=PA.id`, `action_type="updated"`, `performed_by=U1`, `related_entity_type="invoice"`, `related_entity_id=I1.id`, `workspace_id=W1`, `performed_at=NOW`, `ip_address None`, `user_agent None`, `changes == {"before": {"payment_reference": "CHQ-881", "payment_date": "2026-09-01"}, "after": {"payment_reference": "CHQ-999", "payment_date": "2026-01-01"}}`; exactly 1 event of I1: `event_type="payment_updated"`, `description="Payment updated"`, `performed_by=U1`, `created_at=NOW`, `metadata_json["payment_id"] == PA.id`, `sorted(metadata_json["changed_fields"]) == ["payment_date", "payment_reference"]`, no other metadata keys | xfail BUG-607 — fails today on: 0 audit rows |
| UP-19 | R6a [BUG-607] (HR-9) | bug | default | `upd(PA.id, {payment_reference: "CHQ-881", payment_method: "cheque", payment_amount: Decimal("250.0"), notes: "Revised"}, W1.id)` | returns PA; re-read `notes="Revised"`; exactly 1 audit row with `changes == {"before": {"notes": "First instalment"}, "after": {"notes": "Revised"}}`; exactly 1 event of I1 with `metadata_json["changed_fields"] == ["notes"]` | xfail BUG-607 — fails today on: 0 audit rows |
| UP-20 | R6a (no change) | boundary | default | `upd(PA.id, {payment_reference: "CHQ-881", payment_method: "cheque", payment_amount: Decimal("250.00")}, W1.id)` | returns PA; re-read: all fields as set up; 0 audit rows; 0 events of I1 | pass |
| UP-21 | Inputs [BUG-604] | bug | — (schema) | `InvoicePaymentUpdate(payment_amount=Decimal("9.995"))` | raises ValidationError | xfail BUG-604 — fails today on: no error raised |
| UP-22 | Inputs | boundary | — (schema) | `InvoicePaymentUpdate(payment_amount=Decimal("9.99"))` | no error; `.payment_amount == Decimal("9.99")` | pass |
| UP-23 | R2a [BUG-611], Err: amount different | bug | default | `upd(PA.id, {payment_amount: Decimal("300.00"), notes: "changed"}, W1.id)` | 400 `Cannot change payment amount. Void and re-create payment instead.` (exact); N0 | xfail BUG-611 — fails today on: detail is `… Delete and re-create payment instead.` |
| UP-24 | R3a, R3 [BUG-606] | bug | I1 with `paid_amount=0.00`, `payment_status="unpaid"`; PV = voided PAY(I1, 250.00, 2026-09-01) | `upd(PV.id, {payment_amount: Decimal("300.00"), notes: "changed"}, W1.id)` | 400 `Voided payments cannot be edited` (not the amount error); N0 (PV `payment_amount=250.00`, `notes` NULL, void fields as set up) | xfail BUG-606 — fails today on: detail is the amount-change message |

## `InvoicePaymentManager.list_payments_by_invoice`

**Setup L4** (used where stated): I1 in W1; LA = PAY(I1, 100.00, 2026-09-01, `created_by=U1`); LB = PAY(I1, 200.00, 2026-09-05, `created_by=U2`); LC = voided PAY(I1, 300.00, 2026-09-03, `created_by=U3`); LD = PAY(I1, 400.00, 2026-09-02, `created_by=NULL`). "Result ids" = `[p.id for p, _ in result]`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LP-01 | R2, R3, R4, Returns | happy | L4 | `list_payments_by_invoice(db, I1.id, W1.id)` (defaults) | returns a list of 4 2-tuples; result ids `[LB, LC, LD, LA]`; names `["Bilal Khan", "Nusrat Jahan", None, "Alice Rahman"]` (U3 substitution, see Conventions); the LC element has `is_voided True`, `voided_by=U2`, `void_note="Duplicate entry"` | pass |
| LP-02 | R1, Err | error | L4 | `list_payments_by_invoice(db, NOID, W1.id)` | 404 `Invoice with ID 999999999 not found` | pass |
| LP-03 | R1 | isolation | I2 in W2 with PAY(I2, 50.00, 2026-09-01) | `list_payments_by_invoice(db, I2.id, W1.id)` | 404 `Invoice with ID {I2.id} not found` | pass |
| LP-04 | R2 | isolation | L4; I1b with PAY(I1b, 999.00, 2026-09-04) | `list_payments_by_invoice(db, I1.id, W1.id)` | result ids `[LB, LC, LD, LA]` (the I1b payment absent) | pass |
| LP-05 | R2 | isolation | L4; PX = PAY(I1, 500.00, 2026-09-04) inserted with `workspace_id=W2` | `list_payments_by_invoice(db, I1.id, W1.id)` | result ids `[LB, LC, LD, LA]` (PX absent) | pass |
| LP-06 | R2 | boundary | I1b with no payments | `list_payments_by_invoice(db, I1b.id, W1.id)` | returns `[]` (`type(result) is list`) | pass |
| LP-07 | R6 | boundary | L4 with I1 `invoice_status="voided"` | `list_payments_by_invoice(db, I1.id, W1.id)` | result ids `[LB, LC, LD, LA]` | pass |
| LP-08 | R6 | boundary | L4 with I1 `invoice_status="draft"` | `list_payments_by_invoice(db, I1.id, W1.id)` | result ids `[LB, LC, LD, LA]` | pass |
| LP-09 | R4 [BUG-600] | bug | I1; three ids a < b < c reserved from the payment table's id sequence; payments inserted **in the order c, a, b**, each with that explicit id, all dated 2026-09-01 | `list_payments_by_invoice(db, I1.id, W1.id)` | result ids `[c, b, a]` | xfail BUG-600 — fails today on: result ids not `[c, b, a]` (no id tie-breaker; setup per spec G7) |
| LP-10 | R4, R5 [BUG-600] | bug | as LP-09 | `list_payments_by_invoice(db, I1.id, W1.id, skip=1, limit=1)` | result ids `[b]` | xfail BUG-600 — fails today on: result is not `[b]` |
| LP-11 | R5 | happy | L4 | `skip=1, limit=2` | result ids `[LC, LD]` | pass |
| LP-12 | R5 | boundary | L4 | `skip=0, limit=3` | result ids `[LB, LC, LD]` | pass |
| LP-13 | R5 | boundary | L4 | `skip=3, limit=100` | result ids `[LA]` | pass |
| LP-14 | R5 | boundary | L4 | `skip=4, limit=100` | returns `[]` | pass |
| LP-15 | R5 (default limit) | boundary | I1 with 101 payments, the k-th (k = 1…101) dated `date(2026, 1, 1) + timedelta(days=k)` | `list_payments_by_invoice(db, I1.id, W1.id)` (defaults) | returns exactly 100 tuples; the first dated 2026-04-12 (k=101), the last dated 2026-01-03 (k=2); the k=1 payment absent | pass |

## `InvoicePaymentManager.delete_payment`

Given for every case unless stated: I1 with `paid_amount=250.00`, `payment_status="partial"`, `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=False`; PA on I1. Call: `delete_payment(db, payment_id=…, workspace_id=W1.id, user_id=U1.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DP-01 | R1, Err: payment missing | error | default | payment_id=NOID | 404 `Payment with ID 999999999 not found`; N0 (PA still exists) | pass |
| DP-02 | R1 | isolation | default; I2 in W2 with `paid_amount=100.00`, `payment_status="partial"`; PB = PAY(I2, 100.00, 2026-09-01) | payment_id=PB.id, workspace W1 | 404 `Payment with ID {PB.id} not found`; N0 (PB still exists, I2 100.00 / partial) | pass |
| DP-03 | R2 [BUG-609], Err: exists | bug | default | payment_id=PA.id | 400 `Payments cannot be deleted — void them instead`; N0: PA still exists with every field as set up; I1 `paid_amount=250.00`, `payment_status="partial"`; 0 audit rows; 0 events of I1; PO1 `paid False`, 0 PO events | xfail BUG-609 — fails today on: no exception raised (PA removed) |
| DP-04 | R2 [BUG-609] | bug | I1 with `paid_amount=0.00`, `payment_status="unpaid"`; PV = voided PAY(I1, 250.00, 2026-09-01) | payment_id=PV.id | 400 `Payments cannot be deleted — void them instead`; N0 (PV still exists, `is_voided True`, `void_note="Duplicate entry"`) | xfail BUG-609 — fails today on: no exception raised (PV removed) |
| DP-05 | R2 [BUG-609] | bug | default with I1 `invoice_status="voided"` | payment_id=PA.id | 400 `Payments cannot be deleted — void them instead`; N0 (PA still exists) | xfail BUG-609 — fails today on: no exception raised |

## `InvoicePaymentManager.void_payment`

Given for every case unless stated: I1 with `paid_amount=1000.00`, `payment_status="paid"`; PA on I1 (250.00, cheque, 2026-09-01); PB = PAY(I1, 750.00, 2026-09-02). Default call voids PA.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| VP-01 | R5, R6, R8 | happy | default | default call | returns PA (`is PA`); re-read PA: `is_voided True`, `voided_at=NOW`, `voided_by=U1`, `void_note="Cheque bounced"`; row still exists with `payment_amount=250.00`, `payment_reference="CHQ-881"`, `created_by=U2`; PB `is_voided False` | pass |
| VP-02 | R7 | side-effect | default | default call | returns PA; re-read I1 `paid_amount=750.00`, `payment_status="partial"` | pass |
| VP-03 | R7 | boundary | I1 with `paid_amount=250.00`, `payment_status="partial"`; PA only | default call | returns PA; re-read I1 `paid_amount=0.00`, `payment_status="unpaid"` | pass |
| VP-04 | R7 | boundary | I1 with `paid_amount=1000.01`, `payment_status="paid"`; PA with `payment_amount=0.01`; PB with `payment_amount=1000.00` | default call | returns PA; re-read I1 `paid_amount=1000.00`, `payment_status="paid"` | pass |
| VP-05 | R7 | boundary | I1 with `paid_amount=1000.00`, `payment_status="paid"`; PA with `payment_amount=0.01`; PB with `payment_amount=999.99` | default call | returns PA; re-read I1 `paid_amount=999.99`, `payment_status="partial"` | pass |
| VP-06 | R7 | side-effect | I1 with `paid_amount=250.00`, `payment_status="partial"`; PA active; PB is a voided PAY (750.00) | default call | returns PA; re-read I1 `paid_amount=0.00`, `payment_status="unpaid"` | pass |
| VP-07 | R7 | isolation | I1 with `paid_amount=250.00`, `payment_status="partial"`; PA; PX = PAY(I1, 500.00, 2026-09-04) inserted with `workspace_id=W2` | default call | returns PA; re-read I1 `paid_amount=0.00`, `payment_status="unpaid"` | pass |
| VP-08 | R1, Err: payment missing | error | default | payment_id=NOID | 404 `Payment with ID 999999999 not found`; N0 | pass |
| VP-09 | R1 | isolation | default; I2 in W2 with `paid_amount=100.00`, `payment_status="partial"`; PW = PAY(I2, 100.00, 2026-09-01) | payment_id=PW.id, workspace W1 | 404 `Payment with ID {PW.id} not found`; N0 (PW `is_voided False`, I2 100.00 / partial) | pass |
| VP-10 | R2, Err: already voided | error | I1 with `paid_amount=750.00`, `payment_status="partial"`; PA is a voided PAY; PB active | default call | 400 `Payment is already voided`; N0 (PA `voided_at=T0`, `voided_by=U2`, `void_note="Duplicate entry"`) | pass |
| VP-11 | R3, Err: invoice missing | error | I2 in W2 (defaults); PI = PAY with `invoice_id=I2.id` but `workspace_id=W1`, active, 250.00 | payment_id=PI.id, workspace W1 | 404 `Invoice with ID {I2.id} not found`; N0 (PI `is_voided False`) | pass |
| VP-12 | R4 | boundary | default with I1 `invoice_status="draft"`, `allow_payments=False`, `payment_locked_reason="Locked"` | default call | no error; returns PA; re-read PA `is_voided True`; I1 `paid_amount=750.00`, `payment_status="partial"`, `invoice_status="draft"`, `allow_payments False` | pass |
| VP-13 | R10, R11, R12 (default) | side-effect | default | default call | returns PA; exactly 1 audit row: `entity_type="payment"`, `entity_id=PA.id`, `action_type="voided"`, `performed_by=U1`, `related_entity_type="invoice"`, `related_entity_id=I1.id`, `workspace_id=W1`, `performed_at=NOW`, `ip_address None`, `user_agent None`; `changes == {"payment_voided": {"payment_amount": ≈250.00, "payment_date": "2026-09-01", "payment_method": "cheque"}, "invoice_payment_status": {"before": "paid", "after": "partial"}}`; `description == f"Payment of $250.00 voided for invoice ID {I1.id}. Reason: Cheque bounced"` | pass |
| VP-14 | R11, R13 | boundary | I1 with `paid_amount=300.00`, `payment_status="partial"`; PA with `payment_amount=100.00`; PB with `payment_amount=200.00` | default call | returns PA; I1 `paid_amount=200.00`, `payment_status="partial"`; exactly 1 audit row whose `changes` has key `"payment_voided"` and **no** key `"invoice_payment_status"`; exactly 1 event of I1 with `metadata_json["payment_status_before"] == "partial"` and `metadata_json["payment_status_after"] == "partial"` | pass |
| VP-15 | R13 | side-effect | default | default call | returns PA; exactly 1 event of I1: `event_type="payment_voided"`, `description="Payment voided"`, `performed_by=U1`, `created_at=NOW`, `metadata_json == {"payment_id": PA.id, "payment_amount": "250.00", "payment_method": "cheque", "void_note": "Cheque bounced", "payment_status_before": "paid", "payment_status_after": "partial"}` | pass |
| VP-16 | R12 [BUG-603] | bug | default | default call plus `ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)"` | returns PA; exactly 1 audit row with `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 (Test)"` | xfail BUG-603 — fails today on: `TypeError` (no `ip_address` parameter) |
| VP-17 | R14 | side-effect | default with I1 `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=True` | default call | returns PA; I1 `payment_status="partial"`; PO1 `paid False`; exactly 1 PO event: `event_type="payment_status_synced"`, `description="Order marked unpaid from linked invoice"`, `performed_by=U1`, `metadata_json == {"paid": False}` | pass |
| VP-18 | R9 [BUG-601] | bug | default; SQL capture on | default call | returns PA; re-read PA `is_voided True`; captured SQL locks the invoice; after the first locking invoice statement, at least one captured statement selects from the payment table (the re-read) | xfail BUG-601 — fails today on: no captured invoice SELECT contains `FOR UPDATE` |
| VP-19 | R9, R2 [BUG-601] | bug | default; race simulation (see Conventions) | default call | 400 `Payment is already voided`; re-read PA: `voided_by=U2`, `voided_at=T0`, `void_note="Voided by other user"` (the winner's values, not overwritten); I1 `paid_amount=1000.00`, `payment_status="paid"`; 0 audit rows; 0 events of I1 | xfail BUG-601 — fails today on: no exception raised (no `FOR UPDATE` runs, so the hook never fires) |
| VP-20 | R6, Inputs [BUG-605] | bug | — (schema) | `VoidPaymentRequest(void_note="   ")` | raises ValidationError | xfail BUG-605 — fails today on: no error raised |
| VP-21 | R6, Inputs [BUG-605] | bug | — (schema) | `VoidPaymentRequest(void_note="  Cheque  bounced  ")` | no error; `.void_note == "Cheque  bounced"` (outer spaces removed, inner kept) | xfail BUG-605 — fails today on: `void_note` still has the outer spaces |
| VP-22 | Inputs | boundary | — (schema) | `VoidPaymentRequest(void_note="x")` | no error; `.void_note == "x"` | pass |
| VP-23 | Inputs | boundary | — (schema) | `VoidPaymentRequest(void_note="")` | raises ValidationError | pass |
| VP-24 | R9a, R3, R2 [BUG-601] | bug | I2 in W2 (defaults); PIV = voided PAY with `invoice_id=I2.id` but `workspace_id=W1`, 250.00 | payment_id=PIV.id, workspace W1 | 404 `Invoice with ID {I2.id} not found` (not 400 already-voided); N0 (PIV `voided_at=T0`, `voided_by=U2`, `void_note="Duplicate entry"`) | xfail BUG-601 — fails today on: raises 400 `Payment is already voided` |
| VP-25 | R7 | boundary | I1 with `paid_amount=250.01`, `payment_status="partial"`; PA (250.00, active); PB with `payment_amount=0.01` (active) | default call | returns PA; re-read I1 `paid_amount=0.01`, `payment_status="partial"` (remaining total just above 0 → `partial`, not `unpaid`); re-read PB `is_voided False` | pass |

## `InvoicePaymentManager._sync_linked_order`

Called directly with I1 re-loaded from the DB (after setup) and `user_id=U1.id`. Every case asserts the call returns `None`, and re-reads every PO/SO/return in the setup. "No events" = 0 PO events and 0 SO events.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SY-01 | R1 | boundary | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=NULL`; PR1 and PO1 each with `invoice_id=I1.id`, `paid=False` | call | returns None; PR1 `paid False`; PO1 `paid False`; no events | pass |
| SY-02 | R2 | happy | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; PR1 with `invoice_id=I1.id`, `paid=False`; PO1 with `invoice_id=I1.id`, `paid=False` | call | returns None; PR1 `paid True`; PO1 `paid False` (untouched); no events | pass |
| SY-03 | R2 | side-effect | I1 `payment_status="partial"`, `order_type="purchase_order"`, `order_id=PO1.id`; PR1 with `invoice_id=I1.id`, `paid=True` | call | returns None; PR1 `paid False`; no events | pass |
| SY-04 | R2 | boundary | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; PR1 with `invoice_id=I1.id`, `paid=True` | call | returns None; PR1 `paid True`; no events | pass |
| SY-05 | R3 | happy | I1 `payment_status="paid"`, `order_type="sales_order"`, `order_id=SO1.id`; SR1 with `invoice_id=I1.id`, `paid=False`; SO1 with `invoice_id=I1.id`, `paid=False` | call | returns None; SR1 `paid True`; SO1 `paid False` (untouched); no events | pass |
| SY-06 | R3 | side-effect | I1 `payment_status="unpaid"`, `order_type="sales_order"`, `order_id=SO1.id`; SR1 with `invoice_id=I1.id`, `paid=True` | call | returns None; SR1 `paid False`; no events | pass |
| SY-07 | R4, R5 | happy | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=POX.id`; PO1 with `invoice_id=I1.id`, `paid=False`; no returns | call | returns None; PO1 `paid True`; POX `paid False` (the `order_id` target is not used); exactly 1 PO event, for PO1: `event_type="payment_status_synced"`, `description="Order marked paid from linked invoice"`, `performed_by=U1`, `metadata_json == {"paid": True}`; 0 SO events | pass |
| SY-08 | R5 | side-effect | I1 `payment_status="partial"`, `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=True` | call | returns None; PO1 `paid False`; exactly 1 PO event for PO1: `description="Order marked unpaid from linked invoice"`, `metadata_json == {"paid": False}`, `performed_by=U1`, `event_type="payment_status_synced"` | pass |
| SY-09 | R5 | boundary | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=True` | call | returns None; PO1 `paid True`; no events | pass |
| SY-10 | R4 | boundary | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=POX.id`; no PO, SO or return has `invoice_id=I1.id` | call | returns None; POX `paid False`; no events | pass |
| SY-11 | R6 | happy | I1 `payment_status="paid"`, `order_type="sales_order"`, `order_id=SO1.id`; SO1 with `invoice_id=I1.id`, `paid=False`; no returns | call | returns None; SO1 `paid True`; exactly 1 SO event for SO1: `event_type="payment_status_synced"`, `description="Order marked paid from linked invoice"`, `performed_by=U1`, `metadata_json == {"paid": True}`; 0 PO events | pass |
| SY-12 | R6 | side-effect | I1 `payment_status="partial"`, `order_type="sales_order"`, `order_id=SO1.id`; SO1 with `invoice_id=I1.id`, `paid=True` | call | returns None; SO1 `paid False`; exactly 1 SO event: `description="Order marked unpaid from linked invoice"`, `metadata_json == {"paid": False}` | pass |
| SY-13 | R6 | boundary | I1 `payment_status="unpaid"`, `order_type="sales_order"`, `order_id=SO1.id`; SO1 with `invoice_id=I1.id`, `paid=False` | call | returns None; SO1 `paid False`; no events | pass |
| SY-14 | R7 | boundary | I1 `payment_status="paid"`, `order_type="expense_order"`, `order_id=1`; PO1, SO1, PR1, SR1 each with `invoice_id=I1.id`, `paid=False` | call | returns None; PO1, SO1, PR1, SR1 all `paid False`; no events | pass |
| SY-15 | R7 | boundary | as SY-14 with `order_type="work_order"` | call | same as SY-14 | pass |
| SY-16 | R7 | boundary | as SY-14 with `order_type=NULL` (`order_id=1`) | call | same as SY-14 | pass |
| SY-17 | R8 | isolation | I1 (W1) `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; PRX = a purchase-order return in **W2** with `invoice_id=I1.id`, `paid=False`; PO1 (W1) with `invoice_id=I1.id`, `paid=False` | call | returns None; PRX `paid False` (ignored); PO1 `paid True` (PO path taken); exactly 1 PO event, for PO1 | pass |
| SY-18 | R8 | isolation | I1 `payment_status="paid"`, `order_type="purchase_order"`, `order_id=PO1.id`; POW = a purchase order in **W2** with `invoice_id=I1.id`, `paid=False`; no W1 PO or return references I1 | call | returns None; POW `paid False`; no events | pass |
| SY-19 | R8 | isolation | I1 `payment_status="paid"`, `order_type="sales_order"`, `order_id=SO1.id`; SOW = a sales order in **W2** and SRW = a sales-order return in **W2**, each with `invoice_id=I1.id`, `paid=False`; no W1 SO or return references I1 | call | returns None; SOW `paid False`; SRW `paid False`; no events | pass |
| SY-20 | R5 ("paid" = exactly `paid`) | boundary | I1 `payment_status="overdue"`, `order_type="purchase_order"`, `order_id=PO1.id`; PO1 with `invoice_id=I1.id`, `paid=True` | call | returns None; PO1 `paid False`; exactly 1 PO event with `metadata_json == {"paid": False}` | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_payment` R10a, `void_payment` R12 [BUG-603] | `InvoicePaymentService` + `POST /invoice-payments/`, void endpoint | the request's client IP and user agent are passed endpoint → service → manager and reach the audit row |
| `update_payment` R6a [BUG-607] (`user_id`) | `InvoicePaymentService.update_payment` / `PUT /invoice-payments/{id}/` | the caller's user id is passed to `update_payment` |
| `create_payment` R5a, `update_payment` Inputs [BUG-604] | `POST` / `PUT /invoice-payments/` | 3-decimal or 14-integer-digit amount → 422, nothing written |
| `void_payment` Inputs [BUG-605] | void endpoint | `void_note` of spaces only → 422; padded note stored trimmed |
| `list_payments_by_invoice` Inputs (`skip ≥ 0`, `1 ≤ limit ≤ 1000`) | `GET` invoice-payments list endpoint | out-of-range `skip`/`limit` → 422 |
| `delete_payment` R2 [BUG-609] | `DELETE /invoice-payments/{id}/` + `InvoicePaymentService` | response 400 with the detail text; nothing committed |
| `create_payment` R2, `void_payment` R9 [BUG-601] (real two-session race) | integration tests | two committed concurrent transactions on one invoice: the second waits, sees the new `paid_amount` / voided state; the losing voider gets 400 |

## Spec gaps
None. The ten gaps of revision 1 were all closed by the spec's Gap log (G1–G10): audit money format (G1), shape of the `updated` audit row (G2), `workspace_id` on void/update audit rows (G3), R2 message vs BUG-609 → BUG-611 (G4), error precedence → update R3a / void R9a (G5), `utcnow` patch target (G6), BUG-600 insertion order (G7), lock testing method and table names (G8), BUG-604 integer digits today (G9), free-text `order_type` / statuses (G10).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_payment` | R1 | CP-09, CP-10, CP-11 |
| `create_payment` | R2 | CP-12 (race: Deferred) |
| `create_payment` | R3 | CP-13, CP-14, CP-18 |
| `create_payment` | R4 | CP-15, CP-16, CP-17, CP-18, CP-19 |
| `create_payment` | R5 | CP-03, CP-05, CP-06, CP-07 |
| `create_payment` | R5a [BUG-604] | CP-26, CP-27, CP-28, CP-29 |
| `create_payment` | R6 | CP-01, CP-11, CP-23 |
| `create_payment` | R7 | CP-02, CP-03, CP-04, CP-08 |
| `create_payment` | R8 | CP-02 |
| `create_payment` | R9 | CP-11, CP-20 |
| `create_payment` | R10 | CP-20, CP-21, CP-23 |
| `create_payment` | R10a [BUG-603] | CP-20 (default None), CP-24 |
| `create_payment` | R11 | CP-20, CP-21 |
| `create_payment` | R12 | CP-21, CP-22, CP-23 |
| `create_payment` | R13 | CP-25 (+ `_sync_linked_order` SY-*) |
| `create_payment` | R14 | CP-05, CP-06, CP-07, CP-09, CP-10, CP-13–CP-18 |
| `create_payment` | Err: invoice missing / other ws | CP-09, CP-10 |
| `create_payment` | Err: not confirmed | CP-13, CP-14 |
| `create_payment` | Err: allow_payments false | CP-15, CP-16, CP-17 |
| `create_payment` | Err: amount > outstanding | CP-05, CP-06, CP-07 |
| `update_payment` | R1 | UP-07, UP-08, UP-10 |
| `update_payment` | R2 | UP-04, UP-05, UP-06, UP-20 |
| `update_payment` | R2a [BUG-611] | UP-23 |
| `update_payment` | R3 [BUG-606] | UP-09, UP-10, UP-11, UP-24 |
| `update_payment` | R3a [BUG-606] | UP-10 (404 before voided), UP-24 (voided before amount) |
| `update_payment` | R4 | UP-01, UP-03, UP-05 |
| `update_payment` | R5 [BUG-608] | UP-12, UP-13, UP-14, UP-17 |
| `update_payment` | R6 | UP-02 |
| `update_payment` | R6a [BUG-607] | UP-14, UP-15, UP-16, UP-17, UP-18, UP-19, UP-20 |
| `update_payment` | R7 [BUG-608] | UP-15, UP-16, UP-17 |
| `update_payment` | Inputs `payment_amount` [BUG-604] | UP-21, UP-22 |
| `update_payment` | Err: payment missing / other ws | UP-07, UP-08 |
| `update_payment` | Err: amount different [BUG-611] | UP-04, UP-06, UP-23 |
| `update_payment` | Err: voided [BUG-606] | UP-09, UP-24 |
| `list_payments_by_invoice` | R1 | LP-02, LP-03 |
| `list_payments_by_invoice` | R2 | LP-01, LP-04, LP-05, LP-06 |
| `list_payments_by_invoice` | R3 | LP-01 |
| `list_payments_by_invoice` | R4 [BUG-600] | LP-01, LP-09, LP-10 |
| `list_payments_by_invoice` | R5 | LP-10, LP-11, LP-12, LP-13, LP-14, LP-15 |
| `list_payments_by_invoice` | R6 | LP-07, LP-08 |
| `list_payments_by_invoice` | Returns (`created_by_name`) | LP-01 |
| `list_payments_by_invoice` | Err: invoice missing / other ws | LP-02, LP-03 |
| `delete_payment` | R1 | DP-01, DP-02 |
| `delete_payment` | R2 [BUG-609] | DP-03, DP-04, DP-05 |
| `delete_payment` | Err: payment missing / other ws | DP-01, DP-02 |
| `delete_payment` | Err: exists, any state [BUG-609] | DP-03, DP-04, DP-05 |
| `delete_payment` | [BUG-602], [BUG-610] | superseded by BUG-609 per spec Q4/Q5 — no rule, no case |
| `void_payment` | R1 | VP-08, VP-09 |
| `void_payment` | R2 | VP-10, VP-19, VP-24 |
| `void_payment` | R3 | VP-11, VP-24 |
| `void_payment` | R4 | VP-12 |
| `void_payment` | R5 | VP-01 |
| `void_payment` | R6 [BUG-605] | VP-01, VP-20, VP-21, VP-22, VP-23 |
| `void_payment` | R7 | VP-02, VP-03, VP-04, VP-05, VP-06, VP-07, VP-25 |
| `void_payment` | R8 | VP-01 |
| `void_payment` | R9 [BUG-601] | VP-18, VP-19 (real race: Deferred) |
| `void_payment` | R9a [BUG-601] | VP-08/VP-09 (payment 404 first), VP-24 (invoice 404 before already-voided) |
| `void_payment` | R10 | VP-13 |
| `void_payment` | R11 | VP-13, VP-14 |
| `void_payment` | R12 [BUG-603] | VP-13 (default None), VP-16 |
| `void_payment` | R13 | VP-14, VP-15 |
| `void_payment` | R14 | VP-17 (+ SY-*) |
| `void_payment` | Err: payment missing / other ws | VP-08, VP-09 |
| `void_payment` | Err: already voided | VP-10, VP-19 |
| `void_payment` | Err: invoice missing | VP-11, VP-24 |
| `_sync_linked_order` | R1 | SY-01 |
| `_sync_linked_order` | R2 | SY-02, SY-03, SY-04 |
| `_sync_linked_order` | R3 | SY-05, SY-06 |
| `_sync_linked_order` | R4 | SY-07, SY-10 |
| `_sync_linked_order` | R5 | SY-07, SY-08, SY-09, SY-20 |
| `_sync_linked_order` | R6 | SY-11, SY-12, SY-13 |
| `_sync_linked_order` | R7 | SY-14, SY-15, SY-16 |
| `_sync_linked_order` | R8 | SY-17, SY-18, SY-19 |
