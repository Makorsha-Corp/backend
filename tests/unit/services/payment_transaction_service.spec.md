# Spec — `app/services/payment_transaction_service.py`

> **Status:** APPROVED (apply-review 2026-11-21; precedents P1–P4 confirmed and Q1–Q4 decided under the reviewer's delegation of 2026-11-21; Q5 from the owner's answer OQ-61, 2026-11-21)
> **Source commit:** e48a092

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** One new question became a bug (Q1, **BUG-3022**). Three were decided as intended (Q2–Q4). None of them is the owner's own answer. The sweep re-check is OQ-25 (owner: decide in the portal work).
>
> **Apply-review 2026-11-21.** P1–P4 confirmed (existing BUG-019, BUG-1191, BUG-029, BUG-2402 / BUG-1190; service parts only). Q1 → **BUG-3022** logged. Q2–Q4 intended, rules marked ✅. **Q5 (owner, OQ-61):** the one-time-code pattern decided for manual invoice payments (BUG-3002) applies to starting a gateway checkout too → **BUG-3023** (`initiate_payment` R7, R7a–R7e). Frontend note **BUG-3024** (`frontend/src/types/payment.ts`). Logged in `docs/testing/bugs.md` by the coordinator.
>
> **Fill-gaps 2026-11-21** (`payment_transaction_service.cases.md`, 6 gaps; see `## Gap log`). The idempotency key's storage, fingerprint, index, lookup, replay shape and race handling are now exact (R7a1, R7b1, R7c1, R7e1, R7e2, Errors, Facts). Coordinator decisions applied: the caller's profile id is part of the fingerprint (another member's reuse → 409, the same rule as BUG-3002); "same body" is compared after normalisation; a replay writes and commits nothing. Still APPROVED.
>
> **Base behaviour referenced, not restated:** the transaction contract **TC1–TC6** (`tests/unit/services/base_service.spec.md`); `PaymentTransactionManager` (`tests/unit/managers/payment_transaction_manager.spec.md`, APPROVED: `initiate_payment` R1–R10a, `finalize_from_gateway` R1–R7, `mark_terminal_without_validation` R1–R4, `resolve_risk` R1–R6a, `_apply_validation_result` R1–R12); `PaymentTransactionDAO` (`tests/unit/dao/payment_transaction.spec.md`: `get_by_tran_id_and_workspace_with_initiator` R1–R3, `list_by_workspace_with_initiator` R1–R7, `get_by_id_and_workspace_with_initiator` R5 / FU-1, FU-2); `PaymentTransactionEventDAO` (`tests/unit/dao/payment_transaction_event.spec.md`: `get_by_payment_transaction` R1–R8, FU-1).
>
> **Written as reference for the SSLCommerz subscription portal** (owner's request): idempotency, the place of every gateway call relative to the commit, the row locks, and the identifier format are stated as rules here (§ "Payment-flow contract" in the Overview), each one tied to a callable rule a test can check.
>
> **Verified by running** (my own `test_v1_pts.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1desc\payment_transaction_service\`, the unit `db` fixture on `marker_test`, rolled back, private `COVERAGE_FILE`; gateway mocked at `app.managers.payment_transaction_manager.get_sslcommerz_client`): accepted start → `InitiatePaymentResponse(tran_id=<26 hex>, status='INITIATED', gateway_page_url=…, failed_reason=None)` and the row survives a later `db.rollback()`; refused start today → `HTTPException` 502 `SSLCommerz session initiation failed: Store is de-active`, 0 rows; gateway `init_session` raising `TimeoutError` → same `TimeoutError`, 0 rows; risky IPN → returns the ORM `PaymentTransaction`, `RISK_HOLD`; same IPN again → `RISK_HOLD`, events `initiated, ipn_received, risk_hold, duplicate_ignored` all survive a rollback; `resolve_risk` → `PaymentTransactionResponse`, `VALIDATED_SUCCESS`, `initiated_by_name=None`; second resolve → 400 `Only transactions in RISK_HOLD can be resolved (current status: VALIDATED_SUCCESS)`; detail → `PaymentTransactionDetailResponse`, `initiated_by_name='Karim'`, five events oldest first, no `failed_reason` attribute; another workspace → 404 `Payment transaction <tran_id> not found` (detail) and 404 `Payment transaction <id> not found` (resolve); list → own row with name, other workspace `[]`; unknown `tran_id` on a terminal redirect → 404 `Unknown tran_id: nope`; cancel redirect on a resolved row → status unchanged. **Not run:** anything over HTTP; two concurrent sessions.

## Review
> All answers applied (2026-11-21). Blocks below are the record of why.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A refused checkout start comes back as 502 and the response never carries `failed_reason` | bug — BUG-019 (existing; service part) | precedent (manager spec Q1) |
| P2 | The detail page's event read is not limited to the caller's workspace | bug — BUG-1191 (existing; service part) | house rule HR-16 (event DAO FU-1) |
| P3 | Risk resolution reads the row without a lock | bug — BUG-029 (existing; lock lives in manager + DAO) | house rule HR-10 |
| P4 | Ledger list and event history have no tie-break on equal timestamps | bug — BUG-2402, BUG-1190 (existing; DAO) | house rule HR-6 |
| Q1 | The ledger and the detail page do not show why a start was refused, nor whether an outcome was gateway-verified | bug — BUG-3022 | Claude, delegation 2026-11-21 |
| Q2 | The resolve-risk response has no initiator name | intended | Claude, delegation 2026-11-21 |
| Q3 | The gateway session is opened before our record of it is saved | intended | Claude, delegation 2026-11-21 |
| Q4 | A gateway outage reaches the caller as a plain 500 | intended (portal note) | Claude, delegation 2026-11-21 |
| Q5 | Starting the same checkout twice (double click, retry) opens two payable sessions | bug — BUG-3023 | owner, OQ-61 (2026-11-21) |

### House-rule violations — applied automatically
None new in this module. The house-rule bugs that touch it already exist and are carried as precedent (P2–P4).

Checked and **not** violated: **HR-1/2/3** — no name is stored or compared here. **HR-4** — payment tables have no soft-delete column. **HR-5/7** — the list's only filter (workspace) is in the query before `skip`/`limit`; `GET /payments/` bounds `0 ≤ skip`, `1 ≤ limit ≤ 200`. **HR-8** — no `LIKE`. **HR-9** — no "last changed by" stamp; `risk_resolved_by` is the decision itself. **HR-11/12/13/14** — decided in the manager (BUG-019, BUG-023 … 027, BUG-030 … 032); this service commits whatever the manager decided and adds no outcome of its own. **HR-15** — no money is computed or rounded here. **HR-16** — every authenticated read and `resolve_risk` are scoped to the caller's workspace (404 otherwise, verified); the callbacks read across workspaces on purpose (no workspace context from the gateway) and return nothing to the caller but a redirect or `{"status": "received"}`.

**Permission checks:** none in the service. The endpoint allows only the workspace owner to call `resolve_risk` (403 `Only the workspace owner can resolve a risk hold`); every other authenticated route is open to any active member (integration-only; see visibility notes in the report).

### Precedent matches — confirm all with ok

### P1. A refused checkout start is a 502, and `failed_reason` is never in the response — 🐞 BUG-019 (existing)
**Background:** The manager spec decided (Q1, HR-13) that a refused start is saved as an `INIT_FAILED` transaction with the gateway's `failed_reason` and returned normally; it names this service as the place that fills `InitiatePaymentResponse.failed_reason`.
**What happens today:** the manager raises 502; the service rolls back and re-raises it; `failed_reason` is always `None` on an accepted start (verified).
**Example:** SSLCommerz answers "Store is de-active". The user sees `502 SSLCommerz session initiation failed: Store is de-active` and the ledger has no row.
**Rules affected:** `initiate_payment` R3, R3a.
**Answer:** bug — per BUG-019 precedent: the refused start is committed and the response carries `status = "INIT_FAILED"` and the stored `failed_reason` (precedent — confirmed under the reviewer's delegation, 2026-11-21)
**Resolution:** service part of BUG-019 (no new ID). Rules: `initiate_payment` R3, R3a.

### P2. The detail page reads the event history without the workspace — 🐞 BUG-1191 (existing)
**Background:** The event DAO spec (FU-1) requires `get_by_payment_transaction` to take `workspace_id`, and this service to pass it.
**What happens today:** only the transaction id is passed; an event row of workspace A attached to workspace B's transaction shows in B's detail, metadata included (verified in the event DAO review).
**Example:** see `payment_transaction_event.spec.md` R2.
**Rules affected:** `get_transaction_by_tran_id` R4a.
**Answer:** bug — per BUG-1191 precedent: the service passes the caller's `workspace_id` to the event read (precedent — confirmed under the reviewer's delegation, 2026-11-21)
**Resolution:** service part of BUG-1191 (no new ID). Rule: `get_transaction_by_tran_id` R4a.

### P3. Risk resolution is not locked — 🐞 BUG-029 (existing)
**Background:** HR-10; the manager spec `resolve_risk` R6a and the DAO spec R5 / FU-1 fix it with `FOR UPDATE OF payment_transactions` (a plain `FOR UPDATE` is refused by Postgres on that outer join, 0A000).
**What happens today:** no lock; two simultaneous resolves can both succeed.
**Example:** the owner double-clicks "Approve" in two tabs; both return 200 and two `risk_resolved` events are saved.
**Rules affected:** `resolve_risk` R2a (service part: the lock lasts until this service commits or rolls back).
**Answer:** bug — per BUG-029 precedent (precedent — confirmed under the reviewer's delegation, 2026-11-21)
**Resolution:** service part of BUG-029 (no new ID): the lock is held until this service commits or rolls back. Rule: `resolve_risk` R2a.

### P4. Ledger list and event history have no tie-break — 🐞 BUG-2402, BUG-1190 (existing)
**Background:** HR-6. Both fixes live in the DAOs; this service passes the order through unchanged.
**What happens today:** rows with one `created_at` come back in physical order.
**Example:** see `payment_transaction.spec.md` `list_by_workspace_with_initiator` R4 and `payment_transaction_event.spec.md` R6.
**Rules affected:** `list_transactions` R2, `get_transaction_by_tran_id` R5.
**Answer:** bug — per BUG-2402 / BUG-1190 precedent (precedent — confirmed under the reviewer's delegation, 2026-11-21)
**Resolution:** fixes live in the DAOs (no new ID); this service passes the order through. Rules: `list_transactions` R2, `get_transaction_by_tran_id` R5.

### New questions — decided under the reviewer's delegation (2026-11-21)

### Q1. The ledger does not show why a checkout start was refused, or whether an outcome was confirmed by the gateway — 🐞 BUG-3022
**Background:** Two approved manager fixes add columns to `payment_transactions`: `failed_reason` (BUG-019: the gateway's reason for refusing to open a session, on `INIT_FAILED` rows) and `outcome_verified` (BUG-026: `false` when a `VALIDATED_FAILED` / `CANCELLED` came from an unchecked browser redirect and can still be replaced by a later verified result). The ledger list, the detail page and the resolve-risk answer all use one response schema, `PaymentTransactionResponse`, built from the row.
**What happens today:** the response schema has neither field, so once the columns exist the ledger still cannot show them (verified: the detail object has no `failed_reason` attribute). Only the start call's own answer carries `failed_reason` (P1).
**Example:** A workspace owner opens the billing page. One row reads `INIT_FAILED` with no reason; the owner cannot tell "store de-activated" from "amount rejected". Another reads `CANCELLED`; the owner cannot tell a customer's real cancellation at the gateway from a stale tab's cancel redirect that a later IPN may still turn into a 5,000 BDT payment.
**Rules affected:** `_to_response` R1a.
**Answer:** bug — `PaymentTransactionResponse` (and so the list, the detail and the resolve-risk answer) carries `failed_reason: str | None` and `outcome_verified: bool` as stored (best-practice default, delegated by reviewer)
**Resolution:** BUG-3022 (best-practice default, delegated by reviewer, 2026-11-21). Fix in `PaymentTransactionInDB`; frontend types follow (BUG-3024). Rule: `_to_response` R1a.

### Q2. The resolve-risk answer has no initiator name — ✅ intended
**Resolution:** intended; rule `resolve_risk` R1 ✅.
**Background:** List and detail fill `initiated_by_name` from a join to profiles. `resolve_risk` builds the same response without it, so the field is `null` there. The DAO verify note says callers must not rely on that name.
**What happens today:** `POST /payments/{id}/resolve-risk/` returns the transaction with `initiated_by_name = null` (verified), although the profile exists.
**Example:** Karim started a payment that was held; the owner approves it. The answer says `initiated_by_name: null`; `GET /payments/` still says "Karim". The billing page refetches the list after resolving, so nobody sees the `null`.
**Rules affected:** `resolve_risk` R1.
**Answer:** intended — the action answer only confirms the new status; the list is the place for display fields (decided by Claude under the reviewer's delegation, 2026-11-21)

### Q3. The gateway session is opened before our record of it is saved — ✅ intended
**Resolution:** intended; rules `initiate_payment` R5, R6 ✅.
**Background:** Starting a checkout asks SSLCommerz for a session (it returns the payment page URL), then saves the transaction, then this service commits. If the save or the commit fails, the session exists at the gateway with no row here.
**What happens today:** the error reaches the caller, nothing is saved (TC3/TC4), and the payment page URL is never returned, so the customer never reaches that page. A gateway session nobody opens expires at the gateway; no money moves.
**Example:** The commit fails for a 1,500 BDT start. The user sees an error and tries again; a new `tran_id` and a new session are made. The first session is never used.
**Rules affected:** `initiate_payment` R5, R6.
**Answer:** intended — opening a session moves no money and the URL is only released after the commit; saving a placeholder row first would add a state for no gain (decided by Claude under the reviewer's delegation, 2026-11-21)

### Q4. A gateway outage reaches the caller as a plain 500 — ✅ intended (portal note)
**Resolution:** intended today; rules `initiate_payment` R4, `handle_gateway_callback` R4 ✅.
**Background:** The service maps no errors: whatever the gateway client raises (timeout, connection error, `NotImplementedError` when the mock is off) passes through unchanged and becomes a 500. The client interface defines no error type of its own, and the only client today is the mock, which does not raise. The approved manager rule `initiate_payment` R4 says such a failure writes no row.
**What happens today:** `init_session` raising `TimeoutError` gives the same `TimeoutError`, nothing saved (verified).
**Example:** SSLCommerz is down while a user starts a 2,000 BDT payment. The user sees "Internal Server Error" instead of "the payment gateway is unavailable, try again".
**Rules affected:** `initiate_payment` R4, `handle_gateway_callback` R4.
**Answer:** intended today — mapping needs a typed gateway error that does not exist yet; the real client should raise one and the service map it to 502/503 (portal note, decided by Claude under the reviewer's delegation, 2026-11-21)

### Q5. Starting the same checkout twice opens two payable sessions — 🐞 BUG-3023
**Background:** Every `POST /payments/initiate/` is a new attempt: a new `tran_id`, a new SSLCommerz session and a new payment page (manager `initiate_payment` R7, approved). The owner decided for manual invoice payments (OQ-61, BUG-3002) that each payment form carries a one-time code, and that the same pattern applies to starting a gateway checkout.
**What happens today:** a double click, a browser retry, or a retry after a lost answer opens a second session; both payment pages accept money.
**Example:** a workspace owner clicks "Pay 5,000 BDT" twice. Two `INITIATED` rows and two gateway sessions exist; if the customer completes both pages (two tabs), 10,000 BDT is taken.
**Rules affected:** `initiate_payment` R7, R7a–R7e.
**Answer:** bug — owner, OQ-61 (2026-11-21): one-time code per checkout form (client `Idempotency-Key` plus a unique index), as BUG-3002.
**Resolution:** BUG-3023. Pattern `missing-idempotency-key`, shared with BUG-3002. *(Requires: an optional `Idempotency-Key` header on `POST /payments/initiate/`; a new service/manager parameter `idempotency_key`; new nullable columns `idempotency_key` and a request fingerprint on `payment_transactions`; a unique index on `(workspace_id, idempotency_key)` over non-null keys.)*

## Overview
`PaymentTransactionService` draws the transaction boundaries around the SSLCommerz checkout flow. Each write calls exactly one `PaymentTransactionManager` method, commits, re-reads the row and returns it (or a schema built from it); any exception rolls everything back and is re-raised unchanged. The two reads go straight to the DAOs and shape the response. Callers: `app/api/v1/endpoints/payments.py` only — `POST /payments/initiate/` (any member), `GET /payments/`, `GET /payments/{tran_id}/` (any member), `POST /payments/{transaction_id}/resolve-risk/` (owner only), and the public gateway callbacks `/payments/success`, `/fail`, `/cancel`, `/ipn` (no login; the IPN signature is checked by the endpoint first). It protects: a transaction is finalized once (the manager's row lock is held until this service's commit or rollback); nothing half-done is ever saved; no other workspace's transaction is shown or resolved.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** SSLCommerz — patch `app.managers.payment_transaction_manager.get_sslcommerz_client` (client methods `init_session`, `validate`; see the manager spec's "Gateway client interface"); `utcnow` only where a time is asserted (`app.managers.payment_transaction_manager.utcnow`; row defaults use `app.models.payment_transaction.utcnow`); `secrets.token_hex` where the `tran_id` candidates must collide (the 500 row, `initiate_payment` R4) — patch `app.managers.payment_transaction_manager.secrets.token_hex` (the manager imports the `secrets` module and calls `secrets.token_hex(13)`, five candidates at most; each candidate is checked with an unlocked `get_by_tran_id` read, so a pre-inserted row with that `tran_id` in **any** workspace makes it "taken").
**Integration-only (idempotency):** two sessions racing on one new key (R7e1). The unit cases cover the index (its definition) and the loser's path by a pre-inserted row or a mocked `IntegrityError` (R7e2 Notes).
**Integration-only behavior:** the two-session races behind the row locks (callbacks, and `resolve_risk` after BUG-029); the endpoint's owner check, `limit`/`skip` bounds, rate limits and IPN signature check.

### Payment-flow contract (reference for the subscription portal)
Each point is a rule below; this list says where.
- **Idempotency.**
  - A gateway callback finalizes a transaction once. A repeat (same or other channel) after a verified outcome changes nothing, and its single `duplicate_ignored` event **is committed**; the caller gets the stored outcome (`handle_gateway_callback` R2, `handle_terminal_without_validation` R2).
  - A callback that fails commits nothing, not even its "received" event, so the gateway's retry (or the sweep) starts from a clean row (`handle_gateway_callback` R4).
  - A risk hold is resolved once; a second resolve gets 400 and commits nothing (`resolve_risk` R2).
  - Starting a checkout is idempotent per one-time code (BUG-3023, owner OQ-61): a call with an `Idempotency-Key` already used in the workspace with the same body returns the stored attempt, opens no second gateway session and writes nothing; the same key with another body gets 409; a call without a key is a new attempt with a new `tran_id`, as today (`initiate_payment` R7, R7a–R7e). Same pattern as manual invoice payments (BUG-3002).
- **Gateway calls and the commit.**
  - Both gateway calls this flow makes are reads that decide what to save, so they run inside the transaction, before the commit: opening the session (`initiate_payment` R5; Q3) and validating a `val_id` (`handle_gateway_callback` R3).
  - Nothing is called after the commit. A failed commit never leads to a second gateway call (`initiate_payment` R6, `handle_gateway_callback` R5).
  - Any future side effect of a **final** outcome (applying a plan, a receipt email, a notification, a refund or void call) belongs after a successful commit, once per transition, never on a `duplicate_ignored` path, with its failure logged and swallowed. That is the attachment-service pattern recorded in `docs/future/subscription-payments.md` (2026-11-05). This service has no such call today.
- **Locks.**
  - Callbacks lock the transaction row with `SELECT … FOR UPDATE` (manager `finalize_from_gateway` R1, `mark_terminal_without_validation` R1).
  - Risk resolution locks it with `FOR UPDATE OF payment_transactions` (BUG-029, DAO R5).
  - The lock lasts until this service commits or rolls back, so the gateway validation runs while it is held (`handle_gateway_callback` R3, `resolve_risk` R2a).
- **Identifiers.**
  - `tran_id` is 26 lowercase hex characters (`[0-9a-f]{26}`, manager `_generate_tran_id` R1). It is an opaque key, matched exactly and never parsed (`get_transaction_by_tran_id` R3).
  - `transaction_id` is the integer primary key from the path.
  - No business number (receipt or invoice number) exists here. When the portal adds one, its numeric part is accepted only as ASCII `^[0-9]+$` (`docs/future/subscription-payments.md` 2026-11-14; BUG-2676 family). That is not a rule of this module.

### Facts for the test designer
- Import: `from app.services.payment_transaction_service import payment_transaction_service` (module singleton) or `PaymentTransactionService()` (no arguments). All methods take `db` positionally and everything else as keywords.
- Return types: `initiate_payment` → `InitiatePaymentResponse`. `handle_gateway_callback` and `handle_terminal_without_validation` → the ORM `PaymentTransaction`. `resolve_risk` and each `list_transactions` item → `PaymentTransactionResponse`. `get_transaction_by_tran_id` → `PaymentTransactionDetailResponse` (a subclass of `PaymentTransactionResponse` with `events`).
- Rows and profiles: `make_workspace`, `make_profile(db, name=…)` from `tests/unit/factories.py`. Reach `RISK_HOLD` through `handle_gateway_callback` with a mocked `validate` answering `VALID`, matching amount and currency, `risk_level=1` (manager spec Notes: do not insert a `RISK_HOLD` row directly).

### Notes for the test designer
- Commits: as `base_service.spec.md` Notes. Under the `db` fixture `commit()` releases a savepoint. Assert "committed" with a test-level `db.rollback()` and a re-select, and "nothing saved" with a re-select that finds nothing.
- Failing commit (TC4) and failing refresh (TC5): `patch.object(db, "commit", side_effect=…)` / `patch.object(db, "refresh", side_effect=…)`.
- Lock clauses: capture SQL with a `before_cursor_execute` listener (manager spec Notes). Only the presence of the clause is a unit case.
- "Gateway called once": assert on the mocked client's `init_session` / `validate` call count after a patched failing commit.
- Idempotency (BUG-3023):
  - **Keyed row by hand:** set `idempotency_key` and `idempotency_fingerprint` together. Compute the fingerprint as R7c1 does (canonical JSON → `hashlib.sha256(...).hexdigest()`), or use any 64-hex value when the case wants a 409.
  - **Index:** find it by name in `pg_indexes` (`indexname = 'ix_payment_transactions_workspace_idempotency_key'`) and compare `indexdef` with R7a1.
  - **Race loser (R7e2) in one session:**
    1. Commit a keyed row first.
    2. Patch `PaymentTransactionDAO.get_by_workspace_and_idempotency_key` with `side_effect=[None, <real method>]`, so the first lookup misses and the re-read finds the row.
    3. Expect `init_session` called once, the insert to hit the index, and then the R7b answer or the 409.
  - **Lock clause (R7e1):** capture the lookup's SQL with the `before_cursor_execute` listener and assert it has no `FOR UPDATE`.
  - **Replay shape (R7b1):** wrap `db.commit` and `db.rollback` and expect 0 and 1. Add an unrelated pending row before the call and assert it is gone afterwards.

## Not specified
- `PaymentTransactionService.__init__` — sets `self.manager = payment_transaction_manager`, no logic.

---

## `_to_response(txn, initiated_by_name=None)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `resolve_risk`, `get_transaction_by_tran_id`, `list_transactions`)

**Purpose:** Turn a transaction row into the ledger's response shape, with the initiator's name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `txn` | `PaymentTransaction` | read by attribute (`from_attributes`) |
| `initiated_by_name` | `str \| None` | default `None`; copied as given |

**Returns:** a new `PaymentTransactionResponse`.

**Rules:**
- **R1.** Every field of `PaymentTransactionInDB` is copied from the row as stored. These are `id`, `workspace_id`, `tran_id`, `status`, `amount` (Decimal), `currency`, `cus_name`, `cus_email`, `cus_phone`, `value_a`..`value_d`, `session_key`, `gateway_page_url`, `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `risk_resolved_by`, `risk_resolved_at`, `risk_resolution_note`, `initiated_by`, `initiated_at`, `validated_at`, `created_at` and `updated_at`. `initiated_by_name` is the argument (`None` when omitted). `verify_sign` and `last_ipn_payload` are never in the response.
- **R1a.** [BUG-3022] The response also carries `failed_reason` (`str | None`) and `outcome_verified` (`bool`) as stored on the row. *(Today: neither field is in the schema. Both columns are themselves new: BUG-019 adds `failed_reason`, BUG-026 adds `outcome_verified`. The fix belongs in `app/schemas/payment_transaction.py` `PaymentTransactionInDB`.)*
- **R2.** The row is not changed.

**Errors:** none for a row read from the database. **Side effects:** none.

---

## `PaymentTransactionService.initiate_payment(db, *, workspace_id, user, request)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /payments/initiate/`, 201; any active member)

**Purpose:** Start a checkout attempt and give back where to send the customer.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | the caller's workspace (from the request header dependency) |
| `user` | `Profile` | the caller |
| `request` | `InitiatePaymentRequest` | validated by the schema; rules in manager `initiate_payment` R9–R10a |
| `idempotency_key` | `str \| None` | [BUG-3023] *new keyword parameter, default `None`*, from the optional `Idempotency-Key` header. Its length is checked **only at the endpoint**: `Header(None, alias="Idempotency-Key", min_length=1, max_length=100)`, otherwise 422. The service does not check it again, so a 101-character key passed directly fails with a `DataError` from the `String(100)` column, which is rolled back as TC3. Keys are case-sensitive, compared exactly and never trimmed |

**Returns:** `InitiatePaymentResponse(tran_id, status, gateway_page_url, failed_reason)`.

**Rules:**
- **R1.** An accepted start is committed per TC1. The new transaction (`INITIATED`) and its `initiated` event survive a later rollback. What the row and event contain follows manager `initiate_payment` R1–R2, R5–R6.
- **R2.** The response has the committed row's `tran_id`, `status = "INITIATED"` and `gateway_page_url`, re-read after the commit (TC2). `failed_reason` is `None`.
- **R3.** [BUG-019] A start the gateway refuses is committed too: the `INIT_FAILED` row and its `initiation_failed` event survive a later rollback (manager R3). No exception is raised.
- **R3a.** [BUG-019] For a refused start, the response has `status = "INIT_FAILED"`, `failed_reason` = the row's stored `failed_reason` (`"unknown error"` when the gateway gave none, manager R3), and `gateway_page_url` as stored (normally `None`). *(Today: `HTTPException` 502 `SSLCommerz session initiation failed: <reason or 'unknown error'>` reaches the caller and nothing is saved (verified); `failed_reason` is never filled. Requires the new `failed_reason` column.)*
- **R4.** Any exception from the manager reaches the caller unchanged and nothing is saved (TC3). This covers a raising gateway call (e.g. `TimeoutError`, verified; manager R4), the 500 `Could not generate a unique transaction ID`, and a schema `ValidationError` raised before the call. The service maps no error (Q4). ✅
- **R5.** The gateway session is opened before the commit. If the commit fails (TC4) or the manager fails after the session was opened (manager R8), nothing is saved and no URL is returned (Q3). ✅
- **R6.** `init_session` is called exactly once per call that opens a new attempt, even when the commit fails. Nothing calls the gateway after the commit. ✅
- **R7.** Two calls **without** an `idempotency_key`, with the same body, make two committed transactions with different `tran_id`s (manager R7, R7a).
- **R7a.** [BUG-3023] A call whose `idempotency_key` was not used before in this workspace behaves as R1–R3a, and the key and a fingerprint of the request (every `InitiatePaymentRequest` field after normalisation, R7c1, plus the caller's profile id) are stored on the new row. A refused start (R3) stores them too. *(Today: no such parameter or columns.)*
- **R7a1.** [BUG-3023] Storage. *(Requires a migration.)*
  - Column `payment_transactions.idempotency_key`: `String(100)`, NULL allowed, stored exactly as sent (no trim, case kept).
  - Column `payment_transactions.idempotency_fingerprint`: `String(64)`, NULL allowed. It holds the lowercase SHA-256 hex digest (64 characters, `^[0-9a-f]{64}$`) of the canonical JSON in R7c1.
  - Both are NULL on a call without a key (R7), and both are set on a keyed call. Never one without the other; the manager writes them together (no database check constraint).
  - Partial unique index `ix_payment_transactions_workspace_idempotency_key` on `payment_transactions (workspace_id, idempotency_key) WHERE idempotency_key IS NOT NULL`. Its `pg_indexes.indexdef` reads: `CREATE UNIQUE INDEX ix_payment_transactions_workspace_idempotency_key ON public.payment_transactions USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)`.
  - Any number of rows without a key may exist in one workspace.
  - The fingerprint and the key are written only on insert. Later status updates (callbacks, sweep, risk resolution, BUG-019 refusal) never change either column.
- **R7b.** [BUG-3023] A second call in the same workspace with the same key and the same body returns the stored attempt as R2/R3a would show it — same `tran_id`, `status`, `gateway_page_url`, `failed_reason` — with status 201 at the endpoint. No `init_session` call is made, and no row or event is written (no `duplicate_ignored` event either). This holds whatever the stored attempt's status is now (`INITIATED`, `INIT_FAILED`, `VALIDATED_SUCCESS`, …): the answer shows the current stored status; a new attempt needs a new key. *(Today: a second session and row.)*
- **R7b1.** [BUG-3023] A replay ends with a rollback. The service builds the response from the stored row, then calls `_rollback_transaction`:
  - 0 `commit` calls and exactly 1 `rollback` call;
  - any change already pending in the session is discarded, as TC3 does;
  - the stored row is unchanged (`updated_at` included);
  - no event of any type is written (no `duplicate_ignored`) and `_generate_tran_id` is not consulted.

  The response is built from the stored row as R2/R3a build it, and `gateway_page_url` and `failed_reason` are taken as stored. The race loser in R7e2 also ends this way, after its first rollback. *(Aligned with `invoice_payment_service` R9f–R9h, 2026-11-21.)*
- **R7c.** [BUG-3023] The same key with a different body (any field, or another member of the workspace) gets 409 `This idempotency key was already used for a different payment`. Nothing is written and no gateway call is made. The 409 is raised inside the service's `try`, so it rolls back once as TC3: anything else pending in the session is discarded too. The key belongs to the member who first used it: the caller's profile id is in the fingerprint, so another member's identical body gets 409 and never sees the first attempt. One rule with BUG-3002 and the future portal (coordinator, 2026-11-21).
- **R7c1.** [BUG-3023] "Same body" means the same canonical fingerprint. It is computed from the **validated** request, before the manager fills in defaults from the profile.
  - **Canonical object.** The keys are `amount`, `currency`, `cus_phone`, `cus_name`, `cus_email`, `value_a`, `value_b`, `value_c`, `value_d` and `profile_id`, serialised as `json.dumps(obj, sort_keys=True, separators=(",", ":"))`, UTF-8 encoded and hashed with SHA-256.
  - **Amount** is compared by value. It is written as `format(amount.normalize(), "f")`, so `500`, `500.0` and `500.00` all give `"500"`, `500.50` gives `"500.5"`, and `500.00` vs `500.01` is a different body (`"500"` vs `"500.01"`). It is not rounded.
  - **Omitted fields** are the same as their default: `currency` omitted is the same as `"BDT"`.
  - **`currency`** is compared as the schema leaves it. After BUG-022 the schema upper-cases it, so `"bdt"` is the same body as `"BDT"`. Before BUG-022, `"bdt"` is a different body.
  - **Text** (`currency`, `cus_phone`, `cus_name`, `cus_email`, `value_a`..`value_d`) is trimmed, and its case is kept. A value that is omitted, `null`, empty or whitespace-only becomes `null`. So `" Ali "` is the same body as `"Ali"`, and `"Ali"` is a different body from `"ali"`. The request has no dates.
  - **`cus_name` / `cus_email` omitted** stays `null` in the fingerprint, even though the manager stores the profile's name and email. Because `profile_id` is in the fingerprint, this changes no answer.
  - **`cus_phone`** (required) is trimmed like any other text.
  - **`profile_id`** is the caller's `Profile.id`, as an integer.
  - **Example.** Profile 7 sending `amount=500`, `cus_phone="01700000000"` gives the canonical JSON (keys sorted, so `currency` comes before `cus_email`: `"cur" < "cus"`) `{"amount":"500","currency":"BDT","cus_email":null,"cus_name":null,"cus_phone":"01700000000","profile_id":7,"value_a":null,"value_b":null,"value_c":null,"value_d":null}`. Its SHA-256 hex, the stored fingerprint, is `0bbacdbcb2eb158eba9bfab58060dd04bea674cddc22a51a78dd49db87a949bd`. The rule text (`sort_keys=True`) decides; any test JSON must be built in this order (or with `sort_keys=True`).
  - The key itself is not part of the fingerprint. *(Decided by Claude under the reviewer's delegation, 2026-11-21, following the coordinator's rule; the same normalisation applies to BUG-3002.)*
- **R7d.** [BUG-3023] The same key in another workspace is unrelated: it starts a new attempt there (index is per workspace; HR-16 — nothing of the other workspace is shown).
- **R7e.** [BUG-3023] The key is looked up **before** the gateway is called. If two calls with the same new key race, the one that loses on the unique index rolls back and answers as R7b (same body) or R7c (different body), never 500; its own gateway session is never returned and expires unused (as Q3). The race is integration-only; the unit case is "the index exists and a pre-inserted row with the key gives R7b/R7c".
- **R7e1.** [BUG-3023] The key lookup.
  - It is a new DAO read, `PaymentTransactionDAO.get_by_workspace_and_idempotency_key(db, *, workspace_id, idempotency_key)`. It returns the row or `None`.
  - It runs first in the manager's `initiate_payment`, before `_generate_tran_id` and before `init_session`.
  - It is a single-table `SELECT` on `payment_transactions`, with no join and **no row lock**: no `FOR UPDATE` clause of any kind appears in its SQL.
  - Why no lock:
    - On the first use of a key there is no row yet, and `FOR UPDATE` cannot lock a row that does not exist.
    - On a repeat, the fields the answer depends on (`idempotency_fingerprint`, `tran_id`) never change after the insert.
    - Concurrent first uses are serialised by the unique index (R7e2).
    - If the read is ever widened to join the initiator's profile, it still takes no lock. Any future lock on such a joined read must be `FOR UPDATE OF payment_transactions` (BUG-029).
  - The service passes the key through as the new keyword `idempotency_key` of `PaymentTransactionManager.initiate_payment`.
- **R7e2.** [BUG-3023] What the loser of a race does. The row is inserted **after** the gateway call (R5, Q3 ✅), so both racing calls pass the lookup and both call `init_session` once.
  - The loser's insert (the manager's flush) waits on the winner's uncommitted index entry. When the winner commits, the loser gets `IntegrityError` on `ix_payment_transactions_workspace_idempotency_key`.
  - The service then:
    1. rolls back once;
    2. re-reads the winner's row with the R7e1 lookup;
    3. answers as R7b if the fingerprints match, or raises 409 as R7c if they don't.
  - On both paths the loser rolls back more than once: after the `IntegrityError`, and again when the replay ends (R7b1) or the 409 is raised. That is harmless (base B6), and tests assert "at least one rollback, nothing saved".
  - Nothing more is written or committed, and the loser's `tran_id`, session and gateway URL are never returned. Its SSLCommerz session expires unused: no money can move through it, because no row carries its `tran_id`, so any callback for it is "unknown `tran_id`" (manager rules).
  - An `IntegrityError` on any other constraint, or one where the re-read finds no row, is re-raised unchanged after the rollback (TC3).
  - A second gateway session for the loser is therefore **not** prevented, only never exposed. Preventing it would mean saving the row before the gateway call, which reverses Q3; that is a portal note, not a rule here. *(Decided by Claude under the reviewer's delegation, 2026-11-21.)*
- **R8.** If the re-read after the commit fails, the exception reaches the caller and the transaction stays saved (TC5).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| gateway refuses (today, until BUG-019) | `HTTPException` 502 | `SSLCommerz session initiation failed: <reason>` |
| gateway call raises | its exception, unchanged | — |
| 5 `tran_id` candidates all taken | `HTTPException` 500 | `Could not generate a unique transaction ID` |
| [BUG-3023] key reused with a different body, or by another member (R7c, R7c1) | `HTTPException` 409 | `This idempotency key was already used for a different payment` |
| [BUG-3023] lost the race on `ix_payment_transactions_workspace_idempotency_key` (R7e2) | none (replay answer) or `HTTPException` 409 as above | — |
| [BUG-3023] `IntegrityError` on another constraint, or the winner's row not found on re-read | the `IntegrityError`, unchanged | — |
| commit / refresh fails | its exception, unchanged | — |

**Side effects:** one gateway `init_session` call per new attempt (none for a repeated key). One transaction row and one event, flushed by the manager and committed here. Rollback on any error.

---

## `PaymentTransactionService.handle_gateway_callback(db, *, tran_id, val_id, source)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`/payments/success` and `/payments/fail` when a `val_id` is posted, `source` `"redirect_success"` / `"redirect_fail"`; `/payments/ipn` after the signature check, `source` `"ipn"`; no login)

**Purpose:** Commit the outcome of a gateway callback that carries a `val_id`.

**Inputs:** `tran_id`, `val_id`, `source` — strings, passed to the manager unchanged (manager `finalize_from_gateway` Inputs).

**Returns:** the transaction (ORM `PaymentTransaction`), re-read after the commit.

**Rules:**
- **R1.** Whatever the manager decides is committed and survives a later rollback (TC1). The decision can be a verified outcome, a rejection of a foreign or unknown `val_id`, or the replacement of an unverified outcome; it follows manager `finalize_from_gateway` R1–R7 and `_apply_validation_result` R1–R12. That includes both events of the R4 path (received, then outcome or rejection).
- **R2.** A repeat callback for a transaction whose outcome is final (manager R3) leaves the status and gateway fields unchanged and commits exactly one `duplicate_ignored` event. The returned row shows the stored outcome. Example: a risky IPN gives `RISK_HOLD`, the same IPN again returns `RISK_HOLD`, and the saved events are `initiated, ipn_received, risk_hold, duplicate_ignored` (verified).
- **R3.** The transaction row is locked (`SELECT … FOR UPDATE`, manager R1) from the lookup until this method's commit or rollback. The gateway `validate` call runs while the lock is held. The lock clause is a unit case; the race between two sessions is integration-only.
- **R4.** If anything fails, nothing of the call is saved, including the "received" event the manager already flushed (manager R6), and the exception reaches the caller unchanged (TC3). Examples: unknown `tran_id` → 404 `Unknown tran_id: <tran_id>`; `validate` raising → its exception (a 500 at the endpoint, which the gateway retries for the IPN). The row stays as it was, so a later callback or the sweep processes it normally. ✅
- **R5.** `validate` is called at most once per call and never after the commit. A failed commit (TC4) saves nothing and causes no further gateway call.
- **R6.** If the re-read fails after the commit, the outcome stays saved (TC5).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no transaction with `tran_id` | `HTTPException` 404 | `Unknown tran_id: <tran_id>` |
| gateway `validate` raises | its exception, unchanged | — |
| commit / refresh fails | its exception, unchanged | — |

**Side effects:** at most one gateway `validate` call; field updates and events per the manager; commit, or rollback on error.

---

## `PaymentTransactionService.handle_terminal_without_validation(db, *, tran_id, terminal_status, source)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public. Callers: `/payments/success` and `/payments/fail` without `val_id`, which pass `"VALIDATED_FAILED"` with source `"redirect_success_no_val_id"` / `"redirect_fail_no_val_id"`; `/payments/cancel` always, which passes `"CANCELLED"` with source `"redirect_cancel"`. No login.

**Purpose:** Commit a browser redirect's outcome that cannot be checked with the gateway.

**Inputs:** `tran_id`, `terminal_status`, `source` — strings, passed to the manager unchanged (manager `mark_terminal_without_validation` Inputs).

**Returns:** the transaction (ORM `PaymentTransaction`), re-read after the commit.

**Rules:**
- **R1.** For an `INITIATED` transaction, the unverified outcome and its one event are committed (TC1). What they contain follows manager `mark_terminal_without_validation` R3–R3b, and after BUG-026 the outcome stays replaceable.
- **R2.** For any other status, the status is unchanged and exactly one `duplicate_ignored` event is committed (manager R2). Example: a cancel redirect on a `VALIDATED_SUCCESS` row returns `VALIDATED_SUCCESS` (verified).
- **R3.** The row lock is held until commit or rollback, as `handle_gateway_callback` R3. No gateway call is made.
- **R4.** Any failure saves nothing and reaches the caller unchanged (TC3, TC4). Examples: unknown `tran_id` → 404 `Unknown tran_id: <tran_id>` (verified); `terminal_status` over 20 characters → `DataError` (manager R4; callers never pass one). A failing re-read leaves the outcome saved (TC5).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no transaction with `tran_id` | `HTTPException` 404 | `Unknown tran_id: <tran_id>` |
| `terminal_status` > 20 chars | `DataError` | not asserted |
| commit / refresh fails | its exception, unchanged | — |

**Side effects:** status, `validated_at` and one event (or only one event), committed; no gateway call.

---

## `PaymentTransactionService.resolve_risk(db, *, transaction_id, workspace_id, user_id, approve, note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /payments/{transaction_id}/resolve-risk/`; the endpoint allows only the workspace owner, the service does not check)

**Purpose:** Commit the owner's approval or rejection of a held payment.

**Inputs:** as manager `resolve_risk` Inputs. `note` arrives 1–1000 characters from `ResolveRiskRequest`; the service passes any string.

**Returns:** `PaymentTransactionResponse` built from the row re-read after the commit, per `_to_response` with **no** initiator name.

**Rules:**
- **R1.** The decision is committed (TC1): `VALIDATED_SUCCESS` or `VALIDATED_FAILED`, the `risk_resolved_*` fields and one `risk_resolved` event, per manager R3–R5. The response shows the new status and `initiated_by_name = None` even when the initiator's profile exists (Q2, verified). ✅
- **R2.** A transaction is resolved once. A second call, sequential or (after BUG-029) concurrent, gets 400 `Only transactions in RISK_HOLD can be resolved (current status: <status>)`. Nothing of that call is saved, and the first decision and its single event stay (verified sequentially).
- **R2a.** [BUG-029] The row is read with `FOR UPDATE OF payment_transactions` (DAO `get_by_id_and_workspace_with_initiator` R5, manager R6a), and the lock lasts until this method's commit or rollback. *(Today: no lock.)*
- **R3.** A `transaction_id` of another workspace, or an unknown one, gives 404 `Payment transaction <transaction_id> not found`. Nothing is saved and nothing of the other workspace is shown (HR-16, verified).
- **R4.** Any exception rolls back and reaches the caller unchanged (TC3, TC4). A failing re-read leaves the decision saved (TC5).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown / other workspace | `HTTPException` 404 | `Payment transaction <transaction_id> not found` |
| status ≠ `RISK_HOLD` | `HTTPException` 400 | `Only transactions in RISK_HOLD can be resolved (current status: <status>)` |
| commit / refresh fails | its exception, unchanged | — |

**Side effects:** transaction update and one event, committed; no gateway call.

---

## `PaymentTransactionService.get_transaction_by_tran_id(db, *, tran_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /payments/{tran_id}/`; any member)

**Purpose:** One transaction of the workspace with its initiator's name and full event history.

**Inputs:** `tran_id` — str; `workspace_id` — int (the caller's).

**Returns:** `PaymentTransactionDetailResponse`, i.e. `_to_response(txn, initiated_by_name)` plus `events`.

**Rules:**
- **R1.** A transaction of this workspace is returned with its fields per `_to_response` R1 (and R1a). `initiated_by_name` is the initiator profile's `name`, or `None` when `initiated_by` is `NULL` (DAO R1, verified "Karim").
- **R2.** An unknown `tran_id`, or one of another workspace, gives 404 `Payment transaction <tran_id> not found`, with the requested `tran_id` in the message (verified). Nothing of the other workspace is shown.
- **R3.** `tran_id` is matched exactly: the same id in upper case, with a trailing space, or `""` gives the R2 404 (DAO `get_by_tran_id` R2). It is never parsed as a number.
- **R4.** `events` lists the transaction's events as `PaymentTransactionEventResponse`. Each has `id`, `payment_transaction_id`, `event_type`, `description`, `metadata_json`, `performed_by` and `created_at`, and no `workspace_id`. All of them are returned, with no cap.
- **R4a.** [BUG-1191] Only events whose `workspace_id` is the caller's workspace are listed: the service passes `workspace_id` to the event read (event DAO R2, FU-1). *(Today: an event row of another workspace attached to this transaction is listed, metadata included.)*
- **R5.** Events are ordered oldest `created_at` first (event DAO R5). [BUG-1190] Ties are broken by `id` ascending *(today: no tie-break)*.
- **R6.** Read only (TC6): nothing is committed or rolled back, pending changes in the session stay pending, and a 404 leaves them pending too.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown / other workspace / not an exact match | `HTTPException` 404 | `Payment transaction <tran_id> not found` |

**Side effects:** none.

---

## `PaymentTransactionService.list_transactions(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /payments/`; the endpoint bounds `skip ≥ 0`, `1 ≤ limit ≤ 200`)

**Purpose:** The workspace's payment ledger, newest first.

**Inputs:** `workspace_id` — int; `skip` — int, default 0; `limit` — int, default 100. Passed to the DAO unchanged.

**Returns:** a list of `PaymentTransactionResponse`, one per row, each per `_to_response` with the row's initiator name.

**Rules:**
- **R1.** Only this workspace's transactions, every status, are listed (DAO R1). A workspace with none, or another workspace's caller, gets `[]` (verified).
- **R2.** Order and paging follow DAO `list_by_workspace_with_initiator` R3–R6: newest `created_at` first, [BUG-2402] then `id` descending; at most `limit` items after `skip`; `limit=0` gives `[]` (unreachable from the API).
- **R3.** Each item's `initiated_by_name` is the initiator's name, or `None` when there is none (verified "Karim").
- **R4.** Read only (TC6).

**Errors:** none of its own; a negative `skip` / `limit` reaches the database as `DataError` (DAO R6; unreachable from the API).

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–22 | build response, copy name (default `None`) | `_to_response` R1, R1a, R2 |
| 33–39 | manager → commit → refresh → response | `initiate_payment` R1, R2, R3, R3a, R5–R8 |
| (new, BUG-3023) | key given? seen in workspace? same fingerprint? lost index race? | `initiate_payment` R7–R7e |
| (new, BUG-3023) | key given → both columns set / no key → both NULL | `initiate_payment` R7a1 |
| (new, BUG-3023) | lookup hit + same fingerprint → replay, no commit, one rollback | `initiate_payment` R7b, R7b1 |
| (new, BUG-3023) | lookup hit + other fingerprint (body or member) → 409, rollback | `initiate_payment` R7c, R7c1 |
| (new, BUG-3023) | normalisation: amount by value, default currency, text trimmed, blank → null | `initiate_payment` R7c1 |
| (new, BUG-3023) | lookup unlocked, single table | `initiate_payment` R7e1 |
| (new, BUG-3023) | `IntegrityError` on the key index → rollback, re-read, replay / 409; other `IntegrityError` or re-read miss → re-raise | `initiate_payment` R7e2 |
| 37–38 | response fields; `failed_reason` not passed (BUG-019) | `initiate_payment` R2, R3a |
| 40–42 | any exception → rollback, re-raise | `initiate_payment` R4, R5; TC3/TC4 |
| 45–49 | manager → commit → refresh → row | `handle_gateway_callback` R1–R3, R5, R6 |
| 50–52 | any exception → rollback, re-raise | `handle_gateway_callback` R4 |
| 57–63 | manager → commit → refresh → row | `handle_terminal_without_validation` R1–R3 |
| 64–66 | any exception → rollback, re-raise | `handle_terminal_without_validation` R4 |
| 71–78 | manager → commit → refresh → response without name | `resolve_risk` R1, R2, R2a |
| 79–81 | any exception → rollback, re-raise | `resolve_risk` R2, R3, R4 |
| 86–88 | workspace-scoped lookup with name | `get_transaction_by_tran_id` R1, R3 |
| 89–90 | `None` → 404 | `get_transaction_by_tran_id` R2, R3 |
| 92 | event read, no workspace (BUG-1191) | `get_transaction_by_tran_id` R4, R4a, R5 |
| 93–97 | detail response with events | `get_transaction_by_tran_id` R1, R4, R6 |
| 102–105 | DAO list, map each pair (loop empty / one / many) | `list_transactions` R1–R4 |

## Gap log
- G1 (`payment_transaction_service.cases.md` gap 1) — Intent (decided under the reviewer's delegation, 2026-11-21, names per the coordinator) — new `initiate_payment` R7a1: `idempotency_key` `String(100)` NULL, `idempotency_fingerprint` `String(64)` NULL (lowercase SHA-256 hex), both set together or both NULL, no DB check constraint; Notes: how to insert a keyed row by hand.
- G2 (gap 2) — Intent (coordinator rule, 2026-11-21) — new R7c1: canonical fingerprint over the validated, normalised request plus `profile_id`; amount by value via `normalize()`, omitted = default, blank optional strings = null, `currency` case per BUG-022, worked example; R7a now points to R7c1; R7c states that another member's reuse is 409 (the key belongs to the first user).
- G3 (gap 3) — Fact + intent — new R7e1: lookup `PaymentTransactionDAO.get_by_workspace_and_idempotency_key`, single-table, **no lock** and why (no row to lock on first use; fingerprint immutable; index serialises); future joined lock must be `FOR UPDATE OF payment_transactions`. New R7e2: the race loser has already called the gateway once (the row is inserted after `init_session`, code lines 69–106 of the manager), gets `IntegrityError` on the index, rolls back, re-reads, answers as replay or 409; its session is never exposed; other `IntegrityError` re-raised. Errors table gains two rows. Notes: how to drive the loser path in one session.
- G4 (gap 4) — Intent (coordinator rule) — new R7b1: a replay never commits and ends with one rollback (aligned with invoice_payment R9f–R9h), discards other pending changes, writes no event; R7c: the 409 rolls back (TC3).
- G5 (gap 5) — Intent — index name `ix_payment_transactions_workspace_idempotency_key` and its exact `pg_indexes.indexdef` text in R7a1.
- G6 (gap 6) — Fact — Externals line now names `app.managers.payment_transaction_manager.secrets.token_hex` (module import, `token_hex(13)`, five candidates, collision checked by an unlocked `get_by_tran_id` across all workspaces).
- G7 (alignment with `invoice_payment_service` R9f–R9h, request from the invoice-payment fork, 2026-11-21) — Contradiction — the replay now ends with one rollback (R7b1). The fingerprint trims every text field, and blank or null text becomes null (R7c1); `ensure_ascii` is left at its default. Key length is checked only at the endpoint, and a direct 101-character key raises `DataError` (Inputs). Key and fingerprint are never changed after insert (R7a1).
- G8 (`payment_transaction_service.notes.md` DISCREPANCY-3, coordinator decision under the delegation, 2026-11-22) — Contradiction — R7c1's worked example listed `currency` after `cus_phone`, against its own `sort_keys=True`. The rule wins: example rewritten in sorted key order with its SHA-256 `0bbacdbcb2eb158eba9bfab58060dd04bea674cddc22a51a78dd49db87a949bd` (computed with `json.dumps(obj, sort_keys=True, separators=(",", ":"))`, UTF-8). Cards IK-01, IK-02, IK-36, IK-44 must build their expected JSON in sorted order (or with `sort_keys=True`) and drop the DISCREPANCY-3 xfail reason. `invoice_payment_service` R9f checked: it states the same `sort_keys=True` rule and has no literal example, so nothing to change there.
- G9 (coordinator, 2026-11-22) — Contradiction — R7c1's "different body" example `500.001` is not a valid amount once BUG-021 limits amounts to 2 decimals; replaced by `500.00` vs `500.01`. No rule change; no card cited the old example.
