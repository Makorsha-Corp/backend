# Execution notes — `app/utils/datetime_serialize.py`

> Cases: `tests/unit/utils/datetime_serialize.cases.md` (revision 2) · Tests: `tests/unit/utils/test_datetime_serialize.py` · Source commit: e48a092
> Result: 53 passed · 18 xfailed · 0 discrepancies · 0 errors (21 cases: 17 pass cases → 53 param items; 4 xfail cases → 18 param items) — branch coverage 62% module / 100% of `ensure_utc_z_in_json` (only the dead `serialize_utc_datetime` is uncovered)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_datetime_serialize.py -q -p no:cacheprovider --cov=app.utils.datetime_serialize --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no mocks.** The function is pure (spec Overview: externals none); no test takes the `db` fixture.
- **Conventions → helpers** (top of the test file):
  - `f` → module alias `f = ensure_utc_z_in_json`.
  - `DT` → module constant `DT = "2026-01-01T10:00:00"`.
  - "Not mutated" → `copy.deepcopy(input)` before the call, `input == copy` after (E-10, E-12, E-13).
  - `M` → local helper `_make_m(**fields)` that builds a throw-away `AppResponseModel` subclass with `type(...)` from `{name: (annotation, default)}`; serialized with `model_dump(mode="json")` (E-19, E-20).
- **Parametrization:** cases that list several input values (E-02, E-03, E-04, E-05, E-06, E-08, E-09, E-17) are one test function each, parametrized with readable param ids. For xfail cases (E-04, E-09) the strict xfail mark is on the whole function, so every value must fail today — it does (12/12 and 4/4 xfailed).
- **Depth test (E-15):** builds 200 levels alternating `[...]` (even i) and `{"k": ...}` (odd i) in a loop, then unwraps in reverse order.
- **Identity checks:** R3/R8 cases assert `is` (E-16, E-17, E-18); R1/R2 cases assert `is not` plus non-mutation.
- Stability: 3 runs, identical outcome (53 passed, 18 xfailed).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 16-25 | dead | `serialize_utc_datetime` — listed as dead code to remove in the spec's "Not specified" (reviewer Q5). No cases by design. |

`ensure_utc_z_in_json` (lines 28-36): all statements and all branches covered.

## Factories added
None (batch mode; no DB models involved). Candidate for promotion later: `_make_m` (throw-away `AppResponseModel` subclass builder) if other schema-level tests need ad-hoc response models.

## Notes for maintainers
- When BUG-160 is fixed (type-level Z / calendar validation), E-04 (all 12 params) and E-19 will XPASS → remove their xfail markers. E-05 and E-20 are designed to pass both before and after.
- When BUG-161 is fixed (`fullmatch` / `\Z`), E-07 XPASSes → remove the marker.
- When BUG-162 is fixed (`[0-9]` instead of `\d`), E-09 (all 4 params) XPASSes → remove the marker.
- If the BUG-160 fix removes the string walker entirely, most of this file (R1–R8, R10) becomes obsolete — needs a spec revision first.
- When `serialize_utc_datetime` is removed, the module's coverage rises to 100% with no test change.
- The non-ASCII parameter strings (Arabic-Indic, Bengali, fullwidth) are literal UTF-8 in the test file; keep the file UTF-8 encoded.

## Revision history
- **2026-09-29 — cases revision 2.** Cases file re-issued on the same APPROVED spec (source commit e48a092) with no added, changed or retired case IDs; the verifier's PASS had no findings routed to the executor. Tests kept unchanged (only the module docstring's revision number updated). Re-ran 3 times: 53 passed · 18 xfailed each run; branch coverage unchanged at 62% (100% of `ensure_utc_z_in_json`; only dead `serialize_utc_datetime` lines 16-25 missed).
