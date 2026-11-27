# Spec — `app/managers/invoice_payment_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-6** `list_payments_by_invoice` R4 — payments are ordered by `payment_date` descending only; payments on the same date come back in no fixed order, so paging can repeat or skip them. Intended: `payment_date` descending, then `id` descending (same shape as the invoice list's `invoice_date desc, id desc`), applied before `skip`/`limit`. — 🐞 BUG-600
**Answer:** bug — per HR-6 (house rule)
**Resolution:** ordered by `payment_date` descending, then `id` descending, applied before `skip`/`limit`. Rules: `list_payments_by_invoice` R4.

- **HR-10** `void_payment` R9 — the payment and its invoice are read without a row lock. Two concurrent voids of the same payment both pass the "already voided" check and both write audit rows and `payment_voided` events; a void running alongside a `create_payment` on the same invoice can overwrite the invoice's `paid_amount` with a total that misses the new payment. Intended: the invoice row is read `FOR UPDATE` (the same lock `create_payment` takes) and the payment is re-read after the lock; the loser sees the payment already voided and gets 400 "Payment is already voided". — 🐞 BUG-601
**Answer:** bug — per HR-10 (house rule)
**Resolution:** the invoice row is read `FOR UPDATE` before the recompute, and the payment is re-read after the lock is acquired; a voider that loses the race sees `is_voided = True` already set and gets 400 "Payment is already voided". Rules: `void_payment` R9.

- **HR-10** `delete_payment` R9 — the invoice is read without a row lock before `paid_amount`/`payment_status` are recomputed. A delete running alongside a `create_payment` or `void_payment` on the same invoice can overwrite `paid_amount` with a total that misses the other change. Intended: the invoice row is read `FOR UPDATE` before the recalculation; the concurrent operation waits and then sees the new totals. — 🐞 BUG-602
**Answer:** bug — per HR-10 (house rule)
**Resolution:** superseded by BUG-609 (Q4, below): once `delete_payment` never mutates anything (it always ends in 404 or 400), there is nothing left to race, so the lock this rule would have added has no effect to test. Logged for the record; no rule added to `delete_payment`. (Best-practice default, delegated by reviewer — same reasoning as Q4/Q5.)

### Precedent matches — confirm all with ok

### P1. Payment audit rows never record IP address or user agent — 🐞 BUG-603
**Background:** `log_financial_audit` can store the caller's IP address and user agent. BUG-140 already lists `InvoicePaymentManager` among the places the fix must reach.
**What happens today:** Create, delete and void write financial audit rows with `ip_address` and `user_agent` both `NULL`; the manager methods have no way to receive them.
**Example:** A user voids payment 12 from the browser. The audit row for `payment` 12 / `voided` has no IP and no user agent, so an investigator cannot tell where the void came from.
**Rules affected:** `create_payment` R10, `delete_payment` R11, R12, `void_payment` R12
**Answer:** bug — per BUG-140 precedent: `create_payment`, `delete_payment` and `void_payment` accept the request's client IP and user agent (passed from endpoint → service) and pass them into every `log_financial_audit` call (precedent — confirmed: ok)
**Resolution:** `create_payment` and `void_payment` each gain `ip_address: str | None = None` and `user_agent: str | None = None` parameters (passed endpoint → service → manager) and pass them into every `log_financial_audit` call they make. `delete_payment` does **not** gain these parameters: BUG-609 (Q4, below) eliminates every audit row `delete_payment` writes before this fix would ever reach them, so the two rules originally cited there (old R11, R12) are superseded. (Best-practice default, delegated by reviewer — see Q4/Q5 for the same reasoning.) Rules: `create_payment` R10a (new), `void_payment` R12 (rewritten).

### P2. Payment amounts with more than 2 decimals are accepted — 🐞 BUG-604
**Background:** `payment_amount` is stored as `Numeric(15,2)`; Postgres rounds any extra decimals on write. The create schema only requires `> 0` and does not limit decimal places. The overpayment check and the invoice's `payment_status` are computed in Python on the unrounded amount.
**What happens today:** `9.995` is accepted; the payment and the invoice's `paid_amount` are stored as `10.00`, but the status was decided on `9.995`.
**Example:** A confirmed invoice of 10.00 with nothing paid. A user records a payment of 9.995. The check passes (9.995 ≤ 10.00), the invoice status is set to `partial` (9.995 < 10.00), and both amounts are saved as 10.00. The invoice now shows paid 10.00 of 10.00 but status "partial", and any further payment is refused as exceeding the 0.00 outstanding.
**Rules affected:** `create_payment` R5
**Answer:** bug — per BUG-021 precedent: `InvoicePaymentCreate.payment_amount` (and `InvoicePaymentUpdate.payment_amount`) reject more than 2 decimal places or more than 13 integer digits with a validation error (422 at the API); nothing written (precedent — confirmed: ok)
**Resolution:** `InvoicePaymentCreate.payment_amount` and `InvoicePaymentUpdate.payment_amount` reject more than 2 decimal places or more than 13 integer digits with a Pydantic `ValidationError` (422 at the API); the manager is never reached, nothing written. Rules: `create_payment` R5a (new); `update_payment` Inputs note.

### P3. Whitespace-only void reason is accepted — 🐞 BUG-605
**Background:** The void request requires `void_note` with minimum length 1, but does not trim it, so `"   "` passes. The manager stores whatever it receives.
**What happens today:** A payment can be voided with a reason of only spaces; the stored `void_note`, the audit description ("... Reason:    ") and the event metadata all carry the blank reason.
**Example:** A user voids payment 12 with `{"void_note": "   "}`. Response 200; the invoice timeline shows "Payment voided" with an empty reason, although a reason is meant to be mandatory.
**Rules affected:** `void_payment` R6
**Answer:** bug — per BUG-125 precedent: `VoidPaymentRequest.void_note` is stripped of leading/trailing whitespace and blank / whitespace-only values are rejected with a validation error (422); the reason is stored trimmed (precedent — confirmed: ok)
**Resolution:** `VoidPaymentRequest.void_note` is stripped of leading/trailing whitespace by the schema and rejected (422) if blank/whitespace-only after stripping; the manager only ever receives a non-blank, trimmed value and stores it exactly as given. Rules: `void_payment` R6.

### New questions

### Q1. Voided payments can still be edited — 🐞 BUG-606
**Background:** Voiding a payment is described as irreversible: it is excluded from the invoice's paid total and kept only as a record (voiding an invoice also voids all its payments). Editing a payment changes its date, method, reference, bank name, transaction id or notes.
**What happens today:** `update_payment` does not check whether the payment is voided, so a voided payment's details can be changed freely.
**Example:** Payment 12 (5,000.00 by cheque, ref "CHQ-881") was voided last week. A user sends `PUT /invoice-payments/12/ {"payment_reference": "CHQ-999", "payment_date": "2026-01-01"}` and gets 200; the voided record now shows a different cheque and date than the one that was actually voided.
**Rules affected:** `update_payment` R3
**Answer:** bug — a voided payment cannot be edited: 400 "Voided payments cannot be edited", nothing changed (reviewer accepted suggestion)
**Suggested answer:** bug — a voided payment cannot be edited: 400 "Voided payments cannot be edited", nothing changed
**Resolution:** a voided payment (`is_voided = True`) cannot be edited: 400 "Voided payments cannot be edited"; nothing changed. Rules: `update_payment` R3.

### Q2. Editing a payment leaves no audit trail — 🐞 BUG-607
**Background:** Recording, deleting and voiding a payment each write a financial audit row (and recording/voiding also add an entry to the invoice's activity timeline). Editing a payment writes neither. The payment table has no "updated at / updated by" columns either.
**What happens today:** A change to a payment's date, method, reference, bank name, transaction id or notes is saved with no record of who changed what, or when.
**Example:** A user changes payment 12's `payment_date` from 2026-03-01 to 2026-02-01 and its reference from "CHQ-881" to "CHQ-100". Neither the audit log nor the invoice timeline shows that anything happened; the old values are lost.
**Rules affected:** `update_payment` R6
**Answer:** bug — when a field actually changes (HR-9), write a payment 'updated' financial audit row with before/after of the changed fields and a payment_updated invoice event; nothing for a no-op update (requires new user_id parameter) (reviewer accepted suggestion)
**Suggested answer:** bug — when at least one field actually changes value (HR-9), write a financial audit row (`entity_type` `payment`, `action_type` `updated`, related invoice, `changes` = before/after of the changed fields only, performed by the caller) and a `payment_updated` invoice event; nothing is logged for a no-op update (requires new `user_id` parameter)
**Resolution:** `update_payment` gains a required `user_id: int` parameter. When at least one field actually changes value (HR-9), one financial audit row is written (`entity_type` `payment`, `action_type` `updated`, related invoice, `changes` = before/after of only the changed fields) and one `payment_updated` invoice event is written; nothing is logged for a no-op update. The event's metadata shape (`payment_id`, `changed_fields`) and leaving `ip_address`/`user_agent` `NULL` on this new audit row (BUG-603's fix only reaches the three pre-existing call sites) are best-practice defaults, delegated by reviewer. Rules: `update_payment` R6a (new).

### Q3. Optional payment details cannot be cleared — 🐞 BUG-608
**Background:** An update only applies fields that are present **and not null**; sending `null` for a field is treated the same as leaving it out.
**What happens today:** Once a payment has a reference, bank name, transaction id, method or notes, there is no way to remove it — only to overwrite it with another non-null value (an empty string `""` is accepted and stored).
**Example:** Payment 12 was recorded with `bank_name: "City Bank"` by mistake (it was cash). The user sends `{"bank_name": null}`; response 200, but the payment still shows "City Bank".
**Rules affected:** `update_payment` R5
**Answer:** bug — explicit null clears payment_method, payment_reference, bank_name, transaction_id and notes; null for payment_date / payment_amount is ignored (reviewer accepted suggestion)
**Suggested answer:** bug — an explicit `null` clears `payment_method`, `payment_reference`, `bank_name`, `transaction_id` and `notes`; an explicit `null` for the required `payment_date` or for `payment_amount` is ignored (fields left out stay unchanged)
**Resolution:** an explicit `null` for `payment_method`, `payment_reference`, `bank_name`, `transaction_id` or `notes` clears the stored value; an explicit `null` for `payment_date` or `payment_amount` is ignored (those may not be nulled); a field simply left out of the request body is unchanged either way. Implementation (build the update dict with `exclude_unset=True` only, then drop `payment_date`/`payment_amount` from it when sent as `null`) is a best-practice default, delegated by reviewer. Rules: `update_payment` R5, R7 (reworded).

### Q4. Payments can be permanently deleted, even though voiding exists — 🐞 BUG-609
**Background:** Payments have a void mechanism that keeps the record (with who/when/why) and removes it from the invoice's paid total. Deleting instead removes the payment row entirely; only a financial audit row with a snapshot of amount/date/method remains. Delete is allowed for any payment — active or already voided — and on any invoice, including voided ones.
**What happens today:** `DELETE /invoice-payments/{id}/` erases the payment and recomputes the invoice's paid amount and status. Reference, bank, transaction id, notes, creator and any void details are gone.
**Example:** Invoice 40 (10,000.00) has a 4,000.00 bank transfer, ref "TRX-7781". A user deletes it. The invoice goes back to "unpaid"; the payment no longer appears anywhere in the app, and the reference/transaction id cannot be recovered.
**Rules affected:** `delete_payment` R1–R14
**Answer:** bug — payments are never hard-deleted: delete refused with 400 "Payments cannot be deleted — void them instead", nothing changed (reviewer accepted suggestion)
**Suggested answer:** bug — payments are never hard-deleted (accounting records are immutable): delete is refused with 400 "Payments cannot be deleted — void them instead", nothing changed
**Resolution:** `delete_payment` never deletes a payment. After the existence check (R1, unchanged), every payment — active or already voided, on any invoice — is refused: 400 "Payments cannot be deleted — void them instead"; nothing changed. This supersedes the old recompute/audit/sync mechanics and the HR-10 lock above (old R2–R14), which are no longer reachable — see Q5 for the same reasoning applied to BUG-610. Rules: `delete_payment` R1 (unchanged), R2 (rewritten, replaces old R2–R14).

### Q5. Deleting a payment does not appear in the invoice's activity timeline — 🐞 BUG-610
**Background:** The invoice timeline (invoice events) records "Payment recorded" and "Payment voided". Deleting a payment only writes financial audit rows, which the invoice timeline does not show.
**What happens today:** After a payment is deleted, the timeline still shows "Payment recorded" for it but nothing about its removal, while the invoice's paid amount has dropped.
**Example:** Invoice 40's timeline shows "Payment recorded — 4,000.00". The payment is deleted; the invoice now shows paid 0.00, and the timeline gives no hint why.
**Rules affected:** `delete_payment` R13
**Answer:** bug — while deletion is allowed, write a payment_deleted invoice event (performed by caller; metadata payment_id, payment_amount, payment_method, payment_status_before/after), mirroring payment_voided (reviewer accepted suggestion)
**Suggested answer:** bug — as long as deletion is allowed (see Q4), a `payment_deleted` invoice event is written ("Payment deleted", performed by the caller, metadata: `payment_id`, `payment_amount`, `payment_method`, `payment_status_before`, `payment_status_after`), mirroring `payment_voided`
**Resolution:** superseded by Q4/BUG-609 (best-practice default, delegated by reviewer): once `delete_payment` unconditionally refuses deletion, this fix's trigger condition — a payment actually being deleted — never occurs, so a `payment_deleted` event is never reachable. BUG-610 is still logged with its intended behavior, marked superseded; no rule is added to `delete_payment`. If `delete_payment` is ever reopened (BUG-609 reverted), this fix should be re-applied then.

### Q7. Amount-change error tells the user to delete the payment — 🐞 BUG-611
**Background:** Since BUG-609, payments can never be deleted; the only way to reverse a payment is to void it. Changing a payment's amount is refused by `update_payment`.
**What happens today:** The refusal says `Cannot change payment amount. Delete and re-create payment instead.` — pointing the user at an action that (once BUG-609 lands) is always refused.
**Example:** A user edits payment 12 from 4,000.00 to 4,500.00 and gets "Delete and re-create payment instead."; they click delete and get "Payments cannot be deleted — void them instead".
**Rules affected:** `update_payment` R2
**Answer:** bug — the message reads `Cannot change payment amount. Void and re-create payment instead.` (best-practice default, delegated by reviewer — raised as spec gap 4 of the cases file; no reviewer question pending)
**Resolution:** 400 detail becomes `Cannot change payment amount. Void and re-create payment instead.`; status code and trigger unchanged. Rules: `update_payment` R2a (new).

### Q6. `get_payment` is never called — 🗑️ removed
**Background:** The payment detail endpoint goes through the service, which reads the payment (with creator name) straight from the DAO. No service, endpoint or other manager calls `InvoicePaymentManager.get_payment`.
**What happens today:** The method exists and works (404 for a missing or other-workspace payment) but is unreachable from the API.
**Example:** `GET /invoice-payments/12/` returns the payment without ever going through `get_payment`; removing the method changes nothing a user can observe.
**Rules affected:** `get_payment` R1–R3
**Answer:** remove (reviewer accepted suggestion)
**Suggested answer:** remove
**Resolution:** moved to Not specified as dead code; its section and Branch-map rows removed. Logged to `tests/unit/managers/invoice_payment_manager.deadcode-staging.md` (batch run — the shared checklist is merged later).

## Overview
Manages the individual payments recorded against account invoices (payables and receivables): recording a payment against a confirmed invoice, editing its non-amount details (now audited — BUG-607), listing an invoice's payments, voiding a payment, and refusing to delete one (payments are accounting records — BUG-609; void is the only way to reverse one). Every change to money keeps the invoice's `paid_amount` and `payment_status` (`unpaid` / `partial` / `paid`) in step, writes a financial audit row, and (for record/edit/void) an invoice timeline event, then pushes the invoice's paid state to the linked purchase order, sales order or return. Called only by `InvoicePaymentService` (`app/services/invoice_payment_service.py`), which owns commit/rollback. Invariants: payments only against confirmed invoices that allow payments; never more than the outstanding balance; invoice totals equal the sum of non-voided payments after void; a payment row, once created, is never removed.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.utils.time.utcnow`, used for `voided_at`, audit `performed_at`, invoice event `created_at`)
**Integration-only behavior:** the real two-transaction race on the `FOR UPDATE` locks (`create_payment` R2, `void_payment` R9) — it needs committed setup rows visible to two connections, which the rolled-back-per-test harness cannot provide. In unit tests the lock is observed through the emitted SQL (see notes).

**Notes for the test designer:**
- Money columns are `Numeric(15,2)`; Postgres rounds extra decimals on flush. Python-side values on in-session objects are not rounded until refreshed.
- `payment_status` values in play here: `unpaid`, `partial`, `paid`. (`overdue` exists in the model comment but nothing in this module sets it; a prior `overdue` is simply overwritten by the recalculation.)
- Row locks (`create_payment` R2, `void_payment` R9 per BUG-601): setup rows are never committed, so a second connection cannot see them. Observe the lock by capturing the SQL the session emits (e.g. a `before_cursor_execute` listener on the test connection) and asserting a `SELECT … FROM account_invoices … FOR UPDATE` for the invoice id is issued — for `void_payment`, before the payment's voided state is decided. The losing side of a race can be simulated in-session by setting the payment's `is_voided = True` via a direct SQL `UPDATE invoice_payments …` before the call (the post-lock re-read must see it). The true concurrent race is integration-only. Table names: invoices `account_invoices`, payments `invoice_payments` (models' `__tablename__`).
- Time: `utcnow` returns a **naive** UTC datetime (tzinfo stripped); all timestamp columns here are `TIMESTAMP WITHOUT TIME ZONE`. It is imported by name in `app.managers.invoice_payment_manager` (`voided_at`), `app.utils.audit_logger` (audit `performed_at`), and `app.models.invoice_event`, where it is bound as the column default (`default=utcnow`) at import — patching the module attribute there has no effect on that default. To freeze all three reliably, patch `app.utils.time.datetime` (the name `utcnow()` resolves at call time); otherwise patch each importing module's `utcnow` and do not assert invoice-event `created_at` exactly. `invoice_payments.created_at` is `server_default=now()` (DB clock, not `utcnow`).
- `account_invoices.order_type` is free text `String(30)`, nullable, no CHECK/enum — `purchase_order`, `sales_order`, `expense_order`, `work_order`, `NULL` or any other string are storable. `invoice_status` and `payment_status` are free text `String(20)`, no CHECK/enum — `overdue` is storable.
- Same-date ordering (`list_payments_by_invoice` R4 today): Postgres returns ties in no guaranteed order (usually physical/insertion order for a tiny table). To make the BUG-600 xfail meaningful, insert same-date rows so that insertion order differs from the intended `id desc` order (e.g. insert with explicit ids in order c, a, b where a < b < c).
- Collaborator outcomes that are observable in the DB: `financial_audit_logs` rows (`app/models/financial_audit_log.py`, including `ip_address`/`user_agent` per BUG-603), `invoice_events` rows (`event_type`, `description`, `metadata_json`, `performed_by`), `purchase_orders.paid` / `sales_orders.paid` / `purchase_order_returns.paid` / `sales_order_returns.paid`, and `purchase_order_events` / `sales_order_events` rows with `event_type` `payment_status_synced`.
- Audit snapshots go through `extract_relevant_fields` (see `app/utils/audit_logger.py` spec): today `Decimal` becomes `float` (BUG-141), dates become ISO strings. BUG-141's intended format is an exact fixed-point string (`"100.50"`). That bug belongs to the audit-logger spec, not this module: here money values inside audit `changes` are compared **numerically** (`Decimal(str(v)) == expected`), so both today's float and the post-fix string pass (best-practice default, delegated by reviewer). Invoice-event `metadata_json` money values are `str(Decimal)` produced by this module and are compared exactly.
- Invoices have no soft-delete column; payments have no soft-delete column (voiding is a visible state, not a soft delete). PO / SO / return rows looked up here have no soft-delete column either.
- Once BUG-609 lands, `delete_payment` never mutates anything — its only observable behaviors are the 404 (R1) and the unconditional 400 (R2). Do not design cases around the old recompute/audit mechanics described inside R2's `(Today: …)` note; that note is historical record only, per Q4's Resolution.

## Not specified
- `InvoicePaymentManager.__init__` — wires the model and the two DAOs, no logic
- `InvoicePaymentManager.get_payment` — dead code, to be removed (reviewer) — no caller in `app/` (the payment-detail endpoint goes through `InvoicePaymentService.get_payment`, which reads straight from the DAO) or in `tests/`

---

## `InvoicePaymentManager.create_payment(session, payment_data, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public

**Purpose:** Record a payment against a confirmed invoice and bring the invoice's paid amount/status, audit trail, timeline and linked order up to date.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payment_data` | `InvoicePaymentCreate` | `invoice_id: int` (required); `payment_amount: Decimal > 0` — [BUG-604] rejects more than 2 decimal places or more than 13 integer digits (422); `payment_date: date` (required, any date, no range check); `payment_method` ≤ 50 chars, `payment_reference` ≤ 100, `bank_name` ≤ 255, `transaction_id` ≤ 100 — all optional, stored as typed (no trimming, `""` allowed); `notes` optional, unlimited |
| `workspace_id` | int | caller's workspace; the invoice must belong to it |
| `user_id` | int | stored as `created_by`, audit `performed_by`, event `performed_by` |
| `ip_address` | `str \| None` | [BUG-603] caller's client IP address, written to the audit row's `ip_address`. *(Requires new parameter — today not accepted.)* |
| `user_agent` | `str \| None` | [BUG-603] caller's user agent, written to the audit row's `user_agent`. *(Requires new parameter — today not accepted.)* |

**Returns:** the new `InvoicePayment`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** The invoice is looked up by `payment_data.invoice_id` within `workspace_id`. If none exists — including when the id belongs to another workspace — 404 `Invoice with ID {invoice_id} not found`; nothing written.
- **R2.** The invoice row is read with a row lock (`SELECT … FOR UPDATE`) held until the caller's transaction ends, so a concurrent payment on the same invoice waits and then sees the updated `paid_amount`.
- **R3.** An invoice whose `invoice_status` is anything other than exactly `confirmed` (`draft`, `voided`, any other value) is rejected with 400 `Payments can only be recorded against confirmed invoices (current status: '{invoice_status}').`; nothing written.
- **R4.** A confirmed invoice with `allow_payments = False` is rejected with 403; the detail is the invoice's `payment_locked_reason`, or `Payments are locked for this invoice` when the reason is `NULL` or empty string `""`. Nothing written. (Checked after R3: a locked draft invoice gets the R3 error.)
- **R5.** Outstanding = `invoice_amount − paid_amount`. A payment greater than outstanding is rejected with 400 `Payment amount ({payment_amount}) exceeds outstanding amount ({outstanding})` (amounts rendered as Python `Decimal` strings, e.g. `100.50`); nothing written. A payment exactly equal to outstanding is accepted. If `paid_amount` already exceeds `invoice_amount` (outstanding negative) every payment is rejected. Decimal-precision limits on the input are R5a.
- **R5a.** [BUG-604] `payment_data.payment_amount` cannot carry more than 2 decimal places or more than 13 integer digits — `InvoicePaymentCreate` rejects it with a Pydantic `ValidationError` (422 at the API) before the manager runs; nothing written. *(Today: the schema has no `max_digits`/`decimal_places`, so any number of decimals and any number of integer digits are accepted by `InvoicePaymentCreate`/`InvoicePaymentUpdate`; Postgres silently rounds extra decimals on write, but the overpayment check and the invoice's `payment_status` are decided on the unrounded value — see P2's example. A 14-integer-digit amount also passes the schema today; in the manager it is always rejected by R5 because `invoice_amount` (`Numeric(15,2)`) cannot exceed 13 integer digits.)* *(Fix belongs in `app/schemas/invoice_payment.py`.)*
- **R6.** On success a payment row is created with every field from `payment_data`, plus `workspace_id`, `created_by = user_id`, `is_voided = False`, `voided_at`/`voided_by`/`void_note` `NULL`, and `created_at` set by the database.
- **R7.** The invoice's `paid_amount` increases by `payment_amount`. Its `payment_status` becomes `paid` when the new `paid_amount ≥ invoice_amount`, otherwise `partial` (a positive payment always leaves `paid_amount > 0`). Flushed.
- **R8.** No other invoice field changes (`invoice_status`, `allow_payments`, `updated_by` untouched).
- **R9.** Exactly one financial audit row is written: `entity_type` `payment`, `entity_id` = new payment id, `action_type` `created`, `performed_by` = `user_id`, `related_entity_type` `invoice`, `related_entity_id` = invoice id, `workspace_id` = `workspace_id`.
- **R10.** That audit row's `changes` = `{"after": {payment_amount, payment_date, payment_method}}` (snapshot format per `extract_relevant_fields`); when the invoice's `payment_status` changed it also has `"invoice_status_changed": {"before": <old>, "after": <new>}`, otherwise that key is absent.
- **R10a.** [BUG-603] That audit row's `ip_address`/`user_agent` are the caller's client IP and user agent, from the new `ip_address`/`user_agent` parameters (`None` when not supplied — e.g. no request context). *(Today: both always `NULL`.)*
- **R11.** The audit `description` is `Payment of ${payment_amount} recorded for invoice ID {invoice_id}` with `, status changed to {new_status}` appended only when the status changed. The amount is rendered exactly as passed in (e.g. input `100.5` → `$100.5`).
- **R12.** Exactly one invoice event is written: `event_type` `payment_recorded`, `description` `Payment recorded`, `performed_by` = `user_id`, `metadata_json` = `{"payment_id", "payment_amount": str(input amount), "payment_method" (may be null), "payment_status_before", "payment_status_after"}`.
- **R13.** The invoice's linked order/return is synced afterwards — outcomes per `_sync_linked_order` R1–R8.
- **R14.** Any error in R1–R5 leaves no payment, audit row, event, or invoice change.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| invoice missing / other workspace | `HTTPException` 404 | `Invoice with ID {invoice_id} not found` |
| invoice not `confirmed` | `HTTPException` 400 | `Payments can only be recorded against confirmed invoices (current status: '{status}').` |
| `allow_payments` false | `HTTPException` 403 | `payment_locked_reason` or `Payments are locked for this invoice` |
| amount > outstanding | `HTTPException` 400 | `Payment amount ({amount}) exceeds outstanding amount ({outstanding})` |

**Side effects:** 1 payment row; invoice `paid_amount`, `payment_status` updated; 1 financial audit row; 1 invoice event; linked order/return sync (see `_sync_linked_order`); invoice row locked for the rest of the transaction; flushes, never commits.

---

## `InvoicePaymentManager.update_payment(session, payment_id, payment_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public

**Purpose:** Edit a payment's non-amount details and, when something actually changes, record who changed it — BUG-607.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payment_id` | int | payment to edit |
| `payment_data` | `InvoicePaymentUpdate` | all optional: `payment_amount: Decimal > 0` — [BUG-604] rejects more than 2 decimal places or more than 13 integer digits (422); `payment_date`, `payment_method` ≤ 50, `payment_reference` ≤ 100, `bank_name` ≤ 255, `transaction_id` ≤ 100, `notes`. No `invoice_id` field — a payment cannot be moved to another invoice |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | [BUG-607] editor; stored as the new audit row's `performed_by` and the new invoice event's `performed_by`. *(Requires new parameter — today not accepted.)* |

**Returns:** the same payment object, updated and flushed, not committed.

**Rules:**
- **R1.** A payment id that does not exist, or belongs to another workspace, → 404 `Payment with ID {payment_id} not found`; nothing changed.
- **R2.** When `payment_amount` is given and differs from the stored amount (numeric comparison — `100.5` equals stored `100.50`), → 400 `Cannot change payment amount. Delete and re-create payment instead.`; nothing changed, even if other fields were sent too. When it equals the stored amount the update proceeds.
- **R2a.** [BUG-611] The R2 detail message reads `Cannot change payment amount. Void and re-create payment instead.` (best-practice default, delegated by reviewer). *(Today: `… Delete and re-create payment instead.` — deletion is always refused per BUG-609.)*
- **R3.** [BUG-606] A voided payment (`is_voided = True`) is rejected: 400 `Voided payments cannot be edited`; nothing changed — checked before any field is applied. An active (non-voided) payment proceeds normally; the invoice's status (voided or not) is still not checked. *(Today: a voided payment is updated exactly like an active one — no check exists.)*
- **R3a.** [BUG-606] Precedence: 404 (R1) first, then the voided check (R3), then the amount check (R2) — a voided payment sent a different amount gets 400 `Voided payments cannot be edited` (best-practice default, delegated by reviewer: the terminal state is reported before field-level validation). *(Today: it gets R2's amount error, since R3 does not exist.)*
- **R4.** Every field present in `payment_data` — whether a concrete value or explicit `null` — is considered. A concrete value is written as given (a same-value `payment_amount` rewrites the same value; empty strings `""` are written as given). A field left out of the request body entirely is unchanged. Explicit-`null` handling is R5.
- **R5.** [BUG-608] An explicit `null` for `payment_method`, `payment_reference`, `bank_name`, `transaction_id` or `notes` clears the stored value (sets the column to `NULL`). An explicit `null` for the required `payment_date`, or for `payment_amount`, is ignored — those fields keep their stored value, since they may not be nulled. *(Today: an explicit `null` for any field is ignored — an optional field set once can never be cleared, only overwritten with another non-null value.)*
- **R6.** The invoice (`paid_amount`, `payment_status`) is never touched by an update, and no linked-order sync runs — unlike create/delete/void.
- **R6a.** [BUG-607] When at least one field actually changes value (HR-9) — a concrete value differing from the stored one, or a clearing `null` (R5) that turns a currently non-`NULL` value into `NULL` — one financial audit row is written: `entity_type` `payment`, `entity_id` = payment id, `action_type` `updated`, `performed_by` = `user_id`, `related_entity_type` `invoice`, `related_entity_id` = invoice id, `workspace_id` = `workspace_id` (the caller's, same as `create_payment` R9), `changes` = `{"before": {<changed field>: <old value>, …}, "after": {<changed field>: <new value>, …}}` — both dicts keyed by exactly the changed fields, values in `extract_relevant_fields` snapshot format (a cleared field shows `null` in `after`), mirroring the `{"after": …}` / `{"before": …}` shapes of create and the old delete; `description` is free text and not part of the contract; `ip_address`/`user_agent` `NULL` (not yet reached by BUG-603's fix); and one invoice event: `event_type` `payment_updated`, `description` `Payment updated`, `performed_by` = `user_id`, `metadata_json` = `{"payment_id", "changed_fields": [<names of the fields that changed>]}` — `changed_fields` order is not significant (compare as a set/sorted). (Shape, `workspace_id`, free-text description and unordered `changed_fields`: best-practice defaults, delegated by reviewer.) Given no field actually changes, nothing is logged. *(Today: nothing is ever logged for an update.)* *(Requires new parameter `user_id` on `update_payment`.)*
- **R7.** [BUG-608] An update with no fields (`{}`) changes nothing. An update containing only `null`s changes nothing if none of those fields currently hold a non-`NULL` value to clear (R5); if at least one targets a currently-set `payment_method`/`payment_reference`/`bank_name`/`transaction_id`/`notes`, that field is cleared (R5) and counts as a change for R6a. *(Today: any all-`null` update is a pure no-op, since `null` is always ignored regardless of field.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| payment missing / other workspace | `HTTPException` 404 | `Payment with ID {payment_id} not found` |
| amount given and different | `HTTPException` 400 | `Cannot change payment amount. Delete and re-create payment instead.` — [BUG-611] intended `Cannot change payment amount. Void and re-create payment instead.` |
| payment already voided [BUG-606] | `HTTPException` 400 | `Voided payments cannot be edited` |

**Side effects:** payment row fields updated (per R4/R5/R7) and flushed. When at least one field actually changed, one financial audit row and one `payment_updated` invoice event are also written (R6a, BUG-607). No commit. On error (R1–R3), nothing is written.

---

## `InvoicePaymentManager.list_payments_by_invoice(session, invoice_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List an invoice's payments with the display name of whoever recorded each one.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `invoice_id` | int | invoice whose payments are listed |
| `workspace_id` | int | caller's workspace |
| `skip` | int, default 0 | rows to skip (endpoint enforces `≥ 0`) |
| `limit` | int, default 100 | max rows (endpoint enforces `1 ≤ limit ≤ 1000`; the manager itself does not check) |

**Returns:** list of `(payment, created_by_name)` tuples; `created_by_name` is the recording user's profile `name`, or `None` when `created_by` is null or the profile has no name.

**Rules:**
- **R1.** An invoice id that does not exist, or belongs to another workspace, → 404 `Invoice with ID {invoice_id} not found`.
- **R2.** Only payments with this `invoice_id` and this `workspace_id` are returned; an existing invoice with no payments returns `[]`.
- **R3.** Voided payments are included, with their void fields.
- **R4.** [BUG-600] Order: `payment_date` descending, then `id` descending, applied before `skip`/`limit`. *(Today: ordered by `payment_date` descending only; payments on the same date have no fixed tie-breaker, so paging can repeat or skip them.)*
- **R5.** `skip`/`limit` apply to that ordered list: at most `limit` tuples, starting after `skip`.
- **R6.** Invoice `invoice_status` does not matter (payments of a voided or draft invoice are listed).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| invoice missing / other workspace | `HTTPException` 404 | `Invoice with ID {invoice_id} not found` |

**Side effects:** none.

---

## `InvoicePaymentManager.delete_payment(session, payment_id, workspace_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public

**Purpose:** [BUG-609] Refuse to remove a payment — payments are accounting records and are never hard-deleted; void instead. *(Today: permanently removes a payment and recomputes its invoice's totals from the remaining active payments.)*

**Inputs:** `payment_id: int`, `workspace_id: int`, `user_id: int` (kept on the signature; no longer used for an audit `performed_by` or sync actor once BUG-609 lands, since neither runs).

**Returns:** [BUG-609] never returns normally — every call raises. *(Today: the deleted `InvoicePayment` object, deleted state in the session, its attributes as they were before deletion.)*

**Rules:**
- **R1.** A payment id that does not exist, or belongs to another workspace, → 404 `Payment with ID {payment_id} not found`; nothing changed.
- **R2.** [BUG-609] Any payment that exists — active or already voided, on any invoice including a voided one — is refused: 400 `Payments cannot be deleted — void them instead`; nothing changed (no payment removed, no invoice field touched, no audit row, no invoice event, no linked-order sync). *(Today, before this fix: after R1's existence check, the invoice is looked up within `workspace_id` [404 `Invoice with ID {invoice_id} not found` if missing — reachable only with inconsistent data, since the payment's FK otherwise guarantees the invoice exists]; the payment row is permanently removed; the invoice's `paid_amount` is set to the sum of `payment_amount` of its remaining non-voided payments [`0.00` when none remain] and `payment_status` recomputed — `paid` when that total ≥ `invoice_amount`, else `partial` when > 0, else `unpaid`; one financial audit row is written [`entity_type` `payment`, `action_type` `deleted`, `changes` = `{"before": snapshot}` of the deleted payment, `description` `Payment of ${amount} deleted from invoice ID {invoice_id}`]; a second audit row [`entity_type` `invoice`, `action_type` `status_changed`] is written only when `payment_status` changed; no invoice event is written; the linked order/return is synced per `_sync_linked_order`. None of this is reachable once this fix lands — see Q4 and Q5.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| payment missing / other workspace | `HTTPException` 404 | `Payment with ID {payment_id} not found` |
| payment exists, any state [BUG-609] | `HTTPException` 400 | `Payments cannot be deleted — void them instead` |

**Side effects:** [BUG-609] none — every call ends in 404 or 400, never a mutation.

---

## `InvoicePaymentManager.void_payment(session, payment_id, workspace_id, user_id, void_note, ip_address=None, user_agent=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** Void a payment (kept as a record, excluded from totals) and recompute the invoice's totals.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payment_id` | int | payment to void |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | stored as `voided_by`; audit/event actor |
| `void_note` | str | [BUG-605] reason; `VoidPaymentRequest.void_note` strips leading/trailing whitespace and requires length ≥ 1 after stripping (422 otherwise) — the manager only ever receives a non-blank, trimmed value and stores it exactly as given. *(Today: the schema requires length ≥ 1 but does not trim, so `"   "` passes; the manager stores whatever it receives.)* |
| `ip_address` | `str \| None` | [BUG-603] caller's client IP address, written to the audit row's `ip_address`. *(Requires new parameter — today not accepted.)* |
| `user_agent` | `str \| None` | [BUG-603] caller's user agent, written to the audit row's `user_agent`. *(Requires new parameter — today not accepted.)* |

**Returns:** the voided payment, flushed, not committed.

**Rules:**
- **R1.** A payment id that does not exist, or belongs to another workspace, → 404 `Payment with ID {payment_id} not found`; nothing changed.
- **R2.** An already-voided payment → 400 `Payment is already voided`; nothing changed.
- **R3.** If the payment's invoice is not found in `workspace_id` → 404 `Invoice with ID {invoice_id} not found`; nothing changed (inconsistent-data only, as `delete_payment` R2's old behavior).
- **R4.** The invoice's `invoice_status` and `allow_payments` are not checked.
- **R5.** The payment gets `is_voided = True`, `voided_at` = current UTC time (`utcnow()`), `voided_by = user_id`.
- **R6.** [BUG-605] `void_note` is stored exactly as given, already a non-blank, trimmed value (see Inputs). *(Today: whatever the schema let through — including whitespace-only — is stored unchanged.)*
- **R7.** Invoice `paid_amount` and `payment_status` are recomputed: the sum of `payment_amount` of remaining non-voided payments in the same workspace (`0.00` when none remain), `payment_status` set to `paid` when that total ≥ `invoice_amount`, else `partial` when > 0, else `unpaid`.
- **R8.** Flushed, not committed; the payment row stays.
- **R9.** [BUG-601] The payment and its invoice are read under a row lock: the invoice row is read `FOR UPDATE` first (before checking whether the payment is already voided), then the payment is re-read; a concurrent voider that loses the race sees `is_voided = True` already set and gets R2's 400, and a concurrent `create_payment`/`delete_payment` on the invoice is not lost. *(Today: no lock is taken by this method.)*
- **R9a.** [BUG-601] Precedence: payment 404 (R1) first, then invoice 404 (R3, since the invoice is locked before the voided check), then already-voided (R2) — an already-voided payment whose invoice is missing gets 404 `Invoice with ID {invoice_id} not found` (best-practice default, delegated by reviewer; follows from R9's ordering). *(Today: the voided check runs before the invoice lookup, so it gets 400 `Payment is already voided`.)*
- **R10.** One financial audit row: `entity_type` `payment`, `entity_id` = payment id, `action_type` `voided`, `performed_by` = `user_id`, `related_entity_type` `invoice`, `related_entity_id` = invoice id, `workspace_id` = `workspace_id` (the caller's).
- **R11.** Its `changes` = `{"payment_voided": {payment_amount, payment_date, payment_method}}` plus `"invoice_payment_status": {"before", "after"}` only when the invoice's `payment_status` changed; `description` = `Payment of ${stored amount} voided for invoice ID {invoice_id}. Reason: {void_note}`.
- **R12.** [BUG-603] `ip_address`/`user_agent` on that audit row are the caller's client IP and user agent, from the new `ip_address`/`user_agent` parameters (`None` when not supplied). *(Today: both always `NULL`.)*
- **R13.** One invoice event: `event_type` `payment_voided`, `description` `Payment voided`, `performed_by` = `user_id`, `metadata_json` = `{"payment_id", "payment_amount": str(stored amount), "payment_method", "void_note", "payment_status_before", "payment_status_after"}` (before/after present even when equal).
- **R14.** The invoice's linked order/return is synced afterwards — per `_sync_linked_order` R1–R8.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| payment missing / other workspace | `HTTPException` 404 | `Payment with ID {payment_id} not found` |
| already voided | `HTTPException` 400 | `Payment is already voided` |
| invoice missing (inconsistent data) | `HTTPException` 404 | `Invoice with ID {invoice_id} not found` |

**Side effects:** payment void fields set; invoice `paid_amount`/`payment_status` recomputed; 1 audit row; 1 invoice event; linked order/return sync; flushes, never commits.

---

## `InvoicePaymentManager._sync_linked_order(session, invoice, user_id)`
**Shape:** helper
**Persistence:** writes
**Visibility:** internal (used by: `create_payment`, `void_payment` — no longer called by `delete_payment` once BUG-609 lands)

**Purpose:** Push the invoice's paid/unpaid state to the purchase order, sales order, or return (credit note) it belongs to.

**Inputs:** `invoice: AccountInvoice` (already updated), `user_id: int | None` (event actor).

**Returns:** `None`.

"Paid" below means the linked invoice's `payment_status` is exactly `paid`.

**Rules:**
- **R1.** An invoice with `order_id` `NULL` → nothing happens (regardless of `order_type`).
- **R2.** `order_type` `purchase_order` and a purchase-order return in the invoice's workspace has `invoice_id` = this invoice → that return's `paid` flag is set to (invoice is paid) and flushed; no event is written; no purchase order is touched, even if one also references this invoice. If `paid` already has that value, nothing changes.
- **R3.** `order_type` `sales_order` and a sales-order return in the invoice's workspace has `invoice_id` = this invoice → same as R2 for the sales-order return.
- **R4.** `order_type` `purchase_order`, no such return → the purchase order in the invoice's workspace whose `invoice_id` = this invoice (not the invoice's `order_id`) is looked up. If none, nothing happens.
- **R5.** For that purchase order: `paid` is set to (invoice is paid). If the value changed, it is flushed and one purchase-order event is written: `event_type` `payment_status_synced`, `description` `Order marked paid from linked invoice` / `Order marked unpaid from linked invoice`, `performed_by` = `user_id`, `metadata_json` `{"paid": true|false}`. If unchanged, nothing is written.
- **R6.** `order_type` `sales_order`, no such return → same as R4–R5 for the sales order whose `invoice_id` = this invoice (sales-order event, same type/description/metadata).
- **R7.** Any other `order_type` (`expense_order`, `work_order`, `NULL`, anything else) with a non-null `order_id` → nothing happens.
- **R8.** Only rows of the invoice's own `workspace_id` are considered; a return/order in another workspace that references the same invoice id is not touched.

**Errors:** none raised by this helper.

**Side effects:** at most one `paid` flag updated on a return / PO / SO; at most one `payment_status_synced` order event (PO/SO only); flush.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 61–69 | invoice query scoped by id + workspace, `FOR UPDATE` | `create_payment` R1, R2 |
| 70 | invoice not found | `create_payment` R1 |
| 77 | `invoice_status` not `confirmed` | `create_payment` R3 |
| 84 | `allow_payments` falsy | `create_payment` R4 |
| 85 | `payment_locked_reason` falsy (`None`/`""`) → default text | `create_payment` R4 |
| 93 | amount > outstanding (equal passes) | `create_payment` R5 |
| schema (`app/schemas/invoice_payment.py`) | `payment_amount` decimal-place / digit-count limit [BUG-604] | `create_payment` R5a |
| 107 | payment create | `create_payment` R6 |
| dao `update_paid_amount` 486 | invoice found (always, same row) | `create_payment` R7 |
| dao 489 | paid ≥ invoice_amount → `paid` | `create_payment` R7 |
| dao 491 | paid > 0 → `partial` | `create_payment` R7 |
| dao (implicit else) | paid ≤ 0 → status unchanged (unreachable: amount > 0) | `create_payment` R7 |
| 124 | status changed → add `invoice_status_changed` | `create_payment` R10 |
| 127 | `log_financial_audit` call — `ip_address`/`user_agent` passed through [BUG-603] | `create_payment` R10a |
| 138 | status changed → description suffix | `create_payment` R11 |
| 141 | invoice event | `create_payment` R12 |
| 189 | payment not found | `update_payment` R1 |
| 196 | amount truthy and ≠ stored | `update_payment` R2 |
| 196 | amount given and equal → proceed | `update_payment` R2 |
| 196 (message) | amount-change error text [BUG-611] | `update_payment` R2a |
| fix location | `is_voided` check before any field is applied, before the amount check [BUG-606] | `update_payment` R3, R3a |
| 203 | `exclude_unset=True` (no `exclude_none` — clearable fields distinguish explicit `null` from omitted) [BUG-608] | `update_payment` R4, R5 |
| base `update` 114 | `hasattr` field (always true for schema fields) | `update_payment` R4 |
| fix location | field-actually-changed detection → audit row + event [BUG-607] | `update_payment` R6a |
| 264 | invoice not found | `list_payments_by_invoice` R1 |
| dao `get_by_invoice` 28 | outer join on creator → name or `None` | `list_payments_by_invoice` Returns |
| dao `get_by_invoice` 33–35 | order by `payment_date desc`, `id desc` [BUG-600], offset/limit | `list_payments_by_invoice` R4, R5 |
| 299 | payment not found | `delete_payment` R1 |
| 305–365 | invoice lookup, hard delete, recompute, audit rows, sync — today only, superseded by BUG-609 | `delete_payment` R2 |
| 382 | payment not found | `void_payment` R1 |
| 385 | already voided | `void_payment` R2 |
| 392 | invoice not found | `void_payment` R3 |
| fix location | invoice `FOR UPDATE` lock before the voided check, payment re-read after [BUG-601] | `void_payment` R9, R9a |
| 418 | audit row `workspace_id` | `void_payment` R10 |
| 399–403 | set void fields | `void_payment` R5, R6 |
| 410 / 412 / 414 | recompute status paid / partial / unpaid | `void_payment` R7 |
| 418 | `log_financial_audit` call — `ip_address`/`user_agent` passed through [BUG-603] | `void_payment` R12 |
| 429–432 | status changed → add `invoice_payment_status` | `void_payment` R11 |
| 437 | invoice event | `void_payment` R13 |
| 463 | `order_id is None` → return | `_sync_linked_order` R1 |
| 469 | `order_type == purchase_order` (return check) | `_sync_linked_order` R2 |
| 478 | PO return found → sync + return | `_sync_linked_order` R2 |
| PO-return mgr 93 / 97 / 98 | return has invoice_id; paid = status == `paid`; unchanged → no write | `_sync_linked_order` R2 |
| 481 | `order_type == sales_order` (return check) | `_sync_linked_order` R3 |
| 490 | SO return found → sync + return | `_sync_linked_order` R3 |
| 494 | `purchase_order` → PO sync | `_sync_linked_order` R4 |
| PO mgr 292 | PO found by invoice_id | `_sync_linked_order` R4 |
| PO mgr 304 / 307 | paid = status == `paid`; unchanged → nothing | `_sync_linked_order` R5 |
| PO mgr 311 | label Paid / Unpaid | `_sync_linked_order` R5 |
| 503 | `sales_order` → SO sync | `_sync_linked_order` R6 |
| SO mgr 718 / 726 / 728 | SO found; paid computed; unchanged → nothing | `_sync_linked_order` R6 |
| 503 (else) | any other order_type → nothing | `_sync_linked_order` R7 |
| dao lookups (return/PO/SO) | filter by `invoice.workspace_id` | `_sync_linked_order` R8 |

## Gap log
- G1 (invoice_payment_manager.cases.md gap 1) — Fact + decision — Overview note: BUG-141's intended format (fixed-point string) stated; money inside audit `changes` compared numerically in this module (best-practice default, delegated by reviewer).
- G2 (cases gap 2) — Intent (decided, no question) — `update_payment` R6a: `changes` = `{"before": {…}, "after": {…}}` of changed fields; audit `description` free text, not asserted; `changed_fields` order not significant (best-practice default, delegated by reviewer).
- G3 (cases gap 3) — Fact — `void_payment` R10 gains `workspace_id` = caller's (code passes `workspace_id`); `update_payment` R6a gains the same (best-practice default, delegated by reviewer).
- G4 (cases gap 4) — Contradiction — `update_payment` R2a [BUG-611]: message becomes `… Void and re-create payment instead.`; review Q7 added already resolved (best-practice default, delegated by reviewer); errors table annotated.
- G5 (cases gap 5) — Intent (decided, no question) — `update_payment` R3a (404 → voided → amount) and `void_payment` R9a (payment 404 → invoice 404 → already voided, with Today note) (best-practice default, delegated by reviewer).
- G6 (cases gap 6) — Fact + test mechanics — Overview note: `utcnow` is naive UTC; importing modules listed; invoice-event `created_at` default is bound at import, so patch `app.utils.time.datetime` or do not assert it exactly.
- G7 (cases gap 7) — Test mechanics — Overview note: insert same-date rows so insertion order differs from intended `id desc`.
- G8 (cases gap 8) — Test mechanics / contradiction — replaced the second-connection lock note (impossible with uncommitted setup rows) with SQL capture + in-session race simulation; real race moved to Integration-only; table names `account_invoices`, `invoice_payments` given.
- G9 (cases gap 9) — Fact — `create_payment` R5a Today note: schema has no digit cap today, so 14-integer-digit amounts pass the schema (xfail stays valid); in the manager they always hit R5.
- G10 (cases gap 10) — Fact — Overview note: `order_type` `String(30)` nullable, `invoice_status`/`payment_status` `String(20)`, no CHECK/enum — all assumed values are storable.
