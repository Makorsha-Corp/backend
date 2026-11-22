# Verification — `app/managers/sales_order_return_manager.py`

> **Verdict:** PASS
> Tests: 106 passed · 42 xfailed (reproduced ✅) · coverage 100% branch (47 statements, 12 branches)
> Mutation: 41 mutants · 41 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 34 breaking variants · 34 killed; 3 intended-fix variants · all pass tests still pass
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Every one of the 148 cards has exactly one test, the markers match the Expect lines, and every Then line has its assertion with the card's exact value. All 42 xfail tests fail on the line the card's "Fails today on" names (8 of them fail at the When call with the expected HTTPException; G-10..G-12 fail with `TypeError` on `for_update`). Three runs gave the same result. All 41 mutants of the module are killed. mutate.py cannot reach `SalesOrderItem.quantity_available_to_return`, the model property where BUG-2760 and BUG-2796 live, so I tested it with hand variants: all 34 breaking variants were killed. The intended fixes (running total, price range, available = delivered − this workspace's pending) keep all 106 pass tests green. No new bug and nothing to route.

## Findings
None.

## Surviving mutants
None. All 41 were killed: `return` → `None` on every callable, if-negation in `get_return`, `sync_return_paid` and `validate_and_build_items`, the comparisons on lines 49, 55, 63, 77, 93, 97, 98, the `and`/`or` on 77 and 97, the `True`/`False` constants, and every literal in the messages.

## Hand variants (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprodv\so\so_variants.py`, my own plugin, `-p so_variants -m "not xfail"`)
| Variant | Area | Result | Killed by |
|---|---|---|---|
| pending reserved twice (`delivered − returned − 2×pending`) | returnable qty | killed | V-07, V-08, V-10, V-11, V-25, V-43, V-48 |
| pending ignored | returnable qty | killed | V-08, V-11, V-41, V-42 |
| no `max(0, …)` floor | returnable qty | killed | V-41, V-42 |
| refunded also subtracted | returnable qty (OQ-38) | killed | V-13 |
| ordered instead of delivered as base | returnable qty | killed | V-06, V-49 |
| repeated line: keep only the last | repeated line | killed | V-22, V-25 |
| available printed `quantize(0.01)` (`0.00` for `0`) | decimal precision | killed | V-41, V-42 |
| available printed `normalize()` (`10` for `10.00`) | decimal precision | killed | 12 tests (V-04, V-05, V-06, V-08 …) |
| quantity returned as `float` | decimal precision | killed | V-38 |
| price sent rounded to whole units | decimal precision | killed | Q45-05 |
| price check refuses 0 (`<= 0`) | price bound 0 | killed | Q45-02 |
| price check refuses the line price (`>=`) | price bound = line price | killed | Q45-06 |
| price checked before quantity | check order R6a | killed | Q45-09 |
| `if line.unit_price` (truthy) instead of `is not None` | unpriced vs 0 | killed | Q45-02 |
| sent price ignored, line's always used | price | killed | Q45-02, Q45-05 |
| description before catalog name | item name | killed | V-47, V-60 |
| order lines read without the workspace filter | isolation W0/W2 | killed | V-34, V-35, V-36 |
| `get_return` without the order check | isolation | killed | G-04, G-05 |
| `get_return` via `session.get` (no workspace) | isolation W0/W2 | killed | G-06, G-07, G-08, G-16 |
| `get_return` takes `FOR UPDATE` by default | locks | killed | G-09 |
| `has_open_return` takes `FOR UPDATE` | locks | killed | HO-08 |
| `has_open_return` counts any status | status | killed | HO-03 |
| `has_open_return` without the workspace filter | isolation W0/W2 | killed | HO-06, HO-07, HO-10 |
| `list_returns` oldest first / pending only / no workspace filter | list | killed | L-01, L-02, L-12 / L-01, L-02, L-12 / L-04, L-10, L-11 |
| `sync_return_paid`: partial, overdue or "not unpaid" count as paid | credit note | killed | S-02, S-06 / S-04 / S-02, S-04, S-06 |
| `sync_return_paid`: invoice read without the workspace filter | isolation W0/W2 | killed | S-09, S-10 |
| `sync_return_paid`: no flush / commits / always writes | write rules | killed | 11 tests / S-14 / S-05, S-06, S-08, S-09 |
| `sync_return_paid` also sets a pending return to voided when the credit note is voided | credit-note void | killed | Q47-01 |
| **intended fix** running total (BUG-2761) | — | 106 pass tests pass | — |
| **intended fix** price range (BUG-2786) | — | 106 pass tests pass | — |
| **intended fix** all three (2760 + 2761 + 2786 + 2796), `--runxfail` | — | 127 passed; the 21 still failing are only the BUG-2762/2763/2764/2765/2423/2788/2797 cards that this variant does not fix | — |

Not applicable to this module (it writes no stock and no ledger): restock and ledger values (HR-15 half up vs half even), average cost, `make_sellable` ledger pairs, stocked-row flip, cost fallback order. Those live in `SalesService.complete_return` → `ProductManager` (cases Deferred, FU-1).

Credit-note void through the real `void_invoice`: pending (Q47-03..Q47-06, xfail BUG-2788, honest) and completed (Q47-07, xfail BUG-2788, honest). The already voided case (Q47-08) passes today and after the fix. Nothing is patched.

## Traceability
cards 148 · tests 148 (all under `# [claude] <ID>`, normal mode, no local-run.json) · unmatched: none · duplicates: none · marker mismatches: none. 106 pass cards have no marker. 40 strict xfail plus 2 non-strict (G-14, L-09, as the cards say). Every reason names its card's BUG id. BUG-2423, 2760–2765, 2786, 2788, 2796 and 2797 are all in `docs/testing/bugs.md`. The `# Then N` comments match the cards' numbered Then lines in every test. No `try/except`, no `pytest.raises(Exception)`. The only patch is S-14's commit spy, which the cards prescribe. Ruff is clean.

## Commands run
```
COVERAGE_FILE=…/retprodv/so/.cov1 .venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_order_return_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.sales_order_return_manager --cov-branch --cov-report=term-missing
  → app\managers\sales_order_return_manager.py  47  0  12  0  100%
  → 106 passed, 42 xfailed, 15 warnings in 17.24s
COVERAGE_FILE=…/.cov2 .venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_order_return_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  → 42 failed, 106 passed in 8.34s   (the 42 failures = exactly the 42 xfail cards, each on its "Fails today on" line)
run 2 / run 3 (plain): 106 passed, 42 xfailed in 8.55s / 8.46s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/sales_order_return_manager.py tests/unit/managers/test_sales_order_return_manager.py --json …/retprodv/mut_so.json
  → Mutants: 41 · killed 41 · timeout 0 · survived 0 · score 100%
SOV=<variant> PYTHONPATH=…/retprodv/so .venv/Scripts/python.exe -m pytest … -p so_variants -m "not xfail" -rf --tb=no   (37 variants, table above)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_sales_order_return_manager.py → All checks passed!
```
