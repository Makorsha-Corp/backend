# Verification — `app/services/purchase_order_item_insights_service.py`

> **Current verdict (round 2, 2026-11-10):** PASS. Cases rev 4 · 62 passed · 12 xfailed · mutation 95 / 95 counted = 100% (6 equivalent, 5 dead, 1 bug-path excluded).
>
> **Verdict (round 1):** NEEDS WORK
> Tests: 58 passed · 12 xfailed (reproduced ✅) · coverage 95% branch
> Mutation: 107 mutants · 91 killed · 16 survived → score 96% (91 / 95, after excluding 6 equivalent, 5 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful to the cards. Traceability is clean, and every xfail fails on its card's "Fails today on" line. Runs reproduce the notes and are stable.
28 hand variants were all killed. They covered voided rows counted, the workspace filter dropped, the excluded PO kept, unweighted, rounded (half-even and half-up) or raw-quantity averages, line-count vs order-count, zero prices counted, window edges ±1 day and exclusive ends, every tie-break flipped, unsorted rows, local-time `created_at`, and the float `Decimal`.
Four mutants survive because a case is missing, all in `_pick_avg_supplier_lowest` and `_HistoryLine`. R4 ("lowest average wins; on an equal average, more orders win") is only tested with the winner last in the list. R3's "weight 1 only for quantity ≤ 0" is only tested at 0 and −5, never just above 0. These go to the case designer; nothing goes to the executor.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_pick_avg_supplier_lowest` R4 (A-03…A-07, G-08) | In every card the winning supplier comes after the loser in the input list, so "the later supplier replaces on an equal average" and "the later supplier replaces when it has more orders" both go unnoticed | Mutants #51 (L252 `<`→`<=`) and #52 (L253 `and`→`or`) survive | case designer |
| 2 | case-missing | `_pick_avg_supplier_lowest` R3 | The weight rule "quantity, or 1 when ≤ 0" is tested at 0.00 and −5.00 only, never at a quantity between 0 and 1 (for example 0.50) | Mutant #68 (L236 `> 0`→`> 1`) survives | case designer |
| 3 | case-missing | `_HistoryLine` (spec Not specified, Gap log G1) | The spec states that setting an attribute raises `FrozenInstanceError`. No card checks it (revision 2 changed only the HL helper). Either add a card or record it in "Deferred" as not tested | Mutant #18 (L31 `frozen=True`→`False`) survives | case designer |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 18 | 31 | `frozen=True` → `False` | case-missing | Spec G1 states the dataclass is frozen; no card tries to set an attribute | case designer |
| 20 | 65 | `raise` → `pass` | dead | `if not po` 404 is unreachable: the manager raises first (spec FU-1) | — |
| 76 | 67 | message prefix → `""` | dead | Same unreachable 404 (FU-1) | — |
| 77 | 67 | `' not found'` → `""` | dead | Same unreachable 404 (FU-1) | — |
| 29 | 233 | negate `if ln.account_name` | equivalent | Bucket `account_name` is never read or returned (spec R3 note, FU-1) | — |
| 61 | 226 | key `'account_name'` → `''` | equivalent | Same unused bucket field | — |
| 66 | 226 | `or` → `and` (name fallback) | equivalent | Same unused bucket field | — |
| 67 | 234 | key `'account_name'` → `''` | equivalent | Same unused bucket field | — |
| 99 | 226 | `'Account #'` → `''` | equivalent | Same unused bucket field | — |
| 38 | 243 | `best_order_count = -1` → `2` | equivalent | It is never compared before the first assignment, because `best_avg is None` short-circuits the first bucket | — |
| 39 | 246 | `<= 0` → `< 0` | dead | Total weight is always ≥ 1 (R7, cases "Deferred", FU-1) | — |
| 102 | 267 | `else 0` → `else 1` | dead | Missing-date fallback is unreachable from the public method, since `created_at` is NOT NULL (FU-1). Helper-level A-09 Then 4 still holds, because a real date's ordinal is far above 1 | — |
| 75 | 253 | `>` → `>=` (order count) | bug-path | Equal average and equal count is the BUG-2543 tie. Only the xfail cards A-10 and A-11 target it, and they are excluded from the run | — |
| 51 | 252 | `avg < best_avg` → `<=` | case-missing | On an equal average the later supplier replaces the earlier one. A-06 and A-07 put the more-orders supplier last, so it wins either way | case designer |
| 52 | 253 | `and` → `or` | case-missing | A later supplier with a higher average but more orders replaces the winner. No card lists the cheaper supplier first and a pricier, more-ordered supplier after it | case designer |
| 68 | 236 | `> 0` → `> 1` | case-missing | A quantity in (0, 1] would weigh 1. No card uses a fractional quantity | case designer |

Suggested cards, for the designer to decide:
- A-12: cheaper supplier first in the list (1 order at 2.00), then a pricier supplier with 2 orders at 3.00; expect the cheaper one (kills #52).
- A-13: equal average, with the 2-order supplier first and the 1-order supplier after; expect the 2-order supplier (kills #51).
- A-14: Acme lines at 1.00 × qty 0.50 and 10.00 × qty 1.00 (average 7.00), against Beta at 6.50; expect Beta. With the weight forced to 1 for 0.50, Acme's average would be 5.50 and Acme would win (kills #68).

## Hand variants (verifier plugins, `-m "not xfail"`)
Plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv\poi\poi_var.py` re-executes the module source with one textual change. All 28 were killed. Each variant is listed with the cards that caught it.
- **Rows left in or out:** voided rows counted (G-17, F-02); PO workspace filter dropped with W0/W2 rows (G-17, F-06, F-07); excluded PO kept (G-08, G-09, G-17, F-03).
- **Lowest average:** unweighted average (A-03, A-04); raw quantity weight (A-05); average rounded to 0.01, both half-even and half-up (A-04); lines counted instead of orders (A-07); fewer orders win (A-06, A-07); supplier-less lines compete (A-02).
- **Reference line of the average winner:** earliest date wins (A-09); highest PO id wins (A-09).
- **Lowest price:** a zero price counts (M-01, M-02); latest date wins a price tie (M-06); highest PO id wins a tie (M-07).
- **Windows:** start exclusive (G-18, G-20, M-03); end exclusive (G-19, M-03); no upper bound (G-19, M-03); 31-day or 29-day window (G-18); 89-day window (G-20).
- **Last ordered:** only priced lines count (G-08, L-04); lowest line id wins a date tie (L-03); highest PO id wins instead of line id (L-03).
- **Rows and dates:** rows in insertion order (G-10); `created_at` cast in local time (F-12); `order_date` ignored (G-08, G-18…20, F-01, F-12).
- **`_dec`:** a float goes in without `str()` (D-03).

My own intended-behaviour fixes (`poi_fix.py`, `--runxfail`) each flip exactly their own cards and break no pass card:
- BUG-2542 (`utcnow().date()`): G-22 passes. The 11 other xfail cards still fail, and 59 pass.
- BUG-2543 (casefolded name, then `account_id`): A-10 and A-11 pass. The 10 other xfail cards still fail, and 60 pass.

The executor's `poi_ref.py` was read but not run (pipeline rule).

## Traceability
- Cases 70, tests 70. Every case ID appears exactly once, as a test name and a docstring. No test is without a case ID.
- Marker mismatches: none. All 12 xfail cards are `xfail(strict=True)`, and each reason names the card's BUG ID: BUG-2540 ×6, BUG-2541 ×3, BUG-2542 ×1, BUG-2543 ×2. BUG-2540…2543 exist in `docs/testing/bugs.md` (open). No pass card has a marker.
- Fidelity: every Then line of every card is asserted in order, with exact values.
  - No weakened checks, no swallowed exceptions, no extra mocks. The only patches are CLOCK/SKEW and the commit/rollback spies.
  - Givens are reproduced, including the W0/W2 rows and the void columns.
  - Every xfail under `--runxfail` fails on the card's "Fails today on" line:
    - G-12 Then 2 (L462), G-13 Then 2 (L476), G-14 Then 1 (L487)
    - G-15 Then 3 (L507), G-16 Then 2 (L529), G-22 Then 2 (L657)
    - F-09 Then 2 (L799), F-10 Then 2 (L813), F-13 Then 2 (L851), F-14 Then 2 (L865)
    - A-10 Then 2 (L1266), A-11 Then 2 (L1282)

## Commands run
```
COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_purchase_order_item_insights_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.purchase_order_item_insights_service --cov-branch --cov-report=term-missing
  app\services\purchase_order_item_insights_service.py  102  3  32  4  95%  65, 233->235, 247, 260
  58 passed, 12 xfailed
... --runxfail -rf            → 12 failed, 58 passed
... -rxX (run 2)              → 58 passed, 12 xfailed
... -rxX (run 3)              → 58 passed, 12 xfailed
... --runxfail -m xfail --tb=short  → failure lines mapped to the "# Then" lines above
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/purchase_order_item_insights_service.py tests/unit/services/test_purchase_order_item_insights_service.py --json <scratch>/mut_poi.json
  Mutants: 107 · killed 91 · timeout 0 · survived 16 · score 85% (raw)
PYTHONPATH=<scratch>/poi POI_VAR=<v> ... -p poi_var -m "not xfail"   → 28/28 variants killed
PYTHONPATH=<scratch>/poi POI_FIX=2542|2543 ... -p poi_fix --runxfail → 59 / 60 passed, own cards only
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv\` (`mut_poi.*`, `run_poi_*.log`, `poi\`).

## Round 2 — 2026-11-10

> **Verdict:** PASS
> Tests: 62 passed · 12 xfailed (reproduced ✅, 3 identical runs) · coverage 95% branch (65, 233->235, 247, 260, as in round 1)
> Mutation, targeted re-run of the real-gap lines 31, 236 and 252–253: 8 mutants · 7 killed · 1 survived (L253:40 `>`→`>=`, which is round-1 #75, bug-path). Whole module: 95 killed / 95 counted → **100%**.
> Cases revision: 4

**New tests read against their cards.** PII-A-12, A-13, A-14 and DC-01 each build the card's Given exactly: the same `HL` lines, prices, quantities, account ids and list order. Each makes the card's call and checks every Then line with `==`, `is` or `pytest.raises(FrozenInstanceError)`. The A-14 numbers check out: Acme is (0.5·1 + 1·4)/1.5 = 3.00, above Beta's 2.75. With a weight of 1 for 0.50, Acme would be 2.50 and would win. No other test changed. Traceability: 74 cards · 74 tests · no unmatched ID · markers unchanged.

**Round-1 survivors:**
| Mutant | Line | Round 2 |
|---|---|---|
| #18 `frozen=True`→`False` | L31 | killed (DC-01) |
| #68 `> 0`→`> 1` | L236 | killed (A-14). The other two mutants on that line are also killed. |
| #51 `<`→`<=` | L252 | killed (A-13) |
| #52 `and`→`or` | L253 | killed (A-12, A-13) |
| #75 `>`→`>=` (order count) | L253 | survives; still bug-path (the BUG-2543 tie, targeted only by xfail A-10 and A-11) |

**`--runxfail`:** the same 12 tests fail with the same messages as in round 1 (the diff of the `FAILED` lines is empty).

**Findings:**
| # | Kind | Case / line | What is wrong | Fix by |
|---|---|---|---|---|
| 1 | Wording (minor) | cases "Deferred to other specs", R7 row | It says "weights are always ≥ 1 by R3". Spec R7 says "> 0", and A-14 now uses a weight of 0.50. No expectation is affected. | case designer (cosmetic) |

**Commands:**
```
lowsupv/r2/runs.sh services purchase_order_item_insights_service poi   (coverage run + 2 plain runs + --runxfail --junitxml)
  62 passed, 12 xfailed (x3) · --runxfail: 12 failed, 62 passed
mutate.py app/services/purchase_order_item_insights_service.py tests/unit/services/test_purchase_order_item_insights_service.py --lines {31-31 | 236-236 | 252-253} --json lowsupv/r2/mut_poi_<range>.json
  31: 1/1 killed · 236: 3/3 killed · 252-253: 3/4 killed (survivor L253:40 Gt->GtE = round-1 #75, bug-path)
```
