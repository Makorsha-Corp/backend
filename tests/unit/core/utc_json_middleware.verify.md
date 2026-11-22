# Verification — `app/core/utc_json_middleware.py`

> **Verdict:** PASS
> Tests: 47 passed · 9 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 16 mutants · 16 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. Each of the 41 cases in revision 3 has exactly one test, and the tests use the exact values the cases give: byte-for-byte bodies, exact `content-length` strings and exact header lists. There are no mocks, no `try/except`, and no broad `pytest.raises`. With `--runxfail`, each of the 9 xfail tests fails on the assertion its case names. The runs reproduce the Result line in the notes, and 3 runs gave the same outcome. The tests killed all 16 mutants. No stage needs to change anything.

## Findings
None.

Observation (not a finding, batch mode): BUG-520, BUG-521 and BUG-522 are not in `docs/testing/bugs.md` yet. They are staged in `tests/unit/core/utc_json_middleware.bugs-staging.md`, which holds all three rows, and the xfail reasons match the staged titles word for word. The agent that merges the shared files must copy these rows into `bugs.md`. (best-practice default, delegated by reviewer: staged bug IDs count as present for the traceability check in batch mode.)

## Surviving mutants
None. All 16 were killed:

| # | Line | Mutation | Result |
|---|---|---|---|
| 1 | L20 | negate `if` condition | KILLED |
| 2 | L24 | negate `if` condition | KILLED |
| 3 | L31 | negate `if` condition | KILLED |
| 4 | L50 | `return None` | KILLED |
| 5 | L20 | drop `not` | KILLED |
| 6 | L21 | `return None` | KILLED |
| 7 | L24 | `not in` → `in` | KILLED |
| 8 | L25 | `return None` | KILLED |
| 9 | L31 | drop `not` | KILLED |
| 10 | L32 | `return None` | KILLED |
| 11 | L23 | `'content-type'` → `''` | KILLED |
| 12 | L24 | `'application/json'` → `''` | KILLED |
| 13 | L37 | `return None` | KILLED |
| 14 | L45 | `'utf-8'` → `''` | KILLED |
| 15 | L48 | `'content-length'` → `''` | KILLED |
| 16 | L20 | `'/api/'` → `''` | KILLED |

## Traceability
Cases: 41 · test functions: 41 (56 items; D-04, -05, -07, -08 and -17 are parametrized, and every `pytest.param` id is `UTCJ-D-NN-<variant>`). Unmatched: none. Every case ID appears in exactly one test, and every test has a case ID.
Marker mismatches: none. The 32 `pass` cases have no xfail marker. D-22 uses `xfail(strict=True, reason=BUG_522)`. D-29 to D-32 use `BUG_520`. D-38 to D-40 use `BUG_521`. D-41 uses `f"{BUG_522}; {BUG_521}"`, which names both IDs.
`--runxfail` failure reasons: D-22 and D-41 raise `UnicodeDecodeError`. D-29 to D-32 fail because the value comes back with a `Z` added. D-38 and D-40 fail on `['access=a'] == ['access=a', 'refresh=r']`, and D-39 on `['Accept'] == ['Accept', 'Origin']`. These are the failures the "fails today on" column predicts.

## Commands run
```
COVERAGE_FILE=$TEMP/utcv.cov .venv/Scripts/python.exe -m pytest tests/unit/core/test_utc_json_middleware.py -q -p no:cacheprovider --cov=app.core.utc_json_middleware --cov-branch --cov-report=term-missing
  app\core\utc_json_middleware.py      29      0      8      0   100%
  47 passed, 9 xfailed, 1 warning
.venv/Scripts/python.exe -m pytest tests/unit/core/test_utc_json_middleware.py -q -p no:cacheprovider --runxfail -rf
  9 failed, 47 passed (the 9 failures are exactly D-22, D-29..32, D-38..41)
.venv/Scripts/python.exe -m pytest tests/unit/core/test_utc_json_middleware.py -q -p no:cacheprovider   (x2)
  47 passed, 9 xfailed ; 47 passed, 9 xfailed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/utc_json_middleware.py tests/unit/core/test_utc_json_middleware.py --timeout 180 --json $TEMP/utc_mut.json
  Mutants: 16 · killed 16 · timeout 0 · survived 0 · score 100%
```
