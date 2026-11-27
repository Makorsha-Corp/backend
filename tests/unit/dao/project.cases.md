# Test cases — `app/dao/project.py`

> **Spec:** `tests/unit/dao/project.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `project.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): R-1 → PRJ-GF-27, GS-20; R-2 → PRJ-GS-21. The recipes call with `ProjectStatusEnum.PLANNING`; the cards pass `"PLANNING"`, as every card of this file does (Spec gap 1). No other card changed; no ID retired.
> **Counts:** 48 cases · 34 expected-to-pass · 14 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_factory` 27 (8 bug) · `get_by_status` 21 (6 bug).
- **Depth:** lighter target (skill step 1a). Two filtered, paged reads; nothing written.
- **Expected-to-fail:** BUG-1444 8: PRJ-GF-14, GF-15, GF-16, GF-27, GS-10, GS-20 non-strict; PRJ-GF-17, GS-11 strict (the SQL recorder). BUG-1445 3, strict: PRJ-GF-07, GF-08, GS-05; PRJ-GS-21 names BUG-1445 and BUG-1444, non-strict (its page rests on the name order). BUG-1446 2, strict: PRJ-GF-10, GS-07. The R3a cards (PRJ-GF-11 … GF-13, GS-08, GS-09) are the passing companions of BUG-1446.
- **Commit spies:** none; nothing here writes.
- **Notable design choices:**
  - Every passing card compares a set: the query has no order today (BUG-1444).
  - The hidden-row paging cards compare a count (`skip=1, limit=10` gives one row), so they do not rest on order; PRJ-GF-08 is strict for that reason.
  - Status values other than `PLANNING` are set by SQL with a cast to `projectstatusenum`, and the calls pass the status by name: the spec does not name the enum's module (Spec gap 1).
  - No card checks that the SQL does not join `factories`: the fix of BUG-1446 needs that join.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PRJ` = `app/dao/project.py`. `GF` get_by_factory · `GS` get_by_status.

**Actors and fixed values.**
- `dao` = the singleton `project_dao` (`from app.dao.project import project_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `Project` = `app.models.project.Project`. `Factory` = `app.models.factory.Factory`. `DataError` = `sqlalchemy.exc.DataError`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`). F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`; F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`; FI = the same, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False`; FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (soft-deleted; `is_active` stays True); F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.
- **project** = `Project(workspace_id=W1.id, factory_id=F1.id, name=N, description="Main")`; `status` is left to its default `PLANNING`. The card always gives `name`; after "but" it lists every other column that differs. **deleted** = `is_deleted True`, `is_active False`. No `projects` row of W1 or W2 exists unless the Given lists it.
- **set_status(X, s)** = `db.execute(text("UPDATE projects SET status = CAST(:s AS projectstatusenum) WHERE id = :i"), {"s": s, "i": X.id})`, then `db.expire_all()`.
- **bumpP(X)** = `db.execute(text("UPDATE projects SET name = name WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. Passing cards compare `set(ids(result))`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the numbers of `projects` and of `factories` rows stored (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: DataError` = wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `projects`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOProject.get_by_factory`

### PRJ-GF-01 — returns a list of the factory's projects
- **Rules:** `get_by_factory` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {A.id, B.id}`.
3. returns: `isinstance(result[0], Project)`.

### PRJ-GF-02 — a project of another factory is not returned
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = project, `name "Aaa"`, but `factory_id F2.id`.
2. A = project, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRJ-GF-03 — a W2 row on a W1 factory is not returned for W1
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. X = project, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRJ-GF-04 — a W2 row on a W1 factory is returned for W2
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. X = project, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X.id]`.

### PRJ-GF-05 — an unknown factory id returns an empty list
- **Rules:** `get_by_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRJ-GF-06 — factory id 0 returns an empty list
- **Rules:** `get_by_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `result = dao.get_by_factory(db, factory_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRJ-GF-07 — a soft-deleted project is not returned
- **Rules:** `get_by_factory` R2 [BUG-1445]
- **Kind:** bug
- **Expect:** xfail BUG-1445
- **Fails today on:** Then 2 (the deleted project is returned)

**Given**
1. A = project, `name "Alpha"`.
2. D = project, `name "Gone"`, but deleted.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `set(ids(result)) == {A.id}`.

### PRJ-GF-08 — a soft-deleted project takes no place in the page
- **Rules:** `get_by_factory` R2 [BUG-1445]
- **Kind:** bug
- **Expect:** xfail BUG-1445
- **Fails today on:** Then 1 (the deleted project fills a place: two rows come back)

**Given**
1. D = project, `name "Aaa"`, but deleted.
2. A = project, `name "Beta"`.
3. B = project, `name "Gamma"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PRJ-GF-09 — an inactive project and a completed one are returned
- **Rules:** `get_by_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = project, `name "Idle"`, but `is_active False`.
2. C = project, `name "Done"`.
3. set_status(C, "COMPLETED").

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `set(ids(result)) == {I.id, C.id}`.

### PRJ-GF-10 — a soft-deleted factory gives an empty list
- **Rules:** `get_by_factory` R3 [BUG-1446]
- **Kind:** bug
- **Expect:** xfail BUG-1446
- **Fails today on:** Then 1 (the factory's projects are returned)

**Given**
1. P = project, `name "Lost"`, but `factory_id FD.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRJ-GF-11 — an inactive but live factory hides nothing
- **Rules:** `get_by_factory` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = project, `name "Idle work"`, but `factory_id FI.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FI.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [P.id]`.

### PRJ-GF-12 — the call changes no row of the deleted factory or its project
- **Rules:** `get_by_factory` R3a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = project, `name "Lost"`, but `factory_id FD.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(P).
3. unchanged: unchanged(FD).

### PRJ-GF-13 — once the factory is live again its project is returned
- **Rules:** `get_by_factory` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = project, `name "Lost"`, but `factory_id FD.id`.
2. `FD.is_deleted = False`, then `db.flush()`.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [P.id]`.

### PRJ-GF-14 — projects come by name, case-insensitive, whatever their ids
- **Rules:** `get_by_factory` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order puts "Zulu" first)

**Given**
1. Z = project, `name "Zulu"`.
2. A = project, `name "apple"`.
3. B = project, `name "Banana"`.
4. seqscan.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, Z.id]`.

### PRJ-GF-15 — names that differ only in case tie, and the lowest id comes first
- **Rules:** `get_by_factory` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lowest id moves last by physical order)

**Given**
1. A = project, `name "roof"`.
2. B = project, `name "Roof"`.
3. C = project, `name "wall"`.
4. D = project, `name "Wall"`.
5. seqscan.
6. bumpP(A).

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### PRJ-GF-16 — the order comes before the page, and the other factory's row takes no place
- **Rules:** `get_by_factory` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order gives "alpha" second)

**Given**
1. X = project, `name "Aaa"`, but `factory_id F2.id`.
2. A = project, `name "Beta"`.
3. B = project, `name "alpha"`.
4. C = project, `name "Gamma"`.
5. seqscan.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [A.id]`.

### PRJ-GF-17 — the query orders by name, then id, ascending
- **Rules:** `get_by_factory` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = project, `name "Alpha"`.
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

### PRJ-GF-18 — with the defaults 104 projects give 100
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 projects E1 … E104, built with `add_all` and flushed: Ek = project, `name` = `f"Project {k:03d}"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PRJ-GF-19 — limit=1000 gives all 104
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 projects E1 … E104, built with `add_all` and flushed: Ek = project, `name` = `f"Project {k:03d}"`.
2. `all_ids` = the set of the ids of E1 … E104.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 104`.
2. returns: `set(ids(result)) == all_ids`.

### PRJ-GF-20 — limit=0 returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PRJ-GF-21 — limit=1 returns one row
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PRJ-GF-22 — skip past the end returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRJ-GF-23 — a negative limit raises DataError
- **Rules:** `get_by_factory` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### PRJ-GF-24 — a negative skip raises DataError
- **Rules:** `get_by_factory` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### PRJ-GF-25 — writes nothing: a pending project stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_factory` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`, but `factory_id F2.id`.
3. `B.name = "Edited"` (not flushed).
4. `P = Project(workspace_id=W1.id, factory_id=F1.id, name="Pending", description="Main")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### PRJ-GF-26 — the factory filter comes before the page: another factory's row takes no place
- **Rules:** `get_by_factory` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = project, `name "Aaa"`, but `factory_id F2.id`.
2. A = project, `name "Beta"`.
3. B = project, `name "Gamma"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PRJ-GF-27 — names that differ only in case tie, whichever case sorts first byte-wise
- **Rules:** `get_by_factory` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 1 (no order is requested)

**Given**
1. B = project, `name "Roof"`.
2. A = project, `name "roof"`.
3. C = project, `name "Banana"`.
4. D = project, `name "apple"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

## `DAOProject.get_by_status`

### PRJ-GS-01 — returns the projects in that status, of every factory
- **Rules:** `get_by_status` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`, but `factory_id F2.id`.
3. C = project, `name "Done"`.
4. set_status(C, "COMPLETED").

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {A.id, B.id}`.
3. returns: `isinstance(result[0], Project)`.

### PRJ-GS-02 — a W2 row on a W1 factory is not returned for W1
- **Rules:** `get_by_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. X = project, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRJ-GS-03 — a W2 row on a W1 factory is returned for W2
- **Rules:** `get_by_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. X = project, `name "Aaa"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X.id]`.

### PRJ-GS-04 — a lowercase status raises DataError 22P02
- **Rules:** `get_by_status` Inputs, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `dao.get_by_status(db, status="planning", workspace_id=W1.id)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22P02"`.
2. nothing written: nothing written.

### PRJ-GS-05 — a soft-deleted project is not returned
- **Rules:** `get_by_status` R2 [BUG-1445]
- **Kind:** bug
- **Expect:** xfail BUG-1445
- **Fails today on:** Then 2 (the deleted project is returned)

**Given**
1. A = project, `name "Alpha"`.
2. D = project, `name "Gone"`, but deleted.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `set(ids(result)) == {A.id}`.

### PRJ-GS-06 — an inactive project is returned
- **Rules:** `get_by_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = project, `name "Idle"`, but `is_active False`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [I.id]`.

### PRJ-GS-07 — a project of a soft-deleted factory is not returned; the others are
- **Rules:** `get_by_status` R3 [BUG-1446]
- **Kind:** bug
- **Expect:** xfail BUG-1446
- **Fails today on:** Then 2 (the deleted factory's project is returned)

**Given**
1. A = project, `name "Alpha"`.
2. P = project, `name "Lost"`, but `factory_id FD.id`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `set(ids(result)) == {A.id}`.

### PRJ-GS-08 — a project of an inactive but live factory is returned
- **Rules:** `get_by_status` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = project, `name "Idle work"`, but `factory_id FI.id`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [P.id]`.

### PRJ-GS-09 — the call changes no row of the deleted factory or its project
- **Rules:** `get_by_status` R3a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = project, `name "Lost"`, but `factory_id FD.id`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(P).
3. unchanged: unchanged(FD).

### PRJ-GS-10 — projects come by name, case-insensitive, whatever their ids
- **Rules:** `get_by_status` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order puts "Zulu" first)

**Given**
1. Z = project, `name "Zulu"`.
2. A = project, `name "apple"`, but `factory_id F2.id`.
3. B = project, `name "Banana"`.
4. seqscan.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, Z.id]`.

### PRJ-GS-11 — the query orders by name, then id, ascending
- **Rules:** `get_by_status` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = project, `name "Alpha"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### PRJ-GS-12 — with the defaults 104 projects give 100
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 projects E1 … E104, built with `add_all` and flushed: Ek = project, `name` = `f"Project {k:03d}"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PRJ-GS-13 — limit=1000 gives all 104
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 104 projects E1 … E104, built with `add_all` and flushed: Ek = project, `name` = `f"Project {k:03d}"`.
2. `all_ids` = the set of the ids of E1 … E104.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 104`.
2. returns: `set(ids(result)) == all_ids`.

### PRJ-GS-14 — limit=0 returns an empty list
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PRJ-GS-15 — skip past the end returns an empty list
- **Rules:** `get_by_status` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `result == []`.

### PRJ-GS-16 — a negative limit raises DataError
- **Rules:** `get_by_status` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### PRJ-GS-17 — a negative skip raises DataError
- **Rules:** `get_by_status` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.

**When**
- `dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### PRJ-GS-18 — the status filter comes before the page: another status takes no place
- **Rules:** `get_by_status` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = project, `name "Aaa"`.
2. set_status(X, "COMPLETED").
3. A = project, `name "Beta"`.
4. B = project, `name "Gamma"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PRJ-GS-19 — writes nothing: a pending project stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = project, `name "Alpha"`.
2. B = project, `name "Beta"`, but `workspace_id W2.id`.
3. `B.name = "Edited"` (not flushed).
4. `P = Project(workspace_id=W1.id, factory_id=F1.id, name="Pending", description="Main")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### PRJ-GS-20 — names that differ only in case tie, whichever case sorts first byte-wise
- **Rules:** `get_by_status` R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1444 (non-strict)
- **Fails today on:** Then 1 (no order is requested)

**Given**
1. B = project, `name "Roof"`.
2. A = project, `name "roof"`.
3. C = project, `name "Banana"`.
4. D = project, `name "apple"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### PRJ-GS-21 — a soft-deleted project takes no place in the page, after the name order
- **Rules:** `get_by_status` R2 [BUG-1445], R4 [BUG-1444]
- **Kind:** bug
- **Expect:** xfail BUG-1445, BUG-1444 (non-strict)
- **Fails today on:** Then 1 (the deleted project fills the first place)

**Given**
1. X = project, `name "Aaa"`, but deleted.
2. A = project, `name "Bbb"`.
3. B = project, `name "Ccc"`.

**When**
- `result = dao.get_by_status(db, status="PLANNING", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — HR-5: private projects dropped in Python after paging | `ProjectManager.list_projects` | Short or empty pages. |
| Spec FU-1 (b) — without `factory_id` and `status` the raw `get_by_workspace` is used (BUG-100); the three paths must hide and order alike | `ProjectManager.list_projects` | BUG-1444 … BUG-1446 there too. |
| Spec FU-1 (c) — `factory_id=0` means "no filter"; `factory_id` wins over `status`; unknown status raises `ValueError` | `ProjectManager.list_projects` | Here `0` gives `[]` (PRJ-GF-06). |
| HR-7 — `GET /projects/` requires `skip >= 0`, `1 <= limit <= 1000` | `GET /projects/` | The DAO's negatives are PRJ-GF-23, GF-24, GS-16, GS-17. |
| HR-16 — BUG-1010 … BUG-1023 cover project writes across workspaces | `ProjectManager` | Reads here follow the row's own workspace. |
| Inherited `BaseDAO` methods; module singleton | `tests/unit/dao/base.cases.md` / none | Not overridden. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_status` Inputs | `ProjectStatusEnum`'s module is not named. | Cards pass the name `"PLANNING"` (the spec says it works) and set other statuses by SQL with `projectstatusenum`; no card passes the enum member itself. |
| 2 | Notes, BUG-1445 | A soft-deleted project is `is_deleted=True, is_active=False`; whether the real delete also writes `deleted_at` / `deleted_by` is not said. | Cards use the two columns given. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_factory` | Returns | PRJ-GF-01 |
| `get_by_factory` | R1 | PRJ-GF-01, PRJ-GF-02, PRJ-GF-03, PRJ-GF-04, PRJ-GF-05, PRJ-GF-06, PRJ-GF-26 |
| `get_by_factory` | R2 | PRJ-GF-09 |
| `get_by_factory` | R2 [BUG-1445] | PRJ-GF-07, PRJ-GF-08 |
| `get_by_factory` | R3 [BUG-1446] | PRJ-GF-10 |
| `get_by_factory` | R3a | PRJ-GF-11, PRJ-GF-12, PRJ-GF-13 |
| `get_by_factory` | R4 [BUG-1444] | PRJ-GF-14, PRJ-GF-15, PRJ-GF-16, PRJ-GF-17, PRJ-GF-27 |
| `get_by_factory` | R5 | PRJ-GF-18, PRJ-GF-19, PRJ-GF-20, PRJ-GF-21, PRJ-GF-22, PRJ-GF-23, PRJ-GF-24, PRJ-GF-26 |
| `get_by_factory` | Errors | PRJ-GF-23, PRJ-GF-24 |
| `get_by_factory` | Side effects | PRJ-GF-12, PRJ-GF-25 |
| `get_by_status` | Returns | PRJ-GS-01 |
| `get_by_status` | Inputs | PRJ-GS-04 |
| `get_by_status` | R1 | PRJ-GS-01, PRJ-GS-02, PRJ-GS-03, PRJ-GS-18 |
| `get_by_status` | R2 | PRJ-GS-06 |
| `get_by_status` | R2 [BUG-1445] | PRJ-GS-05, PRJ-GS-21 |
| `get_by_status` | R3 [BUG-1446] | PRJ-GS-07 |
| `get_by_status` | R3a | PRJ-GS-08, PRJ-GS-09 |
| `get_by_status` | R4 [BUG-1444] | PRJ-GS-10, PRJ-GS-11, PRJ-GS-20, PRJ-GS-21 |
| `get_by_status` | R5 | PRJ-GS-12, PRJ-GS-13, PRJ-GS-14, PRJ-GS-15, PRJ-GS-16, PRJ-GS-17, PRJ-GS-18 |
| `get_by_status` | Errors | PRJ-GS-04, PRJ-GS-16, PRJ-GS-17 |
| `get_by_status` | Side effects | PRJ-GS-09, PRJ-GS-19 |
