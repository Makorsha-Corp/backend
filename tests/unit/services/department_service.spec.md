# Spec — `app/services/department_service.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **First service specs.** This file sets the form for `tests/unit/services/`. A service spec covers only what the service adds on top of its manager: the transaction (commit, rollback, re-read), error translation, permission checks, response shaping, and which arguments reach the manager. What the manager decides is **cited, not restated**: `tests/unit/managers/department_manager.spec.md` (APPROVED) and below it `tests/unit/dao/department.spec.md`, `tests/unit/dao/base.spec.md`. The **Transaction contract** below (TC1–TC6) is written once here; the other `BaseService` specs point to it.

> **Routed here and written as rules:** department manager Q5 / BUG-005 (the API half: `get_department` must pass `include_deleted`, HR-4 "reachable from the API") and Q10 / BUG-010 (`get_departments` must pass `include_deleted`). No new bug; BUG-005's register row now names this service.
>
> **Standing decisions applied here (not asked again):** HR-4: a soft-deleted row is hidden unless asked for, and an `include_deleted` option is reachable from the API. Refusals stay `HTTPException`s from the manager; a service never turns them into something else.
>
> **Verified by running** (scripts `h.py`, `v1_tx.py`, `v3_http.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, each in one outer transaction rolled back against `marker_test`, the session built as the unit-test `db` fixture, `join_transaction_mode="create_savepoint"`; nothing persisted): a created department survives a later `db.rollback()` of the test; a 409 from the manager rolls back an uncommitted setup row of the same session and leaves a committed one; the session is usable after the rollback; a patched `commit` that raises gives two rollbacks and nothing saved; a patched `refresh` that raises leaves the row saved; a deleted department is returned by `get_department` (200, `is_deleted = True`); a second delete answers 400 `Department is already deleted`; another workspace's id answers 404; the methods' parameter lists (no `include_deleted`); `GET /departments/?include_deleted=true` answers 200 and ignores the parameter. **Not run:** two concurrent requests; the intended behavior of BUG-005 and BUG-010.

## Review
> No questions. Nothing here is the owner's or the delegate's decision: both rules that change come from the department manager review (Q5, Q10) and HR-4.

Existing bugs written as rules here, no new ID: **BUG-005** `get_department` R2, R3; **BUG-010** `get_departments` R2. Reached through the manager and cited, one pass-through case each: BUG-001 … BUG-004, BUG-006 … BUG-009.

Checked and **not** violated: **HR-1 … HR-3, HR-8, HR-9** — decided in the manager and the schemas, nothing here touches a name or an audit field. **HR-5, HR-6** — the manager's (BUG-006, BUG-007, BUG-008). **HR-7** — `GET /departments/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10** — no harmful state; a department delete is a plain soft delete. **HR-11 … HR-15** — no external system, batch or money. **HR-16** — every lookup is by the caller's workspace, in the manager.

**Permission checks:** none. The service takes no role, and any active member of the workspace may create, edit and delete departments. This is the application's model for reference data: only workspace membership and administration endpoints look at roles today (OQ-4 asks it for the permission table only). Not a question here.

## Overview
`DepartmentService` is the transaction boundary for departments, the organisational units of a workspace. The `/departments/` endpoints call it; it calls `DepartmentManager` and commits, rolls back and re-reads around it. It adds no check, no translation and no shaping of its own: every refusal is the manager's `HTTPException`, passed on unchanged.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. (`deleted_at` comes from `app.dao.department.utcnow`: department DAO spec; the service adds no clock.)
**Integration-only behavior:** the HTTP status and body of a passed-on `HTTPException`; the `include_deleted` query parameter on `GET /departments/` and `GET /departments/{id}/`; schema validation (400 today, BUG-461; 422 intended); `skip >= 0`, `1 <= limit <= 1000`; the global `IntegrityError` handler; the dependency that closes the request's session.

### Transaction contract (TC) — every `BaseService` write
`BaseService._commit_transaction` commits and, if the commit raises, rolls back and re-raises. `_rollback_transaction` rolls back. A service write method calls the manager, commits, re-reads the row with `db.refresh` and returns it, all inside one `try`; any exception rolls back and is re-raised. As outcomes:
- **TC1.** A write that succeeds is committed: the change survives a later rollback of the same session.
- **TC2.** The returned object is the manager's row, re-read from the database after the commit: columns the database sets (`created_at`, `updated_at`) are loaded on it, and it is not expired.
- **TC3.** Any exception from the manager (`HTTPException`, `IntegrityError`, `DataError`, `pydantic.ValidationError`, anything) rolls the session back and reaches the caller **as the same object**: same type, same `status_code` and `detail` for an `HTTPException`. Nothing the call wrote is saved, **and every other uncommitted change pending in that session is discarded with it**. The session is usable afterwards.
- **TC4.** If the commit itself raises, the session is rolled back and the commit's exception reaches the caller unchanged; nothing is saved.
- **TC5.** If the re-read after a successful commit raises, that exception reaches the caller, and the change **stays saved** (the rollback after a commit has nothing to undo).
- **TC6.** A read (get, list) neither commits nor rolls back: changes pending in the session stay pending, and an exception from the manager reaches the caller unchanged.

**Facts for the test designer**
- Import: `from app.services.department_service import DepartmentService, department_service`. `DepartmentService()` takes no arguments; its manager is the attribute `department_manager`, the module singleton of `app.managers.department_manager`. All parameters are positional-or-keyword. The endpoints pass everything after `db` by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.
- The manager's rules, errors and messages: `tests/unit/managers/department_manager.spec.md`. Table facts: `tests/unit/dao/department.spec.md`.

**Notes for the test designer**
- **The `db` fixture already makes service commits safe** (`tests/unit/conftest.py`: `join_transaction_mode="create_savepoint"`). A `commit()` inside the service only releases a savepoint; the fixture's outer rollback discards everything after the test. Nothing needs patching for the normal paths. Verified.
- **Asserting "committed" (TC1):** after the call, `db.rollback()` in the test, then re-select the row: it is still there. **Asserting "nothing saved" (TC3, TC4):** re-select after the call: absent or unchanged.
- **Setup before an error path (TC3):** the service's rollback discards **uncommitted** setup rows too (verified: a flushed, uncommitted department vanished after a 409). So on every path that raises, build the setup and then call `db.commit()` (it only releases a savepoint) before calling the service. A committed setup row survives the service's rollback (verified). Use this deliberately in one TC3 case: an uncommitted extra row is gone afterwards.
- **TC4:** `unittest.mock.patch.object(db, "commit", side_effect=RuntimeError("boom"))`; assert `RuntimeError` is raised and, after the patch is gone, the row is absent. Count rollbacks only as "at least one" (today two run).
- **TC5:** `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`; assert `RuntimeError` and that the row is present after a test-level `db.rollback()`.
- **TC6:** add a pending row (`db.add` + `flush`, no commit), call the read, then `db.rollback()`: the pending row is gone, so the read did not commit.
- **Pass-through cases:** one case per manager bug reached (BUG-001 … BUG-004, BUG-006 … BUG-009), written to the intended behavior, strict or non-strict xfail exactly as in the manager's cases file (`tests/unit/managers/department_manager.cases.md`). Do not re-test the manager's edge cases here.
- **BUG-005, BUG-010:** the parameter does not exist today: calling with `include_deleted=` raises `TypeError` → strict xfail. Build a deleted department with `department_service.delete_department` (or directly with `is_deleted=True`), commit, then call.

## Not specified
- `DepartmentService.__init__` — stores the manager, no logic.
- `department_service` — module-level singleton, no logic.
- `BaseService` itself (`app/services/base_service.py`) — its two helpers are specified as outcomes in TC1–TC6; no spec of its own in this batch.

---

## `DepartmentService.create_department(db, department_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /departments/`)

**Purpose:** Create a department and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | the request's session |
| `department_in` | `DepartmentCreate` | passed to the manager as `department_data` |
| `workspace_id` | int | caller's workspace, passed on |
| `user_id` | int | acting user, passed on |

**Returns:** the new `Department`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The department is created exactly as `DepartmentManager.create_department` creates it (manager spec `create_department` R1–R6, including BUG-001 … BUG-004), in the given workspace, with `created_by = user_id`; it is committed (TC1) and returned re-read, with `id` and `created_at` set (TC2).
- **R2.** A refusal of the manager (409 `Department with name '<name>' already exists`, and the database-level 409 of BUG-003) reaches the caller unchanged and nothing is saved (TC3).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| any refusal of the manager | the manager's `HTTPException`, unchanged | the manager's |
| database error at the flush or the commit | the same `sqlalchemy.exc` error, unchanged | — |

**Side effects:** one `departments` row, committed. On any error: session rolled back.

---

## `DepartmentService.get_department(db, department_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /departments/{id}/`)

**Purpose:** One department by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `department_id` | int | passed on |
| `workspace_id` | int | passed on |
| `include_deleted` | bool, default `False` | [BUG-005] new; passed on unchanged; reachable from the API as a query parameter |

**Returns:** the manager's `Department`.

**Rules:**
- **R1.** A live department of the workspace is returned as the manager returns it.
- **R2.** [BUG-005] (department manager Q5, HR-4) A soft-deleted department → 404 `Department with ID <department_id> not found` by default. *(Today: returned, 200, `is_deleted = True`. Verified.)*
- **R3.** [BUG-005] With `include_deleted=True` a soft-deleted department of the workspace is returned; another workspace's id is still 404. *(Today: the parameter does not exist.)*
- **R4.** Unknown id, `0`, another workspace's id → the manager's 404 `Department with ID <department_id> not found`, unchanged.
- **R5.** Read only (TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-005] deleted without `include_deleted` | `HTTPException` 404 | `Department with ID <department_id> not found` |

**Side effects:** none

---

## `DepartmentService.get_departments(db, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /departments/`, always with `skip`, `limit`, `search`)

**Purpose:** The departments of a workspace, optionally searched by name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `search` | str or `None` | passed on as is |
| `skip`, `limit` | int, defaults `0`, `100` | passed on as is; the service sets no bound |
| `include_deleted` | bool, default `False` | [BUG-010] new; passed on; reachable from the API |

**Returns:** the manager's list.

**Rules:**
- **R1.** The list is `DepartmentManager.search_departments` for these arguments: filtering, search, order and paging are the manager's rules R1–R8 (BUG-006, BUG-007, BUG-008), not repeated here. With no arguments after `workspace_id`, the manager gets `search=None`, `skip=0`, `limit=100`.
- **R2.** [BUG-010] (department manager Q10, HR-4) `include_deleted=True` reaches the manager, so soft-deleted departments are listed too (manager R5); the default `False` leaves them out. *(Today: the service has no such parameter and the API cannot list deleted departments.)*
- **R3.** Read only (TC6).

**Errors:** none of its own; negative `skip` / `limit` reach the database (`DataError`) when called directly; the endpoint refuses them first.

**Side effects:** none

---

## `DepartmentService.update_department(db, department_id, department_in, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /departments/{id}/`)

**Purpose:** Edit a department and save it.

**Returns:** the `Department`, committed and re-read (TC1, TC2): `updated_at` is loaded.

**Rules:**
- **R1.** The department is changed exactly as `DepartmentManager.update_department` changes it (manager spec R1–R11, including BUG-001 … BUG-004, BUG-009); committed (TC1); returned re-read (TC2), so the database's `updated_at` is visible on it.
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Department with ID <department_id> not found`, 400 `Cannot update deleted department`, 409 `Department with name '<name>' already exists`.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2; database errors unchanged.

**Side effects:** the row's changed fields, `updated_by`, `updated_at`, committed. On any error: rolled back.

---

## `DepartmentService.delete_department(db, department_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /departments/{id}/`, which answers 200 with the row)

**Purpose:** Soft-delete a department and save it.

**Returns:** the soft-deleted `Department`, committed and re-read: `is_deleted = True`, `deleted_by = user_id`, `deleted_at` set (department DAO `soft_delete`).

**Rules:**
- **R1.** The department is soft-deleted exactly as `DepartmentManager.delete_department` does it (manager spec R1–R4); committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Department with ID <department_id> not found`; 400 `Department is already deleted` (verified on a second delete).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2.

**Side effects:** the soft-delete fields, committed. On any error: rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `base_service.py` 26–27 | commit succeeds | TC1 |
| `base_service.py` 28–30 | commit raises → rollback, re-raise | TC4 |
| `base_service.py` 39 | rollback | TC3 |
| 47–60 | create: manager → commit → refresh → return | `create_department` R1, TC1, TC2 |
| 62–64 | create: any exception → rollback, re-raise | `create_department` R2, R3, TC3–TC5 |
| 86 | get: manager, positional, no `include_deleted` (BUG-005) | `get_department` R1–R5 |
| 109–115 | list: manager with `search`, `skip`, `limit`, no `include_deleted` (BUG-010) | `get_departments` R1–R3 |
| 141–155 | update: manager → commit → refresh → return | `update_department` R1, TC1, TC2 |
| 157–159 | update: any exception → rollback, re-raise | `update_department` R2, R3 |
| 183–196 | delete: manager → commit → refresh → return | `delete_department` R1 |
| 198–200 | delete: any exception → rollback, re-raise | `delete_department` R2, R3 |
| 204 | module singleton | Not specified |
