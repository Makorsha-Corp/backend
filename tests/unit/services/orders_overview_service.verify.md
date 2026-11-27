# Verification — `app/services/orders_overview_service.py`

> **Verdict:** NEEDS WORK
> **Current verdict (round 2):** PASS. Cases rev 4: 110 passed · 69 xfailed + 1 xpassed (non-strict TE-05) · 99% branch. All 20 routed survivors and 3 surviving hand variants are now killed. Full-file score from round 1 plus the targeted re-run: 242 / 242 (6 equivalent, 17 bug-path excluded). See "Round 2 — 2026-11-10".
> Tests: 95 passed · 69 xfailed + 1 xpassed (non-strict OOV-TE-05) (reproduced ✅) · coverage 99% branch (158 stmts, 48 branches, 2 partial: 518->542, 543->548)
> Mutation: 265 mutants · 221 killed · 44 survived → score 92% (221 / 241, after excluding 7 equivalent, 0 dead, 17 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful. All 165 cards are implemented as designed, with no weakened, missing or swallowed assertions and no extra mocks. Every strict xfail fails under `--runxfail` on exactly the Then line (or When) its card names. Runs reproduce the notes and nothing is flaky.

The gaps are in the cases, not in the tests:
- No pass card checks `item_name` or `item_unit` of an item seen only on transfer or sales lines.
- No pass card checks that sales orders stay out of vendor spend. This matters because OQ-30/31 split spend from revenue.
- A deleted account's name is checked for expense vendors only, not PO vendors.
- A project of another factory is never shown to be dropped by the factory filters.
- "Destination type decides the table" is pinned for the machine table only, not the project table.
- The top-factories source fallback through a machine is never exercised.
- An expense-only vendor with an empty name is never built.

The spec also does not say what an empty item unit gives (it is `None` today).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_stats` R8 (TI cards) | `item_name` / `item_unit` is asserted only for PO-line items (TI-01, TI-06). Nothing checks the name/unit of an item that appears only on transfer or sales lines, or an empty-named item first seen there. | Mutants #53, #54, #57, #58, #84, #85, #90, #91, #142, #143, #145, #146 (L377, L378, L404, L405) survive | case designer |
| 2 | case-missing | `get_stats` R10 | No card shows that sales orders never count in top vendors (vendors = POs + expense orders only). This is the OQ-30/31 "spend split from revenue" boundary. | Hand variant `vendor_plus_sales` (customer revenue merged into vendor spend) passes all 95 pass tests | case designer |
| 3 | case-missing | `get_stats` R13 | A soft-deleted account keeps its vendor row. TV-04 checks this only for an expense order, not for a PO vendor. | Hand variant `vendors_exclude_deleted_acct` (PO vendor query drops deleted accounts) survives; the expense-side variant is killed by TV-04 | case designer |
| 4 | case-missing | `get_stats` R13 | No expense-only vendor with an empty name. Today that falls back to "Account #id"; a broken fallback key is not noticed. | Mutant #193 (L474 `['name']` → `['']`) survives | case designer |
| 5 | case-missing | `_filter_po_by_factory` R4, `_filter_transfer_by_factory` R3 | "A project of another factory is dropped" has no pass card. Possible design that holds before and after BUG-2503: destination id X where project X and component X both belong to F2, filtered by F1, gives `[]`. | Mutants #62 (L71), #64 (L113) survive | case designer |
| 6 | case-missing | `_filter_po_by_factory` R4, `_filter_transfer_by_factory` R3 | "The destination type decides which table the id means" is pinned for the machine table only (FP-03). No card has a storage destination whose id equals a project id of the factory. | Mutants #163 (L60), #226 (L91) survive | case designer |
| 7 | case-missing | `_build_top_factories` R3 | Source fallback is covered only for a storage source (TF-05). No card has the destination unresolved and the source a machine of a factory. | Mutant #244 (L242 `'machine'` → `''`) survives | case designer |
| 8 | case-missing (minor) | HR-15 / `get_stats` R4 exactness | The exact-sum cards (TI-02, TF-02, TV-02, TC-01) use values whose float sum prints the same as the Decimal sum (0.05 + 1234.56). A float accumulator is not noticed. A pair like 0.10 + 0.20 would catch it. | Hand variant `float_sum` survives | case designer |
| 9 | spec-gap | `get_stats` R8 | `Item.unit` is NOT NULL but may be `""`. Today `"" or None` gives `item_unit = None`. No rule says so, so no case can pin it. | Mutants #130 (L319), #140 (L350) survive (an empty unit raises `KeyError` under them) | describer (fill-gaps) |
| 10 | case doc (minor) | cases `## Spec gaps` row 1, Coverage matrix | Spec round 3 closed gap 1 with `_build_top_factories` R8b. The cases file still lists the gap as open and the matrix does not cite R8b for FV-08 / FV-09. | cases lines 3066-3069, 3150 | case designer |
| 11 | case doc (minor) | OQ29-06, 07, 12, 13, 16, 17, OQ30-08 Expect lines | These cards pass only with a second fix (BUG-2500 / 2481 / 2501, as the notes list). Their Expect line names only BUG-2480 / 2481, so the marker reason does too. The notes carry the real list; the card should as well. | notes "Cards that need two fixes" | case designer |
| 12 | notes (minor) | notes "Verification runs" first bullet | Still says "67 xfailed" (revision 2). The Result line and Revision history give the correct 69 + 1. | notes line 23 | executor |

No unfaithful test. No fidelity finding.

**OOV-TE-05 / OOV-TC-06 non-strict: justified.** Both cards order ties that are cut in SQL. With no `ORDER BY` tie term, the row order is up to Postgres, so a strict marker would flake. TE-05 xpasses today by chance (text order) and TC-06 fails today. Each has a strict alarm, TE-06 / TC-07, which asserts the tie term in the `ORDER BY` and fails today on its Then 3 as designed.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 14, 30 | L344 | negate if / `IsNot → Is` (PO lines factory filter) | bug-path | With `factory_id=None`, `_filter_po_by_factory(q, None)` keeps every row: at most one of the machine / project outer joins matches, so an `IS NULL` term is always true (hand variant `items_filter_none` passes too). With a `factory_id` the call crashes at L506 (BUG-2502), so it is reached only by the xfail FV cards. | — |
| 15, 31 | L372 | same (transfer lines) | bug-path | Same argument (`transfers_filter_none` passes). | — |
| 17, 33 | L450 | same (PO vendors) | bug-path | Same argument (`vendor_filter_none` passes). | — |
| 89 | L400 | `Eq → NotEq` (sales lines factory filter) | bug-path | Factory view only; crashes at L506 (BUG-2502). | — |
| 101 | L506 | `Eq → NotEq` | bug-path | The BUG-2502 line itself; it raises before the comparison matters. | — |
| 67, 106 | L130 | `'project'` branch `Eq → NotEq` / `''` | bug-path | Today the project branch resolves only through the BUG-2503 lookup (project id). Only TF-30 … 32 (xfail) target it. | — |
| 199 | L60 | `'project'` → `''` | bug-path | Disables the project join in the PO filter. Observable only on project destinations (BUG-2503; FP-07 / 08 xfail). | — |
| 242 | L91 | `'project'` → `''` | bug-path | Same for the transfer filter (FT-06 xfail). | — |
| 227 | L92 | `Eq → NotEq` (transfer dest project id) | bug-path | Only project-type destinations join, and those are BUG-2503 cards only. | — |
| 229, 243 | L195, L194 | `Eq → NotEq` on the id / `'project'` → `''` (top factories PO project join) | bug-path | Project destinations only (TF-30, TF-31 xfail). | — |
| 257, 261 | L236, L235 | same (top factories transfer dest project join) | bug-path | Project destinations only (TF-32 xfail). | — |
| 228 | L194 | `destination_type == 'project'` → `!=` | equivalent | The joined project factory is used only by the `CASE` arm `type == 'project'` (L130). A non-project row that joins a project is never read, and each PO still joins at most one project. | — |
| 256 | L235 | same (transfer dest) | equivalent | Same `CASE` re-check (L130 via `dest_factory`). | — |
| 230 | L242 | `source_location_type == 'machine'` → `!=` | equivalent | The `CASE` reads the source machine factory only when the type is `'machine'` (L129). A non-machine source that joins a machine by id is never read. | — |
| 155, 194 | L455, L476 | `count or 0` → `or 1` | equivalent | `count(id)` of a non-empty `GROUP BY` group is ≥ 1, never 0 or `NULL`. | — |
| 221 | L512 | same (customers) | equivalent | Same. | — |
| 240 | L537 | same (categories) | equivalent | Same. | — |
| 53, 54, 57, 58 | L377, L378, L404, L405 | `name or …` → `and` | case-missing | Finding 1. | case designer |
| 84, 85, 90, 91 | same lines | written key → `''` | case-missing | Finding 1. | case designer |
| 142, 143, 145, 146 | same lines | read key → `''` (`KeyError` for an empty name / unit) | case-missing | Finding 1. | case designer |
| 62, 64 | L71, L113 | `dest_project.factory_id == factory_id` → `!=` | case-missing | Finding 5. | case designer |
| 163, 226 | L60, L91 | `destination_type == 'project'` → `!=` in the filters (there is no `CASE` re-check) | case-missing | Finding 6. | case designer |
| 244 | L242 | `'machine'` → `''` (source machine join) | case-missing | Finding 7. | case designer |
| 193 | L474 | `vendor_map[id]['name']` read → `['']` | case-missing | Finding 4. | case designer |
| 130, 140 | L319, L350 | `'item_unit'` key → `''` | spec-gap | Finding 9. | describer |

Counts: 7 equivalent · 17 bug-path · 18 case-missing · 2 spec-gap = 44.

## Hand variants (own plugin `oo_var.py`, in process, pass-expected tests only)
54 variants. Killed unless noted:
- **Workspace filter dropped** (W0/W2 rows on both sides), one query at a time — all 11 queries killed (GS-09, GS-10, GS-15, TF-09).
- **Date-window edges** — killed: created_at not cast to a date (transfer / work / transfer lines: TF-11, TF-13, TI-10); PO report day without cast, `created_at` only, `order_date` only (RD-01, RD-02, TI-09 …); half-open range (14 cards).
- **Rounding** — half-up and half-even quantize in `_dec` killed (D-03, D-04). Nothing is rounded here. **Float accumulation: survived** (Finding 8).
- **Spend that includes sales: survived** (customer revenue merged into vendors, Finding 2). The item / factory mixing is today's code (BUG-2481, xfail).
- **Sort keys / tie-breaks / cut** — killed: spend-first or negated spend for items, cut before sort (items, vendors), vendors by count, customers by count or id, categories by count or text, factories by value or count only, no cut, limit clamp 5, no lower clamp. Tie-break order itself is BUG-2505 (xfail; TC-07 / TE-06 alarms).
- **Voided / deleted counted** — this is today's behavior (BUG-2500 / 2501, xfail only). Killed: inactive factory names dropped (TF-18), deleted account dropped from expense vendors (TV-04) and customers (TC-02). **Survived: deleted account dropped from PO vendors** (Finding 3).
- **Joins and other** — killed: free-text sales line counted (TI-05), transfer source before destination (TF-04), inactive machine excluded (FP-04), transfer filter dest-only / no source machine (FT-01, FT-02, FT-03), NULL cost skips a work order (TF-07), NULL subtotal skips a line (TI-03), transfer quantity added to spend (TI-04), expense vendors dropped (TV-02 …).
- **Survived, but equivalent:** project source using the destination project alias (`transfer_src_project`); the factory filter with `None` (`items_ / transfers_ / vendor_filter_none`, same as mutants #14 … #33); `vendor_join_any_po_dest_machine` is a no-op variant (a control).
- **Not applicable here:** committed vs projected boundaries per order kind (BUG-2480 not implemented; every split card is a strict xfail that fails on the first `…_committed` read); "last status" by name vs sequence (OQ-32 belongs to item_orders; the D4 stage names are BUG-2480 only); unit price over all quantity (OQ-33, another module); notifier variants (no notifier).

## Traceability
cases 165 · tests 165 · unmatched: none · duplicate IDs: none · marker mismatches: none. 95 pass cards have no marker. 66 strict xfails use `bug(n)` / `BUG_2502` naming their Expect line's BUG. FV-08 / FV-09 use `BUG_2502_2504` (reason names both, `raises=(InvalidRequestError, AssertionError)`). TC-06 / TE-05 use `strict=False`, as their Expect lines say. Every BUG used (2480, 2481, 2500–2506) exists in `bugs.md`. ruff clean; LF only.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov.oo .venv/Scripts/python.exe -m pytest tests/unit/services/test_orders_overview_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.orders_overview_service --cov-branch --cov-report=term-missing
  → 95 passed, 69 xfailed, 1 xpassed · 99% (518->542, 543->548)
… --runxfail -rf            → 69 failed, 96 passed
… -rxX (run 2)              → 95 passed, 69 xfailed, 1 xpassed
… -rxX (run 3)              → 95 passed, 69 xfailed, 1 xpassed
… --runxfail --junitxml + own xcheck.py (maps each failure to its `# Then N` block) → 69/69 fail where the card says; FV-01 … 09 in the When with InvalidRequestError; OQ29 cards on the first split field (AttributeError); OOV-TE-05 passes (non-strict, by chance)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/orders_overview_service.py tests/unit/services/test_orders_overview_service.py --json <scratch>/mut_oo.json
  → Mutants: 265 · killed 221 · timeout 0 · survived 44
OO_VAR=<v> PYTHONPATH=<scratch>/oo pytest … -p oo_var -m "not xfail"   (54 variants, results above)
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_orders_overview_service.py → All checks passed
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv\` (`run_oo_*.log`, `mut_oo.{log,json}`, `oo\trace.py`, `oo\xcheck.py`, `oo\oo_var.py`, `oo\runvars.py`, `oo\vars.out`).

## Round 2 — 2026-11-10

> **Verdict:** PASS
> Tests: 110 passed · 69 xfailed + 1 xpassed (non-strict OOV-TE-05) (reproduced ✅ ×3) · coverage 99% branch (158 stmts, 48 branches, 2 partial: 518->542, 543->548)
> Targeted mutation (the lines that had real-gap survivors): 27 mutants · 25 killed · 2 survived, both bug-path from round 1 (#199 L60, #242 L91)
> Implied full-file score: 242 / 242 = 100% (265 total, after excluding 6 equivalent, 0 dead, 17 bug-path)
> Cases revision: 4 · Source commit: e48a092 (app/ unchanged)

### What was checked
- **Fidelity of the new and changed tests**, each read against its card. Every Given row is built (helpers checked: `mk.to` default = F2 storage → F1 storage, `mk.so` default account AC1, `deleted_account` = `is_deleted True, is_active False, deleted_at T0, deleted_by U1`, `stats()` = the cards' default call). Every Then line is asserted exactly, in card order. Nothing is weakened, mocked or swallowed. Cards checked:
  - new: TI-18, TI-19, TI-20, TI-21, TV-14, TV-15, TV-16, TV-17, FP-10, FP-11, FT-08, FT-09, TF-35, TF-36, TC-08
  - changed Expect lines and markers: OQ29-06, 07, 12, 13, 16, 17, OQ30-08, FV-08, FV-09
- **Markers.** The seven multi-bug cards use `@bugs(...)` (strict). The reason names every BUG ID on the card's Expect line, in the card's order:
  - OQ29-06, 16, 17: BUG-2480, 2500
  - OQ29-07, 12: BUG-2480, 2481
  - OQ29-13: BUG-2480, 2481, 2500, 2501
  - OQ30-08: BUG-2481, 2480

  FV-08 / FV-09 keep `BUG_2502_2504`, and the cards now cite R8b. My round-1 `trace.py` reports these seven as "XFAIL-missing" only because it does not parse `bugs(...)`. Read by hand, they are correct.
- **Traceability:** cases 180 · tests 180 · pass-expected 110 · unmatched: none · marker mismatches: none.
- **`--runxfail`:** 69 failed, 111 passed. `xcheck.py` maps every failure to its `# Then N` block: all 69 fail on the Then line (or the When, FV-01…07) that the card names. `bad 0`. The 111 passes are the 110 pass cards plus the non-strict TE-05.
- **Round-1 cases-doc findings 10 and 11** are fixed. Spec gaps reads "None" (R8b, R8c closed). FV-08/09 cite R8b. The multi-bug Expect lines are complete. Finding 9 (spec gap) is closed by `get_stats` R8c and pinned by TI-20.
- **Notes finding 12** is fixed: the "Verification runs" bullet now reads 69 xfailed + 1 xpassed. The Result line matches my runs. `ruff check` is clean, and the file has 0 CR bytes.

### Round-1 survivors, targeted re-run
| Round-1 # | Line | Mutation | Round 1 class | Round 2 |
|---|---|---|---|---|
| 53, 54, 57, 58 | L377, L378, L404, L405 | `or` → `and` | case-missing | killed (TI-18 / TI-19) |
| 84, 85, 90, 91, 142, 143, 145, 146 | same lines | key → `''` | case-missing | killed |
| 62 | L71 | `==` → `!=` | case-missing | killed (FP-10) |
| 64 | L113 | `==` → `!=` | case-missing | killed (FT-08) |
| 163 | L60 | `==` → `!=` | case-missing | killed (FP-11) |
| 226 | L91 | `==` → `!=` | case-missing | killed (FT-09) |
| 244 | L242 | `'machine'` → `''` | case-missing | killed (TF-36) |
| 193 | L474 | name key → `''` | case-missing | killed (TV-16) |
| 130 | L319 | `'item_unit'` → `''` | spec-gap | killed (TI-20) |
| 140 | L350 | `'item_unit'` → `''` | spec-gap | killed (TI-20) |
| 230 | L242 | `source_location_type == 'machine'` → `!=` | **equivalent (wrong)** | killed (TF-36) |
| 199 | L60 | `'project'` → `''` | bug-path | survives, still bug-path (pass cards FP-10/11 drop the order either way) |
| 242 | L91 | `'project'` → `''` | bug-path | survives, still bug-path (FT-08/09 likewise) |

I correct one of my own round-1 calls. I classed #230 as equivalent, but TF-36 kills it, so it was not equivalent: the source-machine join is not re-checked by the `CASE` in every path. The equivalent count is therefore 6, not 7. Nothing is routed for this, because the mutant is now killed.

The targeted run also covers the remaining mutants on those lines: L60 `==`, L350 `or`, L474 `or`, plus a second `'item_unit'` key at L350. All are killed. Lines not re-run keep their round-1 kills: app/ is unchanged and the test file only gained tests.

### Hand variants re-run (round-1 plugin `oo\oo_var.py`, pass-expected tests only)
| Variant | Round 1 | Round 2 |
|---|---|---|
| `vendor_plus_sales` (sales counted in vendor spend) | survived | killed by TV-14 |
| `vendors_exclude_deleted_acct` (deleted PO account dropped) | survived | killed by TV-15 |
| `float_sum` (float accumulation) | survived | killed by TI-21 |
| `transfer_src_project`, `vendor_join_any_po_dest_machine`, `vendor_filter_none`, `items_filter_none`, `transfers_filter_none` | survived (equivalent) | survive (still equivalent, as argued in round 1) |

### Findings (round 2)
None.

### Commands run (round 2)
```
COVERAGE_FILE=<lowsupv>\r2\.cov.oo .venv/Scripts/python.exe -m pytest tests/unit/services/test_orders_overview_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.orders_overview_service --cov-branch --cov-report=term-missing
  app\services\orders_overview_service.py  158 0 48 2 99%  518->542, 543->548  →  110 passed, 69 xfailed, 1 xpassed
(plain ×2) → 110 passed, 69 xfailed, 1 xpassed · 110 passed, 69 xfailed, 1 xpassed   (XPASS each time: OOV-TE-05)
.venv/Scripts/python.exe -m pytest … --runxfail -rf --junitxml=<lowsupv>\r2\rx_oo.xml → 69 failed, 111 passed
.venv/Scripts/python.exe <lowsupv>\oo\xcheck.py <cases> <test> <lowsupv>\r2\rx_oo.xml → bad 0
.venv/Scripts/python.exe <lowsupv>\oo\trace.py <cases> <test> → cases 180 tests 180 pass 110 (7 "XFAIL-missing" = `bugs(...)` not parsed; checked by hand)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/orders_overview_service.py tests/unit/services/test_orders_overview_service.py --lines <r> --json <lowsupv>\r2\mut_oo_<r>.json
  for r in 60-60 71-71 91-91 113-113 242-242 319-319 350-350 377-378 404-405 474-474
  → 27 mutants · 25 killed · 2 survived (L60:54, L91:63 'project' → '', bug-path)
.venv/Scripts/python.exe <lowsupv>\oo\runvars.py <8 variants> > <lowsupv>\r2\oo\vars_r2.out
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_orders_overview_service.py → All checks passed
```
