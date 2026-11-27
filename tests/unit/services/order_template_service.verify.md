# Verification — `app/services/order_template_service.py`

> **Verdict:** PASS (round 2, 2026-11-09; round 1 was NEEDS WORK)
> **Current:** PASS — cases revision 3 · 30 passed · 3 xfailed · line-57 mutants 2/2 killed (round-1 lines below are history)
> Tests: 29 passed · 2 xfailed (reproduced ✅) · coverage 100% branch (68 statements, no branches)
> Mutation: 16 mutants · 15 killed · 1 survived → score 94% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 32 · 29 caught · 3 not caught (2 to fix, 1 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to their cards: every card is implemented in card order, every Then line is asserted with the exact value, the only patches are the Conventions' commit / rollback / refresh wraps, and both strict xfails fail on the card's "Fails today on" line. Commit, rollback, re-read and pass-through of refusals are pinned on every write (all 17 commit/rollback/refresh hand variants caught). Three gaps remain, all in the cases or spec rather than the test code: `limit` is not shown to reach the manager (L-02 gives the same answer with any limit), the service's default `limit=100` has no rule, and no passing card asks `get_items` for another workspace's template id, so a service that dropped `workspace_id` on `get_items` would go unnoticed.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | OTSV-L-02 / line 59–63 | The card says "all five arguments reach the manager", but with `is_active=False, expense_category="factory"` only A and B match; after `skip=1` one row is left, so `limit=1` and `limit=100` give the same `[A.id]`. Dropping `limit` from the call is not caught. | Hand variant `list_drop_limit`: 29 passed. Fix idea: a third matching row (e.g. another inactive factory template at T0) so `limit=1` cuts one. | case designer |
| 2 | case-missing | `get_items` R1 / line 110 | GI-02 asks for W1's own template, so it never tests that the caller's workspace reaches the manager. A service that ignored `workspace_id` and returned the lines of any template id passes every test. Today's buggy `[]` (BUG-2366) is deliberately not carded; a strict xfail BUG-2366 card on `get_items(tpl_id=Z.id, workspace_id=W1.id)` expecting the 404 would at least pin it once fixed. Designer's call. | Hand variant `scope_get_items_any` (lines selected by `order_template_id` only): 29 passed. | case designer |
| 3 | spec-gap | `list_templates` signature, line 57 `limit: int = 100` | The default limit has no rule (R1 names only the `is_active=None` default); the only caller (`GET /order-templates/`) always passes `limit`. Either add a rule (default 100, so the designer can card it) or list it as not specified. | Mutant #7 `100 -> 101` SURVIVED. | describer (fill-gaps) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | 57 | `limit` default `100 -> 101` | spec-gap | Not equivalent (a direct caller with 101 templates would get 101), but no spec rule states the default; see finding 3. | describer |

## Hand variants
Plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otsvc\hv_otsvc.py` (mine; patches `OrderTemplateService` methods in-process, chosen by `HV`), run with `-m "not xfail"`.

| Variant | Caught by |
|---|---|
| no re-read: create / update_template / add_item / update_item | C-01, C-04 / U-01 / A-01 / I-01 |
| no rollback on error, each of the 6 writes | C-02 / U-02 / D-03 / A-02 / I-02 / R-02 |
| no commit, each of the 6 writes | C-01 C-03 C-04 C-05 / U-01 / D-01 D-04 / A-01 A-03 / I-01 I-04 / R-01 R-03 |
| create re-reads before committing | C-01, C-04 |
| `remove_item` re-reads the deleted line | R-01 |
| `delete_template` swallows the refusal | D-03, D-04 |
| list drops `skip` / `is_active` / `expense_category` | L-02 |
| list default `is_active=True` instead of `None` | L-01 |
| **list drops `limit`** | **not caught** (finding 1) |
| a read commits: get_template / list_templates / get_items | G-01 / L-03 / GI-01 |
| get_template rolls back on its 404 | G-02 |
| get_items rolls back on error | not caught — **bug-path**: `get_items` raises nothing today (BUG-2366); resolves when the 404 exists and a card reaches it |
| get_template ignores workspace | G-02, G-03 |
| list ignores workspace | L-01, L-03 |
| **get_items ignores workspace** | **not caught** (finding 2) |

Money pass-through: C-01 and I-01 assert `0.13` for 0.50 × 0.25 (half up, HR-15), so a half-even pass-through (0.12) fails both; BUG-1226 (I-03) fails on its Then 3 as designed. Refusal order is the manager's; the service only wraps (C-06 checks the BUG-2347 403 passes after the rollback).

## Traceability
cases 31 · tests 31 (each under `# [claude] <ID>`, card order) · unmatched: none · marker mismatches: none. xfail markers: C-06 `strict=True, reason="BUG-2347: …"`, I-03 `strict=True, reason="BUG-1226: …"`; both IDs exist in `bugs.md`. No `local-run.json`; no local-written tests. Extra mocks: none.

## Commands run
```
COVERAGE_FILE=<tplv/otsvc>/.cov
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_template_service --cov-branch --cov-report=term-missing
  → 29 passed, 2 xfailed · app\services\order_template_service.py 68 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_template_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  → 2 failed, 29 passed · C-06 line 353 `DID NOT RAISE HTTPException` (Then 1) · I-03 line 800 `Decimal('20.00') == Decimal('0.00')` (Then 3)
2 more plain runs → 29 passed, 2 xfailed each (no flakiness)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/order_template_service.py tests/unit/services/test_order_template_service.py --json <tplv/otsvc>/mut.json
  → Mutants: 16 · killed 15 · timeout 0 · survived 1 · score 94% (SURVIVED #7 L57:36 const 100 -> 101)
HV=<variant> PYTHONPATH=<tplv/otsvc> .venv/Scripts/python.exe -m pytest tests/unit/services/test_order_template_service.py -q -p no:cacheprovider -o addopts="" -p hv_otsvc -m "not xfail"   (32 variants, table above)
```
`<tplv/otsvc>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otsvc`.

## Round 2 — 2026-11-09

> **Current verdict:** PASS
> Tests: 30 passed · 3 xfailed (reproduced ✅, 3 runs identical) · coverage 100% branch (68 statements)
> Mutation (line 57 re-run): 2 mutants · 2 killed · 0 survived → score 100%; full-file score now 16/16
> Source commit: e48a092 · Cases revision: 3 · Spec: `list_templates` R1a added

**Changed cards read against their tests** (all faithful, card order, exact values, no extra mocks):
- OTSV-L-02 — the new A0 row (inactive, factory, `created_at T0`) is built; newest-first leaves B, A, A0, so `skip=1, limit=1` → `[A.id]` and a dropped `limit` gives `[A, A0]`. Then 1 asserted with `==` on the ordered list.
- OTSV-L-04 (new, R1a) — 101 rows `Rent k` at `T0 + k min` with `add_all` + one flush, commit point; Then 1 `len == 100`, Then 2 ordered ids `== newest[:100]`.
- OTSV-GI-03 (new, strict xfail BUG-2366) — Given T + line, Z + ZL in W2; Then 1 `pytest.raises(HTTPException)`, Then 2 exact status 404 and detail. Marker `strict=True`, reason names BUG-2366 (in `bugs.md`). `--runxfail`: fails on Then 1, line 973 `DID NOT RAISE HTTPException`, as the card's "Fails today on" says.

**Round-1 findings**
| # | Round-1 finding | Now | Evidence |
|---|---|---|---|
| 1 | `list_templates` dropping `limit` not caught | closed | variant `list_drop_limit` → OTSV-L-02 FAILED (1 failed, 29 passed) |
| 2 | `get_items` ignoring `workspace_id` not caught | closed (bug-path until BUG-2366 is fixed) | reference fix `ref2366` alone: GI-01…03 pass under `--runxfail`; `ref2366` + `scope_get_items_any`: GI-03 FAILED (`DID NOT RAISE`, line 973). Without the fix the variant still passes the 30 passing tests, as expected: the only discriminating card is the BUG-2366 xfail |
| 3 | default `limit=100` has no rule | closed | spec R1a; OTSV-L-04; mutant L57 `100 -> 101` KILLED; variant `list_default_101` → L-04 FAILED |

Findings: none. Surviving mutants: none.

Traceability: cases 33 · tests 33 · unmatched: none · marker mismatches: none (xfail: C-06 BUG-2347, I-03 BUG-1226, GI-03 BUG-2366, all strict).

**Commands (round 2)**
```
COVERAGE_FILE=<tplv/otsvc2>/.cov
pytest tests/unit/services/test_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_template_service --cov-branch --cov-report=term-missing   (x3)
  → 30 passed, 3 xfailed · 68 0 0 0 100%   (each run)
pytest … --runxfail -rf → 3 failed, 30 passed · C-06 line 354 DID NOT RAISE (Then 1) · I-03 line 822 20.00 == 0.00 (Then 3) · GI-03 line 973 DID NOT RAISE (Then 1)
mutate.py app/services/order_template_service.py tests/unit/services/test_order_template_service.py --lines 57-57 --json C:/…/tplv/otsvc2/mut.json
  → Mutants: 2 · killed 2 · survived 0 · score 100%
HV=<variants> PYTHONPATH=<tplv/otsvc2> pytest … -p hv2_otsvc -m "not xfail"  |  --runxfail -k gi_
  → baseline 30 passed · list_drop_limit L-02 FAILED · list_default_101 L-04 FAILED · scope_get_items_any 30 passed (bug-path)
  → ref2366 3 passed · ref2366,scope_get_items_any GI-03 FAILED
```
`<tplv/otsvc2>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\otsvc2` (plugin `hv2_otsvc.py`, mine).
