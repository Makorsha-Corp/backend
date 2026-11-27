# Test cases — `app/dao/invoice_payment.py`

> **Spec:** `tests/unit/dao/invoice_payment.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; nothing open). P1 and Q1 were decided by Claude under the reviewer's delegation. No owner question (OQ-25 … OQ-28) touches this module, so there is no pending section.
> **Revision:** 2 (2026-11-10) — spec fill-gaps G1 (the modules of `Account` and `AccountInvoice` confirmed as assumed). Conventions now cite the spec Notes; spec gap 1 closed. Owner answers OQ-25 … OQ-28 touch no rule here, and none of the bugs tagged "revisit after launch" is in this module. No card added, changed or retired.
> **Counts:** 82 cases · 74 expected-to-pass · 8 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_invoice` 33 (4 bug) · `get_by_id_and_workspace_with_creator` 12 · `get_total_paid_for_invoice` 22 · inherited `create` (model facts) 15 (4 bug, one card per time zone and per stamp check).
- **Depth:** full. The total feeds the invoice's `paid_amount` when a payment is voided, so it is money; every amount is compared as an exact `Decimal`, with two decimals.
- **Expected-to-fail:** BUG-600 4 (IVP-GI-16, GI-17, GI-18 non-strict tie orders; GI-19 the strict `ORDER BY` alarm) · BUG-2400 4 (IVP-CR-07, CR-08 strict under `Asia/Dhaka` and `America/New_York`; CR-09, CR-10 the same for the row written through `dao.create` with a dict that carries no `created_at`). Note: CR-09, CR-10 repeat CR-07, CR-08 through the DAO instead of `db.add`; both paths reach the same default.
- **Notable design choices:**
  - HR-15 rounding is a model fact here (the column rounds on write; the DAO rounds nothing). IVP-CR-11 … CR-14 store `2.125`, `0.005`, `-1.005` (half-up and half-even differ) and the control `2.124`; IVP-TP-17 … TP-19 sum such stored values, so a total computed from unrounded input (or rounded half-even) fails.
  - Every workspace filter has a cross-workspace row on the **same invoice** in W0 (lower workspace id) and in W2 (higher); every invoice filter has payments on an invoice with a lower (NA) and a higher (NB) id.
  - Rows always go in with ids rising against the date order, so "newest date first" cannot pass by id order.
  - `get_by_invoice` R5 "the invoice is not checked" is pinned by a statement check (`account_invoices` not in the SQL): an invoice row cannot be removed while payments point at it.
  - Cards with 101 rows and the non-strict tie cards carry `Author: claude`. Race simulations: none (no rule about races; the manager holds the invoice lock).
- **Pending owner answers:** none in this module.
- **Needs a decision:** None. Gap 1 of revision 1 is closed by the spec's Gap log G1 (2026-11-10).

## Conventions for this module

**IDs.** `IVP` = `app/dao/invoice_payment.py`. `GI` get_by_invoice · `GC` get_by_id_and_workspace_with_creator · `TP` get_total_paid_for_invoice · `CR` inherited `create` and model facts.

**Actors and fixed values.**
- `dao` = the singleton `invoice_payment_dao` (`from app.dao.invoice_payment import invoice_payment_dao`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `InvoicePayment` = `app.models.invoice_payment.InvoicePayment`. `Account` = `app.models.account.Account`, `AccountInvoice` = `app.models.account_invoice.AccountInvoice` (spec Notes, G1). `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `select`, `text` = from `sqlalchemy`. `Decimal`, `date`, `datetime`, `timedelta`, `patch` = the usual ones. `utcnow` = `app.utils.time.utcnow`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, made once per test.
- D1 … D5 = `date(2026, 3, 1)` … `date(2026, 3, 5)`. T1 = `datetime(2026, 3, 6, 9, 0, 0)` (naive).

**Externals.** None. Nothing is mocked; no clock is patched.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`.
2. U1 = `make_profile(db, name="Rahim")`, U2 = `make_profile(db, name="Karim")`, U3 = `make_profile(db, name="Salma")`.
3. AC0, AC1, AC2 = `Account(workspace_id=Wn.id, name=f"Acme {TAG}")` for W0, W1, W2.
4. Invoices, `AccountInvoice(workspace_id=…, account_id=…, invoice_type="payable", invoice_amount=Decimal("100"), invoice_date=D1)`, in this order: N0 (W0, AC0), NA (W1, AC1), N1 (W1, AC1), NB (W1, AC1), N9 (W2, AC2). So `NA.id < N1.id < NB.id`.

**Given rows.** Inserted directly (never through `dao`, except in `CR` Whens), flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs. A line written as code is a step to run exactly as written.
- **payment** = `InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("10.00"), payment_date=D2, created_by=U1.id)`; every other column at its default (`is_voided False`, the void fields and the text fields `None`).
- **voided** = payment, but `is_voided True`, `voided_at T1`, `voided_by U2.id`, `void_note "Duplicate"` (a real void writes all four).
- **bump(X)** = `db.execute(text("UPDATE invoice_payments SET notes = 'x' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`; **NewYork** = the same with `'America/New_York'`. Run as the first Given step.

**Named checks.**
- **tids(result)** = `[r[0].id for r in result]`, order part of the check. **tidset(result)** = `{r[0].id for r in result}`. **names(result)** = `[r[1] for r in result]`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **nothing written** = the numbers of `invoice_payments` and `account_invoices` rows (all workspaces) equal their values before the call.
- Amounts are compared as `Decimal`: `result == Decimal("30.30")`; where a line also checks the scale it says `result.as_tuple().exponent == -2`.
- **close to now** = `abs(value - utcnow()) < timedelta(minutes=1)`, `utcnow()` read right after the When.
- `pending:` / `session:` lines check the session directly after the call, before anything expires it.
- `raises: E` (`IntegrityError` or `DataError`) = `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the When; keep using `db`. Later `raises:` lines assert on `exc.value.orig`, one per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; checks "inside the savepoint" first, then `sp.rollback()`, then the "after the rollback" checks.
- **Statement recorder** = the SQL the session sends during the When is recorded. `selects` = every `SELECT`; `sql` = the one `SELECT` from `invoice_payments`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT`/`OFFSET` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every `INSERT`, `UPDATE`, `DELETE`.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown; never weaken an assertion.

**Race simulations.** None in this module.

## `InvoicePaymentDAO.get_by_invoice`

### IVP-GI-01 — an invoice's payments come back as (payment, name) pairs, newest date first, voided included
- **Rules:** `get_by_invoice` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D1`.
2. P2 = payment, but `payment_date D3`.
3. P3 = voided, but `payment_date D2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P2.id, P3.id, P1.id]`.
2. returns: `names(result) == ["Rahim", "Rahim", "Rahim"]`.
3. returns: `type(result) is list`.

### IVP-GI-02 — each element is a plain 2-tuple of the payment and the name
- **Rules:** `get_by_invoice` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `type(result[0]) is tuple`.
3. returns: `len(result[0]) == 2`.
4. returns: `isinstance(result[0][0], InvoicePayment)`.
5. returns: `result[0][0].payment_amount == Decimal("10.00")`.
6. returns: `result[0][1] == "Rahim"`.

### IVP-GI-03 — a voided payment is listed with its void fields
- **Rules:** `get_by_invoice` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = voided.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.
2. returns: `result[0][0].is_voided is True`, `result[0][0].voided_at == T1`, `result[0][0].voided_by == U2.id`, `result[0][0].void_note == "Duplicate"`.

### IVP-GI-04 — payments of the invoices just below and just above are not listed
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PA = payment, but `invoice_id NA.id`, `payment_date D4`.
2. P1 = payment, but `payment_date D2`.
3. PB = payment, but `invoice_id NB.id`, `payment_date D5`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.

### IVP-GI-05 — a payment of the lower workspace W0 on this invoice is not listed
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = payment, but `workspace_id W0.id`, `payment_date D5` (invalid data: a W0 payment on W1's invoice).
2. P1 = payment, but `payment_date D2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.

### IVP-GI-06 — a payment of the higher workspace W2 on this invoice is not listed
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D2`.
2. X2 = payment, but `workspace_id W2.id`, `payment_date D5` (invalid data: a W2 payment on W1's invoice).

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.

### IVP-GI-07 — asked for W2, only W2's row on the invoice is listed, though W1's row is earlier
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D2`.
2. X2 = payment, but `workspace_id W2.id`, `payment_date D1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W2.id)`.

**Then**
1. returns: `tids(result) == [X2.id]`.

### IVP-GI-08 — an invoice without payments gives an empty list
- **Rules:** `get_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = payment, but `invoice_id NA.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IVP-GI-09 — an unknown invoice id gives an empty list
- **Rules:** `get_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IVP-GI-10 — invoice id 0 gives an empty list and raises nothing
- **Rules:** `get_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_invoice(db, invoice_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IVP-GI-11 — W2's invoice asked under W1 gives an empty list
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X9 = payment, but `workspace_id W2.id`, `invoice_id N9.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IVP-GI-12 — the name is each recorder's profile name, or None without a recorder
- **Rules:** `get_by_invoice` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D3`, `created_by U2.id`.
2. P2 = payment, but `payment_date D2`, `created_by None`.
3. P3 = payment, but `payment_date D1`, `created_by U3.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id, P2.id, P3.id]`.
2. returns: `names(result) == ["Karim", None, "Salma"]`.

### IVP-GI-13 — the name is the recorder's, not the voider's
- **Rules:** `get_by_invoice` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = voided, but `created_by U3.id` (voided by U2).

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.
2. returns: `names(result) == ["Salma"]`.

### IVP-GI-14 — newest date first, whatever the ids and amounts
- **Rules:** `get_by_invoice` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D1`, `payment_amount Decimal("90.00")`.
2. P2 = payment, but `payment_date D4`, `payment_amount Decimal("10.00")`.
3. P3 = payment, but `payment_date D2`, `payment_amount Decimal("50.00")`.
4. P4 = payment, but `payment_date D3`, `payment_amount Decimal("5.00")`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P2.id, P4.id, P3.id, P1.id]`.

### IVP-GI-15 — tied payments sit between the newer and the older one, each once
- **Rules:** `get_by_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO = payment, but `payment_date D1`.
2. PA = payment, but `payment_date D3`.
3. PN = payment, but `payment_date D5`.
4. PB = payment, but `payment_date D3`.
5. bump(PA).

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `tids(result)[0] == PN.id`.
3. returns: `tids(result)[3] == PO.id`.
4. returns: `set(tids(result)[1:3]) == {PA.id, PB.id}`.

### IVP-GI-16 — payments of one date: the highest id first, when the lowest id was updated
- **Rules:** `get_by_invoice` R3 [BUG-600]
- **Kind:** bug
- **Expect:** xfail BUG-600 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order among payments of one date; physical order puts the updated row last)

**Given**
1. P1 = payment, but `payment_date D2`.
2. P2 = payment, but `payment_date D2`.
3. P3 = payment, but `payment_date D2`.
4. P4 = payment, but `payment_date D2`.
5. bump(P1).

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `tids(result) == [P4.id, P3.id, P2.id, P1.id]`.

### IVP-GI-17 — payments of one date: the id decides, not amount, creator, method or void state
- **Rules:** `get_by_invoice` R3 [BUG-600]
- **Kind:** bug
- **Expect:** xfail BUG-600 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order among payments of one date)

**Given**
1. P1 = payment, but `payment_date D2`, `payment_amount Decimal("50.00")`, `created_by U2.id`, `payment_method "cash"`.
2. P2 = voided, but `payment_date D2`, `payment_amount Decimal("90.00")`, `created_by U3.id`, `payment_method "bank"`.
3. P3 = payment, but `payment_date D2`, `payment_amount Decimal("5.00")`, `payment_method "Card"`.
4. bump(P1).
5. bump(P3).

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `tids(result) == [P3.id, P2.id, P1.id]`.

### IVP-GI-18 — payments of one date paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_invoice` R3, R4 [BUG-600]
- **Kind:** bug
- **Expect:** xfail BUG-600 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order among payments of one date; a row can repeat and another be missed)

**Given**
1. P1 … P5 = five payments, each `payment_date D2`, inserted in that order.
2. bump(P1).
3. bump(P3).

**When**
- `pages = [dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0][0].id for p in pages] == [P5.id, P4.id, P3.id, P2.id, P1.id]`.

### IVP-GI-19 — the query orders by payment_date, then id, both descending
- **Rules:** `get_by_invoice` R3 [BUG-600]
- **Kind:** bug
- **Expect:** xfail BUG-600
- **Fails today on:** Then 4 (the query orders by `payment_date` alone)

**Given**
1. P1 = payment.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"payment_date" in order_part`.
4. statement: `"invoice_payments.id" in order_part`.
5. statement: `order_part.index("payment_date") < order_part.index("invoice_payments.id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### IVP-GI-20 — one statement, the creator joined with a LEFT OUTER JOIN
- **Rules:** `get_by_invoice` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D2`.
2. P2 = payment, but `payment_date D1`, `created_by None`.
3. `db.expire_all()`
4. Statement recorder.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`, then `n = names(result)` (reading the names sends nothing more).

**Then**
1. returns: `n == ["Rahim", None]`.
2. statement: `len(selects) == 1`.
3. statement: `"LEFT OUTER JOIN profiles" in sql`.

### IVP-GI-21 — no lock is taken
- **Rules:** `get_by_invoice` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.
2. statement: `"FOR UPDATE" not in sql`.
3. statement: `lock_part == ""`.

### IVP-GI-22 — the invoice row is not read: the query does not touch account_invoices
- **Rules:** `get_by_invoice` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [P1.id]`.
2. statement: `"account_invoices" not in sql`.
3. statement: `len(selects) == 1`.

### IVP-GI-23 — with the default limit, 101 payments give 100
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. 101 payments, built in a loop: payment `k` (k = 0 … 100) has `payment_date date(2026, 1, 1) + timedelta(days=k)`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0][0].payment_date == date(2026, 4, 11)`.
3. returns: `result[99][0].payment_date == date(2026, 1, 2)`.

### IVP-GI-24 — limit=1000 gives all 101
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. 101 payments, built in a loop: payment `k` (k = 0 … 100) has `payment_date date(2026, 1, 1) + timedelta(days=k)`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[100][0].payment_date == date(2026, 1, 1)`.

### IVP-GI-25 — skip=1, limit=2 gives the second and third by date
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D3`.
2. P2 = payment, but `payment_date D1`.
3. P3 = payment, but `payment_date D4`.
4. P4 = payment, but `payment_date D2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `tids(result) == [P1.id, P4.id]`.

### IVP-GI-26 — limit=0 gives an empty list
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### IVP-GI-27 — skip past the end gives an empty list
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D1`.
2. P2 = payment, but `payment_date D2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### IVP-GI-28 — skip=1 with two payments gives the older one
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D1`.
2. P2 = payment, but `payment_date D2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `tids(result) == [P1.id]`.

### IVP-GI-29 — a negative limit raises DataError
- **Rules:** `get_by_invoice` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### IVP-GI-30 — a negative skip raises DataError
- **Rules:** `get_by_invoice` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### IVP-GI-31 — the invoice filter comes before the page: a newer payment of another invoice takes no place
- **Rules:** `get_by_invoice` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D2`.
2. P2 = payment, but `payment_date D1`.
3. PB = payment, but `invoice_id NB.id`, `payment_date D5`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `tids(result) == [P2.id]`.

### IVP-GI-32 — the workspace filter comes before the page: a newer W2 payment on this invoice takes no place
- **Rules:** `get_by_invoice` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_date D2`.
2. P2 = payment, but `payment_date D1`.
3. X2 = payment, but `workspace_id W2.id`, `payment_date D5`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `tids(result) == [P2.id]`.

### IVP-GI-33 — writes nothing: a pending payment stays pending and is not listed, an unflushed edit stays unflushed
- **Rules:** `get_by_invoice` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = payment, but `payment_date D1`.
2. `B.notes = "Edited"` (not flushed).
3. `P = InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("7.00"), payment_date=D5, created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `tids(result) == [B.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.

## `InvoicePaymentDAO.get_by_id_and_workspace_with_creator`

### IVP-GC-01 — the workspace's payment comes back as a plain (payment, name) tuple
- **Rules:** `get_by_id_and_workspace_with_creator` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("12.34")`.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is tuple`.
2. returns: `len(result) == 2`.
3. returns: `result[0].id == P1.id`.
4. returns: `result[0].payment_amount == Decimal("12.34")`.
5. returns: `result[1] == "Rahim"`.

### IVP-GC-02 — the id itself decides: neighbours with lower and higher ids are not returned
- **Rules:** `get_by_id_and_workspace_with_creator` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = payment, but `created_by U2.id`.
2. P2 = payment, but `created_by U3.id`.
3. P3 = payment.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == P2.id`.
2. returns: `result[1] == "Salma"`.

### IVP-GC-03 — a voided payment is returned
- **Rules:** `get_by_id_and_workspace_with_creator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = voided.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == P1.id`.
2. returns: `result[0].is_voided is True`, `result[0].voided_by == U2.id`.
3. returns: `result[1] == "Rahim"`.

### IVP-GC-04 — a payment without a recorder comes back with name None
- **Rules:** `get_by_id_and_workspace_with_creator` R1 (name per `get_by_invoice` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `created_by None`.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result[0].id == P1.id`.
3. returns: `result[1] is None`.

### IVP-GC-05 — the name is the recorder's, not the voider's
- **Rules:** `get_by_id_and_workspace_with_creator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = voided, but `created_by U3.id` (voided by U2).

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[1] == "Salma"`.

### IVP-GC-06 — a payment of the lower workspace W0 asked under W1 gives None
- **Rules:** `get_by_id_and_workspace_with_creator` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = payment, but `workspace_id W0.id`, `invoice_id N0.id`.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### IVP-GC-07 — a payment of the higher workspace W2 asked under W1 gives None
- **Rules:** `get_by_id_and_workspace_with_creator` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = payment, but `workspace_id W2.id`, `invoice_id N9.id`.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### IVP-GC-08 — the same W2 payment asked under W2 is returned
- **Rules:** `get_by_id_and_workspace_with_creator` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = payment, but `workspace_id W2.id`, `invoice_id N9.id`.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=X2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result[0].id == X2.id`.
2. returns: `result[1] == "Rahim"`.

### IVP-GC-09 — an unknown id gives None
- **Rules:** `get_by_id_and_workspace_with_creator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### IVP-GC-10 — id 0 gives None and raises nothing
- **Rules:** `get_by_id_and_workspace_with_creator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### IVP-GC-11 — one statement with a LEFT OUTER JOIN of the creator, no lock
- **Rules:** `get_by_id_and_workspace_with_creator` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment.
2. `db.expire_all()`
3. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=P1.id, workspace_id=W1.id)`, then `n = result[1]`.

**Then**
1. returns: `n == "Rahim"`.
2. statement: `len(selects) == 1`.
3. statement: `"LEFT OUTER JOIN profiles" in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### IVP-GC-12 — writes nothing: a pending payment stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_id_and_workspace_with_creator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = payment.
2. `B.notes = "Edited"` (not flushed).
3. `P = InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("7.00"), payment_date=D5, created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace_with_creator(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == B.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `InvoicePaymentDAO.get_total_paid_for_invoice`

### IVP-TP-01 — active payments are summed, a voided one is left out
- **Rules:** `get_total_paid_for_invoice` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("10.10")`.
2. P2 = voided, but `payment_amount Decimal("5.00")`.
3. P3 = payment, but `payment_amount Decimal("20.20")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("30.30")`.
3. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-02 — no payment gives Decimal 0.00
- **Rules:** `get_total_paid_for_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = payment, but `invoice_id NA.id`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.
3. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-03 — every payment voided gives 0.00
- **Rules:** `get_total_paid_for_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = voided, but `payment_amount Decimal("40.00")`.
2. P2 = voided, but `payment_amount Decimal("60.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("0.00")`.
2. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-04 — one active payment next to a voided one counts alone
- **Rules:** `get_total_paid_for_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = voided, but `payment_amount Decimal("40.00")`.
2. P2 = payment, but `payment_amount Decimal("0.01")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("0.01")`.

### IVP-TP-05 — an unknown invoice gives 0.00
- **Rules:** `get_total_paid_for_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("0.00")`.
2. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-06 — invoice id 0 gives 0.00 and raises nothing
- **Rules:** `get_total_paid_for_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("0.00")`.

### IVP-TP-07 — a W2 payment of 1000.00 on this invoice is not counted for W1
- **Rules:** `get_total_paid_for_invoice` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("10.10")`.
2. P2 = payment, but `payment_amount Decimal("20.20")`.
3. X2 = payment, but `workspace_id W2.id`, `payment_amount Decimal("1000.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("30.30")`.

### IVP-TP-08 — a W0 payment of 1000.00 on this invoice is not counted for W1
- **Rules:** `get_total_paid_for_invoice` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = payment, but `workspace_id W0.id`, `payment_amount Decimal("1000.00")`.
2. P1 = payment, but `payment_amount Decimal("10.10")`.
3. P2 = payment, but `payment_amount Decimal("20.20")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("30.30")`.

### IVP-TP-09 — asked for W2, only W2's row on the invoice counts
- **Rules:** `get_total_paid_for_invoice` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("10.10")`.
2. X2 = payment, but `workspace_id W2.id`, `payment_amount Decimal("1000.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == Decimal("1000.00")`.

### IVP-TP-10 — payments of the invoices just below and just above are not counted
- **Rules:** `get_total_paid_for_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PA = payment, but `invoice_id NA.id`, `payment_amount Decimal("300.00")`.
2. P1 = payment, but `payment_amount Decimal("10.10")`.
3. PB = payment, but `invoice_id NB.id`, `payment_amount Decimal("500.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10.10")`.

### IVP-TP-11 — a single 0.00 payment gives Decimal 0.00
- **Rules:** `get_total_paid_for_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("0.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.
3. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-12 — 0.00 plus a stored -5.00 gives -5.00
- **Rules:** `get_total_paid_for_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("0.00")`.
2. P2 = payment, but `payment_amount Decimal("-5.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("-5.00")`.
2. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-13 — amounts that cancel to zero give 0.00
- **Rules:** `get_total_paid_for_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("7.25")`.
2. P2 = payment, but `payment_amount Decimal("-7.25")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("0.00")`.
2. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-14 — two rows of 9999999999999.99 give 19999999999999.98, not capped
- **Rules:** `get_total_paid_for_invoice` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("9999999999999.99")`.
2. P2 = payment, but `payment_amount Decimal("9999999999999.99")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("19999999999999.98")`.

### IVP-TP-15 — cents are summed exactly: three 0.10 give 0.30
- **Rules:** `get_total_paid_for_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1, P2, P3 = three payments, each `payment_amount Decimal("0.10")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.30")`.
3. returns: `str(result) == "0.30"`.

### IVP-TP-16 — an unflushed payment is not counted and stays pending
- **Rules:** `get_total_paid_for_invoice` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("10.00")`.
2. `P = InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("7.00"), payment_date=D2, created_by=U1.id)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10.00")`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.

### IVP-TP-17 — two stored 2.125 amounts (kept as 2.13) total 4.26, half up
- **Rules:** `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("2.125")`.
2. P2 = payment, but `payment_amount Decimal("2.125")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("4.26")`.
2. returns: `result.as_tuple().exponent == -2`.

### IVP-TP-18 — stored -1.005 and 0.005 (kept as -1.01 and 0.01) total -1.00
- **Rules:** `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("-1.005")`.
2. P2 = payment, but `payment_amount Decimal("0.005")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("-1.00")`.

### IVP-TP-19 — control: stored 2.124 twice (kept as 2.12) totals 4.24
- **Rules:** `get_total_paid_for_invoice` R4; model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("2.124")`.
2. P2 = payment, but `payment_amount Decimal("2.124")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("4.24")`.

### IVP-TP-20 — the stored value counts, not an unflushed edit of it
- **Rules:** `get_total_paid_for_invoice` R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("10.00")`.
2. `P1.payment_amount = Decimal("99.00")` (not flushed).

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10.00")`.
2. pending: `P1 in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `P1.payment_amount == Decimal("99.00")`.

### IVP-TP-21 — one SELECT, no lock, nothing written
- **Rules:** `get_total_paid_for_invoice` R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = payment.
2. Statement recorder.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10.00")`.
2. statement: `len(selects) == 1`.
3. statement: `"FOR UPDATE" not in sql`.
4. statement: `written == []`.

### IVP-TP-22 — the voided flag decides, not the void note or the voider
- **Rules:** `get_total_paid_for_invoice` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("8.00")`, `void_note "Checked twice"` (not voided: `is_voided False`).
2. P2 = voided, but `payment_amount Decimal("3.00")`.

**When**
- `result = dao.get_total_paid_for_invoice(db, invoice_id=N1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("8.00")`.

## Inherited `create` and model facts

### IVP-CR-01 — create from a dict stores the payment, not voided, void fields empty
- **Rules:** inherited `create` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `invoice_id == N1.id`, `payment_amount == Decimal("25.50")`, `payment_date == D3`, `created_by == U1.id`.
3. re-read result: `is_voided is False`, `voided_at is None`, `voided_by is None`, `void_note is None`.
4. re-read result: `payment_method is None`, `payment_reference is None`, `transaction_id is None`, `bank_name is None`, `notes is None`.

### IVP-CR-02 — created_at is filled and naive
- **Rules:** inherited `create` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at is not None`.
3. re-read result: `created_at.tzinfo is None`.

### IVP-CR-03 — flushed, not committed: a rollback removes the payment
- **Rules:** inherited `create` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no payment.
2. commit spy.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. count (inside the savepoint): `db.scalar(text("SELECT count(*) FROM invoice_payments WHERE id = :i"), {"i": result.id}) == 1`.
3. mock called: `cm.call_count == 0`.
4. count (after the rollback): `db.scalar(text("SELECT count(*) FROM invoice_payments WHERE id = :i"), {"i": result.id}) == 0`.

### IVP-CR-04 — an unknown invoice fails at flush with IntegrityError 23503
- **Rules:** inherited `create` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": MISSING, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IVP-CR-05 — an unknown workspace fails at flush with IntegrityError 23503
- **Rules:** inherited `create` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IVP-CR-06 — an unknown recorder fails at flush with IntegrityError 23503
- **Rules:** inherited `create` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": MISSING})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IVP-CR-07 — a new payment's created_at is naive UTC under Asia/Dhaka
- **Rules:** inherited `create` R1a [BUG-2400]
- **Kind:** bug
- **Expect:** xfail BUG-2400
- **Fails today on:** Then 2 (today `created_at` is the database's `now()` in Dhaka time, six hours ahead of UTC)

**Given**
1. Dhaka.
2. `A = InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("10.00"), payment_date=D2, created_by=U1.id)` (no `created_at`).

**When**
- `db.add(A); db.flush(); db.refresh(A)` (one step).

**Then**
1. re-read A: `A.created_at.tzinfo is None`.
2. re-read A: `A.created_at` is close to now.

### IVP-CR-08 — a new payment's created_at is naive UTC under America/New_York
- **Rules:** inherited `create` R1a [BUG-2400]
- **Kind:** bug
- **Expect:** xfail BUG-2400
- **Fails today on:** Then 2 (today `created_at` is New York time, four or five hours behind UTC)

**Given**
1. NewYork.
2. `A = InvoicePayment(workspace_id=W1.id, invoice_id=N1.id, payment_amount=Decimal("10.00"), payment_date=D2, created_by=U1.id)` (no `created_at`).

**When**
- `db.add(A); db.flush(); db.refresh(A)` (one step).

**Then**
1. re-read A: `A.created_at.tzinfo is None`.
2. re-read A: `A.created_at` is close to now.

### IVP-CR-09 — a payment created through the DAO gets naive UTC under Asia/Dhaka
- **Rules:** inherited `create` R1a [BUG-2400]
- **Kind:** bug
- **Expect:** xfail BUG-2400
- **Fails today on:** Then 3 (today `created_at` is Dhaka time, six hours ahead of UTC)

**Given**
1. Dhaka.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `created_at` is close to now.

### IVP-CR-10 — a payment created through the DAO gets naive UTC under America/New_York
- **Rules:** inherited `create` R1a [BUG-2400]
- **Kind:** bug
- **Expect:** xfail BUG-2400
- **Fails today on:** Then 3 (today `created_at` is New York time, hours behind UTC)

**Given**
1. NewYork.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("25.50"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `created_at` is close to now.

### IVP-CR-11 — 2.125 is stored as 2.13 (half up, not half even)
- **Rules:** model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("2.125"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payment_amount == Decimal("2.13")`.

### IVP-CR-12 — 0.005 is stored as 0.01
- **Rules:** model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("0.005"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payment_amount == Decimal("0.01")`.

### IVP-CR-13 — -1.005 is stored as -1.01 (away from zero)
- **Rules:** model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("-1.005"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payment_amount == Decimal("-1.01")`.

### IVP-CR-14 — control: 2.124 is stored as 2.12
- **Rules:** model facts `payment_amount` [HR-15]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("2.124"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payment_amount == Decimal("2.12")`.

### IVP-CR-15 — the database stores 0.00 and negative amounts (no check constraint)
- **Rules:** model facts `payment_amount`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = payment, but `payment_amount Decimal("0.00")`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "invoice_id": N1.id, "payment_amount": Decimal("-5.00"), "payment_date": D3, "created_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payment_amount == Decimal("-5.00")`.
3. re-read P1: `payment_amount == Decimal("0.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-600 at the list level | `InvoicePaymentManager.list_payments_by_invoice` R4 | the list shows payments of one date by id descending (the fix lands here; the manager card checks it end to end) |
| `paid_amount` / `payment_status` recomputed from the total | `InvoicePaymentManager.void_payment`, `create_payment` | the invoice row is locked (BUG-601) before the total is read; values half up |
| `payment_amount > 0`, ≤ 2 decimals, ≤ 13 integer digits (BUG-604) | `InvoicePaymentCreate` / `InvoicePaymentUpdate` (schema, manager spec) | 0, negative, 3 decimals and 14 integer digits refused with `ValidationError` |
| FU-2 `CHECK (payment_amount > 0)` | invoice payment schema / migration review | whether the database refuses 0.00 and negative rows |
| 404 `Payment with ID {payment_id} not found` | `InvoicePaymentService.get_payment`, `delete_payment` | the service answers 404 when this DAO returns `None` (FU-1) |
| `1 <= limit <= 1000` on the list endpoint (HR-7) | `GET` of an invoice's payments | 422 for `limit=0` and `limit=1001` |
| `get_by_date_range` removal (Q1) | `docs/testing/dead-code-removal-checklist.md` | dead code, no card |

## Spec gaps
None. Revision 1's gap 1 (modules of `Account` / `AccountInvoice`) is closed by spec Gap log G1 (2026-11-10).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| inherited `create` | R1 | IVP-CR-01, CR-02, CR-03, CR-04, CR-05, CR-06 |
| inherited `create` | R1a [BUG-2400] | IVP-CR-07, CR-08, CR-09, CR-10 |
| inherited `create` | Side effects (flushed, not committed) | IVP-CR-03 |
| model facts | `payment_amount` rounding half away from zero [HR-15] | IVP-CR-11, CR-12, CR-13, CR-14, TP-17, TP-18, TP-19 |
| model facts | `payment_amount` no check constraint | IVP-CR-15, TP-12 |
| `get_by_invoice` | R1 | IVP-GI-01, GI-03, GI-04, GI-05, GI-06, GI-07, GI-08, GI-09, GI-10, GI-11, GI-31, GI-32 |
| `get_by_invoice` | R2 | IVP-GI-01, GI-12, GI-13, GI-20 |
| `get_by_invoice` | R3 | IVP-GI-01, GI-14, GI-15 |
| `get_by_invoice` | R3 [BUG-600] | IVP-GI-16, GI-17, GI-18, GI-19 |
| `get_by_invoice` | R4 | IVP-GI-23, GI-24, GI-25, GI-26, GI-27, GI-28, GI-29, GI-30, GI-31, GI-32 |
| `get_by_invoice` | R5 | IVP-GI-20, GI-21, GI-22 |
| `get_by_invoice` | Returns (plain 2-tuples) | IVP-GI-02 |
| `get_by_invoice` | Errors: negative `limit` / `skip` | IVP-GI-29, GI-30 |
| `get_by_invoice` | Side effects: none | IVP-GI-33 |
| `get_by_id_and_workspace_with_creator` | R1 | IVP-GC-01, GC-02, GC-03, GC-04, GC-05, GC-08 |
| `get_by_id_and_workspace_with_creator` | R2 | IVP-GC-06, GC-07, GC-09, GC-10 |
| `get_by_id_and_workspace_with_creator` | R3 | IVP-GC-11 |
| `get_by_id_and_workspace_with_creator` | Side effects: none | IVP-GC-12 |
| `get_total_paid_for_invoice` | R1 | IVP-TP-01, TP-09, TP-10, TP-22 |
| `get_total_paid_for_invoice` | R2 | IVP-TP-01, TP-02, TP-03, TP-04, TP-05, TP-06, TP-22 |
| `get_total_paid_for_invoice` | R3 | IVP-TP-07, TP-08, TP-09 |
| `get_total_paid_for_invoice` | R4 | IVP-TP-11, TP-12, TP-13, TP-15, TP-17, TP-18, TP-19 |
| `get_total_paid_for_invoice` | R5 | IVP-TP-14 |
| `get_total_paid_for_invoice` | R6 | IVP-TP-16, TP-20, TP-21 |
| `get_total_paid_for_invoice` | Side effects: none | IVP-TP-20, TP-21 |
