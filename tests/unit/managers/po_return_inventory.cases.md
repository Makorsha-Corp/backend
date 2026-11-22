# Test cases: `app/managers/po_return_inventory.py`

> **Spec:** `tests/unit/managers/po_return_inventory.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2. The spec closed gaps G1–G6. G1: new R8a, the storage stock is re-synced from the latest storage-ledger row, so P-41/42/44/45 were added and P-07 strengthened. G2: "latest" is `performed_at` only, seeds use explicit past timestamps (Conventions), and P-43/46 were added to tell `performed_at` apart from id. New R15a [BUG-803] adds P-47 (non-strict xfail). G3: metadata attribute `metadata_json` (P-11/14). G4: rows with qty ≤ 0 persist, so the unsaved-object fallback was dropped. G5: R8b says rounding cannot be observed, so P-04 was retired, P-03 now asserts null `avg_price_*`, and R8b is covered by P-01. G6: the R17 deferral is confirmed.
> **Revision:** 3. Re-run with no spec change since revision 2 and no verify report. The full self-check found one inconsistency: the Coverage matrix cited P-06 for "re-sync leaves `updated_by` unchanged", but P-06 did not assert it. P-06 now asserts `updated_by` U1 and the average price. Counts unchanged.
> **Counts:** 68 cases · 65 expected-to-pass · 3 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `_machine_ledger_exists` 6 cases · `_storage_ledger_exists` 6 · `_location_for_po` 5 · `_quantity_to_int` 5 (1 bug) · `post_purchase_return_inventory` 46 (2 bugs).
- **Notable design choices:**
  - Only BUG-802 has xfail cases here (the helper message, and the same message seen through `post_purchase_return_inventory`). BUG-800 (R17, missing row lock) is **deferred** to `PurchaseOrderService.complete_return` / `inventory_movements`, where the spec puts the fix. This module cannot show the lock in one session, and patching the idempotency check would give a strict xfail that never turns green (best-practice default, delegated by reviewer). BUG-801 is deferred to the return-start module, as the spec says.
  - The `_quantity_to_int` pass cases call it through a test-side wrapper. The wrapper passes the identifier as `line_number=` if the function has that keyword, else as `po_item_id=`, so the pass cases still run after the BUG-802 rename (best-practice default, delegated by reviewer).
  - Every storage-stock setup also seeds a matching storage-ledger history with explicit past `performed_at`, as the spec's R8a requires. A stock row alone would be re-synced to 0. P-41/42 set the stock row and the ledger to different values on purpose, to show the re-sync.
  - PRI-P-47 (R15a, BUG-803) is `xfail(strict=False)`, as the spec directs. Today the result depends on which of two rows with the same timestamp Postgres returns, so the test can pass by chance.
  - `_location_for_po` R3 is also checked through the public function. A `'project'` or `'Storage'` PO points its `destination_id` at a real factory that holds stock, so treating that PO as storage would visibly deduct stock.
- **Needs a decision:** None. The spec's Gap log closed all six earlier gaps (G1–G6), and no new gaps were found.

## Conventions for this module

**IDs:** `PRI` = po_return_inventory. Methods: `MLE` = `_machine_ledger_exists`, `SLE` = `_storage_ledger_exists`, `LOC` = `_location_for_po`, `QTI` = `_quantity_to_int`, `P` = `post_purchase_return_inventory`.

**Externals mocked:** none. `utcnow` is not mocked, and `performed_at` is never asserted on rows the function writes.

**Timestamps (spec G2):** **T0** = the current time minus 1 day. Every seeded storage-ledger (inventory-ledger) row and every seeded machine-ledger row gets an explicit `performed_at`. Within one case, seeded rows are T0, T0+1min, T0+2min, … in the listed order, unless the case gives another time. Rows the function writes are therefore later than any seed.

**Setup vocabulary** (all rows real and flushed unless stated):
- **W1, W2**: two workspaces. **U1**: a profile in W1 that creates the setup rows. **U2**: a second profile in W1, always passed as `user_id`. U2 differs from U1 so `performed_by` / `updated_by` changes are visible.
- **F1**: a live factory in W1. **F1d**: a soft-deleted factory in W1. **F2**: a live factory in W2.
- **M1**: a live machine in W1. **M3**: a second live machine in W1. **M1d**: a soft-deleted machine in W1. **M2**: a live machine in W2.
- **I1** = catalog item "Steel Bolt M8" in W1. **I2** = "Hex Nut M8" in W1. **IX** = "Foreign Washer" in W2.
- **PO**: a purchase order in W1 with `po_number` "PO-0012". Its `destination_type` / `destination_id` are set per case.
- **PL1, PL2, PL3**: lines of PO with `line_number` 1, 2 and 3. Their item is I1, I1 and I2 unless a case says otherwise.
- **R**: a purchase-order return of PO in W1. **RI1, RI2, RI3**: return items of R. Each has `quantity_returned` as given, `item_id` equal to its paired PO line's item unless a case says otherwise, and its paired line as its PO item. The pair notation is `[(RI1, PL2), …]`.
- **S(F, I) = n @ p**: a storage-type stock row for factory F and item I, with quantity n, average price p, and `updated_by` U1. **Seeded per G1**: the storage inventory ledger also holds one "opening" row for (F, I, storage). That row has `transaction_type` 'purchase_receive' (or the receipt type the executor finds in use), `source_type` 'test_seed', `source_id` 1, quantity n, `qty_before` 0, `qty_after` n and `avg_price_after` p. A setup that also seeds an earlier return row builds a consistent chain instead (e.g. 0→12, then return 12→10). This seeding is **required** (spec R8a): the stock row is re-synced from the latest such row before every deduction.
- **D(F, I) = n**: a damaged-type stock row, seeded the same way.
- **MH(M, I) = n**: the machine placement (on-hand quantity) of item I on machine M is n.
- **ML(M, I, avg=p)**: a pre-existing machine ledger row for M/I with `avg_price_after` p, `source_type` 'test_seed' and `source_id` 1. When a case lists several ML rows, they are inserted in the listed order, with strictly increasing `performed_at` (see Timestamps). "Most recent" is by `performed_at` only (spec R11). P-46 inserts the rows in the opposite order on purpose, to tell time apart from id.
- **Posted-row(ledger, RIk)**: a pre-existing ledger row with `source_type` 'purchase_return_item', `source_id` RIk.id, `transaction_type` 'purchase_return', in W1 unless stated. Its quantity is 1, except in a storage chain, where it equals the chain step (e.g. 2 for 12→10). A storage-ledger one is part of the G1 chain, with the next seed timestamp.
- **"No return rows"** means no inventory-ledger or machine-ledger row in any workspace has `source_type` 'purchase_return_item' and a `source_id` among the case's RI ids, except the rows the case seeded.
- **SUFFIX** = `has a fractional quantity; inventory requires whole units`.

**Every `post_purchase_return_inventory` case** passes `workspace_id=W1.id` and `user_id=U2.id`, and re-reads stock rows, placements, ledger rows and activity events from the database after the call (`session.expire_all()` first).

**Race simulations:** none. R17 is deferred (spec Notes, G6).

**Activity-event metadata** is read from the event's `metadata_json` attribute (spec R12).

**Return items with `quantity_returned` 0 or negative** are persisted directly. The column has no check constraint (spec Notes, G4).

**Wrapper `qti(q, ident)`** (test-side; used only by `_quantity_to_int` pass cases): calls `_quantity_to_int(q, line_number=ident)` if that keyword exists in its signature, else `_quantity_to_int(q, po_item_id=ident)`.

## `_machine_ledger_exists`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-MLE-01 | R1 | happy | W1 machine ledger has one row on M3 / I2 with `source_type` 'purchase_return_item', `source_id` 501 | `_machine_ledger_exists(session, workspace_id=W1.id, source_type='purchase_return_item', source_id=501)` | returns `True` (exactly `True`, a bool) | pass |
| PRI-MLE-02 | R2 | boundary | W1 machine ledger has one row with ('purchase_return_item', 502) only | same call with `source_id=501` | returns `False` | pass |
| PRI-MLE-03 | R3 | isolation | W2 machine ledger has a row on M2 with ('purchase_return_item', 501); W1 has none | same call for W1, `source_id=501` | returns `False`; the same call with `workspace_id=W2.id` returns `True` | pass |
| PRI-MLE-04 | R4 | boundary | W1 machine ledger has a row ('po_receive_event_item', 501) | same call ('purchase_return_item', 501) | returns `False`; the call with `source_type='po_receive_event_item'` returns `True` | pass |
| PRI-MLE-05 | R4 | boundary | W1 machine ledger has a row ('purchase_return_item', 501) | call with `source_type='Purchase_Return_Item'`, `source_id=501` | returns `False` (the match is case-sensitive) | pass |
| PRI-MLE-06 | R5 | isolation | W1 **storage** inventory ledger has a row ('purchase_return_item', 501) for F1 / I1; the machine ledger is empty | same call ('purchase_return_item', 501) for W1 | returns `False` | pass |

## `_storage_ledger_exists`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-SLE-01 | R1 | happy | W1 inventory ledger has one **storage**-type row for F1 / I2 with ('purchase_return_item', 601) | `_storage_ledger_exists(session, workspace_id=W1.id, source_type='purchase_return_item', source_id=601)` | returns `True` | pass |
| PRI-SLE-02 | R1 | happy | W1 inventory ledger has one **damaged**-type row for F1d / I1 with ('purchase_return_item', 601) | same call | returns `True` | pass |
| PRI-SLE-03 | R2 | boundary | W1 inventory ledger has one row ('purchase_return_item', 602) only | same call with `source_id=601` | returns `False` | pass |
| PRI-SLE-04 | R3 | isolation | W2 inventory ledger has a row for F2 with ('purchase_return_item', 601); W1 has none | same call for W1 | returns `False`; the same call with `workspace_id=W2.id` returns `True` | pass |
| PRI-SLE-05 | R4 | boundary | W1 inventory ledger has a row ('po_receive_event_item', 601) | same call ('purchase_return_item', 601) | returns `False`; the call with `source_type='po_receive_event_item'` returns `True` | pass |
| PRI-SLE-06 | R5 | isolation | W1 **machine** ledger has a row ('purchase_return_item', 601) on M1; the inventory ledger is empty | same call for W1 | returns `False` | pass |

## `_location_for_po`

PO objects here can be transient (unsaved) `PurchaseOrder` instances with only `destination_type` / `destination_id` set.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-LOC-01 | R1 | happy | PO with `destination_type='storage'`, `destination_id=7` | `_location_for_po(po)` | returns exactly `('storage', 7)` | pass |
| PRI-LOC-02 | R2 | happy | PO with `destination_type='machine'`, `destination_id=7` | `_location_for_po(po)` | returns exactly `('machine', 7)` | pass |
| PRI-LOC-03 | R3 | boundary | parametrized: `destination_type` ∈ {'project', 'damaged'}, `destination_id=7` | `_location_for_po(po)` | returns `None` | pass |
| PRI-LOC-04 | R3 | boundary | parametrized: `destination_type` ∈ {'Storage', 'MACHINE'}, `destination_id=7` | `_location_for_po(po)` | returns `None` (case-sensitive) | pass |
| PRI-LOC-05 | R3 | boundary | `destination_type=''`, `destination_id=7` | `_location_for_po(po)` | returns `None` | pass |

## `_quantity_to_int`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-QTI-01 | R1 | happy | parametrized: `Decimal('3')`, `Decimal('3.00')` | `qti(q, 2)` | returns `3`, and `type(result) is int` | pass |
| PRI-QTI-02 | R1 | boundary | `Decimal('0')` | `qti(q, 2)` | returns `0`, type `int`; no exception | pass |
| PRI-QTI-03 | R1 | boundary | `Decimal('-2.00')` | `qti(q, 2)` | returns `-2`, type `int`; no exception (no sign check) | pass |
| PRI-QTI-04 | R2, Errors row 1 | error | parametrized: `Decimal('1.5')`, `Decimal('0.01')`, `Decimal('-0.5')` | `qti(q, 2)` | raises `HTTPException`, `status_code == 400`; `detail` starts with `Return line for PO ` and ends with SUFFIX | pass |
| PRI-QTI-05 | R2 [BUG-802], Errors row 1 | bug | `Decimal('1.5')` | `_quantity_to_int(Decimal('1.5'), line_number=2)` (keyword literally `line_number`, no wrapper) | raises `HTTPException` 400 with `detail == "Return line for PO line 2 has a fractional quantity; inventory requires whole units"` | xfail BUG-802. Fails today on: `TypeError` (no `line_number` parameter); after a partial fix, on the detail text |

## `post_purchase_return_inventory`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-P-01 | R8, R8b, R16, `_location_for_po` R1 | happy | PO → storage F1. S(F1,I1)=10 @ 12.50; D(F1,I1)=5. RI1 qty `3.00` paired with PL2 (line 2, item I1) | call with `[(RI1, PL2)]` | returns `1`. Re-read: storage stock F1/I1 quantity 7, average price 12.50, `updated_by` U2; damaged stock F1/I1 still 5. Exactly one inventory-ledger row with ('purchase_return_item', RI1.id), and it has: workspace W1, factory F1, item I1, inventory type storage, `transaction_type` 'purchase_return', quantity 3, `qty_before` 10, `qty_after` 7, `unit_cost` 12.50, `total_cost` 37.50, `avg_price_before` 12.50, `avg_price_after` 12.50, transfer-destination fields null, `performed_by` U2, `notes` == `f"PO PO-0012 return {R.id} (line 2)"`. No machine-ledger row with that source; no machine activity event in W1 | pass |
| PRI-P-02 | R8 (item comes from the PO line) | side-effect | PO → storage F1. S(F1,I1)=10 @ 12.50; S(F1,I2)=4 @ 5.00. RI1 qty 3, with `item_id` = **I2**, paired with PL2 (item **I1**) | call `[(RI1, PL2)]` | returns `1`; S(F1,I1) quantity 7; S(F1,I2) quantity still 4; the new ledger row for RI1 has item I1 | pass |
| PRI-P-03 | R8 (no average price → 0) | boundary | PO → storage F1. S(F1,I1)=10 with **null** average price (seed row `avg_price_after` null). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; stock quantity 7; the ledger row for RI1 has `unit_cost` 0 and `total_cost` 0.00 (numerically equal to 0), and `avg_price_before` and `avg_price_after` are both **null**. The stock row's average price is still null | pass |
| PRI-P-05 | R9 (equal stock allowed) | boundary | PO → storage F1. S(F1,I1)=3 @ 12.50. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; stock quantity 0; ledger row for RI1 has `qty_before` 3, `qty_after` 0 | pass |
| PRI-P-06 | R9, Errors row 2 | error | PO → storage F1. S(F1,I1)=2 @ 12.50. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises `HTTPException` 400, `detail == "Insufficient stock (2 available, 3 requested)"`. Re-read: stock F1/I1 quantity 2, average price 12.50, `updated_by` still U1 (the re-sync changed nothing, HR-9); no return rows | pass |
| PRI-P-07 | R9 (no stock row = 0), Errors row 2 | boundary | PO → storage F1. F1 has **no** stock row and no ledger rows for I1. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises 400, `detail == "Insufficient stock (0 available, 3 requested)"`; no return rows. Re-read: exactly one storage-type stock row for F1/I1 now exists (created, flushed), with quantity 0 and a null average price | pass |
| PRI-P-08 | R10, Errors row 4 | error | PO → storage, `destination_id=999999` (no factory with that id). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises `HTTPException` 404, `detail == "Factory with ID 999999 not found"`; no return rows | pass |
| PRI-P-09 | R10, Errors row 4 | isolation | PO (W1) → storage F2 (a W2 factory). S(F2,I1)=10 @ 12.50 in W2. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises 404, `detail == f"Factory with ID {F2.id} not found"`; S(F2,I1) still 10 and `updated_by` still U1; no return rows | pass |
| PRI-P-10 | R10 (soft-deleted factory still found) | soft-delete | PO → storage F1d. S(F1d,I1)=10 @ 12.50. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; S(F1d,I1) quantity 7; one ledger row for RI1 on F1d with quantity 3 | pass |
| PRI-P-11 | R11, R12, R16, `_location_for_po` R2 | happy | PO → machine M1. MH(M1,I1)=10. ML(M1,I1,avg=9.00), then ML(M1,I1,avg=12.50), then decoys ML(M1,I2,avg=99.00) and ML(M3,I1,avg=77.00). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. MH(M1,I1)=7. Exactly one machine-ledger row with ('purchase_return_item', RI1.id), and it has: workspace W1, machine M1, item I1, `transaction_type` 'purchase_return', quantity 3, `unit_cost` 12.50, `value_before` 125.00, `value_after` 87.50, `avg_price_before` 12.50, `avg_price_after` 12.50, `performed_by` U2, `notes` == `f"PO PO-0012 return {R.id} (line 2)"`. Exactly one new activity event for M1: `event_type` 'purchase_returned', `description` == "Purchase returned: 3 units of Steel Bolt M8 to supplier", `performed_by` U2, `metadata_json` == `{"item_id": I1.id, "item_name": "Steel Bolt M8", "quantity": 3}` (exact dict equality, `item_id` and `quantity` are `int`, no `work_order_id` key). No inventory-ledger row with that source | pass |
| PRI-P-12 | R11 (no prior ledger → 0) | boundary | PO → machine M1. MH(M1,I1)=10; no ML rows for M1/I1 (decoy ML(M3,I1,avg=77.00) exists). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; MH 7; the ledger row for RI1 has `unit_cost` 0, `value_before` 0, `value_after` 0, `avg_price_before` 0, `avg_price_after` 0 | pass |
| PRI-P-13 | R11 (latest avg null → 0) | boundary | PO → machine M1. MH(M1,I1)=10. ML(M1,I1,avg=12.50), then ML(M1,I1,avg=**null**). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; the ledger row for RI1 has `unit_cost` 0, `value_before` 0 and `value_after` 0 (not 12.50-based) | pass |
| PRI-P-14 | R12 (item not in workspace → fallback name) | side-effect | PO → machine M1. PL2's item is **IX** (W2). MH(M1,IX)=5. RI1 qty 2 with PL2 | call `[(RI1, PL2)]` | returns `1`; MH(M1,IX)=3; activity event `description` == `f"Purchase returned: 2 units of Item #{IX.id} to supplier"`, `metadata_json` == `{"item_id": IX.id, "item_name": f"Item #{IX.id}", "quantity": 2}` (exact dict) | pass |
| PRI-P-15 | R13 (equal stock allowed) | boundary | PO → machine M1. MH(M1,I1)=3. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; MH(M1,I1)=0; one machine-ledger row for RI1; one activity event | pass |
| PRI-P-16 | R13, Errors row 3 | error | PO → machine M1. MH(M1,I1)=2. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises `HTTPException` 400, `detail == "Insufficient machine stock (2 available, 3 requested)"`; MH still 2; no return rows; no activity event for M1 | pass |
| PRI-P-17 | R13 (no placement → 0 placement created), Errors row 3 | boundary | PO → machine M1. M1 has **no** placement for I1. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises 400, `detail == "Insufficient machine stock (0 available, 3 requested)"`; a placement for M1/I1 now exists with quantity 0; no return rows; no activity event | pass |
| PRI-P-18 | R14, Errors row 5 | error | PO → machine, `destination_id=999999`. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises `HTTPException` 404, `detail == "Machine with ID 999999 not found"`; no return rows; no activity events in W1 | pass |
| PRI-P-19 | R14, Errors row 5 | isolation | PO (W1) → machine M2 (W2). MH(M2,I1)=10 | call `[(RI1, PL2)]` with RI1 qty 3 | raises 404, `detail == f"Machine with ID {M2.id} not found"`; MH(M2,I1) still 10; no return rows; no activity event for M2 | pass |
| PRI-P-20 | R14 (soft-deleted machine still found) | soft-delete | PO → machine M1d. MH(M1d,I1)=10. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; MH(M1d,I1)=7; one machine-ledger row for RI1 on M1d; one 'purchase_returned' event for M1d | pass |
| PRI-P-21 | R1, `_location_for_po` R3 | boundary | PO `destination_type='project'`, `destination_id=F1.id`. S(F1,I1)=10 @ 12.50. RI1 qty `1.50` with PL1; RI2 qty 3 with PL2 already has Posted-row(storage, RI2) (G1 chain ends at 10); RI3 qty 3 with PL3 | call `[(RI1, PL1), (RI2, PL2), (RI3, PL3)]` | returns `0`, no exception; S(F1,I1) still 10 and `updated_by` U1; no return rows beyond the seeded one for RI2; no activity events in W1 | pass |
| PRI-P-22 | R1, `_location_for_po` R3 (case) | boundary | PO `destination_type='Storage'`, `destination_id=F1.id`. S(F1,I1)=10 @ 12.50. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `0`; S(F1,I1) still 10; no return rows | pass |
| PRI-P-23 | R2 | boundary | PO → storage F1. S(F1,I1)=10 @ 12.50 | call with `[]` | returns `0`; S(F1,I1) still 10, `updated_by` U1; no inventory- or machine-ledger rows with `source_type` 'purchase_return_item' in W1 | pass |
| PRI-P-24 | R3, R16 (idempotent re-run) | happy | PO → storage F1. S(F1,I1)=10 @ 12.50. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` twice in the same session | first call returns `1`, second returns `0`; S(F1,I1)=7; exactly **one** inventory-ledger row with ('purchase_return_item', RI1.id) | pass |
| PRI-P-25 | R3 | happy | PO → storage F1. G1 chain: opening 0→12, then Posted-row(storage, RI1) 12→10; stock row S(F1,I1)=10 @ 12.50. RI1 qty 2 with PL2 | call `[(RI1, PL2)]` | returns `0`; S(F1,I1) still 10; still exactly one inventory-ledger row for RI1 (the seeded one) | pass |
| PRI-P-26 | R3 (either ledger, regardless of destination) | boundary | PO → **storage** F1. S(F1,I1)=10 @ 12.50. Posted-row(**machine** ledger on M1, RI1) in W1. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `0`; S(F1,I1) still 10; no inventory-ledger row for RI1; still exactly one machine-ledger row for RI1 | pass |
| PRI-P-27 | R3 (either ledger, regardless of destination) | boundary | PO → **machine** M1. MH(M1,I1)=10. Posted-row(**storage** ledger on F1/I1, RI1) in W1 (inside a G1 chain for S(F1,I1)=10). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `0`; MH still 10; no machine-ledger row for RI1; no activity event for M1 | pass |
| PRI-P-28 | R4 | boundary | PO → storage F1. G1 chain: opening 0→11, Posted-row(storage, RI1) 11→10; S(F1,I1)=10 @ 12.50. RI1 qty **`1.50`** with PL2 | call `[(RI1, PL2)]` | returns `0`, **no** exception; S(F1,I1) still 10; still one ledger row for RI1 | pass |
| PRI-P-29 | R5 (other workspace) | isolation | PO → storage F1. S(F1,I1)=10 @ 12.50. W2 inventory ledger has a row for F2 with ('purchase_return_item', RI1.id), plus a machine-ledger row in W2 on M2 with the same source | call `[(RI1, PL2)]` with RI1 qty 3 | returns `1`; S(F1,I1)=7; exactly one **W1** inventory-ledger row for RI1 (quantity 3); W2 rows unchanged | pass |
| PRI-P-30 | R5 (other source_type) | isolation | PO → storage F1. S(F1,I1)=10 @ 12.50, where the G1 opening row has `source_type` **'po_receive_event_item'** and `source_id` **RI1.id**. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`; S(F1,I1)=7; one inventory-ledger row with ('purchase_return_item', RI1.id) | pass |
| PRI-P-31 | R6, Errors row 1 | error | PO → storage F1. S(F1,I1)=10 @ 12.50. RI1 qty `1.50` with PL2 (line 2) | call `[(RI1, PL2)]` | raises `HTTPException` 400; `detail` starts with `Return line for PO ` and ends with SUFFIX; S(F1,I1) still 10, `updated_by` U1; no return rows | pass |
| PRI-P-32 | R6 [BUG-802], Errors row 1 | bug | same as P-31. Precondition asserted in the test: `PL2.id != 2` (if equal, first create a throw-away PO line so the ids differ) | call `[(RI1, PL2)]` | raises 400 with `detail == "Return line for PO line 2 has a fractional quantity; inventory requires whole units"`; S(F1,I1) still 10; no return rows | xfail BUG-802. Fails today on: detail == `f"Return line for PO item {PL2.id} …"` |
| PRI-P-33 | R6 (earlier lines stay, later lines not processed) | side-effect | PO → storage F1. S(F1,I1)=10 @ 12.50; S(F1,I2)=4 @ 5.00. RI1 qty 2 with PL1 (I1); RI2 qty `1.50` with PL2 (I1); RI3 qty 1 with PL3 (I2) | call `[(RI1, PL1), (RI2, PL2), (RI3, PL3)]` | raises 400 (detail ends with SUFFIX). Re-read without rollback: one ledger row for RI1 (quantity 2, `qty_before` 10, `qty_after` 8); S(F1,I1)=8; no ledger rows for RI2 or RI3; S(F1,I2) still 4 | pass |
| PRI-P-34 | R6 (machine location) | error | PO → machine M1. MH(M1,I1)=10. RI1 qty `1.50` with PL2 | call `[(RI1, PL2)]` | raises 400 (detail ends with SUFFIX); MH still 10; no return rows; no activity event for M1 | pass |
| PRI-P-35 | R7 (zero) | boundary | PO → storage F1. S(F1,I1)=10 @ 12.50. RI1 with `quantity_returned` **0** with PL2 (G4) | call `[(RI1, PL2)]` | returns `0`, no exception; S(F1,I1) still 10, `updated_by` U1; no return rows | pass |
| PRI-P-36 | R7 (negative) | boundary | same, RI1 quantity **-2** (G4) | call `[(RI1, PL2)]` | returns `0`, no exception; S(F1,I1) still 10 (not 12); no return rows | pass |
| PRI-P-37 | R7 (other side: 1 posts) | boundary | PO → storage F1. S(F1,I1)=10 @ 12.50. RI1 qty `1.00` with PL2 | call `[(RI1, PL2)]` | returns `1`; S(F1,I1)=9; ledger row for RI1 has quantity 1, `qty_before` 10, `qty_after` 9 | pass |
| PRI-P-38 | R15, R16 (storage) | side-effect | PO → storage F1. S(F1,I1)=10 @ 12.50. RI1 qty 3 with PL1; RI2 qty 4 with PL2 (both I1) | call `[(RI1, PL1), (RI2, PL2)]` | returns `2`; S(F1,I1)=3; ledger row for RI1: quantity 3, 10→7, notes end `(line 1)`; ledger row for RI2: quantity 4, 7→3, notes end `(line 2)` | pass |
| PRI-P-39 | R15, R16 (machine) | side-effect | PO → machine M1. MH(M1,I1)=10; ML(M1,I1,avg=12.50). RI1 qty 3 with PL1; RI2 qty 4 with PL2 | call `[(RI1, PL1), (RI2, PL2)]` | returns `2`; MH(M1,I1)=3; RI1 machine-ledger row `value_before` 125.00, `value_after` 87.50; RI2 row `value_before` 87.50, `value_after` 37.50; exactly two new 'purchase_returned' events for M1, with descriptions "Purchase returned: 3 units of Steel Bolt M8 to supplier" and "Purchase returned: 4 units of Steel Bolt M8 to supplier" | pass |
| PRI-P-40 | R16 (counts only posted) | side-effect | PO → storage F1. G1 chain: opening 0→12, Posted-row(storage, RI1) 12→10; S(F1,I1)=10 @ 12.50. RI1 qty 2 with PL1; RI2 qty **0** with PL2 (G4); RI3 qty 3 with PL3 whose item is **I1** | call `[(RI1, PL1), (RI2, PL2), (RI3, PL3)]` | returns `1`; S(F1,I1)=7; one ledger row for RI1 (the seeded one); none for RI2; one new row for RI3 (quantity 3, 10→7) | pass |
| PRI-P-41 | R8a (stock row differs from ledger → re-synced), R8 | side-effect | PO → storage F1. Storage ledger for F1/I1: one opening row 0→8 with `avg_price_after` 11.00 at T0. Stock row S(F1,I1) holds quantity **10**, average price **12.50** and `updated_by` U1, deliberately **not** matching the ledger. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. Ledger row for RI1: `qty_before` 8, `qty_after` 5, `unit_cost` 11.00, `total_cost` 33.00, `avg_price_before` 11.00, `avg_price_after` 11.00. Re-read stock row: quantity 5, average price 11.00, `updated_by` U2 | pass |
| PRI-P-42 | R8a (no ledger rows → 0/null, overwrite kept on failure), R9, Errors row 2 | error | PO → storage F1. Stock row S(F1,I1) = quantity 10, average price 12.50, `updated_by` U1, with **no** storage-ledger rows for F1/I1 in any workspace (the spec example). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | raises `HTTPException` 400, `detail == "Insufficient stock (0 available, 3 requested)"`. Re-read without rollback: the same stock row (same id) now reads quantity 0, average price null and `updated_by` U2; no return rows | pass |
| PRI-P-43 | R8a (latest = `performed_at`, not id) | boundary | PO → storage F1. Storage-ledger rows for F1/I1, inserted in this order: row A 0→9, `avg_price_after` 12.00, `performed_at` **T0+10min**; then row B 0→4, `avg_price_after` 8.00, `performed_at` **T0** (B has the higher id but the earlier time). Stock row S(F1,I1) = 9 @ 12.00. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. Ledger row for RI1: `qty_before` 9, `qty_after` 6, `unit_cost` 12.00. Stock row: quantity 6, average price 12.00 | pass |
| PRI-P-44 | R8a (only this workspace/factory/item/storage-type rows count) | isolation | PO → storage F1. The storage ledger for F1/I1 has an opening row 0→5 @ 12.50 at T0, and the stock row S(F1,I1) = 5 @ 12.50. Later decoy rows, each with `qty_after` and `avg_price_after` as shown: damaged-type F1/I1 at T0+1min (qty 50 @ 1.00; only the ledger row is seeded, no damaged stock row); storage F1/I2 at T0+2min (60 @ 2.00, with S(F1,I2)=60 @ 2.00); storage F1d/I1 at T0+3min (70 @ 3.00); W2 storage F2/IX at T0+4min (80 @ 4.00). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. Ledger row for RI1: `qty_before` 5, `qty_after` 2, `unit_cost` 12.50. Stock F1/I1: quantity 2, average price 12.50. S(F1,I2) still 60 | pass |
| PRI-P-45 | Side effects (a soft-deleted stock row is restored, then re-synced) | soft-delete | PO → storage F1. Seeded per G1 at 10 @ 12.50, but the stock row S(F1,I1) is **soft-deleted**. RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. Re-read: the same stock row (same id) is no longer soft-deleted, with quantity 7 and average price 12.50. There is exactly one storage-type stock row for F1/I1 (no duplicate created). The ledger row for RI1 goes 10→7 | pass |
| PRI-P-46 | R11 (most recent = `performed_at`, not id) | boundary | PO → machine M1. MH(M1,I1)=10. ML rows for M1/I1, inserted in this order: ML(avg=12.50) at `performed_at` **T0+10min**, then ML(avg=9.00) at **T0** (higher id, earlier time). RI1 qty 3 with PL2 | call `[(RI1, PL2)]` | returns `1`. Machine-ledger row for RI1: `unit_cost` 12.50, `value_before` 125.00, `value_after` 87.50, `avg_price_before` 12.50, `avg_price_after` 12.50. MH(M1,I1)=7 | pass |
| PRI-P-47 | R15a [BUG-803], R15, R16 | bug | PO → storage F1. S(F1,I1)=10 @ 12.50 (seeded per G1 at T0). RI1, RI2 and RI3 each have qty 3, paired with PL1, PL2 and PL3, **all with item I1** (PL3's item is overridden to I1) | call `[(RI1, PL1), (RI2, PL2), (RI3, PL3)]` | returns `3`. Ledger rows: RI1 10→7, RI2 7→4, RI3 **4→1**. Final stock S(F1,I1) is **1** | xfail BUG-803, `strict=False` (spec R15a test note). Fails today (not every run) on: RI3's `qty_before` == 4 and final stock == 1. Today it can re-sync from the 10→7 row and write 7→4, leaving 4. The two-line behavior that holds today is covered by P-38 |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `post_purchase_return_inventory` R17 [HR-10, BUG-800] | `PurchaseOrderService.complete_return` (locks the return row) and `app/managers/inventory_movements.py::post_stock_out` (locks the stock row) | Two concurrent completions of the same return: the second waits on the return-row lock (`SELECT … FOR UPDATE`) and then sees the return as completed, or the lines as posted. It gets the normal wrong-state result and deducts nothing. This needs a two-connection / integration test; xfail BUG-800 until the lock lands (best-practice default, delegated by reviewer). |
| BUG-801 (spec Q1) | the return-start method (e.g. `PurchaseOrderService` create/start-return) | For a PO whose destination is storage or a machine, starting a return with `quantity_returned` 1.50 raises 400: no return, no return items and no credit-note invoice are created. xfail BUG-801 there. The completion-side safety net stays covered here by PRI-P-31/33/34. |

## Spec gaps
None. The spec's Gap log (revision 2) closed the six earlier gaps:
- G1 (the storage re-sync rule): closed by R8a. Cases P-07, P-41, P-42, P-44 and P-45.
- G2 (the "most recent" ordering key): closed by R8a/R11 and the Notes. Timestamps convention, P-43, P-46, and BUG-803/R15a in P-47.
- G3 (metadata types and attribute): closed by R12. P-11 and P-14.
- G4 (rows with qty ≤ 0 persist): closed by the Notes. P-35, P-36 and P-40 persist the rows, and the unsaved-object fallback was dropped.
- G5 (cost scale and null average): closed by R8/R8b. P-04 retired, P-03 strengthened.
- G6 (R17 at this layer): deferral confirmed by the Notes. See Deferred.

## Retired IDs
- PRI-P-04: `total_cost` rounding (3.333 × 3). This cannot be seeded, because every cost column is `Numeric(15,2)` and rounding is never observable through this function (spec R8b, G5).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_machine_ledger_exists` | R1 | PRI-MLE-01, MLE-03, MLE-04 |
| `_machine_ledger_exists` | R2 | PRI-MLE-02 |
| `_machine_ledger_exists` | R3 | PRI-MLE-03 |
| `_machine_ledger_exists` | R4 | PRI-MLE-04, MLE-05 |
| `_machine_ledger_exists` | R5 | PRI-MLE-06 |
| `_storage_ledger_exists` | R1 | PRI-SLE-01, SLE-02, SLE-04, SLE-05 |
| `_storage_ledger_exists` | R2 | PRI-SLE-03 |
| `_storage_ledger_exists` | R3 | PRI-SLE-04 |
| `_storage_ledger_exists` | R4 | PRI-SLE-05 |
| `_storage_ledger_exists` | R5 | PRI-SLE-06 |
| `_location_for_po` | R1 | PRI-LOC-01, P-01 |
| `_location_for_po` | R2 | PRI-LOC-02, P-11 |
| `_location_for_po` | R3 | PRI-LOC-03, LOC-04, LOC-05, P-21, P-22 |
| `_quantity_to_int` | R1 | PRI-QTI-01, QTI-02, QTI-03 |
| `_quantity_to_int` | R2 [BUG-802] | PRI-QTI-04 (pass), QTI-05 (xfail) |
| `_quantity_to_int` | Errors: fractional quantity [BUG-802] | PRI-QTI-04, QTI-05 |
| `post_purchase_return_inventory` | R1 | PRI-P-21, P-22 |
| `post_purchase_return_inventory` | R2 | PRI-P-23 |
| `post_purchase_return_inventory` | R3 | PRI-P-24, P-25, P-26, P-27, P-40 |
| `post_purchase_return_inventory` | R4 | PRI-P-28 |
| `post_purchase_return_inventory` | R5 | PRI-P-29, P-30 |
| `post_purchase_return_inventory` | R6 [BUG-802] | PRI-P-31, P-33, P-34 (pass), P-32 (xfail) |
| `post_purchase_return_inventory` | R7 | PRI-P-35, P-36, P-37, P-40 |
| `post_purchase_return_inventory` | R8 | PRI-P-01, P-02, P-03, P-41 |
| `post_purchase_return_inventory` | R8a | PRI-P-41, P-42, P-43, P-44, P-07 |
| `post_purchase_return_inventory` | R8b | PRI-P-01 (exact 2-decimal `total_cost`; rounding is unobservable per spec, see Retired IDs) |
| `post_purchase_return_inventory` | R9 | PRI-P-05, P-06, P-07, P-42 |
| `post_purchase_return_inventory` | R10 | PRI-P-08, P-09, P-10 |
| `post_purchase_return_inventory` | R11 | PRI-P-11, P-12, P-13, P-39, P-46 |
| `post_purchase_return_inventory` | R12 | PRI-P-11, P-14, P-20, P-39 |
| `post_purchase_return_inventory` | R13 | PRI-P-15, P-16, P-17 |
| `post_purchase_return_inventory` | R14 | PRI-P-18, P-19, P-20 |
| `post_purchase_return_inventory` | R15 | PRI-P-38, P-39 |
| `post_purchase_return_inventory` | R15a [BUG-803] | PRI-P-47 (xfail, strict=False); the two-line part that holds today is covered by P-38 |
| `post_purchase_return_inventory` | R16 | PRI-P-01, P-11, P-24, P-38, P-39, P-40, P-47 |
| `post_purchase_return_inventory` | R17 [HR-10, BUG-800] | Deferred (`PurchaseOrderService.complete_return`), per spec Notes (G6) |
| `post_purchase_return_inventory` | Side effects: missing stock row / placement created (qty 0) | PRI-P-07, P-17 |
| `post_purchase_return_inventory` | Side effects: soft-deleted stock row restored then re-synced | PRI-P-45 |
| `post_purchase_return_inventory` | Side effects: re-sync writes `updated_by` only on change | PRI-P-41, P-42 (changed → U2); P-06, P-21, P-23 (unchanged → U1) |
| `post_purchase_return_inventory` | Errors: fractional quantity [BUG-802] | PRI-P-31, P-32, P-33, P-34 |
| `post_purchase_return_inventory` | Errors: storage stock below quantity | PRI-P-06, P-07, P-42 |
| `post_purchase_return_inventory` | Errors: machine stock below quantity | PRI-P-16, P-17 |
| `post_purchase_return_inventory` | Errors: factory not in workspace | PRI-P-08, P-09 |
| `post_purchase_return_inventory` | Errors: machine not in workspace | PRI-P-18, P-19 |
| (spec Q1) | BUG-801 | Deferred (return-start module) |
