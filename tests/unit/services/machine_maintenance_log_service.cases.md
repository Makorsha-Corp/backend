# Test cases — `app/services/machine_maintenance_log_service.py`

> **Spec:** `tests/unit/services/machine_maintenance_log_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — spec Gap log G1 (`IntegrityError` through an unknown `user_id`). New: MLS-C-11. Changed: Conventions (`IntegrityError` import), Reviewer summary. No other card changed, none retired.
> **Counts:** 35 cases · 22 expected-to-pass · 13 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `create_log` 11 (4 bug) · `update_log` 6 (3 bug) · `get_log` 6 (3 bug) · `list_logs` 8 (2 bug) · `delete_log` 4 (1 bug). BUG-1158's pass-through (C-10) is a schema card: the refusal belongs to `MachineMaintenanceLogCreate`.
- **Depth:** lighter target (skill step 1a). The service only wraps the manager in a transaction; the manager (full depth, 397 cards) owns every decision. TC2, TC4, TC5 once (on create), TC1 and TC3 once per write, TC6 once per read, each refusal status once. One pass-through card per manager bug the spec lists, strict or non-strict as `machine_maintenance_log_manager.cases.md` marks it (only BUG-1100 is non-strict).
- **TC1 includes the activity entry:** each write's happy card checks, after a test-level `db.rollback()`, both the log change and its `machine_activity_events` row; each error card checks neither was saved.
- **Notable design choices:**
  - Commit point and uncommitted-extra-row device as `department_service.cases.md`; here the extra row is a log.
  - **TC2** on create uses `cost=Decimal("5.5")`: only the re-read turns it into the stored `5.50` (spec Returns), so `str(result.cost) == "5.50"` fails if the refresh is dropped. Two decimals, so the card holds before and after BUG-1157.
  - `create_log` R3 is reached twice: a `DataError` from `performed_by` of 256 characters built by `model_construct` (C-04), and an `IntegrityError` 23503 from an unknown `user_id` (C-11, spec G1). Both are ordinary passes: no fix touches either path.
  - BUG-1102's card patches the DAO clock, as the manager's pass-through does.
  - `maintenance_type` is shown to reach the manager with a second enum member, OTHER (any member that is not `REPAIR`).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `MLS` = `app/services/machine_maintenance_log_service.py`. `C` create_log · `U` update_log · `G` get_log · `L` list_logs · `D` delete_log.

**Actors and fixed values.**
- `svc` = the singleton `machine_maintenance_log_service` (`from app.services.machine_maintenance_log_service import MachineMaintenanceLogService, machine_maintenance_log_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows; U1, U2, U3 = three `profiles` rows (`make_workspace`, `make_profile`). U1 created every Given log, U2 is the acting user, U3 an earlier editor.
- `LC`, `LU` = `MachineMaintenanceLogCreate`, `MachineMaintenanceLogUpdate` (`app.schemas.machine_maintenance_log`). `MachineMaintenanceLog` (`app.models.machine_maintenance_log`), `MachineActivityEvent` (`app.models.machine_activity_event`), `Factory` (`app.models.factory`), `Machine` (`app.models.machine`), `MaintenanceTypeEnum` (`app.models.enums`); `REPAIR` = `MaintenanceTypeEnum.REPAIR`; OTHER = `next(t for t in MaintenanceTypeEnum if t != REPAIR)`. `Decimal`, `date`, `timedelta`, `datetime`; `HTTPException` (`fastapi`); `DataError`, `IntegrityError` (`sqlalchemy.exc`); `inspect`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `pydantic.ValidationError`.
- MISSING = `999999999`. D1 = `date(2026, 3, 1)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`, NOW = `datetime(2031, 5, 6, 7, 8, 9)` (naive).

**Externals.** None is mocked, except the **clock patch** on the one card that names it: `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)`, active during the When.

**Standing rows.** In every test, in this order, no Given line needed; built directly, `is_active True`, `is_deleted False`, `workspace_id W1.id` unless stated.
- F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`. F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.
- M1, M2 = `Machine(workspace_id=W1.id, factory_id=F1.id, name=…)`, `name "Press 1"`, `"Press 2"`. MD = the same, `name "Press 4"`, `is_deleted True`, `is_active False`. MF = `Machine(workspace_id=W1.id, factory_id=FD.id, name="Lost Press")`. M9 = `Machine(workspace_id=W2.id, factory_id=F9.id, name="Far Press")`.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written; each log gets `db.refresh(row)` after its flush. A Given line written as code is a step to run exactly.
- **log** = `MachineMaintenanceLog(workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", created_by=U1.id)`; every other column left to its default. After "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **bulk101** = 101 logs by `add_all`, row k (k = 0 … 100) = log, but `maintenance_date = date(2025, 1, 1) + timedelta(days=k)`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `machine_maintenance_logs` and `machine_activity_events` (all workspaces) equal their values at the commit point.
- **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`. "that row" = the one row just counted.
- `count:` lines count rows with a fresh query, with the filter stated. **ids(x)** = `sorted(r.id for r in x)`.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException`, `raises: DataError`, `raises: IntegrityError`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. `raises: ValidationError` = `pydantic.ValidationError` around the schema's construction (target `schema`).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `MachineMaintenanceLogService.create_log`

### MLS-C-01 — a new log and its entry are committed; the log is returned re-read
- **Rules:** `create_log` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.5"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `cost`, `created_at`, `summary`.
2. returns: `isinstance(result, MachineMaintenanceLog)`.
3. returns: `str(result.cost) == "5.50"`.
4. returns: `result.created_by == U2.id`, `result.created_at is not None`.
5. committed: the row with `id == result.id` exists: `machine_id == M1.id`, `summary == "Bearing change"`, `cost == Decimal("5.50")`, `created_by == U2.id`.
6. committed: events_of(M1) has exactly 1 row.
7. committed: that row: `event_type == "maintenance_logged"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### MLS-C-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back
- **Rules:** `create_log` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `summary "Extra"` (after the commit point).

**When**
- `svc.create_log(db, log_in=LC(machine_id=M9.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. count: `machine_maintenance_logs` rows with `summary == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. event: events_of(M9) has exactly 0 rows.
7. session: usable.

### MLS-C-03 — a deleted machine: the 400 passes unchanged, nothing saved
- **Rules:** `create_log` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD (standing); no log exists.

**When**
- `svc.create_log(db, log_in=LC(machine_id=MD.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MLS-C-04 — a DataError at the flush passes unchanged; nothing saved; the session is usable
- **Rules:** `create_log` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.
2. `data = LC.model_construct(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Long name", cost=None, performed_by="x" * 256)`.

**When**
- `svc.create_log(db, log_in=data, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. count: `machine_maintenance_logs` rows with `summary == "Long name"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

### MLS-C-05 — a failing commit is rolled back and re-raised: neither the log nor the entry is saved
- **Rules:** `create_log` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `machine_maintenance_logs` rows: exactly 0.
4. event: events_of(M1) has exactly 0 rows.

### MLS-C-06 — a failing re-read after the commit leaves the log and its entry saved
- **Rules:** `create_log` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `machine_maintenance_logs` rows with `summary == "Bearing change"`: exactly 1.
3. committed: events_of(M1) has exactly 1 row.

### MLS-C-07 — pass-through BUG-1154: a live machine in a soft-deleted factory is refused
- **Rules:** `create_log` R2 [BUG-1154]
- **Kind:** bug
- **Expect:** xfail BUG-1154
- **Fails today on:** Then 1 (no error is raised: the log and its entry are saved)

**Given**
1. MF (standing); no log exists.

**When**
- `svc.create_log(db, log_in=LC(machine_id=MF.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MLS-C-08 — pass-through BUG-1155: a padded summary is stored trimmed
- **Rules:** `create_log` R1 [BUG-1155]
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (the summary is stored with its spaces)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `summary == "pad"`.

### MLS-C-09 — pass-through BUG-1156: a padded performed_by is stored trimmed
- **Rules:** `create_log` R1 [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="  Rahim  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `performed_by == "Rahim"`.

### MLS-C-10 — pass-through BUG-1158: a negative cost is refused by the schema
- **Rules:** `create_log` R1 [BUG-1158]
- **Kind:** bug
- **Expect:** xfail BUG-1158
- **Fails today on:** Then 1 (the schema has no minimum, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- build `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-5"))` (target `schema`; `svc` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MLS-C-11 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable
- **Rules:** `create_log` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `summary "Extra"` (after the commit point).

**When**
- `svc.create_log(db, log_in=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Ghost"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `machine_maintenance_logs` rows with `summary == "Ghost"`: exactly 0.
4. count: `machine_maintenance_logs` rows with `summary == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. session: usable.

## `MachineMaintenanceLogService.update_log`

### MLS-U-01 — a change and its entry are committed; the log is returned re-read
- **Rules:** `update_log` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = svc.update_log(db, log_id=A.id, log_in=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `summary`, `updated_at`, `updated_by`.
2. returns: `result.id == A.id`.
3. returns: `result.summary == "New text"`, `result.updated_by == U2.id`, `result.updated_at is not None`.
4. committed: re-read A: `summary == "New text"`, `updated_by == U2.id`.
5. committed: events_of(M1) has exactly 1 row.
6. committed: that row: `event_type == "maintenance_updated"`, `performed_by == U2.id`.

### MLS-U-02 — another workspace's log: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_log` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.
3. X = log, but `summary "Extra"` (after the commit point).

**When**
- `svc.update_log(db, log_id=Z.id, log_in=LU(summary="Hacked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {Z.id} not found"`.
4. count: `machine_maintenance_logs` rows with `summary == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.

### MLS-U-03 — a deleted log: the 400 passes unchanged, nothing saved
- **Rules:** `update_log` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `svc.update_log(db, log_id=A.id, log_in=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted maintenance log"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MLS-U-04 — pass-through BUG-1151: an empty body by another user leaves the earlier stamps
- **Rules:** `update_log` R1 [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (`updated_by` becomes U2)

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = svc.update_log(db, log_id=A.id, log_in=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `updated_by == U3.id`.
3. committed: re-read A: `updated_at == T0`.

### MLS-U-05 — pass-through BUG-1153: an explicit null clears cost
- **Rules:** `update_log` R1 [BUG-1153]
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 2 (null is dropped, the old value stays)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = svc.update_log(db, log_id=A.id, log_in=LU(cost=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `cost is None`.

### MLS-U-06 — pass-through BUG-1157: the entry records cost in its stored form
- **Rules:** `update_log` R1 [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 4 (the entry records `"7"`, as typed)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = svc.update_log(db, log_id=A.id, log_in=LU(cost=Decimal("7")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `cost == Decimal("7.00")`.
3. committed: events_of(M1) has exactly 1 row.
4. committed: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.00"}]}`.

## `MachineMaintenanceLogService.get_log`

### MLS-G-01 — a live log of the workspace is returned as the manager returns it
- **Rules:** `get_log` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = svc.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineMaintenanceLog)`.
2. returns: `result.id == A.id`, `result.summary == "Bearing change"`, `result.cost == Decimal("5.00")`.

### MLS-G-02 — another workspace's log: the 404 passes unchanged
- **Rules:** `get_log` R1, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `svc.get_log(db, log_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {Z.id} not found"`.

### MLS-G-03 — a soft-deleted log is hidden by default
- **Rules:** `get_log` R2 [BUG-1150], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (no error is raised: the deleted log is returned)

**Given**
1. A = log, but gone.

**When**
- `svc.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.

### MLS-G-04 — include_deleted=True returns a soft-deleted log
- **Rules:** `get_log` R3 [BUG-1150]
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log, but gone.

**When**
- `result = svc.get_log(db, log_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### MLS-G-05 — pass-through BUG-1101: a log on another workspace's machine gets the 404
- **Rules:** `get_log` R1 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (no error is raised: the log's machine is not checked)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `svc.get_log(db, log_id=X.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.

### MLS-G-06 — the read neither commits nor rolls back
- **Rules:** `get_log` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `summary "Oil change"`.
3. P = log, but `summary "Pending"` (after the commit point).
4. `B.summary = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 1.
5. committed: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
6. committed: re-read B: `summary == "Oil change"`.

## `MachineMaintenanceLogService.list_logs`

### MLS-L-01 — machine_id reaches the manager
- **Rules:** `list_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`.
3. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### MLS-L-02 — maintenance_type reaches the manager
- **Rules:** `list_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type OTHER`.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id, maintenance_type=OTHER)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MLS-L-03 — with the defaults 101 logs give 100
- **Rules:** `list_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MLS-L-04 — limit=1000 reaches the manager and gives all 101
- **Rules:** `list_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### MLS-L-05 — skip reaches the manager
- **Rules:** `list_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id, skip=100)`.

**Then**
1. returns: `len(result) == 1`.

### MLS-L-06 — the list neither commits nor rolls back
- **Rules:** `list_logs` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `workspace_id W2.id`, `machine_id M9.id`.
3. P = log, but `summary "Pending"` (after the commit point).
4. `B.summary = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. committed: re-read B: `summary == "Bearing change"`.

### MLS-L-07 — pass-through BUG-1152: machine_id=0 returns nothing
- **Rules:** `list_logs` R1 [BUG-1152]
- **Kind:** bug
- **Expect:** xfail BUG-1152
- **Fails today on:** Then 1 (0 is falsy, so every log comes back)

**Given**
1. A = log.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id, machine_id=0)`.

**Then**
1. returns: `result == []`.

### MLS-L-08 — pass-through BUG-1100: logs on one date come back highest id first
- **Rules:** `list_logs` R1 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`.

**When**
- `result = svc.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.
2. returns: `[r.id for r in result] == [C.id, B.id, A.id]`.

## `MachineMaintenanceLogService.delete_log`

### MLS-D-01 — a soft delete and its entry are committed; the log is returned re-read
- **Rules:** `delete_log` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = svc.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U2.id`, `result.deleted_at is not None`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U2.id`.
5. committed: events_of(M1) has exactly 1 row.
6. committed: that row: `event_type == "maintenance_removed"`, `performed_by == U2.id`.

### MLS-D-02 — an already deleted log: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_log` R2, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.
2. X = log, but `summary "Extra"` (after the commit point).

**When**
- `svc.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Maintenance log is already deleted"`.
4. count: `machine_maintenance_logs` rows with `summary == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. session: usable.

### MLS-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_log` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `svc.delete_log(db, log_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 999999999 not found"`.
4. nothing written: nothing written.

### MLS-D-04 — pass-through BUG-1102: deleted_at is the application clock
- **Rules:** `delete_log` R1 [BUG-1102]
- **Kind:** bug
- **Expect:** xfail BUG-1102
- **Fails today on:** Then 3 (`deleted_at` is the database's `now()`)

**Given**
1. A = log.
2. clock patch.

**When**
- `result = svc.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `is_deleted is True`, `deleted_by == U2.id`.
3. committed: re-read A: `deleted_at == NOW`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| The manager's rules (`create_log` … `delete_log`), every case beyond one pass-through per bug | `tests/unit/managers/machine_maintenance_log_manager.cases.md` | Not re-tested here. |
| BUG-1150 — the `include_deleted` query parameter on `GET /machine-maintenance-logs/{id}/` | endpoint (integration) | Accepted and passed on. |
| `DataError` → 500; `IntegrityError` → generic 409 | API handlers (integration) | Integration-only. |
| `maintenance_type` enum check | `GET /machine-maintenance-logs/` (integration) | Endpoint. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /machine-maintenance-logs/` | Endpoint bounds. |
| Schema errors answer 422 (BUG-461) | `POST`, `PUT /machine-maintenance-logs/` | Integration-only. |
| `DELETE` answers 200 with the row (manager FU-1 (d)) | endpoint (integration) | The body; the service returns the row (D-01). |

## Spec gaps
None. Revision 0's gap 1 is closed by spec Gap log G1 (MLS-C-11).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_log` | R1 | MLS-C-01 |
| `create_log` | R1 [BUG-1155] | MLS-C-08 |
| `create_log` | R1 [BUG-1156] | MLS-C-09 |
| `create_log` | R1 [BUG-1158] | MLS-C-10 |
| `create_log` | R2 | MLS-C-02, MLS-C-03 |
| `create_log` | R2 [BUG-1154] | MLS-C-07 |
| `create_log` | R3 | MLS-C-04, MLS-C-11 |
| `create_log` | R4 | MLS-C-05, MLS-C-06 |
| `create_log` | Errors | MLS-C-02, MLS-C-03, MLS-C-04, MLS-C-11 |
| `create_log` | Returns | MLS-C-01 |
| `update_log` | R1 | MLS-U-01 |
| `update_log` | R1 [BUG-1151] | MLS-U-04 |
| `update_log` | R1 [BUG-1153] | MLS-U-05 |
| `update_log` | R1 [BUG-1157] | MLS-U-06 |
| `update_log` | R2 | MLS-U-02, MLS-U-03 |
| `update_log` | R3 | MLS-U-02 (rollback of the `except` path); MLS-C-04, MLS-C-05, MLS-C-06 (database error, TC4, TC5 once per service) |
| `update_log` | Errors | MLS-U-02, MLS-U-03 |
| `update_log` | Returns | MLS-U-01 |
| `get_log` | R1 | MLS-G-01, MLS-G-02 |
| `get_log` | R1 [BUG-1101] | MLS-G-05 |
| `get_log` | R2 [BUG-1150] | MLS-G-03 |
| `get_log` | R3 [BUG-1150] | MLS-G-04 |
| `get_log` | R4 | MLS-G-06 |
| `get_log` | Errors | MLS-G-02, MLS-G-03, MLS-G-05 |
| `list_logs` | R1 | MLS-L-01, MLS-L-02, MLS-L-03, MLS-L-04, MLS-L-05 |
| `list_logs` | R1 [BUG-1152] | MLS-L-07 |
| `list_logs` | R1 [BUG-1100] | MLS-L-08 |
| `list_logs` | R2 | MLS-L-06 |
| `delete_log` | R1 | MLS-D-01 |
| `delete_log` | R1 [BUG-1102] | MLS-D-04 |
| `delete_log` | R2 | MLS-D-02, MLS-D-03 |
| `delete_log` | R3 | MLS-D-02 (rollback); MLS-C-05, MLS-C-06 (TC4, TC5 once per service) |
| `delete_log` | Errors | MLS-D-02, MLS-D-03 |
| `delete_log` | Returns | MLS-D-01 |
| Transaction contract | TC1 | MLS-C-01, MLS-U-01, MLS-D-01 |
| Transaction contract | TC2 | MLS-C-01 (also MLS-U-01, MLS-D-01) |
| Transaction contract | TC3 | MLS-C-02, MLS-C-04, MLS-C-11, MLS-U-02, MLS-D-02 |
| Transaction contract | TC4 | MLS-C-05 |
| Transaction contract | TC5 | MLS-C-06 |
| Transaction contract | TC6 | MLS-G-06, MLS-L-06 |
