# Verification — `app/core/config.py`

> **Verdict:** PASS
> Tests: 54 passed · 35 xfailed (reproduced ✅) · 1 skipped (CFG-S-08, Windows only by design) · coverage 100% branch
> Mutation: 45 mutants · 44 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. All 90 cases are implemented, and each one maps to exactly one test or `pytest.param` id.
Every Then item is asserted with the exact value the case gives. With `--runxfail`, each of the 35 xfail tests fails
on the case's "fails today on" assertion, not on setup or import errors. Mutation testing killed every mutant except
the `DEBUG` default flip (`True -> False`). That flip is the intended BUG-424 fix, and only xfail tests check it. Three
runs matched the executor's notes exactly. Cases revision 3 changed no cases, so the unchanged test file still matches
it. Nothing needs to change.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 18 | L57 `DEBUG: bool = True` | `True -> False` | bug-path | Spec `Settings` R4a [BUG-424] says `DEBUG` should default to `False`. The mutant applies the fix, and only the xfail cases CFG-S-11 and CFG-G-11 check it. Mutation runs skip xfail tests. CFG-S-09 leaves `DEBUG` out on purpose (cases rev 3), and CFG-G-01/G-13 set `DEBUG=true` explicitly. Pinning today's `True` default in a passing test would lock in the bug. This survivor goes away once BUG-424 is fixed. | — |

## Traceability
- Cases 90 (55 pass · 35 xfail) · pytest items collected 90 (50 test functions, parametrized) · unmatched cases: none · test items with no case ID: none. I checked this with a script: I matched case-table IDs against `pytest.param(id=…)` values and docstring headers, then compared the result with `--collect-only`.
- Expect ↔ marker: none of the 55 `pass` cases has an xfail marker. CFG-S-08 is marked `skipif(sys.platform == "win32")`, as its case requires. All 35 `xfail` cases use `xfail(strict=True)`, and each reason names every BUG ID the case lists: S-30 names BUG-420 and BUG-421, G-16 names BUG-423 and BUG-424, G-17 names BUG-423 and BUG-422. Mismatches: none.
- BUG IDs used: BUG-420 through BUG-424. None of them are in `docs/testing/bugs.md` yet. They are staged in `tests/unit/core/config.bugs-staging.md`, and the batch-merge agent will merge them into `bugs.md` because batch agents may not edit that file. I counted the staging file as the register for this check (best-practice default, delegated by reviewer). Re-check after the merge. TODO-001 (Q6, the mock gateway) is already in `bugs.md`. It is tested as intended today (CFG-S-10, CFG-G-12) and has no xfail, which is correct.
- Cosmetic only: the module docstring in `test_config.py` says "cases.md (revision 2)". The notes say that on purpose, rev 3 added or changed no cases and the test file was left alone. This is not a fidelity issue.

## Fidelity review
I compared every case with its test.
- **Assertions:** none missing, weakened or changed. Collection results use `==` with the exact list and its order. Bools use `is True` / `is False`, and ints also check `type(...) is int`, as CFG-S-09 and S-16 require.
- **Exceptions:** there is no `try/except`. Every `pytest.raises` names the specific type (`pydantic.ValidationError` / `RuntimeError`). The `loc` checks use the convention helper `assert_field_in_error_loc`, and `DEFAULT_MSG` is compared exactly in G-02/03/15.
- **Mocks:** none. The spec lists no externals to mock.
- **Guard tests:** the reload fixture chdirs to an empty tmp dir, then on teardown runs `monkeypatch.undo()` and reloads, as the conventions specify. Blank values come from `.env` files, as the cases file requires.
- **Database:** the module is pure, so no database re-read applies.

`--runxfail` shows each xfail failing on the expected assertion:
- S-24..31 raise `SettingsError` from JSON decoding.
- S-34/35/36 keep the raw value (`' Production '`, `'STAGING'`, `'Test'`).
- S-37..39, CO-09, WA-08 and G-18 fail with `DID NOT RAISE ValidationError`.
- CO-06/07/08 and WA-07 return un-parsed `'["…"]'` strings.
- CO-10..13 keep the `''` pieces.
- G-06..10 and G-15..17 fail with `DID NOT RAISE RuntimeError`.
- S-11 and G-11 fail with `assert True is False`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_config.py -q -p no:cacheprovider --cov=app.core.config --cov-branch --cov-report=term-missing
  app\core\config.py      46      0      6      0   100%
  (run 1) 54 passed, 1 skipped, 35 xfailed in 3.38s
  (run 2) 54 passed, 1 skipped, 35 xfailed in 3.21s
  (run 3) 54 passed, 1 skipped, 35 xfailed in 3.32s   -- identical; not flaky; matches notes Result line
.venv/Scripts/python.exe -m pytest tests/unit/core/test_config.py -q -p no:cacheprovider --runxfail -rf
  35 failed, 54 passed, 1 skipped in 1.89s   -- exactly the 35 xfail cases, each on its "fails today on" assertion
.venv/Scripts/python.exe -m pytest tests/unit/core/test_config.py -q -p no:cacheprovider --collect-only
  90 tests collected
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/config.py tests/unit/core/test_config.py --timeout 180 --json <system temp>/scratchpad/config_mut.json
  Mutants: 45 - killed 44 - timeout 0 - survived 1 - score 98%
  SURVIVED #18 L57:18 const: True -> False   (bug-path, BUG-424)
```
