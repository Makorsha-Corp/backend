# Test cases — `app/dao/payment_transaction_event.py`

> **Spec:** `tests/unit/dao/payment_transaction_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-01; nothing open). Q1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. From `payment_transaction_event.verify.md` (case-missing Findings 1 … 5; recipes R-1 … R-5), additive but for one line: R-1 → PTE-G-20; R-2 → PTE-G-21; R-3 → PTE-G-19 Then 5, 6 (the old lines 5 … 7 move to 7 … 9) and PTE-G-22; R-4 → PTE-G-10 Then 3, replaced; R-5 → PTE-G-23. Spec gaps 3 and 4 settled. No ID retired.
> **Counts:** 23 cases · 15 expected-to-pass · 8 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a): one list read, no write of its own, and no money, stock or order state written.
- **Per callable:** `get_by_payment_transaction` 23 (8 bug).
- **Expected-to-fail:** BUG-1191 4: PTE-G-03 … G-06, each fails today on the missing parameter. BUG-1190 4: PTE-G-13, G-14, G-20 non-strict (the order itself), PTE-G-15 strict (the SQL recorder, the alarm that goes off when the bug is fixed). PTE-G-12 is the passing companion: both tied rows come back, after the older row.
- **Notable design choices:**
  - "Writes nothing" is PTE-G-19, with PTE-G-22 for the empty result: a newer row added and not flushed must stay pending and alone in the session, no write statement is sent, and no lock clause. Readers have no commit spy.
  - Ties both ways: PTE-G-13 updates the lower row, so the expected row is physically last; PTE-G-14 updates nothing, so it is physically first. Neither alone rules out physical order.
  - Oldest first is Q1, decided by Claude under the reviewer's delegation.
  - PTE-G-20 and G-23 give each row its own `event_type`, `description` and performer, so no other column can pass for `id` or `created_at`. G-21 has an older row with a higher id, one microsecond apart.
  - PTE-G-10 now forbids the parent table by name, so a subquery cannot hide a transaction's log.
  - The pass cards use today's call with no `workspace_id`, as the spec's Notes ask. See Spec gap 5.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. Spec gaps 5, 6 touch money.

## Conventions for this module

**IDs.** `PTE` = `app/dao/payment_transaction_event.py`. `G` = get_by_payment_transaction.

**Actors and fixed values.**
- `dao` = the singleton `payment_transaction_event_dao` (`from app.dao.payment_transaction_event import payment_transaction_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `PaymentTransactionEvent` = `app.models.payment_transaction_event.PaymentTransactionEvent`. `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`, `Decimal` = `decimal.Decimal`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile` of `tests/unit/factories.py`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - TX1 = `payment_transactions` row (`PaymentTransaction`): `workspace_id W1.id`, `tran_id "TXN-1"`, `amount Decimal("100.00")`, `currency "BDT"`. TX2 = the same, but `tran_id "TXN-2"`. TX9 = the same as TX1, but `workspace_id W2.id`, `tran_id "TXN-9"`.
- **event** = `payment_transaction_events` row built with `PaymentTransactionEvent`: `workspace_id W1.id`, `payment_transaction_id TX1.id`, `event_type "initiated"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with the value `None`.
- No `payment_transaction_events` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `payment_transaction_events` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **stored_json(X)** = `db.scalar(text("SELECT metadata_json::text FROM payment_transaction_events WHERE id = :i"), {"i": X.id})` — `None` for SQL `NULL`, `"null"` for JSON `null`.
- `pending:` lines check the row P after the call, on the object itself; `db.new`, `db.dirty`, `db.deleted` are read from the session after the call, before anything expires it.
- `raises: TypeError` = wrap the call: `with pytest.raises(TypeError) as exc:`. Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")` with the bug of the card's Expect line, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Today's call.** The bug is BUG-1191: today the method has no `workspace_id`. Only the BUG-1191 cards pass it. Every other card uses today's call, exactly as written.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `payment_transaction_events`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `PaymentTransactionEventDAO.get_by_payment_transaction`

### PTE-G-01 — returns a list of the payment transaction's rows of every event type
- **Rules:** `get_by_payment_transaction` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "initiated"`.
2. B = event, `created_at T2`, but `event_type "ipn_received"`.
3. C = event, `created_at T3`, but `event_type "validated_success"`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.
3. returns: `isinstance(result[0], PaymentTransactionEvent)`.

### PTE-G-02 — a newer row of another payment transaction is not returned
- **Rules:** `get_by_payment_transaction` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. C = event, `created_at T2`, but `payment_transaction_id TX2.id`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PTE-G-03 — a row of W1 on a transaction of W2 is not returned for W2
- **Rules:** `get_by_payment_transaction` R2 [BUG-1191]
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 1 (the call raises TypeError: there is no `workspace_id` parameter today)

**Given**
1. A = event, `created_at T1`, but `payment_transaction_id TX9.id`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PTE-G-04 — a call with another workspace returns an empty list
- **Rules:** `get_by_payment_transaction` R2 [BUG-1191]
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 1 (the call raises TypeError: there is no `workspace_id` parameter today)

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PTE-G-05 — only the rows of that workspace are returned
- **Rules:** `get_by_payment_transaction` R2 [BUG-1191]
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 1 (the call raises TypeError: there is no `workspace_id` parameter today)

**Given**
1. A = event, `created_at T1`.
2. Z = event, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PTE-G-06 — workspace_id is required
- **Rules:** `get_by_payment_transaction` R2 [BUG-1191]
- **Kind:** bug
- **Expect:** xfail BUG-1191
- **Fails today on:** Then 1 (no error at all: the call succeeds today, with no `workspace_id`)

**Given**
1. A = event, `created_at T1`.

**When**
- `dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. raises: `TypeError` when the call runs.
2. raises: `"workspace_id" in str(exc.value)`.

### PTE-G-07 — an unknown payment transaction id returns an empty list
- **Rules:** `get_by_payment_transaction` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PTE-G-08 — payment_transaction_id=0 returns an empty list
- **Rules:** `get_by_payment_transaction` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=0)`.

**Then**
1. returns: `result == []`.

### PTE-G-09 — a payment transaction with no events returns an empty list
- **Rules:** `get_by_payment_transaction` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX2.id)`.

**Then**
1. returns: `result == []`.

### PTE-G-10 — nothing about the transaction hides its rows: the read does not touch the parent table
- **Rules:** `get_by_payment_transaction` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. statement: `len(selects) == 1`.
3. statement: `"payment_transactions" not in sql`.

### PTE-G-11 — rows are ordered by created_at ascending, oldest first
- **Rules:** `get_by_payment_transaction` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [C.id, A.id, B.id]`.

### PTE-G-12 — on a tie both rows are returned, after the older row
- **Rules:** `get_by_payment_transaction` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. C = event, `created_at T1`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:]} == {A.id, B.id}`.

### PTE-G-13 — on a created_at tie the lower id comes first after the lower row is updated
- **Rules:** `get_by_payment_transaction` R6 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190 (non-strict)
- **Fails today on:** Then 1 (no order is requested among tied rows, and the higher id came first when run; that rests on physical row order, which can match the intended result by accident)

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PTE-G-14 — on a created_at tie with no update the lower id comes first
- **Rules:** `get_by_payment_transaction` R6 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190 (non-strict)
- **Fails today on:** Then 1 (no order is requested among tied rows; physical row order usually gives this result, so this card usually XPASSes, and only the rule keeps it here)

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PTE-G-15 — the query asks the database for an order that includes id
- **Rules:** `get_by_payment_transaction` R6 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190
- **Fails today on:** Then 3 (the `ORDER BY` names `created_at` only)

**Given**
1. A = event, `created_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.

### PTE-G-16 — every matching row is returned: 158 rows give 158
- **Rules:** `get_by_payment_transaction` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 158 events E1 … E158, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `oldest_first` = the ids of E1, E2, … E158, in that order.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `len(result) == 158`.
2. returns: `ids(result) == oldest_first`.

### PTE-G-17 — a row comes back as stored, with its performer
- **Rules:** `get_by_payment_transaction` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`, but `event_type "ipn_received"`, `description "Step done"`, `metadata_json {"status": "DONE", "note": "Shift 1"}`, `performed_by U1.id`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].payment_transaction_id == TX1.id`, `result[0].event_type == "ipn_received"`.
3. returns: `result[0].description == "Step done"`, `result[0].created_at == T2`.
4. returns: `result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}`.
5. returns: `result[0].performer.id == U1.id`.

### PTE-G-18 — SQL NULL and JSON null metadata both read back as None, and no performer gives None
- **Rules:** `get_by_payment_transaction` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. returns: `result[0].metadata_json is None`.
3. returns: `result[1].metadata_json is None`.
4. re-read A: `stored_json(A) is None`.
5. re-read B: `stored_json(B) == "null"`.
6. returns: `result[0].performer is None`.

### PTE-G-19 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_payment_transaction` R8, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = PaymentTransactionEvent(workspace_id=W1.id, payment_transaction_id=TX1.id, event_type="initiated", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. pending: `len(db.new) == 1`.
6. pending: `not db.dirty and not db.deleted`.
7. unchanged: unchanged(A).
8. statement: `written == []`.
9. statement: `"FOR" not in sql.upper().split()`.

### PTE-G-20 — on a created_at tie id decides, not event_type, description or performer
- **Rules:** `get_by_payment_transaction` R6 [BUG-1190]
- **Kind:** bug
- **Expect:** xfail BUG-1190 (non-strict)
- **Fails today on:** Then 1 (no order is requested among tied rows; physical row order gives the intended result today, so this card usually XPASSes, and only the rule keeps it here)

**Given**
1. `U2`, `U3` = two more `profiles` rows (`make_profile`), made after U1, in that order.
2. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`.
3. B = event, `created_at T2`, but `event_type "a"`, `description "a"`, `performed_by U1.id`.
4. C = event, `created_at T2`, but `event_type "c"`, `description "c"`, `performed_by U3.id`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.


### PTE-G-21 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_payment_transaction` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2 + timedelta(microseconds=1)`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.


### PTE-G-22 — writes nothing: with an empty result the pending row is still alone in the session
- **Rules:** `get_by_payment_transaction` R8, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = PaymentTransactionEvent(workspace_id=W1.id, payment_transaction_id=TX1.id, event_type="initiated", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX2.id)`.

**Then**
1. returns: `result == []`.
2. pending: `len(db.new) == 1`.


### PTE-G-23 — created_at decides, not event_type, description or performer
- **Rules:** `get_by_payment_transaction` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `U2`, `U3` = two more `profiles` rows (`make_profile`), made after U1, in that order.
2. A = event, `created_at T1`, but `event_type "b"`, `description "b"`, `performed_by U2.id`.
3. B = event, `created_at T2`, but `event_type "a"`, `description "a"`, `performed_by U1.id`.
4. C = event, `created_at T3`, but `event_type "c"`, `description "c"`, `performed_by U3.id`.

**When**
- `result = dao.get_by_payment_transaction(db, payment_transaction_id=TX1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec gap 3, ruling of 2026-11-02 (HR-16) — a row of A on a transaction of B does not show for A | `PaymentTransactionService.get_transaction_by_tran_id` | The transaction is found in the workspace first, so A gets not found. No card here. |
| FU-1 — BUG-1191, caller side | `PaymentTransactionService.get_transaction_by_tran_id` | Must pass `workspace_id` once the bug is fixed. Here the BUG-1191 cards test the DAO's own filter. |
| Overview — writes go through `_log_event`, which copies `txn.workspace_id` | `PaymentTransactionManager._log_event` | The payment manager spec, `_log_event` R1. No write of this DAO. |
| Q1 — the billing page draws the list as it arrives | `BillingTrialPage.tsx` | Frontend. Here only the order is checked. |
| `create` (by `_log_event`) and the other inherited methods | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not specified here. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |
| Model facts: database default `now()` on `created_at` | none (no rule) | Every card gives `created_at`, as the spec's Notes ask. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`. |
| 2 | Overview ("takes no lock") | Stands outside the numbered rules. | Covered anyway, as the Overview row of the matrix, by the "writes nothing" card. Its check looks for the word `FOR`, so it covers every lock form. Drop the line if it is not meant as a contract. |
| 3 | `get_by_payment_transaction` R2 | **Money. Settled 2026-11-02, by HR-16, decided under the reviewer's delegation:** a row of A on a transaction of B is invalid data and is not returned. | PTE-G-03 holds it for the call with B. No card for the call with A (transaction of B, workspace A): the row's own workspace matches, so the read could refuse it only by looking at the transaction, which PTE-G-10 forbids. For A the ruling is held by the caller, which finds the transaction in the workspace first: see Deferred. **Closed 2026-11-02:** the ruling binds the caller, not this DAO; PTE-G-10 Then 3 stands. |
| 4 | `get_by_payment_transaction` R4 | **Money. Settled by R-4 of the verify report:** the rule still names no state of the transaction, but the read may not look at the parent, whatever its states are. | PTE-G-10 Then 3 asserts that `payment_transactions` is not in the statement, in place of the word `JOIN`, so a subquery is caught too. |
| 5 | Notes, BUG-1191 | **Money.** The fix makes `workspace_id` required, so every pass card, written to today's call as the Notes ask, fails with `TypeError` after the fix. | Expected. The same holds for the BUG-1190 strict recorder: if BUG-1191 is fixed first and that card keeps today's call, it stays xfail on `TypeError`, and its alarm is silent. The fix must add the argument to the whole file. |
| 6 | `get_by_payment_transaction` R6 | **Money.** The Today note says the no-update tie comes back lower `id` first, which is the intended result. | That card has no assertion that fails today: it is kept non-strict for the rule's sake and usually XPASSes. Its partner (lower row updated) is the one that fails when run, and the strict recorder is the alarm. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_payment_transaction` | Returns | PTE-G-01 |
| `get_by_payment_transaction` | R1 | PTE-G-01, PTE-G-02 |
| `get_by_payment_transaction` | R2 [BUG-1191] | PTE-G-03, PTE-G-04, PTE-G-05, PTE-G-06 |
| `get_by_payment_transaction` | R3 | PTE-G-07, PTE-G-08, PTE-G-09 |
| `get_by_payment_transaction` | R4 | PTE-G-10 |
| `get_by_payment_transaction` | R5 | PTE-G-11, PTE-G-12, PTE-G-21, PTE-G-23 |
| `get_by_payment_transaction` | R6 | PTE-G-12 |
| `get_by_payment_transaction` | R6 [BUG-1190] | PTE-G-13, PTE-G-14, PTE-G-15, PTE-G-20 |
| `get_by_payment_transaction` | R7 | PTE-G-16 |
| `get_by_payment_transaction` | R8 | PTE-G-17, PTE-G-18, PTE-G-19, PTE-G-22 |
| `get_by_payment_transaction` | Overview | PTE-G-19 |
| `get_by_payment_transaction` | Side effects | PTE-G-19, PTE-G-22 |
