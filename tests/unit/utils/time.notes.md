# Execution notes — `app/utils/time.py`

> Cases: `tests/unit/utils/time.cases.md` (revision 2) · Tests: `tests/unit/utils/test_time.py` · Source commit: e48a092
> Result: 7 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_time.py -q -p no:cacheprovider --cov=app.utils.time --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database.** `utcnow` is pure (spec Notes); no test takes the `db` fixture.
- **Conventions → helpers** (top of the test file):
  - "real-clock bound" → `real_bound()`: `datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)` using the real module (the test file imports `datetime` itself, so the patch never affects it).
  - LOCAL → module constant `LOCAL = timezone(timedelta(hours=6))`.
  - FROZEN(I) → `FakeDatetime(datetime.datetime)` with class attribute `instant`; `now(tz)`, `utcnow()`, `today()` answer from that one instant exactly as the Conventions define. Fixture `frozen` patches `app.utils.time.datetime` (the target the spec names; the module does `from datetime import datetime`, so the name exists) and yields a setter `frozen(I)`. TIME-U-07 calls the setter twice to advance the clock by 1 µs between the two calls.
- **Mocks:** only `app.utils.time.datetime`, and only in the frozen-clock cases (U-02, U-03, U-04, U-05, U-07). U-01 and U-06 use the real clock. `timezone` in the module is not patched (the real `timezone.utc` is passed to `FakeDatetime.now`).
- No parametrization (each case has distinct assertions).
- Stability: 3 runs, identical outcome (7 passed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (3 statements, 0 branches).

## Factories added
None. No DB models involved. Candidate for promotion to a shared helper later: the `FakeDatetime` / `frozen` clock-freezing fixture, if other modules need a frozen clock at the `datetime`-class level (most modules mock `utcnow` directly instead, which is simpler).

## Notes for maintainers
- If a time-freezing library (`freezegun`, `time_machine`) is added to the dev dependencies, the `FakeDatetime` fixture can be replaced by it; the cases are written against "FROZEN(I)" semantics, not the fake class.
- If `app/utils/time.py` changes its import to `import datetime` (module) instead of `from datetime import datetime`, the patch target `app.utils.time.datetime` would then be the module, and the frozen cases would break — update the fixture (and report to the describer, since the spec names the target).
- If the helper is changed to return aware UTC (docstring mentions a future timestamptz migration), R1 changes and every `tzinfo is None` assertion fails by design — that needs a spec revision first.
- `FakeDatetime.instant` is a class attribute; the `frozen` fixture sets it at the start of each frozen case, so no state leaks into assertions.

## Revision history
- **Cases revision 2** (source commit e48a092): the cases file was re-issued with no changes (IDs TIME-U-01…07 kept, none added or retired); `time.verify.md` verdict PASS with no findings routed to the executor. The test file is unchanged. Re-ran it 3 times with the same result each time (7 passed), and branch coverage is still 100%.
