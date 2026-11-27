# Test cases — `app/services/machine_service.py`

> **Spec:** `tests/unit/services/machine_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 113 cases · 74 expected-to-pass · 39 expected-to-fail (bugs) · 14 deferred
> **Revision:** 2 (2026-11-04) — spec gained `get_machine_activity` R1a (default `limit` 100) → new MCS-A-14 (pass). Verifier findings addressed (`machine_service.verify.md`): Finding 1 → MCS-L-20 Expect now `xfail BUG-956, BUG-957`; Finding 2 / mutant #13 (`'all'` → `''`) → MCS-L-23 Then 4: with the default `maintenance_window="all"` no statement reads `work_orders` (machine manager R1 vs R5, R8); Finding 3 / mutant #25 → MCS-A-14. No other card changed.

## Reviewer summary
- **Per callable:** `_to_machine_response` 8 · `_to_machine_responses` 2 · `create_machine` 15 (7 bug) · `get_machine` 9 (5 bug) · `get_machines` 23 (11 bug) · `get_upcoming_work` 14 (2 bug) · `update_machine` 15 (8 bug) · `delete_machine` 7 (3 bug) · `create_machine_event` 6 (2 bug) · `get_machine_activity` 14 (1 bug).
- **Depth:** lighter target (skill step 1a) for the transaction wrapper: TC4, TC5 once (on create, the commit helper is shared), TC1, TC3 once per write, TC6 once per read, each refusal status once. Full attention for the service's own logic: response shaping (status row choice, map path, falsy and invalid status), the upcoming-work window (both sides of today, +7/+8, 0, negative, 1970-01-01), the row and item content and both sort orders, the BUG-968 translation (patched manager and real stock), and activity metadata. Manager rules are not re-tested; one pass-through card per manager bug reachable from a service call, strict or non-strict as in the managers' cases files (BUG-887, BUG-1090 non-strict).
- **Notable design choices:**
  - Commit point and the uncommitted extra row (an "Extra" machine of F2) as `department_service.cases.md`.
  - **TC2** cannot be read off a `MachineResponse` (the response is built after the re-read, and an expired row reloads on access), so it is covered by C-01 (`created_at` set on the answer) and by the failing-refresh card C-07, which proves the re-read runs.
  - **`create_machine` R3's shaping failure** has no real-data path on create (a new machine has no status rows), so C-08 patches `svc.activity_manager.get_latest_status`. On update and delete the same failure is reached with real data: a stored status `"running"` (U-07, D-06). D-06 also proves `delete_machine` R3: a `ValueError` on the delete path that is not the manager's stays a `ValueError`.
  - **Race simulation** C-12 (BUG-953) patches the manager's `_check_name_exists_in_factory`, as the manager's own C-41.
  - **BUG-951** (C-15): 101 service creates in one loop, counting refusals; the count of misses is deterministic, which name is missed is not.
  - **BUG-957** (L-20) goes through `include_deleted`, so it also fails today on BUG-956's `TypeError`; it stays strict and its Expect line names both bugs.
  - **Default `maintenance_window="all"`** is observed through the SQL of L-23: any other value sends the manager down its maintenance path, which reads work orders (machine manager R5, R8).
  - BUG-1141 (A-13) assumes the service's shaping adds no statement to the manager's three (Spec gap 1).
- **Needs a decision:** None. Spec gap 1 is small and blocks nothing.

## Conventions for this module

**IDs.** `MCS` = `app/services/machine_service.py`. `R` _to_machine_response · `RS` _to_machine_responses · `C` create_machine · `G` get_machine · `L` get_machines · `W` get_upcoming_work · `U` update_machine · `D` delete_machine · `E` create_machine_event · `A` get_machine_activity.

**Actors and fixed values.**
- `svc` = the singleton `machine_service` (`from app.services.machine_service import MachineService, machine_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows (`make_workspace`, `make_profile`). U1 created every Given row; U2 is the acting user.
- Classes: `Machine`, `MachineActivityEvent`, `MachineSectionAssignment`, `MachineItem`, `WorkOrder`, `WorkOrderType` (each from `app.models.<snake_case name>`); `MachineCreate`, `MachineUpdate`, `MachineResponse` (`app.schemas.machine`); `MachineEventCreate`, `MachineEventResponse` (`app.schemas.machine_event`); `MachineActivityEventResponse` (`app.schemas.machine_activity_event`); `MachineUpcomingWorkRow` (`app.schemas.machine_work`); IDLE, RUNNING, OFF, MAINTENANCE = members of `MachineEventTypeEnum` (`app.models.enums`). `HTTPException` (`fastapi`); `AppValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`; `IntegrityError` (`sqlalchemy.exc`); `insert`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `date`, `datetime`, `timedelta` (`datetime`).
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)` (naive). D(n) = `date.today() + timedelta(days=n)`, read in the test; nothing patches the clock.

**Externals.** None is mocked. Patches (each only on the cards that name it, around the When, inside the `raises:` wrap): **shaping patch** = `patch.object(svc.activity_manager, "get_latest_status", side_effect=RuntimeError("boom"))`; **manager patch** = `patch.object(svc.machine_manager, "delete_machine", side_effect=ValueError("Machine has stock or open orders", [{"type": "machine_stock", "id": 3}, {"type": "other_workspace"}]))`.

**Standing rows.** In every test, in this order, no Given line needed; `is_active True`, `is_deleted False`, `workspace_id W1.id` unless stated.
- Factories (`name`, `abbreviation`): F1 `"Main Plant"` / `"MP"`. F2 `"North Yard"` / `"NY"`. FD `"Closed Mill"` / `"CM"`, `is_deleted True`. F9 `"Far Depot"` / `"FR"`, `workspace_id W2.id`.
- Sections (`factory_sections`, `name`, `factory_id`): S1 `"Cutting"` of F1. S2 `"Paint"` of F1. SX `"Old Line"` of F1, `is_deleted True`.
- WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`. I1 = `items` row `name "Bolt M8"`, `name_normalized "bolt m8"`, `unit "pcs"`, `created_by U1.id`.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. A Given line written as code is a step to run exactly.
- **machine** = `Machine(workspace_id=W1.id, factory_id=F1.id, is_running=False, model_number=None, manufacturer=None, note=None, created_by=U1.id)`; the card gives `name`. Recipes: **M1** `"Lathe"`. **M2** `"Press"`. **M3** `"Drill"`, `factory_id F2.id`. **MX** `"Old Saw"`, `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **MF** `"Kiln"`, `factory_id FD.id`. **M9** `"Grinder"`, `workspace_id W2.id`, `factory_id F9.id`. **MA** `"Alpha"`, **MB** `"Beryl"`, **MC** `"Cobalt"`, **MK** `"Krypton"`, **MQ** `"Quartz"`, **MZ** `"Zenith"`. After "but" the card lists every column that differs.
- **bulk(n, p)** = n live machines of F1 in W1 by one `insert(Machine)`, named p + the number from 0, padded to 5 digits (`P00000` …), `is_running False`, `created_by U1.id`.
- **link of M to S** = `MachineSectionAssignment(workspace_id=W1.id, machine_id=M.id, factory_section_id=S.id, created_by=U1.id)`; then `db.expire_all()`.
- **status row of M at T, "X"** = `MachineActivityEvent(workspace_id=<M's>, machine_id=M.id, event_type="status_updated", description="seed", performed_by=U1.id, created_at=T, metadata_json={"status": "X"})`.
- **event of M at T** = `MachineActivityEvent(workspace_id=<M's>, machine_id=M.id, event_type="item_added", description="Logged", created_at=T)`; after "but" the card gives `performed_by`, `metadata_json`, `event_type`.
- **order of M** = `WorkOrder(workspace_id=W1.id, work_order_number="WO-" + <Given name>, work_order_type_id=WT1.id, title="Service", factory_id=F1.id, machine_id=M.id, is_deleted=False)`; the card gives `status`, `planned_date`; `<Given name>` is the row's label (`O1` → `"WO-O1"`), or the `name` the line gives for an unlabelled row (`name "OC"` → `"WO-OC"`; `name` is not a column).
- **stock of M** = `MachineItem(workspace_id=W1.id, machine_id=M.id, item_id=I1.id, req_qty=None, defective_qty=None)`; the card gives `qty`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted. **extra** = machine, but `name "Extra"`, `factory_id F2.id` (after the commit point).

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `machines`, `machine_section_assignments`, `machine_activity_events`, `work_orders`, `work_order_events` (all workspaces) equal their values at the commit point.
- **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`. **names(x)** = `[r.name for r in x]`, order checked. **ids(x)** = `sorted(r.id for r in x)`. `count:` lines count with a fresh query, filter stated.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the construction (target `schema`).
- **failing commit** / **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` (resp. `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`) around the When.
- **sql_log** = a list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call; each entry is the statement text. `statement:` lines check it.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`.

**Race simulations.** MCS-C-12 only (`create_machine` R1, BUG-953): `with patch.object(svc.machine_manager, "_check_name_exists_in_factory", return_value=False):` around the When, inside the `raises:` wrap.

## `MachineService._to_machine_response`

### MCS-R-01 — every column and the section come from the machine; no status row gives no status
- **Rules:** `_to_machine_response` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Haas"`, `note "Bay 3"`, `is_running True`.
2. link of M1 to S1.

**When**
- `result = svc._to_machine_response(db, machine=M1)`.

**Then**
1. returns: `isinstance(result, MachineResponse)`.
2. returns: `result.id == M1.id`, `result.workspace_id == W1.id`, `result.name == "Lathe"`, `result.is_running is True`.
3. returns: `result.factory_id == F1.id`, `result.factory_section_id == S1.id`, `result.factory_section_name == "Cutting"`.
4. returns: `result.model_number == "L-200"`, `result.manufacturer == "Haas"`, `result.note == "Bay 3"`.
5. returns: `result.created_by == U1.id`, `result.is_active is True`, `result.is_deleted is False`, `result.deleted_at is None`, `result.deleted_by is None`.
6. returns: `result.latest_status_type is None`, `result.latest_status_at is None`.

### MCS-R-02 — a machine without a section shows None for both section fields
- **Rules:** `_to_machine_response` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = svc._to_machine_response(db, machine=M1)`.

**Then**
1. returns: `result.factory_section_id is None`.
2. returns: `result.factory_section_name is None`.

### MCS-R-03 — the newest status row decides; a newer row of another type is ignored
- **Rules:** `_to_machine_response` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T2, `"RUNNING"`.
3. status row of M1 at T1, `"IDLE"`.
4. event of M1 at T3, but `event_type "maintenance_logged"`, `metadata_json {"status": "OFF"}`.

**When**
- `result = svc._to_machine_response(db, machine=M1)`.

**Then**
1. returns: `result.latest_status_type == RUNNING`.
2. returns: `result.latest_status_at == T2`.

### MCS-R-04 — with a map the map's row is used and no status is read
- **Rules:** `_to_machine_response` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. X = status row of M1 at T1, `"OFF"`.
3. status row of M1 at T2, `"RUNNING"`.
4. sql_log started.

**When**
- `result = svc._to_machine_response(db, machine=M1, status_map={M1.id: X})`.

**Then**
1. returns: `result.latest_status_type == OFF`.
2. returns: `result.latest_status_at == T1`.
3. statement: `not any("machine_activity_events" in s for s in sql_log)`.

### MCS-R-05 — a machine missing from the map has no status, even with a status row stored
- **Rules:** `_to_machine_response` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. status row of M1 at T1, `"RUNNING"`.
4. Y = status row of M2 at T1, `"IDLE"`.

**When**
- `result = svc._to_machine_response(db, machine=M1, status_map={M2.id: Y})`.

**Then**
1. returns: `result.latest_status_type is None`.
2. returns: `result.latest_status_at is None`.

### MCS-R-06 — an empty stored status shows the time with no type
- **Rules:** `_to_machine_response` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `""`.

**When**
- `result = svc._to_machine_response(db, machine=M1)`.

**Then**
1. returns: `result.latest_status_type is None`.
2. returns: `result.latest_status_at == T1`.

### MCS-R-07 — a status row without metadata shows the time with no type
- **Rules:** `_to_machine_response` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. event of M1 at T1, but `event_type "status_updated"`, `metadata_json None`.

**When**
- `result = svc._to_machine_response(db, machine=M1)`.

**Then**
1. returns: `result.latest_status_type is None`.
2. returns: `result.latest_status_at == T1`.

### MCS-R-08 — a stored status that is not a member value fails the read with ValueError
- **Rules:** `_to_machine_response` R5; `get_machine` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"running"`.

**When**
- `svc.get_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.

## `MachineService._to_machine_responses`

### MCS-RS-01 — an empty list gives [] with no read
- **Rules:** `_to_machine_responses` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. sql_log started.

**When**
- `result = svc._to_machine_responses(db, machines=[], workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. statement: `len(sql_log) == 0`.

### MCS-RS-02 — one status read for all, one response per machine in the input order
- **Rules:** `_to_machine_responses` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. M3.
4. status row of M1 at T1, `"RUNNING"`.
5. status row of M2 at T2, `"OFF"`.
6. sql_log started.

**When**
- `result = svc._to_machine_responses(db, machines=[M2, M3, M1], workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [M2.id, M3.id, M1.id]`.
2. returns: `[r.latest_status_type for r in result] == [OFF, None, RUNNING]`.
3. returns: `[r.latest_status_at for r in result] == [T2, None, T1]`.
4. statement: `len([s for s in sql_log if "FROM machine_activity_events" in s]) == 1`.

## `MachineService.create_machine`

### MCS-C-01 — a new machine and its created entry are committed; the answer has no status
- **Rules:** `create_machine` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=S1.id, model_number="L-200"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineResponse)`.
2. returns: `result.id is not None`, `result.created_at is not None`.
3. returns: `result.name == "Lathe"`, `result.factory_section_id == S1.id`, `result.created_by == U2.id`.
4. returns: `result.latest_status_type is None`, `result.latest_status_at is None`.
5. committed: the `machines` row with `id == result.id`: `name == "Lathe"`, `model_number == "L-200"`, `workspace_id == W1.id`.
6. committed: `machine_section_assignments` rows with `machine_id == result.id`: exactly 1.
7. committed: `machine_activity_events` rows with `machine_id == result.id` and `event_type == "created"`: exactly 1.

### MCS-C-02 — a duplicate name: the 409 passes unchanged and the session is rolled back
- **Rules:** `create_machine` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M1.
2. extra.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. count: `machines` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

### MCS-C-03 — an unknown factory: the 404 passes unchanged
- **Rules:** `create_machine` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.

### MCS-C-04 — a section refused after the machine was flushed: the 400 passes and the machine is not saved
- **Rules:** `create_machine` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. count: `machines` rows with `name == "Lathe"`: exactly 0.
5. nothing written: nothing written.

### MCS-C-05 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable
- **Rules:** `create_machine` R2 (database errors); TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M2.
2. extra.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `machines` rows with `name == "Lathe"`: exactly 0.
4. count: `machines` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. session: usable.

### MCS-C-06 — a failing commit is rolled back and re-raised; nothing is saved
- **Rules:** `create_machine` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `machines` rows: exactly 0.
4. nothing written: nothing written.

### MCS-C-07 — a failing re-read after the commit leaves the machine saved
- **Rules:** `create_machine` R3; TC5, TC2
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `machines` rows with `name == "Lathe"`: exactly 1.
3. committed: `machine_activity_events` rows with `event_type == "created"`: exactly 1.

### MCS-C-08 — a failure while shaping the answer reaches the caller; the machine stays saved
- **Rules:** `create_machine` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, with the shaping patch active, inside `raises: RuntimeError`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `machines` rows with `name == "Lathe"`: exactly 1.

### MCS-C-09 — pass-through BUG-950: the name is stored trimmed
- **Rules:** `create_machine` R1 [BUG-950]
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 2 (the name is stored with its outer spaces)

**Given**
1. No machines exist.

**When**
- `result = svc.create_machine(db, machine_in=MachineCreate(name="  Big  PRESS ", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the `machines` row with `id == result.id` has `name == "Big  PRESS"`.

### MCS-C-10 — pass-through BUG-952: a name that differs only in case is refused
- **Rules:** `create_machine` R1, R2 [BUG-952]
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (no error is raised: names are compared exactly)

**Given**
1. M1.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="LATHE", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'LATHE' already exists in this factory"`.
4. nothing written: nothing written.

### MCS-C-11 — pass-through BUG-967: a padded model number is stored trimmed
- **Rules:** `create_machine` R1 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (stored as typed, with the outer spaces)

**Given**
1. No machines exist.

**When**
- `result = svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id, model_number=" L-200 "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the `machines` row with `id == result.id` has `model_number == "L-200"`.

### MCS-C-12 — pass-through BUG-953: a create that loses the race gets the 409, nothing saved
- **Rules:** `create_machine` R1, R2 [BUG-953]
- **Kind:** bug
- **Expect:** xfail BUG-953
- **Fails today on:** Then 1 (no error is raised: no unique index, the second "Lathe" is saved)

**Given**
1. A = M1.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. count: `machines` rows with `name == "Lathe"`: exactly 1.
5. session: usable.

### MCS-C-13 — pass-through BUG-963: a soft-deleted factory is refused
- **Rules:** `create_machine` R2 [BUG-963]
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 1 (no error is raised: the machine is created)

**Given**
1. No machines exist.

**When**
- `svc.create_machine(db, machine_in=MachineCreate(name="Lathe", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create machine for deleted factory"`.
4. nothing written: nothing written.

### MCS-C-14 — pass-through BUG-972: a model_number of 201 characters is refused by the schema
- **Rules:** `create_machine` R1 [BUG-972]
- **Kind:** bug
- **Expect:** xfail BUG-972
- **Fails today on:** Then 1 (the schema has no limit)

**Given**
1. No machines exist.

**When**
- build `MachineCreate(name="Lathe", factory_id=F1.id, model_number="x" * 201)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### MCS-C-15 — pass-through BUG-951: among 101 machines every name is refused as taken
- **Rules:** `create_machine` R1, R2 [BUG-951]
- **Kind:** bug
- **Expect:** xfail BUG-951
- **Fails today on:** Then 1 (only 100 names are checked: exactly one create succeeds; which one varies, the count does not)

**Given**
1. bulk(101, "P"); `names` = their names.

**When**
- the loop: `refused = 0`, then for each `n` in `names`: `try: svc.create_machine(db, machine_in=MachineCreate(name=n, factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)` / `except HTTPException as e: refused += (e.status_code == 409)`.

**Then**
1. returns: `refused == 101`.
2. count: `machines` rows of F1: exactly 101.

## `MachineService.get_machine`

### MCS-G-01 — a live machine is returned with its current status
- **Rules:** `get_machine` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M9.
2. M1.
3. status row of M1 at T1, `"RUNNING"`.

**When**
- `result = svc.get_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineResponse)`.
2. returns: `result.id == M1.id`, `result.name == "Lathe"`.
3. returns: `result.latest_status_type == RUNNING`, `result.latest_status_at == T1`.

### MCS-G-02 — another workspace's id: the 404 passes unchanged
- **Rules:** `get_machine` R5, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. M9.

**When**
- `svc.get_machine(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. unchanged: unchanged(M9).

### MCS-G-03 — an unknown id: the 404 passes unchanged
- **Rules:** `get_machine` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `svc.get_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.

### MCS-G-04 — a soft-deleted machine is hidden by default
- **Rules:** `get_machine` R2 [BUG-955], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (no error is raised: the deleted machine is returned)

**Given**
1. MX.

**When**
- `svc.get_machine(db, machine_id=MX.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MX.id} not found"`.

### MCS-G-05 — include_deleted=True returns a soft-deleted machine with its last status
- **Rules:** `get_machine` R3 [BUG-955]
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MX.
2. status row of MX at T1, `"OFF"`.

**When**
- `result = svc.get_machine(db, machine_id=MX.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MX.id`, `result.is_deleted is True`.
2. returns: `result.latest_status_type == OFF`, `result.latest_status_at == T1`.

### MCS-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_machine` R3 [BUG-955], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. M9, but `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `svc.get_machine(db, machine_id=M9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.

### MCS-G-07 — a live machine of a soft-deleted factory is hidden by default
- **Rules:** `get_machine` R4 [BUG-966], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-966
- **Fails today on:** Then 1 (no error is raised: the machine is returned)

**Given**
1. MF.

**When**
- `svc.get_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MF.id} not found"`.

### MCS-G-08 — include_deleted=True returns a machine of a soft-deleted factory
- **Rules:** `get_machine` R4 [BUG-966]
- **Kind:** bug
- **Expect:** xfail BUG-966
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MF.

**When**
- `result = svc.get_machine(db, machine_id=MF.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MF.id`, `result.factory_id == FD.id`, `result.is_deleted is False`.

### MCS-G-09 — the read neither commits nor rolls back
- **Rules:** `get_machine` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. P = machine, but `name "Pending"` (after the commit point).
4. `B.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_machine(db, machine_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `machines` rows with `name == "Pending"`: exactly 1.
5. committed: `machines` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `note is None`.

## `MachineService.get_machines`

### MCS-L-01 — factory_id reaches the manager and each machine carries its status
- **Rules:** `get_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. M3.
3. status row of M1 at T1, `"RUNNING"`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `[r.id for r in result] == [M1.id]`.
3. returns: `isinstance(result[0], MachineResponse)`.
4. returns: `result[0].latest_status_type == RUNNING`, `result[0].latest_status_at == T1`.

### MCS-L-02 — a workspace without machines gives []
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M9.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCS-L-03 — with the defaults 101 machines give 100
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MCS-L-04 — limit=1000 reaches the manager and gives all 101
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### MCS-L-05 — skip reaches the manager
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, skip=100)`.

**Then**
1. returns: `len(result) == 1`.

### MCS-L-06 — every list filter reaches the manager, each wrong machine failing exactly one
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `is_running True`, `model_number "L-200"`, `manufacturer "Haas"`.
2. MB, but `name "Basalt"`, `factory_id F2.id`, `is_running True`, `model_number "L-200"`, `manufacturer "Haas"`.
3. MC, but `model_number "L-200"`, `manufacturer "Haas"`.
4. MZ, but `name "Zara"`, `is_running True`, `manufacturer "Haas"`.
5. MQ, but `is_running True`, `model_number "L-200"`.
6. MK, but `is_running True`, `model_number "L-200"`, `manufacturer "Bosch"`.
7. machine, but `name "Salsa"`, `is_running True`, `model_number "L-200"`, `manufacturer "Haas"`.
8. link of MA to S1.
9. link of MB to S1.
10. link of MC to S1.
11. link of MZ to S1.
12. link of MQ to S1.
13. link of MK to S1.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, factory_id=F1.id, factory_section_id=S1.id, is_running=True, search="a", has_model_number=True, has_manufacturer=True)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-07 — maintenance_window reaches the manager
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-1)`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-08 — sort_by and sort_dir reach the manager
- **Rules:** `get_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `created_at T1`.
2. MB, but `created_at T2`.
3. MC, but `created_at T0`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, sort_by="created_at", sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Beryl", "Alpha", "Cobalt"]`.

### MCS-L-09 — by default a soft-deleted machine is left out
- **Rules:** `get_machines` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. MX.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [MA.id]`.

### MCS-L-10 — include_deleted=True lists soft-deleted machines too
- **Rules:** `get_machines` R2 [BUG-956]
- **Kind:** bug
- **Expect:** xfail BUG-956
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MA.
2. MX.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [MA.id, MX.id]`.
2. returns: `[r.is_deleted for r in result if r.id == MX.id] == [True]`.

### MCS-L-11 — the list neither commits nor rolls back
- **Rules:** `get_machines` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2, but `workspace_id W2.id`, `factory_id F9.id`.
3. P = machine, but `name "Pending"` (after the commit point).
4. `B.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == ids([A, P])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `machines` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `note is None`.

### MCS-L-12 — pass-through BUG-886: latest_event_type filters the list
- **Rules:** `get_machines` R1 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the query cannot be built)

**Given**
1. MA.
2. MZ.
3. status row of MA at T1, `"IDLE"`.
4. status row of MZ at T1, `"RUNNING"`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, latest_event_type=IDLE)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-13 — pass-through BUG-887: a case-only tie on the maintenance sort falls to id
- **Rules:** `get_machines` R1 [BUG-887]
- **Kind:** bug
- **Expect:** xfail BUG-887 (non-strict)
- **Fails today on:** Then 1 (the order comes from collation, not from id)

**Given**
1. machine, but `name "Bolt"`.
2. machine, but `name "bolt"`, `factory_id F2.id`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Bolt", "bolt"]`.

### MCS-L-14 — pass-through BUG-888: search text is literal
- **Rules:** `get_machines` R1 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (`%` matches every machine)

**Given**
1. MA, but `model_number "50%"`.
2. MZ.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-15 — pass-through BUG-889: the id of a soft-deleted section finds nothing
- **Rules:** `get_machines` R1 [BUG-889]
- **Kind:** bug
- **Expect:** xfail BUG-889
- **Fails today on:** Then 1 ("Alpha" is returned)

**Given**
1. MA.
2. link of MA to SX.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, factory_section_id=SX.id)`.

**Then**
1. returns: `result == []`.

### MCS-L-16 — pass-through BUG-890: a machine of a soft-deleted factory is not listed
- **Rules:** `get_machines` R1 [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 ("Kiln" is listed)

**Given**
1. MA.
2. MF.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-17 — pass-through BUG-892: search text is trimmed
- **Rules:** `get_machines` R1 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the untrimmed text matches nothing)

**Given**
1. MA.
2. MZ.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, search=" alpha ")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCS-L-18 — pass-through BUG-958: the window filter finds a machine past the first 10 000
- **Rules:** `get_machines` R1 [BUG-958]
- **Kind:** bug
- **Expect:** xfail BUG-958
- **Fails today on:** Then 1 (only the first 10 000 by name are looked at)

**Given**
1. bulk(10001, "B").
2. O1 = order of the machine named "B10000", `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["B10000"]`.

### MCS-L-19 — pass-through BUG-973: work at today + 366 counts as scheduled
- **Rules:** `get_machines` R1 [BUG-973]
- **Kind:** bug
- **Expect:** xfail BUG-973
- **Fails today on:** Then 1 ("Alpha" is listed as having nothing scheduled)

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(366)`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCS-L-20 — pass-through BUG-957: include_deleted applies has_model_number
- **Rules:** `get_machines` R1, R2 [BUG-956, BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-956, BUG-957
- **Fails today on:** Then 1 (the call raises TypeError: BUG-956; once that is fixed, the filter is ignored)

**Given**
1. MA, but `model_number "L-200"`.
2. MZ.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, include_deleted=True, has_model_number=True)`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCS-L-21 — pass-through BUG-1090: on a status tie the row with the higher id is shown
- **Rules:** `get_machines` R1; `_to_machine_responses` R2 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical order decides)

**Given**
1. M1.
2. status row of M1 at T2, `"RUNNING"`.
3. status row of M1 at T2, `"OFF"`.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].latest_status_type == OFF`.

### MCS-L-22 — an empty page shapes nothing and reads no status
- **Rules:** `get_machines` R1; `_to_machine_responses` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`.
3. sql_log started.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.
2. statement: `not any("FROM machine_activity_events" in s for s in sql_log)`.

### MCS-L-23 — a page of machines makes one status read; the default window reads no work orders
- **Rules:** `get_machines` R1 (default `maintenance_window="all"`); `_to_machine_responses` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MA.
2. MB.
3. MC.
4. status row of MA at T1, `"RUNNING"`.
5. status row of MC at T1, `"IDLE"`.
6. sql_log started.

**When**
- `result = svc.get_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha", "Beryl", "Cobalt"]`.
2. returns: `[r.latest_status_type for r in result] == [RUNNING, None, IDLE]`.
3. statement: `len([s for s in sql_log if "FROM machine_activity_events" in s]) == 1`.
4. statement: `not any("work_orders" in s for s in sql_log)`.

## `MachineService.get_upcoming_work`

### MCS-W-01 — the default window is today to today + 7, both ends included
- **Rules:** `get_upcoming_work` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date D(-1)`.
3. O2 = order of M1, `status "DRAFT"`, `planned_date D(0)`.
4. O3 = order of M1, `status "DRAFT"`, `planned_date D(7)`.
5. O4 = order of M1, `status "DRAFT"`, `planned_date D(8)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `isinstance(result[0], MachineUpcomingWorkRow)`.
3. returns: `[i.source_id for i in result[0].items] == [O2.id, O3.id]`.
4. returns: `result[0].earliest_date == D(0)`, `result[0].count == 2`.

### MCS-W-02 — within_days=0 keeps only today
- **Rules:** `get_upcoming_work` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date D(0)`.
3. O2 = order of M1, `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id, within_days=0)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.source_id for i in result[0].items] == [O1.id]`.

### MCS-W-03 — a negative within_days gives []
- **Rules:** `get_upcoming_work` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date D(0)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id, within_days=-1)`.

**Then**
1. returns: `result == []`.

### MCS-W-04 — include_overdue adds overdue orders of both open statuses
- **Rules:** `get_upcoming_work` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`, `planned_date D(-1)`.
3. O2 = order of M1, `status "DRAFT"`, `planned_date D(-30)`.
4. O3 = order of M1, `status "DRAFT"`, `planned_date D(8)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id, include_overdue=True)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.source_id for i in result[0].items] == [O2.id, O1.id]`.
3. returns: `result[0].earliest_date == D(-30)`.

### MCS-W-05 — with include_overdue the window starts on 1 January 1970
- **Rules:** `get_upcoming_work` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date date(1969, 12, 31)`.
3. O2 = order of M1, `status "DRAFT"`, `planned_date date(1970, 1, 1)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id, include_overdue=True)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.source_id for i in result[0].items] == [O2.id]`.

### MCS-W-06 — only open, live, dated orders with a machine count
- **Rules:** `get_upcoming_work` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. OD = order of M1, `status "DRAFT"`, `planned_date D(1)`.
3. OP = order of M1, `status "IN_PROGRESS"`, `planned_date D(1)`.
4. order of M1, `status "COMPLETED"`, `planned_date D(1)`, name `"OC"`.
5. order of M1, `status "VOIDED"`, `planned_date D(1)`, name `"OV"`.
6. order of M1, `status "DRAFT"`, `planned_date D(1)`, `is_deleted True`, name `"OX"`.
7. order of M1, `status "DRAFT"`, `planned_date None`, name `"ON"`.
8. order of M1, `status "DRAFT"`, `planned_date D(1)`, `machine_id None`, name `"OM"`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `sorted(i.source_id for i in result[0].items) == [OD.id, OP.id]`.
3. returns: `result[0].count == 2`.

### MCS-W-07 — another workspace's orders never count, lower or higher id
- **Rules:** `get_upcoming_work` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. WT9 = `WorkOrderType(workspace_id=W2.id, name="Far Repair")`.
2. M9.
3. M1.
4. order of M9, `status "DRAFT"`, `planned_date D(1)`, `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, name `"Z1"`.
5. O1 = order of M1, `status "DRAFT"`, `planned_date D(1)`.
6. order of M9, `status "DRAFT"`, `planned_date D(1)`, `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, name `"Z2"`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `[i.source_id for i in result[0].items] == [O1.id]`.

### MCS-W-08 — orders on a soft-deleted machine never count
- **Rules:** `get_upcoming_work` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.
2. M1.
3. order of MX, `status "DRAFT"`, `planned_date D(1)`, name `"OX"`.
4. O1 = order of M1, `status "DRAFT"`, `planned_date D(2)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.

### MCS-W-09 — factory_id is compared with the order's factory, not the machine's
- **Rules:** `get_upcoming_work` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M3.
3. O1 = order of M1, `status "DRAFT"`, `planned_date D(1)`, `factory_id F2.id`.
4. O3 = order of M3, `status "DRAFT"`, `planned_date D(1)`, `factory_id F1.id`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `[i.source_id for i in result[0].items] == [O1.id]`.

### MCS-W-10 — a row carries the machine, its section, the count and the items by date then id
- **Rules:** `get_upcoming_work` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. link of M1 to S1.
3. O1 = order of M1, `status "DRAFT"`, `planned_date D(2)`.
4. O2 = order of M1, `status "IN_PROGRESS"`, `planned_date D(1)`, `title ""`.
5. O3 = order of M1, `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].machine_id == M1.id`, `result[0].name == "Lathe"`, `result[0].factory_id == F1.id`.
3. returns: `result[0].factory_section_id == S1.id`, `result[0].section_name == "Cutting"`.
4. returns: `result[0].earliest_date == D(1)`, `result[0].count == 3`, `result[0].sources.work_orders == 3`.
5. returns: `[i.source_id for i in result[0].items] == [O2.id, O3.id, O1.id]`.
6. returns: `[i.kind for i in result[0].items] == ["work_order", "work_order", "work_order"]`.
7. returns: `[i.title for i in result[0].items] == ["WO-O2", "Service", "Service"]`.
8. returns: `[i.date for i in result[0].items] == [D(1), D(1), D(2)]`.
9. returns: `[i.status for i in result[0].items] == ["IN_PROGRESS", "DRAFT", "DRAFT"]`.
10. returns: `[i.work_order_type_name for i in result[0].items] == ["Repair", "Repair", "Repair"]`.

### MCS-W-11 — rows sort by earliest date, then name ignoring case, then machine id
- **Rules:** `get_upcoming_work` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X1 = machine, but `name "gamma"`.
2. X2 = machine, but `name "Beta"`.
3. X3 = machine, but `name "Gamma"`, `factory_id F2.id`.
4. X4 = machine, but `name "alpha"`.
5. X5 = machine, but `name "Zed"`.
6. order of X1, `status "DRAFT"`, `planned_date D(3)`, name `"A1"`.
7. order of X2, `status "DRAFT"`, `planned_date D(1)`, name `"A2"`.
8. order of X3, `status "DRAFT"`, `planned_date D(3)`, name `"A3"`.
9. order of X4, `status "DRAFT"`, `planned_date D(1)`, name `"A4"`.
10. order of X5, `status "DRAFT"`, `planned_date D(0)`, name `"A5"`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.name for r in result] == ["Zed", "alpha", "Beta", "gamma", "Gamma"]`.
2. returns: `[r.machine_id for r in result][3:] == [X1.id, X3.id]`.
3. returns: `result[0].factory_section_id is None`, `result[0].section_name is None`.

### MCS-W-12 — BUG-1571: a W1 order on another workspace's machine is left out, nothing of W2 shown
- **Rules:** `get_upcoming_work` R6 [BUG-1571]
- **Kind:** bug
- **Expect:** xfail BUG-1571
- **Fails today on:** Then 1 (the W2 machine is listed with its id and name)

**Given**
1. M9.
2. M1.
3. order of M9, `status "DRAFT"`, `planned_date D(1)`, name `"OS"`.
4. O1 = order of M1, `status "DRAFT"`, `planned_date D(2)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `"Grinder" not in [r.name for r in result]`.
3. returns: `F9.id not in [r.factory_id for r in result]`.

### MCS-W-13 — BUG-1572: a live machine of a soft-deleted factory is left out
- **Rules:** `get_upcoming_work` R7 [BUG-1572]
- **Kind:** bug
- **Expect:** xfail BUG-1572
- **Fails today on:** Then 1 ("Kiln" is listed)

**Given**
1. MF.
2. M1.
3. order of MF, `status "DRAFT"`, `planned_date D(1)`, `factory_id FD.id`, name `"OK"`.
4. O1 = order of M1, `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.

### MCS-W-14 — upcoming work neither commits nor rolls back
- **Rules:** `get_upcoming_work` R8; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. O1 = order of A, `status "DRAFT"`, `planned_date D(1)`.
4. P = machine, but `name "Pending"` (after the commit point).
5. `B.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_upcoming_work(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `machines` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `note is None`.

## `MachineService.update_machine`

### MCS-U-01 — a rename is committed with its entry; the answer keeps the current status
- **Rules:** `update_machine` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`.

**When**
- `result = svc.update_machine(db, machine_id=M1.id, machine_in=MachineUpdate(name="Big Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineResponse)`.
2. returns: `result.id == M1.id`, `result.name == "Big Lathe"`, `result.updated_by == U2.id`, `result.updated_at is not None`.
3. returns: `result.latest_status_type == RUNNING`, `result.latest_status_at == T1`.
4. committed: re-read M1: `name == "Big Lathe"`, `updated_by == U2.id`.
5. committed: `machine_activity_events` rows with `machine_id == M1.id` and `event_type == "updated"`: exactly 1.

### MCS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_machine` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = M1.
2. Z = M9.
3. extra.

**When**
- `svc.update_machine(db, machine_id=Z.id, machine_in=MachineUpdate(name="Hacked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {Z.id} not found"`.
4. count: `machines` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. session: usable.

### MCS-U-03 — a deleted machine: the 400 passes unchanged
- **Rules:** `update_machine` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `svc.update_machine(db, machine_id=MX.id, machine_in=MachineUpdate(name="Revived"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. unchanged: unchanged(MX).

### MCS-U-04 — a name taken: the 409 passes unchanged
- **Rules:** `update_machine` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. B = M2.

**When**
- `svc.update_machine(db, machine_id=B.id, machine_in=MachineUpdate(name="Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. unchanged: unchanged(B).
5. nothing written: nothing written.

### MCS-U-05 — an unknown target factory: the 404 passes unchanged
- **Rules:** `update_machine` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M1.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### MCS-U-06 — a section refused after the manager flushed the rename: nothing is saved
- **Rules:** `update_machine` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = M1.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(name="Big Lathe", factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MCS-U-07 — a ValueError while shaping after the commit reaches the caller unchanged; the edit stays saved
- **Rules:** `update_machine` R3; `delete_machine` R3 (another method)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M1.
2. status row of M1 at T1, `"running"`.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. committed: re-read A: `note == "Bay 4"`.

### MCS-U-08 — pass-through BUG-954: a move into a taken name is refused
- **Rules:** `update_machine` R2 [BUG-954]
- **Kind:** bug
- **Expect:** xfail BUG-954
- **Fails today on:** Then 1 (no error is raised: the move is saved)

**Given**
1. A = M1.
2. M3, but `name "Lathe"`.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. unchanged: unchanged(A).

### MCS-U-09 — pass-through BUG-959: an empty update by an unknown user succeeds and writes nothing
- **Rules:** `update_machine` R1 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 1 (the call raises IntegrityError: `updated_by` is written on every call)

**Given**
1. A = M1.

**When**
- `result = svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result.id == A.id`.
2. unchanged: unchanged(A).

### MCS-U-10 — pass-through BUG-961: factory id 0 gets the 404
- **Rules:** `update_machine` R2 [BUG-961]
- **Kind:** bug
- **Expect:** xfail BUG-961
- **Fails today on:** Then 1 (the call raises IntegrityError: 0 skips the check)

**Given**
1. A = M1.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. unchanged: unchanged(A).

### MCS-U-11 — pass-through BUG-962: an explicit null clears model_number
- **Rules:** `update_machine` R1 [BUG-962]
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 2 (the null is dropped and the old value stays)

**Given**
1. A = M1, but `model_number "L-200"`.

**When**
- `result = svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(model_number=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `model_number is None`.

### MCS-U-12 — pass-through BUG-964: an edit of a machine in a soft-deleted factory is refused
- **Rules:** `update_machine` R2 [BUG-964]
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 1 (no error is raised: the change is saved)

**Given**
1. A = MF.

**When**
- `svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(name="Big Kiln"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MCS-U-13 — pass-through BUG-970: a move without a section clears the old factory's section
- **Rules:** `update_machine` R1 [BUG-970]
- **Kind:** bug
- **Expect:** xfail BUG-970
- **Fails today on:** Then 3 (the link stays on a section of the old factory)

**Given**
1. A = M1.
2. link of M1 to S1.

**When**
- `result = svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_id == F2.id`.
2. committed: re-read A: `factory_id == F2.id`.
3. committed: `machine_section_assignments` rows with `machine_id == A.id`: exactly 0.

### MCS-U-14 — pass-through BUG-971: an edit re-sending a left-over link to a deleted section succeeds
- **Rules:** `update_machine` R1 [BUG-971]
- **Kind:** bug
- **Expect:** xfail BUG-971
- **Fails today on:** Then 1 (the call raises HTTPException 400 for the deleted section)

**Given**
1. A = M1.
2. link of M1 to SX.

**When**
- `result = svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(note="Bay 4", factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `note == "Bay 4"`.
3. committed: `machine_section_assignments` rows with `machine_id == A.id` and `factory_section_id == SX.id`: exactly 1.

### MCS-U-15 — pass-through BUG-975: an open order follows the moved machine
- **Rules:** `update_machine` R1 [BUG-975]
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 3 (the order keeps the old factory)

**Given**
1. A = M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date None`.

**When**
- `result = svc.update_machine(db, machine_id=A.id, machine_in=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_id == F2.id`.
2. committed: re-read A: `factory_id == F2.id`.
3. committed: re-read O1: `factory_id == F2.id`.

## `MachineService.delete_machine`

### MCS-D-01 — a soft delete and its entry are committed; the answer keeps the last status
- **Rules:** `delete_machine` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = M1.
2. status row of M1 at T1, `"RUNNING"`.

**When**
- `result = svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineResponse)`.
2. returns: `result.id == A.id`, `result.is_deleted is True`, `result.is_active is False`, `result.deleted_by == U2.id`, `result.deleted_at is not None`.
3. returns: `result.latest_status_type == RUNNING`, `result.latest_status_at == T1`.
4. committed: re-read A: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`, `deleted_at is not None`.
5. committed: `machine_activity_events` rows with `machine_id == A.id` and `event_type == "deactivated"`: exactly 1.

### MCS-D-02 — an already deleted machine: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_machine` R1, Errors row 2; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = MX.
2. extra.

**When**
- `svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already deleted"`.
4. count: `machines` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### MCS-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M1.

**When**
- `svc.delete_machine(db, machine_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### MCS-D-04 — the manager's in-use ValueError becomes the 400 with the blockers as given, after a rollback
- **Rules:** `delete_machine` R2 [BUG-968], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (the `ValueError` escapes unchanged)

**Given**
1. A = M1.
2. extra.

**When**
- `svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch active, inside `raises: AppValidationError`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine has stock or open orders"`.
4. raises: `exc.value.errors == [{"type": "machine_stock", "id": 3}, {"type": "other_workspace"}]`.
5. count: `machines` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(A).

### MCS-D-05 — end to end: stock on the machine blocks the delete with a 400 that lists it
- **Rules:** `delete_machine` R2 [BUG-968], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. A = M1.
2. ST1 = stock of M1, `qty 5`.

**When**
- `svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine has stock or open orders"`.
4. raises: `exc.value.errors == [{"type": "machine_stock", "id": ST1.id}]`.
5. unchanged: unchanged(A).
6. nothing written: nothing written.

### MCS-D-06 — a ValueError while shaping after the delete is not translated; the delete stays saved
- **Rules:** `delete_machine` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = M1.
2. status row of M1 at T1, `"running"`.

**When**
- `svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. committed: re-read A: `is_deleted is True`.

### MCS-D-07 — pass-through BUG-965: a machine of a soft-deleted factory is refused
- **Rules:** `delete_machine` R1 [BUG-965], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-965
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. A = MF.

**When**
- `svc.delete_machine(db, machine_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a machine of a deleted factory"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

## `MachineService.create_machine_event`

### MCS-E-01 — a status change is committed and the manager's response returned
- **Rules:** `create_machine_event` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = M1.

**When**
- `result = svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=A.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineEventResponse)`.
2. returns: `result.id is not None`.
3. committed: `machine_activity_events` rows with `machine_id == A.id` and `event_type == "status_updated"`: exactly 1.
4. committed: that row has `id == result.id`, `performed_by == U2.id`, `metadata_json["status"] == "RUNNING"`.
5. committed: re-read A: `is_running is True`.

### MCS-E-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back
- **Rules:** `create_machine_event` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = M9.
2. extra.

**When**
- `svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=Z.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {Z.id} not found"`.
4. count: `machines` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. session: usable.

### MCS-E-03 — a deleted machine: the 400 passes unchanged
- **Rules:** `create_machine_event` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = MX.

**When**
- `svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=A.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.
4. nothing written: nothing written.

### MCS-E-04 — the same status again: the 400 passes unchanged
- **Rules:** `create_machine_event` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = M1, but `is_running True`.
2. status row of M1 at T1, `"RUNNING"`.

**When**
- `svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=A.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already in 'RUNNING' state"`.
4. count: `machine_activity_events` rows with `machine_id == A.id`: exactly 1.
5. unchanged: unchanged(A).

### MCS-E-05 — pass-through BUG-960: the machine row is read FOR UPDATE before the current status
- **Rules:** `create_machine_event` R1 [BUG-960]
- **Kind:** bug
- **Expect:** xfail BUG-960
- **Fails today on:** Then 2 (no statement carries `FOR UPDATE`)

**Given**
1. A = M1.
2. sql_log started.

**When**
- `result = svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=A.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `lock = [i for i, s in enumerate(sql_log) if "FROM machines" in s and "FOR UPDATE" in s]`, `len(lock) >= 1`.
3. statement: `lock[0] < min(i for i, s in enumerate(sql_log) if "FROM machine_activity_events" in s)`.

### MCS-E-06 — pass-through BUG-974: a change on a machine of a soft-deleted factory is refused
- **Rules:** `create_machine_event` R2 [BUG-974]
- **Kind:** bug
- **Expect:** xfail BUG-974
- **Fails today on:** Then 1 (no error is raised: the event and `is_running` are written)

**Given**
1. A = MF.

**When**
- `svc.create_machine_event(db, event_in=MachineEventCreate(machine_id=A.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a machine of a deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

## `MachineService.get_machine_activity`

### MCS-A-01 — entries come newest first, each with its columns and performer name
- **Rules:** `get_machine_activity` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T1, but `performed_by U1.id`.
3. B = event of M1 at T2.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [B.id, A.id]`.
2. returns: `isinstance(result[0], MachineActivityEventResponse)`.
3. returns: `result[1].workspace_id == W1.id`, `result[1].machine_id == M1.id`, `result[1].event_type == "item_added"`, `result[1].description == "Logged"`.
4. returns: `result[1].performed_by == U1.id`, `result[1].created_at == T1`, `result[1].performer_name == U1.name`.
5. returns: `result[0].performed_by is None`, `result[0].performer_name is None`.

### MCS-A-02 — from_date, to_date and event_type reach the manager
- **Rules:** `get_machine_activity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at `datetime(2026, 3, 4, 10, 0, 0)`, but `event_type "status_updated"`.
3. B = event of M1 at `datetime(2026, 3, 5, 10, 0, 0)`.
4. C = event of M1 at `datetime(2026, 3, 5, 10, 0, 0)`, but `event_type "status_updated"`.
5. D = event of M1 at `datetime(2026, 3, 6, 10, 0, 0)`, but `event_type "status_updated"`.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5), event_type="status_updated")`.

**Then**
1. returns: `[r.id for r in result] == [C.id]`.

### MCS-A-03 — skip and limit reach the manager
- **Rules:** `get_machine_activity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T0.
3. B = event of M1 at T1.
4. C = event of M1 at T2.
5. D = event of M1 at T3.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `[r.id for r in result] == [C.id, B.id]`.

### MCS-A-04 — another workspace's machine: the 404 passes unchanged
- **Rules:** `get_machine_activity` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.
2. event of M9 at T1.

**When**
- `svc.get_machine_activity(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.

### MCS-A-05 — a soft-deleted machine's activity is returned
- **Rules:** `get_machine_activity` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.
2. A = event of MX at T1.

**When**
- `result = svc.get_machine_activity(db, machine_id=MX.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### MCS-A-06 — metadata {} reads as None
- **Rules:** `get_machine_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T1, but `metadata_json {}`.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.
2. returns: `result[0].metadata is None`.

### MCS-A-07 — metadata None reads as None
- **Rules:** `get_machine_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T1, but `metadata_json None`.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].metadata is None`.

### MCS-A-08 — listed keys are kept, absent ones are None, others are dropped; the row is not changed
- **Rules:** `get_machine_activity` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T1, but `metadata_json {"quantity": 3, "status": "RUNNING", "item_id": 5, "note": "x"}`.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].metadata.quantity == 3`, `result[0].metadata.status == "RUNNING"`, `result[0].metadata.item_id == 5`.
2. returns: `result[0].metadata.changes is None`, `result[0].metadata.work_order_id is None`.
3. returns: `"note" not in result[0].metadata.model_dump()`.
4. re-read A: `metadata_json == {"quantity": 3, "status": "RUNNING", "item_id": 5, "note": "x"}`.

### MCS-A-09 — a single key alone is enough to build metadata
- **Rules:** `get_machine_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. A = event of M1 at T1, but `metadata_json {"note": "x"}`.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].metadata is not None`.
2. returns: `result[0].metadata.status is None`, `result[0].metadata.quantity is None`.

### MCS-A-10 — a metadata the schema cannot read fails the whole call
- **Rules:** `get_machine_activity` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. event of M1 at T1.
3. event of M1 at T2, but `metadata_json {"quantity": 2.5}`.

**When**
- `svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. raises: `PydanticValidationError`.

### MCS-A-11 — the activity read neither commits nor rolls back
- **Rules:** `get_machine_activity` R6; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. E = event of M1 at T1.
4. P = machine, but `name "Pending"` (after the commit point).
5. `B.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_machine_activity(db, machine_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [E.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `machines` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `note is None`.

### MCS-A-12 — an unknown machine: the 404 passes unchanged
- **Rules:** `get_machine_activity` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `svc.get_machine_activity(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.

### MCS-A-13 — pass-through BUG-1141: five entries by one person make at most three reads
- **Rules:** `get_machine_activity` R1 [BUG-1141]
- **Kind:** bug
- **Expect:** xfail BUG-1141
- **Fails today on:** Then 2 (one performer read per entry)

**Given**
1. M1.
2. 5 rows, k = 1 … 5: event of M1 at `datetime(2026, 3, k, 10, 0, 0)`, but `performed_by U1.id`.
3. sql_log started.

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.performer_name for r in result] == [U1.name] * 5`.
2. statement: `len(sql_log) <= 3`.

### MCS-A-14 — without skip or limit, 101 entries give the 100 newest
- **Rules:** `get_machine_activity` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. 100 rows, k = 1 … 100: event of M1 at `T0 + timedelta(minutes=k)`.
3. O = event of M1 at T0 (the oldest entry, flushed last, so it has the highest id).

**When**
- `result = svc.get_machine_activity(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `O.id not in [r.id for r in result]`.
3. returns: `min(r.created_at for r in result) == T0 + timedelta(minutes=1)`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_machines` R4 [BUG-1570] | `GET /machines/` (integration) | `maintenance_window`, `sort_by`, `sort_dir` outside the listed values refused by request validation; the service passes what it gets. |
| BUG-955, BUG-956, BUG-966 — the `include_deleted` query parameter | `GET /machines/{id}/`, `GET /machines/` (integration) | The parameter is accepted and reaches the service. |
| `delete_machine` R2 [BUG-968] — the 400 body over HTTP | `DELETE /machines/{id}/` with `api_exception_handler` (integration) | 400 with the blocker list. |
| BUG-968 manager half — every blocker type and cross-workspace shape | `tests/unit/managers/machine_manager.cases.md` | Full depth there. |
| BUG-1000 | `machine_manager.cases.md` (E-11 …) | Unreachable here: the service never passes a `work_order_id` (`create_machine_event` R1). |
| BUG-1140 | `machine_activity_manager.cases.md` (GS-12 … GS-15) | Unreachable here: the service reads the status of a machine already found in its own workspace (`_to_machine_response` Errors). |
| BUG-891 | `machine_manager.cases.md` (N-20) | Not observable through the service: a create or edit in a soft-deleted factory is refused first (BUG-963, BUG-964), so the name check's answer there never shows. |
| BUG-957 strict `ORDER BY` recorder | `machine_manager.cases.md` S-112 | The query is the manager's; L-20 here is the pass-through. |
| BUG-1090 strict `ORDER BY` recorder | `machine_activity_manager.cases.md` SM-14 | The query is the manager's; L-21 here is the pass-through. |
| `create_machine_event` D1 — the path id replaces the body's `machine_id` | `POST /machines/{id}/events/` (integration) | Integration-only. |
| HR-7 and `1 <= within_days <= 365` | `GET /machines/`, `/activity/`, `/upcoming-work/` | Endpoint bounds; called directly, negative values reach the database. |
| `IntegrityError` → global 409; schema errors 422 (BUG-461); response serialisation | API handlers (integration) | Integration-only. |
| BUG-969 | frontend | No backend case. |
| Every other manager rule beyond one pass-through per bug | `machine_manager.cases.md`, `machine_activity_manager.cases.md` | Not re-tested here. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_machine_activity` R1, R3 (BUG-1141) | Whether the service's shaping (`performer_name`, `metadata`) issues any statement of its own beyond `list_events`. | MCS-A-13 assumes none and keeps the manager's bound of 3 statements; if shaping reads, the bound must be raised. Not blocking. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_to_machine_response` | R1 | MCS-R-01, MCS-R-02 |
| `_to_machine_response` | R2 | MCS-R-01, MCS-R-03 |
| `_to_machine_response` | R3 | MCS-R-04, MCS-R-05 |
| `_to_machine_response` | R4 | MCS-R-01, MCS-R-03, MCS-R-04, MCS-R-06, MCS-R-07 |
| `_to_machine_response` | R5 | MCS-R-08, MCS-U-07, MCS-D-06 |
| `_to_machine_responses` | R1 | MCS-RS-01, MCS-L-22 |
| `_to_machine_responses` | R2 | MCS-RS-02, MCS-L-23 |
| `_to_machine_responses` | R2 [BUG-1090] | MCS-L-21 |
| `create_machine` | R1 | MCS-C-01 |
| `create_machine` | R1 [BUG-950] | MCS-C-09 |
| `create_machine` | R1 [BUG-951] | MCS-C-15 |
| `create_machine` | R1 [BUG-952] | MCS-C-10 |
| `create_machine` | R1 [BUG-953] | MCS-C-12 |
| `create_machine` | R1 [BUG-967] | MCS-C-11 |
| `create_machine` | R1 [BUG-972] | MCS-C-14 |
| `create_machine` | R2 | MCS-C-02, MCS-C-03, MCS-C-04, MCS-C-05 |
| `create_machine` | R2 [BUG-963] | MCS-C-13 |
| `create_machine` | R3 | MCS-C-06, MCS-C-07, MCS-C-08 |
| `get_machine` | R1 | MCS-G-01 |
| `get_machine` | R2 [BUG-955] | MCS-G-04 |
| `get_machine` | R3 [BUG-955] | MCS-G-05, MCS-G-06 |
| `get_machine` | R4 [BUG-966] | MCS-G-07, MCS-G-08 |
| `get_machine` | R5 | MCS-G-02, MCS-G-03, MCS-G-09 |
| `get_machine` | Errors row 1 | MCS-G-02, MCS-G-03, MCS-G-04, MCS-G-06, MCS-G-07 |
| `get_machine` | Errors row 2 | MCS-R-08 |
| `get_machines` | R1 | MCS-L-01, MCS-L-02, MCS-L-03, MCS-L-04, MCS-L-05, MCS-L-06, MCS-L-07, MCS-L-08, MCS-L-22, MCS-L-23 |
| `get_machines` | R1 [BUG-886] | MCS-L-12 |
| `get_machines` | R1 [BUG-887] | MCS-L-13 |
| `get_machines` | R1 [BUG-888] | MCS-L-14 |
| `get_machines` | R1 [BUG-889] | MCS-L-15 |
| `get_machines` | R1 [BUG-890] | MCS-L-16 |
| `get_machines` | R1 [BUG-892] | MCS-L-17 |
| `get_machines` | R1 [BUG-957] | MCS-L-20 |
| `get_machines` | R1 [BUG-958] | MCS-L-18 |
| `get_machines` | R1 [BUG-973] | MCS-L-19 |
| `get_machines` | R1 [BUG-1090] | MCS-L-21 |
| `get_machines` | R2 | MCS-L-09 |
| `get_machines` | R2 [BUG-956] | MCS-L-10, MCS-L-20 |
| `get_machines` | R3 | MCS-L-11 |
| `get_machines` | R4 [BUG-1570] | Deferred (integration) |
| `get_upcoming_work` | R1 | MCS-W-01, MCS-W-02, MCS-W-03, MCS-W-04, MCS-W-05 |
| `get_upcoming_work` | R2 | MCS-W-01, MCS-W-04, MCS-W-06, MCS-W-07 |
| `get_upcoming_work` | R3 | MCS-W-08, MCS-W-09 |
| `get_upcoming_work` | R4 | MCS-W-10, MCS-W-11 |
| `get_upcoming_work` | R5 | MCS-W-11 |
| `get_upcoming_work` | R6 [BUG-1571] | MCS-W-12 |
| `get_upcoming_work` | R7 [BUG-1572] | MCS-W-13 |
| `get_upcoming_work` | R8 | MCS-W-14 |
| `update_machine` | R1 | MCS-U-01 |
| `update_machine` | R1 [BUG-959] | MCS-U-09 |
| `update_machine` | R1 [BUG-962] | MCS-U-11 |
| `update_machine` | R1 [BUG-970] | MCS-U-13 |
| `update_machine` | R1 [BUG-971] | MCS-U-14 |
| `update_machine` | R1 [BUG-975] | MCS-U-15 |
| `update_machine` | R1 (BUG-950 … BUG-953, BUG-963, BUG-967, BUG-972 shared with create) | MCS-C-09 … MCS-C-15 (one pass-through per bug) |
| `update_machine` | R2 | MCS-U-02, MCS-U-03, MCS-U-04, MCS-U-05, MCS-U-06 |
| `update_machine` | R2 [BUG-954] | MCS-U-08 |
| `update_machine` | R2 [BUG-961] | MCS-U-10 |
| `update_machine` | R2 [BUG-964] | MCS-U-12 |
| `update_machine` | R3 | MCS-U-07; MCS-C-06, MCS-C-07 (TC4, TC5 once per service) |
| `delete_machine` | R1 | MCS-D-01, MCS-D-02, MCS-D-03 |
| `delete_machine` | R1 [BUG-965] | MCS-D-07 |
| `delete_machine` | R2 [BUG-968] | MCS-D-04, MCS-D-05 |
| `delete_machine` | R3 | MCS-D-06, MCS-U-07 |
| `delete_machine` | R4 | MCS-D-06; MCS-C-06, MCS-C-07 (TC4, TC5 once per service) |
| `delete_machine` | Errors row 1 | MCS-D-03 |
| `delete_machine` | Errors row 2 | MCS-D-02 |
| `delete_machine` | Errors row 3 | MCS-D-07 |
| `delete_machine` | Errors row 4 | MCS-D-04, MCS-D-05 |
| `create_machine_event` | R1 | MCS-E-01 |
| `create_machine_event` | R1 [BUG-960] | MCS-E-05 |
| `create_machine_event` | R2 | MCS-E-02, MCS-E-03, MCS-E-04 |
| `create_machine_event` | R2 [BUG-974] | MCS-E-06 |
| `create_machine_event` | R3 | MCS-C-06 (TC4 once per service) |
| `get_machine_activity` | R1 | MCS-A-01, MCS-A-02, MCS-A-03 |
| `get_machine_activity` | R1a | MCS-A-14 |
| `get_machine_activity` | R1 [BUG-1141] | MCS-A-13 |
| `get_machine_activity` | R2 | MCS-A-04, MCS-A-05, MCS-A-12 |
| `get_machine_activity` | R3 | MCS-A-01 |
| `get_machine_activity` | R4 | MCS-A-06, MCS-A-07, MCS-A-08, MCS-A-09 |
| `get_machine_activity` | R5 | MCS-A-10 |
| `get_machine_activity` | R6 | MCS-A-11 |
| Transaction contract | TC1 | MCS-C-01, MCS-U-01, MCS-D-01, MCS-E-01 |
| Transaction contract | TC2 | MCS-C-01, MCS-C-07 |
| Transaction contract | TC3 | MCS-C-02, MCS-C-05, MCS-U-02, MCS-D-02, MCS-E-02 |
| Transaction contract | TC4 | MCS-C-06 |
| Transaction contract | TC5 | MCS-C-07 |
| Transaction contract | TC6 | MCS-G-09, MCS-L-11, MCS-W-14, MCS-A-11 |
