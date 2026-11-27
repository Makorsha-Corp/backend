# Test cases — `app/dao/production_formula.py`

> **Spec:** `tests/unit/dao/production_formula.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 and Q2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `production_formula.verify.md`: Finding 1 (R-1) → PFM-GD-13; Finding 2 (R-2) → PFM-GC-18; Finding 3 (R-3a, R-3b) → PFM-GW-21, GA-26. Finding 4: the unused `newest` line is dropped from the default-limit cards PFM-GW-08, GA-15. No other card changed, none retired. Revision 1b: PFM-GW-21, PFM-GA-26 no longer name one row on a query with no `ORDER BY`: `limit=2`, the page's size, the W1 set and `Z.id not in ids(result)`, so they hold under any row order and still fail when the workspace filter runs after `LIMIT` and Z, inserted first, is in the window (executor's "Order-fragile pass cards").
> **Counts:** 107 cases · 77 expected-to-pass · 30 expected-to-fail (bugs) · 12 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 21 (3 bug) · `get_by_formula_code` 18 (4 bug) · `get_active_by_workspace` 26 (7 bug) · `get_default_formulas` 13 (4 bug) · `get_by_id_and_workspace` 10 · `inherited` 12 (6 bug) · `schema` 7 (6 bug).
- **Depth:** lighter target (skill step 1a) for the reads: plain filtered lists, no stock, money or order state. The one real decision, BUG-1316 (code uniqueness), is covered per shape. Commit spies: none, the module has no writer of its own and `base.cases.md` holds them.
- **Expected-to-fail:** BUG-100 3 (1 strict, 2 non-strict) · BUG-1314 7 (1 strict, 6 non-strict) · BUG-1315 4 (1 strict, 3 non-strict) · BUG-1316 10 (10 strict, 0 non-strict) · BUG-1317 6 (6 strict, 0 non-strict).
- **Notable design choices:**
  - `get_by_formula_code` R4 has no card of its own, as the spec orders: the matrix points it at PFM-INH-03, the card that tests the index.
  - No Given holds two rows for one normalised code in one workspace, as the spec's Notes order. The stored-side cards hold one row with that shape; the index card's second row only goes through `create` or `update`.
  - Row order: pass cards compare sets or sizes; each of the three unordered queries has one strict SQL recorder and non-strict order cards. The "Yarn" / "yarn" cards are the ones that see a case-sensitive sort under the libc collation.
  - BUG-1329 is `update_formula`'s, so a Deferred entry. GD-04 builds the row directly, as the spec says.
  - BUG-1317 is a schema rule, so skill step 4 gives it `schema` cards (SCH), with one passing companion.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none; the lost race of BUG-1316 is the manager's (FU-1 (b)).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PFM` = `app/dao/production_formula.py`. `GW` get_by_workspace · `GC` get_by_formula_code · `GA` get_active_by_workspace · `GD` get_default_formulas · `GI` get_by_id_and_workspace · `INH` inherited `BaseDAO` methods on `ProductionFormula` · `SCH` the schemas of BUG-1317.

**Actors and fixed values.**
- `dao` = the singleton `production_formula_dao` (`from app.dao.production_formula import production_formula_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductionFormula` = `app.models.production_formula.ProductionFormula`. `ProductionFormulaCreate`, `ProductionFormulaUpdate` = the schemas of `app.schemas.production_formula`. `ValidationError` = `pydantic.ValidationError`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.

**Externals.** None mocked. `created_at`, `updated_at` come from the real `utcnow`, and no card asserts their value.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows.
- **formula** = `ProductionFormula(workspace_id=W1.id, formula_code=..., name=...)`; `version`, `is_active`, `is_default` are left to their defaults; the card gives `formula_code`, `name` and every other column that differs. No `production_formulas` row exists unless the card's Given lists it. No Given holds two rows for one normalised code in one workspace.
- A real "deleted" formula is `is_active False`, `is_default False`, as `delete_formula` leaves it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `production_formulas` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line. `raises: ValidationError` = `pytest.raises(ValidationError)` around the When, with no savepoint: nothing reaches the database.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `production_formulas`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionFormulaDAO.get_by_workspace`

### PFM-GW-01 — returns a list of the workspace's formulas
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionFormula)`.

### PFM-GW-02 — a row of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Alpha"`, `workspace_id W2.id`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFM-GW-03 — an inactive formula is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`, `is_active False`, `is_default False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PFM-GW-04 — an inactive formula takes a place in the page
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`, `is_active False`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
3. B = formula, `formula_code "FM-B"`, `name "Charlie"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GW-05 — the query orders by id, ascending
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PFM-GW-06 — rows come back by id, when the lowest id was updated
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Charlie"`.
3. B = formula, `formula_code "FM-B"`, `name "Alpha"`.
4. C = formula, `formula_code "FM-C"`, `name "Bravo"`.
5. `A.description = "Changed"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFM-GW-07 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R3 [BUG-100], R4
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Charlie"`.
3. B = formula, `formula_code "FM-B"`, `name "Alpha"`.
4. C = formula, `formula_code "FM-C"`, `name "Bravo"`.
5. D = formula, `formula_code "FM-D"`, `name "Echo"`.
6. E = formula, `formula_code "FM-E"`, `name "Delta"`.
7. `A.description = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [A.id, B.id, C.id, D.id, E.id]`.

### PFM-GW-08 — with the defaults 101 rows give 100
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 formulas E1 … E101, built with `add_all`: Ek = formula, `formula_code` = `f"FM-{k}"`, `name` = `f"Mix {k:03d}"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PFM-GW-09 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 formulas E1 … E101, built with `add_all`: Ek = formula, `formula_code` = `f"FM-{k}"`, `name` = `f"Mix {k:03d}"`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PFM-GW-10 — skip and limit cut one row from the middle
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
3. C = formula, `formula_code "FM-C"`, `name "Charlie"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GW-11 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PFM-GW-12 — limit=1 returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GW-13 — skip at the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PFM-GW-14 — skip at the last row returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GW-15 — a negative limit raises
- **Rules:** `get_by_workspace` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PFM-GW-16 — a negative skip raises
- **Rules:** `get_by_workspace` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PFM-GW-17 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PFM-GW-18 — a workspace with no rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PFM-GW-19 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="FM-P", name="Aardvark")`
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

### PFM-GW-20 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PFM-GW-21 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Alpha"`, `workspace_id W2.id`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
3. B = formula, `formula_code "FM-B"`, `name "Charlie"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductionFormulaDAO.get_by_formula_code`

### PFM-GC-01 — returns the row with that code
- **Rules:** `get_by_formula_code` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = formula, `formula_code "ROPE-1"`, `name "Rope"`.
2. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionFormula)`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Yarn"`.

### PFM-GC-02 — the same code in another workspace is not matched
- **Rules:** `get_by_formula_code` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "YARN-1"`, `name "Yarn"`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-03 — each workspace finds its own row, when the other workspace's row is the earlier one
- **Rules:** `get_by_formula_code` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "YARN-1"`, `name "Far"`, `workspace_id W2.id`.
2. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PFM-GC-04 — each workspace finds its own row, when the other workspace's row is the later one
- **Rules:** `get_by_formula_code` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.
2. Z = formula, `formula_code "YARN-1"`, `name "Far"`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W2.id)`.

**Then**
1. returns: `result.id == Z.id`.

### PFM-GC-05 — a code with no row returns None
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="NOPE-9", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-06 — the code "" returns None
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-07 — a part of the code returns None
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-08 — the end of the code returns None
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="RN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-09 — % is no wildcard
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN%", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-10 — _ is no wildcard
- **Rules:** `get_by_formula_code` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN_1", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GC-11 — a code in small letters finds the capital row
- **Rules:** `get_by_formula_code` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (the compare is exact, so `None` comes back)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="yarn-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == A.id`.

### PFM-GC-12 — a code with spaces finds the row
- **Rules:** `get_by_formula_code` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (the compare is exact, so `None` comes back)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code=" YARN-1 ", workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == A.id`.

### PFM-GC-13 — a code in capitals finds a stored small-letter row
- **Rules:** `get_by_formula_code` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (the compare is exact, so `None` comes back)

**Given**
1. A = formula, `formula_code "yarn-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == A.id`.

### PFM-GC-14 — a stored code with a leading space is found: the stored side is trimmed too
- **Rules:** `get_by_formula_code` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (the compare is exact, so `None` comes back)

**Given**
1. A = formula, `formula_code " YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == A.id`.

### PFM-GC-15 — an inactive formula is found, so its code stays taken
- **Rules:** `get_by_formula_code` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`, `is_active False`, `is_default False`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_active is False`.

### PFM-GC-16 — writes nothing: a pending row with that code stays pending and is not returned
- **Rules:** `get_by_formula_code` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "ROPE-1"`, `name "Rope"`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="YARN-1", name="Pending")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PFM-GC-17 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_formula_code` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.
2. B = formula, `formula_code "ROPE-1"`, `name "Rope"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN-1", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PFM-GC-18 — an inner space is kept: YARN -1 does not find YARN-1
- **Rules:** `get_by_formula_code` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.get_by_formula_code(db, formula_code="YARN -1", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `ProductionFormulaDAO.get_active_by_workspace`

### PFM-GA-01 — returns a list of the active formulas
- **Rules:** `get_active_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionFormula)`.

### PFM-GA-02 — an inactive formula is not returned
- **Rules:** `get_active_by_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`, `is_active False`, `is_default False`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFM-GA-03 — a row of another workspace is not returned
- **Rules:** `get_active_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Alpha"`, `workspace_id W2.id`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFM-GA-04 — the active filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`, `is_active False`, `is_default False`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
3. B = formula, `formula_code "FM-B"`, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PFM-GA-05 — the active filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`, `is_active False`, `is_default False`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
3. B = formula, `formula_code "FM-B"`, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PFM-GA-06 — an unknown workspace returns an empty list
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PFM-GA-07 — a workspace with no active formulas returns an empty list
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_active False`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFM-GA-08 — the query orders by name, then id, ascending
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
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

### PFM-GA-09 — names come back case-insensitively: "apple", "Banana", "Zulu"
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Zulu"`.
3. B = formula, `formula_code "FM-B"`, `name "apple"`.
4. C = formula, `formula_code "FM-C"`, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PFM-GA-10 — "Yarn" and "yarn" tie on the name: the lower id comes first, capital first
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Yarn"`.
3. B = formula, `formula_code "FM-B"`, `name "yarn"`.
4. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PFM-GA-11 — "yarn" and "Yarn" tie on the name: the lower id comes first, small letter first
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "yarn"`.
3. B = formula, `formula_code "FM-B"`, `name "Yarn"`.
4. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PFM-GA-12 — a tie on the name goes to the lower id, when code and version would sort otherwise and the lowest id was updated
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-M"`, `name "Yarn"`, `version 2`.
3. B = formula, `formula_code "FM-Z"`, `name "Yarn"`, `version 3`.
4. C = formula, `formula_code "FM-A"`, `name "Yarn"`, `version 1`.
5. `A.description = "Changed"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFM-GA-13 — the order is applied before the page is cut
- **Rules:** `get_active_by_workspace` R3 [BUG-1314]
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Zulu"`.
3. B = formula, `formula_code "FM-B"`, `name "apple"`.
4. C = formula, `formula_code "FM-C"`, `name "Banana"`.
5. `db.expire_all()`

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [C.id]`.

### PFM-GA-14 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_active_by_workspace` R3 [BUG-1314], R4
- **Kind:** bug
- **Expect:** xfail BUG-1314 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Charlie"`.
3. B = formula, `formula_code "FM-B"`, `name "Alpha"`.
4. C = formula, `formula_code "FM-C"`, `name "Bravo"`.
5. D = formula, `formula_code "FM-D"`, `name "Echo"`.
6. E = formula, `formula_code "FM-E"`, `name "Delta"`.
7. `B.description = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_active_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [B.id, C.id, A.id, E.id, D.id]`.

### PFM-GA-15 — with the defaults 101 rows give 100
- **Rules:** `get_active_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 formulas E1 … E101, built with `add_all`: Ek = formula, `formula_code` = `f"FM-{k}"`, `name` = `f"Mix {k:03d}"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PFM-GA-16 — limit=1000 gives all 101
- **Rules:** `get_active_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 formulas E1 … E101, built with `add_all`: Ek = formula, `formula_code` = `f"FM-{k}"`, `name` = `f"Mix {k:03d}"`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PFM-GA-17 — skip and limit cut one row from the middle
- **Rules:** `get_active_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
3. C = formula, `formula_code "FM-C"`, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GA-18 — limit=0 returns an empty list
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PFM-GA-19 — limit=1 returns one row
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GA-20 — skip at the number of rows returns an empty list
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PFM-GA-21 — skip at the last row returns one row
- **Rules:** `get_active_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PFM-GA-22 — a negative limit raises
- **Rules:** `get_active_by_workspace` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PFM-GA-23 — a negative skip raises
- **Rules:** `get_active_by_workspace` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PFM-GA-24 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_active_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="FM-P", name="Aardvark")`
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

### PFM-GA-25 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_active_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PFM-GA-26 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_active_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Alpha"`, `workspace_id W2.id`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`.
3. B = formula, `formula_code "FM-B"`, `name "Charlie"`.

**When**
- `result = dao.get_active_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductionFormulaDAO.get_default_formulas`

### PFM-GD-01 — returns a list of the active default formulas
- **Rules:** `get_default_formulas` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`.
2. X = formula, `formula_code "FM-X"`, `name "Bravo"`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id]`.
3. returns: `isinstance(result[0], ProductionFormula)`.

### PFM-GD-02 — a workspace with none returns an empty list
- **Rules:** `get_default_formulas` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFM-GD-03 — a default of another workspace is not returned
- **Rules:** `get_default_formulas` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Far"`, `workspace_id W2.id`, `is_default True`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`, `is_default True`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFM-GD-04 — an inactive formula with the flag is not returned
- **Rules:** `get_default_formulas` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = formula, `formula_code "FM-X"`, `name "Alpha"`, `is_default True`, `is_active False`.
2. A = formula, `formula_code "FM-A"`, `name "Bravo"`, `is_default True`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFM-GD-05 — two defaults give two rows
- **Rules:** `get_default_formulas` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`, `is_default True`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PFM-GD-06 — there is no cap: 101 defaults give 101 rows
- **Rules:** `get_default_formulas` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 formulas E1 … E101, built with `add_all`: Ek = formula, `formula_code` = `f"FM-{k}"`, `name` = `f"Mix {k:03d}"`, `is_default True`.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PFM-GD-07 — the query orders by name, then id, ascending
- **Rules:** `get_default_formulas` R4 [BUG-1315]
- **Kind:** bug
- **Expect:** xfail BUG-1315
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### PFM-GD-08 — names come back case-insensitively: "apple", "Banana", "Zulu"
- **Rules:** `get_default_formulas` R4 [BUG-1315]
- **Kind:** bug
- **Expect:** xfail BUG-1315 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Zulu"`, `is_default True`.
3. B = formula, `formula_code "FM-B"`, `name "apple"`, `is_default True`.
4. C = formula, `formula_code "FM-C"`, `name "Banana"`, `is_default True`.
5. `db.expire_all()`

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PFM-GD-09 — "Yarn" and "yarn" tie on the name: the lower id comes first, capital first
- **Rules:** `get_default_formulas` R4 [BUG-1315]
- **Kind:** bug
- **Expect:** xfail BUG-1315 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Yarn"`, `is_default True`.
3. B = formula, `formula_code "FM-B"`, `name "yarn"`, `is_default True`.
4. `db.expire_all()`

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PFM-GD-10 — a tie on the name goes to the lower id, when the lowest id was updated
- **Rules:** `get_default_formulas` R4 [BUG-1315]
- **Kind:** bug
- **Expect:** xfail BUG-1315 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = formula, `formula_code "FM-A"`, `name "Yarn"`, `is_default True`.
3. B = formula, `formula_code "FM-B"`, `name "Yarn"`, `is_default True`.
4. C = formula, `formula_code "FM-C"`, `name "Yarn"`, `is_default True`.
5. `A.description = "Changed"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFM-GD-11 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_default_formulas` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Bravo"`, `is_default True`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="FM-P", name="Aardvark", is_default=True)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PFM-GD-12 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_default_formulas` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`, `is_default True`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_default_formulas(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PFM-GD-13 — a W1 default is not returned for W2
- **Rules:** `get_default_formulas` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`.

**When**
- `result = dao.get_default_formulas(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

## `ProductionFormulaDAO.get_by_id_and_workspace`

### PFM-GI-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
2. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionFormula)`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Alpha"`, `result.workspace_id == W1.id`, `result.formula_code == "FM-A"`.

### PFM-GI-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. Z = formula, `formula_code "FM-Z"`, `name "Bravo"`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GI-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "FM-Z"`, `name "Bravo"`, `workspace_id W2.id`.
2. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GI-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PFM-GI-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GI-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFM-GI-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="FM-P", name="Aardvark")`
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

### PFM-GI-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. `P = ProductionFormula(workspace_id=W1.id, formula_code="FM-P", name="Aardvark")`
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

### PFM-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`.
2. B = formula, `formula_code "FM-B"`, `name "Bravo"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.description == "Edited"`.

### PFM-GI-10 — an inactive formula is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_active False`, `is_default False`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_active is False`.

## Inherited `BaseDAO` methods on `ProductionFormula`

### PFM-INH-01 — create with a dict gives the defaults
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": "YARN-1", "name": "Yarn"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `version == 1`, `is_active is True`, `is_default is False`.
3. re-read the returned row: `created_at is not None`, `updated_at is not None`.

### PFM-INH-02 — create with a ProductionFormulaCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductionFormulaCreate(formula_code="YARN-1", name="Yarn"))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `production_formulas` has exactly 0 rows.

### PFM-INH-03 — a second row with the same code is refused
- **Rules:** `inherited` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so nothing is raised)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": "YARN-1", "name": "Yarn"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `production_formulas` in W1 has exactly 1 row.

### PFM-INH-04 — a second row in other capitals is refused
- **Rules:** `inherited` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so nothing is raised)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": "yarn-1", "name": "Yarn"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `production_formulas` in W1 has exactly 1 row.

### PFM-INH-05 — a second row with spaces round the code is refused
- **Rules:** `inherited` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so nothing is raised)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": " YARN-1 ", "name": "Yarn"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `production_formulas` in W1 has exactly 1 row.

### PFM-INH-06 — the code of an inactive formula is refused: the index covers every row
- **Rules:** `inherited` R3 [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so nothing is raised)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`, `is_active False`, `is_default False`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": "YARN-1", "name": "Yarn"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `production_formulas` in W1 has exactly 1 row.

### PFM-INH-07 — the same code under another workspace is accepted
- **Rules:** `inherited` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "formula_code": "YARN-1", "name": "Yarn"})`.

**Then**
1. returns: `result.id != A.id`.
2. re-read the returned row: `workspace_id == W2.id`.

### PFM-INH-08 — another code in one workspace is accepted
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_code": "YARN-2", "name": "Yarn"})`.

**Then**
1. returns: `result.id != A.id`.
2. count: `production_formulas` in W1 has exactly 2 rows.

### PFM-INH-09 — update moving a row onto a taken code is refused
- **Rules:** `inherited` R3a [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so the change is saved)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.
2. B = formula, `formula_code "ROPE-1"`, `name "Rope"`.

**When**
- `dao.update(db, db_obj=B, obj_in={"formula_code": "YARN-1"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. re-read B: `formula_code == "ROPE-1"`.

### PFM-INH-10 — update moving a row onto a taken code in other capitals is refused
- **Rules:** `inherited` R3a [BUG-1316]
- **Kind:** bug
- **Expect:** xfail BUG-1316
- **Fails today on:** Then 1 (no unique index exists, so the change is saved)

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.
2. B = formula, `formula_code "ROPE-1"`, `name "Rope"`.

**When**
- `dao.update(db, db_obj=B, obj_in={"formula_code": "yarn-1"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. re-read B: `formula_code == "ROPE-1"`.

### PFM-INH-11 — update onto a row's own code is accepted
- **Rules:** `inherited` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = formula, `formula_code "YARN-1"`, `name "Yarn"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"formula_code": "YARN-1", "name": "Yarn two"})`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `formula_code == "YARN-1"`, `name == "Yarn two"`.

### PFM-INH-12 — update onto a code taken only in another workspace is accepted
- **Rules:** `inherited` R3a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = formula, `formula_code "YARN-1"`, `name "Far"`, `workspace_id W2.id`.
2. B = formula, `formula_code "ROPE-1"`, `name "Rope"`.

**When**
- `result = dao.update(db, db_obj=B, obj_in={"formula_code": "YARN-1"})`.

**Then**
1. returns: `result.id == B.id`.
2. re-read B: `formula_code == "YARN-1"`.

## Schemas `ProductionFormulaCreate`, `ProductionFormulaUpdate` (BUG-1317)

### PFM-SCH-01 — a whitespace-only name is refused on create
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (`min_length=1` lets it through, no error is raised)

**Given**
1. No row beyond the standing rows.

**When**
- `ProductionFormulaCreate(formula_code="YARN-1", name="   ")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.

### PFM-SCH-02 — a whitespace-only code is refused on create
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (`min_length=1` lets it through, no error is raised)

**Given**
1. No row beyond the standing rows.

**When**
- `ProductionFormulaCreate(formula_code="   ", name="Yarn")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.

### PFM-SCH-03 — a whitespace-only name is refused on update
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (`min_length=1` lets it through, no error is raised)

**Given**
1. No row beyond the standing rows.

**When**
- `ProductionFormulaUpdate(name="   ")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.

### PFM-SCH-04 — a code is stored trimmed
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (the spaces are kept)

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionFormulaCreate(formula_code=" RE-1 ", name="Yarn")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.formula_code == "RE-1"`.

### PFM-SCH-05 — a name is stored trimmed on create
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (the spaces are kept)

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionFormulaCreate(formula_code="RE-1", name=" Yarn ")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "Yarn"`.

### PFM-SCH-06 — a name is stored trimmed on update
- **Rules:** `schema` BUG-1317
- **Kind:** bug
- **Expect:** xfail BUG-1317
- **Fails today on:** Then 1 (the spaces are kept)

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionFormulaUpdate(name=" Yarn ")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "Yarn"`.

### PFM-SCH-07 — inner spaces and case are kept as typed
- **Rules:** `schema` Companion
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = ProductionFormulaCreate(formula_code="Re-1", name="Fine  Yarn")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.name == "Fine  Yarn"`.
2. returns: `result.formula_code == "Re-1"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1329, FU-1 (g) — `is_active: false` also sets `is_default = False`; re-activating does not restore the flag | `ProductionFormulaManager.update_formula` | The rule is the manager's; `get_default_formulas` R2 and R3 stand. |
| BUG-1318 (HR-7) — `limit >= 1`, 422 otherwise; the cap of 100 stays | `GET /production-formulas/` | Endpoint rule; the DAO's own negatives are the Errors cards. |
| BUG-1316, FU-1 (b) — a lost race on `create_formula` surfaces as the normal refusal, never 500 | `ProductionFormulaManager.create_formula` | `IntegrityError` translated. Needs a race simulation there. |
| BUG-1316 migration — duplicates must be cleared before the index | Whoever writes the migration | The spec gives the query. No unit test. |
| BUG-1317 through the API (422, nothing written) | `POST`, `PUT /production-formulas/` | The rule is the schema's; SCH cards test the schema. |
| FU-1 (a), BUG-100 — display order of `GET /production-formulas/` | `ProductionFormulaManager.get_formulas` | `name` case-insensitive, then `id`. |
| FU-1 (c), BUG-1022 — `update_formula`, `delete_formula` read through `get` | `ProductionFormulaManager` | Existing bug. |
| FU-1 (d) — `get_formula_items`, `add_formula_item` on a deactivated formula | `ProductionFormulaManager` | Read `production_formula_item.spec.md`. |
| FU-1 (e) — `updated_by` stamped when nothing changes (HR-9) | `ProductionFormulaManager.update_formula` | Read, not run. |
| FU-1 (f) — `_clear_other_defaults` writes no `updated_by` | `ProductionFormulaManager._clear_other_defaults` | Audit stamp. |
| Generic behavior of inherited methods; `get_multi`, `remove`, `get` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton `production_formula_dao` | none | No logic. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | `get_by_formula_code` R3 | "Compared trimmed" names the argument; the stored side follows from "stored trimmed" in the Review. Whether the read still trims a stored row is not said. | PFM-GC-14 expects a stored ` YARN-1` to be found. If the fix relies on stored values being clean, this one card goes. |
| 3 | Inherited R3 | The index's normal form is named only in the Review (`lower(trim(formula_code))`, per workspace, over every row). | INH cards use capitals and spaces, and assert pgcode only, as the Notes ask. |
| 4 | Model facts: relationships | The spec names no `lazy="joined"` relationship. | No recorder card here depends on it. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | PFM-GW-01 |
| `get_by_workspace` | R1 | PFM-GW-01, PFM-GW-02, PFM-GW-21 |
| `get_by_workspace` | R2 | PFM-GW-03, PFM-GW-04 |
| `get_by_workspace` | R3 [BUG-100] | PFM-GW-05, PFM-GW-06, PFM-GW-07 |
| `get_by_workspace` | R4 | PFM-GW-07, PFM-GW-08, PFM-GW-09, PFM-GW-10 |
| `get_by_workspace` | R5 | PFM-GW-11, PFM-GW-12, PFM-GW-13, PFM-GW-14, PFM-GW-17, PFM-GW-18 |
| `get_by_workspace` | R6 | PFM-GW-15, PFM-GW-16 |
| `get_by_workspace` | Errors row 1 | PFM-GW-15 |
| `get_by_workspace` | Errors row 2 | PFM-GW-16 |
| `get_by_workspace` | Side effects | PFM-GW-19, PFM-GW-20 |
| `get_by_formula_code` | Returns | PFM-GC-01 |
| `get_by_formula_code` | R1 | PFM-GC-01 |
| `get_by_formula_code` | R2 | PFM-GC-02, PFM-GC-03, PFM-GC-04, PFM-GC-05, PFM-GC-06, PFM-GC-07, PFM-GC-08, PFM-GC-09, PFM-GC-10 |
| `get_by_formula_code` | R3 | PFM-GC-18 |
| `get_by_formula_code` | R3 [BUG-1316] | PFM-GC-11, PFM-GC-12, PFM-GC-13, PFM-GC-14 |
| `get_by_formula_code` | R4 | PFM-INH-03 |
| `get_by_formula_code` | R5 | PFM-GC-15 |
| `get_by_formula_code` | Side effects | PFM-GC-16, PFM-GC-17 |
| `get_active_by_workspace` | Returns | PFM-GA-01 |
| `get_active_by_workspace` | R1 | PFM-GA-01, PFM-GA-02, PFM-GA-03, PFM-GA-04, PFM-GA-05, PFM-GA-26 |
| `get_active_by_workspace` | R2 | PFM-GA-06, PFM-GA-07, PFM-GA-18, PFM-GA-19, PFM-GA-20, PFM-GA-21 |
| `get_active_by_workspace` | R3 [BUG-1314] | PFM-GA-08, PFM-GA-09, PFM-GA-10, PFM-GA-11, PFM-GA-12, PFM-GA-13, PFM-GA-14 |
| `get_active_by_workspace` | R4 | PFM-GA-14, PFM-GA-15, PFM-GA-16, PFM-GA-17 |
| `get_active_by_workspace` | R5 | PFM-GA-22, PFM-GA-23 |
| `get_active_by_workspace` | Errors row 1 | PFM-GA-22 |
| `get_active_by_workspace` | Errors row 2 | PFM-GA-23 |
| `get_active_by_workspace` | Side effects | PFM-GA-24, PFM-GA-25 |
| `get_default_formulas` | Returns | PFM-GD-01 |
| `get_default_formulas` | R1 | PFM-GD-01, PFM-GD-02, PFM-GD-03, PFM-GD-13 |
| `get_default_formulas` | R2 | PFM-GD-04 |
| `get_default_formulas` | R3 | PFM-GD-05, PFM-GD-06 |
| `get_default_formulas` | R4 [BUG-1315] | PFM-GD-07, PFM-GD-08, PFM-GD-09, PFM-GD-10 |
| `get_default_formulas` | Side effects | PFM-GD-11, PFM-GD-12 |
| `get_by_id_and_workspace` | Returns | PFM-GI-01 |
| `get_by_id_and_workspace` | R1 | PFM-GI-01 |
| `get_by_id_and_workspace` | R2 | PFM-GI-02, PFM-GI-03, PFM-GI-04 |
| `get_by_id_and_workspace` | R3 | PFM-GI-05, PFM-GI-06, PFM-GI-07 |
| `get_by_id_and_workspace` | R4 | PFM-GI-10 |
| `get_by_id_and_workspace` | Side effects | PFM-GI-07, PFM-GI-08, PFM-GI-09 |
| `inherited` | R1 | PFM-INH-01 |
| `inherited` | R2 | PFM-INH-02 |
| `inherited` | R3 | PFM-INH-07, PFM-INH-08 |
| `inherited` | R3 [BUG-1316] | PFM-INH-03, PFM-INH-04, PFM-INH-05, PFM-INH-06 |
| `inherited` | R3a | PFM-INH-11, PFM-INH-12 |
| `inherited` | R3a [BUG-1316] | PFM-INH-09, PFM-INH-10 |
| `schema` | BUG-1317 | PFM-SCH-01, PFM-SCH-02, PFM-SCH-03, PFM-SCH-04, PFM-SCH-05, PFM-SCH-06 |
| `schema` | Companion | PFM-SCH-07 |
