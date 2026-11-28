# Contract note: dao-inventory_ledger (round 1, 2026-11-28)

**No shape change. Two value changes. Frontend stage skipped** (no frontend code depends on the old values; see below).

1. `GET /ledgers/inventory/balance/`: for a bucket with ledger history, it answers 200 instead of 500.
   Example: Factory 1, Bolt, STORAGE, latest entry "after: 50 @ 5.00" → `{"factory_id": 1, "item_id": 7,
   "inventory_type": "STORAGE", "quantity": 50, "total_value": 250.0}`. Latest entry with an empty average price →
   `"total_value": 0.0`. (`total_value` is still a float: BUG-3043, separate.) The frontend `LedgersPage`
   already shows `inventoryBalance.data` and needs no change.
2. `POST /ledgers/inventory/reconcile/`: for a bucket with history, it answers 200 with `status` `balanced` / `adjusted`
   (and messages) instead of 500. The response shape is unchanged. The frontend shows `res.message` only.
3. `GET /ledgers/inventory/?factory_id=0` (or `item_id=0`) → `[]` instead of the whole workspace's entries. The frontend
   never sends `0`: it appends the parameter only when it is set.

## Round 2 addition (2026-11-28): tie-break of the "latest entry"

Still no shape change, and the frontend stage is still skipped. Values change only where several ledger rows of one bucket were written in one
save:

4. `GET /ledgers/inventory/balance/` reports the row written last. Example: in one save, 50 bolts received at ৳5.00 and 20 sent
   out → `"quantity": 30, "total_value": 150.0` (not 50 / 250.0).
5. Stock rows (`inventory.qty`, `avg_price`, as shown on the stock pages) stay right after saves that move one bucket several
   times. Example: a purchase return of 3 lines × 3 bolts from a stock of 10 leaves 1, where it used to leave 4. Reconcile on such a
   bucket answers `balanced` instead of writing an adjustment.
