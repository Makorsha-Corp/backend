# Execution notes — `app/managers/to_inventory.py`

> Cases: `tests/unit/managers/to_inventory.cases.md` (revision 4) · Tests: `tests/unit/managers/test_to_inventory.py` · Source commit: e48a092
> Result: 100 passed · 26 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (2026-10-30: BUG-1040, see the last Revision history)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_to_inventory.py -q -p no:cacheprovider --cov=app.managers.to_inventory --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → fixtures/helpers** (top of the test file, each commented with its convention):
  - W1/W2 → `w1`, `w2` (`make_workspace`). U1/U2 → `u1`, `u2` (`make_profile`). ST → `st` (`mk_status`, a local `Status` builder — no DAO/schema needed for this row).
  - I1/I2/IX → `i1`, `i2`, `ix` (`mk_item`, local). F1/F2/FX/FD → `f1`, `f2`, `fx`, `fd` (`mk_factory`, local; FD built with `deleted=True`). M1/M2/MX/MD → `m1`, `m2`, `mx`, `md` (`mk_machine`, local; MD soft-deleted).
  - TO/L → `mk_to_line(db, w1, status, user, item, quantity=, line_number=)`: builds a `TransferOrder` with harmless placeholder source/destination (`storage`/1, `machine`/1 — `_post_location_out`/`_post_location_in` never read them), flushes a throw-away line 1 first so `TO.id != L.id`, then the real line at the given `line_number`/quantity. Used by every `_post_location_out`/`_post_location_in` case. `post_transfer_order_inventory` cases call `mk_order` + `mk_line` directly instead, since that callable *does* read `to.source_location_type/id` and `to.destination_location_type/id` to route each line.
  - "F/TYPE/I = q @ p" → `seed_stock(db, ws, factory, item, inv_type, user, qty=, avg_price=, performed_at=PAST, ledger_only=False)`, composed from `seed_ledger` (one `InventoryLedger` row, `transaction_type='purchase_receive'`, `source_type='purchase_order'`, `source_id=900001`) and `seed_inventory_row` (one active `Inventory` row). "ledger-only" → `ledger_only=True`.
  - "M/I stock n" / "M/I mavg p @ t" → `seed_machine_stock` (one `MachineItem` row) and `seed_machine_ledger` (one `MachineItemLedger` row, `source_type='purchase_order'`, `source_id=900002`).
  - Default call args → `call_out(db, w1, u1, to, line, location_type=, location_id=, qty=, item_id=, dest_type='machine', dest_id=)` and `call_in(..., unit_cost=, source_type='machine', source_id=)`, both thin wrappers over `_post_location_out`/`_post_location_in` with the Conventions' defaults baked in.
  - NW → `nw_snapshot(db)` (ledger/event row counts + every `Inventory`/`MachineItem` row's tracked columns, workspace-agnostic) and `assert_nw(before, after)`.
  - Re-read → `get_bucket`, `get_machine_item`, `last_inv_ledger_for_line`, `last_machine_ledger_for_line`, `events_for_machine`, `to_event_count` — each calls `db.expire_all()` then a fresh `SELECT`. "New row for L" / "exactly one" → the `source_type='transfer_order', source_id=line.id` filter in `last_inv_ledger_for_line`/`last_machine_ledger_for_line`.
  - Decimals → plain `==` throughout (`Decimal('4.00') == Decimal('4')` holds natively); `assert_fields(row, **expected)` does field-by-field `==` with a labeled failure message.
  - SQL capture / lock-before-insert → `SQLCapture` (a `before_cursor_execute` listener scoped to the `with` block) and `assert_lock_before_insert(statements, lock_table, insert_table)`, which finds the first `INSERT INTO <insert_table>` and asserts a `SELECT … FROM <lock_table> … FOR UPDATE` occurs before it in the captured list.
  - Schema cases (`Q-10..18`, `IN-29..42`) build `TransferOrderItemCreate/Update` and `TransferOrderCreate/Update` directly; no `db` fixture needed in most (a few keep `db` in the signature for consistency with neighboring tests even though unused).
- **Mocks:** none — matches Conventions "Externals mocked: none". Every seeded ledger row carries an explicit past `performed_at` (`PAST`/`NEWER`/`NEWEST`/`OLDER` module constants), so "latest" never depends on wall-clock time and `utcnow` needs no patch.
- **Race simulations:** none (Conventions says none for this module).
- **DB-error cases:** none use `db.begin_nested()` — every error case in this module is an application-level `HTTPException` (400/404) raised before any constraint-violating write, not a Postgres integrity error, so the session never needs a savepoint rollback. Re-reads after `pytest.raises` just re-query normally (R5/R6: earlier writes in the same call stay flushed).
- **Lock cases (OUT-16, OUT-29):** `SQLCapture(engine)` wraps the call; `assert_lock_before_insert` checks for the `FOR UPDATE` SELECT. Both are `xfail BUG-820` (no lock exists yet), so the lock assertion is the "fails today on" point.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (42 statements, 16 branches, `app/managers/to_inventory.py`).

## Factories added
None promoted to `tests/unit/factories.py` (batch mode — not edited). Local builders worth promoting later if another module needs them:
- `mk_status` (minimal `Status` row) — generic enough for any manager test needing a `current_status_id`.
- `mk_item`, `mk_factory`, `mk_machine` — already duplicate similar ad hoc builders likely present in `po_storage_inventory`/`po_machine_inventory` tests; worth a shared `make_item`/`make_factory`/`make_machine` in factories.py.
- `seed_stock`/`seed_machine_stock` (+ their ledger halves) — the `F/TYPE/I = q @ p` and `M/I stock n` / `mavg p @ t` seeding pattern recurs across every inventory-touching manager spec in this directory (`po_storage_inventory`, `po_machine_inventory`, `inventory_movements`); a shared `tests/unit/factories.py` pair (`make_inventory_bucket`, `make_machine_stock`) would remove duplication once those modules are reconciled.

## Notes for maintainers
- **When BUG-820 is fixed** (row lock added before the availability check): OUT-16 and OUT-29 will XPASS → remove their `xfail` markers; the deferred race test (two concurrent postings) stays owned by integration tests per the cases file.
- **When BUG-822 is fixed** (soft-deleted factory/machine rejected): OUT-19, OUT-32, IN-18, IN-27 will XPASS → remove their markers.
- **When BUG-823 is fixed** (location type validated at the schema): IN-30..32, IN-34, IN-36..38, IN-42 will XPASS → remove their markers. The HTTP-level 422 behavior stays deferred to the transfer-order endpoint tests per the cases file.
- **When BUG-824 is fixed** (quantity validated at the schema): Q-13..18 will XPASS → remove their markers.
- **When BUG-826 is fixed** (insufficient-stock message names the line/item): OUT-13, OUT-14, OUT-26, OUT-27 will XPASS → remove their markers; the pass-case substring assertions (OUT-12, OUT-25, etc.) stay valid both before and after the fix, per the cases file's design note.
- IN-39 (G2 rounding) and IN-40 (G3 null-average weighting) are the two cases added to close spec gaps G2/G3. IN-39 is a strict xfail BUG-1040: `total_cost` must round half away from zero, like the stored `unit_cost` and `avg_price`. IN-40 passes today and pins a null latest average treated as `0` in the weighted-average formula, not skipped and not averaged with the unit cost. Any future weighting change to the source should revisit IN-40 first.
- **When BUG-1040 is fixed** (the rounding lives in `app/managers/inventory_movements.py`, not in this module): IN-08 and IN-39 will XPASS → remove their markers.
- IN-29/IN-35 use `@pytest.mark.parametrize` for the "each of storage/damaged/machine(/project)" sub-checks named inside a single case ID's When column (one case, several values, not several cases sharing setup) — this is why 126 pytest items are collected for 121 case IDs (5 extra from those two parametrize blocks); every item's node id still carries its case's number as a prefix of the test name.
- Stability: ran 3x; identical outcome each time (102 passed, 24 xfailed).

## Revision history
- **Round 2 (this run):** applied all 10 executor-routed findings from `to_inventory.verify.md` (verdict NEEDS WORK). No case or spec change — all are fidelity fixes to existing tests:
  - Added `status_code == 400` assertions: P-11, P-12, P-13 (previously only `detail` was checked).
  - Added missing event assertions: P-03 ("one `transfer_out` event on M1"), P-06 ("no activity event" — asserted via a direct `MachineActivityEvent` count of 0, since no machine fixture exists in that test).
  - Tightened P-15's vacuous `all(e.workspace_id == w1.id for e in events)` (true on an empty list) to `len(events) == 1` plus a direct field check.
  - Added `transaction_type` assertions on the L1/L3 out+in rows for P-07, P-11, P-12 (previously only row counts were checked).
  - Added machine-ledger-empty assertions for L2/L3 in P-11 and P-12 (previously only the inventory ledger side was checked for those lines).
  - Added `workspace_id=w1.id` to the IN-19 event `assert_fields` call.
  - IN-24: replaced the `.first()`-based `get_machine_item` check (which would hide a duplicate `machine_items` row, since that table has no unique constraint) with a new local helper `get_machine_items_all` and `len(...) == 1`.
  - Wrong setup (Conventions "Default call args" `dest_id`/`source_id = M2.id"): added the missing `m2` fixture and `dest_id=m2.id`/`source_id=m2.id` to OUT-29, OUT-30, OUT-31, OUT-32, OUT-33, IN-20, IN-21, IN-22, IN-23 (fixture already present, only the call argument was missing), IN-24, IN-25, IN-26, IN-27, IN-28, IN-40. (OUT-21..28 already passed `dest_id=m2.id` and needed no change.)
  - Result unchanged: 102 passed, 24 xfailed, 100% branch coverage; ran 2x after the fixes (3x total across both rounds) with identical outcomes.
  - No new discrepancies; no case/spec changes needed per the verifier's own assessment.

## Fixes applied during execution (pre-existing test file from an earlier run)
The test file already existed with all 121 case IDs implemented when this run started (prior session interrupted before writing notes or a clean run). Six tests failed on the first run here and were fixed as implementation bugs (not discrepancies — all are faithful to the cases/spec once corrected):
- `test_toi_out_18__other_workspace_factory_404`, `test_toi_out_31__other_workspace_machine_404`, `test_toi_in_17__other_workspace_factory_404`, `test_toi_in_26__other_workspace_machine_404`: called an undefined `w2_of(...)` helper. Fixed by adding the `w2` fixture to each test's signature and seeding directly against `w2` (the `fx`/`mx` fixtures are already built in `w2`). OUT-18 also had a dead no-op line (`seed_stock(...) if False else None`) left over from an earlier edit; removed.
- `test_toi_p_08__already_posted_fractional_line_skipped_without_validation`: inserted a `MachineItemLedger` row with a placeholder `machine_id=1` that doesn't exist, violating the FK constraint. Fixed by adding the `m1` fixture and using `machine_id=m1.id` (and `dest_id=m1.id` on the order, consistent with how other `post_transfer_order_inventory` tests build their order).
- `test_toi_p_16__wrong_workspace_id_argument_factory_not_found`: called an undefined `st_for(db, w1)` helper. Fixed by using `mk_status(db, w1)` directly (same as the `st` fixture does), and added the `m1` fixture for a real `dest_id` instead of the placeholder `1`.

After these fixes: 102 passed, 24 xfailed, 0 errors, 100% branch coverage, stable across 3 runs.

## Revision history
- **Round 3 (this run):** applied the 6 executor-routed findings from `to_inventory.verify.md` round 3 (verdict NEEDS WORK — full re-audit of all 121 cases; round 2 only checked changed tests). No case or spec change — all are fidelity fixes adding assertions the Then column already named but the test had dropped:
  - `test_toi_p_03__single_line_machine_to_storage`: added `factory_id=f2.id` to the inventory `transfer_in` row's `assert_fields`.
  - `test_toi_p_04__null_source_average_costs_zero`: added `transaction_type="transfer_in"` to the F2 row's `assert_fields`.
  - `test_toi_p_05__machine_to_damaged_no_prior_rows`: added `factory_id=f2.id, transaction_type="transfer_in"` to the DAMAGED row's `assert_fields`.
  - `test_toi_p_13__project_destination_leaves_source_deduction_written`: added `out_rows[0].transaction_type == "transfer_out"`.
  - `test_toi_p_14__missing_destination_factory_leaves_source_deduction_written`: added `out_rows[0].transaction_type == "transfer_out"`.
  - `test_toi_out_04__storage_happy_path`, `test_toi_out_10__shortage_aligns_bucket_before_raising`, `test_toi_out_25__machine_shortage_rejected`, `test_toi_out_28__no_machine_item_row_created_before_shortage`, `test_toi_in_05__storage_happy_path`: replaced the single-machine `events_for_machine(db, mX) == []` check with the table-wide `db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0`, matching the Conventions' NW/"no activity event" wording and the pattern already used in P-06.
  - Result unchanged: 102 passed, 24 xfailed, 100% branch coverage; ran 3x with identical outcomes (no flakiness).
  - No new discrepancies; source commit unchanged (`e48a092`, `app/managers/to_inventory.py` not modified).
- **2026-10-30, BUG-1040:** owner ruling, all money rounds half away from zero (HR-15). Spec R5 split into R5 and R5a, new R6a, G2 updated; cases revision 4.
  - `test_toi_in_08` renamed `__weighted_average_tie_rounds_half_up`, expects `1.03`, strict xfail BUG-1040. Under `--runxfail` it fails on `avg_price_after: expected Decimal('1.03'), got Decimal('1.02')`.
  - `test_toi_in_39` renamed `__three_decimal_cost_rounds_half_up`, expects `total_cost 0.13`, strict xfail BUG-1040. `total_cost` moved to the last assertion, so the values that hold today are all checked first. Under `--runxfail` it fails on `total_cost: expected Decimal('0.13'), got Decimal('0.12')`, after those values passed.
  - Result: 100 passed, 26 xfailed, 100% branch coverage (42 statements, 16 branches). With half up simulated (`decimal` context set to `ROUND_HALF_UP` by a throw-away plugin, `app/` untouched) only IN-08 and IN-39 change: both XPASS and strict-fail, which is what the fix should cause.
