# Spec — `app/services/factory_service.py`

> **Status:** APPROVED (2026-11-04; nothing open)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined there** and cited here, not restated. Below the service: `tests/unit/managers/factory_manager.spec.md` (APPROVED), `tests/unit/dao/factory.spec.md`, `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** factory manager FU-3 (BUG-897: `include_deleted` on `get_factory`; BUG-901: on `get_factories`; `FactoryResponse` has no `is_deleted`, D1 below) and FU-6 (BUG-1331: the translation of the open-batch refusal into a 400 carrying the blockers). No new bug; the register rows of BUG-897, BUG-901 and BUG-1331 now name this service.
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** D1 (`is_deleted` on `FactoryResponse`). The translation scope of FU-6 follows `machine_item_service.spec.md` Q1 (only the manager's `ValueError` on delete, after the rollback), applied as precedent. None of this is the owner's answer; none touches money, stock, an order workflow or who may see or do what.
>
> **Standing decisions applied here (not asked again):** HR-4: a soft-deleted row is hidden unless asked for, and an `include_deleted` option is reachable from the API. A refused delete lists what blocks it, in the 400 body (owner, item manager Q2; `app.core.exceptions.ValidationError(detail, errors)`). Every other refusal stays the manager's `HTTPException`, passed on unchanged.
>
> **Verified by running** (`h.py`, `v1_fac.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test`, the session built as the unit-test `db` fixture, `join_transaction_mode="create_savepoint"`; HTTP through `TestClient` with overridden dependencies; nothing persisted): a created factory survives a later `db.rollback()` and comes back with `created_at` loaded and not expired; a 409 rolls back an uncommitted setup row of the same session; a patched `commit` that raises leaves nothing saved; a patched `refresh` that raises leaves the row saved; a read leaves a pending row pending; a factory with a `draft` batch is deleted today; a deleted factory is returned by `get_factory` (and `GET /factories/{id}/` answers 200 with `name`, `abbreviation`, `id` only); a second delete answers 400 `Factory is already deleted`; another workspace's id answers 404; `include_deleted=` on `get_factory` / `get_factories` raises `TypeError`; `GET /factories/?include_deleted=true` answers 200 and leaves the deleted factory out; a `ValueError("Factory has open production batches", [...])` from a patched manager delete answers **500** over HTTP today; a duplicate name answers 409 `{"detail": …}`. **Not run:** two concurrent requests; the intended behavior of BUG-897, BUG-901, BUG-1331.

## Review
> All answered; nothing pending.

### D1. A listed or opened deleted factory cannot be told from a live one — ✅ add `is_deleted` to the response (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** `FactoryResponse` carries only `id`, `name`, `abbreviation`. Once BUG-897 and BUG-901 make deleted factories reachable with `include_deleted=true`, the API would return them looking exactly like live ones (factory manager FU-3).
**What happens today:** Deleted factories are hidden from the list and shown by id (BUG-897) with no flag.
**Example:** A future "restore factory" screen lists `GET /factories/?include_deleted=true`: "Old Plant" (deleted) and "Main Plant" (live) look the same.
**Rules affected:** `get_factory` R3, `get_factories` R2 (integration-only part)
**Answer:** part of the BUG-897 / BUG-901 fix: `FactoryResponse` gains `is_deleted: bool` (read from the row). Nothing else is added; no new ID. The service returns the ORM row, which already has `is_deleted`, so nothing changes at the service level.

Existing bugs written as rules here, no new ID: **BUG-897** `get_factory` R2, R3; **BUG-901** `get_factories` R2; **BUG-1331** `delete_factory` R2, R3. Reached through the manager and cited, one pass-through case each, strict or non-strict exactly as in `tests/unit/managers/factory_manager.cases.md`: BUG-893 … BUG-896, BUG-898 … BUG-900, BUG-902. BUG-1332 is the frontend's.

Checked and **not** violated: **HR-1 … HR-3, HR-8, HR-9** — decided in the manager and the schemas (BUG-893 … BUG-896, BUG-900, BUG-902). **HR-5, HR-6** — the manager's (BUG-898, BUG-899). **HR-7** — `GET /factories/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10** — a factory delete is a plain soft delete. **HR-11 … HR-15** — no external system, batch or money. **HR-16** — every lookup is by the caller's workspace, in the manager; the translated 400 carries the manager's blockers as they are (R5b there reduces cross-workspace rows to one `{"type": "other_workspace"}`), and the service adds nothing.

**Permission checks:** none; any active member of the workspace may create, edit and delete factories (as `department_service.spec.md`).

## Overview
`FactoryService` is the transaction boundary for factories, the physical sites of a workspace. The `/factories/` endpoints call it; it calls `FactoryManager` and commits, rolls back and re-reads around it. Its one job of its own (intended, BUG-1331): the manager reports "this factory still has open production batches" as a plain `ValueError` with a list of blockers, and the service turns it into the application's 400 carrying that list. Every other refusal is the manager's `HTTPException`, passed on unchanged.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. (`deleted_at` comes from `app.dao.factory.utcnow`: factory manager spec; the service adds no clock.)
**Integration-only behavior:** as `department_service.spec.md`; the 400 body of `app.core.exceptions.ValidationError` (`tests/unit/core/exceptions.spec.md`); the `include_deleted` query parameter on `GET /factories/` and `GET /factories/{id}/` and `is_deleted` in `FactoryResponse` (D1); schema validation (400 today, BUG-461; 422 intended); `skip >= 0`, `1 <= limit <= 1000`.

**Facts for the test designer**
- Import: `from app.services.factory_service import FactoryService, factory_service`. `FactoryService()` takes no arguments; its manager is the attribute `factory_manager`, the singleton of `app.managers.factory_manager`. The service calls the manager's `get_factory` positionally and everything else by keyword; the endpoints pass everything after `db` by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code`, `.detail`. The translated refusal is `app.core.exceptions.ValidationError`: assert `.status_code == 400`, `.detail`, `.errors`.
- The manager's rules, errors and messages: `tests/unit/managers/factory_manager.spec.md`.

**Notes for the test designer**
- Transaction mechanics (committed, nothing saved, setup before an error path, TC4, TC5, TC6): exactly as `department_service.spec.md` Notes.
- **BUG-897, BUG-901:** the parameter does not exist today: calling with `include_deleted=` raises `TypeError` → strict xfail. Build the deleted factory with `factory_service.delete_factory` or directly with `is_deleted=True`, commit, then call.
- **BUG-1331 translation (`delete_factory` R2, R3):** the manager does not raise the `ValueError` yet. Two kinds of case: (1) with real rows (a `draft` batch on a line of the factory, rows as the factory manager spec's Notes), intended 400, strict xfail; (2) with `unittest.mock.patch.object(factory_service.factory_manager, "delete_factory", side_effect=ValueError("Factory has open production batches", [...]))`, which isolates the translation: today the `ValueError` comes out unchanged → strict xfail. In (2) also put an uncommitted row in the session first and assert it is gone (the rollback ran before the translation).
- **Pass-through cases:** one case per manager bug reached, written to the intended behavior, strict or non-strict xfail exactly as in the manager's cases file. Do not re-test the manager's edge cases here.

## Not specified
- `FactoryService.__init__` — stores the manager, no logic.
- `factory_service` — module-level singleton, no logic.

---

## `FactoryService.create_factory(db, factory_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /factories/`, 201)

**Purpose:** Create a factory and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | the request's session |
| `factory_in` | `FactoryCreate` | passed to the manager as `factory_data` |
| `workspace_id` | int | caller's workspace, passed on |
| `user_id` | int | acting user, passed on |

**Returns:** the new `Factory`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The factory is created exactly as `FactoryManager.create_factory` creates it (manager spec R1–R10, including BUG-893 … BUG-896), in the given workspace, with `created_by = user_id`; it is committed (TC1) and returned re-read, with `id` and `created_at` set (TC2). Verified.
- **R2.** A refusal of the manager (409 `Factory with name '<name>' already exists`, 409 for the abbreviation, the database-level 409 of BUG-895) reaches the caller unchanged and nothing is saved (TC3). Verified for the name.
- **R3.** Commit and re-read failures follow TC4, TC5. Verified.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| any refusal of the manager | the manager's `HTTPException`, unchanged | the manager's |
| database error at the flush or the commit | the same `sqlalchemy.exc` error, unchanged | — |

**Side effects:** one `factories` row, committed. On any error: session rolled back.

---

## `FactoryService.get_factory(db, factory_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /factories/{id}/`)

**Purpose:** One factory by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | passed on |
| `workspace_id` | int | passed on |
| `include_deleted` | bool, default `False` | [BUG-897] new; passed on unchanged; reachable from the API as a query parameter |

**Returns:** the manager's `Factory`.

**Rules:**
- **R1.** A live factory of the workspace is returned as the manager returns it.
- **R2.** [BUG-897] (factory manager HR-4 line, FU-3) A soft-deleted factory → 404 `Factory with ID <factory_id> not found` by default. *(Today: returned, 200. Verified.)*
- **R3.** [BUG-897] With `include_deleted=True` a soft-deleted factory of the workspace is returned; another workspace's id is still 404. *(Today: the parameter does not exist, `TypeError`. Verified.)*
- **R4.** Unknown id, `0`, another workspace's id → the manager's 404 `Factory with ID <factory_id> not found`, unchanged. Verified for another workspace.
- **R5.** Read only (TC6). Verified.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-897] deleted without `include_deleted` | `HTTPException` 404 | `Factory with ID <factory_id> not found` |

**Side effects:** none

---

## `FactoryService.get_factories(db, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /factories/`, always with `search`, `skip`, `limit`)

**Purpose:** The factories of a workspace, optionally searched by name or abbreviation.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `search` | str or `None` | passed on as is |
| `skip`, `limit` | int, defaults `0`, `100` | passed on as is; the service sets no bound |
| `include_deleted` | bool, default `False` | [BUG-901] new; passed on; reachable from the API |

**Returns:** the manager's list.

**Rules:**
- **R1.** The list is `FactoryManager.search_factories` for these arguments: filtering, search, order and paging are the manager's R1–R9 (BUG-898, BUG-899, BUG-902), not repeated here. With no arguments after `workspace_id`, the manager gets `search=None`, `skip=0`, `limit=100`.
- **R2.** [BUG-901] (factory manager HR-4 line, FU-3) `include_deleted=True` reaches the manager, so soft-deleted factories are listed too (manager R5); the default `False` leaves them out. *(Today: the service has no such parameter (`TypeError`), and `GET /factories/?include_deleted=true` answers 200 without the deleted factory. Verified.)*
- **R3.** Read only (TC6).

**Errors:** none of its own; negative `skip` / `limit` reach the database (`DataError`) when called directly; the endpoint refuses them first.

**Side effects:** none

---

## `FactoryService.update_factory(db, factory_id, factory_in, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /factories/{id}/`)

**Purpose:** Edit a factory and save it.

**Returns:** the `Factory`, committed and re-read (TC1, TC2): `updated_at` is loaded. Verified.

**Rules:**
- **R1.** The factory is changed exactly as `FactoryManager.update_factory` changes it (manager spec R1–R16, including BUG-893 … BUG-896, BUG-900); committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Factory with ID <factory_id> not found`, 400 `Cannot update deleted factory`, the 409s for name and abbreviation.
- **R3.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2; database errors unchanged.

**Side effects:** the row's changed fields, `updated_by`, `updated_at`, committed. On any error: rolled back.

---

## `FactoryService.delete_factory(db, factory_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /factories/{id}/`, which answers 200 with the row)

**Purpose:** Soft-delete a factory and save it, or tell the user which open batches stop it.

**Returns:** the soft-deleted `Factory`, committed and re-read: `is_deleted = True`, `deleted_by = user_id`, `deleted_at` set, `is_active` still `True` (factory manager R3, R4).

**Rules:**
- **R1.** A factory the manager deletes (manager spec R1–R8) is committed (TC1) and returned re-read (TC2). The manager's `HTTPException`s reach the caller unchanged, nothing saved (TC3): 404 `Factory with ID <factory_id> not found`; 400 `Factory is already deleted` (verified on a second delete).
- **R2.** [BUG-1331] (factory manager FU-6, R5a, R5b) When the manager refuses with `ValueError("Factory has open production batches", blockers)`, the session is rolled back first (TC3: nothing saved, other pending changes discarded) and the caller gets `app.core.exceptions.ValidationError` with `status_code == 400`, `detail == "Factory has open production batches"` (the `ValueError`'s `args[0]`) and `errors` == the blocker list (`args[1]`), the same list object content, unchanged: each `{"type": "production_batch", "id": <batch id>}`, and at most one `{"type": "other_workspace"}`, last. The service adds, removes or reorders nothing. *(Today: nothing refuses, and a `ValueError` would reach the caller unchanged: 500 at the API. Verified with a patched manager.)*
- **R3.** [BUG-1331] Only a `ValueError` raised by the manager's `delete_factory` is translated. Any other exception, on this method or on the other methods of the service, reaches the caller unchanged after the rollback (TC3), so a `ValueError` from anywhere else stays a 500. (Scope per `machine_item_service.spec.md` Q1.)
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| already deleted | `HTTPException` 400 | `Factory is already deleted` |
| [BUG-1331] open batches | `app.core.exceptions.ValidationError` (400) | `Factory has open production batches`; `.errors` = blockers |
| database error | the same `sqlalchemy.exc` error | — |

**Side effects:** the soft-delete fields, committed. On any error: rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `base_service.py` 26–30 | commit; commit raises → rollback, re-raise | TC1, TC4 |
| `base_service.py` 39 | rollback | TC3 |
| 47–60 | create: manager → commit → refresh → return | `create_factory` R1 |
| 62–64 | create: any exception → rollback, re-raise | `create_factory` R2, R3 |
| 86 | get: manager, positional, no `include_deleted` (BUG-897) | `get_factory` R1–R5 |
| 109–115 | list: manager with `search`, `skip`, `limit`, no `include_deleted` (BUG-901) | `get_factories` R1–R3 |
| 141–155 | update: manager → commit → refresh → return | `update_factory` R1 |
| 157–159 | update: any exception → rollback, re-raise | `update_factory` R2, R3 |
| 183–196 | delete: manager → commit → refresh → return | `delete_factory` R1 |
| 198–200 | delete: any exception → rollback, re-raise; no `ValueError` translation (BUG-1331) | `delete_factory` R1–R4 |
| 204 | module singleton | Not specified |
