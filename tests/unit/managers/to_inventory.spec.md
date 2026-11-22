# Spec — `app/managers/to_inventory.py`

> **Status:** APPROVED
> **Source commit:** `e48a092`

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-10** `_post_location_out` R5a — the source stock (factory bucket or machine stock) is checked for enough quantity and then reduced without a row lock; two concurrent postings (another transfer order, a work order consuming stock) can both pass the check and drive stock negative or lose one deduction. Intended: the source stock row is read with `SELECT … FOR UPDATE` before the availability check (fix lives in the shared helpers of `app/managers/inventory_movements.py`, `_storage_out` / `_machine_out`). — 🐞 BUG-820
**Answer:** bug — per HR-10 (house rule)
**Resolution:** row locked before the availability check. Rules: `_post_location_out` R5a.
- **HR-10** `post_transfer_order_inventory` R3a — "already posted?" is checked and then stock is moved without any lock or database uniqueness; two concurrent completions of the same transfer order both see "not posted" and both move the stock. Intended: a line is posted at most once even under concurrent completion (lock the transfer order row with `SELECT … FOR UPDATE` in the caller `TransferOrderManager.mark_order_complete` before the completed/posted checks). — 🐞 BUG-821
**Answer:** bug — per HR-10 (house rule)
**Resolution:** caller locks the transfer order row before its completed/posted checks. Rules: `post_transfer_order_inventory` R3a.

- **HR-15** `_post_location_in` R5a, R6a — a weighted average and a `total_cost` are rounded with `quantize` and no rounding argument, so an exact midpoint rounds half to even, while the database's `Numeric(15, 2)` rounds half away from zero. Intended: all money rounds half away from zero.
**Answer:** bug — per HR-15 (house rule; owner, 2026-10-30)
**Resolution:** 🐞 BUG-1040 (pattern `python-rounding-differs-from-database`) — fixed in `app/managers/inventory_movements.py`, which does the rounding for this module. Rules: `_post_location_in` R5a, R6a.

### Precedent matches — confirm all with ok

### Q1. Deleted factory or machine accepted as transfer source/destination — 🐞 BUG-822
**Background:** factories and machines are soft-deleted (`is_deleted = True`, the row stays). The lookup used here finds a factory/machine by id within the workspace and does not look at `is_deleted`.
**What happens today:** when a transfer order is completed, stock is taken from / put into a factory or machine even if that factory or machine has since been deleted. Only a missing id or one from another workspace is rejected (404).
**Example:** Transfer TR-2026-004 moves 10 bearings from Factory A storage to Machine M-7. M-7 is deleted before the order is completed. On completion, 10 bearings are removed from Factory A and added to the deleted machine M-7's stock, where nobody can see or use them.
**Rules affected:** `_post_location_out` R3, R8; `_post_location_in` R4, R8
**Answer:** bug — per BUG-340 precedent: a soft-deleted factory or machine is rejected as a transfer source/destination exactly like a missing one (404 "Factory with ID {id} not found" / "Machine with ID {id} not found"), nothing written (precedent — confirmed: ok)
**Resolution:** a soft-deleted factory or machine is rejected exactly like a missing one. Rules: `_post_location_out` R3a, R8a; `_post_location_in` R4, R8.

### Q2. Location type is free text; unknown or differently-cased types only fail at completion — 🐞 BUG-823
**Background:** a transfer order stores `source_location_type` / `destination_location_type` as plain text. The create/update schemas accept any string; this module is the only place that checks the value, and only when the order is completed.
**What happens today:** an order with a type like `"Storage"`, `"warehouse"` or `""` can be created, filled with lines and approved; completing it fails with 400 "Unsupported source location type: Storage" (or destination), and the order can never be completed without editing it.
**Example:** A user creates a transfer with source type `"Storage"` (capital S) from an API client. It gets both approvals. Clicking "Complete" returns 400 "Unsupported source location type: Storage".
**Rules affected:** `_post_location_out` R1, R1a; `_post_location_in` R2, R2a
**Answer:** bug — per BUG-360 precedent: `TransferOrderCreate`/`TransferOrderUpdate` accept only the known location types (source: `storage`, `damaged`, `machine`; destination: `storage`, `damaged`, `machine`, `project`) and reject anything else with 422 at entry; the completion-time check here stays as a safety net (precedent — confirmed: ok)
**Resolution:** schema validates location types at entry (422); the completion-time check stays as a safety net. Rules: `_post_location_out` R1a; `_post_location_in` R2a.

### New questions

### Q3. Fractional, zero or negative line quantities are only rejected at completion — 🐞 BUG-824
**Background:** stock is counted in whole units (inventory and machine stock columns are integers). The transfer line schema accepts any decimal for `quantity` — no minimum, no whole-number check. This module checks it only when the order is completed.
**What happens today:** a line with quantity `2.5`, `0` or `-3` can be added, and the order can be approved; completing it fails with 400 ("Line 2 has a fractional quantity; inventory transfers require whole units" or "Line 2 has no quantity to transfer"). Approvals must then be withdrawn to fix the line.
**Example:** A user enters 2.5 kg of grease on line 2 of TR-2026-010. Two managers approve. On "Complete" the user gets 400 "Line 2 has a fractional quantity; inventory transfers require whole units" and has to ask both managers to withdraw and re-approve after the fix.
**Rules affected:** `_quantity_to_int` R2–R4; `post_transfer_order_inventory` R4
**Suggested answer:** bug — `TransferOrderItemCreate`/`TransferOrderItemUpdate` reject a quantity that is not a whole number greater than 0 with 422 at entry; the completion-time check here stays as a safety net
**Answer:** bug — TransferOrderItemCreate/Update reject a quantity that is not a whole number greater than 0 with 422 at entry; keep the completion-time check as a safety net (reviewer accepted suggestion)
**Resolution:** schema validates quantity at entry (422); the completion-time check stays as a safety net. Rules: `_quantity_to_int` R5.

### Q4. "Project" destination can be chosen but can never be completed — 🐞 BUG-825
**Background:** the transfer order UI/labels know a `project` destination type, and creation accepts it. Posting stock into a project is not implemented here.
**What happens today:** an order with destination type `project` can be created, filled and approved; completion always fails with 400 "Project destination inventory posting is not yet supported", so the order is stuck.
**Example:** A user creates TR-2026-012 sending 5 cables from Factory A to Project P-3, gets approvals, clicks "Complete" and gets 400 "Project destination inventory posting is not yet supported". There is no way to finish that order.
**Rules affected:** `_post_location_in` R1
**Suggested answer:** bug — while project posting is unsupported, creating or updating a transfer order with destination type `project` is rejected at entry (400 "Project destination is not yet supported"), so no order can get stuck at completion
**Answer:** bug — while project posting is unsupported, reject destination type 'project' at create/update (400), so no order can get stuck at completion (reviewer accepted suggestion)
**Resolution:** creation/update rejects destination type `project` at entry (400); the completion-time check becomes unreachable via the normal API. Rules: `_post_location_in` R1a.

### Q5. "Insufficient stock" error does not say which line or item — 🐞 BUG-826
**Background:** completion posts every line in turn; the stock-shortage message comes from shared stock helpers used by several features.
**What happens today:** the 400 detail is "Insufficient stock (3 available, 5 requested)" (or "Insufficient machine stock (…)"), with no line number or item name, while the quantity errors in the same flow do name the line.
**Example:** TR-2026-020 has 6 lines. Completion returns 400 "Insufficient stock (3 available, 5 requested)"; the user cannot tell which of the six items is short.
**Rules affected:** `_post_location_out` R5, R9
**Suggested answer:** bug — the shortage error names the line and item, e.g. "Line 4 (Bearing 6204): insufficient stock (3 available, 5 requested)" (status stays 400)
**Answer:** bug — the shortage error names the line and item, e.g. 'Line 4 (Bearing 6204): insufficient stock (3 available, 5 requested)'; status stays 400 (reviewer accepted suggestion)
**Resolution:** shortage error names the line and item; status stays 400. Rules: `_post_location_out` R5b, R9a.

## Overview
Posts a completed transfer order's lines into the stock ledgers: for each line it removes the quantity from the order's source location (a factory's storage or damaged bucket, or a machine's on-hand stock) and adds it to the destination at the source's unit cost, writing one ledger row per side. It is called only by `TransferOrderManager.mark_order_complete` (inside the `TransferOrderService.mark_order_complete` transaction, which commits on success and rolls back on any exception). It protects: stock never goes below zero at the source, costs follow the goods (weighted average at the destination), and a line is never posted twice. The stock mechanics live in `app/managers/inventory_movements.py`; their effects are described here as outcomes.

**Notes for the test designer:**
- Call the module-level functions directly with a real session. `to` and `items` are real `TransferOrder` / `TransferOrderItem` rows (flushed so they have ids); only `to.transfer_number`, `to.source_location_type/id`, `to.destination_location_type/id`, and each line's `id`, `line_number`, `item_id`, `quantity` are read.
- Setup needs real `workspaces`, `profiles` (for `performed_by` / `created_by` / `updated_by` FKs), `items`, `factories`, `machines`, and a `statuses` row for the transfer order's `current_status_id`.
- Factory stock ("buckets") is aligned to the ledger before use: a bucket's current qty and average price are taken from the **latest `inventory_ledger` row** for (workspace, factory, item, type), not from the `inventory` row. To seed factory stock, insert an `inventory_ledger` row with the desired `qty_after` / `avg_price_after` (and optionally an `inventory` row). An `inventory` row with qty but no ledger history is treated as 0 stock / no average.
- `inventory_ledger.performed_at` is a server default `now()`, which is the **transaction start time** in Postgres, so every row inserted in the test's transaction gets the same timestamp. Seed prior ledger rows with an explicit `performed_at` in the past so "latest" is unambiguous.
- Machine stock comes from `machine_items.qty` (NOT aligned to the ledger); the machine's unit cost comes from the latest `machine_item_ledger` row (ordered by `performed_at`, which defaults to `utcnow()`). Seed machine ledger rows with explicit, distinct `performed_at`.
- A row lock (HR-10 rules) is checked by capturing the SQL emitted during the call (e.g. a SQLAlchemy `before_cursor_execute` listener) and asserting the SELECT on the stock table contains `FOR UPDATE`; only the two-session race itself is integration-only.
- On an error, earlier writes of the same call remain in the session (flushed, not committed); roll back / use `session.begin_nested()` around the call if a test needs a clean re-read.
- Schema payloads (for the entry-time BUG-823 / BUG-824 rules): `TransferOrderItemCreate` requires `item_id` (int) and `quantity` (Decimal); `notes` is optional. `TransferOrderItemUpdate` has no required fields (`quantity`, `approved`, `transferred_by`, `transferred_at`, `notes` all optional, default None). `TransferOrderCreate` requires `source_location_type` (str), `source_location_id` (int), `destination_location_type` (str), `destination_location_id` (int); `description` optional, `current_status_id` defaults to 1, `items` optional. `TransferOrderUpdate` has no required fields (all optional). Fill every required field other than the one under test with a valid value (e.g. `item_id=1`, ids `1`, types `storage`).
- Numeric scale: every money/price column touched here is `Numeric(15,2)` — `inventory.avg_price`; `inventory_ledger.unit_cost`, `total_cost`, `avg_price_before`, `avg_price_after`; `machine_item_ledger.unit_cost`, `total_cost`, `value_before`, `value_after`, `avg_price_before`, `avg_price_after`. Postgres rounds a value with more decimals on write (half away from zero), so after a flush + refresh/expire every stored value has 2 decimals. Consequently, through `post_transfer_order_inventory` the carried unit cost always has ≤ 2 decimals and `total_cost` rounding cannot change anything. `total_cost` rounding in Python (`quantize(0.01)`) is only observable by calling `_post_location_in` directly with a 3-decimal `unit_cost`, e.g. `Decimal('0.125')`, `qty=1`, empty destination bucket: `total_cost` is stored `0.13` [BUG-1040] (R6a), and `unit_cost`, `avg_price_after` and the bucket's `avg_price` (all "unit_cost unchanged, not rounded" in Python) are stored `0.13` by Postgres, which rounds half away from zero. *(Today: `total_cost` is stored `0.12`, Python half to even, so the row disagrees with itself.)* Such a case is optional; 2-decimal inputs cover the reachable `total_cost` behavior. A weighted average can reach a midpoint with 2-decimal inputs (R5a).

**Callables:** 5 specified · 0 not specified
**Externals to mock:** `utcnow` (optional; used as the Python default for `machine_item_ledger.performed_at` and `machine_activity_events.created_at`). No other externals.
**Integration-only behavior:** the concurrency guarantee of the intended row locks (needs two sessions).

## Not specified
- `TO_INVENTORY_SOURCE_TYPE` — constant `'transfer_order'`; its value is asserted through the rules below.

---

## `_quantity_to_int(quantity, *, line_number)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `post_transfer_order_inventory`)

**Purpose:** Turn a line's decimal quantity into a whole number of units, rejecting quantities that cannot be moved.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `quantity` | `Decimal` | line quantity; must be a whole number > 0 |
| `line_number` | `int` | used only in error messages |

**Returns:** the quantity as `int` (e.g. `Decimal('5.00')` → `5`).

**Rules:**
- **R1.** A whole, positive quantity is returned as an `int`, regardless of trailing zero decimals (`5`, `5.0`, `5.00` → `5`; `1` → `1`).
- **R2.** A quantity with a non-zero fractional part (e.g. `2.5`, `0.01`, `10.99`) is rejected with 400 "Line {line_number} has a fractional quantity; inventory transfers require whole units".
- **R3.** A whole quantity of zero or below (`0`, `0.00`, `-3`) is rejected with 400 "Line {line_number} has no quantity to transfer".
- **R4.** A negative fractional quantity (e.g. `-2.5`) gets the fractional-quantity error of R2 (the fractional check comes first).
- **R5.** [BUG-824] `TransferOrderItemCreate`/`TransferOrderItemUpdate` reject a `quantity` that is not a whole number greater than 0 with 422 at entry (fix in `app/schemas/transfer_order.py`); R1–R4 remain a safety net that should be unreachable via the normal API. *(Today: any decimal — fractional, zero, or negative — is accepted at entry; rejected only here at completion — see Q3.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional part ≠ 0 | `HTTPException` 400 | `Line {n} has a fractional quantity; inventory transfers require whole units` (safety net once R5's entry-time rejection ships) |
| whole and ≤ 0 | `HTTPException` 400 | `Line {n} has no quantity to transfer` (safety net once R5's entry-time rejection ships) |

**Side effects:** none

---

## `_line_already_posted(session, workspace_id, line_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `post_transfer_order_inventory`)

**Purpose:** Idempotency guard — tell whether a transfer line has already produced any ledger row.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | `int` | only ledger rows of this workspace count |
| `line_id` | `int` | the `TransferOrderItem.id` (not the transfer order id) |

**Returns:** `bool`.

**Rules:**
- **R1.** Returns `True` when an `inventory_ledger` row exists with this workspace, `source_type = 'transfer_order'` and `source_id = line_id`.
- **R2.** Returns `True` when no such inventory ledger row exists but a `machine_item_ledger` row with the same three values exists.
- **R3.** Returns `False` when neither ledger has such a row.
- **R4.** Any matching row counts, whatever its `transaction_type` (a lone `transfer_out` or `transfer_in` row is enough).
- **R5.** Rows in another workspace, or with a different `source_type` (e.g. `'work_order'` or `'purchase_order'` with the same `source_id`), do not count.

**Errors:** none

**Side effects:** none

---

## `_post_location_out(session, *, location_type, location_id, item_id, qty, line, to, workspace_id, user_id, dest_type, dest_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_transfer_order_inventory`)

**Purpose:** Remove one line's quantity from the transfer order's source location and record it in the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `location_type` | `str` | must be exactly `storage`, `damaged` or `machine` (case-sensitive) |
| `location_id` | `int` | factory id (storage/damaged) or machine id (machine) |
| `item_id` | `int` | catalog item moved |
| `qty` | `int` | units to remove (caller guarantees > 0) |
| `line` / `to` | rows | `line.id`, `line.line_number`, `to.transfer_number` used for ledger/source fields and text |
| `workspace_id`, `user_id` | `int` | scope and actor |
| `dest_type`, `dest_id` | `str`, `int` | recorded on the ledger row as the transfer destination |

**Returns:** the unit cost (`Decimal`) at which the units left the source.

**Rules:**
- **R1.** A `location_type` other than exactly `storage`, `damaged` or `machine` (e.g. `project`, `Storage`, `""`) is rejected with 400 "Unsupported source location type: {location_type}"; nothing is written.
- **R1a.** [BUG-823] `TransferOrderCreate`/`TransferOrderUpdate` reject any `source_location_type` other than exactly `storage`, `damaged` or `machine` (e.g. `project`, `Storage`, `warehouse`, `""`) with 422 at entry (fix in `app/schemas/transfer_order.py`); on `TransferOrderUpdate` an omitted/None `source_location_type` stays allowed (field is optional) (best-practice default, delegated by reviewer). R1 remains a safety net that should be unreachable via the normal API. *(Today: any string is accepted at entry; unknown/differently-cased source types are only caught here at completion — see Q2.)*
- **R2.** `storage` reads the factory's STORAGE bucket for the item; `damaged` reads its DAMAGED bucket.
- **R3.** (storage/damaged) The factory must exist in this workspace; a missing id or a factory of another workspace → 404 "Factory with ID {location_id} not found", nothing written.
- **R3a.** [BUG-822] A soft-deleted factory is also rejected as not found (404 "Factory with ID {location_id} not found"), nothing written. *(Today: a soft-deleted factory is accepted as a valid source/destination — see Q1.)*
- **R4.** (storage/damaged) The bucket is made ready before the check: if no `inventory` row exists for (workspace, factory, item, type) one is created (qty 0, avg price null, `created_by = user_id`); a soft-deleted one is restored (`is_deleted = False`, `is_active = True`, `deleted_at`/`deleted_by` cleared); then its qty and avg price are set to the latest ledger entry of that bucket (`qty_after`, `avg_price_after`), or to 0 / null if the bucket has no ledger history. Available stock = that aligned qty.
- **R5.** (storage/damaged) If available < `qty` → 400 (exact message per R5b); nothing written. Available exactly equal to `qty` is allowed and leaves 0.
- **R5a.** [BUG-820] [HR-10] The bucket row is read with a row lock (`SELECT … FOR UPDATE`) before the availability check, so two concurrent postings cannot both take the same stock. *(Today: no lock.)*
- **R5b.** [BUG-826] The 400 detail names the line and item: "Line {line_number} ({item_name}): insufficient stock ({available} available, {qty} requested)"; `item_name` falls back to "Item #{item_id}" if the item is not found in this workspace, same fallback as R12's `label` (best-practice default, delegated by reviewer — the reviewer's example did not cover the not-found case). *(Today: "Insufficient stock ({available} available, {qty} requested)" — no line or item — see Q5.)*
- **R6.** (storage/damaged) On success one `inventory_ledger` row is written: `workspace_id`, `inventory_type` (STORAGE/DAMAGED), `factory_id`, `item_id`, `transaction_type = 'transfer_out'`, `quantity = qty`, `unit_cost` = bucket avg price or `0` if null, `total_cost = unit_cost × qty` rounded to 0.01, `qty_before` = available, `qty_after = available − qty`, `avg_price_before = avg_price_after` = bucket avg price (null stays null), `source_type = 'transfer_order'`, `source_id = line.id`, `transfer_destination_type = dest_type`, `transfer_destination_id = dest_id`, `transfer_source_type/id` null, `notes = "{transfer_number} line {line_number} transfer out"`, `performed_by = user_id`.
- **R7.** (storage/damaged) The bucket's qty becomes `available − qty`, its avg price is unchanged, `updated_by = user_id`. Returns the `unit_cost` of R6. No machine activity event is written.
- **R8.** (machine) The machine must exist in this workspace; missing / other workspace → 404 "Machine with ID {location_id} not found", nothing written.
- **R8a.** [BUG-822] A soft-deleted machine is also rejected as not found (404 "Machine with ID {location_id} not found"), nothing written. *(Today: a soft-deleted machine is accepted as a valid source/destination — see Q1.)*
- **R9.** (machine) The machine's stock row (`machine_items` for machine + item in the workspace) is created with qty 0 if missing. Available = its qty (not aligned to the ledger). If available < `qty` → 400 (exact message per R9a); exactly equal is allowed. (R5a's lock applies to this row too.)
- **R9a.** [BUG-826] The 400 detail names the line and item: "Line {line_number} ({item_name}): insufficient machine stock ({available} available, {qty} requested)"; `item_name` as R5b (best-practice default, delegated by reviewer). *(Today: "Insufficient machine stock ({available} available, {qty} requested)" — no line or item — see Q5.)*
- **R10.** (machine) Unit cost = `avg_price_after` of the latest `machine_item_ledger` row (by `performed_at`) for that machine + item in the workspace; `0` if there is none or it is null.
- **R11.** (machine) On success one `machine_item_ledger` row is written: `workspace_id`, `machine_id`, `item_id`, `transaction_type = 'transfer_out'`, `quantity = qty`, `unit_cost`, `total_cost = unit_cost × qty` rounded to 0.01, `qty_before`, `qty_after = qty_before − qty`, `value_before = qty_before × unit_cost`, `value_after = qty_after × unit_cost`, `avg_price_before = avg_price_after = unit_cost`, `source_type = 'transfer_order'`, `source_id = line.id`, `transfer_destination_type/id = dest_type/dest_id`, `notes = "{transfer_number} line {line_number} transfer out"`, `performed_by = user_id`. The machine stock qty becomes `qty_before − qty`. Returns the unit cost.
- **R12.** (machine) One machine activity event is written: `machine_id`, `workspace_id`, `event_type = 'transfer_out'`, `description = "Transfer out: {qty} units of {label} ({transfer_number})"`, `performed_by = user_id`, metadata `{"item_id": item_id, "item_name": label, "quantity": qty}` (no `work_order_id`). `label` = the item's name in this workspace, or `"Item #{item_id}"` if the item is not found in this workspace.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unsupported type | `HTTPException` 400 | `Unsupported source location type: {type}` (R1; safety net once R1a's entry-time rejection ships) |
| factory missing / other workspace / soft-deleted (R3a) | `HTTPException` 404 | `Factory with ID {id} not found` |
| factory stock short | `HTTPException` 400 | `Line {line_number} ({item_name}): insufficient stock ({available} available, {qty} requested)` (R5b) |
| machine missing / other workspace / soft-deleted (R8a) | `HTTPException` 404 | `Machine with ID {id} not found` |
| machine stock short | `HTTPException` 400 | `Line {line_number} ({item_name}): insufficient machine stock ({available} available, {qty} requested)` (R9a) |

**Side effects:** as R4, R6, R7, R9, R11, R12; all flushed, not committed. On the shortage errors, the bucket preparation of R4 / stock-row creation of R9 has already been flushed (the caller's rollback undoes it).

---

## `_post_location_in(session, *, location_type, location_id, item_id, qty, unit_cost, line, to, workspace_id, user_id, source_type, source_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** internal (used by: `post_transfer_order_inventory`)

**Purpose:** Add one line's quantity to the transfer order's destination at the source's unit cost and record it in the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `location_type` | `str` | exactly `storage`, `damaged` or `machine`; `project` has its own error |
| `location_id` | `int` | factory id or machine id |
| `qty` | `int` | units to add (> 0) |
| `unit_cost` | `Decimal` | cost per unit, as returned by `_post_location_out` |
| `source_type`, `source_id` | `str`, `int` | the order's source location, recorded on the ledger row |
| others | | as `_post_location_out` |

**Returns:** `None`.

**Rules:**
- **R1.** `location_type == 'project'` → 400 "Project destination inventory posting is not yet supported"; nothing written.
- **R1a.** [BUG-825] Creating or updating a transfer order with destination type `project` is rejected at entry with 400 "Project destination is not yet supported" (fix in `TransferOrderManager`/`TransferOrderService` create/update — a 400, not 422, so this is an application-level check rather than a schema validator); an order can no longer reach R1 via the normal API. *(Today: `project` can be chosen at creation and approved; completion always fails with R1's error, leaving the order stuck — see Q4.)*
- **R2.** Any other type not exactly `storage`, `damaged` or `machine` → 400 "Unsupported destination location type: {location_type}"; nothing written.
- **R2a.** [BUG-823] `TransferOrderCreate`/`TransferOrderUpdate` reject any `destination_location_type` other than `storage`, `damaged`, `machine` or `project` with 422 at entry (fix in `app/schemas/transfer_order.py`); R2 remains a safety net that should be unreachable via the normal API. *(Today: any string is accepted at entry; unknown/differently-cased types are only caught here at completion — see Q2.)*
- **R3.** `storage` → the factory's STORAGE bucket; `damaged` → its DAMAGED bucket.
- **R4.** (storage/damaged) Factory must exist in this workspace and not be soft-deleted, else 404 "Factory with ID {location_id} not found" — soft-delete handling per `_post_location_out` R3a [BUG-822]. The bucket is created / restored / aligned to its ledger exactly as `_post_location_out` R4.
- **R5.** (storage/damaged) New avg price: if the aligned qty > 0 and the aligned avg price is not null → `(old_qty × old_avg + qty × unit_cost) / (old_qty + qty)` rounded to 0.01 (an exact midpoint follows R5a); otherwise (empty bucket or no avg price) → `unit_cost` unchanged (not rounded).
- **R5a.** [BUG-1040] A weighted average at an exact midpoint rounds half away from zero (HR-15), as the database does: 1 @ 1.00 plus 1 @ 1.05 = 1.025 → `1.03`. The same holds for the machine average of R9. *(Today: half to even, Decimal default: `1.02`.)*
- **R6.** (storage/damaged) One `inventory_ledger` row: `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `transaction_type = 'transfer_in'`, `quantity = qty`, `unit_cost`, `total_cost = unit_cost × qty` rounded to 0.01, `qty_before = old_qty`, `qty_after = old_qty + qty`, `avg_price_before = old_avg` (may be null), `avg_price_after` = R5 value, `source_type = 'transfer_order'`, `source_id = line.id`, `transfer_source_type = source_type`, `transfer_source_id = source_id`, `transfer_destination_type/id` null, `notes = "{transfer_number} line {line_number} transfer in"`, `performed_by = user_id`. The bucket's qty becomes `old_qty + qty`, avg price = R5 value, `updated_by = user_id`. No machine activity event.
- **R6a.** [BUG-1040] `total_cost` (R6, and R10 on the machine side) at an exact midpoint rounds half away from zero (HR-15): `unit_cost` 0.125, `qty` 1 → `0.13`. *(Today: half to even, Decimal default: `0.12`.)*
- **R7.** A unit cost of `0` is accepted and is averaged in like any other cost (it lowers the destination's average).
- **R8.** (machine) Machine must exist in this workspace and not be soft-deleted, else 404 "Machine with ID {location_id} not found" — soft-delete handling per `_post_location_out` R8a [BUG-822]. The machine's stock row is created with qty 0 if missing.
- **R9.** (machine) `avg_before` = latest machine ledger `avg_price_after` for machine + item, or `0` when there is no ledger row **or** the latest row's `avg_price_after` is null (as `_post_location_out` R10). New avg: if the machine's current qty > 0 → weighted average as R5 using that `avg_before` (rounded to 0.01) — this includes the no-history and null-average cases, where `avg_before = 0` is averaged in (e.g. qty_before 3, null/absent ledger average, add 1 at 4.00 → `(3×0 + 1×4.00)/4 = 1.00`); if current qty is 0 → `unit_cost` (a leftover ledger average is ignored). There is no "no average → use unit_cost" fallback on the machine side while stock is on hand.
- **R10.** (machine) One `machine_item_ledger` row: `transaction_type = 'transfer_in'`, `quantity = qty`, `unit_cost`, `total_cost` rounded to 0.01, `qty_before`, `qty_after = qty_before + qty`, `value_before = qty_before × avg_before`, `value_after = qty_after × new avg`, `avg_price_before = avg_before`, `avg_price_after = new avg`, `source_type = 'transfer_order'`, `source_id = line.id`, `transfer_source_type/id = source_type/source_id`, `notes = "{transfer_number} line {line_number} transfer in"`, `performed_by = user_id`. Machine stock qty becomes `qty_before + qty`.
- **R11.** (machine) One machine activity event: `event_type = 'transfer_in'`, `description = "Transfer in: {qty} units of {label} ({transfer_number})"`, `performed_by = user_id`, metadata `{"item_id", "item_name": label, "quantity"}`; `label` as `_post_location_out` R12.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `project` | `HTTPException` 400 | `Project destination inventory posting is not yet supported` (R1; unreachable via the API once R1a's entry-time rejection ships) |
| other unsupported type | `HTTPException` 400 | `Unsupported destination location type: {type}` (R2; safety net once R2a's entry-time rejection ships) |
| factory missing / other workspace / soft-deleted (`_post_location_out` R3a) | `HTTPException` 404 | `Factory with ID {id} not found` |
| machine missing / other workspace / soft-deleted (`_post_location_out` R8a) | `HTTPException` 404 | `Machine with ID {id} not found` |

**Side effects:** as R4, R6, R8, R10, R11; flushed, not committed.

---

## `post_transfer_order_inventory(session, to, items, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `TransferOrderManager.mark_order_complete`)

**Purpose:** Move stock for every line of a transfer order from its source to its destination; returns how many lines were posted.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `to` | `TransferOrder` | source/destination type+id and `transfer_number` are used; its workspace is not checked against `workspace_id` |
| `items` | `list[TransferOrderItem]` | processed in the given order; not checked to belong to `to`; line approval / `transferred_at` are not checked |
| `workspace_id`, `user_id` | `int` | scope and actor for all writes |

**Returns:** `int` — number of lines posted in this call (skipped lines excluded). Writes flushed, not committed.

**Rules:**
- **R1.** Empty `items` → returns 0, nothing written.
- **R2.** A line that is already posted (`_line_already_posted` R1–R5) is skipped: nothing is written for it, its quantity is not validated, and it is not counted.
- **R3.** Every other line: its quantity is validated (`_quantity_to_int`), then the whole quantity is removed from the order's source (`_post_location_out`, with the order's destination recorded as `dest_type`/`dest_id`) and added to the order's destination at the unit cost the source returned (`_post_location_in`, with the order's source recorded). Result per posted line: exactly one `transfer_out` ledger row at the source and one `transfer_in` ledger row at the destination, both with `source_id = line.id`, and the destination's cost is the source's cost.
- **R3a.** [BUG-821] [HR-10] A line is posted at most once even when the same transfer order is completed twice concurrently (the caller locks the transfer order row with `SELECT … FOR UPDATE` before its completed/posted checks). *(Today: no lock and no database uniqueness on (source_type, source_id) — two concurrent completions both post every line.)*
- **R4.** The line's quantity is read as a decimal from its stored value (`Numeric(15,2)`, e.g. `5.00`) and must be a whole number > 0; otherwise the call raises the error of `_quantity_to_int` R2–R4 and nothing is written for that line. Intended entry-time validation: `_quantity_to_int` R5 [BUG-824].
- **R5.** Lines are processed one after another. When line k fails (quantity, unsupported type, 404, shortage), the error propagates immediately; lines before k stay written in the session (flushed, not committed) and lines after k are not processed. This function does not undo earlier lines — the caller's transaction rollback does.
- **R6.** If the destination side of a line fails (e.g. `project` destination, missing destination factory), the source deduction of that same line has already been flushed when the error is raised.
- **R7.** Returns the number of lines posted; e.g. 3 lines of which 1 was already posted → returns 2.
- **R8.** Stock is always moved between the order's own source and destination; `workspace_id` (the argument), not `to.workspace_id`, scopes every lookup and write.
- **R9.** Unit cost chain: storage→anything carries the source bucket's avg price (0 if none); machine→anything carries the machine's latest ledger average (0 if none).

**Errors:** those of `_quantity_to_int`, `_post_location_out`, `_post_location_in`, propagated unchanged.

**Side effects:** per posted line, as `_post_location_out` R4–R12 and `_post_location_in` R4–R11. No transfer-order events are written here — no row in `transfer_order_events` (model `TransferOrderEvent`); the caller logs them. No commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| to_inventory.py:21 | quantity has fractional part | `_quantity_to_int` R2, R4 |
| to_inventory.py:30 | qty ≤ 0 | `_quantity_to_int` R3 (else R1) |
| to_inventory.py:39 | inventory ledger row exists | `_line_already_posted` R1, R4, R5 |
| to_inventory.py:46-55 | machine ledger row exists / not | `_line_already_posted` R2, R3, R5 |
| to_inventory.py:72 | source type not in storage/damaged/machine | `_post_location_out` R1 (entry-time intent R1a) |
| to_inventory.py:112 | destination type == project | `_post_location_in` R1 |
| to_inventory.py:117 | destination type not in storage/damaged/machine | `_post_location_in` R2 |
| to_inventory.py:152 | loop over empty / one / many lines | `post_transfer_order_inventory` R1, R3, R5, R7 |
| to_inventory.py:153 | line already posted → continue | `post_transfer_order_inventory` R2, R7 |
| to_inventory.py:156 | quantity validation raises | `post_transfer_order_inventory` R4, R5 |
| to_inventory.py:170 | destination fails after source written | `post_transfer_order_inventory` R6 |
| inventory_movements.py:24 | item found in workspace / not | `_post_location_out` R12, `_post_location_in` R11 |
| inventory_movements.py:33 | add_qty ≤ 0 in weighted average | unreachable here (qty always > 0 after `_quantity_to_int`) |
| inventory_movements.py:35 | old qty > 0 and old avg not null | `_post_location_in` R5, R9 |
| inventory_movements.py:42 | damaged → DAMAGED else STORAGE | `_post_location_out` R2, `_post_location_in` R3 |
| inventory_movements.py:64 / 133 | factory not found | `_post_location_out` R3, `_post_location_in` R4 |
| inventory.py (dao):247 / 259 / 260 / try-except | bucket active / soft-deleted / missing / insert race | `_post_location_out` R4 (race path: integration-only) |
| inventory.py (dao) sync_snapshot: latest entry / none; values differ | aligned to ledger or to 0/null | `_post_location_out` R4 |
| inventory_movements.py:75 | storage stock < qty | `_post_location_out` R5 |
| inventory_movements.py:81 | avg price null → unit cost 0 | `_post_location_out` R6, `post_transfer_order_inventory` R9 |
| inventory_movements.py:182 | machine stock row exists / created | `_post_location_out` R9, `_post_location_in` R8 |
| inventory_movements.py:199 | latest machine ledger with avg / none | `_post_location_out` R10, `_post_location_in` R9 |
| inventory_movements.py:222 / 300 | machine not found | `_post_location_out` R8, `_post_location_in` R8 |
| inventory_movements.py:226 | machine stock < qty | `_post_location_out` R9 |
| inventory_movements.py:267 / 340 | source_type == work_order (metadata) | never here (always `transfer_order`) — `_post_location_out` R12, `_post_location_in` R11 |
| inventory_movements.py:274 / 347 | activity description given | always given here — R12 / R11 |
| inventory_movements.py:307 | machine qty_before > 0 → pass ledger avg, else None | `_post_location_in` R9 |
| inventory_movements.py:372 / 388 / 405 | post_stock_out dispatch | `_post_location_out` R2, R8 (else-raise unreachable: R1 guards first) |
| inventory_movements.py:431 / 449 / 468 | post_stock_in dispatch | `_post_location_in` R3, R8 (else-raise unreachable: R1/R2 guard first) |

## Gap log
- G1 (to_inventory.cases.md gap 1) — Fact — added the required/optional fields of `TransferOrderItemCreate/Update` and `TransferOrderCreate/Update` to Overview › Notes for the test designer.
- G2 (to_inventory.cases.md gap 2) — Fact + test mechanics — added the `Numeric(15,2)` scale of every price/cost column and how Python and Postgres rounding can be observed (direct `_post_location_in` call with a 3-decimal unit cost); such a case is optional (best-practice default, delegated by reviewer). Updated 2026-10-30: the owner ruled half away from zero (BUG-1040, HR-15), so the Python half-to-even result this entry recorded is now today's bug, not a fact to pin.
- G3 (to_inventory.cases.md gap 3) — Fact — rewrote `_post_location_in` R9: with machine qty > 0, a missing or null latest ledger average both give `avg_before = 0` and the weighted average is used (no fallback to `unit_cost`); example added.
- G4 (to_inventory.cases.md gap 4) — Contradiction (missing rule) — added `_post_location_out` R1a [BUG-823] for entry-time validation of `source_location_type` (existing bug, no new ID); omitted source type on update stays allowed (best-practice default, delegated by reviewer); Q2 rules-affected, Errors row and Branch map updated.
- G5 (to_inventory.cases.md gap 5) — Fact — named the transfer-order event table (`transfer_order_events`, `TransferOrderEvent`) in `post_transfer_order_inventory` Side effects.
