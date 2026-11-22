# Spec — `app/managers/inventory_movements.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-10** `_storage_out` R4, `_storage_in` R3 — the factory stock row (`inventory`) is read without a row lock, its quantity checked/changed in Python and written back. Two concurrent postings to the same factory/item/type bucket can both read the same quantity (e.g. both see 10, each takes 8 → 16 taken, stock shows 2, no "Insufficient stock" error). Intended: the stock row is read with `SELECT … FOR UPDATE`; the second posting waits, sees the new quantity and gets the normal 400 "Insufficient stock" when short. Same root cause as BUG-029 (`hr-10-unlocked-state-transition`).
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-660 (pattern `hr-10-unlocked-state-transition`, per BUG-029 precedent) — the factory stock bucket row is read with `SELECT … FOR UPDATE` before the quantity check; the loser of a race sees the post-update quantity and gets the normal 400 "Insufficient stock" when short. Rules: `_storage_out` R4, `_storage_in` R3.
- **HR-10** `_machine_out` R4, `_machine_in` R3 — same for a machine's on-hand stock row (`machine_items`): no row lock, so concurrent postings lose updates and can over-draw machine stock. Intended: the machine-item row is read with `SELECT … FOR UPDATE`; the loser sees the new quantity and gets the normal 400 "Insufficient machine stock" when short.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-661 (pattern `hr-10-unlocked-state-transition`, per BUG-029 precedent) — the machine-item row is read with `SELECT … FOR UPDATE` before the quantity check; the loser sees the post-update quantity and gets the normal 400 "Insufficient machine stock" when short. Rules: `_machine_out` R4, `_machine_in` R3.
- **HR-4** `_storage_out` R2, `_storage_in` R2 — a soft-deleted factory (`is_deleted = True`) is accepted as a stock location: stock can be posted into or out of it. Intended: a soft-deleted factory is treated as not found → 404 `Factory with ID {id} not found`. (Reviewer: override if reversals such as voiding a work order must still return stock to a factory deleted in the meantime.)
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-662 (pattern `hr-4-soft-deleted-location-accepted`) — a soft-deleted factory is treated as not found → 404 `Factory with ID {id} not found`; no reversal exception (not raised by the reviewer). Rules: `_storage_out` R2, `_storage_in` R2.
- **HR-4** `_machine_out` R2, `_machine_in` R2 — a soft-deleted machine is accepted as a stock location. Intended: 404 `Machine with ID {id} not found`. (Same reversal caveat as above.)
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-663 (pattern `hr-4-soft-deleted-location-accepted`) — a soft-deleted machine is treated as not found → 404 `Machine with ID {id} not found`. Rules: `_machine_out` R2, `_machine_in` R2.

- **HR-15** `weighted_avg_price` R2a and the `total_cost` of `_storage_out` R7, `_storage_in` R6, `_machine_out` R8, `_machine_in` R6 — `quantize` runs with no rounding argument, so an exact midpoint rounds half to even, while the database's `Numeric(15, 2)` rounds half away from zero. Intended: all money rounds half away from zero.
**Answer:** bug — per HR-15 (house rule; owner, 2026-10-30)
**Resolution:** 🐞 BUG-1040 (pattern `python-rounding-differs-from-database`) — every `quantize` in this module passes `ROUND_HALF_UP`. Rules: `weighted_avg_price` R2a; Overview › money rounding note.

### New questions

### Q1. "Latest ledger entry" is picked by timestamp alone — a third posting in one save can reset stock — 🐞 BUG-664
**Background:** Every stock movement writes one ledger row holding the quantity (and average price) *after* the movement. Before each factory posting the code re-reads the newest ledger row for that factory/item/type and, if the stored stock figure disagrees with it, overwrites the stock figure with the ledger's ("ledger wins"). Machine postings likewise take the machine's current average cost from the newest machine ledger row. "Newest" is decided only by the `performed_at` timestamp. For factory ledger rows that timestamp is the database's transaction start time, so every row written within the same save has the *identical* timestamp; for machine rows it is the app clock (identical whenever two rows land in the same clock tick, and always identical in tests where the clock is frozen).
**What happens today:** When two or more ledger rows for the same bucket share the newest timestamp, the database returns any one of them as "latest". If it returns an older one, the stock quantity and average price are silently rolled back to that older row's values before the next movement is applied.
**Example:** Work order WO-17 has three lines, each consuming 5 × "Bearing 6204" from Storage in Factory A, which holds 20. Starting the work order posts three stock-outs in one save. The first two leave the ledger at 15 and then 10. For the third, the "latest" row may be the 15 row: stock is reset to 15, then 5 is taken → stock shows 10 although 15 units were consumed (should be 5). The ledger itself now shows two rows ending at 10.
**Rules affected:** `_storage_out` R3a, `_storage_in` R3, `get_machine_unit_cost` R1
**Suggested answer:** bug — "latest ledger entry" is ordered by `performed_at` descending, then `id` descending, so the most recently inserted row always wins (fix in `InventoryLedgerDAO.get_latest_entry` / `MachineItemLedgerDAO.get_latest_entry`)
**Answer:** bug — order latest entry by performed_at desc, then id desc (fix in InventoryLedgerDAO.get_latest_entry and MachineItemLedgerDAO.get_latest_entry) (reviewer accepted suggestion)
**Resolution:** "latest" ledger entry for a bucket is the row with the greatest `performed_at`, ties broken by the greatest `id` (fix in `InventoryLedgerDAO.get_latest_entry` / `MachineItemLedgerDAO.get_latest_entry`), so the most recently inserted row always wins even when several rows share one timestamp. Rules: `_storage_out` R3a, `_storage_in` R3, `get_machine_unit_cost` R1.

### Q2. Zero or negative quantity is accepted and reverses the movement direction — 🐞 BUG-665
**Background:** `post_stock_out` / `post_stock_in` are the shared ledger writers used by transfer orders, purchase-order receiving/returns/voids and work-order consumption. Each of today's callers already rejects `qty <= 0` before calling, so this is only reachable by a future caller.
**What happens today:** Nothing checks `qty`. A stock-out with `qty = -5` passes the "enough stock" check (any stock is ≥ −5), *adds* 5 to stock and writes a ledger row with quantity −5 labelled as an outgoing transaction. `qty = 0` writes a zero-quantity ledger row (and, for machines, a "0 units" activity event).
**Example:** A new feature calls `post_stock_out(location_type='storage', qty=-5, transaction_type='consumption', …)` on a bucket holding 10. It returns normally; stock is now 15 and the ledger shows "consumption −5".
**Rules affected:** `post_stock_out` R5, `post_stock_in` R5
**Suggested answer:** bug — `qty < 1` is rejected with 400 before anything is written
**Answer:** bug — qty < 1 is rejected with 400 before anything is written (reviewer accepted suggestion)
**Resolution:** `post_stock_out` and `post_stock_in` reject `qty < 1` with 400 `Quantity must be at least 1, got {qty}` (exact detail wording is a best-practice default, delegated by reviewer), checked first — before the location-type dispatch and before anything is written. Rules: `post_stock_out` R5, `post_stock_in` R5.

### Q3. The item is never checked to belong to the workspace — 🐞 BUG-666
**Background:** Factories and machines are looked up within the caller's workspace (another workspace's id → 404). The item id is not looked up at all; the database only checks that *some* item with that id exists, in any workspace.
**What happens today:** An item id from another workspace is accepted: a stock row, ledger row and (for machines) activity event are created in this workspace pointing at the foreign item; the activity text names it `Item #<id>`. An item id that does not exist at all fails when the row is saved with a database foreign-key error (not a clean 404).
**Example:** Workspace A posts a stock-in of item #900 (which belongs to workspace B) into its Factory 1. It succeeds; Factory 1's inventory now lists workspace B's item. With item #999999 (non-existent) the call fails with a database integrity error instead of "Item with ID 999999 not found".
**Rules affected:** `_storage_out` R9, `_storage_in` R8, `_machine_out` R10, `_machine_in` R9
**Suggested answer:** bug — an item not found in `workspace_id` is rejected with 404 `Item with ID {id} not found` before anything is written
**Answer:** bug — an item not found in workspace_id is rejected with 404 'Item with ID {id} not found' before anything is written (reviewer accepted suggestion)
**Resolution:** the item id is looked up in `workspace_id` before anything is written; not found (non-existent, or belongs to another workspace) → 404 `Item with ID {item_id} not found`. Rules: `_storage_out` R9, `_storage_in` R8, `_machine_out` R10, `_machine_in` R9.

## Overview
Shared stock-posting mechanics: deduct stock from, or add stock to, either a factory stock bucket (`inventory` row for factory + item + type STORAGE/DAMAGED) or a machine's on-hand stock (`machine_items` row), writing one immutable ledger row per movement (`inventory_ledger` or `machine_item_ledger`) with before/after quantity and cost, maintaining a weighted-average unit cost, and (machines only) logging a machine activity event. Called by `to_inventory.py` (transfer orders), `po_receive_inventory.py` / `po_return_inventory.py` (purchase orders) and `WorkOrderManager` (consumption, reversal, quantity adjustment). Invariants it is meant to protect: stock never goes below zero; every change to stock has a matching ledger row; the stored stock figure equals the latest ledger row. Nothing is committed here — everything is flushed only.

**Callables:** 11 specified · 0 not specified
**Externals to mock:** `utcnow` (machine ledger `performed_at` and activity event `created_at` defaults). Factory ledger `performed_at` is a DB `server_default now()` (transaction start time — identical for all rows written in one test transaction). This module does NOT import or call `utcnow` itself: both values come from SQLAlchemy Python column defaults `default=utcnow` on `MachineItemLedger.performed_at` (`app/models/machine_item_ledger.py`) and `MachineActivityEvent.created_at` (`app/models/machine_activity_event.py`). The default holds a reference to the function object captured at import, so patching `app.managers.inventory_movements.utcnow` (does not exist) or `app.models.machine_item_ledger.utcnow` has NO effect — see Notes for the test designer for the working patch target.
**Integration-only behavior:** none. (Concurrency/row-lock behavior for the HR-10 items needs two sessions/connections; see notes.)

**Notes for the test designer:**
- All functions are module-level; call them directly with a real session. Create workspace, profile (user), factory, machine and item rows with the factories in `tests/unit/factories.py`.
- `location_type` strings are exact and case-sensitive: `'storage'`, `'damaged'`, `'machine'`.
- Numeric columns are `Numeric(15, 2)`: values read back after refresh are rounded to 2 decimals by Postgres.
- Money rounding: [BUG-1040] every "rounded to 2 decimals" in this spec, the `total_cost` of `_storage_out` R7, `_storage_in` R6, `_machine_out` R8 and `_machine_in` R6 included, rounds an exact midpoint half away from zero (HR-15). *(Today: half to even, Decimal default.)*
- HR-10 lock tests need a second connection (separate session) holding the row; a lock can also be asserted by checking that a concurrent `SELECT … FOR UPDATE NOWAIT` on the row from another connection fails while the posting's transaction is open.
- **Freezing `utcnow` (gap 1):** patch the column defaults' callables, e.g. `patch.object(MachineItemLedger.__table__.c.performed_at.default, "arg", lambda ctx: NOW)` and `patch.object(MachineActivityEvent.__table__.c.created_at.default, "arg", lambda ctx: NOW)` (SQLAlchemy 2.0 calls `default.arg(ctx)` at insert time). Equivalent alternative: patch `app.utils.time.datetime` so `utcnow()` returns `NOW` — this also freezes every other `utcnow` default written in the test, which is harmless here. Factory ledger `performed_at` cannot be frozen (DB `now()`); assert it is not null / equal across rows of one transaction.
- **Ledger ties today (gap 2; corrected by G6 after verification):** with several rows for the same bucket sharing the newest `performed_at`, today's `ORDER BY performed_at DESC LIMIT 1` has **no deterministic winner**. `performed_at` is indexed on both `inventory_ledger` and `machine_item_ledger`; depending on the plan Postgres picks, ties come back either **physically first-inserted** (sequential/bitmap scan + top-N sort) or **physically last-inserted / highest TID** (backward index scan). The verifier observed both within one test file (2 of 6 runs flipped). So neither "insert the intended row last" nor "insert it first" makes a BUG-664 `xfail(strict=True)` fail reliably. Required setup for every BUG-664 tie case (best-practice default, delegated by reviewer): with all rows sharing one `performed_at`, insert **B** (wrong values) first, then **C** (the intended latest, distinct values) with an **explicitly assigned `id` above the table's sequence** (e.g. current sequence value + 1 000 000, well below the Integer max), then **A** (wrong values) with a normal sequence id. Physical-first returns B, highest-TID returns A, and only the intended `ORDER BY performed_at DESC, id DESC` returns C — so the case fails today under every plan and passes after the fix. The realistic Q1 scenario (three storage postings of 5 in one transaction from a bucket of 20) is **not** deterministic today (ends at 10 under a physical-first plan, at the correct 5 under a backward index scan); it must not be used as a strict xfail case. It may be kept only as a plain (non-xfail) regression case once BUG-664 is fixed, asserting the final qty is 5 (best-practice default, delegated by reviewer).
- **Check order (gap 3):** see `post_stock_out` R6 / `post_stock_in` R6 — at most one error is raised, the first in that order.
- BUG-660/661/662/663/664/665/666 are all `xfail(strict=True)` until the corresponding fix lands; today's (buggy) behavior is noted in each affected rule's `*(Today: …)*` parenthetical.

## Not specified
- (none)

---

## `item_name(session, item_id, workspace_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** public (used by: `_machine_out`, `_machine_in`; imported by `to_inventory`, `po_receive_inventory`, `po_return_inventory`, `WorkOrderManager`)

**Purpose:** Display name of an item for messages, with a fallback.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| item_id | int | item id; none |
| workspace_id | int | only items of this workspace are found |

**Returns:** `str`.

**Rules:**
- **R1.** An item of `workspace_id` → its `name` exactly as stored.
- **R2.** No item with that id in `workspace_id` (non-existent, or belongs to another workspace) → the string `"Item #<item_id>"` (e.g. `"Item #42"`). No error.
- **R3.** An inactive item (`is_active = False`) is still found (R1).
- **R4.** Items have no soft-delete column (`items` has `is_active` but no `is_deleted`/`deleted_at`), so there is no "soft-deleted item" case here or in the BUG-666 item checks.

**Errors:** none.
**Side effects:** none.

---

## `weighted_avg_price(old_qty, old_avg, add_qty, unit_cost)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `_storage_in`, `_machine_in`)

**Purpose:** New moving-average unit cost after adding stock.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| old_qty | int | quantity before; none |
| old_avg | Decimal \| None | average cost before; `None` = unknown |
| add_qty | int | quantity added; none |
| unit_cost | Decimal | cost of the added units; none |

**Returns:** `Decimal`.

**Rules:**
- **R1.** `add_qty <= 0` (0 or negative) → returns `old_avg` unchanged; if `old_avg` is `None` (or zero) → `Decimal(0)`.
- **R2.** `add_qty > 0`, `old_qty > 0` and `old_avg` not `None` → `(old_qty × old_avg + add_qty × unit_cost) / (old_qty + add_qty)`, rounded to 2 decimals (an exact midpoint follows R2a). E.g. (10, 5.00, 10, 7.00) → `6.00`; (1, 1.00, 2, 1.00) → `1.00`; (2, 1.00, 1, 2.00) → `1.33`.
- **R2a.** [BUG-1040] An exact midpoint rounds half away from zero (HR-15), as the database does: (1, 0.01, 1, 0.04) = 0.025 → `0.03`; (1, 0.01, 1, 0.06) = 0.035 → `0.04`. *(Today: half to even, Decimal default: 0.025 → `0.02`. 0.035 → `0.04` is the same under both.)*
- **R3.** `add_qty > 0` and `old_qty <= 0` → returns `unit_cost` as given (not rounded), whatever `old_avg` is.
- **R4.** `add_qty > 0`, `old_qty > 0`, `old_avg` is `None` → returns `unit_cost` as given (existing units of unknown cost are ignored).
- **R5.** `old_avg = Decimal(0)` with `old_qty > 0` counts as a known average of zero (R2 applies, not R4): (10, 0, 10, 4.00) → `2.00`.

**Errors:** none raised by the function. (`old_qty + add_qty == 0` cannot reach the division because R2 needs both > 0.)
**Side effects:** none.

---

## `inventory_type_for_location(location_type)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `post_stock_out`, `post_stock_in`)

**Purpose:** Map a location type string to the factory inventory bucket type.

**Rules:**
- **R1.** `'damaged'` → `InventoryTypeEnum.DAMAGED`.
- **R2.** Any other string (including `'storage'`, `'machine'`, `'Damaged'`, `''`) → `InventoryTypeEnum.STORAGE`.

**Errors:** none.
**Side effects:** none.

---

## `_storage_out(session, *, factory_id, item_id, inventory_type, qty, transaction_type, source_type, source_id, notes, workspace_id, user_id, dest_type, dest_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_stock_out`)

**Purpose:** Deduct stock from a factory bucket and record the movement in the factory ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| factory_id | int | must be a factory of `workspace_id`, not soft-deleted (BUG-662) |
| item_id | int | must exist in `workspace_id` (BUG-666). An inactive item (`is_active = False`) is accepted — deactivating an item must not block stock returns, reversals or write-offs of existing stock (best-practice default, delegated by reviewer). Items cannot be soft-deleted (no `is_deleted` column). |
| inventory_type | InventoryTypeEnum | bucket type |
| qty | int | validated by the caller: `post_stock_out` rejects `qty < 1` before calling (BUG-665) |
| transaction_type, source_type, notes | str | copied to the ledger row. Free strings — no enum and no CHECK constraint: `transaction_type` is `String(50)` NOT NULL, `source_type` is `String(50)` nullable, `notes` is `Text` nullable. A value longer than 50 characters is not validated in Python; Postgres rejects it on flush with `sqlalchemy.exc.DataError` (value too long). |
| source_id | int | copied to the ledger row |
| dest_type / dest_id | str\|None / int\|None | copied to `transfer_destination_type` (`String(50)` nullable, free string) / `transfer_destination_id` (plain integer, no FK) |
| user_id | int | stamped as `updated_by` / `performed_by` / `created_by` |

**Returns:** `Decimal` unit cost used for the deduction (the bucket's average price before the movement, or `Decimal(0)` if it had none).

**Rules:**
- **R1.** Factory id not found in `workspace_id` (non-existent or in another workspace) → 404, nothing written.
- **R2.** [BUG-662] A soft-deleted factory is treated as not found → 404. *(Today: accepted; the movement is posted.)*
- **R3.** Getting the bucket: if a live `inventory` row for (workspace, factory, item, type) exists it is used; else if a soft-deleted one exists it is restored (`is_deleted = False`, `is_active = True`, `deleted_at`/`deleted_by` cleared); else a new row is created with `qty = 0`, `avg_price = None`, `created_by = user_id`. Rows of another inventory type, factory, item or workspace are never used.
- **R3a.** [BUG-664] The bucket row's `qty` and `avg_price` are then set from the newest ledger row for that bucket (`qty_after`, `avg_price_after`) — "newest" = greatest `performed_at`, ties broken by greatest `id` — or to 0 / `None` if the bucket has no ledger rows; if that changed anything, `updated_by = user_id`. *(Today: "newest" is by `performed_at` only; ties between rows written in the same transaction are resolved arbitrarily — a third posting in one save can silently roll stock back to an earlier value.)*
- **R4.** [BUG-660] The bucket row is read with a row lock (`SELECT … FOR UPDATE`) so concurrent postings to the same bucket are serialised. *(Today: no lock.)*
- **R5.** Available quantity (after R3/R3a) less than `qty` → 400 `Insufficient stock ({available} available, {qty} requested)`, e.g. `Insufficient stock (3 available, 5 requested)`; no ledger row written. (The bucket row from R3 may already have been created/restored/synced — the caller's transaction rollback removes it.)
- **R6.** Available quantity exactly equal to `qty` → allowed; stock becomes 0.
- **R7.** On success one `inventory_ledger` row is created with: `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `transaction_type`, `quantity = qty`, `unit_cost` = bucket's `avg_price` or `0`, `total_cost` = `unit_cost × qty` rounded to 2 decimals, `qty_before` = available qty, `qty_after` = available − qty, `avg_price_before` = `avg_price_after` = bucket's `avg_price` (may be `None`), `source_type`, `source_id`, `transfer_destination_type = dest_type`, `transfer_destination_id = dest_id`, `transfer_source_type`/`transfer_source_id` = `None`, `notes`, `performed_by = user_id`, `performed_at` = DB now().
- **R8.** On success the bucket row gets `qty = qty_before − qty`, `updated_by = user_id`; `avg_price` is unchanged. Returned value = R7's `unit_cost`.
- **R9.** [BUG-666] The item is looked up in `workspace_id` before anything is written; not found (non-existent, or belongs to another workspace) → 404 `Item with ID {item_id} not found`, nothing written. The item check runs after the factory check (R1/R2) and before the bucket is created/restored/synced (R3/R3a) and before the stock check (R5) (best-practice default, delegated by reviewer). An inactive item (`is_active = False`) passes the check (best-practice default, delegated by reviewer). *(Today: not checked — an item of another workspace is accepted; a non-existent item id raises the database's `IntegrityError` (foreign key) instead of a clean 404.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Factory not in workspace (or soft-deleted, per R2 / BUG-662) | HTTPException 404 | `Factory with ID {factory_id} not found` |
| Item not found in `workspace_id` (R9 / BUG-666) | HTTPException 404 | `Item with ID {item_id} not found` *(today: `IntegrityError` for a non-existent item id; another workspace's item is accepted with no error)* |
| Not enough stock | HTTPException 400 | `Insufficient stock ({available} available, {qty} requested)` |

**Side effects:** creates/restores/syncs one `inventory` row; one `inventory_ledger` row; flushed, not committed. No activity event.

---

## `_storage_in(session, *, factory_id, item_id, inventory_type, qty, unit_cost, transaction_type, source_type, source_id, notes, workspace_id, user_id, source_loc_type, source_loc_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_stock_in`)

**Purpose:** Add stock to a factory bucket at a given unit cost, updating its moving-average price, and record it in the factory ledger.

**Inputs:** as `_storage_out`, plus `unit_cost: Decimal` (not validated; negative accepted) and `source_loc_type` / `source_loc_id` (copied to `transfer_source_type` / `transfer_source_id`).

**Returns:** `None`.

**Rules:**
- **R1.** Factory not found in `workspace_id` → 404 (as `_storage_out` R1).
- **R2.** [BUG-662] Soft-deleted factory → 404 (as `_storage_out` R2). *(Today: accepted.)*
- **R3.** The bucket is obtained, restored or created exactly as `_storage_out` R3, and its `qty`/`avg_price` synced from the newest ledger row exactly as `_storage_out` R3a [BUG-664]. [BUG-660] The row is then read with a row lock (`SELECT … FOR UPDATE`), as `_storage_out` R4 (HR-10). *(Today: no lock.)*
- **R4.** No stock check: any quantity is added.
- **R5.** New average = `weighted_avg_price(qty_before, bucket avg_price, qty, unit_cost)` (see that function's rules). E.g. bucket 10 @ 5.00, add 10 @ 7.00 → 6.00; empty bucket, add 4 @ 3.50 → 3.50.
- **R6.** One `inventory_ledger` row: fields as `_storage_out` R7 except `unit_cost` = the given `unit_cost`, `total_cost` = `unit_cost × qty` rounded to 2 decimals, `qty_after = qty_before + qty`, `avg_price_before` = bucket's previous `avg_price`, `avg_price_after` = new average (R5), `transfer_source_type = source_loc_type`, `transfer_source_id = source_loc_id`, `transfer_destination_*` = `None`.
- **R7.** Bucket row gets `qty = qty_before + qty`, `avg_price` = new average, `updated_by = user_id`.
- **R8.** [BUG-666] Item checked in `workspace_id` as `_storage_out` R9 (same position: after the factory check, before bucket create/restore/sync); not found → 404 `Item with ID {item_id} not found`. *(Today: not checked, as `_storage_out` R9.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Factory not in workspace (or soft-deleted, per R2 / BUG-662) | HTTPException 404 | `Factory with ID {factory_id} not found` |
| Item not found in `workspace_id` (R8 / BUG-666) | HTTPException 404 | `Item with ID {item_id} not found` *(today: `IntegrityError` for non-existent; foreign-workspace item accepted with no error)* |

**Side effects:** one `inventory` row created/restored/updated; one `inventory_ledger` row; flushed, not committed. No activity event.

---

## `ensure_machine_item(session, *, machine_id, item_id, workspace_id)`
**Shape:** get-or-create
**Persistence:** writes
**Visibility:** public (used by: `_machine_out`, `_machine_in`)

**Purpose:** Return the machine's on-hand stock row for an item, creating an empty one if missing.

**Rules:**
- **R1.** A `machine_items` row for (workspace, machine, item) exists → that row is returned unchanged. Rows of another workspace, machine or item are not matched.
- **R2.** None exists → a new row is created with `workspace_id`, `machine_id`, `item_id`, `qty = 0` (`req_qty`, `defective_qty` = `None`), flushed, and returned.
- **R3.** The machine is not validated here: a machine id not in the workspace still gets a row (FK only requires the machine to exist anywhere); a non-existent machine or item id raises `IntegrityError` on flush.
- **R4.** If several rows exist for the same key (no unique constraint on the table), one of them is returned (unspecified which).

**Errors:** `IntegrityError` for non-existent machine/item id.
**Side effects:** at most one `machine_items` row inserted; flushed.

---

## `get_machine_unit_cost(session, *, machine_id, item_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `_machine_out`, `_machine_in`)

**Purpose:** Current average unit cost of an item on a machine, taken from the machine ledger.

**Rules:**
- **R1.** [BUG-664] Returns the `avg_price_after` of the newest `machine_item_ledger` row for (workspace, machine, item) as a `Decimal` — "newest" = greatest `performed_at`, ties broken by greatest `id`. *(Today: "newest" = latest `performed_at` only; ties are resolved arbitrarily.)*
- **R2.** No ledger row for that key (including rows existing only in another workspace or for another machine/item) → `Decimal(0)`.
- **R3.** Newest row has `avg_price_after = None` → `Decimal(0)` (older rows are not consulted).

**Errors:** none.
**Side effects:** none.

---

## `_machine_out(session, *, machine_id, item_id, qty, transaction_type, source_type, source_id, notes, workspace_id, user_id, dest_type, dest_id, activity_event_type, activity_description=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_stock_out`)

**Purpose:** Deduct stock from a machine's on-hand stock, record it in the machine ledger and the machine's activity log.

**Returns:** `Decimal` unit cost used (the machine's current average cost per `get_machine_unit_cost`).

**Rules:**
- **R1.** Machine id not found in `workspace_id` (non-existent or other workspace) → 404, nothing written.
- **R2.** [BUG-663] Soft-deleted machine → 404. *(Today: accepted.)*
- **R3.** The machine-item row is obtained or created per `ensure_machine_item`. Unlike factory buckets, its `qty` is NOT re-synced from the ledger.
- **R4.** [BUG-661] The machine-item row is read with a row lock (`SELECT … FOR UPDATE`). *(Today: no lock.)*
- **R5.** Row `qty` less than `qty` → 400 `Insufficient machine stock ({available} available, {qty} requested)`; no ledger row or event. (A newly created empty `machine_items` row may remain until the caller rolls back.)
- **R6.** Row `qty` exactly equal to `qty` → allowed; becomes 0.
- **R7.** `unit_cost` = `get_machine_unit_cost` for the machine/item.
- **R8.** One `machine_item_ledger` row (`transaction_type` and `source_type` are free `String(50)` NOT NULL columns, no enum/CHECK; `transfer_*_type` free `String(50)` nullable; `notes` `Text`): `workspace_id`, `machine_id`, `item_id`, `transaction_type`, `quantity = qty`, `unit_cost`, `total_cost` = `unit_cost × qty` rounded to 2 decimals, `qty_before`, `qty_after = qty_before − qty`, `value_before = qty_before × unit_cost`, `value_after = qty_after × unit_cost` (stored to 2 decimals), `avg_price_before` = `avg_price_after` = `unit_cost`, `source_type`, `source_id`, `transfer_destination_type = dest_type`, `transfer_destination_id = dest_id`, `transfer_source_*` = `None`, `order_type`/`order_id`/`invoice_id` = `None`, `notes`, `performed_by = user_id`, `performed_at = utcnow()`. The machine-item row's `qty` becomes `qty_after`.
- **R9.** One machine activity event is recorded for the machine: `workspace_id`, `event_type = activity_event_type` (free string, `String(50)` NOT NULL, no enum/CHECK — longer than 50 chars → `DataError` on flush), `performed_by = user_id`, `created_at = utcnow()`, `description = activity_description` if truthy, else `"{transaction_type}: {qty} units of {item name}"` (e.g. `"consumption: 3 units of Bearing 6204"`; an empty-string description also falls back). Metadata = `{"item_id": item_id, "item_name": <name>, "quantity": qty}` plus `"work_order_id": source_id` only when `source_type == 'work_order'` (exact, case-sensitive). Item name follows `item_name` (fallback `Item #<id>`).
- **R10.** [BUG-666] Item checked in `workspace_id`; not found (non-existent, or belongs to another workspace) → 404 `Item with ID {item_id} not found`, nothing written. Runs after the machine check (R1/R2) and before the machine-item row is created (R3) and before the stock check (R5); inactive items pass (as `_storage_out` R9) (best-practice default, delegated by reviewer). *(Today: not checked — an item of another workspace is accepted and named `Item #<id>` in the event; a non-existent item raises `IntegrityError`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Machine not in workspace (or soft-deleted, per R2 / BUG-663) | HTTPException 404 | `Machine with ID {machine_id} not found` |
| Item not found in `workspace_id` (R10 / BUG-666) | HTTPException 404 | `Item with ID {item_id} not found` *(today: `IntegrityError` for non-existent; foreign-workspace item accepted with no error)* |
| Not enough machine stock | HTTPException 400 | `Insufficient machine stock ({available} available, {qty} requested)` |

**Side effects:** `machine_items` row possibly created and its `qty` updated; one `machine_item_ledger` row; one `machine_activity_events` row; flushed, not committed.

---

## `_machine_in(session, *, machine_id, item_id, qty, unit_cost, transaction_type, source_type, source_id, notes, workspace_id, user_id, source_loc_type, source_loc_id, activity_event_type, activity_description=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_stock_in`)

**Purpose:** Add stock to a machine at a given unit cost, update its moving-average cost, and record ledger + activity.

**Returns:** `None`.

**Rules:**
- **R1.** Machine not found in workspace → 404 (as `_machine_out` R1).
- **R2.** [BUG-663] Soft-deleted machine → 404 (as `_machine_out` R2). *(Today: accepted.)*
- **R3.** Machine-item row obtained/created per `ensure_machine_item`. [BUG-661] It is then read with a row lock (`SELECT … FOR UPDATE`), as `_machine_out` R4. *(Today: no lock.)* No stock check; any quantity is added.
- **R4.** `avg_before` = `get_machine_unit_cost` for the machine/item.
- **R5.** `avg_after` = `weighted_avg_price(qty_before, avg_before, qty, unit_cost)` when `qty_before > 0`; when `qty_before <= 0` the old average is ignored and `avg_after = unit_cost` (for `qty > 0`). E.g. machine holds 4 @ 10.00, add 4 @ 20.00 → 15.00; machine holds 0 (last ledger avg 10.00), add 2 @ 20.00 → 20.00.
- **R6.** One `machine_item_ledger` row: as `_machine_out` R8 except `unit_cost` = given `unit_cost`, `total_cost` = `unit_cost × qty` rounded to 2 decimals, `qty_after = qty_before + qty`, `value_before = qty_before × avg_before`, `value_after = qty_after × avg_after`, `avg_price_before = avg_before`, `avg_price_after = avg_after`, `transfer_source_type = source_loc_type`, `transfer_source_id = source_loc_id`, `transfer_destination_*` = `None`. The machine-item row's `qty` becomes `qty_after`.
- **R7.** One machine activity event exactly as `_machine_out` R9.
- **R8.** When the machine-item row has stock but no ledger history (so `avg_before = 0`), the existing units count as zero-cost in the new average: holds 5, no ledger, add 5 @ 10.00 → `avg_after = 5.00`.
- **R9.** [BUG-666] Item checked in `workspace_id` as `_machine_out` R10 (same position: after the machine check, before the machine-item row is created); not found → 404 `Item with ID {item_id} not found`. *(Today: not checked, as `_machine_out` R10.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Machine not in workspace (or soft-deleted, per R2 / BUG-663) | HTTPException 404 | `Machine with ID {machine_id} not found` |
| Item not found in `workspace_id` (R9 / BUG-666) | HTTPException 404 | `Item with ID {item_id} not found` *(today: `IntegrityError` for non-existent; foreign-workspace item accepted with no error)* |

**Side effects:** `machine_items` row possibly created and `qty` updated; one `machine_item_ledger` row; one `machine_activity_events` row; flushed, not committed.

---

## `post_stock_out(session, *, location_type, location_id, item_id, qty, transaction_type, source_type, source_id, notes, workspace_id, user_id, dest_type=None, dest_id=None, activity_event_type=None, activity_description=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `to_inventory._post_location_out`, `po_receive_inventory`, `po_return_inventory`, `WorkOrderManager._consume_item` / `_adjust_consumed_item_quantity`)

**Purpose:** Deduct stock from a factory storage/damaged bucket or a machine.

**Returns:** `Decimal` unit cost used for the deduction.

**Rules:**
- **R1.** `location_type == 'storage'` → factory deduction from the STORAGE bucket of factory `location_id`, per `_storage_out`; returns its unit cost.
- **R2.** `location_type == 'damaged'` → same, from the DAMAGED bucket. STORAGE and DAMAGED are independent: stock in one never satisfies a deduction from the other.
- **R3.** `location_type == 'machine'` → machine deduction from machine `location_id`, per `_machine_out`; the activity event type is `activity_event_type` if truthy, else `transaction_type`; `activity_description` passed through. For factory locations `activity_event_type`/`activity_description` are ignored (no event).
- **R4.** Any other `location_type` (e.g. `'project'`, `'Storage'`, `''`) → 400 `Unsupported source location type: {location_type}`; nothing written.
- **R5.** [BUG-665] `qty < 1` is rejected with 400 `Quantity must be at least 1, got {qty}` (exact wording: best-practice default, delegated by reviewer), checked first, before the location-type dispatch (R1–R4) and before anything is written. *(Today: not validated — `qty = 0` writes a zero-quantity movement; a negative `qty` passes the stock check and increases stock.)*
- **R6.** Check order when several inputs are invalid — only the first failing check raises (best-practice default, delegated by reviewer: most fundamental first, all validation before any write): (1) `qty < 1` → 400 [BUG-665]; (2) unsupported `location_type` → 400; (3) location (factory/machine) not found or soft-deleted → 404 [BUG-662/663]; (4) item not found in workspace → 404 [BUG-666]; (5) insufficient stock → 400. E.g. factory missing AND item missing → `Factory with ID … not found`; foreign item AND insufficient stock → `Item with ID … not found`. Today steps (1) and (4) do not exist; (2) → (3) → (5) already hold in that order.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `qty < 1` (R5 / BUG-665) | HTTPException 400 | `Quantity must be at least 1, got {qty}` |
| Unknown location type | HTTPException 400 | `Unsupported source location type: {location_type}` |
| (plus errors of `_storage_out` / `_machine_out`) | | |

**Side effects:** those of `_storage_out` or `_machine_out`.

---

## `post_stock_in(session, *, location_type, location_id, item_id, qty, unit_cost, transaction_type, source_type, source_id, notes, workspace_id, user_id, source_loc_type=None, source_loc_id=None, activity_event_type=None, activity_description=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `to_inventory._post_location_in`, `po_receive_inventory`, `WorkOrderManager._reverse_item_consumption` / `_adjust_consumed_item_quantity`)

**Purpose:** Add stock to a factory storage/damaged bucket or a machine.

**Returns:** `None`.

**Rules:**
- **R1.** `'storage'` → per `_storage_in` into the STORAGE bucket of factory `location_id`.
- **R2.** `'damaged'` → per `_storage_in` into the DAMAGED bucket.
- **R3.** `'machine'` → per `_machine_in` for machine `location_id`; activity event type = `activity_event_type` if truthy, else `transaction_type`. Factory locations log no event.
- **R4.** Any other `location_type` → 400 `Unsupported destination location type: {location_type}`; nothing written.
- **R5.** [BUG-665] `qty < 1` is rejected with 400 `Quantity must be at least 1, got {qty}` (exact wording: best-practice default, delegated by reviewer), checked first, before the location-type dispatch (R1–R4) and before anything is written. *(Today: not validated — a negative `qty` reduces stock with no stock check (can drive stock below zero); `0` writes a zero-quantity movement.)*
- **R6.** Check order as `post_stock_out` R6, without step (5) (no stock check on stock-in): `qty` → `location_type` → location → item (best-practice default, delegated by reviewer).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `qty < 1` (R5 / BUG-665) | HTTPException 400 | `Quantity must be at least 1, got {qty}` |
| Unknown location type | HTTPException 400 | `Unsupported destination location type: {location_type}` |
| (plus errors of `_storage_in` / `_machine_in`) | | |

**Side effects:** those of `_storage_in` or `_machine_in`.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| L24 | item found in workspace / not | `item_name` R1, R2 |
| L33 | `add_qty <= 0` | `weighted_avg_price` R1 |
| L34 | `old_avg or Decimal(0)` falsy (None / 0) | `weighted_avg_price` R1 |
| L35 | `old_qty > 0 and old_avg is not None` | `weighted_avg_price` R2, R4, R5 |
| L38 | fallthrough → `unit_cost` | `weighted_avg_price` R3, R4 |
| L42 | `location_type == 'damaged'` | `inventory_type_for_location` R1, R2 |
| L64 | factory not found | `_storage_out` R1, R2 |
| DAO `ensure_for_factory_item_type`: live / soft-deleted / none / IntegrityError race | bucket resolution | `_storage_out` R3 |
| DAO `sync_snapshot_from_ledger`: latest exists / none; differs / same | snapshot sync, `updated_by` | `_storage_out` R3a |
| L75 | `inv.qty < qty` | `_storage_out` R5, R6 |
| L81 | `inv.avg_price or Decimal(0)` | `_storage_out` R7 |
| L133 | factory not found | `_storage_in` R1, R2 |
| L147 | weighted average | `_storage_in` R5 |
| L182 | machine item exists / not | `ensure_machine_item` R1, R2 |
| L199 | latest exists and `avg_price_after` not None | `get_machine_unit_cost` R1, R2, R3 |
| L222 | machine not found | `_machine_out` R1, R2 |
| L226 | `mi.qty < qty` | `_machine_out` R5, R6 |
| L267 | `source_type == 'work_order'` | `_machine_out` R9 |
| L274 | `activity_description or …` | `_machine_out` R9 |
| L300 | machine not found | `_machine_in` R1, R2 |
| L307 | `qty_before > 0` → pass avg / None | `_machine_in` R5, R8 |
| L340 | `source_type == 'work_order'` | `_machine_in` R7 |
| L347 | `activity_description or …` | `_machine_in` R7 |
| L372 | `'storage'`/`'damaged'` | `post_stock_out` R1, R2 |
| L388 | `'machine'` | `post_stock_out` R3 |
| L402 | `activity_event_type or transaction_type` | `post_stock_out` R3 |
| L405 | other location type | `post_stock_out` R4 |
| L431 | `'storage'`/`'damaged'` | `post_stock_in` R1, R2 |
| L449 | `'machine'` | `post_stock_in` R3 |
| L464 | `activity_event_type or transaction_type` | `post_stock_in` R3 |
| L468 | other location type | `post_stock_in` R4 |
| L372–L405, L64/L222, L75/L226 | order of dispatch → location lookup → stock check | `post_stock_out` R6 |
| L431–L468, L133/L300 | order of dispatch → location lookup | `post_stock_in` R6 |

## Gap log
- G1 (inventory_movements.cases.md gap 1) — Fact + test mechanics — Overview "Externals to mock" now states that `utcnow` enters only via the Python column defaults on `MachineItemLedger.performed_at` / `MachineActivityEvent.created_at` (the module has no `utcnow` of its own, so `app.managers.inventory_movements.utcnow` is not a valid patch target); Notes give the working patch (`patch.object(<Column>.default, "arg", lambda ctx: NOW)`) and the `app.utils.time.datetime` alternative.
- G2 (inventory_movements.cases.md gap 2) — Fact (verified on the test DB) + test mechanics — today's tie-break returns the physically first-inserted tied row; Notes tell the designer to insert the intended-latest (greatest id) row LAST so BUG-664 strict xfails fail today, and that the Q1 three-postings scenario is deterministic in practice (ends at 10 instead of 5). The cases file's current "correct row physically first" setup would XPASS and must be flipped. *(Superseded by G6: the tie result is plan-dependent, see Notes.)*
- G3 (inventory_movements.cases.md gap 3) — Intent, decided (best-practice default, delegated by reviewer) — added `post_stock_out` R6 / `post_stock_in` R6 (check order qty → location_type → location → item → stock) and placed the BUG-666 item check after the location check and before bucket create/restore/sync / machine-item create in `_storage_out` R9, `_storage_in` R8, `_machine_out` R10, `_machine_in` R9. No new bug: covered by the BUG-665/BUG-666 fixes.
- G4 (inventory_movements.cases.md gap 4) — Fact + Intent, decided (best-practice default, delegated by reviewer) — items have no soft-delete column (`item_name` R4); the BUG-666 item check accepts inactive items (`_storage_out` Inputs/R9, `_machine_out` R10).
- G5 (inventory_movements.cases.md gap 5) — Fact — `transaction_type`, `source_type`, `transfer_*_type` and `event_type` are free `String(50)` columns with no enum/CHECK (NOT NULL except `inventory_ledger.source_type` and `transfer_*_type`); over-long values raise `DataError` on flush; recorded in `_storage_out` Inputs, `_machine_out` R8/R9.
- G6 (inventory_movements.verify.md finding 2) — Fact correction + test mechanics — the G2 "verified" claim (ties today always return the physically first-inserted row) is wrong: `performed_at` is indexed on both ledger tables and a backward index scan returns the highest-TID tied row, so today's tie result is plan-dependent (verifier saw MUC-05 XPASS strict in 2/6 runs). Notes now require the B → C (explicit id above sequence) → A insertion for every BUG-664 tie case, and forbid using the Q1 three-postings scenario as a strict xfail (best-practice default, delegated by reviewer). No new rule, no new bug (still BUG-664).
