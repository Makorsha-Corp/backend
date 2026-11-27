# Test cases — `app/services/department_service.py`

> **Spec:** `tests/unit/services/department_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 34 cases · 22 expected-to-pass · 12 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `create_department` 9 (4 bug) · `get_department` 7 (3 bug) · `get_departments` 10 (4 bug) · `update_department` 5 (1 bug) · `delete_department` 3.
- **Depth:** lighter target (skill step 1a). The service writes no stock, money or order state and adds no check of its own; it is a transaction wrapper. Each TC is covered once per service (TC4, TC5 on `create_department`, whose commit helper the other writes share), TC1, TC2, TC3 once per write, TC6 once per read, and each refusal status (404, 400, 409) at least once. Manager rules are not re-tested; each manager bug reached gets one pass-through card, strict or non-strict as in `department_manager.cases.md`.
- **Expected-to-fail:** BUG-005 3 (G-04 … G-06), BUG-010 1 (L-06), pass-through BUG-001 (C-08, non-strict), BUG-002 (C-06), BUG-003 (C-09), BUG-004 (C-07), BUG-006 (L-08, non-strict), BUG-007 (L-09, non-strict), BUG-008 (L-10, non-strict), BUG-009 (U-05).
- **Notable design choices:**
  - **Commit point.** Every card commits its setup before the When (`db.commit()`, a savepoint release under the `db` fixture), so the service's own rollback cannot hide setup rows. Each write's error card also adds one **uncommitted** extra row after the commit point and checks it is gone: that is the only thing a missing `db.rollback()` would change, because every manager refusal comes before the manager writes.
  - **TC2** is checked as "the columns are loaded on the returned object" (`sqlalchemy.inspect(result).unloaded`), before anything else touches the session: without the `refresh` the object is expired by the commit and a plain attribute read would hide that.
  - **Race simulation** C-09 (BUG-003) patches the manager's `_check_name_exists`, as the manager's own cards do.
  - The database-error row is reached through an unknown `user_id` (`created_by` FK, department DAO spec), not by patching the manager.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `DSV` = `app/services/department_service.py`. `C` create_department · `G` get_department · `L` get_departments · `U` update_department · `D` delete_department.

**Actors and fixed values.**
- `svc` = the singleton `department_service` (`from app.services.department_service import DepartmentService, department_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `Department` (`app.models.department`), `DepartmentCreate`, `DepartmentUpdate` (`app.schemas.department`), `HTTPException` (`fastapi`), `IntegrityError` (`sqlalchemy.exc`), `inspect`, `text`, `select` (`sqlalchemy`), `patch` (`unittest.mock`).
- W1, W2 = two `workspaces` rows; U1, U2, U3 = three `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. U1 is the acting user; U2 created the Given rows.
- MISSING = `999999999`: an id no row of any table has. T0 = `datetime(2020, 1, 2, 3, 4, 5)` (naive).

**Externals.** None is mocked. `deleted_at` comes from the DAO's own clock and is checked as not None.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **dept** = `Department(workspace_id=W1.id, name="Sales", created_by=U2.id)`; `is_active`, `is_deleted` left to their defaults `True`, `False`; `updated_by`, `deleted_at`, `deleted_by` NULL. After "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- **commit point** = after the last Given line the test runs `db.commit()` (under the `db` fixture it only releases a savepoint). A Given line marked "(after the commit point)" runs after it and stays uncommitted; it is flushed.
- No card builds two live departments of one workspace whose names are equal ignoring case and outer spaces (BUG-003), except C-09's race.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `departments` rows (all workspaces) equals its value at the commit point.
- `count:` lines count `departments` rows with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query. What it finds was committed by the call.
- `session:` lines are checks on `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException`, `raises: IntegrityError`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block, one per line.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` when the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** DSV-C-09 only (`create_department` R1, manager BUG-003): `with patch.object(svc.department_manager, "_check_name_exists", return_value=False):` around the When, inside the `raises:` wrap.

## `DepartmentService.create_department`

### DSV-C-01 — a new department is committed and returned re-read
- **Rules:** `create_department` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no departments.

**When**
- `result = svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `name`, `workspace_id`, `created_by`.
2. returns: `isinstance(result, Department)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.name == "Sales"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`.
5. committed: the row with `id == result.id` exists: `name == "Sales"`, `workspace_id == W1.id`, `created_by == U1.id`, `is_deleted is False`.
6. committed: W1 has exactly 1 `departments` row.

### DSV-C-02 — a duplicate name: the manager's 409 passes unchanged and the session is rolled back
- **Rules:** `create_department` R2, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = dept.
2. X = dept, but `name "Extra"` (after the commit point).

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Department with name 'Sales' already exists"`.
4. count: `departments` rows with `name == "Extra"`: exactly 0.
5. count: `departments` rows of W1 with `name == "Sales"`: exactly 1.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. session: usable.

### DSV-C-03 — a database error at the flush passes unchanged and nothing is saved
- **Rules:** `create_department` Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = dept, but `name "Ops"`.
2. X = dept, but `name "Extra"` (after the commit point).

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `departments` rows with `name == "Sales"`: exactly 0.
4. count: `departments` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. session: usable.

### DSV-C-04 — a failing commit is rolled back and re-raised
- **Rules:** `create_department` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no departments.

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `departments` rows of W1: exactly 0.
4. nothing written: nothing written.

### DSV-C-05 — a failing re-read after the commit leaves the department saved
- **Rules:** `create_department` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no departments.

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Sales"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `departments` row.
3. committed: that row has `name == "Sales"`, `created_by == U1.id`.

### DSV-C-06 — pass-through BUG-002: a name in another case is refused with the submitted name
- **Rules:** `create_department` R1, R2 [BUG-002]
- **Kind:** bug
- **Expect:** xfail BUG-002
- **Fails today on:** Then 1 (no error is raised: "sales" is created)

**Given**
1. A = dept.

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="sales"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Department with name 'sales' already exists"`.
4. nothing written: nothing written.

### DSV-C-07 — pass-through BUG-004: a padded name is stored trimmed
- **Rules:** `create_department` R1 [BUG-004]
- **Kind:** bug
- **Expect:** xfail BUG-004
- **Fails today on:** Then 2 (the name is stored with its spaces)

**Given**
1. W1 has no departments.
2. `data = DepartmentCreate(name=" Sales ")`.

**When**
- `result = svc.create_department(db, department_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `name == "Sales"`.

### DSV-C-08 — pass-through BUG-001: a duplicate past the first 100 rows is still refused
- **Rules:** `create_department` R1, R2 [BUG-001]
- **Kind:** bug
- **Expect:** xfail BUG-001 (non-strict)
- **Fails today on:** Then 1 (usually no error: the duplicate check reads a capped page, so a second "Logistics" is created)

**Given**
1. 30 rows, by `add_all`: k = 1 … 30, dept, but `name f"Archived {k:02d}"`, gone.
2. 79 rows, by `add_all`: k = 1 … 79, dept, but `name f"Team {k:02d}"`.
3. L = dept, but `name "Logistics"`.
4. 10 rows, by `add_all`: k = 1 … 10, dept, but `name f"Unit {k:02d}"`.

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Logistics"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Department with name 'Logistics' already exists"`.
4. count: `departments` rows of W1 with `name == "Logistics"`: exactly 1.
5. count: `departments` rows of W1: exactly 120.

### DSV-C-09 — pass-through BUG-003: a create that loses the race gets the 409, nothing saved
- **Rules:** `create_department` R1, R2 [BUG-003]
- **Kind:** bug
- **Expect:** xfail BUG-003
- **Fails today on:** Then 1 (no error is raised: no index exists and the second "Finance" is saved)

**Given**
1. A = dept, but `name "Finance"`.

**When**
- `svc.create_department(db, department_in=DepartmentCreate(name="Finance"), workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Department with name 'Finance' already exists"`.
4. count: `departments` rows of W1 with `name == "Finance"`: exactly 1.
5. session: usable.

## `DepartmentService.get_department`

### DSV-G-01 — a live department of the workspace is returned
- **Rules:** `get_department` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = dept, but `workspace_id W2.id`, `name "Far"`.
2. A = dept.

**When**
- `result = svc.get_department(db, department_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Department)`.
2. returns: `result.id == A.id`, `result.name == "Sales"`, `result.workspace_id == W1.id`.

### DSV-G-02 — another workspace's id: the manager's 404 passes unchanged
- **Rules:** `get_department` R4, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = dept.
2. Z = dept, but `workspace_id W2.id`, `name "Far"`.

**When**
- `svc.get_department(db, department_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Department with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### DSV-G-03 — id 0 gets the 404
- **Rules:** `get_department` R4, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = dept.

**When**
- `svc.get_department(db, department_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Department with ID 0 not found"`.

### DSV-G-04 — a soft-deleted department is hidden by default
- **Rules:** `get_department` R2 [BUG-005], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-005
- **Fails today on:** Then 1 (no error is raised: the deleted department is returned)

**Given**
1. A = dept, but `name "Legacy"`, gone.

**When**
- `svc.get_department(db, department_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Department with ID {A.id} not found"`.
4. unchanged: unchanged(A).

### DSV-G-05 — include_deleted=True returns a soft-deleted department
- **Rules:** `get_department` R3 [BUG-005]
- **Kind:** bug
- **Expect:** xfail BUG-005
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = dept, but `name "Legacy"`, gone.

**When**
- `result = svc.get_department(db, department_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`, `result.name == "Legacy"`.

### DSV-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_department` R3 [BUG-005], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-005
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException: the parameter does not exist)

**Given**
1. Z = dept, but `workspace_id W2.id`, `name "Far"`, gone.

**When**
- `svc.get_department(db, department_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Department with ID {Z.id} not found"`.

### DSV-G-07 — the read neither commits nor rolls back
- **Rules:** `get_department` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = dept.
2. B = dept, but `name "Ops"`.
3. P = dept, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_department(db, department_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `departments` rows with `name == "Pending"`: exactly 1.
5. committed: `departments` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `name == "Ops"`.

## `DepartmentService.get_departments`

### DSV-L-01 — the search reaches the manager and only the workspace's matches come back
- **Rules:** `get_departments` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = dept.
2. B = dept, but `name "Marketing"`.
3. C = dept, but `name "Resale"`.
4. Z = dept, but `workspace_id W2.id`, `name "Wholesale"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, search="ale")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(r.id for r in result) == [A.id, C.id]`.

### DSV-L-02 — with the defaults 101 live departments give 100
- **Rules:** `get_departments` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, dept, but `name f"Dept {k:03d}"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### DSV-L-03 — limit reaches the manager
- **Rules:** `get_departments` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: dept, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### DSV-L-04 — skip reaches the manager, limit=1000 takes the rest
- **Rules:** `get_departments` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: dept, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### DSV-L-05 — by default a soft-deleted department is left out
- **Rules:** `get_departments` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = dept.
2. D = dept, but `name "Legacy"`, gone.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### DSV-L-06 — include_deleted=True lists soft-deleted departments too
- **Rules:** `get_departments` R2 [BUG-010]
- **Kind:** bug
- **Expect:** xfail BUG-010
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = dept.
2. D = dept, but `name "Legacy"`, gone.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(r.id for r in result) == [A.id, D.id]`.

### DSV-L-07 — the list neither commits nor rolls back
- **Rules:** `get_departments` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = dept.
2. B = dept, but `workspace_id W2.id`, `name "Ops"`.
3. P = dept, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_departments(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `departments` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `name == "Ops"`.

### DSV-L-08 — pass-through BUG-006: deleted rows take no place in the page
- **Rules:** `get_departments` R1 [BUG-006]
- **Kind:** bug
- **Expect:** xfail BUG-006 (non-strict)
- **Fails today on:** Then 1 (usually `[]`: the deleted rows fill the page before they are dropped)

**Given**
1. dept, but `name "Old A"`, gone.
2. dept, but `name "Old B"`, gone.
3. dept, but `name "Old C"`, gone.
4. A = dept, but `name "Ops"`.
5. B = dept.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(r.id for r in result) == [A.id, B.id]`.

### DSV-L-09 — pass-through BUG-007: the search covers the whole workspace, not the page
- **Rules:** `get_departments` R1 [BUG-007]
- **Kind:** bug
- **Expect:** xfail BUG-007 (non-strict)
- **Fails today on:** Then 1 (usually `[]`: the search runs on the first page only)

**Given**
1. dept, but `name "Accounts"`.
2. dept, but `name "Budget"`.
3. dept, but `name "Customs"`.
4. A = dept, but `name "Warehouse"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id, search="ware", limit=2)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### DSV-L-10 — pass-through BUG-008: names come case-insensitive ascending
- **Rules:** `get_departments` R1 [BUG-008]
- **Kind:** bug
- **Expect:** xfail BUG-008 (non-strict)
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. dept.
2. dept, but `name "accounting"`.
3. dept, but `name "HR"`.
4. dept, but `name "beta"`.

**When**
- `result = svc.get_departments(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `[r.name for r in result] == ["accounting", "beta", "HR", "Sales"]`.

## `DepartmentService.update_department`

### DSV-U-01 — a rename is committed and returned re-read with updated_at
- **Rules:** `update_department` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = dept, but `name "Ops"`.

**When**
- `result = svc.update_department(db, department_id=A.id, department_in=DepartmentUpdate(name="Operations"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Operations"`, `result.updated_by == U1.id`, `result.updated_at is not None`.
4. committed: re-read A: `name == "Operations"`, `updated_by == U1.id`, `updated_at is not None`.
5. committed: re-read A: `created_by == U2.id`, `is_deleted is False`.

### DSV-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_department` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = dept.
2. Z = dept, but `workspace_id W2.id`, `name "Far"`.
3. X = dept, but `name "Extra"` (after the commit point).

**When**
- `svc.update_department(db, department_id=Z.id, department_in=DepartmentUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Department with ID {Z.id} not found"`.
4. count: `departments` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. session: usable.

### DSV-U-03 — a deleted department: the 400 passes unchanged, nothing saved
- **Rules:** `update_department` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = dept, but `name "Legacy"`, gone.

**When**
- `svc.update_department(db, department_id=A.id, department_in=DepartmentUpdate(name="Revived"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted department"`.
4. unchanged: unchanged(A).

### DSV-U-04 — a name taken: the 409 passes unchanged, nothing saved
- **Rules:** `update_department` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = dept.
2. B = dept, but `name "Ops"`.

**When**
- `svc.update_department(db, department_id=B.id, department_in=DepartmentUpdate(name="Sales"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Department with name 'Sales' already exists"`.
4. unchanged: unchanged(B).

### DSV-U-05 — pass-through BUG-009: an empty update does not stamp updated_by
- **Rules:** `update_department` R1 [BUG-009]
- **Kind:** bug
- **Expect:** xfail BUG-009
- **Fails today on:** Then 2 (`updated_by` becomes U1)

**Given**
1. A = dept, but `name "HR"`, `updated_by U2.id`.

**When**
- `result = svc.update_department(db, department_id=A.id, department_in=DepartmentUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `updated_by == U2.id`.

## `DepartmentService.delete_department`

### DSV-D-01 — a soft delete is committed and returned re-read
- **Rules:** `delete_department` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = dept, but `name "Ops"`.

**When**
- `result = svc.delete_department(db, department_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U1.id`, `result.deleted_at is not None`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`, `deleted_at is not None`.
5. committed: re-read A: `name == "Ops"`.

### DSV-D-02 — an already deleted department: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_department` R2, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = dept, but `name "Legacy"`, gone.
2. X = dept, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_department(db, department_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Department is already deleted"`.
4. count: `departments` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### DSV-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_department` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = dept.

**When**
- `svc.delete_department(db, department_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Department with ID 999999999 not found"`.
4. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP status and body of a passed-on `HTTPException` | `/departments/` endpoints (integration) | 404 / 400 / 409 bodies as the manager's detail. |
| BUG-005, BUG-010 — the `include_deleted` query parameter | `GET /departments/{id}/`, `GET /departments/` (integration) | The parameter is accepted and reaches the service; today it is ignored (verified). |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /departments/` | Endpoint bounds; called directly, negative values reach the database (spec `get_departments` Errors). |
| BUG-004 / BUG-461 — schema errors answer 422 | `POST`, `PUT /departments/` | Integration-only. |
| Global `IntegrityError` handler (409) | `app/main.py` handlers | Integration-only. |
| Session closed by the request dependency | `get_db` | Integration-only. |
| Manager rules R1–R11 (filters, names, stamps) beyond one pass-through per bug | `tests/unit/managers/department_manager.cases.md` | Not re-tested here. |
| BUG-008 strict `ORDER BY` recorder | `department_manager.cases.md` DEPT-S-26 | The query is the manager's; L-10 here is the pass-through only. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_department` | R1 | DSV-C-01 |
| `create_department` | R1 [BUG-001] | DSV-C-08 |
| `create_department` | R1 [BUG-002] | DSV-C-06 |
| `create_department` | R1 [BUG-003] | DSV-C-09 |
| `create_department` | R1 [BUG-004] | DSV-C-07 |
| `create_department` | R2 | DSV-C-02 |
| `create_department` | R3 | DSV-C-04, DSV-C-05 |
| `create_department` | Errors row 1 | DSV-C-02 |
| `create_department` | Errors row 2 | DSV-C-03 |
| `create_department` | Returns | DSV-C-01 |
| `get_department` | R1 | DSV-G-01 |
| `get_department` | R2 [BUG-005] | DSV-G-04 |
| `get_department` | R3 [BUG-005] | DSV-G-05, DSV-G-06 |
| `get_department` | R4 | DSV-G-02, DSV-G-03 |
| `get_department` | R5 | DSV-G-07 |
| `get_department` | Errors row 1 | DSV-G-02, DSV-G-03, DSV-G-04, DSV-G-06 |
| `get_departments` | R1 | DSV-L-01, DSV-L-02, DSV-L-03, DSV-L-04 |
| `get_departments` | R1 [BUG-006] | DSV-L-08 |
| `get_departments` | R1 [BUG-007] | DSV-L-09 |
| `get_departments` | R1 [BUG-008] | DSV-L-10 |
| `get_departments` | R2 | DSV-L-05 |
| `get_departments` | R2 [BUG-010] | DSV-L-06 |
| `get_departments` | R3 | DSV-L-07 |
| `update_department` | R1 | DSV-U-01 |
| `update_department` | R1 [BUG-009] | DSV-U-05 |
| `update_department` | R2 | DSV-U-02, DSV-U-03, DSV-U-04 |
| `update_department` | R3 | DSV-C-04, DSV-C-05 (TC4, TC5 once per service: the commit helper is shared) |
| `update_department` | Errors | DSV-U-02, DSV-U-03, DSV-U-04 |
| `update_department` | Returns | DSV-U-01 |
| `delete_department` | R1 | DSV-D-01 |
| `delete_department` | R2 | DSV-D-02, DSV-D-03 |
| `delete_department` | R3 | DSV-C-04, DSV-C-05 (TC4, TC5 once per service) |
| `delete_department` | Errors | DSV-D-02, DSV-D-03 |
| `delete_department` | Returns | DSV-D-01 |
| Transaction contract | TC1 | DSV-C-01, DSV-U-01, DSV-D-01 |
| Transaction contract | TC2 | DSV-C-01, DSV-U-01, DSV-D-01 |
| Transaction contract | TC3 | DSV-C-02, DSV-C-03, DSV-U-02, DSV-D-02 |
| Transaction contract | TC4 | DSV-C-04 |
| Transaction contract | TC5 | DSV-C-05 |
| Transaction contract | TC6 | DSV-G-07, DSV-L-07 |
