# Test cases — `app/services/work_order_type_service.py`

> **Spec:** `tests/unit/services/work_order_type_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — spec Gap log G1 (schemas named) and G2 (the manager's search described). New: WSV-L-08 (a case-insensitive substring reaches the manager). Changed: Conventions and Reviewer summary lines only (the schema note). No other card changed, none retired.
> **Counts:** 28 cases · 23 expected-to-pass · 5 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `create_work_order_type` 6 (1 bug) · `get_work_order_type` 7 (3 bug) · `get_work_order_types` 8 (1 bug) · `update_work_order_type` 4 · `delete_work_order_type` 3.
- **Depth:** lighter target (skill step 1a): a transaction wrapper over reference data, the same code as `department_service`. TC2, TC4, TC5 once (on create), TC1 and TC3 once per write, TC6 once per read, each refusal status once or more.
- **Expected-to-fail:** BUG-1521 3 (G-04 … G-06), BUG-1520 1 (L-06), pass-through BUG-1214 1 (C-05). All strict.
- **Notable design choices:**
  - Same commit point and uncommitted-extra-row device as `department_service.cases.md`.
  - The manager has no spec: cards assert only the refusal values the spec lists as pass-through. List cards use the search the spec's Facts describe (case-insensitive substring, applied after the page is cut), on rows that all fit in one page; counts, not orders.
  - BUG-1214's today-shape (`IntegrityError` on a deleted type's name) gets no pass card: that is the buggy path. The database-error row is reached instead through an unknown `user_id` (`created_by` FK, as `departments`).
  - Input schemas `WorkOrderTypeCreate(name=…)`, `WorkOrderTypeUpdate(name=…)` from `app.schemas.work_order_type` (spec Facts, G1).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `WSV` = `app/services/work_order_type_service.py`. `C` create_work_order_type · `G` get_work_order_type · `L` get_work_order_types · `U` update_work_order_type · `D` delete_work_order_type.

**Actors and fixed values.**
- `svc` = the singleton `work_order_type_service` (`from app.services.work_order_type_service import WorkOrderTypeService, work_order_type_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `WorkOrderType` (`app.models.work_order_type`), `WorkOrderTypeCreate`, `WorkOrderTypeUpdate` (`app.schemas.work_order_type`), `HTTPException` (`fastapi`), `IntegrityError` (`sqlalchemy.exc`), `inspect`, `text` (`sqlalchemy`), `patch` (`unittest.mock`).
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. U1 is the acting user; U2 created the Given rows.
- MISSING = `999999999`. T0 = `datetime(2020, 1, 2, 3, 4, 5)` (naive).

**Externals.** None is mocked. `deleted_at` is the DAO's clock, checked as not None.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **type** = `WorkOrderType(workspace_id=W1.id, name="Repair", created_by=U2.id)`; `is_active`, `is_deleted` left to `True`, `False`; `updated_by`, `deleted_at`, `deleted_by` NULL. After "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- Two rows of one workspace never share a name, deleted or not (`uq_wo_type_workspace_name` covers all rows today).
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `work_order_types` rows (all workspaces) equals its value at the commit point.
- `count:` lines count `work_order_types` rows with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException`, `raises: IntegrityError`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. All strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Race simulations.** None in this module.

## `WorkOrderTypeService.create_work_order_type`

### WSV-C-01 — a new type is committed and returned re-read
- **Rules:** `create_work_order_type` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `result = svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `name`, `workspace_id`, `created_by`.
2. returns: `isinstance(result, WorkOrderType)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.name == "Repair"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`.
5. committed: the row with `id == result.id` exists: `name == "Repair"`, `workspace_id == W1.id`, `created_by == U1.id`, `is_deleted is False`.
6. committed: W1 has exactly 1 `work_order_types` row.

### WSV-C-02 — a live duplicate: the manager's 409 passes unchanged and the session is rolled back
- **Rules:** `create_work_order_type` R2, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type.
2. X = type, but `name "Extra"` (after the commit point).

**When**
- `svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'Repair' already exists"`.
4. count: `work_order_types` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

### WSV-C-03 — a failing commit is rolled back and re-raised
- **Rules:** `create_work_order_type` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_order_types` rows of W1: exactly 0.

### WSV-C-04 — a failing re-read after the commit leaves the type saved
- **Rules:** `create_work_order_type` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work order types.

**When**
- `svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `work_order_types` row.
3. committed: that row has `name == "Repair"`, `created_by == U1.id`.

### WSV-C-05 — pass-through BUG-1214: a deleted type's name can be used again
- **Rules:** `create_work_order_type` R3 [BUG-1214]
- **Kind:** bug
- **Expect:** xfail BUG-1214
- **Fails today on:** Then 1 (the call raises IntegrityError on `uq_wo_type_workspace_name`)

**Given**
1. A = type, gone.

**When**
- `result = svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != A.id`.
2. returns: `result.name == "Repair"`, `result.is_deleted is False`.
3. committed: `work_order_types` rows of W1 with `name == "Repair"`: exactly 2.
4. committed: re-read A: `is_deleted is True`.

### WSV-C-06 — a database error at the flush passes unchanged and nothing is saved
- **Rules:** `create_work_order_type` Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type, but `name "Inspection"`.

**When**
- `svc.create_work_order_type(db, type_in=WorkOrderTypeCreate(name="Repair"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `work_order_types` rows with `name == "Repair"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

## `WorkOrderTypeService.get_work_order_type`

### WSV-G-01 — a live type of the workspace is returned
- **Rules:** `get_work_order_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = type, but `workspace_id W2.id`, `name "Far"`.
2. A = type.

**When**
- `result = svc.get_work_order_type(db, type_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderType)`.
2. returns: `result.id == A.id`, `result.name == "Repair"`.

### WSV-G-02 — another workspace's id: the 404 passes unchanged
- **Rules:** `get_work_order_type` R4, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type.
2. Z = type, but `workspace_id W2.id`, `name "Far"`.

**When**
- `svc.get_work_order_type(db, type_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.

### WSV-G-03 — id 0 gets the 404
- **Rules:** `get_work_order_type` R4, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type.

**When**
- `svc.get_work_order_type(db, type_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 0 not found"`.

### WSV-G-04 — a soft-deleted type is hidden by default
- **Rules:** `get_work_order_type` R2 [BUG-1521], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (no error is raised: the deleted type is returned)

**Given**
1. A = type, gone.

**When**
- `svc.get_work_order_type(db, type_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {A.id} not found"`.

### WSV-G-05 — include_deleted=True returns a soft-deleted type
- **Rules:** `get_work_order_type` R3 [BUG-1521]
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = type, gone.

**When**
- `result = svc.get_work_order_type(db, type_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### WSV-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_work_order_type` R3 [BUG-1521], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1521
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. Z = type, but `workspace_id W2.id`, `name "Far"`, gone.

**When**
- `svc.get_work_order_type(db, type_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.

### WSV-G-07 — the read neither commits nor rolls back
- **Rules:** `get_work_order_type` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = type.
2. B = type, but `name "Inspection"`.
3. P = type, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_work_order_type(db, type_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `work_order_types` rows with `name == "Pending"`: exactly 1.
5. committed: `work_order_types` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `name == "Inspection"`.

## `WorkOrderTypeService.get_work_order_types`

### WSV-L-01 — the search reaches the manager and only the workspace's match comes back
- **Rules:** `get_work_order_types` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type.
2. B = type, but `name "Inspection"`.
3. Z = type, but `workspace_id W2.id`.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id, search="Repair")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `[r.id for r in result] == [A.id]`.

### WSV-L-02 — with the defaults 101 live types give 100
- **Rules:** `get_work_order_types` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, type, but `name f"Kind {k:03d}"`.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### WSV-L-03 — limit reaches the manager
- **Rules:** `get_work_order_types` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: type, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### WSV-L-04 — skip reaches the manager, limit=1000 takes the rest
- **Rules:** `get_work_order_types` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: type, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### WSV-L-05 — by default a soft-deleted type is left out
- **Rules:** `get_work_order_types` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type.
2. D = type, but `name "Old Kind"`, gone.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### WSV-L-06 — include_deleted=True lists soft-deleted types too
- **Rules:** `get_work_order_types` R2 [BUG-1520]
- **Kind:** bug
- **Expect:** xfail BUG-1520
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = type.
2. D = type, but `name "Old Kind"`, gone.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(r.id for r in result) == [A.id, D.id]`.

### WSV-L-07 — the list neither commits nor rolls back
- **Rules:** `get_work_order_types` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = type.
2. B = type, but `workspace_id W2.id`, `name "Inspection"`.
3. P = type, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `work_order_types` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `name == "Inspection"`.

### WSV-L-08 — a case-insensitive part of the name reaches the manager as the search
- **Rules:** `get_work_order_types` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = type.
2. B = type, but `name "Inspection"`.

**When**
- `result = svc.get_work_order_types(db, workspace_id=W1.id, search="PAIR")`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

## `WorkOrderTypeService.update_work_order_type`

### WSV-U-01 — a rename is committed and returned re-read with updated_at
- **Rules:** `update_work_order_type` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type.

**When**
- `result = svc.update_work_order_type(db, type_id=A.id, type_in=WorkOrderTypeUpdate(name="Overhaul"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Overhaul"`, `result.updated_by == U1.id`, `result.updated_at is not None`.
4. committed: re-read A: `name == "Overhaul"`, `updated_by == U1.id`, `updated_at is not None`.

### WSV-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_work_order_type` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = type.
2. Z = type, but `workspace_id W2.id`, `name "Far"`.
3. X = type, but `name "Extra"` (after the commit point).

**When**
- `svc.update_work_order_type(db, type_id=Z.id, type_in=WorkOrderTypeUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {Z.id} not found"`.
4. count: `work_order_types` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.

### WSV-U-03 — a deleted type: the 400 passes unchanged, nothing saved
- **Rules:** `update_work_order_type` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type, gone.

**When**
- `svc.update_work_order_type(db, type_id=A.id, type_in=WorkOrderTypeUpdate(name="Revived"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted work order type"`.
4. unchanged: unchanged(A).

### WSV-U-04 — a name taken: the 409 passes unchanged, nothing saved
- **Rules:** `update_work_order_type` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type.
2. B = type, but `name "Inspection"`.

**When**
- `svc.update_work_order_type(db, type_id=B.id, type_in=WorkOrderTypeUpdate(name="Repair"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Work order type 'Repair' already exists"`.
4. unchanged: unchanged(B).

## `WorkOrderTypeService.delete_work_order_type`

### WSV-D-01 — a soft delete is committed and returned re-read
- **Rules:** `delete_work_order_type` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = type.

**When**
- `result = svc.delete_work_order_type(db, type_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U1.id`, `result.deleted_at is not None`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`, `deleted_at is not None`.

### WSV-D-02 — an already deleted type: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_work_order_type` R2, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = type, gone.
2. X = type, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_work_order_type(db, type_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order type is already deleted"`.
4. count: `work_order_types` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### WSV-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_work_order_type` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = type.

**When**
- `svc.delete_work_order_type(db, type_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.
4. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| The manager's own rules (search, paging, order, names, stamps); FU-1 (b) `include_deleted` before paging (HR-5) | `WorkOrderTypeManager` (no spec yet) | Its own cases. L-01 … L-04 here pass through only. |
| BUG-1521 manager half (`get_work_order_type` gains `include_deleted`) | `WorkOrderTypeManager`, FU-1 (a) | The manager's 404 by default and with the flag. |
| BUG-1520, BUG-1521 — the `include_deleted` query parameters | `GET /work-order-types/`, `GET /work-order-types/{id}/` | Integration-only. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /work-order-types/` | Endpoint bounds. |
| BUG-1214's 409 "This resource already exists" today | global `IntegrityError` handler | Integration-only. |
| BUG-1228 — a deleted type chosen on work orders | work order managers | Not reached here. |
| Schema validation (400 today, BUG-461) | `POST`, `PUT /work-order-types/` | Integration-only. |

## Spec gaps
None. Revision 0's gaps 1 and 2 are closed by spec Gap log G1, G2.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_work_order_type` | R1 | WSV-C-01 |
| `create_work_order_type` | R2 | WSV-C-02 |
| `create_work_order_type` | R3 [BUG-1214] | WSV-C-05 |
| `create_work_order_type` | R4 | WSV-C-03, WSV-C-04 |
| `create_work_order_type` | Errors | WSV-C-02, WSV-C-06 |
| `create_work_order_type` | Returns | WSV-C-01 |
| `get_work_order_type` | R1 | WSV-G-01 |
| `get_work_order_type` | R2 [BUG-1521] | WSV-G-04 |
| `get_work_order_type` | R3 [BUG-1521] | WSV-G-05, WSV-G-06 |
| `get_work_order_type` | R4 | WSV-G-02, WSV-G-03 |
| `get_work_order_type` | R5 | WSV-G-07 |
| `get_work_order_type` | Errors | WSV-G-02, WSV-G-03, WSV-G-04, WSV-G-06 |
| `get_work_order_types` | R1 | WSV-L-01, WSV-L-02, WSV-L-03, WSV-L-04, WSV-L-08 |
| `get_work_order_types` | R2 | WSV-L-05 |
| `get_work_order_types` | R2 [BUG-1520] | WSV-L-06 |
| `get_work_order_types` | R3 | WSV-L-07 |
| `update_work_order_type` | R1 | WSV-U-01 |
| `update_work_order_type` | R2 | WSV-U-02, WSV-U-03, WSV-U-04 |
| `update_work_order_type` | R3 | WSV-C-03, WSV-C-04 (TC4, TC5 once per service, as the spec's Notes allow) |
| `update_work_order_type` | Errors | WSV-U-02, WSV-U-03, WSV-U-04 |
| `update_work_order_type` | Returns | WSV-U-01 |
| `delete_work_order_type` | R1 | WSV-D-01 |
| `delete_work_order_type` | R2 | WSV-D-02, WSV-D-03 |
| `delete_work_order_type` | R3 | WSV-C-03, WSV-C-04 (TC4, TC5 once per service) |
| `delete_work_order_type` | Errors | WSV-D-02, WSV-D-03 |
| `delete_work_order_type` | Returns | WSV-D-01 |
| Transaction contract | TC1 | WSV-C-01, WSV-U-01, WSV-D-01 |
| Transaction contract | TC2 | WSV-C-01 (also WSV-U-01, WSV-D-01) |
| Transaction contract | TC3 | WSV-C-02, WSV-C-06, WSV-U-02, WSV-D-02 |
| Transaction contract | TC4 | WSV-C-03 |
| Transaction contract | TC5 | WSV-C-04 |
| Transaction contract | TC6 | WSV-G-07, WSV-L-07 |
