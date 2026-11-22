# Spec — `app/managers/payment_transaction_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Q1. A refused checkout start leaves no record and is returned as a 502 error — 🐞 BUG-019
**Background:** Every checkout attempt starts by asking SSLCommerz for a payment session. The API response schema for this call (`InitiatePaymentResponse`) has `status` and `failed_reason` fields, which suggests a refused start was meant to come back as a normal response. The ledger model is documented as "one row per checkout attempt".
**What happens today:** If the gateway refuses the session, the call fails with HTTP 502. No transaction row and no event are written, and the `failed_reason` field is never filled in.
**Example:** The store credentials are wrong and SSLCommerz answers `FAILED`, "Store is de-active". The user gets `502 "SSLCommerz session initiation failed: Store is de-active"`. The workspace's payment ledger shows nothing, so an admin has no record that the attempt was made or why it failed.
**Rules affected:** `initiate_payment` R3
**Answer:** bug — every checkout attempt is recorded (HR-13): a refused session start saves a transaction with status `INIT_FAILED` and `failed_reason` from the gateway, writes an event, and is returned normally through the `status`/`failed_reason` fields of the response instead of raising 502 (best-practice default, delegated by reviewer)
**Resolution:** a refused start is stored as an `INIT_FAILED` transaction with the gateway's reason, logs one event, and is returned without raising; requires a new `failed_reason` column and the service to fill the response field. Per HR-13. (best-practice default, delegated by reviewer) Rules: `initiate_payment` R3, R5a, R7a.

### Q2. Correlation fields `value_a`–`value_d` are never sent to the gateway — 🐞 BUG-020
**Background:** The model and the request schema describe `value_a`..`value_d` as mirroring "SSLCommerz's own custom-metadata fields (echoed back unchanged by the gateway on every callback)", so that callers (for example future subscription-renewal logic) can attach their own correlation data.
**What happens today:** The four values are stored on our transaction row, but they are not included in the session request sent to SSLCommerz, so the gateway never gets them and can never echo them back.
**Example:** A caller starts a payment with `value_a = "plan:pro;months:12"`. Our row has `value_a = "plan:pro;months:12"`, but the gateway session was created without it, and every redirect/IPN callback for this payment arrives without a `value_a`. The data can only be recovered by looking up our own row by `tran_id`.
**Rules affected:** `initiate_payment` R1
**Answer:** bug — `value_a`..`value_d` are sent to the gateway in the session request (best-practice default, delegated by reviewer)
**Resolution:** `value_a`..`value_d` are included in the gateway session request (requires new fields on `InitSessionRequest`). (best-practice default, delegated by reviewer) Rules: `initiate_payment` R1a.

### Q3. Amounts with more than 2 decimal places (or too large to store) are accepted — 🐞 BUG-021
**Background:** The amount column holds at most 13 digits before the decimal point and exactly 2 after it; Postgres silently rounds extra decimals when storing. The request schema only requires `amount > 0`. The gateway session is created *before* the row is saved. Later, the gateway's reported amount is compared exactly with the stored amount.
**What happens today:** (a) An amount like `10.005` is sent to the gateway as `10.005` but stored as `10.01`; when the gateway later reports `10.005` (or its own rounding), the payment is marked failed with "Amount mismatch". (b) An amount of `10000000000000` (10^13) or more makes the save fail with a database error after the gateway session already exists.
**Example:** A user pays `10.005 BDT`. The checkout page opens and the customer pays. The IPN arrives, the gateway reports `10.005`, our row says `10.01` → status `VALIDATED_FAILED`, although the customer was charged.
**Rules affected:** `initiate_payment` R9
**Answer:** bug — the request schema rejects amounts with more than 2 decimal places or more than 13 integer digits (422), before the gateway is called (best-practice default, delegated by reviewer)
**Resolution:** `InitiatePaymentRequest` rejects amounts with > 2 decimals or > 13 integer digits; fix belongs in `app/schemas/payment_transaction.py`. (best-practice default, delegated by reviewer) Rules: `initiate_payment` R9a.

### Q4. The currency code is not validated or normalised — 🐞 BUG-022
**Background:** The request schema only requires `currency` to be exactly 3 characters (default `"BDT"`). It is stored exactly as typed. When the gateway later reports the currency, it is compared case-sensitively with what we stored.
**What happens today:** `"bdt"`, `"XYZ"` or `"12 "` are accepted and stored as-is. A payment started with `"bdt"` is marked failed with "Currency mismatch" if the gateway reports `"BDT"`.
**Example:** A client sends `{"amount": 500, "currency": "bdt", ...}`. The session is created, the customer pays, the gateway reports currency `"BDT"` → status `VALIDATED_FAILED` with "Currency mismatch: expected bdt, gateway reported BDT", although the customer was charged.
**Rules affected:** `initiate_payment` R10, `_apply_validation_result` R7
**Answer:** bug — currency is upper-cased and must be one of the supported currencies (at least `BDT`, `USD`); anything else is rejected by the schema (422) (best-practice default, delegated by reviewer)
**Resolution:** the request schema upper-cases `currency` and accepts only supported codes (`BDT`, `USD`); fix belongs in `app/schemas/payment_transaction.py`. The gateway comparison stays exact against the stored upper-case code. (best-practice default, delegated by reviewer) Rules: `initiate_payment` R10a, `_apply_validation_result` R7.

### Q5. A val_id that is unrecognised or belongs to another transaction permanently fails this one — 🐞 BUG-023
**Background:** The `/payments/success` and `/payments/fail` redirect endpoints are public (no login, no signature check); anyone who knows a `tran_id` can post a `val_id` for it. The code asks the gateway to validate that `val_id`. Once a transaction leaves `INITIATED`, every later callback is ignored as a duplicate. A code comment says a foreign `val_id` must "never [be] apply[ed] to this row".
**What happens today:** If the gateway says the `val_id` is unknown (`INVALID_TRANSACTION`), or that it belongs to a different transaction, this transaction is set to `VALIDATED_FAILED` for good. The genuine result that arrives afterwards is ignored.
**Example:** Transaction T1 (500 BDT) is waiting for the customer. Someone posts to `/payments/success` with `tran_id=T1` and either a made-up `val_id` or the real `val_id` of their own transaction T2. T1 becomes `VALIDATED_FAILED`. The customer then pays; the genuine IPN for T1 is logged as "Duplicate ipn callback ignored; transaction already VALIDATED_FAILED". The customer is charged, and the ledger shows the payment as failed.
**Rules affected:** `_apply_validation_result` R1, R4; `finalize_from_gateway` R3
**Answer:** bug — an unknown `val_id` (gateway `INVALID_TRANSACTION`) or one resolving to another `tran_id` is logged as an event and ignored; the transaction stays `INITIATED` and a later genuine result still finalizes it (HR-11) (best-practice default, delegated by reviewer)
**Resolution:** a foreign or unknown `val_id` changes nothing on the transaction; one rejection event is logged and a later genuine result still finalizes it. Per HR-11. (best-practice default, delegated by reviewer) Rules: `_apply_validation_result` R1a, R2a; `finalize_from_gateway` R5a; `reconcile_stuck_transactions` R5b.

### Q6. A missing amount or currency in the gateway's answer counts as a match — 🐞 BUG-024
**Background:** After the gateway confirms a payment, the code checks that the amount and currency it reports equal ours, to catch tampered or wrong payments. The gateway result allows both fields to be empty.
**What happens today:** If the gateway answer has no amount, the amount check is skipped. If it has no currency (or an empty one), the currency check is skipped. The payment can then be marked `VALIDATED_SUCCESS` without the amount or currency ever being confirmed.
**Example:** Transaction for 5000 BDT. The gateway validation answer is `status=VALID` with no amount field. The transaction becomes `VALIDATED_SUCCESS`, with no check that 5000 BDT was actually paid.
**Rules affected:** `_apply_validation_result` R6, R8
**Answer:** bug — if a VALID gateway answer is missing the amount or currency, the transaction goes to `RISK_HOLD` for manual review, not `VALIDATED_SUCCESS` (HR-12) (best-practice default, delegated by reviewer)
**Resolution:** a VALID answer with no amount or no currency puts the transaction in `RISK_HOLD`. A definite mismatch on the field that is present still fails it. Per HR-12. (best-practice default, delegated by reviewer) Rules: `_apply_validation_result` R6, R8.

### Q7. A cancelled payment ends as `CANCELLED` or `VALIDATED_FAILED` depending on which message arrives first — 🐞 BUG-025
**Background:** When a customer cancels on the gateway page, two messages come back: the browser redirect to `/payments/cancel`, which is applied directly as `CANCELLED`, and the IPN webhook, which carries a `val_id`. When the gateway validates that `val_id` it reports status `CANCELLED`, and the code treats any status other than `VALID`/`VALIDATED` as `VALIDATED_FAILED`. Whichever message arrives first decides the final status.
**What happens today:** The same customer action produces `CANCELLED` if the browser redirect wins, and `VALIDATED_FAILED` if the IPN wins (for example because the tab was closed).
**Example:** Two customers both click "Cancel" on the gateway page. Customer A's browser returns normally → A's transaction is `CANCELLED`. Customer B closed the tab, so only the IPN arrives → B's transaction is `VALIDATED_FAILED`. The ledger shows the two cancellations with different statuses.
**Rules affected:** `_apply_validation_result` R4, `mark_terminal_without_validation` R3
**Answer:** bug — a gateway-reported `CANCELLED` sets status `CANCELLED` regardless of which channel delivers it (best-practice default, delegated by reviewer)
**Resolution:** a gateway-validated `CANCELLED` sets status `CANCELLED` on every channel (live callback and sweep). The cancel redirect keeps setting `CANCELLED`, as today. (best-practice default, delegated by reviewer) Rules: `_apply_validation_result` R4b; `finalize_from_gateway` R3c; `mark_terminal_without_validation` R3 unchanged in status.

### Q8. An unverified fail/cancel redirect blocks a later verified success — 🐞 BUG-026
**Background:** Fail and cancel redirects, and a success redirect with no `val_id`, are posted by the customer's browser and cannot be checked with the gateway. The code applies them directly as final (`VALIDATED_FAILED` or `CANCELLED`). After that, every later callback for the transaction, including a gateway-verified IPN, is ignored as a duplicate.
**What happens today:** Whichever message arrives first wins, even if it is unverified and a later message is verified.
**Example:** A customer pays successfully in one tab and then presses "Cancel" in an older tab of the same checkout (or anyone posts `tran_id=T1` to `/payments/cancel`). T1 becomes `CANCELLED`. The gateway's IPN then arrives with a valid, paid `val_id` and is logged as "Duplicate ipn callback ignored; transaction already CANCELLED". The customer is charged, and the ledger says cancelled.
**Rules affected:** `mark_terminal_without_validation` R2, R3; `finalize_from_gateway` R3
**Answer:** bug — unverified outcomes (fail/cancel redirects, success redirect without `val_id`) are not final: a later gateway-verified result replaces them (HR-11) (best-practice default, delegated by reviewer)
**Resolution:** an outcome set by `mark_terminal_without_validation` is recorded as unverified. A later `val_id` callback validates it with the gateway and replaces it; another unverified redirect is still ignored as a duplicate. Requires recording whether an outcome was gateway-verified. Per HR-11. (best-practice default, delegated by reviewer) Rules: `finalize_from_gateway` R3a; `mark_terminal_without_validation` R3a; `_apply_validation_result` R12 (marker storage: Q16).

### Q9. A genuine result arriving after the transaction was marked `EXPIRED` is ignored — 🐞 BUG-027
**Background:** A scheduled sweep marks transactions that are still `INITIATED` after 30 minutes as `EXPIRED` when the gateway does not report them as paid. `EXPIRED` is treated like any other final status, so later callbacks are ignored.
**What happens today:** If the customer completes the payment after the sweep ran (for example a slow bank OTP step, or a delayed IPN), the success callback is logged as a duplicate and the transaction stays `EXPIRED`.
**Example:** A checkout starts at 10:00. The sweep at 10:35 asks the gateway, gets "not attempted" and sets `EXPIRED`. The customer finishes paying at 10:37. The IPN with a valid `val_id` is logged as "Duplicate ipn callback ignored; transaction already EXPIRED". The customer is charged, and the ledger says expired.
**Rules affected:** `finalize_from_gateway` R3
**Answer:** bug — a gateway-verified result arriving after `EXPIRED` replaces it (HR-11) (best-practice default, delegated by reviewer)
**Resolution:** `EXPIRED` is not final. A later `val_id` callback is validated with the gateway and replaces it. Per HR-11. (best-practice default, delegated by reviewer) Rules: `finalize_from_gateway` R3b.

### Q10. Event type names differ from the documented list — 🐞 BUG-028
**Background:** Each transaction has an audit trail of events that the detail endpoint returns. The event model documents these types: `initiated, redirect_success, redirect_fail, redirect_cancel, ipn_received, validated_success, validated_failed, risk_hold, risk_resolved, expired, duplicate_ignored`.
**What happens today:** Redirects with a `val_id` are logged as `redirect_success_received` / `redirect_fail_received` (not `redirect_success` / `redirect_fail`). A cancel redirect is logged as `cancelled`, a type that is not in the list, and `redirect_cancel` is never written. A success or fail redirect with no `val_id` is logged as `validated_failed`, the same type used when the gateway really validated a failure, although nothing was validated.
**Example:** A customer cancels. The event history reads `initiated` → `cancelled`. A redirect that lost its `val_id` reads `initiated` → `validated_failed`, which looks identical to a payment the gateway itself declined.
**Rules affected:** `finalize_from_gateway` R4, `mark_terminal_without_validation` R3
**Answer:** bug — events use the documented type names; unverified redirect outcomes get their own event type distinct from gateway-verified `validated_failed` (best-practice default, delegated by reviewer)
**Resolution:** received events are `redirect_success`, `redirect_fail` and `ipn_received`. Unverified redirect outcomes use `redirect_success` / `redirect_fail` / `redirect_cancel`, never `validated_failed`. The names for event types the documented list does not cover were settled in Q15. (best-practice default, delegated by reviewer) Rules: `finalize_from_gateway` R4a; `mark_terminal_without_validation` R3b.

### Q11. Resolving a risk hold does not lock the transaction — 🐞 BUG-029
**Background:** The gateway-callback paths lock the transaction row, so two simultaneous callbacks cannot both finalize it. Resolving a risk hold (owner approves or rejects) reads the row without a lock and then checks that it is still `RISK_HOLD`.
**What happens today:** Two resolve requests arriving at the same moment can both see `RISK_HOLD` and both succeed. The second overwrites the first, and two `risk_resolved` events are recorded.
**Example:** The owner double-clicks "Approve", or two tabs show the same held payment, one approving and one rejecting. Both requests return 200. The final status is whichever wrote last (possibly `VALIDATED_FAILED` after an approval was shown), and the history has two resolutions.
**Rules affected:** `resolve_risk` R6
**Answer:** bug — resolving a risk hold locks the row; a second concurrent resolve sees the new status and gets the normal 400 (HR-10) (best-practice default, delegated by reviewer)
**Resolution:** `resolve_risk` reads the row with a row lock; the loser of a race gets the normal 400. Per HR-10. (best-practice default, delegated by reviewer) Rules: `resolve_risk` R6a.

### Q12. The sweep labels gateway-reported failures and cancellations as `EXPIRED` — 🐞 BUG-030
**Background:** The reconciliation sweep asks the gateway about each stuck transaction by `tran_id`. The gateway can answer `VALID`/`VALIDATED` (paid), or `FAILED`, `CANCELLED`, `EXPIRED`, `UNATTEMPTED`, `INVALID_TRANSACTION`.
**What happens today:** Only `VALID`/`VALIDATED` is used. Every other answer, including a definite `FAILED` or `CANCELLED`, makes the transaction `EXPIRED`.
**Example:** A customer's card is declined and both callbacks are lost. The sweep asks the gateway, which answers `FAILED`. The transaction is set to `EXPIRED`, with the event "No resolution found after 30 minutes (gateway status: FAILED)", instead of `VALIDATED_FAILED`. The same decline delivered live would have produced `VALIDATED_FAILED`.
**Rules affected:** `reconcile_stuck_transactions` R6
**Answer:** bug — the sweep maps gateway statuses: `VALID`/`VALIDATED` → validate as usual, `FAILED` → `VALIDATED_FAILED`, `CANCELLED` → `CANCELLED`; only `UNATTEMPTED`/`EXPIRED`/no result → `EXPIRED` (best-practice default, delegated by reviewer)
**Resolution:** the sweep applies `VALID`/`VALIDATED`/`FAILED`/`CANCELLED` answers through the normal validation outcome. Only the remaining answers (`UNATTEMPTED`, `EXPIRED`, `INVALID_TRANSACTION`, empty/other) give `EXPIRED`. (best-practice default, delegated by reviewer) Rules: `reconcile_stuck_transactions` R5a (R6 unchanged today).

### Q13. The sweep never has a val_id to give the gateway, so the mock gateway can never recover a paid transaction — 🐞 BUG-031
**Background:** The only gateway client implemented today is the mock; the real client raises "not implemented". The mock can only find a transaction's outcome from the `val_id` hint passed to it, and answers `UNATTEMPTED` without one. The sweep passes the row's stored `val_id` as the hint, but a row that is still `INITIATED` never has one: `val_id` is saved only when the transaction leaves `INITIATED`.
**What happens today:** Every stuck transaction the sweep looks at gets `UNATTEMPTED` from the mock and becomes `EXPIRED`, including ones the mock gateway recorded as paid.
**Example:** On the billing trial page a tester pays with "Drop the browser redirect" checked, and the background IPN also fails to arrive. 30 minutes later the sweep runs. The transaction becomes `EXPIRED` although the simulated payment succeeded, so the "reconciliation recovers lost callbacks" scenario cannot be demonstrated.
**Rules affected:** `reconcile_stuck_transactions` R4
**Answer:** bug — the sweep looks transactions up by `tran_id` alone and the mock gateway supports that lookup, so a paid transaction whose callbacks were lost is recovered (best-practice default, delegated by reviewer)
**Resolution:** the sweep queries the gateway by `tran_id` alone. The mock client must answer tran_id-only lookups from its record of completed payments; that fix belongs in `app/integrations/sslcommerz/mock_client.py`. (best-practice default, delegated by reviewer) Rules: `reconcile_stuck_transactions` R4a.

### Q14. One gateway error aborts the whole sweep — 🐞 BUG-032
**Background:** The sweep processes up to 200 stuck transactions, oldest first, calling the gateway once per transaction. The sweep script commits only after all of them are done and rolls back everything if any error occurs.
**What happens today:** If the gateway call raises for any one transaction (timeout, bad response), the whole sweep stops with that error, and the results for the transactions already processed are discarded. Because the oldest transaction is always processed first, a transaction that always errors blocks every future sweep.
**Example:** 150 transactions are stuck. The gateway times out on number 120. Nothing is saved, including the 119 that were resolved. If transaction number 1 always causes an error, no transaction is ever reconciled again.
**Rules affected:** `reconcile_stuck_transactions` R8
**Answer:** bug — one transaction's gateway error is logged as an event and skipped; the rest of the sweep continues and its results are kept (HR-14) (best-practice default, delegated by reviewer)
**Resolution:** an error while handling one candidate is caught. That candidate stays `INITIATED`, gets one error event and is left out of the returned list, and the sweep continues. Requires a per-candidate savepoint. Per HR-14. (best-practice default, delegated by reviewer) Rules: `reconcile_stuck_transactions` R8.

### Follow-up questions

### Q15. Names for the new event types — ✅ resolved
**Background:** Per Q10, events must use the documented type list (`initiated, redirect_success, redirect_fail, redirect_cancel, ipn_received, validated_success, validated_failed, risk_hold, risk_resolved, expired, duplicate_ignored`). The fixes for Q1, Q5, Q7/Q12 and Q14 each need to log an outcome that no documented type covers. Using an existing type would repeat the Q10 problem (for example, a rejected `val_id` logged as `validated_failed` looks like a declined payment).
**What happens after the fixes, as written in the rules:** the rules below use these proposed new types (to be added to the documented list in `app/models/payment_transaction_event.py`):
- `initiation_failed`: the gateway refused to open a checkout session (Q1). Description `Checkout session refused by gateway: <reason>`.
- `validation_rejected`: a `val_id` the gateway does not know, or one belonging to another `tran_id`, ignored (Q5).
- `validated_cancelled`: the gateway itself reported `CANCELLED` during validation or the sweep (Q7, Q12).
- `reconciliation_error`: the sweep failed to handle one transaction and skipped it (Q14). Description `Gateway query failed during reconciliation: <error>`.
**Example:** A customer closes the tab after cancelling, so only the IPN arrives. The history reads `initiated` → `ipn_received` → `validated_cancelled`, and the status is `CANCELLED`.
**Rules affected:** `initiate_payment` R3; `_apply_validation_result` R1a, R2a, R4b; `reconcile_stuck_transactions` R8
**Answer:** ok (best-practice default, delegated by reviewer)
**Resolution:** the four names and descriptions above are adopted; they must be added to the documented event-type list in `app/models/payment_transaction_event.py` alongside the fixes. (best-practice default, delegated by reviewer)

### New questions (from fill-gaps)

### Q16. How the "was this outcome verified by the gateway?" marker is stored, and what it defaults to — 🐞 BUG-026 (detail)
**Background:** The fix for Q8 (BUG-026) makes an outcome set by an unverified redirect (fail/cancel, or success with no `val_id`) replaceable by a later gateway-verified result, while a gateway-verified `VALIDATED_FAILED` or `CANCELLED` stays final. Both outcomes use the same status values, so the transaction needs a new field that records which kind it is. The code has no such field today, and Q8 only said "e.g. a new column". `VALIDATED_SUCCESS`, `RISK_HOLD`, `INIT_FAILED` and `EXPIRED` do not need it: the first three are always final, and `EXPIRED` is always replaceable (Q9).
**What happens today:** Nothing records the difference. The spec rules refer to "the verified marker", but its name, type and default are not decided. This also leaves open what a transaction counts as when it has status `VALIDATED_FAILED` or `CANCELLED` and nobody set the marker (for example, rows that exist before the migration, or a row inserted directly).
**Example:** A row is created with status `CANCELLED` and no marker value. Then an IPN arrives with a paid `val_id`. With a default of "unverified", the payment is validated and the row becomes `VALIDATED_SUCCESS`. With a default of "verified", the IPN is logged as a duplicate and the row stays `CANCELLED`.
**Suggested answer:** bug — new column `outcome_verified` BOOLEAN NOT NULL, default `false` (server default too). `_apply_validation_result` R4–R10 set it to `true`. A rejection (R1a/R2a) leaves it unchanged. `mark_terminal_without_validation` and the sweep's `EXPIRED` leave it `false`, and `resolve_risk` leaves it unchanged (it is already `true`, because `RISK_HOLD` only comes from gateway validation). A `VALIDATED_FAILED`/`CANCELLED` row with the marker unset therefore counts as unverified, which is the safe side under HR-11 because a later verified result can still correct it. The migration backfills `true` for existing `VALIDATED_FAILED` rows whose last outcome event is a gateway validation (not unit-tested).
**Rules affected:** `_apply_validation_result` R12; `finalize_from_gateway` R3, R3a, R3c; `mark_terminal_without_validation` R3a
**Answer:** ok — new column `outcome_verified` BOOLEAN NOT NULL default `false`; unset counts as unverified (best-practice default, delegated by reviewer)
**Resolution:** the suggested answer is adopted as part of the BUG-026 fix (same root cause, no new bug ID). New column `payment_transactions.outcome_verified` BOOLEAN NOT NULL, default `false` (Python and server default). A new transaction starts `false`. `_apply_validation_result` R4–R10 set it to `true`; a rejection leaves it unchanged; `mark_terminal_without_validation`, the sweep's `EXPIRED` and `resolve_risk` do not change it. A `VALIDATED_FAILED`/`CANCELLED` row with `outcome_verified = false` is unverified and replaceable. The migration backfill is not unit-tested. (best-practice default, delegated by reviewer) Rules: `_apply_validation_result` R12; `finalize_from_gateway` R3, R3a; `mark_terminal_without_validation` R3a.

### Q17. How the error is written in the `reconciliation_error` event — 🐞 BUG-032 (detail)
**Background:** Per Q14/Q15, when the sweep fails on one transaction it logs an event `reconciliation_error` with description `Gateway query failed during reconciliation: <error>`, then moves on. The format of `<error>` was not decided. Errors can be a gateway timeout with a short message, or a database error with a long message that includes SQL. Some exceptions have an empty message.
**What happens today:** No such event exists (today the exception aborts the sweep, per BUG-032), so there is no current format to keep.
**Example:** The gateway client raises `TimeoutError("gateway timeout")` for transaction T7. With `str(error)`, the event reads `Gateway query failed during reconciliation: gateway timeout`. If it raised `TimeoutError()` with no message, the event would read `Gateway query failed during reconciliation: ` with nothing after the colon.
**Suggested answer:** bug — `<error>` is `str(exc)`, or the exception class name (e.g. `TimeoutError`) when `str(exc)` is empty.
**Rules affected:** `reconcile_stuck_transactions` R8
**Answer:** ok — `str(exc)`, or the exception class name when that is empty (best-practice default, delegated by reviewer)
**Resolution:** the suggested answer is adopted as part of the BUG-032 fix (same root cause, no new bug ID): `{error}` is `str(exc)`, or `type(exc).__name__` when `str(exc)` is `""`. (best-practice default, delegated by reviewer) Rules: `reconcile_stuck_transactions` R8.

## Overview
Business logic for SSLCommerz checkout transactions. It starts a checkout session (recording the attempt even when the gateway refuses), and it finalizes a transaction from a browser redirect or an IPN webhook, using a row lock so two callbacks cannot both apply. A gateway-verified outcome is final. An unverified outcome (a redirect with no `val_id`, or `EXPIRED` from the sweep) can be replaced by a later verified one. It also covers owner resolution of risk holds, and a reconciliation sweep that closes transactions no callback ever resolved. Callers: `PaymentTransactionService` (commits/rolls back) for initiate, the callbacks and resolve-risk; `scripts/reconcile_payments.py` (commits at the end) for the sweep. Invariants it is meant to protect: once verified, a transaction's outcome never changes (except risk-hold resolution); only the gateway's server-to-server answer can mark a payment successful; the amount and currency must be confirmed to match what was requested; input that fails verification never changes a transaction; every attempt and every state change leaves an audit event. The manager never commits; the DAOs and the manager flush.

**Callables:** 8 specified · 1 not specified
**Externals to mock:** SSLCommerz (patch `app.managers.payment_transaction_manager.get_sslcommerz_client`; the client methods used are `init_session`, `validate`, `query_by_tran_id`); `utcnow` (patch `app.managers.payment_transaction_manager.utcnow`; it drives `validated_at`, `risk_resolved_at` and the sweep cutoff. `initiated_at`, `created_at` and `updated_at` come from the model default `app.models.payment_transaction.utcnow`, and event `created_at` from `app.models.payment_transaction_event.utcnow`, which are separate patch targets); `secrets.token_hex` (patch `app.managers.payment_transaction_manager.secrets.token_hex` only to force `tran_id` collisions)
**Gateway client interface** (`app/integrations/sslcommerz/client.py`; all three are plain dataclasses):
- `init_session(req: InitSessionRequest) -> InitSessionResult`. It takes one positional argument, a single `InitSessionRequest` object. `InitSessionRequest` has the fields `tran_id: str`, `amount: Decimal`, `currency: str`, `success_url`, `fail_url`, `cancel_url`, `ipn_url`, `cus_name`, `cus_email`, `cus_phone: str`, `product_name: str = "Workspace Subscription"`, `product_category: str = "subscription"`. Per BUG-020 it will also get `value_a`..`value_d: str | None = None`, which it does not have today. `InitSessionResult(status: str, session_key: str | None = None, gateway_page_url: str | None = None, failed_reason: str | None = None)`.
- `validate(val_id: str) -> ValidationResult`. It takes one positional argument, the `val_id` exactly as received.
- `query_by_tran_id(tran_id: str, val_id_hint: str | None = None) -> ValidationResult`. Today it is called as `query_by_tran_id(<tran_id>, val_id_hint=<row's val_id>)`: `tran_id` is positional and the hint is a keyword argument whose value is always `None` for an `INITIATED` row. See `reconcile_stuck_transactions` R4/R4a.
- `ValidationResult(status: str, tran_id: str, val_id=None, amount: Decimal | None = None, currency=None, risk_level: int | None = None, risk_title=None, bank_tran_id=None, card_type=None, verify_sign=None, verify_key=None)`. The manager never reads `verify_key`.

**Time values:** `utcnow()` (`app/utils/time.py`) returns a **naive** datetime in UTC (`tzinfo=None`). All timestamp columns (`initiated_at`, `validated_at`, `risk_resolved_at`, `created_at`, `updated_at`, event `created_at`) are `DateTime` without time zone, i.e. Postgres `TIMESTAMP WITHOUT TIME ZONE`. Values read back are naive and compare equal to the naive datetimes written. The sweep cutoff `now − older_than_minutes` is naive as well.

**Integration-only behavior:** the concurrency guarantee of the row lock (`SELECT … FOR UPDATE`) needs two simultaneous sessions and cannot be observed with one rolled-back test session. Within one session the locked lookup behaves as a normal lookup. The presence of the lock clause itself is unit-testable (see Notes for the test designer).

**Notes for the test designer:**
- To make a candidate's *update* fail after a successful gateway answer (`reconcile_stuck_transactions` R8), have the mocked `query_by_tran_id` return `status="VALID"` with matching amount and currency and a value longer than its column: `risk_title` > 50 characters (or `card_type` > 50, `bank_tran_id` > 100). `_apply_validation_result` changes the transaction's fields and then fails at flush with SQLAlchemy `DataError`. This exercises "its changes are undone" with changes actually made.
- The verified/unverified marker is the new column `outcome_verified` (BOOLEAN NOT NULL, default `false`; `_apply_validation_result` R12). It does not exist today, so a test that inserts a row with `outcome_verified=...` fails at construction until BUG-026 is fixed; those tests are expected-to-fail anyway. Tests for untagged rules should reach verified/unverified states through the manager's own methods (`_apply_validation_result`, `mark_terminal_without_validation`) so they run today.
- A `RISK_HOLD` row always has `outcome_verified = true`: the only way to reach `RISK_HOLD` is a gateway-verified VALID answer (`_apply_validation_result` R6, R8, R9, which set the marker per R12). Any `RISK_HOLD` row inserted directly in a test must therefore set `outcome_verified = true`; a `RISK_HOLD` row with `false` is not a valid state and must not be used as a fixture. Until BUG-026 is fixed the column does not exist, so tests for untagged rules should reach `RISK_HOLD` through `_apply_validation_result` (e.g. a VALID answer with `risk_level = 1`) rather than by direct insert.
- Row locks are checked the same way for every locking method, including `resolve_risk` R6a [BUG-029]: capture the SQL emitted during the call (e.g. a SQLAlchemy `before_cursor_execute` listener on the test engine) and assert that the SELECT on `payment_transactions` contains `FOR UPDATE`. This needs only one session and is a unit case; only the two-session race itself is integration-only.

## Not specified
- `PaymentTransactionManager.__init__` — wires the model, the transaction DAO and the event DAO, no logic

---

## `PaymentTransactionManager._log_event(session, txn, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** internal (used by: `initiate_payment`, `_apply_validation_result`, `finalize_from_gateway`, `mark_terminal_without_validation`, `resolve_risk`, `reconcile_stuck_transactions`)

**Purpose:** Append one audit event to a transaction's history.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |
| txn | PaymentTransaction | Must already have an `id` (flushed) |
| event_type | str | Stored as-is; column is `String(50)` |
| description | str | Stored as-is; column is non-null `Text` |
| performed_by | int \| None | Profile id; default `None` |
| metadata | dict \| None | Stored in `metadata_json`; default `None` |

**Returns:** `None`.

**Rules:**
- **R1.** One `payment_transaction_events` row is inserted with `workspace_id = txn.workspace_id`, `payment_transaction_id = txn.id`, `event_type`, `description`, `metadata_json = metadata` and `performed_by`, exactly as given. `metadata_json` and `performed_by` are `None` when omitted. `created_at` is set by the model default. The row is flushed, so it has an `id`.
- **R2.** An `event_type` longer than 50 characters fails at flush with a database error (value too long); nothing is inserted.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `event_type` > 50 chars | SQLAlchemy `DataError` at flush | Postgres message (not asserted) |

**Side effects:** One event row inserted and flushed. No commit.

---

## `PaymentTransactionManager._generate_tran_id(session)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `initiate_payment`)

**Purpose:** Produce a new, globally unused transaction ID for the gateway.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |

**Returns:** A 26-character lowercase hexadecimal string.

**Rules:**
- **R1.** The returned id is 26 lowercase hex characters (`[0-9a-f]{26}`) and is not the `tran_id` of any existing transaction in **any** workspace. The uniqueness check is global, not per workspace.
- **R2.** Up to 5 random candidates are tried, and the first unused one is returned. Example: the first 4 candidates already exist and the 5th is free, so the 5th is returned.
- **R3.** If all 5 candidates already exist, 500 is raised.
- **R4.** Nothing is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| 5 consecutive candidates all already used | `HTTPException` 500 | `Could not generate a unique transaction ID` |

**Side effects:** none.

---

## `PaymentTransactionManager.initiate_payment(session, *, workspace_id, user, request)`
**Shape:** create
**Persistence:** writes
**Visibility:** public

**Purpose:** Open a checkout session with SSLCommerz and record the attempt: `INITIATED` if the gateway accepted it, `INIT_FAILED` if it refused.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| workspace_id | int | Workspace the payment belongs to. Not checked here; a nonexistent id fails at flush (FK) |
| user | Profile | Initiating user; `id`, `name`, `email` are used |
| request | InitiatePaymentRequest | `amount: Decimal` > 0 (R9), at most 2 decimal places and at most 13 integer digits (R9a); `currency: str`, default `"BDT"` (R10), upper-cased, one of `BDT`, `USD` (R10a); `cus_phone: str` 3–50 chars, required; `cus_name`, `cus_email`: optional, max 255 (email format not checked); `value_a`..`value_d`: optional, max 255 |

**Returns:** The new `PaymentTransaction` (status `INITIATED` or `INIT_FAILED`), flushed (has `id`), not committed.

**Rules:**
- **R1.** The gateway's `init_session` is called once with one `InitSessionRequest` containing: `tran_id` = a new id per `_generate_tran_id` R1–R3; `amount` and `currency` as in the (validated) request; `success_url` / `fail_url` / `cancel_url` / `ipn_url` = `f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments/success"` (…`/fail`, …`/cancel`, …`/ipn`, no trailing slash); `cus_name`, `cus_email` per R2; `cus_phone` as given; `product_name = "Workspace Subscription"`, `product_category = "subscription"`.
- **R1a.** [BUG-020] The same `InitSessionRequest` also carries `value_a`..`value_d` exactly as in the request (`None` when omitted). *(Today: `value_a`..`value_d` are not sent to the gateway. Requires new `value_a`..`value_d` fields on `InitSessionRequest`.)*
- **R2.** The customer name is `request.cus_name` if it is non-empty, else `user.name`. An empty string `""` falls back to the profile name. The customer email is `request.cus_email` if non-empty, else `user.email`. The same resolved values are sent to the gateway and stored.
- **R3.** [BUG-019] If the gateway answers with a status other than exactly `"SUCCESS"` (e.g. `"FAILED"`, or lowercase `"success"`), no exception is raised. One transaction row is created with the same fields as R5 except `status = "INIT_FAILED"` and `failed_reason` = the gateway's `failed_reason`, or `"unknown error"` when it is `None` or `""`. `session_key` and `gateway_page_url` are whatever the gateway returned (usually `None`). One event is written per `_log_event` R1: `event_type = "initiation_failed"`, `description = f"Checkout session refused by gateway: {failed_reason}"` (with the same `"unknown error"` fallback), `performed_by = user.id`, `metadata_json = None`. The transaction is returned normally, and the service reports `status = "INIT_FAILED"` and `failed_reason` in `InitiatePaymentResponse`. *(Today: 502 `SSLCommerz session initiation failed: <reason or 'unknown error'>`, and no row or event is written. Requires a new nullable `failed_reason` column on `payment_transactions`, and `PaymentTransactionService.initiate_payment` to fill `failed_reason` in the response.)*
- **R4.** If the gateway call itself raises, that exception propagates unchanged, and no transaction row and no event are written.
- **R5.** On success, one `payment_transactions` row is created with: `workspace_id`; `tran_id` (the one sent to the gateway); `status = "INITIATED"`; `amount`; `currency`; `cus_name`, `cus_email` (per R2); `cus_phone`; `value_a`..`value_d` from the request (`None` when omitted); `session_key` and `gateway_page_url` from the gateway answer (`None` if it gave none); `initiated_by = user.id`. `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`, `last_ipn_payload`, `validated_at`, `risk_resolved_by`, `risk_resolved_at` and `risk_resolution_note` are `None`. `initiated_at`, `created_at` and `updated_at` are set by the model default at flush.
- **R5a.** [BUG-019] On success, the new `failed_reason` column is `None`. *(Today: the column does not exist. Requires the new nullable `failed_reason` column from R3.)*
- **R6.** On success, one event is written per `_log_event` R1: `event_type = "initiated"`, `description = f"Checkout session created for {amount} {currency}"`, with the amount printed as the request's Decimal (`Decimal("500")` → `"…for 500 BDT"`, `Decimal("500.00")` → `"…for 500.00 BDT"`). `performed_by = user.id`, `metadata_json = {"session_key": <gateway session_key>}` (value `None` if the gateway gave none).
- **R7.** Every accepted call creates a new transaction with a new `tran_id`. Repeated or concurrent calls for the same workspace/user/amount are not deduplicated.
- **R7a.** [BUG-019] A refused call also creates a new transaction with a new `tran_id` (per R3), so repeated refusals leave one `INIT_FAILED` row each. *(Today: a refused call raises 502 and creates nothing.)*
- **R8.** A `workspace_id` that does not exist fails at flush with an integrity error, after the gateway session was already requested.
- **R9.** `InitiatePaymentRequest` rejects `amount` ≤ 0 (`0`, `-1`) with a Pydantic `ValidationError` (422 at the API). `10.5`, `10.50` and `9999999999999.99` are accepted, sent to the gateway as given and stored (`10.5` reads back as `Decimal("10.50")`, since the column has 2 decimals).
- **R9a.** [BUG-021] `InitiatePaymentRequest` also rejects an `amount` with more than 2 decimal places (e.g. `10.005`) or with more than 13 digits before the decimal point (≥ `10000000000000`, i.e. 10^13) with a Pydantic `ValidationError` (422 at the API). The manager is therefore never reached, and the gateway is not called. *(Today: the schema accepts them; `10.005` is sent unrounded to the gateway but stored as `10.01`, and ≥ 10^13 fails at flush with a numeric-overflow error after the gateway session exists. The fix belongs in `app/schemas/payment_transaction.py`.)*
- **R10.** `InitiatePaymentRequest.currency` defaults to `"BDT"` when omitted. `"BDT"` and `"USD"` are accepted, and that value is sent to the gateway and stored.
- **R10a.** [BUG-022] `InitiatePaymentRequest.currency` is upper-cased, and only the supported codes `BDT` and `USD` are accepted. `"bdt"` becomes `"BDT"`, and that value is sent to the gateway and stored. Any other value (`"XYZ"`, `"12 "`, `"EUR"`) is rejected with a Pydantic `ValidationError` (422 at the API) before the gateway is called. *(Today: any 3-character string is accepted and stored as typed. The fix belongs in `app/schemas/payment_transaction.py`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| All 5 generated ids already used | `HTTPException` 500 | `Could not generate a unique transaction ID` |
| Gateway call raises | the gateway's exception, unchanged | — |
| Nonexistent `workspace_id` | SQLAlchemy `IntegrityError` at flush | not asserted |
| Amount > 2 decimals or ≥ 10^13; unsupported currency | Pydantic `ValidationError` when building `InitiatePaymentRequest` | not asserted |

**Side effects:** Accepted: one `INITIATED` transaction row and one `initiated` event. Refused: one `INIT_FAILED` transaction row and one `initiation_failed` event. Both flushed. One gateway `init_session` call. No commit.

---

## `PaymentTransactionManager._apply_validation_result(session, txn, result, source)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `finalize_from_gateway`, `reconcile_stuck_transactions`)

**Purpose:** Turn the gateway's validation answer into the transaction's verified outcome (success, risk hold, failure or cancellation), or reject an answer that does not belong to this transaction.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |
| txn | PaymentTransaction | The transaction to finalize. Its current status is **not** checked here (callers decide which statuses may be finalized) |
| result | ValidationResult | Gateway answer: `status`, `tran_id`, optional `val_id`, `amount`, `currency`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign` |
| source | str | Label used only inside event descriptions |

**Returns:** The same `txn` object, changes flushed.

**Rules:**
Checks run in this order, and the first one that decides stops processing: tran_id (R1/R2) → unknown val_id (R2a) → status (R4/R4a) → amount mismatch (R5) → currency mismatch (R7) → missing amount or currency (R6/R8) → risk (R9/R10). Every outcome writes exactly one event with `performed_by = None` and `metadata_json = None` (per `_log_event` R1). Every outcome except a rejection (R1/R1a, R2a) sets `validated_at` to the current time. Recording the outcome as gateway-verified is R12.
- **R1.** If `result.tran_id` is non-empty and differs from `txn.tran_id` (exact, case-sensitive: `"ABC"` ≠ `"abc"`), the answer does not belong to this transaction. The gateway fields (`val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`) keep their previous values, and none of the later checks run (no amount, currency or risk outcome). Exactly one event is written, description `f"val_id/tran_id mismatch via {source}: gateway resolved it to tran_id={result.tran_id}"`.
- **R1a.** [BUG-023] In the R1 case the answer is rejected. `status` (e.g. stays `INITIATED`) and `validated_at` keep their previous values, and the event type is `validation_rejected`. A later genuine result can still finalize the transaction. *(Today: status becomes `VALIDATED_FAILED`, `validated_at` is set and the event is `validated_failed`.)*
- **R2.** If `result.tran_id` is empty (`""`), the tran_id check is skipped and processing continues with R2a.
- **R2a.** [BUG-023] If `result.status` is exactly `"INVALID_TRANSACTION"` (the gateway does not know this `val_id`), the answer is rejected exactly as in R1/R1a: no field changes, one `validation_rejected` event, description `f"Gateway validation via {source} returned status=INVALID_TRANSACTION; val_id rejected"`. *(Today: status becomes `VALIDATED_FAILED` per R4.)*
- **R3.** In every outcome from R4 to R10 (not R1/R1a/R2a), the gateway fields are copied onto the transaction: `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign` = the result's values. A `None` in the result overwrites the existing value with `None`.
- **R4.** If `result.status` is anything other than exactly `"VALID"`, `"VALIDATED"`, `"CANCELLED"` or `"INVALID_TRANSACTION"` (e.g. `FAILED`, `EXPIRED`, `UNATTEMPTED`, lowercase `"valid"`), the status becomes `VALIDATED_FAILED`. Event `validated_failed`, description `f"Gateway validation via {source} returned status={result.status}"`.
- **R4a.** If `result.status` is exactly `"CANCELLED"`, it is a gateway-verified outcome: the gateway fields are copied (R3), `validated_at` is set, no amount/currency/risk check runs, and exactly one event is written with description `f"Gateway validation via {source} returned status=CANCELLED"`.
- **R4b.** [BUG-025] In the R4a case the status becomes `CANCELLED`, no matter which channel delivered it (redirect, IPN or sweep), and the event type is `validated_cancelled`. *(Today: `VALIDATED_FAILED` with event `validated_failed`.)*
- **R5.** If the status is valid and `result.amount` is not `None` and differs numerically from `txn.amount` (Decimal comparison, so `100` equals `100.00`), the status becomes `VALIDATED_FAILED`. Event `validated_failed`, description `f"Amount mismatch: expected {txn.amount} {txn.currency}, gateway reported {result.amount} {result.currency}"`; a missing result currency prints as `None`.
- **R6.** [BUG-024] If the status is valid, no mismatch was found (R5, R7), and `result.amount` is `None`, the status becomes `RISK_HOLD` for manual review, never `VALIDATED_SUCCESS`, whatever the `risk_level`. Event `risk_hold`, description `f"Validated via {source} but gateway reported no amount — held for review"`. *(Today: the amount check is skipped and the transaction can become `VALIDATED_SUCCESS`.)*
- **R7.** If the status is valid, the amount matches or is missing, and `result.currency` is non-empty and differs from `txn.currency` (exact, case-sensitive: `"BDT"` ≠ `"bdt"`; our stored currency is always upper-case per `initiate_payment` R10), the status becomes `VALIDATED_FAILED`. Event `validated_failed`, description `f"Currency mismatch: expected {txn.currency}, gateway reported {result.currency}"`. A definite mismatch takes precedence over a missing field: a missing amount with a mismatched currency gives `VALIDATED_FAILED`.
- **R8.** [BUG-024] If the status is valid, no mismatch was found, the amount is present, and `result.currency` is `None` or `""`, the status becomes `RISK_HOLD`, whatever the `risk_level`. Event `risk_hold`, description `f"Validated via {source} but gateway reported no currency — held for review"`. When both amount and currency are missing, R6 applies (its description). *(Today: the currency check is skipped and the transaction can become `VALIDATED_SUCCESS`.)*
- **R9.** If amount and currency are both present and match, and `result.risk_level == 1`, the status becomes `RISK_HOLD`. Event `risk_hold`, description `f"Validated via {source} but flagged high-risk ({result.risk_title}) — held for review"`; a missing title prints as `None`.
- **R10.** If amount and currency are both present and match, and `risk_level` is anything other than `1` (`0`, `None`, `2`, …), the status becomes `VALIDATED_SUCCESS`. Event `validated_success`, description `f"Validated successfully via {source}"`.
- **R11.** The helper does not check the transaction's current status: an `EXPIRED` or unverified `CANCELLED`/`VALIDATED_FAILED` row passed in is finalized the same way as an `INITIATED` one (this is how `finalize_from_gateway` R3a/R3b replace unverified outcomes). Callers never pass a gateway-verified final row.
- **R12.** [BUG-026] Every outcome from R4 to R10 records the outcome as gateway-verified: `outcome_verified` is set to `true`, including when the row previously held an unverified outcome (`false`). A rejection (R1a, R2a) leaves `outcome_verified` as it was. The column is `payment_transactions.outcome_verified` BOOLEAN NOT NULL with default `false` (Python default and server default), so a new transaction (`initiate_payment`, accepted or refused) and a row inserted without the field read back `false`. No other method changes it: `mark_terminal_without_validation`, the sweep's `EXPIRED` (`reconcile_stuck_transactions` R6) and `resolve_risk` leave it as it was. *(Today: the column does not exist. Requires the new `outcome_verified` column.)*

**Errors:** none raised by the helper itself.

**Side effects:** R4–R10: updates the transaction fields listed above, `validated_at`, and `outcome_verified = true` (R12) (`updated_at` changes via the model's `onupdate`). R1/R1a/R2a: no transaction change. Always one event and a flush. No gateway call. No commit.

---

## `PaymentTransactionManager.finalize_from_gateway(session, *, tran_id, val_id, source)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (called by `PaymentTransactionService.handle_gateway_callback` from the public `/payments/success` and `/payments/fail` (when a `val_id` is present) and `/payments/ipn` endpoints, with `source` = `"redirect_success"`, `"redirect_fail"`, `"ipn"`)

**Purpose:** Finalize a transaction from a gateway callback that carries a `val_id` by validating the `val_id` with the gateway. A verified outcome is final; an unverified one can be replaced.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| tran_id | str | Our transaction id; looked up across all workspaces |
| val_id | str | Gateway validation id; passed to the gateway unchanged, not checked (not even for empty) |
| source | str | Channel label, used in the event type and descriptions |

**Returns:** The transaction, flushed, not committed.

**Rules:**
- **R1.** The transaction is found by `tran_id` alone, in any workspace (the callback has no workspace context). The row is locked for update for the rest of the DB transaction.
- **R2.** If no transaction has this `tran_id`, 404 is raised; nothing is written and the gateway is not called.
- **R3.** If the transaction's outcome is final, no transaction field changes and the gateway is not called. Final means `VALIDATED_SUCCESS` or `INIT_FAILED` (these two may be inserted directly, whatever `outcome_verified` is), `RISK_HOLD` (always `outcome_verified = true`; see Notes for the test designer), a `VALIDATED_FAILED` produced by gateway validation (`_apply_validation_result` R4, R5, R7), or any status set by `resolve_risk` (a `VALIDATED_SUCCESS` or `VALIDATED_FAILED` that keeps `outcome_verified = true`, `resolve_risk` R3a): an owner's risk decision is never replaced by a later callback. The supplied `val_id` is not recorded. Exactly one event is written: `duplicate_ignored`, description `f"Duplicate {source} callback ignored; transaction already {status}"`. The unchanged transaction is returned. Unverified outcomes and `EXPIRED` are not final: see R3a/R3b. Reach the gateway-verified `VALIDATED_FAILED` through `_apply_validation_result` or `finalize_from_gateway` itself (today no column distinguishes it from an unverified one; after the BUG-026 fix it is a `VALIDATED_FAILED` row with `outcome_verified = true`).
- **R3a.** [BUG-026] If the transaction holds an **unverified** outcome, it is handled exactly like an `INITIATED` one (R4): the `val_id` is validated and the gateway's verified answer replaces the status. An unverified outcome is a `VALIDATED_FAILED` or `CANCELLED` row with `outcome_verified = false`: one set by `mark_terminal_without_validation`, or one inserted without setting the field (the default `false` counts as unverified). A `VALIDATED_FAILED` set by `resolve_risk` (rejection) is never unverified, because it keeps the `RISK_HOLD` row's `outcome_verified = true` (`resolve_risk` R3a); it is final per R3. Example: T1 was `CANCELLED` by a cancel redirect, then an IPN arrives with a paid `val_id` → T1 becomes `VALIDATED_SUCCESS`. If the gateway rejects the `val_id` (`_apply_validation_result` R1a/R2a), the unverified status stays as it was. *(Today: a `duplicate_ignored` event is written and the status stays. Requires the `outcome_verified` column, `_apply_validation_result` R12.)*
- **R3b.** [BUG-027] If the transaction is `EXPIRED`, it is handled exactly like an `INITIATED` one (R4), so a verified result arriving after the sweep replaces `EXPIRED`. Example: swept to `EXPIRED` at 10:35, and a valid IPN arrives at 10:37 → `VALIDATED_SUCCESS`. *(Today: `duplicate_ignored`, stays `EXPIRED`.)*
- **R3c.** [BUG-025] A `CANCELLED` produced by gateway validation (`_apply_validation_result` R4b) is final in the same way: a later callback leaves it `CANCELLED` and writes one `duplicate_ignored` event reading `…transaction already CANCELLED`. *(Today: a gateway-reported `CANCELLED` becomes `VALIDATED_FAILED`, so the event reads `…already VALIDATED_FAILED`.)*
- **R4.** If the transaction is `INITIATED` (or R3a/R3b applies), a received event is written with description `f"Callback received via {source}"`. For `source="ipn"` its type is `ipn_received`. The `val_id` is then validated with the gateway (`validate(val_id)`, called once), and the answer is applied per `_apply_validation_result` R1–R12 with `source = f"{source} callback"` (e.g. `"Validated successfully via ipn callback"`). This path writes exactly two events: the received event, then the outcome (or rejection) event.
- **R4a.** [BUG-028] The received event's type for the redirect sources follows the documented list: `source="redirect_success"` → `redirect_success`, `source="redirect_fail"` → `redirect_fail`. *(Today: `redirect_success_received` / `redirect_fail_received`.)*
- **R5.** A second call for the same `tran_id` after a verified finalization takes the R3 path. The first outcome stands and a `duplicate_ignored` event is added.
- **R5a.** [BUG-023] After a rejected `val_id` (`_apply_validation_result` R1a/R2a), a second call is processed normally under R4 (or R3a/R3b). Example: the first call's `val_id` resolves to another `tran_id`, and the second call's `val_id` is genuine and paid → `VALIDATED_SUCCESS`. *(Today: the first call sets `VALIDATED_FAILED`, so the second call gets `duplicate_ignored`.)*
- **R6.** If the gateway validation call raises, the exception propagates, the transaction's status and gateway fields are unchanged, and the received event has already been added to the session (the service rolls it back).
- **R7.** Only the three source labels above are used by callers. The event type for any other label is not specified.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| No transaction with this `tran_id` | `HTTPException` 404 | `Unknown tran_id: <tran_id>` |
| Gateway validation raises | the gateway's exception, unchanged | — |

**Side effects:** R3: one event. R4 (and R3a/R3b): field updates per `_apply_validation_result` (none on a rejection), two events, one gateway `validate(val_id)` call. Flushed. No commit.

---

## `PaymentTransactionManager.mark_terminal_without_validation(session, *, tran_id, terminal_status, source)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (called by `PaymentTransactionService.handle_terminal_without_validation`, from `/payments/success` with no `val_id` → `terminal_status="VALIDATED_FAILED"`, `source="redirect_success_no_val_id"`; `/payments/fail` with no `val_id` → `"VALIDATED_FAILED"`, `"redirect_fail_no_val_id"`; `/payments/cancel`, always, even when a `val_id` is posted → `"CANCELLED"`, `"redirect_cancel"`)

**Purpose:** Record a redirect's outcome that cannot be checked with the gateway, as an **unverified** outcome that a later verified result may replace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| tran_id | str | Looked up across all workspaces |
| terminal_status | str | Status to set; **not validated** (any string, column max 20 chars) |
| source | str | Channel label, used in the event type and description |

**Returns:** The transaction, flushed, not committed.

**Rules:**
- **R1.** Lookup and not-found behave as in `finalize_from_gateway` R1–R2: found by `tran_id` in any workspace and locked, otherwise 404 `Unknown tran_id: <tran_id>` with nothing written.
- **R2.** If the transaction is not `INITIATED`, including when it already holds an unverified outcome or is `EXPIRED`, the duplicate handling of `finalize_from_gateway` R3 applies: no field change, one `duplicate_ignored` event with the same description format, and the transaction is returned. An unverified signal never replaces another outcome (HR-11).
- **R3.** If the transaction is `INITIATED`, the status becomes exactly `terminal_status` and `validated_at` is set to the current time. `val_id`, the risk fields, `bank_tran_id`, `card_type` and `verify_sign` are untouched (stay `None`). Exactly one event is written, with description `f"Marked {terminal_status} via {source} (no val_id to validate)"` and `performed_by` and `metadata_json` `None`. The gateway is not called.
- **R3a.** [BUG-026] The R3 outcome is recorded as **unverified** (`outcome_verified` stays `false`), so `finalize_from_gateway` R3a can replace it later. *(Today: the column does not exist and the outcome is final. Requires the `outcome_verified` column, `_apply_validation_result` R12.)*
- **R3b.** [BUG-028] The R3 event's type comes from the documented list and depends on `source`: `"redirect_success_no_val_id"` → `redirect_success`, `"redirect_fail_no_val_id"` → `redirect_fail`, `"redirect_cancel"` → `redirect_cancel`. It is never `validated_failed` or `cancelled`. *(Today: the event type is `terminal_status.lower()`, i.e. `validated_failed` or `cancelled`.)*
- **R4.** `terminal_status` is not checked against the known statuses. Any string is written. A value longer than 20 characters fails at flush with a database error (value too long).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| No transaction with this `tran_id` | `HTTPException` 404 | `Unknown tran_id: <tran_id>` |
| `terminal_status` > 20 chars | SQLAlchemy `DataError` at flush | not asserted |

**Side effects:** R2: one event. R3: `status` and `validated_at` updated (marker unverified per R3a), plus one event. Flushed. No gateway call. No commit.

---

## `PaymentTransactionManager.resolve_risk(session, *, transaction_id, workspace_id, user_id, approve, note)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (called by `PaymentTransactionService.resolve_risk` from `POST /payments/{transaction_id}/resolve-risk/`. The endpoint allows only the workspace owner; the manager does not check this)

**Purpose:** Let a reviewer approve or reject a transaction held for review (flagged high-risk, or missing amount/currency confirmation).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| transaction_id | int | Transaction primary key (not `tran_id`) |
| workspace_id | int | Caller's workspace; the transaction must belong to it |
| user_id | int | Reviewer. Not checked for role or membership here |
| approve | bool | `True` → success, `False` → failure |
| note | str | Stored as given; the manager accepts any string, including `""` (the API schema requires 1–1000 chars) |

**Returns:** The transaction, flushed, not committed.

**Rules:**
- **R1.** If no transaction with this id exists, or it belongs to another workspace, 404 is raised and nothing is written.
- **R2.** If the transaction's status is anything other than `RISK_HOLD`, 400 is raised and nothing is written.
- **R3.** `approve=True` sets the status to `VALIDATED_SUCCESS`; `approve=False` sets it to `VALIDATED_FAILED`. Either outcome is final (`finalize_from_gateway` R3).
- **R3a.** [BUG-026] `outcome_verified` is not changed and stays `true`: a `RISK_HOLD` row is always gateway-verified (reached only through `_apply_validation_result` R6/R8/R9, which set the marker per R12). So an approved row is `VALIDATED_SUCCESS` with `outcome_verified = true`, and a rejected row is `VALIDATED_FAILED` with `outcome_verified = true`; a later callback for it is ignored as a duplicate (`finalize_from_gateway` R3), never re-validated under R3a. *(Today: the column does not exist. Requires the `outcome_verified` column, `_apply_validation_result` R12.)*
- **R4.** `risk_resolved_by = user_id`, `risk_resolved_at` = the current time, and `risk_resolution_note = note`. `validated_at` and the gateway fields (`val_id`, `risk_level`, `risk_title`, …) are unchanged.
- **R5.** One event `risk_resolved` is written, with description `f"Risk hold approved: {note}"` or `f"Risk hold rejected: {note}"`, `performed_by = user_id` and `metadata_json = None`.
- **R6.** A transaction can be resolved only once. A second sequential call sees the new status and gets 400 per R2, and no second `risk_resolved` event is written.
- **R6a.** [BUG-029] The row is read with a row lock (`SELECT … FOR UPDATE`), so the R6 guarantee also holds for two **concurrent** calls: the loser sees the new status and gets 400. The lock clause is unit-testable: the SQL emitted for the lookup contains `SELECT … FOR UPDATE` on `payment_transactions` (checked by capturing SQL, like the other lock rules; see Notes for the test designer). Only the two-session race itself is integration-only. *(Today: the row is read without a lock, so two simultaneous calls can both succeed.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found, or in another workspace | `HTTPException` 404 | `Payment transaction <transaction_id> not found` |
| Status ≠ `RISK_HOLD` | `HTTPException` 400 | `Only transactions in RISK_HOLD can be resolved (current status: <status>)` |

**Side effects:** Updates `status`, `risk_resolved_by`, `risk_resolved_at` and `risk_resolution_note`, and writes one event. Flushed. No commit.

---

## `PaymentTransactionManager.reconcile_stuck_transactions(session, *, older_than_minutes=30, limit=200)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (called only by `scripts/reconcile_payments.py`, which passes CLI values, defaults 30 and 200, and commits once at the end; no API endpoint)

**Purpose:** Close transactions stuck in `INITIATED` whose callbacks never arrived, by asking the gateway directly.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| older_than_minutes | int | Age threshold; default `RECONCILE_TIMEOUT_MINUTES` = 30. Not validated (0 or negative accepted) |
| limit | int | Maximum transactions handled per call; default 200. Not validated |

**Returns:** A list of the transactions handled in this call, each in its new state, in processing order. The list is empty if none were handled.

**Rules:**
- **R1.** Only transactions with status `INITIATED` and `initiated_at` strictly earlier than (now − `older_than_minutes`) are considered, across **all** workspaces. A transaction initiated exactly at the cutoff is not considered. Non-`INITIATED` transactions (including `RISK_HOLD`, `EXPIRED` and unverified outcomes) are never touched.
- **R2.** Candidates are processed oldest `initiated_at` first, at most `limit` per call. Older-than-cutoff rows beyond `limit` are left `INITIATED` for a later call.
- **R3.** Each candidate is re-read with a lock just before it is handled. If it is no longer `INITIATED` by then (a live callback resolved it), it is skipped: no change, no event, and it is not in the returned list.
- **R4.** For each remaining candidate, the gateway's `query_by_tran_id` is called once with the transaction's `tran_id` as the first argument, and its answer is applied per R5/R6. With the gateway mocked, a transaction the gateway reports as paid is recovered even though no callback ever arrived (e.g. the mock answers `VALID` with matching amount and currency for that `tran_id` → `VALIDATED_SUCCESS` per R5).
- **R4a.** [BUG-031] The query uses `tran_id` alone: `query_by_tran_id(<tran_id>)`, with no `val_id_hint` argument. *(Today: it is called with `val_id_hint=<stored val_id>`, which is always `None` for an `INITIATED` row. The only implemented client, the mock `app/integrations/sslcommerz/mock_client.py`, answers `UNATTEMPTED` without a hint, so every candidate becomes `EXPIRED`. That part of the fix, answering tran_id-only lookups from its record of completed payments, belongs in the mock client and is out of scope for this spec.)*
- **R5.** If the gateway answers `"VALID"` or `"VALIDATED"`, the answer is applied per `_apply_validation_result` with `source = "reconciliation"`. It can give `VALIDATED_SUCCESS` (event description `"Validated successfully via reconciliation"`), `RISK_HOLD`, or `VALIDATED_FAILED` on an amount or currency mismatch (R5–R10). If such an answer names a different `tran_id` (`_apply_validation_result` R1), the gateway fields are not copied, and the transaction is still in the returned list.
- **R5a.** [BUG-030] If the gateway answers `"FAILED"` or `"CANCELLED"`, the answer is also applied per `_apply_validation_result` with `source = "reconciliation"`. `FAILED` gives `VALIDATED_FAILED`, with the gateway fields copied, event `validated_failed` and description `"Gateway validation via reconciliation returned status=FAILED"` (R4). `CANCELLED` gives `CANCELLED` with event `validated_cancelled` (R4a/R4b; that also depends on BUG-025). *(Today: `FAILED` and `CANCELLED` give `EXPIRED` per R6.)*
- **R5b.** [BUG-023] In the R5 different-`tran_id` case, the answer is rejected per `_apply_validation_result` R1a: the transaction stays `INITIATED`. *(Today: it becomes `VALIDATED_FAILED`.)*
- **R6.** For any other answer (`UNATTEMPTED`, `EXPIRED`, `INVALID_TRANSACTION`, empty or unrecognised; per R5a, not `FAILED`/`CANCELLED`), the status becomes `EXPIRED` and `validated_at` is set to the current time. `EXPIRED` is an unverified outcome (`finalize_from_gateway` R3b). The gateway fields are untouched. One event `expired` is written, with description `f"No resolution found after {older_than_minutes} minutes (gateway status: {result.status})"`, `performed_by = None` and `metadata_json = None`.
- **R7.** Every candidate not skipped under R3 and not failed under R8 appears in the returned list exactly once, whatever its outcome under R5 or R6.
- **R8.** [BUG-032] If handling one candidate raises (the gateway query times out or fails, or its update fails), only that candidate is affected. Its changes are undone, so it stays `INITIATED` with no field changes, and it is left out of the returned list. One event `reconciliation_error` is written for it, with description `f"Gateway query failed during reconciliation: {error}"` (`{error}` is `str(exc)`, or the exception class name `type(exc).__name__` when `str(exc)` is `""`: `TimeoutError("gateway timeout")` → `"…reconciliation: gateway timeout"`, `TimeoutError()` → `"…reconciliation: TimeoutError"`), `performed_by = None` and `metadata_json = None`. The sweep continues with the next candidate. No exception escapes the method, and the results for all other candidates, earlier and later, are kept and returned. Example: 150 candidates, and the gateway raises on number 120 → 149 are handled and returned, number 120 stays `INITIATED` with one `reconciliation_error` event. *(Today: the exception propagates, later candidates are not handled, and the script rolls back everything. Requires a per-candidate savepoint.)*
- **R9.** `older_than_minutes = 0` makes every `INITIATED` transaction initiated before "now" a candidate. A negative value moves the cutoff into the future, so every `INITIATED` transaction, including one just created, is a candidate.
- **R10.** Transactions from different workspaces are handled in the same call. Each event carries its own transaction's `workspace_id` (per `_log_event` R1).

**Errors:** none escape. Per-candidate errors are handled per R8.

**Side effects:** For each handled candidate: status and field updates per R5/R6, and one event. For each failed candidate: one `reconciliation_error` event only. Flushed. One gateway `query_by_tran_id` call per non-skipped candidate. No commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 44–51 | event insert, optional `performed_by` / `metadata` default `None` | `_log_event` R1 |
| — (`String(50)` column) | event_type too long → DB error | `_log_event` R2 |
| 54 | loop over 5 attempts | `_generate_tran_id` R2 |
| 55 | 26-char hex candidate | `_generate_tran_id` R1 |
| 56 / DAO `get_by_tran_id` | candidate unused (global, any workspace) → return | `_generate_tran_id` R1, R2 |
| 58 | all 5 used → 500 | `_generate_tran_id` R3 |
| — (schema `gt=0`) | amount ≤ 0 → 422 | `initiate_payment` R9 |
| — (schema) | amount precision / magnitude → 422 | `initiate_payment` R9a |
| — (schema default) | currency omitted → `BDT` | `initiate_payment` R10 |
| — (schema) | currency upper-cased, BDT/USD only → 422 otherwise | `initiate_payment` R10a |
| 68 | id generated before gateway call | `initiate_payment` R1 |
| 69–79 | callback URLs from settings | `initiate_payment` R1 |
| 72 | gateway call raises | `initiate_payment` R4 |
| 80–81, 97–98 | `cus_name` / `cus_email` truthy → request value; falsy (None / "") → profile value | `initiate_payment` R2 |
| — (InitSessionRequest fields) | `value_a`..`value_d` sent | `initiate_payment` R1a |
| 85 | status ≠ `"SUCCESS"` → `INIT_FAILED` row + event, returned | `initiate_payment` R3, R7a |
| 88 | `failed_reason` truthy vs None/"" → `unknown error` | `initiate_payment` R3 |
| 91–107 / BaseDAO.create | row insert + flush | `initiate_payment` R5, R5a, R7 |
| — (FK `workspace_id`) | nonexistent workspace → IntegrityError | `initiate_payment` R8 |
| 109–114 | `initiated` event | `initiate_payment` R6 |
| 122 | `result.tran_id` truthy and ≠ `txn.tran_id` → rejected, nothing changes | `_apply_validation_result` R1, R1a |
| 122 | `result.tran_id` falsy → skip check | `_apply_validation_result` R2 |
| — (new) | status `INVALID_TRANSACTION` → rejected | `_apply_validation_result` R2a |
| 134–140 | copy gateway fields (incl. None) + `validated_at` | `_apply_validation_result` R3 |
| 142 | status ∉ {VALID, VALIDATED, CANCELLED, INVALID_TRANSACTION} → failed | `_apply_validation_result` R4 |
| — (new) | status `CANCELLED` → CANCELLED | `_apply_validation_result` R4a, R4b |
| 151 | amount not None and ≠ → failed | `_apply_validation_result` R5 |
| 160 | currency truthy and ≠ → failed | `_apply_validation_result` R7 |
| 151 | amount None → RISK_HOLD | `_apply_validation_result` R6 |
| 160 | currency None / "" → RISK_HOLD | `_apply_validation_result` R8 |
| 169 | `risk_level == 1` → RISK_HOLD | `_apply_validation_result` R9 |
| 175 | else → VALIDATED_SUCCESS | `_apply_validation_result` R10 |
| — (no status check in helper) | unverified / EXPIRED row finalized | `_apply_validation_result` R11 |
| — (new) | outcome R4–R10 → `outcome_verified = true` | `_apply_validation_result` R12 |
| 189 / DAO `get_by_tran_id_for_update` | lookup by tran_id, any workspace, locked | `finalize_from_gateway` R1 |
| 190 | not found → 404 | `finalize_from_gateway` R2 |
| 193 | final outcome → duplicate_ignored | `finalize_from_gateway` R3, R3c, R5 |
| 193 | unverified outcome → validate and replace | `finalize_from_gateway` R3a |
| 193 | EXPIRED → validate and replace | `finalize_from_gateway` R3b |
| 201 | received event, type mapped from source | `finalize_from_gateway` R4, R4a, R7 |
| 204 | gateway validate raises | `finalize_from_gateway` R6 |
| 205 | apply result with `"<source> callback"` | `finalize_from_gateway` R4, R5a |
| 212–214 | lookup / not found → 404 | `mark_terminal_without_validation` R1 |
| 216 | status ≠ INITIATED → duplicate_ignored | `mark_terminal_without_validation` R2 |
| 224–227 | set terminal status (unverified), `validated_at`, event type mapped from source | `mark_terminal_without_validation` R3, R3a, R3b |
| — (no validation of `terminal_status`; `String(20)`) | any string / too long → DB error | `mark_terminal_without_validation` R4 |
| 233 / DAO lookup | id + workspace filter, locked | `resolve_risk` R1, R6a |
| 234 | not found / other workspace → 404 | `resolve_risk` R1 |
| 238 | status ≠ RISK_HOLD → 400 | `resolve_risk` R2, R6, R6a |
| 244 | `approve` true / false (`outcome_verified` untouched) | `resolve_risk` R3, R3a |
| 245–247 | risk resolution fields | `resolve_risk` R4 |
| 250 | description approved / rejected | `resolve_risk` R5 |
| 264 | cutoff = now − minutes (0 / negative accepted) | `reconcile_stuck_transactions` R1, R9 |
| 265 / DAO `get_stuck_initiated` | INITIATED, `initiated_at <` cutoff, all workspaces, oldest first, `limit` | `reconcile_stuck_transactions` R1, R2, R10 |
| 269 | loop over empty / one / many | `reconcile_stuck_transactions` R7 |
| 271 | re-locked row None or ≠ INITIATED → skip | `reconcile_stuck_transactions` R3 |
| 274 | query by `tran_id` alone | `reconcile_stuck_transactions` R4, R4a |
| 274 | per-candidate error → event, skip, continue | `reconcile_stuck_transactions` R8 |
| — (new) | `str(exc)` empty → class name in event description | `reconcile_stuck_transactions` R8 |
| 275 | VALID / VALIDATED → apply result | `reconcile_stuck_transactions` R5, R5b |
| 275 | FAILED / CANCELLED → apply result | `reconcile_stuck_transactions` R5a |
| 277 | else → EXPIRED | `reconcile_stuck_transactions` R6 |
| 285 | append handled txn | `reconcile_stuck_transactions` R7 |

## Gap log
- G1 (payment_transaction_manager.cases.md gap 1) — Intent — The verified/unverified marker does not exist in the code, and its storage was never decided. Added Q16 with a suggested answer (`outcome_verified` BOOLEAN NOT NULL default `false`, so an unset marker counts as unverified). Moved "records the outcome as gateway-verified" out of the untagged `_apply_validation_result` preamble into the new tagged rule R12 [BUG-026]. Added a designer note: reach verified/unverified states through the manager's methods until Q16 is answered.
- G2 (payment_transaction_manager.cases.md gap 2) — Fact — Added **Gateway client interface** to the Overview, with the exact signatures of `init_session(req: InitSessionRequest)` (one positional dataclass), `validate(val_id)` and `query_by_tran_id(tran_id, val_id_hint=None)` (today's call passes `val_id_hint=` as a keyword), plus the `InitSessionRequest` / `InitSessionResult` / `ValidationResult` fields. `reconcile_stuck_transactions` R4/R4a now state the call form.
- G3 (payment_transaction_manager.cases.md gap 3) — Fact — Added **Time values** to the Overview: `utcnow()` returns a naive UTC datetime, and every timestamp column is `TIMESTAMP WITHOUT TIME ZONE`.
- G4 (payment_transaction_manager.cases.md gap 4) — Test mechanics — Added a note for the test designer: a `VALID` answer with `risk_title` > 50 chars (or `card_type` > 50, `bank_tran_id` > 100) makes the update fail at flush with `DataError` after the fields were changed.
- G5 (payment_transaction_manager.cases.md gap 5) — Intent — Added Q17 with a suggested answer (`str(exc)`, or the class name when that is empty). `reconcile_stuck_transactions` R8 points to it.
- G6 (payment_transaction_manager.cases.md gap 6, reported separately by the case designer) — Contradiction/structure — Several [BUG-NNN] tags covered whole rules that also contained behavior which works today, so those working parts appeared only in expected-to-fail cases. Applied "Tag only the broken part": the working part stays untagged under the original number, and the broken part moves to a new tagged rule. Splits: `initiate_payment` R1→R1a [BUG-020], R5→R5a [BUG-019], R7→R7a [BUG-019], R9→R9a [BUG-021], R10→R10a [BUG-022]; `_apply_validation_result` R1→R1a [BUG-023], R4a→R4b [BUG-025], preamble→R12 [BUG-026]; `finalize_from_gateway` R3→R3c [BUG-025] (tags BUG-026/027 dropped from R3, they already live in R3a/R3b), R4→R4a [BUG-028], R5→R5a [BUG-023]; `mark_terminal_without_validation` R3→R3a [BUG-026] + R3b [BUG-028]; `resolve_risk` R6→R6a [BUG-029] (the sequential case passes today; only the concurrent lock is broken, and that is integration-only); `reconcile_stuck_transactions` R4→R4a [BUG-031], R5→R5a [BUG-030] + R5b [BUG-023], R6 untagged (all of it works today, and the BUG-030 change is only that FAILED/CANCELLED move to R5a). Left whole, because nothing in them works today in a way a test can assert: `initiate_payment` R3 [BUG-019], `_apply_validation_result` R2a [BUG-023], R6/R8 [BUG-024], `finalize_from_gateway` R3a [BUG-026], R3b [BUG-027], `reconcile_stuck_transactions` R8 [BUG-032]. Updated the rule references in Q1–Q13/Q15 Resolutions and in the Branch map to match.
- G7 (payment_transaction_manager.cases.md gap 7) — Contradiction — `RISK_HOLD` is reachable only from a gateway-verified VALID answer, so a `RISK_HOLD` row always has `outcome_verified = true`; `resolve_risk` leaves the marker unchanged (`true`), and an owner's approve (`VALIDATED_SUCCESS`) or reject (`VALIDATED_FAILED`) is final — later callbacks are duplicates. Added `resolve_risk` R3a [BUG-026]; `finalize_from_gateway` R3 no longer lists `RISK_HOLD` among statuses that may be inserted with any marker value and states that `resolve_risk` outcomes keep `outcome_verified = true`; R3a now excludes a `resolve_risk` rejection from "unverified". Added a designer note: a directly inserted `RISK_HOLD` row must set `outcome_verified = true` (untagged tests reach `RISK_HOLD` via `_apply_validation_result` until BUG-026 is fixed). No question added. (best-practice default, delegated by reviewer)
- G8 (payment_transaction_manager.cases.md gap 8) — Test mechanics — `resolve_risk` R6a [BUG-029] is no longer marked integration-only: the `FOR UPDATE` clause is unit-testable by capturing the emitted SQL, the same way as the other lock rules. Only the two-session race remains integration-only (Overview updated). Added a designer note describing the SQL-capture check. No question added. (best-practice default, delegated by reviewer)
