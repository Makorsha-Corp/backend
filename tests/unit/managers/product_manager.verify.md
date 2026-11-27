# Verification — `app/managers/product_manager.py`

> **Verdict:** PASS (Round 2, 2026-11-19; Round 1 was NEEDS WORK)
> Tests: 135 passed · 100 xfailed (reproduced ✅) · coverage 100% branch (116 statements, 36 branches)
> Mutation: 241 mutants · 232 killed · 9 survived → score 98.7% (232 / 235, after excluding 2 equivalent, 0 dead, 4 bug-path)
> Hand variants: 50 · 34 killed · 16 survived (5 equivalent, 6 bug-path, 1 known spec gap, 4 case-missing)
> Source commit: e48a092 · Cases revision: 2

## Summary
You can trust these tests. All 235 cards trace one-to-one to tests. Every Then line I read has its assertion, with the exact value from the card. Nothing is mocked beyond the cases file's commit spy. Every strict xfail fails today on the line its card names. Three plain runs gave the same result. The same holds for the stock paths: workspace isolation (W0 and W2 rows, by id and by bucket key), the stock check, subtracting or adding twice, signed deltas and the ledger `qty_before` / `avg_cost_before` columns all have tests that catch them. The work left is for the **case designer**. A few boundaries and money values have no card:
- quantity 1 accepted by `apply_sale_deduction` and `apply_sale_return`;
- an old stock of 1 in the weighted average;
- an average whose third decimal rounds down;
- a ledger `total_cost` with cents on a delivery, a return or an adjustment.

None of these is a fault in the tests themselves. DISCREPANCY-1 (PRDM-PO-20) is known and still open with the describer.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `apply_sale_deduction` R1 | No card shows that quantity 1 is accepted. PO-03 has this boundary for production, SD does not. | mutant #86 L272 `quantity <= 0` → `<= 1` survives | case designer |
| 2 | case-missing | `apply_sale_return` R1 | Same as #1: no card shows that quantity 1 is accepted. | mutant #110 L344 `<= 0` → `<= 1` survives | case designer |
| 3 | case-missing | `apply_production_output` R5 (old `qty > 0`) | No card has a weighted average with old `qty` 1. Every R5 card has an old qty of 10 or 2. | mutant #214 L216 `old_qty > 0` → `> 1` survives | case designer |
| 4 | case-missing | `apply_production_output` R5 (rounded to 2 places) | Every pass card's average either comes out exact (5.50, 2.50, 3.00) or rounds up (1.1666 → 1.17). No card rounds down, e.g. 2 at 1.00 + 1 at 2.00 → 1.333 → 1.33 (ROUND_UP gives 1.34). The half-cent case PO-18 is the BUG-1040 xfail. | hand variant `quantize(..., ROUND_UP)` survives. (`ROUND_DOWN` is killed by PO-19.) | case designer |
| 5 | case-missing | `apply_sale_deduction` R6, `apply_sale_return` R6, `update_product` R7 (`total_cost = avg × quantity`) | Every pass card's total is a whole number (4.00 × 3, 4.00 × 2, 10.00 × 3 …). Rounding `total_cost` to whole units is never caught. Only `create_product` has one (C-03, 3.25). | hand variants `(avg * qty).to_integral_value()` survive in SD, SR and update. They are killed in create. | case designer |
| 6 | case-missing (low) | `apply_production_output` R5 | The average is rounded in Python before it is written. Every card re-reads, so the `Numeric(15,2)` column hides a missing `quantize`. The in-session value (`result.avg_cost` before expiry) is not checked. Without `quantize` the stored value also turns half-up. A card on the returned object would pin R5 apart from the column. | hand variant "no `quantize`" survives | case designer |
| 7 | known spec gap | PRDM-PO-20 (DISCREPANCY-1) | `avg_cost_before` for a bucket created by a costed output: R2 seeds `avg_cost = unit_cost`, so it is 6.00, but the card expects None. Already routed. Not counted as a new finding. | `--runxfail`: fails on Then 4 `Decimal('6.00') is None`. Hand variant "create the bucket with `avg_cost None`" survives only because PO-20 is xfailed. | describer (fill-gaps), already open |
| 8 | spec gap (open, from cases) | `update_product` R9 vs R10 | Cases gap 7 is still open: a row that holds stock, flipped onto a taken key. Which comes first, 400 or 409? | cases file "Spec gaps" #7 | describer (fill-gaps) |
| 9 | note for the BUG-2770 fix | `apply_*` bucket reads | `Product.item` is `lazy="joined"`, a LEFT OUTER JOIN. A plain `.with_for_update()` on a `products` query fails in Postgres with `FeatureNotSupported: FOR UPDATE cannot be applied to the nullable side of an outer join`. The fix must use `with_for_update(of=Product)`, or drop the eager join on the locked read. With `of=Product` the lock cards PO-15, SD-21 and SR-14 pass, and G-11 and D-10 still guard the readers. | hand variant run, both forms | describer: add to the BUG-2770 entry / spec R10 as a fix note |

Minor, no action: PRDM-U-27 and PRDM-SR-29 name two bugs in their xfail reason (BUG-2777 + BUG-2778, and BUG-2794 + BUG-1336), while the card's Expect line names one. The reason follows the card's Rules line, and SR-29 fails today on BUG-1336, as its "Fails today on" line says. If the Expect lines listed both IDs, they would match the markers.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 86 | 272 | `quantity <= 0` → `<= 1` | case-missing | Finding 1 | case designer |
| 110 | 344 | `quantity <= 0` → `<= 1` | case-missing | Finding 2 | case designer |
| 129 | 383 | `'sales_return_item'` → `''` | bug-path | BUG-2783 changes this label. Only SR-02 (xfail) checks it. The pass cards leave it out on purpose (see "today-independent halves"). | — |
| 130 | 385 | `'customer'` → `''` (`transfer_destination_type`) | bug-path | BUG-2783: the return should record the customer as the source, not the destination. Only xfail SR-02 targets this column. | — |
| 150 | 111 | `exclude_unset=True` → `False` | equivalent | Every `ProductUpdate` field defaults to `None`, and `exclude_none=True` still drops them, so the dict does not change. | — |
| 151 | 111 | `exclude_none=True` → `False` | bug-path | Sent nulls now reach the row. That is the BUG-2777 fix (U-24 … U-27 xfail). No pass card sends an explicit null. | — |
| 180 | 216 | `old_qty > 0` → `>= 0` | equivalent | At old qty 0 the weighted formula gives `(0 + q·uc)/q = uc` quantized, which equals the R6 branch `uc` for any 2-decimal cost. `unit_cost` comes from Numeric(15,2) data, and no caller passes it today (R7). | — |
| 214 | 216 | `old_qty > 0` → `> 1` | case-missing | Finding 3 | case designer |
| 238 | 288 | `' at factory '` → `''` | bug-path | BUG-2782 rewrites the message to use names. The pass cards check only the `: requested N, available M` suffix, by design. | — |

### Hand variants (verifier's own plugin, `retprodv/prod/variant_plugin.py`, `-m "not xfail"`)
Killed (34): weighted average divided by old qty; unweighted mean; `ROUND_DOWN`; `old_avg` tested for truthiness (PO-25); uncosted output dropping the average; `total_cost` from the new average; `avg_cost_before = new`; new bucket created for sale; fraction check removed; `<=` stock check (SD-03); stock check removed; `_quantity_to_int` skipped in SD and SR; SD subtracting twice; SR adding twice; SD and SR writing `avg_cost None`; SR bucket created not-for-sale; signed adjustment delta (U-09); update priced at the old average (U-12); `qty_before = new` (U-08); every flip refused (U-43); a ledger row on every update (U-06); create `qty_before = qty`; opening ledger row at qty 0; re-delete allowed; bucket lookup ignoring the workspace (first or last row), ignoring the for-sale flag, or including deleted rows; by-id read ignoring the workspace; factory check ignoring the workspace; list across workspaces; by-id read locked (G-11, D-10 catch it); create `total_cost` rounded to whole units.
Survived (16):
- equivalent: `int(dec.to_integral_value())`; `dec % 1` check; `Decimal(float(q))`, exact within Numeric(15,2); `max(old − q, 0)`, since the stock check keeps old ≥ q; average at `old_qty >= 0`.
- bug-path: half-up rounding (BUG-1040 / PO-18); bucket lock `FOR UPDATE OF products` (BUG-2770; PO-15, SD-21 and SR-14 xpass under it); a stocked flip refused (BUG-2793; U-40 … U-42, U-50, U-51); zero cost giving `total_cost` 0.00 (BUG-2779).
- known spec gap: new costed bucket created with no average (DISCREPANCY-1).
- case-missing: `ROUND_UP`, no `quantize`, and whole-unit `total_cost` in SD, SR and update (findings 4–6).

Not applicable to this module's code today: `make_sellable` ledger pairs (the method does not exist; all 30 MS cards are strict xfails at the call), the cost-fallback order by `performed_at` / id (BUG-2794 is not built; SR-22 and SR-23 are xfail), and foreign item names (no names are shown; BUG-2782).

## Traceability
- 235 cards (10 deferred are not counted) · 235 test ids (216 single-case functions + 3 parametrized functions with 19 param ids) · unmatched: none · duplicates: none.
- Marker mismatches: none, apart from the documented PRDM-PO-20 (pass → strict xfail DISCREPANCY-1).
- Each xfail reason names every BUG of the card's Expect line. U-27 and SR-29 also carry the second bug from their Rules line (see the minor note). Every BUG ID used is in `docs/testing/bugs.md`.
- Then blocks: every test has `# Then 1 … N` matching the card's Then count.
- `--runxfail`, mapped by my own plugin from the failing line to its `# Then N` block: 100 / 100 fail, each on the card's "Fails today on" line. 24 fail at the call with the named exception: AttributeError for `make_sellable`, TypeError for `include_deleted`, IntegrityError 23505 for PO-14, SR-13 and SR-29. PO-20 fails on Then 4.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_product_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.product_manager --cov-branch --cov-report=term-missing
  app\managers\product_manager.py  116  0  36  0  100%  ·  135 passed, 100 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_product_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  100 failed, 135 passed
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_product_manager.py -q -p no:cacheprovider -o addopts=""   (x2 more)
  135 passed, 100 xfailed · 135 passed, 100 xfailed
.venv/Scripts/python.exe -m pytest … --runxfail -p thenmap_plugin          (own plugin: fail line → Then block)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/product_manager.py tests/unit/managers/test_product_manager.py --json …/retprodv/mut_prod.json
  Mutants: 241 · killed 232 · timeout 0 · survived 9 · score 96% (raw)
.venv/Scripts/python.exe …/retprodv/prod/runvariants.py                    (own hand-variant runner, 50 variants)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_product_manager.py   → All checks passed!
```
All runs used a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprodv\prod\`.

## Round 2 — 2026-11-19

> **Verdict:** PASS
> Tests: 143 passed · 102 xfailed (reproduced ✅, 3 runs identical) · coverage 100% branch · cases revision 3

Narrow re-check after cases revision 3:
- **Traceability:** 245 cards map one-to-one to tests, with every Then block present. Every marker matches its Expect line. The Expect lines of U-27 and SR-29 now name both bugs, as their reasons do. PO-20 is now a strict xfail on BUG-2811 (no DISCREPANCY marker left). Ruff is clean.
- **Fidelity:** I read every new pass card against its test (SD-23, SD-24, SR-31, SR-32, U-55, PO-26, PO-28, PO-29) and every new or changed xfail (PO-20, PO-27, U-54). Every Then line is asserted with the card's exact value. PO-28 and PO-29 check `result.avg_cost` in the session before the re-read, as their cards say. No findings.
- **`--runxfail`:** all 102 fail, each on its card's "Fails today on" line (my Then-mapping plugin). PO-20 fails on Then 4. PO-27 and U-54 fail at the call with IntegrityError 23505.
- **My own reference** (`retprodv/prod/ref_r2_plugin.py`: R8a, so a new bucket has `avg_cost_before NULL`; the R2a restore for production; R9 before R10 per R10a): under `--runxfail`, PO-20, PO-27 and U-54 pass (3 / 3). In normal mode they XPASS and fail as strict, so they will flag the fix. The whole pass suite also passes under the reference (143 / 143).
- **Round 1 survivors re-run:**
  - Mutants: L272 `<= 1` KILLED · L344 `<= 1` KILLED · L216 `> 1` KILLED. L216 `>=` still survives; it is equivalent, as argued in Round 1.
  - Hand variants: the `ROUND_UP` average and the missing `quantize` are KILLED by PO-29. Whole-unit `total_cost` is KILLED in delivery (SD-24), return (SR-32) and update (U-55).
- Findings 1–8 of Round 1 are closed. Finding 9 (the BUG-2770 fix note) is now in the spec (R10, revision 2026-11-19).

Commands: the coverage run as above (`app\managers\product_manager.py 116 0 36 0 100%`, `143 passed, 102 xfailed`), then 2 more plain runs (`143 passed, 102 xfailed` each), `--runxfail -p thenmap_plugin` (`102 failed, 143 passed`), `-p ref_r2_plugin --runxfail -k "po_20 or po_27 or u_54"` (`3 passed`), `mutate.py … --lines 216-216 / 272-272 / 344-344`, and `runvariants.py` on 5 variants (all KILLED).
