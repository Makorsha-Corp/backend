# Test cases — `app/services/payment_transaction_service.py`

> **Spec:** `tests/unit/services/payment_transaction_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps G1–G7 applied. Fingerprint (`idempotency_fingerprint`, SHA-256 of canonical JSON over the normalised body plus `profile_id`) checked on IK-01, IK-02, IK-36, IK-44 with literal JSON; another member gets the exact 409 text (IK-15); replay = 0 commits, 1 rollback, pending change discarded (IK-03); 409 rolls back once (IK-06); index found by name with its exact `indexdef` (IK-25); keyed rows by hand carry both columns (IK-26, IK-27); race loser driven by the patched lookup `get_by_workspace_and_idempotency_key` (IK-28, IK-29, simulation changed); IK-30 adds "no tran_id generated". New: IK-31 (lookup unlocked, single table, first), IK-32 … IK-39 (normalisation: 500 vs 500.00, "" vs omitted name, omitted vs "BDT", trimmed text, "500.5" in the fingerprint, case kept → 409, "bdt" after BUG-022, whitespace-only → null), IK-40/IK-41 (key length 100 / 101 → DataError), IK-42/IK-43 (other IntegrityError, re-read miss → re-raised), IK-44 (key and fingerprint never change). I-07 now uses the listed `token_hex` target. All six gaps closed; no ID retired.
> **Revision:** 2a (2026-11-22) — wording only, from the executor: TR-01 … TR-04 call the module-level function `_to_response` (not `svc._to_response`); IK-30 and IK-31 match `idempotency_key` in the WHERE clause, not anywhere in the select. Counts unchanged; the IK-01/02/36/44 hash update is pending.
> **Revision:** 2b (2026-11-22) — spec G8 (worked example in sorted key order): Conventions FPX is now `fp(FPO)` built with `json.dumps(..., sort_keys=True, separators=(",", ":"))`, so IK-01, IK-02 and IK-44 compute their hash from sorted JSON; IK-36 now reproduces the spec example (profile 7, phone `01700000000`) and asserts the literal `0bbacdbcb2eb158eba9bfab58060dd04bea674cddc22a51a78dd49db87a949bd`; its former 500.5 / trimmed-name check moved to new IK-45. No card carried a DISCREPANCY-3 reason (that reason sits in the test file). 131 cases.
> **Revision:** 3 (2026-11-22) — from `payment_transaction_service.verify.md` (case designer items). Finding 1 / H3: GC-03, GC-04, TW-05, TW-06 now build the earlier outcome at V0 (a second `utcnow` value) and assert `validated_at == V0` after the duplicate, so a re-stamp at NOW fails. Finding 2 / R1: new IK-46: a non-key `IntegrityError` (initiated_by FK) while a matching keyed winner exists is re-raised, and the re-read lookup is never called (single-session setup, race simulation extended). Expect lines now name every bug a card depends on: IK-02, IK-04 (BUG-019), IK-38 (BUG-022), RR-11, L-13, D-17 (BUG-019 for `failed_reason`, BUG-026 for `outcome_verified`). Finding 3 is routed to the describer (R7c1 500.001 example unreachable after BUG-021); no card change. 132 cases.
> **Counts:** 132 cases · 68 expected-to-pass · 64 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `_to_response` 4 (1 bug) · `initiate_payment` 13 (3 bug) · `initiate_payment` idempotency (BUG-3023) 46 (46 bug) · `handle_gateway_callback` 16 (2 bug) · `handle_terminal_without_validation` 12 (2 bug) · `resolve_risk` 11 (2 bug) · `get_transaction_by_tran_id` 17 (5 bug, one non-strict) · `list_transactions` 13 (3 bug, one non-strict). TC1–TC6 live on each callable.
- **Depth:** full (money). Every write gets TC1 (committed: survives a test rollback), TC3 (the manager's error passes as the same object, plus an *uncommitted* extra row X that must be gone), TC4 (failing commit, gateway call count checked) and TC5 (failing refresh, change stays). Each read gets TC6 (pending edit stays pending, no commit, no rollback) on success and on 404.
- **Idempotency (BUG-3023, reference for the subscription portal):** new key and its fingerprint stored (accepted and refused start; fingerprint checked against literal canonical JSON); normalisation (amount by value, omitted = default, trimmed text, blank → null, case kept); the lookup is unlocked, single-table and runs first; a replay commits nothing and rolls back once; same key + same body replays the stored attempt with no gateway call and no write, for `INITIATED`, `INIT_FAILED` and a status changed since; same key + different body → 409 for **each** of the 9 request fields, and for another member of the same workspace; no key → always a new attempt, also next to a stored key; exact key compare (capitals, leading space, a part, `_` for `-`); per-workspace scope with the key used in W0 and in W2 (both sides of W1) and the reverse; the unique index itself (definition, a duplicate raises 23505, the same key in W0/W1/W2 and NULL keys are allowed); the lost race answers as replay or 409, never 500.
- **Notable design choices:**
  - **Race simulation** (IK-28, IK-29, IK-43, `Author: claude`): the spec's recipe — the committed winner exists, and `PaymentTransactionDAO.get_by_workspace_and_idempotency_key` is patched so the first lookup misses; the insert then hits the unique index. Real two-session races are deferred to integration.
  - **Idempotency Givens call `svc.initiate_payment(..., idempotency_key=…)`**, so today those cards fail in the Given with `TypeError`. They are all `Author: claude` and strict xfail. Rows keyed by hand (IK-26, IK-27) set both columns, with any 64-hex fingerprint.
  - `RISK_HOLD` and `VALIDATED_SUCCESS` are reached through `svc.handle_gateway_callback` in the Given (spec Facts), never by direct insert.
  - **Cards that need more than one fix** name every bug on their Expect line, main bug first: IK-02, IK-04 (BUG-3023, BUG-019), IK-38 (BUG-3023, BUG-022), RR-11, L-13, D-17 (BUG-3022, BUG-019, BUG-026). They stay strict xfail until all named bugs are fixed.
  - **Duplicate callbacks** (GC-03, GC-04, TW-05, TW-06) build the first outcome at V0 and run the duplicate at NOW, so a re-stamp of `validated_at` is visible.
  - **IK-46** extends the race simulation: the winner's key is cleared before the When and put back only by the second lookup call, so the insert fails on the initiator FK (not the key index) while a matching winner exists for any handler that re-reads.
  - `secrets.token_hex` is patched for the 500 card (I-07) at the target the spec's Externals now name.
- **Needs a decision:** None. Gaps 1–6 are closed by the spec's Gap log (G1–G7).

## Conventions for this module

**IDs.** `PTS` = `app/services/payment_transaction_service.py`. `TR` `_to_response` · `I` `initiate_payment` · `IK` `initiate_payment` idempotency (BUG-3023) · `GC` `handle_gateway_callback` · `TW` `handle_terminal_without_validation` · `RR` `resolve_risk` · `D` `get_transaction_by_tran_id` · `L` `list_transactions`. Full ID `PTS-<id>`.

**Imports.** `svc` = `payment_transaction_service` (`from app.services.payment_transaction_service import payment_transaction_service`). `PaymentTransaction` (`app.models.payment_transaction`); the event model of `app.models.payment_transaction_event` (`PaymentTransactionEvent`). `InitiatePaymentRequest`, `InitiatePaymentResponse`, `PaymentTransactionResponse`, `PaymentTransactionDetailResponse`, `PaymentTransactionEventResponse` (`app.schemas.payment_transaction`). `InitSessionResult`, `ValidationResult` (`app.integrations.sslcommerz.client`). `HTTPException` (`fastapi`), `IntegrityError`, `DataError` (`sqlalchemy.exc`), `pydantic.ValidationError`, `inspect`, `text`, `select` (`sqlalchemy`), `patch` (`unittest.mock`). `db` first, every other argument by keyword. `result` = what the When returns.

**Standing rows** (every test, this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`); U1 = `make_profile(db, name="Karim")` with email `"karim@example.com"` (W1's owner and acting member); U2 = `make_profile(db, name="Rahim")` (another member of W1); U3 = `make_profile(db, name="Selina")` (acts in W0 and W2). The service checks no membership.

**Fixed values.** MISSING = `999999999`. NOW = `datetime(2026, 9, 27, 12, 0, 0)` (naive); `app.managers.payment_transaction_manager.utcnow` is patched to return NOW in every test. `A26 = "a"*26`, `B26 = "b"*26`, `C26 = "c"*26`, `Z26 = "f"*26` (never stored). HEX26 = regex `^[0-9a-f]{26}$`. V0 = `datetime(2026, 9, 27, 11, 0, 0)`; a Given step written "**at V0**" runs with the `utcnow` patch returning V0, and the patch returns NOW again before the commit point. GHOST = `Profile(id=MISSING, name="Ghost", email="ghost@example.com")` (`app.models.profile`), built in memory, never added to the session. URL1 = `"https://sandbox.example/pay/SESS-1"`, URL2 = `"https://sandbox.example/pay/SESS-2"`. NOTE = `"Card holder confirmed by phone"`. K = `"K-1"` (an idempotency key). IDEM409 = `"This idempotency key was already used for a different payment"`.

**Requests.** REQ = `InitiatePaymentRequest(amount=Decimal("500"), currency="BDT", cus_phone="01711000000")` (no name, email, value_a..d). REQ0 = REQ without `currency` (omitted). "REQ but X" = REQ with field X added or changed, every other field as REQ.

**Fingerprint.** fp(obj) = `hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()` (imports `json`, `hashlib`; always `sort_keys=True`, never a hand-ordered JSON string). FPO = `{"amount": "500", "currency": "BDT", "cus_email": None, "cus_name": None, "cus_phone": "01711000000", "profile_id": U1.id, "value_a": None, "value_b": None, "value_c": None, "value_d": None}` (REQ sent by U1). FPX = fp(FPO). **keyed(R, k, f)** = row R with `idempotency_key=k`, `idempotency_fingerprint=f` (both set together).

**Gateway** (`app.managers.payment_transaction_manager.get_sslcommerz_client` patched in every test to return mock `gw`):
- `gw.init_session` → OKS = `InitSessionResult(status="SUCCESS", session_key="SESS-1", gateway_page_url=URL1)`. REFUSED = `InitSessionResult(status="FAILED", failed_reason="Store is de-active")`.
- `gw.validate` → OKV(t) = `ValidationResult(status="VALID", tran_id=t, val_id="VAL-1", amount=Decimal("500.00"), currency="BDT", risk_level=0, risk_title="Safe", bank_tran_id="BANK-1", card_type="VISA-Brac bank", verify_sign="SIG-1")`. RISKY(t) = OKV(t) but `risk_level=1`, `risk_title="Suspicious card"`. Default `gw.validate.return_value = OKV(A26)`.
- `gw.query_by_tran_id` is never expected to be called.

**Given rows.** Inserted directly, flushed one at a time in the order written. After "but" a line lists every column that differs.
- **T** = `PaymentTransaction(workspace_id=W1.id, tran_id=A26, status="INITIATED", amount=Decimal("500.00"), currency="BDT", cus_name="Karim", cus_email="karim@example.com", cus_phone="01711000000", initiated_by=U1.id, session_key="SESS-0", gateway_page_url="https://sandbox.example/pay/SESS-0")`; every gateway, risk and `validated_at` field `None`. `failed_reason`, `outcome_verified`, `idempotency_key` are never passed unless the card says so.
- **ev(T, type, at)** = an event row `workspace_id=T.workspace_id, payment_transaction_id=T.id, event_type=type, description=f"{type} note", created_at=at`.
- **held(T)** = Given step: `gw.validate.return_value = RISKY(T.tran_id)`; `svc.handle_gateway_callback(db, tran_id=T.tran_id, val_id="VAL-1", source="ipn")`. T is then `RISK_HOLD` with events `ipn_received`, `risk_hold`.
- **paid(T)** = the same step with `OKV(T.tran_id)`: T becomes `VALIDATED_SUCCESS`.
- **first(ws, user, req, key)** = Given step `A = svc.initiate_payment(db, workspace_id=ws, user=user, request=req, idempotency_key=key)`; `A_ROW` = the `payment_transactions` row with `tran_id == A.tran_id`.
- **commit point** = after the last Given line: `db.commit()`, then `gw.reset_mock()` (keeps return values and side effects), then snapshots for `unchanged` / `nothing written` are taken. Call counts in Then lines therefore count the When only.
- **X** (only where listed, after the commit point) = T but `tran_id "e"*26`, flushed, not committed. **x_gone** = 0 `payment_transactions` rows with `tran_id == "e"*26` (checked after the `committed:` rollback, or with a fresh query).

**Named checks.**
- **re-read R** = `db.expire_all()`, then select R again by id; database values.
- **unchanged(R)** = after re-read, every column of R equals its value at the commit point.
- **nothing written** = the numbers of `payment_transactions` rows and of `payment_transaction_events` rows (all workspaces) equal their values at the commit point.
- **events(R)** = the `event_type` values of R's events, fresh query, ordered by `id`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `loaded:` lines run first on the returned ORM object: each column named is not in `inspect(result).unloaded`.
- `session:` lines check `db` directly after the call, before any re-read: "clean" = `not db.new and not db.dirty and not db.deleted`; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Later lines assert on `exc.value`, one per line.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no `rb`.
- **Statement recorder** = a `before_cursor_execute` listener on `db`'s engine records the SQL text of every statement sent during the When only: `stmts`. "the lock statement" = the one statement in `stmts` that selects from `payment_transactions` and contains `FOR UPDATE`.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`, `strict=False` when the Expect line says `(non-strict)`. Write calls and checks as shown even when a parameter, column or field does not exist yet. A card whose Given calls `svc.initiate_payment(..., idempotency_key=…)` fails in the Given today (`TypeError`); that is its expected failure.

**Race simulations.** IK-46 (`initiate_payment` R7e2, other `IntegrityError`): the same patch with `side_effect=[None, restore_then_real]`, where `restore_then_real` sets `A_ROW.idempotency_key = K`, runs `db.commit()`, then returns the real method's answer; the patch object is `lk`. IK-28, IK-29 (`initiate_payment` R7e2, BUG-3023, spec Notes): during the When, `PaymentTransactionDAO.get_by_workspace_and_idempotency_key` (`app.dao.payment_transaction`) is patched with `autospec=True` and `side_effect=[None, <the real method>]`, so the first lookup misses and the re-read after the `IntegrityError` finds the committed winner. IK-43 uses `side_effect=[None, None]` (re-read miss). Nothing else is patched.

## `_to_response` (module-level function)

`_to_response` is a module-level function in `app/services/payment_transaction_service.py`, not a service method: import it from that module and call it directly, with no `svc.` prefix.

### PTS-TR-01 — every stored field is copied, with the given name
- **Rules:** `_to_response` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T but `status "VALIDATED_SUCCESS"`, `val_id "VAL-1"`, `risk_level 0`, `risk_title "Safe"`, `bank_tran_id "BANK-1"`, `card_type "VISA-Brac bank"`, `verify_sign "SIG-1"`, `value_a "va"`, `value_b "vb"`, `value_c "vc"`, `value_d "vd"`, `validated_at NOW`, `risk_resolved_by U2.id`, `risk_resolved_at NOW`, `risk_resolution_note NOTE`, `last_ipn_payload {"k": "v"}`.

**When**
- `result = _to_response(T, initiated_by_name="Karim")`.

**Then**
1. returns: `isinstance(result, PaymentTransactionResponse)`.
2. returns: `result.id == T.id`, `result.workspace_id == W1.id`, `result.tran_id == A26`, `result.status == "VALIDATED_SUCCESS"`.
3. returns: `result.amount == Decimal("500.00")`, `result.currency == "BDT"`, `result.cus_name == "Karim"`, `result.cus_email == "karim@example.com"`, `result.cus_phone == "01711000000"`.
4. returns: `result.value_a == "va"`, `result.value_b == "vb"`, `result.value_c == "vc"`, `result.value_d == "vd"`.
5. returns: `result.session_key == "SESS-0"`, `result.gateway_page_url == "https://sandbox.example/pay/SESS-0"`, `result.val_id == "VAL-1"`, `result.risk_level == 0`, `result.risk_title == "Safe"`, `result.bank_tran_id == "BANK-1"`, `result.card_type == "VISA-Brac bank"`.
6. returns: `result.risk_resolved_by == U2.id`, `result.risk_resolved_at == NOW`, `result.risk_resolution_note == NOTE`, `result.validated_at == NOW`.
7. returns: `result.initiated_by == U1.id`, `result.initiated_at == T.initiated_at`, `result.created_at == T.created_at`, `result.updated_at == T.updated_at`.
8. returns: `result.initiated_by_name == "Karim"`.
9. returns: `"verify_sign" not in result.model_dump()`.
10. returns: `"last_ipn_payload" not in result.model_dump()`.

### PTS-TR-02 — the name defaults to None
- **Rules:** `_to_response` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `result = _to_response(T)`.

**Then**
1. returns: `isinstance(result, PaymentTransactionResponse)`.
2. returns: `result.tran_id == A26`.
3. returns: `result.initiated_by_name is None`.

### PTS-TR-03 — the row is not changed
- **Rules:** `_to_response` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = _to_response(T, initiated_by_name="Karim")`.

**Then**
1. returns: `result.id == T.id`.
2. session: clean.
3. unchanged: unchanged(T).

### PTS-TR-04 — BUG-3022: failed_reason and outcome_verified are in the response
- **Rules:** `_to_response` R1a [BUG-3022]
- **Kind:** bug
- **Expect:** xfail BUG-3022
- **Fails today on:** Then 2 (the response has no `failed_reason` field)

**Given**
1. T but `status "INIT_FAILED"`, `session_key None`, `gateway_page_url None`.
2. in memory (not flushed): `T.failed_reason = "Store is de-active"`, `T.outcome_verified = False`.

**When**
- `result = _to_response(T)`.

**Then**
1. returns: `result.status == "INIT_FAILED"`.
2. returns: `result.failed_reason == "Store is de-active"`.
3. returns: `result.outcome_verified is False`.

## `PaymentTransactionService.initiate_payment`

### PTS-I-01 — an accepted start is committed and answered from the saved row
- **Rules:** `initiate_payment` R1, R2, R6; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`, inside **spies**.

**Then**
1. returns: `isinstance(result, InitiatePaymentResponse)`.
2. returns: `re.fullmatch(HEX26, result.tran_id)`.
3. returns: `result.status == "INITIATED"`, `result.gateway_page_url == URL1`.
4. returns: `result.failed_reason is None`.
5. mock called: `gw.init_session.call_count == 1`.
6. mock called: `gw.init_session.call_args.args[0].tran_id == result.tran_id`.
7. mock called: `gw.validate.call_count == 0`.
8. mock called: `cm.call_count == 1`.
9. committed: exactly 1 `payment_transactions` row in W1: `tran_id == result.tran_id`, `status == "INITIATED"`, `amount == Decimal("500.00")`, `currency == "BDT"`, `cus_name == "Karim"`, `initiated_by == U1.id`, `session_key == "SESS-1"`, `gateway_page_url == URL1`.
10. committed: events(that row) == `["initiated"]`.
11. committed: that event has `description == "Checkout session created for 500 BDT"`, `performed_by == U1.id`, `metadata_json == {"session_key": "SESS-1"}`.

### PTS-I-02 — the answer reads the stored gateway URL, also when the gateway gives none
- **Rules:** `initiate_payment` R2; TC2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gw.init_session.return_value = InitSessionResult(status="SUCCESS", session_key=None, gateway_page_url=None)`.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.gateway_page_url is None`.
3. returns: `result.failed_reason is None`.
4. committed: the row with `tran_id == result.tran_id` has `status == "INITIATED"`, `gateway_page_url is None`.

### PTS-I-03 — BUG-019: a refused start is committed and answered as INIT_FAILED
- **Rules:** `initiate_payment` R3, R3a [BUG-019]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-019
- **Fails today on:** Then 1 (the call raises HTTPException 502)

**Given**
1. `gw.init_session.return_value = REFUSED`.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. returns: `result.status == "INIT_FAILED"`.
2. returns: `result.failed_reason == "Store is de-active"`.
3. returns: `result.gateway_page_url is None`.
4. returns: `re.fullmatch(HEX26, result.tran_id)`.
5. mock called: `gw.init_session.call_count == 1`.
6. committed: exactly 1 row in W1: `tran_id == result.tran_id`, `status == "INIT_FAILED"`, `failed_reason == "Store is de-active"`.
7. committed: events(that row) == `["initiation_failed"]`.

### PTS-I-04 — BUG-019: a refusal without a reason answers "unknown error"
- **Rules:** `initiate_payment` R3a [BUG-019]
- **Kind:** bug
- **Expect:** xfail BUG-019
- **Fails today on:** Then 1 (the call raises HTTPException 502)

**Given**
1. `gw.init_session.return_value = InitSessionResult(status="FAILED", failed_reason=None)`.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. returns: `result.status == "INIT_FAILED"`.
2. returns: `result.failed_reason == "unknown error"`.
3. committed: the row with `tran_id == result.tran_id` has `failed_reason == "unknown error"`.

### PTS-I-05 — BUG-019: a failing commit of a refused start saves nothing
- **Rules:** `initiate_payment` R3 [BUG-019]; TC4
- **Kind:** bug
- **Expect:** xfail BUG-019
- **Fails today on:** Then 1 (the 502 HTTPException is raised instead of the commit's error)

**Given**
1. `gw.init_session.return_value = REFUSED`.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has 0 `payment_transactions` rows.

### PTS-I-06 — a raising gateway call passes as the same object and nothing is saved
- **Rules:** `initiate_payment` R4; Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `E = TimeoutError("gateway timeout")`; `gw.init_session.side_effect = E`.
2. commit point.
3. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. raises: `TimeoutError`.
2. raises: `exc.value is E`.
3. mock called: `gw.init_session.call_count == 1`.
4. count: x_gone.
5. nothing written: nothing written.
6. session: usable.

### PTS-I-07 — no free tran_id: the 500 passes unchanged, no gateway call
- **Rules:** `initiate_payment` R4; Errors row 3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. Five rows, T but `tran_id "1"*26`, `"2"*26`, `"3"*26`, `"4"*26`, `"5"*26`.
2. `app.managers.payment_transaction_manager.secrets.token_hex` patched (during the When) with `side_effect = ["1"*26, "2"*26, "3"*26, "4"*26, "5"*26, "6"*26]`.
3. commit point.
4. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 500`.
3. raises: `exc.value.detail == "Could not generate a unique transaction ID"`.
4. mock called: `gw.init_session.call_count == 0`.
5. count: x_gone.
6. count: 0 rows with `tran_id == "6"*26`.
7. nothing written: nothing written.

### PTS-I-08 — an invalid amount is refused by the schema before the service
- **Rules:** `initiate_payment` R4 (schema `ValidationError`)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transactions.

**When**
- build `InitiatePaymentRequest(amount=Decimal("0"), currency="BDT", cus_phone="01711000000")` (target `schema`; `svc` is not called).

**Then**
1. raises: `pydantic.ValidationError`.
2. mock called: `gw.init_session.call_count == 0`.
3. count: W1 has 0 `payment_transactions` rows.

### PTS-I-09 — a failure after the session was opened saves nothing and returns no URL
- **Rules:** `initiate_payment` R5, R6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. commit point.
2. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=MISSING, user=U1, request=REQ)`.

**Then**
1. raises: `IntegrityError`.
2. mock called: `gw.init_session.call_count == 1`.
3. count: 0 `payment_transactions` rows with `workspace_id == MISSING`.
4. count: x_gone.
5. nothing written: nothing written.
6. session: usable.

### PTS-I-10 — a failing commit is rolled back, the gateway was called once and not again
- **Rules:** `initiate_payment` R5, R6; Errors row 5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transactions.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. mock called: `gw.init_session.call_count == 1`.
4. count: W1 has 0 `payment_transactions` rows.
5. count: 0 `payment_transaction_events` rows in W1.

### PTS-I-11 — a failing re-read leaves the attempt saved
- **Rules:** `initiate_payment` R8; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transactions.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `payment_transactions` row, `status == "INITIATED"`, `session_key == "SESS-1"`.
3. committed: events(that row) == `["initiated"]`.

### PTS-I-12 — two calls without a key make two attempts
- **Rules:** `initiate_payment` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Step: `A = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.tran_id != A.tran_id`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: W1 has exactly 2 `payment_transactions` rows.
5. committed: the set of their `tran_id` values == `{A.tran_id, result.tran_id}`.

### PTS-I-13 — an accepted start in W2 is stored in W2 only
- **Rules:** `initiate_payment` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W0, W1, W2 have no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W2.id, user=U3, request=REQ)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. committed: W2 has exactly 1 row, `tran_id == result.tran_id`, `initiated_by == U3.id`.
3. count: W1 has 0 rows.
4. count: W0 has 0 rows.

## `PaymentTransactionService.initiate_payment` — idempotency (BUG-3023)

### PTS-IK-01 — a new key starts an attempt; the key and its fingerprint are stored
- **Rules:** `initiate_payment` R7a, R7a1, R7c1 [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`, `result.gateway_page_url == URL1`.
2. returns: `result.failed_reason is None`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: exactly 1 row in W1: `tran_id == result.tran_id`, `idempotency_key == "K-1"`.
5. committed: that row has `idempotency_fingerprint == FPX`.
6. committed: events(that row) == `["initiated"]`.

### PTS-IK-02 — a refused start stores the key and the fingerprint too
- **Rules:** `initiate_payment` R7a, R7a1 [BUG-3023] (needs BUG-019)
- **Kind:** bug
- **Expect:** xfail BUG-3023, BUG-019
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. `gw.init_session.return_value = REFUSED`.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.status == "INIT_FAILED"`.
2. returns: `result.failed_reason == "Store is de-active"`.
3. committed: exactly 1 row in W1: `status == "INIT_FAILED"`, `idempotency_key == "K-1"`.
4. committed: that row has `idempotency_fingerprint == FPX`.

### PTS-IK-03 — same key, same body: the stored attempt is returned, no gateway call, nothing written
- **Rules:** `initiate_payment` R7b, R7b1 [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.
3. X (after the commit point).

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`, inside **spies**.

**Then**
1. returns: `isinstance(result, InitiatePaymentResponse)`.
2. returns: `result.tran_id == A.tran_id`.
3. returns: `result.status == "INITIATED"`, `result.gateway_page_url == URL1`.
4. returns: `result.failed_reason is None`.
5. mock called: `gw.init_session.call_count == 0`.
6. mock called: `cm.call_count == 0`.
7. mock called: `rb.call_count == 1`.
8. session: clean.
9. count: x_gone.
10. nothing written: nothing written.
11. count: events(A_ROW) == `["initiated"]` (no `duplicate_ignored`).
12. unchanged: unchanged(A_ROW).

### PTS-IK-04 — same key on a refused attempt replays INIT_FAILED with its reason
- **Rules:** `initiate_payment` R7b [BUG-3023] (needs BUG-019)
- **Kind:** bug
- **Expect:** xfail BUG-3023, BUG-019
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. `gw.init_session.return_value = REFUSED`.
2. first(W1.id, U1, REQ, K).
3. `gw.init_session.return_value = OKS`.
4. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. returns: `result.status == "INIT_FAILED"`.
3. returns: `result.failed_reason == "Store is de-active"`.
4. returns: `result.gateway_page_url is None`.
5. mock called: `gw.init_session.call_count == 0`.
6. nothing written: nothing written.

### PTS-IK-05 — same key after the attempt was paid shows the current status
- **Rules:** `initiate_payment` R7b [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. paid(A_ROW).
3. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. returns: `result.status == "VALIDATED_SUCCESS"`.
3. returns: `result.gateway_page_url == URL1`.
4. mock called: `gw.init_session.call_count == 0`.
5. mock called: `gw.validate.call_count == 0`.
6. nothing written: nothing written.
7. unchanged: unchanged(A_ROW).

### PTS-IK-06 — same key, different amount: 409, nothing written, no gateway call
- **Rules:** `initiate_payment` R7c [BUG-3023]; Errors row 4; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.
3. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key=K)`, inside **spies**.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == IDEM409`.
4. mock called: `gw.init_session.call_count == 0`.
5. mock called: `cm.call_count == 0`.
6. mock called: `rb.call_count == 1`.
7. count: x_gone.
8. nothing written: nothing written.
9. unchanged: unchanged(A_ROW).
10. session: usable.

### PTS-IK-07 — same key, different currency: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but currency "USD", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-08 — same key, a customer name added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_name "Other Name", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-09 — same key, a customer email added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_email "other@example.com", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-10 — same key, a different phone: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_phone "01811000000", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-11 — same key, value_a added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but value_a "plan:pro", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-12 — same key, value_b added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but value_b "b-val", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-13 — same key, value_c added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but value_c "c-val", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-14 — same key, value_d added: 409
- **Rules:** `initiate_payment` R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but value_d "d-val", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == IDEM409`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-15 — same key, same body, another member of the workspace: 409
- **Rules:** `initiate_payment` R7c, R7c1 [BUG-3023] (the key belongs to the first member: `profile_id` is in the fingerprint)
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ but cus_name "Karim" and cus_email "karim@example.com", K).
2. commit point.
3. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U2, request=REQ but cus_name "Karim" and cus_email "karim@example.com", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
3. mock called: `gw.init_session.call_count == 0`.
4. count: x_gone.
5. nothing written: nothing written.
6. unchanged: unchanged(A_ROW).

### PTS-IK-16 — the key used only in W0 does not touch a call in W1
- **Rules:** `initiate_payment` R7d [BUG-3023]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W0.id, U3, REQ, K) (the W0 attempt is A).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.tran_id != A.tran_id`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: W1 has exactly 1 row, `tran_id == result.tran_id`, `idempotency_key == "K-1"`, `initiated_by == U1.id`.
5. unchanged: unchanged(A_ROW).

### PTS-IK-17 — the key used only in W2 does not touch a call in W1
- **Rules:** `initiate_payment` R7d [BUG-3023]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W2.id, U3, REQ, K) (the W2 attempt is A).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.tran_id != A.tran_id`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: W1 has exactly 1 row, `tran_id == result.tran_id`, `idempotency_key == "K-1"`.
5. unchanged: unchanged(A_ROW).

### PTS-IK-18 — the key used in W1 with another body does not give 409 in W2
- **Rules:** `initiate_payment` R7d [BUG-3023]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K) (the W1 attempt is A).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W2.id, user=U3, request=REQ but amount Decimal("700"), idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.tran_id != A.tran_id`.
3. returns: `result.gateway_page_url == URL1`.
4. mock called: `gw.init_session.call_count == 1`.
5. committed: W2 has exactly 1 row, `amount == Decimal("700.00")`, `idempotency_key == "K-1"`.
6. unchanged: unchanged(A_ROW).

### PTS-IK-19 — the key used in W1 and W2, a call in W0 is a new attempt
- **Rules:** `initiate_payment` R7d [BUG-3023]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K); `A1 = A`.
2. first(W2.id, U3, REQ, K); `A2 = A`.
3. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W0.id, user=U3, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `result.tran_id not in {A1.tran_id, A2.tran_id}`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: W0 has exactly 1 row, `idempotency_key == "K-1"`.
5. count: W1 has exactly 1 row; W2 has exactly 1 row.

### PTS-IK-20 — a call without a key next to a stored key is a new attempt
- **Rules:** `initiate_payment` R7, R7a1, R7b [BUG-3023] (no key never matches; both columns NULL)
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ)`.

**Then**
1. returns: `result.tran_id != A.tran_id`.
2. returns: `result.status == "INITIATED"`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: W1 has exactly 2 rows.
5. committed: the row with `tran_id == result.tran_id` has `idempotency_key is None`.
6. committed: that row has `idempotency_fingerprint is None`.

### PTS-IK-21 — a key in other capitals is another key
- **Rules:** `initiate_payment` Inputs (key compared exactly), R7a [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key="k-1")`.

**Then**
1. returns: `result.tran_id != A.tran_id`.
2. returns: `result.status == "INITIATED"`.
3. mock called: `gw.init_session.call_count == 1`.
4. committed: the row with `tran_id == result.tran_id` has `idempotency_key == "k-1"`.

### PTS-IK-22 — a key with a leading space is another key
- **Rules:** `initiate_payment` Inputs (key compared exactly), R7a [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key=" K-1")`.

**Then**
1. returns: `result.tran_id != A.tran_id`.
2. mock called: `gw.init_session.call_count == 1`.
3. committed: the row with `tran_id == result.tran_id` has `idempotency_key == " K-1"`.

### PTS-IK-23 — a part of a stored key is another key
- **Rules:** `initiate_payment` Inputs (key compared exactly), R7a [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, "XK-1Y").
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key=K)`.

**Then**
1. returns: `result.tran_id != A.tran_id`.
2. mock called: `gw.init_session.call_count == 1`.
3. committed: the row with `tran_id == result.tran_id` has `idempotency_key == "K-1"`.

### PTS-IK-24 — `_` in a key is literal
- **Rules:** `initiate_payment` Inputs (key compared exactly), R7a [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key="K_1")`.

**Then**
1. returns: `result.tran_id != A.tran_id`.
2. mock called: `gw.init_session.call_count == 1`.
3. committed: the row with `tran_id == result.tran_id` has `idempotency_key == "K_1"`.

### PTS-IK-25 — the unique index ix_payment_transactions_workspace_idempotency_key exists as specified
- **Rules:** `initiate_payment` R7a1, R7e [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Fails today on:** Then 1 (no such index)

**Given**
1. nothing beyond the standing rows.

**When**
- `rows = db.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_payment_transactions_workspace_idempotency_key'")).scalars().all()`.

**Then**
1. count: `len(rows) == 1`.
2. returns: `rows[0] == "CREATE UNIQUE INDEX ix_payment_transactions_workspace_idempotency_key ON public.payment_transactions USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)"`.

### PTS-IK-26 — two rows with one key in one workspace are refused by the database
- **Rules:** `initiate_payment` R7a1, R7e [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: the rows are built with unknown keywords, already in the Given)

**Given**
1. keyed(T, "K-1", "0"*64).
2. commit point.

**When**
- inside `db.begin_nested()`: add keyed(T but `tran_id B26`, "K-1", "1"*64), then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"ix_payment_transactions_workspace_idempotency_key" in str(exc.value.orig)`.
4. count: (after the savepoint rollback) exactly 1 row with `idempotency_key == "K-1"`.

### PTS-IK-27 — the index allows one key per workspace and many rows without a key
- **Rules:** `initiate_payment` R7, R7a1, R7d [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: the rows are built with unknown keywords)

**Given**
1. nothing beyond the standing rows.

**When**
- add and flush, one at a time: keyed(T but `workspace_id W0.id`, "K-1", "0"*64); keyed(T but `tran_id B26`, "K-1", "0"*64); keyed(T but `workspace_id W2.id`, `tran_id C26`, "K-1", "0"*64); T but `tran_id "1"*26`, `idempotency_key None`, `idempotency_fingerprint None`; T but `tran_id "2"*26`, `idempotency_key None`, `idempotency_fingerprint None`.

**Then**
1. count: exactly 3 rows with `idempotency_key == "K-1"`.
2. count: exactly 2 rows of W1 with `idempotency_key IS NULL`.

### PTS-IK-28 — the race loser with the same body answers with the winner's attempt, never 500
- **Rules:** `initiate_payment` R7e, R7e2, R7b [BUG-3023]; Errors row "lost the race"
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.
3. `gw.init_session.return_value = InitSessionResult(status="SUCCESS", session_key="SESS-2", gateway_page_url=URL2)`.
4. the race simulation is active (Conventions).

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`, inside **spies**.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. returns: `result.status == "INITIATED"`.
3. returns: `result.gateway_page_url == URL1`.
4. mock called: `gw.init_session.call_count == 1`.
5. mock called: `cm.call_count == 0`.
6. mock called: `rb.call_count >= 1`.
7. count: W1 has exactly 1 `payment_transactions` row, `tran_id == A.tran_id`.
8. count: 0 rows with `session_key == "SESS-2"`.
9. session: usable.

### PTS-IK-29 — the race loser with a different body answers 409, never 500
- **Rules:** `initiate_payment` R7e, R7e2, R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.
3. `gw.init_session.return_value = InitSessionResult(status="SUCCESS", session_key="SESS-2", gateway_page_url=URL2)`.
4. the race simulation is active (Conventions).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("600"), idempotency_key=K)`, inside **spies**.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. mock called: `gw.init_session.call_count == 1`.
5. mock called: `rb.call_count >= 1`.
6. count: W1 has exactly 1 `payment_transactions` row, `tran_id == A.tran_id`.
7. count: 0 rows with `amount == Decimal("600.00")`.
8. session: usable.

### PTS-IK-30 — a replay sends no INSERT or UPDATE and never generates a tran_id
- **Rules:** `initiate_payment` R7b, R7b1, R7e1 [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`, with the **statement recorder**.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. returns: no statement in `stmts` starts with `INSERT` or `UPDATE`.
4. returns: every statement in `stmts` that selects from `payment_transactions` has `idempotency_key` in its WHERE clause (the part after `WHERE`), so no `_generate_tran_id` check ran.

### PTS-IK-31 — the key lookup is a single-table read with no lock, sent first
- **Rules:** `initiate_payment` R7e1 [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`, with the **statement recorder**.

**Then**
1. returns: `result.status == "INITIATED"`.
2. count: exactly 1 statement in `stmts` selects from `payment_transactions` and has `idempotency_key` in its WHERE clause (the part after `WHERE`); call it `lookup`.
3. returns: `"FOR UPDATE" not in lookup`.
4. returns: `"JOIN" not in lookup.upper()`.
5. returns: `lookup` comes before every other statement in `stmts` that touches `payment_transactions`.

### PTS-IK-32 — amount 500.00 after 500 is the same body: replay
- **Rules:** `initiate_payment` R7c1 (amount by value), R7b [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("500.00"), idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-33 — cus_name "" after an omitted name is the same body: replay
- **Rules:** `initiate_payment` R7c1 (blank text = null) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_name "", idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-34 — currency "BDT" after an omitted currency is the same body: replay
- **Rules:** `initiate_payment` R7c1 (omitted = default) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ0, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-35 — a name with outer spaces is the same body as the trimmed name: replay
- **Rules:** `initiate_payment` R7c1 (text trimmed) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ but cus_name "Ali", K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_name " Ali ", idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-36 — the stored fingerprint reproduces the spec's worked example
- **Rules:** `initiate_payment` R7a1, R7c1 (worked example) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. P7 = `make_profile(db, id=7)` (profile id 7, as in the spec's example).
2. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=P7, request=InitiatePaymentRequest(amount=Decimal("500"), currency="BDT", cus_phone="01700000000"), idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. returns: `json.dumps({"amount": "500", "currency": "BDT", "cus_email": None, "cus_name": None, "cus_phone": "01700000000", "profile_id": 7, "value_a": None, "value_b": None, "value_c": None, "value_d": None}, sort_keys=True, separators=(",", ":")) == '{"amount":"500","currency":"BDT","cus_email":null,"cus_name":null,"cus_phone":"01700000000","profile_id":7,"value_a":null,"value_b":null,"value_c":null,"value_d":null}'` (the spec's JSON, keys sorted).
3. committed: the row with `tran_id == result.tran_id` has `idempotency_fingerprint == "0bbacdbcb2eb158eba9bfab58060dd04bea674cddc22a51a78dd49db87a949bd"`.

### PTS-IK-45 — the stored fingerprint writes 500.50 as "500.5" and a trimmed name with its case
- **Rules:** `initiate_payment` R7a1, R7c1 (amount, text) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but amount Decimal("500.50") and cus_name " Ali ", idempotency_key=K)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. committed: the row with `tran_id == result.tran_id` has `idempotency_fingerprint == fp({**FPO, "amount": "500.5", "cus_name": "Ali"})`.

### PTS-IK-37 — a name in other case is a different body: 409
- **Rules:** `initiate_payment` R7c1 (case kept), R7c [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ but cus_name "Ali", K).
2. commit point.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but cus_name "ali", idempotency_key=K)`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
3. mock called: `gw.init_session.call_count == 0`.
4. nothing written: nothing written.

### PTS-IK-38 — after BUG-022, currency "bdt" is the same body as "BDT": replay
- **Rules:** `initiate_payment` R7c1 (currency as the schema leaves it) [BUG-3023] (needs BUG-022)
- **Kind:** bug
- **Expect:** xfail BUG-3023, BUG-022
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but currency "bdt", idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-39 — a whitespace-only value_a is the same body as an omitted one: replay
- **Rules:** `initiate_payment` R7c1 (whitespace-only = null) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ but value_a "   ", idempotency_key=K)`.

**Then**
1. returns: `result.tran_id == A.tran_id`.
2. mock called: `gw.init_session.call_count == 0`.
3. nothing written: nothing written.

### PTS-IK-40 — a key of 100 characters is stored exactly as sent
- **Rules:** `initiate_payment` Inputs (key `String(100)`, never trimmed), R7a1 [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. W1 has no transactions.

**When**
- `result = svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=" K"*50)`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. committed: the row with `tran_id == result.tran_id` has `idempotency_key == " K"*50`.

### PTS-IK-41 — a key of 101 characters passed directly: DataError, nothing saved
- **Rules:** `initiate_payment` Inputs (length checked only at the endpoint) [BUG-3023]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. commit point.
2. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key="K"*101)`.

**Then**
1. raises: `DataError`.
2. count: x_gone.
3. nothing written: nothing written.
4. session: usable.

### PTS-IK-42 — an IntegrityError on another constraint is re-raised unchanged
- **Rules:** `initiate_payment` R7e2 (other `IntegrityError`) [BUG-3023]; Errors row "another constraint"
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. commit point.
2. X (after the commit point).

**When**
- `svc.initiate_payment(db, workspace_id=MISSING, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. mock called: `gw.init_session.call_count == 1`.
4. count: x_gone.
5. nothing written: nothing written.

### PTS-IK-43 — a key-index IntegrityError whose re-read finds no row is re-raised
- **Rules:** `initiate_payment` R7e2 (re-read miss) [BUG-3023]; Errors row "winner's row not found"
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. commit point.
3. `PaymentTransactionDAO.get_by_workspace_and_idempotency_key` patched (during the When) with `side_effect=[None, None]`.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=U1, request=REQ, idempotency_key=K)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: W1 has exactly 1 `payment_transactions` row, `tran_id == A.tran_id`.
4. session: usable.

### PTS-IK-44 — a later status change keeps the key and the fingerprint
- **Rules:** `initiate_payment` R7a1 (written only on insert) [BUG-3023]
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. `gw.validate.return_value = OKV(A.tran_id)`.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A.tran_id, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. committed: A_ROW has `idempotency_key == "K-1"`.
3. committed: A_ROW has `idempotency_fingerprint == FPX`.

### PTS-IK-46 — a non-key IntegrityError while a matching keyed winner exists is re-raised, not replayed
- **Rules:** `initiate_payment` R7e2 (an `IntegrityError` on any other constraint is re-raised) [BUG-3023]; Errors row "another constraint"
- **Kind:** bug
- **Expect:** xfail BUG-3023
- **Author:** claude
- **Fails today on:** Then 1 (the Given's first call raises TypeError: no `idempotency_key` parameter)

**Given**
1. first(W1.id, U1, REQ, K).
2. `A_ROW.idempotency_key = None`, flushed (its fingerprint stays).
3. commit point.
4. the IK-46 race simulation is active (Conventions), patch object `lk`.

**When**
- `svc.initiate_payment(db, workspace_id=W1.id, user=GHOST, request=REQ, idempotency_key=K)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. mock called: `lk.call_count == 1`.
4. mock called: `gw.init_session.call_count == 1`.
5. count: 0 `payment_transactions` rows with `initiated_by == MISSING`.
6. re-read A_ROW: `idempotency_key is None`.
7. session: usable.

## `PaymentTransactionService.handle_gateway_callback`

### PTS-GC-01 — a verified IPN is committed and the row is returned re-read
- **Rules:** `handle_gateway_callback` R1, R5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. loaded: `status`, `updated_at`, `validated_at`, `val_id`.
2. returns: `isinstance(result, PaymentTransaction)`, `result.id == T.id`.
3. returns: `result.status == "VALIDATED_SUCCESS"`.
4. mock called: `gw.validate.call_count == 1`, `gw.validate.call_args.args == ("VAL-1",)`.
5. committed: T has `status == "VALIDATED_SUCCESS"`, `val_id == "VAL-1"`, `bank_tran_id == "BANK-1"`, `validated_at == NOW`.
6. committed: events(T) == `["ipn_received", "validated_success"]`.

### PTS-GC-02 — a risky IPN is committed as RISK_HOLD
- **Rules:** `handle_gateway_callback` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. `gw.validate.return_value = RISKY(A26)`.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.id == T.id`, `result.status == "RISK_HOLD"`.
2. committed: T has `status == "RISK_HOLD"`, `risk_level == 1`, `risk_title == "Suspicious card"`.
3. committed: events(T) == `["ipn_received", "risk_hold"]`.

### PTS-GC-03 — the same IPN again: RISK_HOLD and its stamp stay, one duplicate_ignored is committed
- **Rules:** `handle_gateway_callback` R2, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. held(T) at V0.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.id == T.id`, `result.status == "RISK_HOLD"`.
2. mock called: `gw.validate.call_count == 0`.
3. committed: events(T) == `["ipn_received", "risk_hold", "duplicate_ignored"]`.
4. committed: the `duplicate_ignored` event has `description == "Duplicate ipn callback ignored; transaction already RISK_HOLD"`.
5. committed: T has `status == "RISK_HOLD"`, `val_id == "VAL-1"`, `risk_level == 1`.
6. committed: T has `validated_at == V0`.

### PTS-GC-04 — a redirect after a verified success keeps the stored outcome and val_id
- **Rules:** `handle_gateway_callback` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. paid(T) at V0.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-2", source="redirect_success")`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`, `result.val_id == "VAL-1"`.
2. mock called: `gw.validate.call_count == 0`.
3. committed: T has `status == "VALIDATED_SUCCESS"`, `val_id == "VAL-1"`, `validated_at == V0`.
4. committed: the last event of T has `event_type == "duplicate_ignored"`, `description == "Duplicate redirect_success callback ignored; transaction already VALIDATED_SUCCESS"`.
5. count: T has exactly 3 events.

### PTS-GC-05 — a callback finds the transaction in any workspace
- **Rules:** `handle_gateway_callback` R1 (callbacks read across workspaces)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T but `workspace_id W2.id`, `initiated_by U3.id`.
2. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.id == T.id`, `result.workspace_id == W2.id`.
2. returns: `result.status == "VALIDATED_SUCCESS"`.
3. committed: T has `status == "VALIDATED_SUCCESS"`.
4. committed: both events of T have `workspace_id == W2.id`.

### PTS-GC-06 — an unknown tran_id: 404 passes unchanged, nothing saved, no gateway call
- **Rules:** `handle_gateway_callback` R4; Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.
3. X (after the commit point).

**When**
- `svc.handle_gateway_callback(db, tran_id=Z26, val_id="VAL-1", source="ipn")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Unknown tran_id: " + Z26`.
4. mock called: `gw.validate.call_count == 0`.
5. count: x_gone.
6. nothing written: nothing written.
7. unchanged: unchanged(T).

### PTS-GC-07 — a raising validate: the received event is rolled back too
- **Rules:** `handle_gateway_callback` R4; Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. `E = TimeoutError("validate timeout")`; `gw.validate.side_effect = E`.
3. commit point.
4. X (after the commit point).

**When**
- `svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. raises: `TimeoutError`.
2. raises: `exc.value is E`.
3. mock called: `gw.validate.call_count == 1`.
4. count: T has 0 events.
5. count: x_gone.
6. unchanged: unchanged(T).
7. session: usable.

### PTS-GC-08 — after a failed callback the next one processes the row normally
- **Rules:** `handle_gateway_callback` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. commit point.
3. Step: `gw.validate.side_effect = TimeoutError("t")`; call `svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")` inside `pytest.raises(TimeoutError)`; then `gw.validate.side_effect = None`, `gw.validate.return_value = OKV(A26)`, `gw.reset_mock()`.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. mock called: `gw.validate.call_count == 1`.
3. committed: events(T) == `["ipn_received", "validated_success"]`.

### PTS-GC-09 — a failing commit saves nothing and validate is not called again
- **Rules:** `handle_gateway_callback` R5; Errors row 3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. mock called: `gw.validate.call_count == 1`.
4. count: T has 0 events.
5. re-read T: `status == "INITIATED"`, `val_id is None`.

### PTS-GC-10 — a failing re-read leaves the outcome saved
- **Rules:** `handle_gateway_callback` R6; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "VALIDATED_SUCCESS"`.
3. committed: events(T) == `["ipn_received", "validated_success"]`.

### PTS-GC-11 — the row is locked with FOR UPDATE before validate runs
- **Rules:** `handle_gateway_callback` R3
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T.
2. commit point.
3. `gw.validate.side_effect` = a function that stores `len(stmts)` in `seen` and returns `OKV(A26)`.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`, with the **statement recorder**.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. returns: exactly 1 lock statement in `stmts`.
3. returns: the lock statement does not contain `"SKIP LOCKED"` and does not contain `"NOWAIT"`.
4. returns: the index of the lock statement in `stmts` is `< seen`.

### PTS-GC-12 — a foreign val_id: the rejection is committed and gateway fields stay empty
- **Rules:** `handle_gateway_callback` R1 (rejection path)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. `gw.validate.return_value = OKV(B26)`.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-9", source="ipn")`.

**Then**
1. returns: `result.id == T.id`.
2. committed: count of T's events is exactly 2; the first is `ipn_received`.
3. committed: the second event has `description == "val_id/tran_id mismatch via ipn callback: gateway resolved it to tran_id=" + B26`.
4. committed: T has `val_id is None`, `bank_tran_id is None`, `risk_level is None`.

### PTS-GC-13 — pass-through BUG-023: a foreign val_id leaves the row INITIATED
- **Rules:** `handle_gateway_callback` R1 [BUG-023]
- **Kind:** bug
- **Expect:** xfail BUG-023
- **Fails today on:** Then 1 (status becomes VALIDATED_FAILED)

**Given**
1. T.
2. `gw.validate.return_value = OKV(B26)`.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-9", source="ipn")`.

**Then**
1. returns: `result.status == "INITIATED"`.
2. committed: T has `status == "INITIATED"`, `validated_at is None`.
3. committed: events(T) == `["ipn_received", "validation_rejected"]`.

### PTS-GC-14 — pass-through BUG-026: a verified IPN replaces an unverified cancel
- **Rules:** `handle_gateway_callback` R1 (replacement) [BUG-026]
- **Kind:** bug
- **Expect:** xfail BUG-026
- **Fails today on:** Then 1 (the cancel is final today: status stays CANCELLED)

**Given**
1. T.
2. Step: `svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.
3. commit point.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. mock called: `gw.validate.call_count == 1`.
3. committed: T has `status == "VALIDATED_SUCCESS"`, `val_id == "VAL-1"`.

### PTS-GC-15 — a 404 discards another pending change; the session stays usable
- **Rules:** `handle_gateway_callback` R4; TC3 (session usable, other pending change discarded)
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.
3. in memory after the commit point (not flushed): `T.cus_name = "Pending Edit"`.

**When**
- `svc.handle_gateway_callback(db, tran_id=Z26, val_id="VAL-1", source="redirect_fail")`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Unknown tran_id: " + Z26`.
3. session: `T not in db.dirty`.
4. re-read T: `cus_name == "Karim"`.
5. session: usable.

### PTS-GC-16 — the commit happens once, after the gateway call
- **Rules:** `handle_gateway_callback` R5; TC1
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T.
2. commit point.
3. `gw.validate.side_effect` = a function that stores `cm.call_count` in `seen` and returns `OKV(A26)`.

**When**
- `result = svc.handle_gateway_callback(db, tran_id=A26, val_id="VAL-1", source="ipn")`, inside **spies**.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. mock called: `seen == 0`.
3. mock called: `cm.call_count == 1`.
4. mock called: `gw.validate.call_count == 1`.

## `PaymentTransactionService.handle_terminal_without_validation`

### PTS-TW-01 — a cancel redirect on INITIATED is committed
- **Rules:** `handle_terminal_without_validation` R1, R3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.

**Then**
1. loaded: `status`, `validated_at`, `updated_at`.
2. returns: `isinstance(result, PaymentTransaction)`, `result.id == T.id`, `result.status == "CANCELLED"`.
3. mock called: `gw.validate.call_count == 0`, `gw.init_session.call_count == 0`, `gw.query_by_tran_id.call_count == 0`.
4. committed: T has `status == "CANCELLED"`, `validated_at == NOW`, `val_id is None`.
5. committed: T has exactly 1 event, `description == "Marked CANCELLED via redirect_cancel (no val_id to validate)"`, `performed_by is None`, `metadata_json is None`.

### PTS-TW-02 — a fail redirect without val_id is committed as VALIDATED_FAILED
- **Rules:** `handle_terminal_without_validation` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="VALIDATED_FAILED", source="redirect_fail_no_val_id")`.

**Then**
1. returns: `result.status == "VALIDATED_FAILED"`.
2. committed: T has `status == "VALIDATED_FAILED"`, `validated_at == NOW`.
3. committed: T has exactly 1 event, `description == "Marked VALIDATED_FAILED via redirect_fail_no_val_id (no val_id to validate)"`.

### PTS-TW-03 — pass-through BUG-028: the cancel event type is redirect_cancel
- **Rules:** `handle_terminal_without_validation` R1 [BUG-028]
- **Kind:** bug
- **Expect:** xfail BUG-028
- **Fails today on:** Then 2 (event type is `cancelled`)

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.

**Then**
1. returns: `result.status == "CANCELLED"`.
2. committed: events(T) == `["redirect_cancel"]`.

### PTS-TW-04 — pass-through BUG-026: the redirect's outcome is stored unverified
- **Rules:** `handle_terminal_without_validation` R1 [BUG-026]
- **Kind:** bug
- **Expect:** xfail BUG-026
- **Fails today on:** Then 2 (no `outcome_verified` column)

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.

**Then**
1. returns: `result.status == "CANCELLED"`.
2. committed: T has `outcome_verified is False`.

### PTS-TW-05 — a cancel on a paid row: status stays, one duplicate_ignored committed
- **Rules:** `handle_terminal_without_validation` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. paid(T) at V0.
3. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. committed: T has `status == "VALIDATED_SUCCESS"`, `validated_at == V0`, `val_id == "VAL-1"`.
3. committed: events(T) == `["ipn_received", "validated_success", "duplicate_ignored"]`.
4. committed: the `duplicate_ignored` event has `description == "Duplicate redirect_cancel callback ignored; transaction already VALIDATED_SUCCESS"`.

### PTS-TW-06 — a second cancel on an unverified cancel is a duplicate
- **Rules:** `handle_terminal_without_validation` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. Step at V0: `svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`.
3. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="VALIDATED_FAILED", source="redirect_fail_no_val_id")`.

**Then**
1. returns: `result.status == "CANCELLED"`.
2. committed: T has `status == "CANCELLED"`, `validated_at == V0`.
3. committed: T has exactly 2 events; the last has `event_type == "duplicate_ignored"`, `description == "Duplicate redirect_fail_no_val_id callback ignored; transaction already CANCELLED"`.

### PTS-TW-07 — an unknown tran_id: 404 unchanged, nothing saved
- **Rules:** `handle_terminal_without_validation` R4; Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.
3. X (after the commit point).

**When**
- `svc.handle_terminal_without_validation(db, tran_id=Z26, terminal_status="CANCELLED", source="redirect_cancel")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Unknown tran_id: " + Z26`.
4. count: x_gone.
5. nothing written: nothing written.
6. unchanged: unchanged(T).

### PTS-TW-08 — a terminal status of 20 characters is stored
- **Rules:** `handle_terminal_without_validation` R4 (boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="S"*20, source="redirect_cancel")`.

**Then**
1. returns: `result.status == "S"*20`.
2. committed: T has `status == "S"*20`.

### PTS-TW-09 — a terminal status of 21 characters: DataError, nothing saved
- **Rules:** `handle_terminal_without_validation` R4; Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.
3. X (after the commit point).

**When**
- `svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="S"*21, source="redirect_cancel")`.

**Then**
1. raises: `DataError`.
2. count: T has 0 events.
3. count: x_gone.
4. unchanged: unchanged(T).
5. session: usable.

### PTS-TW-10 — a failing commit saves nothing
- **Rules:** `handle_terminal_without_validation` R4; Errors row 3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: T has 0 events.
4. re-read T: `status == "INITIATED"`, `validated_at is None`.

### PTS-TW-11 — a failing re-read leaves the outcome saved
- **Rules:** `handle_terminal_without_validation` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "CANCELLED"`.
3. committed: T has exactly 1 event.

### PTS-TW-12 — the row is locked with FOR UPDATE and no gateway call is made
- **Rules:** `handle_terminal_without_validation` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `result = svc.handle_terminal_without_validation(db, tran_id=A26, terminal_status="CANCELLED", source="redirect_cancel")`, with the **statement recorder**.

**Then**
1. returns: `result.status == "CANCELLED"`.
2. returns: exactly 1 lock statement in `stmts`.
3. returns: the lock statement does not contain `"SKIP LOCKED"` and does not contain `"NOWAIT"`.
4. mock called: `gw.validate.call_count == 0`.

## `PaymentTransactionService.resolve_risk`

### PTS-RR-01 — an approval is committed; the answer has no initiator name
- **Rules:** `resolve_risk` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `result = svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.

**Then**
1. returns: `isinstance(result, PaymentTransactionResponse)`.
2. returns: `result.id == T.id`, `result.status == "VALIDATED_SUCCESS"`.
3. returns: `result.risk_resolved_by == U1.id`, `result.risk_resolution_note == NOTE`.
4. returns: `result.initiated_by_name is None`.
5. mock called: `gw.validate.call_count == 0`.
6. committed: T has `status == "VALIDATED_SUCCESS"`, `risk_resolved_by == U1.id`, `risk_resolved_at == NOW`, `risk_resolution_note == NOTE`.
7. committed: events(T) == `["ipn_received", "risk_hold", "risk_resolved"]`.
8. committed: the `risk_resolved` event has `description == "Risk hold approved: Card holder confirmed by phone"`, `performed_by == U1.id`.

### PTS-RR-02 — a rejection is committed as VALIDATED_FAILED
- **Rules:** `resolve_risk` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `result = svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=False, note=NOTE)`.

**Then**
1. returns: `result.status == "VALIDATED_FAILED"`.
2. returns: `result.initiated_by_name is None`.
3. committed: T has `status == "VALIDATED_FAILED"`, `risk_resolution_note == NOTE`.
4. committed: the last event of T has `event_type == "risk_resolved"`, `description == "Risk hold rejected: Card holder confirmed by phone"`.

### PTS-RR-03 — a second resolve gets 400; the first decision and its one event stay
- **Rules:** `resolve_risk` R2; Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. held(T).
3. Step: `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.
4. commit point.
5. X (after the commit point).

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U2.id, approve=False, note="Second thoughts")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only transactions in RISK_HOLD can be resolved (current status: VALIDATED_SUCCESS)"`.
4. count: T has exactly 1 event of type `risk_resolved`.
5. count: x_gone.
6. unchanged: unchanged(T).
7. re-read T: `status == "VALIDATED_SUCCESS"`, `risk_resolved_by == U1.id`, `risk_resolution_note == NOTE`.

### PTS-RR-04 — resolving an INITIATED row gets 400
- **Rules:** `resolve_risk` R2; Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only transactions in RISK_HOLD can be resolved (current status: INITIATED)"`.
3. nothing written: nothing written.
4. unchanged: unchanged(T).

### PTS-RR-05 — a held row of W2 is 404 for W1 and stays held
- **Rules:** `resolve_risk` R3; Errors row 1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T but `workspace_id W2.id`, `initiated_by U3.id`.
2. held(T).
3. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Payment transaction {T.id} not found"`.
3. nothing written: nothing written.
4. unchanged: unchanged(T).

### PTS-RR-06 — a held row of W0 is 404 for W1 and stays held
- **Rules:** `resolve_risk` R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T but `workspace_id W0.id`, `initiated_by U3.id`.
2. held(T).
3. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=False, note=NOTE)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Payment transaction {T.id} not found"`.
3. nothing written: nothing written.
4. re-read T: `status == "RISK_HOLD"`, `risk_resolved_by is None`.

### PTS-RR-07 — an unknown id gets 404
- **Rules:** `resolve_risk` R3; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=MISSING, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction 999999999 not found"`.
3. nothing written: nothing written.

### PTS-RR-08 — BUG-029: the row is read with FOR UPDATE OF payment_transactions
- **Rules:** `resolve_risk` R2a [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 2 (no statement contains FOR UPDATE)

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `result = svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`, with the **statement recorder**.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. returns: exactly 1 statement in `stmts` contains `"FOR UPDATE OF payment_transactions"`.
3. returns: that statement does not contain `"SKIP LOCKED"` and does not contain `"NOWAIT"`.

### PTS-RR-09 — a failing commit leaves the hold in place
- **Rules:** `resolve_risk` R4; Errors row 3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read T: `status == "RISK_HOLD"`, `risk_resolved_by is None`.
4. count: T has 0 events of type `risk_resolved`.

### PTS-RR-10 — a failing re-read leaves the decision saved
- **Rules:** `resolve_risk` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "VALIDATED_SUCCESS"`, `risk_resolution_note == NOTE`.
3. committed: T has exactly 1 event of type `risk_resolved`.

### PTS-RR-11 — BUG-3022: the resolve answer carries failed_reason and outcome_verified
- **Rules:** `resolve_risk` R1; `_to_response` R1a [BUG-3022] (`failed_reason` column from BUG-019, `outcome_verified` from BUG-026)
- **Kind:** bug
- **Expect:** xfail BUG-3022, BUG-019, BUG-026
- **Fails today on:** Then 2 (the response has no `failed_reason` field)

**Given**
1. T.
2. held(T).
3. commit point.

**When**
- `result = svc.resolve_risk(db, transaction_id=T.id, workspace_id=W1.id, user_id=U1.id, approve=True, note=NOTE)`.

**Then**
1. returns: `result.status == "VALIDATED_SUCCESS"`.
2. returns: `result.failed_reason is None`.
3. returns: `result.outcome_verified is True`.

## `PaymentTransactionService.get_transaction_by_tran_id`

### PTS-D-01 — a transaction of the workspace with its name and events
- **Rules:** `get_transaction_by_tran_id` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T.
2. E1 = ev(T, "initiated", `datetime(2026, 9, 27, 9, 0)`).
3. E2 = ev(T, "ipn_received", `datetime(2026, 9, 27, 9, 5)`), but `performed_by U1.id`, `metadata_json {"k": "v"}`.
4. commit point.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, PaymentTransactionDetailResponse)`.
2. returns: `result.id == T.id`, `result.tran_id == A26`, `result.status == "INITIATED"`, `result.amount == Decimal("500.00")`.
3. returns: `result.initiated_by_name == "Karim"`.
4. returns: `[e.id for e in result.events] == [E1.id, E2.id]`.
5. returns: `isinstance(result.events[1], PaymentTransactionEventResponse)`.
6. returns: `result.events[1].payment_transaction_id == T.id`, `result.events[1].event_type == "ipn_received"`, `result.events[1].description == "ipn_received note"`, `result.events[1].metadata_json == {"k": "v"}`, `result.events[1].performed_by == U1.id`, `result.events[1].created_at == datetime(2026, 9, 27, 9, 5)`.
7. returns: `not hasattr(result.events[0], "workspace_id")`.

### PTS-D-02 — no initiator: the name is None
- **Rules:** `get_transaction_by_tran_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T but `initiated_by None`.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `result.initiated_by_name is None`.
3. returns: `result.events == []`.

### PTS-D-03 — a tran_id of W2 is 404 for W1
- **Rules:** `get_transaction_by_tran_id` R2; Errors row 1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T but `workspace_id W2.id`, `initiated_by U3.id`.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Payment transaction " + A26 + " not found"`.

### PTS-D-04 — a tran_id of W0 is 404 for W1
- **Rules:** `get_transaction_by_tran_id` R2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T but `workspace_id W0.id`, `initiated_by U3.id`.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction " + A26 + " not found"`.

### PTS-D-05 — an unknown tran_id is 404 with the requested id
- **Rules:** `get_transaction_by_tran_id` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id="nope", workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction nope not found"`.

### PTS-D-06 — the tran_id in capitals is 404
- **Rules:** `get_transaction_by_tran_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id="A"*26, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction " + "A"*26 + " not found"`.

### PTS-D-07 — the tran_id with a trailing space is 404
- **Rules:** `get_transaction_by_tran_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id=A26 + " ", workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction " + A26 + "  not found"`.

### PTS-D-08 — a part of the tran_id is 404
- **Rules:** `get_transaction_by_tran_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id="a"*25, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction " + "a"*25 + " not found"`.

### PTS-D-09 — an empty tran_id is 404
- **Rules:** `get_transaction_by_tran_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id="", workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Payment transaction  not found"`.

### PTS-D-10 — 101 events are all returned, oldest first
- **Rules:** `get_transaction_by_tran_id` R4 (no cap), R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.
2. 101 events, inserted newest first: k = 100 … 0, ev(T, "note", `datetime(2026, 9, 1) + timedelta(minutes=k)`).

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.events) == 101`.
2. returns: `[e.created_at for e in result.events] == [datetime(2026, 9, 1) + timedelta(minutes=k) for k in range(101)]`.

### PTS-D-11 — BUG-1191: an event of W2 on W1's transaction is not listed
- **Rules:** `get_transaction_by_tran_id` R4a [BUG-1191]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 2 (the W2 event is listed)

**Given**
1. T.
2. E1 = ev(T, "initiated", `datetime(2026, 9, 27, 9, 0)`).
3. E2 = ev(T, "note", `datetime(2026, 9, 27, 9, 1)`), but `workspace_id W2.id`, `metadata_json {"secret": "w2"}`.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `[e.id for e in result.events] == [E1.id]`.

### PTS-D-12 — BUG-1191: an event of W0 on W1's transaction is not listed
- **Rules:** `get_transaction_by_tran_id` R4a [BUG-1191]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 2 (the W0 event is listed)

**Given**
1. T.
2. E0 = ev(T, "note", `datetime(2026, 9, 27, 8, 0)`), but `workspace_id W0.id`.
3. E1 = ev(T, "initiated", `datetime(2026, 9, 27, 9, 0)`).

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `[e.id for e in result.events] == [E1.id]`.

### PTS-D-13 — BUG-1190: the event read orders ties by id
- **Rules:** `get_transaction_by_tran_id` R5 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190
- **Fails today on:** Then 2 (the ORDER BY has no id)

**Given**
1. T.
2. ev(T, "a", `datetime(2026, 9, 27, 9, 0)`).

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`, with the **statement recorder**.

**Then**
1. returns: `len(result.events) == 1`.
2. returns: in the statement of `stmts` that selects from `payment_transaction_events`, the text after `ORDER BY` contains `"payment_transaction_events.id"`.

### PTS-D-14 — BUG-1190: tied events come back lower id first
- **Rules:** `get_transaction_by_tran_id` R5 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (physical order after the update can put E2 first)

**Given**
1. T.
2. E1 = ev(T, "a", `datetime(2026, 9, 27, 9, 0)`).
3. E2 = ev(T, "b", `datetime(2026, 9, 27, 9, 0)`).
4. Step: update E1 `description = "edited"`, flush.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.events) == 2`.
2. returns: `[e.id for e in result.events] == [E1.id, E2.id]`.

### PTS-D-15 — a read: no commit, no rollback, no lock, a pending edit stays (also on 404)
- **Rules:** `get_transaction_by_tran_id` R6; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. B = T but `tran_id B26`.
3. commit point.
4. in memory after the commit point (not flushed): `B.cus_name = "Pending Edit"`.

**When**
- `svc.get_transaction_by_tran_id(db, tran_id=Z26, workspace_id=W1.id)`, inside **spies**, with the **statement recorder**.

**Then**
1. raises: `exc.value.status_code == 404`.
2. mock called: `cm.call_count == 0`, `rb.call_count == 0`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`.
4. returns: no statement in `stmts` contains `"FOR UPDATE"`.

### PTS-D-16 — the detail read also succeeds without a lock
- **Rules:** `get_transaction_by_tran_id` R6; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. B = T but `tran_id B26`.
3. commit point.
4. in memory after the commit point (not flushed): `B.cus_name = "Pending Edit"`.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`, inside **spies**, with the **statement recorder**.

**Then**
1. returns: `result.id == T.id`.
2. mock called: `cm.call_count == 0`, `rb.call_count == 0`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`.
4. returns: no statement in `stmts` contains `"FOR UPDATE"`.

### PTS-D-17 — BUG-3022: the detail answer carries failed_reason and outcome_verified
- **Rules:** `get_transaction_by_tran_id` R1; `_to_response` R1a [BUG-3022] (`failed_reason` column from BUG-019, `outcome_verified` from BUG-026)
- **Kind:** bug
- **Expect:** xfail BUG-3022, BUG-019, BUG-026
- **Fails today on:** Then 2 (the response has no `failed_reason` field)

**Given**
1. T.

**When**
- `result = svc.get_transaction_by_tran_id(db, tran_id=A26, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `result.failed_reason is None`.
3. returns: `result.outcome_verified is False`.

## `PaymentTransactionService.list_transactions`

### PTS-L-01 — only W1's rows, every status, as responses with names
- **Rules:** `list_transactions` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = T but `workspace_id W0.id`, `tran_id "0"*26`, `initiated_by U3.id`.
2. A = T.
3. B = T but `tran_id B26`, `status "INIT_FAILED"`.
4. C = T but `tran_id C26`, `status "VALIDATED_SUCCESS"`, `initiated_by None`.
5. Z2 = T but `workspace_id W2.id`, `tran_id "9"*26`, `initiated_by U3.id`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: every item `isinstance(item, PaymentTransactionResponse)`.
2. returns: `{r.id for r in result} == {A.id, B.id, C.id}`.
3. returns: the item with `id == A.id` has `initiated_by_name == "Karim"`.
4. returns: the item with `id == C.id` has `initiated_by_name is None`.

### PTS-L-02 — a workspace with no rows gets []
- **Rules:** `list_transactions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T but `workspace_id W2.id`, `initiated_by U3.id`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PTS-L-03 — newest created_at first, even when ids rise the other way
- **Rules:** `list_transactions` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = T but `created_at datetime(2026, 9, 3)`.
2. B = T but `tran_id B26`, `created_at datetime(2026, 9, 1)`.
3. C = T but `tran_id C26`, `created_at datetime(2026, 9, 2)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `[r.id for r in result] == [A.id, C.id, B.id]`.

### PTS-L-04 — skip and limit page the ordered list
- **Rules:** `list_transactions` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows: k = 1 … 5, T but `tran_id str(k)*26`, `created_at datetime(2026, 9, k)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `[r.tran_id for r in result] == ["4"*26, "3"*26]`.

### PTS-L-05 — the default limit is 100
- **Rules:** `list_transactions` R2 (default `limit=100`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows: k = 0 … 100, T but `tran_id f"{k:026x}"`, `created_at datetime(2026, 9, 1) + timedelta(minutes=k)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].tran_id == f"{100:026x}"`.
3. returns: `f"{0:026x}" not in {r.tran_id for r in result}`.

### PTS-L-06 — limit=0 gives []
- **Rules:** `list_transactions` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PTS-L-07 — limit=1 gives the newest row only
- **Rules:** `list_transactions` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = T but `created_at datetime(2026, 9, 1)`.
2. B = T but `tran_id B26`, `created_at datetime(2026, 9, 2)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `[r.id for r in result] == [B.id]`.

### PTS-L-08 — the workspace filter runs before paging
- **Rules:** `list_transactions` R1, R2 (HR-5)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = T but `workspace_id W0.id`, `tran_id "0"*26`, `initiated_by U3.id`, `created_at datetime(2026, 9, 9)`.
2. A = T but `created_at datetime(2026, 9, 1)`.
3. B = T but `tran_id B26`, `created_at datetime(2026, 9, 2)`.
4. Z2 = T but `workspace_id W2.id`, `tran_id "9"*26`, `initiated_by U3.id`, `created_at datetime(2026, 9, 8)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### PTS-L-09 — a negative skip reaches the database as DataError, and the session is not rolled back
- **Rules:** `list_transactions` Errors (negative `skip`); R4; TC6
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. T.

**When**
- `svc.list_transactions(db, workspace_id=W1.id, skip=-1)`, inside **spies**, wrapped in `db.begin_nested()`.

**Then**
1. raises: `DataError`.
2. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

### PTS-L-10 — BUG-2402: the list orders ties by id descending
- **Rules:** `list_transactions` R2 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402
- **Fails today on:** Then 2 (the ORDER BY has no id)

**Given**
1. T.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`, with the **statement recorder**.

**Then**
1. returns: `len(result) == 1`.
2. returns: in the statement of `stmts` that selects from `payment_transactions`, the text after `ORDER BY` contains `"payment_transactions.id DESC"`.

### PTS-L-11 — BUG-2402: tied rows come back higher id first
- **Rules:** `list_transactions` R2 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (physical order can put A first)

**Given**
1. A = T but `created_at datetime(2026, 9, 1)`.
2. B = T but `tran_id B26`, `created_at datetime(2026, 9, 1)`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[r.id for r in result] == [B.id, A.id]`.

### PTS-L-12 — a read: no commit, no rollback, no lock, a pending edit stays
- **Rules:** `list_transactions` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T.
2. B = T but `tran_id B26`.
3. commit point.
4. in memory after the commit point (not flushed): `B.cus_name = "Pending Edit"`.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`, inside **spies**, with the **statement recorder**.

**Then**
1. returns: `len(result) == 2`.
2. mock called: `cm.call_count == 0`, `rb.call_count == 0`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`.
4. returns: no statement in `stmts` contains `"FOR UPDATE"`.

### PTS-L-13 — BUG-3022: list items carry failed_reason and outcome_verified
- **Rules:** `list_transactions` R1; `_to_response` R1a [BUG-3022] (`failed_reason` column from BUG-019, `outcome_verified` from BUG-026)
- **Kind:** bug
- **Expect:** xfail BUG-3022, BUG-019, BUG-026
- **Fails today on:** Then 2 (the item has no `failed_reason` field)

**Given**
1. T.

**When**
- `result = svc.list_transactions(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [T.id]`.
2. returns: `result[0].failed_reason is None`.
3. returns: `result[0].outcome_verified is False`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `initiate_payment` Inputs (`Idempotency-Key` 1–100 chars, empty or longer → 422) [BUG-3023] | `POST /payments/initiate/` | header bounds; header passed as `idempotency_key`; replay answers 201 |
| `initiate_payment` R7e race [BUG-3023] | integration (two sessions) | two concurrent calls with one new key: one attempt, the loser answers as replay or 409, never 500 |
| `handle_gateway_callback` R3, `handle_terminal_without_validation` R3 | integration (two sessions) | two concurrent callbacks: the row lock serialises them; one outcome, one `duplicate_ignored` |
| `resolve_risk` R2 (concurrent, after BUG-029) | integration (two sessions) | two concurrent resolves: one wins, the other gets 400 |
| `resolve_risk` Visibility (owner only, 403) | `POST /payments/{transaction_id}/resolve-risk/` | non-owner member gets 403 `Only the workspace owner can resolve a risk hold` |
| `list_transactions` bounds `skip ≥ 0`, `1 ≤ limit ≤ 200` | `GET /payments/` | 422 outside the bounds |
| IPN signature check | `/payments/ipn` | bad signature never reaches the service |
| Manager outcome rules (`finalize_from_gateway` R1–R7, `_apply_validation_result` R1–R12, `mark_terminal_without_validation` R1–R4, `resolve_risk` R1–R6a, `initiate_payment` R1–R10a) | `payment_transaction_manager.cases.md` | covered there; one pass-through per bug here |
| DAO order / filter (`list_by_workspace_with_initiator` R1–R7, event `get_by_payment_transaction` R1–R8) | `payment_transaction.cases.md`, `payment_transaction_event.cases.md` | covered there |
| BUG-3024 (frontend types for `failed_reason`, `outcome_verified`) | `frontend/src/types/payment.ts` | frontend |
| Payment-flow contract: side effects after a final outcome (none today) | future subscription portal | after-commit, once per transition, never on `duplicate_ignored` |

## Spec gaps
None open. Revision 1's six gaps were closed by the spec's Gap log (2026-11-21):

| # | Gap | Resolved by | Cards |
|---|---|---|---|
| 1 | Fingerprint column name, format, nullability | G1: `idempotency_fingerprint` `String(64)` NULL, lowercase SHA-256 hex, set with the key (R7a1) | IK-01, IK-02, IK-20, IK-26, IK-27, IK-36, IK-44, IK-45 |
| 2 | What "the same body" means | G2, G7: canonical JSON over the normalised body plus `profile_id`, worked example (R7c1) | IK-15, IK-32 … IK-39 |
| 3 | Name and lock of the key lookup | G3: `PaymentTransactionDAO.get_by_workspace_and_idempotency_key`, single-table, no lock; loser path R7e2 | IK-28 … IK-31, IK-42, IK-43 |
| 4 | Replay commit/rollback shape | G4, G7: 0 commits, 1 rollback, pending changes discarded (R7b1); 409 rolls back (R7c) | IK-03, IK-06 |
| 5 | Index name | G5: `ix_payment_transactions_workspace_idempotency_key`, exact `indexdef` (R7a1) | IK-25, IK-26 |
| 6 | `token_hex` patch target | G6: listed in Externals | I-07 |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_to_response` | R1 | TR-01, TR-02 |
| `_to_response` | R1a [BUG-3022] | TR-04, RR-11, L-13, D-17 |
| `_to_response` | R2 | TR-03 |
| `initiate_payment` | R1 | I-01, I-13 |
| `initiate_payment` | R2 | I-01, I-02 |
| `initiate_payment` | R3, R3a [BUG-019]; Errors row 1 | I-03, I-04, I-05 |
| `initiate_payment` | R4; Errors rows 2, 3 | I-06, I-07, I-08 |
| `initiate_payment` | R5 | I-09, I-10 |
| `initiate_payment` | R6 | I-01, I-09, I-10 |
| `initiate_payment` | R7 | I-12, IK-20, IK-27 |
| `initiate_payment` | R7a [BUG-3023] | IK-01, IK-02, IK-21 … IK-24 |
| `initiate_payment` | R7a1 [BUG-3023] | IK-01, IK-02, IK-20, IK-25 … IK-27, IK-36, IK-40, IK-44, IK-45 |
| `initiate_payment` | Inputs (key length, exact compare) [BUG-3023] | IK-21 … IK-24, IK-40, IK-41 |
| `initiate_payment` | R7b [BUG-3023] | IK-03, IK-04, IK-05, IK-30, IK-32 … IK-35, IK-38, IK-39 |
| `initiate_payment` | R7b1 [BUG-3023] | IK-03, IK-28, IK-30 |
| `initiate_payment` | R7c [BUG-3023]; Errors row 4 | IK-06 … IK-15, IK-37 |
| `initiate_payment` | R7c1 [BUG-3023] | IK-01, IK-15, IK-32 … IK-39, IK-45 (IK-36 = the worked example) |
| `initiate_payment` | R7d [BUG-3023] | IK-16 … IK-19, IK-27 |
| `initiate_payment` | R7e [BUG-3023] | IK-25 … IK-30 |
| `initiate_payment` | R7e1 [BUG-3023] | IK-30, IK-31 |
| `initiate_payment` | R7e2 [BUG-3023]; Errors rows "lost the race", "another constraint / re-read miss" | IK-28, IK-29, IK-42, IK-43, IK-46 |
| `initiate_payment` | R8; Errors row 5 | I-10, I-11 |
| `handle_gateway_callback` | R1 | GC-01, GC-02, GC-05, GC-12, GC-13 [BUG-023], GC-14 [BUG-026] |
| `handle_gateway_callback` | R2 (incl. `validated_at` kept) | GC-03, GC-04 |
| `handle_gateway_callback` | R3 | GC-11 |
| `handle_gateway_callback` | R4; Errors rows 1, 2 | GC-06, GC-07, GC-08, GC-15 |
| `handle_gateway_callback` | R5; Errors row 3 | GC-01, GC-03, GC-09, GC-16 |
| `handle_gateway_callback` | R6 | GC-10 |
| `handle_terminal_without_validation` | R1 | TW-01, TW-02, TW-03 [BUG-028], TW-04 [BUG-026] |
| `handle_terminal_without_validation` | R2 (incl. `validated_at` kept) | TW-05, TW-06 |
| `handle_terminal_without_validation` | R3 | TW-01, TW-12 |
| `handle_terminal_without_validation` | R4; Errors rows 1–3 | TW-07, TW-08, TW-09, TW-10, TW-11 |
| `resolve_risk` | R1 | RR-01, RR-02 |
| `resolve_risk` | R2; Errors row 2 | RR-03, RR-04 |
| `resolve_risk` | R2a [BUG-029] | RR-08 |
| `resolve_risk` | R3; Errors row 1 | RR-05, RR-06, RR-07 |
| `resolve_risk` | R4; Errors row 3 | RR-09, RR-10 |
| `get_transaction_by_tran_id` | R1 | D-01, D-02, D-17 |
| `get_transaction_by_tran_id` | R2; Errors row 1 | D-03, D-04, D-05 |
| `get_transaction_by_tran_id` | R3 | D-06, D-07, D-08, D-09 |
| `get_transaction_by_tran_id` | R4 | D-01, D-10 |
| `get_transaction_by_tran_id` | R4a [BUG-1191] | D-11, D-12 |
| `get_transaction_by_tran_id` | R5 [BUG-1190] | D-10, D-13, D-14 |
| `get_transaction_by_tran_id` | R6 | D-15, D-16 |
| `list_transactions` | R1 | L-01, L-02, L-08 |
| `list_transactions` | R2 [BUG-2402] | L-03 … L-08, L-10, L-11 |
| `list_transactions` | R3 | L-01 |
| `list_transactions` | R4; Errors | L-09, L-12 |
