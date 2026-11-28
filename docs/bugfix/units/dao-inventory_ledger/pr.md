## Fix: stock balance and reconcile stop crashing, and stock stays right when one save moves an item several times

**Fixes BUG-655, BUG-803 and BUG-885, and the inventory half of BUG-641 and BUG-664.** One file (`app/dao/inventory_ledger.py`). No database change, no API shape change (some values change, see below). Stock area, so not an auto-merge.

---

### What was wrong

**1. When one save moved the same item more than once, the system could take the wrong row as the "latest" stock (BUG-664, BUG-803, BUG-641). This is the one that matters most.**

Every stock movement writes a row in the inventory ledger: "before 10, after 7". All the rows written in one save get the **same timestamp**. To find the current stock, the code took "the newest row by timestamp", and when several rows tied, the database could hand back any of them, often the first one. The next movement then started from that stale number.

*Example, a purchase return:* the stock of bolts is 10. A return has three lines of 3 bolts each. The right answer is 1 left. Today the third line re-reads the stock from the first line's row (7) instead of the second's (4), so the stock ends at **4 bolts**. Three bolts that went back to the supplier are still shown as on the shelf. With this fix: **1 bolt**.

*Example, the reconcile button:* in one save, 50 bolts are received at ৳5.00 and 20 are sent out. The stock is 30. Once the crash below is fixed, reconcile would have read the first row ("after: 50") as the ledger's balance and **"corrected" the stock to 50**: ৳100.00 of bolts that don't exist (20 × ৳5.00). With this fix the balance is 30 bolts, ৳150.00, and reconcile says **balanced** and writes nothing.

The same thing happened with transfers that repeat an item, and with two receipts at different prices in one save (the average price could fall back to the first receipt's price).

**2. The inventory balance and reconcile crashed for any item with history (BUG-655)**

`GET /ledgers/inventory/balance/` and `POST /ledgers/inventory/reconcile/` answered with an error (500) for every item that had ever moved. The code was copied from the machine ledger and read a column the inventory ledger doesn't have.

*Example:* Factory 1 received 50 bolts at ৳5.00. Asking for the balance gave an error instead of "50 bolts, ৳250.00". Reconcile gave an error too, so a stock row that really had drifted could never be corrected.

**3. `factory_id=0` or `item_id=0` returned everything (BUG-885)**

On the inventory ledger list, a filter of `0` was treated as "no filter", so `GET /ledgers/inventory/?factory_id=0` returned the newest 100 entries of **every** factory. Now `0` is treated like any other id: no factory has id 0, so the list is empty. Only a missing filter means "all".

---

### What changed

All in `app/dao/inventory_ledger.py`:

```diff
  # calculate_balance and get_latest_entry: which row is "the latest"
- .order_by(desc(InventoryLedger.performed_at))
+ .order_by(desc(InventoryLedger.performed_at), desc(InventoryLedger.id))   # same time: the row written last wins

  # calculate_balance: the value of the balance
- return (entry.qty_after, entry.value_after or Decimal('0.00'))           # column doesn't exist: crash
+ if entry.avg_price_after is None:
+     return (entry.qty_after, Decimal('0.00'))                           # no average price: value 0.00
+ return (entry.qty_after, entry.qty_after * entry.avg_price_after)       # quantity x average price

  # the three list methods (by workspace, by transaction type, by date range)
- if factory_id:
+ if factory_id is not None:                                               # 0 filters like any id
- if item_id:
+ if item_id is not None:
```

The tie-break follows house rule HR-6: when the time is the same, the higher id is the later write. Time stays the first key, so an older row never wins only because of a higher id. The value is quantity × average price. Quantity is a whole number and the price has two decimals, so the result is already exact and no rounding is needed (HR-15). It stays a `Decimal`.

### What you'll notice

- The inventory balance and reconcile work for items with history. Reconcile reports **balanced** for ordinary saves and corrects only real drift (for example, a stock row someone edited by hand).
- From the next movement on, stock and average price stay right after purchase returns, transfers and receipts that touch the same item several times in one save.
- An inventory ledger list filtered by `factory_id=0` or `item_id=0` is empty. The item summary's "recent activity" passes an item id; with an id of 0 it now shows nothing instead of the whole workspace's activity. The app never sends 0.
- Deliberately unchanged: the order of the ledger **lists** (BUG-640, separate), the machine ledger, and the project ledger.

### What to look at when reviewing

- **Stock that is already wrong stays wrong.** The fix stops new damage, but it doesn't repair rows that BUG-664 / BUG-803 have already corrupted. The ledger's own "after" chain carries the error forward too, because each later row started from the stale number. The systems engineer proposes a one-off **read-only check**: for each item's history, look for a row whose "before" doesn't match the previous row's "after". That would size the damage. Any repair is your decision and is not in this PR.
- **The machine ledger halves of BUG-641 and BUG-664 are still open.** The machine ledger (`app/dao/machine_item_ledger.py`) has the same tie problem. It's another file and is planned as its own unit. Those two bugs stay open with the note "inventory half fixed".
- **The balance's `total_value` is still sent as a float** in the API (BUG-3043, separate). Now that the balance works, that's visible: ৳250.00 shows up as `250.0`.
- **Four known-failure tests were left as they are this round.** They check the right behaviour but are set up wrongly, so no correct fix can pass them yet. They're recorded in `docs/bugfix/wrong-tests.md` with a proposed correction and will be fixed in a later round. Two are about reconcile (one is missing the "no stock row" setup it describes, and one also needs two other reconcile bugs). Two are about stock-out / stock-in picking "the new ledger row" (they pick it by id, but the setup gives an older seeded row a higher id).

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review (2 rounds):** callers checked: `LedgerManager.get_inventory_balance` / `reconcile_inventory` (balance and reconcile endpoints), `InventoryDAO.sync_snapshot_from_ledger` through `ensure_for_factory_item_type` (stock in, stock out, purchase returns, transfers, production damaged bucket), and `ItemSummaryService._recent_activity`. Throwaway runs through the real callers (purchase return 3 × 3, transfer 3 × 5, in + out in one save, two receipts at ৳5.00 and ৳7.00, real drift) show the right stock, and reconcile balanced with no write. Nothing relied on the old tie order. No index needed.
- **Contract:** same shape, codes and inputs; values only (balance and reconcile answer instead of 500; tied rows resolve to the last write; `0` filters). No frontend change needed, so no frontend PR.
- **Tests:** the 26 tests marked as known failures for these bugs now pass, and their markers are removed. Every other test in the full suite had the same result before and after (base `092776b`), apart from 5 order-only tests of other bugs that pass or fail by luck and are ignored as usual. The flip-check tool can't express "half a bug", so it reports REJECTED, but only for the expected leftovers, each still a known failure before and after: the 7 machine-ledger tests of BUG-641 / BUG-664 (machine half still open) and the 4 wrong tests above. That's the agreed acceptance rule, so the result counts as CLEAN. Two reconcile tests that also name other open bugs (BUG-650, BUG-653) stay known failures, as expected.
- **Database:** no migration; Alembic unchanged.
- **Follow-up for the owner:** the read-only check for already-corrupted stock (impact review §5).
- **Commits:** `f6ff706` on branch `bugfix/dao-inventory_ledger`.

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 1 minor, 1 nit (strict independent review, `review-1.md`).

Minor, for you to decide:
- **R1-1:** the "latest entry" query is written out twice, in `calculate_balance` and `get_latest_entry`. Reconcile takes the quantity from one and the price from the other, so the two must never drift apart. Having `calculate_balance` read through `get_latest_entry` would keep a single definition. They are identical today, so this is safe to merge; it's a small cleanup that could go in a later unit.

Nit: the same inline comment appears in both methods (it goes away if R1-1 is taken).
