# Test cases — `app/managers/delivery_method_manager.py`

> **Spec:** `tests/unit/managers/delivery_method_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec unchanged; verifier findings 1 and 2 (`delivery_method_manager.verify.md`). Changed: DMM-S-06 now checks the page size and a subset of the live ids, not one chosen row of an unordered page. New: DMM-N-17, a strict statement recorder that is the order-free alarm for BUG-1700 (the capped name scan).
> **Counts:** 91 cases · 61 expected-to-pass · 30 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `create_delivery_method` 14 (7 bug) · `update_delivery_method` 22 (8 bug) · `get_delivery_method` 9 (3 bug) · `search_delivery_methods` 24 (7 bug) · `delete_delivery_method` 5 · `_check_name_exists` 17 (5 bug).
- **Depth:** lighter target (skill step 1a). Reference data, no stock, money or order state, same code as `department_manager`. One card per rule and Errors row, one negative per filter, both sides of each paging boundary, one commit spy per writer, one statement recorder for the unordered list query. The name-comparison matrix (case, outer space, a part of the name, `_`, stored side) lives on `_check_name_exists` only; the public writers repeat one case variant and one padded variant each.
- **Expected-to-fail by bug:** BUG-1701 5 · BUG-1702 7 · BUG-1219 3 · BUG-1705 3 · BUG-1523 3 · BUG-1703 4 · BUG-1704 3 · BUG-1700 2. Strict, except the six cards that rest on physical row order (DMM-S-05, S-06, S-07, S-20, S-21, N-13). Those are non-strict, as in `department_manager` revision 5.
- **Notable design choices:**
  - Strict alarms that do not depend on row order: DMM-S-22 (an `ORDER BY lower(name), id` is sent, BUG-1704) and DMM-S-23 (the soft-delete filter is in the query's WHERE, BUG-1703). DMM-N-17 (the name check sends no capped scan, BUG-1700) is the order-free alarm for DMM-N-13, which stays non-strict like department N-12.
  - Race simulations DMM-C-12, C-13, U-21 patch `_check_name_exists` → `False` (spec-sanctioned, BUG-1219). The intended index is not tested by direct inserts: the manager-level race cards already need it.
  - `_check_name_exists` and `search_delivery_methods` share one base-DAO query. The workspace filter is tested with the other workspace on both sides of the id only on the list (DMM-S-01, S-02) and on `get` (DMM-G-04, G-05).
  - No-op updates are split as in department: pass cards U-11, U-12, U-13 leave `updated_by` unasserted. The BUG-1705 xfails U-14, U-15 and U-16 assert only `updated_by`.
  - `delete_delivery_method` R4's "sales deliveries keep the method" has no card: the manager never reads them. The row stays, and DMM-D-01 checks that.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `DMM` = `app/managers/delivery_method_manager.py`. `C` create_delivery_method · `U` update_delivery_method · `G` get_delivery_method · `S` search_delivery_methods · `D` delete_delivery_method · `N` _check_name_exists.

**Actors and fixed values.**
- `M` = the singleton `delivery_method_manager` (`from app.managers.delivery_method_manager import DeliveryMethodManager, delivery_method_manager`). `db` = the test's real session, always the first argument, passed positionally; every other argument by keyword. `result` = what the When call returns.
- `DeliveryMethod` (`app.models.delivery_method`), `DeliveryMethodCreate`, `DeliveryMethodUpdate` (`app.schemas.delivery_method`), `HTTPException` (`fastapi`), `ValidationError` (`pydantic`), `patch` (`unittest.mock`), `re`.
- W1, W2 = two `workspaces` rows made in that order (`W1.id < W2.id`); U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. U1 is the acting user; U2 created every Given row.
- MISSING = `999999999`. T0 = `datetime(2026, 1, 1, 9, 0, 0)`, NOW = `datetime(2026, 1, 15, 10, 30, 0)` (both naive).

**Externals.** An autouse fixture of the test file patches `app.dao.delivery_method.utcnow` to return NOW in every test. A card never patches anything itself, except the race simulations below.

**Given rows.** Inserted directly (never through `M`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. No `delivery_methods` row exists unless the card lists it. A Given line written as code is run exactly as written.
- **method** = `DeliveryMethod(workspace_id=W1.id, name=<given>, created_by=U2.id)`; `is_active True`, `is_deleted False`; `updated_by`, `deleted_at`, `deleted_by` None. The card always gives `name`; after "but" it lists every other column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- Two live rows of one workspace never share a name ignoring case and outer spaces (forbidden once BUG-1219 is fixed); a gone row may share a live row's name.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, **names(result)** = `[r.name for r in result]`, in the order returned. `sorted(ids(result)) == [...]` when order is not checked (ids on the right in Given order).
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read, every column of X equals its value just before the call.
- **nothing written** = the number of `delivery_methods` rows (all workspaces) equals its value just before the call.
- `count:` lines count `delivery_methods` rows with a fresh query and the filter stated.
- `session:` lines check `db` itself, before any re-read.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint. `raises: ValidationError` = `with pytest.raises(ValidationError):` around building the schema. Further `raises:` lines assert on `exc.value` after the block, one per line.

**Targets.** "target `schema`" = the When only builds the schema object; `M` is not called.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict, `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, unless the Expect line says `(non-strict)`.

**Race simulations** (Author: claude only). `patch.object(DeliveryMethodManager, "_check_name_exists", return_value=False)` around the When. The call is wrapped `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call. Cards: DMM-C-12, C-13 (`create_delivery_method` R6), DMM-U-21 (`update_delivery_method` R11), all BUG-1219.

**Rolled back** (Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after rollback" checks. One card per writer.

**sql_log** (Author: claude only). A list filled by a `before_cursor_execute` listener on `db.connection()`, attached right before the When and removed after it. Each entry is the statement text.

## `DeliveryMethodManager.create_delivery_method`

### DMM-C-01 — a new method is stored with its name, workspace and creator
- **Rules:** `create_delivery_method` R1, R5, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, DeliveryMethod)`, `result.id is not None`.
2. returns: `result.name == "Courier"`.
3. re-read the row `result.id`: `name == "Courier"`, `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read the row `result.id`: `is_deleted is False`, `is_active is True`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`.
5. count: rows of W1: exactly 1.

### DMM-C-02 — a live method of the same name is refused with 409
- **Rules:** `create_delivery_method` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### DMM-C-03 — the same name in another workspace does not block
- **Rules:** `create_delivery_method` R3, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != Z.id`.
2. re-read the row `result.id`: `name == "Courier"`, `workspace_id == W1.id`.
3. count: rows of W1: exactly 1.
4. unchanged: unchanged(Z).

### DMM-C-04 — a soft-deleted method's name can be used again
- **Rules:** `create_delivery_method` R3, R6 (a deleted row does not count)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != D.id`.
2. re-read the row `result.id`: `name == "Courier"`, `is_deleted is False`.
3. re-read D: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2.id`.
4. count: rows of W1: exactly 2.

### DMM-C-05 — a live name in other case is refused, the detail shows the submitted name
- **Rules:** `create_delivery_method` R2, Errors row 1 [BUG-1701]
- **Kind:** bug
- **Expect:** xfail BUG-1701
- **Fails today on:** Then 1 (no exception is raised: "courier" is created)

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'courier' already exists"`.
4. count: rows of W1: exactly 1.

### DMM-C-06 — a padded live name is trimmed by the schema and refused
- **Rules:** `create_delivery_method` R2, R4 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (no exception is raised: " Courier " is created)

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name=" Courier "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. count: rows of W1: exactly 1.

### DMM-C-07 — an empty name is refused by the schema
- **Rules:** `create_delivery_method` R4, Errors row 2 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. W1 has no delivery methods.

**When**
- build `DeliveryMethodCreate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: rows of W1: exactly 0.

### DMM-C-08 — a whitespace-only name is refused by the schema
- **Rules:** `create_delivery_method` R4, Errors row 2 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. W1 has no delivery methods.

**When**
- build `DeliveryMethodCreate(name="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: rows of W1: exactly 0.

### DMM-C-09 — a one-character name is accepted
- **Rules:** `create_delivery_method` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="a"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "a"`.
2. re-read the row `result.id`: `name == "a"`.

### DMM-C-10 — outer spaces are trimmed before the name is stored
- **Rules:** `create_delivery_method` R4 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (the schema keeps " Own Fleet ")

**Given**
1. W1 has no delivery methods.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name=" Own Fleet "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Own Fleet"`.
2. re-read the row `result.id`: `name == "Own Fleet"`.

### DMM-C-11 — case and inner spaces are stored as typed
- **Rules:** `create_delivery_method` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="own  FLEET"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "own  FLEET"`.
2. re-read the row `result.id`: `name == "own  FLEET"`.

### DMM-C-12 — a duplicate past the Python check is refused by the database as 409
- **Rules:** `create_delivery_method` R6, Errors row 1 [BUG-1219]
- **Kind:** bug
- **Expect:** xfail BUG-1219
- **Author:** claude — race simulation
- **Fails today on:** Then 1 (no exception is raised: a second "Courier" is saved)

**Given**
1. A = method, `name "Courier"`.
2. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. count: rows of W1 with `name == "Courier"`: exactly 1.

### DMM-C-13 — the database also refuses a case variant past the Python check
- **Rules:** `create_delivery_method` R6, Errors row 1 [BUG-1219]
- **Kind:** bug
- **Expect:** xfail BUG-1219
- **Author:** claude — race simulation
- **Fails today on:** Then 1 (no exception is raised: "COURIER" is saved)

**Given**
1. A = method, `name "Courier"`.
2. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="COURIER"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'COURIER' already exists"`.
4. count: rows of W1: exactly 1.

### DMM-C-14 — create flushes and never commits
- **Rules:** `create_delivery_method` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. W1 has no delivery methods.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.create_delivery_method(db, delivery_method_data=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: rows of W1: exactly 1.
3. count after rollback: rows of W1: exactly 0.
4. mock called: the `db.commit` spy was never called.

## `DeliveryMethodManager.update_delivery_method`

### DMM-U-01 — a rename changes the name and stamps updated_by, nothing else
- **Rules:** `update_delivery_method` R4, R9, R10, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="Express Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Express Courier"`.
2. re-read A: `name == "Express Courier"`, `updated_by == U1.id`, `updated_at is not None`.
3. re-read A: `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.

### DMM-U-02 — an unknown id gets 404
- **Rules:** `update_delivery_method` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.update_delivery_method(db, delivery_method_id=MISSING, delivery_method_data=DeliveryMethodUpdate(name="Pickup"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### DMM-U-03 — another workspace's method gets 404 and is not touched
- **Rules:** `update_delivery_method` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `M.update_delivery_method(db, delivery_method_id=Z.id, delivery_method_data=DeliveryMethodUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### DMM-U-04 — a deleted method gets 400 before any name check
- **Rules:** `update_delivery_method` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, `name "Pickup"`.
2. D = method, `name "Courier"`, but gone.

**When**
- `M.update_delivery_method(db, delivery_method_id=D.id, delivery_method_data=DeliveryMethodUpdate(name="Pickup"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted delivery method"`.
4. unchanged: unchanged(D).
5. unchanged: unchanged(A).

### DMM-U-05 — a deleted method gets 400 also with an empty body
- **Rules:** `update_delivery_method` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone, `updated_by U2.id`.

**When**
- `M.update_delivery_method(db, delivery_method_id=D.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted delivery method"`.
4. re-read D: `name == "Courier"`, `updated_by == U2.id`, `is_deleted is True`.

### DMM-U-06 — a name another live method has is refused with 409
- **Rules:** `update_delivery_method` R6, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`, but `updated_by U2.id`.

**When**
- `M.update_delivery_method(db, delivery_method_id=B.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. unchanged: unchanged(B).
5. unchanged: unchanged(A).

### DMM-U-07 — a name used only in another workspace is free
- **Rules:** `update_delivery_method` R6, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.
2. B = method, `name "Pickup"`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=B.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Courier"`.
2. re-read B: `name == "Courier"`, `updated_by == U1.id`.
3. unchanged: unchanged(Z).

### DMM-U-08 — a name used only by a deleted method is free
- **Rules:** `update_delivery_method` R6, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone.
2. B = method, `name "Pickup"`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=B.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Courier"`.
2. re-read B: `name == "Courier"`, `updated_by == U1.id`.
3. unchanged: unchanged(D).

### DMM-U-09 — a method may change the case of its own name
- **Rules:** `update_delivery_method` R6 (this method excluded), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "courier"`.
2. re-read A: `name == "courier"`, `updated_by == U1.id`.

### DMM-U-10 — another live method's name in other case is refused with 409
- **Rules:** `update_delivery_method` R6, Errors row 3 [BUG-1701]
- **Kind:** bug
- **Expect:** xfail BUG-1701
- **Fails today on:** Then 1 (no exception is raised: A is renamed to "PICKUP")

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.

**When**
- `M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="PICKUP"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'PICKUP' already exists"`.
4. re-read A: `name == "Courier"`.

### DMM-U-11 — an empty body leaves the name and other fields alone
- **Rules:** `update_delivery_method` R7, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Courier"`.
2. re-read A: `name == "Courier"`, `workspace_id == W1.id`, `created_by == U2.id`.
3. re-read A: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
4. count: rows of W1: exactly 1.

### DMM-U-12 — an explicit null name leaves the name alone
- **Rules:** `update_delivery_method` R7, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Courier"`.
2. re-read A: `name == "Courier"`, `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`.

### DMM-U-13 — the current name is not a duplicate of itself
- **Rules:** `update_delivery_method` R5, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Courier"`.
2. re-read A: `name == "Courier"`, `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`.

### DMM-U-14 — an empty body does not stamp updated_by
- **Rules:** `update_delivery_method` R9 [BUG-1705]
- **Kind:** bug
- **Expect:** xfail BUG-1705
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### DMM-U-15 — an explicit null name does not stamp updated_by
- **Rules:** `update_delivery_method` R9 [BUG-1705]
- **Kind:** bug
- **Expect:** xfail BUG-1705
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### DMM-U-16 — the unchanged name does not stamp updated_by
- **Rules:** `update_delivery_method` R9 [BUG-1705]
- **Kind:** bug
- **Expect:** xfail BUG-1705
- **Fails today on:** Then 2 (`updated_by == U1.id`)

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `updated_by == U2.id`.

### DMM-U-17 — the current name with outer spaces is trimmed and counts as unchanged
- **Rules:** `update_delivery_method` R5, R8 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (`result.name == " Courier "`: the schema keeps the spaces)

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name=" Courier "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Courier"`.
2. re-read A: `name == "Courier"`.

### DMM-U-18 — an empty name is refused by the update schema
- **Rules:** `update_delivery_method` R8, Errors row 4 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. A = method, `name "Courier"`.

**When**
- build `DeliveryMethodUpdate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. re-read A: `name == "Courier"`.

### DMM-U-19 — a whitespace-only name is refused by the update schema
- **Rules:** `update_delivery_method` R8, Errors row 4 [BUG-1702]
- **Kind:** bug
- **Expect:** xfail BUG-1702
- **Fails today on:** Then 1 (no ValidationError is raised)

**Given**
1. A = method, `name "Courier"`.

**When**
- build `DeliveryMethodUpdate(name="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. re-read A: `name == "Courier"`.

### DMM-U-20 — a one-character new name is accepted
- **Rules:** `update_delivery_method` R8, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="a"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "a"`.
2. re-read A: `name == "a"`, `updated_by == U1.id`.

### DMM-U-21 — a rename onto a live duplicate past the Python check is refused by the database as 409
- **Rules:** `update_delivery_method` R11, Errors row 3 [BUG-1219]
- **Kind:** bug
- **Expect:** xfail BUG-1219
- **Author:** claude — race simulation
- **Fails today on:** Then 1 (no exception is raised: B is renamed to "Courier")

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`, but `updated_by U2.id`.
3. Race simulation: `_check_name_exists` patched to return `False` (Conventions).

**When**
- inside the race wrapper: `M.update_delivery_method(db, delivery_method_id=B.id, delivery_method_data=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. re-read B: `name == "Pickup"`, `updated_by == U2.id`.

### DMM-U-22 — update flushes and never commits
- **Rules:** `update_delivery_method` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.update_delivery_method(db, delivery_method_id=A.id, delivery_method_data=DeliveryMethodUpdate(name="Express"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Express"`.
2. re-read A: `name == "Express"`.
3. re-read A after rollback: `name == "Courier"`, `updated_by == U2.id`.
4. mock called: the `db.commit` spy was never called.

## `DeliveryMethodManager.get_delivery_method`

### DMM-G-01 — a live method is returned by its id
- **Rules:** `get_delivery_method` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L = method, `name "Air"`.
2. T = method, `name "Courier"`.
3. H = method, `name "Pickup"`.

**When**
- `result = M.get_delivery_method(db, delivery_method_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, DeliveryMethod)`.
2. returns: `result.id == T.id`, `result.name == "Courier"`, `result.workspace_id == W1.id`.

### DMM-G-02 — an unknown id gets 404
- **Rules:** `get_delivery_method` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.get_delivery_method(db, delivery_method_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 999999999 not found"`.

### DMM-G-03 — id 0 gets 404
- **Rules:** `get_delivery_method` R2, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.get_delivery_method(db, delivery_method_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 0 not found"`.

### DMM-G-04 — a method of a workspace with a higher id gets 404
- **Rules:** `get_delivery_method` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. Z = method, `name "Pickup"`, but `workspace_id W2.id`.

**When**
- `M.get_delivery_method(db, delivery_method_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.

### DMM-G-05 — a method of a workspace with a lower id gets 404
- **Rules:** `get_delivery_method` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. Z = method, `name "Pickup"`, but `workspace_id W2.id`.

**When**
- `M.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {A.id} not found"`.

### DMM-G-06 — a soft-deleted method is hidden by default
- **Rules:** `get_delivery_method` R3, Errors [BUG-1523]
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (no exception is raised: the deleted method is returned)

**Given**
1. D = method, `name "Courier"`, but gone.

**When**
- `M.get_delivery_method(db, delivery_method_id=D.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {D.id} not found"`.

### DMM-G-07 — include_deleted=True returns a soft-deleted method
- **Rules:** `get_delivery_method` R4 [BUG-1523]
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. D = method, `name "Courier"`, but gone.

**When**
- `result = M.get_delivery_method(db, delivery_method_id=D.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == D.id`.
2. returns: `result.is_deleted is True`.

### DMM-G-08 — include_deleted=True does not reach another workspace
- **Rules:** `get_delivery_method` R4, Errors [BUG-1523]
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`, gone.

**When**
- `M.get_delivery_method(db, delivery_method_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.

### DMM-G-09 — the read writes nothing and keeps the caller's unflushed edits
- **Rules:** `get_delivery_method` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.
3. `B.name = "Edited"` (not flushed).
4. `P = DeliveryMethod(workspace_id=W1.id, name="Pending", created_by=U2.id)`; `db.add(P)` (not flushed).

**When**
- `result = M.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `P in db.new`.
5. session: `len(db.new) == 1`.
6. session: `not db.deleted`.

## `DeliveryMethodManager.search_delivery_methods`

### DMM-S-01 — only the workspace's methods are listed (other workspace has the higher id)
- **Rules:** `search_delivery_methods` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.
3. Z = method, `name "Own Fleet"`, but `workspace_id W2.id`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### DMM-S-02 — only the workspace's methods are listed (other workspace has the lower id)
- **Rules:** `search_delivery_methods` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. Z = method, `name "Own Fleet"`, but `workspace_id W2.id`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### DMM-S-03 — soft-deleted methods are left out by default
- **Rules:** `search_delivery_methods` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. D = method, `name "Pickup"`, but gone.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### DMM-S-04 — include_deleted=True keeps soft-deleted methods
- **Rules:** `search_delivery_methods` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. D = method, `name "Pickup"`, but gone.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, D.id]`.

### DMM-S-05 — deleted methods take no place in the page (limit)
- **Rules:** `search_delivery_methods` R2, R4 [BUG-1703]
- **Kind:** bug
- **Expect:** xfail BUG-1703 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `[]`: the page holds the deleted rows)

**Given**
1. D1 = method, `name "Air 1"`, but gone.
2. D2 = method, `name "Air 2"`, but gone.
3. D3 = method, `name "Air 3"`, but gone.
4. A = method, `name "Courier"`.
5. B = method, `name "Pickup"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### DMM-S-06 — deleted methods are not counted by skip
- **Rules:** `search_delivery_methods` R2, R4 [BUG-1703]
- **Kind:** bug
- **Expect:** xfail BUG-1703 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `len(result) == 2`: skip counted a deleted row, both live rows come back)

**Given**
1. D1 = method, `name "Air 1"`, but gone.
2. D2 = method, `name "Air 2"`, but gone.
3. D3 = method, `name "Air 3"`, but gone.
4. A = method, `name "Courier"`.
5. B = method, `name "Pickup"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### DMM-S-07 — the search looks past the first page
- **Rules:** `search_delivery_methods` R2, R6 [BUG-1703]
- **Kind:** bug
- **Expect:** xfail BUG-1703 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `[]`: only the first two rows are searched)

**Given**
1. A = method, `name "Air 1"`.
2. B = method, `name "Bike"`.
3. C = method, `name "Car"`.
4. X = method, `name "Courier"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="our", limit=2)`.

**Then**
1. returns: `ids(result) == [X.id]`.

### DMM-S-08 — a page is full when skip + limit equals the matches
- **Rules:** `search_delivery_methods` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: method, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, skip=2, limit=3)`.

**Then**
1. returns: `len(result) == 3`.

### DMM-S-09 — a page is short when skip + limit passes the matches
- **Rules:** `search_delivery_methods` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: method, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, skip=3, limit=3)`.

**Then**
1. returns: `len(result) == 2`.

### DMM-S-10 — skip at the number of matches gives an empty list
- **Rules:** `search_delivery_methods` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: method, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### DMM-S-11 — the default limit is 100
- **Rules:** `search_delivery_methods` R2 (default `limit`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, method, `name f"Method {k:03d}"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### DMM-S-12 — limit=1000 lists past 100
- **Rules:** `search_delivery_methods` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, method, `name f"Method {k:03d}"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### DMM-S-13 — search matches a part of the name, ignoring case on both sides
- **Rules:** `search_delivery_methods` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "SKYCOURIER"`.
3. C = method, `name "Pickup"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="Our")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### DMM-S-14 — a leading space in the search counts
- **Rules:** `search_delivery_methods` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier Express"`.
2. B = method, `name "Expedite"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search=" exp")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### DMM-S-15 — `%` in the search matches only itself
- **Rules:** `search_delivery_methods` R6a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Fast 100%"`.
2. B = method, `name "Pickup"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### DMM-S-16 — `_` in the search matches only itself
- **Rules:** `search_delivery_methods` R6a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Own_Fleet"`.
2. B = method, `name "OwnXFleet"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="n_f")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### DMM-S-17 — an empty search is no filter
- **Rules:** `search_delivery_methods` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### DMM-S-18 — a workspace with no methods gives an empty list
- **Rules:** `search_delivery_methods` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### DMM-S-19 — a search with no match gives an empty list
- **Rules:** `search_delivery_methods` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, search="xyz")`.

**Then**
1. returns: `result == []`.

### DMM-S-20 — the list is sorted by name ignoring case, ties by id
- **Rules:** `search_delivery_methods` R3 [BUG-1704]
- **Kind:** bug
- **Expect:** xfail BUG-1704 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually insertion order: P first)

**Given**
1. P = method, `name "Pickup"`.
2. C = method, `name "Courier"`.
3. C2 = method, `name "courier"`, but gone.
4. C3 = method, `name "COURIER"`, but gone.
5. F = method, `name "Air Freight"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [F.id, C.id, C2.id, C3.id, P.id]`.

### DMM-S-21 — the sort is applied before paging
- **Rules:** `search_delivery_methods` R3 [BUG-1704]
- **Kind:** bug
- **Expect:** xfail BUG-1704 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually `["Charlie", "bravo"]`: insertion order)

**Given**
1. 5 rows, in this order: method, `name` `"Echo"`, `"delta"`, `"Charlie"`, `"bravo"`, `"Alpha"`.

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `names(result) == ["Charlie", "delta"]`.

### DMM-S-22 — the list query orders by lower(name), then id
- **Rules:** `search_delivery_methods` R3 [BUG-1704]
- **Kind:** bug
- **Expect:** xfail BUG-1704
- **Author:** claude — statement recorder
- **Fails today on:** Then 2 (no such `ORDER BY` is sent)

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.
3. **sql_log** attached (Conventions).

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. statement: `any(re.search(r"FROM delivery_methods\b.*ORDER BY\s+lower\([^)]*name\)[^,]*,\s*\S*\bid\b", s, re.DOTALL | re.IGNORECASE) for s in sql_log)`.

### DMM-S-23 — the list query filters soft-deleted rows in SQL
- **Rules:** `search_delivery_methods` R2, R4 [BUG-1703]
- **Kind:** bug
- **Expect:** xfail BUG-1703
- **Author:** claude — statement recorder
- **Fails today on:** Then 2 (the WHERE clause has only the workspace filter)

**Given**
1. A = method, `name "Courier"`.
2. D = method, `name "Pickup"`, but gone.
3. **sql_log** attached (Conventions).

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `any(re.search(r"FROM delivery_methods\b.*\bWHERE\b.*\bis_deleted\b", s, re.DOTALL | re.IGNORECASE) for s in sql_log)`.

### DMM-S-24 — the list writes nothing and keeps the caller's unflushed edits
- **Rules:** `search_delivery_methods` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.
3. `B.name = "Edited"` (not flushed).
4. `P = DeliveryMethod(workspace_id=W1.id, name="Pending", created_by=U2.id)`; `db.add(P)` (not flushed).

**When**
- `result = M.search_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `P in db.new`.
5. session: `len(db.new) == 1`.
6. session: `not db.deleted`.

## `DeliveryMethodManager.delete_delivery_method`

### DMM-D-01 — a live method is soft-deleted and kept
- **Rules:** `delete_delivery_method` R3, R4, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`, but `updated_by U2.id`.

**When**
- `result = M.delete_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.is_deleted is True`.
2. re-read A: `is_deleted is True`, `deleted_at == NOW`, `deleted_at.tzinfo is None`, `deleted_by == U1.id`.
3. re-read A: `name == "Courier"`, `is_active is True`, `updated_by == U2.id`, `created_by == U2.id`, `workspace_id == W1.id`.
4. count: rows of W1: exactly 1.

### DMM-D-02 — an unknown id gets 404
- **Rules:** `delete_delivery_method` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `M.delete_delivery_method(db, delivery_method_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### DMM-D-03 — another workspace's method gets 404 and is not deleted
- **Rules:** `delete_delivery_method` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `M.delete_delivery_method(db, delivery_method_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.
4. re-read Z: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.

### DMM-D-04 — an already deleted method gets 400, its stamps stay
- **Rules:** `delete_delivery_method` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone.

**When**
- `M.delete_delivery_method(db, delivery_method_id=D.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Delivery method is already deleted"`.
4. re-read D: `is_deleted is True`, `deleted_at == T0`, `deleted_by == U2.id`.

### DMM-D-05 — delete flushes and never commits
- **Rules:** `delete_delivery_method` Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A = method, `name "Courier"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.is_deleted is True`.
2. re-read A: `is_deleted is True`.
3. re-read A after rollback: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
4. mock called: the `db.commit` spy was never called.

## `DeliveryMethodManager._check_name_exists`

### DMM-N-01 — a workspace with no methods has no name
- **Rules:** `_check_name_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier")`.

**Then**
1. returns: `result is False`.

### DMM-N-02 — a live method of the name is found
- **Rules:** `_check_name_exists` R1, R6 (`exclude_id=None`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier", exclude_id=None)`.

**Then**
1. returns: `result is True`.

### DMM-N-03 — the name in another workspace is not considered
- **Rules:** `_check_name_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method, `name "Pickup"`.
2. Z = method, `name "Courier"`, but `workspace_id W2.id`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier")`.

**Then**
1. returns: `result is False`.

### DMM-N-04 — a soft-deleted method of the name is ignored
- **Rules:** `_check_name_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier")`.

**Then**
1. returns: `result is False`.

### DMM-N-05 — a live match is found behind a deleted one
- **Rules:** `_check_name_exists` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = method, `name "Courier"`, but gone.
2. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier")`.

**Then**
1. returns: `result is True`.

### DMM-N-06 — the name matches in capitals
- **Rules:** `_check_name_exists` R4 [BUG-1701]
- **Kind:** bug
- **Expect:** xfail BUG-1701
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="COURIER")`.

**Then**
1. returns: `result is True`.

### DMM-N-07 — the name matches with a leading space
- **Rules:** `_check_name_exists` R4 [BUG-1701]
- **Kind:** bug
- **Expect:** xfail BUG-1701
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name=" Courier")`.

**Then**
1. returns: `result is True`.

### DMM-N-08 — a stored name with outer spaces matches in other case
- **Rules:** `_check_name_exists` R4 [BUG-1701]
- **Kind:** bug
- **Expect:** xfail BUG-1701
- **Fails today on:** Then 1 (returns False: exact compare)

**Given**
1. A = method, `name " Courier "`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="courier")`.

**Then**
1. returns: `result is True`.

### DMM-N-09 — a longer name containing the stored one does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier Express")`.

**Then**
1. returns: `result is False`.

### DMM-N-10 — a part of the stored name does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="ourie")`.

**Then**
1. returns: `result is False`.

### DMM-N-11 — `_` in the name is not a wildcard
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Cour_er")`.

**Then**
1. returns: `result is False`.

### DMM-N-12 — a match on the 100th row is found
- **Rules:** `_check_name_exists` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 30 rows, by `add_all`: k = 1 … 30, method, `name f"Archived {k:02d}"`, but gone.
2. 69 rows, by `add_all`: k = 1 … 69, method, `name f"Team {k:02d}"`.
3. L = method, `name "Logistics"` (the 100th row).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Logistics")`.

**Then**
1. returns: `result is True`.

### DMM-N-13 — a match beyond the 100th row is found
- **Rules:** `_check_name_exists` R5 [BUG-1700]
- **Kind:** bug
- **Expect:** xfail BUG-1700 (non-strict)
- **Author:** claude — non-strict xfail
- **Fails today on:** Then 1 (usually returns False: only 100 rows are read)

**Given**
1. 30 rows, by `add_all`: k = 1 … 30, method, `name f"Archived {k:02d}"`, but gone.
2. 70 rows, by `add_all`: k = 1 … 70, method, `name f"Team {k:02d}"`.
3. L = method, `name "Logistics"` (the 101st row).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Logistics")`.

**Then**
1. returns: `result is True`.

### DMM-N-14 — the excluded method's own name is ignored
- **Rules:** `_check_name_exists` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier", exclude_id=A.id)`.

**Then**
1. returns: `result is False`.

### DMM-N-15 — excluding a method with a higher id still finds the match
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method, `name "Courier"`.
2. B = method, `name "Pickup"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier", exclude_id=B.id)`.

**Then**
1. returns: `result is True`.

### DMM-N-16 — excluding a method with a lower id still finds the match
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = method, `name "Pickup"`.
2. A = method, `name "Courier"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier", exclude_id=B.id)`.

**Then**
1. returns: `result is True`.

### DMM-N-17 — the name check sends no capped scan of the workspace
- **Rules:** `_check_name_exists` R5 [BUG-1700]
- **Kind:** bug
- **Expect:** xfail BUG-1700
- **Author:** claude — statement recorder
- **Fails today on:** Then 3 (the check reads the workspace's rows with `LIMIT` and no `name` in the WHERE)

**Given**
1. A = method, `name "Courier"`.
2. **sql_log** attached (Conventions).

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Courier")`.

**Then**
1. returns: `result is True`.
2. statement: `any(re.search(r"FROM delivery_methods", s, re.IGNORECASE) for s in sql_log)`.
3. statement: `not any(re.search(r"LIMIT", s, re.IGNORECASE) and not re.search(r"WHERE.*name", s, re.DOTALL | re.IGNORECASE) for s in sql_log if re.search(r"FROM delivery_methods", s, re.IGNORECASE))`. (Spec R5 asks only that every live row be examined: a read with no `LIMIT`, or one that compares `name` in its WHERE — an `EXISTS` or `LIMIT 1` on the name — both pass.)

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `search_delivery_methods` R5 reach [BUG-1522] | `DeliveryMethodService.get_delivery_methods` + `GET /delivery-methods/` | The list passes `include_deleted` to the manager; with it true deleted methods are listed. |
| `create_delivery_method` R4, `update_delivery_method` R8 [BUG-1702] (422 at the API) | `POST /delivery-methods/`, `PUT /delivery-methods/{id}` | A blank name returns 422 and changes nothing; a padded name is stored trimmed. |
| HR-7 bounds (`skip >= 0`, `1 <= limit <= 1000`) | `GET /delivery-methods/` | `limit=0`, `limit=1001`, `skip=-1` → 422. |
| BUG-730 (a deleted or foreign method chosen on a sales delivery) | sales delivery manager | Not reached here. |
| `delete_delivery_method` R4 "deliveries keep the method" | service spec `delete_delivery_method` R1 / sales delivery manager | The manager never reads deliveries; DMM-D-01 checks only that the row stays. |

## Spec gaps
None.

## Retired IDs
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_delivery_method` | R1 | DMM-C-01, DMM-C-03 |
| `create_delivery_method` | R2 | DMM-C-02, DMM-C-05, DMM-C-06 |
| `create_delivery_method` | R3 | DMM-C-03, DMM-C-04 |
| `create_delivery_method` | R4 | DMM-C-06, DMM-C-07, DMM-C-08, DMM-C-09, DMM-C-10, DMM-C-11 |
| `create_delivery_method` | R5 | DMM-C-01 |
| `create_delivery_method` | R6 | DMM-C-12, DMM-C-13; deleted row does not count: DMM-C-04 |
| `create_delivery_method` | Errors row 1 (409) | DMM-C-02, DMM-C-05, DMM-C-06, DMM-C-12, DMM-C-13 |
| `create_delivery_method` | Errors row 2 (ValidationError) | DMM-C-07, DMM-C-08 |
| `create_delivery_method` | Side effects (flush, no commit) | DMM-C-01, DMM-C-14 |
| `create_delivery_method` | BUG-1701 / BUG-1702 / BUG-1219 | C-05 / C-06, C-07, C-08, C-10 / C-12, C-13 |
| `update_delivery_method` | R1 | DMM-U-02 |
| `update_delivery_method` | R2 | DMM-U-03 |
| `update_delivery_method` | R3 | DMM-U-04, DMM-U-05 |
| `update_delivery_method` | R4 | DMM-U-01, DMM-U-07, DMM-U-08, DMM-U-09, DMM-U-20 |
| `update_delivery_method` | R5 | DMM-U-13, DMM-U-17 |
| `update_delivery_method` | R6 | DMM-U-06, DMM-U-07, DMM-U-08, DMM-U-09, DMM-U-10 |
| `update_delivery_method` | R7 | DMM-U-11, DMM-U-12 |
| `update_delivery_method` | R8 | DMM-U-17, DMM-U-18, DMM-U-19, DMM-U-20 |
| `update_delivery_method` | R9 | DMM-U-01, DMM-U-14, DMM-U-15, DMM-U-16 |
| `update_delivery_method` | R10 | DMM-U-01, DMM-U-11, DMM-U-12, DMM-U-13 |
| `update_delivery_method` | R11 | DMM-U-21 |
| `update_delivery_method` | Errors rows 1 / 2 / 3 / 4 | U-02, U-03 / U-04, U-05 / U-06, U-10, U-21 / U-18, U-19 |
| `update_delivery_method` | Side effects (flush, no commit) | DMM-U-01, DMM-U-22 |
| `update_delivery_method` | BUG-1701 / BUG-1702 / BUG-1705 / BUG-1219 | U-10 / U-17, U-18, U-19 / U-14, U-15, U-16 / U-21 |
| `get_delivery_method` | R1 | DMM-G-01 |
| `get_delivery_method` | R2 | DMM-G-02, DMM-G-03, DMM-G-04, DMM-G-05 |
| `get_delivery_method` | R3 [BUG-1523] | DMM-G-06 |
| `get_delivery_method` | R4 [BUG-1523] | DMM-G-07, DMM-G-08 |
| `get_delivery_method` | Errors | DMM-G-02, DMM-G-03, DMM-G-04, DMM-G-05, DMM-G-06, DMM-G-08 |
| `get_delivery_method` | Side effects none | DMM-G-09 |
| `search_delivery_methods` | R1 | DMM-S-01, DMM-S-02 |
| `search_delivery_methods` | R2 | DMM-S-05, DMM-S-06, DMM-S-07, DMM-S-08, DMM-S-09, DMM-S-11, DMM-S-12, DMM-S-23 |
| `search_delivery_methods` | R3 [BUG-1704] | DMM-S-20, DMM-S-21 (non-strict), DMM-S-22 (strict) |
| `search_delivery_methods` | R4 | DMM-S-03, DMM-S-05, DMM-S-06, DMM-S-23 |
| `search_delivery_methods` | R5 | DMM-S-04; API reach Deferred (BUG-1522) |
| `search_delivery_methods` | R6 | DMM-S-07, DMM-S-13, DMM-S-14 |
| `search_delivery_methods` | R6a (HR-8) | DMM-S-15, DMM-S-16 |
| `search_delivery_methods` | R7 | DMM-S-17 (`""`); `None` is the default in DMM-S-01 … S-04 |
| `search_delivery_methods` | R8 | DMM-S-10, DMM-S-18, DMM-S-19 |
| `search_delivery_methods` | BUG-1703 | DMM-S-05, DMM-S-06, DMM-S-07 (non-strict), DMM-S-23 (strict) |
| `search_delivery_methods` | Side effects none | DMM-S-24 |
| `delete_delivery_method` | R1 | DMM-D-02, DMM-D-03 |
| `delete_delivery_method` | R2 | DMM-D-04 |
| `delete_delivery_method` | R3 | DMM-D-01 |
| `delete_delivery_method` | R4 | DMM-D-01; deliveries part Deferred |
| `delete_delivery_method` | Errors rows 1 / 2 | D-02, D-03 / D-04 |
| `delete_delivery_method` | Side effects (flush, no commit) | DMM-D-01, DMM-D-05 |
| `_check_name_exists` | R1 | DMM-N-02, DMM-N-05 |
| `_check_name_exists` | R2 | DMM-N-03 |
| `_check_name_exists` | R3 | DMM-N-04, DMM-N-05 |
| `_check_name_exists` | R4 [BUG-1701] | DMM-N-06, DMM-N-07, DMM-N-08; pass: DMM-N-09, DMM-N-10, DMM-N-11 |
| `_check_name_exists` | R5 [BUG-1700] | DMM-N-12; DMM-N-13 (non-strict); DMM-N-17 (strict) |
| `_check_name_exists` | R6 | DMM-N-02, DMM-N-14, DMM-N-15, DMM-N-16 |
| `_check_name_exists` | R7 | DMM-N-01 |
