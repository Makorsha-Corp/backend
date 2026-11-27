# Test cases — `app/dao/payment_transaction.py`

> **Spec:** `tests/unit/dao/payment_transaction.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10, nothing open). P1 was decided by Claude under the reviewer's delegation. OQ-25 is deferred by the owner to the payment portal: its rule (`get_stuck_initiated` R7) keeps today's behaviour in its own section, **Deferred to the payment portal — OQ-25**, and no other card depends on it.
> **Revision:** 2 (2026-11-10) — spec apply-review + fill-gaps G1–G3. OQ-25 answered "decide in the payment portal work": the six PTX-OQ25 cards are unchanged; the section and their header line are relabelled from "pending" to "deferred to the payment portal". G1: R1's times are three separate calls and cannot be patched by module name; PTX-CR-01 already checks each time against the call's window and never their equality, so only its rule tag changes. G2: new R1b (13 integer digits fit, 14 fail with 22003) and Errors row 3: new PTX-CR-22, CR-23, CR-24. G3: R7 is status-only by rule; OQ25-02 and OQ25-03 stand as written. Spec gaps closed. No ID retired.
> **Revision:** 3 (2026-11-10) — `payment_transaction.verify.md` findings 1–2, both `case-missing`. F1: PTX-IW-13 gains Then 6, the whole lock clause is exactly `FOR UPDATE OF payment_transactions` (a `SKIP LOCKED` / `NOWAIT` fix fails). F2: PTX-IW-11, TW-15, LW-21 run `db.expunge_all()` before the recorder, so a separate profile read would show. Conventions gain "No-lock check" and "Clear the session before a one-query check". No card added or retired; counts unchanged.
> **Counts:** 143 cases · 125 expected-to-pass · 18 expected-to-fail (bugs) · 9 deferred (the 6 OQ-25 cards are among the passes)

## Reviewer summary
- **Per callable:** inherited `create` 24 (4 bug) · `get_by_tran_id` 18 · `get_by_tran_id_for_update` 14 · `get_by_id_and_workspace_with_initiator` 18 (6 bug) · `get_by_tran_id_and_workspace_with_initiator` 16 · `list_by_workspace_with_initiator` 22 (4 bug) · `get_stuck_initiated` 25 (4 bug) · OQ-25 (deferred to the portal) 6.
- **Depth:** full (skill step 1a). This is the ledger of money taken through SSLCommerz and the owner's reference for the coming subscription portal: every lookup the callbacks, the sweep and risk resolution use is covered, with exact-match, isolation, lock-clause and order cards.
- **Expected-to-fail:** BUG-029 6 (strict; the new `for_update` keyword, failing in the call today) · BUG-2401 4 (strict; the database clock under `Asia/Dhaka` / `America/New_York`) · BUG-2402 4 (3 non-strict tie orders, 1 strict SQL alarm) · BUG-2403 4 (3 non-strict, 1 strict SQL alarm).
- **OQ-25, deferred to the payment portal (owner, 2026-11-10):** 6 cards in their own section (`PTX-OQ25-…`), written to today's behaviour (only `INITIATED` rows are swept, selected by status alone). When the portal decides, only those cards change; every other sweep card uses `INITIATED` rows and statuses OQ-25 does not touch (`VALIDATED_SUCCESS`, look-alike texts).
- **Notable design choices:**
  - The `tran_id` lookups and the sweep read across workspaces by design. Their cards build rows in W0 and W2 as well and expect them back. The sweep cards use times in **2001** and start with the precondition **clean2001**, so a committed row of another test can never take a place in a batch.
  - Lock cards check the SQL only. Whether a second session waits is integration-only (spec Overview). `PTX-TU-14` is a commit spy on a reader: a commit there would release the callback's lock half-way, so it is worth one card.
  - HR-15 is checked where this table rounds money: the `Numeric(15,2)` column on insert. The cards use values where half up and half to even differ (2.125, 0.005, -1.005) and a control (2.124). The column's bounds (R1b) are carded on both sides: 13 integer digits stored; `9999999999999.995` (rounds up to 14 digits) and `10000000000000` refused with 22003.
  - R1's three times are separate `utcnow()` calls that cannot be patched by module name. The cards check that each one falls inside the call's window, never that the three are equal.
  - The BUG-2401 cards use a raw `INSERT` without the time columns, as the spec's Notes say. One pass control under `UTC` holds both today and after the fix.
  - Race simulations: none. The race BUG-029 guards against is integration-only. Here only the clause is checked.
- **Needs a decision:** None. Gaps 1–3 of revision 1 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `PTX` = `app/dao/payment_transaction.py`. `CR` inherited `create` (model facts) · `TI` get_by_tran_id · `TU` get_by_tran_id_for_update · `IW` get_by_id_and_workspace_with_initiator · `TW` get_by_tran_id_and_workspace_with_initiator · `LW` list_by_workspace_with_initiator · `SI` get_stuck_initiated · `OQ25` R7 of `get_stuck_initiated`, deferred to the payment portal.

**Actors and fixed values.**
- `dao` = the singleton `payment_transaction_dao` (`from app.dao.payment_transaction import payment_transaction_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns. The session does not autoflush.
- `PaymentTransaction` = `app.models.payment_transaction.PaymentTransaction`. `Profile` = `app.models.profile.Profile`. `Decimal`, `datetime`, `timedelta`, `timezone`, `secrets`, `text`, `patch` = the usual ones. `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = `psycopg2.errors` classes.
- MISSING = `999999999`: an id that no row of any table has.
- TAG = `"ab" + secrets.token_hex(11)`, made once per test (24 lower-case characters, always containing letters). **tid(k)** = `f"tx{k}{TAG}"` (27 characters; k is one digit). `tran_id` is unique across the whole database, so every row uses a tid.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 4, 11, 0, 0)`, T3 = `datetime(2026, 3, 4, 12, 0, 0)`, T4 = `datetime(2026, 3, 4, 13, 0, 0)` (naive UTC).
- Sweep times (year 2001 on purpose): CUT = `datetime(2001, 3, 1, 12, 0, 0)`, S1 = `datetime(2001, 3, 1, 9, 0, 0)`, S2 = `datetime(2001, 3, 1, 10, 0, 0)`, S3 = `datetime(2001, 3, 1, 11, 0, 0)`, OLD = `datetime(2001, 1, 1, 9, 0, 0)`. US = `timedelta(microseconds=1)`. CUTZ = `datetime(2001, 3, 1, 12, 0, 0, tzinfo=timezone.utc)`.

**Externals.** None. Nothing is mocked and no clock is patched. **utc_now()** = `datetime.now(timezone.utc).replace(tzinfo=None)`.

**Standing rows** (every test, in this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`. U1 = `make_profile(db, name="Rahim")`, U2 = `make_profile(db, name="Karim")`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. A line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending.
- **txn(k)** = `PaymentTransaction(workspace_id=W1.id, tran_id=tid(k), amount=Decimal("990.00"), currency="BDT", initiated_by=U1.id, initiated_at=T1, created_at=T1, updated_at=T1)`; `status` is not passed (default `"INITIATED"`). After "but" a line lists every column that differs, by column name. `initiated_by None` passes the keyword with `None`.
- **paid** (used after "but") = `status "VALIDATED_SUCCESS"`, `val_id "val-ok-1"`, `bank_tran_id "bank-1"`, `card_type "VISA-Dutch Bangla"`, `validated_at T2`.
- **raw_insert(s)** = `db.scalar(text("INSERT INTO payment_transactions (workspace_id, tran_id, amount, currency) VALUES (:w, :t, 990.00, 'BDT') RETURNING id"), {"w": W1.id, "t": s})`; its value is the new id.
- **zone(Z)** = `db.execute(text(f"SET LOCAL TimeZone = '{Z}'"))`.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, then the same for `enable_bitmapscan` and `enable_indexonlyscan`.
- **bump(X)** = `db.execute(text("UPDATE payment_transactions SET currency = currency WHERE id = :i"), {"i": X.id})`, then `db.expire_all()` (moves X's row to the end of the table, so physical order differs from id order).
- **clean2001** = `assert db.scalar(text("SELECT count(*) FROM payment_transactions WHERE initiated_at < '2002-01-01' AND workspace_id NOT IN (:a, :b, :c)"), {"a": W0.id, "b": W1.id, "c": W2.id}) == 0`. It is the first Given step of every `SI` and `OQ25` test, without a Given line; it is a precondition, not a numbered check.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **pairs(result)** = `[(t.id, name) for t, name in result]`, order part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **nothing written** = the numbers of `payment_transactions` rows of W0, W1 and W2 and of `profiles` rows equal their values before the call.
- **count_tid(s)** = `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE tran_id = :t"), {"t": s})`.
- **near_utc(v)** = `abs(utc_now() - v) < timedelta(minutes=5)`.
- Money is compared as `Decimal` (`Decimal("2.13")`), never as float; a line using `str(...)` checks the scale too.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` right after the call, before anything expires the session.
- `raises: E` (`IntegrityError`, `DataError`) = `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `raises: TypeError` = plain `with pytest.raises(TypeError) as exc:`. Further `raises:` lines assert on `exc.value` or `exc.value.orig`, one `assert` per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around the call; "inside" lines run before `sp.rollback()`, "after" lines after it.
- **Statement recorder** = the SQL the session sends during the When is recorded (`before_cursor_execute` listener on `db.get_bind()`, as in `tests/unit/dao/test_access_control.py`). `selects` = every recorded `SELECT`; `sql` = the one `SELECT` whose text contains `FROM payment_transactions`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` if none); `lock_part` = the text of `sql` from its first `FOR UPDATE` to the end (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Here `lock_part` starts at `FOR UPDATE`, so `lock_part == ""` is the same check.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for a tie order that rests on physical row order. Write the call and checks exactly as shown; never weaken an assertion.

**Race simulations.** None in this module.

## Inherited `create` (model facts of `payment_transactions`)

*A checkout starts with `dao.create(db, obj_in={...})` from `initiate_payment`. These cards pin what the table itself guarantees.*

### PTX-CR-01 — a checkout row gets status INITIATED, three naive UTC times and nothing else
- **Rules:** inherited `create` R1 (each time in the call's window; never asserted equal), Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no payment transaction.
2. `before = utc_now()`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("990.00"), "currency": "BDT"})`, then `after = utc_now()` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `status == "INITIATED"`.
3. re-read result: `workspace_id == W1.id`, `tran_id == tid(1)`, `amount == Decimal("990.00")`, `currency == "BDT"`.
4. re-read result: `initiated_at.tzinfo is None`, `created_at.tzinfo is None`, `updated_at.tzinfo is None`.
5. re-read result: `before <= initiated_at <= after`.
6. re-read result: `before <= created_at <= after`.
7. re-read result: `before <= updated_at <= after`.
8. re-read result: `cus_name`, `cus_email`, `cus_phone`, `value_a`, `value_b`, `value_c`, `value_d`, `session_key`, `gateway_page_url`, `val_id`, `risk_level`, `risk_title`, `card_type`, `bank_tran_id`, `verify_sign`, `last_ipn_payload`, `risk_resolved_by`, `initiated_by`, `risk_resolved_at`, `validated_at`, `risk_resolution_note` are all `None`.
9. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"), {"w": W1.id}) == 1`.

### PTX-CR-02 — the new row is flushed: a raw query in the same session finds it
- **Rules:** inherited `create` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("990.00"), "currency": "BDT", "initiated_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. session: `result not in db.new`.
3. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE id = :i AND tran_id = :t AND initiated_by = :u"), {"i": result.id, "t": tid(1), "u": U1.id}) == 1`.

### PTX-CR-03 — create flushes but never commits
- **Rules:** inherited `create` R1 ("not committed")
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- commit spy around `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("990.00"), "currency": "BDT"})`.

**Then**
1. returns (inside): `result.id is not None`.
2. count (inside): `count_tid(tid(1)) == 1`.
3. mock called: `cm.call_count == 0`.
4. count (after the savepoint rollback): `count_tid(tid(1)) == 0`.

### PTX-CR-04 — an amount of 2.125 is stored as 2.13 (half up, not half to even)
- **Rules:** inherited `create` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("2.125"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.13")`.
3. re-read result: `str(amount) == "2.13"`.

### PTX-CR-05 — an amount of 0.005 is stored as 0.01, not 0.00
- **Rules:** inherited `create` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("0.005"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("0.01")`.

### PTX-CR-06 — an amount of -1.005 is stored as -1.01 (away from zero)
- **Rules:** inherited `create` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("-1.005"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("-1.01")`.

### PTX-CR-07 — an amount of 2.124 is stored as 2.12 (control: below the half)
- **Rules:** inherited `create` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("2.124"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.12")`.

### PTX-CR-08 — a whole amount is stored with two decimals
- **Rules:** inherited `create` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("990"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `str(amount) == "990.00"`.

### PTX-CR-09 — a tran_id already used in another workspace fails at flush and saves nothing
- **Rules:** inherited `create` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = txn(1), but `workspace_id W2.id`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("500.00"), "currency": "BDT"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `count_tid(tid(1)) == 1`.
3. re-read A: `workspace_id == W2.id`, `amount == Decimal("990.00")`.
4. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"), {"w": W1.id}) == 0`.

### PTX-CR-10 — a tran_id already used in the same workspace fails at flush
- **Rules:** inherited `create` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("500.00"), "currency": "BDT"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `count_tid(tid(1)) == 1`.
3. re-read A: `amount == Decimal("990.00")`.

### PTX-CR-11 — the same tran_id in capitals is a different tran_id
- **Rules:** inherited `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1).upper(), "amount": Decimal("500.00"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `tran_id == tid(1).upper()`.
3. count: `count_tid(tid(1)) == 1`.

### PTX-CR-12 — a tran_id of exactly 30 characters is stored
- **Rules:** inherited `create` R2 (boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1) + "xyz", "amount": Decimal("990.00"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `tran_id == tid(1) + "xyz"`.
3. re-read result: `len(tran_id) == 30`.

### PTX-CR-13 — a tran_id of 31 characters fails at flush with DataError 22001 and saves nothing
- **Rules:** inherited `create` R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1) + "wxyz", "amount": Decimal("990.00"), "currency": "BDT"})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. count: `count_tid(tid(1) + "wxyz") == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"), {"w": W1.id}) == 0`.

### PTX-CR-14 — any status text is stored as given
- **Rules:** inherited `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("990.00"), "currency": "BDT", "status": "whatever"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `status == "whatever"`.

### PTX-CR-15 — a negative amount is stored
- **Rules:** inherited `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("-5"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("-5.00")`.

### PTX-CR-16 — a row inserted without its times gets the status INITIATED from the database
- **Rules:** inherited `create` R1 (database default of `status`), R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. zone(`"UTC"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE id = :i AND status = 'INITIATED'"), {"i": new_id}) == 1`.

### PTX-CR-17 — under a UTC session a raw insert gets UTC times (control, today and after the fix)
- **Rules:** inherited `create` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone(`"UTC"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. re-read the row `new_id`: `near_utc(initiated_at)`.
3. re-read the row `new_id`: `near_utc(created_at)`.
4. re-read the row `new_id`: `near_utc(updated_at)`.

### PTX-CR-18 — under Asia/Dhaka a raw insert's initiated_at is still UTC
- **Rules:** inherited `create` R1a [BUG-2401]
- **Kind:** bug
- **Expect:** xfail BUG-2401
- **Fails today on:** Then 2 (the database default `now()` gives Dhaka time, six hours ahead)

**Given**
1. zone(`"Asia/Dhaka"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. re-read the row `new_id`: `near_utc(initiated_at)`.

### PTX-CR-19 — under Asia/Dhaka a raw insert's created_at is still UTC
- **Rules:** inherited `create` R1a [BUG-2401]
- **Kind:** bug
- **Expect:** xfail BUG-2401
- **Fails today on:** Then 2 (the database default `now()` gives Dhaka time, six hours ahead)

**Given**
1. zone(`"Asia/Dhaka"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. re-read the row `new_id`: `near_utc(created_at)`.

### PTX-CR-20 — under Asia/Dhaka a raw insert's updated_at is still UTC
- **Rules:** inherited `create` R1a [BUG-2401]
- **Kind:** bug
- **Expect:** xfail BUG-2401
- **Fails today on:** Then 2 (the database default `now()` gives Dhaka time, six hours ahead)

**Given**
1. zone(`"Asia/Dhaka"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. re-read the row `new_id`: `near_utc(updated_at)`.

### PTX-CR-21 — under America/New_York a raw insert's initiated_at is still UTC (behind as well as ahead)
- **Rules:** inherited `create` R1a [BUG-2401]
- **Kind:** bug
- **Expect:** xfail BUG-2401
- **Fails today on:** Then 2 (the database default `now()` gives New York time, five hours behind)

**Given**
1. zone(`"America/New_York"`).

**When**
- `new_id = raw_insert(tid(1))`.

**Then**
1. returns: `new_id is not None`.
2. re-read the row `new_id`: `near_utc(initiated_at)`.

### PTX-CR-22 — an amount with 13 integer digits is stored as is
- **Rules:** inherited `create` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("9999999999999.99"), "currency": "BDT"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("9999999999999.99")`.

### PTX-CR-23 — an amount that rounds up to 14 integer digits fails at flush with DataError 22003 and saves nothing
- **Rules:** inherited `create` R1b, Errors row 3, HR-15
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("9999999999999.995"), "currency": "BDT"})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22003"`.
2. count: `count_tid(tid(1)) == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"), {"w": W1.id}) == 0`.

### PTX-CR-24 — an amount with 14 integer digits fails at flush with DataError 22003 and saves nothing
- **Rules:** inherited `create` R1b, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no payment transaction.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tran_id": tid(1), "amount": Decimal("10000000000000"), "currency": "BDT"})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22003"`.
2. count: `count_tid(tid(1)) == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM payment_transactions WHERE workspace_id = :w"), {"w": W1.id}) == 0`.

## `PaymentTransactionDAO.get_by_tran_id`

*Used while generating a fresh `tran_id` (global uniqueness) and by the mock-gateway pages. Unscoped by design.*

### PTX-TI-01 — returns the row with exactly this tran_id
- **Rules:** `get_by_tran_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. C = txn(3).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(2))`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `result.tran_id == tid(2)`.

### PTX-TI-02 — a row of an earlier workspace is returned (unscoped)
- **Rules:** `get_by_tran_id` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1), but `workspace_id W0.id`.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W0.id`.

### PTX-TI-03 — a row of a later workspace is returned (unscoped)
- **Rules:** `get_by_tran_id` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1), but `workspace_id W2.id`.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W2.id`.

### PTX-TI-04 — a paid row is returned whatever its status
- **Rules:** `get_by_tran_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but paid.
2. B = txn(2), but `status "RISK_HOLD"`, `risk_level 1`, `risk_title "Card from abroad"`.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "VALIDATED_SUCCESS"`.

### PTX-TI-05 — an unknown tran_id returns None
- **Rules:** `get_by_tran_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(9))`.

**Then**
1. returns: `result is None`.

### PTX-TI-06 — an empty tran_id returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id="")`.

**Then**
1. returns: `result is None`.

### PTX-TI-07 — the tran_id in capitals returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1).upper())`.

**Then**
1. returns: `result is None`.

### PTX-TI-08 — the tran_id with a trailing space returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1) + " ")`.

**Then**
1. returns: `result is None`.

### PTX-TI-09 — the tran_id with a leading space returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=" " + tid(1))`.

**Then**
1. returns: `result is None`.

### PTX-TI-10 — the tran_id without its last character returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1)[:-1])`.

**Then**
1. returns: `result is None`.

### PTX-TI-11 — a middle part of the tran_id returns None
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1)[3:20])`.

**Then**
1. returns: `result is None`.

### PTX-TI-12 — "_" in place of one character is no wildcard
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1)[:5] + "_" + tid(1)[6:])`.

**Then**
1. returns: `result is None`.

### PTX-TI-13 — "%" after the start of the tran_id is no wildcard
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1)[:6] + "%")`.

**Then**
1. returns: `result is None`.

### PTX-TI-14 — a stored tran_id with a leading space is not found by the plain one
- **Rules:** `get_by_tran_id` R2 (stored side)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `tran_id " " + tid(1)`.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result is None`.

### PTX-TI-15 — a stored tran_id in capitals is not found by the lower-case one
- **Rules:** `get_by_tran_id` R2 (stored side)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `tran_id tid(1).upper()`.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result is None`.

### PTX-TI-16 — a 40-character string that starts with a tran_id returns None and raises nothing
- **Rules:** `get_by_tran_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1) + "x" * 13)`.

**Then**
1. returns: `result is None`.

### PTX-TI-17 — one SELECT, no lock, nothing written
- **Rules:** `get_by_tran_id` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. Statement recorder.

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part == ""`.
4. statement: `written == []`.

### PTX-TI-18 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_tran_id` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. `B.cus_name = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT")`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_tran_id(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

## `PaymentTransactionDAO.get_by_tran_id_for_update`

*Every gateway callback and the sweep read the row through this lock, so two callbacks cannot both finalize one payment.*

### PTX-TU-01 — returns the row with exactly this tran_id
- **Rules:** `get_by_tran_id_for_update` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. C = txn(3).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(2))`.

**Then**
1. returns: `result.id == B.id`.

### PTX-TU-02 — a row of an earlier workspace is returned (unscoped)
- **Rules:** `get_by_tran_id_for_update` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1), but `workspace_id W0.id`.

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.

### PTX-TU-03 — a paid row of a later workspace is returned (any workspace, any status)
- **Rules:** `get_by_tran_id_for_update` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1), but `workspace_id W2.id`, paid.

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "VALIDATED_SUCCESS"`.

### PTX-TU-04 — an unknown tran_id returns None
- **Rules:** `get_by_tran_id_for_update` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(9))`.

**Then**
1. returns: `result is None`.

### PTX-TU-05 — an empty tran_id returns None
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id="")`.

**Then**
1. returns: `result is None`.

### PTX-TU-06 — the tran_id in capitals returns None
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1).upper())`.

**Then**
1. returns: `result is None`.

### PTX-TU-07 — the tran_id with a trailing space returns None
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1) + " ")`.

**Then**
1. returns: `result is None`.

### PTX-TU-08 — "_" in place of one character is no wildcard
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1)[:5] + "_" + tid(1)[6:])`.

**Then**
1. returns: `result is None`.

### PTX-TU-09 — the tran_id without its last character returns None
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1)[:-1])`.

**Then**
1. returns: `result is None`.

### PTX-TU-10 — a 40-character string that starts with a tran_id returns None and raises nothing
- **Rules:** `get_by_tran_id_for_update` R1 (as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1) + "x" * 13)`.

**Then**
1. returns: `result is None`.

### PTX-TU-11 — the row is read with a plain FOR UPDATE at the end of the one SELECT
- **Rules:** `get_by_tran_id_for_update` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. Statement recorder.

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `len(selects) == 1`.
3. statement: `sql.rstrip().endswith("FOR UPDATE")`.
4. statement: `"NOWAIT" not in sql.upper()`.
5. statement: `"SKIP LOCKED" not in sql.upper()`.
6. statement: `written == []`.

### PTX-TU-12 — an unknown tran_id sends the same locked SELECT and returns None
- **Rules:** `get_by_tran_id_for_update` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).
2. Statement recorder.

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(9))`.

**Then**
1. returns: `result is None`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part.strip() == "FOR UPDATE"`.

### PTX-TU-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_tran_id_for_update` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. `B.cus_name = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT")`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1))`.

**Then**
1. returns: `result.id == A.id`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

### PTX-TU-14 — the locked read never commits (a commit would release the callback's lock)
- **Rules:** `get_by_tran_id_for_update` R2 ("held until the caller's transaction commits or rolls back")
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- commit spy around `result = dao.get_by_tran_id_for_update(db, tran_id=tid(1))`.

**Then**
1. returns (inside): `result.id == A.id`.
2. mock called: `cm.call_count == 0`.
3. count (after the savepoint rollback): `count_tid(tid(1)) == 1`.

## `PaymentTransactionDAO.get_by_id_and_workspace_with_initiator`

*Risk resolution (`POST /payments/{transaction_id}/resolve-risk/`) reads the held payment here. BUG-029: it must be able to lock the transaction row (`for_update=True`), and only that row.*

### PTX-IW-01 — returns the pair (transaction, initiator's name)
- **Rules:** `get_by_id_and_workspace_with_initiator` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `status "RISK_HOLD"`, `risk_level 1`, `risk_title "Card from abroad"`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0].id == A.id`.
3. returns: `result[1] == "Rahim"`.
4. returns: `tuple(result) == (result[0], "Rahim")` (the pair unpacks as two values).

### PTX-IW-02 — the name is the initiator's, not the risk resolver's
- **Rules:** `get_by_id_and_workspace_with_initiator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_by U2.id`, `risk_resolved_by U1.id`, `risk_resolved_at T2`, `risk_resolution_note "Checked with the bank"`, paid.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[1] == "Karim"`.

### PTX-IW-03 — a row without an initiator is returned, with name None
- **Rules:** `get_by_id_and_workspace_with_initiator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_by None`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result[0].id == A.id`.
3. returns: `result[1] is None`.

### PTX-IW-04 — after the initiator's profile is deleted, the row is returned with name None
- **Rules:** `get_by_id_and_workspace_with_initiator` R2 (`ON DELETE SET NULL`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. U3 = `make_profile(db, name="Salma")`.
2. A = txn(1), but `initiated_by U3.id`.
3. `db.execute(text("DELETE FROM profiles WHERE id = :i"), {"i": U3.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[0].initiated_by is None`.
3. returns: `result[1] is None`.

### PTX-IW-05 — a row of an earlier workspace (lower id) returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`.
2. A = txn(2).

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-IW-06 — a row of a later workspace (higher id) returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1).
2. X2 = txn(2), but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-IW-07 — W1's row asked for under W0 or W2 returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = [dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=w) for w in (W0.id, W2.id)]` (one list comprehension).

**Then**
1. returns: `result == [None, None]`.

### PTX-IW-08 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-IW-09 — id 0 returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-IW-10 — status does not matter: an expired row is returned
- **Rules:** `get_by_id_and_workspace_with_initiator` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `status "EXPIRED"`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[0].status == "EXPIRED"`.

### PTX-IW-11 — without for_update: one SELECT, no lock, nothing written
- **Rules:** `get_by_id_and_workspace_with_initiator` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. `db.expunge_all()` (clear the session before a one-query check).
3. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[1] == "Rahim"`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part == ""`.
4. statement: `written == []`.

### PTX-IW-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_id_and_workspace_with_initiator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. `B.risk_resolution_note = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT")`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

### PTX-IW-13 — for_update=True locks only the transaction row: FOR UPDATE OF payment_transactions
- **Rules:** `get_by_id_and_workspace_with_initiator` R5 [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. A = txn(1), but `status "RISK_HOLD"`, `risk_level 1`, `risk_title "Card from abroad"`.
2. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id, for_update=True)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[1] == "Rahim"`.
3. statement: `len(selects) == 1`.
4. statement: `"FOR UPDATE OF payment_transactions" in sql`.
5. statement: `"profiles" not in lock_part`.
6. statement: `lock_part.strip() == "FOR UPDATE OF payment_transactions"` (no `SKIP LOCKED`, no `NOWAIT`: HR-10, the second caller waits).

### PTX-IW-14 — for_update=True with no initiator still returns the row, name None (the outer join is kept)
- **Rules:** `get_by_id_and_workspace_with_initiator` R5, R2 [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. A = txn(1), but `initiated_by None`, `status "RISK_HOLD"`.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id, for_update=True)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[1] is None`.

### PTX-IW-15 — for_update=True on another workspace's row returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R5, R3 [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. X0 = txn(1), but `workspace_id W0.id`, `status "RISK_HOLD"`.
2. X2 = txn(2), but `workspace_id W2.id`, `status "RISK_HOLD"`.

**When**
- `result = [dao.get_by_id_and_workspace_with_initiator(db, id=x, workspace_id=W1.id, for_update=True) for x in (X0.id, X2.id)]` (one list comprehension).

**Then**
1. returns: `result == [None, None]`.

### PTX-IW-16 — for_update=True with an unknown id returns None
- **Rules:** `get_by_id_and_workspace_with_initiator` R5, R3 [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=MISSING, workspace_id=W1.id, for_update=True)`.

**Then**
1. returns: `result is None`.

### PTX-IW-17 — for_update=False takes no lock
- **Rules:** `get_by_id_and_workspace_with_initiator` R4, R5 [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. A = txn(1).
2. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id, for_update=False)`.

**Then**
1. returns: `result[0].id == A.id`.
2. statement: `lock_part == ""`.

### PTX-IW-18 — for_update=True writes nothing and never commits
- **Rules:** `get_by_id_and_workspace_with_initiator` R5, Side effects [BUG-029]
- **Kind:** bug
- **Expect:** xfail BUG-029
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` keyword)

**Given**
1. A = txn(1), but `status "RISK_HOLD"`.

**When**
- commit spy around `result = dao.get_by_id_and_workspace_with_initiator(db, id=A.id, workspace_id=W1.id, for_update=True)`.

**Then**
1. returns (inside): `result[0].id == A.id`.
2. mock called: `cm.call_count == 0`.
3. count (after the savepoint rollback): `count_tid(tid(1)) == 1`.

## `PaymentTransactionDAO.get_by_tran_id_and_workspace_with_initiator`

*The detail page `GET /payments/{tran_id}/`. Scoped to the caller's workspace (HR-16: another workspace's payment is "not found").*

### PTX-TW-01 — returns the pair (transaction, initiator's name)
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but paid.
2. B = txn(2).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0].id == A.id`.
3. returns: `result[1] == "Rahim"`.

### PTX-TW-02 — the name is the initiator's, not the risk resolver's
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_by U2.id`, `risk_resolved_by U1.id`, `risk_resolved_at T2`, paid.

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[1] == "Karim"`.

### PTX-TW-03 — a row without an initiator is returned, with name None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R1 (name as `get_by_id_and_workspace_with_initiator` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_by None`.

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[1] is None`.

### PTX-TW-04 — a tran_id of an earlier workspace returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`.
2. A = txn(2).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-05 — a tran_id of a later workspace returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1).
2. X2 = txn(2), but `workspace_id W2.id`.

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(2), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-06 — W1's tran_id asked for under W0 or W2 returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = [dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=w) for w in (W0.id, W2.id)]` (one list comprehension).

**Then**
1. returns: `result == [None, None]`.

### PTX-TW-07 — an unknown tran_id or workspace returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = [dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=t, workspace_id=w) for t, w in ((tid(9), W1.id), (tid(1), MISSING))]` (one list comprehension).

**Then**
1. returns: `result == [None, None]`.

### PTX-TW-08 — an empty tran_id returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id="", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-09 — a 40-character string that starts with a tran_id returns None and raises nothing
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1) + "x" * 13, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-10 — the tran_id in capitals returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1).upper(), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-11 — the tran_id with a trailing space returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1) + " ", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-12 — "_" in place of one character is no wildcard
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1)[:5] + "_" + tid(1)[6:], workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-13 — the tran_id without its last character returns None
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R2 (matched as `get_by_tran_id` R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1)[:-1], workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PTX-TW-14 — status does not matter: a risk-held row is returned
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `status "RISK_HOLD"`, `risk_level 1`, `risk_title "Card from abroad"`.

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[0].status == "RISK_HOLD"`.

### PTX-TW-15 — one SELECT, no lock, nothing written
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. `db.expunge_all()` (clear the session before a one-query check).
3. Statement recorder.

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part == ""`.
4. statement: `written == []`.

### PTX-TW-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_tran_id_and_workspace_with_initiator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2).
3. `B.cus_name = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT")`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_tran_id_and_workspace_with_initiator(db, tran_id=tid(1), workspace_id=W1.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

## `PaymentTransactionDAO.list_by_workspace_with_initiator`

*The workspace's payment ledger, `GET /payments/`: newest first, then id descending (BUG-2402), with the initiator's name.*

### PTX-LW-01 — only W1's rows; newer rows of W0 and W2 are left out
- **Rules:** `list_by_workspace_with_initiator` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`, `created_at T4`.
2. A = txn(2), but `created_at T1`.
3. X2 = txn(3), but `workspace_id W2.id`, `created_at T4`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(A.id, "Rahim")]`.

### PTX-LW-02 — asked for W0 or W2, each gets only its own row
- **Rules:** `list_by_workspace_with_initiator` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`, `created_at T1`.
2. A = txn(2), but `created_at T4`.
3. X2 = txn(3), but `workspace_id W2.id`, `created_at T1`.

**When**
- `result = [pairs(dao.list_by_workspace_with_initiator(db, workspace_id=w)) for w in (W0.id, W2.id)]` (one list comprehension).

**Then**
1. returns: `result == [[(X0.id, "Rahim")], [(X2.id, "Rahim")]]`.

### PTX-LW-03 — every status is listed
- **Rules:** `list_by_workspace_with_initiator` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T1`.
2. B = txn(2), but `created_at T1 + timedelta(minutes=1)`, paid.
3. C = txn(3), but `created_at T1 + timedelta(minutes=2)`, `status "VALIDATED_FAILED"`.
4. D = txn(4), but `created_at T1 + timedelta(minutes=3)`, `status "CANCELLED"`.
5. E = txn(5), but `created_at T1 + timedelta(minutes=4)`, `status "EXPIRED"`.
6. F = txn(6), but `created_at T1 + timedelta(minutes=5)`, `status "RISK_HOLD"`, `risk_level 1`, `risk_title "Card from abroad"`.
7. G = txn(7), but `created_at T1 + timedelta(minutes=6)`, `status "INIT_FAILED"`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t, _ in result] == [G.id, F.id, E.id, D.id, C.id, B.id, A.id]`.

### PTX-LW-04 — a workspace without payments, and an unknown workspace, give []
- **Rules:** `list_by_workspace_with_initiator` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`.

**When**
- `result = [dao.list_by_workspace_with_initiator(db, workspace_id=w) for w in (W1.id, MISSING)]` (one list comprehension).

**Then**
1. returns: `result == [[], []]`.

### PTX-LW-05 — each name is the row's initiator's, or None without one; items are plain 2-tuples
- **Rules:** `list_by_workspace_with_initiator` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T1`.
2. B = txn(2), but `created_at T2`, `initiated_by U2.id`, `risk_resolved_by U1.id`, `risk_resolved_at T3`.
3. C = txn(3), but `created_at T3`, `initiated_by None`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is list`.
2. returns: `[type(r) for r in result] == [tuple, tuple, tuple]`.
3. returns: `[len(r) for r in result] == [2, 2, 2]`.
4. returns: `pairs(result) == [(C.id, None), (B.id, "Karim"), (A.id, "Rahim")]`.

### PTX-LW-06 — newest created_at first, whatever the ids
- **Rules:** `list_by_workspace_with_initiator` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = txn(1), but `created_at T2`.
2. D = txn(2), but `created_at T4`.
3. A = txn(3), but `created_at T1`.
4. C = txn(4), but `created_at T3`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t, _ in result] == [D.id, C.id, B.id, A.id]`.

### PTX-LW-07 — the key is created_at, not initiated_at, updated_at, amount or tran_id
- **Rules:** `list_by_workspace_with_initiator` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T1`, `initiated_at T3`, `updated_at T3`, `amount Decimal("300.00")`.
2. B = txn(2), but `created_at T3`, `initiated_at T1`, `updated_at T1`, `amount Decimal("100.00")`.
3. C = txn(3), but `created_at T2`, `initiated_at T4`, `updated_at T1`, `amount Decimal("50.00")`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t, _ in result] == [B.id, C.id, A.id]`.

### PTX-LW-08 — on a tie, the tied rows each come once, between the newer and the older row
- **Rules:** `list_by_workspace_with_initiator` R3, R4 (the part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T2`.
2. O = txn(2), but `created_at T1`.
3. N = txn(3), but `created_at T3`.
4. B = txn(4), but `created_at T2`.
5. C = txn(5), but `created_at T2`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0][0].id == N.id`.
3. returns: `result[4][0].id == O.id`.
4. returns: `{t.id for t, _ in result[1:4]} == {A.id, B.id, C.id}`.

### PTX-LW-09 — on a tie the highest id comes first, even after the lowest id was updated
- **Rules:** `list_by_workspace_with_initiator` R4 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked among tied rows; physical row order decides)

**Given**
1. A = txn(1), but `created_at T2`.
2. B = txn(2), but `created_at T2`.
3. C = txn(3), but `created_at T2`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `[t.id for t, _ in result] == [C.id, B.id, A.id]`.

### PTX-LW-10 — on a tie the id decides, when tran_id, amount, name and the other times would sort otherwise
- **Rules:** `list_by_workspace_with_initiator` R4 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked among tied rows; physical row order decides)

**Given**
1. A = txn(3), but `created_at T2`, `initiated_at T3`, `updated_at T1`, `amount Decimal("100.00")`, `initiated_by U2.id`.
2. B = txn(1), but `created_at T2`, `initiated_at T1`, `updated_at T3`, `amount Decimal("300.00")`.
3. C = txn(2), but `created_at T2`, `initiated_at T2`, `updated_at T2`, `amount Decimal("200.00")`, `initiated_by None`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `pairs(result) == [(C.id, None), (B.id, "Rahim"), (A.id, "Karim")]`.

### PTX-LW-11 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `list_by_workspace_with_initiator` R4, R5 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)

**Given**
1. A = txn(1), but `created_at T2`.
2. B = txn(2), but `created_at T2`.
3. C = txn(3), but `created_at T2`.
4. D = txn(4), but `created_at T2`.
5. E = txn(5), but `created_at T2`.
6. seqscan.
7. bump(A).
8. bump(C).

**When**
- `pages = [dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0][0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### PTX-LW-12 — the query orders by created_at, then id, both descending
- **Rules:** `list_by_workspace_with_initiator` R3, R4 [BUG-2402]
- **Kind:** bug
- **Expect:** xfail BUG-2402
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = txn(1), but `created_at T2`.
2. Statement recorder.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(A.id, "Rahim")]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"created_at" in order_part`.
4. statement: `"payment_transactions.id" in order_part`.
5. statement: `order_part.index("created_at") < order_part.index("payment_transactions.id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### PTX-LW-13 — skip and limit cut a page out of the ordered list
- **Rules:** `list_by_workspace_with_initiator` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. C = txn(1), but `created_at T3`.
2. A = txn(2), but `created_at T1`.
3. E = txn(3), but `created_at T4 + timedelta(hours=1)`.
4. B = txn(4), but `created_at T2`.
5. D = txn(5), but `created_at T4`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `[t.id for t, _ in result] == [D.id, C.id]`.

### PTX-LW-14 — with the defaults, 101 rows give the 100 newest
- **Rules:** `list_by_workspace_with_initiator` R5 (default `limit=100`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(PaymentTransaction(workspace_id=W1.id, tran_id=f"b{k:03d}{TAG}", amount=Decimal("990.00"), currency="BDT", initiated_by=U1.id, initiated_at=T1, created_at=T1 + timedelta(minutes=k), updated_at=T1)); db.flush()` (one step).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0][0].tran_id == f"b100{TAG}"`.
3. returns: `result[99][0].tran_id == f"b001{TAG}"`.

### PTX-LW-15 — limit=1000 gives all 101 rows
- **Rules:** `list_by_workspace_with_initiator` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(PaymentTransaction(workspace_id=W1.id, tran_id=f"b{k:03d}{TAG}", amount=Decimal("990.00"), currency="BDT", initiated_by=U1.id, initiated_at=T1, created_at=T1 + timedelta(minutes=k), updated_at=T1)); db.flush()` (one step).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[100][0].tran_id == f"b000{TAG}"`.

### PTX-LW-16 — limit=0 returns an empty list
- **Rules:** `list_by_workspace_with_initiator` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PTX-LW-17 — a skip past the end returns an empty list; a skip just short of it returns the last row
- **Rules:** `list_by_workspace_with_initiator` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T1`.
2. B = txn(2), but `created_at T2`.

**When**
- `result = [dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, skip=s) for s in (1, 2)]` (one list comprehension).

**Then**
1. returns: `[[t.id for t, _ in page] for page in result] == [[A.id], []]`.

### PTX-LW-18 — the workspace filter comes before the page: newer rows of W0 and W2 take no place
- **Rules:** `list_by_workspace_with_initiator` R1, R5 (HR-5)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = txn(1), but `workspace_id W0.id`, `created_at T4`.
2. A = txn(2), but `created_at T2`.
3. B = txn(3), but `created_at T1`.
4. X2 = txn(4), but `workspace_id W2.id`, `created_at T3`.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, skip=0, limit=1)`.

**Then**
1. returns: `pairs(result) == [(A.id, "Rahim")]`.

### PTX-LW-19 — a negative limit raises DataError 2201W
- **Rules:** `list_by_workspace_with_initiator` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
2. nothing written: nothing written.

### PTX-LW-20 — a negative skip raises DataError 2201X
- **Rules:** `list_by_workspace_with_initiator` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = txn(1).

**When**
- `dao.list_by_workspace_with_initiator(db, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
2. nothing written: nothing written.

### PTX-LW-21 — one SELECT carries the names, no lock, nothing written
- **Rules:** `list_by_workspace_with_initiator` R7, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1), but `created_at T1`.
2. B = txn(2), but `created_at T2`, `initiated_by U2.id`.
3. `db.expunge_all()` (clear the session before a one-query check).
4. Statement recorder.

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(B.id, "Karim"), (A.id, "Rahim")]`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part == ""`.
4. statement: `written == []`.

### PTX-LW-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `list_by_workspace_with_initiator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1).
2. B = txn(2), but `workspace_id W2.id`.
3. `B.cus_name = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT")`, then `db.add(P)` (not flushed).

**When**
- `result = dao.list_by_workspace_with_initiator(db, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(A.id, "Rahim")]`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

## `PaymentTransactionDAO.get_stuck_initiated`

*The reconciliation sweep's batch: `INITIATED` checkouts started before the cutoff, all workspaces, oldest first, then id ascending (BUG-2403). Every test here starts with clean2001 (Conventions).*

### PTX-SI-01 — INITIATED rows started before the cutoff come back oldest first, whatever the ids
- **Rules:** `get_stuck_initiated` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = txn(1), but `initiated_at S2`.
2. C = txn(2), but `initiated_at S3`.
3. A = txn(3), but `initiated_at S1`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `type(result) is list`.
2. returns: `all(isinstance(r, PaymentTransaction) for r in result)`.
3. returns: `ids(result) == [A.id, B.id, C.id]`.

### PTX-SI-02 — a row started exactly at the cutoff is left out; one microsecond earlier is kept
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at CUT`.
2. B = txn(2), but `initiated_at CUT - US`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PTX-SI-03 — a row started one microsecond after the cutoff is left out
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at CUT + US`.
2. B = txn(2), but `initiated_at S1`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PTX-SI-04 — the cutoff is compared with initiated_at, not created_at or updated_at
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`, `created_at T1`, `updated_at T1`.
2. B = txn(2), but `initiated_at T1`, `created_at S1`, `updated_at S1`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PTX-SI-05 — status "initiated" in lower case is left out
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`, `status "initiated"`.
2. B = txn(2), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PTX-SI-06 — a status with a leading or a trailing space is left out
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`, `status " INITIATED"`.
2. B = txn(2), but `initiated_at S1`, `status "INITIATED "`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-SI-07 — a status that only starts with, or is part of, INITIATED is left out
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`, `status "INITIATE"`.
2. B = txn(2), but `initiated_at S1`, `status "INITIATED_X"`.
3. C = txn(3), but `initiated_at S1`, `status "INITIATE_"`.
4. D = txn(4), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [D.id]`.

### PTX-SI-08 — a paid row is left out
- **Rules:** `get_stuck_initiated` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`, paid.
2. B = txn(2), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PTX-SI-09 — rows of every workspace come back together, oldest first
- **Rules:** `get_stuck_initiated` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = txn(1), but `workspace_id W2.id`, `initiated_at S1`.
2. A = txn(2), but `initiated_at S3`.
3. X0 = txn(3), but `workspace_id W0.id`, `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [X2.id, X0.id, A.id]`.

### PTX-SI-10 — on a tie, the tied rows each come once, between the older and the newer row
- **Rules:** `get_stuck_initiated` R3 (the part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S2`.
2. N = txn(2), but `initiated_at S3`.
3. O = txn(3), but `initiated_at S1`.
4. B = txn(4), but `initiated_at S2`.
5. C = txn(5), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == O.id`.
3. returns: `result[4].id == N.id`.
4. returns: `idset(result[1:4]) == {A.id, B.id, C.id}`.

### PTX-SI-11 — on a tie the lowest id comes first, when tran_id, amount and created_at would sort otherwise
- **Rules:** `get_stuck_initiated` R3 [BUG-2403]
- **Kind:** bug
- **Expect:** xfail BUG-2403 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked among tied rows; physical row order decides)

**Given**
1. A = txn(3), but `initiated_at S2`, `created_at T3`, `amount Decimal("300.00")`, `initiated_by U2.id`.
2. B = txn(1), but `initiated_at S2`, `created_at T1`, `amount Decimal("100.00")`.
3. C = txn(2), but `initiated_at S2`, `created_at T2`, `amount Decimal("200.00")`, `initiated_by None`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PTX-SI-12 — on a tie across workspaces the lowest id comes first
- **Rules:** `get_stuck_initiated` R2, R3 [BUG-2403]
- **Kind:** bug
- **Expect:** xfail BUG-2403 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked among tied rows; physical row order decides)

**Given**
1. X2 = txn(1), but `workspace_id W2.id`, `initiated_at S2`.
2. X0 = txn(2), but `workspace_id W0.id`, `initiated_at S2`.
3. A = txn(3), but `initiated_at S2`.
4. seqscan.
5. bump(X2).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [X2.id, X0.id, A.id]`.

### PTX-SI-13 — with more tied rows than the limit, the lowest ids fill the batch
- **Rules:** `get_stuck_initiated` R3, R4 [BUG-2403]
- **Kind:** bug
- **Expect:** xfail BUG-2403 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (which tied rows fill the batch rests on physical row order)

**Given**
1. A = txn(1), but `initiated_at S2`.
2. B = txn(2), but `initiated_at S2`.
3. C = txn(3), but `initiated_at S2`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PTX-SI-14 — the query orders by initiated_at, then id, both ascending
- **Rules:** `get_stuck_initiated` R3 [BUG-2403]
- **Kind:** bug
- **Expect:** xfail BUG-2403
- **Fails today on:** Then 4 (the query orders by `initiated_at` alone)

**Given**
1. A = txn(1), but `initiated_at S1`.
2. Statement recorder.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"initiated_at" in order_part`.
4. statement: `"payment_transactions.id" in order_part`.
5. statement: `order_part.index("initiated_at") < order_part.index("payment_transactions.id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### PTX-SI-15 — limit=2 with three stuck rows gives the two oldest
- **Rules:** `get_stuck_initiated` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. C = txn(1), but `initiated_at S3`.
2. A = txn(2), but `initiated_at S1`.
3. B = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PTX-SI-16 — with the default limit, 201 stuck rows give the 200 oldest
- **Rules:** `get_stuck_initiated` R4 (default `limit=200`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(201): db.add(PaymentTransaction(workspace_id=W1.id, tran_id=f"b{k:03d}{TAG}", amount=Decimal("990.00"), currency="BDT", initiated_by=U1.id, initiated_at=OLD + timedelta(minutes=k), created_at=T1, updated_at=T1)); db.flush()` (one step).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `len(result) == 200`.
2. returns: `result[0].tran_id == f"b000{TAG}"`.
3. returns: `result[199].tran_id == f"b199{TAG}"`.

### PTX-SI-17 — limit=1000 gives all 201 stuck rows
- **Rules:** `get_stuck_initiated` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(201): db.add(PaymentTransaction(workspace_id=W1.id, tran_id=f"b{k:03d}{TAG}", amount=Decimal("990.00"), currency="BDT", initiated_by=U1.id, initiated_at=OLD + timedelta(minutes=k), created_at=T1, updated_at=T1)); db.flush()` (one step).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=1000)`.

**Then**
1. returns: `len(result) == 201`.
2. returns: `result[200].tran_id == f"b200{TAG}"`.

### PTX-SI-18 — limit=0 returns an empty list
- **Rules:** `get_stuck_initiated` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=0)`.

**Then**
1. returns: `result == []`.

### PTX-SI-19 — a negative limit raises DataError 2201W
- **Rules:** `get_stuck_initiated` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`.

**When**
- `dao.get_stuck_initiated(db, older_than=CUT, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
2. nothing written: nothing written.

### PTX-SI-20 — the filters come before the limit: older rows that are not candidates take no place
- **Rules:** `get_stuck_initiated` R1, R4 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at OLD`, paid.
2. B = txn(2), but `initiated_at OLD`, `status "initiated"`.
3. C = txn(3), but `initiated_at S2`.
4. D = txn(4), but `initiated_at S3`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-SI-21 — one SELECT, no lock, nothing written
- **Rules:** `get_stuck_initiated` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`.
2. Statement recorder.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `len(selects) == 1`.
3. statement: `lock_part == ""`.
4. statement: `written == []`.

### PTX-SI-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_stuck_initiated` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = txn(1), but `initiated_at S1`.
2. B = txn(2), but `initiated_at T1`.
3. `B.cus_name = "Edited"` (not flushed).
4. `P = PaymentTransaction(workspace_id=W1.id, tran_id=tid(3), amount=Decimal("990.00"), currency="BDT", initiated_at=S2, created_at=T1, updated_at=T1)`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. nothing written: nothing written.

### PTX-SI-23 — a naive cutoff is compared as stored, whatever the session's time zone
- **Rules:** `get_stuck_initiated` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone(`"Asia/Dhaka"`).
2. A = txn(1), but `initiated_at CUT - US`.
3. B = txn(2), but `initiated_at CUT`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PTX-SI-24 — an aware UTC cutoff under a UTC session splits at the same instant
- **Rules:** `get_stuck_initiated` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone(`"UTC"`).
2. A = txn(1), but `initiated_at CUT - US`.
3. B = txn(2), but `initiated_at CUT`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUTZ)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PTX-SI-25 — an aware cutoff under Asia/Dhaka is read in Dhaka time (today's documented behaviour)
- **Rules:** `get_stuck_initiated` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone(`"Asia/Dhaka"`).
2. A = txn(1), but `initiated_at datetime(2001, 3, 1, 17, 59, 59, 999999)`.
3. B = txn(2), but `initiated_at datetime(2001, 3, 1, 18, 0, 0)`.
4. C = txn(3), but `initiated_at S3`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUTZ)`.

**Then**
1. returns: `ids(result) == [C.id, A.id]`.

## Deferred to the payment portal — OQ-25

*`get_stuck_initiated` R7, today's behaviour, deferred by the owner to the payment portal (2026-11-10): rows whose outcome was set without gateway verification (`EXPIRED`, `CANCELLED`, `VALIDATED_FAILED`), and `INIT_FAILED` / `RISK_HOLD` rows, are never sweep candidates, whatever their age; the selection is by `status` alone. When the portal decides, these cards are rewritten or retired and no other card changes. Each card starts with clean2001 and puts the excluded rows both 1 hour before the cutoff (inside 72 hours) and 59 days before it (OLD).*

### PTX-OQ25-01 — EXPIRED rows, recent or old, are not candidates
- **Rules:** `get_stuck_initiated` R7
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at OLD`, `status "EXPIRED"`.
2. B = txn(2), but `initiated_at S3`, `status "EXPIRED"`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-OQ25-02 — CANCELLED rows, recent or old, are not candidates
- **Rules:** `get_stuck_initiated` R7
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at OLD`, `status "CANCELLED"`.
2. B = txn(2), but `initiated_at S3`, `status "CANCELLED"`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-OQ25-03 — VALIDATED_FAILED rows, recent or old, are not candidates
- **Rules:** `get_stuck_initiated` R7
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at OLD`, `status "VALIDATED_FAILED"`, `val_id "val-fail-1"`.
2. B = txn(2), but `initiated_at S3`, `status "VALIDATED_FAILED"`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-OQ25-04 — INIT_FAILED rows are not candidates
- **Rules:** `get_stuck_initiated` R7
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at OLD`, `status "INIT_FAILED"`.
2. B = txn(2), but `initiated_at S3`, `status "INIT_FAILED"`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-OQ25-05 — RISK_HOLD rows are not candidates
- **Rules:** `get_stuck_initiated` R7
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at OLD`, `status "RISK_HOLD"`, `val_id "val-hold-1"`, `risk_level 1`, `risk_title "Card from abroad"`, `validated_at S1`.
2. B = txn(2), but `initiated_at S3`, `status "RISK_HOLD"`, `val_id "val-hold-2"`, `risk_level 1`, `risk_title "Card from abroad"`, `validated_at S3`.
3. C = txn(3), but `initiated_at S2`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PTX-OQ25-06 — older closed rows take no place in a batch of one
- **Rules:** `get_stuck_initiated` R7, R4
- **Kind:** boundary
- **Expect:** pass
- **Deferred:** OQ-25 — today's behaviour; the payment portal decides, and only these cards change

**Given**
1. A = txn(1), but `initiated_at S1`, `status "EXPIRED"`.
2. B = txn(2), but `initiated_at S1`, `status "CANCELLED"`.
3. C = txn(3), but `initiated_at S1`, `status "VALIDATED_FAILED"`.
4. D = txn(4), but `initiated_at S3`.

**When**
- `result = dao.get_stuck_initiated(db, older_than=CUT, limit=1)`.

**Then**
1. returns: `ids(result) == [D.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_tran_id_for_update` R2 (the wait) | integration test | A second session's locked read of the same `tran_id` waits until the first commits, then sees the new status. |
| `get_by_id_and_workspace_with_initiator` R5 (the wait) | integration test, after BUG-029 | Two `resolve_risk` calls on one held payment: the second waits, sees the resolved status and gets the normal 400. |
| FU-1 | `PaymentTransactionManager.resolve_risk` | It calls `get_by_id_and_workspace_with_initiator(…, for_update=True)` (BUG-029). |
| FU-2 (a) | `PaymentTransactionService.get_transaction_by_tran_id` / `GET /payments/{tran_id}/` | `None` (unknown or another workspace's `tran_id`) becomes 404 `Payment transaction {tran_id} not found`; `list_transactions` passes `skip` / `limit` through. |
| FU-2 (b) | payments endpoints (mock gateway) | The mock pages read across workspaces by `tran_id` (mock only, TODO-001). |
| FU-2 (c), OQ-25 | payment portal work (`PaymentTransactionManager.reconcile_stuck_transactions`) | If the portal widens the sweep: its second candidate read and its "at most once per run" rule. |
| `list_by_workspace_with_initiator` R6 (HR-7 bounds) | `GET /payments/` | `skip >= 0`, `1 <= limit <= 200` give 422 before the DAO is reached. |
| `get_stuck_initiated` R6 (naive cutoff) | `PaymentTransactionManager.reconcile_stuck_transactions` | The manager passes `utcnow() - older_than_minutes`, naive UTC. |
| inherited `create` R3 (valid values) | manager spec `initiate_payment` R9, R9a, R10a | Status and amount are validated before the insert. |

## Spec gaps
None. Revision 1's gaps are closed by the spec's Gap log (2026-11-10):
- Gap 1 (equal times in R1): closed by G1. Three separate calls, no equality card; PTX-CR-01 unchanged.
- Gap 2 (amount bounds): closed by G2. R1b and Errors row 3; PTX-CR-22, CR-23, CR-24.
- Gap 3 (`outcome_verified` split): closed by G3. R7 is status-only; PTX-OQ25-02, OQ25-03 unchanged.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| inherited `create` | R1 | PTX-CR-01, CR-02, CR-03, CR-16 |
| inherited `create` | R1a [BUG-2401] | PTX-CR-17 (pass control), CR-18, CR-19, CR-20, CR-21 |
| inherited `create` | R1b / Errors row 3 (14+ integer digits) | PTX-CR-22, CR-23, CR-24 |
| inherited `create` | R2 / Errors row 1 (`tran_id` taken) | PTX-CR-09, CR-10, CR-11 |
| inherited `create` | R2 / Errors row 2 (> 30 chars) | PTX-CR-12, CR-13 |
| inherited `create` | R3 (any status, any amount; HR-15 on the column) | PTX-CR-04, CR-05, CR-06, CR-07, CR-08, CR-14, CR-15 |
| inherited `create` | Side effects | PTX-CR-01, CR-02, CR-03 |
| `get_by_tran_id` | R1 | PTX-TI-01, TI-02, TI-03, TI-04, TI-05 |
| `get_by_tran_id` | R2 | PTX-TI-06 … TI-16 |
| `get_by_tran_id` | R3 / Side effects | PTX-TI-02, TI-03, TI-17, TI-18 |
| `get_by_tran_id_for_update` | R1 | PTX-TU-01 … TU-10 |
| `get_by_tran_id_for_update` | R2 | PTX-TU-11, TU-12, TU-14 (wait: deferred) |
| `get_by_tran_id_for_update` | R3 | PTX-TU-04, TU-12 |
| `get_by_tran_id_for_update` | R4 | covered by the unique `tran_id` (PTX-CR-09, CR-10); no other card possible |
| `get_by_tran_id_for_update` | Side effects | PTX-TU-13, TU-14 |
| `get_by_id_and_workspace_with_initiator` | R1 / Returns | PTX-IW-01, IW-02 |
| `get_by_id_and_workspace_with_initiator` | R2 | PTX-IW-03, IW-04 |
| `get_by_id_and_workspace_with_initiator` | R3 | PTX-IW-05 … IW-10 |
| `get_by_id_and_workspace_with_initiator` | R4 | PTX-IW-11, IW-17 |
| `get_by_id_and_workspace_with_initiator` | R5 [BUG-029] | PTX-IW-13, IW-14, IW-15, IW-16, IW-17, IW-18 |
| `get_by_id_and_workspace_with_initiator` | Side effects | PTX-IW-11, IW-12, IW-18 |
| `get_by_tran_id_and_workspace_with_initiator` | R1 / Returns | PTX-TW-01, TW-02, TW-03, TW-14 |
| `get_by_tran_id_and_workspace_with_initiator` | R2 | PTX-TW-04 … TW-13 |
| `get_by_tran_id_and_workspace_with_initiator` | R3 / Side effects | PTX-TW-15, TW-16 |
| `list_by_workspace_with_initiator` | R1 | PTX-LW-01, LW-02, LW-03, LW-04, LW-18 |
| `list_by_workspace_with_initiator` | R2 / Returns | PTX-LW-05, LW-21 |
| `list_by_workspace_with_initiator` | R3 | PTX-LW-06, LW-07, LW-08 |
| `list_by_workspace_with_initiator` | R4 [BUG-2402] | PTX-LW-08 (pass half), LW-09, LW-10, LW-11 (non-strict), LW-12 (strict) |
| `list_by_workspace_with_initiator` | R5 | PTX-LW-13 … LW-18 |
| `list_by_workspace_with_initiator` | R6 / Errors row 1 | PTX-LW-19, LW-20 |
| `list_by_workspace_with_initiator` | R7 / Side effects | PTX-LW-21, LW-22 |
| `get_stuck_initiated` | R1 / Returns | PTX-SI-01 … SI-08 |
| `get_stuck_initiated` | R2 | PTX-SI-09, SI-12 |
| `get_stuck_initiated` | R3 [BUG-2403] | PTX-SI-01, SI-09, SI-10 (pass half), SI-11, SI-12, SI-13 (non-strict), SI-14 (strict) |
| `get_stuck_initiated` | R4 / Errors row 1 | PTX-SI-13, SI-15 … SI-20 |
| `get_stuck_initiated` | R5 / Side effects | PTX-SI-21, SI-22 |
| `get_stuck_initiated` | R6 | PTX-SI-23, SI-24, SI-25 |
| `get_stuck_initiated` | R7 (deferred to the payment portal, OQ-25) | PTX-OQ25-01 … OQ25-06 |
