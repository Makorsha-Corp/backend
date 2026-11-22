# Execution notes — `app/services/base_service.py`

> Cases: `tests/unit/services/base_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_base_service.py` · Source commit: e48a092
> Result: 8 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_base_service.py -q -p no:cacheprovider --cov=app.services.base_service --cov-branch --cov-report=term-missing`

## How the tests are built
- `svc = BaseService()` at module level; both helpers called with `db` positionally.
- "commit point" = `commit_point(db)` → `db.commit()`; under the `db` fixture this only releases a savepoint, so a later `db.rollback()` returns to that point and the fixture's outer rollback discards everything.
- `found(db, name)` = fresh `select(count)` on `Workspace.name`. `committed:` lines run one `db.rollback()` before the first check; `count:` lines do not.
- "session: usable" = `usable(db)` → `make_workspace(db, name="After").id is not None`.
- Failing commit / failing rollback / spies are `patch.object(db, ...)` exactly as Conventions write them, nested inside `pytest.raises` (ruff SIM117 is silenced file-wide for that reason). BSV-C-03 uses the failing-commit block with the rollback wrap but without `as rb`, since its card checks no call count.
- 3 plain runs: 8 passed each time; no flakiness.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage.

## Factories added
None.

## Notes for maintainers
- The tests rely on `join_transaction_mode="create_savepoint"` in `tests/unit/conftest.py`: `db.rollback()` after a commit point keeps rows committed before it. Changing the fixture's transaction mode breaks BSV-C-01, C-02, C-05, R-01.
- `found()` counts by workspace name across all workspaces; the names used ("Before", "Edited", "Kept", ...) must not exist as committed rows in `marker_test`.
