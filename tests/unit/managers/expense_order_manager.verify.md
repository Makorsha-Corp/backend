# Verification — `app/managers/expense_order_manager.py`

> **Verdict:** PASS
> Tests: 355 passed · 84 xfailed (reproduced ✅; all 84 fail with `--runxfail`) · coverage 99% branch (miss: 294 dead, 653->659 unreachable)
> Mutation: 363 mutants · 351 killed · 12 survived → score 100% (after excluding 5 equivalent, 3 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 5 · Re-verify after fix round 2 (scoped)

## Summary
Fix round 2 closed the four findings left open by the previous verify. The four new cases EO-U-48…U-51 (one per remaining R9 detail field) are implemented faithfully, and all four previously surviving mutants on line 31 are now killed. EO-U-06, U-08 and U-29 now assert the returned id and that lines and approvers are unchanged. EO-FN-17 now inserts the excluded rows V4…V8. EO-C-27…C-29 use the section default payload and the full "nothing written" check. Traceability is clean (439 cases, 439 tests), the runs match the notes, and there is no flakiness. Every remaining survivor is equivalent, dead or bug-path. These tests can be trusted.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by | Status |
|---|---|---|---|---|---|---|
| 1 | Dishonest xfail / wrong setup | EO-C-27 | (first verify) sent `cost_center_id=None` and so failed early on the factory-required check | `--runxfail`: `Failed: DID NOT RAISE HTTPException` (the order is created with W2's account, as the case states) | executor | **resolved** |
| 2 | Case conflict + weakened assertion | EO-U-20 | (first verify) approved U3 conflicted with BUG-740; the check was weakened to `result is not None` | cases rev 4: U3 pending; test asserts `result.id == o.id`, `_approvals_reset is False`, U3 pending, 0 events | case designer, executor | **resolved** |
| 3 | Case conflict | EO-U-06, U-08, U-29 | (first verify) `updated_by` was excluded without a recorded basis | cases rev 4 Then says "except `updated_by`" | case designer | **resolved** |
| 4 | Wrong setup | EO-FN-13 | (first verify) Q8, Q9 and Q10 were missing | the test inserts them and asserts `overdue.count == 1` | executor | **resolved** |
| 5 | Missing assertion | EO-U-21 | (first verify) `performed_by` was not asserted | `assert events[0].performed_by == u2.id` | executor | **resolved** |
| 6 | Weakened "nothing written" | C-10…17, C-31, U-05/10/11/13, U-44, UI-05/08, SA-09/10/11, AA-06…09 | (first verify) these checked only part of the state | each checks `ws_counts`, or the order snapshot plus lines, approvers and events | executor | **resolved** |
| 7 | Missing detail assertion | EO-AI-06, RI-04, D-03 | (first verify) only `status_code` was asserted | each asserts `exc.value.detail` | executor | **resolved** |
| 8 | In-memory only | EO-AI-03, SA-07, SA-16, SA-17 | (first verify) these asserted on the returned object | each uses `reread_item` / `reread_approver` | executor | **resolved** |
| 9 | Unrealizable Given | EO-FN-16 / FN-17 | (first verify) the invoice had no `voided` column and nullable amounts were assumed | cases rev 4 restated the Given (gap G11); tests match | case designer | **resolved** |
| 10 | Incomplete verification | mutation run | (first verify) only 56 of 363 mutants were run | second verify ran 363 of 363 | verifier | **resolved** |
| 11 | Missing assertion | EO-U-06 (L2099), EO-U-08 (L2130), EO-U-29 (L2409) | (second verify) no `result.id == o.id`, no lines/approvers check | each test now seeds a pending U3 approver and asserts `result.id == o.id`, `_approvals_reset is False`, `business_fields_unchanged(...)`, `lines_approvers_snap(db, o.id) == la_before`, `events_of(...) == []` | executor | **resolved** |
| 12 | Wrong setup | EO-FN-17 (L3633) | (second verify) only V1, V2, V3 and V9 were inserted | the test now also inserts V4 (paid), V5 (`invoice_status="voided"`), V6 (completed order), V7 (voided order) and V8 (no invoice); the three sample lists are compared with `==` to the exact dicts | executor | **resolved** |
| 13 | Wrong setup + weakened "nothing written" | EO-C-27 (L1938), C-28 (L1953), C-29 (L1965) | (second verify) wrong category, no F1, extra `expense_date`, orders-only count | all three send `expense_category="factory", cost_center_id=f1.id, description="A"` plus the account, and compare `ws_counts(db, w1.id)` before and after. `--runxfail`: C-27 and C-28 fail on `DID NOT RAISE HTTPException`; C-29 fails on `IntegrityError … expense_orders_account_id_fkey`, which is the case's stated "fails today on" | executor | **resolved** |
| 14 | case-missing | `update_expense_order` R9 / L31 (`DETAILS_FIELDS`) | (second verify) no pass case for `account_id`, `expense_category`, `cost_center_id`, `due_date` | cases rev 5 added EO-U-48…U-51; tests L2664–L2726 match their rows; mutants L31:4, :18, :38, :72 are now KILLED | case designer, executor | **resolved** |

No open findings.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 255:52 | `exclude_unset=True` → `False` (update_expense_order) | equivalent | Every `ExpenseOrderUpdate` field defaults to `None`, and `exclude_none=True` still drops them, so `update_dict` is identical | — |
| 2 | 255:71 | `exclude_none=True` → `False` (update_expense_order) | bug-path | Differs only when the caller sends explicit nulls. That behavior is BUG-753 (spec R2), and only xfail cases cover it (U-30, U-45) | — |
| 3 | 292:20 | `skip=0` → `1` in `list_expense_orders` | dead | Method is unreachable (spec Q24; deadcode-staging) | — |
| 4 | 292:36 | `limit=100` → `101` | dead | same | — |
| 5 | 294:8 | `return` → `return None` | dead | same | — |
| 6 | 399:52 | `exclude_unset=True` → `False` (update_item) | equivalent | Every `ExpenseOrderItemUpdate` field defaults to `None` and `exclude_none=True` still drops it | — |
| 7 | 399:71 | `exclude_none=True` → `False` (update_item) | bug-path | Explicit-null handling on items is BUG-753; only xfail UI-12/UI-13 send nulls | — |
| 8 | 473:13 | `len(approvers) > 0` → `>= 0` | equivalent | With 0 approvers the new branch sets `required = len(approvers) = 0`, the same as the else branch | — |
| 9 | 476:23 | `required = 0` → `1` | bug-path | The mutant matches the intended BUG-755 fix (spec approval_summary R4); only xfail AS-06/AM-03 assert it | — |
| 10 | 512:51 | `'User #'` → `''` (add_approver fallback name) | equivalent | Unreachable profile-missing fallback (spec G7: approver/member `user_id` FK CASCADE); no case by design | — |
| 11 | 531:51 | `'User #'` → `''` (remove_approver fallback name) | equivalent | same (spec G7) | — |
| 12 | 556:69 | `'Order is not ready for approval'` → `''` | bug-path | Today this fallback is the BUG-758 output (spec set_approval R4, G10). SA-11 is status-only by design, and xfail SA-12 targets the intended text | — |

Rows 1–12 are carried over from the previous report (lines not re-run in this scoped pass; the fix round changed no test that targets them). The four line-31 survivors of the previous report were re-run and are killed.

## Traceability
Cases 439 · tests 439 · unmatched: none · duplicate IDs: none · marker mismatches: none. 355 `pass` cases are unmarked; all 84 xfails are `xfail(strict=True)` and every reason names its Expect-column BUG IDs. BUG-004, BUG-021, BUG-340 and BUG-362 are in `docs/testing/bugs.md`. BUG-740…BUG-759 are still only in `expense_order_manager.bugs-staging.md`, which is expected in batch mode (merged later) and is not a finding.

Fidelity scope (scoped re-verify): rows added in cases revision 5 (EO-U-48…U-51), tests the notes' latest Revision history entry lists as changed (U-06, U-08, U-29, FN-17, C-27, C-28, C-29), which are also every test named in a previously open finding. All other tests carry over from the earlier verifies.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_expense_order_manager.py -q -p no:cacheprovider --cov=app.managers.expense_order_manager --cov-branch --cov-report=term-missing
  -> 355 passed, 84 xfailed; app\managers\expense_order_manager.py 338 stmts, 1 miss, 114 branches, 1 partial, 99% (294, 653->659)   [matches notes Result line]
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_expense_order_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  -> 84 failed, 355 passed (C-27/C-28: 'DID NOT RAISE HTTPException'; C-29: IntegrityError on expense_orders_account_id_fkey)
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_expense_order_manager.py -q -p no:cacheprovider
  -> 355 passed, 84 xfailed (repeat; no flakiness; previous report mentions none)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/expense_order_manager.py tests/unit/managers/test_expense_order_manager.py --lines 31-31 --timeout 180 --json <scratch>/eo_mut_31.json
  -> Mutants: 5 · killed 5 · timeout 0 · survived 0 · score 100%
     (L31:4 account_id, :18 expense_category, :38 cost_center_id, :56 expense_date, :72 due_date — all KILLED)
  total (carried over, 1-664, with line 31 updated) -> 363 mutants · 351 killed · 12 survived
```

## Note 2026-11-01 (BUG-1193, not a verdict)
Everything above is unchanged and stands for cases revision 5: 439 cases, 355 passed, 84 xfailed. Its PASS does **not** cover EO-D-10…D-19, added in cases revision 6.

This note is from one agent that wrote the spec change, the cases and the tests itself and then ran these checks, which is lighter than an independent round. The new cases were not checked by a separate verifier, the agent had read the source before designing them, and `mutate.py` was not run: it skips xfail tests, and all ten new tests are xfail.

Run on the revision 6 file: 449 cases, 449 tests. 355 passed, 94 xfailed in 3 plain runs and on 3 forced plans, with no XPASS. `--runxfail` 94 failed, 355 passed. Branch coverage 99% (miss: 294, 653->659). Ruff finds nothing in the new block. Details and the scratch check with a stand-in fix are in the notes, Revision history, entry 2026-11-01.

An independent verify of these ten cases is still open.
