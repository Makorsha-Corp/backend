# Execution notes — `app/services/financial_audit_log_service.py`

> Cases: `tests/unit/services/financial_audit_log_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_financial_audit_log_service.py` · Source commit: e48a092
> Result: 24 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_financial_audit_log_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.financial_audit_log_service --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- Normal mode, every test written from its card (`# [claude] <ID>`), in card order; `# Then N` before the checks of Then line N.
- Standing rows W0, W1, W2, UA, UB, UC → fixture `s` (`make_workspace` ×3, then `make_profile` ×3, so the ids rise in that order).
- Convention **log** → `log(db, s, performed_at, **but)`: direct `FinancialAuditLog` insert, one flush per row. The 51 / 101-row Givens → `many_logs(db, s, n)` (`add_all` + one flush, Ek at `H(k)`); `newest` is built from the returned rows in reverse.
- **X** → `mk_x(db)` returns `(X, X_ID)`; **x_gone** is written inline: `db.rollback()` then `db.get(Workspace, x_id) is None`.
- **spies** → context manager `spies(db)` yielding `(cm, rb)` (`patch.object(..., wraps=...)`, the real methods still run).
- `raises: DataError` cards (R-05, E-04): `pytest.raises(DataError)` around `db.begin_nested()` around the call, as Conventions prescribe; `X` was flushed before the savepoint so it survives it.
- Nothing is mocked except the spies. Each happy card also compares with a direct `financial_audit_log_dao` call in the same session (spec Notes).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (17 statements, no branches).

## Factories added
None.

## Notes for maintainers
- Every row has its own `performed_at`, so no test depends on the tie-break of BUG-2370 (carded in the DAO's cases).
- Reference check: a scratch plugin (`ref_fals.py`) that adds `id DESC` as the tie-break to all six DAO readers (BUG-2370's fix) leaves all 24 tests passing (also with `--runxfail`), so the DAO fix will not break this file.
- `--runxfail`: nothing to check (no xfail cards). 3 plain runs: 24 passed each. `ruff` clean, LF endings.

## Useful for the coming permissions / notifications / payments features
- **Permissions**: OQ-23 (who may read the financial audit log) is deferred to the permissions work; today every active member reads it. This service has no caller argument at all, so the gate must live in the endpoint or a new parameter.
- **Payments**: the log is read-only here; who writes it (account, invoice, payment managers) is outside this module.

## Revision history
- **2026-11-09 — Revision 2** (first execution): 22 cases → 22 passed.
- **2026-11-09 — Revision 3** — cases revision 3 (verify finding 1: a cap at the default limit would have passed). New: FALS-R-06 (52 rows, `limit=51` → 51 newest), FALS-E-05 (102 rows, `limit=101` → 101 newest); no test changed or removed. 24 passed; under `ref_fals.py` with `--runxfail` 24 passed; 3 plain runs 24 passed each; coverage 100% branch; ruff clean, LF.
