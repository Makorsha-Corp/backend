# Test cases — `app/managers/payment_transaction_manager.py`

> **Spec:** `tests/unit/managers/payment_transaction_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 — spec unchanged. Closes one gap against the current designer skill, found after verify round 2: commit-spy cards LOG-05, INIT-32, AVR-44, FIN-28, MTW-16, RR-12, REC-30, one per writer (the spec says "No commit" for each). Each runs on a path that no tagged bug touches, so each can pass today. Table format kept; all seven are `Author: claude`.
> **Revision:** 4 — spec unchanged since revision 3. Addresses verifier findings 1–3 (case-missing; surviving mutants #27, #29, #31): AVR-12 (R4), AVR-17 (R5) and AVR-21 (R7) now assert `_apply_validation_result` returns the same object on the `VALIDATED_FAILED` paths, and FIN-25 asserts `finalize_from_gateway` returns T on a failure outcome. The return-value self-check was then applied to every case: each case whose callable returns a value now asserts it on every path (106 rows gained a return assertion; INIT-01, INIT-09 and FIN-13 had theirs tightened). No case added, removed or renumbered; no Expect changed. (Revision 3: spec closed G7/G8 — RR-08 restored, RR-10/RR-11 added.)
> **Counts:** 172 cases · 108 expected-to-pass · 64 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `_log_event` 5 · `_generate_tran_id` 5 · `initiate_payment` 32 (14 bug; 7 build the schema directly) · `_apply_validation_result` 44 (19 bug) · `finalize_from_gateway` 28 (13 bug) · `mark_terminal_without_validation` 16 (4 bug) · `resolve_risk` 12 (4 bug) · `reconcile_stuck_transactions` 30 (10 bug)
- **Revision 4 changes:** return values are now asserted in every case whose callable returns something, on every path (verifier findings 1–3: `_apply_validation_result` on the three `VALIDATED_FAILED` paths, and `finalize_from_gateway` on a failure outcome). `_apply_validation_result` / `finalize_from_gateway` / `mark_terminal_without_validation` / `resolve_risk` cases check identity (`is T`/`is H`); `initiate_payment` cases check the returned txn's `id` equals the re-read row's; sweep cases check the returned list. Case count unchanged.
- **Regression protection:** a bug case that also checks something that works today is split in two. A passing case holds the part that does not depend on the bug, and the xfail case keeps only the buggy assertions. The standard row T is inserted without `failed_reason`/`outcome_verified`.
- **Notable design choices:**
  - Untagged cases reach verified/unverified states and `RISK_HOLD` only through the manager's own methods. Only BUG-026 cases set `outcome_verified` on insert, so they fail at construction today.
  - In the `resolve_risk` cases, the setup's `_apply_validation_result` runs with `utcnow` returning V0 and the action runs with NOW, so "`validated_at` unchanged" can be told apart from `risk_resolved_at`.
  - AVR-41 and AVR-43 (a rejection leaves `outcome_verified` alone) are marked BUG-026 but also need BUG-023 fixed. REC-14 also needs BUG-025. Strict xfail stays correct until both bugs are fixed.
  - Race simulation: only REC-07 (the gateway mock's side effect resolves a later candidate). No internal method is patched.
  - DB-error cases run the action inside a savepoint. REC-29 forces a `DataError` on a candidate update with a 51-char `risk_title`, per the spec's recipe.
- **Needs a decision:** None.

## Conventions for this module

**ID prefixes:** `PTM` = payment_transaction_manager. Methods: `LOG` = `_log_event`, `GEN` = `_generate_tran_id`, `INIT` = `initiate_payment` (incl. `InitiatePaymentRequest` schema cases), `AVR` = `_apply_validation_result`, `FIN` = `finalize_from_gateway`, `MTW` = `mark_terminal_without_validation`, `RR` = `resolve_risk`, `REC` = `reconcile_stuck_transactions`. IDs below are written without the `PTM-` prefix. The full ID is `PTM-<id>`, e.g. `PTM-AVR-07`.

**Actors and rows:**
- W1, W2 = two workspaces. U1 = a profile in W1 with name `"Rahim Uddin"` and email `"rahim@example.com"`. U2 = a profile in W2.
- `A26` = `"a"*26`, `B26` = `"b"*26`, and so on (26-character lowercase-hex tran_ids).
- **T** = one `payment_transactions` row, unless the case says otherwise: workspace W1, `tran_id=A26`, `status="INITIATED"`, `amount=Decimal("500.00")`, `currency="BDT"`, `cus_phone="01711000000"`, `initiated_by=U1.id`, `initiated_at = NOW − 2h`, `updated_at = datetime(2026, 1, 1, 0, 0)`. `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`, `validated_at` and all `risk_resolved_*` are `None`. **`failed_reason` and `outcome_verified` are not passed on insert** unless the case says so, because neither column exists today. "T in W2" means the same row with workspace W2 and `initiated_by=U2.id`.
- **V0** = `datetime(2026, 9, 27, 11, 0, 0)`, an earlier `validated_at` for rows that already have one.
- A case that inserts a row with `outcome_verified=…` is always a BUG-026 case. Until the column exists it fails at construction (TypeError), which is expected.
- A `RISK_HOLD` row is never inserted directly without `outcome_verified=True` (spec note: a `RISK_HOLD` row with `false` is not a valid state). Untagged cases reach `RISK_HOLD` with `_apply_validation_result(session, <row>, OK with risk_level=1, risk_title="Suspicious card", "ipn callback")`.

**Time:** every datetime is **naive** UTC (`tzinfo=None`), per the spec. `app.managers.payment_transaction_manager.utcnow` is patched in every test to return **NOW = `datetime(2026, 9, 27, 12, 0, 0)`**. Model-default `utcnow`s are not patched. Rows that need specific `initiated_at`/`updated_at` values set them on insert.

**Gateway:** `app.managers.payment_transaction_manager.get_sslcommerz_client` is patched in every test to return a mock client with these defaults:
- `init_session` → `InitSessionResult(status="SUCCESS", session_key="SESS-1", gateway_page_url="https://sandbox.example/pay/SESS-1", failed_reason=None)`. "Gateway request" = the single positional argument, `init_session.call_args.args[0]` (an `InitSessionRequest`).
- `validate` → **OK** = `ValidationResult(status="VALID", tran_id=A26, val_id="VAL-1", amount=Decimal("500.00"), currency="BDT", risk_level=0, risk_title="Safe", bank_tran_id="BANK-1", card_type="VISA-Brac bank", verify_sign="SIG-1")`. "OK with X" means OK with field X overridden.
- `query_by_tran_id` → a side effect that accepts `(tran_id, *args, **kwargs)` and returns `ValidationResult(status="UNATTEMPTED", tran_id=<that tran_id>)` with every other field `None`. "query called for X" means its first positional argument was X's tran_id.
- "Gateway fields" = `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`.

**Events:** "E(type, "desc")" means one `payment_transaction_events` row with that `event_type` and exact `description`, `payment_transaction_id` = the txn's id, `workspace_id` = the txn's workspace, and `performed_by=None`, `metadata_json=None` unless the case says otherwise. "Events: E1, E2" means exactly these events for that txn, in id order. "1 event, description D" asserts the count and the description but **not** the type (used in passing cases where only the type is buggy). Event counts are always re-read from the DB.

**Re-read:** query the row again from the DB after the call (expire the session objects first), not only the returned object.

**DB-error cases** (DataError / IntegrityError at flush): the action runs inside `session.begin_nested()`. After the expected error, roll back the savepoint, then re-read.

**SQL capture:** a SQLAlchemy `before_cursor_execute` listener on the test connection records every statement executed during the action. "SELECT … FOR UPDATE on payment_transactions" means at least one captured statement selects from `payment_transactions` and contains `FOR UPDATE`.

**Rolled back.** `sp = session.begin_nested()` directly before the call, plus a spy that wraps `session.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after rollback" checks. One card per writer. The spy is sanctioned by the test environment; it is not a mock of the session's behaviour.

**Race simulations:**
- REC-07 (`reconcile_stuck_transactions` R3): while handling candidate A, the `query_by_tran_id` side effect loads candidate B through the same session (`session.get`), sets `B.status="VALIDATED_SUCCESS"` and flushes. It then returns the UNATTEMPTED default for A. This simulates a live callback resolving B between candidate selection and B's locked re-read. No internal method of the manager is patched.

---

## `PaymentTransactionManager._log_event`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LOG-01 | R1 | happy | T in W2 | `_log_event(session, T, "initiated", "Checkout session created for 500 BDT", performed_by=U2.id, metadata={"session_key": "SESS-1"})` | returns `None`; re-read: exactly 1 event for T, with `id` not None, `workspace_id=W2`, `payment_transaction_id=T.id`, `event_type="initiated"`, `description="Checkout session created for 500 BDT"`, `performed_by=U2.id`, `metadata_json={"session_key": "SESS-1"}`, `created_at` not None | pass |
| LOG-02 | R1 | side-effect | T in W1 | `_log_event(session, T, "expired", "x")` (no `performed_by`, no `metadata`) | returns `None`; re-read: exactly 1 event, `event_type="expired"`, `description="x"`, `performed_by=None`, `metadata_json=None`, `workspace_id=W1` | pass |
| LOG-03 | R2 | boundary | T | `_log_event(session, T, "e"*50, "fifty")` | returns `None`; re-read: 1 event with `event_type == "e"*50` | pass |
| LOG-04 | R2; Errors row 1 | error | T | `_log_event(session, T, "e"*51, "fifty-one")` inside savepoint | raises SQLAlchemy `DataError`; after savepoint rollback: 0 events for T; T still exists | pass |
| LOG-05 | Side effects (no commit) | side-effect | T in W1; savepoint and commit spy per **rolled back** | `_log_event(session, T, "expired", "x")` | returns `None`; count: exactly 1 event for T; count after rollback: 0 events for T; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager._generate_tran_id`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| GEN-01 | R1, R4 | happy | T (tran_id A26) in W1; record the count of transactions and events | `_generate_tran_id(session)` (no patch on `token_hex`) | returns a str matching `^[0-9a-f]{26}$`, ≠ A26; transaction count and event count unchanged | pass |
| GEN-02 | R1 | isolation | T in **W2** with tran_id A26; `token_hex` patched to return A26, then B26 | `_generate_tran_id(session)` | returns B26 (the check is global, so a W2 tran_id counts as used); `token_hex` called 2 times | pass |
| GEN-03 | R2 | boundary | no transactions; `token_hex` patched to return C26, then D26 | `_generate_tran_id(session)` | returns C26; `token_hex` called exactly once | pass |
| GEN-04 | R2 | boundary | transactions in W1 with tran_ids `"1"*26`, `"2"*26`, `"3"*26`, `"4"*26`; `token_hex` returns those four, then `"5"*26` | `_generate_tran_id(session)` | returns `"5"*26`; `token_hex` called exactly 5 times | pass |
| GEN-05 | R3, R4; Errors row 1 | error | transactions with tran_ids `"1"*26`…`"5"*26`; `token_hex` returns those five, then `"6"*26` | `_generate_tran_id(session)` | raises `HTTPException` 500, detail `"Could not generate a unique transaction ID"`; `token_hex` called exactly 5 times (never a 6th); transaction count unchanged (5); no events | pass |

## `PaymentTransactionManager.initiate_payment`

Default request **REQ** = `InitiatePaymentRequest(amount=Decimal("500"), currency="BDT", cus_phone="01711000000")` (no name, email or value_a..d). The call is `initiate_payment(session, workspace_id=W1, user=U1, request=…)` unless stated. W1 has no transactions before the call.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INIT-01 | R5, R2 | happy | default gateway (SUCCESS, SESS-1) | REQ with `cus_name="Karim"`, `cus_email="karim@example.com"` | returns a txn whose `id` equals the re-read row's `id`, with `status="INITIATED"`; `init_session` called once; gateway request `cus_name="Karim"`, `cus_email="karim@example.com"`, `cus_phone="01711000000"`; re-read: exactly 1 txn in W1 with `workspace_id=W1`, `tran_id` = gateway request's `tran_id`, `status="INITIATED"`, `amount=Decimal("500.00")`, `currency="BDT"`, `cus_name="Karim"`, `cus_email="karim@example.com"`, `cus_phone="01711000000"`, `value_a..value_d=None`, `session_key="SESS-1"`, `gateway_page_url="https://sandbox.example/pay/SESS-1"`, `initiated_by=U1.id`; `val_id`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`, `last_ipn_payload`, `validated_at`, `risk_resolved_by`, `risk_resolved_at`, `risk_resolution_note` all `None`; `initiated_at`, `created_at`, `updated_at` not None (**no** `failed_reason` assertion, see INIT-30) | pass |
| INIT-02 | R6 | side-effect | default gateway | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); re-read: events for the txn = E(`initiated`, `"Checkout session created for 500 BDT"`) with `performed_by=U1.id` and `metadata_json={"session_key": "SESS-1"}` | pass |
| INIT-03 | R6 | boundary | default gateway | REQ with `amount=Decimal("500.00")` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); the one event's description is `"Checkout session created for 500.00 BDT"` | pass |
| INIT-04 | R5, R6 | side-effect | `init_session` returns `InitSessionResult(status="SUCCESS", session_key=None, gateway_page_url=None)` | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); re-read: txn `session_key=None`, `gateway_page_url=None`, `status="INITIATED"`; event `initiated` has `metadata_json={"session_key": None}` | pass |
| INIT-05 | R2 | happy | default gateway | REQ (name and email omitted → `None`) | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `cus_name="Rahim Uddin"`, `cus_email="rahim@example.com"`; re-read txn has the same two values | pass |
| INIT-06 | R2 | boundary | default gateway | REQ with `cus_name=""`, `cus_email=""` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `cus_name="Rahim Uddin"`, `cus_email="rahim@example.com"`; re-read txn has the same two values | pass |
| INIT-07 | R1a [BUG-020] | bug | default gateway | REQ with `value_a="plan:pro;months:12"`, `value_b="b-val"`, `value_c="c-val"`, `value_d="d-val"` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `value_a="plan:pro;months:12"`, `value_b="b-val"`, `value_c="c-val"`, `value_d="d-val"` | xfail BUG-020 — fails today on: gateway request has no `value_a` attribute |
| INIT-08 | R1a [BUG-020] | bug | default gateway | REQ (no value_a..d) | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `value_a`, `value_b`, `value_c`, `value_d` are all `None` | xfail BUG-020 — fails today on: gateway request has no `value_a` attribute |
| INIT-09 | R3 [BUG-019] | bug | `init_session` returns `InitSessionResult(status="FAILED", failed_reason="Store is de-active")` | REQ | **no exception**; returns a txn whose `id` equals the re-read row's `id`, with `status="INIT_FAILED"`; re-read: exactly 1 txn in W1 with `status="INIT_FAILED"`, `failed_reason="Store is de-active"`, `tran_id` = gateway request's `tran_id`, `amount=Decimal("500.00")`, `currency="BDT"`, `cus_name="Rahim Uddin"`, `cus_email="rahim@example.com"`, `cus_phone="01711000000"`, `initiated_by=U1.id`, `session_key=None`, `gateway_page_url=None`, `val_id=None`, `validated_at=None`; events = E(`initiation_failed`, `"Checkout session refused by gateway: Store is de-active"`) with `performed_by=U1.id`, `metadata_json=None` | xfail BUG-019 — fails today on: `HTTPException` 502 raised, no row |
| INIT-10 | R3 [BUG-019] | bug | `init_session` returns `status="FAILED"`, `failed_reason=None` | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INIT_FAILED"`); no exception; re-read txn `status="INIT_FAILED"`, `failed_reason="unknown error"`; events = E(`initiation_failed`, `"Checkout session refused by gateway: unknown error"`) with `performed_by=U1.id` | xfail BUG-019 — fails today on: 502 raised |
| INIT-11 | R3 [BUG-019] | bug | `init_session` returns `status="FAILED"`, `failed_reason=""` | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INIT_FAILED"`); no exception; re-read txn `failed_reason="unknown error"`, `status="INIT_FAILED"`; event description `"Checkout session refused by gateway: unknown error"` | xfail BUG-019 — fails today on: 502 raised |
| INIT-12 | R3 [BUG-019] | bug | `init_session` returns `status="success"` (lowercase), `failed_reason=None`, `session_key="SESS-9"`, `gateway_page_url=None` | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INIT_FAILED"`); no exception; re-read txn `status="INIT_FAILED"`, `failed_reason="unknown error"`, `session_key="SESS-9"`, `gateway_page_url=None`; exactly 1 event, type `initiation_failed` | xfail BUG-019 — fails today on: 502 raised |
| INIT-13 | R4; Errors row 2 | error | `init_session` raises `RuntimeError("gateway down")` | REQ | the same `RuntimeError` instance propagates; re-read: 0 txns in W1, 0 events | pass |
| INIT-14 | R7 | happy | default gateway | call twice with identical REQ | each call returns its own txn (the two returned `id`s are distinct and equal the two re-read rows' `id`s); `init_session` called 2 times; re-read: 2 txns in W1, both `INITIATED`, with distinct `id`s and distinct `tran_id`s; 2 `initiated` events, one per txn | pass |
| INIT-15 | R7a [BUG-019] | bug | `init_session` returns FAILED ("Store is de-active") on the 1st call and the default SUCCESS on the 2nd | call twice with REQ | the 1st call returns the `INIT_FAILED` txn and the 2nd the `INITIATED` txn (each `id` equals the matching re-read row's `id`); no exception; re-read: 2 txns in W1 with distinct `tran_id`s, one `INIT_FAILED` and one `INITIATED` | xfail BUG-019 — fails today on: 1st call raises 502 |
| INIT-16 | R8; Errors row 3 | error | no workspace with id 999999 | `initiate_payment(session, workspace_id=999999, user=U1, request=REQ)` inside savepoint | raises SQLAlchemy `IntegrityError`; `init_session` was called once before the failure; after savepoint rollback: 0 txns with `workspace_id=999999`, 0 events | pass |
| INIT-17 | R1 via `_generate_tran_id` R3; Errors row 1 | error | T in **W2** with tran_id A26; `token_hex` patched to return A26 on all 5 calls | REQ | raises `HTTPException` 500, detail `"Could not generate a unique transaction ID"`; `init_session` not called; re-read: 0 txns in W1, 0 events | pass |
| INIT-18 | R9a [BUG-021]; Errors row 4 | bug | — (target: schema) | build `InitiatePaymentRequest(amount=Decimal("10.005"), cus_phone="01711000000")` | raises Pydantic `ValidationError` | xfail BUG-021 — fails today on: no error raised |
| INIT-19 | R9a [BUG-021]; Errors row 4 | bug | — (target: schema) | build with `amount=Decimal("10000000000000")`, `cus_phone="01711000000"` | raises Pydantic `ValidationError` | xfail BUG-021 — fails today on: no error raised |
| INIT-20 | R9, R9a boundary | boundary | — (target: schema) | build three requests with `amount` = `Decimal("10.5")`, `Decimal("10.50")`, `Decimal("9999999999999.99")` (`cus_phone="01711000000"`) | each builds without error, and `.amount` equals the given value numerically | pass |
| INIT-21 | R10a [BUG-022] | bug | — (target: schema) | build with `currency="bdt"`, `amount=Decimal("500")`, `cus_phone="01711000000"` | no error; `.currency == "BDT"` | xfail BUG-022 — fails today on: `.currency == "bdt"` |
| INIT-22 | R10 | boundary | — (target: schema) | build with `currency="BDT"`, with `currency="USD"`, and with currency omitted | `.currency` is `"BDT"`, `"USD"` and `"BDT"` respectively | pass |
| INIT-23 | R10a [BUG-022]; Errors row 4 | bug | — (target: schema) | build with `currency="XYZ"`, with `"12 "`, with `"EUR"` | each raises Pydantic `ValidationError` | xfail BUG-022 — fails today on: `"XYZ"` accepted |
| INIT-24 | R10a [BUG-022] | bug | default gateway | `initiate_payment` with `InitiatePaymentRequest(amount=Decimal("500"), currency="bdt", cus_phone="01711000000")` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `currency="BDT"`; re-read txn `currency="BDT"`; event description `"Checkout session created for 500 BDT"` | xfail BUG-022 — fails today on: gateway request and row have `"bdt"` |
| INIT-25 | R1, R5 | external | default gateway | REQ with `value_a="plan:pro;months:12"`, `value_b="b-val"`, `value_c="c-val"`, `value_d="d-val"` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); `init_session` called once with exactly one positional argument and no keyword arguments; gateway request: `tran_id` matches `^[0-9a-f]{26}$` and equals the stored txn's `tran_id`; `amount == Decimal("500")`; `currency="BDT"`; `success_url == f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/payments/success"`, `fail_url` …`/payments/fail`, `cancel_url` …`/payments/cancel`, `ipn_url` …`/payments/ipn`; `cus_name="Rahim Uddin"`, `cus_email="rahim@example.com"`, `cus_phone="01711000000"`; `product_name="Workspace Subscription"`, `product_category="subscription"`; re-read txn `value_a="plan:pro;months:12"`, `value_b="b-val"`, `value_c="c-val"`, `value_d="d-val"` (no assertion on the request's value_* fields, see INIT-07) | pass |
| INIT-26 | R9 | boundary | — (target: schema) | build with `amount=Decimal("0")`, with `Decimal("-1")`, and with `Decimal("0.01")` (`cus_phone="01711000000"`) | `0` and `-1` each raise Pydantic `ValidationError`; `0.01` builds, `.amount == Decimal("0.01")` | pass |
| INIT-27 | R9 | side-effect | default gateway | REQ with `amount=Decimal("10.5")` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `amount == Decimal("10.5")` and `str(amount) == "10.5"`; re-read txn `amount == Decimal("10.50")`; event description `"Checkout session created for 10.5 BDT"` | pass |
| INIT-28 | R9 | boundary | default gateway | REQ with `amount=Decimal("9999999999999.99")` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); no error; gateway request `amount == Decimal("9999999999999.99")`; re-read txn `amount == Decimal("9999999999999.99")` | pass |
| INIT-29 | R10 | happy | default gateway | REQ with `currency="USD"` | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); gateway request `currency="USD"`; re-read txn `currency="USD"`; event description `"Checkout session created for 500 USD"` | pass |
| INIT-30 | R5a [BUG-019] | bug | default gateway | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); re-read txn `failed_reason is None` | xfail BUG-019 — fails today on: txn has no `failed_reason` attribute |
| INIT-31 | `_apply` R12 [BUG-026] | bug | default gateway | REQ | returns the new txn (its `id` equals the re-read txn's `id`, `status="INITIATED"`); re-read txn `outcome_verified is False` | xfail BUG-026 — fails today on: txn has no `outcome_verified` attribute |
| INIT-32 | Side effects (no commit) | side-effect | default gateway (SUCCESS, SESS-1); savepoint and commit spy per **rolled back** | REQ | returns a txn whose `id` equals the re-read row's `id`, with `status="INITIATED"`; count: exactly 1 txn in W1; count: exactly 1 event in the database; count after rollback: 0 txns in W1; count after rollback: 0 events in the database; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager._apply_validation_result`

The call is `_apply_validation_result(session, T, result, "ipn callback")` with T as in Conventions (INITIATED, 500.00 BDT, `updated_at` 2026-01-01) unless stated. "Gateway fields copied" means re-read gateway fields equal the result's values. Every case also asserts that no gateway client method was called.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AVR-01 | R10, R3 | happy | T | result OK | returns the same object (`is T`); re-read: `status="VALIDATED_SUCCESS"`, `validated_at=NOW`, `val_id="VAL-1"`, `risk_level=0`, `risk_title="Safe"`, `bank_tran_id="BANK-1"`, `card_type="VISA-Brac bank"`, `verify_sign="SIG-1"`, `updated_at` ≠ 2026-01-01; events = E(`validated_success`, `"Validated successfully via ipn callback"`) | pass |
| AVR-02 | R10 | boundary | T | OK with `risk_level=None` | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`; 1 event `validated_success` | pass |
| AVR-03 | R10 | boundary | T | OK with `risk_level=2` | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `risk_level=2`; 1 event `validated_success` | pass |
| AVR-04 | R9 | happy | T | OK with `risk_level=1`, `risk_title="Suspicious card"` | returns the same object (`is T`); re-read `status="RISK_HOLD"`, `validated_at=NOW`, `risk_level=1`, `risk_title="Suspicious card"`; events = E(`risk_hold`, `"Validated via ipn callback but flagged high-risk (Suspicious card) — held for review"`) | pass |
| AVR-05 | R9 | boundary | T | OK with `risk_level=1`, `risk_title=None` | returns the same object (`is T`); re-read `status="RISK_HOLD"`; event description `"Validated via ipn callback but flagged high-risk (None) — held for review"` | pass |
| AVR-06 | R2 | boundary | T | OK with `tran_id=""` | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`; 1 event `validated_success` | pass |
| AVR-07 | R1a [BUG-023] | bug | T | OK with `tran_id=B26` | returns the same object (`is T`); re-read: `status="INITIATED"`, `validated_at=None`, `updated_at` = 2026-01-01; exactly 1 event, type `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| AVR-08 | R1a [BUG-023] | bug | T (tran_id A26) | OK with `tran_id="A"*26` (upper case) | returns the same object (`is T`); re-read `status="INITIATED"`, `validated_at=None`; 1 event, type `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| AVR-09 | R1a, R2a [BUG-023] | bug | T | result `ValidationResult(status="INVALID_TRANSACTION", tran_id=B26)` (other fields `None`) | returns the same object (`is T`); re-read `status="INITIATED"`, `validated_at=None`; 1 event, type `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| AVR-10 | R1a [BUG-023], R11 | bug | T with `status="EXPIRED"`, `validated_at=V0`, `val_id="OLD-VAL"`, `bank_tran_id="OLD-BANK"` | OK with `tran_id=B26` | returns the same object (`is T`); re-read: `status="EXPIRED"`, `validated_at=V0`; 1 event, type `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| AVR-11 | R2a [BUG-023] | bug | T | result `ValidationResult(status="INVALID_TRANSACTION", tran_id="")` (other fields `None`) | returns the same object (`is T`); re-read `status="INITIATED"`, `validated_at=None`, gateway fields all `None`; events = E(`validation_rejected`, `"Gateway validation via ipn callback returned status=INVALID_TRANSACTION; val_id rejected"`) | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| AVR-12 | R4, R3 | happy | T | OK with `status="FAILED"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`, `validated_at=NOW`, gateway fields copied (`val_id="VAL-1"` … `verify_sign="SIG-1"`); events = E(`validated_failed`, `"Gateway validation via ipn callback returned status=FAILED"`) | pass |
| AVR-13 | R4 | boundary | T | OK with `status="valid"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; event description `"Gateway validation via ipn callback returned status=valid"` | pass |
| AVR-14 | R4, R10 | boundary | T | OK with `status="VALIDATED"` | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`; 1 event `validated_success` | pass |
| AVR-15 | R4b [BUG-025] | bug | T | OK with `status="CANCELLED"` | returns the same object (`is T`); re-read `status="CANCELLED"`; exactly 1 event, type `validated_cancelled` | xfail BUG-025 — fails today on: status `VALIDATED_FAILED` |
| AVR-16 | R3, R11 | side-effect | T with `status="EXPIRED"`, `val_id="OLD-VAL"`, `risk_level=0`, `risk_title="Old"`, `bank_tran_id="OLD-BANK"`, `card_type="OLD-CARD"`, `verify_sign="OLD-SIG"` | `ValidationResult(status="FAILED", tran_id=A26, amount=Decimal("500.00"), currency="BDT")`, all gateway fields `None` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; all six gateway fields `None` | pass |
| AVR-17 | R5 | happy | T | OK with `amount=Decimal("499.99")` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`, `validated_at=NOW`, gateway fields copied; events = E(`validated_failed`, `"Amount mismatch: expected 500.00 BDT, gateway reported 499.99 BDT"`) | pass |
| AVR-18 | R5 | boundary | T (amount 500.00) | OK with `amount=Decimal("500")` | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"` (numeric equality) | pass |
| AVR-19 | R5, R8 order | boundary | T | OK with `amount=Decimal("400")`, `currency=None` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; event description `"Amount mismatch: expected 500.00 BDT, gateway reported 400 None"` | pass |
| AVR-20 | R5, R7 order | boundary | T | OK with `amount=Decimal("400")`, `currency="USD"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; event description `"Amount mismatch: expected 500.00 BDT, gateway reported 400 USD"` | pass |
| AVR-21 | R7 | happy | T | OK with `currency="USD"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`, `validated_at=NOW`, gateway fields copied; events = E(`validated_failed`, `"Currency mismatch: expected BDT, gateway reported USD"`) | pass |
| AVR-22 | R7 | boundary | T | OK with `currency="bdt"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; event description `"Currency mismatch: expected BDT, gateway reported bdt"` | pass |
| AVR-23 | R6 [BUG-024] | bug | T | OK with `amount=None` (currency `"BDT"`, risk_level 0) | returns the same object (`is T`); re-read `status="RISK_HOLD"`, `validated_at=NOW`, gateway fields copied; events = E(`risk_hold`, `"Validated via ipn callback but gateway reported no amount — held for review"`) | xfail BUG-024 — fails today on: status `VALIDATED_SUCCESS` |
| AVR-24 | R6 [BUG-024] | bug | T | OK with `amount=None`, `risk_level=1`, `risk_title="Suspicious card"` | returns the same object (`is T`); re-read `status="RISK_HOLD"`; event description `"Validated via ipn callback but gateway reported no amount — held for review"` | xfail BUG-024 — fails today on: description is the "flagged high-risk" text |
| AVR-25 | R7 over R6 | boundary | T | OK with `amount=None`, `currency="USD"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`; event description `"Currency mismatch: expected BDT, gateway reported USD"` | pass |
| AVR-26 | R8 [BUG-024] | bug | T | OK with `currency=None` (amount matches, risk_level 0) | returns the same object (`is T`); re-read `status="RISK_HOLD"`, `validated_at=NOW`; events = E(`risk_hold`, `"Validated via ipn callback but gateway reported no currency — held for review"`) | xfail BUG-024 — fails today on: status `VALIDATED_SUCCESS` |
| AVR-27 | R8 [BUG-024] | bug | T | OK with `currency=""` | returns the same object (`is T`); re-read `status="RISK_HOLD"`; event description `"Validated via ipn callback but gateway reported no currency — held for review"` | xfail BUG-024 — fails today on: status `VALIDATED_SUCCESS` |
| AVR-28 | R8 [BUG-024] | bug | T | OK with `currency=None`, `risk_level=1`, `risk_title="Suspicious card"` | returns the same object (`is T`); re-read `status="RISK_HOLD"`; event description `"Validated via ipn callback but gateway reported no currency — held for review"` | xfail BUG-024 — fails today on: description is the "flagged high-risk" text |
| AVR-29 | R6, R8 [BUG-024] | bug | T | OK with `amount=None`, `currency=None` | returns the same object (`is T`); re-read `status="RISK_HOLD"`; 1 event, description `"Validated via ipn callback but gateway reported no amount — held for review"` | xfail BUG-024 — fails today on: status `VALIDATED_SUCCESS` |
| AVR-30 | R11 | happy | T with `status="EXPIRED"`, `validated_at=V0` | result OK | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `validated_at=NOW`, `val_id="VAL-1"`; 1 event `validated_success` | pass |
| AVR-31 | R11 | happy | T inserted with `status="CANCELLED"`, `validated_at=V0` (no `outcome_verified`) | result OK | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `validated_at=NOW`; 1 event `validated_success` | pass |
| AVR-32 | R1 | happy | T | OK with `tran_id=B26` (otherwise a passing answer) | returns T; re-read: gateway fields all `None` (not copied: `val_id` ≠ `"VAL-1"`); `status` not in {`VALIDATED_SUCCESS`, `RISK_HOLD`}; exactly 1 event, description `f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"` | pass |
| AVR-33 | R1 | boundary | T (tran_id A26) | OK with `tran_id="A"*26` | returns the same object (`is T`); re-read `val_id=None`, `bank_tran_id=None`; `status` not in {`VALIDATED_SUCCESS`, `RISK_HOLD`}; exactly 1 event, description `f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={'A'*26}"` | pass |
| AVR-34 | R1, R11 | side-effect | T with `status="EXPIRED"`, `validated_at=V0`, `val_id="OLD-VAL"`, `bank_tran_id="OLD-BANK"` | OK with `tran_id=B26` | returns the same object (`is T`); re-read: `val_id="OLD-VAL"`, `bank_tran_id="OLD-BANK"`, `risk_level=None`, `risk_title=None`, `card_type=None`, `verify_sign=None`; exactly 1 event, description `f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"` | pass |
| AVR-35 | R1 before R2a | boundary | T | `ValidationResult(status="INVALID_TRANSACTION", tran_id=B26, val_id="VAL-X")` | returns the same object (`is T`); re-read `val_id=None`; exactly 1 event, description `f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"` (the R1 description, since R1 is checked first) | pass |
| AVR-36 | R4a, R3 | happy | T | OK with `status="CANCELLED"`, `amount=Decimal("1")`, `risk_level=1`, `risk_title="Suspicious card"` | returns the same object (`is T`); re-read `validated_at=NOW`; gateway fields copied (`val_id="VAL-1"`, `risk_level=1`, `risk_title="Suspicious card"`, `bank_tran_id="BANK-1"`, `card_type="VISA-Brac bank"`, `verify_sign="SIG-1"`); `status` not in {`INITIATED`, `VALIDATED_SUCCESS`, `RISK_HOLD`}; exactly 1 event, description `"Gateway validation via ipn callback returned status=CANCELLED"` (no amount or risk text) | pass |
| AVR-37 | R12 [BUG-026] | bug | T | result OK | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `outcome_verified is True` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| AVR-38 | R12 [BUG-026] | bug | T | OK with `status="FAILED"` | returns the same object (`is T`); re-read `status="VALIDATED_FAILED"`, `outcome_verified is True` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| AVR-39 | R12 [BUG-026] | bug | T | OK with `risk_level=1`, `risk_title="Suspicious card"` | returns the same object (`is T`); re-read `status="RISK_HOLD"`, `outcome_verified is True` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| AVR-40 | R12 [BUG-026] | bug | T inserted with `status="CANCELLED"`, `validated_at=V0`, `outcome_verified=False` | result OK | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`, `outcome_verified is True` | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| AVR-41 | R12 [BUG-026] (needs BUG-023 too) | bug | T inserted with `outcome_verified=True` (status INITIATED) | OK with `tran_id=B26` | returns the same object (`is T`); re-read `outcome_verified is True` | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| AVR-42 | R12 [BUG-026] | bug | T inserted without `outcome_verified` | no call | re-read T: `outcome_verified is False` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| AVR-43 | R12 [BUG-026] (needs BUG-023 too) | bug | T inserted with `outcome_verified=False` | `ValidationResult(status="INVALID_TRANSACTION", tran_id="")` | returns the same object (`is T`); re-read `outcome_verified is False` | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| AVR-44 | Side effects (no commit) | side-effect | T; savepoint and commit spy per **rolled back** | result OK | returns the same object (`is T`); re-read `status="VALIDATED_SUCCESS"`; count: exactly 1 event for T; re-read after rollback: `status="INITIATED"`, `validated_at=None`, `val_id=None`; count after rollback: 0 events for T; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager.finalize_from_gateway`

T is in **W2** (the call carries no workspace). The call is `finalize_from_gateway(session, tran_id=A26, val_id="VAL-1", source="ipn")` unless stated. "Events after setup" counts only events written by the action under test.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| FIN-01 | R1, R4 | happy | T in W2; `validate` → OK | call | returns T; `validate` called once with `"VAL-1"`; re-read: `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`, `validated_at=NOW`; events = E(`ipn_received`, `"Callback received via ipn"`), E(`validated_success`, `"Validated successfully via ipn callback"`), both `workspace_id=W2` | pass |
| FIN-02 | R1 | side-effect | T in W2; `validate` → OK; SQL capture on | call | returns T (`is T`); captured SQL contains a SELECT … FOR UPDATE on payment_transactions | pass |
| FIN-03 | R2; Errors row 1 | error | T in W2 | call with `tran_id="z"*26` | raises `HTTPException` 404, detail `f"Unknown tran_id: {'z'*26}"`; `validate` not called; re-read: 0 events in DB; T still `INITIATED` | pass |
| FIN-04 | R4a [BUG-028] | bug | T; `validate` → OK | call with `source="redirect_success"` | returns T (`is T`); the first event after the call has `event_type="redirect_success"` | xfail BUG-028 — fails today on: type `redirect_success_received` |
| FIN-05 | R4a [BUG-028] | bug | T; `validate` → OK with `status="FAILED"` | call with `source="redirect_fail"` | returns T (`is T`); the first event after the call has `event_type="redirect_fail"` | xfail BUG-028 — fails today on: type `redirect_fail_received` |
| FIN-06 | R4, `_apply` R1a [BUG-023] | bug | T; `validate` → OK with `tran_id=B26` | call | returns T (`is T`); re-read `status="INITIATED"`, `validated_at=None`; second event's type `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| FIN-07 | R3 | happy | T with `status="VALIDATED_SUCCESS"`, `val_id="VAL-ORIG"`, `validated_at=V0` | call with `val_id="VAL-NEW"` | returns T; `validate` not called; re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-ORIG"`, `validated_at=V0`; events = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_SUCCESS"`) | pass |
| FIN-08 | R3 | happy | T in W2; `_apply_validation_result(session, T, OK with risk_level=1, risk_title="Suspicious card", "ipn callback")` already called (T is `RISK_HOLD`, `val_id="VAL-1"`); `validate` → OK with `val_id="VAL-NEW"` | call with `val_id="VAL-NEW"` | returns T (`is T`); `validate` not called; re-read `status="RISK_HOLD"`, `val_id="VAL-1"`; events after setup = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already RISK_HOLD"`) | pass |
| FIN-09 | R3 | happy | T with `status="INIT_FAILED"` | call | returns T (`is T`); `validate` not called; re-read `status="INIT_FAILED"`, `val_id=None`; events = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already INIT_FAILED"`) | pass |
| FIN-10 | R3, R5 | happy | T; first call made with `validate` → OK with `status="FAILED"` (T becomes gateway-verified `VALIDATED_FAILED`); then `validate` reset to return OK with `val_id="VAL-2"` | second call with `val_id="VAL-2"` | the second call returns T (`is T`); re-read `status="VALIDATED_FAILED"`, `val_id="VAL-1"`; `validate` called once in total; events after setup = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"`) | pass |
| FIN-11 | R3c [BUG-025] | bug | T; first call made with `validate` → OK with `status="CANCELLED"`; then `validate` → OK | second call with `val_id="VAL-2"` | the second call returns T (`is T`); re-read `status="CANCELLED"`; event after setup has description `"Duplicate ipn callback ignored; transaction already CANCELLED"` | xfail BUG-025 — fails today on: status `VALIDATED_FAILED` |
| FIN-12 | R3; `resolve_risk` R3 | happy | T in W2; `_apply_validation_result(session, T, OK with risk_level=1, risk_title="Suspicious card", "ipn callback")` then `resolve_risk(session, transaction_id=T.id, workspace_id=W2, user_id=U2.id, approve=False, note="Fraud")` already called; `validate` → OK | call | returns T (`is T`); `validate` not called; re-read `status="VALIDATED_FAILED"`, `risk_resolution_note="Fraud"`, `val_id="VAL-1"`; events after setup = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"`) | pass |
| FIN-13 | R5 | happy | T; `validate` → OK on the 1st call and OK with `val_id="VAL-2"` on the 2nd | call twice (`val_id="VAL-1"`, then `"VAL-2"`) | each call returns T (`is T`); re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`; `validate` called once; event types in order = `ipn_received`, `validated_success`, then E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_SUCCESS"`) | pass |
| FIN-14 | R5a [BUG-023] | bug | T; `validate` → `ValidationResult(status="INVALID_TRANSACTION", tran_id="")` on the 1st call, and OK with `val_id="VAL-2"` on the 2nd | call with `val_id="VAL-X"`, then with `val_id="VAL-2"` | each call returns T (`is T`); after the 1st call: re-read `status="INITIATED"`; after the 2nd: `status="VALIDATED_SUCCESS"`, `val_id="VAL-2"`; `validate` called twice (`"VAL-X"`, `"VAL-2"`); event types in order = `ipn_received`, `validation_rejected`, `ipn_received`, `validated_success` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` after the 1st call |
| FIN-15 | R3a [BUG-026] | bug | T; `mark_terminal_without_validation(session, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")` already called; `validate` → OK | call | returns T (`is T`); `validate` called once with `"VAL-1"`; re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`, `validated_at=NOW`, `outcome_verified is True`; events after setup = E(`ipn_received`, `"Callback received via ipn"`), E(`validated_success`, `"Validated successfully via ipn callback"`) | xfail BUG-026 — fails today on: status stays `CANCELLED` (`duplicate_ignored` written) |
| FIN-16 | R3a [BUG-026] | bug | T; `mark_terminal_without_validation(…, terminal_status="VALIDATED_FAILED", source="redirect_fail_no_val_id")` already called; `validate` → OK | call | returns T (`is T`); re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`; event types after setup = `ipn_received`, `validated_success` | xfail BUG-026 — fails today on: status stays `VALIDATED_FAILED` |
| FIN-17 | R3a [BUG-026], `_apply` R2a | bug | T; cancelled via `mark_terminal_without_validation(…, "CANCELLED", "redirect_cancel")`; `validate` → `ValidationResult(status="INVALID_TRANSACTION", tran_id="")` on the 1st call, then OK | call with `val_id="VAL-X"`, then with `val_id="VAL-1"` | each call returns T (`is T`); after the 1st call: re-read `status="CANCELLED"`, `val_id=None`, and the events it added = `ipn_received`, `validation_rejected`; after the 2nd call: `status="VALIDATED_SUCCESS"` (still replaceable) | xfail BUG-026 — fails today on: the 1st call writes `duplicate_ignored`, not `ipn_received` |
| FIN-18 | R3a [BUG-026], R3 | bug | T; cancelled via `mark_terminal_without_validation(…, "CANCELLED", "redirect_cancel")`; `validate` → OK with `status="FAILED"` on the 1st call, OK on the 2nd | call twice (`"VAL-1"`, `"VAL-2"`) | each call returns T (`is T`); after the 1st call: `status="VALIDATED_FAILED"` (the verified answer replaced the unverified one); after the 2nd call: still `VALIDATED_FAILED`, `val_id="VAL-1"`, and the last event is E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"`); `validate` called once | xfail BUG-026 — fails today on: status stays `CANCELLED` after the 1st call |
| FIN-19 | R3b [BUG-027] | bug | T with `status="EXPIRED"`, `validated_at=V0`; `validate` → OK | call | returns T (`is T`); `validate` called once; re-read `status="VALIDATED_SUCCESS"`, `validated_at=NOW`, `val_id="VAL-1"`; events = E(`ipn_received`, `"Callback received via ipn"`), E(`validated_success`, `"Validated successfully via ipn callback"`) | xfail BUG-027 — fails today on: status stays `EXPIRED` |
| FIN-20 | R6; Errors row 2 | error | T; `validate` raises `RuntimeError("gateway timeout")` | call | the same `RuntimeError` instance propagates; re-read in the same session: `status="INITIATED"`, `validated_at=None`, gateway fields `None`; events for T = E(`ipn_received`, `"Callback received via ipn"`) only | pass |
| FIN-21 | R3a [BUG-026] | bug | T inserted with `status="CANCELLED"`, `validated_at=V0` and **no** `outcome_verified` (default counts as unverified); `validate` → OK | call | returns T (`is T`); `validate` called once; re-read `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`, `validated_at=NOW`; event types = `ipn_received`, `validated_success` | xfail BUG-026 — fails today on: status stays `CANCELLED` |
| FIN-22 | R3 [BUG-026 setup] | bug | T inserted with `status="VALIDATED_FAILED"`, `outcome_verified=True`, `val_id="VAL-ORIG"`, `validated_at=V0` | call with `val_id="VAL-NEW"` | returns T (`is T`); `validate` not called; re-read `status="VALIDATED_FAILED"`, `val_id="VAL-ORIG"`, `validated_at=V0`; events = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"`) | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| FIN-23 | R3 [BUG-026 setup] | bug | T inserted with `status="RISK_HOLD"`, `outcome_verified=True`, `val_id="VAL-ORIG"` | call | returns T (`is T`); `validate` not called; re-read `status="RISK_HOLD"`, `val_id="VAL-ORIG"`, `outcome_verified is True`; events = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already RISK_HOLD"`) | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| FIN-24 | R4 | happy | T; `validate` → OK | call with `source="redirect_success"` | returns T (`is T`); `validate` called once with `"VAL-1"`; re-read `status="VALIDATED_SUCCESS"`; exactly 2 events: the 1st has description `"Callback received via redirect_success"` (type not asserted, see FIN-04); the 2nd = E(`validated_success`, `"Validated successfully via redirect_success callback"`) | pass |
| FIN-25 | R4 | happy | T; `validate` → OK with `status="FAILED"` | call with `source="redirect_fail"` | returns T (`is T`); re-read `status="VALIDATED_FAILED"`; exactly 2 events: the 1st has description `"Callback received via redirect_fail"` (type not asserted, see FIN-05); the 2nd = E(`validated_failed`, `"Gateway validation via redirect_fail callback returned status=FAILED"`) | pass |
| FIN-26 | R4, `_apply` R1 | happy | T; `validate` → OK with `tran_id=B26` | call | returns T (`is T`); `validate` called once with `"VAL-1"`; re-read gateway fields all `None`, `status` not in {`VALIDATED_SUCCESS`, `RISK_HOLD`}; exactly 2 events: E(`ipn_received`, `"Callback received via ipn"`), then one with description `f"val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id={B26}"` (type not asserted, see FIN-06) | pass |
| FIN-27 | R3, R5 | happy | T; first call made with `validate` → OK with `status="CANCELLED"`; record the re-read status S1; then `validate` → OK with `val_id="VAL-2"` | second call with `val_id="VAL-2"` | the second call returns T (`is T`); `validate` called once in total; re-read `status == S1`, `val_id="VAL-1"`; events after setup: exactly 1, type `duplicate_ignored`, description starts with `"Duplicate ipn callback ignored; transaction already "` (status word not asserted, see FIN-11) | pass |
| FIN-28 | Side effects (no commit) | side-effect | T in W2; `validate` → OK; savepoint and commit spy per **rolled back** | call | returns T (`is T`); re-read `status="VALIDATED_SUCCESS"`; count: exactly 2 events for T; re-read after rollback: `status="INITIATED"`, `validated_at=None`, `val_id=None`; count after rollback: 0 events for T; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager.mark_terminal_without_validation`

T is in **W2**. The call is `mark_terminal_without_validation(session, tran_id=A26, terminal_status=…, source=…)`. Every case asserts that no gateway client method was called.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MTW-01 | R3b [BUG-028] | bug | T in W2 | `terminal_status="CANCELLED"`, `source="redirect_cancel"` | returns T (`is T`); the one event has `event_type="redirect_cancel"` | xfail BUG-028 — fails today on: event type `cancelled` |
| MTW-02 | R3b [BUG-028] | bug | T | `terminal_status="VALIDATED_FAILED"`, `source="redirect_success_no_val_id"` | returns T (`is T`); the one event has `event_type="redirect_success"` | xfail BUG-028 — fails today on: event type `validated_failed` |
| MTW-03 | R3b [BUG-028] | bug | T | `terminal_status="VALIDATED_FAILED"`, `source="redirect_fail_no_val_id"` | returns T (`is T`); the one event has `event_type="redirect_fail"` | xfail BUG-028 — fails today on: event type `validated_failed` |
| MTW-04 | R1; Errors row 1 | error | T in W2 | `tran_id="z"*26`, `"CANCELLED"`, `"redirect_cancel"` | raises `HTTPException` 404, detail `f"Unknown tran_id: {'z'*26}"`; re-read: 0 events; T `INITIATED`, `validated_at=None` | pass |
| MTW-05 | R1 | side-effect | T; SQL capture on | `"CANCELLED"`, `"redirect_cancel"` | returns T (`is T`); captured SQL contains a SELECT … FOR UPDATE on payment_transactions | pass |
| MTW-06 | R2 | happy | T with `status="VALIDATED_SUCCESS"`, `validated_at=V0` | `"CANCELLED"`, `"redirect_cancel"` | returns T; re-read `status="VALIDATED_SUCCESS"`, `validated_at=V0`; events = E(`duplicate_ignored`, `"Duplicate redirect_cancel callback ignored; transaction already VALIDATED_SUCCESS"`) | pass |
| MTW-07 | R2 | happy | T; `mark_terminal_without_validation(…, "CANCELLED", "redirect_cancel")` already called | `"VALIDATED_FAILED"`, `"redirect_fail_no_val_id"` | returns T (`is T`); re-read `status="CANCELLED"`; events after setup = E(`duplicate_ignored`, `"Duplicate redirect_fail_no_val_id callback ignored; transaction already CANCELLED"`) | pass |
| MTW-08 | R2 | happy | T with `status="EXPIRED"`, `validated_at=V0` | `"CANCELLED"`, `"redirect_cancel"` | returns T (`is T`); re-read `status="EXPIRED"`, `validated_at=V0`; events = E(`duplicate_ignored`, `"Duplicate redirect_cancel callback ignored; transaction already EXPIRED"`) | pass |
| MTW-09 | R4 | boundary | T | `terminal_status="WHATEVER"`, `source="redirect_cancel"` | returns T (`is T`); re-read `status="WHATEVER"`, `validated_at=NOW`; exactly 1 event | pass |
| MTW-10 | R4 | boundary | T | `terminal_status="ABCDEFGHIJKLMNOPQRST"` (20 chars), `source="redirect_cancel"` | returns T (`is T`); re-read `status="ABCDEFGHIJKLMNOPQRST"` | pass |
| MTW-11 | R4; Errors row 2 | error | T | `terminal_status="ABCDEFGHIJKLMNOPQRSTU"` (21 chars), `source="redirect_cancel"`, inside savepoint | raises SQLAlchemy `DataError`; after savepoint rollback: T `status="INITIATED"`, `validated_at=None`; 0 events | pass |
| MTW-12 | R3 | happy | T in W2 | `terminal_status="CANCELLED"`, `source="redirect_cancel"` | returns T; re-read: `status="CANCELLED"`, `validated_at=NOW`, gateway fields all `None`; exactly 1 event, description `"Marked CANCELLED via redirect_cancel (no val_id to validate)"`, `workspace_id=W2`, `performed_by=None`, `metadata_json=None` (type not asserted, see MTW-01) | pass |
| MTW-13 | R3 | happy | T | `terminal_status="VALIDATED_FAILED"`, `source="redirect_success_no_val_id"` | returns T (`is T`); re-read `status="VALIDATED_FAILED"`, `validated_at=NOW`, `val_id=None`; exactly 1 event, description `"Marked VALIDATED_FAILED via redirect_success_no_val_id (no val_id to validate)"` (type not asserted, see MTW-02) | pass |
| MTW-14 | R3 | happy | T | `terminal_status="VALIDATED_FAILED"`, `source="redirect_fail_no_val_id"` | returns T (`is T`); re-read `status="VALIDATED_FAILED"`, `validated_at=NOW`; exactly 1 event, description `"Marked VALIDATED_FAILED via redirect_fail_no_val_id (no val_id to validate)"` (type not asserted, see MTW-03) | pass |
| MTW-15 | R3a [BUG-026] | bug | T (inserted without `outcome_verified`) | `terminal_status="CANCELLED"`, `source="redirect_cancel"` | returns T (`is T`); re-read `status="CANCELLED"`, `outcome_verified is False` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| MTW-16 | Side effects (no commit) | side-effect | T in W2; savepoint and commit spy per **rolled back** | `terminal_status="CANCELLED"`, `source="redirect_cancel"` | returns T (`is T`); re-read `status="CANCELLED"`; count: exactly 1 event for T (type not asserted, see MTW-01); re-read after rollback: `status="INITIATED"`, `validated_at=None`; count after rollback: 0 events for T; no gateway client method called; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager.resolve_risk`

**H** (used by untagged cases) = T in W1, brought to `RISK_HOLD` in setup by `_apply_validation_result(session, T, OK with risk_level=1, risk_title="Suspicious card", "ipn callback")`, with `utcnow` returning **V0** during that setup call. After setup, `utcnow` returns NOW. H is then `status="RISK_HOLD"`, `val_id="VAL-1"`, `risk_level=1`, `risk_title="Suspicious card"`, `bank_tran_id="BANK-1"`, `card_type="VISA-Brac bank"`, `verify_sign="SIG-1"`, `validated_at=V0`, with one setup `risk_hold` event. "H in W2" = the same, starting from T in W2.
**H\*** (used only by BUG-026 cases) = a row inserted directly with the same field values as H, plus `outcome_verified=True`, and no setup event. It fails at construction today.
The call is `resolve_risk(session, transaction_id=H.id, workspace_id=W1, user_id=U1.id, approve=…, note=…)`. "Events" below counts only events written after setup.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| RR-01 | R3, R4, R5 | happy | H | `approve=True`, `note="Customer verified by phone"` | returns H; re-read: `status="VALIDATED_SUCCESS"`, `risk_resolved_by=U1.id`, `risk_resolved_at=NOW`, `risk_resolution_note="Customer verified by phone"`, `validated_at=V0`, `val_id="VAL-1"`, `risk_level=1`, `risk_title="Suspicious card"`, `bank_tran_id="BANK-1"`, `card_type="VISA-Brac bank"`, `verify_sign="SIG-1"`; events after setup = E(`risk_resolved`, `"Risk hold approved: Customer verified by phone"`) with `performed_by=U1.id`, `metadata_json=None`, `workspace_id=W1` | pass |
| RR-02 | R3, R4, R5 | happy | H | `approve=False`, `note="Card reported stolen"` | returns H (`is H`); re-read: `status="VALIDATED_FAILED"`, `risk_resolved_by=U1.id`, `risk_resolved_at=NOW`, `risk_resolution_note="Card reported stolen"`, `validated_at=V0`, `val_id="VAL-1"`; events after setup = E(`risk_resolved`, `"Risk hold rejected: Card reported stolen"`) with `performed_by=U1.id` | pass |
| RR-03 | R4, R5 | boundary | H | `approve=True`, `note=""` | returns H (`is H`); re-read `status="VALIDATED_SUCCESS"`, `risk_resolution_note=""`; the one event after setup has description `"Risk hold approved: "` | pass |
| RR-04 | R1; Errors row 1 | error | H; no transaction with id 999999 | `transaction_id=999999`, `approve=True`, `note="x"` | raises `HTTPException` 404, detail `"Payment transaction 999999 not found"`; re-read: H still `RISK_HOLD`, resolution fields `None`; 0 events after setup | pass |
| RR-05 | R1; Errors row 1 | isolation | H in **W2** | `transaction_id=H.id`, `workspace_id=W1`, `approve=True`, `note="x"` | raises `HTTPException` 404, detail `f"Payment transaction {H.id} not found"`; re-read: `status="RISK_HOLD"`, `risk_resolved_by`, `risk_resolved_at`, `risk_resolution_note` all `None`; 0 events after setup | pass |
| RR-06 | R2; Errors row 2 | error | T in W1 (`INITIATED`) | `transaction_id=T.id`, `approve=True`, `note="x"` | raises `HTTPException` 400, detail `"Only transactions in RISK_HOLD can be resolved (current status: INITIATED)"`; re-read: `status="INITIATED"`, resolution fields `None`; 0 events | pass |
| RR-07 | R6, R2 | error | H; `resolve_risk(…, approve=True, note="First")` already called | `approve=False`, `note="Second"` | raises `HTTPException` 400, detail `"Only transactions in RISK_HOLD can be resolved (current status: VALIDATED_SUCCESS)"`; re-read `status="VALIDATED_SUCCESS"`, `risk_resolution_note="First"`; exactly 1 `risk_resolved` event for H | pass |
| RR-08 | R6a [BUG-029] | bug | H; SQL capture on for the action only (not the setup) | `approve=True`, `note="x"` | returns H (`is H`); no exception; captured SQL contains a SELECT … FOR UPDATE on payment_transactions; re-read `status="VALIDATED_SUCCESS"` | xfail BUG-029 — fails today on: no captured SELECT on payment_transactions contains `FOR UPDATE` |
| RR-09 | R3a [BUG-026]; `_apply` R12 | bug | H\* | `approve=False`, `note="Fraud"` | returns the H\* object (`is H*`); re-read `status="VALIDATED_FAILED"`, `outcome_verified is True` | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| RR-10 | R3a [BUG-026] | bug | H\* | `approve=True`, `note="Customer verified by phone"` | returns the H\* object (`is H*`); re-read `status="VALIDATED_SUCCESS"`, `outcome_verified is True` | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| RR-11 | R3a [BUG-026]; `finalize_from_gateway` R3, R3a | bug | H\* in W2; `resolve_risk(session, transaction_id=H.id, workspace_id=W2, user_id=U2.id, approve=False, note="Fraud")` already called; `validate` → OK with `val_id="VAL-NEW"` | `finalize_from_gateway(session, tran_id=A26, val_id="VAL-NEW", source="ipn")` | `finalize_from_gateway` returns the H\* object (`is H*`); `validate` not called; re-read `status="VALIDATED_FAILED"`, `outcome_verified is True`, `val_id="VAL-1"`, `risk_resolution_note="Fraud"`; events after the finalize call = E(`duplicate_ignored`, `"Duplicate ipn callback ignored; transaction already VALIDATED_FAILED"`) | xfail BUG-026 — fails today on: TypeError inserting `outcome_verified` |
| RR-12 | Side effects (no commit) | side-effect | H; savepoint and commit spy per **rolled back** | `approve=True`, `note="Customer verified by phone"` | returns H (`is H`); re-read `status="VALIDATED_SUCCESS"`; count: exactly 1 event after setup; re-read after rollback: `status="RISK_HOLD"`, `risk_resolved_by=None`, `risk_resolved_at=None`, `risk_resolution_note=None`; count after rollback: 0 events after setup; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `PaymentTransactionManager.reconcile_stuck_transactions`

Candidate rows are INITIATED transactions like T, with distinct tran_ids and the `initiated_at` values given. Unless stated, all rows are in W1 and the call uses the defaults (`older_than_minutes=30`, `limit=200`). "Returns [A, B]" means the returned list holds exactly these txns in this order.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| REC-01 | R1, R6 | boundary | A at NOW−30min−1s, B at exactly NOW−30min, C at NOW−29min | call | returns [A]; `query_by_tran_id` called once, for A; re-read A `status="EXPIRED"`; B and C `status="INITIATED"`, `validated_at=None`, 0 events each | pass |
| REC-02 | R1, R7 | boundary | rows 2h old, inserted with statuses `EXPIRED`, `VALIDATED_SUCCESS`, `CANCELLED`, `VALIDATED_FAILED`, `INIT_FAILED`; plus T (tran_id A26, 2h old) brought to `RISK_HOLD` in setup through `_apply_validation_result` (see Conventions); no INITIATED rows remain | call | returns `[]`; `query_by_tran_id` not called; every row's status unchanged; 0 events added by the call | pass |
| REC-03 | R1, R10 | isolation | A in W1 at NOW−2h, B in W2 at NOW−1h | call | returns [A, B]; both re-read `EXPIRED`; A's `expired` event has `workspace_id=W1`, B's has `workspace_id=W2` | pass |
| REC-04 | R2 | boundary | inserted in this order: X at NOW−1h, Y at NOW−3h, Z at NOW−2h | call with `limit=2` | returns [Y, Z]; `query_by_tran_id` called for Y, then Z (2 calls); X `status="INITIATED"`, 0 events | pass |
| REC-05 | R2 | boundary | same X, Y, Z as REC-04 | call with `limit=3` | returns [Y, Z, X]; all three `EXPIRED` | pass |
| REC-06 | R2 | boundary | 201 candidates, row i at NOW−2h−i seconds for i = 0…200 | call with defaults | returned list has 200 items and does not contain row 0 (the newest); row 0 `status="INITIATED"`, 0 events; `query_by_tran_id` called 200 times | pass |
| REC-07 | R3 | side-effect | A at NOW−3h, B at NOW−2h; race simulation: while handling A, the `query_by_tran_id` side effect sets B to `VALIDATED_SUCCESS` (see Conventions) and returns UNATTEMPTED for A | call | returns [A]; `query_by_tran_id` called once (for A); re-read B `status="VALIDATED_SUCCESS"`, 0 events for B | pass |
| REC-08 | R3 | side-effect | A at NOW−2h; SQL capture on | call | returns [A]; captured SQL contains a SELECT … FOR UPDATE on payment_transactions | pass |
| REC-09 | R4a [BUG-031] | bug | A at NOW−2h; `query_by_tran_id` → `ValidationResult(status="VALID", tran_id=<A's>, val_id="VAL-9", amount=Decimal("500.00"), currency="BDT", risk_level=0)` | call | returns [A]; `query_by_tran_id` called exactly once, with `call_args == call(<A's tran_id>)`: one positional argument, no keyword arguments (no `val_id_hint`) | xfail BUG-031 — fails today on: the call passes `val_id_hint=None` |
| REC-10 | R5 | happy | A at NOW−2h; query → as REC-09 but `status="VALIDATED"` | call | returns [A]; A `status="VALIDATED_SUCCESS"`; 1 event `validated_success` | pass |
| REC-11 | R5 | happy | A at NOW−2h; query → VALID, A's tran_id, `amount=Decimal("499.99")`, `currency="BDT"` | call | returns [A]; A `status="VALIDATED_FAILED"`, `validated_at=NOW`; events = E(`validated_failed`, `"Amount mismatch: expected 500.00 BDT, gateway reported 499.99 BDT"`) | pass |
| REC-12 | R5 | happy | A at NOW−2h; query → VALID, A's tran_id, `amount=Decimal("500.00")`, `currency="BDT"`, `risk_level=1`, `risk_title="Suspicious card"` | call | returns [A]; A `status="RISK_HOLD"`; events = E(`risk_hold`, `"Validated via reconciliation but flagged high-risk (Suspicious card) — held for review"`) | pass |
| REC-13 | R5a [BUG-030] | bug | A at NOW−2h; query → `status="FAILED"`, A's tran_id, `val_id="VAL-9"`, `amount=Decimal("500.00")`, `currency="BDT"` | call | returns [A]; A `status="VALIDATED_FAILED"`, `validated_at=NOW`, `val_id="VAL-9"`; events = E(`validated_failed`, `"Gateway validation via reconciliation returned status=FAILED"`) | xfail BUG-030 — fails today on: status `EXPIRED` |
| REC-14 | R5a [BUG-030] (needs BUG-025 too) | bug | A at NOW−2h; query → `status="CANCELLED"`, A's tran_id | call | returns [A]; A `status="CANCELLED"`; events = E(`validated_cancelled`, `"Gateway validation via reconciliation returned status=CANCELLED"`) | xfail BUG-030 — fails today on: status `EXPIRED` |
| REC-15 | R5b [BUG-023] | bug | A at NOW−2h; query → `status="VALID"`, `tran_id="f"*26`, amount 500.00, BDT | call | returns [A]; A `status="INITIATED"`, `validated_at=None`; the one event's type is `validation_rejected` | xfail BUG-023 — fails today on: status `VALIDATED_FAILED` |
| REC-16 | R6 | happy | A at NOW−2h; query → `status="UNATTEMPTED"`, A's tran_id, `val_id="VAL-X"`, `bank_tran_id="BANK-X"` | call | returns [A]; A `status="EXPIRED"`, `validated_at=NOW`, `val_id=None`, `bank_tran_id=None`, `risk_level=None`; events = E(`expired`, `"No resolution found after 30 minutes (gateway status: UNATTEMPTED)"`) | pass |
| REC-17 | R6 | happy | A at NOW−46min; query → `status="INVALID_TRANSACTION"`, A's tran_id | call with `older_than_minutes=45` | returns [A]; A `status="EXPIRED"`; event description `"No resolution found after 45 minutes (gateway status: INVALID_TRANSACTION)"` | pass |
| REC-18 | R6 | boundary | A at NOW−2h; query → `status=""`, A's tran_id | call | returns [A]; A `status="EXPIRED"`; event description `"No resolution found after 30 minutes (gateway status: )"` | pass |
| REC-19 | R6, `finalize_from_gateway` R3b [BUG-027] | bug | A at NOW−2h (tran_id A26); query → default UNATTEMPTED; `validate` → OK | call the sweep, then `finalize_from_gateway(session, tran_id=A26, val_id="VAL-1", source="ipn")` | the sweep returns [A]; `finalize_from_gateway` returns A (`is A`); after the sweep A is `EXPIRED`; after finalize: A `status="VALIDATED_SUCCESS"`, `val_id="VAL-1"`; last two events `ipn_received`, `validated_success` | xfail BUG-027 — fails today on: A stays `EXPIRED` |
| REC-20 | R7 | happy | A at NOW−3h, B at NOW−2h, C at NOW−1h; query → A: VALID with A's tran_id (500.00 BDT, risk 0); B: UNATTEMPTED; C: VALID with C's tran_id, `amount=Decimal("1")`, BDT | call | returns [A, B, C], each once; statuses `VALIDATED_SUCCESS`, `EXPIRED`, `VALIDATED_FAILED`; exactly 1 event each | pass |
| REC-21 | R8 [BUG-032] | bug | A at NOW−3h, B at NOW−2h, C at NOW−1h; query → A: UNATTEMPTED; B: raises `RuntimeError("gateway timeout")`; C: UNATTEMPTED | call | **no exception**; returns [A, C]; A and C `EXPIRED`; B `status="INITIATED"`, `validated_at=None`, gateway fields `None`; B's events = E(`reconciliation_error`, `"Gateway query failed during reconciliation: gateway timeout"`); `query_by_tran_id` called 3 times | xfail BUG-032 — fails today on: `RuntimeError` propagates |
| REC-22 | R8 [BUG-032] | bug | A at NOW−3h, B at NOW−2h, C at NOW−1h; query → A raises `RuntimeError("bad response")`; B and C UNATTEMPTED | call | no exception; returns [B, C], both `EXPIRED`; A `status="INITIATED"`, events = E(`reconciliation_error`, `"Gateway query failed during reconciliation: bad response"`) | xfail BUG-032 — fails today on: `RuntimeError` propagates |
| REC-23 | R9 | boundary | A at NOW−1s, B at exactly NOW | call with `older_than_minutes=0` | returns [A]; B `status="INITIATED"`, 0 events | pass |
| REC-24 | R9 | boundary | A at exactly NOW | call with `older_than_minutes=-10` | returns [A]; A `status="EXPIRED"`; event description `"No resolution found after -10 minutes (gateway status: UNATTEMPTED)"` | pass |
| REC-25 | R4, R5 | happy | A at NOW−2h, `val_id=None`; query → as REC-09 | call | returns [A]; re-read A `status="VALIDATED_SUCCESS"`, `val_id="VAL-9"`, `validated_at=NOW`; events = E(`validated_success`, `"Validated successfully via reconciliation"`); `query_by_tran_id` called exactly once, first positional argument = A's tran_id (other arguments not asserted, see REC-09) | pass |
| REC-26 | R5 | side-effect | A at NOW−2h; query → `status="VALID"`, `tran_id="f"*26`, `val_id="VAL-F"`, amount 500.00, BDT | call | returns [A]; A `val_id=None`, `bank_tran_id=None`, `status` not in {`VALIDATED_SUCCESS`, `RISK_HOLD`}; exactly 1 event, description `f"val_id/tran_id mismatch via reconciliation: gateway resolved it to tran_id={'f'*26}"` (type not asserted, see REC-15) | pass |
| REC-27 | R6, `_apply` R12 [BUG-026] | bug | A at NOW−2h (inserted without `outcome_verified`); query → default UNATTEMPTED | call | returns [A]; A `status="EXPIRED"`, `outcome_verified is False` | xfail BUG-026 — fails today on: no `outcome_verified` attribute |
| REC-28 | R8 [BUG-032] | bug | A at NOW−3h, B at NOW−2h; query → A raises `TimeoutError()` (empty message); B UNATTEMPTED | call | no exception; returns [B]; B `EXPIRED`; A `status="INITIATED"`; A's events = E(`reconciliation_error`, `"Gateway query failed during reconciliation: TimeoutError"`) | xfail BUG-032 — fails today on: `TimeoutError` propagates |
| REC-29 | R8 [BUG-032] | bug | A at NOW−3h, B at NOW−2h, C at NOW−1h; query → A: UNATTEMPTED; B: `ValidationResult(status="VALID", tran_id=<B's>, val_id="VAL-B", amount=Decimal("500.00"), currency="BDT", risk_level=0, risk_title="R"*51, bank_tran_id="BANK-B")` (update fails at flush with `DataError`); C: UNATTEMPTED | call | no exception; returns [A, C], both `EXPIRED`; B re-read: `status="INITIATED"`, `validated_at=None`, `val_id=None`, `risk_title=None`, `bank_tran_id=None`, `risk_level=None`; B's events: exactly 1, type `reconciliation_error`, description starts with `"Gateway query failed during reconciliation: "` and is longer than that prefix | xfail BUG-032 — fails today on: `DataError` propagates |
| REC-30 | Side effects (no commit) | side-effect | A at NOW−2h; query → default UNATTEMPTED; savepoint and commit spy per **rolled back** | call | returns [A]; re-read A `status="EXPIRED"`; count: exactly 1 event for A; re-read after rollback: A `status="INITIATED"`, `validated_at=None`; count after rollback: 0 events for A; mock called: the `session.commit` spy was never called | pass. Author: claude |

## Deferred to other specs

| Rule | Owner | What must be tested there |
|---|---|---|
| `initiate_payment` R3 (response part) | `PaymentTransactionService.initiate_payment` | A refused start returns `InitiatePaymentResponse` with `status="INIT_FAILED"` and `failed_reason` filled, not 502 (BUG-019). |
| `initiate_payment` R9, R9a, R10a (API part) | `POST` initiate-payment endpoint | Bad amount / unsupported currency gives 422 and the gateway is never called (BUG-021, BUG-022). |
| `finalize_from_gateway` R7 | `PaymentTransactionService.handle_gateway_callback` | Only `"redirect_success"`, `"redirect_fail"` and `"ipn"` are ever passed as `source`. |
| `finalize_from_gateway` R6 (rollback part) | `PaymentTransactionService.handle_gateway_callback` | When `validate` raises, the service rolls back, so the `ipn_received` event is not persisted. |
| `finalize_from_gateway` R1, `mark_terminal_without_validation` R1 (concurrency) | integration tests (two sessions) | Two simultaneous callbacks for one tran_id: only one finalizes, the other gets the duplicate path. |
| `resolve_risk` R6a [BUG-029] (concurrency) | integration tests (two sessions) | Two simultaneous resolves: one succeeds, the other gets 400, and only one `risk_resolved` event exists. (The lock clause itself is unit-tested by RR-08.) |
| `reconcile_stuck_transactions` R3 (concurrency) | integration tests (two sessions) | A live callback committed during a sweep is not overwritten, and that row is skipped. |
| `reconcile_stuck_transactions` R4a [BUG-031] (mock part) | `app/integrations/sslcommerz/mock_client.py` spec | `query_by_tran_id(tran_id)` without a val_id answers from the mock's record of completed payments. |
| `reconcile_stuck_transactions` R8 (commit part) | `scripts/reconcile_payments.py` | With one failing candidate, the script still commits the other candidates' results. |
| `_apply_validation_result` R12 (migration backfill) | `outcome_verified` migration | Existing gateway-validated `VALIDATED_FAILED` rows are backfilled `true` (spec: not unit-tested). |

## Retired IDs

None.

**Restored:** RR-08 (revision 3). It was retired in revision 2 when the spec made `resolve_risk` R6a integration-only. Spec gap G8 was closed, so it again checks `FOR UPDATE` on the `resolve_risk` lookup, now as xfail BUG-029.

## Spec gaps

None. (G7 and G8 from revision 2 were closed by the spec. See the Revision line.)

## Coverage matrix

| Callable | Rule / Error row | Cases |
|---|---|---|
| `_log_event` | R1 | LOG-01, LOG-02 |
| `_log_event` | R2 | LOG-03, LOG-04 |
| `_log_event` | Err: event_type > 50 | LOG-04 |
| `_log_event` | Side effects: no commit | LOG-05 |
| `_generate_tran_id` | R1 | GEN-01, GEN-02 |
| `_generate_tran_id` | R2 | GEN-03, GEN-04 |
| `_generate_tran_id` | R3 | GEN-05 |
| `_generate_tran_id` | R4 | GEN-01, GEN-05 |
| `_generate_tran_id` | Err: 5 ids used → 500 | GEN-05 |
| `initiate_payment` | R1 | INIT-25 (tran_id also INIT-01, INIT-17) |
| `initiate_payment` | R1a [BUG-020] | INIT-07, INIT-08 |
| `initiate_payment` | R2 | INIT-01, INIT-05, INIT-06 |
| `initiate_payment` | R3 [BUG-019] | INIT-09, INIT-10, INIT-11, INIT-12; response part Deferred |
| `initiate_payment` | R4 | INIT-13 |
| `initiate_payment` | R5 | INIT-01, INIT-04, INIT-25 |
| `initiate_payment` | R5a [BUG-019] | INIT-30 |
| `initiate_payment` | R6 | INIT-02, INIT-03, INIT-04, INIT-27, INIT-29 |
| `initiate_payment` | R7 | INIT-14 |
| `initiate_payment` | R7a [BUG-019] | INIT-15 |
| `initiate_payment` | R8 | INIT-16 |
| `initiate_payment` | R9 | INIT-20, INIT-26, INIT-27, INIT-28 |
| `initiate_payment` | R9a [BUG-021] | INIT-18, INIT-19 (accept side INIT-20); API part Deferred |
| `initiate_payment` | R10 | INIT-22, INIT-29 |
| `initiate_payment` | R10a [BUG-022] | INIT-21, INIT-23, INIT-24; API part Deferred |
| `initiate_payment` | Err: all 5 ids used → 500 | INIT-17 |
| `initiate_payment` | Err: gateway raises | INIT-13 |
| `initiate_payment` | Err: nonexistent workspace → IntegrityError | INIT-16 |
| `initiate_payment` | Err: bad amount / currency → ValidationError | INIT-18, INIT-19, INIT-23 |
| `initiate_payment` | Side effects: no commit | INIT-32 |
| `_apply_validation_result` | R1 | AVR-32, AVR-33, AVR-34, AVR-35, FIN-26, REC-26 |
| `_apply_validation_result` | R1a [BUG-023] | AVR-07, AVR-08, AVR-09, AVR-10, FIN-06 |
| `_apply_validation_result` | R2 | AVR-06 |
| `_apply_validation_result` | R2a [BUG-023] | AVR-11, AVR-09; order AVR-35 |
| `_apply_validation_result` | R3 | AVR-01, AVR-12, AVR-16, AVR-36 |
| `_apply_validation_result` | R4 | AVR-12, AVR-13, AVR-14 |
| `_apply_validation_result` | R4a | AVR-36 |
| `_apply_validation_result` | R4b [BUG-025] | AVR-15 |
| `_apply_validation_result` | R5 | AVR-17, AVR-18, AVR-19, AVR-20 |
| `_apply_validation_result` | R6 [BUG-024] | AVR-23, AVR-24, AVR-29 |
| `_apply_validation_result` | R7 | AVR-21, AVR-22, AVR-25 |
| `_apply_validation_result` | R8 [BUG-024] | AVR-26, AVR-27, AVR-28, AVR-29 |
| `_apply_validation_result` | R9 | AVR-04, AVR-05 |
| `_apply_validation_result` | R10 | AVR-01, AVR-02, AVR-03, AVR-14, AVR-18 |
| `_apply_validation_result` | R11 | AVR-16, AVR-30, AVR-31, AVR-34 |
| `_apply_validation_result` | R12 [BUG-026] | AVR-37, AVR-38, AVR-39, AVR-40, AVR-41, AVR-42, AVR-43, INIT-31, MTW-15, RR-09, RR-10, REC-27, FIN-15; backfill Deferred |
| `_apply_validation_result` | Side effects: no commit | AVR-44 |
| `finalize_from_gateway` | R1 | FIN-01, FIN-02; concurrency Deferred |
| `finalize_from_gateway` | R2 | FIN-03 |
| `finalize_from_gateway` | R3 | FIN-07, FIN-08, FIN-09, FIN-10, FIN-12, FIN-27; with marker FIN-22, FIN-23, RR-11 |
| `finalize_from_gateway` | R3a [BUG-026] | FIN-15, FIN-16, FIN-17, FIN-18, FIN-21; `resolve_risk` rejection excluded: RR-11 |
| `finalize_from_gateway` | R3b [BUG-027] | FIN-19, REC-19 |
| `finalize_from_gateway` | R3c [BUG-025] | FIN-11 |
| `finalize_from_gateway` | R4 | FIN-01, FIN-24, FIN-25, FIN-26 |
| `finalize_from_gateway` | R4a [BUG-028] | FIN-04, FIN-05 |
| `finalize_from_gateway` | R5 | FIN-10, FIN-13, FIN-27 |
| `finalize_from_gateway` | R5a [BUG-023] | FIN-14 |
| `finalize_from_gateway` | R6 | FIN-20; rollback part Deferred |
| `finalize_from_gateway` | R7 | Deferred (`PaymentTransactionService.handle_gateway_callback`) |
| `finalize_from_gateway` | Err: unknown tran_id → 404 | FIN-03 |
| `finalize_from_gateway` | Err: gateway validation raises | FIN-20 |
| `finalize_from_gateway` | Side effects: no commit | FIN-28 |
| `mark_terminal_without_validation` | R1 | MTW-04, MTW-05; concurrency Deferred |
| `mark_terminal_without_validation` | R2 | MTW-06, MTW-07, MTW-08 |
| `mark_terminal_without_validation` | R3 | MTW-12, MTW-13, MTW-14 |
| `mark_terminal_without_validation` | R3a [BUG-026] | MTW-15; replaceability via FIN-15, FIN-16 |
| `mark_terminal_without_validation` | R3b [BUG-028] | MTW-01, MTW-02, MTW-03 |
| `mark_terminal_without_validation` | R4 | MTW-09, MTW-10, MTW-11 |
| `mark_terminal_without_validation` | Err: unknown tran_id → 404 | MTW-04 |
| `mark_terminal_without_validation` | Err: terminal_status > 20 → DataError | MTW-11 |
| `mark_terminal_without_validation` | Side effects: no commit | MTW-16 |
| `resolve_risk` | R1 | RR-04, RR-05 |
| `resolve_risk` | R2 | RR-06, RR-07 |
| `resolve_risk` | R3 | RR-01, RR-02, FIN-12 |
| `resolve_risk` | R3a [BUG-026] | RR-09, RR-10, RR-11 |
| `resolve_risk` | R4 | RR-01, RR-02, RR-03 |
| `resolve_risk` | R5 | RR-01, RR-02, RR-03 |
| `resolve_risk` | R6 | RR-07 |
| `resolve_risk` | R6a [BUG-029] | RR-08; two-session race Deferred |
| `resolve_risk` | Err: not found / other workspace → 404 | RR-04, RR-05 |
| `resolve_risk` | Err: status ≠ RISK_HOLD → 400 | RR-06, RR-07 |
| `resolve_risk` | Side effects: no commit | RR-12 |
| `reconcile_stuck_transactions` | R1 | REC-01, REC-02, REC-03 |
| `reconcile_stuck_transactions` | R2 | REC-04, REC-05, REC-06 |
| `reconcile_stuck_transactions` | R3 | REC-07, REC-08; concurrency Deferred |
| `reconcile_stuck_transactions` | R4 | REC-25 |
| `reconcile_stuck_transactions` | R4a [BUG-031] | REC-09; mock-client part Deferred |
| `reconcile_stuck_transactions` | R5 | REC-10, REC-11, REC-12, REC-25, REC-26 |
| `reconcile_stuck_transactions` | R5a [BUG-030] | REC-13, REC-14 |
| `reconcile_stuck_transactions` | R5b [BUG-023] | REC-15 |
| `reconcile_stuck_transactions` | R6 | REC-01, REC-16, REC-17, REC-18, REC-19, REC-27 |
| `reconcile_stuck_transactions` | R7 | REC-02, REC-20 |
| `reconcile_stuck_transactions` | R8 [BUG-032] | REC-21, REC-22, REC-28, REC-29; commit part Deferred |
| `reconcile_stuck_transactions` | R9 | REC-23, REC-24 |
| `reconcile_stuck_transactions` | R10 | REC-03 |
| `reconcile_stuck_transactions` | Side effects: no commit | REC-30 |
| BUG tags | BUG-019 | INIT-09, INIT-10, INIT-11, INIT-12, INIT-15, INIT-30 |
| BUG tags | BUG-020 | INIT-07, INIT-08 |
| BUG tags | BUG-021 | INIT-18, INIT-19 |
| BUG tags | BUG-022 | INIT-21, INIT-23, INIT-24 |
| BUG tags | BUG-023 | AVR-07, AVR-08, AVR-09, AVR-10, AVR-11, FIN-06, FIN-14, REC-15 |
| BUG tags | BUG-024 | AVR-23, AVR-24, AVR-26, AVR-27, AVR-28, AVR-29 |
| BUG tags | BUG-025 | AVR-15, FIN-11 |
| BUG tags | BUG-026 | AVR-37…AVR-43, FIN-15, FIN-16, FIN-17, FIN-18, FIN-21, FIN-22, FIN-23, INIT-31, MTW-15, RR-09, RR-10, RR-11, REC-27 |
| BUG tags | BUG-027 | FIN-19, REC-19 |
| BUG tags | BUG-028 | FIN-04, FIN-05, MTW-01, MTW-02, MTW-03 |
| BUG tags | BUG-029 | RR-08; two-session race Deferred |
| BUG tags | BUG-030 | REC-13, REC-14 |
| BUG tags | BUG-031 | REC-09 |
| BUG tags | BUG-032 | REC-21, REC-22, REC-28, REC-29 |
