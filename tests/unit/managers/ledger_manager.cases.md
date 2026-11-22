# Test cases — `app/managers/ledger_manager.py`

> **Spec:** `tests/unit/managers/ledger_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec fill-gaps G1–G7 applied: exact inventory reconcile notes format (new R9b) → LED-RINV-10/12/13/15 tightened, new LED-RINV-18/20; machine R9 split into R9/R9a (G2, G4) → `value_after` now asserted in passing cases, LED-RMI-17 follows R9a/R10 directly (former D1 dropped); R6a NULL/empty comparison (G3) → new boundary cases LED-RINV-19/21/22; column types and attachment values (G5) → AL-base uses the app's `ready` value instead of `uploaded`; movement-report bounds inclusive (G6) and tie-order facts (G7) now come from the spec. All 7 earlier gaps closed.
> **Revision:** 3 — spec G8 (verify finding 2): tie order today is undefined, so the BUG-640/641 tie cases (LED-GML-14, GMB-05, PCL-04, GIL-16, GIB-06, GAL-10, IMS-07, TBU-06) now prove the bug from the recorded SQL `ORDER BY` (deterministic, strict xfail) — verify finding 1 addressed. Verify finding 11 / surviving mutants #24, #36, #40, #50 (default `limit=100` unchecked) addressed: new LED-GML-20, LED-PCL-07, LED-GIL-19, LED-GAL-13. LED-TBU-02…06 Given/Then spelled out per ledger (verify finding 5, executor-owned; wording only clarified).
> **Revision:** 4 (2026-11-22) — spec Gap log C1 (routed by the `ledger_service` verifier): LED-RMI-16 and LED-RINV-17 now pin the exact clauses `FOR UPDATE OF machine_items` / `FOR UPDATE OF inventory` (one `FOR UPDATE`, no `SKIP LOCKED` / `NOWAIT`, no lock on `items`) instead of any `FOR UPDATE`, as LSV-RMI-13 / LSV-RINV-15 do. Both stay strict xfail. No case added, renumbered or retired. File normalised to LF. Done by one agent.
> **Counts:** 134 cases · 82 expected-to-pass · 52 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_machine_ledger` 20 (4 bug) · `get_machine_balance` 5 (1 bug) · `reconcile_machine_item` 17 (5 bug) · `get_project_component_ledger` 7 (1 bug) · `calculate_project_component_total_cost` 7 (3 bug) · `get_inventory_ledger` 19 (4 bug) · `get_inventory_balance` 6 (4 bug) · `reconcile_inventory` 22 (14 bug) · `get_attachment_ledger` 13 (1 bug) · `get_item_movement_summary` 11 (8 bug) · `get_transactions_by_user` 7 (7 bug).
- **Notable design choices:**
  - BUG-655 means any inventory bucket with ledger history crashes today, so every `reconcile_inventory` case with history is xfail. The only passing `reconcile_inventory` cases use an EMPTY ledger (snapshot vs. 0).
  - All `get_transactions_by_user` cases are xfail (BUG-645: every call crashes today).
  - Tie-order cases (BUG-640/641) are proved from the SQL the call emits, not from the data order (spec G8: tie order today is undefined, so a data-only check can pass by chance). Each tie case records the statements and asserts the ledger SELECT's `ORDER BY` ends `performed_at DESC, id DESC` (plus `LIMIT` for latest-entry lookups) — this fails every run today, so strict xfail is safe. The tied-row data assertion is kept in the same case as documentation; because the SQL assertion always fails today, the case cannot XPASS by chance (best-practice default, delegated by reviewer).
  - Default `limit=100` of the four list methods is checked with 101 matching rows and no `limit` argument (LED-GML-20, PCL-07, GIL-19, GAL-13).
  - The row-lock rules (BUG-643/644) cannot be raced inside one rolled-back transaction. They are covered by (a) a passing sequential second-reconcile case and (b) an xfail case that watches the SQL the call emits (a statement listener, not a mock) and checks that the snapshot SELECT carries `FOR UPDATE`.
  - Inventory snapshot `updated_at` "refreshed by the database" is not asserted: inside one rolled-back transaction the database clock does not move, so a refresh cannot be told apart from no refresh.
  - `limit = 0` has no manager-level case. The spec puts the `limit >= 1` rule at the API, so it is deferred.
- **Needs a decision:** None.

## Conventions for this module

**IDs:** `LED` = ledger_manager. Methods: `GML` get_machine_ledger · `GMB` get_machine_balance · `RMI` reconcile_machine_item · `PCL` get_project_component_ledger · `PCT` calculate_project_component_total_cost · `GIL` get_inventory_ledger · `GIB` get_inventory_balance · `RINV` reconcile_inventory · `GAL` get_attachment_ledger · `IMS` get_item_movement_summary · `TBU` get_transactions_by_user.

**Setup vocabulary** (inserted fresh in each test that needs them; no test depends on another):
- W1, W2 = two workspaces. U1, U2 = two user profiles in W1; U3 = a user profile in W2.
- M1, M2 = machines in W1; M9 = a machine in W2.
- I1 = catalog item "Bolt" in W1 (active); I2 = catalog item "Nut" in W1 (active); I3 = catalog item "Old Bolt" in W1 (inactive); I9 = catalog item "Washer" in W2.
- F1, F2 = factories in W1; F9 = a factory in W2.
- PC1, PC2 = project components in W1; PC9 = a project component in W2.
- A1, A2 = `attachments` rows in W1; A9 = an `attachments` row in W2 (each with non-null `file_name`, `mime_type`, `file_size`; attachment entries reference them by `attachment_id`).
- Value strings: all `transaction_type` / `entity_type` columns are plain strings (spec Notes), so a case-mismatched filter simply matches nothing. Setups use values the app writes (inventory/machine: `transfer_in`, `consumption`, `inventory_adjustment`, …; attachment transaction types `ready`, `deleted`; entity types `project`, `machine`). `inventory_type` is the Postgres enum — pass the Python `InventoryTypeEnum` member.
- "machine entry" = a `machine_item_ledger` row; "project entry" = a `project_component_item_ledger` row; "inventory entry" = an `inventory_ledger` row; "attachment entry" = an `attachment_ledger` row. Unless a case says otherwise, each entry has `workspace_id` W1, `performed_by` U1 and a valid `transaction_type`. Only the fields that matter are given; every other required column gets any valid value.
- "machine snapshot" = a `machine_items` row; "inventory snapshot" = an `inventory` row (live, `is_deleted = False`, unless stated).
- Every setup entry is given an **explicit** `performed_at` (inventory entries too, see the spec notes). `T(d)` = 2025-06-d 10:00:00. `T(d, hh:mm:ss)` = that day at that time. Use the column's own timezone convention (aware UTC if the column is tz-aware, naive otherwise). All setup times are in the past relative to the real clock.
- "call" = the manager method is called directly with the test's session. "Returns [E3, E1]" means the list has exactly those rows, in that order, compared by `id`.

**Externals mocked:** none (spec: "Externals to mock: none"). `utcnow` is not mocked. Cases that check the time on a machine adjustment row record `t0` just before the call and `t1` just after, and assert `t0 <= performed_at <= t1`. Inventory adjustment rows use the database clock: assert `performed_at == SELECT now()` in the same transaction.

**DataError cases:** run the call inside a savepoint (`session.begin_nested()`) so the aborted statement does not poison the rest of the test's transaction.

**Race simulations:** none. Instead, the lock cases (`LED-RMI-16`, `LED-RINV-17`) attach a SQLAlchemy `before_cursor_execute` listener to the session's connection. The listener records every SQL statement text. It observes only and changes no behavior.

**Statement recorder for tie order (BUG-640/641):** the tie cases (`LED-GML-14`, `LED-GMB-05`, `LED-PCL-04`, `LED-GIL-16`, `LED-GIB-06`, `LED-GAL-10`, `LED-IMS-07`, `LED-TBU-06`) use the same listener, attached just before the call. "The <table> SELECT" = every recorded `SELECT` statement whose `FROM` names that ledger table (`machine_item_ledger`, `project_component_item_ledger`, `inventory_ledger`, `attachment_ledger`) and has an `ORDER BY`; there must be at least one. "ORDER BY ends `performed_at DESC, id DESC`" = after collapsing whitespace and ignoring case and table-name/alias qualifiers, the `ORDER BY` clause's sort keys are exactly `performed_at DESC, id DESC` (id is the last key, descending). For latest-entry lookups the clause is additionally followed by `LIMIT` (literal `1` or a bound parameter). Today the clause is `performed_at DESC` alone (spec Notes, G8), so these assertions fail every run. Each tie case asserts the SQL first, then the data order.

**Best-practice defaults (case designer, revision 3):**
- D4 — tie cases keep the data-level tied-row assertion inside the same strict xfail as the SQL assertion instead of a separate `strict=False` case; the SQL assertion makes the failure deterministic today (best-practice default, delegated by reviewer).
- D5 — the SQL `ORDER BY` match ignores whitespace, case and table qualifiers, so a harmless rendering change (alias, quoting) does not break the check (best-practice default, delegated by reviewer).

Earlier revisions: no case-designer defaults in revision 2. The former D1/D2/D3 are now stated by the spec itself (G2: `reconcile_machine_item` R10; G3: `reconcile_inventory` R6a; G6: `get_item_movement_summary` R1). The spec's own delegated defaults (R6a comparison base and `NULL` handling, R9b notes format, R9 avg-price-only ledger row, `calculate_project_component_total_cost` outgoing set) are tested as written.

## `LedgerManager.get_machine_ledger`

Base setup "ML-base": M1 has E1 (I1, `transfer_in`, T(1)), E3 (I1, `consumption`, T(2)), E2 (I2, `consumption`, T(3)). M2 has E4 (I1, `consumption`, T(4)). There is also E5 with `workspace_id` W2, `machine_id` M1, I1, `consumption`, T(5).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-GML-01 | R6, R1 | happy | ML-base | call(machine_id=M1, workspace_id=W1) | returns [E2, E3, E1]; E4 (other machine) and E5 (W2) absent | pass |
| LED-GML-02 | R1 | isolation | ML-base | call(machine_id=M1, workspace_id=W2) | returns [E5] only | pass |
| LED-GML-03 | R5 | happy | ML-base | call(M1, W1, item_id=I1) | returns [E3, E1] | pass |
| LED-GML-04 | R4 | happy | ML-base | call(M1, W1, transaction_type="consumption") | returns [E2, E3] | pass |
| LED-GML-05 | R4 | boundary | ML-base | call(M1, W1, transaction_type="Consumption") | returns `[]` (match is case-sensitive) | pass |
| LED-GML-06 | R4 | happy | ML-base | call(M1, W1, item_id=I1, transaction_type="consumption") | returns [E3] | pass |
| LED-GML-07 | R6 | boundary | ML-base | call(M1, W1, transaction_type="") | returns [E2, E3, E1] (empty string = no type filter) | pass |
| LED-GML-08 | R2 | boundary | M1 entries (I1, `consumption`): Ea at 2025-06-10 00:00:00, Eb at 2025-06-15 12:00:00, Ec at 2025-06-20 23:59:59, Ed at 2025-06-09 23:59:59, Ee at 2025-06-21 00:00:00 | call(M1, W1, start_date=2025-06-10 00:00:00, end_date=2025-06-20 23:59:59) | returns [Ec, Eb, Ea]: both boundary rows included, Ed and Ee excluded | pass |
| LED-GML-09 | R2 | happy | M1: Ea (I1, T(10)), Eb (I2, T(11)), Ec (I1, T(25)) | call(M1, W1, item_id=I1, start_date=T(5), end_date=T(20)) | returns [Ea] | pass |
| LED-GML-10 | R2 [BUG-341] | bug | M1: Ea (I1, `consumption`, T(10)), Eb (I1, `transfer_in`, T(11)), Ec (I1, `purchase_order`, T(12)), Ed (I1, `consumption`, T(25)) | call(M1, W1, start_date=T(5), end_date=T(20), transaction_type="consumption") | returns [Ea] | xfail BUG-341 — fails today on: Eb and Ec included (type ignored when a date range is given) |
| LED-GML-11 | R3 [BUG-341] | bug | M1: Ea (I1, 2025-06-09 23:59:59), Eb (I1, 2025-06-10 00:00:00), Ec (I1, T(20)) | call(M1, W1, start_date=2025-06-10 00:00:00) | returns [Ec, Eb]; Ea excluded | xfail BUG-341 — fails today on: Ea included (a single bound is ignored) |
| LED-GML-12 | R3 [BUG-341] | bug | M1: Ea (I1, T(1)), Eb (I1, 2025-06-10 00:00:00), Ec (I1, 2025-06-10 00:00:01) | call(M1, W1, end_date=2025-06-10 00:00:00) | returns [Eb, Ea]; Ec excluded | xfail BUG-341 — fails today on: Ec included |
| LED-GML-13 | R7 | boundary | ML-base | call(M1, W1, start_date=T(3), end_date=T(1)) | returns `[]` | pass |
| LED-GML-14 | R8 [BUG-640] | bug | M1: Ea (I1, T(5)), then Eb, Ec, Ed (I1, all at T(10), inserted in this order so their ids ascend); statement recorder attached | call(M1, W1) | (1) the `machine_item_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC` (see Conventions); (2) returns [Ed, Ec, Eb, Ea] | xfail BUG-640 — fails today on: (1) ORDER BY is `performed_at DESC` only |
| LED-GML-20 | R9, Inputs (default limit 100) | boundary | M1/I1 entries Q0..Q100 (101 rows) at 2025-06-01 00:00:00 + k minutes, k = 0..100 | call(M1, W1) (no `skip`, no `limit`) | returns exactly 100 rows: Q100, Q99, …, Q1 (newest first); Q0 absent | pass |
| LED-GML-15 | R9 | boundary | M1: I1 entries P1..P5 at T(1)..T(5); I2 entries Q1..Q3 at T(6)..T(8) (newer) | call(M1, W1, item_id=I1, skip=1, limit=2) | returns [P4, P3] (filtered first, then ordered, then paged) | pass |
| LED-GML-16 | R9 | boundary | ML-base | call(M1, W1, limit=1) | returns [E2] | pass |
| LED-GML-17 | Errors row | error | ML-base | call(M1, W1, limit=-1) inside a savepoint | raises SQLAlchemy `DataError`; after rolling back the savepoint, the M1 entry count is still 3 | pass |
| LED-GML-18 | Errors row | error | ML-base | call(M1, W1, skip=-1) inside a savepoint | raises SQLAlchemy `DataError`; after rolling back the savepoint, the M1 entry count is still 3 | pass |
| LED-GML-19 | Inputs (machine_id not checked) | boundary | ML-base | call(machine_id=999999999, workspace_id=W1) | returns `[]`, no error | pass |

## `LedgerManager.get_machine_balance`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-GMB-01 | R1 | happy | no machine entries at all | call(M1, I1, W1) | returns `(0, Decimal("0.00"))`; quantity is an `int` and value is a `Decimal` | pass |
| LED-GMB-02 | R2 | happy | M1/I1 entries inserted in this order: Ea (T(9), qty_after 15, value_after 37.50), Eb (T(3), qty_after 5, value_after 12.50), Ec (T(6), qty_after 8, value_after 20.00) | call(M1, I1, W1) | returns `(15, Decimal("37.50"))` (latest by `performed_at`, not the last one inserted) | pass |
| LED-GMB-03 | R2 | boundary | M1/I1: Ea (T(3), qty_after 5, value_after 12.50), Eb (T(9), qty_after 7, value_after NULL) | call(M1, I1, W1) | returns `(7, Decimal("0.00"))` | pass |
| LED-GMB-04 | R2 | isolation | M1/I1: Ea (T(3), qty_after 5, value_after 10.00). Newer decoys at T(10): M2/I1 (qty_after 99), M1/I2 (qty_after 98), a row with `workspace_id` W2, M1/I1 (qty_after 97) | call(M1, I1, W1) | returns `(5, Decimal("10.00"))` | pass |
| LED-GMB-05 | R3 [BUG-641] | bug | M1/I1: Ea (T(10), qty_after 10, value_after 10.00) inserted first, then Eb (T(10), qty_after 20, value_after 40.00), so Eb has the higher id; statement recorder attached | call(M1, I1, W1) | (1) the `machine_item_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC`, followed by `LIMIT`; (2) returns `(20, Decimal("40.00"))` | xfail BUG-641 — fails today on: (1) ORDER BY is `performed_at DESC` only |

## `LedgerManager.reconcile_machine_item`

Base setup "RM-base": I1 = "Bolt". M1/I1 machine entries Ea (T(1), qty_after 10, avg_price_after 2.00, value_after 20.00) and Eb (T(2), qty_after 15, avg_price_after 2.50, value_after 37.50) → ledger quantity 15. Machine snapshot S (W1, M1, I1) with qty 10. Record every other column of S before the call. "No writes" = the machine-entry count for M1/I1 is unchanged, S is unchanged, and there are 0 `machine_activity_events` rows for M1.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-RMI-01 | R6, R3 | happy | RM-base but S.qty = 15 | call(M1, I1, W1, user_id=U1) | returns exactly `{"status": "balanced", "ledger_qty": 15, "snapshot_qty": 15, "discrepancy": 0, "adjustment_created": False}`; no writes | pass |
| LED-RMI-02 | R4 [BUG-649] | bug | no machine entries for M1/I1; no machine snapshot for M1/I1 | call(M1, I1, W1, U1) | returned `adjustment_created` is `False`, `ledger_qty` 0, `snapshot_qty` 0, `discrepancy` 0; still no `machine_items` row for M1/I1; 0 machine entries; 0 activity events | pass (bug-independent part) |
| LED-RMI-03 | R4 [BUG-649] | bug | same as LED-RMI-02 | call(M1, I1, W1, U1) | returns exactly `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}` (no `"error"` key) | xfail BUG-649 — fails today on: `status == "error"` and the `error` key is present |
| LED-RMI-04 | R5 | error | RM-base without S (ledger quantity 15, no snapshot) | call(M1, I1, W1, U1) | returns exactly `{"status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15, "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions"}`; no `machine_items` row created; M1/I1 entry count still 2; 0 activity events | pass |
| LED-RMI-05 | R2, R5 | isolation | RM-base, but S is inserted with `workspace_id` W2 (M1, I1, qty 10) instead of W1 | call(M1, I1, W1, U1) | returns the R5 error dict with ledger_qty 15, snapshot_qty 0, discrepancy 15, adjustment_created False, error "Snapshot missing for item with ledger transactions"; the W2 row still has qty 10; no W1 `machine_items` row created; entry count still 2 | pass |
| LED-RMI-06 | R10, R3 | happy | RM-base | call(M1, I1, W1, U1) | returns exactly `{"status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10, "discrepancy": 5, "adjustment_created": True}`; re-read S: qty 15, every other recorded column unchanged | pass |
| LED-RMI-07 | R9, R7 | side-effect | RM-base | record t0; call(M1, I1, W1, U1); record t1 | exactly 1 new machine entry for M1/I1 (count 3). Its fields: workspace_id W1, machine_id M1, item_id I1, transaction_type "inventory_adjustment", unit_cost 2.50, avg_price_before 2.50, avg_price_after 2.50, qty_after 15, value_after 37.50, source_type "reconciliation", source_id NULL, invoice_id NULL, all `order_*` and transfer fields NULL, notes == "Reconciliation adjustment: Snapshot was 10, ledger shows 15. Discrepancy: 5", performed_by U1, t0 <= performed_at <= t1 | pass |
| LED-RMI-08 | R9a [BUG-651] | bug | RM-base | call(M1, I1, W1, U1) | new adjustment row: quantity 0, qty_before 15, qty_after 15, total_cost 0, value_before 37.50, value_after 37.50 | xfail BUG-651 — fails today on: quantity == 5 and qty_before == 10 |
| LED-RMI-09 | R10a | side-effect | RM-base | call(M1, I1, W1, U1) | exactly 1 `machine_activity_events` row for M1: event_type "ledger_reconciled", machine_id M1, workspace_id W1, performed_by U1, description == "Ledger reconciled for Bolt: snapshot 10 → 15", metadata == `{"item_id": I1, "item_name": "Bolt", "changes": [{"field": "qty", "label": "Quantity", "from_value": "10", "to_value": "15"}]}` | pass |
| LED-RMI-10 | R10, R3, R9 (notes) | boundary | RM-base but S.qty = 17 (snapshot higher than ledger 15) | call(M1, I1, W1, U1) | returns exactly `{"status": "adjusted", "ledger_qty": 15, "snapshot_qty": 17, "discrepancy": -2, "adjustment_created": True}`; S.qty re-read = 15; 1 new adjustment row with qty_after 15, value_after 37.50 and notes == "Reconciliation adjustment: Snapshot was 17, ledger shows 15. Discrepancy: -2"; 1 activity event with description "Ledger reconciled for Bolt: snapshot 17 → 15" | pass |
| LED-RMI-11 | R7, R1 | boundary | no machine entries for M1/I1 (ledger qty 0); S (W1, M1, I1) qty 4 | call(M1, I1, W1, U1) | returns exactly `{"status": "adjusted", "ledger_qty": 0, "snapshot_qty": 4, "discrepancy": -4, "adjustment_created": True}`; S.qty re-read = 0; 1 adjustment row: unit_cost 0.00, avg_price_before 0.00, avg_price_after 0.00, total_cost 0, qty_after 0, value_after 0.00, notes == "Reconciliation adjustment: Snapshot was 4, ledger shows 0. Discrepancy: -4" | pass |
| LED-RMI-12 | R8 [BUG-650] | bug | M1/I1: Ea (T(1), qty_after 10, avg_price_after 2.00), Eb (T(2), qty_after 12, avg_price_after NULL); S qty 10 | call(M1, I1, W1, U1) | no exception; returns `{"status": "adjusted", "ledger_qty": 12, "snapshot_qty": 10, "discrepancy": 2, "adjustment_created": True}`; S.qty re-read = 12; adjustment row unit_cost 0.00, avg_price_before 0.00, avg_price_after 0.00 | xfail BUG-650 — fails today on: raises `TypeError` |
| LED-RMI-13 | R10a | boundary | RM-base but using item I3 ("Old Bolt", inactive): entries and S are for M1/I3 instead of I1 | call(M1, I3, W1, U1) | 1 activity event: description == "Ledger reconciled for Old Bolt: snapshot 10 → 15", metadata `item_name` == "Old Bolt", metadata `item_id` == I3 | pass |
| LED-RMI-14 | R10a | isolation | RM-base but using item I9 (belongs to W2): W1 entries and a W1 snapshot for M1/I9 (qty 10), ledger qty 15 | call(M1, I9, W1, U1) | returns the adjusted dict (ledger 15, snapshot 10, discrepancy 5); 1 activity event: description == "Ledger reconciled for Item #<I9>: snapshot 10 → 15", metadata `item_name` == "Item #<I9>" (where `<I9>` is I9's id) | pass |
| LED-RMI-15 | R11 | side-effect | RM-base | call(M1, I1, W1, U1) twice in a row, same session | second call returns exactly `{"status": "balanced", "ledger_qty": 15, "snapshot_qty": 15, "discrepancy": 0, "adjustment_created": False}`; after both calls there are exactly 3 M1/I1 entries (1 adjustment) and exactly 1 activity event | pass |
| LED-RMI-16 | R11 [BUG-643] | bug | RM-base; statement listener attached (see Conventions) | call(M1, I1, W1, U1) | at least one SELECT reads from `machine_items`, and every such SELECT (whitespace and case collapsed) ends with exactly `for update of machine_items`: `FOR UPDATE` appears once, no `SKIP LOCKED`, no `NOWAIT`, no lock on `items` | xfail BUG-643 — fails today on: the `machine_items` SELECT has no `FOR UPDATE OF machine_items` |
| LED-RMI-17 | R9a, R10 [BUG-651] | bug | RM-base but S.qty = 17 | call(M1, I1, W1, U1) | new adjustment row: quantity 0, qty_before 15, qty_after 15, total_cost 0.00, value_before 37.50, value_after 37.50 (negative discrepancy follows R9a, per R10) | xfail BUG-651 — fails today on: quantity == 2 and qty_before == 17 |

## `LedgerManager.get_project_component_ledger`

Base setup "PC-base": PC1 has P1 (I1, T(1)), P2 (I2, T(3)), P3 (I1, T(2)). PC2 has P4 (I1, T(4)). There is also P5 with `workspace_id` W2, `project_component_id` PC1, I1, T(5).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-PCL-01 | R3, R1 | happy | PC-base | call(project_component_id=PC1, workspace_id=W1) | returns [P2, P3, P1]; P4 (other component) and P5 (W2) absent | pass |
| LED-PCL-02 | R1 | isolation | PC-base | call(PC1, W2) | returns [P5] only | pass |
| LED-PCL-03 | R2 | happy | PC-base | call(PC1, W1, item_id=I1) | returns [P3, P1] | pass |
| LED-PCL-04 | R4 [BUG-640] | bug | PC1: Pa (I1, T(5)), then Pb, Pc, Pd (I1, all at T(10), ascending ids); statement recorder attached | call(PC1, W1) | (1) the `project_component_item_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC`; (2) returns [Pd, Pc, Pb, Pa] | xfail BUG-640 — fails today on: (1) ORDER BY is `performed_at DESC` only |
| LED-PCL-05 | R5 | boundary | PC1: I1 entries at T(1)..T(5) (Q1..Q5); I2 entries at T(6), T(7) | call(PC1, W1, item_id=I1, skip=1, limit=2) | returns [Q4, Q3] | pass |
| LED-PCL-06 | Errors row | error | PC-base | call(PC1, W1, limit=-1) inside a savepoint | raises SQLAlchemy `DataError`; after rolling back the savepoint, the PC1 entry count is still 3 | pass |
| LED-PCL-07 | R5, Inputs (default limit 100) | boundary | PC1/I1 entries Q0..Q100 (101 rows) at 2025-06-01 00:00:00 + k minutes, k = 0..100 | call(PC1, W1) (no `skip`, no `limit`) | returns exactly 100 rows: Q100, Q99, …, Q1 (newest first); Q0 absent | pass |

## `LedgerManager.calculate_project_component_total_cost`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-PCT-01 | R1 | happy | PC1 entries with total_cost: `purchase_order` 100.00, `manual_add` 50.25, `transfer_in` 200.00, `consumption` 10.00, `inventory_adjustment` 5.00, `cost_adjustment` 1.50 | call(PC1, W1) | returns `Decimal("366.75")` (a `Decimal`) | pass |
| LED-PCT-02 | R1 | isolation | PC1: `transfer_in` 100.00. PC2: `transfer_in` 40.00. A row with `workspace_id` W2, PC1, `transfer_in` 7.00 | call(PC1, W1) | returns `Decimal("100.00")` | pass |
| LED-PCT-03 | R1 [BUG-654] | bug | PC1: `transfer_in` 1000.00, `transfer_out` 300.00 | call(PC1, W1) | returns `Decimal("700.00")` | xfail BUG-654 — fails today on: returns 1300.00 |
| LED-PCT-04 | R1 [BUG-654] | bug | PC1: `purchase_order` 500.00, `damaged` 120.00 | call(PC1, W1) | returns `Decimal("380.00")` | xfail BUG-654 — fails today on: returns 620.00 |
| LED-PCT-05 | R2 | boundary | no project entries for PC1 | call(PC1, W1) | returns `Decimal("0.00")`, type `Decimal` | pass |
| LED-PCT-06 | R2, R1 [BUG-654] | bug | PC1: `transfer_in` 300.00, `transfer_out` 300.00 | call(PC1, W1) | returns `Decimal("0.00")` | xfail BUG-654 — fails today on: returns 600.00 |
| LED-PCT-07 | R2 | boundary | PC1: one `consumption` row with total_cost 0.00 | call(PC1, W1) | returns `Decimal("0.00")`, type `Decimal` | pass |

## `LedgerManager.get_inventory_ledger`

Base setup "IL-base" (all W1): N1 (STORAGE, F1, I1, `transfer_in`, T(1)), N2 (DAMAGED, F1, I1, `inventory_adjustment`, T(2)), N3 (STORAGE, F2, I1, `inventory_adjustment`, T(3)), N4 (STORAGE, F1, I2, `transfer_in`, T(4)), N5 (WASTE, F2, I2, `inventory_adjustment`, T(5)). Plus N9 (`workspace_id` W2, STORAGE, F9, I9, `inventory_adjustment`, T(6)).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-GIL-01 | R6, R1 | happy | IL-base | call(workspace_id=W1) | returns [N5, N4, N3, N2, N1]; N9 absent | pass |
| LED-GIL-02 | R1, R5 | happy | IL-base | call(W1, inventory_type=DAMAGED) | returns [N2] | pass |
| LED-GIL-03 | R1, R5 | happy | IL-base | call(W1, factory_id=F2) | returns [N5, N3] | pass |
| LED-GIL-04 | R1, R5 | happy | IL-base | call(W1, item_id=I2) | returns [N5, N4] | pass |
| LED-GIL-05 | R1, R5 | happy | IL-base | call(W1, inventory_type=STORAGE, factory_id=F1, item_id=I1) | returns [N1] | pass |
| LED-GIL-06 | R4 | happy | IL-base | call(W1, transaction_type="inventory_adjustment") | returns [N5, N3, N2] | pass |
| LED-GIL-07 | R4 | boundary | IL-base | call(W1, transaction_type="Inventory_Adjustment") | returns `[]` | pass |
| LED-GIL-08 | R4, R1 | happy | IL-base | call(W1, inventory_type=STORAGE, transaction_type="inventory_adjustment") | returns [N3] | pass |
| LED-GIL-09 | R5 | boundary | IL-base | call(W1, transaction_type="") | returns [N5, N4, N3, N2, N1] | pass |
| LED-GIL-10 | R2 | boundary | W1 STORAGE/F1/I1 entries: Na 2025-06-10 00:00:00, Nb 2025-06-15 12:00:00, Nc 2025-06-20 23:59:59, Nd 2025-06-09 23:59:59, Ne 2025-06-21 00:00:00 | call(W1, start_date=2025-06-10 00:00:00, end_date=2025-06-20 23:59:59) | returns [Nc, Nb, Na] | pass |
| LED-GIL-11 | R2, R1 | happy | IL-base | call(W1, factory_id=F1, start_date=T(1), end_date=T(3)) | returns [N2, N1] (N3 is F2; N4 is out of range) | pass |
| LED-GIL-12 | R2 [BUG-341] | bug | IL-base | call(W1, start_date=T(1), end_date=T(4), transaction_type="transfer_in") | returns [N4, N1] | xfail BUG-341 — fails today on: N2 and N3 included |
| LED-GIL-13 | R3 [BUG-341] | bug | IL-base | call(W1, start_date=T(4)) | returns [N5, N4] | xfail BUG-341 — fails today on: N1–N3 included |
| LED-GIL-14 | R3 [BUG-341] | bug | IL-base | call(W1, end_date=T(2)) | returns [N2, N1] | xfail BUG-341 — fails today on: N3–N5 included |
| LED-GIL-15 | R7 | boundary | IL-base | call(W1, start_date=T(5), end_date=T(1)) | returns `[]` | pass |
| LED-GIL-16 | R8 [BUG-640] | bug | W1 STORAGE/F1/I1: Na (T(5)), then Nb, Nc, Nd (all T(10), ascending ids); statement recorder attached | call(W1) | (1) the `inventory_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC`; (2) returns [Nd, Nc, Nb, Na] | xfail BUG-640 — fails today on: (1) ORDER BY is `performed_at DESC` only |
| LED-GIL-17 | R9 | boundary | W1 STORAGE/F1/I1 entries at T(1)..T(5) (Q1..Q5); W1 STORAGE/F1/I2 entries at T(6), T(7) | call(W1, item_id=I1, skip=1, limit=2) | returns [Q4, Q3] | pass |
| LED-GIL-18 | Errors row | error | IL-base | call(W1, limit=-1) inside a savepoint | raises SQLAlchemy `DataError`; after rolling back the savepoint, the W1 inventory entry count is still 5 | pass |
| LED-GIL-19 | R9, Inputs (default limit 100) | boundary | W1 STORAGE/F1/I1 entries Q0..Q100 (101 rows) at 2025-06-01 00:00:00 + k minutes, k = 0..100 | call(W1) (no `skip`, no `limit`) | returns exactly 100 rows: Q100, Q99, …, Q1 (newest first); Q0 absent | pass |

## `LedgerManager.get_inventory_balance`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-GIB-01 | R1 | happy | no inventory entries | call(F1, I1, STORAGE, W1) | returns `(0, Decimal("0.00"))` | pass |
| LED-GIB-02 | R2, R1 | isolation | only decoy entries: (DAMAGED, F1, I1, W1, qty_after 9), (STORAGE, F2, I1, W1, qty_after 8), (STORAGE, F1, I2, W1, qty_after 7), (`workspace_id` W2, STORAGE, F1, I1, qty_after 6) | call(F1, I1, STORAGE, W1) | returns `(0, Decimal("0.00"))` | pass |
| LED-GIB-03 | R2 [BUG-655] | bug | STORAGE/F1/I1/W1 entries inserted in this order: Na (T(9), qty_after 50, avg_price_after 5.00), Nb (T(3), qty_after 20, avg_price_after 4.00) | call(F1, I1, STORAGE, W1) | returns `(50, Decimal("250.00"))` (numeric equality) | xfail BUG-655 — fails today on: raises `AttributeError` (`value_after`) |
| LED-GIB-04 | R2 [BUG-655] | bug | STORAGE/F1/I1/W1: Na (T(3), qty_after 20, avg 4.00), Nb (T(9), qty_after 30, avg_price_after NULL) | call(F1, I1, STORAGE, W1) | returns `(30, Decimal("0.00"))` | xfail BUG-655 — fails today on: raises `AttributeError` |
| LED-GIB-05 | R2 [BUG-655] | bug | STORAGE/F1/I1/W1: Na (T(3), qty_after 12, avg 2.00). Newer decoys at T(10): DAMAGED/F1/I1 (qty 99), STORAGE/F2/I1 (qty 98), STORAGE/F1/I2 (qty 97), `workspace_id` W2 STORAGE/F1/I1 (qty 96) | call(F1, I1, STORAGE, W1) | returns `(12, Decimal("24.00"))` | xfail BUG-655 — fails today on: raises `AttributeError` |
| LED-GIB-06 | R3 [BUG-641] | bug | STORAGE/F1/I1/W1: Na (T(10), qty_after 10, avg 1.00) inserted first, then Nb (T(10), qty_after 20, avg 2.00) | call(F1, I1, STORAGE, W1) with the statement recorder attached | (1) the `inventory_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC`, followed by `LIMIT`; (2) returns `(20, Decimal("40.00"))` | xfail BUG-641 (and BUG-655) — fails today on: raises `AttributeError` (after BUG-655 is fixed: (1) ORDER BY is `performed_at DESC` only) |

## `LedgerManager.reconcile_inventory`

Base setup "RI-empty": no inventory entries for (W1, F1, I1, STORAGE). Inventory snapshot S (W1, F1, I1, STORAGE) with qty 5, avg_price 3.00, created_by U1, updated_by U1. Record S's other columns before the call. The reconciling user is U2.
Base setup "RI-hist": STORAGE/F1/I1/W1 entries Na (T(1), qty_after 10, avg_price_after 2.00) and Nb (T(2), qty_after 15, avg_price_after 2.50) → ledger quantity 15, avg 2.50. S (W1, F1, I1, STORAGE) with qty 10, avg_price 2.00, updated_by U1.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-RINV-01 | R4 [BUG-649] | bug | no inventory entries and no inventory snapshot for (W1, F1, I1, STORAGE) | call(F1, I1, STORAGE, W1, user_id=U2) | returned `adjustment_created` False, `ledger_qty` 0, `snapshot_qty` 0, `discrepancy` 0; no `inventory` row created for the bucket; 0 inventory entries | pass (bug-independent part) |
| LED-RINV-02 | R4 [BUG-649] | bug | same as LED-RINV-01 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}` | xfail BUG-649 — fails today on: `status == "error"` |
| LED-RINV-03 | R2 | soft-delete | RI-empty but S has `is_deleted = True` | call(F1, I1, STORAGE, W1, U2) | returned `adjustment_created` False, `ledger_qty` 0, `snapshot_qty` 0, `discrepancy` 0; re-read S: still `is_deleted` True, qty 5, avg_price 3.00, updated_by U1; 0 inventory entries; no new `inventory` row | pass |
| LED-RINV-04 | R2, R4 [BUG-649] | bug | same as LED-RINV-03 | call(F1, I1, STORAGE, W1, U2) | returns exactly the balanced dict (0/0/0/False, status "balanced", no `error` key) | xfail BUG-649 — fails today on: `status == "error"` |
| LED-RINV-05 | R2 | isolation | no entries for the W1 STORAGE bucket. Snapshots Sd (W1, F1, I1, DAMAGED, qty 4) and Sw (`workspace_id` W2, F1, I1, STORAGE, qty 6) | call(F1, I1, STORAGE, W1, U2) | returned `adjustment_created` False, `ledger_qty` 0, `snapshot_qty` 0, `discrepancy` 0; Sd.qty still 4 and Sw.qty still 6; 0 inventory entries | pass |
| LED-RINV-06 | R5, R1 [BUG-655] | bug | RI-hist without S | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15, "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions"}`; no `inventory` row created; entry count still 2 | xfail BUG-655 — fails today on: raises `AttributeError` |
| LED-RINV-07 | R6, R1 [BUG-655] | bug | RI-hist but S.qty 15, S.avg_price 2.50 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "balanced", "ledger_qty": 15, "snapshot_qty": 15, "discrepancy": 0, "adjustment_created": False}`; entry count still 2; S unchanged (updated_by U1) | xfail BUG-655 — fails today on: raises `AttributeError` |
| LED-RINV-08 | R10, R7, R3 | happy | RI-empty | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "adjusted", "ledger_qty": 0, "snapshot_qty": 5, "discrepancy": -5, "adjustment_created": True}`; re-read S: qty 0, avg_price 0.00, `is_deleted` False, other recorded columns (except updated_by/updated_at) unchanged; 0 `machine_activity_events` rows | pass |
| LED-RINV-09 | R10 [BUG-652] | bug | RI-empty | call(F1, I1, STORAGE, W1, U2) | re-read S: updated_by == U2 | xfail BUG-652 — fails today on: updated_by == U1 |
| LED-RINV-10 | R9, R7 | side-effect | RI-empty | call(F1, I1, STORAGE, W1, U2); read `SELECT now()` in the same transaction | exactly 1 inventory entry for the bucket: workspace_id W1, inventory_type STORAGE, factory_id F1, item_id I1, transaction_type "inventory_adjustment", unit_cost 0.00, total_cost 0.00, avg_price_before 0.00, avg_price_after 0.00, qty_after 0, source_type "reconciliation", source_id NULL, transfer fields NULL, performed_by U2, performed_at == DB now(); notes **start with** "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5" | pass |
| LED-RINV-11 | R9a [BUG-651] | bug | RI-empty | call(F1, I1, STORAGE, W1, U2) | adjustment row: quantity 0, qty_before 0, qty_after 0, total_cost 0.00 | xfail BUG-651 — fails today on: quantity == 5 and qty_before == 5 |
| LED-RINV-12 | R3, R9, R9a, R9b, R10, R1 [BUG-655, BUG-651, BUG-652] | bug | RI-hist | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10, "discrepancy": 5, "adjustment_created": True}`; S: qty 15, avg_price 2.50, updated_by U2; 1 new entry: quantity 0, qty_before 15, qty_after 15, unit_cost 2.50, total_cost 0.00, avg_price_before 2.50, avg_price_after 2.50; notes == "Reconciliation adjustment: Snapshot was 10, ledger shows 15. Discrepancy: 5. Avg price: snapshot was 2.00, ledger shows 2.50" | xfail BUG-655 — fails today on: raises `AttributeError` |
| LED-RINV-13 | R6a, R3, R9, R9b, R10 [BUG-653] | bug | STORAGE/F1/I1/W1 entry Na (T(1), qty_after 10, avg_price_after 6.50); S qty 10, avg_price 5.00, updated_by U1 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "adjusted", "ledger_qty": 10, "snapshot_qty": 10, "discrepancy": 0, "adjustment_created": True}`; S: qty 10, avg_price 6.50, updated_by U2; 1 new entry: transaction_type "inventory_adjustment", quantity 0, qty_before 10, qty_after 10, avg_price_before 6.50, avg_price_after 6.50, unit_cost 6.50, source_type "reconciliation"; notes == "Reconciliation adjustment: Snapshot was 10, ledger shows 10. Discrepancy: 0. Avg price: snapshot was 5.00, ledger shows 6.50" | xfail BUG-653 (and BUG-655) — fails today on: raises `AttributeError` (after BUG-655: `status == "balanced"`) |
| LED-RINV-14 | R8 [BUG-650] | bug | STORAGE/F1/I1/W1: Na (T(1), qty_after 10, avg 4.00), Nb (T(2), qty_after 12, avg_price_after NULL); S qty 10, avg_price 4.00 | call(F1, I1, STORAGE, W1, U2) | no exception; returns `{"status": "adjusted", "ledger_qty": 12, "snapshot_qty": 10, "discrepancy": 2, "adjustment_created": True}`; S: qty 12, avg_price 0.00; adjustment row unit_cost 0.00, avg_price_before/after 0.00 | xfail BUG-650 (and BUG-655) — fails today on: raises (`AttributeError` today; `TypeError` once BUG-655 is fixed) |
| LED-RINV-15 | R6a, R7, R9b [BUG-653] | bug | no inventory entries for the bucket; S qty 0, avg_price 5.00, updated_by U1 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "adjusted", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": True}`; S: qty 0, avg_price 0.00, updated_by U2; 1 new adjustment row with quantity 0, qty_before 0, qty_after 0, notes == "Reconciliation adjustment: Snapshot was 0, ledger shows 0. Discrepancy: 0. Avg price: snapshot was 5.00, ledger shows 0.00" (spec R6a example) | xfail BUG-653 — fails today on: `status == "balanced"` and S.avg_price stays 5.00 |
| LED-RINV-16 | R11 [BUG-655] | bug | RI-empty | call(F1, I1, STORAGE, W1, U2) twice in a row, same session | second call returns exactly `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`; exactly 1 inventory entry for the bucket after both calls | xfail BUG-655 — fails today on: the second call raises `AttributeError` (the bucket now has history) |
| LED-RINV-17 | R11 [BUG-644] | bug | RI-empty; statement listener attached | call(F1, I1, STORAGE, W1, U2) | at least one SELECT reads from `inventory` (the snapshot table, not `inventory_ledger`), and every such SELECT (whitespace and case collapsed) ends with exactly `for update of inventory`: `FOR UPDATE` appears once, no `SKIP LOCKED`, no `NOWAIT`, no lock on `items` | xfail BUG-644 — fails today on: the `inventory` SELECT has no `FOR UPDATE OF inventory` |
| LED-RINV-18 | R9b [BUG-651] | bug | RI-empty (S qty 5, avg_price 3.00) | call(F1, I1, STORAGE, W1, U2) | the 1 new adjustment row's notes == "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5. Avg price: snapshot was 3.00, ledger shows 0.00" | xfail BUG-651 — fails today on: notes end after "Discrepancy: -5" |
| LED-RINV-19 | R6a, R10, R9 | boundary | no inventory entries for the bucket; S qty 5, avg_price NULL, updated_by U1 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "adjusted", "ledger_qty": 0, "snapshot_qty": 5, "discrepancy": -5, "adjustment_created": True}`; re-read S: qty 0, avg_price 0.00; exactly 1 inventory entry for the bucket, notes start with "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5" | pass |
| LED-RINV-20 | R9b [BUG-651] | bug | same as LED-RINV-19 | call(F1, I1, STORAGE, W1, U2) | the new adjustment row's notes == "Reconciliation adjustment: Snapshot was 5, ledger shows 0. Discrepancy: -5. Avg price: snapshot was 0.00, ledger shows 0.00" (NULL written as 0.00; the price part is present although both prices are equal) | xfail BUG-651 — fails today on: notes end after "Discrepancy: -5" |
| LED-RINV-21 | R6a, R6 | boundary | no inventory entries for the bucket; S qty 0, avg_price NULL, updated_by U1 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`; re-read S: qty 0, avg_price still NULL, updated_by still U1; 0 inventory entries for the bucket | pass |
| LED-RINV-22 | R6a, R6 | boundary | no inventory entries for the bucket; S qty 0, avg_price 0.00, updated_by U1 | call(F1, I1, STORAGE, W1, U2) | returns exactly `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`; re-read S: qty 0, avg_price 0.00, updated_by still U1; 0 inventory entries for the bucket | pass |

## `LedgerManager.get_attachment_ledger`

Base setup "AL-base" (W1): G1 (A1, entity_type "project", transaction_type "ready", T(1)), G2 (A1, "project", "deleted", T(2)), G3 (A2, "machine", "ready", T(3)), G4 (A2, "project", "ready", T(4)). G9 (`workspace_id` W2, A9, "project", "ready", T(5)).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-GAL-01 | R4, R1 | happy | AL-base | call(workspace_id=W1) | returns [G4, G3, G2, G1]; G9 absent | pass |
| LED-GAL-02 | R2 | happy | AL-base | call(W1, attachment_id=A1) | returns [G2, G1] | pass |
| LED-GAL-03 | R2 | happy | AL-base | call(W1, entity_type="machine") | returns [G3] | pass |
| LED-GAL-04 | R2 | boundary | AL-base | call(W1, entity_type="Machine") | returns `[]` | pass |
| LED-GAL-05 | R2 | happy | AL-base | call(W1, transaction_type="deleted") | returns [G2] | pass |
| LED-GAL-06 | R2 | happy | AL-base | call(W1, attachment_id=A2, entity_type="project", transaction_type="ready") | returns [G4] (G3 matches only 2 of the 3 filters) | pass |
| LED-GAL-07 | R2, R4 | boundary | AL-base | call(W1, entity_type="", transaction_type="") | returns [G4, G3, G2, G1] | pass |
| LED-GAL-08 | R3 | boundary | W1 A1 entries: Ga 2025-06-09 23:59:59, Gb 2025-06-10 00:00:00, Gc T(20) | call(W1, start_date=2025-06-10 00:00:00) | returns [Gc, Gb] | pass |
| LED-GAL-09 | R3 | boundary | W1 A1 entries: Ga T(1), Gb 2025-06-10 00:00:00, Gc 2025-06-10 00:00:01 | call(W1, end_date=2025-06-10 00:00:00) | returns [Gb, Ga] | pass |
| LED-GAL-10 | R5 [BUG-640] | bug | W1 A1: Ga (T(5)), then Gb, Gc, Gd (all T(10), ascending ids); statement recorder attached | call(W1) | (1) the `attachment_ledger` SELECT's ORDER BY ends `performed_at DESC, id DESC`; (2) returns [Gd, Gc, Gb, Ga] | xfail BUG-640 — fails today on: (1) ORDER BY is `performed_at DESC` only |
| LED-GAL-11 | R3, R6 | boundary | W1 A1 entries: Q1..Q5 at T(1)..T(5), plus Ga at 2025-06-09 23:59:59 and Gz at 2025-06-10 00:00:00 (the bounds are inclusive) | call(W1, start_date=T(2), end_date=2025-06-10 00:00:00, skip=1, limit=2) | returns [Ga, Q5]: in-range rows newest first are Gz, Ga, Q5, Q4, Q3, Q2 (Q1 is before the start); skip=1 drops Gz and limit=2 keeps the next two | pass |
| LED-GAL-12 | Errors row | error | AL-base | call(W1, limit=-1) inside a savepoint | raises SQLAlchemy `DataError`; after rolling back the savepoint, the W1 attachment entry count is still 4 | pass |
| LED-GAL-13 | R6, Inputs (default limit 100) | boundary | W1 A1 entries Q0..Q100 (101 rows, `entity_type` "project", `transaction_type` "ready") at 2025-06-01 00:00:00 + k minutes, k = 0..100 | call(W1) (no `skip`, no `limit`) | returns exactly 100 rows: Q100, Q99, …, Q1 (newest first); Q0 absent | pass |

## `LedgerManager.get_item_movement_summary`

Base setup "IM-base": machine entries XM1 (M1, I1, T(10)), XM2 (M2, I1, T(12)). Inventory entries XN1 (STORAGE, F1, I1, T(11)), XN2 (DAMAGED, F2, I1, T(13)). W2 decoys: machine entry (`workspace_id` W2, M9, I1, T(11)) and inventory entry (`workspace_id` W2, F9, I1, T(11)). Range R = start T(1), end T(30).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-IMS-01 | R2, R3, R6 | happy | IM-base | call(item_id=I1, workspace_id=W1, start_date=T(1), end_date=T(30)) | returns a dict whose keys are exactly {"machine", "project", "inventory"}; machine == [XM2, XM1] (both machines); inventory == [XN2, XN1] (all types and factories); W2 decoys absent | pass |
| LED-IMS-02 | R1, R2, R3 | boundary | machine entries (M1, I1) at 2025-06-10 00:00:00, 2025-06-20 23:59:59, 2025-06-09 23:59:59, 2025-06-21 00:00:00; inventory entries (STORAGE, F1, I1) at the same four times | call(I1, W1, start_date=2025-06-10 00:00:00, end_date=2025-06-20 23:59:59) | machine == the 06-20 and 06-10 rows (newest first); inventory == the 06-20 and 06-10 rows (newest first) (bounds inclusive, spec R1) | pass |
| LED-IMS-03 | R2, R3 [BUG-341] | bug | IM-base plus machine entry YM (M1, I2, T(14)) and inventory entry YN (STORAGE, F1, I2, T(14)) | call(I1, W1, start_date=T(1), end_date=T(30)) | machine == [XM2, XM1]; inventory == [XN2, XN1] (YM and YN absent) | xfail BUG-341 — fails today on: YM and YN included |
| LED-IMS-04 | R1, R2, R3 [BUG-646] | bug | IM-base | call(I1, W1) (no dates) | machine == [XM2, XM1]; inventory == [XN2, XN1] | xfail BUG-646 — fails today on: machine == [] |
| LED-IMS-05 | R1, R2, R3 [BUG-646] | bug | IM-base | call(I1, W1, start_date=T(12)) | machine == [XM2]; inventory == [XN2] | xfail BUG-646 — fails today on: machine == [] |
| LED-IMS-06 | R1, R2, R3 [BUG-646] | bug | IM-base | call(I1, W1, end_date=T(11)) | machine == [XM1]; inventory == [XN1] | xfail BUG-646 — fails today on: machine == [] |
| LED-IMS-07 | R4 [BUG-640] | bug | machine entries (M1, I1): Xa (T(5)), then Xb, Xc, Xd (all T(10), ascending ids); inventory entries (STORAGE, F1, I1): Na (T(5)), then Nb, Nc, Nd (all T(10), ascending ids); statement recorder attached | call(I1, W1, start_date=T(1), end_date=T(30)) | (1) the `machine_item_ledger` SELECT's and the `inventory_ledger` SELECT's ORDER BY each end `performed_at DESC, id DESC`; (2) machine == [Xd, Xc, Xb, Xa]; inventory == [Nd, Nc, Nb, Na] | xfail BUG-640 — fails today on: (1) ORDER BY is `performed_at DESC` only |
| LED-IMS-08 | R4a | boundary | 101 machine entries (M1, I1) at 2025-06-01 00:00:00 + k minutes, k = 0..100; 101 inventory entries (STORAGE, F1, I1) at the same times | call(I1, W1, start_date=T(1, 00:00:00), end_date=T(30)) (no skip/limit) | machine has 100 rows, the 100 newest (k = 100..1, newest first; k = 0 absent); inventory likewise | pass |
| LED-IMS-09 | R4a [BUG-648] | bug | same as LED-IMS-08 | call(I1, W1, start_date=T(1, 00:00:00), end_date=T(30), skip=100) | machine == [the k = 0 row]; inventory == [the k = 0 row] | xfail BUG-648 — fails today on: `TypeError` (no `skip` parameter) |
| LED-IMS-10 | R4a [BUG-648] | bug | IM-base | call(I1, W1, start_date=T(1), end_date=T(30), skip=0, limit=1) | machine == [XM2]; inventory == [XN2] (limit applied to each list separately) | xfail BUG-648 — fails today on: `TypeError` (no `limit` parameter) |
| LED-IMS-11 | R5, R6 [BUG-647] | bug | project entries: PX1 (PC1, I1, T(10)), PX2 (PC2, I1, T(12)), PX3 (PC1, I2, T(11)), PX4 (PC1, I1, 2025-07-15), PX9 (`workspace_id` W2, PC9, I1, T(11)) | call(I1, W1, start_date=T(1), end_date=T(30)) | project == [PX2, PX1] (PX3 other item, PX4 out of range, PX9 other workspace) | xfail BUG-647 — fails today on: project == [] |

## `LedgerManager.get_transactions_by_user`

Base setup "TU-base": machine entries by U1: TM1 (M1, T(10)), TM2 (M1, T(12)); by U2: TM3 (M1, T(11)). Project entries by U1: TP1 (PC1, T(10)), TP2 (PC1, T(12)); by U2: TP3 (T(11)). Inventory entries by U1: TN1 (T(10)), TN2 (T(12)); by U2: TN3 (T(11)). W2 decoys, one in each ledger: `workspace_id` W2, `performed_by` U1, T(11).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LED-TBU-01 | R1, R3 | bug | TU-base | call(user_id=U1, workspace_id=W1) | returns a dict with keys exactly {"machine", "project", "inventory"}; machine == [TM2, TM1]; project == [TP2, TP1]; inventory == [TN2, TN1]; U2 rows and W2 decoys absent | xfail BUG-645 — fails today on: raises `AttributeError` |
| LED-TBU-02 | R2 | bug | U1 in each of the three ledgers (one machine entry on M1, one project entry on PC1, one inventory entry STORAGE/F1/I1 per time) at 2025-06-09 23:59:59, 2025-06-10 00:00:00, 2025-06-20 23:59:59, 2025-06-21 00:00:00 (12 rows) | call(U1, W1, start_date=2025-06-10 00:00:00, end_date=2025-06-20 23:59:59) | machine == [06-20, 06-10]; project == [06-20, 06-10]; inventory == [06-20, 06-10] (each list checked) | xfail BUG-645 — fails today on: raises `AttributeError` |
| LED-TBU-03 | R2 | bug | same as LED-TBU-02 (all three ledgers) | call(U1, W1, start_date=2025-06-10 00:00:00) | machine == [06-21, 06-20, 06-10]; project == [06-21, 06-20, 06-10]; inventory == [06-21, 06-20, 06-10] (06-09 excluded from each) | xfail BUG-645 (and BUG-341) — fails today on: raises `AttributeError` |
| LED-TBU-04 | R2 | bug | same as LED-TBU-02 (all three ledgers) | call(U1, W1, end_date=2025-06-10 00:00:00) | machine == [06-10, 06-09]; project == [06-10, 06-09]; inventory == [06-10, 06-09] | xfail BUG-645 (and BUG-341) — fails today on: raises `AttributeError` |
| LED-TBU-05 | R2, R4 | bug | U1 in each of the three ledgers (machine on M1, project on PC1, inventory STORAGE/F1/I1): Ra (T(5)), Rb (T(8)), Rc (T(25), outside the range) per ledger (9 rows) | call(U1, W1, start_date=T(1), end_date=T(10), limit=1) | machine == [machine Rb]; project == [project Rb]; inventory == [inventory Rb] (date filter applied before paging, per list) | xfail BUG-645 (and BUG-341) — fails today on: raises `AttributeError` |
| LED-TBU-06 | R3 [BUG-640] | bug | U1 in each of the three ledgers (machine on M1, project on PC1, inventory STORAGE/F1/I1): Ra (T(5)), then Rb, Rc, Rd (all T(10), ascending ids) per ledger; statement recorder attached | call(U1, W1) | (1) the `machine_item_ledger`, `project_component_item_ledger` and `inventory_ledger` SELECTs' ORDER BY each end `performed_at DESC, id DESC`; (2) machine == [Rd, Rc, Rb, Ra] of the machine rows; project and inventory likewise with their own rows | xfail BUG-645 (and BUG-640) — fails today on: raises `AttributeError` (after BUG-645 is fixed: (1) ORDER BY is `performed_at DESC` only) |
| LED-TBU-07 | R4 | bug | TU-base | call(U1, W1, skip=1, limit=1) | machine == [TM1]; project == [TP1]; inventory == [TN1] (paged per ledger) | xfail BUG-645 — fails today on: raises `AttributeError` |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_machine_ledger` R9 [BUG-642] | `GET /ledgers/machine/` | `limit=0` and `limit=-1` → 422; `limit=1` accepted |
| `get_project_component_ledger` R5 [BUG-642] | `GET /ledgers/project-component/` | `limit=0` → 422; `limit=1` accepted |
| `get_inventory_ledger` R9 [BUG-642] | `GET /ledgers/inventory/` | `limit=0` → 422; `limit=1` accepted |
| `get_attachment_ledger` R6 [BUG-642] | `GET /ledgers/attachments/` | `limit=0` → 422; `limit=1` accepted |
| `get_transactions_by_user` R4 [BUG-642] | `GET /ledgers/reports/user-transactions/{user_id}/` | `limit=0` → 422; `limit=1` accepted |
| `get_item_movement_summary` R4a [BUG-648] | `GET /ledgers/reports/item-movement/{item_id}/` | endpoint accepts `skip`/`limit` (default 0/100, `limit` 1–100, 422 outside) and passes them through |

## Spec gaps
None. (Gaps 1–7 of revision 1 were closed by the describer: spec Gap log G1–G7; G8 corrected the tie-order facts from verify finding 2 and is applied in revision 3.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_machine_ledger` | R1 | LED-GML-01, 02 |
| | R2 [BUG-341] | LED-GML-08, 09, 10 |
| | R3 [BUG-341] | LED-GML-11, 12 |
| | R4 | LED-GML-04, 05, 06 |
| | R5 | LED-GML-03 |
| | R6 | LED-GML-01, 07 |
| | R7 | LED-GML-13 |
| | R8 [BUG-640] | LED-GML-14 (SQL ORDER BY + tied data; ordering with distinct times: GML-01) |
| | R9 [BUG-642] | LED-GML-15, 16, 20 (default limit 100); API part deferred |
| | Errors: negative limit/skip | LED-GML-17, 18 |
| | Inputs: unknown machine | LED-GML-19 |
| | Inputs: default skip/limit 0/100 | LED-GML-20 |
| `get_machine_balance` | R1 | LED-GMB-01 |
| | R2 | LED-GMB-02, 03, 04 |
| | R3 [BUG-641] | LED-GMB-05 |
| `reconcile_machine_item` | R1 | LED-RMI-06, 11 |
| | R2 | LED-RMI-05 |
| | R3 | LED-RMI-01, 06, 10 |
| | R4 [BUG-649] | LED-RMI-02, 03 |
| | R5 | LED-RMI-04, 05 |
| | R6 | LED-RMI-01 |
| | R7 | LED-RMI-07, 11 |
| | R8 [BUG-650] | LED-RMI-12 |
| | R9 | LED-RMI-07, 10, 11 |
| | R9a [BUG-651] | LED-RMI-08, 17 |
| | R10 | LED-RMI-06, 10, 11, 17 |
| | R10a | LED-RMI-09, 10, 13, 14 |
| | R11 [BUG-643] | LED-RMI-15, 16 |
| `get_project_component_ledger` | R1 | LED-PCL-01, 02 |
| | R2 | LED-PCL-03 |
| | R3 | LED-PCL-01 |
| | R4 [BUG-640] | LED-PCL-04 |
| | R5 [BUG-642] | LED-PCL-05, 07 (default limit 100); API part deferred |
| | Errors | LED-PCL-06 |
| `calculate_project_component_total_cost` | R1 [BUG-654] | LED-PCT-01, 02 (pass); 03, 04, 06 (xfail) |
| | R2 | LED-PCT-05, 07, 06 |
| `get_inventory_ledger` | R1 | LED-GIL-01, 02, 03, 04, 05, 08, 11 |
| | R2 [BUG-341] | LED-GIL-10, 11, 12 |
| | R3 [BUG-341] | LED-GIL-13, 14 |
| | R4 | LED-GIL-06, 07, 08 |
| | R5 | LED-GIL-02, 03, 04, 05, 09 |
| | R6 | LED-GIL-01 |
| | R7 | LED-GIL-15 |
| | R8 [BUG-640] | LED-GIL-16 |
| | R9 [BUG-642] | LED-GIL-17, 19 (default limit 100); API part deferred |
| | Errors | LED-GIL-18 |
| `get_inventory_balance` | R1 | LED-GIB-01, 02 |
| | R2 [BUG-655] | LED-GIB-02 (pass); 03, 04, 05 (xfail) |
| | R3 [BUG-641] | LED-GIB-06 |
| `reconcile_inventory` | R1 [BUG-655] | LED-RINV-06, 07, 12, 16 |
| | R2 | LED-RINV-03, 04, 05 |
| | R3 | LED-RINV-08, 12, 13 |
| | R4 [BUG-649] | LED-RINV-01, 02, 04 |
| | R5 | LED-RINV-06 |
| | R6 | LED-RINV-07, 21, 22 |
| | R6a [BUG-653] | LED-RINV-19, 21, 22 (pass boundaries); 13, 15 (xfail) |
| | R7 | LED-RINV-08, 10, 15 |
| | R8 [BUG-650] | LED-RINV-14 |
| | R9 | LED-RINV-10, 19 (pass); 12, 13 (xfail via other bugs) |
| | R9a [BUG-651] | LED-RINV-11, 12 |
| | R9b [BUG-651] | LED-RINV-18, 20, 12, 13, 15 |
| | R10 [BUG-652] | LED-RINV-08, 19 (pass parts); 09, 12, 13, 15 (xfail) |
| | R11 [BUG-644] | LED-RINV-16, 17 |
| `get_attachment_ledger` | R1 | LED-GAL-01 |
| | R2 | LED-GAL-02, 03, 04, 05, 06, 07 |
| | R3 | LED-GAL-08, 09, 11 |
| | R4 | LED-GAL-01, 07 |
| | R5 [BUG-640] | LED-GAL-10 |
| | R6 [BUG-642] | LED-GAL-11, 13 (default limit 100); API part deferred |
| | Errors | LED-GAL-12 |
| `get_item_movement_summary` | R1 [BUG-646] | LED-IMS-02 (inclusive bounds, pass); 04, 05, 06 (xfail) |
| | R2 [BUG-341] | LED-IMS-01, 02 (pass); 03 (xfail) |
| | R3 [BUG-341] | LED-IMS-01, 02 (pass); 03 (xfail) |
| | R4 [BUG-640] | LED-IMS-07 |
| | R4a [BUG-648] | LED-IMS-08 (pass); 09, 10 (xfail); API part deferred |
| | R5 [BUG-647] | LED-IMS-11 |
| | R6 | LED-IMS-01, 11 |
| `get_transactions_by_user` | R1 [BUG-645] | LED-TBU-01 |
| | R2 [BUG-341] | LED-TBU-02, 03, 04, 05 |
| | R3 [BUG-640] | LED-TBU-01, 06 |
| | R4 [BUG-642] | LED-TBU-05, 07; API part deferred |
