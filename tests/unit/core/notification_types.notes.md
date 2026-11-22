# Execution notes — `app/core/notification_types.py`

> Cases: `tests/unit/core/notification_types.cases.md` (READY, 5 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/core/test_notification_types.py` · Source commit: e48a092
> Result: **5 tests for 5 cases — 5 passed · 0 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (10 statements, 0 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_notification_types.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`acctx\audit.py`) found 0 problems.

## How the tests are built
- `KINDS`, `SOURCES`, `WEB_KINDS` are module constants copied from the Conventions. No database, nothing mocked.
- NTY-K-01's When (`values = KINDS`) is kept as written; its Then lines read the constants by name, so the variable carries `# noqa: F841`.

## xfail check
No xfail card.

## Discrepancies
None.

## Coverage gaps
None — 100% (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 runs: 5 passed each time. `ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- `WEB_KINDS` mirrors the web app's `NotificationKind`; change it with that list (cases Reviewer summary).
