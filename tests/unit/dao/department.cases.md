# Test cases — `app/dao/department.py`

> **Spec:** `tests/unit/dao/department.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). P1, P2, P3 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `department.verify.md` (case-missing Finding 1; recipe R-1): DEP-SD-12. Conventions gain the `session:` line, which no card here uses yet. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 24 cases · 23 expected-to-pass · 1 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `soft_delete` 12 · `restore` 12 (1 bug).
- **Depth:** lighter target (skill step 1a). Two stamp methods on a reference list, no stock, money or order state.
- **Family master:** `delivery_method` and `work_order_type` use these rules and these card numbers, each with its own cards, IDs and table.
- **Expected-to-fail:** BUG-003 1, strict (DEP-RS-10).
- **Notable design choices:**
  - One commit spy per writer: SD-10, RS-06. Each also proves the rollback the rule names.
  - SD-02, RS-03 use three different profiles, so an `updated_by` stamped with the deleter cannot hide behind a value already there. SD-03, RS-04 hold the empty side, and the inactive row.
  - The clock is patched to NOW in every test, so `deleted_at` cannot be the database's. RS-07 reads the row back with `db.refresh`: a row only flushed takes an UPDATE on restore, as `machine_maintenance_log` found (its DISCREPANCY-1).
  - SD-11, RS-09 count the statements: one row updated, nothing else. RS-02 uses a row really deleted by `soft_delete`, not only a built one.
  - R6 has both sides beside the bug: a deleted row of that name (RS-11) and a live one elsewhere (RS-12) block nothing, today or with the index.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `DEP` = `app/dao/department.py`. `SD` soft_delete · `RS` restore.

**Actors and fixed values.**
- `dao` = the singleton `department_dao` (`from app.dao.department import department_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `Department` = `app.models.department.Department`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2020, 1, 2, 3, 4, 5)`. NOW = `datetime(2031, 5, 6, 7, 8, 9)` (naive).

**Externals.** In every test `patch("app.dao.department.utcnow", return_value=NOW)` is active (a fixture does it; a card never patches anything itself). Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows; U1, U2, U3 = three `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. No profile has a `workspace_members` row.
- **row** = `Department(workspace_id=W1.id, name="Sales")`; `is_active` and `is_deleted` are left to their defaults, `True` and `False`, and `created_by`, `updated_by`, `deleted_by`, `deleted_at`, `updated_at` to `NULL`. After the word "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`: what a soft delete leaves, with `is_active` as it was. `updated_at` is not passed, so a card can see it become non-null.
- `db.refresh(A)` in a Given reads A back as a real caller's row would be: a row only flushed holds the columns it was given, and setting `None` over an unloaded column is a change to SQLAlchemy.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- `snapshot:` = a check on the value A0 held before the call: A0 is the snapshot of the row's columns taken after the last Given line.
- `read:` = calls the named `dao` reader after the When and asserts on its result.
- A `session:` line is a check on the session object.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.
- After a failed write, `db.refresh(row)` before reading the row. An `unchanged` line after a `raises:` includes that refresh.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()`, `db.refresh(A)`, and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on it.

**Race simulations.** None in this module.

## `DAODepartment.soft_delete`

### DEP-SD-01 — sets the three stamps and returns the same row
- **Rules:** `soft_delete` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. re-read A: `deleted_at == NOW`.
4. re-read A: `deleted_by == U2.id`.

### DEP-SD-02 — nothing else changes: updated_by is not stamped with the deleter
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but `created_by U1.id`, `updated_by U3.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `name == "Sales"`, `is_active is True`.
3. re-read A: `created_by == U1.id`, `updated_by == U3.id`.
4. unchanged: unchanged(A) except `is_deleted`, `deleted_at`, `deleted_by`, `updated_at`.

### DEP-SD-03 — an inactive row stays inactive, and empty stamps stay empty
- **Rules:** `soft_delete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but `is_active False`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is False`.
3. re-read A: `created_by is None`, `updated_by is None`.
4. re-read A: `is_deleted is True`.

### DEP-SD-04 — updated_at goes from NULL to a value
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row.
2. `db.refresh(A)`

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. snapshot: `A0.updated_at is None`.
3. re-read A: `updated_at is not None`.

### DEP-SD-05 — a row already deleted is deleted again: the stamps are overwritten
- **Rules:** `soft_delete` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but gone.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. re-read A: `deleted_at == NOW`.
4. re-read A: `deleted_by == U2.id`.

### DEP-SD-06 — a row of another workspace is deleted, by a profile with no link to it
- **Rules:** `soft_delete` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row.
2. Z = row, but `workspace_id W2.id`, `name "Ops"`.

**When**
- `result = dao.soft_delete(db, db_obj=Z, deleted_by=U1.id)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is True`, `deleted_at == NOW`, `deleted_by == U1.id`.
3. unchanged: unchanged(A).

### DEP-SD-07 — an unknown deleted_by raises and nothing changes
- **Rules:** `soft_delete` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = row.
2. `db.refresh(A)`

**When**
- `dao.soft_delete(db, db_obj=A, deleted_by=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. raises: `"departments_deleted_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. re-read A: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.

### DEP-SD-08 — deleted_by=None is stored
- **Rules:** `soft_delete` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=None)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. re-read A: `deleted_at == NOW`.
4. re-read A: `deleted_by is None`.

### DEP-SD-09 — the raw base reads still return the row
- **Rules:** `soft_delete` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = row.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. read: `dao.get(db, A.id) is A`.
3. read: `dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id) is A`.
4. read: `[r.id for r in dao.get_by_workspace(db, workspace_id=W1.id)] == [A.id]`.

### DEP-SD-10 — the delete is flushed, not committed: a rollback removes all three stamps
- **Rules:** `soft_delete` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `departments` rows with `id == A.id` and `is_deleted` true: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is False`.
4. re-read A after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
5. mock called: the `db.commit` spy was never called.

### DEP-SD-11 — one UPDATE of one department, and no other statement writes
- **Rules:** `soft_delete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row.
2. B = row, but `name "Ops"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. statement: `written[0].startswith("UPDATE departments")`.
4. unchanged: unchanged(B).

### DEP-SD-12 — a row already deleted, with deleted_by=None: the old deleter is overwritten
- **Rules:** `soft_delete` R4, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but gone.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=None)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. re-read A: `deleted_at == NOW`.
4. re-read A: `deleted_by is None`.

## `DAODepartment.restore`

### DEP-RS-01 — clears the three stamps and returns the same row
- **Rules:** `restore` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row, but gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. re-read A: `deleted_at is None`.
4. re-read A: `deleted_by is None`.

### DEP-RS-02 — a row soft-deleted through the DAO comes back
- **Rules:** `restore` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row.
2. `dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`
3. `db.refresh(A)`

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. re-read A: `deleted_at is None`.
4. re-read A: `deleted_by is None`.

### DEP-RS-03 — nothing else changes, and nobody is recorded
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone, `created_by U2.id`, `updated_by U3.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `name == "Sales"`, `is_active is True`.
3. re-read A: `created_by == U2.id`, `updated_by == U3.id`.
4. unchanged: unchanged(A) except `is_deleted`, `deleted_at`, `deleted_by`, `updated_at`.

### DEP-RS-04 — an inactive row stays inactive, and empty stamps stay empty
- **Rules:** `restore` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but gone, `is_active False`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is False`.
3. re-read A: `created_by is None`, `updated_by is None`.
4. re-read A: `is_deleted is False`.

### DEP-RS-05 — updated_at goes from NULL to a value
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone.
2. `db.refresh(A)`

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. snapshot: `A0.updated_at is None`.
3. re-read A: `updated_at is not None`.

### DEP-RS-06 — the restore is flushed, not committed: a rollback brings the deleted state back
- **Rules:** `restore` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `departments` rows with `id == A.id` and `is_deleted` false: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is True`.
4. re-read A after the savepoint rollback: `deleted_at == T0`, `deleted_by == U1.id`.
5. mock called: the `db.commit` spy was never called.

### DEP-RS-07 — a live row is accepted and nothing is sent
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but `created_by U1.id`.
2. `db.refresh(A)`
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).
3. re-read A: `updated_at is None`.
4. statement: `written == []`.

### DEP-RS-08 — a row of another workspace is restored
- **Rules:** `restore` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, but gone.
2. Z = row, but gone, `workspace_id W2.id`, `name "Ops"`.

**When**
- `result = dao.restore(db, db_obj=Z)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
3. unchanged: unchanged(A).

### DEP-RS-09 — one UPDATE of one department, and no other statement writes
- **Rules:** `restore` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone.
2. B = row, but gone, `name "Ops"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. statement: `written[0].startswith("UPDATE departments")`.
4. unchanged: unchanged(B).

### DEP-RS-10 — restoring next to a live row of that name is refused
- **Rules:** `restore` R6 [BUG-003], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-003
- **Fails today on:** Then 1 (no error is raised: two live rows of one name are stored)

**Given**
1. A = row, but gone, `name "Dup"`.
2. B = row, but `name "Dup"`.
3. `db.refresh(A)`

**When**
- `dao.restore(db, db_obj=A)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. re-read A: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U1.id`.
3. unchanged: unchanged(B).

### DEP-RS-11 — another deleted row of that name does not block a restore
- **Rules:** `restore` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but gone, `name "Dup"`.
2. B = row, but gone, `name "Dup"`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. unchanged: unchanged(B).

### DEP-RS-12 — a live row of that name in another workspace does not block a restore
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, but gone, `name "Dup"`.
2. B = row, but `workspace_id W2.id`, `name "Dup"`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. unchanged: unchanged(B).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `restore` R6 [BUG-003] — the 409 at the API, and the concurrent create | `DepartmentManager` (`tests/unit/managers/department_manager.spec.md`) | The DAO raises `IntegrityError`; BUG-001, BUG-002, BUG-003 live there. |
| P1 — the restore feature, when it exists, must refuse a name already taken (P3) and record the user (P2) | the manager method that will call `restore` | No caller today. |
| HR-4 — `get_department` returning a deleted row (BUG-005); a delete refusing a deleted row | `DepartmentManager` | `soft_delete` R4 stays raw here. |
| HR-1 — names trimmed and never blank (BUG-004) | `DepartmentManager`, `DepartmentCreate` | Schema rule. |
| Generic behavior of inherited `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Commit spies: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `department_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | `restore` Errors row 1, R6 | Gives `IntegrityError` with no `pgcode` and no index name, and the index does not exist yet. | DEP-RS-10 asserts the type only. |
| 3 | Model facts | Defaults, foreign keys and indexes are facts of the table, not rules of this DAO. | No card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `soft_delete` | Returns | DEP-SD-01 |
| `soft_delete` | R1 | DEP-SD-01 |
| `soft_delete` | R2 | DEP-SD-01, DEP-SD-10 |
| `soft_delete` | R3 | DEP-SD-02, DEP-SD-03, DEP-SD-04 |
| `soft_delete` | R4 | DEP-SD-05, DEP-SD-12 |
| `soft_delete` | R5 | DEP-SD-06 |
| `soft_delete` | R6 | DEP-SD-07 |
| `soft_delete` | R7 | DEP-SD-08, DEP-SD-12 |
| `soft_delete` | R8 | DEP-SD-09 |
| `soft_delete` | Errors row 1 | DEP-SD-07 |
| `soft_delete` | Side effects | DEP-SD-10, DEP-SD-11 |
| `restore` | Returns | DEP-RS-01 |
| `restore` | R1 | DEP-RS-01, DEP-RS-02 |
| `restore` | R2 | DEP-RS-03, DEP-RS-04, DEP-RS-05 |
| `restore` | R3 | DEP-RS-01, DEP-RS-06 |
| `restore` | R4 | DEP-RS-07 |
| `restore` | R5 | DEP-RS-08 |
| `restore` | R6 | DEP-RS-11, DEP-RS-12 |
| `restore` | R6 [BUG-003] | DEP-RS-10 |
| `restore` | Errors row 1 | DEP-RS-10 |
| `restore` | Side effects | DEP-RS-06, DEP-RS-09 |
