# Test cases — `app/services/invoice_payment_service.py`

> **Spec:** `tests/unit/services/invoice_payment_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps (Gap log G1–G6) closed all six gaps. G1: K-05 is now a 409 card (another member reuses the key); the same-member replay was already K-04. G2: Conventions gain the fingerprint (FP / fp, `idempotency_fingerprint`); every keyed Given row stores its fingerprint; new K-34 (`400` = `400.00` → replay), K-35 (omitted notes = `"  "` → replay), K-36 (stored fingerprint = the literal SHA-256), K-37 (a notes edit does not change it); `"Cash"` vs `"cash"` → 409 is K-12; K-01, K-26 also check the fingerprint. G3: new K-38, K-39 (`""` is an ordinary key, stored and replayed), K-40 (101 characters → `DataError`, nothing saved), K-41 (100 characters stored, the other side), K-42 (`"ABC"` stored, `"abc"` sent → two payments). G4: K-04 … K-08 gain X and a commit spy (a replay rolls back, never commits); K-28 too. G5: C-03 and V-03 now use a completed expense order; their former linked-purchase-order checks moved to new C-16, V-13. G6: K-33 compares the full `indexdef`; K-27 also refuses an `OF` clause; new K-43 (replay on an invoice no longer confirmed), K-44, K-45 (key reused with an unknown / W2 invoice → 404), K-46 (an `IntegrityError` on another constraint is not translated) and its passing companion C-17. Race simulation now names `svc.invoice_payment_manager` (spec Notes). No ID retired.
> **Revision:** 3 (2026-11-22) — verifier feedback (`invoice_payment_service.verify.md`, Finding 1, case-missing): new IPS-G-08 pins `get_payment` R3 / TC6 on the found path (a commit there went unnoticed; G-07 covers only the 404). No other finding is routed to the case designer (the two surviving mutants are dead / bug-path). No card changed, no ID retired.
> **Counts:** 119 cases · 66 expected-to-pass · 53 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `to_payment_response` 4 · `_payment_response` 2 · `create_payment` 17 (2 bug) · `create_payment` idempotency R9–R9i 46 (41 bug) · `get_payment` 8 · `list_payments_by_invoice` 10 (1 bug) · `update_payment` 12 (4 bug) · `delete_payment` 7 (3 bug) · `void_payment` 13 (2 bug).
- **Depth:** full (money). TC1 (committed after a test-level rollback), TC2 (response built after commit, `created_at` set), TC3 (manager refusal passes unchanged, pending extra row X discarded, session usable), TC4, TC5 on every write that refreshes; TC6 on both reads. Manager rules are not re-tested; each manager / DAO bug reached gets one pass-through card.
- **Idempotency (BUG-3002), reference for the subscription portal:** key and fingerprint stored (K-01, K-36 literal SHA-256, K-37 not changed by an edit); different keys (K-02, K-03); replay, same member and same request: plain, invoice since paid with linked order, since locked, since voided payment, invoice no longer confirmed (K-04, K-06, K-07, K-08, K-43), each with a commit spy and a discarded pending row (a replay rolls back); a different member with the same key and body → 409 (K-05); normalisation: `400` = `400.00`, omitted notes = `"  "` → replay (K-34, K-35); one 409 card per body field, `"Cash"` ≠ `"cash"` (K-09 … K-16); key format: capitals, leading space, part, `_`, `"ABC"`/`"abc"`, `""`, 100 / 101 characters (K-17 … K-20, K-38 … K-42); per-workspace scope with W0 and W2 (K-21, K-22); key reused with an unknown / W2 invoice → 404 (K-44, K-45); no key (K-23 … K-26, three of them pass today and after the fix); plain lock before the key lookup (K-27); lost race on the index → replay / 409, never 500 (K-28, K-29), another constraint not translated (K-46); the unique index itself (K-30 … K-33). The real two-connection race is deferred to integration tests.
- **Notable design choices:**
  - A keyed Given row is built **without** the key and then gets `idempotency_key` and `idempotency_fingerprint` assigned as plain attributes before `db.add` (Conventions **keyed**). Today the attributes are ignored, so the Given runs and the xfail fails inside the When (TypeError on the new parameter); after the fix both are stored. Key and fingerprint are always read back with a column query (**col**), so a plain attribute left on the object can never pass a check.
  - Race simulation K-28 / K-29 patches `svc.invoice_payment_manager.create_payment` (spec Notes) with a function that inserts a second row with the same key and flushes — after the fix this is a real `IntegrityError` on `ix_invoice_payments_workspace_idempotency_key`, the post-race state R9e describes. The first keyed row is committed in the Given, so it survives the service's rollback.
  - K-36 uses explicit ids (profile 910001, invoice 920001) so the stored fingerprint can be compared with a literal hex value computed from the spec's R9f recipe.
  - D-07 (failing commit on delete) accepts `RuntimeError` (today) or the 400 (after BUG-609): both leave the payment in place, so it holds on both sides.
  - The BUG-2400 pass-through (C-15) expects `created_at == NOW` with `app.utils.time.datetime` frozen, per the bug register's intended `utcnow()` default.
  - C-03 / V-03 use a completed expense order (spec R7, gap 5). The expense-order model's import path is not in the spec; the executor takes it from the models package (`ExpenseOrder` with `workspace_id`, `invoice_id`, `completed_at`).
- **Needs a decision:** None. Gaps 1–6 of revision 1 are closed by the spec's Gap log (G1–G6).

## Conventions for this module

**IDs.** `IPS` = invoice_payment_service. `M` to_payment_response · `PR` _payment_response · `C` create_payment · `K` create_payment idempotency (R9–R9e) · `G` get_payment · `L` list_payments_by_invoice · `U` update_payment · `D` delete_payment · `V` void_payment. Full ID e.g. `IPS-K-09`.

**Imports.** `svc` = `invoice_payment_service`, and `to_payment_response`, from `app.services.invoice_payment_service`. Models `InvoicePayment`, `AccountInvoice`, `Account`, `FinancialAuditLog`, `InvoiceEvent`, `PurchaseOrder`, `PurchaseOrderEvent` (`app.models.*`). `InvoicePaymentCreate`, `InvoicePaymentUpdate`, `InvoicePaymentResponse` (`app.schemas.invoice_payment`). `HTTPException` (fastapi), `IntegrityError`, `DataError` (sqlalchemy.exc), `ValidationError` (pydantic), `patch` (unittest.mock), `text`, `select`, `func` (sqlalchemy). `db` = the test's real session, first argument; others by keyword. `result` = what the When returns.

**Standing rows** (every test, no Given line, in this order): W0, W1, W2 = `make_workspace(db)` ×3 (so `W0.id < W1.id < W2.id`); U1, U2 = `make_profile(db)` ×2 (U1 acts, U2 recorded the Given rows); A0, A1, A2 = `Account(workspace_id=Wn.id, name="Acme")` for W0, W1, W2.

**Time.** Every test freezes **NOW = `datetime(2026, 9, 27, 12, 0, 0)`** (naive) by patching `app.utils.time.datetime`, as the manager tests do. T0 = `datetime(2026, 9, 20, 9, 0, 0)`. MISSING = `999999999`.

**Given rows** (inserted directly, never through `svc`; flushed one at a time in the order written; after "but" a line names every column that differs):
- **INV(Wn)** = `AccountInvoice(workspace_id=Wn.id, account_id=An.id, invoice_type="payable", invoice_status="confirmed", invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0.00"), payment_status="unpaid", allow_payments=True, payment_locked_reason=None, order_type=None, order_id=None, invoice_date=date(2026, 9, 1))`; other required columns fixed valid values.
- **TW(I)** = the stored twin of BODY: `InvoicePayment(workspace_id=I.workspace_id, invoice_id=I.id, payment_amount=Decimal("400.00"), payment_date=date(2026, 9, 10), payment_method="cash", payment_reference="RCPT-77", bank_name="City Bank", transaction_id="TXN-9", notes="Advance", created_by=U2.id, is_voided=False)`.
- **voided** (after "but") = `is_voided True`, `voided_at T0`, `voided_by U2.id`, `void_note "Duplicate entry"`.
- **keyed K** (after "but") = after building the object and before `db.add`, run `P.idempotency_key = K` and `P.idempotency_fingerprint = FP(P)` (plain attribute assignments, never constructor keywords). The fingerprint is the one its recorder `P.created_by` would have sent.
- **EO1** = an expense order in W1 (`ExpenseOrder`, models package), `completed_at T0`, `invoice_id` as the card states; other required columns fixed valid values (unique number with a per-process suffix).
- **PO1** = a `PurchaseOrder` in W1 with `invoice_id` and `paid` as the card states; other required columns fixed valid values (unique `po_number` with a per-process suffix).
- **commit point** = after the last Given line, `db.commit()`. Snapshots for `unchanged` / `nothing written` are taken there.
- **X** (only where listed, after the commit point) = `Account(workspace_id=W1.id, name="Pending extra")`, flushed, not committed. **x_gone** = a fresh count of accounts named `"Pending extra"` is 0.

**Call values.** **BODY** = `InvoicePaymentCreate(invoice_id=I1.id, payment_amount=Decimal("400.00"), payment_date=date(2026, 9, 10), payment_method="cash", payment_reference="RCPT-77", bank_name="City Bank", transaction_id="TXN-9", notes="Advance")`. "BODY, but f v" = BODY with that one field changed. **KEY** = `"form-7f3a-0001"`.

**Fingerprint (spec R9f).** `n(v)` = `None` if `v` is `None` or `v.strip() == ""`, else `v.strip()`. **fp(uid, d)** = `hashlib.sha256(json.dumps({"profile_id": uid, "invoice_id": d.invoice_id, "payment_amount": format(Decimal(d.payment_amount).normalize(), "f"), "payment_date": d.payment_date.isoformat(), "payment_method": n(d.payment_method), "payment_reference": n(d.payment_reference), "bank_name": n(d.bank_name), "transaction_id": n(d.transaction_id), "notes": n(d.notes)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()`, for `d` a create body or a payment row. **FP(P)** = `fp(P.created_by, P)`. **col(P, c)** = `db.execute(select(getattr(InvoicePayment, c)).where(InvoicePayment.id == P.id)).scalar_one()` — a column query (raises today: the column does not exist). Imports `hashlib`, `json`. **upd(pid, data)** = `svc.update_payment(db, payment_id=pid, payment_in=data, workspace_id=W1.id, user_id=U1.id)` if `user_id` is in the method's signature, else the same call without `user_id` (test-side wrapper; holds today and after BUG-607).

**Named checks.**
- **re-read X** = `db.expire_all()`, then select X by id. **unchanged(I)** = after re-read, invoice I's `paid_amount`, `payment_status`, `invoice_status`, `allow_payments` equal the commit-point values. **unchanged(P)** = every column of payment P equals its commit-point value.
- **nothing written** = fresh counts of `invoice_payments`, `financial_audit_logs`, `invoice_events`, `purchase_order_events` (all workspaces) equal their commit-point values.
- **audit(P)** = `financial_audit_logs` rows with `entity_type == "payment"` and `entity_id == P.id`. **events(I)** = `invoice_events` rows with `invoice_id == I.id`.
- `committed:` lines: before the first, `db.rollback()` once; each line then queries fresh. `session:` lines run on `db` right after the call; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call, no savepoint; later lines check `exc.value`, one assert each.
- **spies** = `patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no rollback spy.
- **Statement recorder** = a `before_cursor_execute` listener on the test connection records every statement of the When, in order, into `stmts`. `lock_stmts` = those that select from `account_invoices` and contain `FOR UPDATE`.

**xfail.** Strict (`pytest.mark.xfail(strict=True, reason="BUG-n")`). Write calls with parameters that do not exist yet exactly as shown.

**Race simulations.** K-28, K-29 only (`create_payment` R9e, BUG-3002): `def dup(*a, **k):` builds TW(I1), but `created_by U1.id`, keyed KEY, then `db.add(row); db.flush()` (after the fix: `ix_invoice_payments_workspace_idempotency_key` raises `IntegrityError`). Active as `patch.object(svc.invoice_payment_manager, "create_payment", side_effect=dup)` around the When, inside the `raises:` wrap where there is one.

## `to_payment_response`

### IPS-M-01 — every column is copied and the name is the argument
- **Rules:** M1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = to_payment_response(P, created_by_name="Nadia Islam")`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`.
2. returns: `result.id == P.id`, `result.workspace_id == W1.id`, `result.invoice_id == I1.id`, `result.payment_amount == Decimal("400.00")`, `result.payment_date == date(2026, 9, 10)`.
3. returns: `result.payment_method == "cash"`, `result.payment_reference == "RCPT-77"`, `result.bank_name == "City Bank"`, `result.transaction_id == "TXN-9"`, `result.notes == "Advance"`.
4. returns: `result.is_voided is False`, `result.voided_at is None`, `result.voided_by is None`, `result.void_note is None`.
5. returns: `result.created_by == U2.id`, `result.created_at == P.created_at`, `result.created_at is not None`.
6. returns: `result.created_by_name == "Nadia Islam"`.

### IPS-M-02 — without a name the response has `created_by_name None`
- **Rules:** M1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P = TW(I1).

**When**
- `result = to_payment_response(P)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.created_by_name is None`.

### IPS-M-03 — a voided row carries its void fields
- **Rules:** M1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P = TW(I1), but voided.

**When**
- `result = to_payment_response(P, created_by_name="Nadia Islam")`.

**Then**
1. returns: `result.is_voided is True`, `result.voided_at == T0`, `result.voided_by == U2.id`, `result.void_note == "Duplicate entry"`.
2. returns: `result.payment_amount == Decimal("400.00")`.

### IPS-M-04 — a stored amount of 0.00 is refused by the response schema
- **Rules:** M2
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P = TW(I1); after the flush set `P.payment_amount = Decimal("0.00")` in memory only (no flush).

**When**
- `to_payment_response(P, created_by_name="x")`.

**Then**
1. raises: `ValidationError`.

## `InvoicePaymentService._payment_response`

### IPS-PR-01 — the response is the passed-in object with the recorder's name
- **Rules:** `_payment_response` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. After the commit point set `P.notes = "In memory"` (not flushed).

**When**
- `result = svc._payment_response(db, payment=P, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P.id`.
2. returns: `result.notes == "In memory"`.
3. returns: `result.created_by_name == U2.name`.

### IPS-PR-02 — the helper takes no lock and leaves the session clean
- **Rules:** `_payment_response` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. Statement recorder on.

**When**
- `result = svc._payment_response(db, payment=P, workspace_id=W1.id)`.

**Then**
1. returns: `result.created_by_name == U2.name`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. statement: no statement in `stmts` contains `"FOR UPDATE"`.
4. statement: no statement in `stmts` starts with `INSERT`, `UPDATE` or `DELETE`.

## `InvoicePaymentService.create_payment`

### IPS-C-01 — a payment is committed and the response is built after the commit
- **Rules:** `create_payment` R1, R2, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`.
2. returns: `result.id is not None`, `result.created_at is not None`.
3. returns: `result.created_by == U1.id`, `result.created_by_name == U1.name`, `result.is_voided is False`.
4. returns: `result.invoice_id == I1.id`, `result.payment_amount == Decimal("400.00")`, `result.payment_reference == "RCPT-77"`.
5. committed: the payment with `id == result.id` exists, `workspace_id == W1.id`, `payment_amount == Decimal("400.00")`, `notes == "Advance"`.
6. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.

### IPS-C-02 — the audit row and the invoice event are committed with the payment
- **Rules:** `create_payment` R1; TC1; R6 (default `None`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: audit(result) has exactly 1 row: `action_type == "created"`, `performed_by == U1.id`, `workspace_id == W1.id`.
3. committed: that audit row has `ip_address is None`, `user_agent is None`.
4. committed: events(I1) has exactly 1 row: `event_type == "payment_recorded"`, `performed_by == U1.id`.

### IPS-C-03 — a payment is recorded on the invoice of a completed order
- **Rules:** `create_payment` R7 (owner O1 / F7); TC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. EO1 with `invoice_id` NULL (set in line 3).
2. I1 = INV(W1), but `order_type "expense_order"`, `order_id EO1.id`.
3. `EO1.invoice_id = I1.id`, flushed.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`, `result.payment_amount == Decimal("400.00")`.
2. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.
3. committed: re-read EO1 `completed_at == T0`, `invoice_id == I1.id`.

### IPS-C-04 — an unknown invoice: the manager's 404 passes, everything pending is discarded
- **Rules:** `create_payment` R3, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Invoice with ID 999999999 not found"`.
4. session: usable.
5. nothing written: nothing written.
6. unchanged: unchanged(I1).
7. count: x_gone.

### IPS-C-05 — an invoice of W2 (built after W1) is not found
- **Rules:** `create_payment` R3 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2).

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id I2.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I2.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I2).

### IPS-C-06 — an invoice of W0 (built before W1) is not found
- **Rules:** `create_payment` R3 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0).
2. I1 = INV(W1).

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id I0.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I0.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I0).

### IPS-C-07 — a draft invoice: the manager's 400 passes unchanged
- **Rules:** `create_payment` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `invoice_status "draft"`.
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payments can only be recorded against confirmed invoices (current status: 'draft')."`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).
6. count: x_gone.

### IPS-C-08 — a locked invoice: the manager's 403 passes unchanged
- **Rules:** `create_payment` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `allow_payments False`, `payment_locked_reason "Awaiting credit approval"`.
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Awaiting credit approval"`.
4. nothing written: nothing written.
5. count: x_gone.

### IPS-C-09 — above what is owed: the manager's 400, nothing saved
- **Rules:** `create_payment` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 700.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `payment_amount 700.00`.
3. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payment amount (400.00) exceeds outstanding amount (300.00)"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).
6. count: x_gone.
7. session: usable.

### IPS-C-10 — a failing commit is rolled back and re-raised; nothing saved
- **Rules:** `create_payment` R4, Errors row 2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written: nothing written.
4. unchanged: unchanged(I1).

### IPS-C-11 — a failing re-read after the commit leaves the payment saved
- **Rules:** `create_payment` R4, Errors row 3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: I1 has exactly 1 `invoice_payments` row, `payment_amount == Decimal("400.00")`, `created_by == U1.id`.
3. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.

### IPS-C-12 — the invoice is locked with a plain `FOR UPDATE`
- **Rules:** `create_payment` R5 (manager R2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. Statement recorder on.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(lock_stmts) >= 1`.
3. statement: no statement in `lock_stmts` contains `"SKIP LOCKED"`.
4. statement: no statement in `lock_stmts` contains `"NOWAIT"`.

### IPS-C-13 — exactly one commit and no rollback on success
- **Rules:** `create_payment` R1, R8, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`, inside **spies**.

**Then**
1. returns: `result.id is not None`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.

### IPS-C-14 — pass-through BUG-603: IP and browser reach the audit row
- **Rules:** `create_payment` R6 [BUG-603]
- **Kind:** bug
- **Expect:** xfail BUG-603
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)")`.

**Then**
1. returns: `result.id is not None`.
2. committed: audit(result) has exactly 1 row, `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 (Test)"`.

### IPS-C-15 — pass-through BUG-2400: `created_at` is the app's UTC clock
- **Rules:** `create_payment` R2 [BUG-2400] (DAO)
- **Kind:** bug
- **Expect:** xfail BUG-2400
- **Fails today on:** Then 2 (`created_at` comes from the database clock, not the frozen NOW)

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.created_at is not None`.
2. returns: `result.created_at == NOW`.

### IPS-C-16 — the linked purchase order's `paid` change is committed too
- **Rules:** `create_payment` R1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 with `paid False` (its `invoice_id` set in line 3).
2. I1 = INV(W1), but `invoice_amount 400.00`, `order_type "purchase_order"`, `order_id PO1.id`.
3. `PO1.invoice_id = I1.id`, flushed.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.payment_amount == Decimal("400.00")`.
2. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "paid"`.
3. committed: re-read PO1 `paid is True`.
4. committed: `purchase_order_events` of PO1: exactly 1 row.

### IPS-C-17 — a database error at the write passes unchanged and nothing is saved
- **Rules:** `create_payment` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.
4. unchanged: unchanged(I1).
5. count: x_gone.
6. session: usable.

## `InvoicePaymentService.create_payment` — idempotency (R9–R9i, BUG-3002)

Every xfail card here fails today because `create_payment` has no `idempotency_key` parameter, unless its line says otherwise.

### IPS-K-01 — a key is stored on the new payment and committed
- **Rules:** `create_payment` R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. returns: `result.id is not None`, `result.created_by == U1.id`.
2. committed: `col(result, "idempotency_key") == "form-7f3a-0001"`.
3. committed: `col(result, "idempotency_fingerprint") == fp(U1.id, BODY)`.
4. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.

### IPS-K-02 — two different keys on one invoice make two payments
- **Rules:** `create_payment` R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but keyed `"form-a"`.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="form-b")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == "form-b"`.
4. committed: re-read I1 `paid_amount == Decimal("800.00")`, `payment_status == "partial"`.

### IPS-K-03 — a new key still obeys "never above what is owed"
- **Rules:** `create_payment` R9a [BUG-3002], R3
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError instead of the 400)

**Given**
1. I1 = INV(W1), but `paid_amount 800.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `payment_amount 800.00`, `created_by U1.id`, keyed `"form-a"`.

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="form-b")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payment amount (400.00) exceeds outstanding amount (200.00)"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-04 — same key, same request, same member: the first payment comes back, nothing committed
- **Rules:** `create_payment` R9b, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. X (after the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P1.id`.
2. returns: `result.payment_amount == Decimal("400.00")`, `result.payment_reference == "RCPT-77"`, `result.created_at == P1.created_at`.
3. returns: `result.created_by == U1.id`, `result.created_by_name == U1.name`, `result.is_voided is False`.
4. mock called: `cm.call_count == 0`.
5. count: x_gone.
6. count: I1 has exactly 1 `invoice_payments` row.
7. nothing written: nothing written.
8. unchanged: unchanged(I1).
9. unchanged: unchanged(P1).

### IPS-K-05 — another member sends the same key and body → 409, nothing written
- **Rules:** `create_payment` R9c, Errors row 4 [BUG-3002] (the key belongs to its first user)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but keyed KEY (recorded by U2, so its fingerprint is U2's).
3. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. count: I1 has exactly 1 `invoice_payments` row.
5. nothing written: nothing written.
6. unchanged: unchanged(I1).
7. unchanged: unchanged(P1).
8. count: x_gone.

### IPS-K-06 — the replay works after the invoice became fully paid; the linked order is not touched
- **Rules:** `create_payment` R9b, R9g (lookup before the checks), R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError; without the key it would be the 400 "exceeds outstanding")

**Given**
1. PO1 with `paid True` (its `invoice_id` set in line 4).
2. I1 = INV(W1), but `invoice_amount 400.00`, `paid_amount 400.00`, `payment_status "paid"`, `order_type "purchase_order"`, `order_id PO1.id`.
3. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
4. `PO1.invoice_id = I1.id`, flushed.
5. X (after the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`.
2. mock called: `cm.call_count == 0`.
3. count: x_gone.
4. count: I1 has exactly 1 `invoice_payments` row.
5. nothing written: nothing written.
6. re-read I1: `paid_amount == Decimal("400.00")`, `payment_status == "paid"`.
7. re-read PO1: `paid is True`.

### IPS-K-07 — the replay works after payments were locked on the invoice
- **Rules:** `create_payment` R9b, R9g, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError; without the key it would be the 403)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`, `allow_payments False`, `payment_locked_reason "Awaiting credit approval"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. X (after the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`.
2. mock called: `cm.call_count == 0`.
3. count: x_gone.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-08 — the replay of a payment voided since shows it voided and records nothing
- **Rules:** `create_payment` R9b, R9g (voided rows included), R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).
2. P1 = TW(I1), but `created_by U1.id`, voided, keyed KEY.
3. X (after the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`.
2. returns: `result.is_voided is True`, `result.void_note == "Duplicate entry"`, `result.voided_by == U2.id`.
3. mock called: `cm.call_count == 0`.
4. count: x_gone.
5. count: I1 has exactly 1 `invoice_payments` row.
6. nothing written: nothing written.
7. re-read I1: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### IPS-K-09 — same key, different `payment_amount` → 409, all pending work discarded
- **Rules:** `create_payment` R9c, Errors row 4 [BUG-3002]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, but payment_amount Decimal("400.01"), workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. count: I1 has exactly 1 `invoice_payments` row.
5. nothing written: nothing written.
6. unchanged: unchanged(I1).
7. count: x_gone.
8. session: usable.

### IPS-K-10 — same key, different `invoice_id` → 409, neither invoice changes
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. I1b = INV(W1).
3. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id I1b.id, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).
6. unchanged: unchanged(I1b).

### IPS-K-11 — same key, different `payment_date` → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but payment_date date(2026, 9, 11), workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-12 — same key, different `payment_method` → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but payment_method "Cash", workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-13 — same key, different `payment_reference` → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but payment_reference "RCPT-78", workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-14 — same key, different `bank_name` → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but bank_name "City Bank Ltd", workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-15 — same key, different `transaction_id` → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but transaction_id "TXN-10", workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-16 — same key, `notes` left out where the first had them → 409
- **Rules:** `create_payment` R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but notes None, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-17 — the key is case-sensitive: capitals are a new key
- **Rules:** `create_payment` Inputs `idempotency_key`, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="FORM-7F3A-0001")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == "FORM-7F3A-0001"`.
4. committed: re-read I1 `paid_amount == Decimal("800.00")`.

### IPS-K-18 — the key is not trimmed: a leading space is a new key
- **Rules:** `create_payment` Inputs `idempotency_key`, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=" form-7f3a-0001")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == " form-7f3a-0001"`.

### IPS-K-19 — a part of a stored key is a new key
- **Rules:** `create_payment` Inputs `idempotency_key`, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="7f3a")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == "7f3a"`.

### IPS-K-20 — `_` is literal: "form_7f3a-0001" is a new key
- **Rules:** `create_payment` Inputs `idempotency_key`, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="form_7f3a-0001")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == "form_7f3a-0001"`.

### IPS-K-21 — the same key in W0 (built before W1) is another key: a normal new payment
- **Rules:** `create_payment` R9d [BUG-3002] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I0 = INV(W0), but `paid_amount 400.00`, `payment_status "partial"`.
2. P0 = TW(I0), but keyed KEY.
3. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. returns: `result.id != P0.id`, `result.workspace_id == W1.id`, `result.invoice_id == I1.id`.
2. returns: `result.created_by == U1.id`.
3. committed: I1 has exactly 1 `invoice_payments` row.
4. committed: `col(result, "idempotency_key") == "form-7f3a-0001"`.
5. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.
6. unchanged: unchanged(P0).
7. unchanged: unchanged(I0).

### IPS-K-22 — the same key in W2 (built after W1) is another key: a normal new payment
- **Rules:** `create_payment` R9d [BUG-3002] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2), but `paid_amount 250.00`, `payment_status "partial"`.
3. P2 = TW(I2), but `payment_amount 250.00`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. returns: `result.id != P2.id`, `result.workspace_id == W1.id`, `result.payment_amount == Decimal("400.00")`.
2. committed: I1 has exactly 1 `invoice_payments` row.
3. committed: `col(result, "idempotency_key") == "form-7f3a-0001"`.
4. committed: re-read I1 `paid_amount == Decimal("400.00")`.
5. unchanged: unchanged(P2).
6. unchanged: unchanged(I2).

### IPS-K-23 — no key: the same body twice makes two payments (today's behaviour, kept)
- **Rules:** `create_payment` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: re-read I1 `paid_amount == Decimal("800.00")`, `payment_status == "partial"`.

### IPS-K-24 — no key: a second identical payment that no longer fits gets the manager's 400
- **Rules:** `create_payment` R9, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `invoice_amount 600.00`, `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payment amount (400.00) exceeds outstanding amount (200.00)"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-25 — no key is never blocked by a keyed payment with the same body
- **Rules:** `create_payment` R9, R9d (index over non-null keys only)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: re-read I1 `paid_amount == Decimal("800.00")`.

### IPS-K-26 — an explicit `idempotency_key=None` is "no key": a new payment with a NULL key and fingerprint
- **Rules:** `create_payment` R9, R9f (NULL iff no key), Inputs [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=None)`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") is None`.
4. committed: `col(result, "idempotency_fingerprint") is None`.

### IPS-K-27 — the key is looked up after the invoice lock, with a plain `FOR UPDATE`
- **Rules:** `create_payment` R9g, R9e, R5 [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).
2. Statement recorder on.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(lock_stmts) >= 1`.
3. statement: no statement in `lock_stmts` contains `"SKIP LOCKED"`.
4. statement: no statement in `lock_stmts` contains `"NOWAIT"`.
5. statement: no statement in `lock_stmts` contains `"FOR UPDATE OF"`.
6. statement: some statement in `stmts` selects from `invoice_payments` and contains `idempotency_key`, and its index in `stmts` is greater than the index of the first statement of `lock_stmts`.
7. statement: that key-lookup statement does not contain `"FOR UPDATE"`.

### IPS-K-28 — lost race on the index, same body: answered with the first payment, never 500
- **Rules:** `create_payment` R9e, R9b, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY (committed at the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, with the race simulation active, inside **spies** (no `raises:` wrap: the call must return).

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P1.id`.
2. mock called: `cm.call_count == 0`.
3. count: I1 has exactly 1 `invoice_payments` row.
4. unchanged: unchanged(I1).
5. session: usable.

### IPS-K-29 — lost race on the index, different body: 409, never 500
- **Rules:** `create_payment` R9e, R9c [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Author:** claude
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY (committed at the commit point).
3. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, but payment_amount Decimal("400.01"), workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This idempotency key was already used for a different payment"`.
4. count: I1 has exactly 1 `invoice_payments` row.
5. unchanged: unchanged(I1).
6. count: x_gone.
7. session: usable.

### IPS-K-30 — the database refuses a second row with the same key in one workspace
- **Rules:** `create_payment` R9d, R9e [BUG-3002] (target `database`)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (no error: there is no column or index, the flush succeeds)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. P2 = TW(I1), but `payment_amount 100.00`, keyed KEY — built and `db.add`ed, not flushed.

**When**
- `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.

### IPS-K-31 — two payments without a key never collide
- **Rules:** `create_payment` R9d (target `database`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P1 = TW(I1).
3. P2 = TW(I1), but `payment_amount 100.00` — `db.add`ed, not flushed.

**When**
- `db.flush()`.

**Then**
1. returns: `P2.id is not None`.
2. count: I1 has exactly 2 `invoice_payments` rows.

### IPS-K-32 — the same key in W1 and W2 does not collide
- **Rules:** `create_payment` R9d (target `database`)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2).
3. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
4. P2 = TW(I2), but keyed KEY — `db.add`ed, not flushed.

**When**
- `db.flush()`.

**Then**
1. returns: `P2.id is not None`.
2. count: `invoice_payments` rows of W2: exactly 1.

### IPS-K-33 — the index is exactly the partial unique index of R9g
- **Rules:** `create_payment` R9d, R9g [BUG-3002] (target `database`)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (no such index exists)

**Given**
1. Nothing beyond the standing rows.

**When**
- `defs = db.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_invoice_payments_workspace_idempotency_key'")).scalars().all()`.

**Then**
1. returns: `len(defs) == 1`.
2. returns: `defs[0] == "CREATE UNIQUE INDEX ix_invoice_payments_workspace_idempotency_key ON public.invoice_payments USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)"`.

### IPS-K-34 — `400` and `400.00` are the same request: replay
- **Rules:** `create_payment` R9f, R9b, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, but payment_amount Decimal("400"), workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`, `result.payment_amount == Decimal("400.00")`.
2. mock called: `cm.call_count == 0`.
3. count: I1 has exactly 1 `invoice_payments` row.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-35 — omitted notes and notes of spaces only are the same request: replay
- **Rules:** `create_payment` R9f, R9b, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `notes None`, `created_by U1.id`, keyed KEY.

**When**
- `result = svc.create_payment(db, payment_in=BODY, but notes "  ", workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`, `result.notes is None`.
2. mock called: `cm.call_count == 0`.
3. count: I1 has exactly 1 `invoice_payments` row.
4. nothing written: nothing written.

### IPS-K-36 — the stored fingerprint is the SHA-256 of the canonical request
- **Rules:** `create_payment` R9f, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. UF = `make_profile(db, id=910001)`.
2. IF = INV(W1), but `id 920001`.

**When**
- `result = svc.create_payment(db, payment_in=BODY, but invoice_id 920001, workspace_id=W1.id, user_id=910001, idempotency_key=KEY)`.

**Then**
1. returns: `result.invoice_id == 920001`, `result.created_by == 910001`.
2. committed: `col(result, "idempotency_fingerprint") == "1c1ff19a34151a4391d80de9b66a31ed5aa0442ea613439a825707398de6c7e1"` (the SHA-256 of `{"bank_name":"City Bank","invoice_id":920001,"notes":"Advance","payment_amount":"400","payment_date":"2026-09-10","payment_method":"cash","payment_reference":"RCPT-77","profile_id":910001,"transaction_id":"TXN-9"}`).
3. committed: `col(result, "idempotency_key") == "form-7f3a-0001"`.

### IPS-K-37 — a later notes edit does not change the stored fingerprint
- **Rules:** `create_payment` R9f [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 2 (the column query raises: `idempotency_fingerprint` does not exist)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `result = upd(P1.id, InvoicePaymentUpdate(notes="Edited later"))`.

**Then**
1. returns: `result.notes == "Edited later"`.
2. committed: `col(P1, "idempotency_fingerprint") == fp(U1.id, BODY)`.
3. committed: `col(P1, "idempotency_key") == "form-7f3a-0001"`.

### IPS-K-38 — called directly, `""` is an ordinary key and is stored
- **Rules:** `create_payment` R9i, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="")`.

**Then**
1. returns: `result.id is not None`.
2. committed: `col(result, "idempotency_key") == ""`.
3. committed: `col(result, "idempotency_fingerprint") == fp(U1.id, BODY)`.

### IPS-K-39 — called directly, `""` is replayed like any other key
- **Rules:** `create_payment` R9i, R9b, R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed `""`.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="")`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`.
2. mock called: `cm.call_count == 0`.
3. count: I1 has exactly 1 `invoice_payments` row.
4. nothing written: nothing written.

### IPS-K-40 — a 101-character key fails on the column: `DataError`, nothing saved
- **Rules:** `create_payment` R9i, Errors row 5 [BUG-3002]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="k" * 101)`.

**Then**
1. raises: `DataError` (`sqlalchemy.exc`).
2. nothing written: nothing written.
3. unchanged: unchanged(I1).
4. count: x_gone.
5. session: usable.

### IPS-K-41 — a 100-character key is stored whole
- **Rules:** `create_payment` R9i, R9g (`String(100)`) [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="k" * 100)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `col(result, "idempotency_key") == "k" * 100`.

### IPS-K-42 — `"ABC"` stored and `"abc"` sent are two keys: two payments
- **Rules:** `create_payment` R9i, R9a [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed `"ABC"`.

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key="abc")`.

**Then**
1. returns: `result.id != P1.id`.
2. committed: I1 has exactly 2 `invoice_payments` rows.
3. committed: `col(result, "idempotency_key") == "abc"`.
4. committed: re-read I1 `paid_amount == Decimal("800.00")`.

### IPS-K-43 — the replay works on an invoice that is no longer confirmed
- **Rules:** `create_payment` R9b, R9g (lookup before the checks), R9h [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError; without the key it would be the 400 "not confirmed")

**Given**
1. I1 = INV(W1), but `invoice_status "voided"`, `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. X (after the commit point).

**When**
- `result = svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`, inside **spies**.

**Then**
1. returns: `result.id == P1.id`.
2. mock called: `cm.call_count == 0`.
3. count: x_gone.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-K-44 — a key reused with an unknown `invoice_id` gets the 404, not 409
- **Rules:** `create_payment` R9g, R3 [BUG-3002]
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id MISSING, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Invoice with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(P1).

### IPS-K-45 — a key reused with another workspace's invoice gets the 404, not 409
- **Rules:** `create_payment` R9g, R3 [BUG-3002] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError: no `idempotency_key` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 = TW(I1), but `created_by U1.id`, keyed KEY.
3. I2 = INV(W2).

**When**
- `svc.create_payment(db, payment_in=BODY, but invoice_id I2.id, workspace_id=W1.id, user_id=U1.id, idempotency_key=KEY)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I2.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(I2).

### IPS-K-46 — with a key, an `IntegrityError` on another constraint is not translated
- **Rules:** `create_payment` R9e, R3 [BUG-3002]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3002
- **Fails today on:** Then 1 (the call raises TypeError instead of the `IntegrityError`)

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.create_payment(db, payment_in=BODY, workspace_id=W1.id, user_id=MISSING, idempotency_key=KEY)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.
4. count: x_gone.
5. session: usable.

## `InvoicePaymentService.get_payment`

### IPS-G-01 — a payment of the workspace with its recorder's name
- **Rules:** `get_payment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = svc.get_payment(db, payment_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P.id`.
2. returns: `result.payment_amount == Decimal("400.00")`, `result.notes == "Advance"`.
3. returns: `result.created_by == U2.id`, `result.created_by_name == U2.name`.

### IPS-G-02 — a voided payment is returned with its void fields
- **Rules:** `get_payment` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P = TW(I1), but voided.

**When**
- `result = svc.get_payment(db, payment_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.is_voided is True`, `result.voided_at == T0`, `result.voided_by == U2.id`, `result.void_note == "Duplicate entry"`.
3. returns: `result.created_by_name == U2.name`.

### IPS-G-03 — a payment with no recorder has `created_by_name None`
- **Rules:** `get_payment` Returns; `_payment_response` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1), but `created_by None`.

**When**
- `result = svc.get_payment(db, payment_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`, `result.created_by is None`.
2. returns: `result.created_by_name is None`.

### IPS-G-04 — an unknown id is a 404 raised by the service
- **Rules:** `get_payment` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `svc.get_payment(db, payment_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Payment with ID 999999999 not found"`.

### IPS-G-05 — a payment of W2 (built after W1) is not found
- **Rules:** `get_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P1 = TW(I1).
3. I2 = INV(W2).
4. P2 = TW(I2).

**When**
- `svc.get_payment(db, payment_id=P2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P2.id} not found"`.

### IPS-G-06 — a payment of W0 (built before W1) is not found
- **Rules:** `get_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0).
2. P0 = TW(I0).
3. I1 = INV(W1).
4. P1 = TW(I1).

**When**
- `svc.get_payment(db, payment_id=P0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P0.id} not found"`.

### IPS-G-07 — a read neither commits nor rolls back, also on the 404
- **Rules:** `get_payment` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.get_payment(db, payment_id=MISSING, workspace_id=W1.id)`, inside **spies**, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: accounts named `"Pending extra"`: exactly 1.

### IPS-G-08 — a found payment: no commit, no rollback, pending work stays pending
- **Rules:** `get_payment` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. After the commit point: `Y = Account(workspace_id=W1.id, name="Pending new")`, `db.add(Y)`, not flushed.
4. After the commit point: `A1.name = "Renamed"` (not flushed).

**When**
- `result = svc.get_payment(db, payment_id=P.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == P.id`, `result.created_by_name == U2.name`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Y in db.new`.
5. session: `A1 in db.dirty`.

## `InvoicePaymentService.list_payments_by_invoice`

### IPS-L-01 — the invoice's payments, newest date first, voided included, with names
- **Rules:** `list_payments_by_invoice` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 300.00`, `payment_status "partial"`.
2. I1b = INV(W1), but `paid_amount 50.00`, `payment_status "partial"`.
3. LA = TW(I1), but `payment_amount 100.00`, `payment_date date(2026, 9, 1)`, `created_by U1.id`.
4. LB = TW(I1), but `payment_amount 200.00`, `payment_date date(2026, 9, 5)`.
5. LC = TW(I1), but `payment_amount 300.00`, `payment_date date(2026, 9, 3)`, voided.
6. LX = TW(I1b), but `payment_amount 50.00`, `payment_date date(2026, 9, 4)`.

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`, every item an `InvoicePaymentResponse`.
2. returns: `[r.id for r in result] == [LB.id, LC.id, LA.id]`.
3. returns: `[r.created_by_name for r in result] == [U2.name, U2.name, U1.name]`.
4. returns: `result[1].is_voided is True`, `result[1].void_note == "Duplicate entry"`.

### IPS-L-02 — pass-through BUG-600: same date ties break by id descending
- **Rules:** `list_payments_by_invoice` R1 [BUG-600]
- **Kind:** bug
- **Expect:** xfail BUG-600
- **Author:** claude
- **Fails today on:** Then 2 (no id tie-breaker; order follows physical row order)

**Given**
1. I1 = INV(W1), but `paid_amount 300.00`, `payment_status "partial"`.
2. Three ids a < b < c reserved from the `invoice_payments` id sequence; TW(I1), but `payment_amount 100.00` and explicit `id`, inserted in the order c, a, b; all dated `date(2026, 9, 10)`.

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `[r.id for r in result] == [c, b, a]`.

### IPS-L-03 — an invoice with no payments gives `[]`
- **Rules:** `list_payments_by_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I1b = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
3. P = TW(I1b).

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`, `type(result) is list`.

### IPS-L-04 — an unknown invoice: the manager's 404 passes unchanged
- **Rules:** `list_payments_by_invoice` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).

**When**
- `svc.list_payments_by_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Invoice with ID 999999999 not found"`.

### IPS-L-05 — an invoice of W2 (built after W1) is not found
- **Rules:** `list_payments_by_invoice` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2), but `paid_amount 400.00`, `payment_status "partial"`.
3. P2 = TW(I2).

**When**
- `svc.list_payments_by_invoice(db, invoice_id=I2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I2.id} not found"`.

### IPS-L-06 — an invoice of W0 (built before W1) is not found
- **Rules:** `list_payments_by_invoice` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0), but `paid_amount 400.00`, `payment_status "partial"`.
2. P0 = TW(I0).
3. I1 = INV(W1).

**When**
- `svc.list_payments_by_invoice(db, invoice_id=I0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I0.id} not found"`.

### IPS-L-07 — `skip` and `limit` are passed on
- **Rules:** `list_payments_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P1 … P4 = TW(I1), but `payment_amount 100.00`, `payment_date date(2026, 9, k)` for k = 1, 2, 3, 4 (P1 oldest).

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `[r.id for r in result] == [P3.id, P2.id]`.

### IPS-L-08 — the default limit is 100
- **Rules:** `list_payments_by_invoice` R1 (signature default)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `invoice_amount 1000000.00`, `paid_amount 1010.00`, `payment_status "partial"`.
2. 101 rows by `add_all`: k = 1 … 101, TW(I1), but `payment_amount 10.00`, `payment_date date(2026, 1, 1) + timedelta(days=k)`.

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].payment_date == date(2026, 4, 12)`, `result[-1].payment_date == date(2026, 1, 3)`.

### IPS-L-09 — `limit=1000` returns all 101
- **Rules:** `list_payments_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `invoice_amount 1000000.00`, `paid_amount 1010.00`, `payment_status "partial"`.
2. 101 rows by `add_all`: k = 1 … 101, TW(I1), but `payment_amount 10.00`, `payment_date date(2026, 1, 1) + timedelta(days=k)`.

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### IPS-L-10 — a list neither commits nor rolls back
- **Rules:** `list_payments_by_invoice` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. X (after the commit point).

**When**
- `result = svc.list_payments_by_invoice(db, invoice_id=I1.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[r.id for r in result] == [P.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: accounts named `"Pending extra"`: exactly 1.

## `InvoicePaymentService.update_payment`

### IPS-U-01 — an edit is committed, the invoice is untouched, the recorder's name is shown
- **Rules:** `update_payment` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = upd(P.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P.id`.
2. returns: `result.payment_reference == "RCPT-99"`, `result.created_by_name == U2.name`, `result.created_at is not None`.
3. committed: re-read P `payment_reference == "RCPT-99"`, `payment_amount == Decimal("400.00")`, `notes == "Advance"`.
4. committed: re-read I1 `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.

### IPS-U-02 — an unknown id: the manager's 404 passes, pending work discarded
- **Rules:** `update_payment` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `upd(MISSING, InvoicePaymentUpdate(notes="x"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Payment with ID 999999999 not found"`.
4. count: x_gone.
5. session: usable.

### IPS-U-03 — a payment of W2 (built after W1) is not found
- **Rules:** `update_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2), but `paid_amount 400.00`, `payment_status "partial"`.
3. P2 = TW(I2).

**When**
- `upd(P2.id, InvoicePaymentUpdate(payment_reference="HACK"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P2.id} not found"`.
4. unchanged: unchanged(P2).

### IPS-U-04 — a payment of W0 (built before W1) is not found
- **Rules:** `update_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0), but `paid_amount 400.00`, `payment_status "partial"`.
2. P0 = TW(I0).
3. I1 = INV(W1).

**When**
- `upd(P0.id, InvoicePaymentUpdate(payment_reference="HACK"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P0.id} not found"`.
4. unchanged: unchanged(P0).

### IPS-U-05 — an amount change: the manager's 400 passes, nothing saved
- **Rules:** `update_payment` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. X (after the commit point).

**When**
- `upd(P.id, InvoicePaymentUpdate(payment_amount=Decimal("300.00"), notes="changed"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail.startswith("Cannot change payment amount.")`.
4. unchanged: unchanged(P).
5. unchanged: unchanged(I1).
6. count: x_gone.

### IPS-U-06 — pass-through BUG-611: the amount message says "Void and re-create"
- **Rules:** `update_payment` R2 [BUG-611]
- **Kind:** bug
- **Expect:** xfail BUG-611
- **Fails today on:** Then 3 (detail says "Delete and re-create payment instead.")

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `upd(P.id, InvoicePaymentUpdate(payment_amount=Decimal("300.00")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot change payment amount. Void and re-create payment instead."`.

### IPS-U-07 — pass-through BUG-606: a voided payment cannot be edited
- **Rules:** `update_payment` R2 [BUG-606]
- **Kind:** bug
- **Expect:** xfail BUG-606
- **Fails today on:** Then 1 (no error: the notes are changed)

**Given**
1. I1 = INV(W1).
2. P = TW(I1), but voided.
3. X (after the commit point).

**When**
- `upd(P.id, InvoicePaymentUpdate(notes="Edited after void"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Voided payments cannot be edited"`.
4. unchanged: unchanged(P).
5. count: x_gone.

### IPS-U-08 — pass-through BUG-608: sending `bank_name None` clears it
- **Rules:** `update_payment` R1 [BUG-608]
- **Kind:** bug
- **Expect:** xfail BUG-608
- **Fails today on:** Then 2 (`bank_name` is still "City Bank")

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = upd(P.id, InvoicePaymentUpdate(bank_name=None))`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P `bank_name is None`.
3. committed: re-read P `payment_reference == "RCPT-77"`, `notes == "Advance"`.

### IPS-U-09 — BUG-607: the editor is passed on and named on the committed audit row and event
- **Rules:** `update_payment` R4, R1 [BUG-607]
- **Kind:** bug
- **Expect:** xfail BUG-607
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = svc.update_payment(db, payment_id=P.id, payment_in=InvoicePaymentUpdate(payment_reference="RCPT-99"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.payment_reference == "RCPT-99"`.
2. committed: audit(P) has exactly 1 row, `action_type == "updated"`, `performed_by == U1.id`.
3. committed: events(I1) has exactly 1 row, `event_type == "payment_updated"`, `performed_by == U1.id`.

### IPS-U-10 — an empty update commits and returns the payment unchanged
- **Rules:** `update_payment` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = upd(P.id, InvoicePaymentUpdate())`, inside **spies**.

**Then**
1. returns: `result.id == P.id`, `result.payment_reference == "RCPT-77"`, `result.notes == "Advance"`.
2. mock called: `cm.call_count == 1`.
3. unchanged: unchanged(P).

### IPS-U-11 — a failing commit is rolled back and re-raised; the edit is not saved
- **Rules:** `update_payment` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `upd(P.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P: `payment_reference == "RCPT-77"`.

### IPS-U-12 — a failing re-read after the commit leaves the edit saved
- **Rules:** `update_payment` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `upd(P.id, InvoicePaymentUpdate(payment_reference="RCPT-99"))`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read P `payment_reference == "RCPT-99"`.

## `InvoicePaymentService.delete_payment`

### IPS-D-01 — an unknown id: the service's 404, rolled back, nothing written
- **Rules:** `delete_payment` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. X (after the commit point).

**When**
- `svc.delete_payment(db, payment_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Payment with ID 999999999 not found"`.
4. nothing written: nothing written.
5. count: x_gone.

### IPS-D-02 — a payment of W2 (built after W1) is not found and stays
- **Rules:** `delete_payment` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2), but `paid_amount 400.00`, `payment_status "partial"`.
3. P2 = TW(I2).

**When**
- `svc.delete_payment(db, payment_id=P2.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P2.id} not found"`.
4. unchanged: unchanged(P2).
5. unchanged: unchanged(I2).

### IPS-D-03 — a payment of W0 (built before W1) is not found and stays
- **Rules:** `delete_payment` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0), but `paid_amount 400.00`, `payment_status "partial"`.
2. P0 = TW(I0).
3. I1 = INV(W1).

**When**
- `svc.delete_payment(db, payment_id=P0.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P0.id} not found"`.
4. unchanged: unchanged(P0).
5. unchanged: unchanged(I0).

### IPS-D-04 — BUG-609: an active payment is never deleted; 400, all unchanged
- **Rules:** `delete_payment` R2, R3, Errors row 2 [BUG-609]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-609
- **Fails today on:** Then 1 (no error: the payment is removed and returned)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. X (after the commit point).

**When**
- `svc.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payments cannot be deleted — void them instead"`.
4. unchanged: unchanged(P).
5. unchanged: unchanged(I1).
6. nothing written: nothing written.
7. count: x_gone.

### IPS-D-05 — BUG-609: a voided payment is never deleted either
- **Rules:** `delete_payment` R2 [BUG-609]
- **Kind:** bug
- **Expect:** xfail BUG-609
- **Fails today on:** Then 1 (no error: the payment is removed)

**Given**
1. I1 = INV(W1).
2. P = TW(I1), but voided.

**When**
- `svc.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payments cannot be deleted — void them instead"`.
4. unchanged: unchanged(P).

### IPS-D-06 — BUG-609: the linked order keeps its `paid` flag
- **Rules:** `delete_payment` R2 [BUG-609]
- **Kind:** bug
- **Expect:** xfail BUG-609
- **Fails today on:** Then 1 (no error: the payment is removed and the order synced)

**Given**
1. PO1 with `paid True` (its `invoice_id` set in line 4).
2. I1 = INV(W1), but `invoice_amount 400.00`, `paid_amount 400.00`, `payment_status "paid"`, `order_type "purchase_order"`, `order_id PO1.id`.
3. P = TW(I1).
4. `PO1.invoice_id = I1.id`, flushed.

**When**
- `svc.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. re-read PO1: `paid is True`.
4. nothing written: nothing written.
5. unchanged: unchanged(I1).

### IPS-D-07 — a failing commit (today) or the refusal (after BUG-609): the payment stays either way
- **Rules:** `delete_payment` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `svc.delete_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id)`, inside `with pytest.raises((RuntimeError, HTTPException)) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")):`.

**Then**
1. raises: `isinstance(exc.value, (RuntimeError, HTTPException))`.
2. count: `invoice_payments` rows with `id == P.id`: exactly 1.
3. unchanged: unchanged(I1).

## `InvoicePaymentService.void_payment`

### IPS-V-01 — a void is committed; the response names the recorder, not the voider
- **Rules:** `void_payment` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. returns: `isinstance(result, InvoicePaymentResponse)`, `result.id == P.id`.
2. returns: `result.is_voided is True`, `result.voided_at == NOW`, `result.voided_by == U1.id`, `result.void_note == "Cheque bounced"`.
3. returns: `result.created_by == U2.id`, `result.created_by_name == U2.name`.
4. committed: re-read P `is_voided is True`, `voided_by == U1.id`, `void_note == "Cheque bounced"`.
5. committed: re-read I1 `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### IPS-V-02 — the void's audit row and invoice event are committed
- **Rules:** `void_payment` R1, R5 (default `None`); TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. returns: `result.is_voided is True`.
2. committed: audit(P) has exactly 1 row, `action_type == "voided"`, `performed_by == U1.id`.
3. committed: that audit row has `ip_address is None`, `user_agent is None`.
4. committed: events(I1) has exactly 1 row, `event_type == "payment_voided"`, `performed_by == U1.id`.

### IPS-V-03 — a payment on the invoice of a completed order can be voided
- **Rules:** `void_payment` R1 (owner O1 / F7); TC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. EO1 with `invoice_id` NULL (set in line 4).
2. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`, `order_type "expense_order"`, `order_id EO1.id`.
3. P = TW(I1).
4. `EO1.invoice_id = I1.id`, flushed.

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. returns: `result.is_voided is True`.
2. committed: re-read P `is_voided is True`.
3. committed: re-read I1 `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
4. committed: re-read EO1 `completed_at == T0`, `invoice_id == I1.id`.

### IPS-V-04 — an unknown id: the manager's 404 passes, pending work discarded
- **Rules:** `void_payment` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. X (after the commit point).

**When**
- `svc.void_payment(db, payment_id=MISSING, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Payment with ID 999999999 not found"`.
4. nothing written: nothing written.
5. count: x_gone.

### IPS-V-05 — a payment of W2 (built after W1) is not found
- **Rules:** `void_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. I2 = INV(W2), but `paid_amount 400.00`, `payment_status "partial"`.
3. P2 = TW(I2).

**When**
- `svc.void_payment(db, payment_id=P2.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P2.id} not found"`.
4. unchanged: unchanged(P2).
5. unchanged: unchanged(I2).

### IPS-V-06 — a payment of W0 (built before W1) is not found
- **Rules:** `void_payment` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I0 = INV(W0), but `paid_amount 400.00`, `payment_status "partial"`.
2. P0 = TW(I0).
3. I1 = INV(W1).

**When**
- `svc.void_payment(db, payment_id=P0.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Payment with ID {P0.id} not found"`.
4. unchanged: unchanged(P0).
5. unchanged: unchanged(I0).

### IPS-V-07 — a second void is a 400, not a replay, and writes nothing
- **Rules:** `void_payment` R2, R6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1).
2. P = TW(I1), but voided.
3. X (after the commit point).

**When**
- `svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Payment is already voided"`.
4. unchanged: unchanged(P).
5. nothing written: nothing written.
6. count: x_gone.

### IPS-V-08 — a payment pointing at a missing invoice: the manager's 404 passes
- **Rules:** `void_payment` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. I2 = INV(W2).
2. P = TW(I2), but `workspace_id W1.id` (invalid cross-workspace link, the only way to reach this row).

**When**
- `svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {I2.id} not found"`.
4. unchanged: unchanged(P).

### IPS-V-09 — a failing commit is rolled back; the payment stays active
- **Rules:** `void_payment` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(P).
4. unchanged: unchanged(I1).
5. nothing written: nothing written.

### IPS-V-10 — a failing re-read after the commit leaves the void saved
- **Rules:** `void_payment` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read P `is_voided is True`, `void_note == "Cheque bounced"`.
3. committed: re-read I1 `paid_amount == Decimal("0.00")`.

### IPS-V-11 — pass-through BUG-601: the void locks the invoice with a plain `FOR UPDATE`
- **Rules:** `void_payment` R4 [BUG-601]
- **Kind:** bug
- **Expect:** xfail BUG-601
- **Fails today on:** Then 2 (no invoice statement contains `FOR UPDATE`)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).
3. Statement recorder on.

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. returns: `result.is_voided is True`.
2. statement: `len(lock_stmts) >= 1`.
3. statement: no statement in `lock_stmts` contains `"SKIP LOCKED"`.
4. statement: no statement in `lock_stmts` contains `"NOWAIT"`.

### IPS-V-12 — BUG-603: IP and browser reach the void's audit row
- **Rules:** `void_payment` R5 [BUG-603]
- **Kind:** bug
- **Expect:** xfail BUG-603
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I1 = INV(W1), but `paid_amount 400.00`, `payment_status "partial"`.
2. P = TW(I1).

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced", ip_address="203.0.113.7", user_agent="Mozilla/5.0 (Test)")`.

**Then**
1. returns: `result.is_voided is True`.
2. committed: audit(P) has exactly 1 row, `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 (Test)"`.

### IPS-V-13 — the linked purchase order's `paid` change is committed
- **Rules:** `void_payment` R1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 with `paid True` (its `invoice_id` set in line 4).
2. I1 = INV(W1), but `invoice_amount 400.00`, `paid_amount 400.00`, `payment_status "paid"`, `order_type "purchase_order"`, `order_id PO1.id`.
3. P = TW(I1).
4. `PO1.invoice_id = I1.id`, flushed.

**When**
- `result = svc.void_payment(db, payment_id=P.id, workspace_id=W1.id, user_id=U1.id, void_note="Cheque bounced")`.

**Then**
1. returns: `result.is_voided is True`.
2. committed: re-read PO1 `paid is False`.
3. committed: re-read I1 `payment_status == "unpaid"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_payment` R5, R9e; `void_payment` R4 (real race) | integration tests | two committed connections on one invoice: the second waits and sees the new `paid_amount` / voided state; two concurrent same-key POSTs leave exactly one payment and neither answers 500 |
| `create_payment` R9i (header `min_length=1, max_length=100`) [BUG-3002] | `POST /invoice-payments/` (integration) | `Idempotency-Key` read from the header; an empty or 101-character header → 422 before the service runs; a replay answers 201 with the first payment's body |
| `create_payment` R6, `void_payment` R5 [BUG-603] | endpoints | the request's client IP and user agent are passed to the service |
| `update_payment` R4 [BUG-607] | `PUT /invoice-payments/{id}/` | the endpoint passes `current_user.id` |
| `delete_payment` R2 [BUG-609] | `DELETE /invoice-payments/{id}/` | answers 400 with the detail, nothing committed |
| `void_payment` Inputs [BUG-605] | `VoidPaymentRequest` / void endpoint | blank note → 422, padded note trimmed (manager cases VP-20, VP-21) |
| `create_payment` / `update_payment` Inputs [BUG-604] | schemas / endpoints | amount precision (manager cases CP-26 … CP-29, UP-21) |
| `list_payments_by_invoice` limit bounds | list endpoint | `limit` < 1 or > 1000 → 422 |

## Spec gaps
None open. The six gaps of revision 1 were closed by the spec's Gap log (fill-gaps 2026-11-21):

| # | Resolution (spec) | Cards |
|---|---|---|
| 1 | G1: the caller's profile id is part of the request; another member reusing a key → 409 (R9b, R9c; one rule with BUG-3023). | K-05 rewritten to a 409 card; same-member replay is K-04 (and every replay card now has the row recorded by the caller). |
| 2 | G2: fingerprint R9f (SHA-256 of canonical JSON over `profile_id` + normalised body; `idempotency_fingerprint` `String(64)`, NULL iff no key). | K-34, K-35, K-36 (literal hash), K-37; K-12 is `"Cash"` vs `"cash"` → 409; K-01, K-26 check the fingerprint. |
| 3 | G3: R9i — the endpoint enforces 1–100 (integration); the service treats `""` as a key and a 101-character key fails with `DataError`. | K-38, K-39, K-40, K-41, K-42; the header check stays Deferred. |
| 4 | G4: R9h — a replay commits nothing and rolls back (pending changes discarded). | K-04, K-06, K-07, K-08, K-28, K-34, K-35, K-39, K-43 use the commit spy; the K-04 … K-08 replays also discard X. |
| 5 | G5: "completed" per kind (R7); an expense order with `completed_at` set is enough. | C-03, V-03 now use EO1; the purchase-order sync checks moved to C-16, V-13. |
| 6 | G6: manager attribute `self.invoice_payment_manager`; index name and `indexdef` (R9g); lookup after the plain lock, before R3–R5. | Race simulation, K-33 (full `indexdef`), K-27 (no `OF`), K-43, K-44, K-45. |

Two small facts the executor confirms without a spec change: the `ExpenseOrder` import path (C-03, V-03), and that an unknown `user_id` fails on a foreign key of the payment or audit row with `pgcode 23503` (C-17, K-46; the spec states R9e's "other constraint" rule but names no such constraint). If either does not hold, route it back as a gap.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `to_payment_response` | M1 | M-01, M-02, M-03 |
| `to_payment_response` | M2 | M-04 |
| `_payment_response` | R1 | PR-01, G-03, V-01, U-01 |
| `_payment_response` | R2 | none — Q1 (intended, unreachable, no case) |
| `_payment_response` | R3 | PR-02 |
| `create_payment` | R1 | C-01, C-02, C-16 |
| `create_payment` | R2 | C-01, C-15 |
| `create_payment` | R3 / Errors row 1 | C-04, C-05, C-06, C-07, C-08, C-09, C-17 |
| `create_payment` | R4 / Errors rows 2, 3 | C-10, C-11 |
| `create_payment` | R5 | C-12 (race: Deferred) |
| `create_payment` | R6 [BUG-603] | C-02 (default None), C-14 |
| `create_payment` | R7 | C-03 |
| `create_payment` | R8 | C-13 |
| `create_payment` | R9 | K-23, K-24, K-25, K-26 |
| `create_payment` | R9a [BUG-3002] | K-01, K-02, K-03, K-17, K-18, K-19, K-20, K-36, K-38, K-42 |
| `create_payment` | R9b [BUG-3002] | K-04, K-06, K-07, K-08, K-34, K-35, K-39, K-43 |
| `create_payment` | R9c / Errors row 4 [BUG-3002] | K-05 (another member), K-09 … K-16 |
| `create_payment` | R9d [BUG-3002] | K-21, K-22, K-25, K-30, K-31, K-32, K-33 |
| `create_payment` | R9e [BUG-3002] | K-27, K-28, K-29, K-30, K-46 (real race: Deferred) |
| `create_payment` | R9f [BUG-3002] | K-01, K-26, K-34, K-35, K-36, K-37, K-38 |
| `create_payment` | R9g [BUG-3002] | K-06, K-07, K-08, K-27, K-33, K-41, K-43, K-44, K-45 |
| `create_payment` | R9h [BUG-3002] | K-04, K-06, K-07, K-08, K-28, K-34, K-35, K-39, K-43 |
| `create_payment` | R9i / Errors row 5 [BUG-3002] | K-17 … K-20, K-38, K-39, K-40, K-41, K-42 (header: Deferred) |
| `create_payment` | [BUG-2400] pass-through | C-15 |
| `get_payment` | R1 | G-01, G-02, G-03 |
| `get_payment` | R2 / Errors row 1 | G-04, G-05, G-06 |
| `get_payment` | R3 | G-07 (404 path), G-08 (found path) |
| `list_payments_by_invoice` | R1 | L-01, L-05, L-06, L-07, L-08, L-09 |
| `list_payments_by_invoice` | R1 [BUG-600] | L-02 |
| `list_payments_by_invoice` | R2 | L-03 |
| `list_payments_by_invoice` | R3 / Errors | L-04, L-10 |
| `update_payment` | R1 | U-01 |
| `update_payment` | R1 [BUG-608] | U-08 |
| `update_payment` | R2 | U-02, U-03, U-04, U-05 |
| `update_payment` | R2 [BUG-611] | U-06 |
| `update_payment` | R2 [BUG-606] | U-07 |
| `update_payment` | R3 | U-11, U-12 |
| `update_payment` | R4 [BUG-607] | U-09 |
| `update_payment` | R5 | U-10 |
| `delete_payment` | R1 / Errors row 1 | D-01, D-02, D-03 |
| `delete_payment` | R2 / Errors row 2 [BUG-609] | D-04, D-05, D-06 |
| `delete_payment` | R3 [BUG-609] | D-04 |
| `delete_payment` | R4 | D-07 |
| `void_payment` | R1 | V-01, V-02, V-03 (completed order), V-13 |
| `void_payment` | R2 | V-04, V-05, V-06, V-07, V-08 |
| `void_payment` | R3 | V-09, V-10 |
| `void_payment` | R4 [BUG-601] | V-11 (race: Deferred) |
| `void_payment` | R5 [BUG-603] | V-02 (default None), V-12 |
| `void_payment` | R6 | V-07 |
| `void_payment` | R7 | no external exists; V-01 commits only database work |
