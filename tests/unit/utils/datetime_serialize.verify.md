# Verification — `app/utils/datetime_serialize.py`

> **Verdict:** PASS
> Tests: 53 passed · 18 xfailed (reproduced ✅) · coverage 62% branch (100% of `ensure_utc_z_in_json`; uncovered lines 16-25 are the dead `serialize_utc_datetime`)
> Mutation: 19 mutants · 10 killed · 9 survived → score 100% (after excluding 0 equivalent, 9 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. This is a re-verification against cases revision 2, which changed no cases. The test file is the same apart from its docstring. All 21 cases map to exactly one test each. Every test asserts its case's Then column exactly: it uses identity checks where the spec says "as is", and `is not` plus a deep-copy non-mutation check where the spec says "new". There are no mocks and no swallowed exceptions. With `--runxfail`, all 18 xfail parameter items fail on the intended "fails today on" assertion (a `Z` is appended), not on a setup or import error. Every mutant in `ensure_utc_z_in_json` was killed. All 9 survivors are in `serialize_utc_datetime`, which the spec marks as dead code (reviewer Q5). Nothing needs to change. One bookkeeping point: BUG-160/161/162 exist only in `datetime_serialize.bugs-staging.md` until the batch merge into `docs/testing/bugs.md`. That is not a test finding.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L16 | negate `if dt.tzinfo is None` | dead | inside `serialize_utc_datetime`. The spec's "Not specified" section lists it as dead code, to be removed (Q5) | — |
| 2 | L22 | negate `if dt.microsecond` | dead | same function (dead) | — |
| 3 | L25 | `return None` | dead | same function (dead) | — |
| 9 | L16 | `is` → `is not` | dead | same function (dead) | — |
| 14 | L21 | `'%Y-%m-%dT%H:%M:%S'` → `''` | dead | same function (dead) | — |
| 15 | L25 | `'Z'` → `''` | dead | same function (dead) | — |
| 16 | L23 | `'0'` → `''` | dead | same function (dead) | — |
| 17 | L24 | `'.'` → `''` | dead | same function (dead) | — |
| 19 | L23 | `'06d'` → `''` | dead | same function (dead) | — |

Killed (10): L30/L32/L34 negated conditions, L31/L33/L35/L36 `return None`, L34 `and` → `or`, L35 `'Z'` → `''`, L10 regex constant → `''`.

Note: the mutation tool does not change the inside of the regex (for example `{4}` → `{3}`, or dropping `(\.\d+)?`). The boundary cases still pin those paths down: E-02 (fraction lengths), E-06 (3- and 5-digit years, 1-digit month, empty fraction, lowercase `t`, missing seconds) and E-08 (trailing characters).

## Traceability
- Cases: 21 · tests: 21. Each ID from `DTS-E-01` to `DTS-E-21` appears in exactly one test name and docstring, and no test lacks a case ID.
- Unmatched: none.
- Marker mismatches: none. The 17 pass cases have no xfail marker. E-04 and E-19 carry `xfail(strict=True, reason=BUG_160)`, E-07 carries `BUG_161`, and E-09 carries `BUG_162`. Each reason names the correct ID.
- BUG IDs: BUG-160, BUG-161 and BUG-162 are defined in `tests/unit/utils/datetime_serialize.bugs-staging.md`, not yet in `docs/testing/bugs.md`. In batch mode that is expected, because one agent merges the shared file later. After the merge, all three must exist in `bugs.md`.
- Mocks: none. The spec lists no externals and the cases list no race simulations. There is no `try/except` and no `pytest.raises`.
- Deferred: the cases file defers the middleware half of R9 (`UtcJsonResponseMiddleware`) to integration tests, and it is correctly absent here.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_datetime_serialize.py -q -p no:cacheprovider --cov=app.utils.datetime_serialize --cov-branch --cov-report=term-missing
  app\utils\datetime_serialize.py  22  8  10  0  62%  16-25
  53 passed, 18 xfailed in 1.13s

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_datetime_serialize.py -q -p no:cacheprovider --runxfail -rf   (plus --tb=line to inspect failures)
  18 failed, 53 passed in 0.56s
  (every failure is the "fails today on" assertion: E-04 x12 at line 111, e.g. assert '2026-13-01T10:00:00Z' == '2026-13-01T10:00:00';
   E-07 at line 164, assert '2026-01-01T10:00:00\nZ' == '2026-01-01T10:00:00\n'; E-09 x4 at line 195, s + 'Z' == s;
   E-19 at line 351, assert '2026-01-01T10:00:00Z' == '2026-01-01T10:00:00')

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_datetime_serialize.py -q -p no:cacheprovider   (x2)
  53 passed, 18 xfailed in 0.49s
  53 passed, 18 xfailed in 0.52s        -> stable, matches the Result line in the notes

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/datetime_serialize.py tests/unit/utils/test_datetime_serialize.py --timeout 180 --json %TEMP%/dts_mut.json
  Mutants: 19 · killed 10 · timeout 0 · survived 9 · score 53% (raw; 100% after excluding 9 dead)
```
