# Verification — `app/services/item_orders_service.py`

> **Verdict:** PASS
> Tests: 92 passed · 36 xfailed (reproduced ✅) · coverage 100% branch (131 stmts, 56 branches)
> Mutation: 148 mutants · 132 killed · 16 survived → score 100% (after excluding 10 equivalent, 0 dead, 6 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can be trusted. All 128 cards are implemented one-to-one, in card order, with the card's exact values. No assertion is weakened, no Given is missing, and nothing is patched beyond the G-34 spies and the G-37 fixed input that Conventions name.
Every xfail fails under `--runxfail` on the Then line its card names. The 8 BUG-2550-shaped cards fail instead in the When, on the `AttributeError` at source line 460, which is what their cards say.
Mutation testing killed every mutant that a pass card can observe. The 16 survivors are of two kinds. Ten are unused SQL label names. Six are work-row and zero-sales-total code that only xfail cards can see today (BUG-2550, BUG-2491).
All 33 hand variants were caught, or behaved as expected: the half-up variant is the intended fix, and the xfail cards catch half-even. Nothing needs fixing.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 47 | 164 | `or` → `and` (work type gate) | bug-path | Turns work rows off. Every live work row crashes today (BUG-2550), so only xfail cards G-06, G-10, W-03 … see them. | — (BUG-2550) |
| 99 | 164 | `'work_order'` → `''` | bug-path | Same gate, typed call only. Only xfail G-10 targets it. | — (BUG-2550) |
| 121 | 455 | `order_type='work_order'` → `''` | bug-path | Built only for a work row. The row crashes on line 460 first today. | — (BUG-2550) |
| 126 | 401 | sales `total > 0` → `>=` | bug-path | A zero sales total would show 0.00. That is spec R5a (BUG-2491), and only xfail OQ33-05 targets it. Pass cards use positive totals by Convention. | — (BUG-2491) |
| 127 | 460 | `is not None` → `is` | bug-path | Removes the crash, but every status becomes None. Only xfail W-03 and W-04 assert the status text. | — (BUG-2550) |
| 133 | 438 | work join `==` → `!=` | bug-path | Pairs each work order with other orders' lines. Every positive work row is observable only through the xfail cards (W-03 gets total 0 under this mutant), because a listed work row crashes today. | — (BUG-2550) |
| 137, 138 | 431, 433 | `.label('order_date' / 'quantity')` → `''` | equivalent | Result rows are unpacked by position (line 452). No code reads the label names, and `group_by` uses the column, not the label. | — |
| 141, 142 | 304, 306 | transfer labels → `''` | equivalent | Unpacked by position (line 326). | — |
| 143, 144, 145 | 214, 218, 219 | PO labels → `''` | equivalent | Unpacked by position (lines 250–261). | — |
| 146, 147, 148 | 364, 366, 367 | sales labels → `''` | equivalent | Unpacked by position (line 390). | — |

After BUG-2550 is fixed, re-run mutation. #47, #99, #121, #127 and #133 should then die on W-03 and G-10. #126 should die once BUG-2491 is fixed.

## Hand variants (verifier plugin `lowsupv/io/iov_variant.py`, pass-expected tests only)
Each variant re-executes the module source with one textual change, in-process. All were caught:

| Variant | Killed by |
|---|---|
| voided POs counted | G-30, P-03 |
| deleted work lines counted | W-01, W-02, W-10 |
| workspace filter dropped: PO / transfer / sales / work | G-31 + P-12 / T-05 / S-06 / W-09 (W0 and W2 rows on both sides) |
| workspace filter dropped on the factory / machine / component label | DL-10 (each) |
| lone date bound applied | G-13, G-14 |
| range end exclusive / start exclusive | DR-01, G-12, P-05, P-06, P-21, T-03, T-08, S-04 (each) |
| PO date from `created_at` only | 8 cards (P-06, G-19 …) |
| sales date from `created_at` only | G-19, S-04 |
| transfer / work date shifted by a time zone | T-08 / W-11 |
| tie-break: order id before type rank; type order reversed | G-20, G-35 |
| sort ascending; `created_at` before date | G-05, G-19, G-24 … / G-05, G-19 |
| `total` = page length; page taken before sort | G-24 … G-31 (8 each) |
| PO zero / unpriced total shown as 0 | OQ33-04, OQ33-08 |
| PO account inner join | P-08 |
| free-text sales lines matched | S-02 |
| received instead of ordered quantity | 9 cards |
| one row per PO line | G-33, P-22, OQ33-06 |
| deleted item hidden | G-04 |
| exclude id applied to transfers too | G-18 |
| PO status dropped | P-01 |
| commit after read | G-34 |
| rounding half-even to 2 places (with `--runxfail`) | WP-08, WP-09, S-09 (xfail cards; correct) |
| rounding half-up to 2 places (with `--runxfail`) | none — this is the intended BUG-2554 fix; WP-06, P-20, S-10 stay green |

Not applicable to this module: spend/revenue split, last-status-by-name (OQ-32), foreign `factory_id` (R8b), notifier recipients, unchanged-save notification. The module has none of these.

## Traceability
cases 128 · tests 128 · unmatched: none · tests without a card: none · duplicates: none · marker mismatches: none.
Every pass card has no marker. Every xfail card is `strict=True`, except G-21, G-22 and G-36, which are non-strict as their Expect lines say. Each reason names exactly the card's BUG IDs (OQ33-01, 02, 07 and 09 name both). All BUG IDs used (2490, 2491, 2550 … 2555) exist in `docs/testing/bugs.md`. BUG-2556 is deferred to the endpoint, as the cards say.
Notes revision 3 entry present; Result line matches.

## Commands run
```
COVERAGE_FILE=<lowsupv>/.cov.io .venv/Scripts/python.exe -m pytest tests/unit/services/test_item_orders_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.item_orders_service --cov-branch --cov-report=term-missing
  app\services\item_orders_service.py  131  0  56  0  100%
  92 passed, 36 xfailed, 15 warnings in 15.40s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_orders_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  36 failed, 92 passed in 7.87s
  (verifier script lowsupv/io/xf_check.py, junit: all 36 fail on the card's "Fails today on" Then line; G-06, G-10, G-23, W-03 … W-06, W-08 on AttributeError at item_orders_service.py:460)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_orders_service.py -q -p no:cacheprovider -o addopts="" -rxX   (x2)
  92 passed, 36 xfailed in 7.82s
  92 passed, 36 xfailed in 7.86s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/item_orders_service.py tests/unit/services/test_item_orders_service.py --json <lowsupv>/mut_io.json
  Mutants: 148 · killed 132 · timeout 0 · survived 16 · score 89%
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/item_orders_service.py tests/unit/services/test_item_orders_service.py --lines 35-128 --json <lowsupv>/io/mut_io_rerun.json
  Mutants: 58 · killed 58 · survived 0   (re-run of the mutants whose first run overlapped the coverage and repeat runs: kills confirmed)
<lowsupv>/io/run_variants.py   (33 hand variants, results above)
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_item_orders_service.py
  All checks passed!   (file LF only)
```
`<lowsupv>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv`.
