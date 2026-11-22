# Spec — `app/managers/po_return_inventory.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-10** `post_purchase_return_inventory` R3/R9 — the "already posted for this return line?" check and the stock deduction run without any row lock, and nothing in the database prevents a second ledger row for the same return line. Two concurrent completions of the same return both pass the check and both deduct stock (stock quantities = real harm). Intended: the completion path locks the row it decides on (the return, and/or the stock row being deducted) so the loser sees the already-posted/completed state; the fix most likely belongs in `PurchaseOrderService.complete_return` (lock the return row) and in `inventory_movements` (lock the stock row), not in this file.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-800. Intended behavior is already stated at `post_purchase_return_inventory` R17 ([HR-10]): the completion path must lock the row it decides on so a second, concurrent call sees the already-posted/completed state and deducts nothing. The fix lands in `PurchaseOrderService.complete_return` (lock the return row) and/or `inventory_movements` (lock the stock row), both out of scope of this spec; `_storage_ledger_exists`/`_machine_ledger_exists`/R3 stay correct as the single-caller idempotency check they already are. Rules: `post_purchase_return_inventory` R3, R9, R17.

### Precedent matches — resolved by best-practice default
- **Latest storage-ledger row chosen by timestamp only** (`post_purchase_return_inventory` R15a). **Background:** before each storage deduction the stock row is re-synced from the "latest" storage-ledger row for that factory/item, chosen by `performed_at` alone; storage-ledger rows written in the same database transaction all get the identical `performed_at` (transaction start time). Same root cause as BUG-664 (`inventory_movements`, `ambiguous-latest-row-tiebreak`). **Example:** a return has three lines, each for 3 units of Steel Bolt M8, stock 10. Lines 1 and 2 write rows 10→7 and 7→4 with the same timestamp; for line 3 the database may pick the 10→7 row as "latest", reset stock to 7 and write 7→4 — the user sees stock 4 although 9 units left.
**Answer:** bug — per BUG-664 precedent: "latest" = `performed_at` descending, then `id` descending, so the most recently inserted row wins on a tie (best-practice default, delegated by reviewer)
**Resolution:** 🐞 BUG-803 (fix lands with BUG-664 in `InventoryLedgerDAO.get_latest_entry` / `MachineItemLedgerDAO.get_latest_entry`, not in this file). Rules: `post_purchase_return_inventory` R15a.

### New questions

### Q1. Fractional return quantities are accepted when the return starts but block its completion — 🐞 BUG-801
**Background:** Return quantities are stored with 2 decimals (e.g. `1.50`). Starting a return only checks the quantity is > 0 and not more than is available to return. Stock (storage and machine) is tracked in whole units only; this module refuses a fractional quantity when the return is **completed**, for POs delivering to a factory storage or a machine.
**What happens today:** A return for 1.5 units is created (its credit-note invoice is confirmed immediately), but every attempt to complete it fails with 400 and nothing changes; the only way out is to void it.
**Example:** PO-0012 delivers to Factory A; line 1 received 10 units. The user starts a return of 1.5 units — accepted, credit note issued. Clicking "Complete return" always answers "Return line for PO item 57 has a fractional quantity; inventory requires whole units"; the return stays pending forever.
**Rules affected:** `_quantity_to_int` R2, `post_purchase_return_inventory` R6
**Suggested answer:** bug — for POs delivering to storage or a machine, reject a fractional quantity when the return is started (400, nothing created), so a return that was accepted can always be completed; keep this check as a safety net.
**Answer:** bug — for storage/machine POs, reject a fractional quantity when the return is started (400, nothing created); keep the completion check as a safety net (reviewer accepted suggestion)
**Resolution:** the fix belongs entirely in the return-start code path (e.g. `PurchaseOrderService`'s start/create-return method) — a different module, out of scope of this spec — which should reject a fractional `quantity_returned` with 400 (nothing created) up front for storage/machine-destination POs. `_quantity_to_int` R2 and `post_purchase_return_inventory` R6 **in this module** already do the intended thing (reject a fractional quantity at completion, as a safety net) and need no change — they are left untagged and no test here is expected to fail. BUG-801 is logged for cross-module tracking only; a future spec for the return-start module should carry the testable rule and its own xfail test (best-practice default, delegated by reviewer).

### Q2. The fractional-quantity error names the internal PO item id, not the line number — 🐞 BUG-802
**Background:** Users see PO lines by their line number (1, 2, 3…). Each line also has an internal database id. The equivalent receive-side error (`po_receive_inventory._delta_to_int`) says "Line 2 has a fractional quantity delta…", using `line_number`.
**What happens today:** The return error message contains the internal database id of the PO line.
**Example:** Line 2 of PO-0012 has database id 57. Completing a return of 1.5 units of line 2 shows "Return line for PO item 57 has a fractional quantity; inventory requires whole units" — the user cannot find "item 57" on the order.
**Rules affected:** `_quantity_to_int` R2
**Suggested answer:** bug — name the PO line number the user sees (e.g. "Return line for PO line 2 has a fractional quantity; inventory requires whole units"), matching the receive-side message.
**Answer:** bug — name the PO line number (e.g. 'Return line for PO line 2 has a fractional quantity; inventory requires whole units'), matching the receive-side message (reviewer accepted suggestion)
**Resolution:** `_quantity_to_int` takes the PO line's `line_number` (already available to the caller as `po_line.line_number`, already used in the ledger `notes` field at R8/R11) instead of `po_item_id`; the message becomes "Return line for PO line {line_number} has a fractional quantity; inventory requires whole units", matching `po_receive_inventory._delta_to_int`'s message shape. Rules: `_quantity_to_int` R2 (and its Inputs), `post_purchase_return_inventory` R6.

## Overview
Posts the stock-out side of a completed purchase-order return: for each returned PO line, the returned units leave the location the PO delivered to (a factory's storage bucket or a machine's on-hand stock), with one ledger row per return line. Called only by `PurchaseOrderService.complete_return`, which has already adjusted the PO lines' quantities and which commits or rolls back the whole transaction. Invariants: each return line is posted at most once (idempotent re-runs), stock never goes negative, and only whole units move.

**Callables:** 5 specified · 0 not specified
**Externals to mock:** none (no Cloudinary/SSLCommerz/notifications/email; `utcnow` only matters for the machine ledger's `performed_at` default)
**Integration-only behavior:** none

**Notes for the test designer:**
- All functions are module-level; call them directly with a real session. `po`, the return items and PO lines can be real persisted rows (preferred), since the idempotency checks read ledger rows by the return item's `id`.
- The module constant `PO_RETURN_ITEM_SOURCE = 'purchase_return_item'` is the `source_type` written on (and searched in) both ledgers.
- The function never commits and never rolls back: every write is flushed only. When it raises part-way through, rows written for earlier lines are still in the session (the caller rolls back).
- Stock mechanics (ledger fields, unit cost, snapshot sync) belong to `app/managers/inventory_movements.py::post_stock_out`; the rules below state only the outcomes this module relies on.
- **Storage stock is ledger-driven (see R8a).** A storage stock row alone is NOT enough: before every storage deduction its `qty`/`avg_price` are overwritten from the latest storage-ledger row of the same workspace/factory/item/`storage` type (no ledger row → qty 0, avg null). Every storage-stock setup must seed a ledger history whose latest row's `qty_after`/`avg_price_after` equal the intended starting stock/average (the G1 seeding convention is correct and required).
- **`performed_at` on seeded ledger rows (G2).** `inventory_ledger.performed_at` has `server_default now()`, which in Postgres is the *transaction start time* — every storage-ledger row inserted in one test (seed rows and the rows this function writes) gets the identical value unless set explicitly. Seed storage-ledger rows with an explicit `performed_at` strictly in the past (earlier seeds earlier). Rows written by the function then carry the test's transaction time and are the latest for their bucket; with two or more of them in one call, see R15a. `machine_item_ledger.performed_at` defaults to Python `utcnow()` at insert (not mocked), so rows written by the function are later than any past-dated seed; seed ML rows with explicit past, strictly increasing `performed_at`.
- **Idempotency is single-session only (G6).** R17 (concurrent completions) cannot be shown by a one-session unit test of this function, and patching the ledger-exists helpers to `False` would still deduct after the intended fix. R17 is tested with `PurchaseOrderService.complete_return` (where the lock belongs), not here (best-practice default, delegated by reviewer); R3 covers the single-caller re-run.
- **Return items with quantity ≤ 0 persist (G4).** `purchase_order_return_items.quantity_returned` is `Numeric(15,2) NOT NULL` with no check constraint (neither in the model nor in migration 120); rows with `0`, `-2` or `1.5` can be inserted directly.

## Not specified
- (none)

---

## `_machine_ledger_exists(session, *, workspace_id, source_type, source_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `post_purchase_return_inventory`)

**Purpose:** Tell whether a machine stock-ledger row already exists for a given source.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open DB session |
| workspace_id | int | workspace the row must belong to |
| source_type | str | exact, case-sensitive match |
| source_id | int | exact match |

**Returns:** `True` if at least one `machine_item_ledger` row matches all three; else `False`.

**Rules:**
- **R1.** Given a machine ledger row with the same workspace, `source_type` and `source_id`, returns `True` (any machine, any item).
- **R2.** Given no such row, returns `False`.
- **R3.** A matching row in another workspace does not count (`False`).
- **R4.** A row with the same `source_id` but a different `source_type` (e.g. `po_receive_event_item`) does not count.
- **R5.** Storage (factory) ledger rows are not considered.

**Errors:** none
**Side effects:** none

---

## `_storage_ledger_exists(session, *, workspace_id, source_type, source_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `post_purchase_return_inventory`)

**Purpose:** Tell whether a factory (storage/damaged) stock-ledger row already exists for a given source.

**Inputs:** same as `_machine_ledger_exists`.

**Returns:** `True` if at least one `inventory_ledger` row matches workspace, `source_type` and `source_id`; else `False`.

**Rules:**
- **R1.** Given an inventory-ledger row with the same workspace, `source_type` and `source_id`, returns `True` — regardless of factory, item or inventory type (storage or damaged).
- **R2.** Given no such row, returns `False`.
- **R3.** A matching row in another workspace does not count.
- **R4.** A different `source_type` with the same `source_id` does not count.
- **R5.** Machine ledger rows are not considered.

**Errors:** none
**Side effects:** none

---

## `_location_for_po(po)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `post_purchase_return_inventory`)

**Purpose:** Map a PO's delivery destination to the stock location returns are taken from.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| po | PurchaseOrder | only `destination_type` and `destination_id` are read |

**Returns:** `(location_type, location_id)` or `None`.

**Rules:**
- **R1.** `destination_type == 'storage'` → `('storage', po.destination_id)` (the id is a factory id).
- **R2.** `destination_type == 'machine'` → `('machine', po.destination_id)`.
- **R3.** Any other value — `'project'`, `'damaged'`, a different case such as `'Storage'`, empty string — → `None`.

**Errors:** none
**Side effects:** none

---

## `_quantity_to_int(quantity, *, po_item_id)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `post_purchase_return_inventory`)

**Purpose:** Convert a returned quantity to whole stock units, refusing fractions.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| quantity | Decimal | any sign; must be a whole number |
| po_item_id | int | [BUG-802] used only in the error message. *(Today. Intended: parameter renamed `line_number`, passed as `po_line.line_number` — the PO line number the user sees, not its internal database id.)* |

**Returns:** `int(quantity)`.

**Rules:**
- **R1.** A whole-number value is returned as an int, whatever its scale: `Decimal('3')`, `Decimal('3.00')` → `3`; `Decimal('0')` → `0`; `Decimal('-2.00')` → `-2` (no sign check here).
- **R2.** [BUG-802] A value with a non-zero fractional part (`1.5`, `0.01`, `-0.5`) raises 400 naming the PO **line number** the user sees (see Errors). *(Today: names the PO item's internal database id instead.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional quantity [BUG-802] | `HTTPException` 400 | `Return line for PO line {line_number} has a fractional quantity; inventory requires whole units` *(Today: `Return line for PO item {po_item_id} has a fractional quantity; inventory requires whole units`, naming the internal PO-item id.)* |

**Side effects:** none

---

## `post_purchase_return_inventory(session, po, return_item_pairs, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (caller: `PurchaseOrderService.complete_return`)

**Purpose:** Take the returned units of each return line out of the PO's delivery location, once per return line.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open DB session |
| po | PurchaseOrder | its `destination_type`/`destination_id` decide the location; `po_number` used in notes. Not checked against `workspace_id` here. |
| return_item_pairs | sequence of `(PurchaseOrderReturnItem, PurchaseOrderItem)` | processed in the given order; may be empty. The item moved is the PO line's `item_id` (the return item's own `item_id` is ignored). Pairing/workspace of the rows is not checked here. |
| workspace_id | int | scopes the idempotency check, location lookup and all rows written |
| user_id | int | recorded as `performed_by` / `updated_by` |

**Returns:** the number of return lines for which a stock-out was posted in this call (int, ≥ 0). Writes are flushed, not committed.

**Rules:**
- **R1.** If the PO's destination is neither storage nor a machine (per `_location_for_po` R3, e.g. a project), returns `0` and writes nothing — even for fractional quantities or already-posted lines.
- **R2.** An empty `return_item_pairs` returns `0` and writes nothing.
- **R3.** A return line that already has a ledger row with `source_type = 'purchase_return_item'` and `source_id = <return item id>` in this workspace — in **either** the storage ledger or the machine ledger, regardless of the PO's current destination — is skipped: no new row, no stock change, not counted. Calling the function twice with the same pairs therefore posts once and the second call returns `0`.
- **R4.** The already-posted check (R3) happens before the quantity checks: an already-posted line with a fractional quantity is skipped without error.
- **R5.** A ledger row for the same return item id in another workspace, or with another `source_type`, does not make the line count as posted.
- **R6.** A not-yet-posted line whose `quantity_returned` has a fractional part raises 400 per `_quantity_to_int` R2 [BUG-802: the message names the PO line's `line_number`; *(Today: names the PO line's internal id)*]. Lines processed before it keep their flushed writes; lines after it are not processed. *(Q1/BUG-801: this check is intended to stay as a safety net — the primary fix, rejecting a fractional quantity when the return starts, belongs in a different module.)*
- **R7.** A not-yet-posted line whose whole quantity is `0` or negative is skipped: nothing written, not counted. *(Not reachable from the API: the return schema requires `quantity_returned > 0`.)*
- **R8.** Storage destination: for each remaining line, the factory's **storage** (not damaged) stock of the PO line's item decreases by the quantity; one inventory-ledger row is written with `transaction_type = 'purchase_return'`, `source_type = 'purchase_return_item'`, `source_id = <return item id>`, `quantity = <qty>`, `qty_before`/`qty_after` = stock before/after, `unit_cost` = the stock's current average price (0 if none), `total_cost = unit_cost × qty` rounded to 2 decimals, `avg_price_before = avg_price_after` = current average (unchanged by a stock-out; **null** when the stock has no average price, while `unit_cost` is `0` and `total_cost` `0.00`), no transfer destination, `performed_by = user_id`, `notes = "PO {po_number} return {return_id} (line {line_number})"`. The stock row gets `updated_by = user_id`. No machine activity event is written.
- **R8a.** Storage destination: "current stock" and "current average price" in R8/R9 are the values **after** a re-sync from the storage ledger. The latest `inventory_ledger` row for (this workspace, the factory, the PO line's item, inventory type `storage`) — latest by `performed_at` descending (ties: see R15a) — supplies the quantity (`qty_after`) and average price (`avg_price_after`). No such ledger row → quantity 0 and no average price, whatever the stock row held. If the stock row differed from the ledger it is overwritten (and flushed) even when the line then fails with insufficient stock. Damaged-type ledger rows and rows of other factories/items/workspaces are not considered. Example: stock row qty 10 @ 12.50 with no ledger rows → 400 `Insufficient stock (0 available, 3 requested)`, and the stock row now reads qty 0, avg null.
- **R8b.** Cost-field precision: all price/cost/value columns (`inventory.avg_price`, both ledgers' `unit_cost`, `total_cost`, `avg_price_before/after`, machine `value_before/after`) are `Numeric(15,2)`. Because the average price is read from a 2-decimal column, `unit_cost × qty` is already exact at 2 decimals — the `total_cost` rounding step is never observable through this function (a 3-decimal average cannot be seeded; Postgres rounds it on insert).
- **R9.** Storage destination, insufficient stock: if the factory's storage stock of the item is less than the quantity (including no stock row yet → treated as 0), raises 400 `Insufficient stock ({available} available, {qty} requested)`; nothing is written for that line. Exactly equal stock is allowed and leaves 0.
- **R10.** Storage destination, factory not found in this workspace (missing id or another workspace's factory) → 404 `Factory with ID {id} not found`. A soft-deleted factory is still found and stock is deducted from it.
- **R11.** Machine destination: the machine's on-hand quantity of the PO line's item decreases by the quantity; one machine-ledger row is written with the same `transaction_type`, `source_type`, `source_id`, `quantity`, `notes`, `performed_by` as R8; `unit_cost` = `avg_price_after` of the machine/item's most recent machine-ledger entry in this workspace — most recent = highest `performed_at` (no tie-breaker; seed distinct timestamps) — (0 if none or null); `value_before`/`value_after` = qty before/after × unit cost; `avg_price_before = avg_price_after = unit_cost`.
- **R12.** Machine destination also writes one machine activity event: `event_type = 'purchase_returned'`, `description = "Purchase returned: {qty} units of {item name} to supplier"`, `performed_by = user_id`, metadata, stored in the event's `metadata_json` attribute (DB column `metadata`, type JSON), equal to exactly `{"item_id": <PO line's item id, int>, "item_name": <str, same name as in the description>, "quantity": <int>}` (plain JSON ints; no `work_order_id` key). The item name is the catalog item's name in this workspace, or `Item #{item_id}` if the item is not found in this workspace.
- **R13.** Machine destination, insufficient stock: if the machine holds less than the quantity (no placement yet → a placement with qty 0 is created first, then the check fails), raises 400 `Insufficient machine stock ({available} available, {qty} requested)`; no ledger row or event for that line (a newly created zero placement stays flushed).
- **R14.** Machine destination, machine not found in this workspace → 404 `Machine with ID {id} not found`. A soft-deleted machine is still found and stock is deducted.
- **R15.** Several lines for the same item are posted as separate ledger rows, each deducting from the stock left by the previous one (`qty_before` of the second = `qty_after` of the first).
- **R15a.** [BUG-803] With three or more lines for the same item in one call (storage destination), each line deducts from the stock left by the immediately preceding line: e.g. stock 10, three lines of 3 → rows 10→7, 7→4, 4→1, final stock 1. *(Today: the rows written earlier in the same call share one `performed_at` and "latest" is chosen by `performed_at` alone, so line 3 may re-sync from the 10→7 row and write 7→4, leaving stock 4; the outcome is nondeterministic. Fix belongs in `InventoryLedgerDAO.get_latest_entry`: tie-break by `id` descending, per BUG-664.)* Two lines for the same item (R15) are unaffected when seeded rows have an explicit past `performed_at`. Test note: because today's outcome depends on which tied row Postgres returns, a test for this rule may pass by chance before the fix; mark it `xfail(strict=False, reason="BUG-803")` rather than strict (best-practice default, delegated by reviewer).
- **R16.** The return value counts only lines posted in this call (R8/R11), not skipped ones (R3, R7).
- **R17.** [HR-10, BUG-800] Two concurrent calls for the same return must not both post: the loser sees the lines as already posted (or the return as completed) and deducts nothing. *(Today: no lock and no unique constraint on the ledger source; both calls deduct.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional quantity (not yet posted, location is storage/machine) [BUG-802] | `HTTPException` 400 | `Return line for PO line {po_line.line_number} has a fractional quantity; inventory requires whole units` *(Today: `Return line for PO item {po_line.id} has a fractional quantity; inventory requires whole units`.)* |
| storage stock below quantity | `HTTPException` 400 | `Insufficient stock ({available} available, {qty} requested)` |
| machine stock below quantity | `HTTPException` 400 | `Insufficient machine stock ({available} available, {qty} requested)` |
| factory not in workspace | `HTTPException` 404 | `Factory with ID {id} not found` |
| machine not in workspace | `HTTPException` 404 | `Machine with ID {id} not found` |

**Side effects:** per posted line, one ledger row (storage or machine) and a stock decrease; for machines also one activity event. Before the stock check, the storage stock row is re-synced from the storage ledger (R8a; `updated_by = user_id` is written on a re-sync that changes something), a missing storage stock row / machine placement is created (qty 0, avg null), or a soft-deleted stock row is restored and then re-synced (see `inventory_movements`). Everything is flushed; no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–28 | machine ledger row found / not found (workspace, source_type, source_id) | `_machine_ledger_exists` R1–R5 |
| 32–34 | storage ledger row found / not found | `_storage_ledger_exists` R1–R5 |
| 38 | destination `'storage'` | `_location_for_po` R1 |
| 40 | destination `'machine'` | `_location_for_po` R2 |
| 42 | any other destination | `_location_for_po` R3 |
| 46 | fractional vs whole | `_quantity_to_int` R1, R2 |
| 63–64 | location is None → return 0 | `post_purchase_return_inventory` R1 |
| 68 | loop: empty / one / many pairs | R2, R8, R15 |
| 69–74 | already posted in storage ledger OR machine ledger → skip | R3, R4, R5 |
| 76 | fractional → raise | R6 |
| 77–78 | qty ≤ 0 → skip | R7 |
| 92 | machine → `activity_event_type = 'purchase_returned'`; storage → none | R11, R12, R8 |
| 93–97 | machine → custom description with item name; storage → none | R12 |
| 99 | counter increment | R16 |
| inventory_movements 372 / 388 | storage vs machine branch of stock-out | R8, R11 |
| inventory_movements 64 / 222 | factory / machine not found | R10, R14 |
| inventory_movements 75 / 226 | insufficient stock (`<`, equal allowed) | R9, R13 |
| inventory_movements 81 | avg price None → unit cost 0 | R8 |
| inventory_movements 199 | no latest machine ledger / null avg → unit cost 0 | R11 |
| inventory_movements 182 | machine placement exists / created | R13 |
| inventory_movements 24 | item found / fallback name | R12 |
| inventory_movements 267 | `source_type == 'work_order'` metadata (never true here) | R12 |
| inventory_movements 274 | `activity_description or …` (always provided here) | R12 |
| inventory dao 247–263 | stock row active / soft-deleted (restored) / missing (created) | R9, Side effects |
| inventory dao 213–218 | latest storage-ledger row exists / none (→ 0, null) | R8a |
| inventory dao 220 | snapshot differs from ledger → overwrite | R8a, Side effects |
| inventory_ledger dao 173 / machine_item_ledger dao 223 | "latest" by `performed_at` desc only, no tie-break | R8a, R11, R15a |
| — | no lock around check-then-deduct | R17 |

## Gap log
- G1 (po_return_inventory.cases.md gap G1) — Fact — added R8a (storage stock/avg are re-synced from the latest storage-ledger row before every deduction; no ledger → 0/null, stock row overwritten); Side effects clarified; Notes for the test designer: a stock row alone is not enough, the G1 seeding convention is required.
- G2 (po_return_inventory.cases.md gap G2) — Fact + Test mechanics — "most recent" is `performed_at` descending only in both ledgers (R8a, R11); Notes explain storage `performed_at` = transaction start (`now()`) and machine = Python `utcnow()`, so seeds need explicit past timestamps. The tie this exposes is logged as BUG-803 / R15a (precedent BUG-664, best-practice default, delegated by reviewer).
- G3 (po_return_inventory.cases.md gap G3) — Fact — R12: metadata attribute `metadata_json` (JSON column `metadata`), exact dict with int `item_id`, str `item_name`, int `quantity`.
- G4 (po_return_inventory.cases.md gap G4) — Fact — Notes: `quantity_returned` is `Numeric(15,2) NOT NULL` with no check constraint; 0/negative/fractional rows persist.
- G5 (po_return_inventory.cases.md gap G5) — Fact — R8b: every cost column is `Numeric(15,2)`, so `total_cost` rounding is unobservable (PRI-P-04 as designed cannot be seeded); R8: with no average price, `avg_price_before/after` are null and `unit_cost` 0.
- G6 (po_return_inventory.cases.md gap G6) — Test mechanics — Notes: R17 is not unit-testable here; tested with `PurchaseOrderService.complete_return` (deferral confirmed, best-practice default, delegated by reviewer).
