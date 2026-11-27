# Verification — `app/managers/purchase_order_return_manager.py`

> **Verdict:** PASS
> Tests: 104 passed · 42 xfailed (reproduced ✅; 40 strict, 2 non-strict as the cards say) · coverage 100% branch (47 statements, 12 branches)
> Mutation: 41 mutants · 41 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 33 run · 21 killed · 12 survived, all expected (1 control, 6 intended-fix, 4 bug-path, 1 equivalent)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Every one of the 146 cards has exactly one test, every expectation matches its marker, and every xfail fails on the Then line its card names (checked by my own plugin, 42/42). Every mutant of the manager is killed. I also ran 33 hand-written variants of the manager and of the `quantity_available_to_return` model property it relies on. They covered returnable quantity, repeated lines, decimals, price bounds, unpriced lines, locks, workspace isolation with W0 and W2, and the `paid` sync. Every wrong variant was caught, except those on paths that are logged bugs (BUG-2750, BUG-2751, BUG-2752, BUG-2787) and one equivalent. Variants that apply the intended fixes leave every pass test green, so no pass card pins a bug. No new bug was found. There is one non-blocking spec wording note for the describer.

## Findings
None.

Non-blocking note (does not change the verdict):

| # | Kind | Case / line | What | Evidence | Fix by |
|---|---|---|---|---|---|
| N1 | spec wording | spec OQ-47 "Suggested answer" | The refusal text there says "its goods have already **gone back**". The binding rule (`account_invoice_manager.spec.md` `void_invoice` R3c, Errors row) and the cards (Q47-07, and the twin SORM-Q47-07) say "its goods have already **moved**". The rule and the tests agree. Only the question's historical text differs. | spec line 77 vs `account_invoice_manager.spec.md` line 739 | describer (optional touch-up; leave it if suggested-answer text is kept verbatim) |

## Surviving mutants
None (41/41 killed by `mutate.py`).

### Hand variants (my plugin `retprodv/po/variants.py`, run with `-m "not xfail"`)
| Variant | What it changes | Result | Class |
|---|---|---|---|
| baseline_vb | reimplementation equal to today (control) | survived | control |
| avail_intended_once | BUG-2750 fixed: received − pending | survived | intended-fix (pass cards hold today and after) |
| avail_ws_filtered | BUG-2792 fixed: only this workspace's lines reserve | survived | intended-fix |
| running_total | BUG-2751 fixed: running total per order line | survived | intended-fix |
| price_bounds | BUG-2785 fixed: 0 ≤ price ≤ line price | survived | intended-fix |
| unpriced_required | BUG-2787 fixed: price required on an unpriced line | survived | intended-fix |
| avail_triple_count | completed lines also reserve (counted 3×) | survived | bug-path: BUG-2750 region. The pass cards V-16 and V-19 deliberately check only "starts with". V-14/15/17/18/20 (xfail) pin the number and will catch it once the bug is fixed |
| running_total_grand_msg | message shows the grand total, not the running total | survived | bug-path BUG-2751 (V-56) |
| price_default_zero | an unpriced line with no price returns `0` instead of `None` | survived | bug-path BUG-2787 (Q46-01). No pass card can pin today's `None` |
| quantize_qty_even | quantity rounded half even to 2 dp in the check and the dict | survived | bug-path BUG-2752 (cards never send 3 dp to the manager, by design) |
| sync_always_write | assigns `paid` even when unchanged | survived | equivalent: same value, so no UPDATE is emitted and the object is clean after the flush |
| avail_voided_reserve | voided returns reserve | killed (V-09) | — |
| avail_minus_refunded | refunded quantity also subtracted | killed (V-13) | — |
| avail_no_floor / avail_floor_0_00 | no `max(0, …)` / floor prints `0.00` | killed (V-41) | — |
| ge_compare | `>=` instead of `>` | killed (V-03) | — |
| zero_price_unset | a sent price of `0` treated as not sent | killed (Q45-02) | — |
| price_bounds_off_by_one | lower bound 0.01 (0 refused) | killed (Q45-02) | — |
| no_ws_lines | order lines read without the workspace filter | killed (V-34) | — |
| dict_item_from_request | wrong `item_id` in the dict | killed (V-01) | — |
| skip_unknown | unknown line skipped instead of refused | killed (V-28) | — |
| get_return_lock | `FOR UPDATE` on the default read | killed (G-09) | — |
| get_return_no_ws | `session.get` without a workspace | killed (G-06) | — |
| has_open_no_ws / has_open_not_voided | no workspace filter / completed counts as open | killed (HO-06 / HO-03) | — |
| list_lock / list_asc | lock on the list / oldest first | killed (L-06 / L-01) | — |
| sync_no_ws | credit note looked up without a workspace | killed (S-09) | — |
| sync_partial_counts | `partial` counts as paid | killed (S-02) | — |
| sync_sets_voided | sync also voids a pending return | killed (Q47-01) | — |
| sync_no_flush / sync_commit / sync_touch_updated_by | no flush / commits / writes `updated_by` | killed (S-01 / S-14 / S-01) | — |

Some variants do not apply to this module: HR-15 restock and ledger values, average cost, `make_sellable`, the stocked-row flip and the cost fallback order. This manager does no money arithmetic, has no ledger or stock writes, and its messages echo only ids and line numbers, never item names. The credit-note void runs through the real `void_invoice` in Q47-03 … Q47-08. Today's part (Q47-08, already voided) passes. The pending and completed outcomes are strict xfails (BUG-2788), confirmed by `--runxfail` to fail on the named Then line.

## Traceability
Cases 146 · tests 146 · unmatched: none · duplicate IDs: none · marker mismatches: none. 42 xfail: 40 `strict=True`, plus G-14 and L-09 `strict=False`, as their cards say (non-strict). Every reason names the card's BUG ID and nothing else. Every BUG ID exists in `docs/testing/bugs.md`. Fidelity: all 146 tests read against their cards (Given, When, every numbered Then line, in order). No missing, weakened or changed assertion. No in-memory-only write check: S-* and Q47-* re-read through `expire_all` + SELECT. No swallowed failure, and no mock: only the commit spy (`wraps`) that S-14 prescribes, and the real `void_invoice`. Executed in normal mode, so no local-coder tests.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_purchase_order_return_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.purchase_order_return_manager --cov-branch --cov-report=term-missing
  → 104 passed, 42 xfailed · app\managers\purchase_order_return_manager.py 47 0 12 0 100%
.venv/Scripts/python.exe -m pytest … -q -p no:cacheprovider -o addopts=""   (×2 more)
  → 104 passed, 42 xfailed · 104 passed, 42 xfailed   (no flakes)
.venv/Scripts/python.exe -m pytest … -q -p no:cacheprovider -o addopts="" --runxfail -rf
  → 42 failed, 104 passed (every xfail fails; G-14 / L-09 fail today too)
.venv/Scripts/python.exe -m pytest … --runxfail -p failson   (own plugin: failing line → `# Then N` block)
  → 42/42 fail on the card's "Fails today on" line (call-raises cards on the When call)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/purchase_order_return_manager.py tests/unit/managers/test_purchase_order_return_manager.py --json …/retprodv/mut_po.json
  → Mutants: 41 · killed 41 · timeout 0 · survived 0 · score 100%
VARIANT=<v> .venv/Scripts/python.exe -m pytest … -m "not xfail" -p variants -x   (33 variants, own plugin)
  → see Hand variants table
```
Scratch (own scripts and outputs; private COVERAGE_FILEs): `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprodv\po\` (`trace.py`, `failson.py`, `cmpfails.py`, `variants.py`, `var\*.txt`, `run*.txt`).

## Round 2 — 2026-11-19

> **Verdict (Round 2, RR cards):** PASS — PORM-RR-01 … RR-35 are faithful; the verifier's own reference passes all 35; all 13 hand variants killed.
> Tests: 104 passed · 77 xfailed (75 strict, 2 non-strict) · cases revision 3 · source commit e48a092 (app/ unchanged, so the Round 1 mutation result stands: 41/41).

**Scope.** Narrow round on the 35 new cards for `validate_replacement_receipt` (BUG-2810, spec RR1–RR8) and the schema `PurchaseOrderReturnReplacementCreate`. The 146 Round 1 tests were not re-audited.

**Fidelity.** Read every RR test against its card: Given steps (L1 6.00/4.00, `replace` + completed, `quantity_replaced`, W0/W2 lines, W0/W2 callers, STC on O2, expunge + reload in RR-30), the When call, and every numbered Then (`==` on status/detail, exact RTOO/NOTPART text, `session clean`, `counts` for "nothing written", `snap` for `unchanged`, re-reads in RR-30, recorder started at the When). All 35 are `xfail(strict=True, reason=X2810)`, and BUG-2810 exists in `bugs.md`. No extra mocks, no try/except, no weakened checks. **Findings: none.**
- DISCREPANCY-1 (26 cards fail on the in-test `ImportError` before the call, not on the named `AttributeError`) is card wording only and already with the case designer. Confirmed: with `--runxfail` and no patch, all 35 fail.

**Own reference** (`retprodv/po/rr_ref.py`, written independently of the executor's plugin). It adds the schema (`quantity` gt 0, max_digits 15, decimal_places 2; `items` min_length 1; `notes` optional), adds the `quantity_replaced` column to the model and, per test, to the table (`ALTER TABLE … ADD COLUMN IF NOT EXISTS` inside the rolled-back transaction; runs made alone), and adds `validate_replacement_receipt` per RR1–RR8: type, then status, then lines in request order filtered by `return_id` and `workspace_id`; running total + `quantity_replaced` against `quantity_returned`; `left` floored to `0`; cost = PO line price, else return line price; no writes.
- `--runxfail -k porm_rr_` → **35 passed**. Pass tests with the plugin loaded (`-m "not xfail"`) → 104 passed (the added column breaks nothing).

**Hand variants** (each run alone, `--runxfail -k porm_rr_`; killed = at least one RR test fails):

| Variant | Result | Killed by |
|---|---|---|
| limit ignores `quantity_replaced` | killed | RR-06, 07, 09 |
| no running total (each entry checked alone) | killed | RR-08, 09 |
| `>=` instead of `>` at the limit (equal refused) | killed | RR-01, 05, 10, 29 |
| return-line price wins over PO-line cost | killed | RR-02, 27 |
| refund type accepted (RR1 dropped) | killed | RR-11, 14 |
| pending accepted (only voided refused) | killed | RR-12, 15 |
| no workspace filter on the return lines | killed | RR-19, 20, 21, 22 |
| write during the check, flushed (`quantity_replaced += q`) | killed | RR-08, 09, 10, 30 |
| write during the check, left dirty | killed | RR-08, 09, 10, 23, 25, 30 |
| `left` not floored (prints `0.00`) | killed | RR-07 |
| lines checked before the status | killed | RR-15, 24 |
| all "not part" checks before any quantity check | killed | RR-24 |
| message total includes already replaced | killed | RR-06, 07, 08, 09, 24 |

**Routed.** Executor: none. Case designer: DISCREPANCY-1 wording (already open). Describer: none. No new bug.

**Commands (Round 2)**
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_purchase_order_return_manager.py -q -p no:cacheprovider -o addopts=""
  → 104 passed, 77 xfailed
.venv/Scripts/python.exe -m pytest … -o addopts="" --runxfail -k porm_rr_ -rf            → 35 failed (no patch)
PYTHONPATH=retprodv/po RR_VARIANT=ref .venv/Scripts/python.exe -m pytest … -o addopts="" -p rr_ref --runxfail -k porm_rr_
  → 35 passed, 146 deselected
PYTHONPATH=retprodv/po .venv/Scripts/python.exe -m pytest … -o addopts="" -p rr_ref -m "not xfail"  → 104 passed
RR_VARIANT=<v> (13 variants above), same command                                          → each 1–6 failed
```
