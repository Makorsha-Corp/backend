# Execution notes — `app/core/notification_channels.py`

> Cases: `tests/unit/core/notification_channels.cases.md` (READY, 3 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/core/test_notification_channels.py` · Source commit: e48a092
> Result: **3 tests for 3 cases — 3 passed · 0 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (1 statement, 0 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_notification_channels.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`acctx\audit.py`) found 0 problems (IDs, docstrings, `# Then` blocks, markers, literals, LF).

## How the tests are built
- NCH-01, NCH-02: plain value checks; no database.
- NCH-03: **TEST_DSN** (Spec gap 1) is the fixture `dsn`, = the URL of the session's `engine` fixture (`tests/unit/conftest.py`, the engine the test session's `db` is bound to), rendered with its password and driver name `postgresql` so `psycopg2.connect` accepts it. Path as assumed in Spec gap 1, chosen here: the engine's URL (it already resolves `TEST_DATABASE_URL` and its default). Two autocommit connections outside the test session; `LISTEN` with the name pasted unquoted; `pg_notify` from the sender; both closed in a `finally`. Nothing is written to any table.
- Nothing is mocked.

## xfail check
No xfail card.

## Discrepancies
None.

## Coverage gaps
None — 100% (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 runs of the file alone: 3 passed each time. `select.select` on the listener's socket returned within the 5-second wait in every run. `ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- NCH-03 needs the test database to accept two extra connections; it does not use `db`.
