# Verification — `app/utils/work_order_recurrence.py`

> **Verdict:** PASS
> Tests: 111 passed · 37 xfailed (reproduced ✅: all 37 fail under `--runxfail` on the designed assertion) · coverage 100% branch (55 stmts, 26 branches)
> Mutation: 82 mutants · 75 killed · 7 survived → score 100% (75/75, after excluding 3 equivalent, 0 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 5

## Summary
These tests can be trusted. All 82 cases are implemented, one test (or one param id) per case. The xfail markers match the cases, and every run matches the notes: 111 passed and 37 xfailed, the same on three runs. Mutation testing kills every mutant that can be killed today. The 7 survivors are the same as in the last verification. Three are equivalent: two unused type-alias strings, and the upper clamp that the month-end cap hides. The other four are on the BUG-360/361 fallback path, which only xfail tests reach. The earlier finding (WOR-APR-04 did not assert `is None`) is fixed at line 584. Nothing needs to change.

## Findings
None.

Notes (not findings):
- BUG-360..363 are not yet in `docs/testing/bugs.md`. They are registered in `tests/unit/utils/work_order_recurrence.bugs-staging.md`, which is merged into `bugs.md` later by one agent. In batch mode I accepted the staging register as the bug source for the "every BUG ID exists" check (best-practice default, delegated by reviewer). Once the merge is done, a quick grep of `bugs.md` for BUG-360..363 confirms it.
- My first coverage run crashed with an INTERNALERROR (`PermissionError [WinError 32]` while renaming `.coverage.*` in the repo root). Another agent was writing a coverage data file there at the same time. This is an environment clash, not a test problem. I re-ran with `COVERAGE_FILE` pointing to the temp dir and got a clean 100%.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | L50 | `return from_date + timedelta(days=1)` → `return None` | bug-path | L50 is the fallback for a `None` or unsupported `recurrence_type`. The spec tags this path BUG-360 / BUG-361 (ADV R11 / R11b: it should raise `ValueError`). Only xfail tests reach it: ADV-19, ADV-20, APR-09, SEED-07 and RESEED-06, and those are excluded from the mutation run. APR-10 also uses bad types, but the range error is raised before L50 runs. | — (resolves when BUG-360/361 are fixed) |
| 28 | L50 | `+ timedelta(days=1)` → `- timedelta(days=1)` | bug-path | Same fallback line as #7. | — |
| 78 | L50 | `timedelta(days=1)` → `timedelta(days=2)` | bug-path | Same fallback line as #7. | — |
| 40 | L28 | `recurrence_type == 'daily'` → `== ''` | bug-path | With this mutant, `'daily'` skips its own branch and falls through to the buggy L50 fallback, which also returns `from_date + 1 day`. The two paths give the same result only because of BUG-360. Once L50 raises, ADV-01/02/03 kill this mutant. | — (resolves when BUG-360 is fixed) |
| 38 | L8 | `Literal['schedule', 'draft']` → `Literal['', 'draft']` | equivalent | `WorkOrderGenerationMode` is a type alias. Nothing reads its arguments at runtime, and the spec's "Not specified" section says nothing in `app/` references it. | — |
| 39 | L8 | `Literal['schedule', 'draft']` → `Literal['schedule', '']` | equivalent | Same as #38. | — |
| 74 | L42 | `min(day, 31)` → `min(day, 32)` | equivalent | L48 then applies `min(day, last_day)`, and `last_day` ≤ 31, so a day clamped to 31 or 32 always gives the same date. The cases file (Reviewer summary) and the notes predict this survivor (R7 upper clamp). | — |

## Traceability
- The cases file has 82 case IDs, and all 82 appear in `test_work_order_recurrence.py`. None are unmatched, and every test function carries at least one case ID. ACT-03/04/05, SHA-01/02/03 and SHA-04/05 are each one parametrised test, with the case ID as the param id. No case ID is split across two test functions.
- Expect ↔ marker: all 12 xfail cases (ADV-19, -20, -22, -23, -24, -25, -27, -29, -31, APR-09, SEED-07, RESEED-06) use `xfail(strict=True)`, and each reason names the case's BUG ID. APR-09's reason names both BUG-360 and BUG-361. None of the 70 pass cases has an xfail marker. Marker mismatches: none. The notes record no discrepancies.
- Fidelity: I read every test against its case and found no issues. There are no weakened, missing or changed assertions, and no swallowed failures. No mocks or patches are used, which matches the spec ("Externals to mock: none"). "Unchanged" is checked with a full `vars(t)` snapshot compared by `==`. Boolean results are asserted with `is True` / `is False`. Error texts are compared exactly with `==`.
- The xfails are honest. Under `--runxfail`, each one fails on its designed assertion: 16 × `DID NOT RAISE ValueError` (ADV-19/20, APR-09, SEED-07, RESEED-06), 17 × `DID NOT RAISE ValidationError` (ADV-23/25/27/29/31), and 4 × an un-normalised value such as `assert ' Weekly ' == 'weekly'` (ADV-22/24). None fails on setup or import.

## Commands run
```
COVERAGE_FILE=%TEMP%/wor.coverage .venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_recurrence.py -q -p no:cacheprovider --cov=app.utils.work_order_recurrence --cov-branch --cov-report=term-missing
  app\utils\work_order_recurrence.py  55  0  26  0  100%
  111 passed, 37 xfailed
  (first attempt without COVERAGE_FILE: 111 passed, 37 xfailed, then a coverage INTERNALERROR PermissionError from a concurrent .coverage file; environmental)
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_recurrence.py -q -p no:cacheprovider --runxfail -rf
  37 failed, 111 passed
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_recurrence.py -q -p no:cacheprovider   (x2)
  111 passed, 37 xfailed ; 111 passed, 37 xfailed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/work_order_recurrence.py tests/unit/utils/test_work_order_recurrence.py --timeout 180 --json %TEMP%/wor_mut.json
  Mutants: 82 · killed 75 · timeout 0 · survived 7 · score 91% (raw) → 100% after classification
```
