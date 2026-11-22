# Test cases — `app/dao/production_batch.py`

> **Spec:** `tests/unit/dao/production_batch.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 is the owner's own answer; P1, P2, Q2, Q3 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `production_batch.verify.md`: Finding 1 (R-1a … R-1d) → BAT-GW-33, GL-34, GF-33, GS-41; Finding 2 (R-2) → BAT-GF-34; Finding 3 (R-3a, R-3b) → BAT-GS-42, GN-33; Finding 4 (R-4) → BAT-CS-30, CS-31, CS-32. No other card changed, none retired.
> **Counts:** 227 cases · 189 expected-to-pass · 38 expected-to-fail (bugs) · 14 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 33 (8 bug) · `get_by_production_line` 34 (5 bug) · `get_by_formula` 34 (6 bug) · `get_by_status` 42 (6 bug) · `count_by_status` 32 (3 bug) · `get_by_id_and_workspace` 12 · `generate_batch_number` 33 (10 bug) · `inherited` 7.
- **Depth:** full (skill step 1a): batches carry stock, the hide rule of BUG-1330 decides what a user can reach, and the number generator has real decisions. `create` and `update` each have one commit spy; the DAO's own code writes nothing.
- **Expected-to-fail:** BUG-1321 13 (4 strict, 9 non-strict) · BUG-1330 15 (15 strict, 0 non-strict) · BUG-1333 8 (8 strict, 0 non-strict) · BUG-1334 2 (2 strict, 0 non-strict).
- **Notable design choices:**
  - Tied dates: BUG-1321's four lists each have one strict SQL recorder and two non-strict cards; the second has number, shift, quantity and stamp not rising with id, and a row of an older date with the highest id. Distinct dates are ordered today: plain pass cards, ordered, with an older date on a higher id.
  - BUG-1330: strict cards, a W2 row on a line of the soft-deleted W1 factory in each method, and pass companions for "changes nothing", "inactive hides nothing", "back once live". `get_by_production_line` R2a's page card is left out: when the line's factory is deleted the whole answer is `[]`.
  - `no place in the page` cards can use a chosen row here, unlike the unordered modules: dates decide the order today, so `skip=1, limit=1` gives A today and B after the fix, every time.
  - `generate_batch_number`: every card sets both clocks. R2 is tested both ways across New Year, so a fix that only moves one way cannot pass. R5 has four shapes, with the larger number stored first and last.
  - R7, one split forced by the spec's Today note: `BATCH-2026-` beside `-005` is a **pass** card, since a shorter text sorts lower and so that row never sorts highest; the others are strict. See Spec gaps.
  - The windows card and the R9 card each have one list comprehension in the When, because the rule itself is about several calls.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none; the lost race of the number is the manager's (FU-1 (e)).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `BAT` = `app/dao/production_batch.py`. `GW` get_by_workspace · `GL` get_by_production_line · `GF` get_by_formula · `GS` get_by_status · `CS` count_by_status · `GI` get_by_id_and_workspace · `GN` generate_batch_number · `INH` inherited `BaseDAO` methods on `ProductionBatch`.

**Actors and fixed values.**
- `dao` = the singleton `production_batch_dao` (`from app.dao.production_batch import production_batch_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `ProductionBatch` = `app.models.production_batch.ProductionBatch`. `ProductionBatchCreate` = the schema of `app.schemas.production_batch`. `ProductionLine` = `app.models.production_line.ProductionLine`. `ProductionFormula` = `app.models.production_formula.ProductionFormula`. `Factory` = `app.models.factory.Factory`. `date`, `datetime`, `timedelta` = the `datetime` module's classes, imported by the test before any patch. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.
- D1 … D5 = `date(2026, 3, 1)` … `date(2026, 3, 5)`. T9 … T12 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)`. CK = `datetime(2026, 6, 1, 12, 0, 0)`.

**Externals.** The clock in `generate_batch_number`, and only there. **clocks(L, U)** = during the When, `patch("app.dao.production_batch.datetime", create=True)` with `.now.return_value = L`, and `patch("app.dao.production_batch.utcnow", create=True, return_value=U)`. Every GN card sets both, so it runs today and after BUG-1334. `created_at`, `updated_at` come from the real `utcnow`; no card asserts their value unless it gives them.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows. U1 = one `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`.
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (soft-deleted; `is_active` stays True). FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (inactive but live). F9 = the same as F1, but `name "Far Plant"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - L1 = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Line One")`. L2 = the same, but `name "Line Two"`. LF = the same, but `name "Line Three"`, `factory_id F2.id`. LN = the same, but `name "Off Line"`, `is_active False` (inactive line in F1).
  - LD = the same as L1, but `name "Lost Line"`, `factory_id FD.id` (live line in a soft-deleted factory). LI = the same as L1, but `name "Quiet Line"`, `factory_id FI.id`. L9 = the same as L1, but `name "Far Line"`, `workspace_id W2.id`, `factory_id F9.id`.
  - PF1 = `ProductionFormula(workspace_id=W1.id, formula_code="FM-1", name="Yarn")`. PF2 = the same, but `formula_code "FM-2"`, `name "Rope"`. PFD = the same, but `formula_code "FM-3"`, `name "Twine"`, `is_active False`, `is_default False` (deactivated).
- **batch** = `ProductionBatch(workspace_id=W1.id, batch_number=..., production_line_id=L1.id, batch_date=D3, status="draft")`; `formula_id` is left to its default; the card gives `batch_number` and every other column that differs. No `production_batches` row exists unless the card's Given lists it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `production_batches` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.
- **Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line. `NotNullViolation`, `UniqueViolation` = classes of `psycopg2.errors`.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `production_batches`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionBatchDAO.get_by_workspace`

### BAT-GW-01 — returns a list of the workspace's batches, of every status
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `status "in_progress"`.
3. C = batch, `batch_number "B-C"`, `batch_date D3`, `status "completed"`.
4. D = batch, `batch_number "B-D"`, `batch_date D2`, `status "cancelled"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.
3. returns: `isinstance(result[0], ProductionBatch)`.

### BAT-GW-02 — a newer batch of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D4`.
2. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D5`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-03 — an earlier-id batch of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D5`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-04 — a batch of an inactive line is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `production_line_id LN.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-05 — a batch of an inactive formula is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-06 — a batch of a soft-deleted factory is not returned
- **Rules:** `get_by_workspace` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-07 — a W2 batch on a line of a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_workspace` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GW-08 — reading with a soft-deleted factory changes nothing
- **Rules:** `get_by_workspace` R2b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(LD).
4. unchanged: unchanged(FD).
5. statement: `written == []`.

### BAT-GW-09 — an inactive factory hides nothing
- **Rules:** `get_by_workspace` R2b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LI.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### BAT-GW-10 — once the factory is live again the batch is back, unchanged
- **Rules:** `get_by_workspace` R2b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### BAT-GW-11 — hidden whatever the status
- **Rules:** `get_by_workspace` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X, Y and V are returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`, `status "in_progress"`.
2. Y = batch, `batch_number "B-Y"`, `batch_date D5`, `production_line_id LD.id`, `status "completed"`.
3. V = batch, `batch_number "B-V"`, `batch_date D5`, `production_line_id LD.id`, `status "cancelled"`.
4. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GW-12 — a hidden batch takes no place in the page
- **Rules:** `get_by_workspace` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (X takes the first place, so A comes back)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GW-13 — the query orders by batch_date, then id, both descending
- **Rules:** `get_by_workspace` R3 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321
- **Fails today on:** Then 4 (the query orders by `batch_date` alone)

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"batch_date" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("batch_date") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### BAT-GW-14 — on a tied date the highest id comes first, when the lowest ids were updated
- **Rules:** `get_by_workspace` R3 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-A"`, `batch_date D3`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.
4. C = batch, `batch_number "B-C"`, `batch_date D3`.
5. D = batch, `batch_number "B-D"`, `batch_date D3`.
6. `A.notes = "Changed"`, `B.notes = "Changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### BAT-GW-15 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id
- **Rules:** `get_by_workspace` R3 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-M"`, `batch_date D3`, `shift "B"`, `expected_output_quantity 7`, `created_at T11`.
3. B = batch, `batch_number "B-Z"`, `batch_date D3`, `shift "C"`, `expected_output_quantity 9`, `created_at T9`.
4. C = batch, `batch_number "B-A"`, `batch_date D3`, `shift "A"`, `expected_output_quantity 5`, `created_at T10`.
5. D = batch, `batch_number "B-N"`, `batch_date D2`, `created_at T12`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### BAT-GW-16 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R3 [BUG-1321], R4
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-A"`, `batch_date D3`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.
4. C = batch, `batch_number "B-C"`, `batch_date D3`.
5. D = batch, `batch_number "B-D"`, `batch_date D3`.
6. E = batch, `batch_number "B-E"`, `batch_date D3`.
7. `A.notes = "Changed"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### BAT-GW-17 — the later date comes first, whatever the ids
- **Rules:** `get_by_workspace` R3a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### BAT-GW-18 — an older date with the higher id comes after
- **Rules:** `get_by_workspace` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### BAT-GW-19 — the order is applied before the page is cut
- **Rules:** `get_by_workspace` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### BAT-GW-20 — with the defaults 101 rows give 100
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### BAT-GW-21 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### BAT-GW-22 — skip and limit cut one row from the middle
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. C = batch, `batch_number "B-C"`, `batch_date D3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GW-23 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### BAT-GW-24 — limit=1 returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### BAT-GW-25 — skip at the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GW-26 — skip at the last row returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GW-27 — a negative limit raises
- **Rules:** `get_by_workspace` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GW-28 — a negative skip raises
- **Rules:** `get_by_workspace` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GW-29 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### BAT-GW-30 — a workspace with no rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GW-31 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D4`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft")`
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

### BAT-GW-32 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GW-33 — another workspace's row sorts first and takes no place in the page
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D5`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

## `ProductionBatchDAO.get_by_production_line`

### BAT-GL-01 — returns a list of the line's batches
- **Rules:** `get_by_production_line` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionBatch)`.

### BAT-GL-02 — a newer batch of another line is not returned
- **Rules:** `get_by_production_line` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id L2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GL-03 — the right line under another workspace returns an empty list
- **Rules:** `get_by_production_line` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-04 — a W2 row on a W1 line is returned for W2
- **Rules:** `get_by_production_line` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W2.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GL-05 — a W2 row on a W1 line is not returned for W1
- **Rules:** `get_by_production_line` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-06 — a batch of an inactive line is returned
- **Rules:** `get_by_production_line` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `production_line_id LN.id`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=LN.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GL-07 — a batch of a soft-deleted factory is not returned
- **Rules:** `get_by_production_line` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=LD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-08 — a W2 batch on a line of a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_production_line` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=LD.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-09 — reading with a soft-deleted factory changes nothing
- **Rules:** `get_by_production_line` R2a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_production_line(db, production_line_id=LD.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(LD).
4. unchanged: unchanged(FD).
5. statement: `written == []`.

### BAT-GL-10 — an inactive factory hides nothing
- **Rules:** `get_by_production_line` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LI.id`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=LI.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### BAT-GL-11 — once the factory is live again the batch is back, unchanged
- **Rules:** `get_by_production_line` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_production_line(db, production_line_id=LD.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### BAT-GL-12 — an unknown line returns an empty list
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-13 — production_line_id=0 returns an empty list
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-14 — a line with no batches returns an empty list
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GL-15 — the query orders by batch_date, then id, both descending
- **Rules:** `get_by_production_line` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321
- **Fails today on:** Then 4 (the query orders by `batch_date` alone)

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"batch_date" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("batch_date") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### BAT-GL-16 — on a tied date the highest id comes first, when the lowest ids were updated
- **Rules:** `get_by_production_line` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-A"`, `batch_date D3`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.
4. C = batch, `batch_number "B-C"`, `batch_date D3`.
5. D = batch, `batch_number "B-D"`, `batch_date D3`.
6. `A.notes = "Changed"`, `B.notes = "Changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### BAT-GL-17 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id
- **Rules:** `get_by_production_line` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-M"`, `batch_date D3`, `shift "B"`, `expected_output_quantity 7`, `created_at T11`.
3. B = batch, `batch_number "B-Z"`, `batch_date D3`, `shift "C"`, `expected_output_quantity 9`, `created_at T9`.
4. C = batch, `batch_number "B-A"`, `batch_date D3`, `shift "A"`, `expected_output_quantity 5`, `created_at T10`.
5. D = batch, `batch_number "B-N"`, `batch_date D2`, `created_at T12`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### BAT-GL-18 — the later date comes first, whatever the ids
- **Rules:** `get_by_production_line` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### BAT-GL-19 — an older date with the higher id comes after
- **Rules:** `get_by_production_line` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### BAT-GL-20 — the order is applied before the page is cut
- **Rules:** `get_by_production_line` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### BAT-GL-21 — the line filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_production_line` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id L2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GL-22 — the line filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_production_line` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id L2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. returns: `X.id not in ids(result)`.

### BAT-GL-23 — with the defaults 101 rows give 100
- **Rules:** `get_by_production_line` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### BAT-GL-24 — limit=1000 gives all 101
- **Rules:** `get_by_production_line` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### BAT-GL-25 — skip and limit cut one row from the middle
- **Rules:** `get_by_production_line` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. C = batch, `batch_number "B-C"`, `batch_date D3`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GL-26 — limit=0 returns an empty list
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### BAT-GL-27 — limit=1 returns one row
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### BAT-GL-28 — skip at the number of rows returns an empty list
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GL-29 — skip at the last row returns one row
- **Rules:** `get_by_production_line` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GL-30 — a negative limit raises
- **Rules:** `get_by_production_line` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GL-31 — a negative skip raises
- **Rules:** `get_by_production_line` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GL-32 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_production_line` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D4`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BAT-GL-33 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_production_line` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GL-34 — another workspace's row sorts first and takes no place in the page
- **Rules:** `get_by_production_line` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `batch_date D5`, `workspace_id W2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

## `ProductionBatchDAO.get_by_formula`

### BAT-GF-01 — returns a list of the formula's batches
- **Rules:** `get_by_formula` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionBatch)`.

### BAT-GF-02 — a newer batch of another formula is not returned
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GF-03 — a batch with no formula is never returned
- **Rules:** `get_by_formula` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GF-04 — another workspace returns an empty list
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GF-05 — a batch of an inactive formula is returned
- **Rules:** `get_by_formula` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PFD.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GF-06 — a batch of a soft-deleted factory is not returned
- **Rules:** `get_by_formula` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GF-07 — a W2 batch on a line of a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_formula` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GF-08 — reading with a soft-deleted factory changes nothing
- **Rules:** `get_by_formula` R2a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(LD).
4. unchanged: unchanged(FD).
5. statement: `written == []`.

### BAT-GF-09 — an inactive factory hides nothing
- **Rules:** `get_by_formula` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LI.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### BAT-GF-10 — once the factory is live again the batch is back, unchanged
- **Rules:** `get_by_formula` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### BAT-GF-11 — a hidden batch takes no place in the page
- **Rules:** `get_by_formula` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (X takes the first place, so A comes back)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF1.id`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GF-12 — an unknown formula returns an empty list
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GF-13 — formula_id=0 returns an empty list
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GF-14 — the query orders by batch_date, then id, both descending
- **Rules:** `get_by_formula` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321
- **Fails today on:** Then 4 (the query orders by `batch_date` alone)

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"batch_date" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("batch_date") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### BAT-GF-15 — on a tied date the highest id comes first, when the lowest ids were updated
- **Rules:** `get_by_formula` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-A"`, `batch_date D3`, `formula_id PF1.id`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`, `formula_id PF1.id`.
4. C = batch, `batch_number "B-C"`, `batch_date D3`, `formula_id PF1.id`.
5. D = batch, `batch_number "B-D"`, `batch_date D3`, `formula_id PF1.id`.
6. `A.notes = "Changed"`, `B.notes = "Changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### BAT-GF-16 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id
- **Rules:** `get_by_formula` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-M"`, `batch_date D3`, `formula_id PF1.id`, `shift "B"`, `expected_output_quantity 7`, `created_at T11`.
3. B = batch, `batch_number "B-Z"`, `batch_date D3`, `formula_id PF1.id`, `shift "C"`, `expected_output_quantity 9`, `created_at T9`.
4. C = batch, `batch_number "B-A"`, `batch_date D3`, `formula_id PF1.id`, `shift "A"`, `expected_output_quantity 5`, `created_at T10`.
5. D = batch, `batch_number "B-N"`, `batch_date D2`, `formula_id PF1.id`, `created_at T12`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### BAT-GF-17 — the later date comes first, whatever the ids
- **Rules:** `get_by_formula` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`, `formula_id PF1.id`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### BAT-GF-18 — an older date with the higher id comes after
- **Rules:** `get_by_formula` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### BAT-GF-19 — the order is applied before the page is cut
- **Rules:** `get_by_formula` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`, `formula_id PF1.id`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### BAT-GF-20 — the formula filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_formula` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GF-21 — the formula filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_formula` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `formula_id PF2.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. returns: `X.id not in ids(result)`.

### BAT-GF-22 — with the defaults 101 rows give 100
- **Rules:** `get_by_formula` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`, `formula_id PF1.id`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### BAT-GF-23 — limit=1000 gives all 101
- **Rules:** `get_by_formula` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`, `formula_id PF1.id`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### BAT-GF-24 — skip and limit cut one row from the middle
- **Rules:** `get_by_formula` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.
3. C = batch, `batch_number "B-C"`, `batch_date D3`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GF-25 — limit=0 returns an empty list
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### BAT-GF-26 — limit=1 returns one row
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### BAT-GF-27 — skip at the number of rows returns an empty list
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GF-28 — skip at the last row returns one row
- **Rules:** `get_by_formula` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GF-29 — a negative limit raises
- **Rules:** `get_by_formula` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GF-30 — a negative skip raises
- **Rules:** `get_by_formula` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GF-31 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft", formula_id=PF1.id)`
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

### BAT-GF-32 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PF1.id`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`, `formula_id PF1.id`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GF-33 — another workspace's row sorts first and takes no place in the page
- **Rules:** `get_by_formula` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `batch_date D5`, `formula_id PF1.id`, `workspace_id W2.id`, `production_line_id L9.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`, `formula_id PF1.id`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`, `formula_id PF1.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GF-34 — a W2 batch on the formula is not returned for W1
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `batch_date D5`, `formula_id PF1.id`, `workspace_id W2.id`, `production_line_id L9.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `ProductionBatchDAO.get_by_status`

### BAT-GS-01 — returns a list of the batches in that status
- **Rules:** `get_by_status` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. X = batch, `batch_number "B-X"`, `batch_date D4`, `status "completed"`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionBatch)`.

### BAT-GS-02 — the same status in another workspace is not returned
- **Rules:** `get_by_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D5`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GS-03 — a batch of an inactive line is returned
- **Rules:** `get_by_status` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `production_line_id LN.id`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GS-04 — a batch of an inactive formula is returned
- **Rules:** `get_by_status` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `formula_id PFD.id`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GS-05 — a batch of a soft-deleted factory is not returned
- **Rules:** `get_by_status` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GS-06 — a W2 batch on a line of a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_status` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-07 — reading with a soft-deleted factory changes nothing
- **Rules:** `get_by_status` R2a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(LD).
4. unchanged: unchanged(FD).
5. statement: `written == []`.

### BAT-GS-08 — an inactive factory hides nothing
- **Rules:** `get_by_status` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LI.id`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.

### BAT-GS-09 — once the factory is live again the batch is back, unchanged
- **Rules:** `get_by_status` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### BAT-GS-10 — a hidden batch takes no place in the page
- **Rules:** `get_by_status` R2a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (X takes the first place, so A comes back)

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `production_line_id LD.id`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GS-11 — a status in capitals finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="DRAFT", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-12 — a leading space in the status finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status=" draft", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-13 — the start of a status finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="dra", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-14 — the end of a status finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="aft", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-15 — _ is no wildcard in a status
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="dr_ft", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-16 — % is no wildcard in a status
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-17 — an unknown status finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="nope", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-18 — the status "" finds nothing
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-19 — a stored status with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `status " draft"`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-20 — a stored status in capitals is not found
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `status "DRAFT"`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### BAT-GS-21 — a status outside the four is matched like any other
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `status "weird"`.

**When**
- `result = dao.get_by_status(db, status="weird", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### BAT-GS-22 — the query orders by batch_date, then id, both descending
- **Rules:** `get_by_status` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321
- **Fails today on:** Then 4 (the query orders by `batch_date` alone)

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"batch_date" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("batch_date") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### BAT-GS-23 — on a tied date the highest id comes first, when the lowest ids were updated
- **Rules:** `get_by_status` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-A"`, `batch_date D3`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.
4. C = batch, `batch_number "B-C"`, `batch_date D3`.
5. D = batch, `batch_number "B-D"`, `batch_date D3`.
6. `A.notes = "Changed"`, `B.notes = "Changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### BAT-GS-24 — on a tied date the id decides, when number, shift, quantity and stamp would each sort otherwise, and an older date has the highest id
- **Rules:** `get_by_status` R4 [BUG-1321]
- **Kind:** bug
- **Expect:** xfail BUG-1321 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = batch, `batch_number "B-M"`, `batch_date D3`, `shift "B"`, `expected_output_quantity 7`, `created_at T11`.
3. B = batch, `batch_number "B-Z"`, `batch_date D3`, `shift "C"`, `expected_output_quantity 9`, `created_at T9`.
4. C = batch, `batch_number "B-A"`, `batch_date D3`, `shift "A"`, `expected_output_quantity 5`, `created_at T10`.
5. D = batch, `batch_number "B-N"`, `batch_date D2`, `created_at T12`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### BAT-GS-25 — the later date comes first, whatever the ids
- **Rules:** `get_by_status` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### BAT-GS-26 — an older date with the higher id comes after
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### BAT-GS-27 — the order is applied before the page is cut
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D3`.
2. B = batch, `batch_number "B-B"`, `batch_date D5`.
3. C = batch, `batch_number "B-C"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### BAT-GS-28 — the status filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `status "completed"`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GS-29 — the status filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `batch_date D5`, `status "completed"`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. returns: `X.id not in ids(result)`.

### BAT-GS-30 — with the defaults 101 rows give 100
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### BAT-GS-31 — limit=1000 gives all 101
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `batch_date` = `D1 + timedelta(days=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### BAT-GS-32 — skip and limit cut one row from the middle
- **Rules:** `get_by_status` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. C = batch, `batch_number "B-C"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GS-33 — limit=0 returns an empty list
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### BAT-GS-34 — limit=1 returns one row
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### BAT-GS-35 — skip at the number of rows returns an empty list
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### BAT-GS-36 — skip at the last row returns one row
- **Rules:** `get_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GS-37 — a negative limit raises
- **Rules:** `get_by_status` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GS-38 — a negative skip raises
- **Rules:** `get_by_status` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### BAT-GS-39 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D4`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BAT-GS-40 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GS-41 — another workspace's row sorts first and takes no place in the page
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D5`.
2. A = batch, `batch_number "B-A"`, `batch_date D4`.
3. B = batch, `batch_number "B-B"`, `batch_date D3`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### BAT-GS-42 — a W1 batch is not returned for W2
- **Rules:** `get_by_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_status(db, status="draft", workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

## `ProductionBatchDAO.count_by_status`

### BAT-CS-01 — with no factory, counts the rows of that workspace and status
- **Rules:** `count_by_status` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. B = batch, `batch_number "B-B"`, `status "in_progress"`, `production_line_id LF.id`.
3. X = batch, `batch_number "B-X"`.
4. Y = batch, `batch_number "B-Y"`, `status "completed"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 2`.
2. returns: `isinstance(result, int)`.

### BAT-CS-02 — rows of another workspace are not counted
- **Rules:** `count_by_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-03 — there is no cap: 101 rows give 101
- **Rules:** `count_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 batches E1 … E101, built with `add_all`: Ek = batch, `batch_number` = `f"B-{k}"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 101`.
2. returns: `isinstance(result, int)`.

### BAT-CS-04 — with a factory, counts only the batches of that factory's lines
- **Rules:** `count_by_status` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. B = batch, `batch_number "B-B"`, `status "in_progress"`, `production_line_id L2.id`.
3. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LF.id`.
4. Y = batch, `batch_number "B-Y"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=F1.id)`.

**Then**
1. returns: `result == 2`.
2. returns: `isinstance(result, int)`.

### BAT-CS-05 — factory_id=0 is a filter: 0
- **Rules:** `count_by_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=0)`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-06 — an unknown factory gives 0
- **Rules:** `count_by_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=MISSING)`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-07 — a factory with no matching batch gives 0
- **Rules:** `count_by_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. X = batch, `batch_number "B-X"`, `production_line_id LF.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=F2.id)`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-08 — no match gives 0, never None
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-09 — an unknown workspace gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=MISSING, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-10 — an unknown status gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="nope")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-11 — a status in capitals gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="IN_PROGRESS")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-12 — a leading space gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status=" in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-13 — a part of the status gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_prog")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-14 — % is no wildcard
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in%progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-15 — another separator gives 0
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in-progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-16 — a batch of an inactive line is counted, with no factory
- **Rules:** `count_by_status` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `production_line_id LN.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-17 — a batch of an inactive line is counted, with its factory
- **Rules:** `count_by_status` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `production_line_id LN.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=F1.id)`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-18 — a batch of a soft-deleted factory is not counted, with no factory
- **Rules:** `count_by_status` R4a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; today it counts 2)

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-19 — a batch of a soft-deleted factory is not counted, with that factory's id
- **Rules:** `count_by_status` R4a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; today it counts 1)

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=FD.id)`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-20 — a W2 batch on a line of a soft-deleted W1 factory is not counted for W2
- **Rules:** `count_by_status` R4a [BUG-1330]
- **Kind:** bug
- **Expect:** xfail BUG-1330
- **Fails today on:** Then 1 (the factory's state is not read; today it counts 1)

**Given**
1. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`, `workspace_id W2.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W2.id, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-21 — the count with a live factory is the same today and after the fix
- **Rules:** `count_by_status` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=F1.id)`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-22 — counting with a soft-deleted factory changes nothing
- **Rules:** `count_by_status` R4b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `isinstance(result, int)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(LD).
4. unchanged: unchanged(FD).
5. statement: `written == []`.

### BAT-CS-23 — an inactive factory hides nothing, with no factory
- **Rules:** `count_by_status` R4b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `production_line_id LI.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-24 — an inactive factory hides nothing, with its id
- **Rules:** `count_by_status` R4b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `production_line_id LI.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=FI.id)`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-25 — once the factory is live again the batch is counted
- **Rules:** `count_by_status` R4b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch, `batch_number "B-X"`, `status "in_progress"`, `production_line_id LD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=FD.id)`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.
3. unchanged: unchanged(X).

### BAT-CS-26 — a W2 row on a W1 line is counted for W2 under the W1 factory
- **Rules:** `count_by_status` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `workspace_id W2.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W2.id, status="in_progress", factory_id=F1.id)`.

**Then**
1. returns: `result == 1`.
2. returns: `isinstance(result, int)`.

### BAT-CS-27 — a W2 row on a W1 line is not counted for W1
- **Rules:** `count_by_status` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`, `workspace_id W2.id`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress", factory_id=F1.id)`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-28 — writes nothing: a pending row is not counted and stays pending
- **Rules:** `count_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=D3, status="in_progress")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BAT-CS-29 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `count_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "in_progress"`.
2. B = batch, `batch_number "B-B"`, `status "in_progress"`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 2`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-CS-30 — a stored status in capitals is not counted
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "IN_PROGRESS"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-31 — a stored status with a leading space is not counted
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status " in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

### BAT-CS-32 — a stored status that ends with the argument is not counted
- **Rules:** `count_by_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "not_in_progress"`.

**When**
- `result = dao.count_by_status(db, workspace_id=W1.id, status="in_progress")`.

**Then**
1. returns: `result == 0`.
2. returns: `isinstance(result, int)`.

## `ProductionBatchDAO.get_by_id_and_workspace`

### BAT-GI-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = batch, `batch_number "B-B"`, `batch_date D4`.
2. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProductionBatch)`.
2. returns: `result.id == A.id`.
3. returns: `result.batch_number == "B-A"`, `result.workspace_id == W1.id`, `result.production_line_id == L1.id`.
4. returns: `result.batch_date == D5`, `result.status == "draft"`.

### BAT-GI-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D4`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BAT-GI-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "B-Z"`, `workspace_id W2.id`, `production_line_id L9.id`, `batch_date D4`.
2. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BAT-GI-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### BAT-GI-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BAT-GI-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### BAT-GI-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft")`
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

### BAT-GI-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="B-P", production_line_id=L1.id, batch_date=date(2026, 3, 9), status="draft")`
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

### BAT-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. B = batch, `batch_number "B-B"`, `batch_date D4`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GI-10 — a cancelled batch is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `status "cancelled"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "cancelled"`.

### BAT-GI-11 — a batch of a soft-deleted factory is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`, `production_line_id LD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### BAT-GI-12 — the query does not read the parent tables
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `batch_date D5`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"JOIN" not in sql`.
3. statement: `"factories" not in sql`.
4. statement: `"production_lines" not in sql`.

## `ProductionBatchDAO.generate_batch_number`

### BAT-GN-01 — with no rows the number is 001
- **Rules:** `generate_batch_number` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "BATCH-2026-001"`.

### BAT-GN-02 — the year comes through when both clocks agree
- **Rules:** `generate_batch_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. clocks(datetime(2031, 3, 1, 12, 0, 0), datetime(2031, 3, 1, 12, 0, 0)).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2031-001"`.

### BAT-GN-03 — the year is the UTC year, when the local clock is already in the next year
- **Rules:** `generate_batch_number` R2 [BUG-1334]
- **Kind:** bug
- **Expect:** xfail BUG-1334
- **Fails today on:** Then 1 (the year comes from `datetime.now()`)

**Given**
1. clocks(datetime(2031, 1, 1, 0, 30, 0), datetime(2030, 12, 31, 23, 30, 0)).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2030-001"`.

### BAT-GN-04 — the year is the UTC year, when the local clock is still in the last year
- **Rules:** `generate_batch_number` R2 [BUG-1334]
- **Kind:** bug
- **Expect:** xfail BUG-1334
- **Fails today on:** Then 1 (the year comes from `datetime.now()`)

**Given**
1. clocks(datetime(2030, 12, 31, 23, 30, 0), datetime(2031, 1, 1, 0, 30, 0)).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2031-001"`.

### BAT-GN-05 — after 001 and 007 comes 008
- **Rules:** `generate_batch_number` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-001"`.
2. B = batch, `batch_number "BATCH-2026-007"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-008"`.

### BAT-GN-06 — the highest number decides, not the newest row
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-007"`.
2. B = batch, `batch_number "BATCH-2026-001"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-008"`.

### BAT-GN-07 — after 009 comes 010: padded to three digits
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-009"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-010"`.

### BAT-GN-08 — after 099 comes 100
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-099"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-100"`.

### BAT-GN-09 — after 998 comes 999
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-998"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-999"`.

### BAT-GN-10 — after 999 comes 1000
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-999"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-1000"`.

### BAT-GN-11 — after 1000 alone comes 1001
- **Rules:** `generate_batch_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-1000"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-1001"`.

### BAT-GN-12 — rows of another year do not count
- **Rules:** `generate_batch_number` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2025-050"`.
2. B = batch, `batch_number "BATCH-2027-060"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-13 — rows of another workspace do not count
- **Rules:** `generate_batch_number` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = batch, `batch_number "BATCH-2026-050"`, `workspace_id W2.id`, `production_line_id L9.id`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-14 — a W1 row counts for W1 only, when W2 has a higher number
- **Rules:** `generate_batch_number` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-003"`.
2. Z = batch, `batch_number "BATCH-2026-050"`, `workspace_id W2.id`, `production_line_id L9.id`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-004"`.

### BAT-GN-15 — another prefix with the same year does not count
- **Rules:** `generate_batch_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "XBATCH-2026-009"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-16 — a cancelled batch counts: its number is never reused
- **Rules:** `generate_batch_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`, `status "cancelled"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.

### BAT-GN-17 — a completed batch counts: its number is never reused
- **Rules:** `generate_batch_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`, `status "completed"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.

### BAT-GN-18 — a in_progress batch counts: its number is never reused
- **Rules:** `generate_batch_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`, `status "in_progress"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.

### BAT-GN-19 — with 999 and 1000 the next is 1001
- **Rules:** `generate_batch_number` R5 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the numbers are sorted as text, so 999 or 9999 wins)

**Given**
1. A = batch, `batch_number "BATCH-2026-999"`.
2. B = batch, `batch_number "BATCH-2026-1000"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-1001"`.

### BAT-GN-20 — with 1000 stored before 999 the next is 1001
- **Rules:** `generate_batch_number` R5 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the numbers are sorted as text, so 999 or 9999 wins)

**Given**
1. A = batch, `batch_number "BATCH-2026-1000"`.
2. B = batch, `batch_number "BATCH-2026-999"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-1001"`.

### BAT-GN-21 — with 999, 1000 and 1001 the next is 1002
- **Rules:** `generate_batch_number` R5 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the numbers are sorted as text, so 999 or 9999 wins)

**Given**
1. A = batch, `batch_number "BATCH-2026-999"`.
2. B = batch, `batch_number "BATCH-2026-1000"`.
3. C = batch, `batch_number "BATCH-2026-1001"`.
4. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-1002"`.

### BAT-GN-22 — with 9999 and 10000 the next is 10001
- **Rules:** `generate_batch_number` R5 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the numbers are sorted as text, so 999 or 9999 wins)

**Given**
1. A = batch, `batch_number "BATCH-2026-9999"`.
2. B = batch, `batch_number "BATCH-2026-10000"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-10001"`.

### BAT-GN-23 — a batch of a soft-deleted factory counts
- **Rules:** `generate_batch_number` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`, `production_line_id LD.id`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.

### BAT-GN-24 — the query does not read the parent tables
- **Rules:** `generate_batch_number` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`, `production_line_id LD.id`.
2. clocks(CK, CK).
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.
2. statement: `"factories" not in sql`.
3. statement: `"production_lines" not in sql`.

### BAT-GN-25 — a suffix of letters alone is ignored
- **Rules:** `generate_batch_number` R7 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the call raises ValueError: `int()` is given a suffix that is not all digits)

**Given**
1. A = batch, `batch_number "BATCH-2026-ABC"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-26 — an empty suffix alone is ignored
- **Rules:** `generate_batch_number` R7 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the call raises ValueError: `int()` is given a suffix that is not all digits)

**Given**
1. A = batch, `batch_number "BATCH-2026-"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-27 — a mixed suffix alone is ignored
- **Rules:** `generate_batch_number` R7 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the call raises ValueError: `int()` is given a suffix that is not all digits)

**Given**
1. A = batch, `batch_number "BATCH-2026-12a"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

### BAT-GN-28 — a suffix of letters beside 005 is ignored
- **Rules:** `generate_batch_number` R7 [BUG-1333]
- **Kind:** bug
- **Expect:** xfail BUG-1333
- **Fails today on:** Then 1 (the call raises ValueError: `int()` is given a suffix that is not all digits)

**Given**
1. A = batch, `batch_number "BATCH-2026-005"`.
2. B = batch, `batch_number "BATCH-2026-ABC"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-006"`.

### BAT-GN-29 — an empty suffix beside 005 sorts below it: 006
- **Rules:** `generate_batch_number` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-005"`.
2. B = batch, `batch_number "BATCH-2026-"`.
3. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-006"`.

### BAT-GN-30 — two calls with no insert between give the same number
- **Rules:** `generate_batch_number` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`.
2. clocks(CK, CK).

**When**
- `result = [dao.generate_batch_number(db, workspace_id=W1.id) for _ in range(2)]` (one list comprehension: the rule is about two calls).

**Then**
1. returns: `result == ["BATCH-2026-005", "BATCH-2026-005"]`.
2. nothing written: nothing written.

### BAT-GN-31 — writes nothing: a pending row with a higher number stays pending and does not count
- **Rules:** `generate_batch_number` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`.
2. `P = ProductionBatch(workspace_id=W1.id, batch_number="BATCH-2026-050", production_line_id=L1.id, batch_date=D3, status="draft")`
3. `db.add(P)` (not flushed).
4. clocks(CK, CK).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### BAT-GN-32 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `generate_batch_number` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-004"`.
2. B = batch, `batch_number "BATCH-2026-002"`.
3. `B.notes = "Edited"` (not flushed).
4. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "BATCH-2026-005"`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.notes == "Edited"`.

### BAT-GN-33 — a W1 row does not count for W2
- **Rules:** `generate_batch_number` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "BATCH-2026-007"`.
2. clocks(CK, CK).

**When**
- `result = dao.generate_batch_number(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == "BATCH-2026-001"`.

## Inherited `BaseDAO` methods on `ProductionBatch`

### BAT-INH-01 — create with a dict gives status draft and the stamps
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_number": "B-1", "production_line_id": L1.id, "batch_date": D3})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `status == "draft"`.
3. re-read the returned row: `created_at is not None`, `updated_at is not None`.

### BAT-INH-02 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_number": "B-1", "production_line_id": L1.id, "batch_date": D3})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `production_batches` has exactly 1 row.
3. count: after the savepoint rollback, `production_batches` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

### BAT-INH-03 — update is flushed, not committed: a rollback restores the row
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-A"`, `status "draft"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=A, obj_in={"status": "in_progress"})`.

**Then**
1. returns: `result.id == A.id`.
2. count: inside the savepoint, `production_batches` has exactly 1 row with `status == "in_progress"`.
3. count: after the savepoint rollback, `production_batches` has exactly 1 row with `status == "draft"`.
4. mock called: the `db.commit` spy was never called.

### BAT-INH-04 — create with a ProductionBatchCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductionBatchCreate(production_line_id=L1.id, batch_date=D3))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. count: `production_batches` has exactly 0 rows.

### BAT-INH-05 — a second row with one number in one workspace is refused
- **Rules:** `inherited` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-1"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "batch_number": "B-1", "production_line_id": L1.id, "batch_date": D3})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. count: `production_batches` has exactly 1 row.

### BAT-INH-06 — the same number in another workspace is accepted
- **Rules:** `inherited` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = batch, `batch_number "B-1"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "batch_number": "B-1", "production_line_id": L9.id, "batch_date": D3})`.

**Then**
1. returns: `result.id != A.id`.
2. re-read the returned row: `workspace_id == W2.id`.

### BAT-INH-07 — a status outside the four is stored
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "batch_number": "B-1", "production_line_id": L1.id, "batch_date": D3, "status": "weird"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `status == "weird"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1331 — `delete_factory` refuses while `draft` or `in_progress` batches exist, listing them | `FactoryManager.delete_factory` (FU-2; that module reopens) | **Stock, owner's answer.** Overturns `delete_factory` R5 of that spec for batches. |
| BUG-1332 — the frontend shows the blockers | frontend factory delete flow | Frontend note, not a unit test here. |
| BUG-1330 in the calendar, FU-3 | `CalendarService._collect_production_batches` | To be logged in that module's own review; its query also has no `ORDER BY`. |
| FU-1 (a) — `get_batches` applies only the first filter | `ProductionBatchManager.get_batches` | **Verified.** Pattern `silently-ignored-input`. |
| FU-1 (b) — `get_batch_stats` `total_count` equals `in_progress_count` | `ProductionBatchManager.get_batch_stats` | **Verified.** |
| FU-1 (c) — HR-10: two starts at once take the inputs twice | `ProductionBatchManager.start_batch`, `complete_batch`, `cancel_batch` | **Stock, owner.** Needs a locked read. |
| FU-1 (d) — `cancel_batch` on `in_progress` does not return the inputs | `ProductionBatchManager.cancel_batch` | **Stock, owner.** Read, not run. |
| FU-1 (e) — a lost race on the number raises `IntegrityError` | `ProductionBatchManager.create_batch` | Must retry or lock, never 500. |
| FU-1 (f) — `delete_batch` writes no `updated_by` | `ProductionBatchManager.delete_batch` |  |
| FU-1 (g) — `update_batch` cannot clear a field; stamps `updated_by` when nothing changes (HR-9) | `ProductionBatchManager.update_batch` | Read, not run. |
| FU-1 (h) — `output_variance_percentage`, `efficiency_percentage` overflow `Numeric(5, 2)` | `ProductionBatchManager.complete_batch` | **Stock.** A completion that fails with stock half posted. Read, not run. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /production-batches/` | Endpoint rule; the DAO's own negatives are the Errors cards. |
| Generic behavior of inherited methods; `get`, `get_multi`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton; dead `get_by_date_range` (P1), dead `year` parameter (P2) | none | No logic / to be removed. No card passes `year`. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `generate_batch_number` rules | The numbering goes R7, then R9: there is no R8. Nothing else in the spec shows what R8 was. | No card. If a rule was lost, it is not tested. |
| 2 | `generate_batch_number` R7 and Notes | **Stock-adjacent.** The Notes say R7 is strict xfail, but the Today note fails only "when that row sorts highest", and an empty suffix beside `-005` never does. | GN cards for that one shape are a pass card. The `-ABC` beside `-005` card assumes letters sort above digits under the `English_United States.1252` collation, as the spec's Today note implies. If not, that card XPASSes. |
| 3 | `generate_batch_number` R7 | "Not all digits" does not say how the suffix is cut: a value such as `BATCH-2026-1-2`, or a non-ASCII digit, has no stated result (HR-8's ASCII rule is not cited). | No card for those shapes. |
| 4 | Model facts: real batch states | **Stock.** The spec does not say which columns `start_batch`, `complete_batch`, `cancel_batch` write beside `status`. | `in_progress`, `completed`, `cancelled` rows carry `status` only. These reads do not look at the others; a fix that did would not be caught. |
| 5 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 6 | Model facts: relationships | **Stock.** The spec names no `lazy="joined"` relationship on `ProductionBatch`, and the recorder cards GI, GN assume there is none. | If one exists they need narrowing. |
| 7 | `get_by_production_line` R5 | Unlike `get_by_workspace` R4 it does not repeat "given 101 rows" or "consecutive windows". | The 101 cards are written anyway; the windows card sits on `get_by_workspace` only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | BAT-GW-01 |
| `get_by_workspace` | R1 | BAT-GW-01, BAT-GW-02, BAT-GW-03, BAT-GW-33 |
| `get_by_workspace` | R2 | BAT-GW-04, BAT-GW-05 |
| `get_by_workspace` | R2a [BUG-1330] | BAT-GW-06, BAT-GW-07, BAT-GW-11, BAT-GW-12 |
| `get_by_workspace` | R2b | BAT-GW-08, BAT-GW-09, BAT-GW-10 |
| `get_by_workspace` | R3 [BUG-1321] | BAT-GW-13, BAT-GW-14, BAT-GW-15, BAT-GW-16 |
| `get_by_workspace` | R3a | BAT-GW-17, BAT-GW-18, BAT-GW-19 |
| `get_by_workspace` | R4 | BAT-GW-16, BAT-GW-20, BAT-GW-21, BAT-GW-22 |
| `get_by_workspace` | R5 | BAT-GW-23, BAT-GW-24, BAT-GW-25, BAT-GW-26, BAT-GW-29, BAT-GW-30 |
| `get_by_workspace` | R6 | BAT-GW-27, BAT-GW-28 |
| `get_by_workspace` | Errors row 1 | BAT-GW-27 |
| `get_by_workspace` | Errors row 2 | BAT-GW-28 |
| `get_by_workspace` | Side effects | BAT-GW-31, BAT-GW-32 |
| `get_by_production_line` | Returns | BAT-GL-01 |
| `get_by_production_line` | R1 | BAT-GL-01, BAT-GL-02, BAT-GL-03, BAT-GL-04, BAT-GL-05, BAT-GL-21, BAT-GL-22, BAT-GL-34 |
| `get_by_production_line` | R2 | BAT-GL-06 |
| `get_by_production_line` | R2a | BAT-GL-09, BAT-GL-10, BAT-GL-11 |
| `get_by_production_line` | R2a [BUG-1330] | BAT-GL-07, BAT-GL-08 |
| `get_by_production_line` | R3 | BAT-GL-12, BAT-GL-13, BAT-GL-14, BAT-GL-26, BAT-GL-27, BAT-GL-28, BAT-GL-29 |
| `get_by_production_line` | R4 | BAT-GL-18, BAT-GL-19, BAT-GL-20 |
| `get_by_production_line` | R4 [BUG-1321] | BAT-GL-15, BAT-GL-16, BAT-GL-17 |
| `get_by_production_line` | R5 | BAT-GL-23, BAT-GL-24, BAT-GL-25 |
| `get_by_production_line` | R6 | BAT-GL-30, BAT-GL-31 |
| `get_by_production_line` | Errors row 1 | BAT-GL-30 |
| `get_by_production_line` | Errors row 2 | BAT-GL-31 |
| `get_by_production_line` | Side effects | BAT-GL-32, BAT-GL-33 |
| `get_by_formula` | Returns | BAT-GF-01 |
| `get_by_formula` | R1 | BAT-GF-01, BAT-GF-02, BAT-GF-03, BAT-GF-04, BAT-GF-20, BAT-GF-21, BAT-GF-33, BAT-GF-34 |
| `get_by_formula` | R2 | BAT-GF-05 |
| `get_by_formula` | R2a | BAT-GF-08, BAT-GF-09, BAT-GF-10 |
| `get_by_formula` | R2a [BUG-1330] | BAT-GF-06, BAT-GF-07, BAT-GF-11 |
| `get_by_formula` | R3 | BAT-GF-12, BAT-GF-13, BAT-GF-25, BAT-GF-26, BAT-GF-27, BAT-GF-28 |
| `get_by_formula` | R4 | BAT-GF-17, BAT-GF-18, BAT-GF-19 |
| `get_by_formula` | R4 [BUG-1321] | BAT-GF-14, BAT-GF-15, BAT-GF-16 |
| `get_by_formula` | R5 | BAT-GF-22, BAT-GF-23, BAT-GF-24 |
| `get_by_formula` | R6 | BAT-GF-29, BAT-GF-30 |
| `get_by_formula` | Errors row 1 | BAT-GF-29 |
| `get_by_formula` | Errors row 2 | BAT-GF-30 |
| `get_by_formula` | Side effects | BAT-GF-31, BAT-GF-32 |
| `get_by_status` | Returns | BAT-GS-01 |
| `get_by_status` | R1 | BAT-GS-01, BAT-GS-02, BAT-GS-28, BAT-GS-29, BAT-GS-41, BAT-GS-42 |
| `get_by_status` | R2 | BAT-GS-03, BAT-GS-04 |
| `get_by_status` | R2a | BAT-GS-07, BAT-GS-08, BAT-GS-09 |
| `get_by_status` | R2a [BUG-1330] | BAT-GS-05, BAT-GS-06, BAT-GS-10 |
| `get_by_status` | R3 | BAT-GS-11, BAT-GS-12, BAT-GS-13, BAT-GS-14, BAT-GS-15, BAT-GS-16, BAT-GS-17, BAT-GS-18, BAT-GS-19, BAT-GS-20, BAT-GS-21, BAT-GS-33, BAT-GS-34, BAT-GS-35, BAT-GS-36 |
| `get_by_status` | R4 | BAT-GS-25, BAT-GS-26, BAT-GS-27 |
| `get_by_status` | R4 [BUG-1321] | BAT-GS-22, BAT-GS-23, BAT-GS-24 |
| `get_by_status` | R5 | BAT-GS-30, BAT-GS-31, BAT-GS-32 |
| `get_by_status` | R6 | BAT-GS-37, BAT-GS-38 |
| `get_by_status` | Errors row 1 | BAT-GS-37 |
| `get_by_status` | Errors row 2 | BAT-GS-38 |
| `get_by_status` | Side effects | BAT-GS-39, BAT-GS-40 |
| `count_by_status` | Returns | BAT-CS-01 |
| `count_by_status` | R1 | BAT-CS-01, BAT-CS-02, BAT-CS-03 |
| `count_by_status` | R2 | BAT-CS-04, BAT-CS-05, BAT-CS-06, BAT-CS-07 |
| `count_by_status` | R3 | BAT-CS-08, BAT-CS-09, BAT-CS-10, BAT-CS-11, BAT-CS-12, BAT-CS-13, BAT-CS-14, BAT-CS-15, BAT-CS-30, BAT-CS-31, BAT-CS-32 |
| `count_by_status` | R4 | BAT-CS-16, BAT-CS-17 |
| `count_by_status` | R4a | BAT-CS-21 |
| `count_by_status` | R4a [BUG-1330] | BAT-CS-18, BAT-CS-19, BAT-CS-20 |
| `count_by_status` | R4b | BAT-CS-22, BAT-CS-23, BAT-CS-24, BAT-CS-25 |
| `count_by_status` | R5 | BAT-CS-26, BAT-CS-27 |
| `count_by_status` | Side effects | BAT-CS-28, BAT-CS-29 |
| `get_by_id_and_workspace` | Returns | BAT-GI-01 |
| `get_by_id_and_workspace` | R1 | BAT-GI-01 |
| `get_by_id_and_workspace` | R2 | BAT-GI-02, BAT-GI-03, BAT-GI-04 |
| `get_by_id_and_workspace` | R3 | BAT-GI-05, BAT-GI-06, BAT-GI-07 |
| `get_by_id_and_workspace` | R4 | BAT-GI-10, BAT-GI-11, BAT-GI-12 |
| `get_by_id_and_workspace` | Side effects | BAT-GI-07, BAT-GI-08, BAT-GI-09 |
| `generate_batch_number` | Returns | BAT-GN-01 |
| `generate_batch_number` | R1 | BAT-GN-01 |
| `generate_batch_number` | R2 | BAT-GN-02 |
| `generate_batch_number` | R2 [BUG-1334] | BAT-GN-03, BAT-GN-04 |
| `generate_batch_number` | R3 | BAT-GN-05, BAT-GN-06, BAT-GN-07, BAT-GN-08, BAT-GN-09, BAT-GN-10, BAT-GN-11 |
| `generate_batch_number` | R4 | BAT-GN-12, BAT-GN-13, BAT-GN-14, BAT-GN-15, BAT-GN-16, BAT-GN-17, BAT-GN-18, BAT-GN-33 |
| `generate_batch_number` | R5 [BUG-1333] | BAT-GN-19, BAT-GN-20, BAT-GN-21, BAT-GN-22 |
| `generate_batch_number` | R6 | BAT-GN-23, BAT-GN-24 |
| `generate_batch_number` | R7 | BAT-GN-29 |
| `generate_batch_number` | R7 [BUG-1333] | BAT-GN-25, BAT-GN-26, BAT-GN-27, BAT-GN-28 |
| `generate_batch_number` | R9 | BAT-GN-30 |
| `generate_batch_number` | Side effects | BAT-GN-31, BAT-GN-32 |
| `inherited` | R1 | BAT-INH-01, BAT-INH-02, BAT-INH-03 |
| `inherited` | R2 | BAT-INH-04 |
| `inherited` | R3 | BAT-INH-05, BAT-INH-06 |
| `inherited` | R4 | BAT-INH-07 |
