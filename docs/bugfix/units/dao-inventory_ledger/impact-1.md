# Impact review, round 1: dao-inventory_ledger (2026-11-28)

Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-inventory_ledger diff` (uncommitted), file
`app/dao/inventory_ledger.py` only. The diff changes `calculate_balance` to return `(qty_after, qty_after × avg_price_after)`,
with `NULL` → `0.00` (BUG-655). It also changes `if factory_id:` / `if item_id:` to `is not None` in
`get_by_workspace`, `get_by_transaction_type` and `get_by_date_range` (BUG-885).

**Verdict: REVIEW. Held for the orchestrator, not sent to the fixer.** The DAO diff itself is correct,
minimal and in scope: no feedback-1 is needed for what it does. The problem is what it unlocks.
`POST /ledgers/inventory/reconcile/` becomes reachable, and on timestamp-tied ledger rows it writes
**wrong stock** (phantom or lost units). That is BUG-641. The same root cause already corrupts stock today through the
automatic snapshot sync on every movement (BUG-664 / BUG-803). See §3 for the options and my recommendation.

## 1. The DAO change (BUG-655, BUG-885)

- `calculate_balance`: the query, its filters and `ORDER BY performed_at DESC` are unchanged. The value is an `int × Numeric(15,2)`
  product, so it is exact to two places: no rounding step, HR-15 not engaged (checked: 7 @ 3.33 → 23.31). No float.
  `NULL` price gives `0.00` with the quantity kept. `get_latest_entry` is untouched.
- BUG-885: the workspace filter is kept in all three methods (HR-16). `inventory_type` checks are left as they are (allowed by the brief).
- No shortcut and no scope creep. The fixer's "seen, not fixed" notes are accurate. The sibling `value_after`
  reads in the machine and project DAOs are not broken: their models have that column.

## 2. Upstream: who calls, what changes

| Caller | Path | Before | After |
|---|---|---|---|
| `LedgerManager.get_inventory_balance` → `LedgerService.get_inventory_balance` | `GET /ledgers/inventory/balance/` | 500 for any bucket with history | `{quantity, total_value}` of the latest entry (value as float: BUG-3043, unchanged) |
| `LedgerManager.reconcile_inventory` → `LedgerService.reconcile_inventory` (commits) | `POST /ledgers/inventory/reconcile/` | 500 for any bucket with history, nothing written | runs the comparison and the adjustment code (§3) |
| `LedgerManager.get_inventory_ledger` | `GET /ledgers/inventory/` | `factory_id=0`/`item_id=0` = no filter | `[]` |
| `ItemSummaryService._recent_activity` | item summary | `item_id=0` = whole workspace | `[]` (no item has id 0) |

- **Who can reconcile:** any active member of the workspace (`get_current_active_user` + `get_current_workspace`,
  no role check). The frontend `LedgersPage` has a Reconcile button once a factory and an item are picked.
  **No automatic or scheduled caller.** There is no scheduler in `app/`. `reconcile_inventory` has exactly one caller.
- "Inventory summary" does not use `calculate_balance`. The stock page reads the `inventory` snapshot rows. Only the
  ledger page shows the balance.
- Frontend: the list query sends `factory_id` / `item_id` only when they are set (`!== undefined`), so `0` is never sent.
  The balance query is skipped until both are chosen. The reconcile handler shows only `res.message`.

## 3. Reconcile now reachable: what it writes (throwaway run through the manager on the worktree code)

The script is in the scratchpad, not the repo: `se-dao-inventory_ledger/probe.py`, `probe2.py`, run against
`bf_dao_inventory_ledger_test` in a rolled-back transaction. User u1 made the stock rows and u2 reconciles.

| # | Data | Result | Writes | Right? |
|---|---|---|---|---|
| S1 | ledger 0→50 @5.00, 50→30; snapshot 30 @5.00 (ordinary, in sync) | `balanced` | nothing | yes |
| S2 | same ledger; snapshot 25 (drift) | `adjusted`, discrepancy 5 | snapshot qty 25→30, avg 5.00; ledger row `inventory_adjustment` qty 5, before 25, after 30, unit 5.00, total 25.00, by u2; second reconcile `balanced`, no duplicate | stock **right**; row breaks the chain (BUG-651); `updated_by` stays u1 (BUG-652) |
| S3 | ledger 30; snapshot 35 | `adjusted`, −5 | snapshot → 30; row qty **5** (unsigned), before 35, after 30 | stock right; history row as BUG-651 |
| S4 | latest entry avg `NULL`; snapshot 25 | `TypeError` → 500, rolled back | nothing | loud, no write (BUG-650) |
| S5 | qty equal, snapshot avg 9.00 vs ledger 5.00 | `balanced` | nothing | price left wrong (BUG-653), same as before the fix (no write) |
| S6 | ledger 7 @3.33; snapshot 4 | `adjusted` | row total 9.99 (exact) | yes, no rounding issue |
| **S7** | **ordinary movement code** in one save: storage-in 50 @5.00, then storage-out 20 (both rows get the same `performed_at` = transaction start) → ledger ends at 30, snapshot 30 (correct) | balance returns **(50, 250.00)**; reconcile `adjusted` +20 | snapshot **30 → 50**; adjustment row before 30, after 50, dated later than both | **WRONG STOCK: 20 phantom units.** The new row is now the latest entry, so the wrong 50 is locked into the ledger |
| S8 | tie, rows inserted 30 then 50, snapshot 50 | balance (30, …), `adjusted` −20 | snapshot 50 → 30 | **WRONG STOCK: 20 units lost** |
| S9 | **today's code, no reconcile**: as S7, then a later ordinary storage-out of 5 | — | snapshot synced to the stale 50, then minus 5 = **45** (right: 25) | the same wrong write already happens automatically (BUG-664 / BUG-803) |

The plan is Seq Scan + Sort on `performed_at`, so on a tie the row that comes back follows physical order. In practice that is the
first-inserted row, which is the stale one.

### What the open manager bugs do once reconcile is reachable

- **BUG-641 (tie in `calculate_balance`): the only one that writes wrong stock** (S7/S8). Ties are ordinary:
  every ledger row of one save shares `now()`. Two movements of one bucket in one request are enough:
  a PO receive with two lines of the same item, a return with several lines (BUG-803), or an in + out in one flow.
  Reconcile also reads the average price through `get_latest_entry` (BUG-664), so on a tie it can also set a stale
  `avg_price` when the two rows have different prices.
- **BUG-651:** the adjustment row has `quantity` = |difference| (no sign), `qty_before` = old snapshot. History is misleading
  ("+5" shown in the item's recent activity for a correction downward), but nothing sums ledger `quantity` /
  `total_cost` (grepped: no aggregate over `inventory_ledger` columns in `app/`), and the row's `qty_after` is the
  ledger quantity, so the balance and later movements are unaffected.
- **BUG-652:** `updated_by` is not stamped: an audit gap, not a stock error.
- **BUG-644 (no lock):** two concurrent reconciles each write an adjustment row. The snapshot value is the same, so this
  gives duplicate history and no stock error.
- **BUG-650:** loud 500, nothing written. **BUG-653:** no write. **BUG-649:** no history means the bucket never reaches the changed code.
- Rounding: `abs(d) × avg` is exact (int × 2 dp). There is no quantize and no float in the write path.

### Is reachable worse than the crash?

For in-sync data (the normal case, S1), reconcile is a harmless `balanced`. For real drift (S2/S3), it fixes the stock correctly,
with untidy history. For tied rows (S7/S8), it makes a **correct** snapshot **wrong** and records the wrong value as the latest
ledger entry. That happens silently, behind a button labelled "reconcile" that a user presses to make stock right. The crash wrote nothing.
So for the tie case, yes, it is worse than the crash. It is not a new class of damage, though: S9 shows that today the next
ordinary movement on that bucket already does the same rollback, with no button pressed. Both come from one root cause in
this same file: `calculate_balance` and `get_latest_entry` order by `performed_at` only.

**Worked example (taka).** In one save, Factory 1 receives 50 bolts at ৳5.00 into STORAGE and sends 20 out. Stock is
30 bolts = ৳150.00, and the stock row says 30. A storekeeper opens the ledger page and presses Reconcile.
After this fix, the system reads the stale first row ("after: 50"). It reports "Discrepancy found and corrected: 20 units adjusted"
and sets stock to 50 bolts = ৳250.00. That is ৳100.00 of bolts that do not exist, and the 20 can then be sold or
transferred. Today the same press gives an error and changes nothing. (Without any press, the next issue of 5 bolts today
already leaves 45 instead of 25: BUG-664.)

### Options

1. **Ship as is.** Correct for all untied data, and the tie damage already exists via BUG-664. But it adds a manual trigger
   that writes a confident, wrong "correction". I do **not** recommend this for a stock unit.
2. **Recommended: widen this unit with the inventory half of BUG-641 and BUG-664 / BUG-803.** In
   `app/dao/inventory_ledger.py`, `calculate_balance` and `get_latest_entry` would order by `performed_at` descending
   **then `id` descending** (HR-6, intended behaviour already settled in those bug rows). That is the same file and two
   `order_by` lines, with no owner rule needed. It removes S7/S8 and also fixes S9 (the automatic sync), the larger exposure.
   Reconcile is then right for every input, except for history-only issues (BUG-651/652/644, untidy rows, no wrong
   stock) and the loud BUG-650.
   - Planner and tester impact: the BUG-641 machine half (`machine_item_ledger.calculate_balance`) and the
     BUG-664 machine half (`MachineItemLedgerDAO.get_latest_entry`) stay open. Their tests that name only the inventory side
     flip; LED-BAL-13 and LED-GIB-06 (641 + 655) then flip too. The tester must re-run the pre-check for the added
     targets. The brief's §6 "leave `get_latest_entry` unchanged" must be lifted (the brief is the fixer's only input).
3. **Keep reconcile blocked** until the manager bugs are fixed. The minimal block is a refusal at the start of
   `LedgerManager.reconcile_inventory` (or `LedgerService.reconcile_inventory`), for example 409 "Inventory reconcile is
   temporarily unavailable". That is outside this unit's file, has no bug row behind it, and changes the API. It is worse than option 2, because the
   automatic sync (S9) would keep doing the damage anyway. Not recommended.

No owner decision is strictly needed. Option 2 applies HR-6, which is already settled, and both bug rows give the intended order.
Because this is stock, the orchestrator may still want to show the owner the example above.

## 4. Downstream

`calculate_balance` calls only `db.query(...).first()`, with no lock and no write (R6). Reconcile's writes go through
`inventory_ledger_dao.create` + snapshot assignment + `flush`. The service commits (TC contract) and rolls back on any
exception (S4 confirmed nothing written).

## 5. API contract

See `contract.md`. Two value-only changes and no shape change. The frontend stage can be skipped.

## 6. Database

No migration, constraint or index. No check script needed.

## 7. Neighbouring bugs

- Unlocks the reconcile write path for BUG-641, BUG-644, BUG-650, BUG-651, BUG-652, BUG-653 (§3). Of these, only BUG-641 is
  stock-wrong, and it pairs with BUG-664 / BUG-803 (same file, same fix pattern).
- BUG-3043 (float `total_value`): now visible for buckets with history. LSV-GIB-05 moves from failing on BUG-655 to failing on
  BUG-3043, as the pre-check said.
- BUG-3042 (message): only matters once BUG-653 lands.
- BUG-640 / BUG-992: untouched, as the brief says.

## 8. New bugs found

None. The reconcile hazards above are all already logged (BUG-641, BUG-664, BUG-803, BUG-651, BUG-652, BUG-644, BUG-650, BUG-653).

## 9. Future notes

None new. `docs/future/permissions.md` line 255 already records that any active member may reconcile (candidate:
owner / manager / ground-team-manager). This unit makes that right reachable for buckets with history.
