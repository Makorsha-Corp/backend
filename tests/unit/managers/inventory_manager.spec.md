# Spec — `app/managers/inventory_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — resolved
- **HR-4** `get_inventory` R3 — a soft-deleted inventory row is returned by id. Intended: soft-deleted → 404 by default; new `include_deleted=True` parameter returns it. — 🐞 BUG-700
**Answer:** bug — per HR-4 (house rule)
**Resolution:** logged as BUG-700 (pattern `get-returns-soft-deleted`, per HR-4). `get_inventory` R3/R4 state the intended behavior.
- **HR-6** `get_inventory_page` R4 — rows ordered by item name case-sensitively, then id. Intended: item name case-insensitive ascending, then inventory `id` ascending, before `skip`/`limit`. — 🐞 BUG-701
**Answer:** bug — per HR-6 (house rule)
**Resolution:** logged as BUG-701 (pattern `unordered-pagination`, per HR-6). `get_inventory_page` R4 states the intended order. (`list_inventory` R3 pointed to the same rule; `list_inventory` itself is removed as dead code — Q11 — so no test is needed for it.)
- **HR-8** `get_inventory_page` R6 and `get_inventory_stats` R4 — search text placed in `ILIKE '%…%'` unescaped; `%` and `_` act as wildcards. Intended: `%`, `_` and `\` match literally in both item name and unit. — 🐞 BUG-702
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged as BUG-702 (pattern `unescaped-like-wildcards`, per HR-8). `get_inventory_page` R6 states the intended literal-match behavior; `get_inventory_stats` R4 points to it.
- **HR-9** `update_inventory` R9 — `updated_by` is written on every successful update, even when no field changes. Intended: `updated_by` written only when at least one field actually changes value. — 🐞 BUG-703
**Answer:** bug — per HR-9 (house rule)
**Resolution:** logged as BUG-703 (pattern `audit-stamp-on-noop`, per HR-9). `update_inventory` R9 states the intended behavior.
- **HR-10** `update_inventory` R10 — stock quantity is read and then changed without a row lock; two concurrent adjustments both use the same "before" quantity. Intended: row read `FOR UPDATE`; the second request sees the first one's quantity (ledger `qty_before` reflects it). — 🐞 BUG-704
**Answer:** bug — per HR-10 (house rule)
**Resolution:** logged as BUG-704 (pattern `hr-10-unlocked-state-transition`, per HR-10). `update_inventory` R10 states the intended behavior.
- **HR-10** `delete_inventory` R8 — stock is read and cleared without a row lock; two concurrent clears both write a "Stock cleared" ledger entry. Intended: row read `FOR UPDATE`; the second clear sees qty 0 and returns the row unchanged with no ledger entry. — 🐞 BUG-705
**Answer:** bug — per HR-10 (house rule)
**Resolution:** logged as BUG-705 (pattern `hr-10-unlocked-state-transition`, per HR-10). `delete_inventory` R8 states the intended behavior.
- **HR-6** `get_incoming_summary` R4 — the up-to-500 factories are fetched with no sort order, so which factories are included and the order of the combined result vary. Intended: factories ordered by name case-insensitive ascending, then `id` ascending, before any cap. — 🐞 BUG-706
**Answer:** bug — per HR-6 (house rule)
**Resolution:** logged as BUG-706 (pattern `unordered-pagination`, per HR-6). `get_incoming_summary` R4 states the intended order (combined with the BUG-709 fix removing the 500 cap).

### Precedent matches — confirmed

### P1. Zero average price records ledger total cost as empty — 🐞 BUG-707
**Background:** Ledger entries store `unit_cost` and `total_cost = unit_cost × quantity`. The code only computes `total_cost` when the price is "truthy"; a price of exactly `0` counts as missing.
**What happens today:** With `avg_price = 0`, the ledger entry gets `unit_cost = 0.00` but `total_cost = NULL`.
**Example:** A user creates inventory for free sample stock: qty 10, avg_price 0. The ledger shows unit cost 0.00 and total cost blank instead of 0.00.
**Rules affected:** `create_inventory` R8, `update_inventory` R7, `delete_inventory` R6
**Answer:** bug — per BUG-501 precedent: only a missing (`None`) price leaves `total_cost` empty; a price of `0` gives `total_cost = 0.00` (precedent — confirmed: ok)
**Resolution:** logged as BUG-707 (pattern `falsy-zero-treated-as-missing`, per BUG-501 precedent). `total_cost` is computed whenever the ledger entry's `unit_cost` is not `None`; a price of `0` gives `total_cost = 0.00`. Rules: `create_inventory` R8, `update_inventory` R7, `delete_inventory` R6.

### P2. Average price with more than 2 decimals or too many digits accepted — 🐞 BUG-708
**Background:** `avg_price` is stored as `Numeric(15,2)` on both the inventory row and the ledger. The schemas accept any `Decimal`.
**What happens today:** `10.005` is stored rounded (`10.01`) while ledger `total_cost` is computed from the unrounded value; a value ≥ 10^13 fails at flush with a database error.
**Example:** Create with qty 3, avg_price 10.005 → row shows 10.01, ledger total cost 30.02 (from 30.015) instead of 30.03. Create with avg_price 1e13 → 500/database error.
**Rules affected:** `create_inventory` R4, `update_inventory` R4
**Answer:** bug — per BUG-021 precedent: `InventoryCreate` / `InventoryUpdate` reject `avg_price` with more than 2 decimals or more than 13 integer digits (422) before anything is written (precedent — confirmed: ok)
**Resolution:** logged as BUG-708 (pattern `unbounded-decimal-input`, per BUG-021 precedent). `InventoryCreate`/`InventoryUpdate` reject `avg_price` with more than 2 decimals or more than 13 integer digits (422) before anything is written. Rules: `create_inventory` R4, `update_inventory` R4.

### P3. Workspace-wide incoming summary silently covers at most 500 factories — 🐞 BUG-709
**Background:** Without a factory filter, the summary loads the workspace's active factories with a hard cap of 500 and no sort order.
**What happens today:** Factories beyond the first 500 returned by the database are silently left out.
**Example:** A workspace has 520 active factories. `GET /inventory/incoming-summary/` omits pending purchase orders for 20 factories; which 20 can change between calls.
**Rules affected:** `get_incoming_summary` R3
**Answer:** bug — per BUG-342 precedent: all active, live factories of the workspace are covered, no cap (precedent — confirmed: ok)
**Resolution:** logged as BUG-709 (pattern `silent-result-cap`, per BUG-342 precedent). All active, live factories of the workspace are covered by `get_incoming_summary`, no cap. Rules: `get_incoming_summary` R3.

### New questions

### Q1. Inventory can be created for a catalog item of another workspace (or a non-existent item) — 🐞 BUG-710
**Background:** Catalog items belong to one workspace. On create the manager checks that the factory belongs to the caller's workspace, but never checks the item. The database only checks that the item id exists somewhere.
**What happens today:** An `item_id` from another workspace is accepted and the new row is returned (and later listed) with that item's name and unit. A non-existent `item_id` fails at flush with a foreign-key error (409 "Referenced resource does not exist." at the API).
**Example:** A user in workspace A posts `{"item_id": 812, "factory_id": 3, "inventory_type": "STORAGE", "qty": 1}` where item 812 belongs to workspace B. Response 201 with `"item_name": "B's secret part"`; the row appears in workspace A's inventory list, revealing workspace B's catalog.
**Rules affected:** `create_inventory` R3
**Answer:** bug — the item must exist in the caller's workspace; otherwise 404 "Item with ID N not found" and nothing is written (reviewer accepted suggestion)
**Resolution:** logged as BUG-710 (pattern `unvalidated-foreign-key-reference`). The item must belong to the caller's workspace; otherwise `HTTPException` 404 `Item with ID {item_id} not found` and nothing is written. Rules: `create_inventory` R3.

### Q2. Negative quantity and negative average price are accepted — 🐞 BUG-711
**Background:** `InventoryCreate.qty` and `InventoryUpdate.qty` are plain integers; `avg_price` is a plain decimal. No minimum is enforced anywhere.
**What happens today:** Create with qty `-5` stores a row with qty -5 and writes no ledger entry (entries are only written for qty > 0). Update to qty `-5` stores it and writes an adjustment. Negative prices are stored as given.
**Example:** A user creates inventory with qty -5, avg_price -3. The storage list (with "include zero qty") shows -5 units at -3.00, and the estimated value KPI drops by 15.00; the ledger has no record of how the -5 appeared.
**Rules affected:** `create_inventory` R4, R7; `update_inventory` R4
**Answer:** bug — InventoryCreate/InventoryUpdate reject qty < 0 and avg_price < 0 with 422; nothing written (reviewer accepted suggestion)
**Resolution:** logged as BUG-711 (pattern `unvalidated-numeric-range`). `InventoryCreate`/`InventoryUpdate` reject `qty < 0` and `avg_price < 0` with 422 (Pydantic `ValidationError`); nothing written. Rules: `create_inventory` R4, R7; `update_inventory` R4.

### Q3. Average price can be set without any ledger entry — 🐞 BUG-712
**Background:** The ledger is meant to be the source of truth: other stock operations re-sync the inventory row from the latest ledger entry ("ledger wins"), overwriting `qty` and `avg_price`.
**What happens today:** A ledger entry is written only when the quantity changes (update) or is > 0 (create). Creating with qty 0 and a price, or updating only `avg_price`, changes the row's price with no ledger record; the next ledger-driven sync silently reverts it.
**Example:** A user edits item "Bolt" storage in Factory 1 from 5.00 to 6.00 avg price (qty unchanged at 100). The row shows 6.00, the ledger still ends at 5.00; after the next stock receipt the row is re-synced and the price the user entered is gone, with no trace in the ledger.
**Rules affected:** `create_inventory` R7, `update_inventory` R6
**Answer:** bug — any avg_price change writes a ledger inventory_adjustment entry (quantity 0 when qty is unchanged, before/after prices set) so the ledger stays the source of truth (reviewer accepted suggestion)
**Resolution:** logged as BUG-712 (pattern `unlogged-value-change`). Any change to `avg_price` writes a ledger `inventory_adjustment` entry (quantity 0 when `qty` is unchanged, `qty_before = qty_after`, `avg_price_before`/`avg_price_after` set), so the ledger stays the source of truth. `create_inventory` R7a (new); `update_inventory` R6 (rewritten).

### Q4. Update cannot clear the note or the average price — 🐞 BUG-713
**Background:** Update ignores every field sent as `null` (and every field not sent).
**What happens today:** `{"note": null}` or `{"avg_price": null}` returns 200 with the old value unchanged.
**Example:** A user deletes the text of an inventory note and saves; the API receives `{"note": null}`, answers 200, and the old note is still shown.
**Rules affected:** `update_inventory` R5
**Answer:** bug — explicit null clears note and avg_price; qty: null is rejected with 422 (reviewer accepted suggestion)
**Resolution:** logged as BUG-713 (pattern `null-value-treated-as-absent`). An explicit `null` for `note` or `avg_price` clears the field (sets it `None`); `qty: null` is rejected with 422 (`qty` cannot be empty). Rules: `update_inventory` R5 (rewritten).

### Q5. Creating inventory where a soft-deleted row exists for the same item/type/factory fails with a database conflict — 🐞 BUG-714
**Background:** The table allows only one row per (workspace, item, type, factory), deleted rows included. The duplicate check before insert only looks at live rows. (No API path soft-deletes inventory today, so such rows come from older data or direct DB edits.) The internal stock-posting code handles this case by restoring the deleted row.
**What happens today:** The pre-check passes, the insert violates the unique constraint at flush and the API answers 409 "This resource already exists. Please use a different value." — although the user cannot see any existing row.
**Example:** Legacy row 40 (item 7, STORAGE, Factory 2) is soft-deleted. A user creates item 7 STORAGE in Factory 2 → 409; the storage list shows no such row.
**Rules affected:** `create_inventory` R5
**Answer:** bug — the soft-deleted row is restored and updated with the submitted values (with the initial ledger entry), and returned as the created record (reviewer accepted suggestion)
**Resolution:** logged as BUG-714 (pattern `soft-deleted-conflict-not-restored`). When a soft-deleted row exists for the same workspace/factory/item/type, it is restored (`is_deleted = False`) and updated with the submitted `qty`/`avg_price`/`note`, with the same opening-ledger-entry behavior as a new row (R7/R7a/R8), and returned as the created record instead of raising. Rules: `create_inventory` R5 (rewritten).

### Q6. Inventory can be created in a soft-deleted factory — 🐞 BUG-715
**Background:** Factories are soft-deleted (`is_deleted = True`, row stays). The factory check on create finds deleted factories too.
**What happens today:** A deleted factory id is accepted and the inventory row is created in it.
**Example:** Factory 9 "Old Plant" was deleted. `POST /inventory/` with `factory_id: 9` returns 201; the stock sits in a factory that no longer appears anywhere in the UI.
**Rules affected:** `create_inventory` R2
**Answer:** bug — a soft-deleted factory is treated as not found: 404 "Factory with ID N not found", nothing written (reviewer accepted suggestion)
**Resolution:** logged as BUG-715 (pattern `unvalidated-foreign-key-reference`, same root cause as BUG-710). A soft-deleted factory is treated as not found: `HTTPException` 404 `Factory with ID {factory_id} not found`, nothing written; an inactive-but-live factory is still accepted (only soft-delete state matters here, not `is_active`). Rules: `create_inventory` R2 (rewritten).

### Q7. "Clear stock" leaves a negative quantity untouched — 🐞 BUG-716
**Background:** `DELETE /inventory/{id}/` does not delete the row; it sets the quantity to zero and records a "Stock cleared" ledger entry.
**What happens today:** When the quantity is 0 or negative, the row is returned unchanged and nothing is recorded, so a negative quantity is never brought back to zero.
**Example:** Row 12 has qty -4 (after an over-issue). The user clicks "Clear stock"; the response is 200 with qty still -4.
**Rules affected:** `delete_inventory` R4
**Answer:** bug — a negative quantity is also set to 0 with a "Stock cleared" ledger entry; only qty exactly 0 is a no-op (reviewer accepted suggestion)
**Resolution:** logged as BUG-716 (pattern `off-by-boundary-noop-check`). A negative quantity is also cleared to 0, with a "Stock cleared" ledger entry (`quantity = |old qty|`, `qty_before` = old qty, `qty_after = 0`); only `qty` exactly `0` is a true no-op. Rules: `delete_inventory` R4 (rewritten).

### Q8. Voided purchase orders still count as incoming stock — 🐞 BUG-717
**Background:** A purchase order can be voided (`voided = True`, order stays). Other PO lists and calendars exclude voided orders. The incoming summary only excludes orders whose status is the last status of their workflow.
**What happens today:** Unreceived quantities on a voided PO are reported as pending incoming stock indefinitely.
**Example:** PO-0042 for 100 bolts to Factory 1 is voided after 30 were received. The incoming summary for Factory 1 still shows 70 bolts pending from PO-0042.
**Rules affected:** `get_incoming_summary_for_factory` R4
**Answer:** bug — voided purchase orders are excluded from the incoming summary (reviewer accepted suggestion)
**Resolution:** logged as BUG-717 (pattern `voided-record-not-excluded`). A PO with `voided = True` is excluded from the incoming summary regardless of its status/workflow. Rules: `get_incoming_summary_for_factory` R4 (rewritten).

### Q9. Incoming summary for one factory accepts a deleted or inactive factory — 🐞 BUG-718
**Background:** Without a factory filter the summary only covers active, non-deleted factories. With a factory id, the lookup accepts any factory of the workspace.
**What happens today:** `factory_id` of a soft-deleted or inactive factory returns its summary normally, while the workspace-wide summary leaves that same factory out.
**Example:** Factory 9 was deleted but still has an open PO. `GET /inventory/incoming-summary/?factory_id=9` lists the PO's items; `GET /inventory/incoming-summary/` does not.
**Rules affected:** `get_incoming_summary_for_factory` R2
**Answer:** bug — a soft-deleted factory is treated as not found (404); an inactive but live factory is still summarised (reviewer accepted suggestion)
**Resolution:** logged as BUG-718 (pattern `get-returns-soft-deleted`). A soft-deleted factory is treated as not found: `HTTPException` 404 `Factory with ID {factory_id} not found`; an inactive-but-live factory is still summarised (only `is_deleted` matters, not `is_active`, consistent with BUG-715). Rules: `get_incoming_summary_for_factory` R2 (rewritten).

### Q10. Per-type breakdown in inventory stats has no fixed order — 🐞 BUG-719
**Background:** The stats response includes one `by_type` row per inventory type that has matching rows (STORAGE, DAMAGED, WASTE, SCRAP).
**What happens today:** The rows come back in whatever order the database groups them, which can change between calls.
**Example:** Two consecutive `GET /inventory/stats/` calls return `by_type` as `[STORAGE, SCRAP]` and then `[SCRAP, STORAGE]`; a KPI strip that renders the list in order swaps its tiles.
**Rules affected:** `get_inventory_stats` R6
**Answer:** bug — by_type is ordered by inventory type in enum order: STORAGE, DAMAGED, WASTE, SCRAP (reviewer accepted suggestion)
**Resolution:** logged as BUG-719 (pattern `unordered-pagination`). `by_type` is ordered by inventory type in enum declaration order: STORAGE, DAMAGED, WASTE, SCRAP. Rules: `get_inventory_stats` R6 (rewritten).

### Q11. `list_inventory` is not reachable from the API — ✅ remove
**Background:** The inventory list endpoint uses the paginated `get_inventory_page`. `list_inventory` is only called by `InventoryService.list_inventory`, which no endpoint, script or other service calls.
**What happens today:** The method exists but can never run in production.
**Example:** No request to the API reaches `list_inventory`; changing or breaking it has no visible effect.
**Rules affected:** `list_inventory` R1–R4
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** `InventoryManager.list_inventory` moved to Not specified as dead code; its section and Branch-map rows removed. Confirmed unreachable: `GET /inventory/` calls `get_inventory_page`, not `list_inventory`; `InventoryService.list_inventory` (the method's only caller) has no caller itself; no legacy test under `tests/` (outside `tests/unit/`) references either method. Logged in `tests/unit/managers/inventory_manager.deadcode-staging.md`. Not a bug — no BUG ID.

## Overview
`InventoryManager` owns the inventory snapshot rows (one per workspace × catalog item × inventory type × factory; types STORAGE, DAMAGED, WASTE, SCRAP) behind `/inventory/`: create, manual quantity/price edits, "clear stock", get, paginated list, KPI stats, and a summary of stock still incoming from open purchase orders and inbound transfers. Manual quantity changes are mirrored into the inventory ledger (`inventory_ledger`), which other code treats as the source of truth. It is called only by `InventoryService`, which commits or rolls back; the manager never commits (DAO writes flush).

**Callables:** 8 specified · 2 not specified
**Externals to mock:** none (ledger `performed_at` and row `created_at` are Postgres `server_default now()`; `updated_at` is `onupdate now()`)
**Integration-only behavior:** none

**Notes for the test designer:**
- Call the manager directly with a real session; `InventoryManager()` or the module singleton `inventory_manager`.
- Ledger entries for a bucket can be found by `(workspace_id, factory_id, item_id, inventory_type)`; the manager writes at most one ledger entry per call.
- Unique constraint `uq_inventory_workspace_item_type_factory` on `(workspace_id, item_id, inventory_type, factory_id)` covers soft-deleted rows too; a violation is `sqlalchemy.exc.IntegrityError` at flush. Wrap such calls in `session.begin_nested()` so the test session stays usable.
- Soft-deleted inventory rows must be set up directly (`is_deleted = True`); no manager method soft-deletes.
- `HTTPException` is `fastapi.HTTPException`; check `.status_code` and `.detail`.
- Incoming summary needs: `PurchaseOrder` rows with `destination_type = "storage"`, `destination_id = factory id`, a `current_status_id` (required), `voided` (BUG-717) and optional `order_workflow_id`; `OrderWorkflow.status_sequence` is a JSON list of status ids whose **last** element is the terminal status; `TransferOrder` rows with `destination_location_type = "storage"`, `destination_location_id = factory id`, `completed_at` NULL for incomplete.
- BUG-714 (restore a soft-deleted row on create): set up a soft-deleted `Inventory` row directly for the combination under test, then call `create_inventory` for the same workspace/factory/item/type.
- Race simulation for `create_inventory` R9: `InventoryManager().inv_dao` is the module singleton `app.dao.inventory.inventory_dao` (imported into `app.managers.inventory_manager` as `inventory_dao`). The pre-insert duplicate lookup is `inventory_dao.get_by_factory_item_type` (live rows only). Simulate the race by `patch.object(inventory_dao, "get_by_factory_item_type", return_value=None)` with a live row already present; since the BUG-714 fix may switch to the any-state lookup `inventory_dao._get_any_by_factory_item_type`, patch that one to return `None` as well (best-practice default, delegated by reviewer).
- Row locks (`update_inventory` R10, `delete_inventory` R8): setup rows are uncommitted, so a second connection cannot see or lock them. The single-session observable is the emitted SQL: capture statements (SQLAlchemy `before_cursor_execute` event on the session's connection) and assert the `SELECT` on `inventory` that loads the row contains `FOR UPDATE`. Real two-connection concurrency is out of scope for unit tests (best-practice default, delegated by reviewer).
- Test-DB collation (environment fact, checked in the gap round): the test database uses collation `English_United States.1252`, which already sorts "apple, Banana, cherry" case-insensitively but breaks case-only ties lowercase-first (`bolt` before `Bolt`) regardless of id. So `get_inventory_page` R4 [BUG-701] fails today only on a case-only tie where the upper-case name has the lower `id`.
- Rows read without `ORDER BY` (`get_incoming_summary` R4 [BUG-706]) come back in insertion (heap) order on the test table in practice: insert factories in reverse of the intended order so the test fails today.
- `get_inventory_stats` R6 [BUG-719]: `inventory_type` is a native Postgres enum declared STORAGE, DAMAGED, WASTE, SCRAP; when Postgres chooses a sort-based GROUP BY (likely, since a distinct-item count is computed) the rows already come out in enum order, so the intended-order test may XPASS today. The code guarantees no order either way. Design the test to the intended order; if it XPASSes, the executor reports it as a discrepancy (non-strict xfail), never weakens the assertion (best-practice default, delegated by reviewer).

## Not specified
- `InventoryManager.__init__` — wires the model and DAOs, no logic
- `InventoryManager.list_inventory` — dead code, to be removed (reviewer, Q11); see `tests/unit/managers/inventory_manager.deadcode-staging.md`

---

## `InventoryManager.create_inventory(session, data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public

**Purpose:** Create a new inventory snapshot row for one item/type/factory, with an opening ledger entry when it starts with stock.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `data.item_id` | int | Catalog item. [BUG-710] Must exist in the caller's workspace, else 404 (Q1). |
| `data.inventory_type` | `InventoryTypeEnum` | STORAGE / DAMAGED / WASTE / SCRAP. |
| `data.factory_id` | int | Must be a live (not soft-deleted) factory of `workspace_id`; inactive-but-live accepted [BUG-715] (Q6). |
| `data.qty` | int, default 0 | [BUG-711] Must be ≥ 0 (422 otherwise) (Q2). |
| `data.avg_price` | Decimal or None, default None | [BUG-711][BUG-708] Must be ≥ 0, at most 2 decimals, at most 13 integer digits (422 otherwise) (P2, Q2). Stored `Numeric(15,2)`. |
| `data.note` | str or None | Stored as given. |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int | Acting profile. |

**Returns:** the new `Inventory` row, flushed (has an `id`), not committed.

**Rules:**
- **R1.** The factory must belong to `workspace_id`. A factory id that does not exist, or exists only in another workspace → 404 `"Factory with ID {factory_id} not found"`; nothing is written.
- **R2.** [BUG-715] A soft-deleted factory of the workspace is treated as not found: 404 `"Factory with ID {factory_id} not found"`; nothing is written. An inactive-but-live factory is still accepted. *(Today: a soft-deleted factory is accepted like a live one.)*
- **R3.** [BUG-710] The item must exist in the caller's workspace; otherwise 404 `"Item with ID {item_id} not found"` and nothing is written. *(Today: the item is not checked — an item of another workspace is accepted and the row is created referencing it; a non-existent `item_id` raises `IntegrityError` (foreign key) at flush.)*
- **R3a.** Catalog items (`items` table) have no soft-delete column; "exists" means a row with that id and `workspace_id`. An inactive item (`is_active = False`) of the workspace is accepted like an active one (best-practice default, delegated by reviewer — the Q1 answer only requires existence in the workspace, and deactivating a catalog item does not erase stock that may still exist). Today this holds as well (no item check at all).
- **R4.** [BUG-711][BUG-708] `qty` and `avg_price` are rejected by `InventoryCreate` when `qty < 0`, `avg_price < 0`, `avg_price` has more than 2 decimals, or more than 13 integer digits (422, nothing written). Valid values, and `note`, are stored exactly as given (the database rounds `avg_price` to 2 decimals). *(Today: no such validation — negative values and over-precise prices are accepted.)*
- **R5.** [BUG-714] If a **live** row already exists for the same workspace, factory, item and type → 409 `"Inventory record already exists for this item/type/factory combination"`; nothing is written. The same combination in another workspace, another factory, another item or another type does not conflict. If a **soft-deleted** row exists for the combination, it is restored (`is_deleted = False`) and updated with the submitted `qty`/`avg_price`/`note`, given the same opening-ledger-entry treatment as a new row (R7/R7a/R8), and returned as the created record. *(Today: the soft-deleted case is not detected by the pre-check; the insert then raises `IntegrityError` (unique constraint) at flush and the API answers 409, with no row restored.)*
- **R6.** A newly created row has `workspace_id` = the caller's workspace, `created_by = user_id`, `is_active = True`, `is_deleted = False`, `updated_by` NULL, `created_at` set by the database.
- **R6a.** [BUG-714] A row restored per R5 keeps its original `id`, `created_by` and `created_at`; it gets `is_deleted = False`, `is_active = True`, `updated_by = user_id` (the restore is a change, HR-9) and `updated_at` set by the database (best-practice default, delegated by reviewer). *(Today: no restore happens — `IntegrityError` at flush, R5.)*
- **R7.** When `qty > 0`, exactly one ledger entry is written; when `qty` is 0 or negative, no ledger entry is written for the quantity (the row still stores the given `avg_price`) (Q2).
- **R7a.** [BUG-712] When `qty` is 0 (so R7 writes no entry) and `avg_price` is given (not `None`), one ledger entry is written: same fields as R8 but `quantity = 0`, `qty_before = qty_after = 0`. *(Today: no ledger entry is written at all when `qty` is 0, even with a price — the price change has no record.)*
- **R8.** The opening ledger entry (R7, R7a) has: same `workspace_id`, `inventory_type`, `factory_id`, `item_id`; `transaction_type = "manual_add"`; `quantity = qty`; `unit_cost = avg_price`; `total_cost = avg_price × qty` when `avg_price` is not `None`, otherwise NULL [BUG-707] *(today: NULL also when `avg_price` is `0`)*; `qty_before = 0`; `qty_after = qty`; `avg_price_before` NULL; `avg_price_after = avg_price`; `source_type = "manual"`; `source_id` NULL; `notes = "Initial inventory record created"`; `performed_by = user_id`.
- **R9.** Two concurrent creates of the same live combination: the database unique constraint lets only one insert succeed; the other raises `IntegrityError` at flush (not converted by the manager).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Factory not in workspace / missing / soft-deleted [BUG-715] | `HTTPException` 404 | `Factory with ID {factory_id} not found` |
| Item not in caller's workspace / missing [BUG-710] | `HTTPException` 404 | `Item with ID {item_id} not found` |
| `qty < 0`, `avg_price < 0`, or `avg_price` too precise/large [BUG-711][BUG-708] | Pydantic `ValidationError` (422 at the API); manager not reached | Pydantic's message (not asserted) |
| Live row for same workspace/factory/item/type | `HTTPException` 409 | `Inventory record already exists for this item/type/factory combination` |
| Concurrent duplicate insert of the same live combination | `IntegrityError` at flush | — |

**Side effects:** one `inventory` row inserted, or a soft-deleted one restored and updated (R5); zero or one `inventory_ledger` row inserted; flushed, not committed.

---

## `InventoryManager.update_inventory(session, inv_id, data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public

**Purpose:** Manually edit an inventory row's quantity, average price or note; quantity changes are recorded in the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `inv_id` | int | Inventory row id. |
| `data.qty` | int or None | [BUG-711] When sent (not `null`), must be ≥ 0 (schema 422 otherwise). Not sent = keep; explicit `qty: null` is rejected by the manager itself (`HTTPException` 422) since Pydantic alone cannot distinguish "not sent" from "sent as null" — R5. |
| `data.avg_price` | Decimal or None | [BUG-711][BUG-708] When sent and not `null`, must be ≥ 0, at most 2 decimals, at most 13 integer digits (422 otherwise). Not sent = keep; explicit `null` = clear (R5). |
| `data.note` | str or None | Not sent = keep; explicit `null` = clear (R5). |
| `workspace_id`, `user_id` | int | Caller's workspace and acting profile. |

**Returns:** the same `Inventory` row, updated and flushed, not committed.

**Rules:**
- **R1.** A row id that does not exist, or belongs to another workspace → 404 `"Inventory record with ID {inv_id} not found"`; nothing is written.
- **R2.** A soft-deleted row → 400 `"Cannot update a deleted inventory record"`; nothing is written.
- **R3.** Fields sent with a value (`qty`, `avg_price`, `note`) replace the stored value. Fields not sent keep their value.
- **R4.** [BUG-711][BUG-708] A sent, non-null `qty` or `avg_price` is rejected by `InventoryUpdate` when `qty < 0`, `avg_price < 0`, or `avg_price` is too precise/large (422, nothing written). Valid values are stored as given (database rounds `avg_price` to 2 decimals). *(Today: no such validation — negative values and over-precise prices are accepted.)*
- **R5.** [BUG-713] `note` and `avg_price` sent as explicit `null` are cleared (stored `None`). `qty` sent as explicit `null` is detected via `data.model_fields_set` and rejected by the manager itself with `HTTPException` 422 `"qty cannot be empty"` — nothing is written. *(Today: any field sent as `null` is ignored via `exclude_none` and keeps its stored value; `note`/`avg_price` cannot be cleared; `qty: null` is likewise silently ignored rather than rejected.)* *(Requires the manager to inspect `model_fields_set` instead of `model_dump(exclude_none=True)`, and to distinguish "not sent" from "sent as null" per field.)*
- **R6.** [BUG-712] A ledger entry is written when `qty` is sent and differs from the current quantity (R7), OR when `qty` is not sent/unchanged but `avg_price` is sent and differs from the current `avg_price` (quantity 0, `qty_before = qty_after` = current qty, `avg_price_before`/`avg_price_after` set as in R7). No ledger entry is written when neither changes. *(Today: no ledger entry is written at all unless `qty` is sent and differs from the current quantity — an `avg_price`-only change leaves no record.)*
- **R6a.** [BUG-712] The avg-price-only ledger entry (R6, second case) has: same `workspace_id`, the row's `inventory_type`, `factory_id`, `item_id`; `transaction_type = "inventory_adjustment"`; `quantity = 0`; `qty_before = qty_after` = current qty; `unit_cost` = new `avg_price`; `total_cost = 0.00` when the new `avg_price` is not `None`, NULL when it is cleared to `None` (BUG-713); `avg_price_before` = previous `avg_price`; `avg_price_after` = new `avg_price` (`None` when cleared); `source_type = "adjustment"`; `source_id` NULL; `notes = "Average price adjusted from {old} to {new}"` (Python `str()` of each value, `None` printed as `None`); `performed_by = user_id` (best-practice default, delegated by reviewer — mirrors R7's field choices). Clearing a non-NULL `avg_price` to `None` counts as a change and writes this entry; sending the same value, or `null` when it is already NULL, does not. When both `qty` and `avg_price` change in one call, only the single R7 entry is written. *(Today: no such entry is written.)*
- **R7.** When `qty` is sent and differs from the current quantity, exactly one ledger entry is written: same `workspace_id`, and the row's `inventory_type`, `factory_id`, `item_id`; `transaction_type = "inventory_adjustment"`; `quantity = |new qty − old qty|` (always non-negative; direction is visible only in before/after); `unit_cost` = the new `avg_price` if sent, else the row's previous `avg_price`; `total_cost = unit_cost × quantity` when `unit_cost` is not `None`, else NULL [BUG-707] *(today: NULL also when `unit_cost` is `0`)*; `qty_before` = old qty; `qty_after` = new qty; `avg_price_before` = previous `avg_price`; `avg_price_after` = `unit_cost`; `source_type = "adjustment"`; `notes = "Quantity adjusted from {old} to {new}"`; `performed_by = user_id`.
- **R8.** `inventory_type`, `factory_id`, `item_id` and `workspace_id` cannot be changed through this method (not in the schema).
- **R9.** [BUG-703] `updated_by = user_id` is written only when at least one field actually changes value. *(Today: written on every successful call, including `{}`, all-`null`, or values equal to the stored ones.)*
- **R10.** [BUG-704] The row is read with a row lock — exactly `SELECT … FROM inventory LEFT OUTER JOIN items … FOR UPDATE OF inventory` (`with_for_update(of=Inventory)`; no `NOWAIT` / `SKIP LOCKED`). A plain `FOR UPDATE` is refused by Postgres because the load joins `items` (`Inventory.item` is `lazy="joined"`; BUG-029 rule, as `inventory_service.spec.md` `update_inventory` R1a) — so a concurrent adjustment sees the other's committed quantity; ledger `qty_before` always equals the quantity actually replaced. *(Today: no lock; two concurrent updates both record the same `qty_before`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Row missing or in another workspace | `HTTPException` 404 | `Inventory record with ID {inv_id} not found` |
| Row soft-deleted | `HTTPException` 400 | `Cannot update a deleted inventory record` |
| `qty < 0`, `avg_price < 0`, or `avg_price` too precise/large [BUG-711][BUG-708] | Pydantic `ValidationError` (422 at the API); manager not reached | Pydantic's message (not asserted) |
| `qty` sent as explicit `null` [BUG-713] | `HTTPException` 422 | `qty cannot be empty` |

**Side effects:** row fields updated (and `updated_by` when something changed), `updated_at` set by the database on change; zero or one ledger row inserted; flushed, not committed.

---

## `InventoryManager.get_inventory(session, inv_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public

**Purpose:** Fetch one inventory row of the workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `inv_id` | int | Inventory row id. |
| `workspace_id` | int | Caller's workspace. |
| `include_deleted` | bool | [BUG-700] Default `False`; `True` also returns a soft-deleted row. *(Does not exist today — requires new parameter `include_deleted`.)* |

**Returns:** the `Inventory` row.

**Rules:**
- **R1.** A row of the workspace is returned, whatever its quantity (including 0 or negative).
- **R2.** A row id that does not exist, or belongs to another workspace → 404 `"Inventory record with ID {inv_id} not found"` regardless of `include_deleted`.
- **R3.** [BUG-700] Given the row is soft-deleted and `include_deleted` is `False` (default), 404 `"Inventory record with ID {inv_id} not found"` is raised. *(Today: the soft-deleted row is returned with no error.)*
- **R4.** [BUG-700] Given the row is soft-deleted and `include_deleted` is `True`, it is returned. *(Requires new parameter `include_deleted`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Missing / other workspace / soft-deleted without `include_deleted` [BUG-700] | `HTTPException` 404 | `Inventory record with ID {inv_id} not found` |

**Side effects:** none.

---

## `InventoryManager.get_inventory_page(session, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** Paginated, filterable inventory list with a total count for the storage/inventory screens.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `inventory_type` | enum or None | Filter by type when given. |
| `factory_id` | int or None | Filter when truthy (`0` = no filter). |
| `item_id` | int or None | Filter when not `None` (`0` filters to item 0 → nothing). |
| `search` | str or None | Trimmed; blank/whitespace-only = no search. |
| `include_zero_qty` | bool, default False | When False only rows with qty > 0. |
| `skip`, `limit` | int, defaults 0 / 50 | API enforces `skip >= 0`, `1 <= limit <= 1000`; the manager does not. |

**Returns:** `InventoryListResponse` with `items`, `total`, `skip`, `limit`, `has_more`.

**Rules:**
- **R1.** Only live (not soft-deleted) rows of `workspace_id` are listed and counted; other workspaces' rows never appear.
- **R2.** Each given filter narrows the result: `inventory_type` (exact), `factory_id`, `item_id`. Filters combine with AND.
- **R3.** With `include_zero_qty=False` (default) only rows with qty > 0 are included (qty 0 and negative rows are excluded); with `True` all quantities are included.
- **R4.** [BUG-701] Rows are ordered by item name case-insensitive ascending, then inventory `id` ascending, before `skip`/`limit`. *(Today: item name ascending case-sensitively (database collation), then `id`.)*
- **R5.** `skip`/`limit` are applied after all filters; `items` holds at most `limit` rows starting at position `skip`.
- **R6.** A non-blank `search` (after trimming) keeps rows whose item name **or** item unit contains the text, case-insensitively. [BUG-702] `%`, `_` and `\` in the text match literally. *(Today: unescaped — `%` or `_` alone matches every row.)*
- **R7.** `total` is the number of rows matching all filters (and search), ignoring `skip`/`limit`.
- **R8.** `skip` and `limit` are echoed back unchanged; `has_more` is true exactly when `skip + len(items) < total`.

**Errors:** none.

**Side effects:** none.

---

## `InventoryManager.get_inventory_stats(session, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public

**Purpose:** KPI totals for the same filter set as the inventory list.

**Inputs:** as `get_inventory_page`, without `skip`/`limit`.

**Returns:** `InventoryStatsResponse(records, total_qty, estimated_value, by_type)`.

**Rules:**
- **R1.** The rows considered are exactly the rows `get_inventory_page` would count in `total` for the same filters (R1–R3, R6 there), without paging.
- **R2.** `records` = number of those rows; `total_qty` = sum of their `qty` (integer); both 0 when no rows match.
- **R3.** `estimated_value` = sum of `qty × avg_price` over the rows; rows with `avg_price` NULL contribute nothing; `Decimal` 0 when no rows match or all prices are NULL.
- **R4.** Search behaves as `get_inventory_page` R6 (including the BUG-702/HR-8 literal-text rule).
- **R5.** `by_type` has one entry (`InventoryStatsByTypeRow`) per inventory type that has at least one matching row, with `inventory_type` = the type (`InventoryTypeEnum`), `unique_item_count` = number of distinct items and `total_qty` = sum of qty for that type; types with no matching rows are absent; empty list when nothing matches.
- **R6.** [BUG-719] `by_type` is ordered by inventory type in enum declaration order: STORAGE, DAMAGED, WASTE, SCRAP. *(Today: order is whatever the database groups them in, which can change between calls.)*

**Errors:** none.

**Side effects:** none.

---

## `InventoryManager.delete_inventory(session, inv_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** "Clear stock": set an inventory row's quantity to zero and record the removal in the ledger; the row itself stays.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `inv_id` | int | Inventory row id. |
| `workspace_id`, `user_id` | int | Caller's workspace and acting profile. |

**Returns:** the `Inventory` row (flushed, not committed).

**Rules:**
- **R1.** A row id that does not exist or belongs to another workspace → 404 `"Inventory record with ID {inv_id} not found"`.
- **R2.** A soft-deleted row → 400 `"Cannot clear stock on a deactivated inventory record"`.
- **R3.** The row is never deleted or soft-deleted: `is_deleted` stays False, `is_active` stays True, `avg_price` and `note` are unchanged.
- **R4.** [BUG-716] When qty is exactly 0, the row is returned unchanged: no ledger entry, `updated_by` not written — a true no-op. When qty is negative, it is also cleared to 0 like a positive qty (R5, R6: `quantity = |old qty|`, `qty_before` = old qty, `qty_after = 0`). *(Today: any qty ≤ 0, including negative, is treated as the no-op case — a negative quantity is never brought back to zero.)*
- **R5.** When qty > 0 or qty < 0 (R4): qty becomes 0, `updated_by = user_id`, and exactly one ledger entry is written.
- **R6.** That ledger entry has: same `workspace_id`, the row's `inventory_type`, `factory_id`, `item_id`; `transaction_type = "inventory_adjustment"`; `quantity = |old qty|`; `unit_cost` = row's `avg_price`; `total_cost = avg_price × |old qty|` when `avg_price` is not `None`, otherwise NULL [BUG-707] *(today: NULL also when `avg_price` is `0`)*; `qty_before` = old qty; `qty_after = 0`; `avg_price_before = avg_price_after` = row's `avg_price`; `source_type = "adjustment"`; `notes = "Stock cleared"`; `performed_by = user_id`.
- **R7.** Calling it twice: the second call finds qty 0 and changes nothing (R4).
- **R8.** [BUG-705] The row is read with a row lock — exactly `FOR UPDATE OF inventory` on the joined load, as R10 (no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused; `inventory_service.spec.md` `delete_inventory` R1a); of two concurrent clears only one writes a ledger entry, the other returns the row with qty 0 unchanged. *(Today: no lock; both can write a "Stock cleared" entry.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Row missing or in another workspace | `HTTPException` 404 | `Inventory record with ID {inv_id} not found` |
| Row soft-deleted | `HTTPException` 400 | `Cannot clear stock on a deactivated inventory record` |

**Side effects:** `qty`, `updated_by` (and `updated_at` by the database) on the row; one ledger row; flushed, not committed.

---

## `InventoryManager.get_incoming_summary_for_factory(session, *, workspace_id, factory_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `get_incoming_summary`)

**Purpose:** Per catalog item, how much stock is still expected to arrive in one factory's storage from open purchase orders and incomplete inbound transfers.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | Caller's workspace. |
| `factory_id` | int | Must be a live (not soft-deleted) factory of the workspace; inactive-but-live accepted [BUG-718] (Q9). |

**Returns:** list of `ItemIncomingSummary(factory_id, item_id, total_pending_qty, order_count, orders)`; each `orders` entry is `IncomingOrderLine(order_kind, order_id, order_number, status_name, pending_qty)`. Quantities are `Decimal`.

**Rules:**
- **R1.** A factory id that does not exist or belongs to another workspace → 404 `"Factory with ID {factory_id} not found"`.
- **R2.** [BUG-718] A soft-deleted factory of the workspace → 404 `"Factory with ID {factory_id} not found"` (same as R1). An inactive-but-live factory is still summarised like any live one. *(Today: a soft-deleted factory is summarised like a live one, inconsistent with the workspace-wide summary which excludes it — R2 of `get_incoming_summary`.)*
- **R3.** Purchase orders considered: those of `workspace_id` with destination type `"storage"` and destination id = `factory_id`. POs of other workspaces, other factories, or other destination types (machine, project) never contribute.
- **R4.** [BUG-717] A PO is excluded when it is voided (`voided = True`), or when it is in its workflow's terminal status: it has a workflow, the workflow belongs to the workspace, the workflow's status sequence is a non-empty list whose last element is an integer status id, and the PO's current status equals that id. Every other PO counts as open — including POs without a workflow, POs whose workflow has an empty sequence or a non-integer last element, and POs whose workflow is in another workspace. *(Today: voided POs are not excluded and count as open indefinitely.)*
- **R5.** For each line of an open PO, pending = `quantity_ordered − quantity_received` (NULL treated as 0). Lines with pending ≤ 0 (fully or over-received) are skipped.
- **R6.** Transfer orders considered: those of `workspace_id` with destination location type `"storage"`, destination id = `factory_id`, and not completed (`completed_at` NULL). Completed transfers, other factories, other destination types and other workspaces never contribute. Transfer status or approvals do not matter.
- **R7.** For each line of such a transfer, the full line `quantity` counts as pending (NULL treated as 0); lines with quantity ≤ 0 are skipped.
- **R8.** Within one item, several lines of the same order are merged into one `orders` entry whose `pending_qty` is their sum. Lines of different orders give separate entries; a PO and a transfer with the same numeric id are separate entries (`order_kind` differs).
- **R9.** Each `orders` entry: `order_kind` `"purchase"` / `"transfer"`, `order_id` = order id, `order_number` = PO number / transfer number, `status_name` = name of the order's current status. Both `purchase_orders.current_status_id` and `transfer_orders.current_status_id` are NOT NULL (FK to `statuses`), so a status is always present; the code's "no status → `None`" fallback is unreachable with valid data and needs no test.
- **R10.** `total_pending_qty` for an item = sum of its entries' `pending_qty`; `order_count` = number of entries; `factory_id` = the requested factory.
- **R11.** Only items with at least one pending line appear; result sorted by `item_id` ascending. Within an item, purchase entries come first (by PO id ascending), then transfer entries (by transfer id ascending).
- **R12.** No open POs and no incomplete transfers (or all lines skipped) → empty list.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Factory missing, in another workspace, or soft-deleted [BUG-718] | `HTTPException` 404 | `Factory with ID {factory_id} not found` |

**Side effects:** none.

---

## `InventoryManager.get_incoming_summary(session, *, workspace_id, factory_id=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public

**Purpose:** Incoming-stock summary for one factory, or for every active factory of the workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int or None | When not `None`, one factory; `None` = all active factories. |

**Returns:** list of `ItemIncomingSummary`.

**Rules:**
- **R1.** With `factory_id` given (including `0`), the result is exactly `get_incoming_summary_for_factory` for that factory, including its 404.
- **R2.** Without `factory_id`, the result is the concatenation of each factory's summary for every factory of the workspace that is active and not soft-deleted; inactive or deleted factories and other workspaces' factories are left out. A factory with nothing incoming contributes nothing. No factories → empty list.
- **R3.** [BUG-709] All active, live factories of the workspace are considered, with no cap. *(Today: only the first 500 such factories, per whatever order the database returns them in, are considered — the rest are silently left out.)*
- **R4.** [BUG-706] Factories are processed in name case-insensitive ascending order, then `id` ascending, so the combined list is grouped by factory in that order (items by id within a factory). *(Today: no order.)*

**Errors:** as `get_incoming_summary_for_factory` (only when `factory_id` is given).

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 43–46 | factory found in workspace? | `create_inventory` R1, R2 |
| — (no soft-delete check on factory) | [BUG-715] factory soft-deleted → treat as not found | `create_inventory` R2 |
| — (no item/workspace check) | [BUG-710] item must belong to caller's workspace | `create_inventory` R3 |
| — (no `qty`/`avg_price` range validation) | [BUG-711][BUG-708] schema rejects negative/over-precise values | `create_inventory` R4 |
| 53–57 (dao `get_by_factory_item_type`) | live row exists for combination (deleted excluded) | `create_inventory` R5 |
| 67 (flush) | unique / FK violation | `create_inventory` R5, R9 |
| — (soft-deleted row not restored) | [BUG-714] restore soft-deleted row instead of conflicting | `create_inventory` R5 |
| 70 | `data.qty > 0` | `create_inventory` R7 |
| — (no ledger entry when `qty` is 0 with a price) | [BUG-712] `create_inventory` R7a (new) | `create_inventory` R7a |
| 79 | `data.avg_price` truthy | `create_inventory` R8 |
| 100 | row found in workspace? | `update_inventory` R1 |
| 105 | row soft-deleted | `update_inventory` R2 |
| — (no `qty`/`avg_price` range validation) | [BUG-711][BUG-708] schema rejects negative/over-precise values | `update_inventory` R4 |
| 114 | `exclude_unset` / `exclude_none` | `update_inventory` R3 |
| — (no distinction between absent and explicit `null` per field) | [BUG-713] `model_fields_set`-based clear/keep/reject | `update_inventory` R5 |
| 117 (base `update`) | `hasattr` on each field (all schema fields exist) | `update_inventory` R3, R8 |
| 121 | qty sent and changed | `update_inventory` R6, R7 |
| — (no ledger entry for an `avg_price`-only change) | [BUG-712] `update_inventory` R6 (rewritten) | `update_inventory` R6 |
| 122 | `avg_price` sent vs previous | `update_inventory` R7 |
| 131 | `new_avg` truthy | `update_inventory` R7 |
| 147 | row found | `get_inventory` R1–R3 |
| — (no `is_deleted` check) | [BUG-700] `include_deleted` parameter (new) | `get_inventory` R3, R4 |
| dao `_filtered_query` `if inventory_type` | type filter | `get_inventory_page` R2 |
| dao `_filtered_query` `if factory_id` | truthy factory filter | `get_inventory_page` R2 |
| dao `_filtered_query` `if item_id is not None` | item filter | `get_inventory_page` R2 |
| dao `_filtered_query` `if not include_zero_qty` | qty > 0 filter | `get_inventory_page` R3 |
| dao `_filtered_query` `if search` / `if term` | non-blank search after trim | `get_inventory_page` R6 |
| dao `list_filtered` order/offset/limit | ordering, paging | `get_inventory_page` R4, R5 |
| 202 | `skip + len(items) < total` | `get_inventory_page` R8 |
| dao `stats_filtered` coalesce | empty → 0 | `get_inventory_stats` R2, R3 |
| 228 | `estimated_value or Decimal(0)` | `get_inventory_stats` R3 |
| 229–236 | loop over by-type rows (0/1/many); `or 0` | `get_inventory_stats` R5 |
| — (no `by_type` order) | [BUG-719] ordered by inventory-type enum order | `get_inventory_stats` R6 |
| 242 | row found | `delete_inventory` R1 |
| 244 | row soft-deleted | `delete_inventory` R2 |
| 249 | `qty <= 0` | [BUG-716] narrowed to `qty == 0`; negative also cleared | `delete_inventory` R4, R7 |
| 262 | `old_avg` truthy | `delete_inventory` R6 |
| 287 | factory found in workspace | `get_incoming_summary_for_factory` R1 |
| — (no soft-delete check on factory) | [BUG-718] factory soft-deleted → treat as not found | `get_incoming_summary_for_factory` R2 |
| 298 (dao `list_for_destination`) | workspace / storage / factory filter | `get_incoming_summary_for_factory` R3 |
| 304 | PO has workflow | `get_incoming_summary_for_factory` R4 |
| util `terminal_status_ids_by_workflow` empty set / workspace filter / seq non-empty list / last is int | terminal map | `get_incoming_summary_for_factory` R4 |
| 311 (util `is_order_terminal`) | workflow or status None; terminal known; equal | `get_incoming_summary_for_factory` R4 |
| — (`voided` flag not checked) | [BUG-717] voided PO excluded regardless of status | `get_incoming_summary_for_factory` R4 |
| 320 | any open PO | `get_incoming_summary_for_factory` R12 |
| 325 | `or 0` on ordered/received | `get_incoming_summary_for_factory` R5 |
| 328 | pending ≤ 0 | `get_incoming_summary_for_factory` R5 |
| 332–333 | existing entry for (purchase, PO id) | `get_incoming_summary_for_factory` R8 |
| 338 | PO has current status (always true: NOT NULL column) | `get_incoming_summary_for_factory` R9 |
| 343 (dao `list_inbound_to_storage_incomplete`) | workspace / incomplete / storage / factory | `get_incoming_summary_for_factory` R6 |
| 348 | any incomplete transfer | `get_incoming_summary_for_factory` R12 |
| 353 | `or 0` on quantity | `get_incoming_summary_for_factory` R7 |
| 354 | qty ≤ 0 | `get_incoming_summary_for_factory` R7 |
| 358–359 | existing entry for (transfer, id) | `get_incoming_summary_for_factory` R8 |
| 364 | transfer has current status (always true: NOT NULL column) | `get_incoming_summary_for_factory` R9 |
| 370 | sorted item ids; loop empty/many | `get_incoming_summary_for_factory` R10–R12 |
| 391 | `factory_id is not None` | `get_incoming_summary` R1 |
| 396 (dao `get_active_factories`, limit 500, no order) | active & live | `get_incoming_summary` R2 |
| 396 (dao `get_active_factories`, `limit=500`) | [BUG-709] cap removed — all active, live factories | `get_incoming_summary` R3 |
| 396 (dao `get_active_factories`, no `ORDER BY`) | [BUG-706] ordered by name, then `id` | `get_incoming_summary` R4 |
| 400 | loop over factories (0/1/many) | `get_incoming_summary` R2 |

## Gap log
- G1 (inventory_manager.cases.md gap 1) — test mechanics — Notes for the test designer: patch target for the `create_inventory` R9 race is `inventory_dao.get_by_factory_item_type` (and `_get_any_by_factory_item_type` for the post-BUG-714 code) on the `app.dao.inventory.inventory_dao` singleton (best-practice default, delegated by reviewer).
- G2 (inventory_manager.cases.md gap 2) — test mechanics — Notes for the test designer: lock rules are observed via captured SQL (`SELECT … FOR UPDATE` on `inventory`); real concurrency out of unit scope (best-practice default, delegated by reviewer).
- G3 (inventory_manager.cases.md gap 3) — intent — new `update_inventory` R6a gives every field of the avg-price-only ledger entry (notes `"Average price adjusted from {old} to {new}"`, `source_type = "adjustment"`, `unit_cost` = new price, `total_cost` 0.00 / NULL on clear), plus the clear-to-NULL and qty-and-price-together cases (best-practice default, delegated by reviewer). Part of BUG-712; no new bug.
- G4 (inventory_manager.cases.md gap 4) — fact — `current_status_id` is NOT NULL on both purchase and transfer orders; `get_incoming_summary_for_factory` R9 and the Branch map now say the `None` fallback is unreachable with valid data.
- G5 (inventory_manager.cases.md gap 5) — contradiction — `create_inventory` R6 now covers newly created rows only; new R6a [BUG-714]: a restored row keeps its original `id`/`created_by`/`created_at` and gets `updated_by = user_id` per HR-9 (best-practice default, delegated by reviewer). Part of BUG-714; no new bug.
- G6 (inventory_manager.cases.md gap 6) — fact + intent — catalog items have no soft-delete column (fact); new `create_inventory` R3a: an inactive item of the workspace is accepted (best-practice default, delegated by reviewer).
- G7 (inventory_manager.cases.md gap 7) — test mechanics — Notes for the test designer: test-DB collation behavior for BUG-701, insertion-order today-behavior for BUG-706, and the possible XPASS of BUG-719 (reported as a non-strict discrepancy, never by weakening the assertion) (best-practice default, delegated by reviewer).
- G8 (inventory_manager.cases.md gap 8) — fact — `get_inventory_stats` R5 names the `by_type` entry field `inventory_type` (`InventoryStatsByTypeRow`).
- G9 (coordinator, 2026-11-22, from inventory_service fill-gaps G2) — fact — `update_inventory` R10 and `delete_inventory` R8 state the exact lock: `FOR UPDATE OF inventory` on the joined load; a plain `FOR UPDATE` is refused by Postgres (BUG-029 rule). The HR-10 lines above keep the short form; R10 / R8 are authoritative. Decided by Claude under the reviewer's delegation (2026-11-22).
