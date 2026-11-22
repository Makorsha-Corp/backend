# Test cases — `app/managers/inventory_manager.py`

> **Spec:** `tests/unit/managers/inventory_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 151 cases · 110 expected-to-pass · 41 expected-to-fail (bugs) · 6 deferred
> **Revision:** 1 — spec unchanged (re-run). Full self-check: INV-P-12 redesigned (old setup would XPASS on the test DB's `English_United States.1252` collation) and its old setup kept as new pass case INV-P-26; return-value assertions added to xfail cases INV-C-04/08, INV-U-09/11/12/14/16/30, INV-D-06/07/13; read-only "nothing changed" convention made explicit for every raising case; gap 7 narrowed.
> **Revision:** 2 — spec Gap log G1–G8 closed all 8 earlier gaps. RS-1 now names its patch targets (G1); lock-case SQL capture confirmed by spec Notes (G2); INV-U-11/12/28 assert every field of the new `update_inventory` R6a entry, new INV-U-31 (null on an already-NULL price → no entry) and INV-U-32 (price from NULL → notes print `None`) (G3); INV-IF-20 retired — `current_status_id` is NOT NULL (G4); INV-C-28 re-targeted to new `create_inventory` R6a (restored row keeps original creator/created_at, `updated_by` U1) (G5); new INV-C-30 for R3a (inactive catalog item accepted) (G6); INV-S-11 marked non-strict xfail per spec Notes (G7); `by_type` entries matched by field `inventory_type` (G8).
> **Revision:** 3 — re-run on the updated spec: its Gap log is still G1–G8, and Revision 2 already applied all of them, so no rule, Errors row or BUG tag changed. I ran the full self-check over the whole file again: all rules and Errors rows are in the Coverage matrix, the per-callable counts and the Counts line add up (151 / 110 / 41 / 6), and every xfail case names the assertion that fails today. No case rows changed.
> **Revision:** 4 — re-run requested after a Gap-log update. The spec still ends at G1–G8, which Revision 2 already applied, and no rule, Errors row, BUG tag or Notes entry is new. No verify report exists yet. I ran the full self-check over the whole file again against the spec and HR-1..HR-14: every rule, Errors row and BUG tag is in the Coverage matrix; recounting the rows gives C 30/10, U 32/14, G 9/4, P 26/4, S 11/2, D 13/3, IF 22/2, IS 8/2 (total 151, 41 xfail); every xfail case names the assertion that fails today; and every assertion that holds today inside an xfail case is also checked by a pass case. No case rows changed.
> **Revision:** 5 (2026-11-22) — spec Gap log G9: `update_inventory` R10 and `delete_inventory` R8 now give the exact lock clause. The SQL-capture convention's "locked read" now means a `SELECT` from `inventory` that ends with `FOR UPDATE OF inventory`, and no `SELECT` from `inventory` may carry `NOWAIT` or `SKIP LOCKED`. INV-U-30 and INV-D-13 reworded to match; both stay strict xfail (BUG-704 / BUG-705). No other row, count or status changed.

## Reviewer summary
- **Per callable:** `create_inventory` 30 (10 bug) · `update_inventory` 32 (14 bug) · `get_inventory` 9 (4 bug) · `get_inventory_page` 26 (4 bug) · `get_inventory_stats` 11 (2 bug) · `delete_inventory` 13 (3 bug) · `get_incoming_summary_for_factory` 22 (2 bug) · `get_incoming_summary` 8 (2 bug)
- **Notable design choices:**
  - Row-lock rules (BUG-704, BUG-705) cannot be raced in one session; the cases capture the SQL emitted during the call and require a `SELECT … FOR UPDATE OF inventory` with no `NOWAIT` / `SKIP LOCKED` (best-practice default, delegated by reviewer; exact clause from spec G9).
  - `create_inventory` R9 (concurrent duplicate → `IntegrityError`) uses race simulation RS-1: the DAO's live-row lookup and its any-state lookup are both forced to return `None` (the latter patched with `create=True`, since it may not exist before the BUG-714 fix — best-practice default, delegated by reviewer).
  - `create_inventory` R7 "negative qty → no ledger" is unreachable through a validated `InventoryCreate` once BUG-711 is fixed; INV-C-06 builds the payload with `model_construct` to bypass validation (best-practice default, delegated by reviewer).
  - Restore on create (BUG-714, INV-C-28) asserts the spec's R6a: original id/`created_by`/`created_at` kept, `updated_by` U1.
  - Ordering xfails: INV-P-12 uses two items named "Apple"/"apple" (case-only difference), because the test DB collation already sorts mixed-case names case-insensitively; only the tie-break shows BUG-701 (checked against the test database, not app code). INV-S-11 and INV-IS-08 insert in reverse of the intended order. INV-S-11 may XPASS today (native enum, sort-based GROUP BY), so per the spec Notes it is a **non-strict** xfail; an XPASS is reported as a discrepancy, the assertion is never weakened (best-practice default, delegated by reviewer).
  - INV-IF-19 gives a PO and a transfer the same explicit id (987654) to test that the two kinds stay separate. INV-IS-07 builds 501 factories. INV-IF-20 retired (order status is NOT NULL, so "no status" is unreachable).
- **Needs a decision:** None.

## Conventions for this module

**IDs:** `INV` = inventory_manager. Methods: `C` create_inventory (+ `InventoryCreate` schema), `U` update_inventory (+ `InventoryUpdate` schema), `G` get_inventory, `P` get_inventory_page, `S` get_inventory_stats, `D` delete_inventory, `IF` get_incoming_summary_for_factory, `IS` get_incoming_summary.

**Workspaces and people:** W1, W2, W3 = workspaces (W3 only where a fresh, empty workspace is needed). U1, U2 = profiles in W1. Every call is made as W1/U1 unless stated.

**Factories:** F1 "Main Plant" (W1, active, live) · F2 "Second Plant" (W1, active, live) · F_in "Idle Plant" (W1, `is_active` False, live) · F_del "Old Plant" (W1, active, `is_deleted` True) · FX "Foreign Plant" (W2, active, live).

**Catalog items:** I1 "Bolt" unit "pkgs" (W1) · I2 "Hex Nut" unit "pcs" (W1) · I3, I4, I5 "Washer", "Rivet", "Screw" unit "pcs" (W1, created in that order after I2) · IX "Secret Part" unit "pcs" (W2). Cases that need other names define items inline. Item ids ascend in creation order.

**Inventory rows:** written `INV(ws, item, type, factory, qty, avg_price, note)`; prices are set as 2-decimal `Decimal`s (`5.00` = `Decimal("5.00")`), so `str()` of a stored or passed price prints two decimals; unless stated `is_active` True, `is_deleted` False, `created_by` U2, `updated_by` NULL. Common rows:
- T = `INV(W1, I1, STORAGE, F1, 10, 5.00, "n1")`
- TX = `INV(W2, IX, STORAGE, FX, 10, 5.00, "x1")`
- TD = `INV(W1, I1, STORAGE, F1, 10, 5.00, "n1")` with `is_deleted` True (used instead of T, never together with it — unique constraint).

**Ledger:** "ledger rows for the bucket" = `inventory_ledger` rows with the row's (workspace, factory, item, type). Setup never inserts ledger rows unless stated, so "zero ledger rows" means zero for that bucket, and for error cases zero in the whole workspace. A "full R8 entry" / "full R7 entry" means every field listed in the Then cell is asserted exactly.

**MISSING** = an id not used by any row of that table (e.g. the table's max id + 100000).

**Decimals:** all money/quantity expectations are `Decimal` and compared exactly (`Decimal("31.50")`); stored `avg_price` is read back as `Numeric(15,2)`.

**Default calls:**
- create: `create_inventory(session, InventoryCreate(item_id=I1, inventory_type=STORAGE, factory_id=F1, qty=…, avg_price=…, note=…), W1, U1)`
- update: `update_inventory(session, T.id, InventoryUpdate(<fields>), W1, U1)` — only the fields listed are passed to the constructor (so `model_fields_set` is exactly those fields); `note=None` means explicitly passing `note=None`.
- get: `get_inventory(session, <id>, W1)`; page/stats: `workspace_id=W1` plus the listed keyword args; delete: `delete_inventory(session, <id>, W1, U1)`; incoming: `workspace_id=W1, factory_id=F1` unless stated.

**Results:** `get_inventory_page` `items` are compared by row `id` in order. `by_type` entries are matched by their `inventory_type` field (`InventoryTypeEnum`) and compared per type (in order only in INV-S-11). Incoming results are compared field by field (`factory_id`, `item_id`, `total_pending_qty`, `order_count`, and each `orders` entry's `order_kind`, `order_id`, `order_number`, `status_name`, `pending_qty`).

**Error cases — "nothing changed":** for write callables each error case re-reads the named row(s) and the ledger. For read-only callables (get, page, stats, incoming) the check is: number of `inventory` and `inventory_ledger` rows in W1 is the same before and after the call — this applies to EVERY case of these callables that raises (including isolation and xfail cases), whether or not its Then cell repeats it.

**Schema cases** (target `schema`): construct `InventoryCreate` / `InventoryUpdate` directly; the manager is never called. Rejection = `pydantic.ValidationError` (message not asserted); each rejection case also asserts W1 still has no inventory row for (I1, STORAGE, F1) and no ledger rows.

**Incoming-summary vocabulary:** statuses (W1) S_OPEN "Ordered", S_DONE "Received", S_TR "In Transit", S_DRAFT "Draft". WF = order workflow in W1 with `status_sequence = [S_OPEN.id, S_DONE.id]`.
`PO(number, factory, status, workflow, voided, lines)` — defaults: W1, `destination_type "storage"`, `destination_id` = factory id, `current_status_id` S_OPEN, `order_workflow_id` WF, `voided` False; lines are `(item, quantity_ordered, quantity_received)`.
`TR(number, factory, status, completed_at, lines)` — defaults: W1, `destination_location_type "storage"`, `destination_location_id` = factory id, current status S_TR, `completed_at` NULL; lines are `(item, quantity)`.
Orders are created in the order listed in Given, so ids ascend in that order.

**Externals mocked:** none. `created_at`, `updated_at`, `performed_at` come from the database.

**Savepoint:** a call expected (today or intended) to raise `IntegrityError` runs inside `session.begin_nested()` so the session stays usable for the re-read.

**SQL capture (lock cases):** a SQLAlchemy `before_cursor_execute` listener on the session's connection records every statement issued during the manager call only. "Locked read" = at least one recorded `SELECT` whose text reads from the `inventory` table and ends with `FOR UPDATE OF inventory` (trailing whitespace ignored), and no recorded `SELECT` from `inventory` contains `NOWAIT` or `SKIP LOCKED` (spec Notes for the test designer; exact clause from spec G9, `update_inventory` R10 / `delete_inventory` R8).

**Race simulations:**
- **RS-1** (`create_inventory` R9 only): on the DAO singleton `app.dao.inventory.inventory_dao` (the object the manager holds as `inv_dao`), `patch.object(inventory_dao, "get_by_factory_item_type", return_value=None)` and `patch.object(inventory_dao, "_get_any_by_factory_item_type", return_value=None, create=True)` (the second may not exist before the BUG-714 fix; `create=True` keeps the case runnable today and after — best-practice default, delegated by reviewer). The insert then reaches the database while a live duplicate exists.

---

## `InventoryManager.create_inventory`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-C-01 | R4 R6 R7 R8 | happy | W1 has no inventory rows | create qty 3, avg_price `Decimal("10.50")`, note `" Opening stock "` | returns an `Inventory` with an id; re-read row: workspace W1, item I1, type STORAGE, factory F1, qty 3, avg_price 10.50, note `" Opening stock "` (unchanged, spaces kept), created_by U1, updated_by NULL, is_active True, is_deleted False, created_at not NULL. Exactly one ledger row for the bucket: workspace W1, type STORAGE, factory F1, item I1, transaction_type `"manual_add"`, quantity 3, unit_cost 10.50, total_cost 31.50, qty_before 0, qty_after 3, avg_price_before NULL, avg_price_after 10.50, source_type `"manual"`, source_id NULL, notes `"Initial inventory record created"`, performed_by U1 | pass |
| INV-C-02 | R7 | boundary | W1 has no inventory rows | create qty 1, avg_price 2.00 | returns row with id; re-read qty 1; exactly one ledger row: quantity 1, qty_before 0, qty_after 1, unit_cost 2.00, total_cost 2.00 | pass |
| INV-C-03 | R7 R7a | boundary | W1 has no inventory rows | create qty 0, avg_price None, note None | returns row with id; re-read qty 0, avg_price NULL, note NULL; zero ledger rows for the bucket | pass |
| INV-C-04 | R7a R8 [BUG-712] | bug | W1 has no inventory rows | create qty 0, avg_price 4.25 | returns a row with an id; exactly one ledger row for the bucket: transaction_type `"manual_add"`, quantity 0, qty_before 0, qty_after 0, unit_cost 4.25, total_cost 0.00, avg_price_before NULL, avg_price_after 4.25, source_type `"manual"`, notes `"Initial inventory record created"`, performed_by U1 | xfail BUG-712 — fails today on: no ledger row written |
| INV-C-05 | R7 | happy | W1 has no inventory rows | create qty 0, avg_price 4.25 | returns row with id; re-read qty 0, avg_price 4.25 | pass |
| INV-C-06 | R7 | boundary | W1 has no inventory rows | create with a payload built by `InventoryCreate.model_construct(item_id=I1, inventory_type=STORAGE, factory_id=F1, qty=-5, avg_price=Decimal("3.00"), note=None)` (validation bypassed) | returns row with id; re-read qty -5, avg_price 3.00; zero ledger rows for the bucket | pass |
| INV-C-07 | R8 | happy | W1 has no inventory rows | create qty 10, avg_price 0 | returns row; re-read avg_price 0.00; exactly one ledger row: quantity 10, unit_cost 0.00, qty_after 10, avg_price_after 0.00 | pass |
| INV-C-08 | R8 [BUG-707] | bug | W1 has no inventory rows | create qty 10, avg_price 0 | returns a row with an id; the ledger row's total_cost is 0.00 | xfail BUG-707 — fails today on: total_cost NULL |
| INV-C-09 | R8 | happy | W1 has no inventory rows | create qty 5, avg_price None | returns row; exactly one ledger row: quantity 5, unit_cost NULL, total_cost NULL, avg_price_after NULL, qty_after 5 | pass |
| INV-C-10 | R1, Errors row 1 | error | W1 has no inventory rows | create with factory_id = MISSING, qty 3 | raises `HTTPException` 404, detail `"Factory with ID {MISSING} not found"`; no inventory row in W1; no ledger rows in W1 | pass |
| INV-C-11 | R1, Errors row 1 | isolation | W1 has no inventory rows; FX exists in W2 | create with factory_id = FX, qty 3 | raises 404 `"Factory with ID {FX} not found"`; no inventory row with item I1 in any workspace; no ledger rows in W1 or W2 | pass |
| INV-C-12 | R2 [BUG-715], Errors row 1 | bug | F_del exists; W1 has no inventory rows | create with factory_id = F_del, qty 3 | raises 404 `"Factory with ID {F_del} not found"`; no inventory row for F_del; no ledger rows in W1 | xfail BUG-715 — fails today on: no exception raised (row created) |
| INV-C-13 | R2 | boundary | F_in (inactive, live) exists | create with factory_id = F_in, qty 2, avg_price 1.00 | returns row with id; re-read factory F_in, qty 2; exactly one ledger row for (W1, F_in, I1, STORAGE) | pass |
| INV-C-14 | R3 [BUG-710], Errors row 2 | bug | IX exists in W2; W1 has no inventory rows | create with item_id = IX, factory F1, qty 1 | raises 404 `"Item with ID {IX} not found"`; no inventory row with item IX; no ledger rows in W1 | xfail BUG-710 — fails today on: no exception raised (row created) |
| INV-C-15 | R3 [BUG-710], Errors row 2 | bug | W1 has no inventory rows | create with item_id = MISSING, qty 1 (in a savepoint) | raises 404 `"Item with ID {MISSING} not found"`; no inventory row in W1; no ledger rows in W1 | xfail BUG-710 — fails today on: `IntegrityError` (foreign key) instead of `HTTPException` |
| INV-C-16 | R4 [BUG-711], Errors row 3 | bug | — | schema: `InventoryCreate(item_id=I1, inventory_type=STORAGE, factory_id=F1, qty=-1)` | raises `ValidationError` | xfail BUG-711 — fails today on: no error raised |
| INV-C-17 | R4 | boundary | — | schema: `InventoryCreate(item_id=I1, inventory_type=STORAGE, factory_id=F1, qty=0, avg_price=Decimal("0"))` | builds without error; `qty` 0, `avg_price` `Decimal("0")` | pass |
| INV-C-18 | R4 [BUG-711], Errors row 3 | bug | — | schema: `InventoryCreate(…, qty=1, avg_price=Decimal("-0.01"))` | raises `ValidationError` | xfail BUG-711 — fails today on: no error raised |
| INV-C-19 | R4 [BUG-708], Errors row 3 | bug | — | schema: `InventoryCreate(…, qty=3, avg_price=Decimal("10.005"))` | raises `ValidationError` | xfail BUG-708 — fails today on: no error raised |
| INV-C-20 | R4 | boundary | W1 has no inventory rows | create qty 3, avg_price `Decimal("10.01")` | returns row; re-read avg_price 10.01; ledger row unit_cost 10.01, total_cost 30.03 | pass |
| INV-C-21 | R4 [BUG-708], Errors row 3 | bug | — | schema: `InventoryCreate(…, qty=1, avg_price=Decimal("10000000000000"))` (14 integer digits) | raises `ValidationError` | xfail BUG-708 — fails today on: no error raised |
| INV-C-22 | R4 | boundary | W1 has no inventory rows | create qty 1, avg_price `Decimal("9999999999999.99")` (13 integer digits) | returns row; re-read avg_price 9999999999999.99; ledger row unit_cost and total_cost 9999999999999.99 | pass |
| INV-C-23 | R5, Errors row 4 | error | live `INV(W1, I1, STORAGE, F1, 7, 2.00, "existing")` | create qty 4, avg_price 3.00, note "new" | raises `HTTPException` 409, detail `"Inventory record already exists for this item/type/factory combination"`; re-read: exactly one inventory row for (W1, I1, STORAGE, F1) with qty 7, avg_price 2.00, note "existing", updated_by NULL; zero ledger rows for the bucket | pass |
| INV-C-24 | R5 | isolation | live row inserted directly as `INV(W2, I1, STORAGE, F1, 7, 2.00, "w2")` (cross-workspace references, allowed by the DB) | create qty 4 in W1 | returns a new row whose id ≠ the W2 row's id, workspace W1, qty 4; W2 row still qty 7, note "w2"; two inventory rows exist for (I1, STORAGE, F1) | pass |
| INV-C-25 | R5 | isolation | live `INV(W1, I1, STORAGE, F2, 7, 2.00, "f2")` | create (F1) qty 4 | returns new row with factory F1, qty 4; F2 row unchanged (qty 7) | pass |
| INV-C-26 | R5 | isolation | live `INV(W1, I2, STORAGE, F1, 7, 2.00, "i2")` | create (item I1) qty 4 | returns new row with item I1, qty 4; I2 row unchanged (qty 7) | pass |
| INV-C-27 | R5 | isolation | live `INV(W1, I1, DAMAGED, F1, 7, 2.00, "dmg")` | create (STORAGE) qty 4 | returns new row with type STORAGE, qty 4; DAMAGED row unchanged (qty 7) | pass |
| INV-C-28 | R5 R6a R7 R8 [BUG-714] | bug | soft-deleted row R40 = `INV(W1, I1, STORAGE, F1, 7, 2.00, "old")` with `is_deleted` True, `is_active` False, created_by U2, updated_by U2; its `created_at` value recorded before the call | create qty 4, avg_price 3.00, note "new" by U1 (in a savepoint) | returns the row with id = R40.id; re-read: exactly one inventory row for (W1, I1, STORAGE, F1), id R40, is_deleted False, is_active True, qty 4, avg_price 3.00, note "new", created_by U2 (original kept), created_at equal to the recorded value, updated_by U1, updated_at not NULL; exactly one ledger row for the bucket: transaction_type `"manual_add"`, quantity 4, qty_before 0, qty_after 4, unit_cost 3.00, total_cost 12.00, avg_price_before NULL, avg_price_after 3.00, notes `"Initial inventory record created"`, performed_by U1 | xfail BUG-714 — fails today on: `IntegrityError` raised instead of a row returned |
| INV-C-29 | R9, Errors row 5 | error | live `INV(W1, I1, STORAGE, F1, 7, 2.00, "existing")`; RS-1 active | create qty 4 (in a savepoint) | raises `sqlalchemy.exc.IntegrityError` (not `HTTPException`); after the savepoint rolls back: exactly one inventory row for (W1, I1, STORAGE, F1), qty 7; zero ledger rows for the bucket | pass |
| INV-C-30 | R3a | boundary | catalog item I_in "Old Gasket" unit "pcs" in W1 with `is_active` False; W1 has no inventory rows | create with item_id = I_in, factory F1, qty 2, avg_price 1.00 | returns a row with an id; re-read item I_in, workspace W1, qty 2, avg_price 1.00; exactly one ledger row for (W1, F1, I_in, STORAGE) with quantity 2 | pass |

## `InventoryManager.update_inventory`

All cases use T unless stated; zero ledger rows before the call.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-U-01 | R3 R8 R9 | happy | T | update `note="n2"` | returns T (same id); re-read note "n2", qty 10, avg_price 5.00, updated_by U1, workspace W1, item I1, type STORAGE, factory F1; zero ledger rows | pass |
| INV-U-02 | R3 R6 R7 R9 | happy | T | update `qty=12` | returns T; re-read qty 12, avg_price 5.00, note "n1", updated_by U1; exactly one ledger row: workspace W1, type STORAGE, factory F1, item I1, transaction_type `"inventory_adjustment"`, quantity 2, unit_cost 5.00, total_cost 10.00, qty_before 10, qty_after 12, avg_price_before 5.00, avg_price_after 5.00, source_type `"adjustment"`, notes `"Quantity adjusted from 10 to 12"`, performed_by U1 | pass |
| INV-U-03 | R7 | happy | T | update `qty=4` | returns T; re-read qty 4; one ledger row: quantity 6 (non-negative), qty_before 10, qty_after 4, unit_cost 5.00, total_cost 30.00, notes `"Quantity adjusted from 10 to 4"` | pass |
| INV-U-04 | R4 R7 | boundary | T | update `qty=0` | returns T; re-read qty 0; one ledger row: quantity 10, qty_before 10, qty_after 0, total_cost 50.00, notes `"Quantity adjusted from 10 to 0"` | pass |
| INV-U-05 | R3 R6 R7 R8 | happy | T | update `qty=12, avg_price=Decimal("6.00")` | returns T; re-read qty 12, avg_price 6.00, note "n1", workspace/item/type/factory unchanged; exactly one ledger row (not two): quantity 2, unit_cost 6.00, total_cost 12.00, qty_before 10, qty_after 12, avg_price_before 5.00, avg_price_after 6.00 | pass |
| INV-U-06 | R6 | boundary | T | update `qty=10` (equal to current) | returns T; re-read qty 10, avg_price 5.00; zero ledger rows | pass |
| INV-U-07 | R7 | happy | `INV(W1, I1, STORAGE, F1, 10, None, "n1")` | update `qty=12` | returns the row; one ledger row: quantity 2, unit_cost NULL, total_cost NULL, avg_price_before NULL, avg_price_after NULL, qty_after 12 | pass |
| INV-U-08 | R7 | happy | `INV(W1, I1, STORAGE, F1, 10, 0.00, "n1")` | update `qty=12` | returns the row; one ledger row: quantity 2, unit_cost 0.00, avg_price_before 0.00, avg_price_after 0.00, qty_after 12 | pass |
| INV-U-09 | R7 [BUG-707] | bug | `INV(W1, I1, STORAGE, F1, 10, 0.00, "n1")` | update `qty=12` | returns the row (same id); the ledger row's total_cost is 0.00 | xfail BUG-707 — fails today on: total_cost NULL |
| INV-U-10 | R3 R9 | happy | T | update `avg_price=Decimal("6.00")` | returns T; re-read avg_price 6.00, qty 10, note "n1", updated_by U1 | pass |
| INV-U-11 | R6 R6a [BUG-712] | bug | T | update `avg_price=Decimal("6.00")` | returns T (same id); exactly one ledger row for the bucket (full R6a entry): workspace W1, type STORAGE, factory F1, item I1, transaction_type `"inventory_adjustment"`, quantity 0, qty_before 10, qty_after 10, unit_cost 6.00, total_cost 0.00, avg_price_before 5.00, avg_price_after 6.00, source_type `"adjustment"`, source_id NULL, notes `"Average price adjusted from 5.00 to 6.00"`, performed_by U1 | xfail BUG-712 — fails today on: no ledger row written |
| INV-U-12 | R6 R6a [BUG-712] | bug | T | update `qty=10, avg_price=Decimal("6.00")` (qty sent but unchanged) | returns T (same id); exactly one ledger row: transaction_type `"inventory_adjustment"`, quantity 0, qty_before 10, qty_after 10, unit_cost 6.00, total_cost 0.00, avg_price_before 5.00, avg_price_after 6.00, source_type `"adjustment"`, notes `"Average price adjusted from 5.00 to 6.00"`, performed_by U1 | xfail BUG-712 — fails today on: no ledger row written |
| INV-U-13 | R6 | boundary | T | update `avg_price=Decimal("5.00")` (equal to current) | returns T; re-read avg_price 5.00, qty 10; zero ledger rows | pass |
| INV-U-14 | R9 [BUG-703] | bug | T | update with `InventoryUpdate()` (no fields) | returns T (same id); re-read updated_by NULL | xfail BUG-703 — fails today on: updated_by = U1 |
| INV-U-15 | R3 | happy | T | update with `InventoryUpdate()` (no fields) | returns T; re-read qty 10, avg_price 5.00, note "n1"; zero ledger rows | pass |
| INV-U-16 | R9 [BUG-703] | bug | T | update `qty=10, avg_price=Decimal("5.00"), note="n1"` (all equal to stored) | returns T (same id); re-read updated_by NULL | xfail BUG-703 — fails today on: updated_by = U1 |
| INV-U-17 | R1, Errors row 1 | error | T | `update_inventory(session, MISSING, InventoryUpdate(qty=12), W1, U1)` | raises `HTTPException` 404, detail `"Inventory record with ID {MISSING} not found"`; T unchanged (qty 10, avg_price 5.00, note "n1", updated_by NULL); zero ledger rows in W1 | pass |
| INV-U-18 | R1, Errors row 1 | isolation | TX (W2) | `update_inventory(session, TX.id, InventoryUpdate(qty=12), W1, U1)` | raises 404 `"Inventory record with ID {TX.id} not found"`; TX unchanged (qty 10, note "x1", updated_by NULL); zero ledger rows in W1 and W2 | pass |
| INV-U-19 | R2, Errors row 2 | soft-delete | TD (soft-deleted) | `update_inventory(session, TD.id, InventoryUpdate(qty=12, note="z"), W1, U1)` | raises `HTTPException` 400, detail `"Cannot update a deleted inventory record"`; TD unchanged (qty 10, note "n1", is_deleted True, updated_by NULL); zero ledger rows | pass |
| INV-U-20 | R4 [BUG-711], Errors row 3 | bug | — | schema: `InventoryUpdate(qty=-1)` | raises `ValidationError` | xfail BUG-711 — fails today on: no error raised |
| INV-U-21 | R4 | boundary | — | schema: `InventoryUpdate(qty=0, avg_price=Decimal("0"))` | builds without error; qty 0, avg_price `Decimal("0")` | pass |
| INV-U-22 | R4 [BUG-711], Errors row 3 | bug | — | schema: `InventoryUpdate(avg_price=Decimal("-0.01"))` | raises `ValidationError` | xfail BUG-711 — fails today on: no error raised |
| INV-U-23 | R4 [BUG-708], Errors row 3 | bug | — | schema: `InventoryUpdate(avg_price=Decimal("10.005"))` | raises `ValidationError` | xfail BUG-708 — fails today on: no error raised |
| INV-U-24 | R4 [BUG-708], Errors row 3 | bug | — | schema: `InventoryUpdate(avg_price=Decimal("10000000000000"))` | raises `ValidationError` | xfail BUG-708 — fails today on: no error raised |
| INV-U-25 | R4 R7 | boundary | T | update `qty=11, avg_price=Decimal("10.01")` | returns T; re-read avg_price 10.01, qty 11; ledger row unit_cost 10.01, quantity 1, total_cost 10.01 | pass |
| INV-U-26 | R4 R7 | boundary | T | update `qty=11, avg_price=Decimal("9999999999999.99")` | returns T; re-read avg_price 9999999999999.99; ledger row unit_cost 9999999999999.99, total_cost 9999999999999.99 | pass |
| INV-U-27 | R5 [BUG-713] | bug | T | update `note=None` (explicit) | returns T; re-read note NULL | xfail BUG-713 — fails today on: note still "n1" |
| INV-U-28 | R5 R6 R6a [BUG-713][BUG-712] | bug | T | update `avg_price=None` (explicit) | returns T; re-read avg_price NULL, qty 10; exactly one ledger row: transaction_type `"inventory_adjustment"`, quantity 0, qty_before 10, qty_after 10, unit_cost NULL, total_cost NULL, avg_price_before 5.00, avg_price_after NULL, source_type `"adjustment"`, notes `"Average price adjusted from 5.00 to None"`, performed_by U1 | xfail BUG-713 — fails today on: avg_price still 5.00 |
| INV-U-29 | R5 [BUG-713], Errors row 4 | bug | T | update `qty=None, note="changed"` (qty explicit null) | raises `HTTPException` 422, detail `"qty cannot be empty"`; T unchanged (qty 10, note "n1", updated_by NULL); zero ledger rows | xfail BUG-713 — fails today on: no exception raised |
| INV-U-30 | R10 [BUG-704] | bug | T; SQL capture on | update `qty=12` | returns T (same id); a locked read of `inventory` (`… FOR UPDATE OF inventory`) was issued during the call; no `SELECT` from `inventory` has `NOWAIT` / `SKIP LOCKED` (see SQL capture) | xfail BUG-704 — fails today on: no `SELECT … FOR UPDATE OF inventory` issued |
| INV-U-31 | R5 R6a | boundary | `INV(W1, I1, STORAGE, F1, 10, None, "n1")` | update `avg_price=None` (explicit; already NULL) | returns the row (same id); re-read avg_price NULL, qty 10, note "n1"; zero ledger rows for the bucket | pass |
| INV-U-32 | R6 R6a [BUG-712] | bug | `INV(W1, I1, STORAGE, F1, 10, None, "n1")` | update `avg_price=Decimal("6.00")` | returns the row (same id); re-read avg_price 6.00; exactly one ledger row: transaction_type `"inventory_adjustment"`, quantity 0, qty_before 10, qty_after 10, unit_cost 6.00, total_cost 0.00, avg_price_before NULL, avg_price_after 6.00, source_type `"adjustment"`, notes `"Average price adjusted from None to 6.00"`, performed_by U1 | xfail BUG-712 — fails today on: no ledger row written |

## `InventoryManager.get_inventory`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-G-01 | R1 | happy | T | `get_inventory(session, T.id, W1)` | returns the row with id T.id, qty 10, workspace W1 | pass |
| INV-G-02 | R1 | boundary | `INV(W1, I1, STORAGE, F1, 0, None, None)` | get by its id | returns that row (id matches), qty 0 | pass |
| INV-G-03 | R1 | boundary | `INV(W1, I1, STORAGE, F1, -3, None, None)` | get by its id | returns that row, qty -3 | pass |
| INV-G-04 | R2, Errors row 1 | error | T | get MISSING | raises `HTTPException` 404, detail `"Inventory record with ID {MISSING} not found"`; W1 row counts unchanged | pass |
| INV-G-05 | R2, Errors row 1 | isolation | TX (W2) | get TX.id with W1 | raises 404 `"Inventory record with ID {TX.id} not found"` | pass |
| INV-G-06 | R2 [BUG-700] | bug | T | `get_inventory(session, MISSING, W1, include_deleted=True)` | raises 404 `"Inventory record with ID {MISSING} not found"` | xfail BUG-700 — fails today on: `TypeError` (no `include_deleted` parameter) |
| INV-G-07 | R2 [BUG-700] | bug | TX (W2) | `get_inventory(session, TX.id, W1, include_deleted=True)` | raises 404 `"Inventory record with ID {TX.id} not found"` | xfail BUG-700 — fails today on: `TypeError` (no `include_deleted` parameter) |
| INV-G-08 | R3 [BUG-700], Errors row 1 | bug | TD (soft-deleted) | `get_inventory(session, TD.id, W1)` | raises 404 `"Inventory record with ID {TD.id} not found"` | xfail BUG-700 — fails today on: row returned, no error |
| INV-G-09 | R4 [BUG-700] | bug | TD (soft-deleted) | `get_inventory(session, TD.id, W1, include_deleted=True)` | returns the row with id TD.id, is_deleted True | xfail BUG-700 — fails today on: `TypeError` (no `include_deleted` parameter) |

## `InventoryManager.get_inventory_page`

Unless stated, rows are STORAGE in F1 with qty 5 and avg_price 1.00; items named in the row are created in W1 with unit "pcs".

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-P-01 | R1 R7 R8 | happy | items "Anchor", "Bolt", "Cable" (W1), "Anvil" (W2); rows A = Anchor qty 5, B = Bolt qty 3, D = Cable qty 4 soft-deleted (all W1, F1), X = `INV(W2, Anvil, STORAGE, FX, 9, …)` | page with defaults | items ids [A, B]; total 2; skip 0; limit 50; has_more False | pass |
| INV-P-02 | R2 | happy | item "Anchor"; A = Anchor STORAGE F1, B = Anchor DAMAGED F1 | `inventory_type=DAMAGED` | items [B]; total 1 | pass |
| INV-P-03 | R2 | happy | item "Anchor"; A = Anchor STORAGE F1, B = Anchor STORAGE F2 | `factory_id=F2` | items [B]; total 1 | pass |
| INV-P-04 | R2 | boundary | as INV-P-03 | `factory_id=0` | items [A, B]; total 2 | pass |
| INV-P-05 | R2 | happy | items "Anchor", "Bolt"; A = Anchor, B = Bolt | `item_id=Bolt.id` | items [B]; total 1 | pass |
| INV-P-06 | R2 | boundary | as INV-P-05 | `item_id=0` | items []; total 0; has_more False | pass |
| INV-P-07 | R2 | happy | items "Anchor", "Bolt"; A = Anchor STORAGE F1, B = Anchor DAMAGED F1, C = Anchor STORAGE F2, E = Bolt STORAGE F1 | `inventory_type=STORAGE, factory_id=F1, item_id=Anchor.id` | items [A]; total 1 | pass |
| INV-P-08 | R3 | boundary | items "Anchor", "Bolt", "Cable"; A = Anchor qty 1, Z = Bolt qty 0, N = Cable qty -2 | defaults (`include_zero_qty` False) | items [A]; total 1 | pass |
| INV-P-09 | R3 | boundary | as INV-P-08 | `include_zero_qty=True` | items [A, Z, N]; total 3 | pass |
| INV-P-10 | R4 | happy | items "cable", "anchor", "bolt" created in that order, one row each, rows inserted in that order | defaults | items in order [anchor row, bolt row, cable row] | pass |
| INV-P-11 | R4 | happy | item "Anchor"; rows R1 = Anchor STORAGE F1, R2 = Anchor DAMAGED F1, R3 = Anchor SCRAP F2, inserted in that order | defaults | items in order [R1, R2, R3] (same name → id ascending) | pass |
| INV-P-12 | R4 [BUG-701] | bug | two distinct W1 items created in this order: "Apple", then "apple" (case-only difference); one row each, Apple's row inserted first (lower inventory id) | defaults | items in order [Apple row, apple row] (equal ignoring case → inventory id ascending) | xfail BUG-701 — fails today on: order is [apple row, Apple row] (test DB collation `English_United States.1252` puts lowercase first on a case-only tie; spec Notes) |
| INV-P-13 | R5 R7 R8 | happy | items "Item A".."Item E", one row each | `skip=1, limit=2` | items [Item B row, Item C row]; total 5; skip 1; limit 2; has_more True | pass |
| INV-P-14 | R5 R8 | boundary | as INV-P-13 | `skip=3, limit=2` | items [Item D row, Item E row]; total 5; has_more False (3 + 2 = 5) | pass |
| INV-P-15 | R5 R8 | boundary | as INV-P-13 | `skip=5, limit=2` | items []; total 5; skip 5; has_more False | pass |
| INV-P-16 | R3 R5 R7 | happy | items "Item A".."Item D"; Item A row qty 0, B/C/D rows qty 1 | `skip=0, limit=2` | items [Item B row, Item C row]; total 3; has_more True | pass |
| INV-P-17 | R1 R6 | happy | items (instead of I1/I2) "Hex Bolt" unit "pcs", "Nut" unit "pkgs" (W1), "Hex Bolt Foreign" (W2); rows H = Hex Bolt, N = Nut, HD = Hex Bolt DAMAGED soft-deleted, HX = W2 row of "Hex Bolt Foreign" | `search="X BO"` | items [H]; total 1 | pass |
| INV-P-18 | R6 | happy | as INV-P-17 | `search="KG"` (middle of unit "pkgs") | items [N]; total 1 | pass |
| INV-P-19 | R6 | happy | as INV-P-17 | `search="  nut  "` | items [N]; total 1 | pass |
| INV-P-20 | R6 | boundary | as INV-P-17 | `search="   "` | items [H, N]; total 2 | pass |
| INV-P-21 | R6 | boundary | as INV-P-17 | `search=""` | items [H, N]; total 2 | pass |
| INV-P-22 | R6 | happy | as INV-P-17 | `search="zzz"` | items []; total 0; has_more False | pass |
| INV-P-23 | R6 [BUG-702] | bug | items "100% Cotton", "Cotton Blend" (unit "pcs"), one row each | `search="%"` | items [100% Cotton row]; total 1 | xfail BUG-702 — fails today on: both rows returned (total 2) |
| INV-P-24 | R6 [BUG-702] | bug | items "A_B Bracket", "AXB Bracket" (unit "pcs"), one row each | `search="_"` | items [A_B Bracket row]; total 1 | xfail BUG-702 — fails today on: both rows returned (total 2) |
| INV-P-25 | R6 [BUG-702] | bug | items `"C:\Temp Tool"`, "Plain Tool" (unit "pcs"), one row each | `search="\\"` (one backslash) | items [C:\Temp Tool row]; total 1 | xfail BUG-702 — fails today on: total 0 (backslash acts as escape) |
| INV-P-26 | R4 | happy | items "cherry", "Banana", "apple" created in that order, one row each, rows inserted in that order | defaults | items in order [apple row, Banana row, cherry row] (holds today on the test DB collation and after the BUG-701 fix) | pass |

## `InventoryManager.get_inventory_stats`

**Stats setup SS:** W1 rows A = `INV(W1, I1 "Bolt", STORAGE, F1, 3, 2.50)`, B = `INV(W1, I2 "Hex Nut", STORAGE, F2, 2, None)`, C = `INV(W1, I1, SCRAP, F1, 4, 1.25)`, D = `INV(W1, I1, DAMAGED, F1, 100, 1.00)` soft-deleted, E = `INV(W1, I2, WASTE, F1, 0, 9.00)`, N = `INV(W1, I2, DAMAGED, F2, -2, 3.00)`; X = `INV(W2, IX, STORAGE, FX, 50, 1.00)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-S-01 | R1 R2 R3 R5 | happy | SS | stats with defaults | records 3; total_qty 9; estimated_value `Decimal("12.50")`; by_type has exactly two entries: STORAGE {unique_item_count 2, total_qty 5}, SCRAP {unique_item_count 1, total_qty 4}; no DAMAGED, no WASTE entry | pass |
| INV-S-02 | R2 R3 R5 | boundary | W3 has no inventory rows | stats with `workspace_id=W3` | records 0; total_qty 0; estimated_value `Decimal("0")`; by_type [] | pass |
| INV-S-03 | R3 | boundary | W1 rows `INV(W1, I1, STORAGE, F1, 3, None)`, `INV(W1, I2, STORAGE, F1, 2, None)` | stats with defaults | records 2; total_qty 5; estimated_value `Decimal("0")` | pass |
| INV-S-04 | R1 | happy | SS | `inventory_type=STORAGE` | records 2; total_qty 5; estimated_value 7.50; by_type only STORAGE {2, 5} | pass |
| INV-S-05 | R1 | happy | SS | `factory_id=F1` | records 2 (A, C); total_qty 7; estimated_value 12.50 | pass |
| INV-S-06 | R1 | happy | SS | `item_id=I2` | records 1 (B); total_qty 2; estimated_value 0 | pass |
| INV-S-07 | R1 R3 R5 | boundary | SS | `include_zero_qty=True` | records 5 (A, B, C, E, N); total_qty 7; estimated_value `Decimal("6.50")`; by_type: STORAGE {2, 5}, SCRAP {1, 4}, WASTE {1, 0}, DAMAGED {1, -2} | pass |
| INV-S-08 | R4 | happy | SS | `search="x n"` (middle of "Hex Nut") | records 1 (B); total_qty 2; estimated_value 0; by_type only STORAGE {1, 2} | pass |
| INV-S-09 | R4 [BUG-702] | bug | items "100% Cotton", "Cotton Blend" (W1, unit "pcs"); rows qty 2 avg 1.00 and qty 3 avg 1.00 (STORAGE, F1) | `search="%"` | records 1; total_qty 2; estimated_value 2.00 | xfail BUG-702 — fails today on: records 2 |
| INV-S-10 | R5 | happy | W1 rows `INV(I1, STORAGE, F1, 2)`, `INV(I1, STORAGE, F2, 3)`, `INV(I2, STORAGE, F1, 1)` | stats with defaults | by_type = one entry STORAGE {unique_item_count 2 (distinct items, not 3 rows), total_qty 6}; records 3 | pass |
| INV-S-11 | R6 [BUG-719] | bug | W1 rows qty 1 each, inserted in this order: I1 SCRAP F1, I1 WASTE F1, I1 DAMAGED F1, I1 STORAGE F1 | stats with defaults | by_type types in order [STORAGE, DAMAGED, WASTE, SCRAP] | xfail BUG-719, **non-strict** (spec Notes: may XPASS today) — expected to fail today on: order differs (database grouping order); an XPASS is reported as a discrepancy, never fixed by weakening the assertion |

## `InventoryManager.delete_inventory`

All cases use T unless stated; zero ledger rows before the call.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-D-01 | R3 R5 R6 | happy | T | delete T.id | returns T (same id); re-read qty 0, updated_by U1, is_deleted False, is_active True, avg_price 5.00, note "n1"; exactly one ledger row: workspace W1, type STORAGE, factory F1, item I1, transaction_type `"inventory_adjustment"`, quantity 10, unit_cost 5.00, total_cost 50.00, qty_before 10, qty_after 0, avg_price_before 5.00, avg_price_after 5.00, source_type `"adjustment"`, notes `"Stock cleared"`, performed_by U1 | pass |
| INV-D-02 | R5 R6 | boundary | `INV(W1, I1, STORAGE, F1, 1, 5.00, "n1")` | delete it | returns the row; qty 0; one ledger row quantity 1, qty_before 1, total_cost 5.00 | pass |
| INV-D-03 | R4 | boundary | `INV(W1, I1, STORAGE, F1, 0, 5.00, "n1")` | delete it | returns the row (same id); re-read qty 0, updated_by NULL, avg_price 5.00, note "n1", is_deleted False; zero ledger rows | pass |
| INV-D-04 | R6 | happy | `INV(W1, I1, STORAGE, F1, 10, None, "n1")` | delete it | returns the row; qty 0; one ledger row: quantity 10, unit_cost NULL, total_cost NULL, avg_price_before NULL, avg_price_after NULL | pass |
| INV-D-05 | R6 | happy | `INV(W1, I1, STORAGE, F1, 10, 0.00, "n1")` | delete it | returns the row; qty 0; one ledger row: quantity 10, unit_cost 0.00, avg_price_before 0.00, avg_price_after 0.00 | pass |
| INV-D-06 | R6 [BUG-707] | bug | `INV(W1, I1, STORAGE, F1, 10, 0.00, "n1")` | delete it | returns the row (same id); the ledger row's total_cost is 0.00 | xfail BUG-707 — fails today on: total_cost NULL |
| INV-D-07 | R4 R5 R6 [BUG-716] | bug | `INV(W1, I1, STORAGE, F1, -4, 5.00, "n1")` | delete it | returns the row (same id); re-read qty 0, updated_by U1; exactly one ledger row: transaction_type `"inventory_adjustment"`, quantity 4, qty_before -4, qty_after 0, unit_cost 5.00, total_cost 20.00, notes `"Stock cleared"`, performed_by U1 | xfail BUG-716 — fails today on: qty still -4 |
| INV-D-08 | R3 | happy | `INV(W1, I1, STORAGE, F1, -4, 5.00, "n1")` | delete it | returns the row (same id); re-read is_deleted False, is_active True, avg_price 5.00, note "n1" | pass |
| INV-D-09 | R4 R7 | happy | T | delete T.id as U1, then delete T.id again as U2 | both calls return T; re-read qty 0, updated_by U1 (second call wrote nothing); exactly one ledger row for the bucket | pass |
| INV-D-10 | R1, Errors row 1 | error | T | delete MISSING | raises `HTTPException` 404, detail `"Inventory record with ID {MISSING} not found"`; T unchanged (qty 10, updated_by NULL); zero ledger rows in W1 | pass |
| INV-D-11 | R1, Errors row 1 | isolation | TX (W2) | delete TX.id with W1 | raises 404 `"Inventory record with ID {TX.id} not found"`; TX unchanged (qty 10, updated_by NULL); zero ledger rows in W1 and W2 | pass |
| INV-D-12 | R2, Errors row 2 | soft-delete | TD (soft-deleted, qty 10) | delete TD.id | raises `HTTPException` 400, detail `"Cannot clear stock on a deactivated inventory record"`; TD unchanged (qty 10, updated_by NULL, is_deleted True); zero ledger rows | pass |
| INV-D-13 | R8 [BUG-705] | bug | T; SQL capture on | delete T.id | returns T (same id); a locked read of `inventory` (`… FOR UPDATE OF inventory`) was issued during the call; no `SELECT` from `inventory` has `NOWAIT` / `SKIP LOCKED` (see SQL capture) | xfail BUG-705 — fails today on: no `SELECT … FOR UPDATE OF inventory` issued |

## `InventoryManager.get_incoming_summary_for_factory`

Default call: `workspace_id=W1, factory_id=F1`. "PO_k"/"TR_k" numbers are `"PO-000k"` / `"TR-000k"`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-IF-01 | R3 R5 R9 R10 R11 | happy | PO_1 lines [(I1, 10, 3)] | default call | returns exactly [{factory_id F1, item_id I1, total_pending_qty `Decimal("7")`, order_count 1, orders [{order_kind "purchase", order_id PO_1.id, order_number "PO-0001", status_name "Ordered", pending_qty `Decimal("7")`}]}] | pass |
| INV-IF-02 | R6 R7 R9 R10 | happy | TR_1 lines [(I1, 4)] | default call | returns exactly [{F1, I1, total 4, order_count 1, orders [{"transfer", TR_1.id, "TR-0001", "In Transit", 4}]}] | pass |
| INV-IF-03 | R1, Errors row 1 | error | — | `factory_id=MISSING` | raises `HTTPException` 404, detail `"Factory with ID {MISSING} not found"`; W1 row counts unchanged | pass |
| INV-IF-04 | R1, Errors row 1 | isolation | PO in W2 to FX lines [(IX, 5, 0)] | `factory_id=FX` (with W1) | raises 404 `"Factory with ID {FX} not found"` | pass |
| INV-IF-05 | R2 [BUG-718], Errors row 1 | bug | PO_1 to F_del lines [(I1, 10, 0)] | `factory_id=F_del` | raises 404 `"Factory with ID {F_del} not found"` | xfail BUG-718 — fails today on: summary returned, no error |
| INV-IF-06 | R2 | boundary | PO_1 to F_in lines [(I1, 10, 0)] | `factory_id=F_in` | returns [{factory_id F_in, item_id I1, total 10, order_count 1, orders [PO_1 entry, pending 10]}] | pass |
| INV-IF-07 | R3 | isolation | PO_1 to F1 [(I1, 5, 0)]; PO_2 to F2 [(I1, 7, 0)]; PO_3 `destination_type "machine"`, `destination_id` = F1.id [(I1, 8, 0)]; PO_4 in W2 (W2 status, no workflow), `destination_type "storage"`, `destination_id` = F1.id [(I1, 9, 0)] | default call | one item I1: total 5, order_count 1, orders [PO_1 entry] | pass |
| INV-IF-08 | R4 | boundary | PO_1 status S_DONE (last of WF) [(I1, 5, 0)]; PO_2 status S_OPEN [(I1, 3, 0)] | default call | one item I1: total 3, orders [PO_2 entry] only | pass |
| INV-IF-09 | R4 | happy | PO_1 with no workflow, status S_DONE [(I1, 5, 0)] | default call | one item I1: total 5, orders [PO_1 entry, status_name "Received"] | pass |
| INV-IF-10 | R4 | happy | workflow WF_E (W1) `status_sequence []`; PO_1 with WF_E, status S_DONE [(I1, 5, 0)] | default call | one item I1: total 5, orders [PO_1 entry] | pass |
| INV-IF-11 | R4 | happy | workflow WF_S (W1) `status_sequence [S_OPEN.id, str(S_DONE.id)]` (last element a string); PO_1 with WF_S, status S_DONE [(I1, 5, 0)] | default call | one item I1: total 5, orders [PO_1 entry] | pass |
| INV-IF-12 | R4 | isolation | workflow WF_X in W2 `status_sequence [S_OPEN.id, S_DONE.id]`; PO_1 (W1) with WF_X, status S_DONE [(I1, 5, 0)] | default call | one item I1: total 5, orders [PO_1 entry] | pass |
| INV-IF-13 | R4 [BUG-717] | bug | PO_1 `voided` True, status S_OPEN [(I1, 6, 0)]; PO_2 status S_OPEN [(I1, 3, 0)] | default call | one item I1: total 3, order_count 1, orders [PO_2 entry] | xfail BUG-717 — fails today on: PO_1 included (total 9) |
| INV-IF-14 | R5 R11 | boundary | PO_1 lines [(I1, 10, 10), (I2, 5, 6), (I3, 5, NULL), (I4, 1, 0), (I5, NULL, NULL)] | default call | returns exactly two items in order: I3 {total 5, orders [PO_1 pending 5]}, I4 {total 1, orders [PO_1 pending 1]}; no entry for I1, I2, I5 | pass |
| INV-IF-15 | R6 | isolation | TR_1 to F1 [(I1, 2)]; TR_2 to F1 with completed_at set [(I1, 3)]; TR_3 to F2 [(I1, 4)]; TR_4 `destination_location_type "machine"`, `destination_location_id` = F1.id [(I1, 5)]; TR_5 in W2 to F1.id [(I1, 6)] | default call | one item I1: total 2, orders [TR_1 entry] | pass |
| INV-IF-16 | R6 R9 | happy | TR_1 in status S_DRAFT, not approved [(I1, 2)] | default call | one item I1: total 2, orders [{"transfer", TR_1.id, "TR-0001", "Draft", 2}] | pass |
| INV-IF-17 | R7 R11 | boundary | TR_1 lines [(I1, 0), (I2, NULL), (I3, -1), (I4, 1)] | default call | returns exactly one item I4: total 1, orders [TR_1 pending 1] | pass |
| INV-IF-18 | R8 R10 | happy | PO_1 lines [(I1, 3, 0), (I1, 4, 0)]; PO_2 lines [(I1, 2, 0)] | default call | one item I1: total 9, order_count 2, orders [PO_1 pending 7, PO_2 pending 2] | pass |
| INV-IF-19 | R8 | boundary | PO with explicit id 987654 lines [(I1, 5, 0)]; TR with explicit id 987654 lines [(I1, 2)] | default call | one item I1: total 7, order_count 2, orders [{"purchase", 987654, pending 5}, {"transfer", 987654, pending 2}] | pass |
| INV-IF-21 | R10 R11 | happy | created in this order: TR_1 [(I2, 1)], TR_2 [(I2, 1)], PO_1 [(I2, 1), (I1, 1)], PO_2 [(I2, 1)] | default call | returns exactly [I1 {total 1, order_count 1, orders [PO_1]}, I2 {total 4, order_count 4, orders [PO_1, PO_2, TR_1, TR_2]}] (by kind and id as listed) | pass |
| INV-IF-22 | R12 | boundary | no POs, no transfers | default call | returns [] | pass |
| INV-IF-23 | R5 R7 R12 | boundary | PO_1 [(I1, 5, 5)]; TR_1 completed [(I1, 3)]; TR_2 [(I1, 0)] | default call | returns [] | pass |

## `InventoryManager.get_incoming_summary`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| INV-IS-01 | R1 | happy | PO_1 to F1 [(I1, 5, 0)]; PO_2 to F2 [(I1, 3, 0)] | `get_incoming_summary(session, workspace_id=W1, factory_id=F1)` | result equals `get_incoming_summary_for_factory(workspace_id=W1, factory_id=F1)` and is exactly [{F1, I1, total 5, order_count 1, orders [PO_1 pending 5]}] (F2 absent) | pass |
| INV-IS-02 | R1, Errors | boundary | F1 exists | `factory_id=0` | raises `HTTPException` 404, detail `"Factory with ID 0 not found"` | pass |
| INV-IS-03 | R1, Errors | isolation | FX (W2) | `factory_id=FX` (W1) | raises 404 `"Factory with ID {FX} not found"` | pass |
| INV-IS-04 | R1 R2 | boundary | PO_1 to F_in [(I1, 4, 0)] | `factory_id=F_in` | returns [{factory_id F_in, I1, total 4, orders [PO_1]}] (given id is summarised although inactive) | pass |
| INV-IS-05 | R2 | happy | F3 "Empty Plant" (W1, active, live, nothing incoming); PO_1 to F1 [(I1, 5, 0)]; PO_2 to F2 [(I1, 3, 0)]; PO_3 to F_in [(I1, 4, 0)]; PO_4 to F_del [(I1, 6, 0)]; PO_5 in W2 to FX [(IX, 7, 0)] | `factory_id` omitted | exactly two entries; set of factory_ids {F1, F2}; F1 entry total 5, F2 entry total 3 | pass |
| INV-IS-06 | R2 | boundary | W3 has no factories | `workspace_id=W3`, `factory_id` omitted | returns [] | pass |
| INV-IS-07 | R3 [BUG-709] | bug | W3 with 501 active, live factories "Plant 001".."Plant 501", each with one PO (W3 status, no workflow) lines [(an item of W3, 1, 0)] | `workspace_id=W3`, `factory_id` omitted | 501 entries; the set of factory_ids equals all 501 factory ids | xfail BUG-709 — fails today on: only 500 entries |
| INV-IS-08 | R4 [BUG-706] | bug | W3 factories created in order "charlie", "Bravo", "alpha" (active, live), each with one PO lines [(an item of W3, 1, 0)] | `workspace_id=W3`, `factory_id` omitted | factory_ids in result order = [alpha, Bravo, charlie] | xfail BUG-706 — fails today on: order = insertion (heap) order [charlie, Bravo, alpha] (spec Notes) |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_inventory` R4, `update_inventory` R4 (422 at the API) | `POST /inventory/`, `PUT/PATCH /inventory/{id}/` | Negative / over-precise `qty`/`avg_price` answer 422 and write nothing |
| `update_inventory` R5 (`qty: null` → 422) | `PUT/PATCH /inventory/{id}/` | JSON body `{"qty": null}` reaches the manager with `qty` in `model_fields_set` and answers 422 "qty cannot be empty" |
| `create_inventory` R9 (IntegrityError → 409 at the API) | global DB-error handler / `POST /inventory/` | A concurrent duplicate answers 409, not 500 |
| `update_inventory` R10, `delete_inventory` R8 (real concurrency) | integration tests on `InventoryService` with two sessions | Second concurrent adjustment sees the first's committed qty; second concurrent clear writes no ledger entry |
| `get_inventory_page` inputs (`skip >= 0`, `1 <= limit <= 1000`, HR-7) | `GET /inventory/` | Out-of-range `skip`/`limit` answer 422 |
| Commit / rollback of every write | `InventoryService` | Service commits on success and rolls back on error; manager never commits |

## Spec gaps
None. (Earlier gaps 1–8 closed by the spec's Gap log G1–G8.)

## Retired IDs
- INV-IF-20 — tested a transfer with no current status; spec G4 / R9: `current_status_id` is NOT NULL on purchase and transfer orders, so the `None` fallback is unreachable and needs no test.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_inventory` | R1 | INV-C-10, INV-C-11 |
| `create_inventory` | R2 [BUG-715] | INV-C-12, INV-C-13 |
| `create_inventory` | R3 [BUG-710] | INV-C-14, INV-C-15 (positive side: INV-C-01) |
| `create_inventory` | R3a | INV-C-30 |
| `create_inventory` | R4 [BUG-711][BUG-708] | INV-C-16, INV-C-17, INV-C-18, INV-C-19, INV-C-20, INV-C-21, INV-C-22, INV-C-01 (note as given) |
| `create_inventory` | R5 [BUG-714] | INV-C-23, INV-C-24, INV-C-25, INV-C-26, INV-C-27, INV-C-28 |
| `create_inventory` | R6 | INV-C-01 |
| `create_inventory` | R6a [BUG-714] | INV-C-28 |
| `create_inventory` | R7 | INV-C-01, INV-C-02, INV-C-03, INV-C-05, INV-C-06 |
| `create_inventory` | R7a [BUG-712] | INV-C-04, INV-C-03 (avg None side) |
| `create_inventory` | R8 [BUG-707] | INV-C-01, INV-C-07, INV-C-08, INV-C-09 |
| `create_inventory` | R9 | INV-C-29 |
| `create_inventory` | Errors: factory 404 | INV-C-10, INV-C-11, INV-C-12 |
| `create_inventory` | Errors: item 404 | INV-C-14, INV-C-15 |
| `create_inventory` | Errors: ValidationError | INV-C-16, INV-C-18, INV-C-19, INV-C-21 |
| `create_inventory` | Errors: 409 live duplicate | INV-C-23 |
| `create_inventory` | Errors: concurrent IntegrityError | INV-C-29 |
| `update_inventory` | R1 | INV-U-17, INV-U-18 |
| `update_inventory` | R2 | INV-U-19 |
| `update_inventory` | R3 | INV-U-01, INV-U-02, INV-U-05, INV-U-10, INV-U-15 |
| `update_inventory` | R4 [BUG-711][BUG-708] | INV-U-20, INV-U-21, INV-U-22, INV-U-23, INV-U-24, INV-U-25, INV-U-26, INV-U-04 |
| `update_inventory` | R5 [BUG-713] | INV-U-27, INV-U-28, INV-U-29, INV-U-31 |
| `update_inventory` | R6 [BUG-712] | INV-U-02, INV-U-05, INV-U-06, INV-U-11, INV-U-12, INV-U-13, INV-U-28, INV-U-32 |
| `update_inventory` | R6a [BUG-712] | INV-U-11, INV-U-12, INV-U-28, INV-U-31, INV-U-32, INV-U-05 (both change → single R7 entry), INV-U-13 (same value → no entry) |
| `update_inventory` | R7 [BUG-707] | INV-U-02, INV-U-03, INV-U-04, INV-U-05, INV-U-07, INV-U-08, INV-U-09, INV-U-25, INV-U-26 |
| `update_inventory` | R8 | INV-U-01, INV-U-05 |
| `update_inventory` | R9 [BUG-703] | INV-U-01, INV-U-02, INV-U-10, INV-U-14, INV-U-16 |
| `update_inventory` | R10 [BUG-704] | INV-U-30 (concurrency deferred) |
| `update_inventory` | Errors: 404 | INV-U-17, INV-U-18 |
| `update_inventory` | Errors: 400 deleted | INV-U-19 |
| `update_inventory` | Errors: ValidationError | INV-U-20, INV-U-22, INV-U-23, INV-U-24 |
| `update_inventory` | Errors: 422 qty null | INV-U-29 |
| `get_inventory` | R1 | INV-G-01, INV-G-02, INV-G-03 |
| `get_inventory` | R2 | INV-G-04, INV-G-05, INV-G-06, INV-G-07 |
| `get_inventory` | R3 [BUG-700] | INV-G-08 |
| `get_inventory` | R4 [BUG-700] | INV-G-09 |
| `get_inventory` | Errors: 404 | INV-G-04, INV-G-05, INV-G-06, INV-G-07, INV-G-08 |
| `get_inventory_page` | R1 | INV-P-01, INV-P-17 |
| `get_inventory_page` | R2 | INV-P-02, INV-P-03, INV-P-04, INV-P-05, INV-P-06, INV-P-07 |
| `get_inventory_page` | R3 | INV-P-08, INV-P-09, INV-P-16 |
| `get_inventory_page` | R4 [BUG-701] | INV-P-10, INV-P-11, INV-P-12, INV-P-26 |
| `get_inventory_page` | R5 | INV-P-13, INV-P-14, INV-P-15, INV-P-16 |
| `get_inventory_page` | R6 [BUG-702] | INV-P-17, INV-P-18, INV-P-19, INV-P-20, INV-P-21, INV-P-22, INV-P-23, INV-P-24, INV-P-25 |
| `get_inventory_page` | R7 | INV-P-01, INV-P-13, INV-P-16 |
| `get_inventory_page` | R8 | INV-P-01, INV-P-13, INV-P-14, INV-P-15 |
| `get_inventory_stats` | R1 | INV-S-01, INV-S-04, INV-S-05, INV-S-06, INV-S-07 |
| `get_inventory_stats` | R2 | INV-S-01, INV-S-02, INV-S-03 |
| `get_inventory_stats` | R3 | INV-S-01, INV-S-02, INV-S-03, INV-S-07 |
| `get_inventory_stats` | R4 [BUG-702] | INV-S-08, INV-S-09 |
| `get_inventory_stats` | R5 | INV-S-01, INV-S-02, INV-S-07, INV-S-10 |
| `get_inventory_stats` | R6 [BUG-719] | INV-S-11 |
| `delete_inventory` | R1 | INV-D-10, INV-D-11 |
| `delete_inventory` | R2 | INV-D-12 |
| `delete_inventory` | R3 | INV-D-01, INV-D-08 |
| `delete_inventory` | R4 [BUG-716] | INV-D-03, INV-D-07, INV-D-08 |
| `delete_inventory` | R5 | INV-D-01, INV-D-02, INV-D-07 |
| `delete_inventory` | R6 [BUG-707] | INV-D-01, INV-D-04, INV-D-05, INV-D-06, INV-D-07 |
| `delete_inventory` | R7 | INV-D-09 |
| `delete_inventory` | R8 [BUG-705] | INV-D-13 (concurrency deferred) |
| `delete_inventory` | Errors: 404 | INV-D-10, INV-D-11 |
| `delete_inventory` | Errors: 400 deleted | INV-D-12 |
| `get_incoming_summary_for_factory` | R1 | INV-IF-03, INV-IF-04 |
| `get_incoming_summary_for_factory` | R2 [BUG-718] | INV-IF-05, INV-IF-06 |
| `get_incoming_summary_for_factory` | R3 | INV-IF-01, INV-IF-07 |
| `get_incoming_summary_for_factory` | R4 [BUG-717] | INV-IF-08, INV-IF-09, INV-IF-10, INV-IF-11, INV-IF-12, INV-IF-13 |
| `get_incoming_summary_for_factory` | R5 | INV-IF-01, INV-IF-14, INV-IF-23 |
| `get_incoming_summary_for_factory` | R6 | INV-IF-02, INV-IF-15, INV-IF-16 |
| `get_incoming_summary_for_factory` | R7 | INV-IF-02, INV-IF-17, INV-IF-23 |
| `get_incoming_summary_for_factory` | R8 | INV-IF-18, INV-IF-19 |
| `get_incoming_summary_for_factory` | R9 | INV-IF-01, INV-IF-02, INV-IF-09, INV-IF-16 |
| `get_incoming_summary_for_factory` | R10 | INV-IF-01, INV-IF-18, INV-IF-21 |
| `get_incoming_summary_for_factory` | R11 | INV-IF-14, INV-IF-17, INV-IF-21 |
| `get_incoming_summary_for_factory` | R12 | INV-IF-22, INV-IF-23 |
| `get_incoming_summary_for_factory` | Errors: factory 404 | INV-IF-03, INV-IF-04, INV-IF-05 |
| `get_incoming_summary` | R1 | INV-IS-01, INV-IS-02, INV-IS-03, INV-IS-04 |
| `get_incoming_summary` | R2 | INV-IS-05, INV-IS-06 |
| `get_incoming_summary` | R3 [BUG-709] | INV-IS-07 |
| `get_incoming_summary` | R4 [BUG-706] | INV-IS-08 |
| `get_incoming_summary` | Errors (as per-factory) | INV-IS-02, INV-IS-03 |
