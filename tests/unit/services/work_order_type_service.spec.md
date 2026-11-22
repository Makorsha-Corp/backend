# Spec — `app/services/work_order_type_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers what the service adds; the **Transaction contract TC1–TC6 is defined there** and cited here. Below the service: `app/managers/work_order_type_manager.py` (**no spec yet**), `tests/unit/dao/work_order_type.spec.md` (APPROVED; it points to `tests/unit/dao/department.spec.md` for the shared rules) and `tests/unit/dao/base.spec.md`.
>
> **The manager is not described yet.** It is the department manager's code with the names changed (read, not run: same checks, same order, same messages with "Work order type"). Its rules belong to its own spec; work order type DAO FU-1 lists what that review must look at. This spec therefore names the manager's refusals only as values that must pass through unchanged, and makes no rule of the manager's own behavior.

> **House-rule lines logged here (2026-11-03):** BUG-1520, BUG-1521. No question; nothing decided under the delegation.
>
> **Verified by running** (`h.py`, `v1_tx.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): create, a duplicate (409 `Work order type 'Repair' already exists`), delete, `get_work_order_type` of the deleted type (returned, `is_deleted = True`), a create with the deleted type's name (`IntegrityError` 23505 `uq_wo_type_workspace_name`, BUG-1214; the session usable after the service's rollback), the list's parameters (no `include_deleted`). The transaction mechanics were verified on the department service, whose code is the same line for line (TC1–TC6). **Not run:** HTTP; the intended behavior of BUG-1520, BUG-1521.

## Review

### House-rule violations — applied automatically

- **HR-4** `get_work_order_types` R2 — the manager's `search_work_order_types` has an `include_deleted` flag, but the service never passes it and the endpoint has no such parameter: deleted types cannot be listed through the API. Intended: `include_deleted` (default `False`) reachable from `GET /work-order-types/` and passed on (per BUG-010).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1520 (pattern `flag-unreachable-from-api`). Rules: `get_work_order_types` R2.
- **HR-4** `get_work_order_type` R2, R3 — a soft-deleted type is returned by id (verified, 200 with `is_deleted = True`), although the list hides it. Intended: 404 by default; a new `include_deleted=True` returns it, reachable from the API (per BUG-005). The fix is in the manager (`get_work_order_type` gains the parameter) and here (pass it on).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1521 (pattern `get-returns-soft-deleted`). Rules: `get_work_order_type` R2, R3. The manager's spec, when written, takes this ID for its own rule.

Reached through the manager and cited, one pass-through case: **BUG-1214** (a deleted type's name cannot be used again: `create_work_order_type` R3). **BUG-1228** (a deleted type chosen on work orders) is the work order managers', not reached here.

Checked and **not** violated here: **HR-1, HR-2, HR-5, HR-6, HR-8, HR-9** — the manager's and the schema's (work order type DAO FU-1 lists them for that review). **HR-7** — `GET /work-order-types/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10 … HR-15** — no harmful state, external system or money. **HR-16** — the manager looks rows up by the caller's workspace.

**Permission checks:** none; any active member may create, edit and delete types (as `department_service.spec.md`).

## Overview
`WorkOrderTypeService` is the transaction boundary for work order types, the user-defined kinds of work order of a workspace ("Repair", "Inspection"). The `/work-order-types/` endpoints call it; it calls `WorkOrderTypeManager` and commits, rolls back and re-reads around it. It adds no check, translation or shaping: every refusal is the manager's `HTTPException`, passed on unchanged.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none (`deleted_at` is the DAO's clock: department DAO spec).
**Integration-only behavior:** as `department_service.spec.md`; the `include_deleted` query parameters; the global `IntegrityError` handler (BUG-1214's 409 "This resource already exists" today).

**Facts for the test designer**
- Input schemas: `from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate`. `WorkOrderTypeCreate(name: str)`: `name` is the only field, required, with no length, trim or blank check (HR-1 is the manager review's, DAO FU-1). `WorkOrderTypeUpdate(name: str | None = None)`: the only field. `WorkOrderTypeResponse` adds `id` to `name`.
- The manager's search, as read and run (`v7_gaps.py`, work order types; delivery methods are the same code): a case-insensitive substring of the name (`"pair"` and `"REPAIR"` find "Repair"), applied in Python to the page already cut by `skip` / `limit`; `%` is literal (`"%"` finds nothing); `None` and `""` mean no search. Only to build pass-through cases; not a rule of this service.
- Import: `from app.services.work_order_type_service import WorkOrderTypeService, work_order_type_service`. The manager is the attribute `manager` (the singleton of `app.managers.work_order_type_manager`). Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- Table `work_order_types`: as `departments` (department DAO spec, Model facts) plus the unique constraint `uq_wo_type_workspace_name` on `(workspace_id, name)` over all rows, deleted included (work order type DAO spec, BUG-1214).
- The manager's refusals, as read from its code (for pass-through cases only): create, duplicate live name compared with `==` → 409 `Work order type '<name>' already exists`; get / update / delete, not found or another workspace → 404 `Work order type with ID <type_id> not found`; update of a deleted type → 400 `Cannot update a deleted work order type`; delete of a deleted type → 400 `Work order type is already deleted`.

**Notes for the test designer**
- Session, commits, setup before error paths, TC4 / TC5 patching: exactly as the Notes of `department_service.spec.md`.
- One case per TC rule on one write method is enough for TC2, TC4, TC5 here (the code of the three writes is identical); TC1 and TC3 get one case per write method.
- **BUG-1214 pass-through:** create a type, delete it through the service, then create one with the same name: intended, a new row is returned; today `IntegrityError` → strict xfail. No `begin_nested` is needed: the service's own rollback leaves the session usable (verified). Commit the setup first (it is the "setup before an error path" note).
- **BUG-1520, BUG-1521:** the parameter does not exist today (`TypeError`) → strict xfail. For BUG-1521 R2 (404 by default) the call needs no new parameter: today it returns the row → strict xfail.

## Not specified
- `WorkOrderTypeService.__init__` — stores the manager, no logic.
- `work_order_type_service` — module-level singleton, no logic.

---

## `WorkOrderTypeService.create_work_order_type(db, type_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-order-types/`)

**Purpose:** Create a work order type and save it.

**Returns:** the new `WorkOrderType`, committed and re-read (TC1, TC2): `id`, `created_at` set, `created_by = user_id`, `workspace_id` the given one.

**Rules:**
- **R1.** The type is created by the manager from `type_in`, in the given workspace, by `user_id`; committed (TC1); returned re-read (TC2).
- **R2.** The manager's 409 for a live duplicate name reaches the caller unchanged; nothing saved (TC3).
- **R3.** [BUG-1214] (pass-through) A name used only by a soft-deleted type of the workspace can be used again: the new type is created and returned. *(Today: `IntegrityError` 23505 on `uq_wo_type_workspace_name` reaches the caller after the rollback; the session is usable. Verified.)*
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** the manager's `HTTPException` unchanged; database errors unchanged (TC3).

**Side effects:** one `work_order_types` row, committed; on error, rolled back.

---

## `WorkOrderTypeService.get_work_order_type(db, type_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /work-order-types/{id}/`)

**Inputs:** `include_deleted` — [BUG-1521] new, default `False`, passed on, reachable from the API.

**Returns:** the manager's `WorkOrderType`.

**Rules:**
- **R1.** A live type of the workspace is returned.
- **R2.** [BUG-1521] (HR-4) A soft-deleted type → 404 `Work order type with ID <type_id> not found`. *(Today: returned, 200. Verified.)*
- **R3.** [BUG-1521] With `include_deleted=True` it is returned; another workspace's id stays 404. *(Today: no such parameter, here or in the manager.)*
- **R4.** Unknown id, `0`, another workspace's id → the manager's 404, unchanged.
- **R5.** Read only (TC6).

**Errors:** `HTTPException` 404 `Work order type with ID <type_id> not found`.

**Side effects:** none

---

## `WorkOrderTypeService.get_work_order_types(db, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /work-order-types/`, always with `search`, `skip`, `limit`)

**Returns:** the manager's list.

**Rules:**
- **R1.** The list is the manager's `search_work_order_types` for `search`, `skip`, `limit` (defaults `None`, `0`, `100`), unchanged. How it filters, pages and orders is the manager's (not yet specified; work order type DAO FU-1).
- **R2.** [BUG-1520] (HR-4) `include_deleted=True` reaches the manager, so deleted types are listed too; the default leaves them out. *(Today: the service has no such parameter.)*
- **R3.** Read only (TC6).

**Errors:** none of its own.

**Side effects:** none

---

## `WorkOrderTypeService.update_work_order_type(db, type_id, type_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /work-order-types/{id}/`)

**Returns:** the `WorkOrderType`, committed and re-read (TC1, TC2): `updated_by = user_id`, `updated_at` loaded.

**Rules:**
- **R1.** The type is changed by the manager; committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals (404, 400 deleted, 409 duplicate) reach the caller unchanged; nothing saved (TC3).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** the manager's `HTTPException` unchanged; database errors unchanged.

**Side effects:** changed fields, `updated_by`, `updated_at`, committed; on error, rolled back.

---

## `WorkOrderTypeService.delete_work_order_type(db, type_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-order-types/{id}/`, 200 with the row)

**Returns:** the soft-deleted `WorkOrderType`, committed and re-read: `is_deleted = True`, `deleted_by = user_id`, `deleted_at` set.

**Rules:**
- **R1.** The type is soft-deleted by the manager; committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals (404; 400 `Work order type is already deleted`) reach the caller unchanged; nothing saved (TC3).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2.

**Side effects:** the soft-delete fields, committed; on error, rolled back. Work orders that use the type keep it (BUG-1228 is about choosing it on new ones).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–27 | create: manager → commit → refresh → return | `create_work_order_type` R1, R3; TC1, TC2 |
| 28–30 | create: any exception → rollback, re-raise | `create_work_order_type` R2, R3, R4; TC3–TC5 |
| 33 | get: manager, positional, no `include_deleted` (BUG-1521) | `get_work_order_type` R1–R5 |
| 39–41 | list: manager with `search`, `skip`, `limit`; no `include_deleted` (BUG-1520) | `get_work_order_types` R1–R3 |
| 46–52 | update: manager → commit → refresh → return | `update_work_order_type` R1 |
| 53–55 | update: any exception → rollback, re-raise | `update_work_order_type` R2, R3 |
| 58–64 | delete: manager → commit → refresh → return | `delete_work_order_type` R1 |
| 65–67 | delete: any exception → rollback, re-raise | `delete_work_order_type` R2, R3 |
| `base_service.py` 26–30, 39 | commit / commit fails / rollback | TC1, TC3, TC4 (`department_service.spec.md`) |
| 71 | module singleton | Not specified |

## Follow-ups for other reviews
> Nothing below is a rule of this service.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order type manager** (`app/managers/work_order_type_manager.py`, not yet specified) | (a) BUG-1521: `get_work_order_type` gains `include_deleted` (404 for a deleted type by default); use this ID. (b) Its list must honour `include_deleted` before paging (HR-5): today it drops deleted rows after `limit`, so BUG-1520's `include_deleted=False` pages are short. (c) Everything in work order type DAO FU-1. | HR-4 lines |

## Gap log
G1 (work_order_type_service.cases.md gap 1) — Fact — input schemas named. Facts.
G2 (gap 2) — Fact, verified by running — the manager's search described for case-building. Facts.
