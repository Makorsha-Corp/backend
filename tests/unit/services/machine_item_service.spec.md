# Spec — `app/services/machine_item_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers what the service adds; the **Transaction contract TC1–TC6 is defined there** and cited here. Below the service: `tests/unit/managers/machine_item_manager.spec.md` (APPROVED), `tests/unit/dao/machine_item.spec.md`, `tests/unit/dao/machine_item_ledger.spec.md` (APPROVED).

> **Routed here and written as rules:** machine item manager FU-1 (a) BUG-1081, the translation of the in-use refusal into a 400 (`delete_machine_item` R2, R3); (b) BUG-1077, `include_deleted` on the get (`get_machine_item` R2, R3); (c) the `IntegrityError` of BUG-1010 / BUG-983 passed on unchanged (`create_machine_item` R3); (d) `DataError` passed on unchanged, a 500 at the API (`create_machine_item` R3). No new bug; BUG-1081's and BUG-1077's register rows already name this service.
>
> **Decided by Claude under the reviewer's delegation (2026-11-03):** Q1, the scope of the translation: only a `ValueError` from the manager's `delete_machine_item`, after the rollback.
>
> **Verified by running** (`h.py`, `v3_http.py`, `v5_tag2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`; nothing persisted): over HTTP with overridden dependencies, a `ValueError("Machine item has open orders", [{"type": "work_order", "id": 7}])` from a patched manager delete answers **500** today; an `app.core.exceptions.ValidationError(detail=..., errors=[...])` from the same place answers 400 with body `type` …`/errors/validation_error`, `title` `Validation Error`, `status` 400, `detail`, `instance`, `request_id`, `errors` as given, and with `errors=[]` the `errors` key is absent; `get_machine_item`'s parameters (`db`, `machine_item_id`, `workspace_id`). The manager's own behavior was verified in its review. **Not run:** the intended behavior of BUG-1077, BUG-1081 (the manager does not raise the `ValueError` yet).

## Review
> All answered; nothing pending. The owner decided the refusal itself (machine item manager Q6); only its translation scope was open.

### Q1. Which errors does the service turn into a 400? — ✅ only the manager's in-use refusal on delete
**Background:** The manager raises a plain `ValueError` in exactly one place: the in-use refusal of `delete_machine_item` (R5a). Every other refusal is already an `HTTPException`. The application has no handler for `ValueError`, so anything not translated is a 500.
**What happens today:** Nothing is translated; once BUG-1081 is fixed in the manager, the refusal would answer 500.
**Example:** A user removes 10 bearings from Press 4 while a draft work order still needs 2. Translated, they get 400 "Machine item has open orders" with that work order listed; untranslated, "internal server error".
**Rules affected:** `delete_machine_item` R2, R3
**Suggested answer:** translate only on `delete_machine_item`, only `ValueError`, to `ValidationError(detail=args[0], errors=args[1])` after the rollback. Alternative: catch `ValueError` on every write, which would also turn a programming error into a misleading 400.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** part of BUG-1081 (no new ID). Rules: `delete_machine_item` R2, R3.

Existing bugs written as rules here, no new ID: **BUG-1081** `delete_machine_item` R2, R3; **BUG-1077** `get_machine_item` R2, R3. Reached through the manager and cited, one pass-through case each, strict or non-strict as in `machine_item_manager.cases.md`: BUG-1010, BUG-1070, BUG-1071, BUG-1074 … BUG-1080, BUG-1083 … BUG-1086. BUG-1082 is the frontend's.

Checked and **not** violated: everything the manager spec lists under "Checked". **HR-7** — `GET /machine-items/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-16** — the translated 400 carries the manager's blockers as they are; R5a already reduces cross-workspace rows to one `{"type": "other_workspace"}` entry, and the service adds nothing.

**Permission checks:** none; any active member may add, change and remove machine stock (as `department_service.spec.md`).

## Overview
`MachineItemService` is the transaction boundary for the manual side of a machine's stock (`machine_items`, with ledger and activity entries written by the manager). The `/machine-items/` endpoints call it. Besides commit, rollback and re-read, it has one job of its own: the manager reports "this stock row is still needed by open orders" as a plain `ValueError` with a list of blockers, and the service turns it into the application's 400 error carrying that list, so the user can see what blocks the delete (owner's rule: a refused delete lists what blocks it).

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none.
**Integration-only behavior:** as `department_service.spec.md`; the 400 body of `app.core.exceptions.ValidationError` (`tests/unit/core/exceptions.spec.md`, `ValidationError` R1, `api_exception_handler`); the `include_deleted` query parameter on `GET /machine-items/{id}/`; `DataError` → 500; `IntegrityError` → the global handler's 409.

**Facts for the test designer**
- Import: `from app.services.machine_item_service import MachineItemService, machine_item_service`. The manager is the attribute `machine_item_manager` (the singleton of `app.managers.machine_item_manager`). The service calls the manager's get positionally and the writes by keyword; the endpoints pass all after `db` by keyword.
- `ValidationError` is `app.core.exceptions.ValidationError` (not pydantic's): `.status_code == 400`, `.error_type == "validation_error"`, `.title == "Validation Error"`, `.detail`, `.errors`.
- The manager's refusals, rows, ledger and activity entries, and how to build every row: `tests/unit/managers/machine_item_manager.spec.md` (Facts, Notes).

**Notes for the test designer**
- Session, commits, setup before error paths, TC4 / TC5 patching: as the Notes of `department_service.spec.md`. **TC1 here includes the ledger and activity rows** the manager writes: after a successful write and a test-level `db.rollback()` they are all there; after an error none is.
- **BUG-1081 (R2, R3):** the manager does not raise the `ValueError` yet. Test the service on its own by `unittest.mock.patch.object(machine_item_service.machine_item_manager, "delete_machine_item", side_effect=ValueError("Machine item has open orders", [{"type": "work_order", "id": 3}, {"type": "other_workspace"}]))`; assert `pytest.raises(app.core.exceptions.ValidationError)` with `.detail` and `.errors` equal to the two args, and that `db.rollback` ran (a committed-then-changed row is back to its committed state, or an uncommitted extra row is gone). Today the `ValueError` itself escapes → strict xfail. Add one end-to-end pass-through case with a real blocker (manager Notes "BUG-1081 rows") → strict xfail.
- **BUG-1077:** the parameter does not exist today (`TypeError`) → strict xfail. R2 (404 by default for a row of a soft-deleted machine) needs no new parameter: today the row is returned → strict xfail.
- **`create_machine_item` R3:** `DataError` today through `qty = 2**31` (manager P5; BUG-1078 moves the refusal into the schema), so build the input with `MachineItemCreate.model_construct(...)` to reach the flush independently of the fix. `IntegrityError`: reach it with an unknown `user_id` (any qty; the ledger's / activity's `performed_by` foreign key fails at the flush, pgcode `23503`, manager spec verified). That path is not touched by any fix, so the case is an ordinary pass: `IntegrityError` unchanged, nothing saved, session usable. Do **not** use an unknown `item_id` for it: that is BUG-1010's case, which asserts the intended 404.

## Not specified
- `MachineItemService.__init__` — stores the manager, no logic.
- `machine_item_service` — module-level singleton, no logic.

---

## `MachineItemService.get_machine_item(db, machine_item_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /machine-items/{id}/`)

**Inputs:** `include_deleted` — [BUG-1077] new, default `False`, passed on, reachable from the API.

**Rules:**
- **R1.** The manager's `get_machine_item` answer is returned unchanged (manager R1, R2, R4, R6).
- **R2.** [BUG-1077] (manager P4, HR-4) A row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item → 404 `Machine item not found` by default. *(Today: returned, 200.)*
- **R3.** [BUG-1077] With `include_deleted=True` such a row is returned (manager R3a); a row with another workspace's item stays 404 (manager R6). *(Today: no such parameter, here or in the manager.)*
- **R4.** Read only (TC6).

**Errors:** `HTTPException` 404 `Machine item not found`.

**Side effects:** none

---

## `MachineItemService.get_machine_items(db, workspace_id, machine_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /machine-items/`, always with `skip`, `limit`)

**Rules:**
- **R1.** The list is the manager's `list_machine_items` for `machine_id`, `skip`, `limit` (defaults `None`, `0`, `100`), unchanged: filters, order, paging are the manager's (with BUG-1070, BUG-1071, BUG-1074, BUG-1086).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none

---

## `MachineItemService.create_machine_item(db, item_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /machine-items/`)

**Returns:** the new `MachineItem`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The stock row, its ledger entry and its activity entry are written by the manager (`create_machine_item` rules) and committed together (TC1); the row is returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Machine not found in this workspace`; 400 `Cannot add items to a deleted machine`; [BUG-1010] 404 `Item with ID <item_id> not found`; [BUG-1085] 400 `Cannot add a removed item to a machine`; 409 `This item already exists on this machine. Update the existing record instead.`
- **R3.** A database error at the flush (`IntegrityError`, `DataError`) reaches the caller unchanged after the rollback; nothing saved; the session is usable (manager FU-1 (c), (d)).
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2, R3. **Side effects:** one stock row, ledger and activity rows, committed; on error, rolled back.

---

## `MachineItemService.update_machine_item(db, machine_item_id, item_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /machine-items/{id}/`)

**Returns:** the `MachineItem`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The row is changed by the manager (`update_machine_item` rules, with its ledger and activity entries) and committed with them (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Machine item not found`; [BUG-1083] 400 `Cannot update items of a deleted machine`.
- **R3.** Database errors, commit and re-read failures as `create_machine_item` R3, R4.

**Errors:** as R2, R3. **Side effects:** the row's changed fields, ledger and activity rows, committed; on error, rolled back.

---

## `MachineItemService.delete_machine_item(db, machine_item_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /machine-items/{id}/`, 204)

**Returns:** `None`. No re-read: the row is gone.

**Rules:**
- **R1.** The row is removed by the manager (`delete_machine_item` rules: final ledger adjustment, activity entries) and the removal is committed (TC1); the call returns `None`.
- **R2.** [BUG-1081] (manager Q6, FU-1 (a)) When the manager refuses because open orders still need the row (`ValueError` with two args, manager R5a), the session is rolled back and the service raises `app.core.exceptions.ValidationError` with `detail = args[0]` (`"Machine item has open orders"`) and `errors = args[1]`, the blocker list exactly as given, same order, nothing added or removed. Nothing is saved. *(Today: the manager does not refuse; a `ValueError` from it would escape unchanged and answer 500. Verified with a patched manager.)*
- **R3.** [BUG-1081] Over HTTP that is a 400 whose body carries `detail` and the `errors` list (integration-only; verified with a hand-made `ValidationError`).
- **R4.** The manager's other refusals reach the caller unchanged, nothing saved (TC3): 404 `Machine item not found`; [BUG-1084] 400 `Cannot remove items from a deleted machine`.
- **R5.** A commit failure follows TC4. There is no re-read, so TC5 does not apply.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1081] still needed by an open order | `app.core.exceptions.ValidationError` (400) | `Machine item has open orders`, `errors` = the blockers |
| not found; deleted machine (BUG-1084) | the manager's `HTTPException`, unchanged | the manager's |

**Side effects:** the row deleted, ledger and activity rows written, committed; on any error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 22–24 | get: manager, positional, no `include_deleted` (BUG-1077) | `get_machine_item` R1–R4 |
| 32–35 | list: manager with `machine_id`, `skip`, `limit` | `get_machine_items` R1, R2 |
| 44–51 | create: manager → commit → refresh → return | `create_machine_item` R1; TC1, TC2 |
| 52–54 | create: any exception → rollback, re-raise | `create_machine_item` R2, R3, R4; TC3–TC5 |
| 64–72 | update: manager → commit → refresh → return | `update_machine_item` R1 |
| 73–75 | update: any exception → rollback, re-raise | `update_machine_item` R2, R3 |
| 84–89 | delete: manager → commit; returns `None` | `delete_machine_item` R1 |
| 90–92 | delete: any exception → rollback, re-raise; no `ValueError` translation (BUG-1081) | `delete_machine_item` R2–R5 |
| `base_service.py` 26–30, 39 | commit / commit fails / rollback | TC1, TC3, TC4 (`department_service.spec.md`) |
| 95 | module singleton | Not specified |

## Gap log
G1 (machine_item_service.cases.md gap 1) — Contradiction — the `IntegrityError` example moved from the unknown item (BUG-1010, a bug path) to an unknown user (no fix touches it). Notes, `create_machine_item` R3.
