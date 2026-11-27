# Test cases — `app/dao/production_batch_stage_log.py`

> **Spec:** `tests/unit/dao/production_batch_stage_log.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `production_batch_stage_log.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → PBL-I-05; R-2 → one Then line each on PBL-G-15 and PBL-I-04; R-3 → PBL-G-16, PBL-I-06; R-4 → PBL-G-17; the Reviewer summary line on `SET NULL` corrected (Finding 4). New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 23 cases · 23 expected-to-pass · 0 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `get_by_batch` 17 · `get_by_id_and_workspace` 6.
- **Depth:** lighter target (skill step 1a): two thin reads; the module writes no stock, money or order state.
- **Expected-to-fail:** none. No rule here carries a bug tag: the order already ends in `id`.
- **Commit spies:** none. Both methods only read.
- **Notable design choices:** the tie cards give the tied rows names that do not rise with `id`; the update card runs on a sequential scan, so a lost `id` key shows. PBL-G-14 removes the formula stage through the session, which nulls the log by itself; PBL-G-17 removes it with a raw `DELETE`, so the database's `ON DELETE SET NULL` does the work. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** PBL-I-05 (another workspace's log at the earlier id); PBL-G-15, PBL-I-04 forbid `production_batches`; PBL-G-16, PBL-I-06 (an unflushed edit stays unflushed); PBL-G-17 (raw `DELETE`).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PBL` = `app/dao/production_batch_stage_log.py`. `G` get_by_batch · `I` get_by_id_and_workspace.

**Actors and fixed values.**
- `dao` = the singleton `production_batch_stage_log_dao` (`from app.dao.production_batch_stage_log import production_batch_stage_log_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProductionBatchStageLog` = `app.models.production_batch_stage_log.ProductionBatchStageLog`. `Factory`, `ProductionLine`, `ProductionBatch`, `ProductionFormula`, `ProductionFormulaStage` come from `app.models.factory`, `.production_line`, `.production_batch`, `.production_formula`, `.production_formula_stage`. `date` = `datetime.date`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces from `make_workspace`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. PL1 = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Line One")`. PF1 = `ProductionFormula(workspace_id=W1.id, formula_code="FM-T-001", name="Mix")`.
  - B1 = `ProductionBatch(workspace_id=W1.id, batch_number="PB-T-001", production_line_id=PL1.id, batch_date=date(2026, 3, 1), status="draft")`. B2 = the same, but `batch_number "PB-T-002"`.
- **log** = `production_batch_stage_logs` row built with `ProductionBatchStageLog`: `workspace_id W1.id`, `batch_id B1.id`, `stage_name "Stage"`; `status`, `formula_stage_id`, `production_line_id`, `logged_by` are not passed. The card always gives `stage_order`; after the word "but" it lists every other column that differs.
- No `production_batch_stage_logs` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `production_batch_stage_logs` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`: transaction-local, gone with the rollback. Today's read then follows physical row order.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `production_batch_stage_logs`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductionBatchStageLogDAO.get_by_batch`

### PBL-G-01 — returns a list of the batch's logs
- **Rules:** `get_by_batch` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. B = log, `stage_order 2`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProductionBatchStageLog)`.

### PBL-G-02 — a log of another batch of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, `stage_order 2`.
2. B = log, `stage_order 1`, but `batch_id B2.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PBL-G-03 — the right batch under another workspace returns an empty list
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PBL-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_batch` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PBL-G-05 — a W2 row on a W1 batch is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PBL-G-06 — a W2 row on a W1 batch is not returned for W1, though it sorts first
- **Rules:** `get_by_batch` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = log, `stage_order 1`, but `workspace_id W2.id`.
2. A = log, `stage_order 2`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PBL-G-07 — an unknown batch id returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_batch(db, batch_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PBL-G-08 — batch id 0 returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_batch(db, batch_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PBL-G-09 — a batch with no rows returns an empty list
- **Rules:** `get_by_batch` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_batch(db, batch_id=B2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PBL-G-10 — orders 2, 1, 1, 0 give the 0 row, the two 1 rows by id, then the 2 row
- **Rules:** `get_by_batch` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `stage_order 2`, but `stage_name "Alpha"`.
2. B = log, `stage_order 1`, but `stage_name "Zeta"`.
3. C = log, `stage_order 1`, but `stage_name "Mid"`.
4. D = log, `stage_order 0`, but `stage_name "Beta"`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, C.id, A.id]`.

### PBL-G-11 — the tied pair keeps its order after the lower id is updated
- **Rules:** `get_by_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 2`, but `stage_name "Alpha"`.
2. B = log, `stage_order 1`, but `stage_name "Zeta"`.
3. C = log, `stage_order 1`, but `stage_name "Mid"`.
4. D = log, `stage_order 0`, but `stage_name "Beta"`.
5. `B.stage_name = "Omega"`, then `db.flush()`.
6. `db.expire_all()`.
7. seqscan.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, C.id, A.id]`.

### PBL-G-12 — the query orders by stage_order, then id ascending
- **Rules:** `get_by_batch` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"stage_order" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("stage_order") < order_part.index(".id")`.
5. statement: `"DESC" not in order_part.upper()`.

### PBL-G-13 — there is no cap: 101 logs give 101 rows
- **Rules:** `get_by_batch` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all`: Ek = log, `stage_order` k. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### PBL-G-14 — a log whose formula stage was removed is still returned, with its name
- **Rules:** `get_by_batch` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FS1 = `ProductionFormulaStage(workspace_id=W1.id, formula_id=PF1.id, stage_order=1, name="Mixing")`, added and flushed.
2. A = log, `stage_order 1`, but `formula_stage_id FS1.id`, `stage_name "Mixing"`.
3. `db.delete(FS1)`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].formula_stage_id is None`.
3. returns: `result[0].stage_name == "Mixing"`.

### PBL-G-15 — writes nothing: a pending log that sorts first stays pending and alone in the session
- **Rules:** `get_by_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `stage_order 2`.
2. `P = ProductionBatchStageLog(workspace_id=W1.id, batch_id=B1.id, stage_name="Pending", stage_order=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

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
10. nothing written: nothing written.
11. unchanged: unchanged(A).
12. statement: `"production_batches" not in sql`.

### PBL-G-16 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_batch` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. B = log, `stage_order 1`, but `batch_id B2.id`.
3. `B.stage_name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.stage_name == "Edited"`.

### PBL-G-17 — a formula stage removed by a raw DELETE leaves its log, nulled by the database
- **Rules:** `get_by_batch` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FS1 = `ProductionFormulaStage(workspace_id=W1.id, formula_id=PF1.id, stage_order=1, name="Mixing")`, added and flushed.
2. A = log, `stage_order 1`, but `formula_stage_id FS1.id`, `stage_name "Mixing"`.
3. `db.execute(text("DELETE FROM production_formula_stages WHERE id = :i"), {"i": FS1.id})`
4. `db.expire_all()`.

**When**
- `result = dao.get_by_batch(db, batch_id=B1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].formula_stage_id is None`.
3. returns: `result[0].stage_name == "Mixing"`.


## `ProductionBatchStageLogDAO.get_by_id_and_workspace`

### PBL-I-01 — returns the log of that id, not the first log
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. B = log, `stage_order 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, ProductionBatchStageLog)`.

### PBL-I-02 — another workspace returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PBL-I-03 — an unknown id returns None and nothing is created
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### PBL-I-04 — writes nothing: a read that finds its log leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. `P = ProductionBatchStageLog(workspace_id=W1.id, batch_id=B1.id, stage_name="Pending", stage_order=2)`
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
12. statement: `"production_batches" not in sql`.

### PBL-I-05 — a W2 log at the earlier id is not returned for W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = log, `stage_order 1`, but `workspace_id W2.id`.
2. A = log, `stage_order 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PBL-I-06 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `stage_order 1`.
2. B = log, `stage_order 2`.
3. `B.stage_name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.stage_name == "Edited"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview — seeding from the formula, and the edit of a log | `ProductionBatchManager._seed_stage_logs_from_formula`, `update_batch_stage_log` | The writes are the manager's. |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts, Notes | The spec gives class names, not modules. No test imports `ProductionBatchStageLog` yet: `app.models.production_batch_stage_log` follows the pattern of its neighbours. | Conventions use the path. A wrong one fails at import, in every test. |
| 2 | Notes | `ProductionBatch(..., status)`: the spec gives no value. `"draft"` comes from `tests/unit/managers/test_item_manager.py`. | Conventions use it. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_batch` | Returns | PBL-G-01 |
| `get_by_batch` | R1 | PBL-G-01, PBL-G-02, PBL-G-03, PBL-G-04, PBL-G-05, PBL-G-06 |
| `get_by_batch` | R2 | PBL-G-07, PBL-G-08, PBL-G-09 |
| `get_by_batch` | R3 | PBL-G-10, PBL-G-11, PBL-G-12 |
| `get_by_batch` | R4 | PBL-G-13 |
| `get_by_batch` | R5 | PBL-G-14, PBL-G-17 |
| `get_by_batch` | Side effects | PBL-G-15, PBL-G-16 |
| `get_by_id_and_workspace` | Returns | PBL-I-01 |
| `get_by_id_and_workspace` | R1 | PBL-I-01, PBL-I-02, PBL-I-03, PBL-I-05 |
| `get_by_id_and_workspace` | Side effects | PBL-I-04, PBL-I-06 |
