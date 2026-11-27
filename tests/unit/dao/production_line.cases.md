# Test cases — `app/dao/production_line.py`

> **Spec:** `tests/unit/dao/production_line.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). P1 and Q1 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `production_line.verify.md` (Finding 1, recipes R-1a … R-1c): PLN-GW-23, GF-36, GA-35. Finding 2: the unused `newest` line is dropped from the default-limit cards PLN-GW-10, GF-25, GA-24. No other card changed, none retired. Revision 1b: PLN-GW-23, PLN-GF-36, PLN-GA-35 no longer name one row on a query with no `ORDER BY`: `limit=2`, the page's size, the W1 set and `Z.id not in ids(result)`, so they hold under any row order and still fail when the workspace filter runs after `LIMIT` and Z, inserted first, is in the window (executor's "Order-fragile pass cards").
> **Counts:** 116 cases · 89 expected-to-pass · 27 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 23 (3 bug) · `get_by_factory` 36 (9 bug) · `get_active_by_workspace` 35 (11 bug) · `get_by_id_and_workspace` 13 · `inherited` 4 · `schema` 5 (4 bug).
- **Depth:** lighter target (skill step 1a). Four plain filtered reads; nothing here writes stock, money or order state, and the inherited writers are the base spec's. Commit spies: none, the module has no writer of its own and `base.cases.md` holds them.
- **Expected-to-fail:** BUG-100 3 (1 strict, 2 non-strict) · BUG-1310 7 (1 strict, 6 non-strict) · BUG-1311 7 (1 strict, 6 non-strict) · BUG-1312 6 (6 strict, 0 non-strict) · BUG-1313 4 (4 strict, 0 non-strict).
- **Notable design choices:**
  - Row order: pass cards and BUG-1312 strict cards compare `sorted(ids(result))`, sizes or `[]`. Each of the three unordered queries has one strict SQL recorder (GW, GF, GA) and non-strict cards for the order itself.
  - The test database's libc collation sorts "apple", "Banana", "Zulu" right with no `lower()`, so that example alone cannot show a case-sensitive sort. The "Press" / "press" cards do, in both insert orders.
  - "Takes no place in the page" on an unordered query is written with `skip=2` on three rows and `skip=1` with a size check, never with a chosen row: the size holds in any physical order, so these cards can stay strict.
  - Real states: a soft-deleted factory or machine carries `is_deleted`, `deleted_at`, `deleted_by`, and an inactive line carries `is_active False` alone, as `delete_production_line` leaves it.
  - BUG-1313 is a schema rule, so skill step 4 gives it `schema` cards (SCH), with one passing companion. A `Companion` row in the matrix marks that one.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PLN` = `app/dao/production_line.py`. `GW` get_by_workspace · `GF` get_by_factory · `GA` get_active_by_workspace · `GI` get_by_id_and_workspace · `INH` inherited `BaseDAO` methods on `ProductionLine` · `SCH` the schemas of BUG-1313.

**Actors and fixed values.**
- `dao` = the singleton `production_line_dao` (`from app.dao.production_line import production_line_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductionLine` = `app.models.production_line.ProductionLine`. `ProductionLineCreate`, `ProductionLineUpdate` = the schemas of `app.schemas.production_line`. `ValidationError` = `pydantic.ValidationError`. `Factory` = `app.models.factory.Factory`. `Machine` = `app.models.machine.Machine`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows. U1 = one `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`.
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (soft-deleted; `is_active` stays True). FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (inactive but live). F9 = the same as F1, but `name "Far Plant"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 1")`. MD = the same, but `name "Press 2"`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (soft-deleted).
- **line** = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name=...)`; `is_active` and `machine_id` are left to their defaults; the card gives `name` and every other column that differs. No `production_lines` row exists unless the card's Given lists it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `production_lines` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line. `raises: ValidationError` = `pytest.raises(ValidationError)` around the When, with no savepoint: nothing reaches the database.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `production_lines`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionLineDAO.get_by_workspace`

### PLN-GW-01 — returns a list of the workspace's lines
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionLine)`.

### PLN-GW-02 — a row of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `name "Alpha"`, `workspace_id W2.id`, `factory_id F9.id`.
2. A = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GW-03 — an inactive line is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PLN-GW-04 — a line of a soft-deleted machine is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `machine_id MD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GW-05 — a line of a soft-deleted factory is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `factory_id FD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GW-06 — the query does not read the parent tables
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.
3. statement: `"factories" not in sql`.
4. statement: `"machines" not in sql`.

### PLN-GW-07 — the query orders by id, ascending
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PLN-GW-08 — rows come back by id, when the lowest id was updated
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Charlie"`.
3. B = line, `name "Alpha"`.
4. C = line, `name "Bravo"`.
5. `A.description = "Changed"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PLN-GW-09 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R3 [BUG-100], R4
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Charlie"`.
3. B = line, `name "Alpha"`.
4. C = line, `name "Bravo"`.
5. D = line, `name "Echo"`.
6. E = line, `name "Delta"`.
7. `A.description = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [A.id, B.id, C.id, D.id, E.id]`.

### PLN-GW-10 — with the defaults 101 rows give 100
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PLN-GW-11 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PLN-GW-12 — skip and limit cut one row from the middle
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. C = line, `name "Charlie"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GW-13 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PLN-GW-14 — limit=1 returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GW-15 — skip at the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GW-16 — skip at the last row returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GW-17 — a negative limit raises
- **Rules:** `get_by_workspace` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GW-18 — a negative skip raises
- **Rules:** `get_by_workspace` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GW-19 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PLN-GW-20 — a workspace with no rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PLN-GW-21 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Bravo"`.
2. `P = ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Aardvark")`
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

### PLN-GW-22 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PLN-GW-23 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = line, `name "Alpha"`, `workspace_id W2.id`, `factory_id F9.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductionLineDAO.get_by_factory`

### PLN-GF-01 — returns a list of the factory's lines
- **Rules:** `get_by_factory` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionLine)`.

### PLN-GF-02 — a line of another factory is not returned
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id F2.id`.
2. A = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GF-03 — the right factory under another workspace returns an empty list
- **Rules:** `get_by_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-04 — a W2 row on a W1 factory is returned for W2
- **Rules:** `get_by_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W2.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GF-05 — a W2 row on a W1 factory is not returned for W1
- **Rules:** `get_by_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-06 — an inactive line is returned
- **Rules:** `get_by_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`, `is_active False`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PLN-GF-07 — an unknown factory returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-08 — factory_id=0 returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-09 — a factory with no lines returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-10 — the query does not read the parent tables
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `machine_id MD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"machines" not in sql`.

### PLN-GF-11 — a soft-deleted factory returns an empty list
- **Rules:** `get_by_factory` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (the factory's state is not read; its line is returned)

**Given**
1. A = line, `name "Alpha"`.
2. X = line, `name "Bravo"`, `factory_id FD.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-12 — a W2 row on a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_factory` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (the factory's state is not read; its line is returned)

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PLN-GF-13 — listing a soft-deleted factory changes nothing
- **Rules:** `get_by_factory` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(FD).
4. statement: `written == []`.

### PLN-GF-14 — an inactive factory hides nothing
- **Rules:** `get_by_factory` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FI.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FI.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### PLN-GF-15 — once the factory is live again its line is back, unchanged
- **Rules:** `get_by_factory` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### PLN-GF-16 — the query orders by name, then id, ascending
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### PLN-GF-17 — names come back case-insensitively: "apple", "Banana", "Zulu"
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Zulu"`.
3. B = line, `name "apple"`.
4. C = line, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PLN-GF-18 — "Press" and "press" tie on the name: the lower id comes first, capital first
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Press"`.
3. B = line, `name "press"`.
4. `db.expire_all()`

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PLN-GF-19 — "press" and "Press" tie on the name: the lower id comes first, small letter first
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "press"`.
3. B = line, `name "Press"`.
4. `db.expire_all()`

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PLN-GF-20 — a tie on the name goes to the lower id, when description would sort otherwise and the lowest id was updated
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Press"`, `description "Zed"`.
3. B = line, `name "Press"`, `description "Abe"`.
4. C = line, `name "Press"`, `description "Mid"`.
5. `A.description = "Yak"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PLN-GF-21 — the order is applied before the page is cut
- **Rules:** `get_by_factory` R4 [BUG-1310]
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Zulu"`.
3. B = line, `name "apple"`.
4. C = line, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [C.id]`.

### PLN-GF-22 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_factory` R4 [BUG-1310], R5
- **Kind:** bug
- **Expect:** xfail BUG-1310 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Charlie"`.
3. B = line, `name "Alpha"`.
4. C = line, `name "Bravo"`.
5. D = line, `name "Echo"`.
6. E = line, `name "Delta"`.
7. `B.description = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [B.id, C.id, A.id, E.id, D.id]`.

### PLN-GF-23 — the factory filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id F2.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GF-24 — the factory filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id F2.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PLN-GF-25 — with the defaults 101 rows give 100
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PLN-GF-26 — limit=1000 gives all 101
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PLN-GF-27 — skip and limit cut one row from the middle
- **Rules:** `get_by_factory` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. C = line, `name "Charlie"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GF-28 — limit=0 returns an empty list
- **Rules:** `get_by_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PLN-GF-29 — limit=1 returns one row
- **Rules:** `get_by_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GF-30 — skip at the number of rows returns an empty list
- **Rules:** `get_by_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GF-31 — skip at the last row returns one row
- **Rules:** `get_by_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GF-32 — a negative limit raises
- **Rules:** `get_by_factory` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GF-33 — a negative skip raises
- **Rules:** `get_by_factory` R7, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GF-34 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_factory` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Bravo"`.
2. `P = ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Aardvark")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PLN-GF-35 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_factory` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PLN-GF-36 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_by_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = line, `name "Alpha"`, `workspace_id W2.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductionLineDAO.get_active_by_workspace`

### PLN-GA-01 — returns a list of the active lines
- **Rules:** `get_active_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionLine)`.

### PLN-GA-02 — an inactive line is not returned
- **Rules:** `get_active_by_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `is_active False`.
2. A = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GA-03 — a row of another workspace is not returned
- **Rules:** `get_active_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `name "Alpha"`, `workspace_id W2.id`, `factory_id F9.id`.
2. A = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GA-04 — the active filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `is_active False`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GA-05 — the active filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `is_active False`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PLN-GA-06 — a line of a soft-deleted machine is returned
- **Rules:** `get_active_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `machine_id MD.id`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GA-07 — the query does not read the parent tables
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `machine_id MD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"machines" not in sql`.

### PLN-GA-08 — an unknown workspace returns an empty list
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PLN-GA-09 — a workspace with no active lines returns an empty list
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `is_active False`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PLN-GA-10 — a line of a soft-deleted factory is not returned
- **Rules:** `get_active_by_workspace` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (the factory's state is not read; the line X is returned)

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. A = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PLN-GA-11 — a W2 line on a soft-deleted W1 factory is hidden too
- **Rules:** `get_active_by_workspace` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (the factory's state is not read; the line X is returned)

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PLN-GA-12 — a hidden line takes no place: skip=2 past the two live rows gives nothing
- **Rules:** `get_active_by_workspace` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (three rows are counted, so one comes back)

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GA-13 — a hidden line takes no place: skip=1 leaves one live row
- **Rules:** `get_active_by_workspace` R3a [BUG-1312]
- **Kind:** bug
- **Expect:** xfail BUG-1312
- **Fails today on:** Then 1 (three rows are counted, so two come back)

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PLN-GA-14 — listing with a soft-deleted factory changes nothing
- **Rules:** `get_active_by_workspace` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(FD).
4. statement: `written == []`.

### PLN-GA-15 — an inactive factory hides nothing
- **Rules:** `get_active_by_workspace` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FI.id`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### PLN-GA-16 — once the factory is live again its line is back, unchanged
- **Rules:** `get_active_by_workspace` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = line, `name "Alpha"`, `factory_id FD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### PLN-GA-17 — the query orders by name, then id, ascending
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### PLN-GA-18 — names come back case-insensitively: "apple", "Banana", "Zulu"
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Zulu"`.
3. B = line, `name "apple"`.
4. C = line, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PLN-GA-19 — "Press" and "press" tie on the name: the lower id comes first, capital first
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Press"`.
3. B = line, `name "press"`.
4. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PLN-GA-20 — "press" and "Press" tie on the name: the lower id comes first, small letter first
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "press"`.
3. B = line, `name "Press"`.
4. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PLN-GA-21 — a tie on the name goes to the lower id, when description would sort otherwise and the lowest id was updated
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Press"`, `description "Zed"`.
3. B = line, `name "Press"`, `description "Abe"`.
4. C = line, `name "Press"`, `description "Mid"`.
5. `A.description = "Yak"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PLN-GA-22 — the order is applied before the page is cut
- **Rules:** `get_active_by_workspace` R4 [BUG-1311]
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Zulu"`.
3. B = line, `name "apple"`.
4. C = line, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [C.id]`.

### PLN-GA-23 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_active_by_workspace` R4 [BUG-1311], R5
- **Kind:** bug
- **Expect:** xfail BUG-1311 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `name "Charlie"`.
3. B = line, `name "Alpha"`.
4. C = line, `name "Bravo"`.
5. D = line, `name "Echo"`.
6. E = line, `name "Delta"`.
7. `B.description = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_active_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [B.id, C.id, A.id, E.id, D.id]`.

### PLN-GA-24 — with the defaults 101 rows give 100
- **Rules:** `get_active_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PLN-GA-25 — limit=1000 gives all 101
- **Rules:** `get_active_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line, `name` = `f"Line {k:03d}"`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PLN-GA-26 — skip and limit cut one row from the middle
- **Rules:** `get_active_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. C = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GA-27 — limit=0 returns an empty list
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PLN-GA-28 — limit=1 returns one row
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GA-29 — skip at the number of rows returns an empty list
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PLN-GA-30 — skip at the last row returns one row
- **Rules:** `get_active_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PLN-GA-31 — a negative limit raises
- **Rules:** `get_active_by_workspace` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GA-32 — a negative skip raises
- **Rules:** `get_active_by_workspace` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PLN-GA-33 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_active_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Bravo"`.
2. `P = ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Aardvark")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PLN-GA-34 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_active_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PLN-GA-35 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = line, `name "Alpha"`, `workspace_id W2.id`, `factory_id F9.id`.
2. A = line, `name "Bravo"`.
3. B = line, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductionLineDAO.get_by_id_and_workspace`

### PLN-GI-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = line, `name "Bravo"`.
2. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionLine)`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Alpha"`, `result.workspace_id == W1.id`, `result.factory_id == F1.id`.

### PLN-GI-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. Z = line, `name "Bravo"`, `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PLN-GI-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `name "Bravo"`, `workspace_id W2.id`, `factory_id F9.id`.
2. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PLN-GI-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PLN-GI-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PLN-GI-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PLN-GI-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. `P = ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Aardvark")`
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

### PLN-GI-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. `P = ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Aardvark")`
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

### PLN-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. B = line, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PLN-GI-10 — an inactive line is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `is_active False`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_active is False`.

### PLN-GI-11 — a line of a soft-deleted factory is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `factory_id FD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PLN-GI-12 — a line of a soft-deleted machine is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`, `machine_id MD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PLN-GI-13 — the query does not read the parent tables
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"JOIN" not in sql`.
3. statement: `"factories" not in sql`.
4. statement: `"machines" not in sql`.

## Inherited `BaseDAO` methods on `ProductionLine`

### PLN-INH-01 — create with a dict gives the defaults
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "name": "Press"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_active is True`, `machine_id is None`.
3. re-read the returned row: `name == "Press"`, `workspace_id == W1.id`, `factory_id == F1.id`.

### PLN-INH-02 — create with a ProductionLineCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductionLineCreate(factory_id=F1.id, name="Press"))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `production_lines` has exactly 0 rows.

### PLN-INH-03 — two lines with one name in one factory are both saved
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `name "Press"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id, "name": "Press"})`.

**Then**
1. returns: `result.id != A.id`.
2. count: `production_lines` has exactly 2 rows with `name == "Press"`.

### PLN-INH-04 — after a hard delete of the machine the line stays, with machine_id None
- **Rules:** `inherited` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `name "Press"`, `machine_id M1.id`.

**When**
- `db.execute(text("DELETE FROM machines WHERE id = :i"), {"i": M1.id})`.

**Then**
1. re-read A: `machine_id is None`.
2. count: `production_lines` has exactly 1 row.

## Schemas `ProductionLineCreate`, `ProductionLineUpdate` (BUG-1313)

### PLN-SCH-01 — a whitespace-only name is refused on create
- **Rules:** `schema` BUG-1313
- **Kind:** bug
- **Expect:** xfail BUG-1313
- **Fails today on:** Then 1 (`min_length=1` lets it through, no error is raised)

**Given**
1. No row beyond the standing rows.

**When**
- `ProductionLineCreate(factory_id=F1.id, name="   ")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.

### PLN-SCH-02 — a whitespace-only name is refused on update
- **Rules:** `schema` BUG-1313
- **Kind:** bug
- **Expect:** xfail BUG-1313
- **Fails today on:** Then 1 (`min_length=1` lets it through, no error is raised)

**Given**
1. No row beyond the standing rows.

**When**
- `ProductionLineUpdate(name="   ")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.

### PLN-SCH-03 — a name is stored trimmed on create
- **Rules:** `schema` BUG-1313
- **Kind:** bug
- **Expect:** xfail BUG-1313
- **Fails today on:** Then 1 (the spaces are kept)

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionLineCreate(factory_id=F1.id, name=" a ")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "a"`.

### PLN-SCH-04 — a name is stored trimmed on update
- **Rules:** `schema` BUG-1313
- **Kind:** bug
- **Expect:** xfail BUG-1313
- **Fails today on:** Then 1 (the spaces are kept)

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionLineUpdate(name=" a ")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "a"`.

### PLN-SCH-05 — inner spaces and case are kept as typed
- **Rules:** `schema` Companion
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionLineCreate(factory_id=F1.id, name="Line  B")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "Line  B"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a), BUG-100 — display order of `GET /production-lines/` | `ProductionLineManager.get_production_lines` | `name` case-insensitive, then `id`. `get_by_workspace` R3 gives `id` only. |
| FU-1 (b) — the plain list shows lines of a soft-deleted factory | `ProductionLineManager.get_production_lines` | Hidden in the query, before paging. `get_by_workspace` R2 stays raw. |
| FU-1 (c) — `factory_id` wins over `active_only` | `ProductionLineManager.get_production_lines` | Pattern `silently-ignored-input`. |
| FU-1 (d) — `delete_production_line` writes no `updated_by`, and has no check for open batches | `ProductionLineManager.delete_production_line` | **Stock.** A line with `draft` or `in_progress` batches can be deactivated. |
| FU-1 (e) — `machine_id: null` is dropped | `ProductionLineManager.update_production_line` | Pattern `exclude-none-blocks-clear`. |
| FU-1 (f) — `updated_by` stamped when nothing changes (HR-9) | `ProductionLineManager.update_production_line` | Read, not run. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /production-lines/` | Endpoint rule; the DAO's own negatives are the Errors cards. |
| BUG-1313 through the API (422, nothing written) | `POST`, `PUT /production-lines/` | The rule is the schema's; SCH cards test the schema. |
| Generic behavior of inherited methods; `get_multi`, `remove`, `update`, `get` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton `production_line_dao`; dead `get_by_machine` (P1) | none | No logic / to be removed. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | Model facts: `Machine` | The spec does not say which columns a real machine soft delete writes. | MD uses the four named in `factory.spec.md`. The DAO does not read them. |
| 3 | Model facts: relationships | The spec names no `lazy="joined"` relationship on `ProductionLine`, and the "JOIN" not in sql cards assume there is none. | If one exists, GW and GI recorder cards fail and need the word narrowed. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | PLN-GW-01 |
| `get_by_workspace` | R1 | PLN-GW-01, PLN-GW-02, PLN-GW-23 |
| `get_by_workspace` | R2 | PLN-GW-03, PLN-GW-04, PLN-GW-05, PLN-GW-06 |
| `get_by_workspace` | R3 [BUG-100] | PLN-GW-07, PLN-GW-08, PLN-GW-09 |
| `get_by_workspace` | R4 | PLN-GW-09, PLN-GW-10, PLN-GW-11, PLN-GW-12 |
| `get_by_workspace` | R5 | PLN-GW-13, PLN-GW-14, PLN-GW-15, PLN-GW-16, PLN-GW-19, PLN-GW-20 |
| `get_by_workspace` | R6 | PLN-GW-17, PLN-GW-18 |
| `get_by_workspace` | Errors row 1 | PLN-GW-17 |
| `get_by_workspace` | Errors row 2 | PLN-GW-18 |
| `get_by_workspace` | Side effects | PLN-GW-21, PLN-GW-22 |
| `get_by_factory` | Returns | PLN-GF-01 |
| `get_by_factory` | R1 | PLN-GF-01, PLN-GF-02, PLN-GF-23, PLN-GF-24 |
| `get_by_factory` | R2 | PLN-GF-03, PLN-GF-04, PLN-GF-05, PLN-GF-36 |
| `get_by_factory` | R3 | PLN-GF-06, PLN-GF-07, PLN-GF-08, PLN-GF-09, PLN-GF-10 |
| `get_by_factory` | R3a [BUG-1312] | PLN-GF-11, PLN-GF-12 |
| `get_by_factory` | R3b | PLN-GF-13, PLN-GF-14, PLN-GF-15 |
| `get_by_factory` | R4 [BUG-1310] | PLN-GF-16, PLN-GF-17, PLN-GF-18, PLN-GF-19, PLN-GF-20, PLN-GF-21, PLN-GF-22 |
| `get_by_factory` | R5 | PLN-GF-22, PLN-GF-25, PLN-GF-26, PLN-GF-27 |
| `get_by_factory` | R6 | PLN-GF-28, PLN-GF-29, PLN-GF-30, PLN-GF-31 |
| `get_by_factory` | R7 | PLN-GF-32, PLN-GF-33 |
| `get_by_factory` | Errors row 1 | PLN-GF-32 |
| `get_by_factory` | Errors row 2 | PLN-GF-33 |
| `get_by_factory` | Side effects | PLN-GF-34, PLN-GF-35 |
| `get_active_by_workspace` | Returns | PLN-GA-01 |
| `get_active_by_workspace` | R1 | PLN-GA-01, PLN-GA-02, PLN-GA-03, PLN-GA-04, PLN-GA-05, PLN-GA-35 |
| `get_active_by_workspace` | R2 | PLN-GA-06, PLN-GA-07 |
| `get_active_by_workspace` | R3 | PLN-GA-08, PLN-GA-09, PLN-GA-27, PLN-GA-28, PLN-GA-29, PLN-GA-30 |
| `get_active_by_workspace` | R3a [BUG-1312] | PLN-GA-10, PLN-GA-11, PLN-GA-12, PLN-GA-13 |
| `get_active_by_workspace` | R3b | PLN-GA-14, PLN-GA-15, PLN-GA-16 |
| `get_active_by_workspace` | R4 [BUG-1311] | PLN-GA-17, PLN-GA-18, PLN-GA-19, PLN-GA-20, PLN-GA-21, PLN-GA-22, PLN-GA-23 |
| `get_active_by_workspace` | R5 | PLN-GA-23, PLN-GA-24, PLN-GA-25, PLN-GA-26 |
| `get_active_by_workspace` | R6 | PLN-GA-31, PLN-GA-32 |
| `get_active_by_workspace` | Errors row 1 | PLN-GA-31 |
| `get_active_by_workspace` | Errors row 2 | PLN-GA-32 |
| `get_active_by_workspace` | Side effects | PLN-GA-33, PLN-GA-34 |
| `get_by_id_and_workspace` | Returns | PLN-GI-01 |
| `get_by_id_and_workspace` | R1 | PLN-GI-01 |
| `get_by_id_and_workspace` | R2 | PLN-GI-02, PLN-GI-03, PLN-GI-04 |
| `get_by_id_and_workspace` | R3 | PLN-GI-05, PLN-GI-06, PLN-GI-07 |
| `get_by_id_and_workspace` | R4 | PLN-GI-10, PLN-GI-11, PLN-GI-12, PLN-GI-13 |
| `get_by_id_and_workspace` | Side effects | PLN-GI-07, PLN-GI-08, PLN-GI-09 |
| `inherited` | R1 | PLN-INH-01 |
| `inherited` | R2 | PLN-INH-02 |
| `inherited` | R3 | PLN-INH-03 |
| `inherited` | R4 | PLN-INH-04 |
| `schema` | BUG-1313 | PLN-SCH-01, PLN-SCH-02, PLN-SCH-03, PLN-SCH-04 |
| `schema` | Companion | PLN-SCH-05 |
