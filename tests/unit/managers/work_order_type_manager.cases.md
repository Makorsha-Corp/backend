# Test cases — `app/managers/work_order_type_manager.py`

> **Spec:** `tests/unit/managers/work_order_type_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec unchanged; verifier findings 1 and 2 (`work_order_type_manager.verify.md`). Changed: WOTM-S-06 now checks the page size and a subset of the live ids, not one chosen row of an unordered page. New: WOTM-N-17, a strict statement recorder that is the order-free alarm for BUG-1706 (the capped name scan).
> **Counts:** 93 cases · 63 expected-to-pass · 30 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `create_work_order_type` 15 (7 bug) · `update_work_order_type` 23 (8 bug) · `get_work_order_type` 9 (3 bug) · `search_work_order_types` 24 (7 bug) · `delete_work_order_type` 5 · `_check_name_exists` 17 (5 bug).
- **Depth:** lighter target (skill step 1a). Reference data: a label on work orders. Nothing here moves order state, and the code is the same as `department_manager`. One card per rule and Errors row, one negative per filter, both sides of each paging boundary, one commit spy per writer, one statement recorder for the unordered list query. The name-comparison matrix lives on `_check_name_exists`.
- **Parallel to `delivery_method_manager.cases.md`:** the same ID tests the same thing in both files. The extra cards here are WOTM-C-15 and U-23 (a deleted name in other case is free, today and after the fix).
- **The unique constraint is the one real difference.** `uq_wo_type_workspace_name` covers all rows and is case-sensitive. A deleted type's exact name therefore fails today: WOTM-C-04 and U-08 are xfail BUG-1214, where delivery methods pass. The race cards WOTM-C-12 and U-21 pass today with `IntegrityError` 23505 (spec R6 / R11: the manager does not map it to 409). WOTM-C-13 (case variant past the check) is xfail BUG-1214.
- **Expected-to-fail by bug:** BUG-1707 5 · BUG-1708 7 · BUG-1214 3 · BUG-1711 3 · BUG-1521 3 · BUG-1709 4 · BUG-1710 3 · BUG-1706 2. Strict, except the six cards that rest on physical row order (WOTM-S-05, S-06, S-07, S-20, S-21, N-13). Those are non-strict, as in `department_manager` revision 5.
- **Notable design choices:**
  - Strict alarms that do not depend on row order: WOTM-S-22 (`ORDER BY lower(name), id`, BUG-1710) and WOTM-S-23 (the soft-delete filter is in the WHERE, BUG-1709). WOTM-N-17 (the name check sends no capped scan, BUG-1706) is the order-free alarm for WOTM-N-13.
  - Setups never hold two rows of one workspace with the exact same name (today's constraint). Equal names ignoring case use a deleted row in other case (WOTM-N-05, S-20, C-15, U-23).
  - No-op updates are split as in department: pass cards U-11, U-12, U-13 leave `updated_by` unasserted. The BUG-1711 xfails U-14, U-15 and U-16 assert only `updated_by`.
  - `delete_work_order_type` R4's "work orders and templates keep the type" has no card: the manager never reads them. The row stays, and WOTM-D-01 checks that.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `WOTM` = `app/managers/work_order_type_manager.py`. `C` create_work_order_type · `U` update_work_order_type · `G` get_work_order_type · `S` search_work_order_types · `D` delete_work_order_type · `N` _check_name_exists.

**Actors and fixed values.**
- `M` = the singleton `work_order_type_manager` (`from app.managers.work_order_type_manager import WorkOrderTypeManager, work_order_type_manager`). `db` = the test's real session, always the first argument, passed positionally; every other argument by keyword. `result` = what the When call returns.
- `WorkOrderType` (`app.models.work_order_type`), `WorkOrderTypeCreate`, `WorkOrderTypeUpdate` (`app.schemas.work_order_type`), `HTTPException` (`fastapi`), `ValidationError` (`pydantic`), `IntegrityError` (`sqlalchemy.exc`), `patch` (`unittest.mock`), `re`.
- W1, W2 = two `workspaces` rows made in that order (`W1.id < W2.id`); U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. U1 is the acting user; U2 created every Given row.
- MISSING = `999999999`. T0 = `datetime(2026, 1, 1, 9, 0, 0)`, NOW = `datetime(2026, 1, 15, 10, 30, 0)` (both naive).

**Externals.** An autouse fixture of the test file patches `app.dao.work_order_type.utcnow` to return NOW in every test. A card never patches anything itself, except the race simulations below.

**Given rows.** Inserted directly (never through `M`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. No `work_order_types` row exists unless the card lists it. A Given line written as code is run exactly as written.
- **type** = `WorkOrderType(workspace_id=W1.id, name=<given>, created_by=U2.id)`; `is_active True`, `is_deleted False`; `updated_by`, `deleted_at`, `deleted_by` None. The card always gives `name`; after "but" it lists every other column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- Two rows of one workspace never share the exact same name, deleted or not (`uq_wo_type_workspace_name` today). Two live rows never share a name ignoring case and outer spaces.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, **names(result)** = `[r.name for r in result]`, in the order returned. `sorted(ids(result)) == [...]` when order is not checked (ids on the right in Given order).
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read, every column of X equals its value just before the call.
- **nothing written** = the number of `work_order_types` rows (all workspaces) equals its value just before the call.
- `count:` lines count `work_order_types` rows with a fresh query and the filter stated.
- `session:` lines check `db` itself, before any re-read.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint. `raises: ValidationError` = `with pytest.raises(ValidationError):` around building the schema. Further `raises:` lines assert on `exc.value` after the block, one per line.

**Targets.** "target `schema`" = the When only builds the schema object; `M` is not called.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict, `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, unless the Expect line says `(non-strict)`.

**Race simulations** (Author: claude only). `patch.object(WorkOrderTypeManager, "_check_name_exists", return_value=False)` around the When. The call is wrapped `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Cards: WOTM-C-12, C-13 (`create_work_order_type` R6, R6a), WOTM-U-21 (`update_work_order_type` R11).

**Rolled back** (Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after rollback" checks. One card per writer.

**sql_log** (Author: claude only). A list filled by a `before_cursor_execute` listener on `db.connection()`, attached right before the When and removed after it. Each entry is the statement text.

## `WorkOrderTypeManager.create_work_order_type`

### WOTM-C-01 — a new type is stored with its name, workspace and creator
- **Rules:** `create_work_order_type` R1, R5, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderType)`, `result.id is not None`.
2. returns: `result.name == "Repair"`.
3. re-read the row `result.id`: `name == "Repair"`, `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read the row `result.id`: `is_deleted is False`, `is_active is True`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`.
5. count: rows of W1: exactly 1.

### WOTM-C-02 — a live type of the same name is refused with 409
- **Rules:** `create_work_order_type` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'Repair' already exists"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### WOTM-C-03 — the same name in another workspace does not block
- **Rules:** `create_work_order_type` R3a, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != Z.id`.
2. re-read the row `result.id`: `name == "Repair"`, `workspace_id == W1.id`.
3. count: rows of W1: exactly 1.
4. unchanged: unchanged(Z).

### WOTM-C-04 — a soft-deleted type's exact name can be used again
- **Rules:** `create_work_order_type` R3 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (the call raises IntegrityError on `uq_wo_type_workspace_name`)

**Given**
1. D = type, `name "Repair"`, but gone.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != D.id`.
2. re-read the row `result.id`: `name == "Repair"`, `is_deleted is False`.
3. re-read D: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2.id`.
4. count: rows of W1: exactly 2.

### WOTM-C-05 — a live name in other case is refused, the detail shows the submitted name
- **Rules:** `create_work_order_type` R2, Errors row 1 [BUG-1707]
- **Kind:** bug
- **Expect:** xfail BUG-1707
- **Fails today on:** Then 1 (no exception is raised: "repair" is created)

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'repair' already exists"`.
4. count: rows of W1: exactly 1.

### WOTM-C-06 — a padded live name is trimmed by the schema and refused
- **Rules:** `create_work_order_type` R2, R4 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (no exception is raised: " Repair " is created)

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name=" Repair "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'Repair' already exists"`.
4. count: rows of W1: exactly 1.

### WOTM-C-07 — an empty name is refused by the schema
- **Rules:** `create_work_order_type` R4, Errors row 3 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. W1 has no work order types.

**When**
- build `WorkOrderTypeCreate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: rows of W1: exactly 0.

### WOTM-C-08 — a whitespace-only name is refused by the schema
- **Rules:** `create_work_order_type` R4, Errors row 3 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. W1 has no work order types.

**When**
- build `WorkOrderTypeCreate(name="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: rows of W1: exactly 0.

### WOTM-C-09 — a one-character name is accepted
- **Rules:** `create_work_order_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="a"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "a"`.
2. re-read the row `result.id`: `name == "a"`.

### WOTM-C-10 — outer spaces are trimmed before the name is stored
- **Rules:** `create_work_order_type` R4 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (the schema keeps " Field Repair ")

**Given**
1. W1 has no work order types.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name=" Field Repair "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Field Repair"`.
2. re-read the row `result.id`: `name == "Field Repair"`.

### WOTM-C-11 — case and inner spaces are stored as typed
- **Rules:** `create_work_order_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="field  REPAIR"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "field  REPAIR"`.
2. re-read the row `result.id`: `name == "field  REPAIR"`.

### WOTM-C-12 — a duplicate past the Python check is refused by the database constraint
- **Rules:** `create_work_order_type` R6, Errors row 2
- **Kind:** error
- **Expect:** pass
- **Author:** claude — race simulation

**Given**
1. A = type, `name "Repair"`.
2. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `exc.value.orig.diag.constraint_name == "uq_wo_type_workspace_name"`.
4. count: rows of W1 with `name == "Repair"`: exactly 1.
5. count: rows of W1: exactly 1.

### WOTM-C-13 — the database also refuses a case variant past the Python check
- **Rules:** `create_work_order_type` R6a, Errors row 2 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Author:** claude — race simulation
- **Fails today on:** Then 1 (no IntegrityError: "repair" is stored)

**Given**
1. A = type, `name "Repair"`.
2. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: rows of W1: exactly 1.

### WOTM-C-14 — create flushes and never commits
- **Rules:** `create_work_order_type` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. W1 has no work order types.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: rows of W1: exactly 1.
3. count after rollback: rows of W1: exactly 0.
4. mock called: the `db.commit` spy was never called.

### WOTM-C-15 — a deleted type's name in other case does not block
- **Rules:** `create_work_order_type` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "repair"`, but gone.

**When**
- `result = M.create_work_order_type(db, type_data=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != D.id`.
2. re-read the row `result.id`: `name == "Repair"`, `is_deleted is False`.
3. re-read D: `name == "repair"`, `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2.id`.
4. count: rows of W1: exactly 2.

## `WorkOrderTypeManager.update_work_order_type`

### WOTM-U-01 — a rename changes the name and stamps updated_by, nothing else
- **Rules:** `update_work_order_type` R4, R9, R10, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="Field Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Field Repair"`.
2. re-read A: `name == "Field Repair"`, `updated_by == U1.id`, `updated_at is not None`.
3. re-read A: `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.

### WOTM-U-02 — an unknown id gets 404
- **Rules:** `update_work_order_type` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.update_work_order_type(db, type_id=MISSING, type_data=WorkOrderTypeUpdate(name="Inspection"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### WOTM-U-03 — another workspace's type gets 404 and is not touched
- **Rules:** `update_work_order_type` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `M.update_work_order_type(db, type_id=Z.id, type_data=WorkOrderTypeUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### WOTM-U-04 — a deleted type gets 400 before any name check
- **Rules:** `update_work_order_type` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type, `name "Inspection"`.
2. D = type, `name "Repair"`, but gone.

**When**
- `M.update_work_order_type(db, type_id=D.id, type_data=WorkOrderTypeUpdate(name="Inspection"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted work order type"`.
4. unchanged: unchanged(D).
5. unchanged: unchanged(A).

### WOTM-U-05 — a deleted type gets 400 also with an empty body
- **Rules:** `update_work_order_type` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "Repair"`, but gone, `updated_by U2.id`.

**When**
- `M.update_work_order_type(db, type_id=D.id, type_data=WorkOrderTypeUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted work order type"`.
4. re-read D: `name == "Repair"`, `updated_by == U2.id`, `is_deleted is True`.

### WOTM-U-06 — a name another live type has is refused with 409
- **Rules:** `update_work_order_type` R6, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`, but `updated_by U2.id`.

**When**
- `M.update_work_order_type(db, type_id=B.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'Repair' already exists"`.
4. unchanged: unchanged(B).
5. unchanged: unchanged(A).

### WOTM-U-07 — a name used only in another workspace is free
- **Rules:** `update_work_order_type` R6, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.
2. B = type, `name "Inspection"`.

**When**
- `result = M.update_work_order_type(db, type_id=B.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Repair"`.
2. re-read B: `name == "Repair"`, `updated_by == U1.id`.
3. unchanged: unchanged(Z).

### WOTM-U-08 — a deleted type's exact name can be taken by a rename
- **Rules:** `update_work_order_type` R6a [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (the call raises IntegrityError on flush)

**Given**
1. D = type, `name "Repair"`, but gone.
2. B = type, `name "Inspection"`.

**When**
- `result = M.update_work_order_type(db, type_id=B.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Repair"`.
2. re-read B: `name == "Repair"`, `updated_by == U1.id`.
3. unchanged: unchanged(D).

### WOTM-U-09 — a type may change the case of its own name
- **Rules:** `update_work_order_type` R6 (this type excluded), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "repair"`.
2. re-read A: `name == "repair"`, `updated_by == U1.id`.

### WOTM-U-10 — another live type's name in other case is refused with 409
- **Rules:** `update_work_order_type` R6, Errors row 3 [BUG-1707]
- **Kind:** bug
- **Expect:** xfail BUG-1707
- **Fails today on:** Then 1 (no exception is raised: A is renamed to "INSPECTION")

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.

**When**
- `M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="INSPECTION"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'INSPECTION' already exists"`.
4. re-read A: `name == "Repair"`.

### WOTM-U-11 — an empty body leaves the name and other fields alone
- **Rules:** `update_work_order_type` R7, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Repair"`.
2. re-read A: `name == "Repair"`, `workspace_id == W1.id`, `created_by == U2.id`.
3. re-read A: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
4. count: rows of W1: exactly 1.

### WOTM-U-12 — an explicit null name leaves the name alone
- **Rules:** `update_work_order_type` R7, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Repair"`.
2. re-read A: `name == "Repair"`, `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`.

### WOTM-U-13 — the current name is not a duplicate of itself
- **Rules:** `update_work_order_type` R5, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Repair"`.
2. re-read A: `name == "Repair"`, `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`.

### WOTM-U-14 — an empty body does not stamp updated_by
- **Rules:** `update_work_order_type` R9 [BUG-1711]
- **Kind:** bug
- **Expect:** xfail BUG-1711
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### WOTM-U-15 — an explicit null name does not stamp updated_by
- **Rules:** `update_work_order_type` R9 [BUG-1711]
- **Kind:** bug
- **Expect:** xfail BUG-1711
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### WOTM-U-16 — the unchanged name does not stamp updated_by
- **Rules:** `update_work_order_type` R9 [BUG-1711]
- **Kind:** bug
- **Expect:** xfail BUG-1711
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### WOTM-U-17 — the current name with outer spaces is trimmed and counts as unchanged
- **Rules:** `update_work_order_type` R5, R8 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (`result.name == " Repair "`: the schema keeps the spaces)

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name=" Repair "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Repair"`.
2. re-read A: `name == "Repair"`.

### WOTM-U-18 — an empty name is refused by the update schema
- **Rules:** `update_work_order_type` R8, Errors row 5 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. A = type, `name "Repair"`.

**When**
- build `WorkOrderTypeUpdate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. re-read A: `name == "Repair"`.

### WOTM-U-19 — a whitespace-only name is refused by the update schema
- **Rules:** `update_work_order_type` R8, Errors row 5 [BUG-1708]
- **Kind:** bug
- **Expect:** xfail BUG-1708
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. A = type, `name "Repair"`.

**When**
- build `WorkOrderTypeUpdate(name="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. re-read A: `name == "Repair"`.

### WOTM-U-20 — a one-character new name is accepted
- **Rules:** `update_work_order_type` R8, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="a"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "a"`.
2. re-read A: `name == "a"`, `updated_by == U1.id`.

### WOTM-U-21 — a rename onto a live duplicate past the Python check is refused by the constraint
- **Rules:** `update_work_order_type` R11, Errors row 4
- **Kind:** error
- **Expect:** pass
- **Author:** claude — race simulation

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`, but `updated_by U2.id`.
3. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.update_work_order_type(db, type_id=B.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `exc.value.orig.diag.constraint_name == "uq_wo_type_workspace_name"`.
4. re-read B: `name == "Inspection"`, `updated_by == U2.id`.

### WOTM-U-22 — update flushes and never commits
- **Rules:** `update_work_order_type` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.update_work_order_type(db, type_id=A.id, type_data=WorkOrderTypeUpdate(name="Overhaul"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Overhaul"`.
2. re-read A: `name == "Overhaul"`.
3. re-read A after rollback: `name == "Repair"`, `updated_by == U2.id`.
4. mock called: the `db.commit` spy was never called.

### WOTM-U-23 — a deleted type's name in other case is free for a rename
- **Rules:** `update_work_order_type` R6, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "repair"`, but gone.
2. B = type, `name "Inspection"`.

**When**
- `result = M.update_work_order_type(db, type_id=B.id, type_data=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Repair"`.
2. re-read B: `name == "Repair"`, `updated_by == U1.id`.
3. unchanged: unchanged(D).

## `WorkOrderTypeManager.get_work_order_type`

### WOTM-G-01 — a live type is returned by its id
- **Rules:** `get_work_order_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L = type, `name "Assembly"`.
2. T = type, `name "Repair"`.
3. H = type, `name "Service"`.

**When**
- `result = M.get_work_order_type(db, type_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderType)`.
2. returns: `result.id == T.id`, `result.name == "Repair"`, `result.workspace_id == W1.id`.

### WOTM-G-02 — an unknown id gets 404
- **Rules:** `get_work_order_type` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.get_work_order_type(db, type_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.

### WOTM-G-03 — id 0 gets 404
- **Rules:** `get_work_order_type` R2, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.get_work_order_type(db, type_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 0 not found"`.

### WOTM-G-04 — a type of a workspace with a higher id gets 404
- **Rules:** `get_work_order_type` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. Z = type, `name "Inspection"`, but `workspace_id W2.id`.

**When**
- `M.get_work_order_type(db, type_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.

### WOTM-G-05 — a type of a workspace with a lower id gets 404
- **Rules:** `get_work_order_type` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. Z = type, `name "Inspection"`, but `workspace_id W2.id`.

**When**
- `M.get_work_order_type(db, type_id=A.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {A.id} not found"`.

### WOTM-G-06 — a soft-deleted type is hidden by default
- **Rules:** `get_work_order_type` R3, Errors [BUG-1521]
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (no exception is raised: the deleted type is returned)

**Given**
1. D = type, `name "Repair"`, but gone.

**When**
- `M.get_work_order_type(db, type_id=D.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {D.id} not found"`.

### WOTM-G-07 — include_deleted=True returns a soft-deleted type
- **Rules:** `get_work_order_type` R4 [BUG-1521]
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. D = type, `name "Repair"`, but gone.

**When**
- `result = M.get_work_order_type(db, type_id=D.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == D.id`.
2. returns: `result.is_deleted is True`.

### WOTM-G-08 — include_deleted=True does not reach another workspace
- **Rules:** `get_work_order_type` R4, Errors [BUG-1521]
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`, gone.

**When**
- `M.get_work_order_type(db, type_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.

### WOTM-G-09 — the read writes nothing and keeps the caller's unflushed edits
- **Rules:** `get_work_order_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.
3. `B.name = "Edited"` (not flushed).
4. `P = WorkOrderType(workspace_id=W1.id, name="Pending", created_by=U2.id)`; `db.add(P)` (not flushed).

**When**
- `result = M.get_work_order_type(db, type_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `P in db.new`.
5. session: `len(db.new) == 1`.
6. session: `not db.deleted`.

## `WorkOrderTypeManager.search_work_order_types`

### WOTM-S-01 — only the workspace's types are listed (other workspace has the higher id)
- **Rules:** `search_work_order_types` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.
3. Z = type, `name "Service"`, but `workspace_id W2.id`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### WOTM-S-02 — only the workspace's types are listed (other workspace has the lower id)
- **Rules:** `search_work_order_types` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. Z = type, `name "Service"`, but `workspace_id W2.id`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### WOTM-S-03 — soft-deleted types are left out by default
- **Rules:** `search_work_order_types` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. D = type, `name "Inspection"`, but gone.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTM-S-04 — include_deleted=True keeps soft-deleted types
- **Rules:** `search_work_order_types` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. D = type, `name "Inspection"`, but gone.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, D.id]`.

### WOTM-S-05 — deleted types take no place in the page (limit)
- **Rules:** `search_work_order_types` R2, R4 [BUG-1709]
- **Kind:** bug
- **Expect:** xfail BUG-1709 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `[]`: the page holds the deleted rows)

**Given**
1. D1 = type, `name "Audit 1"`, but gone.
2. D2 = type, `name "Audit 2"`, but gone.
3. D3 = type, `name "Audit 3"`, but gone.
4. A = type, `name "Inspection"`.
5. B = type, `name "Repair"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### WOTM-S-06 — deleted types are not counted by skip
- **Rules:** `search_work_order_types` R2, R4 [BUG-1709]
- **Kind:** bug
- **Expect:** xfail BUG-1709 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `len(result) == 2`: skip counted a deleted row, both live rows come back)

**Given**
1. D1 = type, `name "Audit 1"`, but gone.
2. D2 = type, `name "Audit 2"`, but gone.
3. D3 = type, `name "Audit 3"`, but gone.
4. A = type, `name "Inspection"`.
5. B = type, `name "Repair"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### WOTM-S-07 — the search looks past the first page
- **Rules:** `search_work_order_types` R2, R6 [BUG-1709]
- **Kind:** bug
- **Expect:** xfail BUG-1709 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `[]`: only the first two rows are searched)

**Given**
1. A = type, `name "Assembly"`.
2. B = type, `name "Cleaning"`.
3. C = type, `name "Inspection"`.
4. X = type, `name "Repair"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="pair", limit=2)`.

**Then**
1. returns: `ids(result) == [X.id]`.

### WOTM-S-08 — a page is full when skip + limit equals the matches
- **Rules:** `search_work_order_types` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: type, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, skip=2, limit=3)`.

**Then**
1. returns: `len(result) == 3`.

### WOTM-S-09 — a page is short when skip + limit passes the matches
- **Rules:** `search_work_order_types` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: type, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, skip=3, limit=3)`.

**Then**
1. returns: `len(result) == 2`.

### WOTM-S-10 — skip at the number of matches gives an empty list
- **Rules:** `search_work_order_types` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: type, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### WOTM-S-11 — the default limit is 100
- **Rules:** `search_work_order_types` R2 (default `limit`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, type, `name f"Kind {k:03d}"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### WOTM-S-12 — limit=1000 lists past 100
- **Rules:** `search_work_order_types` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, type, `name f"Kind {k:03d}"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### WOTM-S-13 — search matches a part of the name, ignoring case on both sides
- **Rules:** `search_work_order_types` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "PREREPAIR"`.
3. C = type, `name "Inspection"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="Pai")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### WOTM-S-14 — a leading space in the search counts
- **Rules:** `search_work_order_types` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Field Repair"`.
2. B = type, `name "Repaint"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search=" rep")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTM-S-15 — `%` in the search matches only itself
- **Rules:** `search_work_order_types` R6a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Check 100%"`.
2. B = type, `name "Repair"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTM-S-16 — `_` in the search matches only itself
- **Rules:** `search_work_order_types` R6a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Pre_Check"`.
2. B = type, `name "PreXCheck"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="e_c")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTM-S-17 — an empty search is no filter
- **Rules:** `search_work_order_types` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### WOTM-S-18 — a workspace with no types gives an empty list
- **Rules:** `search_work_order_types` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOTM-S-19 — a search with no match gives an empty list
- **Rules:** `search_work_order_types` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, search="xyz")`.

**Then**
1. returns: `result == []`.

### WOTM-S-20 — the list is sorted by name ignoring case, ties by id
- **Rules:** `search_work_order_types` R3 [BUG-1710]
- **Kind:** bug
- **Expect:** xfail BUG-1710 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually insertion order: S first)

**Given**
1. S = type, `name "Service"`.
2. R = type, `name "Repair"`.
3. R2 = type, `name "repair"`, but gone.
4. R3 = type, `name "REPAIR"`, but gone.
5. A = type, `name "Assembly"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [A.id, R.id, R2.id, R3.id, S.id]`.

### WOTM-S-21 — the sort is applied before paging
- **Rules:** `search_work_order_types` R3 [BUG-1710]
- **Kind:** bug
- **Expect:** xfail BUG-1710 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `["Charlie", "bravo"]`: insertion order)

**Given**
1. 5 rows, in this order: type, `name` `"Echo"`, `"delta"`, `"Charlie"`, `"bravo"`, `"Alpha"`.

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `names(result) == ["Charlie", "delta"]`.

### WOTM-S-22 — the list query orders by lower(name), then id
- **Rules:** `search_work_order_types` R3 [BUG-1710]
- **Kind:** bug
- **Expect:** xfail BUG-1710
- **Author:** claude — statement recorder
- **Fails today on:** Then 2 (no such `ORDER BY` is sent)

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.
3. **sql_log** attached (Conventions).

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. statement: `any(re.search(r"FROM work_order_types\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL | re.IGNORECASE) for s in sql_log)`.

### WOTM-S-23 — the list query filters soft-deleted rows in SQL
- **Rules:** `search_work_order_types` R2, R4 [BUG-1709]
- **Kind:** bug
- **Expect:** xfail BUG-1709
- **Author:** claude — statement recorder
- **Fails today on:** Then 2 (the WHERE clause has only the workspace filter)

**Given**
1. A = type, `name "Repair"`.
2. D = type, `name "Inspection"`, but gone.
3. **sql_log** attached (Conventions).

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `any(re.search(r"FROM work_order_types\b.*\bWHERE\b.*\bis_deleted\b", s, re.DOTALL | re.IGNORECASE) for s in sql_log)`.

### WOTM-S-24 — the list writes nothing and keeps the caller's unflushed edits
- **Rules:** `search_work_order_types` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.
3. `B.name = "Edited"` (not flushed).
4. `P = WorkOrderType(workspace_id=W1.id, name="Pending", created_by=U2.id)`; `db.add(P)` (not flushed).

**When**
- `result = M.search_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `P in db.new`.
5. session: `len(db.new) == 1`.
6. session: `not db.deleted`.

## `WorkOrderTypeManager.delete_work_order_type`

### WOTM-D-01 — a live type is soft-deleted and kept
- **Rules:** `delete_work_order_type` R3, R4, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`, but `updated_by U2.id`.

**When**
- `result = M.delete_work_order_type(db, type_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.is_deleted is True`.
2. re-read A: `is_deleted is True`, `deleted_at == NOW`, `deleted_at.tzinfo is None`, `deleted_by == U1.id`.
3. re-read A: `name == "Repair"`, `is_active is True`, `updated_by == U2.id`, `created_by == U2.id`, `workspace_id == W1.id`.
4. count: rows of W1: exactly 1.

### WOTM-D-02 — an unknown id gets 404
- **Rules:** `delete_work_order_type` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `M.delete_work_order_type(db, type_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### WOTM-D-03 — another workspace's type gets 404 and is not deleted
- **Rules:** `delete_work_order_type` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `M.delete_work_order_type(db, type_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.
4. re-read Z: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.

### WOTM-D-04 — an already deleted type gets 400, its stamps stay
- **Rules:** `delete_work_order_type` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "Repair"`, but gone.

**When**
- `M.delete_work_order_type(db, type_id=D.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order type is already deleted"`.
4. re-read D: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2.id`.

### WOTM-D-05 — delete flushes and never commits
- **Rules:** `delete_work_order_type` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A = type, `name "Repair"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_work_order_type(db, type_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.is_deleted is True`.
2. re-read A: `is_deleted is True`.
3. re-read A after rollback: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
4. mock called: the `db.commit` spy was never called.

## `WorkOrderTypeManager._check_name_exists`

### WOTM-N-01 — a workspace with no types has no name
- **Rules:** `_check_name_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair")`.

**Then**
1. returns: `result is False`.

### WOTM-N-02 — a live type of the name is found
- **Rules:** `_check_name_exists` R1, R6 (`exclude_id=None`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair", exclude_id=None)`.

**Then**
1. returns: `result is True`.

### WOTM-N-03 — the name in another workspace is not considered
- **Rules:** `_check_name_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type, `name "Inspection"`.
2. Z = type, `name "Repair"`, but `workspace_id W2.id`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair")`.

**Then**
1. returns: `result is False`.

### WOTM-N-04 — a soft-deleted type of the name is ignored
- **Rules:** `_check_name_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "Repair"`, but gone.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair")`.

**Then**
1. returns: `result is False`.

### WOTM-N-05 — a live match is found behind a deleted row in other case
- **Rules:** `_check_name_exists` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = type, `name "repair"`, but gone.
2. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair")`.

**Then**
1. returns: `result is True`.

### WOTM-N-06 — the name matches in capitals
- **Rules:** `_check_name_exists` R4 [BUG-1707]
- **Kind:** bug
- **Expect:** xfail BUG-1707
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="REPAIR")`.

**Then**
1. returns: `result is True`.

### WOTM-N-07 — the name matches with a leading space
- **Rules:** `_check_name_exists` R4 [BUG-1707]
- **Kind:** bug
- **Expect:** xfail BUG-1707
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name=" Repair")`.

**Then**
1. returns: `result is True`.

### WOTM-N-08 — a stored name with outer spaces matches in other case
- **Rules:** `_check_name_exists` R4 [BUG-1707]
- **Kind:** bug
- **Expect:** xfail BUG-1707
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = type, `name " Repair "`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="repair")`.

**Then**
1. returns: `result is True`.

### WOTM-N-09 — a longer name containing the stored one does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair Urgent")`.

**Then**
1. returns: `result is False`.

### WOTM-N-10 — a part of the stored name does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="epai")`.

**Then**
1. returns: `result is False`.

### WOTM-N-11 — `_` in the name is not a wildcard
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Rep_ir")`.

**Then**
1. returns: `result is False`.

### WOTM-N-12 — a match on the 100th row is found
- **Rules:** `_check_name_exists` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 30 rows, by `add_all`: k = 1 … 30, type, `name f"Archived {k:02d}"`, but gone.
2. 69 rows, by `add_all`: k = 1 … 69, type, `name f"Team {k:02d}"`.
3. L = type, `name "Logistics"` (the 100th row).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Logistics")`.

**Then**
1. returns: `result is True`.

### WOTM-N-13 — a match beyond the 100th row is found
- **Rules:** `_check_name_exists` R5 [BUG-1706]
- **Kind:** bug
- **Expect:** xfail BUG-1706 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually returns False: only 100 rows are read)

**Given**
1. 30 rows, by `add_all`: k = 1 … 30, type, `name f"Archived {k:02d}"`, but gone.
2. 70 rows, by `add_all`: k = 1 … 70, type, `name f"Team {k:02d}"`.
3. L = type, `name "Logistics"` (the 101st row).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Logistics")`.

**Then**
1. returns: `result is True`.

### WOTM-N-14 — the excluded type's own name is ignored
- **Rules:** `_check_name_exists` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair", exclude_id=A.id)`.

**Then**
1. returns: `result is False`.

### WOTM-N-15 — excluding a type with a higher id still finds the match
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type, `name "Repair"`.
2. B = type, `name "Inspection"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair", exclude_id=B.id)`.

**Then**
1. returns: `result is True`.

### WOTM-N-16 — excluding a type with a lower id still finds the match
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = type, `name "Inspection"`.
2. A = type, `name "Repair"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair", exclude_id=B.id)`.

**Then**
1. returns: `result is True`.

### WOTM-N-17 — the name check sends no capped scan of the workspace
- **Rules:** `_check_name_exists` R5 [BUG-1706]
- **Kind:** bug
- **Expect:** xfail BUG-1706
- **Author:** claude — statement recorder
- **Fails today on:** Then 3 (the check reads the workspace's rows with `LIMIT` and no `name` in the WHERE)

**Given**
1. A = type, `name "Repair"`.
2. **sql_log** attached (Conventions).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Repair")`.

**Then**
1. returns: `result is True`.
2. statement: `any(re.search(r"FROM work_order_types", s, re.IGNORECASE) for s in sql_log)`.
3. statement: `not any(re.search(r"LIMIT", s, re.IGNORECASE) and not re.search(r"WHERE.*name", s, re.DOTALL | re.IGNORECASE) for s in sql_log if re.search(r"FROM work_order_types", s, re.IGNORECASE))`. (Spec R5 asks only that every live row be examined: a read with no `LIMIT`, or one that compares `name` in its WHERE — an `EXISTS` or `LIMIT 1` on the name — both pass.)

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `search_work_order_types` R5 reach [BUG-1520] | `WorkOrderTypeService.get_work_order_types` + `GET /work-order-types/` | The list passes `include_deleted` to the manager; with it true deleted types are listed. |
| `create_work_order_type` R4, `update_work_order_type` R8 [BUG-1708] (422 at the API) | `POST /work-order-types/`, `PUT /work-order-types/{id}` | A blank name returns 422 and changes nothing; a padded name is stored trimmed. |
| `create_work_order_type` R6, `update_work_order_type` R11 — the 409 "This resource already exists" | global `IntegrityError` handler | Integration-only: a constraint violation answers 409. |
| HR-7 bounds (`skip >= 0`, `1 <= limit <= 1000`) | `GET /work-order-types/` | `limit=0`, `limit=1001`, `skip=-1` → 422. |
| BUG-1228 (a deleted type chosen on new work orders) | work order managers | Not reached here. |
| `delete_work_order_type` R4 "work orders and templates keep the type" | work order / template managers | The manager never reads them; WOTM-D-01 checks only that the row stays. |

## Spec gaps
None.

## Retired IDs
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_work_order_type` | R1 | WOTM-C-01, WOTM-C-03, WOTM-C-15 |
| `create_work_order_type` | R2 | WOTM-C-02, WOTM-C-05, WOTM-C-06 |
| `create_work_order_type` | R3 [BUG-1214] | WOTM-C-04 (xfail); pass side: WOTM-C-15 |
| `create_work_order_type` | R3a | WOTM-C-03 |
| `create_work_order_type` | R4 | WOTM-C-06, WOTM-C-07, WOTM-C-08, WOTM-C-09, WOTM-C-10, WOTM-C-11 |
| `create_work_order_type` | R5 | WOTM-C-01 |
| `create_work_order_type` | R6 | WOTM-C-12 |
| `create_work_order_type` | R6a [BUG-1214] | WOTM-C-13 |
| `create_work_order_type` | Errors row 1 (409) | WOTM-C-02, WOTM-C-05, WOTM-C-06 |
| `create_work_order_type` | Errors row 2 (IntegrityError 23505) | WOTM-C-12, WOTM-C-13 |
| `create_work_order_type` | Errors row 3 (ValidationError) | WOTM-C-07, WOTM-C-08 |
| `create_work_order_type` | Side effects (flush, no commit) | WOTM-C-01, WOTM-C-14 |
| `create_work_order_type` | BUG-1707 / BUG-1708 / BUG-1214 | C-05 / C-06, C-07, C-08, C-10 / C-04, C-13 |
| `update_work_order_type` | R1 | WOTM-U-02 |
| `update_work_order_type` | R2 | WOTM-U-03 |
| `update_work_order_type` | R3 | WOTM-U-04, WOTM-U-05 |
| `update_work_order_type` | R4 | WOTM-U-01, WOTM-U-07, WOTM-U-09, WOTM-U-20, WOTM-U-23 |
| `update_work_order_type` | R5 | WOTM-U-13, WOTM-U-17 |
| `update_work_order_type` | R6 | WOTM-U-06, WOTM-U-07, WOTM-U-09, WOTM-U-10, WOTM-U-23 |
| `update_work_order_type` | R6a [BUG-1214] | WOTM-U-08 |
| `update_work_order_type` | R7 | WOTM-U-11, WOTM-U-12 |
| `update_work_order_type` | R8 | WOTM-U-17, WOTM-U-18, WOTM-U-19, WOTM-U-20 |
| `update_work_order_type` | R9 | WOTM-U-01, WOTM-U-14, WOTM-U-15, WOTM-U-16 |
| `update_work_order_type` | R10 | WOTM-U-01, WOTM-U-11, WOTM-U-12, WOTM-U-13 |
| `update_work_order_type` | R11 | WOTM-U-21; case variant via the shared constraint, WOTM-C-13 |
| `update_work_order_type` | Errors rows 1 / 2 / 3 / 4 / 5 | U-02, U-03 / U-04, U-05 / U-06, U-10 / U-21 / U-18, U-19 |
| `update_work_order_type` | Side effects (flush, no commit) | WOTM-U-01, WOTM-U-22 |
| `update_work_order_type` | BUG-1707 / BUG-1708 / BUG-1711 / BUG-1214 | U-10 / U-17, U-18, U-19 / U-14, U-15, U-16 / U-08 |
| `get_work_order_type` | R1 | WOTM-G-01 |
| `get_work_order_type` | R2 | WOTM-G-02, WOTM-G-03, WOTM-G-04, WOTM-G-05 |
| `get_work_order_type` | R3 [BUG-1521] | WOTM-G-06 |
| `get_work_order_type` | R4 [BUG-1521] | WOTM-G-07, WOTM-G-08 |
| `get_work_order_type` | Errors | WOTM-G-02, WOTM-G-03, WOTM-G-04, WOTM-G-05, WOTM-G-06, WOTM-G-08 |
| `get_work_order_type` | Side effects none | WOTM-G-09 |
| `search_work_order_types` | R1 | WOTM-S-01, WOTM-S-02 |
| `search_work_order_types` | R2 | WOTM-S-05, WOTM-S-06, WOTM-S-07, WOTM-S-08, WOTM-S-09, WOTM-S-11, WOTM-S-12, WOTM-S-23 |
| `search_work_order_types` | R3 [BUG-1710] | WOTM-S-20, WOTM-S-21 (non-strict), WOTM-S-22 (strict) |
| `search_work_order_types` | R4 | WOTM-S-03, WOTM-S-05, WOTM-S-06, WOTM-S-23 |
| `search_work_order_types` | R5 | WOTM-S-04; API reach Deferred (BUG-1520) |
| `search_work_order_types` | R6 | WOTM-S-07, WOTM-S-13, WOTM-S-14 |
| `search_work_order_types` | R6a (HR-8) | WOTM-S-15, WOTM-S-16 |
| `search_work_order_types` | R7 | WOTM-S-17 (`""`); `None` is the default in WOTM-S-01 … S-04 |
| `search_work_order_types` | R8 | WOTM-S-10, WOTM-S-18, WOTM-S-19 |
| `search_work_order_types` | BUG-1709 | WOTM-S-05, WOTM-S-06, WOTM-S-07 (non-strict), WOTM-S-23 (strict) |
| `search_work_order_types` | Side effects none | WOTM-S-24 |
| `delete_work_order_type` | R1 | WOTM-D-02, WOTM-D-03 |
| `delete_work_order_type` | R2 | WOTM-D-04 |
| `delete_work_order_type` | R3 | WOTM-D-01 |
| `delete_work_order_type` | R4 | WOTM-D-01; work orders / templates part Deferred |
| `delete_work_order_type` | Errors rows 1 / 2 | D-02, D-03 / D-04 |
| `delete_work_order_type` | Side effects (flush, no commit) | WOTM-D-01, WOTM-D-05 |
| `_check_name_exists` | R1 | WOTM-N-02, WOTM-N-05 |
| `_check_name_exists` | R2 | WOTM-N-03 |
| `_check_name_exists` | R3 | WOTM-N-04, WOTM-N-05 |
| `_check_name_exists` | R4 [BUG-1707] | WOTM-N-06, WOTM-N-07, WOTM-N-08; pass: WOTM-N-09, WOTM-N-10, WOTM-N-11 |
| `_check_name_exists` | R5 [BUG-1706] | WOTM-N-12; WOTM-N-13 (non-strict); WOTM-N-17 (strict) |
| `_check_name_exists` | R6 | WOTM-N-02, WOTM-N-14, WOTM-N-15, WOTM-N-16 |
| `_check_name_exists` | R7 | WOTM-N-01 |
