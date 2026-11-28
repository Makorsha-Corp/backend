# Feedback, round 1 → round 2: dao-inventory_ledger (2026-11-28)

## Keep everything you did in round 1

Your round-1 changes are correct and stay exactly as they are:
- `calculate_balance` returns `(qty_after, qty_after × avg_price_after)` of the latest entry, with
  `Decimal("0.00")` when the average price is empty (BUG-655).
- `factory_id` / `item_id` filter whenever they are not `None`, so `0` matches nothing (BUG-885).

## The brief gained a section: §7 "Scope change (round 2, 2026-11-28)"

Read §7 of `brief.md` first. A few earlier lines of the brief were updated to match it (§3 R4a, the
"must not change" list, HR-6 in §4, §5 and §6). In short, this unit now also covers the inventory half of
**BUG-641**, **BUG-664** and **BUG-803**.

## Why

With the crash gone, the reconcile button now works for buckets with history. It reads "the latest
entry", and today that is chosen by `performed_at` alone. All ledger rows written in one save share the
same `performed_at`, so on a tie the database may return an older row.

Example: in one save, Factory 1 receives 50 bolts at ৳5.00 into STORAGE and then sends 20 out. The
real stock is 30 bolts (৳150.00), and the stock row correctly says 30. Someone presses Reconcile. The
balance reads the older "after: 50" row and "corrects" the stock to 50 bolts (৳250.00), creating
৳100.00 of bolts that do not exist. The same stale pick also happens today before every ordinary
stock movement, because the "ledger wins" re-sync uses `get_latest_entry`. After this round, the
balance in that example must be 30 bolts / ৳150.00, and reconcile must report the bucket as balanced.

## What must hold now

- **`calculate_balance` R4a (BUG-641):** among entries of the bucket that share the greatest
  `performed_at`, the latest is the one with the greatest `id`.
- **`get_latest_entry` R3 (BUG-664 / BUG-803):** the same rule. Among tied entries, the greatest `id`
  wins. The `id` decides, not the physical insertion order.
- In both, an older entry (smaller `performed_at`) never wins, whatever its `id` (`calculate_balance` R4,
  `get_latest_entry` R2). `id` only breaks ties.
- Every other rule of both methods in §7.2 stays: the exact four-key bucket match (HR-16 workspace
  filter included), the no-entry results (`(0, Decimal("0.00"))` and `None`), no change to the database,
  and no look at the factory's or item's state.
- What this means for callers (no change needed in them): three purchase-return lines of 3 bolts each,
  from a stock of 10 in one completion, must leave 10 → 7 → 4 → 1. A stock-out right after tied ledger
  rows must start from the row with the highest id.

## Still out of scope

- `app/dao/machine_item_ledger.py` (the machine halves of BUG-641 and BUG-664): leave that file alone.
- The `ORDER BY` of the four list methods (`get_by_workspace`, `get_by_transaction_type`,
  `get_by_date_range`, `get_by_performer`) stays as it is (BUG-640, another unit).
- No migration and no index.

Add a "Round 2" section to `fix-notes.md` with what you changed and why.
