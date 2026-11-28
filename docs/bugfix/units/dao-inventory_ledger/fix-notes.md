# Fix notes: dao-inventory_ledger

## Round 1 (2026-11-28)

Worktree: `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-inventory_ledger` (branch `bugfix/dao-inventory_ledger`). Only file changed: `app/dao/inventory_ledger.py`.

### Changed

- **BUG-655**, `InventoryLedgerDAO.calculate_balance`: the line that read the nonexistent `entry.value_after` now does this:
  ```python
  if entry.avg_price_after is None:
      return (entry.qty_after, Decimal('0.00'))
  return (entry.qty_after, entry.qty_after * entry.avg_price_after)
  ```
  I updated the docstring to state the value formula and the empty-price case. The query, its filters and its `ORDER BY performed_at DESC` are unchanged, and so are the no-entry return `(0, Decimal('0.00'))` and the signature.
- **BUG-885**, in `get_by_workspace`, `get_by_transaction_type` and `get_by_date_range`: `if factory_id:` became `if factory_id is not None:`, and `if item_id:` became `if item_id is not None:`. That is three methods with two lines each.

I left the `if inventory_type:` checks alone. The brief allows changing them, but it would make no difference to any result.

### Why

- BUG-655: the balance is now worked out from the latest entry as `qty_after × avg_price_after`. An int times a `Numeric(15,2)` `Decimal` gives a `Decimal` that is already exact to two places, so it is not rounded (as the brief says, no quantize and no float). If `avg_price_after` is NULL, the value is `Decimal("0.00")` and the quantity is still returned. The `is None` check also handles a 0.00 price correctly, because the product is then 0.00 anyway.
- BUG-885: only `None` now means "no filter". A `0` is treated like any other id and matches no rows, the same as the BUG-880 precedent. The workspace filter is still there in every query (HR-16).

### Reproductions (rowkit, against `bf_dao_inventory_ledger_test`; script was in the session scratchpad and has been deleted)

Data: one workspace, factory F and item I. STORAGE entries inserted in this order: 09:00 (30 @ 7.00), 11:00 (20 @ 6.00), 10:00 (10 @ 4.00). A newer DAMAGED entry at 12:00 (99 @ 1.00). A WASTE entry (5 @ NULL). A SCRAP entry (0 @ 6.00). Six entries in total, four of them with transaction type `manual_add`.

| Check | Before | After |
|---|---|---|
| balance STORAGE (latest by `performed_at`, other bucket newer) | `AttributeError: 'InventoryLedger' object has no attribute 'value_after'` | `(20, Decimal('120.00'))` |
| balance WASTE, avg price NULL | `AttributeError` | `(5, Decimal('0.00'))`, types `int` / `Decimal`, str `"0.00"` |
| balance SCRAP, qty 0 @ 6.00 | `AttributeError` | `(0, Decimal('0.00'))` |
| balance, bucket with no entries | `(0, Decimal('0.00'))` | `(0, Decimal('0.00'))` (unchanged) |
| `get_by_workspace` factory_id=0 / item_id=0 | 6 / 6 | 0 / 0 |
| `get_by_transaction_type("manual_add")` factory_id=0 / item_id=0 | 4 / 4 | 0 / 0 |
| `get_by_date_range(2026-01-01..02)` factory_id=0 / item_id=0 | 6 / 6 | 0 / 0 |
| same three methods, no filter / factory_id=F | 6,4,6 / 6,4,6 | 6,4,6 / 6,4,6 (unchanged) |

I also ran `python -c "import app.main"`, which succeeded, and `ruff check app/dao/inventory_ledger.py`, which found nothing.

### Assumptions

- I didn't quantize. Per the brief, the product of an int and a two-place Decimal is already exact. For qty 0 @ 6.00 the result is `Decimal('0.00')`, which equals `Decimal("0")`.
- I didn't share code between `calculate_balance` and `get_latest_entry`. This keeps `get_latest_entry` completely untouched and the diff small.

### Seen, not fixed

- `app/dao/machine_item_ledger.py` and `app/dao/project_component_item_ledger.py` `calculate_balance` both use the same `entry.value_after or Decimal('0.00')` pattern. I didn't check whether their models have a `value_after` column. They are outside this unit, and project ledgers are deferred.
- The tie-order bugs (BUG-640, BUG-641, BUG-664), the date-range bug (BUG-992), and the dead `get_by_order`, which reads `InventoryLedger.order_id`, a column that doesn't exist: all left as the brief says.

### Risk

- Low. Callers that used to get a 500 for buckets with history now get real values. `reconcile_inventory` will now go on to the stock-row comparison and adjustment logic for those buckets. That code was never reached before, and it has its own known bugs (BUG-642 and others in `ledger_manager.py`).
- `factory_id=0` / `item_id=0` on `GET /ledgers/inventory/` and in the item summary's recent activity now return an empty list instead of every entry.

## Round 2 (2026-11-28)

This round answers `feedback-1.md` and brief §7: the inventory halves of BUG-641, BUG-664 and BUG-803 are now in scope. The round-1 changes are unchanged. Only `app/dao/inventory_ledger.py` changed.

### Changed

- **BUG-641**, `InventoryLedgerDAO.calculate_balance`: `ORDER BY` is now `performed_at DESC, id DESC`, using `.order_by(desc(InventoryLedger.performed_at), desc(InventoryLedger.id))`. The docstring now says how the latest entry is chosen.
- **BUG-664 / BUG-803**, `InventoryLedgerDAO.get_latest_entry`: the same `ORDER BY` change. The docstring gained a line on how "most recent" is chosen.
- Each query has a one-line comment explaining why `id` breaks the tie: rows written in one save share `performed_at`.
- Filters, signatures, return values and the no-entry results are unchanged. I didn't touch the four list methods (BUG-640), `machine_item_ledger.py`, any migration or any index. The two queries stay separate.

I checked with `compile_query.py`. `get_latest_entry` now sends `... WHERE workspace_id = 3 AND factory_id = 1 AND item_id = 2 AND inventory_type = 'STORAGE' ORDER BY performed_at DESC, id DESC`, with all four bucket filters still there (HR-16).

### Why

Every ledger row written in one save gets the same `performed_at`, which is the transaction's `now()`. With `performed_at` alone, Postgres may return any of the tied rows. Ids grow with each insert, so `id DESC` picks the row written last, and only among the tied rows: `performed_at` is still the first sort key, so an older entry never wins, whatever its id.

### Reproductions (rowkit, `bf_dao_inventory_ledger_test`; scripts were in the session scratchpad and have been deleted)

| Check | Before | After |
|---|---|---|
| One save: receive 50 @ 5.00, then send 20 (two STORAGE rows, both with `performed_at` = the same `now()`, ids n and n+1; stock row 30 @ 5.00): `calculate_balance` | `(50, Decimal('250.00'))` (stale row) | `(30, Decimal('150.00'))` |
| Same: `get_latest_entry().qty_after` | `50` | `30` |
| Same: `ledger_manager.reconcile_inventory` | `{'status': 'adjusted', 'ledger_qty': 50, 'snapshot_qty': 30, 'discrepancy': 20, 'adjustment_created': True}`: 20 bolts (৳100.00) that don't exist | `{'status': 'balanced', 'ledger_qty': 30, 'snapshot_qty': 30, 'discrepancy': 0, 'adjustment_created': False}` |
| R4a: three tied rows with qty 15, 10, 99 @ 2.00, the qty-10 row having the highest id but inserted second; plus an older (11:00) row with an even higher id. `calculate_balance` | `(15, Decimal('30.00'))` | `(10, Decimal('20.00'))` (the older row with the higher id does not win) |
| Same: `get_latest_entry` | the qty-15 row (lowest id) | the qty-10 row (highest id) |
| Tied rows where the highest id was inserted first, avg price NULL | `(40, Decimal('0.00'))` / the highest-id row (passed by chance, from physical order) | the same, now guaranteed by the `ORDER BY` |
| Empty bucket | `(0, Decimal('0.00'))` / `None` | unchanged |
| Round-1 re-check: R4 distinct times → `(20, Decimal('120.00'))`; NULL price → `(5, Decimal('0.00'))`; `get_latest_entry` returns the 11:00 row; `factory_id=0` / `item_id=0` → 0 rows; no filter → all rows | as expected | unchanged |

I also ran `python -c "import app.main"`, which succeeded, and `ruff check app/dao/inventory_ledger.py`, which found nothing.

### Assumptions

- I didn't reproduce the purchase-return chain (10 → 7 → 4 → 1) through `po_return_inventory`, because the manager is out of scope. It relies on `get_latest_entry` choosing the highest id on a tie, and that is shown directly above.

### Seen, not fixed

- The same tie still exists in `app/dao/machine_item_ledger.py` (`calculate_balance`, `get_latest_entry`) and `app/dao/project_component_item_ledger.py` (BUG-2463). Both are out of scope.

### Risk

- Every stock movement goes through `get_latest_entry` (in `InventoryDAO.sync_snapshot_from_ledger`). On a tie it now re-syncs from the highest-id row instead of a row chosen by the query plan. That is the intended fix, but it changes the stock values a movement starts from whenever rows written in one save share a timestamp. Callers that apply several movements to the same bucket in one save are worth a look first: purchase returns, transfers, and stock-in followed by stock-out.
- There is no index on `(…, performed_at, id)`. The added sort key only orders the rows that are already filtered to one bucket, so the cost should be negligible.
