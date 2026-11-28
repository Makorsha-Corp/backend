# Tester pre-check: dao-inventory_ledger (2026-11-28)

Base: `origin/main` 092776b (unit file, test files and the bug rows equal to the main checkout).
Database: `bf_dao_inventory_ledger_test`. No `app/` edit: a correct fix and four wrong-value
fixes were simulated by a pytest plugin in the session scratchpad that monkeypatches
`InventoryLedgerDAO` at start-up, plus a filter-in-Python stand-in for the `0` filters.

## Verdict

| Bug | Target tests | Verdict |
|---|---|---|
| BUG-655 | 21 strict markers naming BUG-655: 17 single-tagged (8 DAO, 7 manager, 2 service) + 4 dual-tagged | **Go, conditional:** 15 single-tagged and all 4 dual-tagged right; LED-RINV-06 and LED-RINV-12 wrong (see `wrong-tests.md`, marker/setup diff). BUG-655 stays in the unit only if that diff lands on `origin/main` before the batch-5 baseline. |
| BUG-885 | 6 strict (DAO) | **Go:** all right. |

Wrong tests: 2 (both BUG-655), recorded in `docs/bugfix/wrong-tests.md` with a checked diff
(`git apply --check` clean; patched copy re-run: both still xfail today; with the correct fix
RINV-06 flips, RINV-12 stays xfailed on BUG-651/652).

## BUG-655 (`calculate_balance` reads a column that does not exist)

Today every target fails on `AttributeError: 'InventoryLedger' object has no attribute 'value_after'`
at `app/dao/inventory_ledger.py:157`, as each card says (run with `--runxfail`).

**Right, flip with a correct fix** (`(qty_after, qty_after * avg_price_after)`, `NULL` → `0.00`):
- `tests/unit/dao/test_inventory_ledger.py`: LED-BAL-08 (R2, 20 @ 6.00 → 120.00), BAL-09 (R2, `NULL` → 0.00),
  BAL-10 (R2, qty 0), BAL-11 (R4, greatest `performed_at`), BAL-12 (R4/R3, decoys), BAL-14 (R5, deleted factory),
  BAL-15 (R5, removed item), BAL-16 (R6, nothing changes).
- `tests/unit/managers/test_ledger_manager.py`: LED-GIB-03 (50 @ 5.00 → 250.00), GIB-04 (`NULL` → 0.00),
  GIB-05 (decoys), LED-RINV-07 (balanced with history), LED-RINV-16 (second reconcile sees the
  first's adjustment row and is balanced).
- `tests/unit/services/test_ledger_service.py`: LSV-GIB-06 (40 @ 6.50 → 260.00), LSV-RINV-16 (adjusted, committed).

**Right, stay xfailed (name a second bug, marker kept at stage C):** LED-BAL-13 (BUG-641 + 655),
LED-GIB-06 (BUG-641, "and BUG-655"), LED-RINV-13 (BUG-653, "and BUG-655"), LED-RINV-14 (BUG-650,
"and BUG-655"). With the correct fix each still fails on its other bug's line (ORDER BY / `balanced` /
`TypeError`), as their cards say.

**Wrong:**
- **LED-RINV-06**: card Given "RI-hist without S", but the test keeps the setup's live snapshot, so it
  checks the R5 "snapshot missing" error with a snapshot present. With the fix it gets `adjusted`.
  Correction: delete the snapshot first (2 lines).
- **LED-RINV-12**: right checks, but the marker names only BUG-655 while the test also needs
  BUG-651 (R9a/R9b) and BUG-652 (R10 `updated_by`). With the fix it fails on `updated_by`.
  Correction: marker reason names all three.

**Wrong-value check (crash bug):** each shortcut stops the crash but gives a wrong value. Every one
is caught by at least two right tests:

| Simulated fix | Caught by |
|---|---|
| value = `avg_price_after` (no multiply) | BAL-08, 10, 11, 12, 14, 15; GIB-03, 05 |
| value always `0.00` | BAL-08, 11, 12, 14, 15; GIB-03, 05 |
| value = latest `total_cost` | BAL-08, 11, 12, 14, 15; GIB-03, 05 |
| `NULL` price → `None` instead of `0.00` | BAL-09; GIB-04 |
| value as `float` | BAL-08, 09 (`isinstance(..., Decimal)`) |

Picking the wrong entry (oldest, or another bucket's) is caught by BAL-11, BAL-12 and GIB-05. The
correct fix passes all 15 right single-tagged targets and changes no passing test in the three files.

## BUG-885 (`0` treated as "no filter")

`tests/unit/dao/test_inventory_ledger.py`: LED-W-15 (`get_by_workspace` R4a), W-18 (R5a), LED-TT-20, TT-21
(`get_by_transaction_type` R3a), LED-DR-19, DR-20 (`get_by_date_range` R4a). Each puts two entries
in the workspace (one of another factory / item, distinct times) and calls with `0`; today they
return the entries, as the cards say. All right. A correct fix flips all six. A fix that covers
only `factory_id` or only one method leaves the matching `item_id` / other-method tests failing.
A fix that returns `[]` for `0` without filtering gives the same results, which is fine (same
behaviour). Passing tests (R4/R5 with `None` and non-zero ids, R6 AND) guard against breaking the
`None` case. No manager or service test is tagged BUG-885.

## Outside this unit

- **Service BUG-3043 tests depend on BUG-655 without saying so:** `test_lsv_gib_05__bug_3043_a_non_zero_value_stays_the_exact_decimal`
  and `test_lsv_gmb_02__...` (machine side, not affected) are tagged BUG-3043 only. LSV-GIB-05 builds
  inventory history, so today it fails on BUG-655's `AttributeError` before it reaches the float check.
  Harmless now (BUG-655 is fixed first, and with it LSV-GIB-05 fails on `isinstance(1234.5, Decimal)`,
  i.e. on BUG-3043). If BUG-3043 were ever fixed before BUG-655, LSV-GIB-05 would stay failing:
  the BUG-3043 planner should check that BUG-655 is merged.
- **BUG-641 vs this unit:** the tie order of `calculate_balance` (BUG-641) is logged against the manager
  with the machine ledger DAO too (two DAO files, no "fix in X"), so it is not in this unit. LED-BAL-13 and
  LED-GIB-06 keep their markers. Note for the systems engineer: if the fixer shares code between
  `calculate_balance` and `get_latest_entry`, `get_latest_entry` (BUG-664's tests, and the
  `InventoryDAO.sync_snapshot_from_ledger` path) must not change.
- **Item summary:** `ItemSummaryService._recent_activity` calls `get_by_workspace(item_id=...)`; after
  BUG-885 an `item_id` of `0` gives `[]` there instead of the whole workspace's activity. No test pins
  the old behaviour.
- **`inventory_type` truthiness** is not a bug (enum members are always truthy); the brief allows an
  `is not None` switch that must not change results.

---

# Round 2 pre-check: scope widened with BUG-641 / BUG-664 / BUG-803, inventory half (2026-11-28)

Decision (orchestrator, after impact-1.md): latest = `performed_at DESC, id DESC` in
`InventoryLedgerDAO.calculate_balance` and `get_latest_entry`. The machine halves
(`app/dao/machine_item_ledger.py`) stay out. Base still 092776b (`app/`, `tests/`, `alembic/` equal in
main checkout HEAD 181c48a). DB `bf_dao_inventory_ledger_test`. No `app/` edit. The simulated fix is a
scratch pytest plugin that loads the worktree's round-1 file, adds `desc(InventoryLedger.id)` to the
two top-1 queries, and copies the five changed methods onto the real class.

## Targets found (collection-time scan of every xfail reason in `tests/unit`, constants resolved)

14 tests name BUG-641, BUG-664 or BUG-803. All 14 fail today under `--runxfail`, and all 14 still
fail with the round-1 fix alone. Nothing else in `tests/` names them.

| Class | Test | File | Strict | Bugs | With simulated round-2 fix |
|---|---|---|---|---|---|
| (a) | INV-SY-17 | dao/test_inventory.py | strict | 664 | passes |
| (a) | LED-BAL-13 | dao/test_inventory_ledger.py | strict | 641, 655 | passes |
| (a) | LED-LE-06 | dao/test_inventory_ledger.py | strict | 664 | passes |
| (a) | LED-GIB-06 | managers/test_ledger_manager.py | strict | 641, 655 | passes |
| (a) | PRI-P-47 | managers/test_po_return_inventory.py | **non-strict** | 803 | passes (today it fails on this plan) |
| (a), **wrong test** | INVM-SO-18 | managers/test_inventory_movements.py | strict | 664 | fails on `new.qty_before` (0 == 10); see below |
| (a), **wrong test** | INVM-SI-15 | managers/test_inventory_movements.py | strict | 664 | fails on `new.qty_before`; see below |
| (b) | MIL-BAL-11 | dao/test_machine_item_ledger.py | non-strict | 641 | still fails (machine DAO) |
| (b) | MIL-BAL-12 | dao/test_machine_item_ledger.py | strict | 641 | still fails |
| (b) | MIL-LE-09 | dao/test_machine_item_ledger.py | non-strict | 664 | still fails |
| (b) | MIL-LE-10 | dao/test_machine_item_ledger.py | strict | 664 | still fails |
| (b) | INVM-MUC-05 | managers/test_inventory_movements.py | strict | 664 | still fails (`get_machine_unit_cost`, machine ledger) |
| (b) | LED-GMB-05 | managers/test_ledger_manager.py | strict | 641 | still fails (machine balance) |
| (b) | LSV-GMB-08 | services/test_ledger_service.py | strict | 641 | still fails (machine balance pass-through) |

**Counts:** (a) 7, of which 5 are right and 2 are wrong tests. (b) 7. (c) 0: LED-BAL-13 and LED-GIB-06 also
name BUG-655, which is in this unit, so with the round-2 scope they flip. That replaces round 1's
"stay xfailed" for those two.

**Wrong tests (2, BUG-664), recorded in `docs/bugfix/wrong-tests.md`:** INVM-SO-18 and INVM-SI-15 read
"the new ledger row" as `ledger_rows(...)[-1]` (ordered by id ascending), but the tie setup gives
seeded row C an id of nextval + 1,000,000, so `[-1]` is C, not the row the movement wrote. No correct fix
can pass them. The diff picks the row that was not seeded. It passes `git apply --check`. On the patched
copy: today both still fail on the card's sync line (synced from row B); with the simulated fix both
pass; no other test in the file changes. BUG-664 stays in the unit **if** that diff is on `origin/main`
and in `bugfix/dao-inventory_ledger` before stage C. Today's outcome for both tests is unchanged
(xfailed), so the 092776b baseline stays valid. If the diff has not landed, keep both markers and treat
them as expected leftovers (below).

**Shortcut fixes are caught** (same 6 inventory-side files, `--runxfail`, compared with the correct fix):

| Simulated fix | Extra failures |
|---|---|
| `ORDER BY id DESC` only (no `performed_at`) | INV-EN-09/10, INV-SY-01, LED-BAL-11, LED-LE-02/04/07, LED-GIB-03/06, PRI-P-43 |
| `performed_at DESC, id ASC` | INV-SY-17, LED-BAL-13, LED-LE-06, LED-GIB-06, PRI-P-47 |
| tie-break in `get_latest_entry` only | LED-BAL-13, LED-GIB-06 |
| tie-break in `calculate_balance` only | INV-SY-17, LED-LE-06, PRI-P-47 (and SO-18/SI-15 once corrected) |

## Full-suite simulation (whole suite with the simulated round-2 fix, markers on; compared with `docs/bugfix/baseline-092776b.json`)

24,423 tests. Every strict change is a target of this unit: the 21 right BUG-655 / BUG-885 targets, plus
INV-SY-17, LED-LE-06, LED-BAL-13 and LED-GIB-06. Each goes xfailed → strict XPASS. PRI-P-47 goes
xfailed → xpassed. **No passing test changed.** The remaining 37 changes are non-strict physical-order ties
of other bugs (BUG-100, BUG-640 attachment ledger, BUG-1200, BUG-2463 project ledger, ...) that move in
both directions between runs. Flipcheck ignores them.

## How the tester must run the stage-C compare (flipcheck cannot express "part of a bug")

`flipcheck.compare` treats every test whose reason names a `--bugs` id as a target that must be
`passed` afterwards. The only exception is a test that also names a bug **outside** `--bugs` and stays
xfailed. A bug that is only partly fixed (BUG-641, BUG-664) can't be expressed. I emulated stage C on
the simulated run (markers removed on the class (a) tests and the BUG-655/885 targets, kept on class (b))
and ran the real `compare`:

- `--bugs BUG-655,BUG-885` → REJECTED: INV-SY-17, LED-LE-06 and PRI-P-47 count as "xfailed → passed, not a
  target". Wrong option.
- **`--bugs BUG-641,BUG-655,BUG-664,BUG-803,BUG-885` (use this)** → REJECTED, but only with
  "target ... is xfailed after (was xfailed)" for exactly these tests, and nothing else:
  - **Expected leftovers, class (b), 7, the machine halves:** MIL-BAL-11, MIL-BAL-12, MIL-LE-09, MIL-LE-10,
    INVM-MUC-05, LED-GMB-05, LSV-GMB-08. **Keep their markers.** Skill §C.3 would otherwise remove
    them, because their only bug id is "in the unit".
  - INVM-SO-18, INVM-SI-15: only while the BUG-664 wrong-test diff has not landed. Once it has, remove
    their markers and they flip.
  - LED-RINV-06, LED-RINV-12: only while the round-1 BUG-655 wrong-test diff has not landed. As of this
    pre-check it is still "proposed" and not on `origin/main`.
  - Notes, not rejections: LED-RINV-13 (also BUG-653) and LED-RINV-14 (also BUG-650) stay xfailed.
  - Flipped as intended: 26 (21 BUG-655/885 + INV-SY-17, LED-LE-06, LED-BAL-13, LED-GIB-06, PRI-P-47).

**Acceptance rule for the tester:** the unit counts as CLEAN when the compare's rejection list is exactly
the 7 class (b) tests (plus any of the 4 wrong-test ids whose diff has not landed), each with
before == after == `xfailed` (non-strict MIL-BAL-11 / MIL-LE-09 may show `xpassed`, also unchanged in
kind). `flipped_as_intended` must contain all class (a) tests whose markers were removed. Any other
rejection is real. Record the leftovers in `flipcheck.json` and in `pr.md` as "machine halves of
BUG-641 / BUG-664 still open". In `bugs.md` mark BUG-803 Fixed. BUG-641 and BUG-664 get "inventory half
fixed in bugfix/dao-inventory_ledger; machine half open" and are **not** marked Fixed.
(Tooling improvement for the orchestrator: a `--partial BUG-641,BUG-664` option that lets a target stay
xfailed when its test file is outside the unit. Not done here.)

## Outside this unit (round 2)

- The machine-half tests above are the targets of a later `dao-machine_item_ledger` unit (same tie-break,
  `MachineItemLedgerDAO.calculate_balance` / `get_latest_entry`).
- BUG-2463 (project ledger, same tie) is deferred; its non-strict tests move with physical order only.
