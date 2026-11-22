# Spec — `app/services/delivery_method_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers what the service adds; the **Transaction contract TC1–TC6 is defined there** and cited here. Below the service: `app/managers/delivery_method_manager.py` (**no spec yet**), `tests/unit/dao/delivery_method.spec.md` (APPROVED; it points to `tests/unit/dao/department.spec.md`) and `tests/unit/dao/base.spec.md`.
>
> **The manager is not described yet.** It is the department manager's code with the names changed (read, not run). Its rules belong to its own spec; delivery method DAO FU-1 lists what that review must look at. This spec names the manager's refusals only as values that must pass through unchanged.

> **House-rule lines logged here (2026-11-03):** BUG-1522, BUG-1523. No question; nothing decided under the delegation.
>
> **Verified by running** (`h.py`, `v1_tx.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): create, delete, `get_delivery_method` of the deleted method (returned, `is_deleted = True`), a create with the deleted method's name (accepted: this table has no unique constraint), the list (deleted left out). The transaction mechanics were verified on the department service, whose code is the same line for line (TC1–TC6). **Not run:** HTTP; the intended behavior of BUG-1522, BUG-1523.

## Review

### House-rule violations — applied automatically

- **HR-4** `get_delivery_methods` R2 — the manager's `search_delivery_methods` has an `include_deleted` flag, but the service never passes it and the endpoint has no such parameter. Intended: `include_deleted` (default `False`) reachable from `GET /delivery-methods/` and passed on (per BUG-010).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1522 (pattern `flag-unreachable-from-api`). Rules: `get_delivery_methods` R2.
- **HR-4** `get_delivery_method` R2, R3 — a soft-deleted method is returned by id (verified), although the list hides it. Intended: 404 by default; a new `include_deleted=True` returns it, reachable from the API (per BUG-005). Fix in the manager and here.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1523 (pattern `get-returns-soft-deleted`). Rules: `get_delivery_method` R2, R3. The manager's spec, when written, takes this ID for its own rule.

Not reached here: BUG-730 (a deleted method chosen on a delivery) is the sales delivery code's.

Checked and **not** violated here: **HR-1, HR-2, HR-5, HR-6, HR-8, HR-9** — the manager's and the schema's (delivery method DAO FU-1). **HR-7** — `GET /delivery-methods/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10 … HR-15** — no harmful state, external system or money. **HR-16** — the manager looks rows up by the caller's workspace.

**Permission checks:** none; any active member may create, edit and delete methods (as `department_service.spec.md`).

## Overview
`DeliveryMethodService` is the transaction boundary for delivery methods (Courier, Pickup, Own Fleet), used to tag how a sales delivery is shipped. The `/delivery-methods/` endpoints call it; it calls `DeliveryMethodManager` and commits, rolls back and re-reads around it. It adds no check, translation or shaping.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none (`deleted_at` is the DAO's clock).
**Integration-only behavior:** as `department_service.spec.md`; the `include_deleted` query parameters.

**Facts for the test designer**
- Input schemas: `from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate`. `DeliveryMethodCreate(name: str)`: `name` is the only field, required, with no length, trim or blank check (HR-1 is the manager review's, DAO FU-1). `DeliveryMethodUpdate(name: str | None = None)`: the only field. `DeliveryMethodResponse` adds `id` to `name`.
- The manager's search, as read and run (`v7_gaps.py`, work order types; delivery methods are the same code): a case-insensitive substring of the name (`"pair"` and `"REPAIR"` find "Repair"), applied in Python to the page already cut by `skip` / `limit`; `%` is literal (`"%"` finds nothing); `None` and `""` mean no search. Only to build pass-through cases; not a rule of this service.
- Import: `from app.services.delivery_method_service import DeliveryMethodService, delivery_method_service`. The manager is the attribute `delivery_method_manager`. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- Table `delivery_methods`: delivery method DAO spec ("What differs"). No unique constraint on the name.
- The manager's refusals, as read from its code (for pass-through cases only): create, duplicate live name compared with `==` → 409 `Delivery method with name '<name>' already exists`; get / update / delete, not found or another workspace → 404 `Delivery method with ID <id> not found`; update of a deleted method → 400 `Cannot update deleted delivery method`; delete of a deleted method → 400 `Delivery method is already deleted`.

**Notes for the test designer**
- Session, commits, setup before error paths, TC4 / TC5 patching: as the Notes of `department_service.spec.md`.
- TC2, TC4, TC5: one case each on one write method is enough (the three writes are the same code); TC1 and TC3 get one case per write.
- **BUG-1522, BUG-1523:** the parameter does not exist today (`TypeError`) → strict xfail; BUG-1523 R2 needs no new parameter (today the row is returned) → strict xfail.

## Not specified
- `DeliveryMethodService.__init__` — stores the manager, no logic.
- `delivery_method_service` — module-level singleton, no logic.

---

## `DeliveryMethodService.create_delivery_method(db, delivery_method_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /delivery-methods/`)

**Returns:** the new `DeliveryMethod`, committed and re-read (TC1, TC2): `id`, `created_at` set, `created_by = user_id`.

**Rules:**
- **R1.** The method is created by the manager from `delivery_method_in`, in the given workspace, by `user_id`; committed (TC1); returned re-read (TC2).
- **R2.** The manager's 409 for a live duplicate name reaches the caller unchanged; nothing saved (TC3).
- **R3.** A name used only by a soft-deleted method is accepted (no constraint covers deleted rows here; verified).
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** the manager's `HTTPException` unchanged; database errors unchanged.

**Side effects:** one `delivery_methods` row, committed; on error, rolled back.

---

## `DeliveryMethodService.get_delivery_method(db, delivery_method_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /delivery-methods/{id}/`)

**Inputs:** `include_deleted` — [BUG-1523] new, default `False`, passed on, reachable from the API.

**Rules:**
- **R1.** A live method of the workspace is returned.
- **R2.** [BUG-1523] (HR-4) A soft-deleted method → 404 `Delivery method with ID <id> not found`. *(Today: returned, 200. Verified.)*
- **R3.** [BUG-1523] With `include_deleted=True` it is returned; another workspace's id stays 404. *(Today: no such parameter.)*
- **R4.** Unknown id, `0`, another workspace's id → the manager's 404, unchanged.
- **R5.** Read only (TC6).

**Errors:** `HTTPException` 404 `Delivery method with ID <id> not found`.

**Side effects:** none

---

## `DeliveryMethodService.get_delivery_methods(db, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /delivery-methods/`, always with `search`, `skip`, `limit`)

**Rules:**
- **R1.** The list is the manager's `search_delivery_methods` for `search`, `skip`, `limit` (defaults `None`, `0`, `100`), unchanged; how it filters, pages and orders is the manager's (delivery method DAO FU-1).
- **R2.** [BUG-1522] (HR-4) `include_deleted=True` reaches the manager, so deleted methods are listed too; the default leaves them out. *(Today: no such parameter.)*
- **R3.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none

---

## `DeliveryMethodService.update_delivery_method(db, delivery_method_id, delivery_method_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /delivery-methods/{id}/`)

**Returns:** the `DeliveryMethod`, committed and re-read (TC1, TC2): `updated_by = user_id`, `updated_at` loaded.

**Rules:**
- **R1.** The method is changed by the manager; committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals (404, 400 deleted, 409 duplicate) reach the caller unchanged; nothing saved (TC3).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** the manager's `HTTPException` unchanged. **Side effects:** changed fields, committed; on error, rolled back.

---

## `DeliveryMethodService.delete_delivery_method(db, delivery_method_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /delivery-methods/{id}/`, 200 with the row)

**Returns:** the soft-deleted `DeliveryMethod`, committed and re-read: `is_deleted = True`, `deleted_by = user_id`, `deleted_at` set.

**Rules:**
- **R1.** The method is soft-deleted by the manager; committed (TC1); returned re-read (TC2). Deliveries that name it keep it.
- **R2.** The manager's refusals (404; 400 `Delivery method is already deleted`) reach the caller unchanged; nothing saved (TC3).
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2. **Side effects:** the soft-delete fields, committed; on error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 37–48 | create: manager → commit → refresh → return | `create_delivery_method` R1, R3; TC1, TC2 |
| 50–52 | create: any exception → rollback, re-raise | `create_delivery_method` R2, R4; TC3–TC5 |
| 65 | get: manager, positional, no `include_deleted` (BUG-1523) | `get_delivery_method` R1–R5 |
| 76–82 | list: manager with `search`, `skip`, `limit`; no `include_deleted` (BUG-1522) | `get_delivery_methods` R1–R3 |
| 97–109 | update: manager → commit → refresh → return | `update_delivery_method` R1 |
| 111–113 | update: any exception → rollback, re-raise | `update_delivery_method` R2, R3 |
| 127–138 | delete: manager → commit → refresh → return | `delete_delivery_method` R1 |
| 140–142 | delete: any exception → rollback, re-raise | `delete_delivery_method` R2, R3 |
| `base_service.py` 26–30, 39 | commit / commit fails / rollback | TC1, TC3, TC4 (`department_service.spec.md`) |
| 146 | module singleton | Not specified |

## Follow-ups for other reviews
> Nothing below is a rule of this service.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Delivery method manager** (`app/managers/delivery_method_manager.py`, not yet specified) | (a) BUG-1523: `get_delivery_method` gains `include_deleted`; use this ID. (b) Its list must honour `include_deleted` before paging (HR-5). (c) Everything in delivery method DAO FU-1. | HR-4 lines |

## Gap log
G1 (delivery_method_service.cases.md gap 1) — Fact — input schemas named. Facts.
G2 (gap 2) — Fact, verified by running — the manager's search described for case-building. Facts.
