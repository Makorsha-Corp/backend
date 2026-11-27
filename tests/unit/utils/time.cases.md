# Test cases — `app/utils/time.py`

> **Spec:** `tests/unit/utils/time.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run on the unchanged spec (commit e48a092, rules R1–R4 identical); `time.verify.md` verdict PASS with no Findings and no case-designer (`case-missing`) items (only hand mutant H1, equivalent, no action). All case IDs TIME-U-01…07 kept as they were; none added or retired.
> **Counts:** 7 cases · 7 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `utcnow` 7 cases (0 bug).
- **Notable design choices:**
  - No database is used: the function is pure (spec Notes). Tests need no session fixture.
  - No time-freezing library is installed in `.venv` (checked: neither `freezegun` nor `time_machine`
    imports), so frozen-clock cases patch `app.utils.time.datetime` (the target the spec names) with a
    small fake `datetime` subclass defined in the test file. The fake answers every usual "current
    time" entry point from ONE frozen aware instant, so the cases do not depend on which one the
    implementation calls (best-practice default, delegated by reviewer). See Conventions.
  - The "UTC, not local" half of R2 is tested deterministically with the frozen clock and a fake
    local zone of UTC+06:00 (TIME-U-03), because the real test machine may itself be on UTC and a
    real-clock comparison against local time would then prove nothing (best-practice default,
    delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module

- **IDs:** `TIME` = `app/utils/time.py`; `U` = `utcnow`.
- **No DB, no externals mocked** (spec: "Externals to mock: none").
- **Real-clock bound** ("naive-UTC reading"): `datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)`,
  taken with the real, unpatched `datetime` module. Never `datetime.now()` without a tz (local time).
- **Frozen clock (FROZEN(I))** — patch `app.utils.time.datetime` for the duration of the case with a
  fake class `FakeDatetime(datetime.datetime)` holding one aware instant `I`, and a fake local zone
  `LOCAL = timezone(timedelta(hours=6))`:
  - `FakeDatetime.now(tz=None)` → if `tz` is given: `I.astimezone(tz)`; if `tz` is None: `I.astimezone(LOCAL).replace(tzinfo=None)` (naive LOCAL time, as the real `now()` gives naive local time).
  - `FakeDatetime.utcnow()` → `I.astimezone(timezone.utc).replace(tzinfo=None)`.
  - `FakeDatetime.today()` → same as `now(None)`.
  The fake local zone is deliberately not UTC so that an implementation returning local time is
  caught. (best-practice default, delegated by reviewer)
  If the executor finds the patch target does not exist (the module does not import a name
  `datetime`), that is a spec problem to report back, not a reason to change the case.
- Comparisons of results use plain `datetime.datetime(...)` values; the fake subclass compares equal
  to them. Type checks use `isinstance(result, datetime.datetime)`.

## `utcnow`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| TIME-U-01 | R1, R2 | happy | real clock; `before` = real-clock bound taken immediately before the call | call `utcnow()`; then take `after` = real-clock bound | `isinstance(result, datetime.datetime)`; `result.tzinfo is None`; `before <= result <= after` | pass |
| TIME-U-02 | R1, R3 | happy | FROZEN(`2026-01-15 10:30:45.123456+00:00`) | call `utcnow()` | result `== datetime(2026, 1, 15, 10, 30, 45, 123456)`; `result.tzinfo is None`; `result.microsecond == 123456` | pass |
| TIME-U-03 | R2, R3 | boundary | FROZEN(`2026-01-15 16:30:45.123456+06:00`) — fake local zone is UTC+06:00, so naive local now is 16:30:45.123456 | call `utcnow()` | result `== datetime(2026, 1, 15, 10, 30, 45, 123456)` (converted to UTC); result `!= datetime(2026, 1, 15, 16, 30, 45, 123456)` (not local time); `result.tzinfo is None` | pass |
| TIME-U-04 | R3 | boundary | FROZEN(`2026-01-01 03:15:00.000001+06:00`) — UTC conversion crosses the day/month/year | call `utcnow()` | result `== datetime(2025, 12, 31, 21, 15, 0, 1)`; `result.microsecond == 1`; `result.tzinfo is None` | pass |
| TIME-U-05 | R3 | boundary | FROZEN(`2026-06-30 23:59:59.999999+00:00`) — last microsecond of a second/day | call `utcnow()` | result `== datetime(2026, 6, 30, 23, 59, 59, 999999)` (not rounded up to `2026-07-01 00:00:00`, not truncated to whole seconds); `result.tzinfo is None` | pass |
| TIME-U-06 | R4, R1 | happy | real clock | call `utcnow()` twice in a row → `first`, `second` | `second >= first`; `first.tzinfo is None`; `second.tzinfo is None` | pass |
| TIME-U-07 | R4 | boundary | FROZEN(`2026-01-15 10:30:45.123456+00:00`); after the first call, move the frozen instant forward by exactly 1 microsecond to `2026-01-15 10:30:45.123457+00:00` | call `utcnow()` → `first`; advance clock; call `utcnow()` → `second` | `first == datetime(2026, 1, 15, 10, 30, 45, 123456)`; `second == datetime(2026, 1, 15, 10, 30, 45, 123457)`; `second - first == timedelta(microseconds=1)` (each call reads the clock afresh, no caching) | pass |

## Deferred to other specs
None.

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `utcnow` | R1 (naive, `tzinfo is None`) | TIME-U-01, TIME-U-02, TIME-U-03, TIME-U-04, TIME-U-05, TIME-U-06 |
| `utcnow` | R2 (current UTC, between bounds; not local) | TIME-U-01, TIME-U-03 |
| `utcnow` | R3 (frozen instant → UTC, tz removed, µs kept) | TIME-U-02, TIME-U-03, TIME-U-04, TIME-U-05 |
| `utcnow` | R4 (successive calls never go backwards) | TIME-U-06, TIME-U-07 |
| `utcnow` | Errors: none | — (no error rows) |
| `utcnow` | Side effects: none | — (pure; no DB used) |
| `utcnow` | BUG tags: none | — |
