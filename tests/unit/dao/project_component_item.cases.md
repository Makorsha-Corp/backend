# Test cases — `app/dao/project_component_item.py`

> **Spec:** `tests/unit/dao/project_component_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `project_component_item.verify.md` (case-missing Finding 1; recipe R-1): R-1 → PCI-G-26. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 26 cases · 22 expected-to-pass · 4 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_component` 26 (4 bug).
- **Depth:** lighter target (skill step 1a): one thin paged read; the module writes no stock, money or order state.
- **Expected-to-fail:** BUG-1276 4: PCI-G-12, PCI-G-13, PCI-G-14 non-strict, PCI-G-15 strict (the SQL recorder).
- **Commit spies:** none, the module has no writer of its own.
- **Notable design choices:** every passing card compares a set, because today's order is not fixed. The hidden row in each paging card sorts ahead of the skipped row, also after the intended sort. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** PCI-G-26: an unflushed edit of another row stays unflushed.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PCI` = `app/dao/project_component_item.py`. `G` get_by_component.

**Actors and fixed values.**
- `dao` = the singleton `project_component_item_dao` (`from app.dao.project_component_item import project_component_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectComponentItem` = `app.models.project_component_item.ProjectComponentItem`. `Factory`, `Project`, `ProjectComponent`, `Item` come from `app.models.factory`, `.project`, `.project_component`, `.item`. `datetime` = the `datetime` module's class.
- MISSING = `999999999`: an id that no row of any table has.
- T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`.
  - PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`. PJ2 = the same, but `name "Project Two"`. PJD = the same, but `name "Project Three"`, `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
  - C1 = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Roof")`. C2 = the same, but `name "Wall"`. CD = the same, but `project_id PJD.id`, `name "Floor"`.
  - I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`.
- **entry** = `project_component_items` row built with `ProjectComponentItem`: `workspace_id W1.id`, `project_component_id C1.id`, `item_id I1.id`, `qty 1`. After the word "but" the card lists every other column that differs.
- No `project_component_items` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `project_component_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- Passing cards of this module never compare an order: the query has none today (BUG-1276). They compare a set.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value.orig`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1276.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_component_items`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOProjectComponentItem.get_by_component`

### PCI-G-01 — returns a list of the component's rows, one item twice included
- **Rules:** `get_by_component` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `set(ids(result)) == {A.id, B.id}`.
4. returns: `isinstance(result[0], ProjectComponentItem)`.

### PCI-G-02 — a row of another component of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = entry, but `project_component_id C2.id`.
2. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCI-G-03 — the right component under another workspace returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PCI-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCI-G-05 — a W2 row on a W1 component is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCI-G-06 — a W2 row on a W1 component is not returned for W1, though it sorts first
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = entry, but `workspace_id W2.id`.
2. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCI-G-07 — an unknown component id returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCI-G-08 — component id 0 returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCI-G-09 — a component with no rows returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCI-G-10 — the component filter comes before paging: a hidden row does not use up the skip
- **Rules:** `get_by_component` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, but `project_component_id C2.id`.
2. A = entry.
3. B = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCI-G-11 — the workspace filter comes before paging: a hidden row does not use up the skip
- **Rules:** `get_by_component` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = entry, but `workspace_id W2.id`.
2. A = entry.
3. B = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### PCI-G-12 — rows come back by id ascending, when the lowest id was updated
- **Rules:** `get_by_component` R3 [BUG-1276]
- **Kind:** bug
- **Expect:** xfail BUG-1276 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lowest id comes last, but that rests on physical row order)

**Given**
1. A = entry, but `qty 9`.
2. B = entry, but `qty 5`.
3. C = entry, but `qty 1`.
4. `A.qty = 3`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PCI-G-13 — rows come back by id ascending, with no update
- **Rules:** `get_by_component` R3 [BUG-1276]
- **Kind:** bug
- **Expect:** xfail BUG-1276 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = entry, but `qty 9`.
2. B = entry, but `qty 5`.
3. C = entry, but `qty 1`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PCI-G-14 — the order comes before paging, and the hidden row does not use up the skip
- **Rules:** `get_by_component` R3 [BUG-1276]
- **Kind:** bug
- **Expect:** xfail BUG-1276 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the page rests on physical row order)

**Given**
1. X = entry, but `project_component_id C2.id`.
2. A = entry.
3. B = entry.
4. C = entry.
5. `A.qty = 3`, then `db.flush()`.
6. `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### PCI-G-15 — the query orders by id ascending
- **Rules:** `get_by_component` R3 [BUG-1276]
- **Kind:** bug
- **Expect:** xfail BUG-1276
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = entry.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### PCI-G-16 — with the default limit 102 rows give 100
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 102 entries E1 … E102, built with `add_all`. `in_order` = their ids.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCI-G-17 — limit=1000 gives all 102 rows
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 102 entries E1 … E102, built with `add_all`. `in_order` = their ids.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 102`.
2. returns: `set(ids(result)) == set(in_order)`.

### PCI-G-18 — limit=0 returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry.
3. C = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCI-G-19 — limit=1 returns one row: the other side of limit=0
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry.
3. C = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PCI-G-20 — skip past the end returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry.
3. C = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCI-G-21 — skip=2 of three rows leaves one row: the other side of skip past the end
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry.
3. C = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.

### PCI-G-22 — a negative limit is refused by Postgres
- **Rules:** `get_by_component` R6, Errors row 1 (negative `limit`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCI-G-23 — a negative skip is refused by Postgres
- **Rules:** `get_by_component` R6, Errors row 2 (negative `skip`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCI-G-24 — the rows of a component of a soft-deleted project are returned
- **Rules:** `get_by_component` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Project PJD has `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = entry, but `project_component_id CD.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCI-G-25 — writes nothing: a pending row stays pending and alone in the session
- **Rules:** `get_by_component` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry.
2. `P = ProjectComponentItem(workspace_id=W1.id, project_component_id=C1.id, item_id=I1.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

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
11. statement: `"project_components" not in sql`.
12. nothing written: nothing written.
13. unchanged: unchanged(A).

### PCI-G-26 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_component` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `project_component_id C2.id`.
3. `B.qty = 5` (not flushed).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.qty == 5`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Review, HR-7 — BUG-1277: `GET /project-component-items/` requires `limit >= 1` | `GET /project-component-items/` | The DAO rule does not change; the check belongs to the endpoint. |
| `get_by_component` R7 — BUG-1278: rows under a soft-deleted project are hidden | `ProjectComponentItemService` (spec FU-1 (a)) | The service's spec carries the rule and the tag. |
| Spec FU-1 (b) — without `project_component_id`, `get_items` pages first and filters by access after | `ProjectComponentItemService.get_items` | Same shape as `project_component.spec.md` FU-1 (b). |
| Spec FU-1 (c) — `project_component_id=0` lists the workspace | `ProjectComponentItemService.get_items` | Here `0` returns `[]`. |
| Review, HR-16 — a stored foreign item: BUG-1012 | `ProjectComponentItemService` | This read follows the row. |
| Overview — inherited `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_component` R7 | The spec names no soft-delete column for the project. `is_deleted`, `deleted_at`, `deleted_by` come from `project_event.cases.md`. | The PJD row uses them. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_component` | Returns | PCI-G-01 |
| `get_by_component` | R1 | PCI-G-01, PCI-G-02, PCI-G-03, PCI-G-04, PCI-G-05, PCI-G-06, PCI-G-10, PCI-G-11 |
| `get_by_component` | R2 | PCI-G-07, PCI-G-08, PCI-G-09 |
| `get_by_component` | R3 [BUG-1276] | PCI-G-12, PCI-G-13, PCI-G-14, PCI-G-15 |
| `get_by_component` | R4 | PCI-G-10, PCI-G-11, PCI-G-16, PCI-G-17 |
| `get_by_component` | R5 | PCI-G-18, PCI-G-19, PCI-G-20, PCI-G-21 |
| `get_by_component` | R6 | PCI-G-22, PCI-G-23 |
| `get_by_component` | R7 | PCI-G-24 |
| `get_by_component` | Errors row 1 (negative `limit`) | PCI-G-22 |
| `get_by_component` | Errors row 2 (negative `skip`) | PCI-G-23 |
| `get_by_component` | Side effects | PCI-G-25, PCI-G-26 |
