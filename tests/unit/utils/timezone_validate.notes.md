# Execution notes — `app/utils/timezone_validate.py`

> Cases: `tests/unit/utils/timezone_validate.cases.md` (revision 2) · Tests: `tests/unit/utils/test_timezone_validate.py` · Source commit: e48a092
> Result: 35 passed · 4 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (22 cases → 39 test items via parametrization; on win32)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_timezone_validate.py -q -p no:cacheprovider --cov=app.utils.timezone_validate --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no fixtures, no mocks.** The function is pure (Conventions). No test takes `db`.
- **Conventions → helpers** (top of the test file):
  - "BUG-300 marker" → module constant `BUG_300 = pytest.mark.xfail(condition=sys.platform == "win32", strict=True, reason="BUG-300: …")`, applied to TZV-V-17/18/19/22.
  - "Excluded names" → `_EXCLUDED_PREFIXES` plus `_canonical_names()` (host `available_timezones()` minus `posix/` / `right/`), used by TZV-V-06.
  - Positive-case invariant (TZV-V-05, TZV-V-07) → `_assert_loadable_canonical(value)`: checks the value is in `available_timezones()` and that `ZoneInfo(value)` loads.
  - "Parametrized rows" → one parametrized test per multi-value row, with `pytest.param(..., id="TZV-V-NN-<value>")`; the case ID is in the docstring.
  - "No exception" → every call is made outside `pytest.raises` and asserted with `is True` / `is False`.
- TZV-V-06 asserts `rejected == []` first (so a failure prints the names), then `len(names) >= 400`.
- TZV-V-20 asserts the exact `TypeError` message `object of type 'int' has no len()`.
- TZV-V-21/22 assert `len(value) == 65` / `== 64` before calling the function, as the cases require.
- Stability: 3 runs, identical outcome (35 passed, 4 xfailed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (10 statements, 2 branches).

## Factories added
None. No DB models involved and nothing worth promoting (the helpers are specific to this module).

## Notes for maintainers
- **Platform dependence.** On Linux, TZV-V-17/18/19/22 run as ordinary passing tests (the xfail condition is false). On Windows they are strict xfails. After BUG-300 is fixed (check membership in `available_timezones()`), they will XPASS on Windows and fail under strict mode, so remove the `@BUG_300` decorator at that point.
- The R2 64/65 boundary: TZV-V-03/04 check it by return value only; TZV-V-21 (65-char padded `"UTC"` → `False`) catches a limit raised above 64 on every platform. A limit lowered to 63 is only caught by TZV-V-22, which is an xfail on win32 until BUG-300 is fixed.
- TZV-V-06 depends on the installed `tzdata` / system tz database. If a future `tzdata` release lists a name that the fixed implementation rejects (or vice versa), this test reports it by name.
- The parametrize ids contain `/` and `+`, which pytest accepts. If a CLI `-k` filter needs them, select by the case prefix (e.g. `-k tzv_v_05`).

## Revision history
- **Revision 2 (cases rev 2):** added TZV-V-21 (pass) and TZV-V-22 (xfail BUG-300 on win32, strict) — padded real names on each side of the 64/65 length limit, added after the verify report's surviving mutants #7/#10. Existing tests unchanged. Result 35 passed · 4 xfailed, 100% branch coverage.
