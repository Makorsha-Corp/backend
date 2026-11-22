# Test cases — `app/dao/production_formula_stage.py`

> **Spec:** `tests/unit/dao/production_formula_stage.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `production_formula_stage.verify.md` (case-missing Findings 1 … 3; recipes R-1 … R-3): R-1 → PFS-I-05; R-2 → PFS-I-06; R-3 → PFS-G-14, PFS-I-07. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 21 cases · 21 expected-to-pass · 0 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_formula` 14 · `get_by_id_and_workspace` 7.
- **Depth:** lighter target (skill step 1a): two thin reads; the module writes no stock, money or order state.
- **Expected-to-fail:** none. No rule here carries a bug tag.
- **Commit spies:** none. Both methods only read.
- **Notable design choices:** R3's three named values sit in one card, against name and insert order. Ties need no card: `stage_order` is unique per formula. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** PFS-I-05, PFS-I-06 (by-id read: another workspace's stage at the earlier id; a stage of PFD, with no `production_formulas` in the statement); PFS-G-14, PFS-I-07 (an unflushed edit stays unflushed).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PFS` = `app/dao/production_formula_stage.py`. `G` get_by_formula · `I` get_by_id_and_workspace.

**Actors and fixed values.**
- `dao` = the singleton `production_formula_stage_dao` (`from app.dao.production_formula_stage import production_formula_stage_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProductionFormulaStage` = `app.models.production_formula_stage.ProductionFormulaStage`. `ProductionFormula` = `app.models.production_formula.ProductionFormula`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces from `make_workspace`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows.
  - PF1 = `ProductionFormula(workspace_id=W1.id, formula_code="FM-T-001", name="Mix")`. PF2 = the same, but `formula_code "FM-T-002"`. PFD = the same, but `formula_code "FM-T-003"`, `is_active False`.
- **stage** = `production_formula_stages` row built with `ProductionFormulaStage`: `workspace_id W1.id`, `formula_id PF1.id`, `name "Stage"`. The card always gives `stage_order`; after the word "but" it lists every other column that differs.
- No `production_formula_stages` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `production_formula_stages` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `production_formula_stages`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionFormulaStageDAO.get_by_formula`

### PFS-G-01 — returns a list of the formula's stages
- **Rules:** `get_by_formula` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.
2. B = stage, `stage_order 2`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionFormulaStage)`.

### PFS-G-02 — a stage of another formula of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stage, `stage_order 2`.
2. B = stage, `stage_order 1`, but `formula_id PF2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PFS-G-03 — the right formula under another workspace returns an empty list
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PFS-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_formula` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PFS-G-05 — a W2 row on a W1 formula is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PFS-G-06 — a W2 row on a W1 formula is not returned for W1, though it sorts first
- **Rules:** `get_by_formula` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = stage, `stage_order 1`, but `workspace_id W2.id`.
2. A = stage, `stage_order 2`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PFS-G-07 — an unknown formula id returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_formula(db, formula_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFS-G-08 — formula id 0 returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_formula(db, formula_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFS-G-09 — a formula with no rows returns an empty list
- **Rules:** `get_by_formula` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PFS-G-10 — stages are ordered by stage_order ascending, negative and zero included, whatever the insert order or the name
- **Rules:** `get_by_formula` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stage, `stage_order 3`, but `name "Alpha"`.
2. B = stage, `stage_order -1`, but `name "Zeta"`.
3. C = stage, `stage_order 0`, but `name "Mid"`.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### PFS-G-11 — there is no cap: 101 stages give 101 rows
- **Rules:** `get_by_formula` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 stages E1 … E101, built with `add_all`: Ek = stage, `stage_order` k. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### PFS-G-12 — the stages of a deactivated formula are returned
- **Rules:** `get_by_formula` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Formula PFD has `is_active False`: it is a standing row.
2. A = stage, `stage_order 1`, but `formula_id PFD.id`.

**When**
- `result = dao.get_by_formula(db, formula_id=PFD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PFS-G-13 — writes nothing: a pending stage that sorts first stays pending and alone in the session
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stage, `stage_order 2`.
2. `P = ProductionFormulaStage(workspace_id=W1.id, formula_id=PF1.id, stage_order=1, name="Pending")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. statement: `"production_formulas" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### PFS-G-14 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_formula` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.
2. B = stage, `stage_order 1`, but `formula_id PF2.id`.
3. `B.name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.name == "Edited"`.


## `ProductionFormulaStageDAO.get_by_id_and_workspace`

### PFS-I-01 — returns the stage of that id, not the first stage
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.
2. B = stage, `stage_order 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, ProductionFormulaStage)`.

### PFS-I-02 — another workspace returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PFS-I-03 — an unknown id returns None and nothing is created
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### PFS-I-04 — writes nothing: a read that finds its stage leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.
2. `P = ProductionFormulaStage(workspace_id=W1.id, formula_id=PF1.id, stage_order=2, name="Pending")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. nothing written: nothing written.
11. unchanged: unchanged(A).

### PFS-I-05 — a W2 stage at the earlier id is not returned for W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stage, `stage_order 1`, but `workspace_id W2.id`.
2. A = stage, `stage_order 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PFS-I-06 — a stage of a deactivated formula is returned, and the formula is not joined
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Formula PFD has `is_active False`: it is a standing row.
2. A = stage, `stage_order 1`, but `formula_id PFD.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"production_formulas" not in sql`.

### PFS-I-07 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stage, `stage_order 1`.
2. B = stage, `stage_order 2`.
3. `B.name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.name == "Edited"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — does a deactivated formula count as deleted for HR-4; its stages follow the answer | `ProductionFormulaManager.get_formula`, `get_formula_stages`, `delete_formula` | This DAO returns those stages by rule R5. |
| Spec FU-1 (b) — `stage_order` uniqueness: the Python check, and `uq_formula_stage_order` on a race | `ProductionFormulaManager.add_formula_stage`, `update_formula_stage` | An `IntegrityError` unless the manager maps it. |
| Review, HR-16 — line, machine and item checked against the workspace | `ProductionFormulaManager._validate_stage_refs` | This read follows the row. |
| Overview — `_seed_stage_logs_from_formula` | `ProductionBatchManager` | It reads this list to seed the batch. |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes | `ProductionFormula(..., version)`: the spec gives no value or type, and existing tests build it without one. | Conventions leave `version` out, and each formula has its own `formula_code`. |
| 2 | Model facts | `uq_formula_stage_order` is not a rule, though Review's HR-6 line rests on it. | No card. It is the schema's, and the manager's race is FU-1 (b). |
| 3 | `get_by_formula` R5 | `is_active False` is the only column named for a deactivated formula. | The PFD row sets that one column. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_formula` | Returns | PFS-G-01 |
| `get_by_formula` | R1 | PFS-G-01, PFS-G-02, PFS-G-03, PFS-G-04, PFS-G-05, PFS-G-06 |
| `get_by_formula` | R2 | PFS-G-07, PFS-G-08, PFS-G-09 |
| `get_by_formula` | R3 | PFS-G-10 |
| `get_by_formula` | R4 | PFS-G-11 |
| `get_by_formula` | R5 | PFS-G-12 |
| `get_by_formula` | Side effects | PFS-G-13, PFS-G-14 |
| `get_by_id_and_workspace` | Returns | PFS-I-01 |
| `get_by_id_and_workspace` | R1 | PFS-I-01, PFS-I-02, PFS-I-03, PFS-I-05, PFS-I-06 |
| `get_by_id_and_workspace` | Side effects | PFS-I-04, PFS-I-07 |
