# Test cases — `app/managers/to_inventory.py`

> **Spec:** `tests/unit/managers/to_inventory.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec Gap log G1–G5 closed all five gaps: schema required fields given (G1 → Conventions); Numeric(15,2) scale + rounding observation (G2 → new IN-39); machine null-average with stock on hand defined (G3 → new IN-40); `_post_location_out` R1a [BUG-823] added (G4 → IN-35..38 re-mapped, new IN-41, IN-42); `transfer_order_events` named (G5 → P-02 asserts it). No verifier report exists.
> **Revision:** 3 — re-run; spec unchanged since revision 2. Full self-check passed. The only edit makes the setup concrete: P-07's pre-existing L2 ledger row now names its bucket and values. Counts unchanged.
> **Revision:** 4 — 2026-10-30, owner ruling BUG-1040 (all money rounds half up, HR-15); spec R5 split into R5 and R5a, new R6a, both [BUG-1040]; G2 updated. IN-08 now expects `1.03` and IN-39 `total_cost 0.13`, both strict xfails. In IN-39 `total_cost` moves to the last Then, so every value that holds today is checked before the expected failure. No cases added or retired.
> **Counts:** 121 cases · 95 expected-to-pass · 26 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `_quantity_to_int` 18 cases (6 bug; 9 of the 18 build the item schemas) · `_line_already_posted` 10 (0 bug) · `_post_location_out` 34 (8 bug) · `_post_location_in` 42 (12 bug; 16 of the 42 build the transfer-order schemas — IN-35..38, IN-41, IN-42 serve `_post_location_out` R1a and are kept in this table so their IDs stay stable) · `post_transfer_order_inventory` 17 (0 bug).
- **Notable design choices:**
  - The five bug rules that are fixed in other files are handled two ways. Schema fixes (BUG-823, BUG-824) get direct schema cases here. Manager/caller fixes (BUG-821, BUG-825) are deferred.
  - The HR-10 lock (BUG-820) is checked by capturing SQL: a `SELECT … FOR UPDATE` on the stock table must be emitted before the ledger INSERT. The race itself is integration-only.
  - Shortage errors (BUG-826) are split. The pass cases assert status 400, the substring `stock (A available, Q requested)` (true both today and after the fix), and that no ledger row was written. The xfail cases assert the exact new message.
  - Source-type entry validation is now `_post_location_out` R1a [BUG-823]; its schema cases keep their IN-35..38 IDs. An omitted/None source type on `TransferOrderUpdate` stays allowed (IN-41).
  - IN-39 is the optional 3-decimal unit-cost case the spec allows (G2); it expects `total_cost` to round half away from zero, the same as Postgres storing the unrounded values, so one row agrees with itself (BUG-1040, strict xfail until the fix) (best-practice default, delegated by reviewer: include it, it is cheap and catches a rounding regression).
  - Error cases in `post_transfer_order_inventory` assert what stays flushed in the session (R5/R6), not a rollback. There is no race simulation.
- **Needs a decision:** None. All previous gaps were closed by the spec; no new gaps.

## Conventions for this module
- **IDs:** `TOI` = to_inventory. `Q` = `_quantity_to_int`, `LP` = `_line_already_posted`, `OUT` = `_post_location_out`, `IN` = `_post_location_in`, `P` = `post_transfer_order_inventory`.
- **Rows used in every DB test:**
  - W1, W2 = two workspaces. U1 = a profile in W1; U2 = a profile in W2. ST = a `statuses` row usable as a transfer order's `current_status_id`.
  - I1 = item "Bearing 6204" in W1. I2 = item "Grease EP2" in W1. IX = item "Cable" in **W2** (used as "item not found in this workspace").
  - F1, F2 = active factories in W1. FX = factory in W2. FD = factory in W1 with `is_deleted = True`.
  - M1, M2 = active machines in W1. MX = machine in W2. MD = machine in W1 with `is_deleted = True`.
  - TO = transfer order in W1, `transfer_number = "TR-2026-004"`, `current_status_id` ST, created by U1. Its source/destination type+id are set per case (defaults below). L = a line of TO with `line_number = 2`, item I1, quantity `3.00`. All rows are flushed so they have ids. Setup must make `TO.id != L.id`, e.g. by flushing a throw-away extra line first.
- **Seeding factory stock:** `F/TYPE/I = q @ p` means:
  - one `inventory_ledger` row: workspace of F, factory F, item I, inventory type TYPE. Any valid non-transfer `transaction_type` (best-practice default, delegated by reviewer: the purchase-receive type). `source_type = 'purchase_order'`, `source_id = 900001`. `qty_after = q`, `avg_price_after = p` (p may be `null`). `performed_by` U1 (U2 in W2). Explicit `performed_at = 2026-01-01T00:00:00Z` unless a case gives another time.
  - one active `inventory` row for the same bucket with `qty = q`, `avg_price = p`.
  - "ledger-only" means the ledger row without the `inventory` row.
- **Seeding machine stock:** `M/I stock n` = one `machine_items` row (workspace of M, machine M, item I, `qty = n`). `M/I mavg p @ t` = one `machine_item_ledger` row for M/I: non-transfer `transaction_type`, `source_type = 'purchase_order'`, `source_id = 900002`, `qty_after = n` (or as given), `avg_price_after = p`, explicit `performed_at = t`.
- **Default call args:**
  - `_post_location_out`: `item_id = I1.id`, `line = L`, `to = TO`, `workspace_id = W1.id`, `user_id = U1.id`, `dest_type = 'machine'`, `dest_id = M2.id`.
  - `_post_location_in`: the same, plus `source_type = 'machine'`, `source_id = M2.id`.
  - Cases give `location_type`, `location_id`, `qty` and (IN) `unit_cost`.
- **"Nothing written" (NW):** snapshot before the call and compare after, all workspaces:
  - row counts of `inventory_ledger`, `machine_item_ledger` and `machine_activity_events`;
  - every `inventory` row (id, qty, avg_price, is_deleted, is_active) and every `machine_items` row (id, qty);
  - no new `inventory` / `machine_items` rows.
- **Re-read:** every "then" on DB state is read with a fresh query after `session.flush()` (expire the objects first), not from the in-memory rows. On error cases the assertions are made in the same session right after catching the exception (earlier writes stay flushed; R5/R6).
- **"New row for L":** the row with `source_type = 'transfer_order'` and `source_id = L.id`. "Exactly one" means the count of such rows in that ledger is 1.
- **Decimals:** assert with `Decimal` equality (`Decimal('4.00') == Decimal('4')`), so trailing-zero scale does not matter.
- **SQL capture:** a SQLAlchemy `before_cursor_execute` listener on the test connection records every statement executed during the action only. "Lock on T" means at least one captured statement is a SELECT from table T that contains `FOR UPDATE`, **and** it comes before the first captured INSERT into the ledger table of that case.
- **Externals mocked:** none. `utcnow` is not mocked; every seeded ledger row has an explicit past `performed_at`, so "latest" never depends on the call time.
- **Race simulations:** none.
- **Schema cases** (target `schema`), no DB needed. "Otherwise valid" means exactly: `TransferOrderItemCreate(item_id=1, quantity=<under test>)` (`notes` omitted); `TransferOrderItemUpdate(<field under test>)` only (no required fields); `TransferOrderCreate(source_location_type='storage', source_location_id=1, destination_location_type='storage', destination_location_id=1)` with only the field under test replaced (`description`, `current_status_id`, `items` omitted); `TransferOrderUpdate(<field under test>)` only.

## `_quantity_to_int`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TOI-Q-01 | R1 | happy | — (pure) | call with each of `Decimal('5')`, `Decimal('5.0')`, `Decimal('5.00')`, `line_number=1` | each returns `5` and `type(result) is int` | pass |
| TOI-Q-02 | R1 | boundary | — | `Decimal('1')`, `line_number=1` | returns `1`, `type is int` | pass |
| TOI-Q-03 | R2 | error | — | `Decimal('2.5')`, `line_number=2` | raises `HTTPException`, `status_code == 400`, `detail == "Line 2 has a fractional quantity; inventory transfers require whole units"` | pass |
| TOI-Q-04 | R2 | boundary | — | `Decimal('0.01')`, `line_number=3` | 400, detail `"Line 3 has a fractional quantity; inventory transfers require whole units"` | pass |
| TOI-Q-05 | R2 | boundary | — | `Decimal('10.99')`, `line_number=7` | 400, detail `"Line 7 has a fractional quantity; inventory transfers require whole units"` | pass |
| TOI-Q-06 | R3 | boundary | — | `Decimal('0')`, `line_number=4` | 400, detail `"Line 4 has no quantity to transfer"` | pass |
| TOI-Q-07 | R3 | boundary | — | `Decimal('0.00')`, `line_number=1` | 400, detail `"Line 1 has no quantity to transfer"` | pass |
| TOI-Q-08 | R3 | error | — | `Decimal('-3')`, `line_number=5` | 400, detail `"Line 5 has no quantity to transfer"` | pass |
| TOI-Q-09 | R4 | error | — | `Decimal('-2.5')`, `line_number=6` | 400, detail `"Line 6 has a fractional quantity; inventory transfers require whole units"` (not the "no quantity" message) | pass |
| TOI-Q-10 | R5 | boundary | schema | build `TransferOrderItemCreate` with `quantity=Decimal('1')`, otherwise valid | no error; `.quantity == 1` | pass |
| TOI-Q-11 | R5 | boundary | schema | build `TransferOrderItemCreate` with `quantity=Decimal('5.00')`, otherwise valid | no error; `.quantity == 5` | pass |
| TOI-Q-12 | R5 | boundary | schema | build `TransferOrderItemUpdate(quantity=Decimal('5'))` | no error; `.quantity == 5` | pass |
| TOI-Q-13 | R5 [BUG-824] | bug | schema | build `TransferOrderItemCreate` with `quantity=Decimal('2.5')`, otherwise valid | raises `pydantic.ValidationError` whose errors mention field `quantity` | xfail BUG-824 — fails today on: no error raised |
| TOI-Q-14 | R5 [BUG-824] | bug | schema | `TransferOrderItemCreate`, `quantity=Decimal('0')` | raises `ValidationError` on `quantity` | xfail BUG-824 — fails today on: no error raised |
| TOI-Q-15 | R5 [BUG-824] | bug | schema | `TransferOrderItemCreate`, `quantity=Decimal('-3')` | raises `ValidationError` on `quantity` | xfail BUG-824 — fails today on: no error raised |
| TOI-Q-16 | R5 [BUG-824] | bug | schema | `TransferOrderItemUpdate(quantity=Decimal('2.5'))` | raises `ValidationError` on `quantity` | xfail BUG-824 — fails today on: no error raised |
| TOI-Q-17 | R5 [BUG-824] | bug | schema | `TransferOrderItemUpdate(quantity=Decimal('0'))` | raises `ValidationError` on `quantity` | xfail BUG-824 — fails today on: no error raised |
| TOI-Q-18 | R5 [BUG-824] | bug | schema | `TransferOrderItemUpdate(quantity=Decimal('-3'))` | raises `ValidationError` on `quantity` | xfail BUG-824 — fails today on: no error raised |

## `_line_already_posted`

Setup for all rows: TO with lines L (quantity 3.00) and L2 (line_number 3). `TO.id` differs from both line ids.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TOI-LP-01 | R1, R4 | happy | one `inventory_ledger` row: W1, F1, I1, STORAGE, `transaction_type='transfer_out'`, `source_type='transfer_order'`, `source_id=L.id`; no machine ledger rows | `_line_already_posted(session, W1.id, L.id)` | returns `True` (`is True`) | pass |
| TOI-LP-02 | R2, R4 | happy | no inventory ledger row for L; one `machine_item_ledger` row W1, M1, I1, `transaction_type='transfer_in'`, `source_type='transfer_order'`, `source_id=L.id` | call for (W1, L.id) | returns `True` | pass |
| TOI-LP-03 | R3 | happy | an `inventory_ledger` and a `machine_item_ledger` row, both W1, `'transfer_order'`, `source_id=L2.id`; nothing for L | call for (W1, L.id) | returns `False` (`is False`) | pass |
| TOI-LP-04 | R4 | boundary | only one `inventory_ledger` row W1, `'transfer_order'`, `source_id=L.id`, `transaction_type='transfer_in'` | call for (W1, L.id) | returns `True` | pass |
| TOI-LP-05 | R4 | boundary | only one `machine_item_ledger` row W1, `'transfer_order'`, `source_id=L.id`, `transaction_type='transfer_out'` | call for (W1, L.id) | returns `True` | pass |
| TOI-LP-06 | R5 | isolation | one `inventory_ledger` row in **W2** (FX, IX, STORAGE, `transfer_out`, `'transfer_order'`, `source_id=L.id`, performed_by U2); nothing in W1 | call for (W1, L.id) | returns `False` | pass |
| TOI-LP-07 | R5 | isolation | one `machine_item_ledger` row in **W2** (MX, IX, `transfer_in`, `'transfer_order'`, `source_id=L.id`); nothing in W1 | call for (W1, L.id) | returns `False` | pass |
| TOI-LP-08 | R5 | boundary | one `inventory_ledger` row W1, `source_type='purchase_order'`, `source_id=L.id` | call for (W1, L.id) | returns `False` | pass |
| TOI-LP-09 | R5 | boundary | one `machine_item_ledger` row W1, `source_type='work_order'`, `source_id=L.id` | call for (W1, L.id) | returns `False` | pass |
| TOI-LP-10 | R1, R3 | boundary | one `inventory_ledger` row W1, `'transfer_order'`, `source_id=TO.id` (the order id, not a line id) | call for (W1, L.id) | returns `False` | pass |

## `_post_location_out`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TOI-OUT-01 | R1 | error | F1/STORAGE/I1 = 10 @ 4.00 | `location_type='project'`, `location_id=F1.id`, `qty=3` | raises `HTTPException` 400, detail `"Unsupported source location type: project"`; NW | pass |
| TOI-OUT-02 | R1 | boundary | F1/STORAGE/I1 = 10 @ 4.00 | `location_type='Storage'`, F1, `qty=3` | 400, detail `"Unsupported source location type: Storage"`; NW | pass |
| TOI-OUT-03 | R1 | boundary | F1/STORAGE/I1 = 10 @ 4.00 | `location_type=''`, F1, `qty=3` | 400, detail `"Unsupported source location type: "`; NW | pass |
| TOI-OUT-04 | R2, R4, R6, R7 | happy | F1/STORAGE/I1 = 10 @ 4.00; no DAMAGED bucket row for F1/I1 | `'storage'`, F1, `qty=3` | returns `Decimal('4.00')`. **Ledger:** exactly one new `inventory_ledger` row for L, with `workspace_id` W1, `inventory_type` STORAGE, `factory_id` F1, `item_id` I1, `transaction_type 'transfer_out'`, `quantity 3`, `unit_cost 4.00`, `total_cost 12.00`, `qty_before 10`, `qty_after 7`, `avg_price_before 4.00`, `avg_price_after 4.00`, `transfer_destination_type 'machine'`, `transfer_destination_id M2.id`, `transfer_source_type` null, `transfer_source_id` null, `notes "TR-2026-004 line 2 transfer out"`, `performed_by U1`. **Bucket:** F1/STORAGE/I1 inventory row `qty 7`, `avg_price 4.00`, `updated_by U1`. **Untouched:** no F1/DAMAGED/I1 inventory row exists; no `machine_activity_events` row; no `machine_item_ledger` row | pass |
| TOI-OUT-05 | R2, R6, R7 | happy | F1/DAMAGED/I1 = 6 @ 2.50; F1/STORAGE/I1 = 10 @ 4.00 | `'damaged'`, F1, `qty=2` | returns `Decimal('2.50')`. One new ledger row for L: `inventory_type` DAMAGED, `qty_before 6`, `qty_after 4`, `unit_cost 2.50`, `total_cost 5.00`. DAMAGED inventory row qty 4, avg 2.50. STORAGE inventory row still qty 10, avg 4.00, and no new STORAGE ledger row | pass |
| TOI-OUT-06 | R4 | side-effect | F1/STORAGE/I1 = 5 @ 3.00 **ledger-only** (no `inventory` row) | `'storage'`, F1, `qty=2` | returns `Decimal('3.00')`. Exactly one F1/STORAGE/I1 inventory row now exists: `qty 3`, `avg_price 3.00`, `created_by U1`, `updated_by U1`, `is_deleted False`. New ledger row: `qty_before 5`, `qty_after 3` | pass |
| TOI-OUT-07 | R4 | soft-delete | F1/STORAGE/I1 ledger row 8 @ 5.00. Its inventory row is soft-deleted: `is_deleted True`, `is_active False`, `deleted_at 2026-01-15T00:00Z`, `deleted_by U1`, qty 0 | `'storage'`, F1, `qty=3` | returns `Decimal('5.00')`. Still exactly one inventory row for the bucket (same id), with `is_deleted False`, `is_active True`, `deleted_at` null, `deleted_by` null, `qty 5`, `avg_price 5.00`. New ledger row `qty_before 8`, `qty_after 5` | pass |
| TOI-OUT-08 | R4 | side-effect | F1/STORAGE/I1 inventory row `qty 50`, `avg 9.00`. Ledger rows for the bucket: 99 @ 1.00 at 2026-01-01; 10 @ 4.00 at 2026-02-01 (latest) | `'storage'`, F1, `qty=3` | returns `Decimal('4.00')`. New ledger row: `qty_before 10`, `qty_after 7`, `unit_cost 4.00`, `avg_price_before 4.00`. Inventory row `qty 7`, `avg 4.00` | pass |
| TOI-OUT-09 | R4 | side-effect | F1/STORAGE/I1 = 10 @ 4.00 at 2026-01-01. Newer (2026-03-01) ledger rows for other buckets: F1/DAMAGED/I1 50 @ 9.00, F2/STORAGE/I1 60 @ 8.00, F1/STORAGE/I2 70 @ 7.00 | `'storage'`, F1, `qty=3` | returns `Decimal('4.00')`; new ledger row `qty_before 10`, `qty_after 7` | pass |
| TOI-OUT-10 | R4, R5 | error | F1/STORAGE/I1 inventory row `qty 20`, `avg 4.00`, **no ledger rows** for the bucket | `'storage'`, F1, `qty=1` | raises `HTTPException` 400; `"stock (0 available, 1 requested)"` is in `detail`. Re-read in the session: inventory row now `qty 0`, `avg_price` null (aligned, flushed). No `inventory_ledger` row for L; no activity event | pass |
| TOI-OUT-11 | R5, R7 | boundary | F1/STORAGE/I1 = 5 @ 4.00 | `'storage'`, F1, `qty=5` | returns `Decimal('4.00')`; ledger row `qty_before 5`, `qty_after 0`, `total_cost 20.00`; inventory `qty 0`, `avg 4.00` | pass |
| TOI-OUT-12 | R5 | boundary | F1/STORAGE/I1 = 5 @ 4.00 | `'storage'`, F1, `qty=6` | 400; `"stock (5 available, 6 requested)"` in detail; inventory row still `qty 5`, `avg 4.00`; no `inventory_ledger` row for L; ledger/event counts unchanged | pass |
| TOI-OUT-13 | R5b [BUG-826] | bug | as OUT-12 | as OUT-12 | 400; `detail == "Line 2 (Bearing 6204): insufficient stock (5 available, 6 requested)"` | xfail BUG-826 — fails today on: detail is `"Insufficient stock (5 available, 6 requested)"` |
| TOI-OUT-14 | R5b [BUG-826] | bug | no stock for F1/STORAGE/IX | `'storage'`, F1, `item_id=IX.id`, `qty=1` | 400; `detail == "Line 2 (Item #{IX.id}): insufficient stock (0 available, 1 requested)"` | xfail BUG-826 — fails today on: detail has no "Line 2 (Item #…)" prefix |
| TOI-OUT-15 | R5 | error | no inventory row and no ledger for F1/STORAGE/I2 | `'storage'`, F1, `item_id=I2.id`, `qty=1` | 400; `"stock (0 available, 1 requested)"` in detail. An F1/STORAGE/I2 inventory row now exists with `qty 0`, `avg` null, `created_by U1` (bucket preparation flushed). No ledger row for L | pass |
| TOI-OUT-16 | R5a [BUG-820] | bug | F1/STORAGE/I1 = 10 @ 4.00; SQL capture on | `'storage'`, F1, `qty=3` | returns `Decimal('4.00')`; lock on `inventory` (a SELECT on `inventory` with `FOR UPDATE`, before the INSERT into `inventory_ledger`) | xfail BUG-820 — fails today on: no captured SELECT on `inventory` contains `FOR UPDATE` |
| TOI-OUT-17 | R3 | error | F1/STORAGE/I1 = 10 @ 4.00 | `'storage'`, `location_id=999999999`, `qty=3` | 404, detail `"Factory with ID 999999999 not found"`; NW | pass |
| TOI-OUT-18 | R3 | isolation | FX/STORAGE/IX = 10 @ 4.00 (in W2, performed_by U2) | `'storage'`, `location_id=FX.id`, `item_id=IX.id`, `qty=3`, `workspace_id=W1` | 404, detail `"Factory with ID {FX.id} not found"`; NW (W2 bucket still qty 10; no W1 inventory row for FX) | pass |
| TOI-OUT-19 | R3a [BUG-822] | bug | FD/STORAGE/I1 = 10 @ 4.00 (FD soft-deleted) | `'storage'`, `location_id=FD.id`, `qty=3` | raises 404, detail `"Factory with ID {FD.id} not found"`; NW (FD bucket qty 10; no ledger row for L) | xfail BUG-822 — fails today on: no exception (returns 4.00 and writes a ledger row) |
| TOI-OUT-20 | R8, R9, R10, R11, R12 | happy | M1/I1 stock 10. Ledger rows: M1/I1 mavg 1.00 @ 2026-01-01; M1/I1 mavg 6.00 @ 2026-02-01 with `qty_after 99` (so the ledger qty disagrees with stock) | `'machine'`, M1, `qty=4`, `dest_type='storage'`, `dest_id=F2.id` | returns `Decimal('6.00')`. **Ledger:** exactly one new `machine_item_ledger` row for L: `workspace_id W1`, `machine_id M1`, `item_id I1`, `transaction_type 'transfer_out'`, `quantity 4`, `unit_cost 6.00`, `total_cost 24.00`, `qty_before 10`, `qty_after 6`, `value_before 60.00`, `value_after 36.00`, `avg_price_before 6.00`, `avg_price_after 6.00`, `transfer_destination_type 'storage'`, `transfer_destination_id F2.id`, `notes "TR-2026-004 line 2 transfer out"`, `performed_by U1`. **Stock:** M1/I1 `machine_items.qty 6`. **Event:** exactly one new `machine_activity_events` row: `machine_id M1`, `workspace_id W1`, `event_type 'transfer_out'`, `description "Transfer out: 4 units of Bearing 6204 (TR-2026-004)"`, `performed_by U1`, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 4}` (no `work_order_id` key). **Untouched:** no `inventory_ledger` row | pass |
| TOI-OUT-21 | R10 | side-effect | M1/I1 stock 10; M1/I1 mavg 6.00 @ 2026-02-01. Newer (2026-03-01) rows: M2/I1 mavg 50.00; M1/I2 mavg 40.00 | `'machine'`, M1, `qty=1` | returns `Decimal('6.00')`; ledger row `unit_cost 6.00` | pass |
| TOI-OUT-22 | R10 | boundary | M1/I1 stock 5; no machine ledger rows for M1/I1 | `'machine'`, M1, `qty=2` | returns a Decimal `== 0`; ledger row `unit_cost 0`, `total_cost 0`, `value_before 0`, `value_after 0`, `avg_price_before 0`, `avg_price_after 0`, `qty_after 3`; stock qty 3 | pass |
| TOI-OUT-23 | R10 | boundary | M1/I1 stock 5. Ledger rows: mavg 7.00 @ 2026-01-01; mavg **null** @ 2026-02-01 (latest) | `'machine'`, M1, `qty=2` | returns `== 0`; ledger row `unit_cost 0`, `avg_price_after 0` | pass |
| TOI-OUT-24 | R9, R11 | boundary | M1/I1 stock 4; mavg 6.00 @ 2026-02-01 | `'machine'`, M1, `qty=4` | returns `Decimal('6.00')`; ledger row `qty_before 4`, `qty_after 0`, `value_after 0`; stock qty 0 | pass |
| TOI-OUT-25 | R9 | boundary | M1/I1 stock 4; mavg 6.00 | `'machine'`, M1, `qty=5` | 400; `"stock (4 available, 5 requested)"` in detail; stock still 4; no `machine_item_ledger` row for L; no new activity event | pass |
| TOI-OUT-26 | R9a [BUG-826] | bug | as OUT-25 | as OUT-25 | 400; `detail == "Line 2 (Bearing 6204): insufficient machine stock (4 available, 5 requested)"` | xfail BUG-826 — fails today on: detail is `"Insufficient machine stock (4 available, 5 requested)"` |
| TOI-OUT-27 | R9a [BUG-826] | bug | no M1/IX stock row | `'machine'`, M1, `item_id=IX.id`, `qty=1` | 400; `detail == "Line 2 (Item #{IX.id}): insufficient machine stock (0 available, 1 requested)"` | xfail BUG-826 — fails today on: detail has no "Line 2 (Item #…)" prefix |
| TOI-OUT-28 | R9 | error | no `machine_items` row for M1/I2 | `'machine'`, M1, `item_id=I2.id`, `qty=1` | 400; `"stock (0 available, 1 requested)"` in detail. A M1/I2 `machine_items` row now exists with `qty 0` (flushed). No machine ledger row for L; no activity event | pass |
| TOI-OUT-29 | R5a, R9 [BUG-820] | bug | M1/I1 stock 10; mavg 6.00; SQL capture on | `'machine'`, M1, `qty=4` | returns `Decimal('6.00')`; lock on `machine_items` (a SELECT with `FOR UPDATE` before the INSERT into `machine_item_ledger`) | xfail BUG-820 — fails today on: no captured SELECT on `machine_items` contains `FOR UPDATE` |
| TOI-OUT-30 | R8 | error | M1/I1 stock 10 | `'machine'`, `location_id=999999999`, `qty=1` | 404, detail `"Machine with ID 999999999 not found"`; NW | pass |
| TOI-OUT-31 | R8 | isolation | MX/IX stock 10 (W2) | `'machine'`, `location_id=MX.id`, `item_id=IX.id`, `qty=1` | 404, detail `"Machine with ID {MX.id} not found"`; NW (MX stock still 10) | pass |
| TOI-OUT-32 | R8a [BUG-822] | bug | MD/I1 stock 10; MD/I1 mavg 6.00 (MD soft-deleted) | `'machine'`, `location_id=MD.id`, `qty=4` | 404, detail `"Machine with ID {MD.id} not found"`; NW (MD stock 10; no machine ledger row; no activity event) | xfail BUG-822 — fails today on: no exception (returns 6.00 and writes rows) |
| TOI-OUT-33 | R12 | side-effect | M1/IX stock 3 (row in W1 for the W2 item); no machine ledger | `'machine'`, M1, `item_id=IX.id`, `qty=1` | returns `== 0`. Activity event `description "Transfer out: 1 units of Item #{IX.id} (TR-2026-004)"`, metadata `== {"item_id": IX.id, "item_name": "Item #{IX.id}", "quantity": 1}`; M1/IX stock 2 | pass |
| TOI-OUT-34 | R6, R7 | boundary | F1/STORAGE/I1 = 5 @ **null** | `'storage'`, F1, `qty=2` | returns `== 0`. Ledger row `unit_cost 0`, `total_cost 0`, `avg_price_before` null, `avg_price_after` null, `qty_after 3`. Inventory row `qty 3`, `avg_price` null | pass |

## `_post_location_in`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TOI-IN-01 | R1 | error | F1/STORAGE/I1 = 10 @ 4.00 | `location_type='project'`, `location_id=F1.id`, `qty=3`, `unit_cost=Decimal('4.00')` | 400, detail `"Project destination inventory posting is not yet supported"`; NW | pass |
| TOI-IN-02 | R2 | boundary | F1/STORAGE/I1 = 10 @ 4.00 | `'Storage'`, F1, `qty=3`, cost 4.00 | 400, detail `"Unsupported destination location type: Storage"`; NW | pass |
| TOI-IN-03 | R2 | error | same | `'warehouse'`, F1, `qty=3`, cost 4.00 | 400, detail `"Unsupported destination location type: warehouse"`; NW | pass |
| TOI-IN-04 | R2 | boundary | same | `''`, F1, `qty=3`, cost 4.00 | 400, detail `"Unsupported destination location type: "`; NW | pass |
| TOI-IN-05 | R3, R4, R5, R6 | happy | F1/STORAGE/I1 = 10 @ 4.00; no F1/DAMAGED/I1 row | `'storage'`, F1, `qty=5`, `unit_cost=Decimal('7.00')`, `source_type='machine'`, `source_id=M2.id` | returns `None`. **Ledger:** exactly one new `inventory_ledger` row for L: `workspace_id W1`, `inventory_type STORAGE`, `factory_id F1`, `item_id I1`, `transaction_type 'transfer_in'`, `quantity 5`, `unit_cost 7.00`, `total_cost 35.00`, `qty_before 10`, `qty_after 15`, `avg_price_before 4.00`, `avg_price_after 5.00`, `transfer_source_type 'machine'`, `transfer_source_id M2.id`, `transfer_destination_type` null, `transfer_destination_id` null, `notes "TR-2026-004 line 2 transfer in"`, `performed_by U1`. **Bucket:** `qty 15`, `avg 5.00`, `updated_by U1`. **Untouched:** no F1/DAMAGED/I1 row; no activity event; no machine ledger row | pass |
| TOI-IN-06 | R3, R5, R6 | happy | F1/DAMAGED/I1 = 4 @ 2.00; F1/STORAGE/I1 = 10 @ 4.00 | `'damaged'`, F1, `qty=4`, cost 3.00 | returns `None`. New ledger row `inventory_type DAMAGED`, `qty_before 4`, `qty_after 8`, `avg_price_after 2.50`. DAMAGED row `qty 8`, `avg 2.50`. STORAGE row unchanged (10 @ 4.00), no new STORAGE ledger row | pass |
| TOI-IN-07 | R5 | boundary | F1/STORAGE/I1 = 2 @ 1.00 | `'storage'`, F1, `qty=1`, cost 2.00 | returns `None`; ledger `avg_price_after 1.33`; bucket `avg 1.33`, `qty 3` | pass |
| TOI-IN-08 | R5a [BUG-1040] | bug | F1/STORAGE/I1 = 1 @ 1.00 | `'storage'`, F1, `qty=1`, cost `Decimal('1.05')` | returns `None`; weighted value 1.025 rounds half away from zero → ledger `avg_price_after 1.03` and bucket `avg 1.03` | xfail BUG-1040 — fails today on: ledger `avg_price_after` is `1.02` (half to even), not `1.03` |
| TOI-IN-09 | R5 | boundary | F1/STORAGE/I1 = 0 @ 9.00 (ledger `qty_after 0`, avg 9.00; inventory row qty 0) | `'storage'`, F1, `qty=3`, cost 2.00 | returns `None`; ledger `qty_before 0`, `avg_price_before 9.00`, `avg_price_after 2.00`; bucket `qty 3`, `avg 2.00` | pass |
| TOI-IN-10 | R5 | boundary | F1/STORAGE/I1 = 5 @ **null** | `'storage'`, F1, `qty=5`, cost 3.00 | returns `None`; ledger `avg_price_before` null, `avg_price_after 3.00` (not 1.50); bucket `qty 10`, `avg 3.00` | pass |
| TOI-IN-11 | R4, R5, R6 | side-effect | no F1/STORAGE/I1 inventory row, no ledger | `'storage'`, F1, `qty=3`, cost 2.00 | returns `None`. Exactly one F1/STORAGE/I1 inventory row: `qty 3`, `avg 2.00`, `created_by U1`, `updated_by U1`, `is_deleted False`. Ledger `qty_before 0`, `qty_after 3`, `avg_price_before` null, `avg_price_after 2.00`, `total_cost 6.00` | pass |
| TOI-IN-12 | R4 | soft-delete | F1/STORAGE/I1 ledger 4 @ 5.00. Its inventory row is soft-deleted (`is_deleted True`, `is_active False`, `deleted_at 2026-01-15T00:00Z`, `deleted_by U1`) | `'storage'`, F1, `qty=4`, cost 5.00 | returns `None`. Same single row: `is_deleted False`, `is_active True`, `deleted_at` null, `deleted_by` null, `qty 8`, `avg 5.00`. Ledger `qty_before 4` | pass |
| TOI-IN-13 | R4 | side-effect | inventory row `qty 50`, `avg 9.00`. Ledger rows: 99 @ 1.00 at 2026-01-01; 10 @ 4.00 at 2026-02-01 | `'storage'`, F1, `qty=5`, cost 7.00 | ledger `qty_before 10`, `avg_price_before 4.00`, `avg_price_after 5.00`; bucket `qty 15`, `avg 5.00`; returns `None` | pass |
| TOI-IN-14 | R4 | side-effect | inventory row `qty 20`, `avg 9.00`; no ledger rows for the bucket | `'storage'`, F1, `qty=3`, cost 2.00 | ledger `qty_before 0`, `avg_price_before` null, `avg_price_after 2.00`; bucket `qty 3`, `avg 2.00`; returns `None` | pass |
| TOI-IN-15 | R7 | boundary | F1/STORAGE/I1 = 10 @ 4.00 | `'storage'`, F1, `qty=10`, `unit_cost=Decimal('0')` | returns `None`; ledger `unit_cost 0`, `total_cost 0`, `avg_price_after 2.00`; bucket `qty 20`, `avg 2.00` | pass |
| TOI-IN-16 | R4 | error | — | `'storage'`, `location_id=999999999`, `qty=3`, cost 4.00 | 404, detail `"Factory with ID 999999999 not found"`; NW | pass |
| TOI-IN-17 | R4 | isolation | FX/STORAGE/IX = 10 @ 4.00 (W2) | `'storage'`, `location_id=FX.id`, `item_id=IX.id`, `qty=3`, cost 4.00 | 404, detail `"Factory with ID {FX.id} not found"`; NW | pass |
| TOI-IN-18 | R4 [BUG-822] | bug | FD/STORAGE/I1 = 10 @ 4.00 (FD soft-deleted) | `'storage'`, `location_id=FD.id`, `qty=3`, cost 4.00 | 404, detail `"Factory with ID {FD.id} not found"`; NW (FD bucket still qty 10; no ledger row for L) | xfail BUG-822 — fails today on: no exception (bucket becomes 13) |
| TOI-IN-19 | R8, R9, R10, R11 | happy | M1/I1 stock 10. Ledger: mavg 1.00 @ 2026-01-01; mavg 4.00 @ 2026-02-01 | `'machine'`, M1, `qty=5`, cost 7.00, `source_type='storage'`, `source_id=F2.id` | returns `None`. **Ledger:** exactly one new `machine_item_ledger` row for L: `workspace_id W1`, `machine_id M1`, `item_id I1`, `transaction_type 'transfer_in'`, `quantity 5`, `unit_cost 7.00`, `total_cost 35.00`, `qty_before 10`, `qty_after 15`, `value_before 40.00`, `value_after 75.00`, `avg_price_before 4.00`, `avg_price_after 5.00`, `transfer_source_type 'storage'`, `transfer_source_id F2.id`, `notes "TR-2026-004 line 2 transfer in"`, `performed_by U1`. **Stock:** qty 15. **Event:** exactly one new activity event: `machine_id M1`, `workspace_id W1`, `event_type 'transfer_in'`, `description "Transfer in: 5 units of Bearing 6204 (TR-2026-004)"`, `performed_by U1`, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 5}`. **Untouched:** no `inventory_ledger` row | pass |
| TOI-IN-20 | R9 | boundary | M1/I1 stock 0; mavg 9.00 @ 2026-02-01 | `'machine'`, M1, `qty=3`, cost 2.00 | returns `None`; ledger `qty_before 0`, `avg_price_before 9.00`, `avg_price_after 2.00`, `value_before 0`, `value_after 6.00`; stock 3 | pass |
| TOI-IN-21 | R9 | boundary | M1/I1 stock 5; no machine ledger rows | `'machine'`, M1, `qty=5`, cost 4.00 | returns `None`; ledger `avg_price_before 0`, `avg_price_after 2.00`, `value_before 0`, `value_after 20.00`; stock 10 | pass |
| TOI-IN-22 | R9, R10 | boundary | M1/I1 stock 2; mavg 1.00 | `'machine'`, M1, `qty=1`, cost 2.00 | returns `None`; ledger `avg_price_after 1.33`, `value_after 3.99`, `value_before 2.00` | pass |
| TOI-IN-23 | R9 | side-effect | M1/I1 stock 10; mavg 4.00 @ 2026-02-01. Newer (2026-03-01) rows: M2/I1 mavg 50.00; M1/I2 mavg 40.00 | `'machine'`, M1, `qty=5`, cost 7.00 | ledger `avg_price_before 4.00`, `avg_price_after 5.00`; returns `None` | pass |
| TOI-IN-24 | R8, R10 | side-effect | no `machine_items` row for M1/I2 | `'machine'`, M1, `item_id=I2.id`, `qty=3`, cost 2.00 | returns `None`. Exactly one M1/I2 `machine_items` row, `qty 3`. Ledger `qty_before 0`, `qty_after 3`, `avg_price_after 2.00`, `total_cost 6.00` | pass |
| TOI-IN-25 | R8 | error | — | `'machine'`, `location_id=999999999`, `qty=1`, cost 1.00 | 404, detail `"Machine with ID 999999999 not found"`; NW | pass |
| TOI-IN-26 | R8 | isolation | MX/IX stock 10 (W2) | `'machine'`, `location_id=MX.id`, `item_id=IX.id`, `qty=1`, cost 1.00 | 404, detail `"Machine with ID {MX.id} not found"`; NW | pass |
| TOI-IN-27 | R8 [BUG-822] | bug | MD/I1 stock 10 (MD soft-deleted) | `'machine'`, `location_id=MD.id`, `qty=1`, cost 1.00 | 404, detail `"Machine with ID {MD.id} not found"`; NW (MD stock 10; no ledger row; no event) | xfail BUG-822 — fails today on: no exception (stock becomes 11) |
| TOI-IN-28 | R11 | side-effect | no M1/IX stock row | `'machine'`, M1, `item_id=IX.id`, `qty=2`, cost 1.00 | returns `None`. Event `description "Transfer in: 2 units of Item #{IX.id} (TR-2026-004)"`, metadata `== {"item_id": IX.id, "item_name": "Item #{IX.id}", "quantity": 2}` | pass |
| TOI-IN-29 | R2a | boundary | schema | build `TransferOrderCreate` with each of `destination_location_type` = `'storage'`, `'damaged'`, `'machine'`, `'project'`, otherwise valid (source `'storage'`) | no error in each; the field keeps the given value | pass |
| TOI-IN-30 | R2a [BUG-823] | bug | schema | `TransferOrderCreate` with `destination_location_type='Storage'`, otherwise valid | raises `ValidationError` on `destination_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-31 | R2a [BUG-823] | bug | schema | `TransferOrderCreate`, `destination_location_type='warehouse'` | raises `ValidationError` on `destination_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-32 | R2a [BUG-823] | bug | schema | `TransferOrderCreate`, `destination_location_type=''` | raises `ValidationError` on `destination_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-33 | R2a | boundary | schema | `TransferOrderUpdate(destination_location_type='damaged')` | no error; value `'damaged'` | pass |
| TOI-IN-34 | R2a [BUG-823] | bug | schema | `TransferOrderUpdate(destination_location_type='Storage')` | raises `ValidationError` on `destination_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-35 | `_post_location_out` R1a | boundary | schema | `TransferOrderCreate` with each of `source_location_type` = `'storage'`, `'damaged'`, `'machine'`, otherwise valid (destination `'storage'`) | no error in each | pass |
| TOI-IN-36 | `_post_location_out` R1a [BUG-823] | bug | schema | `TransferOrderCreate`, `source_location_type='project'` | raises `ValidationError` on `source_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-37 | `_post_location_out` R1a [BUG-823] | bug | schema | `TransferOrderCreate`, `source_location_type='Storage'` | raises `ValidationError` on `source_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-38 | `_post_location_out` R1a [BUG-823] | bug | schema | `TransferOrderUpdate(source_location_type='warehouse')` | raises `ValidationError` on `source_location_type` | xfail BUG-823 — fails today on: no error raised |
| TOI-IN-39 | R5, R6, R6a [BUG-1040] (G2 rounding) | bug | no F1/STORAGE/I2 inventory row and no ledger for it | `'storage'`, F1, `item_id=I2.id`, `qty=1`, `unit_cost=Decimal('0.125')` | returns `None`. After flush + expire, re-read the new `inventory_ledger` row for L: `unit_cost == Decimal('0.13')`, `avg_price_before` null, `avg_price_after == Decimal('0.13')` (Postgres half away from zero of the unrounded value), `qty_after 1`. F1/STORAGE/I2 inventory row `qty 1`, `avg_price == Decimal('0.13')`. Last, the ledger row's `total_cost == Decimal('0.13')` | xfail BUG-1040 — fails today on: stored `total_cost` is `0.12` (Python half to even), not `0.13` |
| TOI-IN-40 | R9, R10 | boundary | M1/I1 stock 3. Ledger rows: mavg 7.00 @ 2026-01-01; mavg **null** @ 2026-02-01 (latest) | `'machine'`, M1, `qty=1`, `unit_cost=Decimal('4.00')` | returns `None`. New machine ledger row for L: `avg_price_before == 0`, `avg_price_after == Decimal('1.00')` (weighted with 0, not 4.00 and not 4.75), `value_before == 0`, `value_after == Decimal('4.00')`, `qty_before 3`, `qty_after 4`, `total_cost 4.00`. M1/I1 stock qty 4 | pass |
| TOI-IN-41 | `_post_location_out` R1a | boundary | schema | build `TransferOrderUpdate()` (nothing given), `TransferOrderUpdate(source_location_type=None)`, and `TransferOrderUpdate(source_location_type='machine')` | no error in each; `source_location_type` is `None`, `None`, `'machine'` respectively | pass |
| TOI-IN-42 | `_post_location_out` R1a [BUG-823] | bug | schema | `TransferOrderCreate`, `source_location_type=''` | raises `ValidationError` on `source_location_type` | xfail BUG-823 — fails today on: no error raised |

## `post_transfer_order_inventory`

Defaults: TO source `('storage', F1.id)`, destination `('machine', M1.id)`. Call `post_transfer_order_inventory(session, TO, items, W1.id, U1.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TOI-P-01 | R1 | boundary | F1/STORAGE/I1 = 10 @ 4.00 | `items=[]` | returns `0`; NW | pass |
| TOI-P-02 | R3, R7, R9 | happy | L1 (line_number 1, I1, quantity `3.00`); F1/STORAGE/I1 = 10 @ 4.00; no M1/I1 stock | `items=[L1]` | returns `1`. Exactly one `inventory_ledger` row for L1 (`transfer_out`, F1 STORAGE, `quantity 3`, `unit_cost 4.00`, `transfer_destination_type 'machine'`, `transfer_destination_id M1.id`). Exactly one `machine_item_ledger` row for L1 (`transfer_in`, M1, `quantity 3`, `unit_cost 4.00`, `avg_price_after 4.00`, `transfer_source_type 'storage'`, `transfer_source_id F1.id`). F1 bucket `qty 7`. M1/I1 stock `qty 3`. Exactly one new activity event (`transfer_in`, M1), none `transfer_out`. Row count of `transfer_order_events` (model `TransferOrderEvent`) unchanged — no transfer-order event written here | pass |
| TOI-P-03 | R3, R9 | happy | TO source `('machine', M1.id)`, destination `('storage', F2.id)`; L1 I1 qty `4.00`; M1/I1 stock 10; M1/I1 mavg 6.00; F2/STORAGE/I1 = 2 @ 3.00 | `[L1]` | returns `1`. Machine ledger row for L1: `transfer_out`, `unit_cost 6.00`, `transfer_destination_type 'storage'`, `transfer_destination_id F2.id`. Inventory ledger row for L1: F2 STORAGE `transfer_in`, `unit_cost 6.00`, `qty_before 2`, `qty_after 6`, `avg_price_after 5.00`, `transfer_source_type 'machine'`, `transfer_source_id M1.id`. M1 stock 6; F2 bucket 6 @ 5.00. One `transfer_out` event on M1 | pass |
| TOI-P-04 | R9 | boundary | TO destination `('storage', F2.id)`; L1 I1 qty 5; F1/STORAGE/I1 = 5 @ null; F2/STORAGE/I1 = 5 @ 4.00 | `[L1]` | returns `1`; F2 `transfer_in` row `unit_cost 0`, `avg_price_after 2.00`; F2 bucket 10 @ 2.00; F1 bucket qty 0 | pass |
| TOI-P-05 | R9 | boundary | TO source `('machine', M1.id)`, destination `('damaged', F2.id)`; L1 I1 qty 5; M1/I1 stock 5, no machine ledger; no F2/DAMAGED/I1 row | `[L1]` | returns `1`; F2 DAMAGED `transfer_in` row `unit_cost 0`, `avg_price_after 0`; F2/DAMAGED/I1 bucket `qty 5`, `avg 0`; M1 stock 0 | pass |
| TOI-P-06 | R3 | happy | TO source `('damaged', F1.id)`, destination `('storage', F1.id)`; L1 I1 qty 2; F1/DAMAGED/I1 = 6 @ 2.50; F1/STORAGE/I1 = 4 @ 5.00 | `[L1]` | returns `1`. DAMAGED `transfer_out` row (`unit_cost 2.50`, `transfer_destination_type 'storage'`, `transfer_destination_id F1.id`). STORAGE `transfer_in` row (`unit_cost 2.50`, `avg_price_after 4.17`, `transfer_source_type 'damaged'`, `transfer_source_id F1.id`). DAMAGED bucket 4 @ 2.50; STORAGE bucket 6 @ 4.17; no activity event | pass |
| TOI-P-07 | R2, R7 | side-effect | L1 (I1, `1.00`), L2 (I2, `2.00`), L3 (I1, `3.00`), line_numbers 1–3. F1/STORAGE/I1 = 10 @ 4.00; F1/STORAGE/I2 = 10 @ 1.00. Pre-existing `inventory_ledger` row W1, F1, I2, STORAGE, `transfer_out`, `'transfer_order'`, `source_id=L2.id`, `quantity 2`, `qty_after 12`, `avg_price_after 1.00`, performed_at 2025-12-01 (older than the 2026-01-01 seed, so it does not change the aligned bucket) | `[L1, L2, L3]` | returns `2`. L1 and L3 each have exactly one inventory `transfer_out` and one machine `transfer_in` row. L2 still has only the pre-existing inventory row and 0 machine ledger rows. F1/I1 bucket qty 6; F1/I2 bucket still 10 @ 1.00; M1/I1 stock 4; no M1/I2 `machine_items` row | pass |
| TOI-P-08 | R2, R4 | boundary | L1 quantity `2.50` (line_number 1); pre-existing `machine_item_ledger` row W1 `transfer_in`, `'transfer_order'`, `source_id=L1.id`; F1/STORAGE/I1 = 10 @ 4.00 | `[L1]` | no exception; returns `0`; NW | pass |
| TOI-P-09 | R4 | error | L1 quantity `2.50`, line_number 2; F1/STORAGE/I1 = 10 @ 4.00 | `[L1]` | 400, detail `"Line 2 has a fractional quantity; inventory transfers require whole units"`; NW (no bucket preparation either) | pass |
| TOI-P-10 | R4 | error | L1 quantity `0.00`, line_number 1; stock as P-09 | `[L1]` | 400, detail `"Line 1 has no quantity to transfer"`; NW | pass |
| TOI-P-11 | R5 | error | L1 (I1, `3.00`, line 1), L2 (I1, `2.50`, line 2), L3 (I1, `1.00`, line 3); F1/STORAGE/I1 = 10 @ 4.00 | `[L1, L2, L3]` | 400, detail `"Line 2 has a fractional quantity; inventory transfers require whole units"`. In the session: L1 has one inventory `transfer_out` and one machine `transfer_in` row; no ledger rows for L2 or L3; F1 bucket qty 7; M1/I1 stock 3 | pass |
| TOI-P-12 | R5 | error | L1 (I1, `3.00`), L2 (I2, `20.00`), L3 (I1, `1.00`); F1/STORAGE/I1 = 10 @ 4.00; F1/STORAGE/I2 = 5 @ 1.00 | `[L1, L2, L3]` | 400, `"stock (5 available, 20 requested)"` in detail. L1 rows present (out + in); none for L2 or L3; F1/I1 bucket 7; F1/I2 bucket 5 | pass |
| TOI-P-13 | R6 | error | TO destination `('project', 0)`; L1 I1 `3.00`; F1/STORAGE/I1 = 10 @ 4.00 | `[L1]` | 400, detail `"Project destination inventory posting is not yet supported"`. In the session: one inventory `transfer_out` row for L1 (`transfer_destination_type 'project'`), F1 bucket qty 7; no `transfer_in` row in either ledger | pass |
| TOI-P-14 | R6 | error | TO destination `('storage', 999999999)`; L1 I1 `3.00`; F1/STORAGE/I1 = 10 @ 4.00 | `[L1]` | 404, detail `"Factory with ID 999999999 not found"`. The `transfer_out` row for L1 is present; F1 bucket 7; no `transfer_in` row | pass |
| TOI-P-15 | R8 | isolation | TO row belongs to **W2** (created by U2, same status ST or a W2 status); source F1, destination M1 (both W1); L1 I1 `3.00`; F1/STORAGE/I1 = 10 @ 4.00 | `post_transfer_order_inventory(session, TO, [L1], W1.id, U1.id)` | returns `1`; both new ledger rows and the activity event have `workspace_id W1`; F1 bucket 7; M1 stock 3 | pass |
| TOI-P-16 | R8 | isolation | TO in W1, source F1 (W1); L1 I1 `3.00`; F1/STORAGE/I1 = 10 @ 4.00 | call with `workspace_id=W2.id`, `user_id=U2.id` | 404, detail `"Factory with ID {F1.id} not found"`; NW | pass |
| TOI-P-17 | R3 | error | TO source `('Storage', F1.id)`; L1 I1 `3.00`; F1/STORAGE/I1 = 10 @ 4.00 | `[L1]` | 400, detail `"Unsupported source location type: Storage"`; NW | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `post_transfer_order_inventory` R3a [BUG-821] (HR-10) | `TransferOrderManager.mark_order_complete` | The order row is read with `SELECT … FOR UPDATE` before the completed/posted checks (SQL capture); the actual double-completion race is integration-only |
| `_post_location_out` R5a [BUG-820] race | integration tests | Two concurrent postings on the same bucket / machine stock: one wins, the other sees the reduced stock (the lock SQL itself is covered here, OUT-16/29) |
| `_post_location_in` R1a [BUG-825] | `TransferOrderManager` / `TransferOrderService` create & update | Create/update with `destination_location_type='project'` → 400 "Project destination is not yet supported", nothing written |
| `_quantity_to_int` R5 [BUG-824] (HTTP) | `POST/PATCH` transfer-order item endpoints | Payload with quantity 2.5 / 0 / −3 → 422 |
| `_post_location_in` R2a, `_post_location_out` R1a [BUG-823] (HTTP) | `POST/PATCH` transfer-order endpoints | Unknown / miscased location type → 422 |
| `post_transfer_order_inventory` side effects: "no transfer-order events written here" | `TransferOrderManager.mark_order_complete` | The caller logs the completion event exactly once (the absence here is asserted in P-02) |

## Spec gaps
None. (Revision 1 gaps 1–5 were closed by spec Gap log G1–G5.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_quantity_to_int` | R1 | Q-01, Q-02 |
| `_quantity_to_int` | R2 / Errors "fractional" | Q-03, Q-04, Q-05 |
| `_quantity_to_int` | R3 / Errors "≤ 0" | Q-06, Q-07, Q-08 |
| `_quantity_to_int` | R4 | Q-09 |
| `_quantity_to_int` | R5 [BUG-824] | Q-10..Q-12 (pass), Q-13..Q-18 (xfail); HTTP deferred |
| `_line_already_posted` | R1 | LP-01, LP-10 |
| `_line_already_posted` | R2 | LP-02 |
| `_line_already_posted` | R3 | LP-03, LP-10 |
| `_line_already_posted` | R4 | LP-01, LP-02, LP-04, LP-05 |
| `_line_already_posted` | R5 | LP-06, LP-07, LP-08, LP-09 |
| `_post_location_out` | R1 / Errors "unsupported type" | OUT-01, OUT-02, OUT-03 (other side: OUT-04) |
| `_post_location_out` | R1a [BUG-823] | IN-35, IN-41 (pass), IN-36, IN-37, IN-38, IN-42 (xfail); HTTP deferred |
| `_post_location_out` | R2 | OUT-04, OUT-05 |
| `_post_location_out` | R3 / Errors "factory missing/other ws" | OUT-17, OUT-18 |
| `_post_location_out` | R3a [BUG-822] / Errors "soft-deleted" | OUT-19 |
| `_post_location_out` | R4 | OUT-06, OUT-07, OUT-08, OUT-09, OUT-10, OUT-15 |
| `_post_location_out` | R5 / Errors "factory stock short" | OUT-10, OUT-11, OUT-12, OUT-15 |
| `_post_location_out` | R5a [BUG-820] | OUT-16, OUT-29; race deferred |
| `_post_location_out` | R5b [BUG-826] | OUT-13, OUT-14 |
| `_post_location_out` | R6 | OUT-04, OUT-05, OUT-34 |
| `_post_location_out` | R7 | OUT-04, OUT-05, OUT-11, OUT-34 |
| `_post_location_out` | R8 / Errors "machine missing/other ws" | OUT-30, OUT-31 |
| `_post_location_out` | R8a [BUG-822] | OUT-32 |
| `_post_location_out` | R9 / Errors "machine stock short" | OUT-20, OUT-24, OUT-25, OUT-28 |
| `_post_location_out` | R9a [BUG-826] | OUT-26, OUT-27 |
| `_post_location_out` | R10 | OUT-20, OUT-21, OUT-22, OUT-23 |
| `_post_location_out` | R11 | OUT-20, OUT-22, OUT-24 |
| `_post_location_out` | R12 | OUT-20, OUT-33 |
| `_post_location_in` | R1 / Errors "project" | IN-01 |
| `_post_location_in` | R1a [BUG-825] | Deferred (TransferOrderManager/Service) |
| `_post_location_in` | R2 / Errors "other unsupported" | IN-02, IN-03, IN-04 |
| `_post_location_in` | R2a [BUG-823] | IN-29, IN-33 (pass), IN-30..32, IN-34 (xfail); HTTP deferred |
| `_post_location_in` | R3 | IN-05, IN-06 |
| `_post_location_in` | R4 / Errors "factory …" | IN-11..IN-14, IN-16, IN-17, IN-18 [BUG-822] |
| `_post_location_in` | R5 | IN-05..IN-07, IN-09, IN-10, IN-13, IN-39 |
| `_post_location_in` | R5a [BUG-1040] | IN-08 (xfail) |
| `_post_location_in` | R6 | IN-05, IN-06, IN-11, IN-39 |
| `_post_location_in` | R6a [BUG-1040] | IN-39 (xfail) |
| `_post_location_in` | R7 | IN-15 |
| `_post_location_in` | R8 / Errors "machine …" | IN-19, IN-24, IN-25, IN-26, IN-27 [BUG-822] |
| `_post_location_in` | R9 | IN-19..IN-23, IN-40 |
| `_post_location_in` | R10 | IN-19, IN-22, IN-24, IN-40 |
| `_post_location_in` | R11 | IN-19, IN-28 |
| `post_transfer_order_inventory` | R1 | P-01 |
| `post_transfer_order_inventory` | R2 | P-07, P-08 |
| `post_transfer_order_inventory` | R3 | P-02, P-03, P-06, P-17 |
| `post_transfer_order_inventory` | R3a [BUG-821] | Deferred (TransferOrderManager.mark_order_complete + integration) |
| `post_transfer_order_inventory` | R4 | P-08, P-09, P-10 |
| `post_transfer_order_inventory` | R5 | P-11, P-12 |
| `post_transfer_order_inventory` | R6 | P-13, P-14 |
| `post_transfer_order_inventory` | R7 | P-01, P-02, P-07, P-08 |
| `post_transfer_order_inventory` | R8 | P-15, P-16 |
| `post_transfer_order_inventory` | R9 | P-02, P-03, P-04, P-05 |
| `post_transfer_order_inventory` | Errors (propagated) | P-09, P-10, P-13, P-14, P-16, P-17 |
| HR-10 (BUG-820, BUG-821) | review items | OUT-16, OUT-29; BUG-821 deferred |
| HR-15 (BUG-1040) | review items | IN-08, IN-39 |
