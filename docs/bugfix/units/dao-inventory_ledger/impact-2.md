# Impact review, round 2: dao-inventory_ledger (2026-11-28)

Scope was widened per impact-1 option 2 (brief §7, feedback-1.md). The unit now covers BUG-655, BUG-885, and the inventory halves
of BUG-641, BUG-664 and BUG-803. Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-inventory_ledger diff`
(uncommitted), file `app/dao/inventory_ledger.py` only.

**Verdict: APPROVE.**

## 1. The round-2 change

- `calculate_balance` and `get_latest_entry`: `ORDER BY performed_at DESC, id DESC` (ORM columns). The four bucket filters
  and the workspace filter are unchanged (HR-16). Signatures and return values are unchanged. Each query has a one-line comment.
- `performed_at` stays the first key, so an older entry never wins on a higher id (brief §7.2).
- The round-1 changes (BUG-655 value, BUG-885 `is not None`) are untouched. List methods (BUG-640), machine and project DAOs,
  indexes and migrations are untouched. No scope creep, no shortcut.
- Cost: the extra key only orders rows already filtered to one bucket. No index is needed.

## 2. Throwaway check through the real callers

Script: scratchpad `se-dao-inventory_ledger/probe3.py <code root>`, against `bf_dao_inventory_ledger_test`, in a rolled-back
transaction. I ran the same script on the base code (main checkout `app/`) and on the worktree. A "later save" is simulated
by moving all earlier rows back one hour; they still tie with each other. Real callers used:
`post_purchase_return_inventory`, `post_transfer_order_inventory`, `_storage_in` / `_storage_out` (through
`ensure_for_factory_item_type` → `sync_snapshot_from_ledger`), and `LedgerManager.reconcile_inventory` / `get_inventory_balance`.

| Scenario | Base code (today) | Worktree (fix) |
|---|---|---|
| A. One save: in 50 @ ৳5.00, out 20. Then reconcile. Then a later save: out 5 | balance and reconcile crash; later out 5 leaves **45** (stale 50 − 5) | balance (30, ৳150.00); reconcile `balanced` 30/30, no write; later out leaves **25**; reconcile `balanced` |
| B. Purchase return, 3 lines × 3 of one item, stock 10 @ ৳4.00 from an earlier save | stock **4** (want 1); a later out of 1 leaves **6** | stock **1**; reconcile `balanced`; later out of 1 leaves **0** |
| C. Transfer F1 → F2, 3 lines × 5 of one item, F1 had 20 @ ৳5.00 | F1 **10** (want 5), F2 **10** (want 15); a later out of 2 from F2 leaves **3** | F1 **5**, F2 **15** @ ৳5.00; both reconcile `balanced`; later out of 2 leaves **13** |
| D. Two receipts in one save: 10 @ ৳5.00 + 10 @ ৳7.00 | stock 20 @ ৳6.00, but a later out of 5 re-syncs from the first row: **5 @ ৳5.00** (want 15 @ ৳6.00) | 20 @ ৳6.00, balance ৳120.00, reconcile `balanced`; later out leaves **15 @ ৳6.00** |
| E. Real drift: ledger 30, stock row edited to 25 | reconcile crashes | `adjusted` 30/25 → stock 30 @ ৳5.00; second reconcile `balanced` |

**Reconcile no longer writes wrong stock for ordinary data.** In every multi-movement save (A–D) it reports `balanced` and writes
nothing. It corrects only real drift (E). What is left on the reconcile write path is history and audit only, with no wrong stock:
BUG-651 (unsigned quantity, chain break in the adjustment row), BUG-652 (`updated_by`), BUG-644 (concurrent duplicate
row). BUG-650 is a loud 500 with no write, and BUG-653 makes no write (impact-1 §3).

The base-code column shows that the fix also stops today's **automatic** stock corruption on ordinary flows (purchase
returns, transfers with repeated items, mixed-price receipts, in + out in one save). That is a real stock-value change for users:
balances that were silently wrong become right from the next movement on. Existing rows that are already wrong are not repaired.
That needs a data repair, which is not part of this unit and is noted for the orchestrator below.

## 3. Did anything rely on the old tie order?

- `get_latest_entry` callers: `InventoryDAO.sync_snapshot_from_ledger`, reached from `ensure_for_factory_item_type` (3 paths). That
  function is called by `_storage_in`, `_storage_out` and `production_batch_manager` (damaged bucket, production deferred, benefits the same way),
  and by `LedgerManager.reconcile_inventory` (average price). `calculate_balance` callers: `get_inventory_balance` and `reconcile_inventory`. All of them want "the
  row written last". None depended on the plan-dependent pick.
- No other code orders `inventory_ledger` rows to find a "latest" row. `po_receive_inventory.py:313` looks up one row by
  `(source_type, source_id)` with `.first()`, which is unique per source and not affected. The list methods are unchanged (BUG-640).
- The machine side (`MachineItemLedgerDAO`, `inventory_movements.py:196`) is untouched. Its halves of BUG-641 and BUG-664 stay open, as
  planned.
- Tests that passed by chance through physical order now get a fixed order. The flip check will show any test whose
  expectation was the stale pick. The tester's round-2 pre-check already lists the expected leftovers: 7 machine-half tests and
  LED-RINV-06/12, INVM-SO-18/SI-15.

## 4. API contract

No shape change. The value changes are in `contract.md` (round-2 section). The frontend stage is skipped.

## 5. Database

No migration, constraint or index.

**For the orchestrator / owner (not blocking):** stock rows already corrupted in production by BUG-664 / BUG-803 stay wrong.
The ledger's own `qty_after` chain also carries the error forward, because each later row started from the stale base. A one-off
read-only check, comparing each bucket's chain for a row whose `qty_before` ≠ the previous row's `qty_after`, could size this. Any repair
is an owner decision (§6 of pipeline.md). This is not part of this unit.

## 6. Neighbouring bugs

- Fixes the inventory halves of BUG-641, BUG-664 and BUG-803. Machine halves remain open (BUG-641, BUG-664), as does BUG-2463 (project, deferred).
- BUG-3043 (float `total_value`) stays and is now visible. BUG-640 and BUG-992 are untouched.

## 7. New bugs found

None.
