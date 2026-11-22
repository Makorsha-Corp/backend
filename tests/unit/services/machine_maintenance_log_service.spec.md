# Spec — `app/services/machine_maintenance_log_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers what the service adds; the **Transaction contract TC1–TC6 is defined there** and cited here. Below the service: `tests/unit/managers/machine_maintenance_log_manager.spec.md` (APPROVED), `tests/unit/dao/machine_maintenance_log.spec.md` (APPROVED), `tests/unit/managers/machine_activity_manager.spec.md` (the activity entries the manager writes).

> **Routed here and written as rules:** machine maintenance log manager FU-1 (a) BUG-1150 (`get_log` R2, R3); (b) the 500 for `DataError` and the 409 for `IntegrityError` (`create_log` R3; integration-only beyond "passed on unchanged"); (c) schema errors are the endpoint's (BUG-461); (d) the 200-with-row answer of `DELETE` (`delete_log` R1, stated, no question: the manager review called it harmless, the frontend types it `void`). No new bug, no question.
>
> **Verified by running** (`h.py`, `v5_tag2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, rolled back; nothing persisted): `get_log`'s parameters (`db`, `log_id`, `workspace_id`; no `include_deleted`). The manager's behavior, the deleted log returned with 200 included, was verified in the manager review (`mmlm` scripts). The transaction mechanics were verified on the department service, whose code is the same shape (TC1–TC6). **Not run:** HTTP; the intended behavior of BUG-1150.

## Review
> No questions.

Existing bugs written as rules here, no new ID: **BUG-1150** `get_log` R2, R3. Reached through the manager and cited, one pass-through case each, strict or non-strict as in `machine_maintenance_log_manager.cases.md`: BUG-1100 (order), BUG-1101, BUG-1102, BUG-1151 … BUG-1158.

Checked and **not** violated: everything the manager spec lists under "Checked"; nothing here adds a filter, a name, a lock or a sort. **HR-7** — `GET /machine-maintenance-logs/` enforces `1 <= limit <= 1000`, `skip >= 0`.

**Permission checks:** none; any active member may log, edit and remove maintenance (as `department_service.spec.md`).

## Overview
`MachineMaintenanceLogService` is the transaction boundary for maintenance logs, the record of work done on machines. The `/machine-maintenance-logs/` endpoints call it; it calls `MachineMaintenanceLogManager` and commits, rolls back and re-reads around it. The manager also writes one machine activity entry per change; it is part of the same commit. The service adds no check, translation or shaping.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. (`deleted_at` and the activity entry's `created_at` are the DAOs' clocks: manager spec.)
**Integration-only behavior:** as `department_service.spec.md`; the `include_deleted` query parameter on `GET /machine-maintenance-logs/{id}/`; the `maintenance_type` enum check of the endpoint; `DataError` → 500 (no handler).

**Facts for the test designer**
- Import: `from app.services.machine_maintenance_log_service import MachineMaintenanceLogService, machine_maintenance_log_service`. The manager is the attribute `manager`. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- The manager's rules, errors, activity entries and Notes (how to build machines, factories, logs): `tests/unit/managers/machine_maintenance_log_manager.spec.md`.

**Notes for the test designer**
- Session, commits, setup before error paths, TC4 / TC5 patching: as the Notes of `department_service.spec.md`.
- **TC1 here includes the activity entry:** after a successful create, update or delete, a test-level `db.rollback()` leaves both the log change and its `machine_activity_events` row (event types as the manager spec). After a refusal or a database error, neither is saved (TC3).
- **IntegrityError pass-through (`create_log` R3):** an unknown `user_id` fails the `created_by` / activity `performed_by` foreign key at the flush (pgcode `23503`; manager spec verified "unknown user on all three writes"). Ordinary pass: unchanged, nothing saved, session usable.
- **DataError pass-through (`create_log` R3):** `cost` beyond `Numeric(15, 2)` (manager P7) is refused by the schema once BUG-1157 is fixed; to reach a `DataError` at the flush independently of that fix, use `performed_by` of 256 characters built with `MachineMaintenanceLogCreate.model_construct(...)` (BUG-1156 refuses it in the schema, not in the manager). Assert `sqlalchemy.exc.DataError` (`.orig.pgcode == "22001"`, manager R9a's today-shape), nothing saved, session usable. This case passes today and after the fixes, because `model_construct` skips the schema.
- **BUG-1150:** the parameter does not exist today (`TypeError`) → strict xfail; R2 (404 by default) needs no new parameter: today the deleted log is returned → strict xfail.

## Not specified
- `MachineMaintenanceLogService.__init__` — stores the manager, no logic.
- `machine_maintenance_log_service` — module-level singleton, no logic.

---

## `MachineMaintenanceLogService.create_log(db, log_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /machine-maintenance-logs/`)

**Returns:** the new `MachineMaintenanceLog`, committed and re-read (TC1, TC2): `cost` is the stored, rounded value after the re-read (manager spec: the instance holds the unrounded value until refreshed).

**Rules:**
- **R1.** The log and its `maintenance_logged` activity entry are created by the manager (`create_log` rules) and committed together (TC1); the log is returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Machine with ID <machine_id> not found`; 400 `Cannot create maintenance log for a deleted machine`.
- **R3.** A database error at the flush (`DataError`, `IntegrityError`) reaches the caller unchanged after the rollback; nothing saved; the session is usable.
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2, R3.

**Side effects:** one log and one activity row, committed; on error, rolled back.

---

## `MachineMaintenanceLogService.update_log(db, log_id, log_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /machine-maintenance-logs/{id}/`)

**Returns:** the `MachineMaintenanceLog`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The log is changed by the manager (`update_log` rules, with its activity entry when a field changed) and committed with it (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Maintenance log with ID <log_id> not found`; 400 `Cannot update a deleted maintenance log`.
- **R3.** Database errors and commit / re-read failures as `create_log` R3, R4.

**Errors:** as R2, R3. **Side effects:** the log's changed fields and the activity row, committed; on error, rolled back.

---

## `MachineMaintenanceLogService.get_log(db, log_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /machine-maintenance-logs/{id}/`)

**Inputs:** `include_deleted` — [BUG-1150] new, default `False`, passed on, reachable from the API.

**Rules:**
- **R1.** The manager's `get_log` answer for this id and workspace is returned unchanged (manager R1, R4, R5, R6).
- **R2.** [BUG-1150] (manager FU-1 (a), HR-4) A soft-deleted log → 404 `Maintenance log with ID <log_id> not found` by default. *(Today: returned, 200.)*
- **R3.** [BUG-1150] With `include_deleted=True` it is returned (manager R3a). *(Today: no such parameter, here or in the manager.)*
- **R4.** Read only (TC6).

**Errors:** `HTTPException` 404 `Maintenance log with ID <log_id> not found`.

**Side effects:** none

---

## `MachineMaintenanceLogService.list_logs(db, workspace_id, machine_id=None, maintenance_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /machine-maintenance-logs/`, always with `skip`, `limit`)

**Rules:**
- **R1.** The list is the manager's `list_logs` for `machine_id`, `maintenance_type`, `skip`, `limit` (defaults `None`, `None`, `0`, `100`), unchanged: filters, order and paging are the manager's (R1–R13, with BUG-1100, BUG-1101, BUG-1152).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none

---

## `MachineMaintenanceLogService.delete_log(db, log_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /machine-maintenance-logs/{id}/`, which answers 200 with the row; the frontend ignores the body)

**Returns:** the soft-deleted `MachineMaintenanceLog`, committed and re-read: `is_deleted = True` and the fields the manager's `delete_log` sets.

**Rules:**
- **R1.** The log is soft-deleted by the manager, with its `maintenance_removed` activity entry, committed together (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Maintenance log with ID <log_id> not found`; 400 `Maintenance log is already deleted`.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2. **Side effects:** the soft-delete fields and one activity row, committed; on error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 27–34 | create: manager → commit → refresh → return | `create_log` R1; TC1, TC2 |
| 35–37 | create: any exception → rollback, re-raise | `create_log` R2, R3, R4; TC3–TC5 |
| 44–51 | update: manager → commit → refresh → return | `update_log` R1 |
| 52–54 | update: any exception → rollback, re-raise | `update_log` R2, R3 |
| 60 | get: manager, positional, no `include_deleted` (BUG-1150) | `get_log` R1–R4 |
| 69–73 | list: manager with every filter and paging argument | `list_logs` R1, R2 |
| 80–87 | delete: manager → commit → refresh → return | `delete_log` R1 |
| 88–90 | delete: any exception → rollback, re-raise | `delete_log` R2, R3 |
| `base_service.py` 26–30, 39 | commit / commit fails / rollback | TC1, TC3, TC4 (`department_service.spec.md`) |
| 94 | module singleton | Not specified |

## Gap log
G1 (machine_maintenance_log_service.cases.md gap 1) — Test mechanics — `IntegrityError` through an unknown `user_id`. Notes.
