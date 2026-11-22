# Spec — `app/managers/po_receive_inventory.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Precedent matches — confirm all with ok

### P1. "Already posted / already reversed" is only checked in Python — 🐞 BUG-680
**Background:** Each receive line may move stock exactly once, and each posting
may be reversed exactly once. The module guarantees this by first looking for an
existing ledger row with the same source (e.g. `po_receive_event_item` + event
item id) and skipping if one exists. Neither ledger table has a unique
constraint on `(workspace_id, source_type, source_id)`, and the void flow reads
the purchase order without a row lock (HR-10 covers stock quantities).
**What happens today:** Two transactions running at the same time (e.g. the PO
is voided twice from two browser tabs) both see "no reversal yet" and both write
a reversal.
**Example:** PO-2026-004 received 10 bolts into Factory A. Two users press "Void"
at the same moment; both requests pass the "already voided?" and "already
reversed?" checks, and Factory A loses 20 bolts instead of 10.
**Rules affected:** `_post_event_item_delta` R1, `_reverse_event_item_posting` R1,
`_reverse_legacy_line_posting` R1, `_ledger_exists` R1
**Answer:** bug — per BUG-003 precedent: one ledger row per PO source is enforced by the database too (partial unique index on `(workspace_id, source_type, source_id)` for the `po_receive_event_item`, `po_receive_event_item_reversal` and `purchase_order_reversal` source types, in both ledgers); a concurrent duplicate surfaces as 409, never a second stock movement (precedent — confirmed: ok)
**Resolution:** one ledger row per PO source is now also a database guarantee. Rules: `_post_event_item_delta` R1a, `_reverse_event_item_posting` R1a, `_reverse_legacy_line_posting` R1a. `_ledger_exists` itself is unchanged (its own read behavior, R1–R4, was never the bug); it remains the pre-check the callers use before the insert that the new index also protects.

### P2. PO destination type is free text; any other spelling silently skips inventory — 🐞 BUG-681
**Background:** A purchase order's `destination_type` is a plain string in the
create/update schemas — nothing restricts it to `storage` / `machine` /
`project`, and nothing normalises case or whitespace. The PO display code
lower-cases it (so "Storage" is shown as a factory), but this module compares it
exactly.
**What happens today:** A PO whose destination type is `"Storage"`, `"storage "`
or `"factory"` is received without any stock movement and without an error;
the receive quantities are recorded on the PO, but no inventory changes.
**Example:** A PO created with `destination_type: "Storage"`, destination
Factory A, receives 50 units. The PO shows 50 received; Factory A's stock stays
at 0, and no "inventory posted" event is logged.
**Rules affected:** `_location_for_po` R3, `_post_event_item_delta` R2
**Answer:** bug — per BUG-022 precedent: `destination_type` trimmed and lower-cased in the PO schemas; only `storage`, `machine`, `project` accepted, anything else 422 (fix in `app/schemas/purchase_order.py`); existing bad rows need a data clean-up (precedent — confirmed: ok)
**Resolution:** fix lives upstream in `app/schemas/purchase_order.py`, not in this module. This module's own comparison (`_location_for_po` R3) is unchanged and stays exact; what changes is which values can reach it. Rules: `_location_for_po` R3 (note added), `_post_event_item_delta` R2 (note added).

### New questions

### Q1. Voiding a PO after a purchase return removes the returned units a second time — 🐞 BUG-682
**Background:** Receiving adds stock (one ledger row per receive line). A
purchase return (goods sent back to the supplier) removes stock separately,
under its own source (`purchase_return_item`). Voiding a PO reverses every
receive line in full; it does not look at returns, and the returns themselves
are not reversed. Voiding is allowed while completed returns exist.
**What happens today:** The void takes out the full received quantity again,
even though part of it already left through the return — so the returned units
are deducted twice.
**Example:** PO-2026-010 receives 10 units into Factory A (stock 10), then 3 are
returned to the supplier (stock 7). The user voids the PO: the void tries to
remove 10. If Factory A has only those 7, the void fails with 400 "Insufficient
stock (7 available, 10 requested)"; if Factory A has 20 other units of the same
item, the void succeeds and Factory A ends at 17 instead of 20.
**Rules affected:** `reverse_po_receive_inventory` R7, `_reverse_event_item_posting` R6
**Suggested answer:** bug — voiding nets out returns: the stock removed by the void equals received minus already-returned quantity per line (equivalently, completed returns on the PO are reversed as part of the void), so the location ends where it was before the PO
**Answer:** bug — the void nets out returns: stock removed equals received minus already-returned per line (or completed returns are reversed as part of the void), leaving the location as before the PO (reviewer accepted suggestion)
**Resolution:** the void nets out completed purchase returns per PO line. Rules: `reverse_po_receive_inventory` R7, `_reverse_event_item_posting` R6a (new). Bookkeeping mechanism (how the netting is distributed across a PO line's several receive-line reversals) is not specified by the reviewer's answer: decided by best practice — `reverse_po_receive_inventory` tracks, per PO line, the returned-but-not-yet-netted quantity (sum of `quantity_returned` on completed `PurchaseOrderReturnItem` rows for that `po_item_id`) and consumes it against that line's receive-line reversals newest-event-first (best-practice default, delegated by reviewer).

### Q2. A PO whose received stock was already used cannot be voided — ✅ intended
**Background:** Voiding reverses each receive by taking the units back out of
the factory storage bucket or machine. Stock can never go below zero; a
stock-out larger than what is on hand is refused.
**What happens today:** If some of the received units were consumed or
transferred away since, the whole void fails with the generic stock error and
nothing is voided.
**Example:** PO-2026-012 received 10 filters into Machine M1; 8 were consumed by
work orders. Voiding the PO answers 400 "Insufficient machine stock (2
available, 10 requested)" and the PO stays un-voided.
**Rules affected:** `_reverse_event_item_posting` R8 ✅, `_reverse_legacy_line_posting` R7 ✅
**Suggested answer:** intended
**Answer:** intended (reviewer accepted suggestion)

### Q3. Reversal happens at the PO's current destination, not where the stock went — 🐞 BUG-683
**Background:** A PO has one destination (a factory's storage or a machine).
The destination is locked once the PO's invoice is confirmed, but it can become
editable again if the invoice is later unlinked from the PO. The original stock
movement records exactly where the stock went (factory id or machine id).
**What happens today:** On void, the module reads the PO's destination at void
time and reverses there, with the quantity taken from the receive line (or the
legacy ledger row). It only checks that *some* original posting exists in
either ledger, not that it was at the same place.
**Example:** PO-2026-020 received 5 units into Factory A. The destination is
later changed to Factory B. Voiding the PO removes 5 units from Factory B
(or fails with "Insufficient stock" there), while Factory A keeps the 5 units.
**Rules affected:** `_reverse_event_item_posting` R9, `_reverse_legacy_line_posting` R8
**Suggested answer:** bug — each reversal is made at the location recorded on the original ledger row (factory + inventory type, or machine), whatever the PO's destination is at void time
**Answer:** bug — each reversal is made at the location recorded on the original ledger row, whatever the PO's destination is at void time (reviewer accepted suggestion)
**Resolution:** reversals use the location recorded on the original posting, not the PO's current destination. Rules: `_reverse_event_item_posting` R9, `_reverse_legacy_line_posting` R8.

### Q4. Receiving can post stock into a deleted factory or machine — 🐞 BUG-684
**Background:** Factories and machines are soft-deleted (`is_deleted = True`, the
row stays). When stock is posted, the destination is looked up by id within
the workspace only; the deleted flag is not checked. A PO's destination is not
re-checked after the PO was created.
**What happens today:** Receiving against a PO whose destination factory or
machine was deleted succeeds and adds stock to the deleted location, where no
list shows it.
**Example:** PO-2026-030 targets Machine M7; M7 is deleted before the goods
arrive. The user receives 12 units: the request succeeds, M7 (deleted) now holds
12 units, and the stock is invisible in machine inventory screens.
**Rules affected:** `_post_event_item_delta` R12
**Suggested answer:** bug — receiving (not void reversals) into a soft-deleted factory or machine is rejected with 400 before anything is written
**Answer:** bug — receiving (not void reversals) into a soft-deleted factory or machine is rejected with 400 before anything is written (reviewer accepted suggestion)
**Resolution:** `_post_event_item_delta` rejects a soft-deleted destination with 400 before writing anything; void reversals (`_reverse_event_item_posting`, `_reverse_legacy_line_posting`) are unaffected — they must still be able to reverse stock at a since-deleted location. Rules: `_post_event_item_delta` R12a (new). Error message not specified by the reviewer's answer: decided by best practice — reuses the existing not-found wording as a 400, `"Factory with ID {id} has been deleted"` / `"Machine with ID {id} has been deleted"` (best-practice default, delegated by reviewer).

## Overview
Moves stock for purchase-order receiving. `post_receive_event_inventory` is
called by `PurchaseOrderService.create_receive_event` after a receive batch or
quantity correction is recorded: each receive line's quantity delta is added to
(positive) or removed from (negative) the PO's destination — a factory's
STORAGE bucket or a machine's on-hand stock — as one ledger row keyed by the
receive line. `reverse_po_receive_inventory` is called by
`PurchaseOrderService.void_purchase_order` and undoes every such posting, plus
postings made by the old "mark complete" flow (legacy ledger rows keyed by PO
line id, source `purchase_order`). Invariants it protects: stock moves in whole
units only; each receive line posts at most once and is reversed at most once;
projects (and any other destination) never touch inventory.

**Callables:** 10 specified · 0 not specified
**Externals to mock:** none (all stock mechanics run for real through
`app/managers/inventory_movements.py` against the test DB)
**Integration-only behavior:** none

**Notes for the test designer:**
- Nothing here commits. Every write is flushed into the caller's session.
- Stock movement is done by `inventory_movements.post_stock_in` /
  `post_stock_out`. Rules below state the observable outcome (ledger row
  fields, stock row quantity/average, machine activity event); the exact
  weighted-average formula is: new avg = (old qty × old avg + qty × unit cost) /
  (old qty + qty), rounded to 0.01; when the old quantity is 0 or the old average
  is unknown, new avg = unit cost.
- Storage stock lives in `inventories` (one row per factory/item/type,
  `inventory_type = STORAGE`); before each movement that row is created if
  missing (qty 0, avg `NULL`), restored if soft-deleted, and its qty/avg reset to
  the latest `inventory_ledger` row for that factory/item/type (ledger wins).
  Machine stock lives in `machine_items` (created with qty 0 if missing); the
  machine's current unit cost is `avg_price_after` of the latest
  `machine_item_ledger` row for that machine/item (by `performed_at`), else 0.
- To set up "legacy" postings, insert ledger rows directly with
  `source_type = 'purchase_order'` and `source_id = <PO line id>`.
- A *completed* purchase return (BUG-682) is set up as a `PurchaseOrderReturnItem`
  row (`po_item_id` = the PO line, `quantity_returned` a whole number) plus a
  matching stock-out ledger row with `source_type = 'purchase_return_item'` and
  `source_id = <return item id>` in the same workspace and the same ledger as the
  original receive posting (this is exactly what `po_return_inventory` writes
  when a return is completed). The parent `PurchaseOrderReturn.status` is not
  consulted (best-practice default, delegated by reviewer).
- BUG-680 (R1a rules): at this layer the losing duplicate insert surfaces as
  `sqlalchemy.exc.IntegrityError` (unique violation, pgcode 23505); this module
  does not catch it. Translating it to 409 is the global integrity-error handler's
  job (BUG-462), tested there (best-practice default, delegated by reviewer). A
  race is simulated in one session by patching the relevant "already
  posted/reversed" existence check to answer `False` for that source type only.
- Stock quantities (`inventories.qty`, `machine_items.qty`) are `Integer`
  columns and the requested quantity is an `int`, so `{available}` / `{qty}` in
  the "Insufficient ..." messages are always rendered as plain integers (`7`,
  never `7.00`).
- `po` / `po_lines` / `event_items` are plain ORM objects; the module does not
  check that the lines belong to the PO or that the PO is not voided (callers do).

## Not specified
- (none)

---

## `_delta_to_int(delta, *, line_number)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `_post_event_item_delta`, `_reverse_event_item_posting`)

**Purpose:** Turn a receive line's quantity delta into a whole number of units to move.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `delta` | `Decimal` | signed quantity change; any value accepted |
| `line_number` | `int` | PO line number, only used in the error message |

**Returns:** `int` ≥ 0 — the absolute value of the delta.

**Rules:**
- **R1.** A whole positive delta returns that number (`Decimal('5')` → 5, `Decimal('5.0000')` → 5).
- **R2.** A whole negative delta returns its absolute value (`Decimal('-3')` → 3).
- **R3.** A zero delta (`0`, `-0`, `0.0000`) returns 0 (no error).
- **R4.** A delta with a fractional part (`2.5`, `-0.5`, `1.0001`) raises 400 with the line number in the message.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional delta | `HTTPException` 400 | `Line {line_number} has a fractional quantity delta; inventory requires whole units` |

**Side effects:** none

---

## `_ledger_exists(session, *, workspace_id, source_type, source_id, model)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_machine_ledger_exists`)

**Purpose:** Tell whether a ledger table already has a row for a given source.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | `int` | workspace scope |
| `source_type` | `str` | compared exactly (case-sensitive) |
| `source_id` | `int` | compared exactly |
| `model` | ORM class | any model with `id`, `workspace_id`, `source_type`, `source_id` columns (used with `MachineItemLedger`) |

**Returns:** `True` if at least one row of `model` has this workspace, source type and source id; otherwise `False`.

**Rules:**
- **R1.** One or more matching rows → `True`.
- **R2.** A matching row in another workspace does not count → `False`.
- **R3.** A row with the same source id but a different source type (or the same type, different id) does not count → `False`.
- **R4.** Ledger tables have no soft delete; every row counts.

**Errors:** none

**Side effects:** none (reads; autoflush may flush pending session changes first)

---

## `_storage_ledger_exists(session, *, workspace_id, source_type, source_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_post_event_item_delta`, `_reverse_event_item_posting`, `_reverse_legacy_line_posting`)

**Purpose:** Same check as `_ledger_exists`, on the factory inventory ledger (`inventory_ledger`).

**Rules:**
- **R1.** Behaves as `_ledger_exists` R1–R4 on `inventory_ledger`, across all inventory types (a STORAGE or DAMAGED row both count).

**Errors:** none

**Side effects:** none

---

## `_machine_ledger_exists(session, *, workspace_id, source_type, source_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_post_event_item_delta`, `_reverse_event_item_posting`, `_reverse_legacy_line_posting`)

**Purpose:** Same check as `_ledger_exists`, on the machine item ledger (`machine_item_ledger`).

**Rules:**
- **R1.** Behaves as `_ledger_exists` R1–R4 on `machine_item_ledger`.

**Errors:** none

**Side effects:** none

---

## `_location_for_po(po)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `_post_event_item_delta`, `_reverse_event_item_posting`, `_reverse_legacy_line_posting`)

**Purpose:** Map a PO's destination to the inventory location stock should move to.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `po` | `PurchaseOrder` | only `destination_type` and `destination_id` read |

**Returns:** `('storage', destination_id)`, `('machine', destination_id)`, or `None`.

**Rules:**
- **R1.** `destination_type == 'storage'` → `('storage', po.destination_id)`.
- **R2.** `destination_type == 'machine'` → `('machine', po.destination_id)`.
- **R3.** Any other value → `None`. Reachable values are `'storage'`, `'machine'`, `'project'` — trimmed, lower-cased and restricted to those three by the PO create/update schemas (🐞 BUG-681, fix in `app/schemas/purchase_order.py`); of those, only `'project'` falls into this branch. *(Today: `destination_type` is unrestricted free text; any other spelling — `'Storage'`, `'storage '`, `''`, `'factory'` — also silently falls into this branch, since the comparison against `'storage'`/`'machine'` is exact — see P2.)*

**Errors:** none

**Side effects:** none

---

## `_post_event_item_delta(session, *, po, event_item, po_line, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `post_receive_event_inventory`)

**Purpose:** Move stock for one receive line and report whether a ledger row was written.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `po` | `PurchaseOrder` | destination, `po_number` used |
| `event_item` | `PoReceiveEventItem` | must have an `id` (flushed); `quantity_delta` read |
| `po_line` | `PurchaseOrderItem` | `item_id`, `line_number`, `unit_price` read; not checked to belong to `po` |
| `workspace_id` | `int` | scope for existence checks, destination lookup and ledger rows |
| `user_id` | `int` | recorded as `performed_by` / `updated_by` |

**Returns:** `True` if one ledger row was written; `False` if nothing was done.

**Rules:**
- **R1.** If this receive line was already posted — a row exists in either the factory ledger or the machine ledger with `source_type = 'po_receive_event_item'`, `source_id = event_item.id`, in this workspace — nothing is written and `False` is returned. A row with that source in another workspace does not count.
  - **R1a.** 🐞 BUG-680 The same guarantee is also enforced by the database: a partial unique index on `(workspace_id, source_type, source_id)` for the `po_receive_event_item` source type, on both `inventory_ledger` and `machine_item_ledger`. Of two concurrent calls for the same receive line, at most one succeeds; the loser's insert raises `sqlalchemy.exc.IntegrityError`, which this module does not catch (the global integrity-error handler, BUG-462, turns it into 409 — not tested here; best-practice default, delegated by reviewer), and no second stock movement is written. *(Today: no such index exists; two concurrent calls can both pass the R1 check and both post, double-moving stock — see P1.)*
- **R2.** If the PO's destination is not a storage/machine location (`_location_for_po` R3, e.g. a project — or, after BUG-681's schema fix, only `'project'`), nothing is written and `False` is returned — even for a fractional delta.
- **R3.** A zero delta writes nothing and returns `False`.
- **R4.** A fractional delta at a storage/machine destination raises 400 per `_delta_to_int` R4; nothing is written by this call.
- **R5.** If the PO line has no unit price (`unit_price` is `NULL`) and the delta is a non-zero whole number at a storage/machine destination, `decimal.InvalidOperation` is raised (not an `HTTPException`); nothing is written. *(Not reachable from the API today: items cannot be confirmed without positive unit prices, and receiving requires a confirmed invoice.)*
- **R6.** Positive delta, storage destination: a factory ledger row is written with `inventory_type` STORAGE, `factory_id = destination_id`, `item_id = po_line.item_id`, `transaction_type 'purchase_order'`, `quantity` = delta, `unit_cost = po_line.unit_price`, `total_cost` = unit cost × quantity rounded to 0.01, `qty_before`/`qty_after` = stock before/after, `avg_price_before` = old average, `avg_price_after` = new weighted average, `source_type 'po_receive_event_item'`, `source_id = event_item.id`, `transfer_source_type`/`id` `NULL`, `notes "PO {po_number} line {line_number} (receive event #{event_item.id})"`, `performed_by = user_id`. The factory's STORAGE stock row gets `qty` + delta, `avg_price` = new average, `updated_by = user_id`. Returns `True`.
- **R7.** Positive delta, machine destination: a machine ledger row is written with `machine_id = destination_id`, same item/transaction type/quantity/unit cost/total cost/source/notes/performed_by as R6, `qty_before`/`qty_after`, `avg_price_before` = the machine's current unit cost, `avg_price_after` = new weighted average (old average ignored when stock was 0), `value_before` = qty before × avg before, `value_after` = qty after × avg after. The machine's stock row gets `qty` + delta. A machine activity event is logged: `event_type 'purchase_received'`, description `"Purchase received: {qty} units of {item name} from PO {po_number}"`, `performed_by = user_id`, metadata `{"item_id", "item_name", "quantity"}`. Returns `True`.
- **R8.** Negative delta, storage destination: a factory ledger row is written with `transaction_type 'inventory_adjustment'`, `quantity` = |delta|, `unit_cost` = the bucket's current average price (0 if none), `total_cost` = unit cost × quantity rounded to 0.01, `avg_price_before` = `avg_price_after` = current average, `qty_after = qty_before − |delta|`, source as R6, `transfer_destination_type`/`id` `NULL`, `notes "PO {po_number} line {line_number} (receive event #{event_item.id}) — quantity correction"`. Stock row `qty` decreases by |delta|, `updated_by = user_id`, average unchanged. Returns `True`.
- **R9.** Negative delta, machine destination: a machine ledger row as in R8 (unit cost = machine's current unit cost, before/after averages equal, `value_before`/`value_after` = qty × that cost), machine stock decreases by |delta|, and a machine activity event is logged: `event_type 'purchase_correction'`, description `"Receiving correction: {qty} units of {item name} removed from PO {po_number}"`. Returns `True`.
- **R10.** Negative delta larger than the stock on hand raises 400 and writes no ledger row (storage: `"Insufficient stock ({available} available, {qty} requested)"`; machine: `"Insufficient machine stock ({available} available, {qty} requested)"`), both numbers rendered as plain integers (e.g. `"Insufficient stock (7 available, 10 requested)"`). A stock row may still have been created/restored/re-synced (see Notes).
- **R11.** "Item name" in descriptions is the item's name in this workspace (a soft-deleted item's name is still used), or `"Item #{item_id}"` if no such item exists in the workspace.
- **R12.** The destination is looked up by id within the workspace: a factory/machine that does not exist, or belongs to another workspace, raises 404 (`"Factory with ID {id} not found"` / `"Machine with ID {id} not found"`) and nothing is written.
  - **R12a.** 🐞 BUG-684 A soft-deleted factory or machine is rejected with `HTTPException` 400 before anything is written — `"Factory with ID {id} has been deleted"` / `"Machine with ID {id} has been deleted"` (best-practice default, delegated by reviewer). This applies to receiving only; void reversals (`_reverse_event_item_posting`, `_reverse_legacy_line_posting`) must still be able to reverse stock at a since soft-deleted location, so their destination lookup is unchanged. *(Today: a soft-deleted factory or machine is accepted and receives the stock, invisible in inventory screens — see Q4.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional delta (storage/machine destination) | `HTTPException` 400 | `Line {line_number} has a fractional quantity delta; inventory requires whole units` |
| storage factory missing / other workspace | `HTTPException` 404 | `Factory with ID {id} not found` |
| machine missing / other workspace | `HTTPException` 404 | `Machine with ID {id} not found` |
| negative delta > storage stock | `HTTPException` 400 | `Insufficient stock ({available} available, {qty} requested)` |
| negative delta > machine stock | `HTTPException` 400 | `Insufficient machine stock ({available} available, {qty} requested)` |
| unit price `NULL` | `decimal.InvalidOperation` | — |
| destination soft-deleted (🐞 BUG-684, R12a) | `HTTPException` 400 | `Factory with ID {id} has been deleted` / `Machine with ID {id} has been deleted` |
| concurrent duplicate post for the same receive line (🐞 BUG-680, R1a) | `sqlalchemy.exc.IntegrityError` (propagates; 409 only via the global handler, BUG-462) | — |

**Side effects:** as in R6–R9: one ledger row, stock row updated (flushed), machine activity event for machine destinations. No commit.

---

## `post_receive_event_inventory(session, po, event_items, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by `PurchaseOrderService.create_receive_event`)

**Purpose:** Move stock for every line of one receive batch / correction.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `po` | `PurchaseOrder` | the PO received against |
| `event_items` | sequence of `(PoReceiveEventItem, PurchaseOrderItem)` | receive line + its PO line; may be empty |
| `workspace_id` | `int` | workspace scope |
| `user_id` | `int` | acting user |

**Returns:** number of ledger rows written (0 … len(event_items)).

**Rules:**
- **R1.** Each pair is handled per `_post_event_item_delta` R1–R12, in the given order; the result is how many of them returned `True`.
- **R2.** An empty sequence returns 0 and writes nothing.
- **R3.** The same receive line appearing twice is posted once (the second sees the first's row) and counts once.
- **R4.** If any pair raises, the error propagates unchanged; rows written for earlier pairs remain flushed in the session (the caller rolls back).

**Errors:** those of `_post_event_item_delta`.

**Side effects:** see `_post_event_item_delta`. No commit.

---

## `_reverse_event_item_posting(session, *, po, event_item, po_line, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `reverse_po_receive_inventory`)

**Purpose:** Undo the stock movement of one receive line when its PO is voided.

**Inputs:** as `_post_event_item_delta` (`event_item` read from the DB).

**Returns:** `True` if a reversal ledger row was written, else `False`.

**Rules:**
- **R1.** If this receive line was already reversed — a row exists in either ledger with `source_type = 'po_receive_event_item_reversal'`, `source_id = event_item.id`, in this workspace — nothing is written, `False`.
  - **R1a.** 🐞 BUG-680 Also enforced by the database: a partial unique index on `(workspace_id, source_type, source_id)` for the `po_receive_event_item_reversal` source type, on both `inventory_ledger` and `machine_item_ledger`. Of two concurrent reversal calls for the same receive line, at most one succeeds; the loser's insert raises `sqlalchemy.exc.IntegrityError`, not caught here (409 translation belongs to the global handler, BUG-462; best-practice default, delegated by reviewer), and no second reversal is written. *(Today: no such index exists — see P1.)*
- **R2.** If the receive line was never posted — no row in either ledger with `source_type 'po_receive_event_item'` and this id in this workspace — nothing is written, `False`.
- **R3.** 🐞 BUG-683 The PO's *current* destination does not decide whether a reversal happens: once R1/R2 pass, the reversal is made at the recorded location per R9 even if the PO's destination is now a project (or any non-storage/machine value). *(Today: a current destination that is not storage/machine (`_location_for_po` R3) → nothing written, `False`, leaving the originally posted stock in place. Reworded in fill-gaps because the untagged "nothing written" rule contradicted R9 — best-practice default, delegated by reviewer.)*
- **R4.** Zero delta → nothing written, `False`. *(Not reachable in practice: zero deltas are never posted, so R2 returns first.)*
- **R5.** Fractional delta → 400 per `_delta_to_int` R4. *(Not reachable in practice: fractional deltas are never posted.)*
- **R6.** Positive delta (a receive): stock-out of |delta| at the destination with `transaction_type 'inventory_adjustment'`, `source_type 'po_receive_event_item_reversal'`, `source_id = event_item.id`, `notes "PO {po_number} voided — reverse receive event #{event_item.id} line {line_number}"`; ledger/stock outcome as `_post_event_item_delta` R8 (storage) / R9 (machine). Machine destinations log activity `event_type 'purchase_reversed'`, description `"PO {po_number} voided — {qty} units of {item name} removed"`. Returns `True`.
  - **R6a.** 🐞 BUG-682 The quantity stocked out is |delta| minus the PO line's returned-but-not-yet-netted quantity (sum of `quantity_returned` on completed `PurchaseOrderReturnItem` rows where `po_item_id = po_line.id` — "completed" meaning a ledger row exists in this workspace, in the same ledger as this receive line's original posting, with `source_type 'purchase_return_item'` and `source_id` = the return item's id; a return item without such a row is not netted, and the parent return's `status` is not consulted — best-practice default, delegated by reviewer), consumed against that PO line's receive-line reversals newest-event-first per `reverse_po_receive_inventory` R2, until fully netted (best-practice default, delegated by reviewer — see Q1 Resolution). If the netted quantity is 0 (this receive line's delta is fully absorbed by returns), no ledger row is written and this returns `False`; otherwise the reduced quantity is used in R6. The remaining-to-net quantity is handed in by `reverse_po_receive_inventory` through a new optional keyword parameter whose default means "nothing to net", so a direct call without it behaves exactly as R6 (parameter name left to the fix; R6a is tested only through `reverse_po_receive_inventory` R7 — best-practice default, delegated by reviewer). *(Today: the full |delta| is always reversed, with no awareness of returns, double-deducting units already sent back to the supplier — see Q1.)*
- **R7.** Negative delta (a downward correction): stock-in of |delta| with `unit_cost = po_line.unit_price`, `transaction_type 'inventory_adjustment'`, same source/notes as R6; ledger/stock outcome as `_post_event_item_delta` R6/R7 (weighted average updated). Machine activity `event_type 'purchase_reversed'`, description `"PO {po_number} voided — {qty} units of {item name} restored"`. Returns `True`.
- **R8.** ✅ Stock-out larger than stock on hand raises 400 per `_post_event_item_delta` R10; nothing is reversed for that line. *(see Q2 — intended.)*
- **R9.** 🐞 BUG-683 Quantity and direction come from the receive line's delta; the reversal is made at the location recorded on the original ledger row found by R2 (factory + inventory type, or machine), not the PO's destination at the time of the call. The original posting may be in either ledger. *(Today: the reversal uses the PO's destination at void time; if the destination was changed after receiving, the wrong location is debited/credited and the original location is never restored — see Q3.)*
- **R10.** Missing unit price raises `decimal.InvalidOperation` for any non-zero whole delta (also for positive deltas, where the cost is not used). Destination lookup, 404s, soft-deleted destinations and item name follow `_post_event_item_delta` R11–R12.

**Errors:** as `_post_event_item_delta`, plus a concurrent duplicate reversal for the same receive line (🐞 BUG-680, R1a) → `sqlalchemy.exc.IntegrityError` propagates (409 only via the global handler, BUG-462).

**Side effects:** one ledger row, stock row updated, machine activity event for machines. No commit.

---

## `_reverse_legacy_line_posting(session, *, po, po_line, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `reverse_po_receive_inventory`)

**Purpose:** Undo stock posted by the old "mark complete" flow, which keyed ledger rows by PO line id.

**Inputs:** `po`, `po_line` (its `id`, `item_id`, `line_number` read), `workspace_id`, `user_id`.

**Returns:** `True` if a reversal row was written, else `False`.

**Rules:**
- **R1.** If a legacy reversal already exists — a row in either ledger with `source_type = 'purchase_order_reversal'`, `source_id = po_line.id`, this workspace — nothing is written, `False`.
  - **R1a.** 🐞 BUG-680 Also enforced by the database: a partial unique index on `(workspace_id, source_type, source_id)` for the `purchase_order_reversal` source type, on both `inventory_ledger` and `machine_item_ledger`. Of two concurrent calls for the same PO line, at most one succeeds; the loser's insert raises `sqlalchemy.exc.IntegrityError`, not caught here (409 translation belongs to the global handler, BUG-462; best-practice default, delegated by reviewer), and no second reversal is written. *(Today: no such index exists — see P1.)*
- **R2.** If there is no legacy posting — no row in either ledger with `source_type = 'purchase_order'`, `source_id = po_line.id`, this workspace — nothing is written, `False`. Rows from another workspace do not count.
- **R3.** 🐞 BUG-683 The PO's *current* destination does not decide whether a legacy reversal happens: once R1/R2 pass, the reversal is made at the legacy row's recorded location per R8, even if the PO's destination is now a project (or any non-storage/machine value). *(Today: a current destination that is not storage/machine → nothing written, `False`, even when a legacy posting exists. Reworded in fill-gaps because it contradicted R8 — best-practice default, delegated by reviewer.)*
- **R4.** The quantity to remove is the `quantity` of the legacy factory-ledger row if one exists; otherwise of the legacy machine-ledger row. If several legacy rows exist in the same ledger, one of them is used (no defined order).
- **R5.** A stock-out of that quantity is made at the destination with `transaction_type 'inventory_adjustment'`, `source_type 'purchase_order_reversal'`, `source_id = po_line.id`, `notes "PO {po_number} voided — reverse legacy posting for line {line_number}"`; ledger/stock outcome as `_post_event_item_delta` R8/R9. Machine destinations log activity `event_type 'purchase_reversed'`, description `"PO {po_number} voided — {qty} units of {item name} removed"`. Returns `True`.
- **R6.** A legacy row with quantity 0 still produces a reversal row of quantity 0 (stock unchanged) and returns `True`.
- **R7.** ✅ Stock-out larger than stock on hand raises 400 per `_post_event_item_delta` R10. *(see Q2 — intended.)*
- **R8.** 🐞 BUG-683 The reversal is made at the location recorded on the legacy row found by R4 (factory + inventory type, or machine), not the PO's destination at the time of the call. *(Today: the reversal uses the PO's current destination; if it was changed after the legacy posting, the reversal happens at the wrong location — see Q3.)* Destination lookup, 404s, soft-deleted destinations and item name follow `_post_event_item_delta` R11–R12 (applied to the row's recorded location). The PO line's unit price is not used.

**Errors:** `HTTPException` 404 (destination missing) / 400 (insufficient stock) as `_post_event_item_delta`, plus a concurrent duplicate legacy reversal for the same PO line (🐞 BUG-680, R1a) → `sqlalchemy.exc.IntegrityError` propagates (409 only via the global handler, BUG-462).

**Side effects:** one ledger row, stock row updated, machine activity event for machines. No commit.

---

## `reverse_po_receive_inventory(session, po, po_lines, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by `PurchaseOrderService.void_purchase_order`)

**Purpose:** Undo every stock movement a PO's receiving caused, when the PO is voided.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `po` | `PurchaseOrder` | PO being voided |
| `po_lines` | `list[PurchaseOrderItem]` | the PO's lines (caller passes all lines ordered by line number) |
| `workspace_id` | `int` | workspace scope |
| `user_id` | `int` | acting user |

**Returns:** number of reversal rows written.

**Rules:**
- **R1.** All receive lines of all receive events of this PO whose event belongs to `workspace_id` are considered; events of other POs, or recorded under another workspace, are ignored.
- **R2.** Receive lines are reversed newest event first (event `created_at` descending), and within the same timestamp by receive-line id descending — so a later downward correction is restored before the earlier receive is taken out.
- **R3.** A receive line whose PO line is not in `po_lines` is skipped (nothing written, not counted).
- **R4.** Each receive line is handled per `_reverse_event_item_posting`; then each line in `po_lines`, in the given order, per `_reverse_legacy_line_posting`.
- **R5.** The result is the total number of `True` results from both passes; a PO with no receive events and no legacy postings returns 0 and writes nothing.
- **R6.** Calling it again after a successful call writes nothing and returns 0.
- **R7.** 🐞 BUG-682 Completed purchase returns already made on the PO are netted out: across a PO line's receive-line reversals performed during this void, the total quantity removed from the destination equals that PO line's total received quantity minus its total completed-returned quantity (never negative) — so the location ends where it was before the PO, not below it. See `_reverse_event_item_posting` R6a for how the netting is applied per receive-line reversal. *(Today: purchase returns are not considered; every posted receive line is reversed in full, double-deducting units already sent back to the supplier — see Q1.)*
- **R8.** If any reversal raises, the error propagates unchanged; reversals written before it remain flushed (the caller rolls back).

**Errors:** those of `_reverse_event_item_posting` and `_reverse_legacy_line_posting`.

**Side effects:** reversal ledger rows, stock rows updated, machine activity events. No commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25 | delta has fractional part | `_delta_to_int` R4 (else R1–R3) |
| 33 | `abs()` of negative delta | `_delta_to_int` R2 |
| 34 | qty ≤ 0 | `_delta_to_int` R3 |
| 48–55 | row found / not found (workspace, type, id) | `_ledger_exists` R1–R4 |
| 60 (`exists_for_source`) | row found / not found | `_storage_ledger_exists` R1 |
| 66 | delegates to `_ledger_exists` | `_machine_ledger_exists` R1 |
| 76 | destination `'storage'` | `_location_for_po` R1 |
| 78 | destination `'machine'` | `_location_for_po` R2 |
| 80 | anything else | `_location_for_po` R3 |
| 93–103 | already posted (storage ledger `or` machine ledger) | `_post_event_item_delta` R1 |
| 107 | no location | `_post_event_item_delta` R2 |
| 112 | delta == 0 | `_post_event_item_delta` R3 |
| 115 | `_delta_to_int` raises | `_post_event_item_delta` R4 |
| 116 | qty ≤ 0 (unreachable: delta ≠ 0 and whole ⇒ qty ≥ 1) | `_post_event_item_delta` R3 |
| 119 | `unit_price` `NULL` → `Decimal('None')` | `_post_event_item_delta` R5 |
| 122 | delta > 0 vs < 0 | `_post_event_item_delta` R6/R7 vs R8/R9 |
| 136–141 | location machine vs storage (activity type/description) | `_post_event_item_delta` R7 vs R6; R9 vs R8 |
| 157–163 | location machine vs storage | `_post_event_item_delta` R9 vs R8 |
| `inventory_movements` 372/388/405, 431/449/468 | location type storage / machine / other | `_post_event_item_delta` R6–R9 (other unreachable: `_location_for_po` only yields storage/machine) |
| `inventory_movements` 64, 133 | factory not found in workspace | `_post_event_item_delta` R12 |
| `inventory_movements` 222, 300 | machine not found in workspace | `_post_event_item_delta` R12 |
| `inventory_movements` 75 | storage stock < qty | `_post_event_item_delta` R10 |
| `inventory_movements` 226 | machine stock < qty | `_post_event_item_delta` R10 |
| `inventory_movements` 81 | bucket avg `NULL` → cost 0 | `_post_event_item_delta` R8 |
| `inventory_movements` 199 | no machine ledger / avg `NULL` → cost 0 | `_post_event_item_delta` R7, R9 |
| `inventory_movements` 33–38 | weighted avg: add ≤ 0 / old stock > 0 with avg / else unit cost | Notes (formula), `_post_event_item_delta` R6/R7 |
| `inventory_movements` 307 | machine qty_before > 0 (old avg used) | `_post_event_item_delta` R7 |
| `inventory_movements` 24 | item found / not found | `_post_event_item_delta` R11 |
| `inventory_movements` 182 | machine stock row exists / created | Notes; `_post_event_item_delta` R7 |
| `inventory_movements` 267, 340 | `source_type == 'work_order'` (never true here) | `_post_event_item_delta` R7 (metadata has no `work_order_id`) |
| `inventory_movements` 274, 347 | description given (always here) | `_post_event_item_delta` R7, R9 |
| `inventory` DAO 247/259/268–283 | stock row active / soft-deleted / missing | Notes |
| 177 | loop over empty / one / many pairs | `post_receive_event_inventory` R1–R3 |
| 178 | posted → count | `post_receive_event_inventory` R1 |
| 199–209 | reversal already exists | `_reverse_event_item_posting` R1 |
| 212–225 | original posting missing | `_reverse_event_item_posting` R2 |
| 229 | no location | `_reverse_event_item_posting` R3 |
| 234 | delta == 0 | `_reverse_event_item_posting` R4 |
| 237 | fractional raises | `_reverse_event_item_posting` R5 |
| 238 | qty ≤ 0 (unreachable) | `_reverse_event_item_posting` R4 |
| 241 | `unit_price` `NULL` | `_reverse_event_item_posting` R10 |
| 244 | delta > 0 vs < 0 | `_reverse_event_item_posting` R6 vs R7 |
| 257–263, 279–285 | machine vs storage activity | `_reverse_event_item_posting` R6, R7 |
| 299–309 | legacy reversal exists | `_reverse_legacy_line_posting` R1 |
| 330 | no legacy row in either ledger | `_reverse_legacy_line_posting` R2 |
| 334 | no location | `_reverse_legacy_line_posting` R3 |
| 338 | storage legacy row vs machine legacy row | `_reverse_legacy_line_posting` R4 |
| 359–365 | machine vs storage activity | `_reverse_legacy_line_posting` R5 |
| 381–389 | receive lines of PO + workspace, ordered | `reverse_po_receive_inventory` R1, R2 |
| 392 | loop over none / many receive lines | `reverse_po_receive_inventory` R4, R5 |
| 394 | PO line not in `po_lines` → skip | `reverse_po_receive_inventory` R3 |
| 396 | reversed → count | `reverse_po_receive_inventory` R5 |
| 406–414 | loop over lines, legacy reversed → count | `reverse_po_receive_inventory` R4, R5 |

## Gap log
- G1 (po_receive_inventory.cases.md gap 1) — Intent, decided by best practice (delegated by reviewer) — R1a in `_post_event_item_delta`, `_reverse_event_item_posting`, `_reverse_legacy_line_posting` and their Errors now say the losing insert raises `sqlalchemy.exc.IntegrityError`, not caught by this module; the 409 translation belongs to the global handler (BUG-462). Note added for the test designer.
- G2 (po_receive_inventory.cases.md gap 2) — Intent, decided by best practice (delegated by reviewer) — `_reverse_event_item_posting` R6a: the remaining-to-net quantity arrives through a new optional keyword parameter that defaults to "nothing to net". The name is left to the fix, and R6a is tested only through `reverse_po_receive_inventory` R7.
- G3 (po_receive_inventory.cases.md gap 3) — Fact + intent, decided by best practice (delegated by reviewer) — defined a "completed" return: a ledger row with `source_type 'purchase_return_item'` and `source_id` = return item id (what `po_return_inventory` writes), in the same workspace and the same ledger as the original posting. The parent return's status is not consulted. R6a reworded; setup note added.
- G4 (po_receive_inventory.cases.md gap 4) — Contradiction — `_reverse_event_item_posting` R3 and `_reverse_legacy_line_posting` R3 re-tagged BUG-683: the current destination no longer blocks a reversal, and today's "nothing written" behavior moved into the *(Today: ...)* note. No new bug (same fix as BUG-683).
- G5 (po_receive_inventory.cases.md gap 5) — Fact — stock `qty` columns are `Integer` and the requested qty is an `int`, so the numbers in "Insufficient ..." messages are plain integers; stated in `_post_event_item_delta` R10 and Notes.
