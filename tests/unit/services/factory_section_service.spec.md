# Spec — `app/services/factory_section_service.py`

> **Status:** APPROVED (2026-11-04; nothing open)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined there** and cited here, not restated. Below the service: `tests/unit/managers/factory_section_manager.spec.md` (APPROVED), `tests/unit/dao/factory_section.spec.md`, `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** factory section manager FU-3 (BUG-916, BUG-925: `include_deleted` on `get_factory_section`; BUG-920: on `get_factory_sections`; `FactorySectionResponse` has no `is_deleted`, D1 below; the commit / rollback and `db.refresh` after each write). No new bug; the register rows of BUG-916 and BUG-920 now name this service.
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** D1 (`is_deleted` on `FactorySectionResponse`, as `factory_service.spec.md` D1). Not the owner's answer; nothing here touches money, stock, an order workflow or who may see or do what.
>
> **Standing decisions applied here (not asked again):** HR-4: a soft-deleted row is hidden unless asked for, and an `include_deleted` option is reachable from the API. Every refusal of the manager is an `HTTPException` and is passed on unchanged; the manager raises no `ValueError`, so there is nothing to translate.
>
> **Verified by running** (`h.py`, `v1_fac.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; HTTP through `TestClient` with overridden dependencies; nothing persisted): create, delete and re-read; a deleted section is returned by `get_factory_section` (`GET /factory-sections/{id}/` answers 200 with `name`, `factory_id`, `id` only); a section of a deleted factory is returned by id; a second delete answers 400 `Factory section is already deleted`; a missing factory on create answers 404 `Factory with ID 999999999 not found`; an unknown section on update answers 404 `Factory section with ID 999999999 not found`; `include_deleted=` on `get_factory_sections` raises `TypeError`; `GET /factory-sections/?limit=0` answers 400 (BUG-461). The transaction mechanics (TC1–TC6) were verified on the same harness through `FactoryService`, which has the same code shape line for line. **Not run:** two concurrent requests; the intended behavior of BUG-916, BUG-920, BUG-925.

## Review
> All answered; nothing pending.

### D1. A listed or opened deleted section cannot be told from a live one — ✅ add `is_deleted` to the response (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** `FactorySectionResponse` carries only `id`, `name`, `factory_id`. BUG-916 and BUG-920 make deleted sections reachable with `include_deleted=true` (factory section manager FU-3).
**What happens today:** Deleted sections are hidden from the list and shown by id (BUG-916) with no flag.
**Example:** With `include_deleted=true`, "Paint" (deleted) and "Cut" (live) would look the same.
**Rules affected:** `get_factory_section` R2–R4, `get_factory_sections` R2 (integration-only part)
**Answer:** part of the BUG-916 / BUG-920 fix: `FactorySectionResponse` gains `is_deleted: bool`. No new ID. The service returns the ORM row, which has the column.

Existing bugs written as rules here, no new ID: **BUG-916** `get_factory_section` R2, R3; **BUG-925** `get_factory_section` R4; **BUG-920** `get_factory_sections` R2. Reached through the manager and cited, one pass-through case each, strict or non-strict exactly as in `tests/unit/managers/factory_section_manager.cases.md`: BUG-903 … BUG-908, BUG-911 … BUG-915, BUG-917 … BUG-919, BUG-921 … BUG-924, BUG-926 … BUG-928.

Checked and **not** violated: everything the manager spec lists under "Checked". **HR-7** — `GET /factory-sections/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10** — a section delete is a plain soft delete. **HR-16** — every lookup is by the caller's workspace, in the manager.

**Permission checks:** none; any active member may create, edit and delete sections (as `department_service.spec.md`).

## Overview
`FactorySectionService` is the transaction boundary for factory sections, the named areas inside a factory. The `/factory-sections/` endpoints call it; it calls `FactorySectionManager` and commits, rolls back and re-reads around it. It adds no check, no translation and no shaping of its own.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. (`deleted_at`: factory section DAO; the service adds no clock.)
**Integration-only behavior:** as `department_service.spec.md`; the `include_deleted` query parameter on `GET /factory-sections/` and `GET /factory-sections/{id}/` and `is_deleted` in `FactorySectionResponse` (D1); schema validation (400 today, BUG-461); `skip >= 0`, `1 <= limit <= 1000`.

**Facts for the test designer**
- Import: `from app.services.factory_section_service import FactorySectionService, factory_section_service`. `FactorySectionService()` takes no arguments; its manager is the attribute `factory_section_manager`, the singleton of `app.managers.factory_section_manager`. The service calls the manager's get positionally and everything else by keyword; the endpoints pass everything after `db` by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.
- The manager's rules, errors and messages: `tests/unit/managers/factory_section_manager.spec.md`.

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): exactly as `department_service.spec.md` Notes. Build a factory directly (`Factory(workspace_id, name, abbreviation)`) and commit before calling.
- **BUG-916, BUG-920, BUG-925:** the parameter does not exist today: calling with `include_deleted=` raises `TypeError` → strict xfail.
- **Delete today also erases machine assignments (BUG-908):** what the commit saves is whatever the manager flushed; one pass-through case for BUG-908 through the service (assignment row still there after the delete, intended), as the manager's cases file marks it.
- **Pass-through cases:** one per manager bug reached, intended behavior, strict / non-strict as in the manager's cases file.

## Not specified
- `FactorySectionService.__init__` — stores the manager, no logic.
- `factory_section_service` — module-level singleton, no logic.

---

## `FactorySectionService.create_factory_section(db, section_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /factory-sections/`, 201)

**Purpose:** Create a section in a factory and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `section_in` | `FactorySectionCreate` | passed to the manager as `section_data` |
| `workspace_id` | int | caller's workspace, passed on |
| `user_id` | int | acting user, passed on |

**Returns:** the new `FactorySection`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The section is created exactly as `FactorySectionManager.create_factory_section` creates it (manager spec R1–R10, including BUG-911 … BUG-913, BUG-915); committed (TC1); returned re-read with `id` and `created_at` set (TC2). Verified.
- **R2.** The manager's refusals reach the caller unchanged and nothing is saved (TC3): 404 `Factory with ID <factory_id> not found` (verified), 400 `Cannot create section for deleted factory`, 409 `Section with name '<name>' already exists in this factory`.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2; database errors unchanged.

**Side effects:** one `factory_sections` row, committed. On any error: rolled back.

---

## `FactorySectionService.get_factory_section(db, section_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /factory-sections/{id}/`)

**Purpose:** One section by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `section_id`, `workspace_id` | int | passed on |
| `include_deleted` | bool, default `False` | [BUG-916] new; passed on unchanged; reachable from the API |

**Returns:** the manager's `FactorySection`.

**Rules:**
- **R1.** A live section of the workspace in a live factory is returned as the manager returns it.
- **R2.** [BUG-916] (HR-4) A soft-deleted section → 404 `Factory section with ID <section_id> not found` by default. *(Today: returned, 200. Verified.)*
- **R3.** [BUG-916] With `include_deleted=True` a soft-deleted section of the workspace is returned; another workspace's id is still 404. *(Today: the parameter does not exist.)*
- **R4.** [BUG-925] A live section whose factory is soft-deleted → the same 404 by default; returned with `include_deleted=True` (manager R5). *(Today: returned. Verified.)*
- **R5.** Unknown id, another workspace's id → the manager's 404, unchanged. Read only (TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-916, BUG-925] hidden without `include_deleted` | `HTTPException` 404 | `Factory section with ID <section_id> not found` |

**Side effects:** none

---

## `FactorySectionService.get_factory_sections(db, workspace_id, factory_id=None, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /factory-sections/`, always with `factory_id`, `search`, `skip`, `limit`)

**Purpose:** The sections of a workspace, optionally of one factory, optionally searched by name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int or `None` | passed on as is |
| `search` | str or `None` | passed on as is |
| `skip`, `limit` | int, defaults `0`, `100` | passed on; no bound here |
| `include_deleted` | bool, default `False` | [BUG-920] new; passed on; reachable from the API |

**Returns:** the manager's list.

**Rules:**
- **R1.** The list is `FactorySectionManager.search_factory_sections` for these arguments: filtering, search, order and paging are the manager's R1–R11 (BUG-903 … BUG-905, BUG-917, BUG-918, BUG-921, BUG-922, BUG-924), not repeated here. With no arguments after `workspace_id`, the manager gets `factory_id=None`, `search=None`, `skip=0`, `limit=100`.
- **R2.** [BUG-920] (HR-4) `include_deleted=True` reaches the manager, so soft-deleted sections are listed too (manager R6); the default leaves them out. *(Today: no such parameter, `TypeError`. Verified.)*
- **R3.** Read only (TC6).

**Errors:** none of its own; negative `skip` / `limit` reach the database (`DataError`) when called directly.

**Side effects:** none

---

## `FactorySectionService.update_factory_section(db, section_id, section_in, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /factory-sections/{id}/`)

**Purpose:** Rename a section or move it to another factory, and save it.

**Returns:** the `FactorySection`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The section is changed exactly as `FactorySectionManager.update_factory_section` changes it (manager spec R1–R17, including BUG-911 … BUG-915, BUG-919, BUG-923, BUG-926, BUG-928); committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Factory section with ID <section_id> not found` (verified), 400 `Cannot update deleted factory section`, 404 `Factory with ID <factory_id> not found`, 400 `Cannot move section to deleted factory`, [BUG-928] 400 `Cannot move a section that has machines assigned`, 409 `Section with name '<name>' already exists in this factory`.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2; database errors unchanged (today a `factory_id` of `0` is an `IntegrityError`, BUG-923).

**Side effects:** the row's changed fields, `updated_by`, `updated_at`, committed. On any error: rolled back.

---

## `FactorySectionService.delete_factory_section(db, section_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /factory-sections/{id}/`, which answers 200 with the row)

**Purpose:** Soft-delete a section and save it.

**Returns:** the soft-deleted `FactorySection`, committed and re-read.

**Rules:**
- **R1.** The section is soft-deleted exactly as `FactorySectionManager.delete_factory_section` does it (manager spec R1–R10, including BUG-906 … BUG-908, BUG-927); committed (TC1); returned re-read (TC2). Verified.
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Factory section with ID <section_id> not found`; 400 `Factory section is already deleted` (verified on a second delete); [BUG-927] 400 `Cannot delete a section of a deleted factory`.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2.

**Side effects:** the soft-delete fields, committed (today also the erased assignments, BUG-908). On any error: rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `base_service.py` 26–30 | commit; commit raises → rollback, re-raise | TC1, TC4 |
| `base_service.py` 39 | rollback | TC3 |
| 48–61 | create: manager → commit → refresh → return | `create_factory_section` R1 |
| 63–65 | create: any exception → rollback, re-raise | `create_factory_section` R2, R3 |
| 87 | get: manager, positional, no `include_deleted` (BUG-916) | `get_factory_section` R1–R5 |
| 112–119 | list: manager with `factory_id`, `search`, `skip`, `limit`, no `include_deleted` (BUG-920) | `get_factory_sections` R1–R3 |
| 145–159 | update: manager → commit → refresh → return | `update_factory_section` R1 |
| 161–163 | update: any exception → rollback, re-raise | `update_factory_section` R2, R3 |
| 187–200 | delete: manager → commit → refresh → return | `delete_factory_section` R1 |
| 202–204 | delete: any exception → rollback, re-raise | `delete_factory_section` R2, R3 |
| 208 | module singleton | Not specified |
