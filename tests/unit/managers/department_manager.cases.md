# Test cases — `app/managers/department_manager.py`

> **Spec:** `tests/unit/managers/department_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 — spec unchanged. DEPT-S-04, S-05, S-06, S-07, C-06 and N-12 moved to non-strict xfail. Each was run under another physical order and passed today, so each rests on physical row order. None was left strict: no failure among them is independent of row order. DEPT-N-11 stays pass: its 100 rows equal the cap, so every row is examined in any order. Counts unchanged. All six are now `Author: claude`.
> **Revision:** 4 — spec unchanged. Closes two gaps against the current designer skill, found after verify round 2. Added commit-spy cards DEPT-C-21, U-27, D-05 (one per writer; the spec says "No commit" for each) and strict statement-recorder card DEPT-S-26 (BUG-008). DEPT-S-13/14/15 moved to `xfail BUG-008 (non-strict)`: each compares an order the query does not fix, so physical row order can make it pass by accident. Table format kept; all four new cards and the three non-strict cards are `Author: claude`.
> **Revision:** 3 — spec Gap log G6 closes gap 6 (HR-10 does not apply to rename / soft delete; no lock rule, no case). Verifier finding 1 (`update_department` R7, explicit `name=None` covered only inside xfail DEPT-U-13, surviving mutant #42) addressed by new pass case DEPT-U-25. Audit of every xfail case for working-today assertions found three more and split them into pass cases: DEPT-U-24 (from U-12, empty body leaves name unchanged), DEPT-U-26 (from U-14, same name leaves name unchanged), DEPT-C-20 (from C-11, inner whitespace kept as typed). U-12/U-13/U-14 now keep only the BUG-009 assertions.
> **Revision:** 2 — spec closed gaps 1–5 (G1–G5) and resolved Q13: users are global `profiles` rows (no membership rows); race simulation via patching `_check_name_exists` confirmed, with the manager call wrapped in `session.begin_nested()`; the 409 detail shows the submitted (trimmed) name, so the normalised-match 409 cases now assert the detail; `search_departments` R3 example and `_check_name_exists` R6 reworded; new `search_departments` R6a (HR-8, literal `%`/`_`).
> **Counts:** 99 cases · 60 expected-to-pass · 39 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `create_department` 21 cases (12 bug) · `update_department` 27 (11 bug) · `get_department` 6 (3 bug) · `search_departments` 26 (8 bug) · `delete_department` 5 (0 bug) · `_check_name_exists` 14 (5 bug).
- **Notable design choices:**
  - Race simulations: DEPT-C-17, C-19, U-22, U-23 patch the target's own `_check_name_exists` to return `False` to reach the database constraint (spec-sanctioned, create R6 / update R11).
  - DEPT-C-14, C-15, C-16, U-21 test the intended unique index directly by inserting/renaming rows without the manager.
  - Cards that rest on physical row order are non-strict (revisions 4 and 5): C-06, N-12, S-04..07, S-13..15. DEPT-S-26 is the strict alarm for BUG-008 only; BUG-001, 006 and 007 now have no strict card that goes off on a fix.
  - No recorder card for `_check_name_exists`: its query is unordered today, but R5 asks that every live row be examined, not for an order, so an `ORDER BY` card there would invent a rule.
  - `_check_name_exists` R6 "still `True`" uses an `exclude_id` of an unrelated department (only one live row per normalised name can exist).
  - `search_departments` R6a cases (`%`, `_`) pass today; they are regression guards for the BUG-007 fix moving search into SQL.
  - Regression split (rev 3): no-op updates (empty body, `name=None`, same name) have pass cases DEPT-U-24/25/26 that assert the name and untouched fields but deliberately NOT `updated_by`; the BUG-009 xfail cases U-12/13/14 assert only `updated_by`. DEPT-S-15's "pages cover all rows without repeats" holds today only because of insertion order (the BUG-008 defect itself), so it was not split into a pass case.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `DEPT` = department_manager. Method codes: `C` = `create_department`,
`U` = `update_department`, `G` = `get_department`, `S` = `search_departments`,
`D` = `delete_department`, `N` = `_check_name_exists`.

**Actors and tenants.**
- W1, W2 = two `workspaces` rows.
- U1, U2, U3 = three `profiles` rows. Profiles are global; no `workspace_members`
  rows are created (the manager never checks membership). By convention U1/U2 act
  in W1 and U3 is used as creator of W2 rows.
- M = a `DepartmentManager()` instance; `session` = the test's real session.
- MISSING = an integer id that no department row has (e.g. highest existing id + 1000).

**Setup rows.** Departments in Given are inserted directly into `departments`
(not through the manager) and flushed, in the order written; ids therefore
increase in that order.
- "live X" = row with name X, `is_deleted = False`, `is_active = True`,
  `created_by = U2`, `updated_by = None`, `deleted_at = None`, `deleted_by = None`
  (U3 instead of U2 for W2 rows), unless the case says otherwise.
- "deleted X" = same, but `is_deleted = True`, `deleted_at = T0`, `deleted_by = U2`.
- T0 = `2026-01-01 09:00:00` (naive).
- Setups never contain two live departments with the same name ignoring case and
  leading/trailing whitespace in one workspace (forbidden once BUG-003 is fixed).

**Externals.** Every test patches `app.dao.department.utcnow` to return
NOW = `datetime(2026, 1, 15, 10, 30, 0)` (naive). No other mocks, except the race
simulations below.

**Race simulations.** Only these cases patch `DepartmentManager._check_name_exists`
to return `False`, simulating a concurrent request that passed the Python
duplicate check:
- DEPT-C-17, DEPT-C-19 — `create_department` R6 [BUG-003]
- DEPT-U-22, DEPT-U-23 — `update_department` R11 [BUG-003]

In these cases the manager call itself is wrapped:
`with pytest.raises(HTTPException) as exc: with session.begin_nested(): M.<call>`.
Assert `exc.value.status_code` / `detail`, then re-read with fresh queries. Do not
assert on the session's state as left by the manager after the error.

**Rolled back.** `sp = session.begin_nested()` directly before the call, plus a spy that wraps `session.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after rollback" checks. One card per writer. The spy is sanctioned by the test environment; it is not a mock of the session's behaviour.

**sql_log.** A list filled by a `before_cursor_execute` listener on `session.connection()`, started at that Given line, removed after the call. Each entry is the statement text. `re` = the standard module.

**Checking results.**
- "re-read" = expire the session (`session.expire_all()`) and SELECT the row by id
  again; assertions after "re-read" are on the database values.
- "W1 count" = number of `departments` rows with `workspace_id = W1`, deleted
  rows included, counted with a fresh query.
- "unchanged" = every column listed for that row in Given has the same value on
  re-read.
- 404 / 400 / 409 errors are `fastapi.HTTPException`; assert `status_code` and
  `detail` exactly as written.
- Search results are compared as a **set of names** unless the case says
  "in order", in which case the exact list of names (and ids where given) is
  compared.
- Schema cases construct `DepartmentCreate` / `DepartmentUpdate` directly;
  "raises `ValidationError`" = `pydantic.ValidationError`, message not asserted.
- DB-level constraint cases (DEPT-C-14, C-15, U-21) make the offending change
  directly (no manager) and flush inside `session.begin_nested()`; the expected
  error is `sqlalchemy.exc.IntegrityError`, then the savepoint is rolled back
  before the re-read.

**Row-order dependence.** Cases DEPT-C-06, N-12, S-04..07 fail today only while physical row order keeps their target row outside the fetched page. The query fixes no order, so they are non-strict, as are the order cards S-13..15. DEPT-N-11 does not depend on order: its 100 rows equal the cap.

## `DepartmentManager.create_department`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-C-01 | R1, R5 | happy | W1 has no departments | `create_department(session, DepartmentCreate(name="Sales"), W1, U1)` | returns a `Department` with non-null `id` and `name == "Sales"`; re-read: `name == "Sales"`, `workspace_id == W1`, `created_by == U1`, `is_deleted is False`, `is_active is True`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`; W1 count == 1 | pass |
| DEPT-C-02 | R2; Errors row 1 | error | W1: live "Sales" | create `DepartmentCreate(name="Sales")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'Sales' already exists`; W1 count == 1; existing "Sales" row unchanged (`created_by == U2`) | pass |
| DEPT-C-03 | R3 | isolation | W2: live "Sales"; W1: none | create "Sales" in W1 by U1 | returns a Department; re-read new row: `name == "Sales"`, `workspace_id == W1`; W1 count == 1; W2's "Sales" row unchanged | pass |
| DEPT-C-04 | R3 | soft-delete | W1: deleted "Sales" | create "Sales" in W1 by U1 | returns a Department whose id differs from the deleted row's id; re-read new row: `name == "Sales"`, `is_deleted is False`; re-read old row: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2`; W1 count == 2 | pass |
| DEPT-C-05 | R2; Errors row 1 [BUG-002] | bug | W1: live "Sales" | create `DepartmentCreate(name="sales")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'sales' already exists` (submitted name, not "Sales"); W1 count == 1 | xfail BUG-002 — fails today on: no exception raised ("sales" is created) |
| DEPT-C-06 | R2 [BUG-001] | bug | W1, inserted in this order (120 rows): deleted "Archived 01"…"Archived 30", live "Team 01"…"Team 79", live "Logistics" (110th row), live "Unit 01"…"Unit 10" | create "Logistics" in W1 by U1 | raises HTTPException 409, detail `Department with name 'Logistics' already exists`; W1 count == 120; exactly one live row named "Logistics" in W1 | xfail BUG-001 (non-strict) — usually fails today on: no exception raised (a second "Logistics" is created). Author: claude |
| DEPT-C-07 | R4; Errors row 2 [BUG-004] | bug | W1 has no departments | target `schema`: build `DepartmentCreate(name="")` | raises `ValidationError`; W1 count == 0 | xfail BUG-004 — fails today on: no `ValidationError` raised |
| DEPT-C-08 | R4; Errors row 2 [BUG-004] | bug | W1 has no departments | target `schema`: build `DepartmentCreate(name="   ")` | raises `ValidationError`; W1 count == 0 | xfail BUG-004 — fails today on: no `ValidationError` raised |
| DEPT-C-09 | R4 | boundary | W1 has no departments | build `DepartmentCreate(name="a")`, then create it in W1 by U1 | building does not raise and `.name == "a"`; re-read new row: `name == "a"` | pass |
| DEPT-C-10 | R4 [BUG-004] | bug | W1 has no departments | build `DepartmentCreate(name=" Sales ")`, then create it in W1 by U1 | built `.name == "Sales"`; re-read new row: `name == "Sales"` | xfail BUG-004 — fails today on: `.name == " Sales "` |
| DEPT-C-11 | R4 [BUG-004] | bug | W1 has no departments | build `DepartmentCreate(name="  Sales  Team ")`, then create it in W1 by U1 | built `.name == "Sales  Team"` (two inner spaces kept); re-read new row: `name == "Sales  Team"` | xfail BUG-004 — fails today on: `.name == "  Sales  Team "` |
| DEPT-C-12 | R4 | happy | W1 has no departments | create `DepartmentCreate(name="sALES dept")` in W1 by U1 | re-read new row: `name == "sALES dept"` (case kept as typed) | pass |
| DEPT-C-13 | R2, R4 [BUG-004] | bug | W1: live "Sales" | build `DepartmentCreate(name=" Sales ")`, then create it in W1 by U1 | raises HTTPException 409, detail `Department with name 'Sales' already exists`; W1 count == 1 | xfail BUG-004 — fails today on: no exception raised (" Sales " is created) |
| DEPT-C-14 | R6 [BUG-003] | bug | W1: live "Finance" | DB level: add a second live "Finance" row in W1 directly (bypassing M) and flush inside a savepoint | flush raises `IntegrityError`; after rolling back the savepoint, W1 has exactly one row named "Finance" | xfail BUG-003 — fails today on: no `IntegrityError` raised |
| DEPT-C-15 | R6 [BUG-003] | bug | W1: live "Finance" | DB level: add a live "FINANCE" row in W1 directly and flush inside a savepoint | flush raises `IntegrityError` (constraint is on the normalised name); after rollback of the savepoint W1 count == 1 | xfail BUG-003 — fails today on: no `IntegrityError` raised |
| DEPT-C-16 | R6 | soft-delete | W1: deleted "Finance"; W2: live "Finance" | DB level: add a live "Finance" row in W1 directly and flush | flush succeeds; W1 count == 2 (one deleted, one live "Finance"); W2 still has its live "Finance" | pass |
| DEPT-C-17 | R6; Errors row 1 [BUG-003] | bug | W1: live "Finance"; race simulation: `_check_name_exists` patched → `False` | inside `session.begin_nested()`: create "Finance" in W1 by U1 | raises HTTPException 409, detail `Department with name 'Finance' already exists` (not `IntegrityError`); re-read: W1 has exactly one row named "Finance"; W1 count == 1 | xfail BUG-003 — fails today on: no exception raised (second "Finance" saved) |
| DEPT-C-18 | R2, R4; Errors row 1 [BUG-002] [BUG-004] | bug | W1: live "Sales" | build `DepartmentCreate(name=" sales ")`, then create it in W1 by U1 | built `.name == "sales"`; raises HTTPException 409, detail `Department with name 'sales' already exists` (submitted name trimmed, not the existing "Sales"); W1 count == 1 | xfail BUG-002, BUG-004 — fails today on: no exception raised (" sales " is created) |
| DEPT-C-19 | R6; Errors row 1 [BUG-003] | bug | W1: live "Finance"; race simulation: `_check_name_exists` patched → `False` | inside `session.begin_nested()`: create `DepartmentCreate(name="FINANCE")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'FINANCE' already exists` (submitted name); re-read: W1 count == 1, its only row named "Finance" | xfail BUG-003 — fails today on: no exception raised ("FINANCE" saved) |
| DEPT-C-20 | R4 | boundary | W1 has no departments | build `DepartmentCreate(name="Sales  Team")` (two inner spaces, no padding), then create it in W1 by U1 | building does not raise and `.name == "Sales  Team"`; re-read new row: `name == "Sales  Team"` (inner whitespace kept) | pass (split from DEPT-C-11) |
| DEPT-C-21 | Side effects (no commit) | side-effect | W1 has no departments; savepoint and commit spy per **rolled back** | `create_department(session, DepartmentCreate(name="Sales"), W1, U1)` | returns: a Department with non-null `id`; count: W1 count == 1; count after rollback: W1 count == 0; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `DepartmentManager.update_department`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-U-01 | R4, R9, R10 | happy | W1: live "Ops" with `updated_by = U2` | `update_department(session, <Ops id>, DepartmentUpdate(name="Operations"), W1, U1)` | returns a Department with `id == <Ops id>` and `name == "Operations"`; re-read: `name == "Operations"`, `updated_by == U1`, `workspace_id == W1`, `created_by == U2`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None` | pass |
| DEPT-U-02 | R1; Errors row 1 | error | W1: live "Ops" (`updated_by = U2`) | update MISSING with `DepartmentUpdate(name="X")` in W1 by U1 | raises HTTPException 404, detail `Department with ID <MISSING> not found`; "Ops" row unchanged; W1 count == 1 | pass |
| DEPT-U-03 | R2; Errors row 1 | isolation | W2: live "Ops" (`updated_by = U3`) | update <W2 Ops id> with `DepartmentUpdate(name="Hacked")`, workspace W1, by U1 | raises HTTPException 404, detail `Department with ID <W2 Ops id> not found`; re-read W2 row: `name == "Ops"`, `updated_by == U3`, `workspace_id == W2` | pass |
| DEPT-U-04 | R3; Errors row 2 | soft-delete | W1: deleted "Legacy" with `updated_by = U2` | update it with `DepartmentUpdate(name="Revived")` in W1 by U1 | raises HTTPException 400, detail `Cannot update deleted department`; re-read: `name == "Legacy"`, `updated_by == U2`, `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2` | pass |
| DEPT-U-05 | R3 | soft-delete | W1: deleted "Legacy" (`updated_by = U2`), live "Sales" | update "Legacy" with `DepartmentUpdate(name="Sales")` in W1 by U1 | raises HTTPException 400 `Cannot update deleted department` (not 409); "Legacy" row unchanged; "Sales" row unchanged | pass |
| DEPT-U-06 | R3 | soft-delete | W1: deleted "Legacy" (`updated_by = U2`) | update it with `DepartmentUpdate()` (empty) in W1 by U1 | raises HTTPException 400 `Cannot update deleted department`; re-read: `name == "Legacy"`, `updated_by == U2` | pass |
| DEPT-U-07 | R6; Errors row 3 | error | W1: live "Sales", live "Ops" (`updated_by = U2`) | update "Ops" with `DepartmentUpdate(name="Sales")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'Sales' already exists`; re-read "Ops": `name == "Ops"`, `updated_by == U2`; "Sales" row unchanged | pass |
| DEPT-U-08 | R6 | isolation | W2: live "Sales"; W1: live "Ops" (`updated_by = U2`) | update "Ops" with `DepartmentUpdate(name="Sales")` in W1 by U1 | no error; re-read "Ops" row: `name == "Sales"`, `updated_by == U1`; W2 "Sales" row unchanged | pass |
| DEPT-U-09 | R6 | soft-delete | W1: deleted "Sales", live "Ops" (`updated_by = U2`) | update "Ops" with `DepartmentUpdate(name="Sales")` in W1 by U1 | no error; re-read "Ops" row: `name == "Sales"`, `updated_by == U1`; deleted "Sales" row unchanged | pass |
| DEPT-U-10 | R6 | boundary | W1: live "HR" (`updated_by = U2`) | update "HR" with `DepartmentUpdate(name="hr")` in W1 by U1 | no error (the department itself is excluded from the duplicate check); re-read: `name == "hr"`, `updated_by == U1` | pass |
| DEPT-U-11 | R6; Errors row 3 [BUG-002] | bug | W1: live "Sales", live "Ops" (`updated_by = U2`) | update "Ops" with `DepartmentUpdate(name="SALES")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'SALES' already exists` (submitted name, not "Sales"); re-read "Ops": `name == "Ops"`, `updated_by == U2` | xfail BUG-002 — fails today on: no exception raised ("Ops" renamed to "SALES") |
| DEPT-U-12 | R9 [BUG-009] | bug | W1: live "HR" with `updated_by = U2` | update "HR" with `DepartmentUpdate()` (empty body) in W1 by U1 | no error; re-read: `updated_by == U2` (name assertions moved to DEPT-U-24) | xfail BUG-009 — fails today on: `updated_by == U1` |
| DEPT-U-13 | R9 [BUG-009] | bug | W1: live "HR" with `updated_by = U2` | update "HR" with `DepartmentUpdate(name=None)` in W1 by U1 | no error; re-read: `updated_by == U2` (name assertions moved to DEPT-U-25) | xfail BUG-009 — fails today on: `updated_by == U1` |
| DEPT-U-14 | R9 [BUG-009] | bug | W1: live "HR" with `updated_by = U2` | update "HR" with `DepartmentUpdate(name="HR")` in W1 by U1 | no error; re-read: `updated_by == U2` (name assertions moved to DEPT-U-26) | xfail BUG-009 — fails today on: `updated_by == U1` |
| DEPT-U-15 | R5, R8, R9 [BUG-004] [BUG-009] | bug | W1: live "HR" with `updated_by = U2` | build `DepartmentUpdate(name=" HR ")`, then update "HR" with it in W1 by U1 | built `.name == "HR"`; no error; re-read: `name == "HR"`, `updated_by == U2` | xfail BUG-004, BUG-009 — fails today on: re-read `name == " HR "` (and `updated_by == U1`) |
| DEPT-U-16 | R8; Errors row 4 [BUG-004] | bug | W1: live "Ops" | target `schema`: build `DepartmentUpdate(name="")` | raises `ValidationError`; re-read "Ops": `name == "Ops"` | xfail BUG-004 — fails today on: no `ValidationError` raised |
| DEPT-U-17 | R8; Errors row 4 [BUG-004] | bug | W1: live "Ops" | target `schema`: build `DepartmentUpdate(name="   ")` | raises `ValidationError`; re-read "Ops": `name == "Ops"` | xfail BUG-004 — fails today on: no `ValidationError` raised |
| DEPT-U-18 | R8 [BUG-004] | bug | W1: live "Team" (`updated_by = U2`) | build `DepartmentUpdate(name=" Ops ")`, then update "Team" with it in W1 by U1 | built `.name == "Ops"`; re-read: `name == "Ops"`, `updated_by == U1` | xfail BUG-004 — fails today on: `.name == " Ops "` |
| DEPT-U-19 | R8 | boundary | W1: live "Ops" (`updated_by = U2`) | build `DepartmentUpdate(name="a")`, then update "Ops" with it in W1 by U1 | building does not raise; re-read: `name == "a"`, `updated_by == U1` | pass |
| DEPT-U-20 | R7 | happy | — | target `schema`: build `DepartmentUpdate()` and `DepartmentUpdate(name=None)` | neither raises; both have `.name is None` | pass |
| DEPT-U-21 | R11 [BUG-003] | bug | W1: live "Finance", live "Budget" | DB level: set the "Budget" row's `name = "Finance"` directly and flush inside a savepoint | flush raises `IntegrityError`; after rolling back the savepoint, re-read "Budget": `name == "Budget"` | xfail BUG-003 — fails today on: no `IntegrityError` raised |
| DEPT-U-22 | R11; Errors row 3 [BUG-003] | bug | W1: live "Finance", live "Budget" (`updated_by = U2`); race simulation: `_check_name_exists` patched → `False` | inside `session.begin_nested()`: update "Budget" with `DepartmentUpdate(name="Finance")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'Finance' already exists` (not `IntegrityError`); re-read "Budget": `name == "Budget"`, `updated_by == U2` | xfail BUG-003 — fails today on: no exception raised (rename saved) |
| DEPT-U-23 | R11; Errors row 3 [BUG-003] | bug | W1: live "Finance", live "Budget" (`updated_by = U2`); race simulation: `_check_name_exists` patched → `False` | inside `session.begin_nested()`: update "Budget" with `DepartmentUpdate(name="finance")` in W1 by U1 | raises HTTPException 409, detail `Department with name 'finance' already exists` (submitted name, not "Finance"); re-read "Budget": `name == "Budget"`, `updated_by == U2`; "Finance" row unchanged | xfail BUG-003 — fails today on: no exception raised (rename to "finance" saved) |
| DEPT-U-24 | R7, R10 | happy | W1: live "HR" (`updated_by = U2`) | update "HR" with `DepartmentUpdate()` (empty body) in W1 by U1 | no error; returns a Department with `id == <HR id>` and `name == "HR"`; re-read: `name == "HR"`, `workspace_id == W1`, `created_by == U2`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`; W1 count == 1. Do NOT assert `updated_by` (BUG-009, see DEPT-U-12) | pass (split from DEPT-U-12) |
| DEPT-U-25 | R7, R10 | boundary | W1: live "HR" (`updated_by = U2`) | update "HR" with `DepartmentUpdate(name=None)` (explicit null) in W1 by U1 | no error (in particular no database error from writing NULL into `name`); returns a Department with `id == <HR id>` and `name == "HR"`; re-read: `name == "HR"` (not NULL), `workspace_id == W1`, `created_by == U2`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`; W1 count == 1. Do NOT assert `updated_by` (BUG-009, see DEPT-U-13) | pass (split from DEPT-U-13; verifier finding 1) |
| DEPT-U-26 | R5, R10 | boundary | W1: live "HR" (`updated_by = U2`) | update "HR" with `DepartmentUpdate(name="HR")` (current name) in W1 by U1 | no error (no 409 — the department does not collide with itself); returns a Department with `id == <HR id>` and `name == "HR"`; re-read: `name == "HR"`, `workspace_id == W1`, `created_by == U2`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`; W1 count == 1. Do NOT assert `updated_by` (BUG-009, see DEPT-U-14) | pass (split from DEPT-U-14) |
| DEPT-U-27 | Side effects (no commit) | side-effect | W1: live "Ops" (`updated_by = U2`); savepoint and commit spy per **rolled back** | `update_department(session, <Ops id>, DepartmentUpdate(name="Operations"), W1, U1)` | returns: `name == "Operations"`; re-read: `name == "Operations"`; re-read after rollback: `name == "Ops"`, `updated_by == U2`; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `DepartmentManager.get_department`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-G-01 | R1 | happy | W1: live "Sales" | `get_department(session, <Sales id>, W1)` | returns a Department with `id == <Sales id>`, `name == "Sales"`, `workspace_id == W1` | pass |
| DEPT-G-02 | R2; Errors row 1 | error | W1: live "Sales" | `get_department(session, MISSING, W1)` | raises HTTPException 404, detail `Department with ID <MISSING> not found` | pass |
| DEPT-G-03 | R2; Errors row 1 | isolation | W2: live "Sales" | `get_department(session, <W2 Sales id>, W1)` | raises HTTPException 404, detail `Department with ID <W2 Sales id> not found` | pass |
| DEPT-G-04 | R3; Errors row 1 [BUG-005] | bug | W1: deleted "Legacy" | `get_department(session, <Legacy id>, W1)` | raises HTTPException 404, detail `Department with ID <Legacy id> not found` | xfail BUG-005 — fails today on: no exception raised ("Legacy" returned) |
| DEPT-G-05 | R4 [BUG-005] | bug | W1: deleted "Legacy" | `get_department(session, <Legacy id>, W1, include_deleted=True)` | returns a Department with `id == <Legacy id>`, `name == "Legacy"`, `is_deleted is True` | xfail BUG-005 — fails today on: `TypeError` (no `include_deleted` parameter) |
| DEPT-G-06 | R4 [BUG-005] | bug | W2: live "Sales" | `get_department(session, <W2 Sales id>, W1, include_deleted=True)` | raises HTTPException 404, detail `Department with ID <W2 Sales id> not found` | xfail BUG-005 — fails today on: raises `TypeError` instead of HTTPException 404 |

## `DepartmentManager.search_departments`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-S-01 | R1 | isolation | W1: live "Ops", live "Sales"; W2: live "Sales", live "Finance" | `search_departments(session, W1)` | names == {"Ops", "Sales"}; every returned row has `workspace_id == W1`; returned ids are the W1 rows' ids | pass |
| DEPT-S-02 | R4 | soft-delete | W1: live "Ops", live "Sales", deleted "Legacy" | `search_departments(session, W1)` | names == {"Ops", "Sales"} | pass |
| DEPT-S-03 | R5 | soft-delete | W1: live "Ops", live "Sales", deleted "Legacy" | `search_departments(session, W1, include_deleted=True)` | names == {"Ops", "Sales", "Legacy"} | pass |
| DEPT-S-04 | R2, R4 [BUG-006] | bug | W1, inserted in order: deleted "Old A", deleted "Old B", deleted "Old C", live "Ops", live "Sales" | `search_departments(session, W1, limit=2)` | in order: ["Ops", "Sales"] (exactly 2 items) | xfail BUG-006 (non-strict) — usually fails today on: returns `[]`. Author: claude |
| DEPT-S-05 | R2, R4 [BUG-006] | bug | same as DEPT-S-04 | `search_departments(session, W1, skip=1, limit=1)` | in order: ["Sales"] | xfail BUG-006 (non-strict) — usually fails today on: returns `[]`. Author: claude |
| DEPT-S-06 | R2, R6 [BUG-007] | bug | W1, inserted in order: live "Accounts", "Budget", "Customs", "Warehouse" | `search_departments(session, W1, search="ware", limit=2)` | in order: ["Warehouse"] | xfail BUG-007 (non-strict) — usually fails today on: returns `[]`. Author: claude |
| DEPT-S-07 | R2, R6 [BUG-007] | bug | W1, inserted in order: live "Resale", "Admin", "Wholesale", "Billing", "Sales" | `search_departments(session, W1, search="ale", skip=1, limit=1)` | in order: ["Sales"] (matches sorted: Resale, Sales, Wholesale; skip 1) | xfail BUG-007 (non-strict) — usually fails today on: returns `[]`. Author: claude |
| DEPT-S-08 | R2 | boundary | W1, inserted in order: live "Alpha", "Bravo", "Charlie", "Delta", "Echo" | `search_departments(session, W1, skip=2, limit=3)` | exactly 3 items (skip + limit == 5 == number of matches) | pass |
| DEPT-S-09 | R2 | boundary | same as DEPT-S-08 | `search_departments(session, W1, skip=3, limit=3)` | exactly 2 items (skip + limit == 6 > 5 matches) | pass |
| DEPT-S-10 | R8 | boundary | same as DEPT-S-08 | `search_departments(session, W1, skip=5)` | returns `[]` | pass |
| DEPT-S-11 | R8 | boundary | same as DEPT-S-08 | `search_departments(session, W1, skip=4)` | exactly 1 item | pass |
| DEPT-S-12 | R2 | boundary | W1: 101 live departments "Dept 001"…"Dept 101" | `search_departments(session, W1)` (default `limit`) | exactly 100 items | pass |
| DEPT-S-13 | R3 [BUG-008] | bug | W1, inserted in order: live "Sales", "accounting", "HR", "beta" | `search_departments(session, W1)` | in order: ["accounting", "beta", "HR", "Sales"] (case-insensitive) | xfail BUG-008 (non-strict) — usually fails today on: order is ["Sales", "accounting", "HR", "beta"]. Author: claude |
| DEPT-S-14 | R3 [BUG-008] | bug | W1, inserted in order (spec example): deleted "sales" (id a), live "Accounting", live "HR", live "Sales" (id b, b > a) | `search_departments(session, W1, include_deleted=True)` | in order: ["Accounting", "HR", "sales" (id a), "Sales" (id b)] — equal names ignoring case ordered by id ascending | xfail BUG-008 (non-strict) — usually fails today on: order is ["sales", "Accounting", "HR", "Sales"]. Author: claude |
| DEPT-S-15 | R3 [BUG-008] | bug | W1, inserted in order: live "Echo", "delta", "Charlie", "bravo", "Alpha" | three calls: `limit=2` with `skip=0`, `skip=2`, `skip=4` | pages in order: ["Alpha", "bravo"], ["Charlie", "delta"], ["Echo"]; the 5 ids across pages are all distinct and cover all 5 rows | xfail BUG-008 (non-strict) — usually fails today on: first page is ["Echo", "delta"]. Author: claude |
| DEPT-S-16 | R6 | happy | W1: live "Sales", "Marketing", "Resale" | `search_departments(session, W1, search="ale")` | names == {"Sales", "Resale"} | pass |
| DEPT-S-17 | R6 | boundary | W1: live "sales team", "Ops" | `search_departments(session, W1, search="SALES")` | names == {"sales team"} | pass |
| DEPT-S-18 | R6 | boundary | W1: live "Sales", "Sales Team" | `search_departments(session, W1, search="sales ")` | names == {"Sales Team"} (trailing space in search is significant; "Sales" not matched) | pass |
| DEPT-S-19 | R7 | happy | W1: live "Ops", "Sales" | `search_departments(session, W1, search=None)` | names == {"Ops", "Sales"} | pass |
| DEPT-S-20 | R7 | boundary | W1: live "Ops", "Sales" | `search_departments(session, W1, search="")` | names == {"Ops", "Sales"} | pass |
| DEPT-S-21 | R8 | boundary | W1 has no departments; W2: live "Sales" | `search_departments(session, W1)` | returns `[]` | pass |
| DEPT-S-22 | R8 | happy | W1: live "Ops" | `search_departments(session, W1, search="xyz")` | returns `[]` | pass |
| DEPT-S-23 | R6a (HR-8) | boundary | W1: live "Growth 100%", "Sales", "Ops" | `search_departments(session, W1, search="%")` | names == {"Growth 100%"} (`%` is not a wildcard) | pass (regression guard for BUG-007 fix) |
| DEPT-S-24 | R6a (HR-8) | boundary | W1: live "R_D", "RnD", "Ops" | `search_departments(session, W1, search="_")` | names == {"R_D"} (`_` is not a wildcard) | pass (regression guard for BUG-007 fix) |
| DEPT-S-25 | R6a (HR-8) | boundary | W1: live "R_D", "RnD", "Ops" | `search_departments(session, W1, search="r_d")` | names == {"R_D"} ("RnD" not matched: `_` matches only itself; case still ignored) | pass (regression guard for BUG-007 fix) |
| DEPT-S-26 | R3 [BUG-008] | side-effect | W1: live "Ops", live "Sales"; **sql_log** started | `search_departments(session, W1)` | returns: names == {"Ops", "Sales"}; sql: a recorded statement selecting from `departments` orders by `lower(name)`, then `id` (`any(re.search(r"FROM departments\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL \| re.IGNORECASE) for s in sql_log)`) | xfail BUG-008 — fails today on: Then 2 (no such `ORDER BY`). Author: claude |

## `DepartmentManager.delete_department`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-D-01 | R3, R4 | happy | W1: live "Ops" with `updated_by = U2` | `delete_department(session, <Ops id>, W1, U1)` | returns a Department with `id == <Ops id>` and `is_deleted is True`; re-read (row still exists): `is_deleted is True`, `deleted_at == NOW` with `tzinfo is None`, `deleted_by == U1`, `name == "Ops"`, `updated_by == U2`, `is_active is True`, `created_by == U2`, `workspace_id == W1`; W1 count == 1 | pass |
| DEPT-D-02 | R1; Errors row 1 | error | W1: live "Ops" | `delete_department(session, MISSING, W1, U1)` | raises HTTPException 404, detail `Department with ID <MISSING> not found`; re-read "Ops": `is_deleted is False`, `deleted_at is None`, `deleted_by is None` | pass |
| DEPT-D-03 | R1; Errors row 1 | isolation | W2: live "Ops" | `delete_department(session, <W2 Ops id>, W1, U1)` | raises HTTPException 404, detail `Department with ID <W2 Ops id> not found`; re-read W2 row: `is_deleted is False`, `deleted_at is None`, `deleted_by is None` | pass |
| DEPT-D-04 | R2; Errors row 2 | soft-delete | W1: deleted "Legacy" (`deleted_at = T0`, `deleted_by = U2`) | `delete_department(session, <Legacy id>, W1, U1)` | raises HTTPException 400, detail `Department is already deleted`; re-read: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2` | pass |
| DEPT-D-05 | Side effects (no commit) | side-effect | W1: live "Ops"; savepoint and commit spy per **rolled back** | `delete_department(session, <Ops id>, W1, U1)` | returns: `is_deleted is True`; re-read: `is_deleted is True`; re-read after rollback: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`; mock called: the `session.commit` spy was never called | pass. Author: claude |

## `DepartmentManager._check_name_exists`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPT-N-01 | R7 | boundary | W1 has no departments; W2: live "Sales" | `_check_name_exists(session, W1, "Sales")` | returns `False` | pass |
| DEPT-N-02 | R1, R6 | happy | W1: live "Sales" | `_check_name_exists(session, W1, "Sales", exclude_id=None)` | returns `True` | pass |
| DEPT-N-03 | R2 | isolation | W2: live "Sales"; W1: live "Ops" | `_check_name_exists(session, W1, "Sales")` | returns `False` | pass |
| DEPT-N-04 | R3 | soft-delete | W1: deleted "Sales" | `_check_name_exists(session, W1, "Sales")` | returns `False` | pass |
| DEPT-N-05 | R3 | soft-delete | W1: deleted "Sales", live "Sales" | `_check_name_exists(session, W1, "Sales")` | returns `True` | pass |
| DEPT-N-06 | R4 [BUG-002] | bug | W1: live "Sales" | `_check_name_exists(session, W1, "sales")` | returns `True` | xfail BUG-002 — fails today on: returns `False` |
| DEPT-N-07 | R4 [BUG-002] | bug | W1: live "Sales" | `_check_name_exists(session, W1, "SALES")` | returns `True` | xfail BUG-002 — fails today on: returns `False` |
| DEPT-N-08 | R4 [BUG-002] | bug | W1: live "Sales" | `_check_name_exists(session, W1, "Sales ")` | returns `True` | xfail BUG-002 — fails today on: returns `False` |
| DEPT-N-09 | R4 [BUG-002] | bug | W1: live "Sales" | `_check_name_exists(session, W1, " Sales")` | returns `True` | xfail BUG-002 — fails today on: returns `False` |
| DEPT-N-10 | R4 | boundary | W1: live "Sales" | `_check_name_exists(session, W1, "Sales Team")` | returns `False` | pass |
| DEPT-N-11 | R5 | boundary | W1, inserted in order (100 rows): deleted "Archived 01"…"Archived 30", live "Team 01"…"Team 69", live "Logistics" (100th row) | `_check_name_exists(session, W1, "Logistics")` | returns `True` | pass |
| DEPT-N-12 | R5 [BUG-001] | bug | W1, inserted in order (101 rows): deleted "Archived 01"…"Archived 30", live "Team 01"…"Team 70", live "Logistics" (101st row) | `_check_name_exists(session, W1, "Logistics")` | returns `True` | xfail BUG-001 (non-strict) — usually fails today on: returns `False`. Author: claude |
| DEPT-N-13 | R6 | happy | W1: live "Sales" (id A) | `_check_name_exists(session, W1, "Sales", exclude_id=A)` | returns `False` | pass |
| DEPT-N-14 | R6 | boundary | W1: live "Sales" (id A), live "Ops" (id B) | `_check_name_exists(session, W1, "Sales", exclude_id=B)` | returns `True` (matching live department has a different id than `exclude_id`) | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `search_departments` R5 [BUG-010] | `DepartmentService` + `GET /departments/` | The list service/endpoint accepts `include_deleted` (default false) and passes it to the manager; with it true, soft-deleted departments are listed; without it they are hidden. Expected to fail today (flag never passed). |
| `create_department` R4, `update_department` R8 [BUG-004] (422 at the API) | `POST /departments/`, `PUT /departments/{id}` | A blank or whitespace-only `name` returns 422 and creates/changes nothing; a padded name is stored trimmed. |
| `search_departments` Inputs (API enforces `skip >= 0`, `limit` 1–1000; HR-7) | `GET /departments/` | `limit=0`, `limit=1001`, `skip=-1` → 422; `limit=1` and `limit=1000` accepted. |

## Spec gaps
None. Gaps 1–5 of revision 1 are closed by the spec (Gap log G1–G5); gap 6 of revision 2 (HR-10 row lock) is closed by G6 — HR-10 does not apply to renames / soft deletes, so no lock rule and no case.

## Retired IDs
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_department` | R1 | DEPT-C-01, DEPT-C-03 |
| `create_department` | R2 | DEPT-C-02, DEPT-C-05, DEPT-C-06, DEPT-C-13, DEPT-C-18 |
| `create_department` | R3 | DEPT-C-03, DEPT-C-04 |
| `create_department` | R4 | DEPT-C-07, DEPT-C-08, DEPT-C-09, DEPT-C-10, DEPT-C-11, DEPT-C-12, DEPT-C-13, DEPT-C-18, DEPT-C-20 |
| `create_department` | R5 | DEPT-C-01 |
| `create_department` | R6 | DEPT-C-14, DEPT-C-15, DEPT-C-16, DEPT-C-17, DEPT-C-19 |
| `create_department` | Errors: duplicate live name → 409 (submitted trimmed name in detail) | DEPT-C-02, DEPT-C-05, DEPT-C-06, DEPT-C-13, DEPT-C-17, DEPT-C-18, DEPT-C-19 |
| `create_department` | Errors: blank name → ValidationError | DEPT-C-07, DEPT-C-08 |
| `create_department` | Side effects: no commit | DEPT-C-21 |
| `create_department` | BUG-001 | DEPT-C-06 |
| `create_department` | BUG-002 | DEPT-C-05, DEPT-C-18 |
| `create_department` | BUG-003 | DEPT-C-14, DEPT-C-15, DEPT-C-17, DEPT-C-19 |
| `create_department` | BUG-004 | DEPT-C-07, DEPT-C-08, DEPT-C-10, DEPT-C-11, DEPT-C-13, DEPT-C-18 |
| `update_department` | R1 | DEPT-U-02 |
| `update_department` | R2 | DEPT-U-03 |
| `update_department` | R3 | DEPT-U-04, DEPT-U-05, DEPT-U-06 |
| `update_department` | R4 | DEPT-U-01, DEPT-U-08, DEPT-U-09, DEPT-U-10 |
| `update_department` | R5 | DEPT-U-15, DEPT-U-26 |
| `update_department` | R6 | DEPT-U-07, DEPT-U-08, DEPT-U-09, DEPT-U-10, DEPT-U-11 |
| `update_department` | R7 | DEPT-U-20, DEPT-U-24, DEPT-U-25 |
| `update_department` | R8 | DEPT-U-15, DEPT-U-16, DEPT-U-17, DEPT-U-18, DEPT-U-19 |
| `update_department` | R9 | DEPT-U-01, DEPT-U-12, DEPT-U-13, DEPT-U-14, DEPT-U-15 |
| `update_department` | R10 | DEPT-U-01, DEPT-U-24, DEPT-U-25, DEPT-U-26 |
| `update_department` | R11 | DEPT-U-21, DEPT-U-22, DEPT-U-23 |
| `update_department` | Errors: not found / other workspace → 404 | DEPT-U-02, DEPT-U-03 |
| `update_department` | Errors: soft-deleted → 400 | DEPT-U-04, DEPT-U-05, DEPT-U-06 |
| `update_department` | Errors: name taken → 409 (submitted trimmed name in detail) | DEPT-U-07, DEPT-U-11, DEPT-U-22, DEPT-U-23 |
| `update_department` | Errors: blank name → ValidationError | DEPT-U-16, DEPT-U-17 |
| `update_department` | Side effects: no commit | DEPT-U-27 |
| `update_department` | BUG-002 | DEPT-U-11 |
| `update_department` | BUG-003 | DEPT-U-21, DEPT-U-22, DEPT-U-23 |
| `update_department` | BUG-004 | DEPT-U-15, DEPT-U-16, DEPT-U-17, DEPT-U-18 |
| `update_department` | BUG-009 | DEPT-U-12, DEPT-U-13, DEPT-U-14, DEPT-U-15 |
| `get_department` | R1 | DEPT-G-01 |
| `get_department` | R2 | DEPT-G-02, DEPT-G-03 |
| `get_department` | R3 | DEPT-G-04 |
| `get_department` | R4 | DEPT-G-05, DEPT-G-06 |
| `get_department` | Errors: not found / other workspace / soft-deleted → 404 | DEPT-G-02, DEPT-G-03, DEPT-G-04, DEPT-G-06 |
| `get_department` | BUG-005 | DEPT-G-04, DEPT-G-05, DEPT-G-06 |
| `search_departments` | R1 | DEPT-S-01 |
| `search_departments` | R2 | DEPT-S-04, DEPT-S-05, DEPT-S-06, DEPT-S-07, DEPT-S-08, DEPT-S-09, DEPT-S-12 |
| `search_departments` | R3 | DEPT-S-13, DEPT-S-14, DEPT-S-15, DEPT-S-26 |
| `search_departments` | R4 | DEPT-S-02, DEPT-S-04, DEPT-S-05 |
| `search_departments` | R5 | DEPT-S-03; service/API part Deferred |
| `search_departments` | R6 | DEPT-S-06, DEPT-S-07, DEPT-S-16, DEPT-S-17, DEPT-S-18 |
| `search_departments` | R6a (HR-8) | DEPT-S-23, DEPT-S-24, DEPT-S-25 |
| `search_departments` | R7 | DEPT-S-19, DEPT-S-20 |
| `search_departments` | R8 | DEPT-S-10, DEPT-S-11, DEPT-S-21, DEPT-S-22 |
| `search_departments` | BUG-006 | DEPT-S-04, DEPT-S-05 |
| `search_departments` | BUG-007 | DEPT-S-06, DEPT-S-07 (R6a regression guards: DEPT-S-23, DEPT-S-24, DEPT-S-25) |
| `search_departments` | BUG-008 | DEPT-S-13, DEPT-S-14, DEPT-S-15 (non-strict), DEPT-S-26 (strict) |
| `search_departments` | BUG-010 | Deferred (`DepartmentService` + `GET /departments/`); manager side DEPT-S-03 |
| `delete_department` | R1 | DEPT-D-02, DEPT-D-03 |
| `delete_department` | R2 | DEPT-D-04 |
| `delete_department` | R3 | DEPT-D-01 |
| `delete_department` | R4 | DEPT-D-01 |
| `delete_department` | Errors: not found / other workspace → 404 | DEPT-D-02, DEPT-D-03 |
| `delete_department` | Errors: already deleted → 400 | DEPT-D-04 |
| `delete_department` | Side effects: no commit | DEPT-D-05 |
| `_check_name_exists` | R1 | DEPT-N-02, DEPT-N-05 |
| `_check_name_exists` | R2 | DEPT-N-03 |
| `_check_name_exists` | R3 | DEPT-N-04, DEPT-N-05 |
| `_check_name_exists` | R4 | DEPT-N-06, DEPT-N-07, DEPT-N-08, DEPT-N-09, DEPT-N-10 |
| `_check_name_exists` | R5 | DEPT-N-11, DEPT-N-12 |
| `_check_name_exists` | R6 | DEPT-N-02, DEPT-N-13, DEPT-N-14 |
| `_check_name_exists` | R7 | DEPT-N-01 |
| `_check_name_exists` | BUG-001 | DEPT-N-12 |
| `_check_name_exists` | BUG-002 | DEPT-N-06, DEPT-N-07, DEPT-N-08, DEPT-N-09 |
