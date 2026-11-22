# Test cases — `app/dao/base.py`

> **Spec:** `tests/unit/dao/base.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 — re-run against the APPROVED spec (Gap log G1–G6, unchanged since revision 4). Re-checked every rule, Errors row and BUG tag against the cases; verify.md finding 1 (case-designer part: redesign BASE-G-05) was already addressed in revision 4 — verify.md predates it (cases revision 3). No case added, changed or retired; no new gaps.
> **Revision 4:** spec Gap log G6 (verify finding 1 / DISCREPANCY-1): `get` R5 corrected to "pending (unflushed) rows are not found; found after an explicit flush" (autoflush is off). BASE-G-05 redesigned to the corrected rule, testing both sides (pending → `None`, flushed → same object); same ID kept, still `pass` (no bug). Executor must drop the DISCREPANCY-1 xfail. Counts unchanged.
> **Revision 3:** spec Gap log closed G1–G5: G3 now names the exception for `create` R7 (`AttributeError` at model construction, nothing added), so BASE-C-09 asserts that exact type/message and that nothing was added to the session; G1, G2, G4, G5 confirmed the mechanics already used here (NoIdThing, temp RESTRICT/CASCADE child tables, `N0`-relative `get_multi`, `SET LOCAL` sequential scan with heap order ≠ id order). No IDs added or retired.
> **Revision 2:** BUG-100 xfails force a sequential scan; return-value assertions added to C-03, C-04, U-10, U-15.
> **Counts:** 65 cases · 62 expected-to-pass · 3 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** `get` 6 cases · `get_multi` 10 (1 bug) · `create` 9 · `update` 15 · `remove` 7 (1 bug) · `get_by_workspace` 13 (1 bug) · `get_by_id_and_workspace` 5
- **Notable design choices:**
  - `BaseDAO` is tested once, through a bare `BaseDAO(Department)` (the spec's recommended vehicle); `BaseDAO(Workspace)` is the model without `workspace_id`.
  - `get` "model has no `id`" error: no real model lacks `id`, so BASE-G-06 uses a test-local mapped class with no `id` attribute (spec Notes, best-practice default, delegated by reviewer).
  - `remove` FK restrict/cascade (R4): no model references `departments`, so BASE-R-04/05 create two **temporary** tables inside the test transaction with `ON DELETE RESTRICT` / `ON DELETE CASCADE` (spec Notes, best-practice default, delegated by reviewer). Creating an FK briefly locks `departments`; see Conventions.
  - `get_multi` is unscoped, so its cases are written relative to `N0` = committed department rows already in the shared test DB; the "no rows at all" sub-case of R5 is covered through `get_by_workspace` (BASE-GW-07), as the spec Notes direct.
  - BUG-100 xfail cases (BASE-GM-04, BASE-GW-05) rename the lowest-id row before the call so that today's unordered result (heap order) differs from `id` order; strict xfail relies on that storage behavior, so both cases run with `SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off` (sequential scan = physical order; an index scan could follow the HOT chain from A's original slot and return id order by accident) (best-practice default, delegated by reviewer).
  - "Not committed" is proved by rolling back a savepoint taken before the call, plus a spy (wraps, does not replace) on `db.commit` asserting it was never called.
  - BASE-U-07 assigns the relationship `creator` on Department, as the spec's R5 example names it.
  - BASE-G-05 checks both sides of `get` R5 in one case (pending row → `None`, then after `db.flush()` → the same object), since setup is shared and the flip is the point of the rule.
- **Needs a decision:** None — the spec closed all earlier gaps (G1–G6); no new gaps.

## Conventions for this module

**IDs:** `BASE` = `app/dao/base.py`. Method codes: `G` = `get`, `GM` = `get_multi`, `C` = `create`, `U` = `update`, `R` = `remove`, `GW` = `get_by_workspace`, `GIW` = `get_by_id_and_workspace`.

**DAOs:** `dao` = `BaseDAO(Department)`; `wdao` = `BaseDAO(Workspace)`. No subclass DAO is used.

**Rows:**
- W1, W2, W3 = three existing workspaces (fresh per test). W3 has no departments unless stated.
- P1 = an existing profile (any workspace link needed by the profile itself).
- `D "Sales" (W1)` = a Department with `name="Sales"`, `workspace_id=W1`, all other columns at their defaults (`is_active=True`, `is_deleted=False`, `created_by/updated_by/deleted_by=NULL`), inserted and flushed. `(deleted)` = also `is_deleted=True`. "Inserted in order A, B, C" = insert and flush one after another, so ids ascend in that order.
- `k own rows` = k departments named `"R001"`, `"R002"`, … in W1 (unless stated), inserted in that order.
- `MISSING` = an integer that is no department's id (max committed/visible department id + 1000). `MISSING_PROFILE` = an integer that is no profile's id (max profile id + 1000).
- `N0` = number of department rows visible to the test session **before** any setup of the case (count query at test start). Rows created by the case get ids larger than every pre-existing row (sequence), and concurrent agents' uncommitted rows are invisible.

**Re-read:** "re-read" = after the call, `db.expire_all()` then load the row fresh by a raw `SELECT` on `departments` by id (not via the DAO under test). "No row" = that `SELECT` returns nothing (so a soft delete would NOT count as gone).

**Error cases (IntegrityError / DataError / TypeError / any raise during flush):** take a savepoint (`db.begin_nested()`) immediately before the call, assert the raise, roll the savepoint back, then re-read to show the database is unchanged.

**"Not committed" checks:** a spy that wraps `db.commit` (still callable, records calls) is installed before the call; assert it was never called. Then the savepoint rollback shown in the case.

**Warnings:** `remove` emits `LegacyAPIWarning`; do not turn warnings into errors for `remove` cases.

**Ad-hoc schemas (test-local Pydantic models):**
- `DeptIn(BaseModel)`: `title: str = Field(alias="name")`; `workspace_id: int | None = None`; `is_active: bool = False`; `created_by: int | None = None`. Constructed with the alias key (`DeptIn(name=..., ...)`).
- `DeptPatch(BaseModel)`: `title: str | None = Field(None, alias="name")`; `is_active: bool = True`. Constructed with the alias key.
- `CreatorIn(BaseModel)`: `id: int`. `DeptNested(BaseModel)`: `name: str`; `workspace_id: int`; `creator: CreatorIn`.

**Test-local mapped class (BASE-G-06 only):** `NoIdThing` on its own `DeclarativeBase` (own metadata, never created in the DB), `__tablename__ = "base_dao_no_id_probe"`, single primary-key column `code: str`; it has **no** `id` attribute.

**Temporary tables (BASE-R-04/05 only):** created by raw SQL inside the test transaction (rolled back with it, session-local, so no clash with parallel agents):
- `tmp_restrict_child(id serial primary key, department_id int not null references departments(id) on delete restrict)`
- `tmp_cascade_child(id serial primary key, department_id int not null references departments(id) on delete cascade)`
Adding the FK takes a short lock on `departments`; the executor may `SET LOCAL lock_timeout = '10s'` first.

**Externals mocked:** none (spec). **Time:** not mocked; Postgres `now()` = transaction start.

**Planner settings (BASE-GM-04, BASE-GW-05 only):** immediately before the calls, `SET LOCAL enable_indexscan = off`, `SET LOCAL enable_bitmapscan = off`, `SET LOCAL enable_indexonlyscan = off` (transaction-local, rolled back with the test). This only pins today's unordered read to heap order; after the BUG-100 fix the `ORDER BY id` makes the result independent of it.

**Race simulations:** none.

## `BaseDAO.get`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-G-01 | R1 | happy | `D1 "Sales" (W1)`, `D2 "Ops" (W1)` | `dao.get(db, id=D1.id)` | returns a Department with `id == D1.id` and `name == "Sales"` (not D2) | pass |
| BASE-G-02 | R2 | boundary | `D1 "Sales" (W1)` | `dao.get(db, id=MISSING)` | returns `None`; no exception | pass |
| BASE-G-03 | R3 | soft-delete | `D1 "Gone" (W1) (deleted)` | `dao.get(db, id=D1.id)` | returns the Department with `id == D1.id`, `is_deleted is True` | pass |
| BASE-G-04 | R4 | isolation | `D1 "Sales" (W1)`, `E1 "Other" (W2)` | `dao.get(db, id=E1.id)` (no workspace given) | returns the Department with `id == E1.id`, `workspace_id == W2.id`, `name == "Other"` | pass |
| BASE-G-05 | R5 | boundary | a Department `name="Unflushed"`, `workspace_id=W1`, explicit `id = MISSING` added with `db.add`, **not** flushed (session `autoflush=False`, as in the harness) | (a) `dao.get(db, id=MISSING)`; then `db.flush()`; (b) `dao.get(db, id=MISSING)` again | (a) returns `None`, and a raw `SELECT` by that id right after (a) finds no row (the `get` did not flush); (b) returns that same Python object (`is`) with `name == "Unflushed"`, and a raw `SELECT` by that id now finds the row | pass |
| BASE-G-06 | Errors: no `id` | error | `BaseDAO(NoIdThing)` | `.get(db, id=1)` | raises `AttributeError` whose message mentions `id`; department count unchanged (`N0`) | pass |

## `BaseDAO.get_multi`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-GM-01 | R1 | boundary | 101 own rows | (a) `dao.get_multi(db)`; (b) `dao.get_multi(db, skip=N0)` | (a) returns a list of exactly 100 Departments; (b) exactly 100 (101 remain after skip, capped by default `limit=100`) | pass |
| BASE-GM-02 | R1 | boundary | 100 own rows | `dao.get_multi(db, skip=N0)` | returns exactly 100 (all remaining rows; other side of the cap) | pass |
| BASE-GM-03 | R1 | happy | 5 own rows | (a) `get_multi(db, skip=N0, limit=3)`; (b) `get_multi(db, skip=N0+3, limit=3)` | (a) exactly 3 rows; (b) exactly 2 rows (short last page) | pass |
| BASE-GM-04 | R2 [BUG-100] | bug | own rows inserted in order A "Zeta", B "Alpha", C "Mid" (W1); then A renamed to "Zulu" via a flushed `UPDATE` (so A's live tuple is stored after C) | with the planner settings (Conventions): (a) `get_multi(db, skip=N0, limit=100)`; (b) `get_multi(db, skip=N0, limit=2)` then `get_multi(db, skip=N0+2, limit=2)`; (c) `get_multi(db, limit=N0+3)` | (a) ids exactly `[A, B, C]` (not name order "Alpha","Mid","Zulu"); (b) page 1 ids `[A, B]`, page 2 ids `[C]`, concatenation `[A, B, C]` with no repeats; (c) returned ids strictly ascending | xfail BUG-100 — fails today on: (a) first own id is B (heap order), not A |
| BASE-GM-05 | R3 | soft-delete | own rows D1 "One", D2 "Two" (deleted), D3 "Three" | (a) `get_multi(db, limit=N0+100)`; (b) `get_multi(db, skip=N0+2, limit=100)` | (a) length `N0+3`, ids include D1, D2, D3; (b) exactly 1 row (the deleted row counts for `skip`) | pass |
| BASE-GM-06 | R4 | isolation | `D1 "Sales" (W1)`, `E1 "Other" (W2)` | `get_multi(db, limit=N0+100)` | returned ids include both D1 and E1; length `N0+2` | pass |
| BASE-GM-07 | R5 | boundary | 2 own rows | (a) `get_multi(db, skip=N0+2)`; (b) `get_multi(db, skip=N0+1)` | (a) returns `[]` (a list, empty); (b) exactly 1 row | pass |
| BASE-GM-08 | R5 | boundary | 2 own rows | (a) `get_multi(db, limit=0)`; (b) `get_multi(db, skip=N0, limit=1)` | (a) returns `[]`; (b) exactly 1 row | pass |
| BASE-GM-09 | R6, Errors: negative | error | 2 own rows | `get_multi(db, skip=-1)` (in savepoint) | raises `sqlalchemy.exc.DataError`, message contains `OFFSET must not be negative`; after savepoint rollback department count is `N0+2` | pass |
| BASE-GM-10 | R6, Errors: negative | error | 2 own rows | `get_multi(db, limit=-1)` (in savepoint) | raises `sqlalchemy.exc.DataError`, message contains `LIMIT must not be negative`; after rollback count `N0+2` | pass |

## `BaseDAO.create`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-C-01 | R1 | happy | W1 has no departments | `dao.create(db, obj_in={"name": "Sales", "workspace_id": W1.id})` | returns a `Department` with integer `id`; a raw `SELECT` by that id in the same session finds it; re-read: `name "Sales"`, `workspace_id W1` | pass |
| BASE-C-02 | R2 | happy | W1 empty | `dao.create(db, obj_in=DeptIn(name="Ops", workspace_id=W1.id))` (`is_active`, `created_by` not set) | returns a Department with an id; re-read: `name "Ops"` (alias used — without it a `title` key would be rejected), `is_active False` (schema default applied although unset, model default is True), `created_by NULL`, `workspace_id W1` | pass |
| BASE-C-03 | R3 | side-effect | W1 empty | `create(obj_in={"name": "Plain", "workspace_id": W1.id})` | returns a `Department` with integer `id` and `name == "Plain"`; re-read: `is_active True`, `is_deleted False`, `created_at` not NULL, `updated_at` NULL, `created_by`/`updated_by`/`deleted_by` NULL | pass |
| BASE-C-04 | R3 | boundary | W1 empty | `create(obj_in={"name": "Nones", "workspace_id": W1.id, "is_active": None, "is_deleted": None, "created_at": None, "created_by": None})` | no error; returns a `Department` with integer `id` and `name == "Nones"`; re-read: `is_active True`, `is_deleted False`, `created_at` not NULL (defaults applied), `created_by` NULL | pass |
| BASE-C-05 | R4 | side-effect | W1 empty; commit spy; savepoint taken | `create(obj_in={"name": "Temp", "workspace_id": W1.id})`, note id; roll back the savepoint | before rollback raw `SELECT` finds the row; commit spy never called; after rollback raw `SELECT` by that id finds nothing and W1 has 0 departments | pass |
| BASE-C-06 | R5, Errors: unknown key | error | W1 empty | `create(obj_in={"nmae": "Ops", "name": "Ops", "workspace_id": W1.id})` (in savepoint) | raises `TypeError`, message contains `'nmae' is an invalid keyword argument for Department`; after rollback W1 has 0 departments and total count is `N0` | pass |
| BASE-C-07 | R6, R8, Errors: constraint | error | W1 empty | `create(obj_in={"name": "NoWs"})` (in savepoint) | raises `sqlalchemy.exc.IntegrityError` (NOT NULL `workspace_id` — no workspace filled in automatically); after rollback no department named "NoWs" exists, count `N0` | pass |
| BASE-C-08 | R6, Errors: constraint | error | W1 empty | `create(obj_in={"name": "BadFk", "workspace_id": W1.id, "created_by": MISSING_PROFILE})` (in savepoint) | raises `sqlalchemy.exc.IntegrityError`; after rollback W1 has 0 departments | pass |
| BASE-C-09 | R7, Errors: nested value for relationship | error | W1 empty; P1 | `create(obj_in=DeptNested(name="Nest", workspace_id=W1.id, creator=CreatorIn(id=P1.id)))` (in savepoint) | raises `AttributeError`, message contains `'dict' object has no attribute '_sa_instance_state'`; immediately after the raise (before rollback) no `Department` instance is in `db.new`; after rollback no department named "Nest" exists, count `N0` | pass |

## `BaseDAO.update`

All cases start from `D "Old" (W1)` (flushed, `updated_at` NULL) unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-U-01 | R1 | happy | D with `created_by=P1` | `dao.update(db, db_obj=D, obj_in={"name": "New", "created_by": None})` | returns the same object D (`is`); re-read: `name "New"`, `created_by` NULL | pass |
| BASE-U-02 | R2 | happy | D with `is_active=False` | `update(db_obj=D, obj_in=DeptPatch(name="New"))` (`is_active` not set; schema default True) | returns D; re-read: `name "New"` (alias applied), `is_active False` (unset field not applied) | pass |
| BASE-U-03 | R3 | boundary | D (`is_active=True`) | `update(db_obj=D, obj_in=DeptPatch(name=None, is_active=False))` | returns D; re-read: `name "Old"` (explicit None ignored), `is_active False` (other set field applied) | pass |
| BASE-U-04 | R4 | boundary | D | `update(db_obj=D, obj_in={"nmae": "Ops", "name": "New"})` | no error; returns D; re-read `name "New"`; `hasattr(D, "nmae")` is False | pass |
| BASE-U-05 | R4 | boundary | D | `update(db_obj=D, obj_in={"nmae": "Ops"})` | no error; returns D; re-read `name "Old"` | pass |
| BASE-U-06 | R5 | side-effect | D in W1; P1 | `update(db_obj=D, obj_in={"workspace_id": W2.id, "is_deleted": True, "updated_by": P1.id})` | returns D; re-read: `workspace_id W2`, `is_deleted True`, `updated_by P1`; `get_by_id_and_workspace(id=D.id, workspace_id=W1.id)` now `None` | pass |
| BASE-U-07 | R5 | side-effect | D with `created_by` NULL; P1 loaded | `update(db_obj=D, obj_in={"creator": P1})` | no error; returns D; re-read `created_by == P1.id` | pass |
| BASE-U-08 | R6 | boundary | D | `update(db_obj=D, obj_in={})` | no error; returns D; re-read `name "Old"`, `updated_at` NULL | pass |
| BASE-U-09 | R6 | boundary | D | `update(db_obj=D, obj_in=DeptPatch())` (nothing set) | no error; returns D; re-read `name "Old"`, `is_active True`, `updated_at` NULL | pass |
| BASE-U-10 | R7 | side-effect | D (`updated_at` NULL) | `update(db_obj=D, obj_in={"name": "New"})` | returns D (`is`); re-read `name "New"`, `updated_at` not NULL | pass |
| BASE-U-11 | R7 | boundary | D (`updated_at` NULL), D loaded in the session | `update(db_obj=D, obj_in={"name": "Old"})` (same value) | returns D; re-read `name "Old"`, `updated_at` still NULL | pass |
| BASE-U-12 | R8 | side-effect | D; commit spy; savepoint taken | `update(db_obj=D, obj_in={"name": "New"})`; then roll back the savepoint | before rollback a raw `SELECT` (without expiring first is not enough — use raw SQL) returns `name "New"`; commit spy never called; after rollback re-read `name "Old"` | pass |
| BASE-U-13 | R9, Errors: constraint | error | D | `update(db_obj=D, obj_in={"name": None})` (in savepoint) | raises `sqlalchemy.exc.IntegrityError`; after rollback re-read `name "Old"` | pass |
| BASE-U-14 | R9, Errors: constraint | error | D (`created_by` NULL) | `update(db_obj=D, obj_in={"created_by": MISSING_PROFILE})` (in savepoint) | raises `sqlalchemy.exc.IntegrityError`; after rollback re-read `created_by` NULL, `name "Old"` | pass |
| BASE-U-15 | R10 | side-effect | D with `created_by=P1`, `updated_by` NULL, `deleted_by` NULL | `update(db_obj=D, obj_in={"name": "New"})` | returns D (`is`); re-read: `name "New"`, `updated_by` NULL, `deleted_by` NULL, `created_by P1` | pass |

## `BaseDAO.remove`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-R-01 | R1, R2 | happy | `D1 "One" (W1)`, `D2 "Two" (W1)` | `dao.remove(db, id=D1.id)` | returns a Department whose `id == D1.id`; raw `SELECT` by D1's id finds **no row** (physical delete, not `is_deleted`); D2 still present with `name "Two"` | pass |
| BASE-R-02 | R2 | side-effect | `D1 "One" (W1)`; commit spy; savepoint taken | `remove(db, id=D1.id)`; then roll back the savepoint | before rollback raw `SELECT` finds no row; commit spy never called; after rollback raw `SELECT` finds D1 with `name "One"` | pass |
| BASE-R-03 | R3 [BUG-101] | bug | `D1 "One" (W1)` | `remove(db, id=MISSING)` | no exception; returns `None`; D1 still present with `name "One"`; department count unchanged (`N0+1`) | xfail BUG-101 — fails today on: raises `UnmappedInstanceError` instead of returning `None` |
| BASE-R-04 | R4, Errors: FK restrict | error | `D1 "One" (W1)`; temp table `tmp_restrict_child` with one row referencing D1 | `remove(db, id=D1.id)` (in savepoint) | raises `sqlalchemy.exc.IntegrityError`; after rollback D1 still present and the child row still present | pass |
| BASE-R-05 | R4 | side-effect | `D1 "One" (W1)`; temp table `tmp_cascade_child` with two rows referencing D1 | `remove(db, id=D1.id)` | returns the removed D1 (`id == D1.id`); raw `SELECT` finds no D1 row; `tmp_cascade_child` has 0 rows | pass |
| BASE-R-06 | R5 | isolation | `D1 "One" (W1)`, `E1 "Other" (W2)` | `remove(db, id=E1.id)` (no workspace given) | returns object with `id == E1.id`; raw `SELECT` finds no E1 row; D1 still present | pass |
| BASE-R-07 | R2 | soft-delete | `D1 "Gone" (W1) (deleted)` | `remove(db, id=D1.id)` | returns object with `id == D1.id`; raw `SELECT` finds no row | pass |

## `BaseDAO.get_by_workspace`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-GW-01 | R1 | isolation | `D1 "A" (W1)`, `D2 "B" (W1)`, `E1 "C" (W2)` | `dao.get_by_workspace(db, workspace_id=W1.id)` | returns a list of length 2; set of ids `{D1, D2}`; every row has `workspace_id W1` (E1 absent though the page has room) | pass |
| BASE-GW-02 | R2 | boundary | 101 own rows in W1 | (a) `get_by_workspace(workspace_id=W1)`; (b) `get_by_workspace(workspace_id=W1, skip=100)` | (a) exactly 100 rows; (b) exactly 1 row | pass |
| BASE-GW-03 | R2 | boundary | 100 own rows in W1 | `get_by_workspace(workspace_id=W1)` | exactly 100 rows (all of them; set of ids equals the 100 inserted) | pass |
| BASE-GW-04 | R2 | happy | 5 own rows in W1 | (a) `(workspace_id=W1, limit=3)`; (b) `(workspace_id=W1, skip=3, limit=3)` | (a) 3 rows; (b) 2 rows; all rows in W1 | pass |
| BASE-GW-05 | R3 [BUG-100] | bug | W1 rows inserted in order A "Zeta", B "Alpha", C "Mid"; then A renamed to "Zulu" via a flushed `UPDATE` | with the planner settings (Conventions): (a) `(workspace_id=W1)`; (b) `(workspace_id=W1, skip=0, limit=2)` then `(skip=2, limit=2)` | (a) ids exactly `[A, B, C]` (not name order), strictly ascending; (b) page 1 `[A, B]`, page 2 `[C]`, concatenation `[A, B, C]` with no repeats | xfail BUG-100 — fails today on: (a) first id is B (heap order), not A |
| BASE-GW-06 | R4 | soft-delete | W1: D1 "One", D2 "Two" (deleted), D3 "Three" | (a) `(workspace_id=W1)`; (b) `(workspace_id=W1, skip=2)` | (a) length 3, set of ids `{D1, D2, D3}`, D2 has `is_deleted True`; (b) exactly 1 row (deleted row counted by `skip`) | pass |
| BASE-GW-07 | R5 | boundary | W3 has no rows; W1 has `D1 "A"` | `(workspace_id=W3.id)` | returns `[]` | pass |
| BASE-GW-08 | R5 | boundary | W1 has `D1 "A"` | `(workspace_id=W404)` where W404 = max workspace id + 1000 | returns `[]` | pass |
| BASE-GW-09 | R5 | boundary | W1 has 2 own rows | (a) `(workspace_id=W1, skip=2)`; (b) `(workspace_id=W1, skip=1)` | (a) `[]`; (b) exactly 1 row | pass |
| BASE-GW-10 | R5 | boundary | W1 has 2 own rows | (a) `(workspace_id=W1, limit=0)`; (b) `(workspace_id=W1, limit=1)` | (a) `[]`; (b) exactly 1 row | pass |
| BASE-GW-11 | R6, Errors: negative | error | W1 has 2 own rows | `(workspace_id=W1, skip=-1)` (in savepoint) | raises `sqlalchemy.exc.DataError`, message contains `OFFSET must not be negative`; after rollback W1 still has 2 departments | pass |
| BASE-GW-12 | R6, Errors: negative | error | W1 has 2 own rows | `(workspace_id=W1, limit=-1)` (in savepoint) | raises `sqlalchemy.exc.DataError`, message contains `LIMIT must not be negative`; after rollback W1 still has 2 departments | pass |
| BASE-GW-13 | R7, Errors: no `workspace_id` | error | W1 exists; an engine `before_cursor_execute` listener counting statements attached just before the call | `wdao.get_by_workspace(db, workspace_id=W1.id)` | raises `AttributeError`, message `type object 'Workspace' has no attribute 'workspace_id'`; 0 SQL statements executed during the call; workspace W1 still present | pass |

## `BaseDAO.get_by_id_and_workspace`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| BASE-GIW-01 | R1 | happy | `D1 "Sales" (W1)`, `D2 "Ops" (W1)` | `dao.get_by_id_and_workspace(db, id=D1.id, workspace_id=W1.id)` | returns Department with `id == D1.id`, `name "Sales"`, `workspace_id W1` | pass |
| BASE-GIW-02 | R2 | isolation | `D1 "Sales" (W1)`; W2 has `E1 "Other"` | `get_by_id_and_workspace(id=D1.id, workspace_id=W2.id)` | returns `None`; `dao.get(db, id=D1.id)` still returns D1 (row exists) | pass |
| BASE-GIW-03 | R3 | boundary | `D1 "Sales" (W1)` | `get_by_id_and_workspace(id=MISSING, workspace_id=W1.id)` | returns `None` | pass |
| BASE-GIW-04 | R4 | soft-delete | `D1 "Gone" (W1) (deleted)` | `get_by_id_and_workspace(id=D1.id, workspace_id=W1.id)` | returns Department with `id == D1.id`, `is_deleted True` | pass |
| BASE-GIW-05 | R5, Errors: no `workspace_id` | error | W1 exists | `wdao.get_by_id_and_workspace(db, id=W1.id, workspace_id=W1.id)` | raises `AttributeError`, message `type object 'Workspace' has no attribute 'workspace_id'`; W1 still present | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Q4 / BUG-035 (`get` R4, `get_multi` R4, `remove` R5 used on workspace-scoped statuses) | `StatusService` (`app/services/status_service.py`), `GET/PUT/DELETE /statuses/` | every statuses list/get/update/delete is scoped to the caller's workspace; a status of another workspace is neither listed nor editable/deletable (404) |

## Spec gaps
None. The earlier gaps G1–G6 are closed by the spec's Gap log (kept below for traceability).

| # | Where | Earlier gap | Closed by |
|---|---|---|---|
| G1 | `get` Errors row (no `id`) | No real model lacks `id` | Spec Notes: test-local mapped class → BASE-G-06 (best-practice default, delegated by reviewer) |
| G2 | `remove` R4 | No FK referencing `departments` | Spec Notes: temporary RESTRICT / CASCADE child tables → BASE-R-04/05 (best-practice default, delegated by reviewer) |
| G3 | `create` R7 | No exception type | Spec R7 + Errors row: `AttributeError` at construction → BASE-C-09 tightened |
| G4 | `get_multi` | Shared DB, pre-existing rows | Spec Notes: `N0`-relative, `skip=N0`; empty sub-case via BASE-GW-07 (best-practice default, delegated by reviewer) |
| G5 | BUG-100 xfails | Today's physical order unspecified | Spec Notes: `SET LOCAL` sequential scan + heap order ≠ id order → BASE-GM-04, GW-05 (best-practice default, delegated by reviewer) |
| G6 | `get` R5 (verify finding 1, DISCREPANCY-1) | R5 claimed autoflush finds pending rows; autoflush is off | Spec R5 rewritten: pending → `None`, found after explicit flush → BASE-G-05 redesigned (best-practice default, delegated by reviewer) |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get` | R1 | BASE-G-01 |
| `get` | R2 | BASE-G-02 |
| `get` | R3 | BASE-G-03 |
| `get` | R4 | BASE-G-04 |
| `get` | R5 | BASE-G-05 |
| `get` | Errors: no `id` → `AttributeError` | BASE-G-06 |
| `get_multi` | R1 | BASE-GM-01, GM-02, GM-03 |
| `get_multi` | R2 [BUG-100] | BASE-GM-04 |
| `get_multi` | R3 | BASE-GM-05 |
| `get_multi` | R4 | BASE-GM-06 |
| `get_multi` | R5 | BASE-GM-07, GM-08 |
| `get_multi` | R6 / Errors: negative → `DataError` | BASE-GM-09, GM-10 |
| `create` | R1 | BASE-C-01 |
| `create` | R2 | BASE-C-02 |
| `create` | R3 | BASE-C-03, C-04 |
| `create` | R4 | BASE-C-05 |
| `create` | R5 / Errors: unknown key → `TypeError` | BASE-C-06 |
| `create` | R6 / Errors: constraint → `IntegrityError` | BASE-C-07, C-08 |
| `create` | R7 / Errors: nested value → `AttributeError` | BASE-C-09 |
| `create` | R8 | BASE-C-07 |
| `update` | R1 | BASE-U-01 |
| `update` | R2 | BASE-U-02 |
| `update` | R3 | BASE-U-03 |
| `update` | R4 | BASE-U-04, U-05 |
| `update` | R5 | BASE-U-06, U-07 |
| `update` | R6 | BASE-U-08, U-09 |
| `update` | R7 | BASE-U-10, U-11 |
| `update` | R8 | BASE-U-12 |
| `update` | R9 / Errors: constraint → `IntegrityError` | BASE-U-13, U-14 |
| `update` | R10 | BASE-U-15 |
| `remove` | R1 | BASE-R-01 |
| `remove` | R2 | BASE-R-01, R-02, R-07 |
| `remove` | R3 [BUG-101] | BASE-R-03 |
| `remove` | R4 / Errors: FK restrict → `IntegrityError` | BASE-R-04, R-05 |
| `remove` | R5 | BASE-R-06 |
| `get_by_workspace` | R1 | BASE-GW-01 |
| `get_by_workspace` | R2 | BASE-GW-02, GW-03, GW-04 |
| `get_by_workspace` | R3 [BUG-100] | BASE-GW-05 |
| `get_by_workspace` | R4 | BASE-GW-06 |
| `get_by_workspace` | R5 | BASE-GW-07, GW-08, GW-09, GW-10 |
| `get_by_workspace` | R6 / Errors: negative → `DataError` | BASE-GW-11, GW-12 |
| `get_by_workspace` | R7 / Errors: no `workspace_id` → `AttributeError` | BASE-GW-13 |
| `get_by_id_and_workspace` | R1 | BASE-GIW-01 |
| `get_by_id_and_workspace` | R2 | BASE-GIW-02 |
| `get_by_id_and_workspace` | R3 | BASE-GIW-03 |
| `get_by_id_and_workspace` | R4 | BASE-GIW-04 |
| `get_by_id_and_workspace` | R5 / Errors: no `workspace_id` → `AttributeError` | BASE-GIW-05 |
| (review) | Q4 / BUG-035 statuses leak | Deferred (StatusService / statuses endpoints) |
