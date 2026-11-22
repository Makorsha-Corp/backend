# Verification — `app/managers/ledger_manager.py`

> **Verdict:** PASS
> Tests: 82 passed · 52 xfailed (reproduced ✅, stable over 3 runs) · coverage 98% branch
> Mutation: 175 mutants · 159 killed · 16 survived → score 100% (159/159, after excluding 0 equivalent, 0 dead, 16 bug-path) — carried over, not re-run
> Source commit: e48a092 · Cases revision: 3

Narrow re-verify of the two findings left open by the previous report (#12, #13). Traceability and the reproduce step were done in full. Fidelity covered LED-RMI-14, LED-RINV-08 and every use of `snap_inventory`. Mutation was not re-run: `app/managers/ledger_manager.py` is unchanged and the two test edits only add assertions to tests that already passed, so every earlier result still holds.

## Summary
Both open findings are fixed, and nothing else is open.
LED-RMI-14 now asserts exactly one activity event before reading it.
`snap_inventory` now records `note` and `created_at`, so LED-RINV-08's "unchanged" check covers every `inventory` column except the ones the case expects to change or excludes.
The full file reproduces the notes' Result line on three runs, and all 52 xfail tests still fail under `--runxfail` on the failure their case names.
The 16 surviving mutants all sit on paths only a logged bug reaches, so the passing tests can be trusted.
The notes file was not updated for these two edits; that is noted below and is not a finding.

## Findings
None open.

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 12 | Missing assertion | LED-RMI-14 (test l.1039–1055) | **RESOLVED.** The test now asserts the event count before reading the latest event, matching "1 activity event" in the Then. | l.1052 `assert mae_count(db, m1) == 1`, then l.1053–1055 description and `item_name` | — |
| 13 | Missing assertion | LED-RINV-08 (test l.1637–1657, helper l.406–411) | **RESOLVED.** `snap_inventory` now records 11 columns, including `note` and `created_at`. With `qty`, `avg_price` and `is_deleted` asserted directly, only `id`, `updated_by` and `updated_at` are left out, and the case excludes the last two. | helper tuple l.409–410 vs `app/models/inventory.py` l.32–51; l.1641 and l.1656 compare before and after | — |
| 1 | Flaky test / dishonest xfail | LED-GML-14, GMB-05, PCL-04, GIL-16, GIB-06, GAL-10, IMS-07, TBU-06 | **RESOLVED.** Cases revision 3 proves BUG-640/641 from the recorded SQL. Under `--runxfail`, six of the eight fail on `assert order_by_ends_id_desc(...)` (l.681, 790, 1145, 1402, 2008, 2143). LED-GIB-06 and LED-TBU-06 fail on the `AttributeError` their cases name (BUG-655, BUG-645). | 3 full-file runs, all `82 passed, 52 xfailed`; `--runxfail`: `52 failed, 82 passed` | — |
| 2 | Spec fact wrong | spec Gap log G7 | **RESOLVED.** G8 supersedes G7: tie order today is undefined, and the spec gives the `ORDER BY` emitted today and intended. | spec l.232, l.626–627 | — |
| 3 | Marker mismatch | LED-IMS-07 | **RESOLVED.** Now `xfail(strict=True, reason=BUG_640)`; no `strict=False` is left in the file. | 0 occurrences of `strict=False` | — |
| 4 | Notes do not reproduce | `ledger_manager.notes.md` | **RESOLVED.** Helper names match the file and the Result line reproduces. | notes l.4, l.14–18 | — |
| 5 | Wrong setup + missing assertion | LED-TBU-03/04/05/06 | **RESOLVED.** Each test inserts machine, project and inventory rows and asserts all three lists. | previous report | — |
| 6 | Missing assertion | LED-RMI-06 | **RESOLVED.** `snap_machine_item` compared before and after; it covers every `machine_items` column except `id` and `qty`. | previous report | — |
| 7 | Missing assertion | LED-RMI-01 | **RESOLVED.** Same before/after comparison. | previous report | — |
| 8 | Missing assertion | LED-RINV-08 | **RESOLVED**, and completed by finding 13. | l.1641, 1656 | — |
| 9 | Weakened assertion | LED-RMI-14 | **RESOLVED.** The whole result dict is compared, including `adjustment_created`. | l.1048–1051 | — |
| 10 | Missing assertion | LED-RMI-13 | **RESOLVED.** `assert mae_count(db, m1) == 1` added. | l.1032 | — |
| 11 | Case missing | default `limit=100` of the four list methods | **RESOLVED.** LED-GML-20, PCL-07, GIL-19, GAL-13 added (101 rows, no `limit`, exact list of the 100 newest). Mutants #24, #36, #40, #50 are killed. | previous report's mutation re-run | — |

Not findings:
- **Notes not updated for this round.** `ledger_manager.notes.md` has no Revision history entry for the LED-RMI-14 count assertion or the wider `snap_inventory`. Its description of the helper ("a fixed set of non-mutating columns", l.14) is still true, and the Result line still reproduces.
- `snap_inventory` is used by one test only, LED-RINV-08 (l.1641, l.1656). No other test is affected by the wider snapshot.
- `created_at` in the snapshot cannot make LED-RINV-08 flaky: the column has a server default and no `onupdate`, so a reconcile does not touch it.
- `order_by_ends_id_desc` returns true if *any* matching SELECT has the intended `ORDER BY`, while the Conventions say "every". Each call under test emits exactly one SELECT per ledger table, so the two are the same here.
- Notes l.21 says LED-GIB-06's SQL assertion is "reached first". It is not: the call raises `AttributeError` (BUG-655) inside the recorder block, before either assertion. That is still the failure the case names, and the notes' Self-check describes it correctly.
- BUG-640…BUG-655 are now in `docs/testing/bugs.md` (the batch merge has reached them), as is BUG-341.
- Out of scope, carried over for whoever specs `app/services/ledger_service.py`: `ledger_service.py:361` calls `self.ledger_manager.get_transactions_by_order(...)`, but `LedgerManager` has no such method.

## Surviving mutants
Carried over from the previous two reports without a re-run. The source file is unchanged at e48a092, and the two test edits cannot turn a killed mutant into a survivor or reach any of the lines below.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 22 | 706 | `return result` → `return None` | bug-path | `get_transactions_by_user` raises at l.680 (BUG-645) before reaching l.706; only xfail LED-TBU-* target it | — |
| 53 | 654 | `skip=0` → `1` | bug-path | Same method; unreachable until BUG-645 is fixed | — |
| 54 | 655 | `limit=100` → `101` | bug-path | Same method; unreachable until BUG-645 is fixed | — |
| 112 | 680 | key `'machine'` → `''` | bug-path | Right-hand side raises `AttributeError` (BUG-645) before the assignment | — |
| 113 | 689 | key `'project'` → `''` | bug-path | Unreachable (BUG-645) | — |
| 114 | 698 | key `'inventory'` → `''` | bug-path | Unreachable (BUG-645) | — |
| 25 | 71 | `start_date and end_date` → `or` | bug-path | Differs only when one bound is given. Lone-bound behavior is BUG-341 (`get_machine_ledger` R3), tested only by xfail LED-GML-11/12 | — |
| 41 | 385 | `start_date and end_date` → `or` | bug-path | Same for `get_inventory_ledger` R3 (BUG-341); only xfail LED-GIL-13/14 | — |
| 51 | 621 | `start_date and end_date` → `or` (machine list) | bug-path | Lone-bound / no-bound report is BUG-646; only xfail LED-IMS-04/05/06 | — |
| 52 | 635 | `start_date and end_date` → `or` (inventory list) | bug-path | Same, BUG-646 | — |
| 164 | 629 | `result['machine'] = []` key → `''` | bug-path | The "dates missing → empty list" branch is the BUG-646 short-circuit itself; only xfail LED-IMS-04/05/06 reach it | — |
| 166 | 643 | `result['inventory'] = []` key → `''` | bug-path | Same, BUG-646 | — |
| 141 | 493 | key `'status'` → `''` (inventory no-snapshot dict) | bug-path | Reached today only with ledger qty 0 (LED-RINV-01/03/05), where the intended result is `balanced` (BUG-649), so those passing cases check only the bug-independent keys. The intended `error` dict (R5) needs history and crashes on BUG-655, so only xfail LED-RINV-06 checks it | — |
| 147 | 493 | value `'error'` → `''` | bug-path | Same as #141 | — |
| 146 | 498 | key `'error'` → `''` | bug-path | Same as #141 | — |
| 150 | 498 | message `'Snapshot missing for…'` → `''` | bug-path | Same as #141 | — |

## Traceability
Cases 134 · tests 134 · every case ID appears in exactly one test (name and docstring agree), no duplicates, and no test lacks an ID · unmatched: none.
Marker mismatches: none. All 82 Expect `pass` cases have no xfail marker. All 52 Expect `xfail` cases are `xfail(strict=True)`, and each reason names every BUG ID in the Expect column. Three reasons add BUG-655 through `BUG_655.split(':')[0]` (l.1493, 1738, 1769), which evaluates to "BUG-655".
BUG IDs used: BUG-341 and BUG-640, 641, 643–655. All are in `docs/testing/bugs.md`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_ledger_manager.py -q -p no:cacheprovider --cov=app.managers.ledger_manager --cov-branch --cov-report=term-missing
  app\managers\ledger_manager.py  106 stmts  3 miss  24 branch  0 brpart  98%  missing 689-706
  82 passed, 52 xfailed, 15 warnings

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_ledger_manager.py -q -p no:cacheprovider -rfX   (2 repeats)
  82 passed, 52 xfailed
  82 passed, 52 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_ledger_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  52 failed, 82 passed
  (tie-order cases on `assert order_by_ends_id_desc(...)` at l.681, 790, 1145, 1402, 2008, 2143; inventory-history cases on AttributeError at dao/inventory_ledger.py:157; LED-TBU-* on AttributeError at ledger_manager.py:680)

Traceability: scratch AST script over the cases file and the test file (IDs, markers, strictness, BUG IDs vs bugs.md).

Mutation: not re-run this round (see Surviving mutants).
```
