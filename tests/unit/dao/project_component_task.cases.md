# Test cases — `app/dao/project_component_task.py`

> **Spec:** `tests/unit/dao/project_component_task.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `project_component_task.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): R-1 → PCT-GC-23, GI-17; R-2 → PCT-GI-18. No other card changed; no ID retired.
> **Counts:** 41 cases · 34 expected-to-pass · 7 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_component` 23 (4 bug) · `get_incomplete_tasks` 18 (3 bug).
- **Depth:** lighter target (skill step 1a). Two filtered, paged reads; nothing written.
- **Expected-to-fail:** BUG-1447 7: PCT-GC-11, GC-12, GC-23, GI-08, GI-17 non-strict; PCT-GC-13, GI-09 strict (the SQL recorder).
- **Commit spies:** none; nothing here writes.
- **Notable design choices:**
  - Every passing card compares a set or a count: the queries have no order today (BUG-1447).
  - The hidden-row paging cards compare a count (`skip=1, limit=10` gives one row), one per filter: the note flag, the component, the completed flag.
  - The case-tie card (PCT-GC-12) is written once, on the first list; the second list shares the order rule and gets the name card and the recorder only.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PCT` = `app/dao/project_component_task.py`. `GC` get_by_component · `GI` get_incomplete_tasks.

**Actors and fixed values.**
- `dao` = the singleton `project_component_task_dao` (`from app.dao.project_component_task import project_component_task_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectComponentTask` = `app.models.project_component_task.ProjectComponentTask`. `ProjectComponent` = `app.models.project_component.ProjectComponent`. `Project` = `app.models.project.Project`. `Factory` = `app.models.factory.Factory`. `DataError` = `sqlalchemy.exc.DataError`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`; PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`; PJD = the same, but `name "Project Gone"`, `is_deleted True`, `is_active False`; PC1 = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Roof")`; PC2 = the same, but `name "Wall"`; PCD = the same, but `project_id PJD.id`, `name "Old roof"`.
- **task** = `ProjectComponentTask(workspace_id=W1.id, project_component_id=PC1.id, name=N, description="Do it")`; `is_note`, `is_completed` are left to their default `False`. The card always gives `name`; after "but" it lists every other column that differs. **note** = task, but `is_note True`. No task row exists unless the Given lists it.
- **bumpK(X)** = `db.execute(text("UPDATE project_component_tasks SET name = name WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. Passing cards compare `set(ids(result))`.
- **nothing written** = the number of `project_component_tasks` rows stored (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` lines.
- `raises: DataError` = wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.

**xfail cards.** `Expect: xfail BUG-1447` = `pytest.mark.xfail(strict=True, reason="BUG-1447")`; `(non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_component_tasks`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOProjectComponentTask.get_by_component`

### PCT-GC-01 — with is_note None: open and completed tasks and notes of the component
- **Rules:** `get_by_component` R1, R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. C = task, `name "Paint"`, but `is_completed True`.
3. N = note, `name "Remark"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {T.id, C.id, N.id}`.
3. returns: `isinstance(result[0], ProjectComponentTask)`.

### PCT-GC-02 — a row of another component is not returned
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = task, `name "Aaa"`, but `project_component_id PC2.id`.
2. T = task, `name "Fix"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GC-03 — a W2 row on a W1 component is not returned for W1
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. X = task, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GC-04 — a W2 row on a W1 component is returned for W2
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. X = task, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X.id]`.

### PCT-GC-05 — an unknown component id returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.

**When**
- `result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCT-GC-06 — component id 0 returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.

**When**
- `result = dao.get_by_component(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCT-GC-07 — is_note=True returns only notes
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. N = note, `name "Remark"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, is_note=True)`.

**Then**
1. returns: `ids(result) == [N.id]`.

### PCT-GC-08 — is_note=False returns only tasks
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. N = note, `name "Remark"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, is_note=False)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GC-09 — the note filter comes before the page: a note takes no place
- **Rules:** `get_by_component` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = note, `name "Aaa"`.
2. A = task, `name "Beta"`.
3. B = task, `name "Gamma"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, is_note=False, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCT-GC-10 — the component filter comes before the page: another component's row takes no place
- **Rules:** `get_by_component` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = task, `name "Aaa"`, but `project_component_id PC2.id`.
2. A = task, `name "Beta"`.
3. B = task, `name "Gamma"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCT-GC-11 — rows come by name, case-insensitive, whatever their ids
- **Rules:** `get_by_component` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order puts "Zulu" first)

**Given**
1. Z = task, `name "Zulu"`.
2. A = task, `name "apple"`.
3. B = note, `name "Banana"`.
4. seqscan.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, Z.id]`.

### PCT-GC-12 — names that differ only in case tie, and the lowest id comes first
- **Rules:** `get_by_component` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lowest id moves last by physical order)

**Given**
1. A = task, `name "roof"`.
2. B = task, `name "Roof"`.
3. C = task, `name "wall"`.
4. D = task, `name "Wall"`.
5. seqscan.
6. bumpK(A).

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### PCT-GC-13 — the query orders by name, then id, ascending
- **Rules:** `get_by_component` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. T = task, `name "Fix"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### PCT-GC-14 — with the defaults 104 rows give 100
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 tasks E1 … E104, built with `add_all` and flushed: Ek = task, `name` = `f"Task {k:03d}"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCT-GC-15 — limit=1000 gives all 104
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 tasks E1 … E104, built with `add_all` and flushed: Ek = task, `name` = `f"Task {k:03d}"`.
2. `all_ids` = the set of the ids of E1 … E104.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 104`.
2. returns: `set(ids(result)) == all_ids`.

### PCT-GC-16 — limit=0 returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.
2. B = task, `name "Paint"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCT-GC-17 — limit=1 returns one row
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.
2. B = task, `name "Paint"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PCT-GC-18 — skip past the end returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.
2. B = task, `name "Paint"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PCT-GC-19 — a negative limit raises DataError
- **Rules:** `get_by_component` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.

**When**
- `dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### PCT-GC-20 — a negative skip raises DataError
- **Rules:** `get_by_component` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.

**When**
- `dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### PCT-GC-21 — the rows of a component of a soft-deleted project are returned
- **Rules:** `get_by_component` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`, but `project_component_id PCD.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=PCD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GC-22 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_component` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.
2. B = task, `name "Paint"`, but `project_component_id PC2.id`.
3. `B.name = "Edited"` (not flushed).
4. `P = ProjectComponentTask(workspace_id=W1.id, project_component_id=PC1.id, name="Pending", description="Do it")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### PCT-GC-23 — names that differ only in case tie, whichever case sorts first byte-wise
- **Rules:** `get_by_component` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447 (non-strict)
- **Fails today on:** Then 1 (no order is requested)

**Given**
1. B = task, `name "Roof"`.
2. A = task, `name "roof"`.
3. C = task, `name "Banana"`.
4. D = task, `name "apple"`.

**When**
- `result = dao.get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

## `DAOProjectComponentTask.get_incomplete_tasks`

### PCT-GI-01 — with the defaults: the component's open tasks only
- **Rules:** `get_incomplete_tasks` R1, R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. C = task, `name "Paint"`, but `is_completed True`.
3. N = note, `name "Remark"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [T.id]`.
3. returns: `isinstance(result[0], ProjectComponentTask)`.

### PCT-GI-02 — is_note=True returns the open notes only
- **Rules:** `get_incomplete_tasks` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. N = note, `name "Remark"`.
3. M = note, `name "Old remark"`, but `is_completed True`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, is_note=True)`.

**Then**
1. returns: `ids(result) == [N.id]`.

### PCT-GI-03 — is_note=None returns an empty list
- **Rules:** `get_incomplete_tasks` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. N = note, `name "Remark"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, is_note=None)`.

**Then**
1. returns: `result == []`.

### PCT-GI-04 — an open task of another component is not returned
- **Rules:** `get_incomplete_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = task, `name "Aaa"`, but `project_component_id PC2.id`.
2. T = task, `name "Fix"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GI-05 — a W2 row on a W1 component is not returned for W1
- **Rules:** `get_incomplete_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.
2. X = task, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GI-06 — an unknown component id returns an empty list
- **Rules:** `get_incomplete_tasks` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCT-GI-07 — the completed filter comes before the page: a completed row takes no place
- **Rules:** `get_incomplete_tasks` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = task, `name "Aaa"`, but `is_completed True`.
2. A = task, `name "Beta"`.
3. B = task, `name "Gamma"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCT-GI-08 — open tasks come by name, case-insensitive, whatever their ids
- **Rules:** `get_incomplete_tasks` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order puts "Zulu" first)

**Given**
1. Z = task, `name "Zulu"`.
2. A = task, `name "apple"`.
3. B = task, `name "Banana"`.
4. seqscan.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, Z.id]`.

### PCT-GI-09 — the query orders by name, then id, ascending
- **Rules:** `get_incomplete_tasks` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. T = task, `name "Fix"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### PCT-GI-10 — with the defaults 104 open tasks give 100
- **Rules:** `get_incomplete_tasks` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 tasks E1 … E104, built with `add_all` and flushed: Ek = task, `name` = `f"Task {k:03d}"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCT-GI-11 — limit=1000 gives all 104
- **Rules:** `get_incomplete_tasks` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 tasks E1 … E104, built with `add_all` and flushed: Ek = task, `name` = `f"Task {k:03d}"`.
2. `all_ids` = the set of the ids of E1 … E104.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 104`.
2. returns: `set(ids(result)) == all_ids`.

### PCT-GI-12 — limit=0 returns an empty list
- **Rules:** `get_incomplete_tasks` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCT-GI-13 — a negative limit raises DataError
- **Rules:** `get_incomplete_tasks` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.

**When**
- `dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### PCT-GI-14 — a negative skip raises DataError
- **Rules:** `get_incomplete_tasks` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.

**When**
- `dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### PCT-GI-15 — the open tasks of a component of a soft-deleted project are returned
- **Rules:** `get_incomplete_tasks` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = task, `name "Fix"`, but `project_component_id PCD.id`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PCD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T.id]`.

### PCT-GI-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_incomplete_tasks` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = task, `name "Fix"`.
2. B = task, `name "Paint"`, but `project_component_id PC2.id`.
3. `B.name = "Edited"` (not flushed).
4. `P = ProjectComponentTask(workspace_id=W1.id, project_component_id=PC1.id, name="Pending", description="Do it")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### PCT-GI-17 — names that differ only in case tie, whichever case sorts first byte-wise
- **Rules:** `get_incomplete_tasks` R4 [BUG-1447]
- **Kind:** bug
- **Expect:** xfail BUG-1447 (non-strict)
- **Fails today on:** Then 1 (no order is requested)

**Given**
1. B = task, `name "Roof"`.
2. A = task, `name "roof"`.
3. C = task, `name "Banana"`.
4. D = task, `name "apple"`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### PCT-GI-18 — asked for W2, only the W2 row is returned, though the W1 row is earlier
- **Rules:** `get_incomplete_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = task, `name "Alpha"`.
2. Z = task, `name "Zed"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P1 — BUG-1278: the component access guard answers 404 for a component of a deleted project | `ProjectManager.require_component_access` | The DAO keeps R6 (PCT-GC-21, GI-15). |
| Spec FU-1 (a) — HR-7: `limit` is `Query(100, le=100)` with no `ge=1` (BUG-642 pattern) | `GET /project-component-tasks/`, `GET /project-component-notes/` | Endpoint rule; the DAO's negatives are PCT-GC-19, GC-20, GI-13, GI-14. |
| Spec FU-1 (b) — without a component, the services read the whole workspace and drop rows after paging (HR-5) | `ProjectComponentTaskService.get_tasks`, `ProjectComponentNoteService.get_notes` | Not this DAO's methods. |
| Spec FU-1 (c) — `project_component_id=0` means "no filter" in the task service | `ProjectComponentTaskService.get_tasks` | Here `0` gives `[]` (PCT-GC-06). |
| Inherited `BaseDAO` methods (`get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`) | `tests/unit/dao/base.cases.md` | Not overridden. |
| Module singleton `project_component_task_dao` | none (no logic) | Entry point of every card. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_component` | Returns | PCT-GC-01 |
| `get_by_component` | R1 | PCT-GC-01, PCT-GC-02, PCT-GC-03, PCT-GC-04, PCT-GC-05, PCT-GC-06, PCT-GC-10 |
| `get_by_component` | R2 | PCT-GC-01, PCT-GC-07, PCT-GC-08, PCT-GC-09 |
| `get_by_component` | R3 | PCT-GC-01 |
| `get_by_component` | R4 [BUG-1447] | PCT-GC-11, PCT-GC-12, PCT-GC-13, PCT-GC-23 |
| `get_by_component` | R5 | PCT-GC-09, PCT-GC-10, PCT-GC-14, PCT-GC-15, PCT-GC-16, PCT-GC-17, PCT-GC-18, PCT-GC-19, PCT-GC-20 |
| `get_by_component` | R6 | PCT-GC-21 |
| `get_by_component` | Errors | PCT-GC-19, PCT-GC-20 |
| `get_by_component` | Side effects | PCT-GC-22 |
| `get_incomplete_tasks` | Returns | PCT-GI-01 |
| `get_incomplete_tasks` | R1 | PCT-GI-01, PCT-GI-04, PCT-GI-05, PCT-GI-06, PCT-GI-18 |
| `get_incomplete_tasks` | R2 | PCT-GI-01, PCT-GI-02, PCT-GI-03 |
| `get_incomplete_tasks` | R3 | PCT-GI-01, PCT-GI-02, PCT-GI-07 |
| `get_incomplete_tasks` | R4 [BUG-1447] | PCT-GI-08, PCT-GI-09, PCT-GI-17 |
| `get_incomplete_tasks` | R5 | PCT-GI-07, PCT-GI-10, PCT-GI-11, PCT-GI-12, PCT-GI-13, PCT-GI-14 |
| `get_incomplete_tasks` | R6 | PCT-GI-15 |
| `get_incomplete_tasks` | Errors | PCT-GI-13, PCT-GI-14 |
| `get_incomplete_tasks` | Side effects | PCT-GI-16 |
