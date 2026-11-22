# Test cases — `app/managers/po_receive_inventory.py`

> **Spec:** `tests/unit/managers/po_receive_inventory.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 — spec unchanged (Gap log still G1–G5). Addresses verify.md finding 1 (case-missing; surviving mutants #77, #83, #85, #91, #96, #98, #103): no case used a delta of exactly ±1, so the `qty <= 0`, `delta == 0` and `delta > 0` boundaries were checked on one side only. Added PRI-D-05 (`±1` → 1), PRI-P-34 (`+1` receive → stock-in 1), PRI-P-35 (`−1` correction → stock-out 1), PRI-RE-21 (reverse a posted `+1` → stock-out 1) and PRI-RE-22 (reverse a posted `−1` → stock-in 1). Each asserts direction (`transaction_type`, `qty_before`/`qty_after`), so a 1-unit delta that is dropped or sent the wrong way fails. Also clarified `pending-return` in Conventions (verify finding 2, routed to executor): the parent return is set up exactly as for `return(…)`, so the missing ledger row is the only reason it is not netted. No other row changed.
> **Revision (history):** 4 — spec unchanged since revision 3 (no verify.md yet). The full self-check found two named BUG-682 boundaries that were tested on one side only, so two cases were added: PRI-V-17 (pass) checks a return ledger row in the wrong ledger or the wrong workspace, which is not netted, the other side of spec R6a's "same workspace, same ledger" definition. PRI-V-18 (xfail BUG-682) checks R7's "never negative" when more was returned than received. No other row changed.
> **Revision (history):** 3 — spec Gap log G1–G5 closed all 5 earlier gaps (R1a losers raise `IntegrityError`; R6a netting tested only through `reverse_po_receive_inventory` R7; "completed return" definition; reversal R3 re-tagged BUG-683; plain-integer stock numbers).
> **Counts:** 120 cases · 101 expected-to-pass · 19 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `_delta_to_int` 5 · `_ledger_exists` 5 · `_storage_ledger_exists` 3 · `_machine_ledger_exists` 3 · `_location_for_po` 4 · `_post_event_item_delta` 35 (4 bug) · `post_receive_event_inventory` 6 · `_reverse_event_item_posting` 22 (4 bug) · `_reverse_legacy_line_posting` 15 (3 bug) · `reverse_po_receive_inventory` 18 (6 bug) · database index (BUG-680) 4 (2 bug)
- **Notable design choices:**
  - Race simulations (BUG-680, R1a): the existence helpers are patched **selectively**: only the "already posted/reversed" source type answers `False`. A blanket `False` would also trip the "never posted" check (R2) and the case would return early without reaching the index.
  - At manager level the duplicate insert is expected to raise `sqlalchemy.exc.IntegrityError`. Turning that into 409 is the global handler's job (BUG-462) and is deferred to that module (best-practice default, delegated by reviewer).
  - BUG-682 (void nets out returns) is tested only through `reverse_po_receive_inventory`, as the spec now states (R6a, G2): the new keyword parameter's name is left to the fix.
  - A completed return is set up as a `PurchaseOrderReturnItem` row plus a matching `purchase_return_item` ledger row (spec R6a / Notes, G3). A return item is not netted when that ledger row is missing (PRI-V-10), in the other ledger, or in another workspace (PRI-V-17). Over-return (12 returned of 10 received) is expected to remove nothing (PRI-V-18, R7 "never negative").
  - Reversal R3 is now itself tagged BUG-683 (spec G4): a PO later changed to `project` still reverses at the recorded location, so PRI-RE-20 / PRI-RL-15 are xfail and R3 has no passing case (today's behavior is the bug).
  - Smallest whole delta: every direction rule (receive, correction, reversal of each) also has a case with a delta of exactly `±1` (PRI-D-05, P-34, P-35, RE-21, RE-22), the other side of the `0` boundaries next to the 5/3-unit cases.
  - BUG-681's fix lives in the PO schemas and is deferred there. This module's exact comparison is tested as unchanged.
- **Needs a decision:** None. The 5 earlier gaps are closed in the spec's Gap log (G1–G5); no new gaps.

## Conventions for this module

**IDs.** `PRI` = po_receive_inventory. Method codes: `D` `_delta_to_int` · `LE` `_ledger_exists` · `SLE` `_storage_ledger_exists` · `MLE` `_machine_ledger_exists` · `LOC` `_location_for_po` · `P` `_post_event_item_delta` · `PR` `post_receive_event_inventory` · `RE` `_reverse_event_item_posting` · `RL` `_reverse_legacy_line_posting` · `V` `reverse_po_receive_inventory` · `IDX` database uniqueness (BUG-680, no callable).

**Actors and places.**
- W1, W2 are two workspaces. U1 is a profile acting in W1. Every call uses `workspace_id=W1, user_id=U1` unless the case says otherwise.
- Items in W1: X = "Hex Bolt" and Y = "Flat Washer". Xd = "Old Gasket", soft-deleted item in W1. Z2 = "Foreign Nut", item in W2.
- Factories: A and B = live factories in W1. Ad = soft-deleted factory in W1. F2 = factory in W2.
- Machines: M1 and M2 = live machines in W1. Md = soft-deleted machine in W1. M9 = machine in W2.
- P = purchase order in W1 with `po_number "PO-2026-004"`. Its destination is given per case as `storage:A`, `machine:M1`, `project:<any id>`, etc. P2 = another PO in W1 (`"PO-2026-099"`).
- Lines of P: L1 = line_number 1, item X, `unit_price 26.00`. L2 = line_number 2, item Y, `unit_price 4.00`. Case-specific lines are described inline.
- Receive events: E1, E2 … = receive events of P in W1. `created_at` is set explicitly: E1 = T2, E2 = T3, … (strictly increasing) unless stated. Receive lines are written `E1.a = (L1, +5)`, meaning a `PoReceiveEventItem` of E1 for PO line L1 with `quantity_delta Decimal('5')`, flushed so it has an id.
- Times: T0 = `2026-01-01 08:00`, T1 = `2026-01-01 09:00`, T2 = `2026-02-01 10:00`, T3 = `2026-02-02 10:00`, T4 = `2026-02-03 10:00`.

**Stock shorthands (all rows inserted directly, in the order written).**
- `posted(E1.a → A, n)` = `inventory_ledger` row: W1, `inventory_type STORAGE`, factory A, the line's item, `quantity n`, `source_type 'po_receive_event_item'`, `source_id = E1.a.id`, `performed_at T0`. `posted(E1.a → M1, n)` = the same in `machine_item_ledger` for machine M1.
- `legacy(L1 → A, n)` / `legacy(L1 → M1, n)` = the same, but `source_type 'purchase_order'` and `source_id = L1.id`.
- `reversed(E1.a @ A)` = `inventory_ledger` row with `source_type 'po_receive_event_item_reversal'`, `source_id = E1.a.id`, W1 (or the workspace given). `legacy-reversed(L1 @ A)` = the same with `'purchase_order_reversal'` and `L1.id`. The `@ M1` forms are the same rows in `machine_item_ledger`.
- `stock(A, X) = q @ a` = an `inventories` row (W1, A, X, STORAGE, `qty q`, `avg_price a`, `updated_by` U2), plus a seed `inventory_ledger` row for A/X/STORAGE with `qty_after q`, `avg_price_after a`, `source_type 'test_seed'`, `performed_at T1`. The seed row is inserted **after** every other ledger row of the case, so it is the latest by both id and time. `a` may be `NULL`.
- `mstock(M1, X) = q @ a` = a `machine_items` row (M1, X, `qty q`), plus a seed `machine_item_ledger` row for M1/X with `qty_after q`, `avg_price_after a`, `source_type 'test_seed'`, `performed_at T1`, inserted last.
- `return(L1, n)` = a completed purchase return of n units on L1. It is a `PurchaseOrderReturnItem` (with whatever parent return row it needs, in W1, for PO P) with `po_item_id = L1.id` and `quantity_returned n`, plus the matching stock-out ledger row in the **same ledger and location as L1's original posting**: `source_type 'purchase_return_item'`, `source_id = <return item id>`, `quantity n` (spec R6a / Notes, G3). The stated `stock(…)` already reflects the return. `pending-return(L1, n)` = the return item only, with no ledger row, so it is not completed. Its parent return row is set up **exactly as for `return(…)`** (if the parent has a status column, it is `'completed'`, never `'pending'`), so the missing ledger row is the only thing that stops netting (spec R6a: the parent status is not consulted).

**Externals.** None are mocked (spec: "Externals to mock: none"). Stock mechanics run for real.

**Race simulations (BUG-680 R1a only).** Only these cases patch the module's own existence helpers, `app.managers.po_receive_inventory._storage_ledger_exists` and `app.managers.po_receive_inventory._machine_ledger_exists`. The patches are **selective**: a side effect that returns `False` when `source_type` equals the named type and calls the real function otherwise.
- PRI-P-30, PRI-P-31: type `'po_receive_event_item'` (`_post_event_item_delta` R1a)
- PRI-RE-17: type `'po_receive_event_item_reversal'` (`_reverse_event_item_posting` R1a)
- PRI-RL-14: type `'purchase_order_reversal'` (`_reverse_legacy_line_posting` R1a)

In these cases the call is wrapped as `with pytest.raises(IntegrityError): with session.begin_nested(): <call>`. The savepoint is then rolled back and everything is re-read with fresh queries.

**Checking results.**
- "re-read" = `session.expire_all()` followed by fresh SELECTs.
- "New ledger rows" = rows in `inventory_ledger` / `machine_item_ledger` whose id is greater than the max id before the call.
- "Nothing written" means all of the following:
  - no new rows in either ledger;
  - no new machine activity events;
  - every `inventories` / `machine_items` row from Given has unchanged `qty`, `avg_price` and `updated_by`;
  - where the case says so, no new `inventories` / `machine_items` row exists.
- Money and quantity columns are compared as `Decimal` with 2 dp (`Decimal('22.00')`). Integer-valued quantities are compared numerically (`== 5`).
- "Ledger row = {…}" lists the columns to assert exactly. `NULL` means `is None`.
- Errors: `HTTPException` (FastAPI). Assert `status_code` and `detail` exactly. Numbers in insufficient-stock messages are plain integers, as the spec states (`_post_event_item_delta` R10 and Notes, G5: `7 available, 10 requested`).
- "Activity event" = the machine activity event row. Assert `event_type`, `description`, `performed_by` and (where given) metadata. The metadata `quantity` is compared numerically.
- When the item name is used in text: X → "Hex Bolt".

**Strict-xfail determinism.** Every xfail case below fails today on a named assertion that is deterministic. None depends on query order.

## `_delta_to_int` (5 cases)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-D-01 | R1 | happy | — | parametrized: `_delta_to_int(Decimal('5'), line_number=7)`; `_delta_to_int(Decimal('5.0000'), line_number=7)` | returns `5` (type `int`) | pass |
| PRI-D-02 | R2 | happy | — | `_delta_to_int(Decimal('-3'), line_number=7)` | returns `3` (type `int`) | pass |
| PRI-D-03 | R3 | boundary | — | parametrized: `Decimal('0')`, `Decimal('-0')`, `Decimal('0.0000')`, each with `line_number=7` | returns `0`; no exception | pass |
| PRI-D-04 | R4; Errors row 1 | error | — | parametrized: `Decimal('2.5')`, `Decimal('-0.5')`, `Decimal('1.0001')`, each with `line_number=7` | raises HTTPException 400, detail `Line 7 has a fractional quantity delta; inventory requires whole units` | pass |
| PRI-D-05 | R1, R2, R3 (smallest non-zero whole delta: other side of the zero boundary) | boundary | — | parametrized: `_delta_to_int(Decimal('1'), line_number=7)`; `_delta_to_int(Decimal('-1'), line_number=7)` | returns `1` (type `int`) for each; no exception | pass |

## `_ledger_exists` (5 cases), with `model = MachineItemLedger`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-LE-01 | R1, R4 | happy | two `machine_item_ledger` rows in W1 (M1, X), both `source_type 'po_receive_event_item'`, `source_id 501` | `_ledger_exists(session, workspace_id=W1, source_type='po_receive_event_item', source_id=501, model=MachineItemLedger)` | returns `True` | pass |
| PRI-LE-02 | R2 | isolation | one `machine_item_ledger` row in **W2** (M9, Z2), `'po_receive_event_item'`, `source_id 501` | same call with `workspace_id=W1` | returns `False`; the same call with `workspace_id=W2` returns `True` | pass |
| PRI-LE-03 | R3 | boundary | one W1 row: `'po_receive_event_item'`, `source_id 501` | parametrized: (`'po_receive_event_item_reversal'`, 501); (`'po_receive_event_item'`, 502); (`'PO_RECEIVE_EVENT_ITEM'`, 501) | returns `False` for each | pass |
| PRI-LE-04 | R1 | boundary | `machine_item_ledger` empty for W1 | call with `'po_receive_event_item'`, 501 | returns `False` | pass |
| PRI-LE-05 | R1 | boundary | only an `inventory_ledger` row (A, X, STORAGE) in W1: `'po_receive_event_item'`, 501 | call with `model=MachineItemLedger` | returns `False` (only the given model's table is read) | pass |

## `_storage_ledger_exists` (3 cases)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-SLE-01 | R1 | happy | `inventory_ledger` row W1, A, X, `inventory_type STORAGE`, `'po_receive_event_item'`, 601 | `_storage_ledger_exists(session, workspace_id=W1, source_type='po_receive_event_item', source_id=601)` | returns `True` | pass |
| PRI-SLE-02 | R1 | boundary | `inventory_ledger` row W1, A, X, `inventory_type DAMAGED`, `'po_receive_event_item'`, 601 (no STORAGE row) | same call | returns `True` (any inventory type counts) | pass |
| PRI-SLE-03 | R1 (→ LE R2, R3) | isolation | rows: W2 F2 STORAGE `'po_receive_event_item'` 601; W1 A STORAGE `'purchase_order'` 601; W1 A STORAGE `'po_receive_event_item'` 602; a `machine_item_ledger` row W1 M1 `'po_receive_event_item'` 601 | same call (W1, `'po_receive_event_item'`, 601) | returns `False` | pass |

## `_machine_ledger_exists` (3 cases)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-MLE-01 | R1 | happy | `machine_item_ledger` row W1, M1, X, `'purchase_order'`, 701 | `_machine_ledger_exists(session, workspace_id=W1, source_type='purchase_order', source_id=701)` | returns `True` | pass |
| PRI-MLE-02 | R1 (→ LE R2, R3) | isolation | rows: W2 M9 `'purchase_order'` 701; W1 M1 `'purchase_order_reversal'` 701; W1 M1 `'purchase_order'` 702 | same call | returns `False` | pass |
| PRI-MLE-03 | R1 | boundary | only an `inventory_ledger` row W1 A STORAGE `'purchase_order'` 701 | same call | returns `False` | pass |

## `_location_for_po` (4 cases)

`po` is an unsaved `PurchaseOrder` with only `destination_type` / `destination_id` set.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-LOC-01 | R1 | happy | `destination_type 'storage'`, `destination_id 42` | `_location_for_po(po)` | returns `('storage', 42)` | pass |
| PRI-LOC-02 | R2 | happy | `'machine'`, 43 | call | returns `('machine', 43)` | pass |
| PRI-LOC-03 | R3 | happy | `'project'`, 44 | call | returns `None` | pass |
| PRI-LOC-04 | R3 (BUG-681 note: this module's comparison stays exact) | boundary | parametrized `destination_type`: `'Storage'`, `'storage '`, `'MACHINE'`, `''`, `'factory'`; `destination_id 45` | call | returns `None` for each | pass |

## `_post_event_item_delta` (35 cases)

Default: P destination `storage:A`, line L1, receive event E1 (T2). The call is `_post_event_item_delta(session, po=P, event_item=E1.a, po_line=L1, workspace_id=W1, user_id=U1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-P-01 | R6 | happy | P `storage:A`; `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, +5)` | call | returns `True`; exactly 1 new ledger row, in `inventory_ledger`, = {workspace W1, `inventory_type STORAGE`, `factory_id A`, `item_id X`, `transaction_type 'purchase_order'`, `quantity 5`, `unit_cost 26.00`, `total_cost 130.00`, `qty_before 10`, `qty_after 15`, `avg_price_before 20.00`, `avg_price_after 22.00`, `source_type 'po_receive_event_item'`, `source_id E1.a.id`, `transfer_source_type NULL`, `transfer_source_id NULL`, `notes "PO PO-2026-004 line 1 (receive event #<E1.a.id>)"`, `performed_by U1`}; re-read `inventories` (A, X, STORAGE): `qty 15`, `avg_price 22.00`, `updated_by U1`; no `machine_item_ledger` row and no activity event | pass |
| PRI-P-02 | R6 (Notes: row created if missing) | side-effect | P `storage:A`; no `inventories` row and no ledger row for A/X; `E1.a = (L1, +5)` | call | returns `True`; new `inventory_ledger` row: `qty_before 0`, `qty_after 5`, `avg_price_before NULL`, `avg_price_after 26.00`, `unit_cost 26.00`, `total_cost 130.00`; re-read: exactly one `inventories` row for (W1, A, X, STORAGE) with `qty 5`, `avg_price 26.00`, `updated_by U1` | pass |
| PRI-P-03 | R6 (Notes: avg rounded to 0.01) | boundary | P `storage:A`; `stock(A, X) = 10 @ 20.00`; L1 `unit_price 21.00`; `E1.a = (L1, +3)` | call | returns `True`; new row `avg_price_before 20.00`, `avg_price_after 20.23` ((200 + 63) / 13 = 20.2307…); `total_cost 63.00`; re-read stock `qty 13`, `avg_price 20.23` | pass |
| PRI-P-04 | R6 (Notes: ledger wins, soft-deleted row restored) | side-effect | P `storage:A`; an `inventories` row (A, X, STORAGE) with `qty 99`, `avg_price 1.00`, `is_deleted True`; then the seed ledger row for A/X/STORAGE with `qty_after 10`, `avg_price_after 20.00` (latest); `E1.a = (L1, +5)` | call | returns `True`; new row `qty_before 10`, `qty_after 15`, `avg_price_before 20.00`, `avg_price_after 22.00`; re-read: that same `inventories` row (same id) has `is_deleted False`, `qty 15`, `avg_price 22.00`; still one `inventories` row for (W1, A, X, STORAGE) | pass |
| PRI-P-05 | R7, R11 | happy | P `machine:M1`; `mstock(M1, X) = 10 @ 20.00`; `E1.a = (L1, +5)` | call | returns `True`; exactly 1 new ledger row, in `machine_item_ledger`, = {W1, `machine_id M1`, `item_id X`, `transaction_type 'purchase_order'`, `quantity 5`, `unit_cost 26.00`, `total_cost 130.00`, `qty_before 10`, `qty_after 15`, `avg_price_before 20.00`, `avg_price_after 22.00`, `value_before 200.00`, `value_after 330.00`, `source_type 'po_receive_event_item'`, `source_id E1.a.id`, `notes "PO PO-2026-004 line 1 (receive event #<E1.a.id>)"`, `performed_by U1`}; re-read `machine_items` (M1, X) `qty 15`; exactly 1 new activity event for M1 = {`event_type 'purchase_received'`, `description "Purchase received: 5 units of Hex Bolt from PO PO-2026-004"`, `performed_by U1`, metadata `{"item_id": X.id, "item_name": "Hex Bolt", "quantity": 5}`, no `work_order_id` key}; no new `inventory_ledger` row | pass |
| PRI-P-06 | R7 (old average ignored when stock 0) | boundary | P `machine:M1`; `mstock(M1, X) = 0 @ 99.00`; `E1.a = (L1, +5)` | call | returns `True`; new machine row `qty_before 0`, `qty_after 5`, `avg_price_before 99.00`, `avg_price_after 26.00`, `value_before 0.00`, `value_after 130.00`; re-read `machine_items` `qty 5` | pass |
| PRI-P-07 | R7 (Notes: machine item created; cost 0 without ledger) | side-effect | P `machine:M1`; no `machine_items` row and no machine ledger row for M1/X; `E1.a = (L1, +5)` | call | returns `True`; new machine row `qty_before 0`, `qty_after 5`, `avg_price_before 0.00`, `avg_price_after 26.00`, `value_before 0.00`, `value_after 130.00`; re-read: exactly one `machine_items` row (M1, X) with `qty 5` | pass |
| PRI-P-08 | R7 (Notes: current cost = latest by `performed_at`) | boundary | P `machine:M1`; `machine_items` (M1, X) `qty 10`; machine ledger rows for M1/X inserted in this order: row R_new {`performed_at T1`, `qty_after 10`, `avg_price_after 20.00`}, then row R_old {`performed_at T0`, `qty_after 10`, `avg_price_after 50.00`}; `E1.a = (L1, +5)` | call | returns `True`; new machine row `avg_price_before 20.00` (from R_new, not the last-inserted R_old), `avg_price_after 22.00`, `value_before 200.00` | pass |
| PRI-P-09 | R8 | happy | P `storage:A`; `posted(E1.a → A, 5)` (E1 at T2); `stock(A, X) = 10 @ 20.00`; E2 (T3) `E2.a = (L1, −3)` | call with `event_item=E2.a` | returns `True`; exactly 1 new `inventory_ledger` row = {STORAGE, `factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 3`, `unit_cost 20.00`, `total_cost 60.00`, `qty_before 10`, `qty_after 7`, `avg_price_before 20.00`, `avg_price_after 20.00`, `source_type 'po_receive_event_item'`, `source_id E2.a.id`, `transfer_destination_type NULL`, `transfer_destination_id NULL`, `notes "PO PO-2026-004 line 1 (receive event #<E2.a.id>) — quantity correction"`, `performed_by U1`}; re-read stock `qty 7`, `avg_price 20.00`, `updated_by U1` | pass |
| PRI-P-10 | R8 (bucket avg NULL → cost 0) | boundary | P `storage:A`; `stock(A, X) = 5 @ NULL`; `E2.a = (L1, −2)` | call with `E2.a` | returns `True`; new row `unit_cost 0.00`, `total_cost 0.00`, `quantity 2`, `qty_before 5`, `qty_after 3`; re-read stock `qty 3` | pass |
| PRI-P-11 | R9 | happy | P `machine:M1`; `mstock(M1, X) = 10 @ 20.00`; `E2.a = (L1, −3)` | call with `E2.a` | returns `True`; exactly 1 new `machine_item_ledger` row = {`machine_id M1`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 3`, `unit_cost 20.00`, `total_cost 60.00`, `qty_before 10`, `qty_after 7`, `avg_price_before 20.00`, `avg_price_after 20.00`, `value_before 200.00`, `value_after 140.00`, `source_type 'po_receive_event_item'`, `source_id E2.a.id`, `notes "PO PO-2026-004 line 1 (receive event #<E2.a.id>) — quantity correction"`, `performed_by U1`}; re-read `machine_items` `qty 7`; 1 new activity event {`event_type 'purchase_correction'`, `description "Receiving correction: 3 units of Hex Bolt removed from PO PO-2026-004"`, `performed_by U1`} | pass |
| PRI-P-12 | R10; Errors row 4 | error | P `storage:A`; `stock(A, X) = 2 @ 20.00`; `E2.a = (L1, −3)` | call with `E2.a` | raises HTTPException 400, detail `Insufficient stock (2 available, 3 requested)`; no new ledger row; re-read stock `qty 2`, `avg_price 20.00` | pass |
| PRI-P-13 | R10 | boundary | P `storage:A`; `stock(A, X) = 3 @ 20.00`; `E2.a = (L1, −3)` | call with `E2.a` | returns `True`; new row `qty_before 3`, `qty_after 0`; re-read stock `qty 0` | pass |
| PRI-P-14 | R10; Errors row 5 | error | P `machine:M1`; `mstock(M1, X) = 2 @ 20.00`; `E2.a = (L1, −3)` | call with `E2.a` | raises HTTPException 400, detail `Insufficient machine stock (2 available, 3 requested)`; no new ledger row; no new activity event; re-read `machine_items` `qty 2` | pass |
| PRI-P-15 | R10 | boundary | P `machine:M1`; `mstock(M1, X) = 3 @ 20.00`; `E2.a = (L1, −3)` | call with `E2.a` | returns `True`; new machine row `qty_after 0`; re-read `machine_items` `qty 0`; 1 `'purchase_correction'` activity event | pass |
| PRI-P-16 | R1 | happy | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `stock(A, X) = 5 @ 26.00` | call | returns `False`; nothing written (still exactly one `inventory_ledger` row with source `'po_receive_event_item'`/`E1.a.id`) | pass |
| PRI-P-17 | R1 (either ledger) | boundary | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → M1, 5)` (machine ledger only); `stock(A, X) = 10 @ 20.00` | call | returns `False`; nothing written; stock A/X `qty 10` | pass |
| PRI-P-18 | R1 (other workspace) | isolation | P `storage:A`; `E1.a = (L1, +5)`; an `inventory_ledger` row in **W2** (F2, Z2) with `source_type 'po_receive_event_item'`, `source_id E1.a.id`; `stock(A, X) = 10 @ 20.00` | call | returns `True`; one new W1 `inventory_ledger` row for `E1.a.id`; re-read stock `qty 15`; the W2 row is unchanged | pass |
| PRI-P-19 | R2 | happy | P `project:77`; `E1.a = (L1, +5)` | call | returns `False`; nothing written; no `inventories` or `machine_items` row created in W1 | pass |
| PRI-P-20 | R2 (even fractional) | boundary | P `project:77`; `E1.a = (L1, Decimal('2.5'))` | call | returns `False` (no exception); nothing written | pass |
| PRI-P-21 | R2 (BUG-681 note: module compares exactly) | boundary | P `destination_type 'Storage'`, `destination_id A`; `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, +5)` | call | returns `False`; nothing written; stock A/X `qty 10` | pass |
| PRI-P-22 | R3 | boundary | P `storage:A`; no `inventories` row for A/X; `E1.a = (L1, Decimal('0'))` | call | returns `False`; nothing written; no `inventories` row for (A, X) created | pass |
| PRI-P-23 | R4; Errors row 1 | error | P `storage:A`; `stock(A, X) = 10 @ 20.00`; L1 is line_number 3 for this case; `E1.a = (L1, Decimal('2.5'))` | call | raises HTTPException 400, detail `Line 3 has a fractional quantity delta; inventory requires whole units`; nothing written | pass |
| PRI-P-24 | R5; Errors row 6 | error | P `storage:A`; `stock(A, X) = 10 @ 20.00`; L1 with `unit_price NULL` | parametrized: `E1.a = (L1, +5)`; `E1.a = (L1, −3)` | raises `decimal.InvalidOperation` (not `HTTPException`); nothing written (stock `qty 10`, `avg_price 20.00`) | pass |
| PRI-P-25 | R11 (soft-deleted item name) | side-effect | P `machine:M1`; line Ld = line_number 1, item Xd ("Old Gasket"), `unit_price 10.00`; `mstock(M1, Xd) = 0 @ NULL`; `E1.a = (Ld, +2)` | call with `po_line=Ld` | returns `True`; activity description `"Purchase received: 2 units of Old Gasket from PO PO-2026-004"`; metadata `item_name "Old Gasket"` | pass |
| PRI-P-26 | R11 (item not in workspace) | side-effect | P `machine:M1`; line Lz = line_number 1, item Z2 (W2), `unit_price 10.00`; `E1.a = (Lz, +2)` | call with `po_line=Lz` | returns `True`; activity description `"Purchase received: 2 units of Item #<Z2.id> from PO PO-2026-004"`; metadata `item_name "Item #<Z2.id>"`, `item_id Z2.id` | pass |
| PRI-P-27 | R12; Errors row 2 | error | parametrized P destination: `storage:999999` (no such factory); `storage:F2` (W2 factory); `E1.a = (L1, +5)` | call | raises HTTPException 404, detail `Factory with ID <id> not found` (id = 999999 / F2.id); nothing written; no `inventories` row created for that factory id | pass |
| PRI-P-28 | R12; Errors row 3 | error | parametrized P destination: `machine:999999`; `machine:M9` (W2 machine); `E1.a = (L1, +5)` | call | raises HTTPException 404, detail `Machine with ID <id> not found`; nothing written; no `machine_items` row created for that machine id | pass |
| PRI-P-29 | R12a; Errors row 7 [BUG-684] | bug | P `storage:Ad` (soft-deleted factory in W1); `E1.a = (L1, +5)` | call | raises HTTPException 400, detail `Factory with ID <Ad.id> has been deleted`; nothing written; no `inventories` row for (Ad, X) | xfail BUG-684 — fails today on: no exception raised (stock posted into Ad) |
| PRI-P-32 | R12a; Errors row 7 [BUG-684] | bug | P `machine:Md` (soft-deleted machine in W1); `E1.a = (L1, +5)` | call | raises HTTPException 400, detail `Machine with ID <Md.id> has been deleted`; nothing written; no `machine_items` row for (Md, X); no activity event | xfail BUG-684 — fails today on: no exception raised |
| PRI-P-30 | R1a; Errors row 8 [BUG-680] | bug | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `stock(A, X) = 5 @ 26.00`; race simulation for `'po_receive_event_item'` (see Conventions) | inside `session.begin_nested()`: call | raises `sqlalchemy.exc.IntegrityError`; after the savepoint is rolled back, re-read: exactly one `inventory_ledger` row with `'po_receive_event_item'`/`E1.a.id` in W1; stock A/X `qty 5` | xfail BUG-680 — fails today on: no exception raised (second posting row written) |
| PRI-P-31 | R1a; Errors row 8 [BUG-680] | bug | P `machine:M1`; `E1.a = (L1, +5)`; `posted(E1.a → M1, 5)`; `mstock(M1, X) = 5 @ 26.00`; race simulation for `'po_receive_event_item'` | inside `session.begin_nested()`: call | raises `IntegrityError`; after rollback, re-read: exactly one `machine_item_ledger` row with that source; `machine_items` `qty 5` | xfail BUG-680 — fails today on: no exception raised |
| PRI-P-33 | R6 (workspace scoping of rows written) | isolation | P `storage:A`; `stock(A, X) = 10 @ 20.00`; F2 in W2 has an `inventories` row for Z2 `qty 4` | call with `E1.a = (L1, +5)` | returns `True`; the new ledger row has `workspace_id W1`; the W2 `inventories` row is unchanged (`qty 4`) | pass |
| PRI-P-34 | R3, R6 (smallest positive delta `+1`: other side of `delta == 0`; `> 0` → stock-in) | boundary | P `storage:A`; `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, +1)` (L1 `unit_price 26.00`) | call | returns `True`; exactly 1 new ledger row, in `inventory_ledger`, = {`factory_id A`, `item_id X`, `transaction_type 'purchase_order'`, `quantity 1`, `unit_cost 26.00`, `total_cost 26.00`, `qty_before 10`, `qty_after 11`, `avg_price_before 20.00`, `avg_price_after 20.55` ((200 + 26) / 11 = 20.5454…), `source_type 'po_receive_event_item'`, `source_id E1.a.id`, `performed_by U1`}; re-read stock A/X `qty 11`, `avg_price 20.55`, `updated_by U1`; no new `machine_item_ledger` row | pass |
| PRI-P-35 | R3, R8 (smallest negative delta `−1`: other side of `delta == 0`; `< 0` → stock-out) | boundary | P `storage:A`; `stock(A, X) = 10 @ 20.00`; E2 (T3) `E2.a = (L1, −1)` | call with `event_item=E2.a` | returns `True`; exactly 1 new ledger row, in `inventory_ledger`, = {`factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 1`, `unit_cost 20.00`, `total_cost 20.00`, `qty_before 10`, `qty_after 9`, `avg_price_before 20.00`, `avg_price_after 20.00`, `source_type 'po_receive_event_item'`, `source_id E2.a.id`, `notes "PO PO-2026-004 line 1 (receive event #<E2.a.id>) — quantity correction"`, `performed_by U1`}; re-read stock A/X `qty 9`, `avg_price 20.00`, `updated_by U1` | pass |

## `post_receive_event_inventory` (6 cases)

The call is `post_receive_event_inventory(session, P, pairs, W1, U1)`. P is `storage:A` unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-PR-01 | R1 | happy | `stock(A, X) = 10 @ 20.00`; no stock for A/Y; `E1.a = (L1, +5)`, `E1.b = (L2, +3)` | `pairs = [(E1.a, L1), (E1.b, L2)]` | returns `2`; exactly 2 new `inventory_ledger` rows, the one for `E1.a.id` having the lower id; re-read stock A/X `qty 15`, `avg_price 22.00`; A/Y `qty 3`, `avg_price 4.00` | pass |
| PRI-PR-02 | R1 (count only `True`) | happy | `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, 0)`, `E1.b = (L2, +3)` | `pairs = [(E1.a, L1), (E1.b, L2)]` | returns `1`; one new ledger row (source `E1.b.id`); stock A/X `qty 10` | pass |
| PRI-PR-03 | R2 | boundary | `stock(A, X) = 10 @ 20.00` | `pairs = []` | returns `0`; nothing written | pass |
| PRI-PR-04 | R3 | boundary | `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, +5)` | `pairs = [(E1.a, L1), (E1.a, L1)]` | returns `1`; exactly one ledger row with source `E1.a.id`; stock `qty 15` | pass |
| PRI-PR-05 | R4 | error | `stock(A, X) = 10 @ 20.00`; `E1.a = (L1, +5)`, `E1.b = (L2, Decimal('1.5'))` | `pairs = [(E1.a, L1), (E1.b, L2)]` | raises HTTPException 400, detail `Line 2 has a fractional quantity delta; inventory requires whole units`; in the same session (without rollback): the `inventory_ledger` row for `E1.a.id` exists and stock A/X `qty 15`; no ledger row for `E1.b.id` | pass |
| PRI-PR-06 | R1 (→ P R2) | boundary | P `project:77`; `E1.a = (L1, +5)`, `E1.b = (L2, +3)` | `pairs = [(E1.a, L1), (E1.b, L2)]` | returns `0`; nothing written | pass |

## `_reverse_event_item_posting` (22 cases)

The call is `_reverse_event_item_posting(session, po=P, event_item=E1.a, po_line=L1, workspace_id=W1, user_id=U1)`. It is called directly, with today's signature and no returns present (R6a's netting is tested only through `reverse_po_receive_inventory`, per spec R6a).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-RE-01 | R6, R9 (same location) | happy | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `stock(A, X) = 15 @ 22.00` | call | returns `True`; exactly 1 new `inventory_ledger` row = {STORAGE, `factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 5`, `unit_cost 22.00`, `total_cost 110.00`, `qty_before 15`, `qty_after 10`, `avg_price_before 22.00`, `avg_price_after 22.00`, `source_type 'po_receive_event_item_reversal'`, `source_id E1.a.id`, `notes "PO PO-2026-004 voided — reverse receive event #<E1.a.id> line 1"`, `performed_by U1`}; re-read stock `qty 10`, `avg_price 22.00`, `updated_by U1` | pass |
| PRI-RE-02 | R6 | happy | P `machine:M1`; `E1.a = (L1, +5)`; `posted(E1.a → M1, 5)`; `mstock(M1, X) = 15 @ 22.00` | call | returns `True`; exactly 1 new `machine_item_ledger` row = {`machine_id M1`, `transaction_type 'inventory_adjustment'`, `quantity 5`, `unit_cost 22.00`, `total_cost 110.00`, `qty_before 15`, `qty_after 10`, `avg_price_before 22.00`, `avg_price_after 22.00`, `value_before 330.00`, `value_after 220.00`, `source_type 'po_receive_event_item_reversal'`, `source_id E1.a.id`, same notes as RE-01, `performed_by U1`}; `machine_items` `qty 10`; 1 activity event {`'purchase_reversed'`, `"PO PO-2026-004 voided — 5 units of Hex Bolt removed"`, `performed_by U1`} | pass |
| PRI-RE-03 | R7 | happy | P `storage:A`; `E1.a = (L1, −2)`; `posted(E1.a → A, 2)`; `stock(A, X) = 8 @ 20.00` | call | returns `True`; new `inventory_ledger` row {`transaction_type 'inventory_adjustment'`, `quantity 2`, `unit_cost 26.00`, `total_cost 52.00`, `qty_before 8`, `qty_after 10`, `avg_price_before 20.00`, `avg_price_after 21.20`, `source_type 'po_receive_event_item_reversal'`, `source_id E1.a.id`, notes as RE-01}; stock `qty 10`, `avg_price 21.20` | pass |
| PRI-RE-04 | R7 | happy | P `machine:M1`; `E1.a = (L1, −2)`; `posted(E1.a → M1, 2)`; `mstock(M1, X) = 8 @ 20.00` | call | returns `True`; new machine row {`quantity 2`, `unit_cost 26.00`, `qty_before 8`, `qty_after 10`, `avg_price_before 20.00`, `avg_price_after 21.20`, `value_before 160.00`, `value_after 212.00`, `source_type 'po_receive_event_item_reversal'`}; `machine_items` `qty 10`; activity {`'purchase_reversed'`, `"PO PO-2026-004 voided — 2 units of Hex Bolt restored"`} | pass |
| PRI-RE-05 | R1 | happy | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `reversed(E1.a @ A)`; `stock(A, X) = 10 @ 22.00` | call | returns `False`; nothing written | pass |
| PRI-RE-06 | R1 (either ledger) | boundary | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `reversed(E1.a @ M1)` (machine ledger only); `stock(A, X) = 10 @ 22.00` | call | returns `False`; nothing written | pass |
| PRI-RE-07 | R1 (other workspace) | isolation | P `storage:A`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; a reversal row with `'po_receive_event_item_reversal'`/`E1.a.id` in **W2** (F2, Z2); `stock(A, X) = 15 @ 22.00` | call | returns `True`; one new W1 reversal row; stock `qty 10` | pass |
| PRI-RE-08 | R2 | happy | P `storage:A`; `E1.a = (L1, +5)`; no ledger row with source `E1.a.id`; `stock(A, X) = 15 @ 22.00` | call | returns `False`; nothing written | pass |
| PRI-RE-09 | R2 (other workspace) | isolation | P `storage:A`; `E1.a = (L1, +5)`; `'po_receive_event_item'`/`E1.a.id` row only in **W2** (F2, Z2); `stock(A, X) = 15 @ 22.00` | call | returns `False`; nothing written | pass |
| PRI-RE-10 | R4 | boundary | P `storage:A`; `E1.a = (L1, 0)`; a posting row `'po_receive_event_item'`/`E1.a.id` at A with `quantity 0`; `stock(A, X) = 15 @ 22.00` | call | returns `False`; nothing written | pass |
| PRI-RE-11 | R5 | error | P `storage:A`; `E1.a = (L1, Decimal('2.5'))`; a posting row for `E1.a.id` at A; `stock(A, X) = 15 @ 22.00` | call | raises HTTPException 400, detail `Line 1 has a fractional quantity delta; inventory requires whole units`; nothing written | pass |
| PRI-RE-12 | R8 (✅ Q2) | error | P `storage:A`; `posted(E1.a → A, 5)` for `E1.a = (L1, +5)`; `stock(A, X) = 2 @ 22.00` | call | raises HTTPException 400, detail `Insufficient stock (2 available, 5 requested)`; no reversal row; stock `qty 2` | pass |
| PRI-RE-13 | R8 (✅ Q2) | error | P `machine:M1`; `E1.a = (L1, +10)`; `posted(E1.a → M1, 10)`; `mstock(M1, X) = 2 @ 22.00` | call | raises HTTPException 400, detail `Insufficient machine stock (2 available, 10 requested)`; no reversal row; no activity event; `machine_items` `qty 2` | pass |
| PRI-RE-14 | R10 (unit price NULL) | error | P `storage:A`; L1 `unit_price NULL`; `E1.a = (L1, +5)`; `posted(E1.a → A, 5)`; `stock(A, X) = 15 @ 22.00` | call | raises `decimal.InvalidOperation`; nothing written | pass |
| PRI-RE-15 | R10 (→ P R12: 404) | error | P `storage:F2` (W2 factory); `E1.a = (L1, +5)`; `inventory_ledger` posting row in W1 with `factory_id F2`, `'po_receive_event_item'`, `E1.a.id` | call | raises HTTPException 404, detail `Factory with ID <F2.id> not found`; nothing written | pass |
| PRI-RE-16 | R10, P R12a scope (reversals still work at a deleted location) | soft-delete | P `storage:Ad` (soft-deleted); `E1.a = (L1, +5)`; `posted(E1.a → Ad, 5)`; `stock(Ad, X) = 5 @ 26.00` | call | returns `True`; new reversal row at `factory_id Ad`, `quantity 5`, `qty_after 0`; stock (Ad, X) `qty 0` | pass |
| PRI-RE-17 | R1a [BUG-680] | bug | P `storage:A`; `posted(E1.a → A, 5)` for `E1.a = (L1, +5)`; `reversed(E1.a @ A)`; `stock(A, X) = 10 @ 22.00`; race simulation for `'po_receive_event_item_reversal'` | inside `session.begin_nested()`: call | raises `IntegrityError`; after rollback, re-read: exactly one `'po_receive_event_item_reversal'`/`E1.a.id` row in W1; stock `qty 10` | xfail BUG-680 — fails today on: no exception raised (second reversal written) |
| PRI-RE-18 | R9 [BUG-683] | bug | P was received at A: `posted(E1.a → A, 5)` for `E1.a = (L1, +5)`; `stock(A, X) = 15 @ 22.00`; P's destination now `storage:B`; `stock(B, X) = 20 @ 30.00` | call | returns `True`; the new reversal row has `factory_id A`, `quantity 5`, `qty_before 15`, `qty_after 10`; re-read stock A/X `qty 10`; stock B/X `qty 20`, `avg_price 30.00`; no new ledger row for B | xfail BUG-683 — fails today on: reversal row has `factory_id B` (stock B 15, A 15) |
| PRI-RE-19 | R9 [BUG-683] | bug | `posted(E1.a → A, 5)` for `E1.a = (L1, +5)`; `stock(A, X) = 15 @ 22.00`; P's destination now `machine:M1`; `mstock(M1, X) = 20 @ 30.00` | call | returns `True`; exactly one new row, in `inventory_ledger`, `factory_id A`, `quantity 5`; stock A/X `qty 10`; no new `machine_item_ledger` row; `machine_items` (M1, X) `qty 20`; no activity event | xfail BUG-683 — fails today on: the reversal is written to the machine ledger at M1 |
| PRI-RE-20 | R3, R9 [BUG-683] | bug | `posted(E1.a → A, 5)` for `E1.a = (L1, +5)`; `stock(A, X) = 15 @ 22.00`; P's destination now `project:77` | call | returns `True`; new reversal row at `factory_id A`, `quantity 5`; stock A/X `qty 10` | xfail BUG-683 — fails today on: returns `False` and nothing is written |
| PRI-RE-21 | R4, R6 (smallest posted `+1`: other side of `delta == 0`; `> 0` → stock-out) | boundary | P `storage:A`; `E1.a = (L1, +1)`; `posted(E1.a → A, 1)`; `stock(A, X) = 11 @ 20.00` | call | returns `True`; exactly 1 new ledger row, in `inventory_ledger`, = {`factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 1`, `unit_cost 20.00`, `total_cost 20.00`, `qty_before 11`, `qty_after 10`, `avg_price_before 20.00`, `avg_price_after 20.00`, `source_type 'po_receive_event_item_reversal'`, `source_id E1.a.id`, `notes "PO PO-2026-004 voided — reverse receive event #<E1.a.id> line 1"`, `performed_by U1`}; re-read stock A/X `qty 10`, `avg_price 20.00`, `updated_by U1` | pass |
| PRI-RE-22 | R4, R7 (smallest posted `−1`: other side of `delta == 0`; `< 0` → stock-in) | boundary | P `storage:A`; `E1.a = (L1, −1)`; `posted(E1.a → A, 1)`; `stock(A, X) = 9 @ 20.00` (L1 `unit_price 26.00`) | call | returns `True`; exactly 1 new ledger row, in `inventory_ledger`, = {`factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 1`, `unit_cost 26.00`, `total_cost 26.00`, `qty_before 9`, `qty_after 10`, `avg_price_before 20.00`, `avg_price_after 20.60` ((180 + 26) / 10), `source_type 'po_receive_event_item_reversal'`, `source_id E1.a.id`, `performed_by U1`}; re-read stock A/X `qty 10`, `avg_price 20.60`, `updated_by U1` | pass |

## `_reverse_legacy_line_posting` (15 cases)

The call is `_reverse_legacy_line_posting(session, po=P, po_line=L1, workspace_id=W1, user_id=U1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-RL-01 | R4, R5 | happy | P `storage:A`; `legacy(L1 → A, 4)`; `stock(A, X) = 10 @ 20.00` | call | returns `True`; exactly 1 new `inventory_ledger` row = {STORAGE, `factory_id A`, `item_id X`, `transaction_type 'inventory_adjustment'`, `quantity 4`, `unit_cost 20.00`, `total_cost 80.00`, `qty_before 10`, `qty_after 6`, `avg_price_before 20.00`, `avg_price_after 20.00`, `source_type 'purchase_order_reversal'`, `source_id L1.id`, `notes "PO PO-2026-004 voided — reverse legacy posting for line 1"`, `performed_by U1`}; stock `qty 6`, `updated_by U1` | pass |
| PRI-RL-02 | R4, R5 | happy | P `machine:M1`; `legacy(L1 → M1, 7)`; `mstock(M1, X) = 10 @ 20.00` | call | returns `True`; 1 new `machine_item_ledger` row {`machine_id M1`, `quantity 7`, `unit_cost 20.00`, `total_cost 140.00`, `qty_before 10`, `qty_after 3`, `value_before 200.00`, `value_after 60.00`, `source_type 'purchase_order_reversal'`, `source_id L1.id`, notes as RL-01}; `machine_items` `qty 3`; activity {`'purchase_reversed'`, `"PO PO-2026-004 voided — 7 units of Hex Bolt removed"`, `performed_by U1`} | pass |
| PRI-RL-03 | R4 (factory row preferred) | boundary | P `storage:A`; `legacy(L1 → A, 4)` and `legacy(L1 → M1, 7)`; `stock(A, X) = 10 @ 20.00`; `mstock(M1, X) = 10 @ 20.00` | call | returns `True`; exactly 1 new row, in `inventory_ledger`, `quantity 4`; stock A `qty 6`; `machine_items` M1 `qty 10` | pass |
| PRI-RL-04 | R4 (several rows, no defined order) | boundary | P `storage:A`; two `legacy(L1 → A, 3)` rows; `stock(A, X) = 10 @ 20.00` | call | returns `True`; exactly 1 new reversal row, `quantity 3`; stock `qty 7` | pass |
| PRI-RL-05 | R1 | happy | P `storage:A`; `legacy(L1 → A, 4)`; `legacy-reversed(L1 @ A)`; `stock(A, X) = 6 @ 20.00` | call | returns `False`; nothing written | pass |
| PRI-RL-06 | R1 (either ledger; other workspace) | isolation | parametrized: (a) `legacy-reversed(L1 @ M1)` in W1 → returns `False`, nothing written; (b) a `'purchase_order_reversal'`/`L1.id` row only in **W2** (F2, Z2) → returns `True`, one new W1 reversal row, stock `qty 6`. Both have P `storage:A`, `legacy(L1 → A, 4)`, `stock(A, X) = 10 @ 20.00` | call | as listed per parameter | pass |
| PRI-RL-07 | R2 | happy | P `storage:A`; no `'purchase_order'` rows for `L1.id`; `stock(A, X) = 10 @ 20.00` | call | returns `False`; nothing written | pass |
| PRI-RL-08 | R2 (other workspace) | isolation | P `storage:A`; a `'purchase_order'`/`L1.id` row only in **W2** (F2, Z2); `stock(A, X) = 10 @ 20.00` | call | returns `False`; nothing written | pass |
| PRI-RL-09 | R6 | boundary | P `storage:A`; `legacy(L1 → A, 0)`; `stock(A, X) = 10 @ 20.00` | call | returns `True`; 1 new reversal row with `quantity 0`, `qty_before 10`, `qty_after 10`; stock `qty 10` | pass |
| PRI-RL-10 | R7 (✅ Q2) | error | P `storage:A`; `legacy(L1 → A, 4)`; `stock(A, X) = 3 @ 20.00` | call | raises HTTPException 400, detail `Insufficient stock (3 available, 4 requested)`; no reversal row; stock `qty 3` | pass |
| PRI-RL-11 | R8 (unit price not used) | boundary | P `storage:A`; L1 `unit_price NULL`; `legacy(L1 → A, 4)`; `stock(A, X) = 10 @ 20.00` | call | returns `True` (no `InvalidOperation`); reversal `quantity 4`, `unit_cost 20.00`; stock `qty 6` | pass |
| PRI-RL-12 | R8 (→ P R12: 404; deleted location still reversible) | error / soft-delete | parametrized: (a) P `storage:F2`, legacy row in W1 at `factory_id F2` → raises HTTPException 404 `Factory with ID <F2.id> not found`, nothing written; (b) P `storage:Ad`, `legacy(L1 → Ad, 4)`, `stock(Ad, X) = 10 @ 20.00` → returns `True`, stock (Ad, X) `qty 6` | call | as listed per parameter | pass |
| PRI-RL-13 | R8 [BUG-683] | bug | `legacy(L1 → A, 4)`; `stock(A, X) = 10 @ 20.00`; P's destination now `storage:B`; `stock(B, X) = 20 @ 30.00` | call | returns `True`; the new reversal row has `factory_id A`, `quantity 4`; stock A/X `qty 6`; stock B/X `qty 20` | xfail BUG-683 — fails today on: reversal row has `factory_id B` |
| PRI-RL-14 | R1a [BUG-680] | bug | P `storage:A`; `legacy(L1 → A, 4)`; `legacy-reversed(L1 @ A)`; `stock(A, X) = 6 @ 20.00`; race simulation for `'purchase_order_reversal'` | inside `session.begin_nested()`: call | raises `IntegrityError`; after rollback, re-read: exactly one `'purchase_order_reversal'`/`L1.id` row in W1; stock `qty 6` | xfail BUG-680 — fails today on: no exception raised |
| PRI-RL-15 | R3, R8 [BUG-683] | bug | `legacy(L1 → A, 4)`; `stock(A, X) = 10 @ 20.00`; P's destination now `project:77` | call | returns `True`; new reversal row at `factory_id A`, `quantity 4`; stock `qty 6` | xfail BUG-683 — fails today on: returns `False`, nothing written |

## `reverse_po_receive_inventory` (18 cases)

The call is `reverse_po_receive_inventory(session, P, po_lines, W1, U1)`, with `po_lines = [L1, L2]` unless stated. P is `storage:A`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-V-01 | R1, R4, R5 | happy | E1 (T2): `E1.a = (L1, +5)`, `E1.b = (L2, +3)`; `posted(E1.a → A, 5)`, `posted(E1.b → A, 3)`; `stock(A, X) = 15 @ 22.00`; `stock(A, Y) = 3 @ 4.00` | call | returns `2`; 2 new rows, both `'po_receive_event_item_reversal'`, with source ids {`E1.a.id`, `E1.b.id`}; stock A/X `qty 10`; A/Y `qty 0` | pass |
| PRI-V-02 | R1 (other PO / other workspace ignored) | isolation | as V-01 for L1 only: `E1.a = (L1, +5)`, `posted(E1.a → A, 5)`; plus P2's event E9 with line of P2 (item X, `+4`) and `posted(E9.a → A, 4)`; plus an event E8 **for P recorded in W2** with `E8.a = (L1, +2)` and a W1 posting row `posted(E8.a → A, 2)`; `stock(A, X) = 21 @ 22.00` | call with `po_lines=[L1]` | returns `1`; the only new row has `source_id E1.a.id`; no reversal row for `E9.a.id` or `E8.a.id`; stock `qty 16` | pass |
| PRI-V-03 | R2 (newest event first) | happy | E1 (T2): `E1.a = (L1, +5)`; E2 (T3): `E2.a = (L1, −2)`; `posted(E1.a → A, 5)`, `posted(E2.a → A, 2)`; `stock(A, X) = 3 @ 26.00` | call with `po_lines=[L1]` | returns `2` (a wrong order would raise 400: 3 available, 5 requested); new rows in id order: first `source_id E2.a.id` (stock-in 2), then `E1.a.id` (stock-out 5); stock `qty 0` | pass |
| PRI-V-04 | R2 (same timestamp → receive-line id desc) | boundary | E1 and E2 both `created_at T2`; E1 inserted first; `E1.a = (L1, +5)` (lower id), `E2.a = (L1, −2)` (higher id); postings for both; `stock(A, X) = 3 @ 26.00` | call with `po_lines=[L1]` | returns `2`; the first new row has `source_id E2.a.id`, the second `E1.a.id`; stock `qty 0` | pass |
| PRI-V-05 | R3 | boundary | `E1.a = (L1, +5)`, `E1.b = (L2, +3)`; both posted; `stock(A, X) = 15 @ 22.00`; `stock(A, Y) = 3 @ 4.00` | call with `po_lines=[L1]` | returns `1`; no reversal row for `E1.b.id`; stock A/Y `qty 3` | pass |
| PRI-V-06 | R4 (event pass, then legacy pass in `po_lines` order) | happy | `E1.a = (L1, +5)`, `posted(E1.a → A, 5)`; `legacy(L1 → A, 4)`; `legacy(L2 → A, 3)`; `stock(A, X) = 19 @ 20.00`; `stock(A, Y) = 3 @ 4.00` | call with `po_lines=[L2, L1]` | returns `3`; new rows in id order: (`'po_receive_event_item_reversal'`, `E1.a.id`), (`'purchase_order_reversal'`, `L2.id`), (`'purchase_order_reversal'`, `L1.id`); stock A/X `qty 10`; A/Y `qty 0` | pass |
| PRI-V-07 | R5 | boundary | P has no receive events and no legacy rows; `stock(A, X) = 10 @ 20.00` | call | returns `0`; nothing written | pass |
| PRI-V-08 | R6 | happy | as V-01, and V-01's call has already run in this test | call a second time | second call returns `0`; no new rows after the first call; stock A/X `qty 10`, A/Y `qty 0` | pass |
| PRI-V-09 | R8 | error | E1 (T2): `E1.a = (L2, +5)`, `posted(E1.a → A, 5)`, `stock(A, Y) = 1 @ 4.00`; E2 (T3): `E2.a = (L1, +3)`, `posted(E2.a → A, 3)`, `stock(A, X) = 10 @ 20.00` | call | raises HTTPException 400, detail `Insufficient stock (1 available, 5 requested)`; in the same session (no rollback): a reversal row for `E2.a.id` exists and stock A/X `qty 7`; no reversal row for `E1.a.id` | pass |
| PRI-V-10 | R7 (pending return is not netted) | boundary | `E1.a = (L1, +10)`, `posted(E1.a → A, 10)`; `pending-return(L1, 3)`; `stock(A, X) = 30 @ 20.00` | call with `po_lines=[L1]` | returns `1`; reversal row `quantity 10`; stock `qty 20` | pass |
| PRI-V-11 | R7, RE R6a [BUG-682] | bug | Q1 example A: `E1.a = (L1, +10)`, `posted(E1.a → A, 10)`; `return(L1, 3)`; `stock(A, X) = 7 @ 20.00` | call with `po_lines=[L1]` | returns `1`; one reversal row (`'po_receive_event_item_reversal'`, `E1.a.id`) with `quantity 7`; stock `qty 0` | xfail BUG-682 — fails today on: raises 400 `Insufficient stock (7 available, 10 requested)` |
| PRI-V-12 | R7, RE R6a [BUG-682] | bug | Q1 example B: as V-11 but `stock(A, X) = 27 @ 20.00` (20 other units) | call with `po_lines=[L1]` | returns `1`; reversal `quantity 7`; stock `qty 20` | xfail BUG-682 — fails today on: stock ends at `17` (reversal quantity 10) |
| PRI-V-13 | R7, RE R6a (newest-event-first consumption) [BUG-682] | bug | E1 (T2): `E1.a = (L1, +6)`; E2 (T3): `E2.a = (L1, +4)`; both posted at A; `return(L1, 5)`; `stock(A, X) = 25 @ 20.00` (20 baseline + 10 − 5) | call with `po_lines=[L1]` | returns `1`; no reversal row for `E2.a.id` (fully absorbed); the reversal row for `E1.a.id` has `quantity 5`; stock `qty 20` | xfail BUG-682 — fails today on: returns `2` / a reversal row for `E2.a.id` exists |
| PRI-V-14 | R7 (fully returned) [BUG-682] | bug | `E1.a = (L1, +10)`, `posted(E1.a → A, 10)`; `return(L1, 10)`; `stock(A, X) = 0 @ 20.00` | call with `po_lines=[L1]` | returns `0`; no new rows; stock `qty 0` | xfail BUG-682 — fails today on: raises 400 `Insufficient stock (0 available, 10 requested)` |
| PRI-V-15 | R7 (netting is per PO line) [BUG-682] | bug | `E1.a = (L1, +5)`, `E1.b = (L2, +5)`; both posted at A; `return(L2, 3)`; `stock(A, X) = 5 @ 20.00`; `stock(A, Y) = 12 @ 4.00` (10 baseline + 5 − 3) | call | returns `2`; reversal for `E1.a.id` `quantity 5`, for `E1.b.id` `quantity 2`; stock A/X `qty 0`, A/Y `qty 10` | xfail BUG-682 — fails today on: A/Y ends at `7` (reversal quantity 5) |
| PRI-V-16 | R7 (a return on another PO's line is not netted) | isolation | `E1.a = (L1, +10)`, `posted(E1.a → A, 10)`; a completed return item on P2's line L9 (line_number 1, item X, `quantity_returned 3`) with its `inventory_ledger` row at A/X/STORAGE (W1, `source_type 'purchase_return_item'`, `source_id` = that return item's id, `quantity 3`); `stock(A, X) = 27 @ 20.00` (20 baseline + 10 − 3) | call with `po_lines=[L1]` | returns `1`; reversal `quantity 10`; stock `qty 17` | pass |
| PRI-V-17 | R7, RE R6a ("completed" = return ledger row in the same workspace AND the same ledger as the original posting — other side of both conditions) | boundary | `E1.a = (L1, +10)`, `posted(E1.a → A, 10)` (factory ledger); `stock(A, X) = 30 @ 20.00`; a `PurchaseOrderReturnItem` on L1 with `quantity_returned 3`, whose `'purchase_return_item'`/<return item id> ledger row is, parametrized: (a) in `machine_item_ledger` W1 at M1/X, `quantity 3` (wrong ledger); (b) in `inventory_ledger` **W2** at F2/Z2 STORAGE, `quantity 3` (wrong workspace) | call with `po_lines=[L1]` | for each: returns `1`; one reversal row (`'po_receive_event_item_reversal'`, `E1.a.id`) with `quantity 10`; re-read stock A/X `qty 20` | pass |
| PRI-V-18 | R7 ("never negative": returned > received) [BUG-682] | bug | `E1.a = (L1, +10)`, `posted(E1.a → A, 10)`; `return(L1, 12)`; `stock(A, X) = 18 @ 20.00` (20 baseline + 10 − 12) | call with `po_lines=[L1]` | returns `0`; no new ledger rows (no reversal row for `E1.a.id`); re-read stock A/X `qty 18`, `avg_price 20.00` | xfail BUG-682 — fails today on: returns `1` and stock ends at `8` (reversal quantity 10) |

## Database uniqueness — BUG-680 (4 cases)

These cases make no manager call. They insert ledger rows directly and flush inside `session.begin_nested()`. The expected error is `sqlalchemy.exc.IntegrityError`. The savepoint is rolled back before the re-read.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PRI-IDX-01 | P R1a, RE R1a, RL R1a [BUG-680] | bug | parametrized over `source_type` ∈ {`'po_receive_event_item'`, `'po_receive_event_item_reversal'`, `'purchase_order_reversal'`}: one `inventory_ledger` row W1, A, X, STORAGE, that type, `source_id 801` | insert a second `inventory_ledger` row W1, **B**, X, STORAGE, same type, `source_id 801`; flush | raises `IntegrityError`; after rollback, exactly one row with (W1, type, 801) | xfail BUG-680 — fails today on: no exception raised |
| PRI-IDX-02 | P R1a, RE R1a, RL R1a [BUG-680] | bug | same parametrization, in `machine_item_ledger` (W1, M1, X) | insert a second row W1, **M2**, X, same type, `source_id 801`; flush | raises `IntegrityError`; after rollback, exactly one row | xfail BUG-680 — fails today on: no exception raised |
| PRI-IDX-03 | RL R4 (several legacy rows allowed; index is partial) | boundary | one `inventory_ledger` row and one `machine_item_ledger` row, each W1 with `source_type 'purchase_order'`, `source_id 802` | insert a second row of each with the same (W1, `'purchase_order'`, 802); flush | no exception; 2 rows with that source in each ledger | pass |
| PRI-IDX-04 | R1a (index includes workspace) | isolation | `inventory_ledger` row W1, A, X, STORAGE, `'po_receive_event_item'`, 803 | insert a row W2, F2, Z2, STORAGE, `'po_receive_event_item'`, 803; flush | no exception; one row per workspace | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P R1a / RE R1a / RL R1a: "surfaced as HTTPException 409" | `app/core/exceptions.py` (global integrity-error handler, BUG-462) | A unique violation (pgcode 23505) on the new ledger indexes becomes 409, never 500. Here only the `IntegrityError` is asserted (spec R1a, G1). |
| P R1a etc.: true two-session concurrency | integration test (two connections) | Two concurrent voids / receives for the same source: exactly one ledger row, the loser gets 409. |
| `_location_for_po` R3 / P R2 [BUG-681] | `app/schemas/purchase_order.py` (PO create/update schemas) | `destination_type` is trimmed and lower-cased, and only `storage` / `machine` / `project` are accepted (422 otherwise). The data clean-up of existing bad rows is a migration concern. |
| Overview: lines belong to the PO; the PO is not already voided | `PurchaseOrderService.create_receive_event` / `void_purchase_order` | The callers enforce these; this module does not check them. |
| Q2 (✅): a void that fails on insufficient stock leaves the PO un-voided | `PurchaseOrderService.void_purchase_order` | A 400 from `reverse_po_receive_inventory` rolls back and the PO status is unchanged. |

## Spec gaps
None. The 5 gaps of revision 2 are closed by the spec's Gap log G1–G5 (the spec now states what this file had decided).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_delta_to_int` | R1 | PRI-D-01, PRI-D-05 |
| `_delta_to_int` | R2 | PRI-D-02, PRI-D-05 |
| `_delta_to_int` | R3 | PRI-D-03, PRI-D-05 (other side) |
| `_delta_to_int` | R4; Err fractional | PRI-D-04 |
| `_ledger_exists` | R1 | PRI-LE-01, PRI-LE-04, PRI-LE-05 |
| `_ledger_exists` | R2 | PRI-LE-02 |
| `_ledger_exists` | R3 | PRI-LE-03 |
| `_ledger_exists` | R4 | PRI-LE-01 (no soft-delete filter; every row counts), PRI-SLE-02 |
| `_storage_ledger_exists` | R1 | PRI-SLE-01, PRI-SLE-02, PRI-SLE-03 |
| `_machine_ledger_exists` | R1 | PRI-MLE-01, PRI-MLE-02, PRI-MLE-03 |
| `_location_for_po` | R1 | PRI-LOC-01 |
| `_location_for_po` | R2 | PRI-LOC-02 |
| `_location_for_po` | R3 [BUG-681] | PRI-LOC-03, PRI-LOC-04; schema fix Deferred |
| `_post_event_item_delta` | R1 | PRI-P-16, PRI-P-17, PRI-P-18 |
| `_post_event_item_delta` | R1a [BUG-680]; Err concurrent duplicate | PRI-P-30, PRI-P-31, PRI-IDX-01, PRI-IDX-02, PRI-IDX-04; 409 Deferred |
| `_post_event_item_delta` | R2 [BUG-681 note] | PRI-P-19, PRI-P-20, PRI-P-21, PRI-PR-06 |
| `_post_event_item_delta` | R3 | PRI-P-22, PRI-PR-02; other side (±1): PRI-P-34, PRI-P-35 |
| `_post_event_item_delta` | R4; Err fractional | PRI-P-23, PRI-PR-05 |
| `_post_event_item_delta` | R5; Err unit price NULL | PRI-P-24 |
| `_post_event_item_delta` | R6 | PRI-P-01, PRI-P-02, PRI-P-03, PRI-P-04, PRI-P-33, PRI-P-34 |
| `_post_event_item_delta` | R7 | PRI-P-05, PRI-P-06, PRI-P-07, PRI-P-08 |
| `_post_event_item_delta` | R8 | PRI-P-09, PRI-P-10, PRI-P-35 |
| `_post_event_item_delta` | R9 | PRI-P-11 |
| `_post_event_item_delta` | R10; Err storage / machine insufficient | PRI-P-12, PRI-P-13, PRI-P-14, PRI-P-15 |
| `_post_event_item_delta` | R11 | PRI-P-05, PRI-P-25, PRI-P-26 |
| `_post_event_item_delta` | R12; Err factory / machine 404 | PRI-P-27, PRI-P-28 |
| `_post_event_item_delta` | R12a [BUG-684]; Err soft-deleted | PRI-P-29, PRI-P-32; reversal side: PRI-RE-16, PRI-RL-12 |
| `post_receive_event_inventory` | R1 | PRI-PR-01, PRI-PR-02, PRI-PR-06 |
| `post_receive_event_inventory` | R2 | PRI-PR-03 |
| `post_receive_event_inventory` | R3 | PRI-PR-04 |
| `post_receive_event_inventory` | R4 | PRI-PR-05 |
| `_reverse_event_item_posting` | R1 | PRI-RE-05, PRI-RE-06, PRI-RE-07 |
| `_reverse_event_item_posting` | R1a [BUG-680]; Err 409 | PRI-RE-17, PRI-IDX-01, PRI-IDX-02; 409 Deferred |
| `_reverse_event_item_posting` | R2 | PRI-RE-08, PRI-RE-09 |
| `_reverse_event_item_posting` | R3 [BUG-683] | PRI-RE-20 |
| `_reverse_event_item_posting` | R4 | PRI-RE-10; other side (±1): PRI-RE-21, PRI-RE-22 |
| `_reverse_event_item_posting` | R5 | PRI-RE-11 |
| `_reverse_event_item_posting` | R6 | PRI-RE-01, PRI-RE-02, PRI-RE-21 |
| `_reverse_event_item_posting` | R6a [BUG-682] | PRI-V-10, PRI-V-11, PRI-V-12, PRI-V-13, PRI-V-14, PRI-V-15, PRI-V-17 (via public caller, per spec R6a) |
| `_reverse_event_item_posting` | R7 | PRI-RE-03, PRI-RE-04, PRI-RE-22 |
| `_reverse_event_item_posting` | R8 | PRI-RE-12, PRI-RE-13 |
| `_reverse_event_item_posting` | R9 [BUG-683] | PRI-RE-01 (same location, pass), PRI-RE-18, PRI-RE-19, PRI-RE-20 |
| `_reverse_event_item_posting` | R10 | PRI-RE-14, PRI-RE-15, PRI-RE-16 |
| `_reverse_legacy_line_posting` | R1 | PRI-RL-05, PRI-RL-06 |
| `_reverse_legacy_line_posting` | R1a [BUG-680]; Err 409 | PRI-RL-14, PRI-IDX-01, PRI-IDX-02; 409 Deferred |
| `_reverse_legacy_line_posting` | R2 | PRI-RL-07, PRI-RL-08 |
| `_reverse_legacy_line_posting` | R3 [BUG-683] | PRI-RL-15 |
| `_reverse_legacy_line_posting` | R4 | PRI-RL-01, PRI-RL-02, PRI-RL-03, PRI-RL-04, PRI-IDX-03 |
| `_reverse_legacy_line_posting` | R5 | PRI-RL-01, PRI-RL-02 |
| `_reverse_legacy_line_posting` | R6 | PRI-RL-09 |
| `_reverse_legacy_line_posting` | R7; Err 400 | PRI-RL-10 |
| `_reverse_legacy_line_posting` | R8 [BUG-683]; Err 404 | PRI-RL-11, PRI-RL-12, PRI-RL-13, PRI-RL-15 |
| `reverse_po_receive_inventory` | R1 | PRI-V-01, PRI-V-02 |
| `reverse_po_receive_inventory` | R2 | PRI-V-03, PRI-V-04 |
| `reverse_po_receive_inventory` | R3 | PRI-V-05 |
| `reverse_po_receive_inventory` | R4 | PRI-V-01, PRI-V-06 |
| `reverse_po_receive_inventory` | R5 | PRI-V-01, PRI-V-06, PRI-V-07 |
| `reverse_po_receive_inventory` | R6 | PRI-V-08 |
| `reverse_po_receive_inventory` | R7 [BUG-682] | PRI-V-10, PRI-V-11, PRI-V-12, PRI-V-13, PRI-V-14, PRI-V-15, PRI-V-16, PRI-V-17, PRI-V-18 |
| `reverse_po_receive_inventory` | R8 | PRI-V-09 |
| BUG tags | BUG-680 | PRI-P-30, PRI-P-31, PRI-RE-17, PRI-RL-14, PRI-IDX-01, PRI-IDX-02 |
| BUG tags | BUG-681 | PRI-LOC-04, PRI-P-21 (module side, pass); schema Deferred |
| BUG tags | BUG-682 | PRI-V-11 … PRI-V-15, PRI-V-18 |
| BUG tags | BUG-683 | PRI-RE-18, PRI-RE-19, PRI-RE-20, PRI-RL-13, PRI-RL-15 |
| BUG tags | BUG-684 | PRI-P-29, PRI-P-32 |
