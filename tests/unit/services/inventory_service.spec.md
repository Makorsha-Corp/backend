# Spec — `app/services/inventory_service.py`

> **Status:** APPROVED (2026-11-21; HR-4 line applied as BUG-3082, decided under the reviewer's delegation). Stays APPROVED after fill-gaps (Gap log at the end).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md` and `machine_item_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined in `tests/unit/services/base_service.spec.md`** and cited here. Below the service: `tests/unit/managers/inventory_manager.spec.md` (APPROVED). Every refusal, ledger entry, filter, order and figure is the manager's and is cited, not repeated.
>
> **Decided by Claude under the reviewer's delegation (2026-11-21):** D1 (below). No owner question: the service adds no money, stock or workflow decision of its own.
>
> **Verified by running** (`v1_inv.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2desc\inventory\`, one outer transaction rolled back against `marker_test`, session `join_transaction_mode="create_savepoint"`; nothing persisted): `InventoryService()` takes no arguments and its `manager` is the module singleton `inventory_manager`; a create with qty 5 commits the row and its one ledger entry (both survive a later `db.rollback()`), `created_at` loaded; an unknown factory gives 404 `Factory with ID 999999999 not found` and an unrelated flushed row pending in the session is discarded with it; a duplicate gives 409 `Inventory record already exists for this item/type/factory combination`; an update from another workspace gives 404 `Inventory record with ID {id} not found`; "clear stock" sets qty 0 and leaves `is_deleted` False; a second clear writes no ledger entry; a soft-deleted row is returned by `get_inventory` today and `include_deleted=True` raises `TypeError`; `get_incoming_summary(factory_id=0)` gives 404 `Factory with ID 0 not found`; a patched failing `commit` leaves nothing saved; a patched failing `refresh` after commit raises and the row stays saved; `get_inventory_page` default `limit` 50.

## Review
> Reviewer: answer each item on its **Answer:** line. Then run the describer in `apply-review` mode.

### House-rule violations — resolved
- **HR-4** `get_inventory` R3 — 🐞 BUG-3082 — BUG-700 gives the manager's `get_inventory` an `include_deleted` option (default `False`); the service and `GET /inventory/{inv_id}/` have no such parameter, so the option is not reachable from the API. Intended: the service takes `include_deleted: bool = False` and passes it on; the endpoint exposes it as a query parameter (as BUG-1077 did for machine items). Provisional **BUG-3082**, pattern `get-returns-soft-deleted` (same fix family as BUG-700).
**Answer:** bug — per HR-4 (house rule); decided by Claude under the reviewer's delegation (2026-11-21).
**Resolution:** BUG-3082 (pattern `get-returns-soft-deleted`, per HR-4). `get_inventory` Inputs and R3 state the intended behavior; R2 stays BUG-700's (manager).

### Decided under the reviewer's delegation
### D1. No inventory row is ever soft-deleted today — keep the HR-4 line anyway — ✅ decided
**Background:** Nothing in `app/` soft-deletes an inventory row (the DAO has a `soft_delete` helper that no code calls; "clear stock" only sets the quantity to 0). Soft-deleted rows can only come from old data or a script.
**What happens today:** The `include_deleted` option would almost never matter.
**Example:** A row soft-deleted by an old import: `GET /inventory/57/` shows it today (BUG-700 makes it 404); support could still open it with `?include_deleted=true` once BUG-3082 is fixed.
**Rules affected:** `get_inventory` R2, R3
**Answer:** keep the HR-4 line — decided by Claude under the reviewer's delegation (2026-11-21). The house rule states that where the option exists it is reachable; leaving it manager-only would make BUG-700's second half untestable from the API.

Existing bugs reached through the manager and cited here, no new ID: BUG-700 … BUG-719 (manager spec). Pass-through cases follow `inventory_manager.cases.md` (strict or non-strict as there), **except** where the case-design skill requires non-strict: BUG-706 (factory query with no `ORDER BY`) is non-strict here, and its strict SQL `ORDER BY` check belongs to the factory DAO cases (`app/dao/factory.py` `get_active_factories`, where the fix lives) — decided by Claude under the reviewer's delegation (2026-11-21), gap 3.

Checked and **not** violated: **HR-1 … HR-3** — the service writes no name; **HR-5, HR-6, HR-8** — filtering, order and search are the manager's (BUG-701, BUG-702, BUG-706, BUG-719); **HR-7** — `GET /inventory/` enforces `skip >= 0`, `1 <= limit <= 1000`; **HR-9** — manager (BUG-703); **HR-10** — the row locks are the manager's (BUG-704, BUG-705), and the service commits in the same call, so a lock is held until the commit and no longer; **HR-11 … HR-14** — no external system, no batch; **HR-15** — the service does no arithmetic (money rounding in the manager / `Numeric(15,2)`, BUG-708); **HR-16** — the service adds no link; the manager refuses another workspace's factory, row and (BUG-710) item as not found.

**Production deferred / projects:** nothing in this service touches production or projects (no production path; the incoming summary covers purchase and transfer orders only).

**Permission checks:** none. Any active member may create stock rows, change quantity and average price, and clear stock; any workspace member may read (endpoint dependencies only). Note for the permissions task.

**Notifications:** none sent. Note for the notifications task (optional): a "stock cleared" or manual quantity change is not announced to anyone.

## Overview
`InventoryService` is the transaction boundary for the inventory snapshot rows behind `/inventory/` (STORAGE, DAMAGED, WASTE, SCRAP per item and factory). Its writes — create, update (manual quantity / price / note edit) and "clear stock" (`DELETE`, which sets the quantity to 0 and keeps the row) — call the manager, commit, re-read and return the row; any error rolls back and is passed on unchanged. Its reads pass straight through. It translates no error and sends nothing.

**Callables:** 7 specified · 3 not specified
**Externals to mock:** none.
**Integration-only behavior:** as `department_service.spec.md`; `IntegrityError` → the global handler's 409, `DataError` → 500, `pydantic.ValidationError` of the body → 422 before the service runs; the `include_deleted` query parameter on `GET /inventory/{inv_id}/` [BUG-3082].

**Facts for the test designer**
- Import: `from app.services.inventory_service import InventoryService, inventory_service`. `InventoryService()` takes no arguments; its attribute `manager` is the singleton `app.managers.inventory_manager.inventory_manager`.
- Signatures (as called by the endpoints): `create_inventory(db, inv_in, workspace_id, user_id)`, `update_inventory(db, inv_id, inv_in, workspace_id, user_id)`, `delete_inventory(db, inv_id, workspace_id, user_id)`, `get_inventory(db, inv_id, workspace_id)` (+ `include_deleted` per BUG-3082); `get_inventory_page`, `get_inventory_stats`, `get_incoming_summary` take everything after `db` by keyword only.
- Schemas: `InventoryCreate`, `InventoryUpdate` from `app.schemas.inventory`. How to build factories, items, inventory rows, purchase / transfer orders for the incoming summary, and how ledger rows are found: `inventory_manager.spec.md` Notes.

**Notes for the test designer**
- Session, commits, TC4 / TC5 patching: as the Notes of `base_service.spec.md` and `department_service.spec.md`. **TC1 here includes the ledger row** the manager writes: after a successful create (qty > 0), quantity update or clear, and a test-level `db.rollback()`, the row and its ledger entry are both there; after an error neither is.
- A failing flush for the database-error pass-through: build `InventoryCreate.model_construct(..., avg_price=Decimal("1e13"))` (a `DataError` today; BUG-708 moves the refusal into the schema, `model_construct` skips it) — or the race of manager R9 (patch the duplicate lookups to `None`, manager Notes) for `IntegrityError`.
- **Soft-deleted factory (C-06, IS-05):** a real factory delete (`FactoryManager.delete_factory` → `FactoryDAO.soft_delete`) sets `is_deleted = True`, `deleted_at = utcnow()` and `deleted_by = <profile id>`; it leaves `is_active` as it was. The inventory checks (BUG-715, BUG-718) read `is_deleted` only, so `is_deleted = True` alone is enough; setting `deleted_at` / `deleted_by` as well gives the fully real state.
- **Lock clause (`update_inventory` R1a, `delete_inventory` R1a):** capture statements as manager Notes; assert the `SELECT` on `inventory` that loads the row ends with `FOR UPDATE OF inventory` (no `NOWAIT` / `SKIP LOCKED`).
- BUG-3082: the parameter does not exist today (`TypeError`) → strict xfail; set up the soft-deleted row directly (`is_deleted = True`).

## Not specified
- `InventoryService.__init__` — stores the manager, no logic.
- `inventory_service` — module-level singleton, no logic.
- `InventoryService.list_inventory` — dead code, already on `docs/testing/dead-code-removal-checklist.md` (`inventory_service.py:54`, manager spec Q11); no caller.

---

## `InventoryService.create_inventory(db, inv_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /inventory/`, 201)

**Returns:** the new `Inventory` row, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The row (and its opening ledger entry when qty > 0) is written by the manager (`create_inventory` rules, with BUG-707, BUG-710, BUG-711, BUG-714, BUG-715) and committed together (TC1); the row is returned re-read, `created_at` loaded (TC2).
- **R2.** The manager's refusals reach the caller unchanged and nothing is saved — including any other change pending in the session (TC3): 404 `Factory with ID {factory_id} not found`; [BUG-710] 404 `Item with ID {item_id} not found`; 409 `Inventory record already exists for this item/type/factory combination`.
- **R3.** A database error at the flush (`IntegrityError` from a concurrent duplicate, `DataError` from an out-of-range price today) reaches the caller unchanged after the rollback; nothing saved; the session is usable.
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R2, R3. **Side effects:** one inventory row (or a restored one, BUG-714) and zero or one ledger row, committed; on error, rolled back.

---

## `InventoryService.update_inventory(db, inv_id, inv_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /inventory/{inv_id}/`)

**Returns:** the `Inventory` row, committed and re-read (TC1, TC2); `updated_at` loaded.

**Rules:**
- **R1.** `inv_in` is passed to the manager as received, so which fields were sent (and which were sent as `null`, BUG-713) is the manager's to read (`update_inventory` rules, with BUG-703, BUG-704, BUG-707, BUG-712, BUG-713). The change and its ledger entry are committed together (TC1); the row is returned re-read (TC2).
- **R1a.** [BUG-704] The row is loaded with the lock clause `FOR UPDATE OF inventory` (exactly that: no `NOWAIT`, no `SKIP LOCKED`). The load joins `items` (the model's `item` relationship is a joined eager load, a `LEFT OUTER JOIN`), and Postgres refuses a plain `FOR UPDATE` on the nullable side of an outer join (BUG-029 rule, as BUG-644 for the same table). The lock is held until this service's commit or rollback. *(Today: no lock.)*
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Inventory record with ID {inv_id} not found` (missing or another workspace); 400 `Cannot update a deleted inventory record`; [BUG-713] 422 `qty cannot be empty`.
- **R3.** Database errors, commit and re-read failures as `create_inventory` R3, R4.

**Errors:** as R2, R3. **Side effects:** the row's changed fields and zero or one ledger row, committed; on error, rolled back.

---

## `InventoryService.get_inventory(db, inv_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /inventory/{inv_id}/`)

**Inputs:** `include_deleted` — [BUG-3082] new, default `False`, passed to the manager, reachable from the API as a query parameter. *(Today: no such parameter.)*

**Rules:**
- **R1.** The manager's `get_inventory` answer is returned unchanged: the row, or 404 `Inventory record with ID {inv_id} not found` for a missing id or another workspace's row.
- **R2.** [BUG-700] A soft-deleted row → 404 by default (manager `get_inventory` R3). *(Today: returned.)*
- **R3.** [BUG-3082] With `include_deleted=True` a soft-deleted row of the workspace is returned; another workspace's row stays 404. *(Today: `TypeError`, no such parameter here; the manager has none either until BUG-700.)*
- **R4.** Read only (TC6).

**Errors:** `HTTPException` 404 as R1. **Side effects:** none.

---

## `InventoryService.get_inventory_page(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False, skip=0, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /inventory/`)

**Rules:**
- **R1.** Every argument is passed to the manager's `get_inventory_page` unchanged (same defaults: no filters, `include_zero_qty=False`, `skip=0`, `limit=50`), and its `InventoryListResponse` is returned unchanged; filters, order, search and paging are the manager's (with BUG-701, BUG-702).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `InventoryService.get_inventory_stats(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `GET /inventory/stats/`)

**Rules:**
- **R1.** Every argument is passed to the manager's `get_inventory_stats` unchanged and its `InventoryStatsResponse` is returned unchanged (with BUG-702, BUG-719).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `InventoryService.get_incoming_summary(db, *, workspace_id, factory_id=None)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `GET /inventory/incoming-summary/`)

**Rules:**
- **R1.** The manager's `get_incoming_summary` result for `workspace_id` and `factory_id` is returned unchanged (with BUG-706, BUG-709, BUG-717, BUG-718). `factory_id=None` covers the workspace; any other value, `0` included, is one factory.
- **R2.** A factory not found reaches the caller unchanged: 404 `Factory with ID {factory_id} not found` (e.g. `factory_id=0`).
- **R3.** Read only (TC6).

**Errors:** as R2. **Side effects:** none.

---

## `InventoryService.delete_inventory(db, inv_id, workspace_id, user_id)`
**Shape:** state-transition ("clear stock") · **Persistence:** writes · **Visibility:** public (used by: `DELETE /inventory/{inv_id}/`, 200 with the row)

**Returns:** the `Inventory` row, committed and re-read (TC1, TC2). Despite the name nothing is deleted: the row stays live (`is_deleted` False) with qty 0.

**Rules:**
- **R1.** The stock is cleared by the manager (`delete_inventory` rules, with BUG-705, BUG-707, BUG-716): qty set to 0 with one "Stock cleared" ledger entry, committed together (TC1); the row is returned re-read (TC2).
- **R1a.** [BUG-705] The row is loaded with `FOR UPDATE OF inventory`, exactly as `update_inventory` R1a (same load, same reason). *(Today: no lock.)*
- **R2.** Clearing a row whose qty is already 0 commits and returns the row unchanged, with no ledger entry (manager no-op rule).
- **R3.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Inventory record with ID {inv_id} not found`; 400 `Cannot clear stock on a deactivated inventory record`.
- **R4.** Commit and re-read failures follow TC4, TC5.

**Errors:** as R3. **Side effects:** `qty`, `updated_by`, one ledger row, committed; on error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 29–33 | create: manager → commit → refresh → return | `create_inventory` R1; TC1, TC2 |
| 34–36 | create: any exception → rollback, re-raise | `create_inventory` R2, R3; TC3 |
| 31 / 32 | commit raises / refresh raises | `create_inventory` R4; TC4, TC5 |
| 42–46 | update: manager → commit → refresh → return | `update_inventory` R1; TC1, TC2 |
| 47–49 | update: exception → rollback, re-raise | `update_inventory` R2, R3; TC3–TC5 |
| 51–52 | get: manager, no `include_deleted` (BUG-3082) | `get_inventory` R1–R4 |
| 54–64 | `list_inventory` (dead code) | Not specified |
| 66–89 | page: all arguments passed through | `get_inventory_page` R1, R2 |
| 91–110 | stats: all arguments passed through | `get_inventory_stats` R1, R2 |
| 112–117 | incoming summary: passed through, `session=` keyword | `get_incoming_summary` R1–R3 |
| 120–124 | clear: manager → commit → refresh → return | `delete_inventory` R1, R2; TC1, TC2 |
| 125–127 | clear: exception → rollback, re-raise | `delete_inventory` R3, R4; TC3–TC5 |
| (manager) | [BUG-704] row load with `FOR UPDATE OF inventory` | `update_inventory` R1a |
| (manager) | [BUG-705] row load with `FOR UPDATE OF inventory` | `delete_inventory` R1a |

## Gap log
- G1 (inventory_service.cases.md gap 1) — fact — Notes: a real factory soft delete sets `is_deleted`, `deleted_at`, `deleted_by`, not `is_active`; the inventory checks read `is_deleted` only.
- G2 (inventory_service.cases.md gap 2) — fact — new `update_inventory` R1a and `delete_inventory` R1a: lock clause `FOR UPDATE OF inventory` (joined eager load of `items`, BUG-029 rule, as BUG-644), no `NOWAIT` / `SKIP LOCKED`; Notes updated. The manager spec's R10 / R8 say plain `FOR UPDATE` and should be aligned (outside this spec).
- G3 (inventory_service.cases.md gap 3) — contradiction — Review header: BUG-706 pass-through is non-strict here; the strict `ORDER BY` check belongs to the factory DAO cases (decided by Claude under the reviewer's delegation, 2026-11-21).
