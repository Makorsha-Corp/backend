# Test cases — `app/dao/work_order_type.py`

> **Spec:** `tests/unit/dao/work_order_type.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). P1, P2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `work_order_type.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): Finding 1 → WOT-SD-12; Finding 2 → WOT-RS-12. Conventions gain the `session:` line, which no card here uses yet. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 30 cases · 26 expected-to-pass · 4 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `soft_delete` 12 · `restore` 12 (1 bug) · `create` 6 (3 bug).
- **Depth:** lighter target (skill step 1a). Same code as `department`, the family master; a type list writes no order state.
- **Expected-to-fail:** BUG-1214 4, all strict: WOT-RS-10, WOT-IN-02, IN-03, IN-04.
- **Notable design choices:**
  - One commit spy per writer: SD-10, RS-06. Each also proves the rollback the rule names.
  - SD-02, RS-03 use three different profiles, so an `updated_by` stamped with the deleter cannot hide behind a value already there. SD-03, RS-04 hold the empty side, and the inactive row.
  - The clock is patched to NOW in every test, so `deleted_at` cannot be the database's. RS-07 reads the row back with `db.refresh`: a row only flushed takes an UPDATE on restore, as `machine_maintenance_log` found (its DISCREPANCY-1).
  - SD-11, RS-09 count the statements: one row updated, nothing else. RS-02 uses a row really deleted by `soft_delete`, not only a built one.
  - **R6's setup.** The spec's Today note says R6 cannot be reached. Two rows of one exact name cannot be built today, but `Dup` and `dup` can (N3), so WOT-RS-10 uses those: it fails in the restore today, and stays valid with the index. See Spec gaps.
  - WOT-IN-01 is a pass card and asserts `23505` only. The spec also names `uq_wo_type_workspace_name`, but BUG-1214's fix replaces that constraint, so a pass card on the name would turn red on the fix. See Spec gaps.
  - Two deleted rows of one exact name cannot be built today, so RS-12 uses `Dup` and `dup`. IN-02 is the deleted-name rule here.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `WOT` = `app/dao/work_order_type.py`. `SD` soft_delete · `RS` restore · `IN` inherited `BaseDAO.create` on this table.

**Rule numbers** are those of the family master, `tests/unit/dao/department.spec.md`, read with `Department` as `WorkOrderType`, as `tests/unit/dao/work_order_type.spec.md` says. `restore` R6 and `create` N1, N2, N3 are that spec's own.

**Actors and fixed values.**
- `dao` = the singleton `work_order_type_dao` (`from app.dao.work_order_type import work_order_type_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `WorkOrderType` = `app.models.work_order_type.WorkOrderType`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2020, 1, 2, 3, 4, 5)`. NOW = `datetime(2031, 5, 6, 7, 8, 9)` (naive).

**Externals.** In every test `patch("app.dao.work_order_type.utcnow", return_value=NOW)` is active (a fixture does it; a card never patches anything itself). Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows; U1, U2, U3 = three `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. No profile has a `workspace_members` row.
- **row** = `WorkOrderType(workspace_id=W1.id, name="Repair")`; `is_active` and `is_deleted` are left to their defaults, `True` and `False`, and `created_by`, `updated_by`, `deleted_by`, `deleted_at`, `updated_at` to `NULL`. After the word "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`: what a soft delete leaves, with `is_active` as it was. `updated_at` is not passed, so a card can see it become non-null.
- `db.refresh(A)` in a Given reads A back as a real caller's row would be: a row only flushed holds the columns it was given, and setting `None` over an unloaded column is a change to SQLAlchemy.
- **Every two rows of one workspace have different names, deleted or not**, except where a card says otherwise: `uq_wo_type_workspace_name` covers all rows today.

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

## `DAOWorkOrderType.soft_delete`

### WOT-SD-01 — sets the three stamps and returns the same row
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

### WOT-SD-02 — nothing else changes: updated_by is not stamped with the deleter
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but `created_by U1.id`, `updated_by U3.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `name == "Repair"`, `is_active is True`.
3. re-read A: `created_by == U1.id`, `updated_by == U3.id`.
4. unchanged: unchanged(A) except `is_deleted`, `deleted_at`, `deleted_by`, `updated_at`.

### WOT-SD-03 — an inactive row stays inactive, and empty stamps stay empty
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

### WOT-SD-04 — updated_at goes from NULL to a value
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

### WOT-SD-05 — a row already deleted is deleted again: the stamps are overwritten
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

### WOT-SD-06 — a row of another workspace is deleted, by a profile with no link to it
- **Rules:** `soft_delete` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row.
2. Z = row, but `workspace_id W2.id`, `name "Install"`.

**When**
- `result = dao.soft_delete(db, db_obj=Z, deleted_by=U1.id)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is True`, `deleted_at == NOW`, `deleted_by == U1.id`.
3. unchanged: unchanged(A).

### WOT-SD-07 — an unknown deleted_by raises and nothing changes
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
3. raises: `"work_order_types_deleted_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. re-read A: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.

### WOT-SD-08 — deleted_by=None is stored
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

### WOT-SD-09 — the raw base reads still return the row
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

### WOT-SD-10 — the delete is flushed, not committed: a rollback removes all three stamps
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
2. count: inside the savepoint, `work_order_types` rows with `id == A.id` and `is_deleted` true: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is False`.
4. re-read A after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
5. mock called: the `db.commit` spy was never called.

### WOT-SD-11 — one UPDATE of one work order type, and no other statement writes
- **Rules:** `soft_delete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row.
2. B = row, but `name "Install"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. statement: `written[0].startswith("UPDATE work_order_types")`.
4. unchanged: unchanged(B).

### WOT-SD-12 — a row already deleted, with deleted_by=None: the old deleter is overwritten
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

## `DAOWorkOrderType.restore`

### WOT-RS-01 — clears the three stamps and returns the same row
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

### WOT-RS-02 — a row soft-deleted through the DAO comes back
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

### WOT-RS-03 — nothing else changes, and nobody is recorded
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone, `created_by U2.id`, `updated_by U3.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `name == "Repair"`, `is_active is True`.
3. re-read A: `created_by == U2.id`, `updated_by == U3.id`.
4. unchanged: unchanged(A) except `is_deleted`, `deleted_at`, `deleted_by`, `updated_at`.

### WOT-RS-04 — an inactive row stays inactive, and empty stamps stay empty
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

### WOT-RS-05 — updated_at goes from NULL to a value
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

### WOT-RS-06 — the restore is flushed, not committed: a rollback brings the deleted state back
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
2. count: inside the savepoint, `work_order_types` rows with `id == A.id` and `is_deleted` false: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is True`.
4. re-read A after the savepoint rollback: `deleted_at == T0`, `deleted_by == U1.id`.
5. mock called: the `db.commit` spy was never called.

### WOT-RS-07 — a live row is accepted and nothing is sent
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

### WOT-RS-08 — a row of another workspace is restored
- **Rules:** `restore` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, but gone.
2. Z = row, but gone, `workspace_id W2.id`, `name "Install"`.

**When**
- `result = dao.restore(db, db_obj=Z)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
3. unchanged: unchanged(A).

### WOT-RS-09 — one UPDATE of one work order type, and no other statement writes
- **Rules:** `restore` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, but gone.
2. B = row, but gone, `name "Install"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. statement: `written[0].startswith("UPDATE work_order_types")`.
4. unchanged: unchanged(B).

### WOT-RS-10 — restoring next to a live row of that name is refused, the case differing
- **Rules:** `restore` R6 [BUG-1214], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (no error is raised: the constraint compares case-sensitively, so both rows are live)

**Given**
1. A = row, but gone, `name "Dup"`.
2. B = row, but `name "dup"`.
3. `db.refresh(A)`

**When**
- `dao.restore(db, db_obj=A)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. re-read A: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U1.id`.
3. unchanged: unchanged(B).

### WOT-RS-11 — a live row of that name in another workspace does not block a restore
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

### WOT-RS-12 — another deleted row of that name, the case differing, does not block a restore
- **Rules:** `restore` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, but gone, `name "Dup"`.
2. B = row, but gone, `name "dup"`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. unchanged: unchanged(B).

## Inherited `BaseDAO.create` on `work_order_types`

### WOT-IN-01 — a second live row of one name is refused
- **Rules:** `create` N1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = row.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Repair"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `work_order_types` has exactly 1 row with `workspace_id == W1.id` and `name == "Repair"`.
4. unchanged: unchanged(A).

### WOT-IN-02 — a name held only by a soft-deleted row can be used again
- **Rules:** `create` N2 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (the call raises IntegrityError: the constraint counts soft-deleted rows)

**Given**
1. A = row, but gone.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Repair"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `name == "Repair"`, `is_deleted is False`.
3. count: `work_order_types` has exactly 2 rows with `workspace_id == W1.id` and `name == "Repair"`.
4. unchanged: unchanged(A).

### WOT-IN-03 — names that differ only in case collide among live rows
- **Rules:** `create` N3 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (no error is raised: both rows are stored)

**Given**
1. A = row, but `name "Same"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "same"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `work_order_types` has exactly 1 row with `workspace_id == W1.id`.
4. unchanged: unchanged(A).

### WOT-IN-04 — names that differ only in outer spaces collide among live rows
- **Rules:** `create` N3 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (no error is raised: both rows are stored)

**Given**
1. A = row, but `name "Same"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": " Same "})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `work_order_types` has exactly 1 row with `workspace_id == W1.id`.
4. unchanged: unchanged(A).

### WOT-IN-05 — the same name in another workspace is stored
- **Rules:** `create` N1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "name": "Repair"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `name == "Repair"`.
3. unchanged: unchanged(A).

### WOT-IN-06 — another name in the same workspace is stored
- **Rules:** `create` N1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Install"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "Install"`.
3. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create` N2, N3, `restore` R6 [BUG-1214] — the migration and the model declaring the index | the fix for BUG-1214 | These cards are its alarm. |
| `POST /work-order-types/` for a deleted name answers 409 today | `WorkOrderTypeManager.create_work_order_type` (not yet specified) | Verified there; WOT-IN-02 is the DAO's half. |
| FU-1 — `search_work_order_types` filters after `limit` (HR-5); `_check_name_exists` scans 100 rows with `==` (HR-2); no trim (HR-1) | `WorkOrderTypeManager` | Read, not run. |
| FU-2 — a soft-deleted type can be chosen for a new work order or template | `WorkOrderManager`, `WorkOrderTemplateManager` | **Order.** Read, not run. If that describer has not ruled, the owner is asked. |
| P1 — the restore feature, when it exists, must record the user | the manager method that will call `restore` | No caller today. |
| Generic behavior of inherited `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Commit spies: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `work_order_type_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | `create` N1, BUG-1214 | **Order.** N1 is untagged and names `uq_wo_type_workspace_name`, but the fix replaces that constraint with a partial index whose name the spec does not give. | WOT-IN-01 asserts `23505` only. If N1 is meant to pin the name, it needs the new name once the fix is written. |
| 3 | `restore` R6, *Today* note | **Order.** "Today this cannot be reached" holds only for the exact name. With `Dup` and `dup` (N3 says both are stored) both rows exist today, and a restore gives two live rows that differ in case. | WOT-RS-10 uses those names, so it fails in the restore and not in its Given. The note could be corrected at the next touch. |
| 4 | `restore` Errors, read from the department spec | Its row says "once BUG-003's index exists". Read here as BUG-1214's. No `pgcode` is given. | WOT-RS-10 asserts the type only. |
| 5 | Model facts | Defaults, foreign keys and indexes are facts of the table, not rules of this DAO. | No card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `soft_delete` | Returns | WOT-SD-01 |
| `soft_delete` | R1 | WOT-SD-01 |
| `soft_delete` | R2 | WOT-SD-01, WOT-SD-10 |
| `soft_delete` | R3 | WOT-SD-02, WOT-SD-03, WOT-SD-04 |
| `soft_delete` | R4 | WOT-SD-05, WOT-SD-12 |
| `soft_delete` | R5 | WOT-SD-06 |
| `soft_delete` | R6 | WOT-SD-07 |
| `soft_delete` | R7 | WOT-SD-08, WOT-SD-12 |
| `soft_delete` | R8 | WOT-SD-09 |
| `soft_delete` | Errors row 1 | WOT-SD-07 |
| `soft_delete` | Side effects | WOT-SD-10, WOT-SD-11 |
| `restore` | Returns | WOT-RS-01 |
| `restore` | R1 | WOT-RS-01, WOT-RS-02 |
| `restore` | R2 | WOT-RS-03, WOT-RS-04, WOT-RS-05 |
| `restore` | R3 | WOT-RS-01, WOT-RS-06 |
| `restore` | R4 | WOT-RS-07 |
| `restore` | R5 | WOT-RS-08 |
| `restore` | R6 | WOT-RS-11, WOT-RS-12 |
| `restore` | R6 [BUG-1214] | WOT-RS-10 |
| `restore` | Errors row 1 | WOT-RS-10 |
| `restore` | Side effects | WOT-RS-06, WOT-RS-09 |
| `create` | N1 | WOT-IN-01, WOT-IN-05, WOT-IN-06 |
| `create` | N2 [BUG-1214] | WOT-IN-02 |
| `create` | N3 [BUG-1214] | WOT-IN-03, WOT-IN-04 |
