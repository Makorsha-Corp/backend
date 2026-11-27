# Verification — `app/managers/po_receive_inventory.py`

> **Verdict:** PASS
> Tests: 119 passed · 23 xfailed (reproduced ✅) · coverage 98% branch (lines 117, 239: unreachable per spec branch map)
> Mutation: 179 mutants · 166 killed · 13 survived → score 100% (166/166, after excluding 9 equivalent, 0 dead, 4 bug-path)
> Source commit: e48a092 (app/ unchanged since the previous verify) · Cases revision: 5
> Verify pass: 2 (scoped re-verify after the fix round; previous pass: NEEDS WORK, 10 findings)

## Summary
The suite can be trusted. The fix round resolved all 10 findings from the previous pass. The case designer added five ±1 boundary cases (PRI-D-05, P-34, P-35, RE-21, RE-22). These kill all seven `0 -> 1` boundary mutants that survived before. The executor completed the under-asserted "nothing written", "no activity event" and "row unchanged" Then clauses, and fixed the PRI-V-10 setup so the parent return keeps status `completed`. The runs match the notes exactly (119 passed · 23 xfailed · 98% branch) and are stable on repeat. Every xfail still fails on its named assertion. The only surviving mutants are the 9 equivalent and 4 bug-path mutants already classified in pass 1.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by | Status |
|---|---|---|---|---|---|---|
| 1 | case-missing | `_delta_to_int` R1/R2, `_post_event_item_delta` R3/R6/R8, `_reverse_event_item_posting` R4/R6/R7 | No case used a delta of ±1. | Cases rev 5 adds PRI-D-05 (a/b), P-34, P-35, RE-21, RE-22. All 7 previous survivors (#77, #83, #85, #91, #96, #98, #103) are now KILLED (see Commands run). | case designer | **resolved** |
| 2 | Wrong setup | PRI-V-10 | `pending_return()` set the parent status to `pending`, which gave a second reason for not netting. | `pending_return()` (test L380–385) now calls `mk_return_item(w, po_line, qty)` with the default `status="completed"`. This matches the clarified Conventions (cases L42). | executor | **resolved** |
| 3 | Missing assertion | PRI-P-16 | "Nothing written" was only partly checked. | Now uses `snapshot_ids` + `assert_nothing_written`, keeps the source-row count == 1, and re-reads stock `qty 5`, `avg_price 26.00`, and `updated_by` unchanged. | executor | **resolved** |
| 4 | Missing assertion | PRI-P-22 | "Nothing written" was only partly checked. | Now uses `assert_nothing_written(db, before)` plus the check that no stock row exists. | executor | **resolved** |
| 5 | Missing assertion | PRI-P-27, PRI-P-28 | "Nothing written" was only partly checked. | Both now use `assert_nothing_written(db, before)` plus the check that no stock row exists. | executor | **resolved** |
| 6 | Missing assertion | PRI-P-01 | The test did not check for an activity event. | Now asserts `new_rows(db, MachineActivityEvent, 0) == []`. | executor | **resolved** |
| 7 | Missing / weakened assertion | PRI-P-24 | The test used `pytest.raises(Exception)` and had no ledger snapshot. | Now uses `pytest.raises(InvalidOperation)`, `assert_nothing_written`, and a stock re-read (`qty 10`, `avg_price 20.00`). | executor | **resolved** |
| 8 | Weakened assertion | PRI-P-18 | The test only checked that the W2 row still existed. | Now snapshots 10 columns before the call and compares them after with `assert_cols`. | executor | **resolved** |
| 9 | Missing assertion | PRI-PR-02 | The test did not check that only the expected row was written. | Now asserts no row for `e1a.id`, exactly 1 new `inventory_ledger` row (source `e1b.id`), and no new machine-ledger or activity rows. | executor | **resolved** |
| 10 | Missing assertion | PRI-RE-19 (xfail) | The test did not check for an activity event. | Now asserts `new_activity(db, w.m1, 0) == []`. Under `--runxfail` it still fails on the case's assertion (BUG-683). | executor | **resolved** |

Open findings: **none.**

Observation (not routed): PRI-P-34, P-35, RE-21 and RE-22 check "exactly 1 new ledger row, in `inventory_ledger`" with `one(rows_for_source(...))` and the full column set. They do not use an id snapshot across both ledgers (P-34 does check `machine_item_ledger` is empty). This is the same pattern pass 1 accepted for PRI-P-09 and PRI-RE-01..04. With a storage destination, `factory_id`, `transaction_type` and the stock re-read pin down the row exactly, so it is not a finding.

## Surviving mutants
Pass 1 numbering is kept. This pass re-ran the lines of every previous survivor (34, 112–122, 230–244, 335). The fix round changed no app code and did not change line coverage (still 98%, missing 117 and 239). So the classifications of all other mutants carry over from pass 1 (all KILLED).

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 34 | 34 `if qty <= 0:` | `<=` → `<` | equivalent | `qty = int(abs(delta)) >= 0`. When qty is 0, both branches return 0. | — |
| 47 | 116 `if qty <= 0:` | `<=` → `<` | equivalent | Unreachable branch. Past L112 the delta is non-zero and whole, so qty ≥ 1. | — |
| 48 | 117 `return False` | `return None` | equivalent | Same unreachable branch as #47. | — |
| 86 | 117 `return False` | `False → True` | equivalent | Same unreachable branch as #47. | — |
| 49 | 122 `if delta > 0:` | `>` → `>=` | equivalent | `delta == 0` already returned at L112. | — |
| 61 | 238 `if qty <= 0:` | `<=` → `<` | equivalent | Unreachable (as #47). | — |
| 62 | 239 `return False` | `return None` | equivalent | Same unreachable branch as #61. | — |
| 99 | 239 `return False` | `False → True` | equivalent | Same unreachable branch as #61. | — |
| 63 | 244 `if delta > 0:` | `>` → `>=` | equivalent | `delta == 0` already returned at L234. | — |
| 58 | 230 `return False` | `return None` | bug-path | BUG-683 behavior (`_reverse_event_item_posting` R3). Only xfail PRI-RE-20 targets it. | — |
| 95 | 230 `return False` | `False → True` | bug-path | Same as #58. | — |
| 70 | 335 `return False` | `return None` | bug-path | BUG-683 (`_reverse_legacy_line_posting` R3). Only xfail PRI-RL-15 targets it. | — |
| 108 | 335 `return False` | `False → True` | bug-path | Same as #70. | — |

These pass 1 survivors are now **KILLED**: #77 (L34 `0→1`), #83 (L112 `0→1`), #85 (L116 `0→1`), #91 (L122 `0→1`), #96 (L234 `0→1`), #98 (L238 `0→1`), #103 (L244 `0→1`).

## Traceability
- Cases: 120 (115 + 5 new in rev 5) · test functions: 122 · test items: 142 (119 pass + 23 xfail).
- Unmatched: none. Every case ID maps to a test and no test lacks a case ID. PRI-D-05 is parametrized with ids `PRI-D-05a`/`PRI-D-05b`. RL-06 and RL-12 are still split into two functions each, which was accepted in pass 1.
- Marker mismatches: none. The 5 new cases are `pass` and carry no marker. The xfail set is unchanged: 19 xfail cases, 23 items, all `xfail(strict=True, reason=BUG_NNN)`.
- BUG IDs: BUG-680 … BUG-684 are still only in `po_receive_inventory.bugs-staging.md`. They are waiting for the batch register merge. This is not routed as a finding.
- Mocks: unchanged. There are only the three listed race simulations, and the new tests patch nothing.
- `--runxfail`: 23 failed. These are exactly the xfail items: P-29, P-32, P-30, P-31, RE-17, RE-18, RE-19, RE-20, RL-13, RL-14, RL-15, V-11, V-12, V-13, V-14, V-15, V-18, IDX-01a/b/c and IDX-02a/b/c. 119 passed.

## Fidelity (scoped)
I re-read every case changed in cases rev 5 and every test changed in notes revision 5 against the Given / When / Then columns:
- **PRI-D-05a/b**: `_delta_to_int(±1, line_number=7)` returns `1`, and `type(result) is int`. ✅
- **PRI-P-34**: Given `stock 10 @ 20.00` and `+1`. The test asserts the full column set (`purchase_order`, qty 1, unit/total 26.00, 10→11, avg 20.00→20.55, source, `performed_by`), re-reads stock 11 / 20.55 / U1, and checks there is no machine-ledger row. ✅
- **PRI-P-35**: E2 at T3 with `−1`. The test asserts `inventory_adjustment`, qty 1, 20.00/20.00, 10→9, avg unchanged, the exact correction note and `performed_by`, and re-reads stock 9 / 20.00 / U1. ✅
- **PRI-RE-21**: posted `+1` and stock 11. The test asserts the reversal row (`inventory_adjustment`, 11→10, the exact void note, source `..._reversal`) and re-reads stock. ✅
- **PRI-RE-22**: posted `−1` and stock 9. The test asserts unit/total 26.00, 9→10, avg 20.00→20.60, and re-reads stock 10 / 20.60 / U1. ✅
- **PRI-V-10, P-01, P-16, P-18, P-22, P-24, P-27, P-28, PR-02, RE-19**: see findings 2–10 above. Each one now covers its Then clause fully. No case expectation changed, and no try/except or broad raises were added.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_receive_inventory.py -q -p no:cacheprovider --cov=app.managers.po_receive_inventory --cov-branch --cov-report=term-missing
  app\managers\po_receive_inventory.py  113 stmts  2 miss  52 branch  2 brpart  98%  Missing: 117, 239
  119 passed, 23 xfailed, 15 warnings in 13.12s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_receive_inventory.py -q -p no:cacheprovider --runxfail -rf
  23 failed, 119 passed in 7.29s   (the 23 failures are exactly the xfail items)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_receive_inventory.py -q -p no:cacheprovider   (repeat, flakiness)
  119 passed, 23 xfailed in 6.89s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/po_receive_inventory.py tests/unit/managers/test_po_receive_inventory.py --lines 34-34 --timeout 180 --json %TEMP%/povr2/mut_34-34.json
  Mutants: 3 · killed 2 · survived 1 (L34 LtE->Lt = #34 equivalent; L34 0->1 = #77 now KILLED)
... --lines 112-122
  Mutants: 17 · killed 13 · survived 4 (L116 LtE->Lt, L117 return None, L117 False->True, L122 Gt->GtE = #47/#48/#86/#49 equivalent; #83/#85/#91 now KILLED)
... --lines 230-244
  Mutants: 18 · killed 12 · survived 6 (L230 x2 = #58/#95 bug-path; L238 LtE->Lt, L239 x2, L244 Gt->GtE = #61/#62/#99/#63 equivalent; #96/#98/#103 now KILLED)
... --lines 335-335
  Mutants: 2 · killed 0 · survived 2 (#70/#108 bug-path)

Scoped run: 40 mutants · 27 killed · 13 survived (all classified equivalent/bug-path).
Full-module total (other 139 mutants carried over from pass 1, all KILLED): 179 · 166 killed · 13 survived.
```
These results match the notes' Result line (119 passed · 23 xfailed · 98% branch).
