# Code review 1: dao-inventory_ledger (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 1)
Diff reviewed: 092776b..f6ff706 (`git diff origin/main...HEAD -- app alembic`), files: `app/dao/inventory_ledger.py` (no alembic change)

## 1. What a correct fix must do (written before reading the diff)

**BUG-655 (`calculate_balance`)**
- No entry for the bucket → exactly `(0, Decimal("0.00"))`.
- Otherwise pick the bucket's latest entry (all four bucket columns + `workspace_id` filtered) and return
  `(qty_after, qty_after × avg_price_after)` as `(int, Decimal)`; never a float, never `value_after`.
- `avg_price_after IS NULL` → `(qty_after, Decimal("0.00"))`, quantity still returned.
- `qty_after = 0` with a price → a Decimal equal to 0; no special-casing of any qty (negative included).
- No rounding needed (int × Numeric(15,2) is exact); any quantize must be 0.01 HALF_UP (HR-15).
- No join or filter on factories/items; read-only.

**BUG-641 / BUG-664 / BUG-803 (tie order of both "latest entry" lookups)**
- `ORDER BY performed_at DESC, id DESC` then top-1, in both `calculate_balance` and `get_latest_entry`.
- An older `performed_at` never wins whatever its id; `id` decides only between tied rows.
- Both lookups must agree, because `reconcile_inventory` reads qty from one and avg price from the other.
- Callers to verify: `InventoryDAO.sync_snapshot_from_ledger` (re-sync before every stock movement in
  `_storage_in` / `_storage_out`), `reconcile_inventory`, `get_inventory_balance`. In one transaction
  every row has the same `now()`, so the §7 scenario (receive 50 @ 5.00, send 20 → 30 / 150.00) and the
  BUG-803 scenario (10 → 7 → 4 → 1) must come out right.

**BUG-885 (three list methods)**
- `factory_id` / `item_id`: only `None` skips the filter; `0` filters and matches nothing.
- Workspace filter kept; ORDER BY of the four list methods unchanged (BUG-640 out of scope);
  `if inventory_type:` may stay.

**Must not change:** signatures, return types, `get_by_performer`, `exists_for_source`, dead
`get_by_id_and_workspace` / `get_by_order`, other files, no migration.

## 2. Findings

### R1-1 [minor] The "latest entry" query is written out twice
- Where: `app/dao/inventory_ledger.py:147-158` (`calculate_balance`) and `:173-184` (`get_latest_entry`)
- Problem: the two methods carry an identical filter + `ORDER BY performed_at DESC, id DESC` + `first()`
  block, each with the same copied comment. `reconcile_inventory` (`app/managers/ledger_manager.py:475`
  and `:513`) takes the quantity from one and the average price from the other, so the two must never
  drift apart. Two copies of one definition is exactly how BUG-641 and BUG-664 came to exist as separate
  bugs. Today they are identical and correct.
- Evidence: the two blocks in the file, lines 147-158 and 173-184. The brief §7.4 explicitly allows sharing one query.
- Suggested direction: have `calculate_balance` read the entry through `get_latest_entry`, so "latest"
  is defined in one place. Optional: the owner can take it or leave it. It does not block.

### Nit
- The same inline comment ("Rows written in one save share performed_at; the higher id is the later
  write.") appears twice. It goes away if R1-1 is taken.

## 3. Questions (unproven)

None.

## 4. What is good

- Minimal: 3 × 2 one-token `is not None` changes, a two-column ORDER BY in exactly the two lookups, and the
  value formula. Nothing else in `app/` or `alembic/` moved. `ruff check` is clean.
- Tie-break style matches the codebase (`app/dao/expense_order_event.py:20`
  `order_by(desc(...created_at), desc(...id))`; this file already uses `desc()`).
- `None` price is checked with `is None`, not truthiness, so a stored `0.00` price yields `0.00` through
  the formula rather than through a special case.
- Verified with throwaway rolled-back checks on `bf_dao_inventory_ledger_test` (real `_storage_in` /
  `_storage_out` in one transaction, so `performed_at` really ties):
  - §7 scenario: two rows with identical `performed_at`. Balance `(30, Decimal('150.00'))` (`int`, `Decimal`)
    and `get_latest_entry.qty_after == 30`. Reconcile on a correct snapshot returns `balanced`. With the
    snapshot corrupted to 40, reconcile sets it to 30 @ 5.00 and the balance afterwards is still `(30, 150.00)`.
  - BUG-803: stock 10, three outs of 3 in one transaction, final stock 1.
  - An older entry with a higher id does not win (`(20, 120.00)`). A NULL price gives `(5, Decimal('0.00'))`.
    qty 0 gives `Decimal('0.00')`. A newer entry in another inventory type is ignored. An empty bucket gives
    `(0, Decimal('0.00'))` and `None`. Another workspace gives `(0, 0.00)`.
  - `factory_id=0` / `item_id=0` give `[]` in all three list methods and through
    `LedgerManager.get_inventory_ledger`. `None` still means "no filter".
- Performance: no composite index covers these lookups (only single-column indexes in
  `alembic/versions/100_squashed_baseline.sql:5734-5790`), so the extra `id` sort key does not change
  how the query runs.
