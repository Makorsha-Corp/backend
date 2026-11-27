# Test cases — `app/dao/product_ledger.py`

> **Spec:** `tests/unit/dao/product_ledger.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). P1 … P4 and Q1 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `product_ledger.verify.md`: Finding 1 (R-1) → PLG-GW-66; Finding 2 (R-2) → PLG-EX-19; Finding 3 (R-3) → PLG-GW-65. No other card changed, none retired.
> **Counts:** 95 cases · 86 expected-to-pass · 9 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 66 (8 bug) · `exists_for_production_batch` 19 · `inherited` 10 (1 bug).
- **Depth:** full (skill step 1a): the stock history, and `exists_for_production_batch` is the only guard against posting a batch twice. `create`, `update`, `remove` each have one commit spy.
- **Expected-to-fail:** BUG-640 4 (1 strict, 3 non-strict) · BUG-992 4 (4 strict, 0 non-strict) · BUG-1337 1 (1 strict, 0 non-strict).
- **Notable design choices:**
  - Different times are ordered today, so nearly every list card compares the order; only the tied cards are non-strict. Every Given sets `performed_at` by hand, as the Notes say.
  - BUG-640: one strict SQL recorder, two non-strict tie cards (the second with type, quantity, user and source not rising with id, and an older row holding the highest id), one windows card.
  - BUG-992: Dhaka and New York strict, UTC pass. Two extra strict cards send one aware bound alone, so a fix that converts only one bound fails. Both follow from the spec's Today note; neither was run.
  - BUG-991 is integration-only, so a Deferred entry. GW has a pass card for what the DAO does with midnight.
  - `exists_for_production_batch` R3 reads a constant, so "exact compare" is tested on the stored side only: capitals, a leading space, a part, `-` for `_`.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none; the double-post race is the manager's (FU-1 (a)).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PLG` = `app/dao/product_ledger.py`. `GW` get_by_workspace · `EX` exists_for_production_batch · `INH` inherited `BaseDAO` methods on `ProductLedger`.

**Actors and fixed values.**
- `dao` = the singleton `product_ledger_dao` (`from app.dao.product_ledger import product_ledger_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductLedger` = `app.models.product_ledger.ProductLedger`. `ProductLedgerCreate`, `ProductLedgerUpdate` = the schemas of `app.schemas.product_ledger`. `Product` = `app.models.product.Product`. `Item` = `app.models.item.Item`. `Factory` = `app.models.factory.Factory`. `utcnow` = `app.utils.time.utcnow`. `Decimal` = `decimal.Decimal`. `datetime`, `timedelta`, `timezone` = the `datetime` module's classes. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.
- T9 … T12 = `datetime(2026, 3, 1, 9, 0, 0)` … `datetime(2026, 3, 1, 12, 0, 0)`, one day. Z(h, m) = `datetime(2026, 3, 1, h, m, tzinfo=timezone.utc)`, an aware bound.

**Externals.** None. `performed_at` is a column default, so a patch would not reach it: the one card on its value compares with the real `utcnow()`. Every other Given sets `performed_at` by hand.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`. FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T9`, `deleted_by U1.id` (soft-deleted). F9 = the same, but `name "Far Plant"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. I2 = the same, but `name "Cam"`, `name_normalized "cam"`. IX = the same, but `name "Old Gasket"`, `name_normalized "old gasket"`, `is_active False` (removed). I9 = the same, but `name "Far Crate"`, `name_normalized "far crate"`, `workspace_id W2.id`.
- **entry** = `ProductLedger(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=...)`; the card always gives `performed_at` and every other column that differs. No `product_ledger` row exists unless the card's Given lists it.
- **posted** (for `exists_for_production_batch`) = an entry with `performed_at T10`, `source_type "production_batch"`, and the card's `source_id`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `product_ledger` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.
- **Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line. `NotNullViolation` = class of `psycopg2.errors`.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `product_ledger`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductLedgerDAO.get_by_workspace`

### PLG-GW-01 — with no filters: a list of the workspace's rows, newest first
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T11`.
2. B = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], ProductLedger)`.

### PLG-GW-02 — a newer row of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `performed_at T11`.
2. Z = entry, `performed_at T12`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-03 — an earlier-id row of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = entry, `performed_at T12`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.
2. A = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PLG-GW-05 — factory_id narrows to that factory
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `factory_id F2.id`.
2. A = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-06 — factory_id=0 returns an empty list: 0 is a filter
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### PLG-GW-07 — factory_id=None applies no filter
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`, `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=None)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PLG-GW-08 — item_id narrows to that item
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `item_id I2.id`.
2. A = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-09 — item_id=0 returns an empty list: 0 is a filter
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### PLG-GW-10 — item_id=None applies no filter
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=None)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PLG-GW-11 — a row at exactly start_date is returned
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=T11)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### PLG-GW-12 — a row one second before start_date is not returned
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=T11 + timedelta(seconds=1))`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PLG-GW-13 — a row at exactly end_date is returned
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=T11)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PLG-GW-14 — a row one second after end_date is not returned
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=T11 - timedelta(seconds=1))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-15 — both bounds keep the range, inclusive
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=T10, end_date=T11)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PLG-GW-16 — equal bounds keep the row at that instant
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=T11, end_date=T11)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-17 — an inverted range returns an empty list, with no error
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=T12, end_date=T10)`.

**Then**
1. returns: `result == []`.

### PLG-GW-18 — a date with no time reaches the DAO as midnight, compared as given
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 1, 0, 0, 0))`.

**Then**
1. returns: `result == []`.

### PLG-GW-19 — aware bounds find the row under UTC
- **Rules:** `get_by_workspace` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=Z(11, 30), end_date=Z(12, 30))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-20 — aware bounds find the row under Asia/Dhaka
- **Rules:** `get_by_workspace` R4a [BUG-992]
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the bounds are compared through the session's `TimeZone`, so `[]` comes back)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=Z(11, 30), end_date=Z(12, 30))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-21 — aware bounds find the row under America/New_York
- **Rules:** `get_by_workspace` R4a [BUG-992]
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the bounds are compared through the session's `TimeZone`, so `[]` comes back)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=Z(11, 30), end_date=Z(12, 30))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-22 — an aware start_date alone is converted too
- **Rules:** `get_by_workspace` R4a [BUG-992]
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the row reads as 06:00 UTC under Dhaka, before the bound)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=Z(11, 30))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-23 — an aware end_date alone is converted too
- **Rules:** `get_by_workspace` R4a [BUG-992]
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the row reads as 06:00 UTC under Dhaka, before the bound, so it is returned)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=Z(11, 30))`.

**Then**
1. returns: `result == []`.

### PLG-GW-24 — transaction_type keeps the rows of that type
- **Rules:** `get_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `transaction_type "return"`.
2. A = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="sale")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-25 — capitals do not match
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="SALE")`.

**Then**
1. returns: `result == []`.

### PLG-GW-26 — a leading space does not match
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type=" sale")`.

**Then**
1. returns: `result == []`.

### PLG-GW-27 — the start of a type does not match
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="sal")`.

**Then**
1. returns: `result == []`.

### PLG-GW-28 — the end of a type does not match
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="ale")`.

**Then**
1. returns: `result == []`.

### PLG-GW-29 — _ is no wildcard
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="s_le")`.

**Then**
1. returns: `result == []`.

### PLG-GW-30 — % is no wildcard
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="%")`.

**Then**
1. returns: `result == []`.

### PLG-GW-31 — a space alone is a filter and finds nothing
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type=" ")`.

**Then**
1. returns: `result == []`.

### PLG-GW-32 — a stored type with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `transaction_type " sale"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="sale")`.

**Then**
1. returns: `result == []`.

### PLG-GW-33 — a stored type in capitals is not found
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `transaction_type "SALE"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="sale")`.

**Then**
1. returns: `result == []`.

### PLG-GW-34 — transaction_type="" applies no filter
- **Rules:** `get_by_workspace` R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`, `transaction_type "return"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="")`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PLG-GW-35 — transaction_type=None applies no filter
- **Rules:** `get_by_workspace` R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`, `transaction_type "return"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type=None)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PLG-GW-36 — all the filters combine with AND
- **Rules:** `get_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T11`.
2. B = entry, `performed_at T11`, `factory_id F2.id`.
3. C = entry, `performed_at T11`, `item_id I2.id`.
4. G = entry, `performed_at T9`.
5. H = entry, `performed_at T12`.
6. J = entry, `performed_at T11`, `transaction_type "return"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, start_date=T10, end_date=T11, transaction_type="sale")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-37 — two filters no row meets together return an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `factory_id F2.id`.
2. Y = entry, `performed_at T11`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F2.id, item_id=I2.id)`.

**Then**
1. returns: `result == []`.

### PLG-GW-38 — the factory filter runs before the page
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `factory_id F2.id`.
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-39 — the item filter runs before the page
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `item_id I2.id`.
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=I1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-40 — the type filter runs before the page
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`, `transaction_type "return"`.
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="sale", skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-41 — the date filter runs before the page
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, `performed_at T12`.
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=T11, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-42 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_workspace` R7 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = entry, `performed_at T12`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### PLG-GW-43 — tied rows: the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_workspace` R7 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T11`.
4. C = entry, `performed_at T11`.
5. `A.notes = "Changed"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### PLG-GW-44 — tied rows: the id decides, when type, quantity, user and source would each sort otherwise, and an older row has the highest id
- **Rules:** `get_by_workspace` R7 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = entry, `performed_at T11`, `transaction_type "return"`, `quantity 7`, `performed_by U2.id`, `source_id 30`.
3. B = entry, `performed_at T11`, `transaction_type "sale"`, `quantity 9`, `performed_by U1.id`, `source_id 10`.
4. C = entry, `performed_at T11`, `transaction_type "adjust"`, `quantity 5`, `performed_by U2.id`, `source_id 20`.
5. D = entry, `performed_at T10`, `transaction_type "zero"`, `quantity 1`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### PLG-GW-45 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R7 [BUG-640], R8
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T11`.
4. C = entry, `performed_at T11`.
5. D = entry, `performed_at T11`.
6. E = entry, `performed_at T11`.
7. `A.notes = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### PLG-GW-46 — the later time comes first, whatever the ids
- **Rules:** `get_by_workspace` R7a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T12`.
3. C = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### PLG-GW-47 — an older row with the higher id inside one day comes after
- **Rules:** `get_by_workspace` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### PLG-GW-48 — the order is applied before the page is cut
- **Rules:** `get_by_workspace` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`.
2. B = entry, `performed_at T12`.
3. C = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### PLG-GW-49 — with the defaults 101 rows give 100
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries E1 … E101, built with `add_all`: Ek = entry, `performed_at` = `T9 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### PLG-GW-50 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries E1 … E101, built with `add_all`: Ek = entry, `performed_at` = `T9 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### PLG-GW-51 — skip and limit cut one row from the middle
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.
3. C = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-52 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PLG-GW-53 — limit=1 returns one row
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-54 — skip at the number of rows returns an empty list
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLG-GW-55 — skip at the last row returns one row
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-56 — a negative limit raises
- **Rules:** `get_by_workspace` R10, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLG-GW-57 — a negative skip raises
- **Rules:** `get_by_workspace` R10, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLG-GW-58 — the row of a soft-deleted factory is returned
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `factory_id FD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-59 — the row of a soft-deleted factory is returned, filtered by that factory
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `factory_id FD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-60 — the row of a removed item is returned
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `item_id IX.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-61 — the row of a removed item is returned, filtered by that item
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `item_id IX.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=IX.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PLG-GW-62 — the query does not read the parent tables
- **Rules:** `get_by_workspace` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `factory_id FD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.
3. statement: `"factories" not in sql`.

### PLG-GW-63 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at T11`.
2. `P = ProductLedger(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=T12)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PLG-GW-64 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### PLG-GW-65 — another workspace's row sorts first and takes no place in the page
- **Rules:** `get_by_workspace` R1, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = entry, `performed_at T12`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.
2. A = entry, `performed_at T11`.
3. B = entry, `performed_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PLG-GW-66 — bounds at +06:00 are converted, under UTC
- **Rules:** `get_by_workspace` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at T12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 1, 17, 30, tzinfo=timezone(timedelta(hours=6))), end_date=datetime(2026, 3, 1, 18, 30, tzinfo=timezone(timedelta(hours=6))))`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `ProductLedgerDAO.exists_for_production_batch`

### PLG-EX-01 — one matching row gives True
- **Rules:** `exists_for_production_batch` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is True`.

### PLG-EX-02 — several matching rows give True
- **Rules:** `exists_for_production_batch` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.
2. B = posted, `source_id 88`, `transaction_type "production_output"`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is True`.

### PLG-EX-03 — a batch with no ledger row gives False
- **Rules:** `exists_for_production_batch` R2, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-04 — another batch gives False
- **Rules:** `exists_for_production_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = posted, `source_id 87`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-05 — batch_id=0 gives False
- **Rules:** `exists_for_production_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=0)`.

**Then**
1. returns: `result is False`.

### PLG-EX-06 — an unknown batch gives False
- **Rules:** `exists_for_production_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=MISSING)`.

**Then**
1. returns: `result is False`.

### PLG-EX-07 — the row's own id is not the batch id
- **Rules:** `exists_for_production_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = posted, `source_id 999999998`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=A.id)`.

**Then**
1. returns: `result is False`.

### PLG-EX-08 — the same source_id under sales_delivery gives False
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type "sales_delivery"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-09 — a row with no source_type gives False
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-10 — a stored source_type in capitals does not count
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type "PRODUCTION_BATCH"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-11 — a stored source_type with a leading space does not count
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type " production_batch"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-12 — a part of the source_type does not count
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type "production"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-13 — another separator does not count: _ is no wildcard
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type "production-batch"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-14 — a matching row under another workspace gives False
- **Rules:** `exists_for_production_batch` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = posted, `source_id 88`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-15 — a matching row of W1 gives False for W2
- **Rules:** `exists_for_production_batch` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W2.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

### PLG-EX-16 — the W1 row answers W1, when W2's row is the earlier one
- **Rules:** `exists_for_production_batch` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = posted, `source_id 88`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.
2. A = posted, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is True`.

### PLG-EX-17 — writes nothing: a pending matching row stays pending and does not count
- **Rules:** `exists_for_production_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = posted, `source_id 87`.
2. `P = ProductLedger(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=T12, source_type="production_batch", source_id=88)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PLG-EX-18 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `exists_for_production_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = posted, `source_id 88`.
2. B = posted, `source_id 87`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is True`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### PLG-EX-19 — a stored source_type that extends the constant does not count
- **Rules:** `exists_for_production_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T10`, `source_type "production_batch_v2"`, `source_id 88`.

**When**
- `result = dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)`.

**Then**
1. returns: `result is False`.

## Inherited `BaseDAO` methods on `ProductLedger`

### PLG-INH-01 — create with a ProductLedgerCreate fails on flush and saves nothing
- **Rules:** `inherited` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductLedgerCreate(factory_id=F1.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. count: `product_ledger` has exactly 0 rows.

### PLG-INH-02 — create with a dict and no performed_at sets it
- **Rules:** `inherited` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "item_id": I1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_at is not None`.
3. re-read the returned row: `quantity == 1`, `qty_before == 5`, `qty_after == 4`.

### PLG-INH-03 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "item_id": I1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `product_ledger` has exactly 1 row.
3. count: after the savepoint rollback, `product_ledger` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

### PLG-INH-04 — create changes no stock row
- **Rules:** `inherited` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = `Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=5)`, added and flushed.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "item_id": I1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(S).

### PLG-INH-05 — performed_at is within a minute of UTC, under Asia/Dhaka
- **Rules:** `inherited` R2a [BUG-1337]
- **Kind:** bug
- **Expect:** xfail BUG-1337
- **Fails today on:** Then 2 (the database's `now()` is six hours ahead of UTC under Dhaka)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "item_id": I1.id, "transaction_type": "sale", "quantity": 1, "qty_before": 5, "qty_after": 4})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `abs(performed_at - utcnow()) < timedelta(minutes=1)`.

### PLG-INH-06 — update with a ProductLedgerUpdate changes notes
- **Rules:** `inherited` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`, `notes "Old"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductLedgerUpdate(notes="New"))`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `notes == "New"`.
3. unchanged: unchanged(A) except `notes`.

### PLG-INH-07 — update with a dict changes any column
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"quantity": 9})`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `quantity == 9`.

### PLG-INH-08 — update is flushed, not committed: a rollback restores the row
- **Rules:** `inherited` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=A, obj_in={"quantity": 9})`.

**Then**
1. returns: `result.id == A.id`.
2. count: inside the savepoint, `product_ledger` has exactly 1 row with `quantity` 9.
3. count: after the savepoint rollback, `product_ledger` has exactly 1 row with `quantity` 1.
4. mock called: the `db.commit` spy was never called.

### PLG-INH-09 — remove hard-deletes the row
- **Rules:** `inherited` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. B = entry, `performed_at T11`.

**When**
- `result = dao.remove(db, id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: `product_ledger` has exactly 1 row.
3. unchanged: unchanged(B).

### PLG-INH-10 — remove is flushed, not committed: a rollback brings the row back
- **Rules:** `inherited` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at T12`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove(db, id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: inside the savepoint, `product_ledger` has exactly 0 rows.
3. count: after the savepoint rollback, `product_ledger` has exactly 1 row.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-991 — an `end_date` with no time means the end of that day; a value with a time stays exact | `GET /products/ledger/`, integration-only | **Stock.** The fix is at the endpoint. PLG GW pins what the DAO does with midnight. |
| FU-1 (a) — HR-10: the double-post guard is a read before the writes, with no lock and no index | `ProductionBatchManager.post_outputs_to_finished_goods` | **Stock, owner.** Two posts at once book the output twice. The key needs thought: one row per line in `complete_batch`, merged in the other path. |
| FU-1 (b) — `complete_batch` already posts; two routes post | `ProductionBatchManager`, `/products/receive-from-batch/{id}/` | **Stock.** Check the flow. |
| FU-2 — `inventory_ledger.performed_at` has the same database-clock default as BUG-1337 | `app/models/inventory_ledger.py` | **Stock.** Not logged. Fix or log it with BUG-1337. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /products/ledger/` | Endpoint rule; the DAO's own negatives are the Errors cards. |
| Generic behavior of inherited methods; `get`, `get_multi`, `get_by_id_and_workspace` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton; dead `get_by_id_and_workspace` override (P4) | none | No logic / to be removed. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts: `ProductLedgerCreate` | **Stock.** The schema's fields are not listed, only that it has no `workspace_id` and no `performed_by`. | PLG-INH-01 passes the six the table needs. If the schema asks for another, the card's call changes, not its Then. |
| 2 | Model facts: relationships | **Stock.** The spec names no `lazy="joined"` relationship on `ProductLedger`, and the "JOIN" not in sql card assumes there is none. | If one exists that card needs narrowing; R11's row cards stand. |
| 3 | `get_by_workspace` R4a | **Stock.** One bound alone is not stated, though the Branch map has a branch for each. The Today note gives the session's `TimeZone` as the cause, from which the two cards follow. | The two strict cards are derived, not verified. If one XPASSes, that card needs the spec's word. |
| 4 | `exists_for_production_batch` R1 | **Stock.** A row with `quantity 0`, or a later reversal of a posting, has no stated meaning: any row counts. | No card beyond R1. |
| 5 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | PLG-GW-01 |
| `get_by_workspace` | R1 | PLG-GW-01, PLG-GW-02, PLG-GW-03, PLG-GW-04, PLG-GW-65 |
| `get_by_workspace` | R2 | PLG-GW-05, PLG-GW-06, PLG-GW-07 |
| `get_by_workspace` | R3 | PLG-GW-08, PLG-GW-09, PLG-GW-10 |
| `get_by_workspace` | R4 | PLG-GW-11, PLG-GW-12, PLG-GW-13, PLG-GW-14, PLG-GW-15, PLG-GW-16, PLG-GW-17, PLG-GW-18 |
| `get_by_workspace` | R4a | PLG-GW-19, PLG-GW-66 |
| `get_by_workspace` | R4a [BUG-992] | PLG-GW-20, PLG-GW-21, PLG-GW-22, PLG-GW-23 |
| `get_by_workspace` | R5 | PLG-GW-24, PLG-GW-25, PLG-GW-26, PLG-GW-27, PLG-GW-28, PLG-GW-29, PLG-GW-30, PLG-GW-31, PLG-GW-32, PLG-GW-33 |
| `get_by_workspace` | R5a | PLG-GW-34, PLG-GW-35 |
| `get_by_workspace` | R6 | PLG-GW-36, PLG-GW-37, PLG-GW-38, PLG-GW-39, PLG-GW-40, PLG-GW-41, PLG-GW-65 |
| `get_by_workspace` | R7 [BUG-640] | PLG-GW-42, PLG-GW-43, PLG-GW-44, PLG-GW-45 |
| `get_by_workspace` | R7a | PLG-GW-46, PLG-GW-47, PLG-GW-48 |
| `get_by_workspace` | R8 | PLG-GW-45, PLG-GW-49, PLG-GW-50, PLG-GW-51 |
| `get_by_workspace` | R9 | PLG-GW-52, PLG-GW-53, PLG-GW-54, PLG-GW-55 |
| `get_by_workspace` | R10 | PLG-GW-56, PLG-GW-57 |
| `get_by_workspace` | R11 | PLG-GW-58, PLG-GW-59, PLG-GW-60, PLG-GW-61, PLG-GW-62 |
| `get_by_workspace` | Errors row 1 | PLG-GW-56 |
| `get_by_workspace` | Errors row 2 | PLG-GW-57 |
| `get_by_workspace` | Side effects | PLG-GW-63, PLG-GW-64 |
| `exists_for_production_batch` | Returns | PLG-EX-01, PLG-EX-03 |
| `exists_for_production_batch` | R1 | PLG-EX-01, PLG-EX-02 |
| `exists_for_production_batch` | R2 | PLG-EX-03, PLG-EX-04, PLG-EX-05, PLG-EX-06, PLG-EX-07 |
| `exists_for_production_batch` | R3 | PLG-EX-08, PLG-EX-09, PLG-EX-10, PLG-EX-11, PLG-EX-12, PLG-EX-13, PLG-EX-19 |
| `exists_for_production_batch` | R4 | PLG-EX-14, PLG-EX-15, PLG-EX-16 |
| `exists_for_production_batch` | Side effects | PLG-EX-17, PLG-EX-18 |
| `inherited` | R1 | PLG-INH-01 |
| `inherited` | R2 | PLG-INH-02, PLG-INH-03 |
| `inherited` | R2a [BUG-1337] | PLG-INH-05 |
| `inherited` | R3 | PLG-INH-06 |
| `inherited` | R4 | PLG-INH-07, PLG-INH-08 |
| `inherited` | R5 | PLG-INH-09, PLG-INH-10 |
| `inherited` | Side effects | PLG-INH-04 |
