# Verification — `app/core/middleware.py`

> **Verdict:** PASS
> Tests: 64 passed · 48 xfailed (reproduced ✅) · coverage 100% branch (31 stmts, 4 branches)
> Mutation: 44 mutants · 43 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 4

## Summary
These tests can be trusted. Every one of the 51 cases maps to exactly one test. Each test asserts what its case's Then column says, with no loosening, and the only patches are the `uuid.uuid4` and `time.time` patches that the conventions allow. Every xfail test fails today on the assertion its case names in "fails today on". Mutation testing killed every mutant except one. That one (`'1; mode=block'` → `''`) sits on the line BUG-486 says is wrong, so the only test that targets its exact value is the xfail MW-SH-03. The notes' Result line was reproduced exactly, and the outcome was the same on 3 plain runs. There is one non-blocking observation for the case designer: several bug cases also depend on BUG-486, but their Expect column does not say so (see Observations).

## Findings
None.

### Observations (non-blocking, advisory)
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| O1 | Incomplete Expect column | MW-SH-13, MW-SH-16 (a, c, d), MW-SH-18, MW-SH-19, MW-SH-22, MW-SH-23 (and MW-SH-12, where the executor already added BUG-486 to the reason) | These cases assert `X-XSS-Protection == "0"` (the intended value, BUG-486), but their Expect column lists only the primary bug (483 / 484 / 487). If the listed bug is fixed alone, the strict xfail keeps failing on the XXSS assertion, and its marker reason does not explain why. Each test is still honest today: `--runxfail` shows each one failing on its stated "fails today on" assertion. The notes file already records the dependency ("SH-18/19/22/23 need BUG-483 and BUG-486"). | `test_middleware.py:995,1030,1084,1100` `assert_headers(r, (XCTO, XFO, XXSS, HSTS))`; reasons at `:883,938,981,1018,1067,1093` name one bug only; `:864` names `BUG_484; BUG_486` | case designer: list every BUG a case depends on in Expect (e.g. `xfail BUG-483, BUG-486`). The executor then updates the matching xfail reasons. (best-practice default, delegated by reviewer: treated as advisory, not blocking, because the marker↔Expect rule is met as written and no xfail is dishonest today) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 17 | L86:51 | `"1; mode=block"` → `""` (value of `X-XSS-Protection`) | bug-path | SH R3a [BUG-486] says the value must be `0`, so today's value is the bug. Only the xfail MW-SH-03 (and the other XXSS=`0` xfails) assert the exact value, and mutate.py leaves xfail tests out. The passing tests only check that the header is present (MW-SH-01/15), as their cases specify. This resolves when BUG-486 is fixed. | — |

## Traceability
- **Cases vs tests:** 51 cases (`MW-RC-01..28`, `MW-SH-01..23`) and 51 test functions. Each case ID appears in exactly one test docstring. There are no unmatched cases, no tests without a case ID, and no duplicates.
- **Parameter ids:** parameter ids carry the `<CASE-ID>-<variant>` prefix, giving 112 items in total.
- **Markers:** there are 18 xfail tests, and they are exactly the 18 cases marked `xfail` in Expect: RC-08, 09, 10, 20, 25, 28 and SH-03, 08, 09, 10, 12, 13, 16, 17, 18, 19, 22, 23. All use `strict=True`, and each reason names the BUG ID(s) listed in its case. The 33 `pass` cases have no xfail marker. The notes record no DISCREPANCY. Marker mismatches: none.
- **BUG IDs:** BUG-480 to BUG-487 are not in `docs/testing/bugs.md` yet. All eight are in `tests/unit/core/middleware.bugs-staging.md`, which is the batch-mode staging register a single agent merges into `bugs.md` later. I accepted the staging file as the register for this check (best-practice default, delegated by reviewer).
- **Fidelity:** I read every test against its case. None of the finding types applies:
  - no missing or weakened assertions (the `>=` checks in RC-18/RC-19 and the "present" checks in SH-01/SH-15 are what those cases specify);
  - no changed expectations and no wrong setup;
  - no swallowed failures (`pytest.raises` names `ValueError` as the case does);
  - no extra mocks (only `app.core.middleware.uuid.uuid4` and `app.core.middleware.time.time` are patched, as the conventions define);
  - the "in-memory only" check does not apply, because the module has no database.
- **Return value convention:** every TestClient case asserts the status and body, and every direct-dispatch case asserts `result is resp`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_middleware.py -q -p no:cacheprovider --cov=app.core.middleware --cov-branch --cov-report=term-missing
  app\core\middleware.py   31   0   4   0   100%
  64 passed, 48 xfailed, 1 warning in 6.99s

.venv/Scripts/python.exe -m pytest tests/unit/core/test_middleware.py -q -p no:cacheprovider --runxfail -rf
  48 failed, 64 passed, 1 warning in 2.65s
  Each failure is on the named assertion:
    BUG-480: query_params verbatim, e.g. 'a=1&token=abc&b=2' == 'a=1&token=***&b=2'
    BUG-481: assert 40 == 30
    BUG-482: assert 0 == 1 (no completed record)
    BUG-483: RuntimeError: boom ×3, KeyError: 'k'
    BUG-484: AssertionError: X-Content-Type-Options / None == 'nosniff'
    BUG-485: None == "default-src 'self'" ×7; CSP present on /api/v2 docs ×3
    BUG-486: ['1; mode=block'] == ['0']
    BUG-487: route value overwritten ×4, CSP replaced ×1

.venv/Scripts/python.exe -m pytest tests/unit/core/test_middleware.py -q -p no:cacheprovider   (×2 more)
  64 passed, 48 xfailed, 1 warning in 2.61s
  64 passed, 48 xfailed, 1 warning in 2.63s
  -> stable

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/middleware.py tests/unit/core/test_middleware.py --timeout 180 --json %TEMP%/middleware_mut.json
  Mutants: 44 · killed 43 · timeout 0 · survived 1 · score 98%
  SURVIVED #17 L86:51 const: '1; mode=block' -> ''   (bug-path, BUG-486 -> adjusted score 43/43 = 100%)
```
