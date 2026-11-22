# Test cases — `app/managers/machine_maintenance_log_manager.py`

> **Spec:** `tests/unit/managers/machine_maintenance_log_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 (2026-11-01) — additive, from `machine_maintenance_log_manager.verify.md`; the spec did not change. Finding 1 → MMLM-L-136, MMLM-L-137 (a W2 row on a W1 machine on the no-filter and by-type paths). Finding 2 → MMLM-U-121 (100 000-character `summary` on update). Finding 3 is optional and not taken. No existing card, Convention or ID changed, none retired.
> **Counts:** 397 cases · 283 expected-to-pass · 114 expected-to-fail (bugs) · 13 deferred

## Reviewer summary
- **Per callable:** `create_log` 81 (26 bug) · `update_log` 121 (52 bug) · `get_log` 24 (10 bug) · `list_logs` 137 (21 bug) · `delete_log` 34 (5 bug).
- **Depth:** full (owner, spec Q6: maintenance logging is live). Every path of `list_logs` gets its own cards, because each is its own DAO query.
- **Expected-to-fail by bug:** BUG-1100 12 · BUG-1101 14 · BUG-1102 1 · BUG-1150 9 · BUG-1151 11 · BUG-1152 3 · BUG-1153 7 · BUG-1154 3 · BUG-1155 10 · BUG-1156 14 · BUG-1157 26 · BUG-1158 4. 8 of the 114 are non-strict (physical order); all others strict. BUG-1159 is frontend: no card.
- **Notable design choices:**
  - **Beyond the spec's "one pass-through" for BUG-1100 and BUG-1101:** the order cards and the leak cards run on all four list paths, and BUG-1101 on get, update and delete, because verifiers keep returning exactly these. Each path has a non-strict tie card, a non-strict tie card with `skip=1, limit=1`, and one strict recorder.
  - **Filter before paging:** the hidden row is ahead of the skipped row, with `skip=1` and with `limit=1`, on every path. For a machine path the BUG-1101 version is left out: one machine's rows are all linked or all not, so it would be equivalent (DAO verify).
  - **No-op matrix:** empty body, same five values, `null` on empty fields, `5.000` on `5.00`, each by four cards: no entry; never stamped; by the user already stamped (a **pass** card, no UPDATE today); by another user (xfail BUG-1151).
  - **Parents:** soft-deleted machine, machine in a soft-deleted factory, only-deactivated machine, machine in an only-deactivated factory are separate cards on every callable. On update, delete and get, the two only-deactivated cards rest on "the machine is not read" (Q3, Q4, Branch map), not on a rule that names them.
  - **Cost:** every value on both Create and Update. `-1.005` and `-0.001` are left out on purpose: both limits refuse them, so a strict card would XPASS when only one bug is fixed. All cost values were tried on a schema of my own with the spec's limits.
  - **Two bugs in one card:** the padded-no-change cards (BUG-1155, BUG-1156) also need BUG-1151; the `include_deleted=True` cards of BUG-1101 also need BUG-1150. They stay xfail until both are fixed.
  - **R15** "does not change the machine's status" is checked as no `status_updated` row and `unchanged(M1)`, not by calling `get_latest_status`.
  - **Nothing leaked:** exact equality on `detail`, with the id sent, on every cross-workspace refusal; a separate text search could not fail on its own. A soft-deleted row of another workspace gets the 404, not the 400, so its state does not show either.
  - Keyword forms the service uses have one card per callable. `Author:` lines are not used; a Claude subagent writes the whole file.
- **Needs a decision:** None blocking. Spec gaps 1, 2, 3 are money readings worth a look.

## Conventions for this module

**IDs.** `MMLM` = `app/managers/machine_maintenance_log_manager.py`. `C` create_log · `U` update_log · `G` get_log · `L` list_logs · `D` delete_log.

**Actors and fixed values.**
- `M` = the singleton `machine_maintenance_log_manager` (`from app.managers.machine_maintenance_log_manager import machine_maintenance_log_manager`). `db` = the test's real session, always the first argument. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2, U3 = three `profiles` rows, from `tests/unit/factories.py`. U1 is `created_by` of every Given log, U2 the acting user unless the When says otherwise, U3 an earlier editor.
- `LC`, `LU`, `LR` = `MachineMaintenanceLogCreate`, `MachineMaintenanceLogUpdate`, `MachineMaintenanceLogResponse` (`app.schemas.machine_maintenance_log`). `MachineMaintenanceLog` (`app.models.machine_maintenance_log`), `MachineActivityEvent` (`app.models.machine_activity_event`), `MaintenanceTypeEnum` (`app.models.enums`); `REPAIR` = `MaintenanceTypeEnum.REPAIR`. `Decimal` (`decimal`), `date`, `timedelta` (`datetime`), `HTTPException` (`fastapi`).
- MISSING = `999999999`: an id no row of any table has. D1, D2, D3 = `date(2026, 3, 1)`, `date(2026, 3, 2)`, `date(2026, 3, 3)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. NOW = `datetime(2031, 5, 6, 7, 8, 9)` (naive).
- Money compares by value (`Decimal`); `str(cost) == "5.00"` is used where the form is part of the check.
- **Two "performed by":** on the log, free text; on the entry, the acting user's profile id.

**Externals.** None is mocked, except **clock patch**, on the one card that names it: `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)`, active during the When. `created_at` on an entry is checked as set.

**Standing rows.** In every test, in this order, no Given line needed; `is_active True`, `is_deleted False`, `workspace_id W1.id` unless stated. Workspaces and profiles from the factories, the rest built directly. A card may name one as a reminder.
- Factories: F1 `"Factory One"` / `"F1"`. FD `"Old Plant"` / `"OP"`, `is_deleted True` (`is_active` stays True). FI `"Idle Plant"` / `"IP"`, `is_active False`. F9 `"Factory Nine"` / `"F9"`, `workspace_id W2.id`.
- Machines of F1: M1 `"Press 1"`. M2 `"Press 2"`. MD `"Press 4"`, `is_deleted True`, `is_active False` (soft-deleted). MA `"Idle Press"`, `is_active False` (only deactivated). Machines elsewhere: MF `"Lost Press"` of FD (live, soft-deleted factory). MG `"Quiet Press"` of FI (live, only deactivated factory). M9 `"Far Press"` of F9, `workspace_id W2.id`.
- "The same as M1, but …" in a Given builds one more `machines` row: `workspace_id W1.id`, `factory_id F1.id`, the columns named. The same for "the same as M9", "the same as F1".

**Given rows.** Built directly, never through `M` unless the line is written as code, flushed one at a time in the order written, so ids rise in that order. A line written as code is a step to run exactly, at that place. No log exists unless a Given line builds it. Rows of W1 on a W2 machine, and of W2 on a W1 machine, are invalid data, built only to prove they are hidden.
- **log** = `machine_maintenance_logs` row: `workspace_id W1.id`, `machine_id M1.id`, `maintenance_type REPAIR`, `maintenance_date D1`, `summary "Bearing change"`, `created_by U1.id`, every other column left to its default. After "but" the card lists every column that differs. Each log gets `db.refresh(row)` right after its flush, so `cost` holds the stored form.
- **gone** (after "but") = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **pending log** Q = `Q = MachineMaintenanceLog(workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Pending")`, then `db.add(Q)`, never flushed. Last Given line; row counts and snapshots are taken before it is added.
- **bulk101** = `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`, `created_by U1.id`. `all_ids = [r.id for r in rows]` after the flush.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line). **unchanged(X) except `c`, …** leaves out the columns named. X may be any row, a machine too.
- **nothing written** = the row counts of `machine_maintenance_logs` and `machine_activity_events` (all workspaces) equal their values before the call.
- **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`. "that row" = the one row just counted. `metadata_json` is compared as a whole dict, order of `changes` included.
- **ids(x)** = `[r.id for r in x]`, in the order returned. `sorted(ids(result))` where order is not part of the check; right-hand ids are in Given order.
- `count:` lines count rows in all workspaces, with the filter stated, by a fresh query.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint, because a savepoint's rollback would hide a write. The rest of the `raises:` lines are assertions on `exc.value` after the block, one per line.
- `raises: IntegrityError`, `raises: DataError` (`sqlalchemy.exc`): `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call. `ForeignKeyViolation` = `psycopg2.errors.ForeignKeyViolation`.
- `raises: ValidationError` = `pydantic.ValidationError` around the schema's construction; the manager is not called.
- `session:` lines run on `db` directly, before any re-read: one `assert` each; "`db.refresh(x)` runs and raises nothing" is the bare call.

**Targets.** "target `schema`" = the When only builds or reads the schema object.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy wrapping `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks. One per writer.

**sql_log.** A list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call. Each entry is the statement text. `sql` = the last entry containing `FROM machine_maintenance_logs`. `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none). `statement:` lines are checks on these.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `MachineMaintenanceLogManager.create_log`

### MMLM-C-01 — a log with all six fields is stored
- **Rules:** `create_log` R5, `create_log` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("4000.50"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineMaintenanceLog)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `maintenance_type == REPAIR`, `maintenance_date == D1`.
4. re-read the returned row: `summary == "Bearing change"`, `cost == Decimal("4000.50")`, `performed_by == "Rahim"`.
5. re-read the returned row: `created_by == U2.id`, `created_at is not None`.
6. re-read the returned row: `is_active is True`, `is_deleted is False`.
7. re-read the returned row: `updated_at is None`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`.
8. count: `machine_maintenance_logs` has exactly 1 row.

### MMLM-C-02 — cost and performed_by omitted are NULL
- **Rules:** `create_log` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost is None`, `performed_by is None`.

### MMLM-C-03 — the service's keyword call works
- **Rules:** `create_log` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(session=db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `created_by == U2.id`, `workspace_id == W1.id`.

### MMLM-C-04 — workspace comes from the argument: keys in the body are dropped
- **Rules:** `create_log` R5, `create_log` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", workspace_id=W2.id, created_by=U3.id, is_deleted=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `created_by == U2.id`, `is_deleted is False`.
3. count: `machine_maintenance_logs` rows with `workspace_id == W2.id`: exactly 0.

### MMLM-C-05 — a second log on the same machine, date and type is stored: no duplicate check
- **Rules:** `create_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != A.id`.
2. count: `machine_maintenance_logs` rows with `machine_id == M1.id`: exactly 2.
3. unchanged: unchanged(A).

### MMLM-C-06 — an unknown machine gets the 404
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=MISSING, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.

### MMLM-C-07 — machine id 0 gets the 404
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=0, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 0 not found"`.
4. nothing written: nothing written.

### MMLM-C-08 — a negative machine id gets the 404
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=-1, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID -1 not found"`.
4. nothing written: nothing written.

### MMLM-C-09 — another workspace's machine gets the same 404 and no write in either workspace
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=M9.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.
5. event: events_of(M9) has exactly 0 rows.
6. unchanged: unchanged(M9).

### MMLM-C-10 — a machine of W1 asked for from W2 gets the same 404
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M1.id} not found"`.
4. nothing written: nothing written.

### MMLM-C-11 — a soft-deleted machine of another workspace cannot be told from a missing one: 404, not 400
- **Rules:** `create_log` R1, `create_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9D = the same as M9, but `name "Far Gone"`, `is_deleted True`, `is_active False`.

**When**
- `M.create_log(db, log_data=LC(machine_id=M9D.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9D.id} not found"`.
4. nothing written: nothing written.

### MMLM-C-12 — a soft-deleted machine is refused
- **Rules:** `create_log` R2, `create_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=MD.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MD).

### MMLM-C-13 — a soft-deleted machine still marked active is refused
- **Rules:** `create_log` R2, `create_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MDA = the same as M1, but `name "Half Gone"`, `is_deleted True`, `is_active True`.

**When**
- `M.create_log(db, log_data=LC(machine_id=MDA.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MMLM-C-14 — a soft-deleted machine in a soft-deleted factory gets the same refusal
- **Rules:** `create_log` R2, `create_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MDF = the same as M1, but `name "Both Gone"`, `factory_id FD.id`, `is_deleted True`, `is_active False`.

**When**
- `M.create_log(db, log_data=LC(machine_id=MDF.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MMLM-C-15 — a live machine in a soft-deleted factory is refused like a deleted machine
- **Rules:** `create_log` R3 [BUG-1154], `create_log` Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1154
- **Fails today on:** Then 1 (no error is raised: the factory is not read, the log and its entry are stored)

**Given**
1. MF (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=MF.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.
5. event: events_of(MF) has exactly 0 rows.
6. unchanged: unchanged(MF).

### MMLM-C-16 — a machine marked inactive in a soft-deleted factory is refused too
- **Rules:** `create_log` R3 [BUG-1154], `create_log` Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1154
- **Fails today on:** Then 1 (no error is raised: the factory is not read, the log and its entry are stored)

**Given**
1. MFI = the same as M1, but `name "Dim Press"`, `factory_id FD.id`, `is_active False`.

**When**
- `M.create_log(db, log_data=LC(machine_id=MFI.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MMLM-C-17 — a soft-deleted factory also marked inactive refuses too
- **Rules:** `create_log` R3 [BUG-1154], `create_log` Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1154
- **Fails today on:** Then 1 (no error is raised: the factory is not read, the log and its entry are stored)

**Given**
1. FX = the same as F1, but `name "Shut Plant"`, `abbreviation "SP"`, `is_deleted True`, `is_active False`.
2. MX = the same as M1, but `name "Shut Press"`, `factory_id FX.id`.

**When**
- `M.create_log(db, log_data=LC(machine_id=MX.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create maintenance log for a deleted machine"`.
4. nothing written: nothing written.

### MMLM-C-18 — an inactive machine is accepted, with its entry
- **Rules:** `create_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=MA.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MA.id`, `is_active is True`, `is_deleted is False`.
3. event: events_of(MA) has exactly 1 row.
4. event: that row: `event_type == "maintenance_logged"`, `description == "Maintenance logged: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MA.id`.
5. unchanged: unchanged(MA).

### MMLM-C-19 — a machine in an inactive factory is accepted, with its entry
- **Rules:** `create_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MG (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=MG.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MG.id`, `is_active is True`, `is_deleted is False`.
3. event: events_of(MG) has exactly 1 row.
4. event: that row: `event_type == "maintenance_logged"`, `description == "Maintenance logged: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MG.id`.
5. unchanged: unchanged(MG).

### MMLM-C-20 — an inactive machine in an inactive factory is accepted
- **Rules:** `create_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MAG = the same as M1, but `name "Dim Quiet"`, `factory_id FI.id`, `is_active False`.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=MAG.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MAG.id`.
3. event: events_of(MAG) has exactly 1 row.

### MMLM-C-21 — the returned object keeps cost as given until a refresh
- **Rules:** `create_log` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `str(result.cost) == "5.000"`.
2. session: `db.refresh(result)` runs and raises nothing.
3. returns: `str(result.cost) == "5.00"`.

### MMLM-C-22 — a padded summary is stored and repeated trimmed
- **Rules:** `create_log` R8 [BUG-1155]
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (the summary is stored with its spaces)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `summary == "pad"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_logged"`, `description == "Maintenance logged: pad"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.

### MMLM-C-23 — trimming keeps inner whitespace
- **Rules:** `create_log` R8 [BUG-1155]
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (the summary is stored with its spaces)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="  pad  line  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `summary == "pad  line"`.

### MMLM-C-24 — tabs and new lines around a summary are trimmed too
- **Rules:** `create_log` R8 [BUG-1155]
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (the summary is stored as given)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="\tpad\n"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `summary == "pad"`.

### MMLM-C-25 — inner whitespace of a summary with no padding is kept as typed
- **Rules:** `create_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing  change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `summary == "Bearing  change"`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "maintenance_logged"`, `description == "Maintenance logged: Bearing  change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.

### MMLM-C-26 — a one-character summary is accepted: the other side of empty
- **Rules:** `create_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="a"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `summary == "a"`.

### MMLM-C-27 — an empty summary is refused by the schema
- **Rules:** `create_log` R8 [BUG-1155], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 1 (the schema has no check, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-28 — a whitespace-only summary is refused by the schema
- **Rules:** `create_log` R8 [BUG-1155], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 1 (the schema has no check, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="   ")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-29 — a summary of tabs and new lines is refused by the schema
- **Rules:** `create_log` R8 [BUG-1155], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 1 (the schema has no check, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="\t\n ")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-30 — a summary of 100 000 characters is stored and copied into the entry
- **Rules:** `create_log` R8b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="S" * 100000), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `summary == "S" * 100000`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `description == "Maintenance logged: " + "S" * 100000`.

### MMLM-C-31 — a padded performed_by is stored trimmed
- **Rules:** `create_log` R8a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="  Rahim  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by == "Rahim"`.

### MMLM-C-32 — an empty performed_by is stored as NULL
- **Rules:** `create_log` R8a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored as given)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by is None`.

### MMLM-C-33 — a whitespace-only performed_by is stored as NULL
- **Rules:** `create_log` R8a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored as given)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="   "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by is None`.

### MMLM-C-34 — a plain performed_by is stored as typed, inner whitespace kept
- **Rules:** `create_log` R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="Rahim  Uddin"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `performed_by == "Rahim  Uddin"`.

### MMLM-C-35 — performed_by of 255 characters is stored
- **Rules:** `create_log` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="x" * 255), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `performed_by == "x" * 255`.

### MMLM-C-36 — performed_by of 256 characters is refused by the schema
- **Rules:** `create_log` R9a [BUG-1156], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="x" * 256)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-37 — 256 characters inside surrounding spaces are refused: the limit is on the trimmed value
- **Rules:** `create_log` R9a [BUG-1156], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=" " + "x" * 256 + " ")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-38 — 255 characters inside surrounding spaces are accepted and stored trimmed
- **Rules:** `create_log` R9a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the call raises DataError: 257 characters reach the column)

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by=" " + "x" * 255 + " "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by == "x" * 255`.

### MMLM-C-39 — cost 0 is accepted and stored as 0.00: zero is a value, not an empty field
- **Rules:** `create_log` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "0.00"`.

### MMLM-C-40 — cost -0 is accepted and stored as 0.00: minus zero passes the minimum
- **Rules:** `create_log` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "0.00"`.

### MMLM-C-41 — cost 0.01 is accepted and stored as 0.01: the smallest cost above zero
- **Rules:** `create_log` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("0.01")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "0.01"`.

### MMLM-C-42 — cost 5 is accepted and stored as 5.00: no decimals
- **Rules:** `create_log` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "5.00"`.

### MMLM-C-43 — cost 5.1 is accepted and stored as 5.10: one decimal, as a JSON number
- **Rules:** `create_log` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=5.1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "5.10"`.

### MMLM-C-44 — cost 5.00 is accepted and stored as 5.00: two decimals
- **Rules:** `create_log` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "5.00"`.

### MMLM-C-45 — cost 5.000 is accepted and stored as 5.00: a trailing zero does not count
- **Rules:** `create_log` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "5.00"`.

### MMLM-C-46 — cost 9999999999999 is accepted and stored as 9999999999999.00: 13 integer digits
- **Rules:** `create_log` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "9999999999999.00"`.

### MMLM-C-47 — cost 9999999999999.99 is accepted and stored as 9999999999999.99: the column's limit
- **Rules:** `create_log` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.99")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "9999999999999.99"`.

### MMLM-C-48 — cost 9999999999999.990 is accepted and stored as 9999999999999.99: the limit with a trailing zero
- **Rules:** `create_log` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.990")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `str(cost) == "9999999999999.99"`.

### MMLM-C-49 — cost -5 is refused by the schema
- **Rules:** `create_log` R11a [BUG-1158], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1158
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-5"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-50 — cost -0.01 is refused by the schema
- **Rules:** `create_log` R11a [BUG-1158], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1158
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("-0.01"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-51 — cost 10000000000000 is refused by the schema
- **Rules:** `create_log` R10a [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-52 — cost 10000000000000.00 is refused by the schema
- **Rules:** `create_log` R10a [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("10000000000000.00"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-53 — cost 1E+13 is refused by the schema
- **Rules:** `create_log` R10a [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1E+13"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-54 — cost 1e20 is refused by the schema
- **Rules:** `create_log` R10a [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1e20"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-55 — cost 5.001 is refused by the schema
- **Rules:** `create_log` R12 [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.001"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-56 — cost 5.0010 is refused by the schema
- **Rules:** `create_log` R12 [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.0010"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-57 — cost 0.125 is refused by the schema
- **Rules:** `create_log` R12 [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("0.125"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-58 — cost 1E-7 is refused by the schema
- **Rules:** `create_log` R12 [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("1E-7"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-59 — cost 9999999999999.995 is refused by the schema
- **Rules:** `create_log` R12 [BUG-1157], `create_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("9999999999999.995"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-60 — a row already negative stays readable through the response schema
- **Rules:** `create_log` R11a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("-5.00")`.

**When**
- `result = LR.model_validate(A, from_attributes=True)` (target `schema`; `M` is not called).

**Then**
1. returns: `result.cost == Decimal("-5.00")`.
2. unchanged: unchanged(A).

### MMLM-C-61 — a row already blank or padded stays readable through the response schema
- **Rules:** `create_log` FU-2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `summary "   "`, `performed_by "  Rahim  "`.

**When**
- `result = LR.model_validate(A, from_attributes=True)` (target `schema`; `M` is not called).

**Then**
1. returns: `result.summary == "   "`.
2. returns: `result.performed_by == "  Rahim  "`.

### MMLM-C-62 — a date in 1900 is stored: no bound
- **Rules:** `create_log` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=date(1900, 1, 1), summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `maintenance_date == date(1900, 1, 1)`.
2. event: events_of(M1) has exactly 1 row.

### MMLM-C-63 — a date in 2099 is stored: no bound
- **Rules:** `create_log` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=date(2099, 1, 1), summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `maintenance_date == date(2099, 1, 1)`.
2. event: events_of(M1) has exactly 1 row.

### MMLM-C-64 — cost NaN is refused by the schema: not a number
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("NaN"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-65 — cost Infinity is refused by the schema: infinity
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("Infinity"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-66 — a type name that is no member is refused by the schema
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type="BOGUS", maintenance_date=D1, summary="Bearing change")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-67 — machine_id is required by the schema
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-68 — maintenance_type is required by the schema
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_date=D1, summary="Bearing change")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-69 — maintenance_date is required by the schema
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, summary="Bearing change")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-70 — summary is required by the schema
- **Rules:** `create_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### MMLM-C-71 — one maintenance_logged entry with every field; cost and the free-text name are not in it
- **Rules:** `create_log` R14, `create_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("4000.50"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "maintenance_logged"`, `description == "Maintenance logged: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
4. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}`.
5. event: that row: `created_at is not None`.
6. event: events_of(M2) has exactly 0 rows.

### MMLM-C-72 — the entry's performed_by is the acting user, never the free-text name
- **Rules:** `create_log` R14
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", performed_by="Rahim"), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by == "Rahim"`, `created_by == U3.id`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `performed_by == U3.id`.

### MMLM-C-73 — the machine row is not touched
- **Rules:** `create_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(M1).

### MMLM-C-74 — metadata status holds PREVENTIVE
- **Rules:** `create_log` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.PREVENTIVE, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "PREVENTIVE"}`.

### MMLM-C-75 — metadata status holds REPAIR
- **Rules:** `create_log` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}`.

### MMLM-C-76 — metadata status holds EMERGENCY
- **Rules:** `create_log` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "EMERGENCY"}`.

### MMLM-C-77 — metadata status holds INSPECTION
- **Rules:** `create_log` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.INSPECTION, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "INSPECTION"}`.

### MMLM-C-78 — a plain string type gives the same text
- **Rules:** `create_log` R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.
2. Pydantic's serializer warning filtered for this test: `warnings.catch_warnings()` with `warnings.simplefilter("ignore", UserWarning)` around the When.

**When**
- `result = M.create_log(db, log_data=LC.model_construct(machine_id=M1.id, maintenance_type="REPAIR", maintenance_date=D1, summary="Bearing change", cost=None, performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read the returned row: `maintenance_type == REPAIR`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": result.id, "status": "REPAIR"}`.

### MMLM-C-79 — metadata status is no machine status: no status event, machine as it was
- **Rules:** `create_log` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_activity_events` rows with `event_type == "status_updated"`: exactly 0.
3. unchanged: unchanged(M1).

### MMLM-C-80 — an unknown user: foreign key error, no log and no entry
- **Rules:** `create_log` R16, `create_log` Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing); no log exists.

**When**
- `M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_maintenance_logs_created_by_fkey"`.
4. nothing written: nothing written.

### MMLM-C-81 — flushed, never committed
- **Rules:** `create_log` R17, `create_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_maintenance_logs` has exactly 1 row.
3. count: `machine_activity_events` has exactly 1 row.
4. count after the savepoint rollback: `machine_maintenance_logs` has exactly 0 rows.
5. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

## `MachineMaintenanceLogManager.update_log`

### MMLM-U-01 — a changed summary is written, stamped and recorded
- **Rules:** `update_log` R6, `update_log` R10, `update_log` R11, `update_log` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. re-read A: `updated_by == U2.id`, `updated_at is not None`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
6. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}]}`.
7. event: that row: `created_at is not None`.

### MMLM-U-02 — the service's keyword call works
- **Rules:** `update_log` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(session=db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.

### MMLM-U-03 — a log of another workspace gets the 404 and nothing is written
- **Rules:** `update_log` R1, `update_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.
6. event: events_of(M1) has exactly 0 rows.

### MMLM-U-04 — a soft-deleted log of another workspace gets the same 404, not the 400
- **Rules:** `update_log` R1, `update_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-U-05 — an unknown id gets the same 404
- **Rules:** `update_log` R1, `update_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.update_log(db, log_id=MISSING, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 999999999 not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-U-06 — id 0 gets the same 404
- **Rules:** `update_log` R1, `update_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.update_log(db, log_id=0, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 0 not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-U-07 — a soft-deleted log is refused with a change
- **Rules:** `update_log` R2, `update_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted maintenance log"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.
6. event: events_of(M1) has exactly 0 rows.

### MMLM-U-08 — a soft-deleted log is refused with an empty body too
- **Rules:** `update_log` R2, `update_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted maintenance log"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-U-09 — a log on another workspace's machine gets the 404 and that machine no entry
- **Rules:** `update_log` R3 [BUG-1101], `update_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (no error is raised: the log's machine is not checked)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.update_log(db, log_id=X.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.
6. event: events_of(M9) has exactly 0 rows.

### MMLM-U-10 — the same row with an empty body gets the 404 too
- **Rules:** `update_log` R3 [BUG-1101], `update_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (no error is raised: the log's machine is not checked)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.update_log(db, log_id=X.id, log_data=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.

### MMLM-U-11 — a soft-deleted log on another workspace's machine answers 404, not 400
- **Rules:** `update_log` R3 [BUG-1101], `update_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 2 (today 400: the row is found and its own flag answers)

**Given**
1. X = log, but `machine_id M9.id`, gone.

**When**
- `M.update_log(db, log_id=X.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.

### MMLM-U-12 — the same row asked for from the machine's workspace gets the 404
- **Rules:** `update_log` R3, `update_log` R1, `update_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.update_log(db, log_id=X.id, log_data=LU(summary="New text"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.
6. event: events_of(M9) has exactly 0 rows.

### MMLM-U-13 — an inactive log is updated and stays inactive
- **Rules:** `update_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`, `is_active is False`, `is_deleted is False`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-14 — a log of a soft-deleted machine is updated, and the entry goes to that machine
- **Rules:** `update_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. event: events_of(MD) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MD.id`.
5. unchanged: unchanged(MD).

### MMLM-U-15 — a log of a machine in a soft-deleted factory is updated, and the entry goes to that machine
- **Rules:** `update_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. event: events_of(MF) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MF.id`.
5. unchanged: unchanged(MF).

### MMLM-U-16 — a log of an inactive machine is updated, and the entry goes to that machine
- **Rules:** `update_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MA.id`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. event: events_of(MA) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MA.id`.
5. unchanged: unchanged(MA).

### MMLM-U-17 — a log of a machine in an inactive factory is updated, and the entry goes to that machine
- **Rules:** `update_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. event: events_of(MG) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MG.id`.
5. unchanged: unchanged(MG).

### MMLM-U-18 — maintenance_type alone is written and listed; the entry's text keeps the stored summary
- **Rules:** `update_log` R6, `update_log` R11, `update_log` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=MaintenanceTypeEnum.EMERGENCY), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `maintenance_type == MaintenanceTypeEnum.EMERGENCY`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "maintenance_type", "label": "Maintenance type", "from_value": "REPAIR", "to_value": "EMERGENCY"}]}`.

### MMLM-U-19 — maintenance_date alone is written and listed; the entry's text keeps the stored summary
- **Rules:** `update_log` R6, `update_log` R11, `update_log` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_date=D2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `maintenance_date == D2`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2026-03-02"}]}`.

### MMLM-U-20 — cost alone is written and listed; the entry's text keeps the stored summary
- **Rules:** `update_log` R6, `update_log` R11, `update_log` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost == Decimal("7.50")`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}`.

### MMLM-U-21 — performed_by alone is written and listed; the entry's text keeps the stored summary
- **Rules:** `update_log` R6, `update_log` R11, `update_log` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="Karim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by == "Karim"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": "Karim"}]}`.

### MMLM-U-22 — a field omitted stays as it was
- **Rules:** `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `maintenance_type == REPAIR`, `maintenance_date == D1`, `cost == Decimal("5.00")`, `performed_by == "Rahim"`.
3. re-read A: `machine_id == M1.id`, `workspace_id == W1.id`, `created_by == U1.id`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}]}`.

### MMLM-U-23 — all five fields change: one entry, listed in field order whatever order they were sent in
- **Rules:** `update_log` R6, `update_log` R10, `update_log` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="Karim", cost=Decimal("7.50"), summary="New text", maintenance_date=D2, maintenance_type=MaintenanceTypeEnum.EMERGENCY), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`, `cost == Decimal("7.50")`, `performed_by == "Karim"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "maintenance_type", "label": "Maintenance type", "from_value": "REPAIR", "to_value": "EMERGENCY"}, {"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2026-03-02"}, {"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}, {"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}, {"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": "Karim"}]}`.

### MMLM-U-24 — fields sent with their stored value are left out of changes
- **Rules:** `update_log` R12, `update_log` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("7.50"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}`.

### MMLM-U-25 — the entry records empty old values as None
- **Rules:** `update_log` R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "7.50"}, {"field": "performed_by", "label": "Performed by", "from_value": None, "to_value": "Rahim"}]}`.

### MMLM-U-26 — the entry shows the machine and workspace of the log, and the acting user
- **Rules:** `update_log` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `machine_id M2.id`, `created_by U1.id`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M2) has exactly 1 row.
3. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: New text"`, `performed_by == U3.id`, `workspace_id == W1.id`, `machine_id == M2.id`.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-27 — the machine is not touched when the date changes
- **Rules:** `update_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_date=D2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(M1).

### MMLM-U-28 — unaffected columns stay
- **Rules:** `update_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `summary`, `updated_by`, `updated_at`.

### MMLM-U-29 — cost 0 on a log at 5.00 is a value and is applied
- **Rules:** `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. re-read A: `updated_by == U2.id`.
4. event: events_of(M1) has exactly 1 row.

### MMLM-U-30 — cost 0.00 on a log with no cost is a change, listed from None
- **Rules:** `update_log` R6, `update_log` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "0.00"}]}`.

### MMLM-U-31 — null clears cost and the entry says None
- **Rules:** `update_log` R7 [BUG-1153]
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 2 (null is dropped, the old value stays)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost is None`.
3. re-read A: `updated_by == U2.id`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}]}`.

### MMLM-U-32 — null clears performed_by and the entry says None
- **Rules:** `update_log` R7 [BUG-1153]
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 2 (null is dropped, the old value stays)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by is None`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}`.

### MMLM-U-33 — null on both clears both, one entry
- **Rules:** `update_log` R7 [BUG-1153]
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 2 (null is dropped, the old value stays)

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost is None`, `performed_by is None`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}, {"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}`.

### MMLM-U-34 — null beside a changed field: both apply, listed in field order
- **Rules:** `update_log` R7 [BUG-1153]
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 2 (null is dropped, the old value stays)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost is None`.
3. re-read A: `summary == "New text"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "New text"}, {"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": None}]}`.

### MMLM-U-35 — null for maintenance_type is refused by the schema
- **Rules:** `update_log` R7a [BUG-1153], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 1 (the schema allows None, so the object is built)

**Given**
1. A = log.

**When**
- `LU(maintenance_type=None)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-36 — null for maintenance_date is refused by the schema
- **Rules:** `update_log` R7a [BUG-1153], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 1 (the schema allows None, so the object is built)

**Given**
1. A = log.

**When**
- `LU(maintenance_date=None)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-37 — null for summary is refused by the schema
- **Rules:** `update_log` R7a [BUG-1153], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1153
- **Fails today on:** Then 1 (the schema allows None, so the object is built)

**Given**
1. A = log.

**When**
- `LU(summary=None)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-38 — an empty body: no entry
- **Rules:** `update_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.

### MMLM-U-39 — an empty body on a never-stamped log: no stamp
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by is set on every call)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. re-read A: `updated_at is None`.
4. unchanged: unchanged(A).

### MMLM-U-40 — an empty body by the user already stamped: both stamps stay
- **Rules:** `update_log` R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. event: events_of(M1) has exactly 0 rows.
5. unchanged: unchanged(A).

### MMLM-U-41 — an empty body by another user: the stamps of the earlier user stay
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by becomes the acting user)

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. unchanged: unchanged(A).

### MMLM-U-42 — the same five values: no entry
- **Rules:** `update_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.

### MMLM-U-43 — the same five values on a never-stamped log: no stamp
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by is set on every call)

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. re-read A: `updated_at is None`.
4. unchanged: unchanged(A).

### MMLM-U-44 — the same five values by the user already stamped: both stamps stay
- **Rules:** `update_log` R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`, `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. event: events_of(M1) has exactly 0 rows.
5. unchanged: unchanged(A).

### MMLM-U-45 — the same five values by another user: the stamps of the earlier user stay
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by becomes the acting user)

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`, `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("5.00"), performed_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. unchanged: unchanged(A).

### MMLM-U-46 — null on empty fields: no entry
- **Rules:** `update_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.

### MMLM-U-47 — null on empty fields on a never-stamped log: no stamp
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by is set on every call)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. re-read A: `updated_at is None`.
4. unchanged: unchanged(A).

### MMLM-U-48 — null on empty fields by the user already stamped: both stamps stay
- **Rules:** `update_log` R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, performed_by=None), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. event: events_of(M1) has exactly 0 rows.
5. unchanged: unchanged(A).

### MMLM-U-49 — null on empty fields by another user: the stamps of the earlier user stay
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by becomes the acting user)

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=None, performed_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. unchanged: unchanged(A).

### MMLM-U-50 — cost 5.000 on 5.00: no entry
- **Rules:** `update_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.

### MMLM-U-51 — cost 5.000 on 5.00 on a never-stamped log: no stamp
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by is set on every call)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. re-read A: `updated_at is None`.
4. unchanged: unchanged(A).

### MMLM-U-52 — cost 5.000 on 5.00 by the user already stamped: both stamps stay
- **Rules:** `update_log` R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. event: events_of(M1) has exactly 0 rows.
5. unchanged: unchanged(A).

### MMLM-U-53 — cost 5.000 on 5.00 by another user: the stamps of the earlier user stay
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by becomes the acting user)

**Given**
1. A = log, but `cost Decimal("5.00")`, `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.
4. unchanged: unchanged(A).

### MMLM-U-54 — an empty body by an unknown user raises nothing
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 1 (the call raises IntegrityError: updated_by is set and flushed)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. event: events_of(M1) has exactly 0 rows.

### MMLM-U-55 — the same values by an unknown user raises nothing
- **Rules:** `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 1 (the call raises IntegrityError: updated_by is set and flushed)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="Bearing change"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by is None`.
3. event: events_of(M1) has exactly 0 rows.

### MMLM-U-56 — cost 5 on 5.00 is no change: compared by value
- **Rules:** `update_log` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.
3. re-read A: `str(cost) == "5.00"`.

### MMLM-U-57 — cost 5.0 on 5.00 is no change: compared by value
- **Rules:** `update_log` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.
3. re-read A: `str(cost) == "5.00"`.

### MMLM-U-58 — cost 5.00 on 5.00 is no change: compared by value
- **Rules:** `update_log` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.
3. re-read A: `str(cost) == "5.00"`.

### MMLM-U-59 — cost -0 on 0.00 is no change: compared by value
- **Rules:** `update_log` R9, `update_log` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("0.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("-0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 0 rows.
3. re-read A: `str(cost) == "0.00"`.

### MMLM-U-60 — cost 5 on 5.00 by another user leaves the stamps
- **Rules:** `update_log` R9, `update_log` R8a [BUG-1151]
- **Kind:** bug
- **Expect:** xfail BUG-1151
- **Fails today on:** Then 2 (updated_by becomes the acting user)

**Given**
1. A = log, but `cost Decimal("5.00")`, `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at == T0`.

### MMLM-U-61 — a real change by the user already stamped issues the update
- **Rules:** `update_log` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U3.id`.
3. re-read A: `updated_at != T0`.
4. re-read A: `updated_at is not None`.
5. event: events_of(M1) has exactly 1 row.

### MMLM-U-62 — a real change by another user moves both stamps
- **Rules:** `update_log` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_by == U2.id`.
3. re-read A: `updated_at != T0`.
4. event: events_of(M1) has exactly 1 row.

### MMLM-U-63 — the same change sent again after a refresh writes no second entry
- **Rules:** `update_log` R8, `update_log` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.
2. `M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50")), workspace_id=W1.id, user_id=U2.id)`.
3. `db.refresh(A)`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.50"}]}`.

### MMLM-U-64 — two real changes write two entries, one each
- **Rules:** `update_log` R10, `update_log` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.
2. `M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50")), workspace_id=W1.id, user_id=U2.id)`.
3. `db.refresh(A)`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("8.25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 2 rows.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "7.50"`.
4. event: `events_of(M1)[1].metadata_json["changes"] == [{"field": "cost", "label": "Cost", "from_value": "7.50", "to_value": "8.25"}]`.

### MMLM-U-65 — cost 7 on 5.00: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "7.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.00"}]}`.

### MMLM-U-66 — cost 7.1 on 5.00: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.10"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "7.10"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "7.10"}]}`.

### MMLM-U-67 — cost 1E+3 on 0.13: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("0.13")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("1E+3")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "1000.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "1000.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "0.13", "to_value": "1000.00"}]}`.

### MMLM-U-68 — cost 5.000 on 7.00: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("7.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "5.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "5.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "7.00", "to_value": "5.00"}]}`.

### MMLM-U-69 — cost 0 on 5.00: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "0.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "0.00"}]}`.

### MMLM-U-70 — cost -0 on 5.00: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("-0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "0.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "0.00"}]}`.

### MMLM-U-71 — cost 7 on a log with no cost: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "7.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": None, "to_value": "7.00"}]}`.

### MMLM-U-72 — cost 7 on a log already negative: the entry shows the stored form
- **Rules:** `update_log` R12a [BUG-1157]
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 3 (`to_value` is as typed)

**Given**
1. A = log, but `cost Decimal("-5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.00"`.
3. event: `events_of(M1)[0].metadata_json["changes"][0]["to_value"] == "7.00"`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "7.00"}]}`.

### MMLM-U-73 — cost 7 on 5.00: the log, its stamp and the entry's old value hold whatever the form
- **Rules:** `update_log` R12a, `update_log` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.00"`.
3. re-read A: `updated_by == U2.id`.
4. event: events_of(M1) has exactly 1 row.
5. event: `events_of(M1)[0].metadata_json["changes"][0]["from_value"] == "5.00"`.

### MMLM-U-74 — the limit in two-decimal form is recorded as it stands
- **Rules:** `update_log` R12a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("9999999999999.99")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "9999999999999.99"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "5.00", "to_value": "9999999999999.99"}]}`.

### MMLM-U-75 — cost 0.01 is accepted and stored as 0.01
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("0.01")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.01"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-76 — cost 5 is accepted and stored as 5.00
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "5.00"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-77 — cost 5.1 is accepted and stored as 5.10
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=5.1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "5.10"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-78 — cost 5.00 is accepted and stored as 5.00
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "5.00"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-79 — cost 5.000 is accepted and stored as 5.00
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("5.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "5.00"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-80 — cost -0 is accepted and stored as 0.00
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("-0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-81 — cost 9999999999999 is accepted and stored as 9999999999999.00
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("9999999999999")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "9999999999999.00"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-82 — cost 9999999999999.990 is accepted and stored as 9999999999999.99
- **Rules:** `update_log` R14, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("1.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("9999999999999.990")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "9999999999999.99"`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-U-83 — cost -5 is refused by the schema
- **Rules:** `update_log` R13b [BUG-1158], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1158
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("-5"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-84 — cost -0.01 is refused by the schema
- **Rules:** `update_log` R13b [BUG-1158], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1158
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("-0.01"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-85 — cost 10000000000000 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-86 — cost 10000000000000.00 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("10000000000000.00"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-87 — cost 1E+13 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("1E+13"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-88 — cost 1e20 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("1e20"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-89 — cost 5.001 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("5.001"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-90 — cost 5.0010 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("5.0010"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-91 — cost 0.125 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("0.125"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-92 — cost 1E-7 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("1E-7"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-93 — cost 9999999999999.995 is refused by the schema
- **Rules:** `update_log` R14 [BUG-1157], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1157
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `LU(cost=Decimal("9999999999999.995"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-94 — a log already negative is edited to 0.00 like any other change
- **Rules:** `update_log` R13b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("-5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "0.00"`.
3. re-read A: `updated_by == U2.id`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "0.00"}]}`.

### MMLM-U-95 — a log already negative is edited to 7.50 like any other change
- **Rules:** `update_log` R13b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("-5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `str(cost) == "7.50"`.
3. re-read A: `updated_by == U2.id`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "cost", "label": "Cost", "from_value": "-5.00", "to_value": "7.50"}]}`.

### MMLM-U-96 — a log already negative can have another field edited: its cost stays
- **Rules:** `update_log` R13b, `update_log` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("-5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. re-read A: `str(cost) == "-5.00"`.
4. event: events_of(M1) has exactly 1 row.

### MMLM-U-97 — cost NaN is refused by the schema
- **Rules:** `update_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `LU(cost=Decimal("NaN"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-98 — cost Infinity is refused by the schema
- **Rules:** `update_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `LU(cost=Decimal("Infinity"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-99 — a type name that is no member is refused by the schema
- **Rules:** `update_log` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `LU(maintenance_type="BOGUS")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-100 — machine_id and updated_by in the body are dropped: the log's machine cannot change
- **Rules:** `update_log` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(machine_id=M2.id, updated_by=U3.id, summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `machine_id == M1.id`, `updated_by == U2.id`.
3. event: events_of(M1) has exactly 1 row.
4. event: events_of(M2) has exactly 0 rows.

### MMLM-U-101 — a padded summary is stored trimmed, in the entry's to_value and description too
- **Rules:** `update_log` R13 [BUG-1155]
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="  pad  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "pad"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: pad"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "summary", "label": "Summary", "from_value": "Bearing change", "to_value": "pad"}]}`.

### MMLM-U-102 — the stored summary sent with padding is no change
- **Rules:** `update_log` R13 [BUG-1155], `update_log` R8
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 2 (stored with its spaces, and listed as a change)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="  Bearing change  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "Bearing change"`.
3. event: events_of(M1) has exactly 0 rows.

### MMLM-U-103 — inner whitespace of a summary is kept as typed
- **Rules:** `update_log` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="Bearing  change"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read A: `summary == "Bearing  change"`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "maintenance_updated"`, `description == "Maintenance log updated: Bearing  change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.

### MMLM-U-104 — an empty summary is refused by the schema
- **Rules:** `update_log` R13 [BUG-1155], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 1 (the schema has no check, so the object is built)

**Given**
1. A = log.

**When**
- `LU(summary="")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-105 — a whitespace-only summary is refused by the schema
- **Rules:** `update_log` R13 [BUG-1155], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1155
- **Fails today on:** Then 1 (the schema has no check, so the object is built)

**Given**
1. A = log.

**When**
- `LU(summary="   ")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.

### MMLM-U-106 — a one-character summary is accepted: the other side of empty
- **Rules:** `update_log` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="a"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "a"`.

### MMLM-U-107 — a padded performed_by is stored trimmed
- **Rules:** `update_log` R13a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="  Rahim  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by == "Rahim"`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": None, "to_value": "Rahim"}]}`.

### MMLM-U-108 — an empty performed_by clears the stored name
- **Rules:** `update_log` R13a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored as given)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by is None`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}`.

### MMLM-U-109 — a whitespace-only performed_by clears the stored name
- **Rules:** `update_log` R13a [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored as given)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="   "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by is None`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "performed_by", "label": "Performed by", "from_value": "Rahim", "to_value": None}]}`.

### MMLM-U-110 — an empty performed_by on an empty field is no change
- **Rules:** `update_log` R13a [BUG-1156], `update_log` R8
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored as given)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by is None`.
3. event: events_of(M1) has exactly 0 rows.

### MMLM-U-111 — the stored name sent with padding is no change
- **Rules:** `update_log` R13a [BUG-1156], `update_log` R8
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 2 (stored with its spaces, and listed as a change)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="  Rahim  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by == "Rahim"`.
3. event: events_of(M1) has exactly 0 rows.

### MMLM-U-112 — performed_by of 255 characters is stored
- **Rules:** `update_log` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by="x" * 255), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by == "x" * 255`.

### MMLM-U-113 — 255 characters inside surrounding spaces are accepted and stored trimmed
- **Rules:** `update_log` R14 [BUG-1156]
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the call raises DataError: 257 characters reach the column)

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(performed_by=" " + "x" * 255 + " "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `performed_by == "x" * 255`.

### MMLM-U-114 — 256 characters are refused by the schema
- **Rules:** `update_log` R14 [BUG-1156], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `LU(performed_by="x" * 256)` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-115 — 256 characters inside surrounding spaces are refused by the schema
- **Rules:** `update_log` R14 [BUG-1156], `update_log` Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1156
- **Fails today on:** Then 1 (the schema has no limit, so the object is built)

**Given**
1. A = log, but `performed_by "Rahim"`.

**When**
- `LU(performed_by=" " + "x" * 256 + " ")` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(A).
3. nothing written: nothing written.
4. event: events_of(M1) has exactly 0 rows.

### MMLM-U-116 — a date in 1900 is stored and listed: no bound
- **Rules:** `update_log` R13c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_date=date(1900, 1, 1)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `maintenance_date == date(1900, 1, 1)`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "1900-01-01"}]}`.

### MMLM-U-117 — a date in 2099 is stored and listed: no bound
- **Rules:** `update_log` R13c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(maintenance_date=date(2099, 1, 1)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `maintenance_date == date(2099, 1, 1)`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id, "changes": [{"field": "maintenance_date", "label": "Maintenance date", "from_value": "2026-03-01", "to_value": "2099-01-01"}]}`.

### MMLM-U-118 — an unknown user with a change: foreign key error, log as it was, no entry
- **Rules:** `update_log` R15, `update_log` Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_maintenance_logs_updated_by_fkey"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-U-119 — the returned object is the instance read and keeps cost as given until a refresh
- **Rules:** `update_log` R16
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(cost=Decimal("7.000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. returns: `str(result.cost) == "7.000"`.
3. session: `db.refresh(result)` runs and raises nothing.
4. returns: `str(result.cost) == "7.00"`.

### MMLM-U-120 — flushed, never committed
- **Rules:** `update_log` R17, `update_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "New text"`.
3. event: events_of(M1) has exactly 1 row.
4. re-read A after the savepoint rollback: `summary == "Bearing change"`, `updated_by is None`, `updated_at is None`.
5. event after the savepoint rollback: events_of(M1) has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### MMLM-U-121 — a summary of 100 000 characters is stored and copied into the entry: no length limit
- **Rules:** `update_log` R6, `update_log` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.update_log(db, log_id=A.id, log_data=LU(summary="S" * 100000), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "S" * 100000`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `description == "Maintenance log updated: " + "S" * 100000`.

## `MachineMaintenanceLogManager.get_log`

### MMLM-G-01 — a live log of the workspace is returned
- **Rules:** `get_log` R1, `get_log` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. returns: `isinstance(result, MachineMaintenanceLog)`.
3. returns: `result.summary == "Bearing change"`, `result.cost == Decimal("5.00")`, `result.performed_by == "Rahim"`.

### MMLM-G-02 — positional arguments work, as the service calls it
- **Rules:** `get_log` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.get_log(db, A.id, W1.id)`.

**Then**
1. returns: `result is A`.

### MMLM-G-03 — a log of another workspace gets the 404
- **Rules:** `get_log` R2, `get_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-G-04 — a soft-deleted log of another workspace gets the same 404
- **Rules:** `get_log` R2, `get_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-G-05 — an unknown id gets the same 404
- **Rules:** `get_log` R2, `get_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.get_log(db, log_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 999999999 not found"`.
4. nothing written: nothing written.

### MMLM-G-06 — id 0 gets the same 404
- **Rules:** `get_log` R2, `get_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.get_log(db, log_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 0 not found"`.
4. nothing written: nothing written.

### MMLM-G-07 — a negative id gets the same 404
- **Rules:** `get_log` R2, `get_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.get_log(db, log_id=-1, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID -1 not found"`.
4. nothing written: nothing written.

### MMLM-G-08 — a soft-deleted log is hidden by default
- **Rules:** `get_log` R3 [BUG-1150], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (no error is raised: `is_deleted` is not read)

**Given**
1. A = log, but gone.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-G-09 — a soft-deleted log of a soft-deleted machine is hidden too: the log's own flag decides
- **Rules:** `get_log` R3 [BUG-1150], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (no error is raised: `is_deleted` is not read)

**Given**
1. A = log, but `machine_id MD.id`, gone.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).

### MMLM-G-10 — include_deleted=False hides it as the default does
- **Rules:** `get_log` R3 [BUG-1150], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log, but gone.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W1.id, include_deleted=False)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.

### MMLM-G-11 — include_deleted=True returns a soft-deleted log
- **Rules:** `get_log` R3a [BUG-1150]
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log, but gone.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is A`.
2. returns: `result.is_deleted is True`.
3. unchanged: unchanged(A).

### MMLM-G-12 — include_deleted=True returns a live log as well
- **Rules:** `get_log` R3a [BUG-1150]
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is A`.

### MMLM-G-13 — include_deleted=True does not reach another workspace
- **Rules:** `get_log` R3a [BUG-1150], `get_log` R2, `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log, but gone.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W2.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).

### MMLM-G-14 — include_deleted=True on an unknown id gets the 404
- **Rules:** `get_log` R3a [BUG-1150], `get_log` R2, `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log.

**When**
- `M.get_log(db, log_id=MISSING, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 999999999 not found"`.

### MMLM-G-15 — an inactive log is returned
- **Rules:** `get_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.

### MMLM-G-16 — a log of a soft-deleted machine is returned: history stays readable
- **Rules:** `get_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. nothing written: nothing written.

### MMLM-G-17 — a log of a machine in a soft-deleted factory is returned: history stays readable
- **Rules:** `get_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. nothing written: nothing written.

### MMLM-G-18 — a log of an inactive machine is returned: history stays readable
- **Rules:** `get_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MA.id`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. nothing written: nothing written.

### MMLM-G-19 — a log of a machine in an inactive factory is returned: history stays readable
- **Rules:** `get_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. nothing written: nothing written.

### MMLM-G-20 — a log on another workspace's machine gets the 404
- **Rules:** `get_log` R6 [BUG-1101], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (no error is raised: the log's machine is not checked)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.get_log(db, log_id=X.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.

### MMLM-G-21 — the same row gets the 404 with include_deleted=True too
- **Rules:** `get_log` R6 [BUG-1101], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.get_log(db, log_id=X.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).

### MMLM-G-22 — a soft-deleted log on another workspace's machine gets the 404 with include_deleted=True
- **Rules:** `get_log` R6 [BUG-1101], `get_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. X = log, but `machine_id M9.id`, gone.

**When**
- `M.get_log(db, log_id=X.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.

### MMLM-G-23 — the same row asked for from the machine's workspace gets the 404
- **Rules:** `get_log` R6, `get_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.get_log(db, log_id=X.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).

### MMLM-G-24 — the read writes nothing and leaves a pending row pending
- **Rules:** `get_log` R7, `get_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Q = pending log.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. session: `Q in db.new`.
3. session: `A not in db.dirty`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

## `MachineMaintenanceLogManager.list_logs`

### MMLM-L-01 — no filter: a list of the live logs
- **Rules:** `list_logs` R1, `list_logs` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-02 — by machine: a list of the live logs
- **Rules:** `list_logs` R2, `list_logs` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-03 — by type: a list of the live logs
- **Rules:** `list_logs` R3, `list_logs` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-04 — by machine and type: a list of the live logs
- **Rules:** `list_logs` R4, `list_logs` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-05 — the service's keyword call works
- **Rules:** `list_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(session=db, workspace_id=W1.id, machine_id=None, maintenance_type=None, skip=0, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-06 — no filter spans machines and types
- **Rules:** `list_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`, `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-07 — by machine spans types
- **Rules:** `list_logs` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-08 — by type spans machines
- **Rules:** `list_logs` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-09 — explicit None on both means no filter
- **Rules:** `list_logs` R1, `list_logs` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`, `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=None, maintenance_type=None)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-10 — no filter: another workspace's log does not appear, although it fits the page
- **Rules:** `list_logs` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-11 — by type: another workspace's log of that type does not appear
- **Rules:** `list_logs` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-12 — by machine: a W2 row on that machine id does not appear
- **Rules:** `list_logs` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`. (A row of W2 on a W1 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-13 — by machine and type: a W2 row on that pair does not appear
- **Rules:** `list_logs` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`. (A row of W2 on a W1 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-14 — by machine: another machine's log does not appear
- **Rules:** `list_logs` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-15 — by machine and type: that type on another machine does not appear
- **Rules:** `list_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-16 — by type: another type does not appear
- **Rules:** `list_logs` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-17 — by machine and type: another type on that machine does not appear
- **Rules:** `list_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-18 — no filter: a soft-deleted log is not returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. G = log, but gone.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-19 — by machine: a soft-deleted log is not returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. G = log, but gone.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-20 — by type: a soft-deleted log is not returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. G = log, but gone.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-21 — by machine and type: a soft-deleted log is not returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. G = log, but gone.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-22 — no filter: a soft-deleted log ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MMLM-L-23 — by machine: a soft-deleted log ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MMLM-L-24 — by type: a soft-deleted log ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MMLM-L-25 — by machine and type: a soft-deleted log ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MMLM-L-26 — no filter: a soft-deleted log ahead of the page uses up no limit
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-27 — by machine: a soft-deleted log ahead of the page uses up no limit
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-28 — by type: a soft-deleted log ahead of the page uses up no limit
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-29 — by machine and type: a soft-deleted log ahead of the page uses up no limit
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. G = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-30 — no filter: a log with is_active False is returned
- **Rules:** `list_logs` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-31 — by machine: a log with is_active False is returned
- **Rules:** `list_logs` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-32 — by type: a log with is_active False is returned
- **Rules:** `list_logs` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-33 — by machine and type: a log with is_active False is returned
- **Rules:** `list_logs` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-34 — no filter: logs of deleted and of inactive parents are all listed
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.
2. B = log, but `machine_id MF.id`.
3. C = log, but `machine_id MA.id`.
4. E = log, but `machine_id MG.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id, E.id]`.

### MMLM-L-35 — by type: logs of deleted and of inactive parents are all listed
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.
2. B = log, but `machine_id MF.id`.
3. C = log, but `machine_id MA.id`.
4. E = log, but `machine_id MG.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id, E.id]`.

### MMLM-L-36 — by machine, asked for a soft-deleted machine: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MD.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-37 — by machine and type, asked for a soft-deleted machine: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MD.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-38 — by machine, asked for a machine in a soft-deleted factory: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MF.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-39 — by machine and type, asked for a machine in a soft-deleted factory: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MF.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-40 — by machine, asked for an inactive machine: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MA.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MA.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-41 — by machine and type, asked for an inactive machine: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MA.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MA.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-42 — by machine, asked for a machine in an inactive factory: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MG.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-43 — by machine and type, asked for a machine in an inactive factory: its logs are returned
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MG.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-44 — a log of a soft-deleted machine that is itself deleted stays hidden
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.
2. G = log, but `machine_id MD.id`, gone.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MD.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-45 — a log of a soft-deleted machine takes its place in the page
- **Rules:** `list_logs` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`, `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### MMLM-L-46 — no filter: a log on another workspace's machine is left out
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned, showing the other workspace's machine id)

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `ids(result) == [A.id]`.

### MMLM-L-47 — by type: a log on another workspace's machine is left out
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned, showing the other workspace's machine id)

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `A.id in ids(result)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `ids(result) == [A.id]`.

### MMLM-L-48 — by machine: asked for that machine, nothing comes back
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned, showing the other workspace's machine id)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M9.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `result == []`.

### MMLM-L-49 — by machine and type: asked for that machine, nothing comes back
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned, showing the other workspace's machine id)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M9.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `result == []`.

### MMLM-L-50 — no filter: a log on another workspace's machine ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X counts, so B and C both come back)

**Given**
1. X = log, but `machine_id M9.id`, `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `ids(result) == [C.id]`.

### MMLM-L-51 — by type: a log on another workspace's machine ahead of the skipped row uses up no skip
- **Rules:** `list_logs` R12 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X counts, so B and C both come back)

**Given**
1. X = log, but `machine_id M9.id`, `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=1)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1.
3. returns: `ids(result) == [C.id]`.

### MMLM-L-52 — from the machine's own workspace the row is not listed
- **Rules:** `list_logs` R12, `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W2.id, machine_id=M9.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-53 — machine_id=0 alone returns nothing
- **Rules:** `list_logs` R5 [BUG-1152]
- **Kind:** bug
- **Expect:** xfail BUG-1152
- **Fails today on:** Then 2 (0 is falsy, so every log comes back)

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=0)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### MMLM-L-54 — machine_id=0 with a type returns nothing
- **Rules:** `list_logs` R5 [BUG-1152]
- **Kind:** bug
- **Expect:** xfail BUG-1152
- **Fails today on:** Then 2 (0 is falsy, so every log comes back)

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=0, maintenance_type=REPAIR)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### MMLM-L-55 — machine_id=0 with an empty type string returns nothing
- **Rules:** `list_logs` R5 [BUG-1152], `list_logs` R7
- **Kind:** bug
- **Expect:** xfail BUG-1152
- **Fails today on:** Then 2 (0 is falsy, so every log comes back)

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=0, maintenance_type="")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### MMLM-L-56 — an unknown machine returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MMLM-L-57 — an unknown machine with a type returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=MISSING, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-58 — a negative machine id returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=-1)`.

**Then**
1. returns: `result == []`.

### MMLM-L-59 — a negative machine id with a type returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=-1, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-60 — a machine of another workspace returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M9.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-61 — a machine of another workspace with a type returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M9.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-62 — a machine with no logs returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M2.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-63 — a machine with no logs with a type returns an empty list, with no 404
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M2.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-64 — a type no log has returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)`.

**Then**
1. returns: `result == []`.

### MMLM-L-65 — a type the machine has no log of returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.EMERGENCY)`.

**Then**
1. returns: `result == []`.

### MMLM-L-66 — no filter: an unknown workspace returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MMLM-L-67 — by machine: an unknown workspace returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=MISSING, machine_id=M1.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-68 — by type: an unknown workspace returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=MISSING, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-69 — by machine and type: an unknown workspace returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=MISSING, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-70 — no filter: a workspace with no logs returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-71 — by machine: a W1 machine asked for from W2 returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W2.id, machine_id=M1.id)`.

**Then**
1. returns: `result == []`.

### MMLM-L-72 — by machine and type: a W1 machine asked for from W2 returns an empty list
- **Rules:** `list_logs` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W2.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `result == []`.

### MMLM-L-73 — by type: the string "REPAIR" works like the member
- **Rules:** `list_logs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type="REPAIR")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-74 — by machine and type: the string "REPAIR" works like the member
- **Rules:** `list_logs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type="REPAIR")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-75 — an empty type string means no filter
- **Rules:** `list_logs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type="")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-76 — an empty type string with a machine filters by the machine alone
- **Rules:** `list_logs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `maintenance_type MaintenanceTypeEnum.EMERGENCY`.
3. C = log, but `machine_id M2.id`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type="")`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MMLM-L-77 — by type: a string that is no member is a database error
- **Rules:** `list_logs` R7, `list_logs` Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, maintenance_type="BOGUS")`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22P02"`.
3. nothing written: nothing written.

### MMLM-L-78 — by machine and type: a string that is no member is a database error
- **Rules:** `list_logs` R7, `list_logs` Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type="BOGUS")`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22P02"`.
3. nothing written: nothing written.

### MMLM-L-79 — no filter: limit=1 gives the first row of the page
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-80 — no filter: skip=1 gives the rest
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-81 — no filter: skip=1, limit=1 gives the middle row
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-82 — no filter: the defaults give the latest 100 of 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.

### MMLM-L-83 — no filter: limit=1000 gives all 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MMLM-L-84 — no filter: limit=0 returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MMLM-L-85 — no filter: skip at the end returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MMLM-L-86 — by machine: limit=1 gives the first row of the page
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-87 — by machine: skip=1 gives the rest
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-88 — by machine: skip=1, limit=1 gives the middle row
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-89 — by machine: the defaults give the latest 100 of 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.

### MMLM-L-90 — by machine: limit=1000 gives all 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MMLM-L-91 — by machine: limit=0 returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MMLM-L-92 — by machine: skip at the end returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MMLM-L-93 — by type: limit=1 gives the first row of the page
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-94 — by type: skip=1 gives the rest
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-95 — by type: skip=1, limit=1 gives the middle row
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-96 — by type: the defaults give the latest 100 of 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.

### MMLM-L-97 — by type: limit=1000 gives all 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MMLM-L-98 — by type: limit=0 returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, limit=0)`.

**Then**
1. returns: `result == []`.

### MMLM-L-99 — by type: skip at the end returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=2)`.

**Then**
1. returns: `result == []`.

### MMLM-L-100 — by machine and type: limit=1 gives the first row of the page
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-101 — by machine and type: skip=1 gives the rest
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-102 — by machine and type: skip=1, limit=1 gives the middle row
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-L-103 — by machine and type: the defaults give the latest 100 of 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.

### MMLM-L-104 — by machine and type: limit=1000 gives all 101
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk101.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MMLM-L-105 — by machine and type: limit=0 returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, limit=0)`.

**Then**
1. returns: `result == []`.

### MMLM-L-106 — by machine and type: skip at the end returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=2)`.

**Then**
1. returns: `result == []`.

### MMLM-L-107 — skip past the end returns an empty list
- **Rules:** `list_logs` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### MMLM-L-108 — no filter: a negative limit is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-109 — no filter: a negative skip is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-110 — by machine: a negative limit is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-111 — by machine: a negative skip is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-112 — by type: a negative limit is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-113 — by type: a negative skip is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-114 — by machine and type: a negative limit is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-115 — by machine and type: a negative skip is a database error
- **Rules:** `list_logs` R9, `list_logs` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MMLM-L-116 — no filter: different dates come back latest first
- **Rules:** `list_logs` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MMLM-L-117 — by machine: different dates come back latest first
- **Rules:** `list_logs` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MMLM-L-118 — by type: different dates come back latest first
- **Rules:** `list_logs` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MMLM-L-119 — by machine and type: different dates come back latest first
- **Rules:** `list_logs` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MMLM-L-120 — no filter: logs on one date come back highest id first
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MMLM-L-121 — by machine: logs on one date come back highest id first
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MMLM-L-122 — by type: logs on one date come back highest id first
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MMLM-L-123 — by machine and type: logs on one date come back highest id first
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MMLM-L-124 — no filter: the tie-break applies before skip and limit
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### MMLM-L-125 — by machine: the tie-break applies before skip and limit
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### MMLM-L-126 — by type: the tie-break applies before skip and limit
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### MMLM-L-127 — by machine and type: the tie-break applies before skip and limit
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is asked for; physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (A is changed after the later rows exist: this usually moves it physically behind them.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### MMLM-L-128 — no filter: the query asks for date descending, then id descending
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has no `id` key)

**Given**
1. A = log.
2. sql_log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MMLM-L-129 — by machine: the query asks for date descending, then id descending
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has no `id` key)

**Given**
1. A = log.
2. sql_log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MMLM-L-130 — by type: the query asks for date descending, then id descending
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has no `id` key)

**Given**
1. A = log.
2. sql_log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MMLM-L-131 — by machine and type: the query asks for date descending, then id descending
- **Rules:** `list_logs` R10 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has no `id` key)

**Given**
1. A = log.
2. sql_log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MMLM-L-132 — no filter: the read writes nothing and leaves a pending row pending
- **Rules:** `list_logs` R13, `list_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Q = pending log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `Q in db.new`.
3. session: `A not in db.dirty`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

### MMLM-L-133 — by machine: the read writes nothing and leaves a pending row pending
- **Rules:** `list_logs` R13, `list_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Q = pending log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `Q in db.new`.
3. session: `A not in db.dirty`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

### MMLM-L-134 — by type: the read writes nothing and leaves a pending row pending
- **Rules:** `list_logs` R13, `list_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Q = pending log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `Q in db.new`.
3. session: `A not in db.dirty`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

### MMLM-L-135 — by machine and type: the read writes nothing and leaves a pending row pending
- **Rules:** `list_logs` R13, `list_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Q = pending log.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `Q in db.new`.
3. session: `A not in db.dirty`.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

### MMLM-L-136 — no filter: a W2 row on a W1 machine does not appear
- **Rules:** `list_logs` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`. (A row of W2 on a W1 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MMLM-L-137 — by type: a W2 row on a W1 machine does not appear
- **Rules:** `list_logs` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Y = log, but `workspace_id W2.id`. (A row of W2 on a W1 machine, invalid data.)

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `MachineMaintenanceLogManager.delete_log`

### MMLM-D-01 — a live log is soft-deleted
- **Rules:** `delete_log` R6, `delete_log` Returns, `delete_log` Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`, `performed_by "Rahim"`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`.
3. re-read A: `deleted_by == U2.id`, `deleted_at is not None`.
4. re-read A: `summary == "Bearing change"`, `cost == Decimal("5.00")`, `performed_by == "Rahim"`.
5. re-read A: `updated_at is not None`.
6. unchanged: unchanged(A) except `is_deleted`, `is_active`, `deleted_at`, `deleted_by`, `updated_at`.
7. count: `machine_maintenance_logs` rows with `id == A.id`: exactly 1.

### MMLM-D-02 — the service's keyword call works
- **Rules:** `delete_log` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.delete_log(session=db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.

### MMLM-D-03 — a log of another workspace gets the 404 and nothing is written
- **Rules:** `delete_log` R1, `delete_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.delete_log(db, log_id=A.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.
6. event: events_of(M1) has exactly 0 rows.

### MMLM-D-04 — a soft-deleted log of another workspace gets the same 404, not the 400
- **Rules:** `delete_log` R1, `delete_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.delete_log(db, log_id=A.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-D-05 — an unknown id gets the same 404
- **Rules:** `delete_log` R1, `delete_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.delete_log(db, log_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 999999999 not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-D-06 — id 0 gets the same 404
- **Rules:** `delete_log` R1, `delete_log` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.delete_log(db, log_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Maintenance log with ID 0 not found"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-D-07 — an already deleted log is refused: the first stamps stay, no entry
- **Rules:** `delete_log` R2, `delete_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Maintenance log is already deleted"`.
4. re-read A: `deleted_by == U1.id`, `deleted_at == T0`.
5. unchanged: unchanged(A).
6. nothing written: nothing written.
7. event: events_of(M1) has exactly 0 rows.

### MMLM-D-08 — a log on another workspace's machine gets the 404 and stays live
- **Rules:** `delete_log` R3 [BUG-1101], `delete_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 1 (no error is raised: the log's machine is not checked)

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.delete_log(db, log_id=X.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.
6. event: events_of(M9) has exactly 0 rows.

### MMLM-D-09 — a soft-deleted log on another workspace's machine answers 404, not 400
- **Rules:** `delete_log` R3 [BUG-1101], `delete_log` Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 2 (today 400: the row is found and its own flag answers)

**Given**
1. X = log, but `machine_id M9.id`, gone.

**When**
- `M.delete_log(db, log_id=X.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.

### MMLM-D-10 — the same row asked for from the machine's workspace gets the 404
- **Rules:** `delete_log` R3, `delete_log` R1, `delete_log` Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, but `machine_id M9.id`. (A row of W1 on a W2 machine, invalid data.)

**When**
- `M.delete_log(db, log_id=X.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {X.id} not found"`.
4. unchanged: unchanged(X).
5. nothing written: nothing written.
6. event: events_of(M9) has exactly 0 rows.

### MMLM-D-11 — an inactive log is deleted like any other
- **Rules:** `delete_log` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`.
3. event: events_of(M1) has exactly 1 row.

### MMLM-D-12 — a log of a soft-deleted machine is deleted, and the entry goes to that machine
- **Rules:** `delete_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. event: events_of(MD) has exactly 1 row.
4. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MD.id`.
5. unchanged: unchanged(MD).

### MMLM-D-13 — a log of a machine in a soft-deleted factory is deleted, and the entry goes to that machine
- **Rules:** `delete_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. event: events_of(MF) has exactly 1 row.
4. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MF.id`.
5. unchanged: unchanged(MF).

### MMLM-D-14 — a log of an inactive machine is deleted, and the entry goes to that machine
- **Rules:** `delete_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MA.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. event: events_of(MA) has exactly 1 row.
4. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MA.id`.
5. unchanged: unchanged(MA).

### MMLM-D-15 — a log of a machine in an inactive factory is deleted, and the entry goes to that machine
- **Rules:** `delete_log` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. event: events_of(MG) has exactly 1 row.
4. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == MG.id`.
5. unchanged: unchanged(MG).

### MMLM-D-16 — a delete leaves an empty updated_by empty
- **Rules:** `delete_log` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == U2.id`.
3. re-read A: `updated_by is None`.

### MMLM-D-17 — a delete by another user leaves updated_by as it was
- **Rules:** `delete_log` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`, `updated_at T0`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == U2.id`.
3. re-read A: `updated_by == U3.id`.

### MMLM-D-18 — a delete by the user already in updated_by stamps deleted_by only
- **Rules:** `delete_log` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `updated_by U3.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == U3.id`.
3. re-read A: `updated_by == U3.id`.

### MMLM-D-19 — deleted_at is the application clock
- **Rules:** `delete_log` R6a [BUG-1102]
- **Kind:** bug
- **Expect:** xfail BUG-1102
- **Fails today on:** Then 3 (`deleted_at` is the database's `now()`)

**Given**
1. A = log.
2. clock patch.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `deleted_by == U2.id`.
3. re-read A: `deleted_at == NOW`.

### MMLM-D-20 — one maintenance_removed entry with every field
- **Rules:** `delete_log` R7, `delete_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Bearing change"`, `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
4. event: that row: `metadata_json == {"maintenance_log_id": A.id}`.
5. event: that row: `created_at is not None`.
6. event: events_of(M2) has exactly 0 rows.

### MMLM-D-21 — the entry's text is the log's summary; the entry shows the acting user
- **Rules:** `delete_log` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `summary "Oil top-up"`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "maintenance_removed"`, `description == "Maintenance log removed: Oil top-up"`, `performed_by == U3.id`, `workspace_id == W1.id`, `machine_id == M1.id`.

### MMLM-D-22 — the earlier maintenance_logged entry stays
- **Rules:** `delete_log` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. E1 = `machine_activity_events` row: `workspace_id W1.id`, `machine_id M1.id`, `event_type "maintenance_logged"`, `description "Maintenance logged: Bearing change"`, `performed_by U1.id`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 2 rows.
3. unchanged: unchanged(E1).
4. event: `events_of(M1)[1].event_type == "maintenance_removed"`.

### MMLM-D-23 — one entry per real change across a log's whole life
- **Rules:** `delete_log` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `A = M.create_log(db, log_data=LC(machine_id=M1.id, maintenance_type=REPAIR, maintenance_date=D1, summary="Bearing change"), workspace_id=W1.id, user_id=U2.id)`.
2. `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. event: events_of(M1) has exactly 3 rows.
3. event: `[e.event_type for e in events_of(M1)] == ["maintenance_logged", "maintenance_updated", "maintenance_removed"]`.
4. event: `events_of(M1)[2].description == "Maintenance log removed: New text"`.

### MMLM-D-24 — only that log and nothing else changes
- **Rules:** `delete_log` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(B).
3. unchanged: unchanged(M1).
4. count: `machine_maintenance_logs` rows with `is_deleted IS TRUE`: exactly 1.

### MMLM-D-25 — after a delete, no filter: the log is in no list
- **Rules:** `delete_log` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log.
3. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-D-26 — after a delete, by machine: the log is in no list
- **Rules:** `delete_log` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log.
3. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-D-27 — after a delete, by type: the log is in no list
- **Rules:** `delete_log` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log.
3. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-D-28 — after a delete, by machine and type: the log is in no list
- **Rules:** `delete_log` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log.
3. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.list_logs(db, workspace_id=W1.id, machine_id=M1.id, maintenance_type=REPAIR)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MMLM-D-29 — after a delete, update_log answers the 400
- **Rules:** `delete_log` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `M.update_log(db, log_id=A.id, log_data=LU(summary="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted maintenance log"`.
4. re-read A: `summary == "Bearing change"`.
5. event: events_of(M1) has exactly 1 row.

### MMLM-D-30 — a second delete answers the 400, with the first stamps kept and one entry
- **Rules:** `delete_log` R9, `delete_log` R2, `delete_log` Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Maintenance log is already deleted"`.
4. re-read A: `deleted_by == U2.id`.
5. event: events_of(M1) has exactly 1 row.

### MMLM-D-31 — after a delete, get_log answers the 404
- **Rules:** `delete_log` R9, `get_log` R3 [BUG-1150]
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (no error is raised: `is_deleted` is not read)

**Given**
1. A = log.
2. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `M.get_log(db, log_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Maintenance log with ID {A.id} not found"`.

### MMLM-D-32 — after a delete, get_log with include_deleted=True returns it
- **Rules:** `delete_log` R9, `get_log` R3a [BUG-1150]
- **Kind:** bug
- **Expect:** xfail BUG-1150
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = log.
2. `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**When**
- `result = M.get_log(db, log_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is A`.

### MMLM-D-33 — an unknown user: foreign key error, the log stays live, no entry
- **Rules:** `delete_log` R10, `delete_log` Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_maintenance_logs_deleted_by_fkey"`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MMLM-D-34 — flushed, never committed
- **Rules:** `delete_log` R11, `delete_log` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.delete_log(db, log_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. event: events_of(M1) has exactly 1 row.
4. re-read A after the savepoint rollback: `is_deleted is False`, `is_active is True`, `deleted_by is None`, `deleted_at is None`.
5. event after the savepoint rollback: events_of(M1) has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| every `HTTPException` refusal; schema errors at the API | `POST`, `PUT`, `DELETE`, `GET /machine-maintenance-logs/` (integration) | the HTTP status reaches the client; a schema refusal is 400 today (BUG-461), 422 intended |
| `get_log` R3a; BUG-1150; FU-1 (a) | `MachineMaintenanceLogService.get_log`, `GET /machine-maintenance-logs/{id}/` | `include_deleted` is passed on and reachable from the API |
| `list_logs` R8, R9; HR-7 | `GET /machine-maintenance-logs/` | `skip >= 0`, `1 <= limit <= 1000`, the enum check on `maintenance_type` |
| `create_log` R16, `update_log` R15, `delete_log` R10; FU-1 (b) | global `IntegrityError` and `DataError` handling (integration) | the generic 409; no 500 left on the paths BUG-1156 and BUG-1157 close |
| `create_log` R17, `update_log` R17, `delete_log` R11 | `MachineMaintenanceLogService` | the service's commit, rollback and `db.refresh` |
| FU-1 (d) | `DELETE /machine-maintenance-logs/{id}/` | answers 200 with the row, where machine and machine item deletes answer 204 |
| `delete_log` R6a; BUG-1102 | `tests/unit/dao/machine_maintenance_log.cases.md` | the DAO's clock cards; here one pass-through |
| `list_logs` R10; BUG-1100 | `tests/unit/dao/machine_maintenance_log.cases.md` | the DAO's order and window cards; here the same checks per path through the manager |
| BUG-1101 | `tests/unit/dao/machine_maintenance_log.cases.md` | the fix at the DAO; `scripts/find_cross_workspace_rows.py` for rows already stored |
| FU-2 | `app/schemas/machine_maintenance_log.py` spec, when one is written | the limits sit on Create and Update only; `null` told apart from omitted |
| FU-3; BUG-1159 | frontend (`MachineActivityEventLogRow.tsx`, `MachineDetailBody.tsx`, `machineMaintenanceLog.ts`) | the missing add and edit forms with the schema's limits; no card here |
| FU-4 | `tests/unit/managers/machine_activity_manager.spec.md` | `collect_field_changes`, `format_field_value`, `log_event`: where BUG-1157's stored form lands |
| Two real concurrent transactions | integration | HR-10 does not apply here (spec, house-rule section); two deletes at once can write two entries |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create_log` R10, R12; `update_log` R14 **[money]** | `5.0010`, `10000000000000.00` and `9999999999999.990` are not in the spec. They follow from "trailing zeros do not count" and the 13-digit limit; I tried all three on a schema of my own with `ge=0, max_digits=15, decimal_places=2`: refused, refused, accepted. | Not blocked. Cards written to that reading. If the fix is not those exact field limits, these are the cards to look at first. |
| 2 | `update_log` R12a, R13b **[money]** | `-0` on update is not stated; R11 and Q1 say it for `create_log` only. Read: accepted through "the limits of `create_log`", stored `0.00`, entry `"0.00"` (today `"-0"`). | Not blocked. |
| 3 | `update_log` R12a "on both sides" **[money]** | A row read from the database always holds two decimals, so `from_value` can differ from the stored form only on an instance not refreshed, which no real request has (spec Notes). A wrong `from_value` format cannot be shown on a reachable path. | No card pins `from_value` on an unrefreshed instance. `from_value` is asserted from refreshed rows. A fix that formats only `to_value` passes. |
| 4 | `update_log` R2 with R3, `delete_log` R2 with R3 | A row that is both soft-deleted and on another workspace's machine meets two rules, 400 and 404. Read 404, from DAO `get_by_id_and_workspace` R6 and the spec's FU-1 (i) "get `None`". | Not blocked. Two cards rest on it. |
| 5 | `create_log` R3 | A live machine of W1 whose factory belongs to W2 (invalid data, HR-16): whether that factory's deleted flag refuses the log is not said. | No card. Low: `create_log` sets no link to a factory. |
| 6 | Overview, Facts | The spec imports `MAINTENANCE_LOG_FIELDS` but does not say what kind of object it is. | No direct card. Order and labels are held by the all-five `changes` card, MMLM-U-23. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_log` | R1 | MMLM-C-06 MMLM-C-07 MMLM-C-08 MMLM-C-09 MMLM-C-10 MMLM-C-11 |
| `create_log` | R2 | MMLM-C-12 MMLM-C-13 MMLM-C-14 |
| `create_log` | R3 | MMLM-C-15 MMLM-C-16 MMLM-C-17 |
| `create_log` | R4 | MMLM-C-18 MMLM-C-19 MMLM-C-20 |
| `create_log` | R5 | MMLM-C-01 MMLM-C-02 MMLM-C-03 MMLM-C-04 |
| `create_log` | R6 | MMLM-C-05 |
| `create_log` | R7 | MMLM-C-21 |
| `create_log` | R8 | MMLM-C-22 MMLM-C-23 MMLM-C-24 MMLM-C-25 MMLM-C-26 MMLM-C-27 MMLM-C-28 MMLM-C-29 |
| `create_log` | R8a | MMLM-C-31 MMLM-C-32 MMLM-C-33 MMLM-C-34 |
| `create_log` | R8b | MMLM-C-30 |
| `create_log` | R9 | MMLM-C-35 |
| `create_log` | R9a | MMLM-C-36 MMLM-C-37 MMLM-C-38 |
| `create_log` | R10 | MMLM-C-46 MMLM-C-47 MMLM-C-48 |
| `create_log` | R10a | MMLM-C-51 MMLM-C-52 MMLM-C-53 MMLM-C-54 |
| `create_log` | R11 | MMLM-C-39 MMLM-C-40 MMLM-C-41 |
| `create_log` | R11a | MMLM-C-49 MMLM-C-50 MMLM-C-60 |
| `create_log` | R12 | MMLM-C-42 MMLM-C-43 MMLM-C-44 MMLM-C-45 MMLM-C-55 MMLM-C-56 MMLM-C-57 MMLM-C-58 MMLM-C-59 |
| `create_log` | R13 | MMLM-C-62 MMLM-C-63 |
| `create_log` | R14 | MMLM-C-71 MMLM-C-72 |
| `create_log` | R15 | MMLM-C-74 MMLM-C-75 MMLM-C-76 MMLM-C-77 MMLM-C-78 MMLM-C-79 |
| `create_log` | R16 | MMLM-C-80 |
| `create_log` | R17 | MMLM-C-81 |
| `create_log` | Errors row 1 | MMLM-C-06 MMLM-C-07 MMLM-C-08 MMLM-C-09 MMLM-C-10 MMLM-C-11 |
| `create_log` | Errors row 2 | MMLM-C-12 MMLM-C-13 MMLM-C-14 MMLM-C-15 MMLM-C-16 MMLM-C-17 |
| `create_log` | Errors row 3 | MMLM-C-27 MMLM-C-28 MMLM-C-29 MMLM-C-36 MMLM-C-37 MMLM-C-49 MMLM-C-50 MMLM-C-51 MMLM-C-52 MMLM-C-53 MMLM-C-54 MMLM-C-55 MMLM-C-56 MMLM-C-57 MMLM-C-58 MMLM-C-59 |
| `create_log` | Errors row 4 | MMLM-C-80 |
| `create_log` | FU-2 | MMLM-C-61 |
| `create_log` | Inputs | MMLM-C-04 MMLM-C-64 MMLM-C-65 MMLM-C-66 MMLM-C-67 MMLM-C-68 MMLM-C-69 MMLM-C-70 |
| `create_log` | Returns | MMLM-C-01 |
| `create_log` | Side effects | MMLM-C-71 MMLM-C-73 MMLM-C-81 |
| `update_log` | R1 | MMLM-U-03 MMLM-U-04 MMLM-U-05 MMLM-U-06 MMLM-U-12 |
| `update_log` | R2 | MMLM-U-07 MMLM-U-08 |
| `update_log` | R3 | MMLM-U-09 MMLM-U-10 MMLM-U-11 MMLM-U-12 |
| `update_log` | R4 | MMLM-U-13 |
| `update_log` | R5 | MMLM-U-14 MMLM-U-15 MMLM-U-16 MMLM-U-17 |
| `update_log` | R6 | MMLM-U-01 MMLM-U-02 MMLM-U-18 MMLM-U-19 MMLM-U-20 MMLM-U-21 MMLM-U-22 MMLM-U-23 MMLM-U-29 MMLM-U-30 MMLM-U-75 MMLM-U-76 MMLM-U-77 MMLM-U-78 MMLM-U-79 MMLM-U-80 MMLM-U-81 MMLM-U-82 MMLM-U-96 MMLM-U-121 |
| `update_log` | R7 | MMLM-U-31 MMLM-U-32 MMLM-U-33 MMLM-U-34 |
| `update_log` | R7a | MMLM-U-35 MMLM-U-36 MMLM-U-37 |
| `update_log` | R8 | MMLM-U-38 MMLM-U-42 MMLM-U-46 MMLM-U-50 MMLM-U-59 MMLM-U-63 MMLM-U-102 MMLM-U-110 MMLM-U-111 |
| `update_log` | R8a | MMLM-U-39 MMLM-U-40 MMLM-U-41 MMLM-U-43 MMLM-U-44 MMLM-U-45 MMLM-U-47 MMLM-U-48 MMLM-U-49 MMLM-U-51 MMLM-U-52 MMLM-U-53 MMLM-U-54 MMLM-U-55 MMLM-U-60 |
| `update_log` | R9 | MMLM-U-56 MMLM-U-57 MMLM-U-58 MMLM-U-59 MMLM-U-60 |
| `update_log` | R10 | MMLM-U-01 MMLM-U-23 MMLM-U-24 MMLM-U-61 MMLM-U-62 MMLM-U-63 MMLM-U-64 MMLM-U-73 |
| `update_log` | R11 | MMLM-U-01 MMLM-U-18 MMLM-U-19 MMLM-U-20 MMLM-U-21 MMLM-U-26 MMLM-U-64 |
| `update_log` | R12 | MMLM-U-18 MMLM-U-19 MMLM-U-20 MMLM-U-21 MMLM-U-23 MMLM-U-24 MMLM-U-25 MMLM-U-30 |
| `update_log` | R12a | MMLM-U-65 MMLM-U-66 MMLM-U-67 MMLM-U-68 MMLM-U-69 MMLM-U-70 MMLM-U-71 MMLM-U-72 MMLM-U-73 MMLM-U-74 |
| `update_log` | R13 | MMLM-U-101 MMLM-U-102 MMLM-U-103 MMLM-U-104 MMLM-U-105 MMLM-U-106 |
| `update_log` | R13a | MMLM-U-107 MMLM-U-108 MMLM-U-109 MMLM-U-110 MMLM-U-111 |
| `update_log` | R13b | MMLM-U-83 MMLM-U-84 MMLM-U-94 MMLM-U-95 MMLM-U-96 |
| `update_log` | R13c | MMLM-U-116 MMLM-U-117 |
| `update_log` | R14 | MMLM-U-75 MMLM-U-76 MMLM-U-77 MMLM-U-78 MMLM-U-79 MMLM-U-80 MMLM-U-81 MMLM-U-82 MMLM-U-85 MMLM-U-86 MMLM-U-87 MMLM-U-88 MMLM-U-89 MMLM-U-90 MMLM-U-91 MMLM-U-92 MMLM-U-93 MMLM-U-112 MMLM-U-113 MMLM-U-114 MMLM-U-115 |
| `update_log` | R15 | MMLM-U-118 |
| `update_log` | R16 | MMLM-U-119 |
| `update_log` | R17 | MMLM-U-120 |
| `update_log` | Errors row 1 | MMLM-U-03 MMLM-U-04 MMLM-U-05 MMLM-U-06 MMLM-U-09 MMLM-U-10 MMLM-U-11 MMLM-U-12 |
| `update_log` | Errors row 2 | MMLM-U-07 MMLM-U-08 |
| `update_log` | Errors row 3 | MMLM-U-35 MMLM-U-36 MMLM-U-37 MMLM-U-83 MMLM-U-84 MMLM-U-85 MMLM-U-86 MMLM-U-87 MMLM-U-88 MMLM-U-89 MMLM-U-90 MMLM-U-91 MMLM-U-92 MMLM-U-93 MMLM-U-104 MMLM-U-105 MMLM-U-114 MMLM-U-115 |
| `update_log` | Errors row 4 | MMLM-U-118 |
| `update_log` | Inputs | MMLM-U-97 MMLM-U-98 MMLM-U-99 MMLM-U-100 MMLM-U-121 |
| `update_log` | Returns | MMLM-U-01 |
| `update_log` | Side effects | MMLM-U-27 MMLM-U-28 MMLM-U-120 |
| `get_log` | R1 | MMLM-G-01 MMLM-G-02 |
| `get_log` | R2 | MMLM-G-03 MMLM-G-04 MMLM-G-05 MMLM-G-06 MMLM-G-07 MMLM-G-13 MMLM-G-14 |
| `get_log` | R3 | MMLM-G-08 MMLM-G-09 MMLM-G-10 MMLM-D-31 |
| `get_log` | R3a | MMLM-G-11 MMLM-G-12 MMLM-G-13 MMLM-G-14 MMLM-D-32 |
| `get_log` | R4 | MMLM-G-15 |
| `get_log` | R5 | MMLM-G-16 MMLM-G-17 MMLM-G-18 MMLM-G-19 |
| `get_log` | R6 | MMLM-G-20 MMLM-G-21 MMLM-G-22 MMLM-G-23 |
| `get_log` | R7 | MMLM-G-24 |
| `get_log` | Errors row 1 | MMLM-G-03 MMLM-G-04 MMLM-G-05 MMLM-G-06 MMLM-G-07 MMLM-G-08 MMLM-G-09 MMLM-G-10 MMLM-G-13 MMLM-G-14 MMLM-G-20 MMLM-G-21 MMLM-G-22 MMLM-G-23 |
| `get_log` | Returns | MMLM-G-01 |
| `get_log` | Side effects | MMLM-G-24 |
| `list_logs` | R1 | MMLM-L-01 MMLM-L-05 MMLM-L-06 MMLM-L-09 MMLM-L-10 MMLM-L-136 |
| `list_logs` | R2 | MMLM-L-02 MMLM-L-07 MMLM-L-12 MMLM-L-14 |
| `list_logs` | R3 | MMLM-L-03 MMLM-L-08 MMLM-L-11 MMLM-L-16 MMLM-L-137 |
| `list_logs` | R4 | MMLM-L-04 MMLM-L-13 MMLM-L-15 MMLM-L-17 |
| `list_logs` | R5 | MMLM-L-09 MMLM-L-53 MMLM-L-54 MMLM-L-55 |
| `list_logs` | R6 | MMLM-L-52 MMLM-L-56 MMLM-L-57 MMLM-L-58 MMLM-L-59 MMLM-L-60 MMLM-L-61 MMLM-L-62 MMLM-L-63 MMLM-L-64 MMLM-L-65 MMLM-L-66 MMLM-L-67 MMLM-L-68 MMLM-L-69 MMLM-L-70 MMLM-L-71 MMLM-L-72 |
| `list_logs` | R7 | MMLM-L-55 MMLM-L-73 MMLM-L-74 MMLM-L-75 MMLM-L-76 MMLM-L-77 MMLM-L-78 |
| `list_logs` | R8 | MMLM-L-79 MMLM-L-80 MMLM-L-81 MMLM-L-82 MMLM-L-83 MMLM-L-84 MMLM-L-85 MMLM-L-86 MMLM-L-87 MMLM-L-88 MMLM-L-89 MMLM-L-90 MMLM-L-91 MMLM-L-92 MMLM-L-93 MMLM-L-94 MMLM-L-95 MMLM-L-96 MMLM-L-97 MMLM-L-98 MMLM-L-99 MMLM-L-100 MMLM-L-101 MMLM-L-102 MMLM-L-103 MMLM-L-104 MMLM-L-105 MMLM-L-106 MMLM-L-107 |
| `list_logs` | R9 | MMLM-L-108 MMLM-L-109 MMLM-L-110 MMLM-L-111 MMLM-L-112 MMLM-L-113 MMLM-L-114 MMLM-L-115 |
| `list_logs` | R10 | MMLM-L-116 MMLM-L-117 MMLM-L-118 MMLM-L-119 MMLM-L-120 MMLM-L-121 MMLM-L-122 MMLM-L-123 MMLM-L-124 MMLM-L-125 MMLM-L-126 MMLM-L-127 MMLM-L-128 MMLM-L-129 MMLM-L-130 MMLM-L-131 |
| `list_logs` | R11 | MMLM-L-18 MMLM-L-19 MMLM-L-20 MMLM-L-21 MMLM-L-22 MMLM-L-23 MMLM-L-24 MMLM-L-25 MMLM-L-26 MMLM-L-27 MMLM-L-28 MMLM-L-29 MMLM-L-30 MMLM-L-31 MMLM-L-32 MMLM-L-33 MMLM-L-34 MMLM-L-35 MMLM-L-36 MMLM-L-37 MMLM-L-38 MMLM-L-39 MMLM-L-40 MMLM-L-41 MMLM-L-42 MMLM-L-43 MMLM-L-44 MMLM-L-45 |
| `list_logs` | R12 | MMLM-L-46 MMLM-L-47 MMLM-L-48 MMLM-L-49 MMLM-L-50 MMLM-L-51 MMLM-L-52 |
| `list_logs` | R13 | MMLM-L-132 MMLM-L-133 MMLM-L-134 MMLM-L-135 |
| `list_logs` | Errors row 1 | MMLM-L-108 MMLM-L-110 MMLM-L-112 MMLM-L-114 |
| `list_logs` | Errors row 2 | MMLM-L-109 MMLM-L-111 MMLM-L-113 MMLM-L-115 |
| `list_logs` | Errors row 3 | MMLM-L-77 MMLM-L-78 |
| `list_logs` | Returns | MMLM-L-01 MMLM-L-02 MMLM-L-03 MMLM-L-04 |
| `list_logs` | Side effects | MMLM-L-132 MMLM-L-133 MMLM-L-134 MMLM-L-135 |
| `delete_log` | R1 | MMLM-D-03 MMLM-D-04 MMLM-D-05 MMLM-D-06 MMLM-D-10 |
| `delete_log` | R2 | MMLM-D-07 MMLM-D-30 |
| `delete_log` | R3 | MMLM-D-08 MMLM-D-09 MMLM-D-10 |
| `delete_log` | R4 | MMLM-D-11 |
| `delete_log` | R5 | MMLM-D-12 MMLM-D-13 MMLM-D-14 MMLM-D-15 |
| `delete_log` | R6 | MMLM-D-01 MMLM-D-02 MMLM-D-16 MMLM-D-17 MMLM-D-18 |
| `delete_log` | R6a | MMLM-D-19 |
| `delete_log` | R7 | MMLM-D-20 MMLM-D-21 MMLM-D-22 MMLM-D-23 |
| `delete_log` | R8 | MMLM-D-24 |
| `delete_log` | R9 | MMLM-D-25 MMLM-D-26 MMLM-D-27 MMLM-D-28 MMLM-D-29 MMLM-D-30 MMLM-D-31 MMLM-D-32 |
| `delete_log` | R10 | MMLM-D-33 |
| `delete_log` | R11 | MMLM-D-34 |
| `delete_log` | Errors row 1 | MMLM-D-03 MMLM-D-04 MMLM-D-05 MMLM-D-06 MMLM-D-08 MMLM-D-09 MMLM-D-10 |
| `delete_log` | Errors row 2 | MMLM-D-07 MMLM-D-30 |
| `delete_log` | Errors row 3 | MMLM-D-33 |
| `delete_log` | Returns | MMLM-D-01 |
| `delete_log` | Side effects | MMLM-D-01 MMLM-D-20 MMLM-D-34 |
| — | BUG-1159 | Deferred: frontend, no rule here |
