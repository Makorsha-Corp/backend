# Verification — `app/managers/order_template_manager.py`

> **Verdict:** PASS (round 2, 2026-11-09; round 1: NEEDS WORK)
> **Current verdict (round 2): PASS** — cases revision 3, 111 passed · 94 xfailed; round-1 Finding 1 resolved (see Round 2)
> Tests: 110 passed · 93 xfailed (reproduced ✅) · coverage 100% branch (84 statements, 18 branches)
> Mutation: 87 mutants · 81 killed · 6 survived → score 100% (after excluding 4 equivalent, 0 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests can be trusted. All 203 cards are implemented faithfully, one test per card. Every xfail fails on the Then line its card names. The runs match the notes and are stable. Every mutant that survived is equivalent or on a bug path.

I also ran 18 hand-written variants of the intended fix and 1 of today's code, for money, ownership, refusal order and workspace scoping. One of them is not caught: an update-item total check that runs only when the price is sent. No card sends a quantity-only update whose merged total overflows. That is a one-sided boundary for BUG-2349, so it goes to the case designer. Nothing in the tests themselves has to change.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_item` R4a (BUG-2349), source L126–129 | R4a's overflow refusal on the merged total is tested only by sending a new price (UI-24, UI-25, UI-26). No card sends a new **quantity** onto a stored price whose product is 10^13 or more. A fix that checks the total only when `unit_price` is sent passes every card. | Variant `tot_priceonly` (my plugin, `--runxfail`): nothing new fails compared with the reference fix. | **case designer**: add an xfail BUG-2349 card, e.g. a stored price of 1 000 000 000.00 and quantity 10000 sent → 422 `LTL`, `not db.dirty`, unchanged(L). Optionally add its just-below pair: stored price 9900990099009.89 and quantity 1.01 sent → subtotal 9999999999999.99. |

There are no fidelity findings. I read every card against its test, line by line, covering Given, When, each numbered Then line in order, the session checks before re-reads, the snapshots taken after the last Given line, and the commit spy. Nothing is mocked beyond the convention's commit spy, there is no `try/except`, and every `pytest.raises` names `HTTPException` or `ValidationError` as its card does.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 53 | L62:52 | `exclude_unset=True` → `False` (`update_template`) | equivalent | Every `OrderTemplateUpdate` field defaults to `None`, so with `exclude_none=True` still set the unset fields are dropped anyway. The resulting dict is the same. | — |
| 54 | L62:71 | `exclude_none=True` → `False` (`update_template`) | bug-path | An explicit `null` then reaches the row. That is the BUG-2357 direction, seen only by its xfail cards (UT-13 … UT-15), and those are excluded from the run. No pass card sends an explicit `null`. | — |
| 56 | L124:52 | `exclude_unset=True` → `False` (`update_item`) | equivalent | Every `OrderTemplateItemUpdate` field defaults to `None` and is dropped by `exclude_none`, so the dict is the same. | — |
| 57 | L124:71 | `exclude_none=True` → `False` (`update_item`) | bug-path | Same as #54, for lines: BUG-2358 (UI-16, UI-17), xfail only. | — |
| 69 | L110:52 | `.get('quantity', 1)` → `2` (`add_item`) | equivalent | `model_dump()` always contains `quantity` (schema default `1`, not nullable), so the fallback is never used. | — |
| 75 | L45:56 | `.get('quantity', 1)` → `2` (`create_template`) | equivalent | Same as #69. | — |

## Hand variants (verifier's own plugin, in-process, `--runxfail`)
I wrote my own plugin for this: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otmgr\plug\vrt_otm.py`. Its reference fix covers the BUG-2347 owner check, the BUG-2349 total check (schema validator plus manager 422), BUG-1226, and recompute from sent-or-stored values. With the reference fix, all 13 BUG-2347 cards, all 4 BUG-2349 cards and UI-15 pass, and every pass card stays green. Each variant changes one thing. The "caught by" column lists the tests that fail under the variant but pass under the reference.

| Variant | Caught by |
|---|---|
| HR-15 half-even subtotal (`quantize(ROUND_HALF_EVEN)`) | CT-07, AI-10, UI-07 (pass cards) |
| BUG-2349 compares the unrounded product | CT-58, UI-26 |
| BUG-2349 limit `> 10^13` (off by one) | CT-57, UI-24, CT-58, UI-26 |
| BUG-2349 limit `>= 10^13 − 0.01` (off by one the other way) | CT-13, CT-52, CT-59, UI-25 |
| BUG-2349 checked only when the price is sent | **not caught**: Finding 1 |
| Subtotal recomputed on every update | UI-04 |
| Recomputed only when quantity is sent | UI-02, UI-08, UI-09 (+ UI-15, UI-24 … 26) |
| Update ignores the sent quantity | UI-01, UI-03, UI-07, UI-10 |
| Update ignores the stored price | UI-01, UI-07, UI-10 |
| Owner = an owner row in **any** workspace (W0/W2) | Q22-09, Q22-10, Q22-17 |
| Owner row counted whatever its status (suspended) | Q22-08 |
| `owner_user_id` of any workspace | Q22-11 |
| Owner check placed **after** the write | CT-62, UT-43, Q22-01, 02, 04, 05, 08 … 11, 13, 14, 17 |
| Only `requires_approval` checked | Q22-02, Q22-05, Q22-10 |
| Any sent flag refused, even the stored value | Q22-15 |
| Only switching approval off is refused | Q22-13 |
| Refusal order: missing cost centre before the 403 | CT-62, UT-43 |
| Workspace scoping dropped on template and line lookups | UT-04, UT-05, UT-42, GT-04, GT-05, DT-03, DT-04, AI-08, AI-09, UI-12, UI-13, RI-03, RI-04 |

## Traceability
Cases 203 · tests 203 · every case ID appears exactly once (under `# [claude] <ID>`, in the test name and in the docstring). No test lacks a case ID. Marker mismatches: none. All 93 xfails are `strict=True` and name the card's bug in the reason. Every BUG ID used is in `docs/testing/bugs.md`. No `local-run.json`, so all tests are Claude-written.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov .venv/Scripts/python.exe -m pytest tests/unit/managers/test_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.order_template_manager --cov-branch --cov-report=term-missing
  app\managers\order_template_manager.py  84 0 18 0 100%  ·  110 passed, 93 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_order_template_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  93 failed, 110 passed
PYTHONPATH=<scratch> VFAIL_OUT=<scratch>/vfail.json ... --runxfail -p vfail   (own plugin: failing line -> "# Then N")
  failed 93 · mismatch with card "Fails today on" 0 · Failed 74, AssertionError 15, IntegrityError 2, DataError 2
plain run x2 more: 110 passed, 93 xfailed (both)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/order_template_manager.py tests/unit/managers/test_order_template_manager.py --timeout 300 --json <scratch>/mut.json
  Mutants: 87 · killed 81 · timeout 0 · survived 6 · score 93%
VRT=<variant> PYTHONPATH=<scratch>/plug ... --runxfail -p vrt_otm   (19 runs: the reference plus 18 variants, table above)
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otmgr\`.

## Round 2 — 2026-11-09

> **Current verdict (round 2): PASS**
> Tests: 111 passed · 94 xfailed (reproduced ✅, 3 runs identical) · coverage 100% branch (84 statements, 18 branches)
> Mutation: not re-run (source unchanged at e48a092; the round-1 mutants all stay killed or classified; no new survivor class possible from added tests) · Cases revision: 3

**What changed.** Cases revision 3 adds two cards for round-1 Finding 1 (case-missing, `update_item` R4a, BUG-2349): OTMG-UI-27 (strict xfail BUG-2349) and OTMG-UI-28 (pass). No card was changed or retired; the rest of the test file is unchanged.

**Fidelity of the new tests.**
| Case | Check | Result |
|---|---|---|
| OTMG-UI-27 | Given: line 1 with quantity 1.00, price 1 000 000 000.00, subtotal 1 000 000 000.00 · When: only `quantity=10000` sent · Then 1–5: `pytest.raises(HTTPException)`, `status_code == 422`, `detail == LTL`, `not db.dirty`, `not db.new`, `snap(L) == before` | faithful; marker `@BUG_2349` (`strict=True`, reason names BUG-2349) |
| OTMG-UI-28 | Given: price 9900990099009.89, quantity 1.00 · When: only `quantity=1.01` sent · Then 1: `result.id == L.id` · Then 2: re-read `quantity == 1.01`, `unit_price == 9900990099009.89`, `line_subtotal == 9999999999999.99` (exact `==`) | faithful; no marker |

`--runxfail`: UI-27 fails on Then 1 (line 3143, the call inside `pytest.raises`) with `sqlalchemy.exc.DataError` 22003 `numeric field overflow`, as its "Fails today on" says. UI-28 passes.

**Round-1 survivor confirmed killed.** Variant "BUG-2349 total checked only when the price is sent" (`VRT=tot_priceonly`, own plugin `tplv\otmgr\plug\vrt_otm.py`) against the reference fix: reference 73 failed / 132 passed; variant 74 failed / 131 passed. The only extra failure is OTMG-UI-27. UI-28 stays green under both, so the just-below boundary holds.

**Traceability.** Cases 205 · tests 205 · each ID once · no marker mismatch · 94 xfails all strict · BUG-2349 now on 5 cards (CT-57, CT-58, UI-24, UI-26, UI-27, matching the cases file's reviewer summary count of 5).

**Findings.** None. **Remaining items.** None for any stage.

**Commands run (round 2)**
```
COVERAGE_FILE=<s2>/.cov .venv/Scripts/python.exe -m pytest tests/unit/managers/test_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.order_template_manager --cov-branch --cov-report=term-missing
  app\managers\order_template_manager.py  84 0 18 0 100%  ·  111 passed, 94 xfailed
plain run x2 more: 111 passed, 94 xfailed (both)
... --runxfail -rf -k "ui_27 or ui_28"   ->  1 failed (UI-27, DataError at line 3143), 1 passed
... --runxfail                            ->  94 failed, 111 passed
VRT=          PYTHONPATH=<s1>/plug ... --runxfail -p vrt_otm   ->  73 failed, 132 passed
VRT=tot_priceonly  (same)                                     ->  74 failed, 131 passed  (extra: UI-27)
```
`<s1>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otmgr\`, `<s2>` = `…\tplv\otmgr2\`.
