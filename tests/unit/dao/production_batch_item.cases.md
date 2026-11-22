# Test cases — `app/dao/production_batch_item.py`

> **Spec:** `tests/unit/dao/production_batch_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). P1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `production_batch_item.verify.md` (Finding 1, recipe R-1): BIT-R-25. No other card changed, none retired.
> **Counts:** 61 cases · 55 expected-to-pass · 6 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `get_by_batch` 17 (3 bug) · `get_by_batch_and_role` 25 (3 bug) · `get_by_id_and_workspace` 12 · `inherited` 7.
- **Depth:** lighter target (skill step 1a). The stock moves are the manager's; this module only reads the lines, with plain filters. Commit spies: none, the module has no writer of its own and `base.cases.md` holds them.
- **Expected-to-fail:** BUG-1322 3 (1 strict, 2 non-strict) · BUG-1323 3 (1 strict, 2 non-strict).
- **Notable design choices:**
  - Row order: pass cards compare sets or sizes. Each of the two unordered queries has one strict SQL recorder and two non-strict order cards, one of them with item, role and quantity not rising with id.
  - `B` in a Given is a line; the standing batches are `B1`, `B2`, `BC`, `B9`.
  - BUG-1324 sits in the manager: the DAO stores any location id, so a Deferred entry and no card.
  - A row of workspace W2 on a batch of W1 is built on purpose: rule R1 states what the read does with it.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `BIT` = `app/dao/production_batch_item.py`. `G` get_by_batch · `R` get_by_batch_and_role · `I` get_by_id_and_workspace · `INH` inherited `BaseDAO` methods on `ProductionBatchItem`.

**Actors and fixed values.**
- `dao` = the singleton `production_batch_item_dao` (`from app.dao.production_batch_item import production_batch_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductionBatchItem` = `app.models.production_batch_item.ProductionBatchItem`. `ProductionBatchItemCreate`, `ProductionBatchItemUpdate` = the schemas of `app.schemas.production_batch_item`. `ProductionBatch` = `app.models.production_batch.ProductionBatch`. `ProductionLine` = `app.models.production_line.ProductionLine`. `Factory` = `app.models.factory.Factory`. `Item` = `app.models.item.Item`. `date` = the `datetime` module's class. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F9 = the same, but `name "Far Plant"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - L1 = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Press")`. L9 = the same, but `workspace_id W2.id`, `factory_id F9.id`.
  - B1 = `ProductionBatch(workspace_id=W1.id, batch_number="B-1", production_line_id=L1.id, batch_date=date(2026, 3, 1))`. B2 = the same, but `batch_number "B-2"`. BC = the same, but `batch_number "B-3"`, `status "cancelled"`. B9 = the same, but `batch_number "B-9"`, `workspace_id W2.id`, `production_line_id L9.id`.
  - I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. I2 = the same, but `name "Washer"`, `name_normalized "washer"`. I3 = the same, but `name "Spring"`, `name_normalized "spring"`.
  - IX = the same as I1, but `name "Old Gasket"`, `name_normalized "old gasket"`, `is_active False` (removed). I9 = the same as I1, but `name "Far Crate"`, `name_normalized "far crate"`, `workspace_id W2.id`.
- **line** = `ProductionBatchItem(workspace_id=W1.id, batch_id=B1.id, item_id=I1.id, item_role="input")`; the card lists every column that differs. No `production_batch_items` row exists unless the card's Given lists it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `production_batch_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `production_batch_items`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionBatchItemDAO.get_by_batch`

### BIT-G-01 — returns a list of the parent's lines, of every role
- **Rules:** `get_by_batch` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "output"`, `item_id I2.id`.
3. C = line, `item_role "waste"`, `item_id I3.id`.
4. D = line, `item_role "byproduct"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id, C.id, D.id]`.
3. returns: `isinstance(result[0], ProductionBatchItem)`.

### BIT-G-02 — a line of another parent is not returned
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = line, `item_role "input"`, `item_id I1.id`, `batch_id B2.id`.
2. A = line, `item_role "input"`, `item_id I2.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-G-03 — the right parent under another workspace returns an empty list
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BIT-G-04 — a W2 row on a W1 parent is returned for W2
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W2.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-G-05 — a W2 row on a W1 parent is not returned for W1
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-G-06 — an unknown parent returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-G-07 — batch_id=0 returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-G-08 — a parent with no lines returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-G-09 — the query orders by id, ascending
- **Rules:** `get_by_batch` R3 [BUG-1322]
- **Kind:** bug
- **Expect:** xfail BUG-1322
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### BIT-G-10 — lines come back by id, when the lowest id was updated
- **Rules:** `get_by_batch` R3 [BUG-1322]
- **Kind:** bug
- **Expect:** xfail BUG-1322 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I1.id`, `expected_quantity 7`.
3. B = line, `item_role "input"`, `item_id I2.id`, `expected_quantity 9`.
4. C = line, `item_role "input"`, `item_id I3.id`, `expected_quantity 5`.
5. `A.expected_quantity = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### BIT-G-11 — lines come back by id, when item, role and quantity would each sort otherwise
- **Rules:** `get_by_batch` R3 [BUG-1322]
- **Kind:** bug
- **Expect:** xfail BUG-1322 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "output"`, `item_id I3.id`, `expected_quantity 7`.
3. B = line, `item_role "waste"`, `item_id I1.id`, `expected_quantity 9`.
4. C = line, `item_role "byproduct"`, `item_id I2.id`, `expected_quantity 5`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### BIT-G-12 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_batch` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### BIT-G-13 — a line of a cancelled batch is returned
- **Rules:** `get_by_batch` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `batch_id BC.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=BC.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-G-14 — a line of a removed item is returned
- **Rules:** `get_by_batch` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-G-15 — the query does not read the parent tables
- **Rules:** `get_by_batch` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.

### BIT-G-16 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I2.id`.
2. `P = ProductionBatchItem(workspace_id=W1.id, batch_id=B1.id, item_id=I1.id, item_role="input")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BIT-G-17 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

## `ProductionBatchItemDAO.get_by_batch_and_role`

### BIT-R-01 — returns a list of the lines of that parent and role
- **Rules:** `get_by_batch_and_role` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. X = line, `item_role "output"`, `item_id I2.id`.
3. B = line, `item_role "input"`, `item_id I3.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionBatchItem)`.

### BIT-R-02 — a line of another parent is not returned
- **Rules:** `get_by_batch_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = line, `item_role "input"`, `item_id I1.id`, `batch_id B2.id`.
2. A = line, `item_role "input"`, `item_id I2.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-R-03 — the right parent and role under another workspace returns an empty list
- **Rules:** `get_by_batch_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-04 — two lines with one item and role are both returned
- **Rules:** `get_by_batch_and_role` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### BIT-R-05 — a role in capitals finds nothing
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="INPUT", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-06 — a leading space in the role finds nothing
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role=" input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-07 — the start of a role finds nothing
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="inp", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-08 — the end of a role finds nothing
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="put", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-09 — _ is no wildcard in a role
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="i_put", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-10 — % is no wildcard in a role
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-11 — an unknown role finds nothing
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="zzz", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-12 — a stored role with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role " input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-13 — a stored role in capitals is not found
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "INPUT"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-14 — an unknown parent returns an empty list
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=MISSING, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-15 — batch_id=0 returns an empty list
- **Rules:** `get_by_batch_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=0, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BIT-R-16 — the query orders by id, ascending
- **Rules:** `get_by_batch_and_role` R3 [BUG-1323]
- **Kind:** bug
- **Expect:** xfail BUG-1323
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### BIT-R-17 — lines come back by id, when the lowest id was updated
- **Rules:** `get_by_batch_and_role` R3 [BUG-1323]
- **Kind:** bug
- **Expect:** xfail BUG-1323 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I1.id`, `expected_quantity 7`.
3. B = line, `item_role "input"`, `item_id I2.id`, `expected_quantity 9`.
4. C = line, `item_role "input"`, `item_id I3.id`, `expected_quantity 5`.
5. `A.expected_quantity = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### BIT-R-18 — lines come back by id, when item and quantity would each sort otherwise
- **Rules:** `get_by_batch_and_role` R3 [BUG-1323]
- **Kind:** bug
- **Expect:** xfail BUG-1323 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I3.id`, `expected_quantity 7`.
3. B = line, `item_role "input"`, `item_id I1.id`, `expected_quantity 9`.
4. C = line, `item_role "input"`, `item_id I2.id`, `expected_quantity 5`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### BIT-R-19 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_batch_and_role` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### BIT-R-20 — a line of a cancelled batch is returned
- **Rules:** `get_by_batch_and_role` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `batch_id BC.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=BC.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-R-21 — a line of a removed item is returned
- **Rules:** `get_by_batch_and_role` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BIT-R-22 — the query does not read the parent tables
- **Rules:** `get_by_batch_and_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.

### BIT-R-23 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_batch_and_role` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I2.id`.
2. `P = ProductionBatchItem(workspace_id=W1.id, batch_id=B1.id, item_id=I1.id, item_role="input")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BIT-R-24 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_batch_and_role` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BIT-R-25 — a W2 line on the W1 parent is not returned for W1
- **Rules:** `get_by_batch_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `ProductionBatchItemDAO.get_by_id_and_workspace`

### BIT-I-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = line, `item_role "input"`, `item_id I2.id`.
2. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionBatchItem)`.
2. returns: `result.id == A.id`.
3. returns: `result.batch_id == B1.id`, `result.workspace_id == W1.id`, `result.item_role == "input"`.

### BIT-I-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. Z = line, `item_id I9.id`, `item_role "input"`, `workspace_id W2.id`, `batch_id B9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BIT-I-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `item_id I9.id`, `item_role "input"`, `workspace_id W2.id`, `batch_id B9.id`.
2. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BIT-I-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### BIT-I-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BIT-I-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BIT-I-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. `P = ProductionBatchItem(workspace_id=W1.id, batch_id=B1.id, item_id=I1.id, item_role="input")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BIT-I-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. `P = ProductionBatchItem(workspace_id=W1.id, batch_id=B1.id, item_id=I1.id, item_role="input")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BIT-I-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BIT-I-10 — a line of a cancelled batch is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `batch_id BC.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### BIT-I-11 — a line of a removed item is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### BIT-I-12 — the query does not read the parent tables
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"JOIN" not in sql`.

## Inherited `BaseDAO` methods on `ProductionBatchItem`

### BIT-INH-01 — create with a dict leaves the optional columns None
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_id": B1.id, "item_id": I1.id, "item_role": "input"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_role == "input"`.
3. re-read the returned row: `expected_quantity is None`, `actual_quantity is None`.
4. re-read the returned row: `source_location_type is None`, `source_location_id is None`, `destination_location_type is None`, `destination_location_id is None`.
5. re-read the returned row: `notes is None`.

### BIT-INH-02 — create with a ProductionBatchItemCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductionBatchItemCreate(batch_id=B1.id, item_id=I1.id, item_role="input"))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `production_batch_items` has exactly 0 rows.

### BIT-INH-03 — an odd role is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_id": B1.id, "item_id": I1.id, "item_role": "zz"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_role == "zz"`.

### BIT-INH-04 — a negative expected quantity is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_id": B1.id, "item_id": I1.id, "item_role": "input", "expected_quantity": -1})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `expected_quantity == -1`.

### BIT-INH-05 — a zero actual quantity is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_id": B1.id, "item_id": I1.id, "item_role": "input", "actual_quantity": 0})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `actual_quantity == 0`.

### BIT-INH-06 — update with a schema applies the fields set to a value
- **Rules:** `inherited` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `actual_quantity 2`, `notes "Keep"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductionBatchItemUpdate(actual_quantity=5, notes=None))`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `actual_quantity == 5`, `notes == "Keep"`.

### BIT-INH-07 — remove hard-deletes the row
- **Rules:** `inherited` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.

**When**
- `result = dao.remove(db, id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: `production_batch_items` has exactly 1 row.
3. unchanged: unchanged(B).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1324 (HR-16) — a location of another workspace is refused as "not found", nothing written | `ProductionBatchManager.add_batch_item`, `update_batch_item`, `complete_batch` | **Stock.** Verified: an output line posted a `products` row into another workspace's factory. |
| BUG-1322 consequence — the order in which stock is taken and posted | `ProductionBatchManager.start_batch`, `complete_batch` | **Stock.** Ledger rows of one batch follow this read's order. |
| FU-1 (a) — `add_batch_item` accepts a removed item and a soft-deleted factory as a location | `ProductionBatchManager.add_batch_item` | **Stock.** |
| FU-1 (b) — `actual_quantity or expected_quantity`: `0` falls through | `ProductionBatchManager.start_batch` | **Stock.** Pattern `falsy-zero-treated-as-missing`; `post_outputs_to_finished_goods` disagrees. |
| FU-1 (c) — lines changed or removed on an `in_progress` batch never give stock back | `ProductionBatchManager.update_batch_item`, `remove_batch_item` | **Stock, owner.** |
| FU-1 (d) — `update_batch_item` cannot clear a field | `ProductionBatchManager.update_batch_item` |  |
| FU-1 (e) — `_calculate_batch_item_variances` overflows `Numeric(5, 2)` at about 1000 % | `ProductionBatchManager._calculate_batch_item_variances` | Read, not run. |
| Generic behavior of inherited methods; `get`, `get_by_workspace`, `get_multi` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton `production_batch_item_dao`; dead `get_by_item` (P1) | none | No logic / to be removed. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | Model facts: relationships | **Stock.** The spec names no `lazy="joined"` relationship, and the "JOIN" not in sql cards assume there is none. | If one exists, three recorder cards fail and need narrowing to the parent's name. |
| 3 | Model facts: a cancelled batch | **Stock.** The spec does not say what `cancel_batch` writes beside `status`. | BC carries `status "cancelled"` only. These reads do not look at the batch. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_batch` | Returns | BIT-G-01 |
| `get_by_batch` | R1 | BIT-G-01, BIT-G-02, BIT-G-03, BIT-G-04, BIT-G-05 |
| `get_by_batch` | R2 | BIT-G-06, BIT-G-07, BIT-G-08 |
| `get_by_batch` | R3 [BUG-1322] | BIT-G-09, BIT-G-10, BIT-G-11 |
| `get_by_batch` | R4 | BIT-G-12 |
| `get_by_batch` | R5 | BIT-G-13, BIT-G-14, BIT-G-15 |
| `get_by_batch` | Side effects | BIT-G-16, BIT-G-17 |
| `get_by_batch_and_role` | Returns | BIT-R-01 |
| `get_by_batch_and_role` | R1 | BIT-R-01, BIT-R-02, BIT-R-03, BIT-R-04, BIT-R-25 |
| `get_by_batch_and_role` | R2 | BIT-R-05, BIT-R-06, BIT-R-07, BIT-R-08, BIT-R-09, BIT-R-10, BIT-R-11, BIT-R-12, BIT-R-13, BIT-R-14, BIT-R-15 |
| `get_by_batch_and_role` | R3 [BUG-1323] | BIT-R-16, BIT-R-17, BIT-R-18 |
| `get_by_batch_and_role` | R4 | BIT-R-19 |
| `get_by_batch_and_role` | R5 | BIT-R-20, BIT-R-21, BIT-R-22 |
| `get_by_batch_and_role` | Side effects | BIT-R-23, BIT-R-24 |
| `get_by_id_and_workspace` | Returns | BIT-I-01 |
| `get_by_id_and_workspace` | R1 | BIT-I-01 |
| `get_by_id_and_workspace` | R2 | BIT-I-02, BIT-I-03, BIT-I-04 |
| `get_by_id_and_workspace` | R3 | BIT-I-05, BIT-I-06, BIT-I-07 |
| `get_by_id_and_workspace` | R4 | BIT-I-10, BIT-I-11, BIT-I-12 |
| `get_by_id_and_workspace` | Side effects | BIT-I-07, BIT-I-08, BIT-I-09 |
| `inherited` | R1 | BIT-INH-01 |
| `inherited` | R2 | BIT-INH-02 |
| `inherited` | R3 | BIT-INH-03, BIT-INH-04, BIT-INH-05 |
| `inherited` | R4 | BIT-INH-06 |
| `inherited` | R5 | BIT-INH-07 |
