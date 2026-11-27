# Verification — `app/services/item_summary_service.py`

> **Current verdict (round 2, 2026-11-10):** PASS. Cases rev 4 · 195 passed · 107 xfailed + 3 xpassed non-strict · mutation 298 / 298 counted = 100% (4 equivalent, 3 bug-path excluded).
>
> **Verdict (round 1):** NEEDS WORK
> Tests: 188 passed · 107 xfailed + 3 xpassed non-strict (reproduced ✅) · coverage 99% branch (283 stmts, 80 branches, 1 partial: 249->251)
> Mutation: 305 mutants · 295 killed · 10 survived → score 99% (295 / 298, after excluding 4 equivalent, 0 dead, 3 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. All 298 cards are implemented faithfully (traceability and Given/Then checks found nothing). Each strict xfail fails on the Then line its card names. My own reference fixes for BUG-2485, 2486, 2521 and 2524 each flip exactly their own cards (19 in all) and break no pass card. Mutation kills 295 of 305 mutants. The three real survivors are gaps in the cases or the spec, not weak tests: a weighted average whose priced quantity adds up to 1 or less, the 999999999 sentinel, and an account with no dated line. My hand variants found two more case gaps:
- A dropped workspace filter in the pricing 30/90-day windows, and in the formula / project counts and the formula / batch / project previews, goes unnoticed.
- Spend computed as quantity × price instead of `line_subtotal` goes unnoticed.

Nothing goes to the executor. The Revision 3 notes entry is present and matches these runs.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_pricing_snapshot_from_po_lines` R3; PS-01 … PS-07 | No case has a weighted average whose priced quantity adds up to more than 0 and at most 1. The `weight_total > 0` boundary is never checked with a non-empty average. | mutant #206 L429 `0 -> 1` survived | case designer |
| 2 | case-missing | `_pricing` R1/R3 (workspace); PRC-07 | PRC-07 checks only `last_unit_price` and `all_time` min/max. A W2 line of I1 dated TD would enter `days_30` / `days_90` if the window query lost its workspace filter. | hand variant: deleting L462 (`PurchaseOrder.workspace_id == workspace_id` in `lines_for_days`): 188 passed | case designer |
| 3 | case-missing | `_usage` R1/R2 (workspace); US-03 | US-03 has no W0/W2 formula line of I1 and no W0/W2 project-component line of I1. It also checks no formula / batch / project preview: B9 (a W2 batch line of I1) is checked through the count only. | hand variants deleting L663 (formula count), L681 (component count), L709 / L729 / L751 (formula / batch / project preview workspace filters): each 188 passed | case designer |
| 4 | case-missing | `_order_stats_for_item` R2 (spend = Σ `line_subtotal`); OS-01, OS-02 | No purchase line has a `line_subtotal` that differs from quantity × price. OS-01 has 50.00 = 10 × 5.00; OS-02's line has no price and no subtotal. | hand variant: spend = `quantity_ordered * coalesce(unit_price, 0)`: 188 passed | case designer |
| 5 | case-missing (low) | `_pick_most_frequent_supplier` R1 (sentinel 999999999) | No case puts a real average near the sentinel, for example 999999999.50 against no average. | mutant #285 L653 `999999999 -> 1000000000` survived | case designer (or describer: "no average ranks last" may be the better rule than a literal sentinel) |
| 6 | spec-gap (low) | `_supplier_rows_from_po_lines` R5 | No rule says what `last_order_date` / `last_unit_price` are for an account whose lines all have no date. Today both are `None`. The pure helper accepts such rows; `_supplier_stats` cannot produce them. | mutant #185 L587 `'last_price' -> ''` survived (only such an account would hit the KeyError) | describer (fill-gaps) |
| 7 | case-missing (low) | `_product_rows` R3 (margin unrounded, HR-15) | Every card's margin ends in 0 in the hundredths (0.50, -1.00, 0.00), so rounding the margin to one decimal goes unnoticed. | hand variant: `margin.quantize(Decimal('0.1'))`: 188 passed | case designer |

No fidelity finding: no missing, weakened or changed assertion, no wrong setup, swallowed failure, extra mock or dishonest xfail.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 78 | L860 | `not order_type or not order_id` → `and` | equivalent | With the type empty, the elif chain ends in `return None`. With the id empty, the query `id = NULL/0` finds nothing → `None`. Only an extra read results, and `_resolve_order_number` has no read rule. | — |
| 86 | L249 | `inv.qty > 0` → `>=` | equivalent | Rows with `qty <= 0` are skipped two lines above, so the condition is always true (spec Branch map). | — |
| 153 | L635 | `avg is not None and total_qty > 0` → `or` | equivalent | Today `avg` is `None` exactly when `total_qty <= 0` (R4), so both parts are the same test. **Note:** after BUG-2524 (average over priced quantity) they differ: an all-unpriced supplier has `avg None` and `total_qty > 0`, and `or` would feed `None` to `min`. | — (future note) |
| 185 | L587 | `'last_price'` key → `''` | spec-gap | See Finding 6. | describer |
| 194 | L635 | `total_qty > 0` → `>=` | equivalent | `avg` not `None` already implies `total_qty > 0`, so equality is impossible here. | — |
| 206 | L429 | `weight_total > 0` → `> 1` | case-missing | See Finding 1. | case designer |
| 244 | L319 | fallback `factory_id` `0 -> 1` | bug-path | R3's "missing from the location map" fallback is reached today only through BUG-981 (deleted machine) or BUG-2520 (foreign machine / factory). Intended behaviour leaves those placements out (MP-10, MP-11 and the BUG-981 cards, all xfail). | — |
| 246 | L320 | fallback `factory_name` `'—' -> ''` | bug-path | As #244. | — |
| 268 | L318 | fallback `'Machine #'` → `''` | bug-path | As #244. | — |
| 285 | L653 | sentinel `999999999 -> 1000000000` | case-missing | See Finding 5. | case designer |

## Hand variants (own plugin `vr.py`, in-process, pass cards only: `-m "not xfail"`)
**Killed** (variant → failing pass cards):
- Workspace filter dropped:
  - order stats PO / TO / SO (1 each);
  - pricing last price, all-time and open lines (1 each);
  - supplier query (1); work-order count (1) and preview (1); batch count (1);
  - factory map (2), machine map (1), location map (2).
- Unit price over all quantity: 3.
- Rounding: half-even or half-up to 0.01 on the pricing average (2 / 2), on the supplier average (2 / 2), and even to 6 places (1). Half-even and half-up are killed alike, because PS-07 / SR-07 require the unrounded half cent.
- Date-window edges:
  - order stats PO low/high (4/2), no upper bound (2), TO low/high (1/1), TO by timestamp (1), SO low/high (1/1), PO dated by `created_at` only (4);
  - pricing windows low/high (2/1), off by one day (2);
  - supplier window off by one day (4), undated rows let in (1).
- Tie-breaks:
  - cheapest `+order_count` or no count key (1/1); most-frequent sign flipped or no average key (3/3), zero sentinel (1);
  - last price `>=` (1); PRC last price by `id asc` (1) or by id only (2);
  - batch / work-order id tie-break reversed (1/1);
  - inventory type key dropped (1); placement section key dropped (1), low-stock order flipped (1);
  - activity merge order reversed for equal times (1).
- Open lines:
  - by status **name** "Completed" instead of the workflow sequence: 4 (OQ32-08 and siblings);
  - received-only test: 2.
- Quantity / line totals without sales or transfers: 3 / 2 / 3.
- Placement with qty 0 dropped: 3. Limits:
  - activity `per_source = limit`: 1; cut to limit − 1: 2;
  - preview limit 6: 4; supplier top 11: 2.
- Deleted machine kept in the location map: 1.

**Survived:**
- Pricing-window workspace filter, and five usage workspace filters (Findings 2, 3).
- Spend as qty × price (Finding 4); margin to 0.1 (Finding 7).
- **equivalent:**
  - `is_deleted` dropped in `_inventory_rows` / `_product_rows` (the DAOs already filter `is_deleted == False`);
  - `_est_value` quantized to 0.01 (`Numeric(15, 2)` × int is already two places).
- **bug-path (BUG-2523):** cheapest-tie resolved from the end of the input; equal-spend supplier order reversed.
- **expected:** spend without sales. This is half of the BUG-2485 fix, and no pass card contradicts the owner's OQ-31 answer.

Voided rows counted is today's behaviour (BUG-2521); see the reference check below.

## Reference check (own `vr.py`, `--runxfail`)
| Fix (own, from the spec) | Own xfail cards | Flipped | Pass cards broken | Other xfails passing |
|---|---|---|---|---|
| BUG-2485 (`sales_revenue` split, spend = purchases) | 6 | 6 | 0 | 0 |
| BUG-2486 (last id of `status_sequence`, same-workspace workflow) | 4 | 4 | 0 | 0 |
| BUG-2521 (voided POs out of every purchase read) | 4 | 4 | 0 | 0 |
| BUG-2524 (unpriced lines out of averages / last prices; last date kept) | 5 | 5 | 0 | 0 |
| all four together | 19 | 19 | 0 | 0 |

(An early draft of my BUG-2524 fix also stopped unpriced lines from setting the last date, and it broke SR-12. That was my fix's error: spec R5a keeps the date. The card is right.) I read the executor's `is_ref.py` but did not run it; its 24-bug per-fix claims are not re-verified beyond these four bugs.

## Non-strict xfails (US-10, US-11, US-13; also SS-10, SS-11)
They are justified:
- US-10 and US-13 depend on the database collation. `marker_test` is `English_United States.1252`, which already orders "apex" before "Zeta", so both XPASS on every run here. They would fail under `C`.
- US-11, SS-10 and SS-11 depend on the plan order of rows that tie.
- Each group has a strict SQL alarm: US-12 / US-14 for the id tie key, SS-12 for the `ORDER BY`.

Caveat for the case designer (optional, not a finding): on this database nothing strict signals a missing *case-insensitive* key in the formula / project previews.

## DISCREPANCY-1 (OQ31-11)
Confirmed closed. Cases revision 3 retired OQ31-11: `sales_order_items.unit_price` / `line_total` are NOT NULL (`app/models/sales_order_item.py` L63–64). The card is gone and no test is left. Nothing open for the case designer.

## Traceability
- Cases: 298 (188 pass, 110 xfail). Tests: 298, one per case.
- Unmatched: none. Duplicate IDs: none.
- Marker mismatches: none. Every xfail uses `xf(...)` with the exact BUG IDs of its Expect line, strict unless the card says non-strict. Every BUG ID exists in `docs/testing/bugs.md`.
- `# Then N` blocks equal the card's Then count in every test.
- Then expressions: 684 checked mechanically, 22 not literal. All 22 are equivalent forms:
  - `Decimal("0")` → `Decimal(0)` (ruff);
  - ids read into locals before the recorder;
  - statement checks written as helpers that match the card text.
- Given builder calls: every mismatch is a loop or table form with the same rows.

## Commands run
```
COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_item_summary_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.item_summary_service --cov-branch --cov-report=term-missing
  app\services\item_summary_service.py  283  0  80  1  99%  249->251
  188 passed, 107 xfailed, 3 xpassed, 15 warnings in 40.66s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_summary_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  107 failed, 191 passed in 21.29s
.venv/Scripts/python.exe -m pytest ... -o addopts="" --runxfail --tb=long --junitxml=<scratch>/rx.xml   (own line mapping, rxmap.py)
  107 failed, 191 passed — 107/107 strict xfails fail inside the card's "Fails today on" Then block; 17 BUG-2520 signature cards + RA-23 raise TypeError, OQ31-10 AttributeError, as pinned by raises=; US-10/11/13 pass
.venv/Scripts/python.exe -m pytest ... -o addopts="" -rxX   (run 2)   188 passed, 107 xfailed, 3 xpassed in 20.91s
.venv/Scripts/python.exe -m pytest ... -o addopts="" -rxX   (run 3)   188 passed, 107 xfailed, 3 xpassed in 20.53s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/item_summary_service.py tests/unit/services/test_item_summary_service.py --json <scratch>/mut_is.json
  Mutants: 305 · killed 295 · timeout 0 · survived 10 · score 97%
PYTHONPATH=<scratch>/is VR=<variant> pytest ... -o addopts="" -p vr -m "not xfail"          (66 hand variants + 12 line deletions)
PYTHONPATH=<scratch>/is VR=R2485|R2486|R2521|R2524|all four pytest ... -o addopts="" -p vr --runxfail --junitxml=...
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv\` (`mut_is.*`, `run_is_*`, `is\` with `trace.py`, `fid.py`, `giv.py`, `rxmap.py`, `refcheck.py`, `vr.py`, `v\`). All runs used private `COVERAGE_FILE`s and ran in parallel with the other modules' runs without a clash (per-process `GN` / `XID`). Outcomes were stable across 4 plain runs.

## Round 2 — 2026-11-10

> **Verdict:** PASS
> Tests: 195 passed · 107 xfailed · 3 xpassed non-strict (reproduced ✅) · coverage 99% branch (283 stmts, 80 branches, only the unreachable 249->251)
> Mutation, targeted re-run of the real-gap lines 429, 587 and 653: 6 mutants · 6 killed · 0 survived. Whole module: 298 killed / 298 counted → **100%**.
> Cases revision: 4 · spec: `_supplier_rows_from_po_lines` R5b added. MF-07 keeps the literal 999999999 rule, as decided under delegation.

**New and changed tests read against their cards.**
- **PS-08:** the card's two lines; Then 1 `== Decimal(3)` (the same value as the card's `Decimal("3")`) and Then 2 min/max.
- **OS-13:** two stored subtotals (45.00 and 7.50), with the qty, spend and line count asserted exactly.
- **MF-07 and MF-08:** the card's tuples in the card's order, built into rows the same way as MF-02 … MF-06.
- **PD-14:** margin `== Decimal("0.75")`.
- **SR-19 and SR-20:** every Then line, with `is None` and exact values.
- **PRC-07 (changed):** gains Then 4 and 5 (`days_30` and `days_90` min and max).
- **US-03 (changed):** has all 13 Given lines, including the W0 I0 formula line, the W0 I1 formula, and the W0 and W2 batch, project and component lines, plus the W1 line of I2. All 8 Then lines are exact list comparisons.
- No weakened or missing assertion, no extra mock, no wrong setup.
- Traceability: 305 cards · 305 tests · the IDs match one to one · markers unchanged.

**Round-1 findings:**
| Round-1 item | Round 2 |
|---|---|
| F1, mutant #206 (L429 `> 0`→`> 1`) | killed (PS-08). The other two mutants on L429 are also killed. |
| F2, `days_30` / `days_90` workspace filter (variant `del462`) | killed (PRC-07) |
| F3, five usage-query workspace filters (`del663`, `del681`, `del709`, `del729`, `del751`) | all killed (US-03) |
| F4, spend = qty × price (`spend_qty_times_price`) | killed (OS-13) |
| F5, mutant #285 (L653 sentinel) | killed (MF-07, MF-08); the `or`→`and` mutant on L653 is also killed |
| F6, mutant #185 (L587 `'last_price'`) | killed (SR-19 / SR-20 after spec R5b) |
| F7, margin rounded (`round_margin`) | killed (PD-14) |
| `spend_ex_sales` | still survives, as intended: it is half of the BUG-2485 fix, and no pass card contradicts OQ-31 |

**The executor's revision 4 claims, checked independently:**
- **Mutant #206 kill:** confirmed by `mutate.py --lines 429-429` (3/3 killed).
- **`--runxfail`:** 107 failed, 198 passed. The set of failing tests is identical to round 1, whose 107 were each mapped to the card's "Fails today on" line. No new card is xfail.
- **Reference plugin:** I did not run the executor's `is_ref.py`. My own `vr.py`, re-run on revision 4, gives these results:
  - BUG-2485: 6 own cards flip.
  - BUG-2486: 4 own cards flip.
  - BUG-2521: 4 own cards flip.
  - BUG-2524: 5 own cards flip.
  - All four together: 19 / 19 flip.
  - In every run, 0 other xfails pass and 0 pass cards break, including the 7 new cards.
  - The notes' "305 passed with all fixes" covers 20 more bugs, which I have not re-checked; that is unchanged since round 1.
- **Coverage:** 99%, as the notes say.
- **Revision 4 notes entry:** present (header "revision 4", Verification runs and Revision history entries). Nothing to route.

**Repeat runs:** there were 5 plain or coverage runs in all.
- 4 of them gave 195 passed · 107 xfailed · 3 xpassed (US-10, US-11, US-13).
- The first coverage run gave 106 xfailed · **4 xpassed**: one of the tie-order non-strict cards (SS-10 / SS-11) happened to pass.
- This is the non-determinism those `strict=False` markers exist for (justified in round 1). No pass card changed outcome, so it is not a flaky-test finding.
- Low priority for the executor: the notes say "3 xpassed in each run". "3 (rarely 4–5: SS-10/SS-11 depend on tie order)" would be accurate.

**Findings:**
| # | Kind | Case / line | What is wrong | Fix by |
|---|---|---|---|---|
| 1 | Notes accuracy (low) | notes "3 plain runs" | The xpassed count can be 4 when a tie-order non-strict card passes (seen once in 5 runs). | executor |

This does not change what the tests catch, so the verdict is PASS.

**Commands:**
```
lowsupv/r2/runs.sh services item_summary_service is  → 195p/106xf/4xp (cov), 195p/107xf/3xp (x2); --runxfail 107 failed, 198 passed; 99% branch
pytest … --cov … -rX (x2)  → 195p/107xf/3xp; XPASS US-10, US-11, US-13
mutate.py app/services/item_summary_service.py tests/unit/services/test_item_summary_service.py --lines {429-429 | 587-587 | 653-653} --json lowsupv/r2/mut_is_<range>.json
  429: 3/3 · 587: 1/1 · 653: 2/2 killed
VR=<variant> PYTHONPATH=lowsupv/is pytest … -p vr -m "not xfail"  (del462, del663, del681, del709, del729, del751, spend_qty_times_price, round_margin: each 1 failed; spend_ex_sales: 0 failed)
VR=R2485|R2486|R2521|R2524|all PYTHONPATH=lowsupv/is pytest … -p vr --runxfail --junitxml + lowsupv/is/refcheck.py  (results above)
```
