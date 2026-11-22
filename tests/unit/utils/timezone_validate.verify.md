# Verification — `app/utils/timezone_validate.py`

> **Verdict:** PASS
> Tests: 35 passed · 4 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 11 mutants · 10 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. All 22 cases (revision 2) are implemented faithfully. The tests use exact identity checks (`is True` / `is False`), no mocks, and the exact `TypeError` message.
The executor's result reproduces exactly (35 passed, 4 xfailed, 100% branch). It stayed the same over 3 runs.
The new TZV-V-21 (65-char padded `"UTC"`) now kills mutant #10 (`64` → `65`), which survived in the revision-1 audit.
Only one mutant survives: #7 (`>` → `>=`). On this host it can be observed only through the BUG-300 padded spelling that TZV-V-22 targets, and TZV-V-22 is a strict xfail on win32, so it is excluded from the mutation run. Under the intended behavior, and on Linux, no 64-character string is valid. So the mutant is `bug-path`, and it becomes equivalent once BUG-300 is fixed.
BUG-300 is still only in `timezone_validate.bugs-staging.md`, not in `docs/testing/bugs.md`. That is the expected batch-mode state (see O1).

## Findings
None.

### Observations (non-blocking, no stage action required now)
| # | Kind | Where | Note | Evidence |
|---|---|---|---|---|
| O1 | bug registry | BUG-300 | `docs/testing/bugs.md` does not contain BUG-300 yet. The row exists only in `tests/unit/utils/timezone_validate.bugs-staging.md`, which is the expected batch-mode state. The shared-file merge agent must copy it into `bugs.md`. Treated as satisfied for traceability because the staging row is complete and unique (best-practice default, delegated by reviewer). | `grep -c BUG-300 docs/testing/bugs.md` → 0; staging file has the BUG-300 row |
| O2 | spec example breadth | R6 [BUG-300] | Carried over from revision 1: on Windows, trailing-dot spellings (`"Asia/Dhaka."`) are also accepted today. R6's general rule already covers them, so this is not a spec gap (best-practice default, delegated by reviewer: no action now). | revision-1 ad-hoc run |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | L8:20 | `len(value) > 64` → `>= 64` | bug-path | The mutant changes the result only for a 64-character string that would otherwise load as a zone. The longest canonical name has 32 characters, so under the intended R6 behavior (exact membership) and on Linux every 64-character string returns `False` either way. On win32 the only observable input is a BUG-300 non-canonical spelling (`"UTC" + " " * 61` → `True` today). TZV-V-22 is the case for it, and it is a strict xfail on win32, so the mutation tool excludes it. Once BUG-300 is fixed, TZV-V-22 runs as a pass test and the mutant becomes equivalent. | — |

## Traceability
cases 22 · tests 22 functions (39 items via parametrize) · each case ID TZV-V-01…22 appears in exactly one test function's docstring, plus the `pytest.param` ids for rows 05, 07, 09–13 and 16 · no test lacks a case ID · unmatched: none.
Marker check: TZV-V-01…16, 20 and 21 are `pass` and have no xfail marker. TZV-V-17/18/19/22 are `xfail BUG-300 on win32 only (strict)`. They use `BUG_300 = pytest.mark.xfail(condition=sys.platform == "win32", strict=True, reason="BUG-300: …")`, so the reason names BUG-300. Mismatches: none. BUG-300 is in the staging file only (O1).

Fidelity: each test matches its Given/When/Then. TZV-V-21 and TZV-V-22 assert `len(value) == 65` and `== 64` before the call, as their cases require, then assert `is False`. TZV-V-05/07 assert `is True`, membership in `available_timezones()` and that `ZoneInfo` loads. TZV-V-06 asserts `rejected == []` and `len(names) >= 400`, and excludes `posix/`/`right/`. TZV-V-20 uses `pytest.raises(TypeError)` and asserts the exact message. There is no `try/except` and there are no mocks.
Honest xfail: with `--runxfail`, all four xfail tests fail on their `is False` assertion (`assert True is False`), not on setup or import errors.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_timezone_validate.py -q -p no:cacheprovider --cov=app.utils.timezone_validate --cov-branch --cov-report=term-missing
  app\utils\timezone_validate.py  10  0  2  0  100%
  35 passed, 4 xfailed in 0.49s

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_timezone_validate.py -q -p no:cacheprovider --runxfail -rf
  FAILED ...::test_tzv_v_17__lowercase_utc_is_false              (assert True is False; is_valid_iana_timezone('utc'))
  FAILED ...::test_tzv_v_18__backslash_separator_is_false        (assert True is False; 'Asia\\Dhaka')
  FAILED ...::test_tzv_v_19__trailing_space_is_false             (assert True is False; 'Asia/Dhaka ')
  FAILED ...::test_tzv_v_22__padded_real_name_64_chars_is_false  (assert True is False; 'UTC' + 61 spaces)
  4 failed, 35 passed in 0.35s

stability reruns (x2): 35 passed, 4 xfailed in 0.31s · 35 passed, 4 xfailed in 0.37s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/timezone_validate.py tests/unit/utils/test_timezone_validate.py --timeout 180 --json %TEMP%/tzv_mut.json
  Mutants: 11 · killed 10 · timeout 0 · survived 1 · score 91% (raw)
  SURVIVED #7 L8:20 cmp: Gt -> GtE
  (#10 L8:33 const 64 -> 65 now KILLED by TZV-V-21)
```
