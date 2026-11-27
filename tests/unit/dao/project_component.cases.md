# Test cases — `app/dao/project_component.py`

> **Spec:** `tests/unit/dao/project_component.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `project_component.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): R-1 → PCO-G-26; R-2 → PCO-G-27. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 27 cases · 22 expected-to-pass · 5 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_by_project` 27 (5 bug).
- **Depth:** lighter target (skill step 1a): one thin paged read; the module writes no stock, money or order state.
- **Expected-to-fail:** BUG-1275 5: PCO-G-12, PCO-G-13, PCO-G-14, PCO-G-27 non-strict, PCO-G-15 strict (the SQL recorder).
- **Commit spies:** none, the module has no writer of its own.
- **Notable design choices:** every passing card compares a set, because today's order is not fixed. The hidden row in each paging card sorts ahead of the skipped row, also after the intended sort. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** PCO-G-26 (an unflushed edit stays unflushed); PCO-G-27 (one tied pair puts lower case first, the other upper case, so a case-sensitive sort fails under either collation; `marker_test` sorts case-blind).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PCO` = `app/dao/project_component.py`. `G` get_by_project.

**Actors and fixed values.**
- `dao` = the singleton `project_component_dao` (`from app.dao.project_component import project_component_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectComponent` = `app.models.project_component.ProjectComponent`. `Factory` = `app.models.factory.Factory`. `Project` = `app.models.project.Project`. `datetime` = the `datetime` module's class. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`.
  - PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`. PJ2 = the same, but `name "Project Two"`. PJD = the same, but `name "Project Three"`, `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
- **component** = `project_components` row built with `ProjectComponent`: `workspace_id W1.id`, `project_id PJ1.id`; `status`, `created_at` are not passed. The card always gives `name`; after the word "but" it lists every other column that differs.
- No `project_components` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `project_components` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- Passing cards of this module never compare an order: the query has none today (BUG-1275). They compare a set.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`: transaction-local, gone with the rollback. Today's read then follows physical row order.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value.orig`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1275.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_components`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOProjectComponent.get_by_project`

### PCO-G-01 — returns a list of the project's components
- **Rules:** `get_by_project` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `set(ids(result)) == {A.id, B.id}`.
4. returns: `isinstance(result[0], ProjectComponent)`.

### PCO-G-02 — a component of another project of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = component, `name "Part 1"`, but `project_id PJ2.id`.
2. A = component, `name "Part 2"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCO-G-03 — the right project under another workspace returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PCO-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCO-G-05 — a W2 row on a W1 project is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCO-G-06 — a W2 row on a W1 project is not returned for W1, though it sorts first
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = component, `name "Part 1"`, but `workspace_id W2.id`.
2. A = component, `name "Part 2"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCO-G-07 — an unknown project id returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCO-G-08 — project id 0 returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCO-G-09 — a project with no rows returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCO-G-10 — the project filter comes before paging: a row of another project does not use up the skip
- **Rules:** `get_by_project` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = component, `name "Aaa"`, but `project_id PJ2.id`.
2. A = component, `name "Beta"`.
3. B = component, `name "Gamma"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCO-G-11 — the workspace filter comes before paging: a row of another workspace does not use up the skip
- **Rules:** `get_by_project` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = component, `name "Aaa"`, but `workspace_id W2.id`.
2. A = component, `name "Beta"`.
3. B = component, `name "Gamma"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCO-G-12 — components are ordered by name, case-insensitive, whatever their ids
- **Rules:** `get_by_project` R3 [BUG-1275]
- **Kind:** bug
- **Expect:** xfail BUG-1275 (non-strict)
- **Fails today on:** Then 2 (no order is requested; today's result is physical order, `Beta` first)

**Given**
1. A = component, `name "Beta"`.
2. B = component, `name "alpha"`.
3. C = component, `name "Gamma"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, A.id, C.id]`.

### PCO-G-13 — on a name tie, also across case, the lowest id comes first
- **Rules:** `get_by_project` R3 [BUG-1275]
- **Kind:** bug
- **Expect:** xfail BUG-1275 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lower id comes second, but that rests on physical row order)

**Given**
1. A = component, `name "roof"`.
2. B = component, `name "Roof"`.
3. `db.execute(text("UPDATE project_components SET name = name WHERE id = :i"), {"i": A.id})`
4. `db.expire_all()`.
5. seqscan.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PCO-G-14 — the order comes before paging, and the hidden row does not use up the skip
- **Rules:** `get_by_project` R3 [BUG-1275]
- **Kind:** bug
- **Expect:** xfail BUG-1275 (non-strict)
- **Fails today on:** Then 2 (no order is requested; today's second row is physical order, `alpha`)

**Given**
1. X = component, `name "Aaa"`, but `project_id PJ2.id`.
2. A = component, `name "Beta"`.
3. B = component, `name "alpha"`.
4. C = component, `name "Gamma"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [A.id]`.

### PCO-G-15 — the query orders by name, then id ascending
- **Rules:** `get_by_project` R3 [BUG-1275]
- **Kind:** bug
- **Expect:** xfail BUG-1275
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = component, `name "Part 1"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("name") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### PCO-G-16 — with the default limit 103 rows give 100
- **Rules:** `get_by_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 103 components E1 … E103, built with `add_all`: Ek = component, `name` = `f"Part {k:03d}"`. `in_order` = their ids.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCO-G-17 — limit=1000 gives all 103 rows
- **Rules:** `get_by_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 103 components E1 … E103, built with `add_all`: Ek = component, `name` = `f"Part {k:03d}"`. `in_order` = their ids.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 103`.
2. returns: `set(ids(result)) == set(in_order)`.

### PCO-G-18 — limit=0 returns an empty list
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`.
3. C = component, `name "Part 3"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCO-G-19 — limit=1 returns one row: the other side of limit=0
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`.
3. C = component, `name "Part 3"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PCO-G-20 — skip past the end returns an empty list
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`.
3. C = component, `name "Part 3"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCO-G-21 — skip=2 of three rows leaves one row: the other side of skip past the end
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`.
3. C = component, `name "Part 3"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.

### PCO-G-22 — a negative limit is refused by Postgres
- **Rules:** `get_by_project` R6, Errors row 1 (negative `limit`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCO-G-23 — a negative skip is refused by Postgres
- **Rules:** `get_by_project` R6, Errors row 2 (negative `skip`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCO-G-24 — the components of a soft-deleted project are returned
- **Rules:** `get_by_project` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Project PJD has `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = component, `name "Roof"`, but `project_id PJD.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCO-G-25 — writes nothing: a pending row stays pending and alone in the session
- **Rules:** `get_by_project` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. `P = ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Pending")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

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
10. statement: `"projects" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### PCO-G-26 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_project` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = component, `name "Part 1"`.
2. B = component, `name "Part 2"`, but `project_id PJ2.id`.
3. `B.name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.name == "Edited"`.

### PCO-G-27 — names that differ only in case tie, and id decides, whichever case comes first
- **Rules:** `get_by_project` R3 [BUG-1275]
- **Kind:** bug
- **Expect:** xfail BUG-1275 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the result rests on physical row order)

**Given**
1. A = component, `name "roof"`.
2. B = component, `name "Roof"`.
3. C = component, `name "Wall"`.
4. D = component, `name "wall"`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Review, HR-7 — BUG-1277: `GET /project-components/` requires `limit >= 1`, the cap of 100 stays | `GET /project-components/` | The DAO rule does not change; the check belongs to the endpoint. |
| `get_by_project` R7 — BUG-1278: the components of a soft-deleted project are hidden | `ProjectComponentService` (spec FU-1 (a)) | The service's spec carries the rule and the tag. |
| Spec FU-1 (b) — without `project_id`, `get_components` pages first and filters by access after (HR-5, not logged yet) | `ProjectComponentService.get_components` | That spec must log it with `paginate-before-filter`. |
| Spec FU-1 (c) — `project_id=0` lists the whole workspace | `ProjectComponentService.get_components` | Pattern `falsy-zero-treated-as-missing`. Here `0` returns `[]`. |
| Spec FU-1 (d) — the workspace list has only `id` order | `ProjectComponentService.get_components` | It goes through inherited `get_by_workspace`. |
| Review, HR-16 — stored cross-workspace ids: BUG-1012, BUG-1013, BUG-1016; hard delete: BUG-1196 | `ProjectManager`, the order managers | This read follows the row. |
| Overview — inherited `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes | BUG-1275's Notes say the name-order case "can be strict". Skill step 3 makes every card comparing an order non-strict, and the strict alarm is the SQL recorder. | The cards follow the skill. The Notes only allow strict, so this is no contradiction, but freed row places could make a strict card pass by accident. |
| 2 | `get_by_project` R7 | The spec names no soft-delete column for the project. `is_deleted`, `deleted_at`, `deleted_by` come from `project_event.cases.md`. | The PJD row uses them. |
| 3 | `get_by_project` R3 | "Case-insensitive" is stated, the way of doing it is not (`lower()`, a collation). | The recorder checks only `name`, then `.id`; the behavior cards hold the case. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_project` | Returns | PCO-G-01 |
| `get_by_project` | R1 | PCO-G-01, PCO-G-02, PCO-G-03, PCO-G-04, PCO-G-05, PCO-G-06, PCO-G-10, PCO-G-11 |
| `get_by_project` | R2 | PCO-G-07, PCO-G-08, PCO-G-09 |
| `get_by_project` | R3 [BUG-1275] | PCO-G-12, PCO-G-13, PCO-G-14, PCO-G-15, PCO-G-27 |
| `get_by_project` | R4 | PCO-G-10, PCO-G-11, PCO-G-16, PCO-G-17 |
| `get_by_project` | R5 | PCO-G-18, PCO-G-19, PCO-G-20, PCO-G-21 |
| `get_by_project` | R6 | PCO-G-22, PCO-G-23 |
| `get_by_project` | R7 | PCO-G-24 |
| `get_by_project` | Errors row 1 (negative `limit`) | PCO-G-22 |
| `get_by_project` | Errors row 2 (negative `skip`) | PCO-G-23 |
| `get_by_project` | Side effects | PCO-G-25, PCO-G-26 |
