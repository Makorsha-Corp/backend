# Test cases — `app/utils/timezone_validate.py`

> **Spec:** `tests/unit/utils/timezone_validate.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 22 cases · 18 expected-to-pass · 4 expected-to-fail (bugs) · 4 deferred
> **Revision:** 1 — spec Gap log G1 closed gap 1 (R2 64/65 boundary tested by return value only, no spying on the timezone library); the spec's decision matches the earlier design, so no case changed. No verify report exists yet.
> **Revision:** 2 — spec unchanged; read `timezone_validate.verify.md` (PASS, no Findings). Surviving mutants #7 (`>` → `>=`) and #10 (`64` → `65`) were classed bug-path, not case-missing, but the report's own evidence shows the 65-character side is observable on every platform with a padded spelling, so added TZV-V-21 (pass, `"UTC" + " " * 62` → `False`, kills #10) and its other side TZV-V-22 (`"UTC" + " " * 61`, 64 chars → `False`, xfail BUG-300 on win32) (best-practice default, delegated by reviewer). Observation O2 (trailing dot) left as-is per the report.

## Reviewer summary
- **Per callable:** `is_valid_iana_timezone` 22 cases (4 bug, all BUG-300).
- **Notable design choices:**
  - The 3 BUG-300 cases (`utc`, `Asia\Dhaka`, `Asia/Dhaka `) are expected-to-fail
    **on Windows only**: `xfail(condition=sys.platform == "win32", strict=True, reason="BUG-300")`,
    as the spec's Notes prescribe. On Linux they are ordinary passing tests.
  - R3 gets one extra "whole list" case: every name in `zoneinfo.available_timezones()`
    (minus `posix/…` / `right/…`) must return `True`. Cheap and catches any
    rule that rejects real names.
  - Positive cases also check that `zoneinfo.ZoneInfo(value)` loads, to protect
    the spec's stated invariant ("stored timezones can be loaded later").
  - R2's length limit cannot be observed through the return value at the 64/65
    boundary (no real timezone name is that long, so both sides return `False`).
    Both sides are tested on return value and "no exception" (TZV-V-03/04).
    Revision 2 adds a padded real name on each side (TZV-V-21: 65 chars →
    `False` everywhere, a plain pass case that catches a limit raised above 64;
    TZV-V-22: 64 chars → `False` only after BUG-300 is fixed, so xfail on
    win32). A limit lowered to 63 is still not catchable by a passing test
    until BUG-300 is fixed (best-practice default, delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module
- **Abbreviations:** `TZV` = timezone_validate; `V` = `is_valid_iana_timezone`.
- **No database.** Pure function: call it directly, with no DB session and no
  fixtures. "Database unchanged" checks do not apply (the function has no persistence).
- **Externals mocked:** none. Validity comes from the timezone database installed
  on the host (`tzdata` package; system tz database on Linux).
- **Race simulations:** none.
- **Parametrized rows:** where a row lists several input values, the executor
  writes one parametrized test with one `pytest.param(..., id=...)` per value;
  the case ID goes in the docstring. Each value must meet the row's Then on its own.
- **"No exception"** means the call returns normally (the test calls it without
  `pytest.raises` and asserts on the returned value with `is True` / `is False`,
  never truthiness).
- **BUG-300 marker:** `pytest.mark.xfail(condition=sys.platform == "win32", strict=True, reason="BUG-300")`.
- **Excluded names:** never use `posix/…` or `right/…` prefixed names (they exist on Linux only).

## `is_valid_iana_timezone`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TZV-V-01 | R1 | boundary | — | call with `""` | returns `False` (identity check `is False`); no exception | pass |
| TZV-V-02 | R1 | boundary | — | call with `None` | returns `False`; no exception (in particular no `TypeError`) | pass |
| TZV-V-03 | R2 | boundary | — | call with `"A" * 65` (65 characters) | returns `False`; no exception | pass |
| TZV-V-04 | R2 | boundary | — | call with `"A" * 64` (exactly 64 characters) | returns `False` (rejected by lookup, not length); no exception | pass |
| TZV-V-05 | R3 | happy | — | call with each of `"Asia/Dhaka"`, `"UTC"`, `"America/New_York"`, `"Etc/GMT+6"`, `"GMT"` | returns `True`; the value is in `zoneinfo.available_timezones()`; `zoneinfo.ZoneInfo(value)` loads without error | pass |
| TZV-V-06 | R3 | happy | the host's `zoneinfo.available_timezones()` set, minus names starting with `posix/` or `right/` | call once for every name in that set | the list of names for which the result is not `True` is empty (assert `== []`, so a failure prints the offending names); the set has at least 400 names (guards against an empty tz database making the test vacuous) | pass |
| TZV-V-07 | R4 | happy | — | call with each of `"Asia/Calcutta"`, `"US/Eastern"`, `"EST"`, `"EST5EDT"`, `"Factory"` | returns `True`; the value is in `zoneinfo.available_timezones()`; `zoneinfo.ZoneInfo(value)` loads | pass |
| TZV-V-08 | R5 | error | — | call with `"Nowhere/City"` | returns `False`; no exception | pass |
| TZV-V-09 | R5 | error | — | call with each of `"Asia"`, `"Asia/"` (region folder) | returns `False`; no exception | pass |
| TZV-V-10 | R5 | error | — | call with each of `"../etc"`, `"/etc/UTC"`, `"Asia/../UTC"`, `"Asia/./Dhaka"` (path-like) | returns `False`; no exception | pass |
| TZV-V-11 | R5 | error | — | call with `"Asia/Dhaka\x00"` and with `"Asia/Dh\x00aka"` (NUL character) | returns `False`; no exception (in particular no `ValueError`) | pass |
| TZV-V-12 | R5 | error | — | call with each of `"zone.tab"`, `"tzdata.zi"`, `"leapseconds"` (database metadata files) | returns `False`; no exception | pass |
| TZV-V-13 | R5 | error | — | call with each of `"localtime"`, `"posixrules"` | returns `False`; no exception | pass |
| TZV-V-14 | R5 | error | — | call with `"+06:00"` (offset) | returns `False`; no exception | pass |
| TZV-V-15 | R5 | boundary | — | call with `" Asia/Dhaka"` (one leading space) | returns `False`; no exception (other side of the boundary is TZV-V-05 `"Asia/Dhaka"` → `True`) | pass |
| TZV-V-16 | R5, R6 | boundary | — | call with each of `"asia/dhaka"`, `"ASIA/DHAKA"` (wrong case) | returns `False` on every platform; no exception (other side: TZV-V-05 `"Asia/Dhaka"` → `True`). Regression guard for the case-sensitivity that already works today | pass |
| TZV-V-17 | R6 [BUG-300] | bug | — | call with `"utc"` (lowercase) | returns `False` | xfail BUG-300 on win32 only (strict) — fails today on Windows on: `is False` (returns `True`); passes on Linux |
| TZV-V-18 | R6 [BUG-300] | bug | — | call with `"Asia\\Dhaka"` (Python literal: one backslash between `Asia` and `Dhaka`) | returns `False` | xfail BUG-300 on win32 only (strict) — fails today on Windows on: `is False` (returns `True`); passes on Linux |
| TZV-V-19 | R6 [BUG-300] | bug | — | call with `"Asia/Dhaka "` (one trailing space) | returns `False` | xfail BUG-300 on win32 only (strict) — fails today on Windows on: `is False` (returns `True`); passes on Linux |
| TZV-V-20 | R7, Errors row 1 | error | — | call with the integer `123` | raises `TypeError`; message is exactly `object of type 'int' has no len()` | pass |
| TZV-V-21 | R2 | boundary | — | call with `"UTC" + " " * 62` (a real name padded with trailing spaces to exactly 65 characters; assert `len(value) == 65` in the test) | returns `False`; no exception. Holds on every platform today and after the BUG-300 fix (rejected by length before any lookup) | pass |
| TZV-V-22 | R2, R6 [BUG-300] | bug | — | call with `"UTC" + " " * 61` (exactly 64 characters; assert `len(value) == 64` in the test) | returns `False` (not rejected by length, rejected because it is not an exact canonical name) | xfail BUG-300 on win32 only (strict) — fails today on Windows on: `is False` (returns `True`, per verify report evidence); passes on Linux |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: callers strip whitespace, skip `None`/blank, and turn `False` into a 422 | `RegisterRequest.timezone` (`app/schemas/auth.py`) | `" Asia/Dhaka "` accepted and stored as `"Asia/Dhaka"`; `None`/blank skipped; `"Nowhere/City"` → validation error "Invalid IANA timezone identifier" |
| same | `ProfileCreate.timezone` (`app/schemas/profile.py`) | same three checks |
| same | `ProfileMeUpdate.timezone` (`app/schemas/profile.py`) | same three checks |
| same | workspace settings validator, `settings["timezone"]` (`app/schemas/workspace.py`) | same three checks |

## Spec gaps
None.

Closed in this revision: gap 1 (R2 length-limit boundary not observable) — resolved by spec Gap log G1; TZV-V-03 / TZV-V-04 unchanged.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `is_valid_iana_timezone` | R1 | TZV-V-01, TZV-V-02 |
| `is_valid_iana_timezone` | R2 | TZV-V-03, TZV-V-04, TZV-V-21; TZV-V-22 (xfail on win32) |
| `is_valid_iana_timezone` | R3 | TZV-V-05, TZV-V-06 |
| `is_valid_iana_timezone` | R4 | TZV-V-07 |
| `is_valid_iana_timezone` | R5 | TZV-V-08 … TZV-V-16 |
| `is_valid_iana_timezone` | R6 [BUG-300] | TZV-V-17, TZV-V-18, TZV-V-19, TZV-V-22 (xfail on win32); TZV-V-16, TZV-V-21 (pass, parts that work today) |
| `is_valid_iana_timezone` | R7 / Errors row 1 (`TypeError`) | TZV-V-20 |
| (Overview) | caller strip / 422 behavior | Deferred (4 schema owners) |
