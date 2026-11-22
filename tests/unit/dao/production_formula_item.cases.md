# Test cases — `app/dao/production_formula_item.py`

> **Spec:** `tests/unit/dao/production_formula_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 is the owner's own answer.
> **Revision:** 1 — the spec did not change. Additive, from `production_formula_item.verify.md` (Finding 1, recipe R-1): PFI-R-25. No other card changed, none retired.
> **Counts:** 62 cases · 56 expected-to-pass · 6 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_by_formula` 18 (3 bug) · `get_by_formula_and_role` 25 (3 bug) · `get_by_id_and_workspace` 12 · `inherited` 7.
- **Depth:** lighter target (skill step 1a). The module reads a recipe; it writes no stock itself, and its reads are plain filters. `get_by_formula_and_role` feeds stock posting, so Q1's rule is carried on both lists. Commit spies: none, the module has no writer of its own and `base.cases.md` holds them.
- **Expected-to-fail:** BUG-1319 3 (1 strict, 2 non-strict) · BUG-1320 3 (1 strict, 2 non-strict).
- **Notable design choices:**
  - Row order: pass cards compare sets or sizes. Each of the two unordered queries has one strict SQL recorder and two non-strict order cards, one of them with item, role and quantity not rising with id.
  - Q1 (owner): a line of a removed item stays visible on both lists and on the by-id read, one card each. The "JOIN" not in sql cards catch a filter on the formula or the item that a test row happens not to trip.
  - A row of workspace W2 on a formula of W1 is built on purpose: rule R1 states what the read does with it.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PFI` = `app/dao/production_formula_item.py`. `G` get_by_formula · `R` get_by_formula_and_role · `I` get_by_id_and_workspace · `INH` inherited `BaseDAO` methods on `ProductionFormulaItem`.

**Actors and fixed values.**
- `dao` = the singleton `production_formula_item_dao` (`from app.dao.production_formula_item import production_formula_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductionFormulaItem` = `app.models.production_formula_item.ProductionFormulaItem`. `ProductionFormulaItemCreate`, `ProductionFormulaItemUpdate` = the schemas of `app.schemas.production_formula_item`. `ProductionFormula` = `app.models.production_formula.ProductionFormula`. `Item` = `app.models.item.Item`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows.
  - PF1 = `ProductionFormula(workspace_id=W1.id, formula_code="FM-1", name="Yarn")`. PF2 = the same, but `formula_code "FM-2"`, `name "Rope"`. PFD = the same, but `formula_code "FM-3"`, `name "Twine"`, `is_active False`, `is_default False` (deactivated). PF9 = the same, but `formula_code "FM-9"`, `name "Far"`, `workspace_id W2.id`.
  - I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. I2 = the same, but `name "Washer"`, `name_normalized "washer"`. I3 = the same, but `name "Spring"`, `name_normalized "spring"`.
  - IX = the same as I1, but `name "Old Gasket"`, `name_normalized "old gasket"`, `is_active False` (removed). I9 = the same as I1, but `name "Far Crate"`, `name_normalized "far crate"`, `workspace_id W2.id`.
- **line** = `ProductionFormulaItem(workspace_id=W1.id, formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=2)`; the card lists every column that differs. No `production_formula_items` row exists unless the card's Given lists it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `production_formula_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `production_formula_items`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionFormulaItemDAO.get_by_formula`

### PFI-G-01 — returns a list of the parent's lines, of every role
- **Rules:** `get_by_formula` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "output"`, `item_id I2.id`.
3. C = line, `item_role "waste"`, `item_id I3.id`.
4. D = line, `item_role "byproduct"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id, C.id, D.id]`.
3. returns: `isinstance(result[0], ProductionFormulaItem)`.

### PFI-G-02 — a line of another parent is not returned
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = line, `item_role "input"`, `item_id I1.id`, `formula_id PF2.id`.
2. A = line, `item_role "input"`, `item_id I2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-G-03 — the right parent under another workspace returns an empty list
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PFI-G-04 — a W2 row on a W1 parent is returned for W2
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-G-05 — a W2 row on a W1 parent is not returned for W1
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-G-06 — an unknown parent returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-G-07 — formula_id=0 returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-G-08 — a parent with no lines returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-G-09 — the query orders by id, ascending
- **Rules:** `get_by_formula` R3 [BUG-1319]
- **Kind:** bug
- **Expect:** xfail BUG-1319
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PFI-G-10 — lines come back by id, when the lowest id was updated
- **Rules:** `get_by_formula` R3 [BUG-1319]
- **Kind:** bug
- **Expect:** xfail BUG-1319 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I1.id`, `quantity 7`.
3. B = line, `item_role "input"`, `item_id I2.id`, `quantity 9`.
4. C = line, `item_role "input"`, `item_id I3.id`, `quantity 5`.
5. `A.quantity = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFI-G-11 — lines come back by id, when item, role and quantity would each sort otherwise
- **Rules:** `get_by_formula` R3 [BUG-1319]
- **Kind:** bug
- **Expect:** xfail BUG-1319 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "output"`, `item_id I3.id`, `quantity 7`.
3. B = line, `item_role "waste"`, `item_id I1.id`, `quantity 9`.
4. C = line, `item_role "byproduct"`, `item_id I2.id`, `quantity 5`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFI-G-12 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_formula` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PFI-G-13 — a line of a deactivated formula is returned
- **Rules:** `get_by_formula` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PFD.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-G-14 — a line of a removed item is returned
- **Rules:** `get_by_formula` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-G-15 — two lines with one item and role are both returned
- **Rules:** `get_by_formula` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PFI-G-16 — the query does not read the parent tables
- **Rules:** `get_by_formula` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.

### PFI-G-17 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I2.id`.
2. `P = ProductionFormulaItem(workspace_id=W1.id, formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PFI-G-18 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.quantity = 44` (not flushed).

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.quantity == 44`.

## `ProductionFormulaItemDAO.get_by_formula_and_role`

### PFI-R-01 — returns a list of the lines of that parent and role
- **Rules:** `get_by_formula_and_role` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. X = line, `item_role "output"`, `item_id I2.id`.
3. B = line, `item_role "input"`, `item_id I3.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionFormulaItem)`.

### PFI-R-02 — a line of another parent is not returned
- **Rules:** `get_by_formula_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = line, `item_role "input"`, `item_id I1.id`, `formula_id PF2.id`.
2. A = line, `item_role "input"`, `item_id I2.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-R-03 — the right parent and role under another workspace returns an empty list
- **Rules:** `get_by_formula_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-04 — two lines with one item and role are both returned
- **Rules:** `get_by_formula_and_role` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PFI-R-05 — a role in capitals finds nothing
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="INPUT", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-06 — a leading space in the role finds nothing
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role=" input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-07 — the start of a role finds nothing
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="inp", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-08 — the end of a role finds nothing
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="put", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-09 — _ is no wildcard in a role
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="i_put", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-10 — % is no wildcard in a role
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-11 — an unknown role finds nothing
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="zzz", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-12 — a stored role with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role " input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-13 — a stored role in capitals is not found
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "INPUT"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-14 — an unknown parent returns an empty list
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=MISSING, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-15 — formula_id=0 returns an empty list
- **Rules:** `get_by_formula_and_role` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=0, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFI-R-16 — the query orders by id, ascending
- **Rules:** `get_by_formula_and_role` R3 [BUG-1320]
- **Kind:** bug
- **Expect:** xfail BUG-1320
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PFI-R-17 — lines come back by id, when the lowest id was updated
- **Rules:** `get_by_formula_and_role` R3 [BUG-1320]
- **Kind:** bug
- **Expect:** xfail BUG-1320 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I1.id`, `quantity 7`.
3. B = line, `item_role "input"`, `item_id I2.id`, `quantity 9`.
4. C = line, `item_role "input"`, `item_id I3.id`, `quantity 5`.
5. `A.quantity = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFI-R-18 — lines come back by id, when item and quantity would each sort otherwise
- **Rules:** `get_by_formula_and_role` R3 [BUG-1320]
- **Kind:** bug
- **Expect:** xfail BUG-1320 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = line, `item_role "input"`, `item_id I3.id`, `quantity 7`.
3. B = line, `item_role "input"`, `item_id I1.id`, `quantity 9`.
4. C = line, `item_role "input"`, `item_id I2.id`, `quantity 5`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PFI-R-19 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_formula_and_role` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`: Ek = line.
2. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PFI-R-20 — a line of a deactivated formula is returned
- **Rules:** `get_by_formula_and_role` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PFD.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-R-21 — a line of a removed item is returned
- **Rules:** `get_by_formula_and_role` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PFI-R-22 — the query does not read the parent tables
- **Rules:** `get_by_formula_and_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `"JOIN" not in sql`.

### PFI-R-23 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_formula_and_role` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I2.id`.
2. `P = ProductionFormulaItem(workspace_id=W1.id, formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PFI-R-24 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_formula_and_role` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.quantity = 44` (not flushed).

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.quantity == 44`.

### PFI-R-25 — a W2 line on the W1 parent is not returned for W1
- **Rules:** `get_by_formula_and_role` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `item_role "input"`, `item_id I1.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `ProductionFormulaItemDAO.get_by_id_and_workspace`

### PFI-I-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = line, `item_role "input"`, `item_id I2.id`.
2. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionFormulaItem)`.
2. returns: `result.id == A.id`.
3. returns: `result.formula_id == PF1.id`, `result.workspace_id == W1.id`, `result.item_role == "input"`, `result.quantity == 2`.

### PFI-I-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. Z = line, `item_id I9.id`, `item_role "input"`, `workspace_id W2.id`, `formula_id PF9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFI-I-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `item_id I9.id`, `item_role "input"`, `workspace_id W2.id`, `formula_id PF9.id`.
2. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFI-I-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PFI-I-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFI-I-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFI-I-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. `P = ProductionFormulaItem(workspace_id=W1.id, formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=1)`
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

### PFI-I-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. `P = ProductionFormulaItem(workspace_id=W1.id, formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=1)`
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

### PFI-I-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`.
2. B = line, `item_role "input"`, `item_id I2.id`.
3. `B.quantity = 44` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.quantity == 44`.

### PFI-I-10 — a line of a deactivated formula is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PFI-I-11 — a line of a removed item is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id IX.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PFI-I-12 — the query does not read the parent tables
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

## Inherited `BaseDAO` methods on `ProductionFormulaItem`

### PFI-INH-01 — create with a dict gives the defaults
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_id": PF1.id, "item_id": I1.id, "item_role": "input", "quantity": 2})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_role == "input"`, `quantity == 2`.
3. re-read the returned row: `is_optional is False`, `unit is None`, `tolerance_percentage is None`.

### PFI-INH-02 — create with a ProductionFormulaItemCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductionFormulaItemCreate(formula_id=PF1.id, item_id=I1.id, item_role="input", quantity=2))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `production_formula_items` has exactly 0 rows.

### PFI-INH-03 — an odd role is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_id": PF1.id, "item_id": I1.id, "item_role": "zzz", "quantity": 2})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_role == "zzz"`.

### PFI-INH-04 — a zero quantity is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_id": PF1.id, "item_id": I1.id, "item_role": "input", "quantity": 0})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `quantity == 0`.

### PFI-INH-05 — a negative quantity is stored
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "formula_id": PF1.id, "item_id": I1.id, "item_role": "input", "quantity": -3})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `quantity == -3`.

### PFI-INH-06 — update with a schema applies the fields set to a value
- **Rules:** `inherited` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `item_role "input"`, `item_id I1.id`, `quantity 2`, `unit "kg"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductionFormulaItemUpdate(quantity=5, unit=None))`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `quantity == 5`, `unit == "kg"`.

### PFI-INH-07 — remove hard-deletes the row
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
2. count: `production_formula_items` has exactly 1 row.
3. unchanged: unchanged(B).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — `add_formula_item` accepts a removed item and a deactivated formula | `ProductionFormulaManager.add_formula_item` | **Stock.** A line of a removed item can reach `post_outputs_to_finished_goods`. |
| FU-1 (b) — `get_formula_items` answers for a deactivated formula | `ProductionFormulaManager.get_formula_items` | Intended: `production_formula.spec.md` Q1. |
| FU-1 (c) — the same item and role twice in one formula | `ProductionFormulaManager`, `post_outputs_to_finished_goods` | **Stock.** Two output lines of one item count as two outputs, so posting is refused. |
| FU-1 (d) — `update_formula_item` drops `null` | `ProductionFormulaManager.update_formula_item` | `unit`, `tolerance_percentage` cannot be cleared. |
| FU-1 (e) — `VALID_ITEM_ROLES` repeats the schema's pattern | `ProductionFormulaManager` | Only `get_formula_items` can reach that branch. |
| Q1 — number of output lines decides where stock goes | `ProductionBatchManager.post_outputs_to_finished_goods` | **Stock.** One output posts all, two refuse. Rule of the manager; this DAO only returns the lines. |
| Generic behavior of inherited methods; `get`, `get_by_workspace`, `get_multi` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton `production_formula_item_dao` | none | No logic. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | Model facts: relationships | **Stock.** The spec names no `lazy="joined"` relationship, and the "JOIN" not in sql cards assume there is none. | If one exists, three recorder cards fail and need narrowing to the parent's name. |
| 3 | `get_by_formula_and_role` R1 | **Stock.** R6 of `get_by_formula` (two lines of one item and role) has no twin here, though here the number of rows decides stock. | R-04 tests it anyway under R1. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_formula` | Returns | PFI-G-01 |
| `get_by_formula` | R1 | PFI-G-01, PFI-G-02, PFI-G-03, PFI-G-04, PFI-G-05 |
| `get_by_formula` | R2 | PFI-G-06, PFI-G-07, PFI-G-08 |
| `get_by_formula` | R3 [BUG-1319] | PFI-G-09, PFI-G-10, PFI-G-11 |
| `get_by_formula` | R4 | PFI-G-12 |
| `get_by_formula` | R5 | PFI-G-13, PFI-G-14, PFI-G-16 |
| `get_by_formula` | R6 | PFI-G-15 |
| `get_by_formula` | Side effects | PFI-G-17, PFI-G-18 |
| `get_by_formula_and_role` | Returns | PFI-R-01 |
| `get_by_formula_and_role` | R1 | PFI-R-01, PFI-R-02, PFI-R-03, PFI-R-04, PFI-R-25 |
| `get_by_formula_and_role` | R2 | PFI-R-05, PFI-R-06, PFI-R-07, PFI-R-08, PFI-R-09, PFI-R-10, PFI-R-11, PFI-R-12, PFI-R-13, PFI-R-14, PFI-R-15 |
| `get_by_formula_and_role` | R3 [BUG-1320] | PFI-R-16, PFI-R-17, PFI-R-18 |
| `get_by_formula_and_role` | R4 | PFI-R-19 |
| `get_by_formula_and_role` | R5 | PFI-R-20, PFI-R-21, PFI-R-22 |
| `get_by_formula_and_role` | Side effects | PFI-R-23, PFI-R-24 |
| `get_by_id_and_workspace` | Returns | PFI-I-01 |
| `get_by_id_and_workspace` | R1 | PFI-I-01 |
| `get_by_id_and_workspace` | R2 | PFI-I-02, PFI-I-03, PFI-I-04 |
| `get_by_id_and_workspace` | R3 | PFI-I-05, PFI-I-06, PFI-I-07 |
| `get_by_id_and_workspace` | R4 | PFI-I-10, PFI-I-11, PFI-I-12 |
| `get_by_id_and_workspace` | Side effects | PFI-I-07, PFI-I-08, PFI-I-09 |
| `inherited` | R1 | PFI-INH-01 |
| `inherited` | R2 | PFI-INH-02 |
| `inherited` | R3 | PFI-INH-03, PFI-INH-04, PFI-INH-05 |
| `inherited` | R4 | PFI-INH-06 |
| `inherited` | R5 | PFI-INH-07 |
