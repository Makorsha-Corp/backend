# Verification — `app/managers/inventory_movements.py`

> **Verdict:** PASS
> Tests: 121 passed · 30 xfailed (after the 2026-10-30 note below; the audit below ran at 122 passed · 29 xfailed, all 29 failing under `--runxfail` on the case's "fails today on" assertion) · coverage 100% branch (120 stmts, 34 branches, 0 missed)
> Mutation: 210 mutants · 209 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path). Scoped re-run: L307 only (2 mutants, 1 killed, 1 survived = the known bug-path survivor). The other 208 classifications carry over from the previous full run.
> Source commit: e48a092 · Cases revision: 5 (audit below ran at revision 4; see the 2026-10-30 note)

## Summary
This is a scoped re-verify after the executor's fix round, "Revision 4, finding fix" in the notes. The one open finding is resolved: MO-15, MI-13 and PSO-23 now take `w2` and call `assert_no_events(db, w1, w2)`. That matches the cases file's "No events" convention, which covers W1 and W2. The cases file did not change, and no other tests changed. All runs reproduce the notes' Result line, and nothing is flaky. The only surviving mutant is still the BUG-665 bug-path survivor at L307. These tests can be trusted.

## Findings
None open.

Resolved from earlier rounds:
| # | Kind | Case / line | What was wrong | Resolution |
|---|---|---|---|---|
| 1 (prev. round) | Missing assertion | INVM-MO-15 (line 1797), INVM-MI-13 (line 2093), INVM-PSO-23 (line 2454) | These tests checked "no events" only in W1. They create W2 through `ix`, so the convention also requires a W2 check. | **Resolved.** Each test now takes `w2` and calls `assert_no_events(db, w1, w2)` (lines 1786/1797, 2082/2093, 2443/2454). `assert_no_events` re-reads after `db.expire_all()` and filters on `workspace_id IN (w1, w2)`. |
| Earlier rounds | MO-15 dishonest xfail; BUG-664 tie flakiness; SI-13/MI-13 savepoint; PSI-08 ledger type; incomplete mutation run | — | — | All **resolved** in revision 4. This re-verify confirmed them again: tie cases are stable across reruns, MO-15 fails on `DID NOT RAISE HTTPException`, and the full mutation run is on record. |

Informational, not findings:
- BUG-660…666 are still in `inventory_movements.bugs-staging.md`, not yet in `docs/testing/bugs.md`. This is expected in batch mode, where the register is merged later. Every xfail reason names its BUG ID through the `BUG_660`…`BUG_666` constants.
- SO-19 is retired in cases revision 4 and is correctly absent, both as a cases table row and as a test.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 91 (full run) / 1 (scoped run) | L307 `avg_before if qty_before > 0 else None` | `>` → `>=` | bug-path | The mutant differs only at `qty_before == 0`. There it passes the Decimal `avg_before` instead of `None`. For `qty ≥ 1`, `weighted_avg_price` returns `unit_cost` whenever `old_qty == 0`, whatever `old_avg` is, so the result is identical. A difference shows only on the `add_qty <= 0` branch, which needs `qty < 1`. That input is BUG-665 (intended: `post_stock_in` rejects it first), and only xfail PSI-11 targets it. Once BUG-665 is fixed, this mutant becomes equivalent. | — |

All other mutants (208 killed in the previous full run) carry over unchanged. The fix round changed only assertions in three xfail tests, and the mutation run excludes xfail tests, so no coverage changed.

## Traceability
Full check: cases 151 (122 `pass` · 29 `xfail`; SO-19 retired, not a table row) · tests 151. Each case ID appears in exactly one test docstring. Unmatched: none. Duplicates: none. Tests without a case ID: none. Marker mismatches: none. The 122 `pass` cases have no marker. The 29 xfail cases have `xfail(strict=True, reason=BUG_xxx)`, and each reason contains every BUG ID in the case's Expect column.

## Fidelity review (scoped)
- Cases revision 4 is unchanged since the last verify (file dated 2026-10-01; no new Revision line). No case rows were re-read for change.
- Changed tests (from the notes' "Revision 4, finding fix"): MO-15, MI-13 and PSO-23. Each was re-read against its case row.
  - **MO-15**: setup `MS(m1, ix, 10, 4.00)` and action `item_id=ix, qty=2` match the case. Then: 404 with exact detail, row `qty == 10`, ledger count `== 1`, no events in W1+W2. All asserted with `==`, flush without a savepoint, strict xfail BUG-666.
  - **MI-13**: 404 with exact detail, no `machine_items` row and no ledger row for `ix`, no events in W1+W2. Flush without a savepoint, strict xfail BUG-666.
  - **PSO-23**: machine stock-out of a foreign item. Asserts 404 before the stock check (fails today on `assert 400 == 404`), no `machine_items` row and no ledger row, no events in W1+W2. Strict xfail BUG-666.
- No new mocks, no `try/except`, and no broad `pytest.raises`.

## Commands run
- `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_movements.py -q -p no:cacheprovider --cov=app.managers.inventory_movements --cov-branch --cov-report=term-missing` → `122 passed, 29 xfailed, 15 warnings in 13.42s` · `app\managers\inventory_movements.py 120 0 34 0 100%`. This matches the notes' Result line.
- `... --runxfail -rf --tb=line` → `29 failed, 122 passed in 4.14s`. Each failure is on its designed assertion. The three changed tests fail as follows:
  - MO-15: `DID NOT RAISE HTTPException`
  - MI-13: `DID NOT RAISE HTTPException`
  - PSO-23: `assert 400 == 404`

  The others are the same as the previous report: lock `assert False`, ForeignKeyViolation for SO-16/SI-14/MO-16/MI-14, tie values `4.50 == 5.00` / `22 == 20` / `4.00 == 10.00`, and `Unsupported ...type: project`. None fails on setup.
- Repeat runs of the full file, ×2 → `122 passed, 29 xfailed` each time. No flakiness.
- Traceability: AST/regex script over the cases table, test docstrings and xfail decorators → `cases 151 tests 151 missing [] dup [] extra [] notest [] mism []` · `pass 122 xfail 29`.
- `.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/inventory_movements.py tests/unit/managers/test_inventory_movements.py --lines 307-307 --timeout 180 --json <scratchpad>/invmov_mut.json` → `Mutants: 2 · killed 1 · timeout 0 · survived 1`. Survivor: `L307:61 cmp Gt -> GtE` (bug-path, see above). `L307:74 const 0 -> 1` was killed.

## Note, 2026-10-30 — BUG-1040, not a new verify round
The owner ruled that all money rounds half away from zero (HR-15). Spec R2 split into R2 and R2a; cases revision 5.
- INVM-WAP-04 now expects `0.03` as a strict xfail BUG-1040. Under `--runxfail` it fails on `assert Decimal('0.02') == Decimal('0.03')`, the card's "fails today on".
- INVM-WAP-05 stays a plain pass at `0.04`, because half up and half even agree on 0.035. Only its wording and test name changed.
- Counts: cases 151 (121 `pass` · 30 `xfail`) · tests 151. Coverage 100% branch (120 stmts, 34 branches, 0 missed).
- Mutation was not re-run. WAP-04 is now an xfail and the mutation run excludes xfail tests, so the mutation figures above predate this change.
- Commands: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_movements.py -q -p no:cacheprovider --tb=no --cov=app.managers.inventory_movements --cov-branch --cov-report=term-missing` → `121 passed, 30 xfailed`.
