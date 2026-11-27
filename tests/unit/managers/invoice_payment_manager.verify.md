# Verification — `app/managers/invoice_payment_manager.py`

> **Verdict:** PASS
> Tests: 95 passed · 23 xfailed (reproduced ✅) · coverage 94% branch (138 stmts, 7 missed; 52 branches, 3 partial)
> Mutation: 179 mutants · 140 killed · 39 survived → score 100% (140/140, after excluding 1 equivalent, 6 dead, 32 bug-path)
> Source commit: e48a092 · Cases revision: 5

## Summary
This is a scoped re-verify after fix round 2 (cases revision 5, notes revision 5b). The tests can be trusted. Traceability is clean: 118 cases map 1:1 to 118 tests, and every marker matches. The runs reproduce the notes (95 passed, 23 xfailed) and are stable across the repeat. The same 23 xfail tests fail under `--runxfail`.

Finding 5, the only finding open in the previous report, is resolved: VP-09, VP-10, VP-11, DP-01, DP-02 and DP-05 now assert the N0 parts they were missing. No finding is open. Every surviving mutant is equivalent, dead code, or on the BUG-609 path, and the re-run of those lines gave the same result as before. Nothing has to change.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `void_payment` R7 / L412 | **Resolved** (fix round 1). Cases rev 5 added VP-25 (remaining active total 0.01 → `partial`), and the test implements it faithfully. | L412 re-run this round: 3/3 killed (including `0 → 1`) | — |
| 2 | changed expectation / wrong setup | SY-01..SY-20 | **Resolved** (fix round 1). Every `_sync_linked_order` call passes `user_id=u1.id`. SY-07, SY-08 and SY-11 assert `performed_by == u1.id`. | Previous report | — |
| 3 | missing assertion (N0 partial) | CP-06..VP-11 list from the first report | **Resolved.** Fix round 1 closed most of it. The rest was tracked as Finding 5, which is now resolved. | See Finding 5 | — |
| 4 | missing assertion | SY-03, SY-04, SY-06, SY-09, SY-10, SY-13, SY-18 | **Resolved** (fix round 1). Each asserts both `po_events(db) == []` and `so_events(db) == []`, and re-reads PO1 where relevant. | Previous report | — |
| 5 | missing assertion (N0 residual) | VP-09, VP-10, VP-11, DP-01, DP-02, DP-05 | **Resolved** (notes revision 5b). **VP-09** now snapshots PA and PB before the call and asserts both unchanged after the re-read, as well as PW, I1 and I2. **VP-10** asserts the full `pay_snapshot` of PA and of active PB, and keeps the explicit `voided_at == T0`, `voided_by == u2.id` and `void_note == "Duplicate entry"` checks. **VP-11** asserts the full `pay_snapshot(PI)`. **DP-01, DP-02 and DP-05** assert `so_events(db) == []` after `po_events(db) == []`. No assertion was removed or weakened. | Test file L1783–1807 (VP-09), L1810–1832 (VP-10), L1835–1851 (VP-11), L1564, L1592, L1657 (DP) | — |

No finding is open.

## Surviving mutants
All 39 survivors were re-run this round on their own lines (203, 231–237, 309–367). The surviving set is identical to the previous report. Classifications are unchanged. The other 137 mutants' results are carried over from the first full run (179 mutants); L412 was re-run and is still 3/3 killed.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 10 | 231 | negate `if not payment` | dead | `get_payment` is dead code (spec Q6 "remove"; Not specified). | — |
| 11 | 237 | `return payment` → `return None` | dead | `get_payment`. | — |
| 41 | 231 | drop `not` | dead | `get_payment`. | — |
| 42 | 232 | `raise` → `pass` | dead | `get_payment`. | — |
| 152 | 234 | `'Payment with ID '` → `''` | dead | `get_payment`. | — |
| 153 | 234 | `' not found'` → `''` | dead | `get_payment`. | — |
| 15 | 309 | negate `if not invoice` | bug-path | `delete_payment` after R1. Today's hard-delete body is replaced by BUG-609 (R2: always 400). Only the xfail DP-03..05 reach it, and they are excluded from the run. | — |
| 49 | 309 | drop `not` | bug-path | Same (BUG-609). | — |
| 50 | 310 | `raise` → `pass` | bug-path | Same (BUG-609). | — |
| 158 | 312 | `'Invoice with ID '` → `''` | bug-path | Same (BUG-609). | — |
| 159 | 312 | `' not found'` → `''` | bug-path | Same (BUG-609). | — |
| 98 | 317 | `'payment_amount'` → `''` | bug-path | Delete audit snapshot (BUG-609). | — |
| 99 | 317 | `'payment_date'` → `''` | bug-path | Same (BUG-609). | — |
| 100 | 317 | `'payment_method'` → `''` | bug-path | Same (BUG-609). | — |
| 16 | 329 | negate `if total_paid >= …` | bug-path | Delete recompute (BUG-609). | — |
| 51 | 329 | `>=` → `>` | bug-path | Same (BUG-609). | — |
| 75 | 330 | `'paid'` → `''` | bug-path | Same (BUG-609). | — |
| 52 | 331 | negate `elif total_paid > 0` | bug-path | Same (BUG-609). | — |
| 76 | 331 | `>` → `>=` | bug-path | Same (BUG-609). | — |
| 101 | 331 | `0` → `1` | bug-path | Same (BUG-609). | — |
| 102 | 332 | `'partial'` → `''` | bug-path | Same (BUG-609). | — |
| 103 | 334 | `'unpaid'` → `''` | bug-path | Same (BUG-609). | — |
| 104 | 343 | `'payment'` → `''` | bug-path | Delete audit row (BUG-609). | — |
| 105 | 345 | `'deleted'` → `''` | bug-path | Same (BUG-609). | — |
| 106 | 347 | `'invoice'` → `''` | bug-path | Same (BUG-609). | — |
| 125 | 350 | `'Payment of $'` → `''` | bug-path | Same (BUG-609). | — |
| 126 | 350 | `' deleted from invoic…'` → `''` | bug-path | Same (BUG-609). | — |
| 17 | 353 | negate status-changed `if` | bug-path | Second delete audit row (BUG-609). | — |
| 53 | 353 | `!=` → `==` | bug-path | Same (BUG-609). | — |
| 127 | 357 | `'invoice'` → `''` | bug-path | Same (BUG-609). | — |
| 128 | 359 | `'status_changed'` → `''` | bug-path | Same (BUG-609). | — |
| 160 | 361 | `'payment_status'` → `''` | bug-path | Same (BUG-609). | — |
| 172 | 361 | `'before'` → `''` | bug-path | Same (BUG-609). | — |
| 173 | 361 | `'after'` → `''` | bug-path | Same (BUG-609). | — |
| 161 | 362 | description prefix → `''` | bug-path | Same (BUG-609). | — |
| 162 | 362 | `' to '` → `''` | bug-path | Same (BUG-609). | — |
| 163 | 362 | `' after payment delet…'` → `''` | bug-path | Same (BUG-609). | — |
| 18 | 367 | `return payment` → `return None` | bug-path | Today's delete return value. Spec Returns [BUG-609]: never returns normally. | — |
| 96 | 203 | `exclude_unset=True` → `False` | equivalent | `exclude_none=True` is also set on the same call, and every `InvoicePaymentUpdate` field defaults to `None` (`app/schemas/invoice_payment.py` L29–37). An unset field dumps as `None` and is dropped either way, so the dump is identical for every input. (The line becomes meaningful once BUG-608 removes `exclude_none`. UP-12, UP-13 and UP-17 then cover it.) The sibling mutant on `exclude_none` is killed. | — |
| ~~107~~ | 412 | `total_paid > 0` → `total_paid > 1` | **killed** (was case-missing) | Killed by VP-25. | — |

## Traceability
cases 118 · tests 118 · unmatched: none · duplicate IDs: none · tests without a case ID: none. Each test name `test_ipm_<xx>_<nn>` and docstring `IPM-XX-NN` agree (checked by an AST script).
Marker mismatches: none. All 95 `pass` cases have no xfail marker. All 23 `xfail BUG-NNN` cases have `xfail(strict=True, reason=BUG_NNN)`, and each reason constant's text names every listed BUG ID.
The BUG IDs used (BUG-600, 601, 603–609, 611) are still not in `docs/testing/bugs.md`. All of them exist in `tests/unit/managers/invoice_payment_manager.bugs-staging.md` (batch run, merged later). That file is accepted as the bug register for this check (best-practice default, delegated by reviewer), so this is not a finding.

Fidelity (scoped): the cases file is still at revision 5, so no case row changed since the last verify. I re-read the six tests that notes revision 5b changed, which are also the six named in the open Finding 5: VP-09, VP-10, VP-11, DP-01, DP-02, DP-05. Each matches its case's Given / When / Then and now covers the N0 parts that apply to its setup. A file-wide scan found no `try/except`, no `pytest.raises(Exception)`, and no patch other than the `app.utils.time.datetime` freeze that the spec lists. The other tests were unchanged and were verified in the previous reports.
xfail honesty (`--runxfail -rf`): the failed set is exactly the 23 xfail cases, the same set as in the previous report. DP-05 was the only xfail test touched in round 5b; the added `so_events` assertion sits after the `pytest.raises` block, which is still where it fails today.

Observation, not a finding: VP-09, VP-10 and VP-11 pass `void_note="x"` where the default call uses `"Cheque bounced"`. This was the same in the earlier rounds. All three raise before the note is read, so the value cannot affect the result.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_invoice_payment_manager.py -q -p no:cacheprovider --cov=app.managers.invoice_payment_manager --cov-branch --cov-report=term-missing
  app\managers\invoice_payment_manager.py  138  7  52  3  94%  227-237, 310, 330, 332
  95 passed, 23 xfailed, 20 warnings in 10.02s           (matches notes Result line)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_invoice_payment_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  23 failed, 95 passed, 5 warnings in 4.55s              (failed set == the 23 xfail cases)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_invoice_payment_manager.py -q -p no:cacheprovider   (repeat)
  95 passed, 23 xfailed, 5 warnings in 5.26s             (no flakiness; previous report mentions none)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/invoice_payment_manager.py tests/unit/managers/test_invoice_payment_manager.py --lines <range> --timeout 180 --json <scratchpad>/ipm_mut_<range>.json
  --lines 203-203   Mutants: 2 · killed 1 · survived 1    (survivor: L203:60 exclude_unset True -> False, equivalent)
  --lines 231-237   Mutants: 6 · killed 0 · survived 6    (all in dead get_payment)
  --lines 309-367   Mutants: 32 · killed 0 · survived 32  (all on the BUG-609 delete path)
  --lines 412-412   Mutants: 3 · killed 3 · survived 0
  (All other results carried over from the first full run: 179 mutants, 140 killed, 39 survived.)
```
