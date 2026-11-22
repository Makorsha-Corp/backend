# Spec — `app/services/ledger_service.py`

> **Status:** APPROVED (fill-gaps 2026-11-21: G1, G2, no questions; apply-review 2026-11-21; BUG-3042, BUG-3043 logged; Q2 moved to the dead-code checklist; BUG-648 row extended to this service)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers only what the service adds on top of its manager. The **Transaction contract TC1–TC6** is defined in `tests/unit/services/base_service.spec.md` and cited here. Below the service: `tests/unit/managers/ledger_manager.spec.md` (APPROVED) and, for the project-component access check, `tests/unit/managers/project_manager.spec.md` (`require_component_access` R1–R4, APPROVED). Everything those specs decide (filters, ordering, paging, balances, reconcile results, BUG-341, BUG-640 … BUG-655) is **cited, not restated, and not asked again**.

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** Every item below was decided by Claude under that delegation and is marked so; none is the owner's own answer. No item is a genuinely new money, stock, order-workflow or security question: the one money item (Q1) follows BUG-141's precedent, and the stock behaviour of reconcile is the manager's, already decided. **Owner questions: none.**

> **Deferred areas.** **Production:** this module has no production rules (the ledgers it reads may hold `production` rows; nothing here treats them specially). **Projects (revisit after launch):** `get_project_component_ledger` and `get_project_component_total_cost` describe today's behaviour and carry the tag *revisit after launch*; no bug is logged for them. Note OQ-27 (owner): nothing writes the project component item ledger today, so these two always answer an empty list / `0.0`.

> **Bug IDs:** this spec's block is BUG-3042 … BUG-3061; it uses BUG-3042 and BUG-3043, logged in `docs/testing/bugs.md` (2026-11-21). BUG-3044 … BUG-3061 unused.

> **Verified by running** (import-only check, no database): `ledger_service.ledger_manager` has no attribute `get_transactions_by_order`, and `ledger_service.get_transactions_by_order(...)` raises `AttributeError: 'LedgerManager' object has no attribute 'get_transactions_by_order'`; a `dict[str, Any]` response serialises `Decimal("2000.00")` as `"2000.00"` and `float(Decimal("2000.00"))` as `2000.0`. **Not run:** the database paths (they are the manager's, verified in its review).

## Review
> All items resolved in apply-review (2026-11-21).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The machine and inventory balance endpoints return the stock value as a binary float (`2000.0`), unlike every other money amount (`"2000.00"`) | 🐞 BUG-3043 | Claude, precedent BUG-141 |
| Q1 | After the manager's BUG-653 fix, an inventory reconcile that only corrects the average price would say "0 units adjusted" | 🐞 BUG-3042 | Claude, delegated |
| Q2 | `get_transactions_by_order` always crashes and nothing calls it | removed (dead code) | Claude, delegated |
| FU | The item movement report must pass the new `skip` / `limit` through (manager BUG-648) | bug — existing BUG-648, no new ID | manager review |

### House-rule violations — applied automatically
None of the service's own. The manager's (HR-6 BUG-640/641, HR-7 BUG-642, HR-10 BUG-643/644) are reached through it and cited.

### Precedent matches

### P1. The stock value of a balance comes back as a float — 🐞 BUG-3043
**Background:** Money is stored as exact two-decimal numbers (`Numeric(15,2)`). Everywhere else the API sends money as an exact decimal string (`"2000.00"`). BUG-141 (audit log) ruled that money must never be converted to a binary float.
**What happens today:** `get_machine_balance` and `get_inventory_balance` turn the manager's exact `total_value` into a Python `float`, so the JSON shows `2000.0`, `0.1`, `1234.5` — not `"2000.00"`, `"0.10"`, `"1234.50"`.
**Example:** Press 4 holds 40 bearings worth 1,234.50 taka. `GET /ledgers/machine/balance/?machine_id=4&item_id=9` answers `{"quantity": 40, "total_value": 1234.5, ...}`; the purchase order page shows the same money as `"1234.50"`.
**Rules affected:** `get_machine_balance` R2, `get_inventory_balance` R3
**Answer:** bug — per BUG-141 precedent: `total_value` is the manager's exact `Decimal`, two decimals, serialised like every other money amount (`"1234.50"`) (precedent — decided by Claude under the reviewer's delegation, 2026-11-21)
**Resolution:** `total_value` stays the manager's exact two-decimal `Decimal`; the JSON type changes from number to string (frontend note in the bug row). Rules: `get_machine_balance` R2, `get_inventory_balance` R3.

### New questions

### Q1. A price-only inventory correction would say "0 units adjusted" — 🐞 BUG-3042
**Background:** The ledger manager spec (BUG-653, owner-accepted) makes inventory reconcile also correct the stock row's average price when the quantities already match; such a result comes back as `status: "adjusted"` with `discrepancy: 0`. The service turns every `adjusted` result into the message "Discrepancy found and corrected: <|discrepancy|> units adjusted." plus "Snapshot updated to match ledger."
**What happens today:** Once BUG-653 is fixed, a price-only correction shows "Discrepancy found and corrected: 0 units adjusted." — the user cannot tell what was corrected.
**Example:** Stock row: 10 bolts at 5.00 taka each; ledger: 10 bolts at 6.50. Reconcile fixes the price (stock value 50.00 → 65.00 taka) but tells the user "0 units adjusted".
**Rules affected:** `reconcile_inventory` R4
**Answer:** bug — an `adjusted` result with `discrepancy` 0 gives the warning "Discrepancy found and corrected: average price updated to match ledger." (details = the result) followed by "Snapshot updated to match ledger."; a non-zero discrepancy keeps today's message — decided by Claude under the reviewer's delegation (2026-11-21). Not an owner question: wording of a message about a correction the owner already approved.
**Resolution:** a zero-discrepancy `adjusted` result names the average-price correction. Rules: `reconcile_inventory` R4.

### Q2. `get_transactions_by_order` always crashes and has no caller — 🗑 removed
**Background:** The service method forwards to `LedgerManager.get_transactions_by_order`, which does not exist. No endpoint, service, script or test calls the service method. The DAO lookups by order were already removed as dead code (`InventoryLedgerDAO.get_by_order`, `MachineItemLedgerDAO.get_by_order`, dead-code checklist): ledger rows link to their source through `source_type` / `source_id`, not an order id.
**What happens today:** Any call raises `AttributeError` (verified). Unreachable from the API.
**Example:** A developer wiring a "ledger entries of PO-17" panel to this method would get a 500 for every order.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — decided by Claude under the reviewer's delegation (2026-11-21). On apply-review: append `app/services/ledger_service.py:354` (`LedgerService.get_transactions_by_order`) to `docs/testing/dead-code-removal-checklist.md`, "confirmed unreachable in spec review". Not a bug, no ID.
**Resolution:** moved to Not specified as dead code; entry added to `docs/testing/dead-code-removal-checklist.md` under `app/services/ledger_service.py`.

### Follow-up of the manager spec — written as a rule, no new ID
- **BUG-648** (manager `get_item_movement_summary` R4a): the report gains `skip` / `limit`. The service method has no such parameters today, so the fix must add them here (and at `GET /ledgers/reports/item-movement/{item_id}/`, `skip >= 0`, `1 <= limit <= 100`) and pass them on. Rule: `get_item_movement_summary` R2. BUG-648's register row now names this service and the endpoint too (apply-review 2026-11-21).

Existing bugs reached through the manager and cited (one pass-through case each where the cases file needs it, strict or non-strict as in `ledger_manager.cases.md`): BUG-341, BUG-640 … BUG-655.

Checked and **not** violated: **HR-1/2/3** — no names written. **HR-4** — ledgers have no soft delete; the inventory snapshot's soft delete is the manager's (R2). **HR-5/6/7** — filtering, order and paging are the manager's (BUG-640, BUG-642 apply there and at the endpoints). **HR-8** — no `LIKE`. **HR-9** — reconcile stamps are the manager's (BUG-652). **HR-10** — the reconcile row locks are the manager's (BUG-643, BUG-644); the service holds the transaction open until its commit, so the lock covers the whole request. **Exact intended clause (gap 2, from the code):** both snapshot reads join: `MachineItem.item` and `Inventory.item` are `lazy="joined"`, so the lookups emit `FROM machine_items LEFT OUTER JOIN items AS items_1 …` / `FROM inventory LEFT OUTER JOIN items AS items_1 …`. A plain `FOR UPDATE` there is refused by Postgres (nullable side of an outer join), so per BUG-029 the intended clauses are exactly `FOR UPDATE OF machine_items` (BUG-643) and `FOR UPDATE OF inventory` (BUG-644) — no `SKIP LOCKED`, no `NOWAIT`, no lock on `items`. Verified by compiling both queries with `with_for_update(of=<Model>)` (PostgreSQL dialect). **HR-11 … HR-14** — no external system. **HR-15** — the service does no rounding (BUG-3043's intended value is already two decimals). **HR-16** — every call is scoped by the request's workspace; ids of another workspace's machine, factory, item or component find nothing (empty list, zero balance, `balanced`/`error` reconcile, 404 for a component), and nothing of another workspace is returned.

**Permission checks:** only the project-component access check (`require_component_access`) on the two project methods. Any active member may read every ledger, read another member's activity report, and reconcile (which writes stock rows) — as the other ledger endpoints; noted for `docs/future/permissions.md`.

## Overview
`LedgerService` is the transaction boundary and message layer for the ledger endpoints (`app/api/v1/endpoints/ledgers.py`, `/ledgers/...`). It reads the stock ledgers (machine item, project component item, unified inventory, attachment) through `LedgerManager`, shapes the two balance answers into dicts, and runs the two reconciles: it calls the manager, turns the result's `status` into user messages, and commits. It adds no workspace or existence check of its own; the project methods first check the user may open the component.

**Callables:** 11 specified · 3 not specified
**Externals to mock:** `utcnow` only indirectly — every `ActionMessage` gets `timestamp` from `app.schemas.response.utcnow` (patch there if a test compares messages whole; otherwise compare `type`, `message`, `details`).
**Integration-only behavior:** the query-parameter validation of the endpoints (`skip >= 0`, `limit <= 100`, required ids, `InventoryTypeEnum` parsing) and the JSON form of the dicts (`ActionResponse`, `dict[str, Any]`).

**Facts for the test designer**
- Import: `from app.services.ledger_service import LedgerService, ledger_service`. The manager is the attribute `ledger_manager` (the singleton of `app.managers.ledger_manager`). The project access check is `app.managers.project_manager.project_manager.require_component_access` (imported inside the method — patch it on the `project_manager` singleton, not on the service module).
- `current_user` is a `Profile`; only `.id` is used (as the manager's `user_id`).
- Messages: `ActionMessage` (`app.schemas.response`) with `.type` a `MessageType` (`"success"`, `"warning"`), `.message`, `.details` (`None` unless stated), `.timestamp`.
- Reconcile result dicts, their keys and every write (ledger row, snapshot, activity event): `ledger_manager.spec.md` `reconcile_machine_item` R1–R11, `reconcile_inventory` R1–R11, and its Notes (how to build buckets with history; BUG-655 makes inventory buckets with history raise today).

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md`. Under the `db` fixture `commit()` only releases a savepoint; assert "committed" with a test-level `db.rollback()` and a re-select, "discarded" with a re-select that finds nothing.
- The message mapping (reconcile R2–R5) is easiest to test by `unittest.mock.patch.object(ledger_service.ledger_manager, "reconcile_machine_item", return_value={...})`; keep at least one end-to-end case per reconcile against real rows (balanced and adjusted). An `adjusted` result with `discrepancy: 0` (Q1, BUG-3042) can only be produced by a patched manager today.
- BUG-3043: assert `isinstance(result["total_value"], Decimal)` and its value (`Decimal("1234.50")`); today a `float` → strict xfail. For `get_inventory_balance` use an empty bucket (`Decimal("0.00")` intended, `0.0` today) or a patched manager, since BUG-655 makes a bucket with history raise today.
- TC2 / TC5 do not apply: no method re-reads a row (the reconciles return dicts, the reads do not commit).

## Not specified
- `LedgerService.__init__` — stores the manager singleton, no logic.
- `ledger_service` — module-level singleton, no logic.
- `LedgerService.get_transactions_by_order` — dead code, to be removed (reviewer; Q2, decided by Claude under the reviewer's delegation, 2026-11-21).

---

## `LedgerService.get_machine_ledger(db, machine_id, workspace_id, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/machine/`, all arguments by keyword)

**Rules:**
- **R1.** Returns the manager's `get_machine_ledger` for exactly these arguments, unchanged (manager R1–R9, with BUG-341, BUG-640, BUG-642). Defaults `item_id=None`, dates `None`, `transaction_type=None`, `skip=0`, `limit=100`.
- **R2.** Read only (TC6): no commit, no rollback; an exception from the manager (today a negative `limit` → `DataError`) reaches the caller unchanged and pending changes stay pending.

**Errors:** none of its own. **Side effects:** none.

---

## `LedgerService.get_machine_balance(db, machine_id, item_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/machine/balance/`)

**Returns:** dict with exactly the keys `machine_id`, `item_id`, `quantity`, `total_value`.

**Rules:**
- **R1.** `machine_id` and `item_id` are echoed as given; `quantity` is the manager's balance quantity (`int`; manager R1–R3, BUG-641). An unknown bucket, or one of another workspace → `quantity 0`.
- **R2.** [BUG-3043] `total_value` is the manager's balance value as the exact `Decimal` it returns (two decimals; `Decimal("0.00")` for an empty bucket, e.g. `Decimal("1234.50")`), serialised by the API as `"1234.50"`. *(Today: converted to `float` — `0.0`, `1234.5`.)*
- **R3.** Read only (TC6).

**Errors:** none. **Side effects:** none.

---

## `LedgerService.reconcile_machine_item(db, machine_id, item_id, workspace_id, current_user)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /ledgers/machine/reconcile/`, which returns `ActionResponse(data=result, messages=messages)`)

**Purpose:** Run the machine reconcile, explain the outcome to the user, and save it.

**Returns:** tuple `(result, messages)`: `result` is the manager's result dict unchanged (manager R1–R11, with BUG-643, BUG-649, BUG-650, BUG-651); `messages` a list of `ActionMessage`. Committed.

**Rules:**
- **R1.** The manager reconciles the (workspace, machine, item) bucket as `current_user.id`; the result dict is returned unchanged.
- **R2.** `status "balanced"` → exactly one message: success, `"Machine inventory is balanced at <ledger_qty> units."` (e.g. `"… balanced at 12 units."`; after BUG-649, an empty bucket gives `"… balanced at 0 units."`), `details` `None`.
- **R3.** `status "adjusted"` → exactly two messages, in this order: (1) warning, `"Discrepancy found and corrected: <|discrepancy|> units adjusted."` — the absolute value (ledger 10, snapshot 15 → `"… 5 units adjusted."`), `details` = the result dict; (2) success, `"Snapshot updated to match ledger."`, `details` `None`.
- **R4.** `status "error"` → exactly one message: warning, `"Reconciliation issue: <result['error']>"` (today's manager text: `"Reconciliation issue: Snapshot missing for item with ledger transactions"`); a result without an `error` key → `"Reconciliation issue: Unknown error"`. `details` `None`. The call still commits and returns normally (nothing was written by the manager on this path).
- **R5.** Any other `status` value → no message (`messages == []`); the result is returned and the call commits.
- **R6.** Success is committed (TC1): the adjustment ledger row, the snapshot change and the activity event survive a later rollback.
- **R7.** Any exception — from the manager (e.g. today's `TypeError` of BUG-650) or while building the messages (e.g. a result without `ledger_qty` on the `balanced` path, `KeyError`) — rolls back and reaches the caller as the same object (TC3): no ledger row, snapshot change or event is saved, and other uncommitted changes in the session are discarded.
- **R8.** A failing commit → rolled back, the commit's exception reaches the caller unchanged, nothing saved (TC4).
- **R9.** [BUG-643] The snapshot read emits exactly `FOR UPDATE OF machine_items` (see HR-10 line above), and the lock is held until this method's commit or rollback. *(Today: no lock clause.)*

**Errors:** none of its own; the manager's, unchanged.

**Side effects:** the manager's writes on a discrepancy (1 ledger row, snapshot `qty`, 1 activity event); commit.

---

## `LedgerService.get_project_component_ledger(db, project_component_id, workspace_id, user_id, item_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/project-component/`, `user_id` = the current user)

*All rules: revisit after launch (projects deferred, owner 2026-11-10). Today the ledger is never written (OQ-27), so the list is always empty.*

**Rules:**
- **R1.** The user must be allowed to open the component first: `require_component_access` R1–R4 — unknown id, `0`, or another workspace's component → 404 `Project component not found`; private project the user may not open → 403. On refusal the ledger is not read. *(revisit after launch)*
- **R1a.** [BUG-1278, BUG-1954] A component whose project is soft-deleted → 404 `Project with ID <project_id> not found`, ledger not read (as `project_manager.spec.md` `require_project_access` R3 and `require_component_access` R2; existing bugs, no new one). *(Today: the deleted project passes the check; the ledger is read and, under OQ-27, `[]` is returned.)* *(revisit after launch)*
- **R2.** Allowed → the manager's `get_project_component_ledger` for the component, `item_id`, `skip`, `limit` (defaults `None`, `0`, `100`), unchanged (manager R1–R5, BUG-640, BUG-642). *(revisit after launch)*
- **R3.** Read only (TC6): the 404 / 403 reaches the caller unchanged, no rollback.

**Errors:** `HTTPException` 404 / 403 from the access check. **Side effects:** none.

---

## `LedgerService.get_project_component_total_cost(db, project_component_id, workspace_id, user_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/project-component/{project_component_id}/total-cost/`)

*All rules: revisit after launch (projects deferred). Today always `0.0` (OQ-27).*

**Returns:** dict with exactly the keys `project_component_id`, `total_cost`.

**Rules:**
- **R1.** Access check as `get_project_component_ledger` R1; on refusal the cost is not computed. *(revisit after launch)*
- **R1a.** [BUG-1278, BUG-1954] Component of a soft-deleted project → as `get_project_component_ledger` R1a: 404 `Project with ID <project_id> not found`, cost not computed. *(Today: passes; returns `{"project_component_id": <id>, "total_cost": 0.0}`.)* *(revisit after launch)*
- **R2.** Allowed → `project_component_id` echoed as given; `total_cost` = the manager's `calculate_project_component_total_cost` (manager R1–R2, BUG-654) converted to `float` (`0.0` when the component has no ledger rows). *(revisit after launch — today's float, no bug logged; the BUG-3043 fix may cover it when projects are revisited)*
- **R3.** Read only (TC6).

**Errors:** as `get_project_component_ledger`. **Side effects:** none.

---

## `LedgerService.get_inventory_ledger(db, workspace_id, inventory_type=None, factory_id=None, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/inventory/`)

**Rules:**
- **R1.** Returns the manager's `get_inventory_ledger` for exactly these arguments, unchanged (manager R1–R9, BUG-341, BUG-640, BUG-642). Only `workspace_id` is required: with no other argument every inventory ledger entry of the workspace (as the manager's R6).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `LedgerService.get_inventory_balance(db, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/inventory/balance/`)

**Returns:** dict with exactly the keys `factory_id`, `item_id`, `inventory_type`, `quantity`, `total_value`.

**Rules:**
- **R1.** `factory_id`, `item_id` echoed as given; `quantity` = the manager's balance quantity (manager R1–R3, BUG-641, BUG-655 — a bucket with history raises `AttributeError` today, passed on unchanged).
- **R2.** `inventory_type` is the enum's value string when given an `InventoryTypeEnum` (`InventoryTypeEnum.STORAGE` → `"STORAGE"`); any value without a `.value` (e.g. the plain string `"STORAGE"`) is echoed as given.
- **R3.** [BUG-3043] `total_value` is the manager's exact `Decimal` (two decimals, `Decimal("0.00")` for an empty bucket), serialised as `"0.00"`. *(Today: `float` — `0.0`.)*
- **R4.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `LedgerService.reconcile_inventory(db, factory_id, item_id, inventory_type, workspace_id, current_user)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /ledgers/inventory/reconcile/`)

**Returns:** `(result, messages)` as `reconcile_machine_item`; `result` = the manager's `reconcile_inventory` result unchanged (manager R1–R11, BUG-644, BUG-649 … BUG-655). Committed.

**Rules:**
- **R1.** The manager reconciles the (workspace, factory, item, inventory type) bucket as `current_user.id`; the result dict is returned unchanged.
- **R2.** `status "balanced"` → one success message `"Inventory is balanced at <ledger_qty> units."` (note: `"Inventory"`, not `"Machine inventory"`), `details` `None`.
- **R3.** `status "adjusted"` with a non-zero `discrepancy` → the two messages of `reconcile_machine_item` R3, same texts (warning with `details` = result, then success `"Snapshot updated to match ledger."`).
- **R4.** [BUG-3042] `status "adjusted"` with `discrepancy` 0 (the manager's average-price-only correction, BUG-653) → two messages: (1) warning `"Discrepancy found and corrected: average price updated to match ledger."`, `details` = the result; (2) success `"Snapshot updated to match ledger."`. *(Today: the R3 text, `"Discrepancy found and corrected: 0 units adjusted."`.)*
- **R5.** `status "error"` and any other status → as `reconcile_machine_item` R4, R5.
- **R6.** Commit, rollback and commit failure as `reconcile_machine_item` R6–R8 (TC1, TC3, TC4); the saved writes are the manager's inventory ledger row and snapshot change (no activity event). Today's `AttributeError` of BUG-655 for a bucket with history is an R7-type exception: rolled back and passed on.
- **R7.** [BUG-644] The snapshot read emits exactly `FOR UPDATE OF inventory` (see HR-10 line above), held until this method's commit or rollback. *(Today: no lock clause.)*

**Errors:** none of its own. **Side effects:** the manager's writes on a correction; commit.

---

## `LedgerService.get_attachment_ledger(db, workspace_id, attachment_id=None, entity_type=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/attachments/`)

**Rules:**
- **R1.** Returns the manager's `get_attachment_ledger` for exactly these arguments, unchanged (manager R1–R6, BUG-640, BUG-642).
- **R2.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `LedgerService.get_item_movement_summary(db, item_id, workspace_id, start_date=None, end_date=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/reports/item-movement/{item_id}/`)

**Inputs:** `skip`, `limit` — [BUG-648] new, defaults `0` / `100`; the endpoint gains them too (`skip >= 0`, `1 <= limit <= 100`). *(Today: neither the service nor the endpoint has them.)*

**Returns:** the manager's dict `{"machine": [...], "project": [...], "inventory": [...]}` unchanged.

**Rules:**
- **R1.** Returns the manager's `get_item_movement_summary` for `item_id`, `workspace_id`, `start_date`, `end_date`, unchanged (manager R1–R6, BUG-341, BUG-640, BUG-646, BUG-647). The `project` list is project data: *revisit after launch*.
- **R2.** [BUG-648] `skip` and `limit` are passed on to the manager, so every entry in range is reachable by paging (manager R4a). *(Today: the service has no such parameters; the manager always uses 0 / 100.)*
- **R3.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none.

---

## `LedgerService.get_transactions_by_user(db, user_id, workspace_id, start_date=None, end_date=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /ledgers/reports/user-transactions/{user_id}/`)

**Rules:**
- **R1.** Returns the manager's `get_transactions_by_user` for exactly these arguments, unchanged (manager R1–R4, BUG-341, BUG-640, BUG-642, BUG-645). Today every call raises `AttributeError` (BUG-645), passed on unchanged.
- **R2.** `user_id` is not checked: any id, including one who is not a member of the workspace, is accepted; only entries of the request's workspace can be returned (manager scope).
- **R3.** Read only (TC6): the exception of R1 reaches the caller without a rollback.

**Errors:** none of its own. **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 50–60 | pass-through | `get_machine_ledger` R1, R2 |
| 70–81 | balance shaping, `float(value)` | `get_machine_balance` R1, R2, R3 |
| 94 / 121–123 | `try` / `except Exception` → rollback, re-raise | `reconcile_machine_item` R7 |
| 103 | `status == 'balanced'` | `reconcile_machine_item` R2 |
| 107 | `status == 'adjusted'` | `reconcile_machine_item` R3 |
| 113 | `status == 'error'` | `reconcile_machine_item` R4 |
| 115 | `result.get('error', 'Unknown error')` | `reconcile_machine_item` R4 |
| 113 (fall-through) | no branch matches | `reconcile_machine_item` R5 |
| 118 | commit (raises → rollback) | `reconcile_machine_item` R6, R8 |
| 141–143 | access check raises (incl. deleted project, BUG-1278) | `get_project_component_ledger` R1, R1a, R3 |
| 144–151 | pass-through | `get_project_component_ledger` R2 |
| 162–164 | access check raises (incl. deleted project, BUG-1278) | `get_project_component_total_cost` R1, R1a |
| 165–173 | cost shaping, `float(total_cost)` | `get_project_component_total_cost` R2, R3 |
| 198–209 | pass-through | `get_inventory_ledger` R1, R2 |
| 220–233 | balance shaping, `float(value)` | `get_inventory_balance` R1, R3, R4 |
| 230 | `hasattr(inventory_type, 'value')` | `get_inventory_balance` R2 |
| 247 / 275–277 | `try` / `except` → rollback, re-raise | `reconcile_inventory` R6 |
| 257 | `status == 'balanced'` | `reconcile_inventory` R2 |
| 261 | `status == 'adjusted'` (discrepancy 0 / non-zero — no branch today) | `reconcile_inventory` R3, R4 |
| 267, 269 | `status == 'error'`, `.get('error', …)`; fall-through | `reconcile_inventory` R5 |
| 272 | commit | `reconcile_inventory` R6 |
| 296–306 | pass-through | `get_attachment_ledger` R1, R2 |
| 325–331 | pass-through (no `skip`/`limit`) | `get_item_movement_summary` R1, R2, R3 |
| 344–352 | pass-through | `get_transactions_by_user` R1, R2, R3 |

## Gap log
- G1 (ledger_service.cases.md gap 1) — Contradiction — split the deleted-project refusal out of `get_project_component_ledger` R1 and `get_project_component_total_cost` R1 into new R1a rules tagged with the existing BUG-1278 / BUG-1954, following `project_manager.spec.md`; today's behaviour (passes; `[]` / `0.0`) in the Today note; tagged "revisit after launch" (projects deferred); no new bug.
- G2 (ledger_service.cases.md gap 2) — Fact — exact lock clauses from the code: both snapshot queries carry a joined eager load of `items` (LEFT OUTER JOIN), so intended is `FOR UPDATE OF machine_items` / `FOR UPDATE OF inventory` (BUG-029 rule). Added to the HR-10 line and as `reconcile_machine_item` R9 and `reconcile_inventory` R7. The manager spec's R11 rules and the BUG-643 / BUG-644 rows say only "`FOR UPDATE`" and should be made exact the same way.
