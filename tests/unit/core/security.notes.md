# Execution notes — `app/core/security.py`

> Cases: `tests/unit/core/security.cases.md` (revision 2, READY) · Tests: `tests/unit/core/test_security.py` · Source commit: e48a092
> Result: 61 passed · 7 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_security.py -q -p no:cacheprovider --cov=app.core.security --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database.** The module is pure; no test uses the `db` fixture and there is no persisted state to re-read.
- **Conventions → code** (top of the test file, each commented):
  - K1/K2, T0, A72/A73/TK24/TK25 → module constants; `ts(h, m, s)` → helper.
  - "Settings in every test" → autouse fixture `_settings` (`monkeypatch.setattr` on `app.core.config.settings`: `SECRET_KEY=K1`, `ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES=15`). Per-case overrides (CAT-02, CAT-05, DT-07) call `monkeypatch.setattr` again inside the test.
  - "utcnow = X" → `patch_utcnow(value)` (`patch.object(app.core.security, "utcnow", return_value=value)`); fixture `at_t0` for the T0 cases. This is the only mock (spec Externals).
  - NOW / REAL_UTCNOW → per-test fixtures read from the real clock at test start.
  - H1 → module-scoped fixture (one real bcrypt hash shared, read-only), as the cases allow.
  - `peek`, `header`, `sign`, `b64url_nopad` → local helpers exactly as defined in Conventions.
- **Parametrized** (each case ID is its own `pytest.param` id): CAT-15/16, VP-02/03/04, VP-05/06, GPH-03/05, HRT-01/02.
- **xfail honesty** verified with `--runxfail`: CAT-11 fails on `exp == ts(12,0,0)` (actual `ts(12,15,0)`, default applied); VP-14..18 raise `ValueError("Password exceeds bcrypt's 72-byte limit")`; DT-17 returns `{"sub": "1"}` instead of `None`.
- Stability: 3 runs, identical outcome (61 passed, 7 xfailed), ~6 s each.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (46 statements, 8 branches).

## Factories added
None (no models involved). No builders worth promoting; the JWT helpers (`sign`, `peek`) could move to a shared `tests/unit/_jwt.py` if `app/core/deps.py` tests need hand-signed tokens.

## Notes for maintainers
- PyJWT emits `InsecureKeyLengthWarning` for HS512 with the 37-byte K1 (CAT-02, DT-11). Harmless; comes from the key sizes fixed in the cases.
- DT-02..DT-05 depend on the real clock (5 s / 60 s / 1 min margins); a very slow machine pausing > 5 s between `NOW` and decode could only affect DT-05 (60 s margin) in the extreme.
- **When a bug is fixed**, its strict xfails XPASS → remove the marker: BUG-500 (VP-14..VP-18), BUG-501 (CAT-11), BUG-502 (DT-17). VP-07 is the regression guard for the BUG-500 fix and must keep passing.

## Revision history
- **Revision 2 (cases rev 2, source e48a092, 2026-09-29):** re-run on cases revision 2, which adds, changes and retires no cases (the cases file says no rule changes; `security.verify.md` routed no findings to the executor). Test file left unchanged. Re-verified: every case ID in the cases file is in the test file (ID set diff empty). The file ended 61 passed · 7 xfailed on three runs; `--runxfail` gives 7 failed (the xfails are honest); `app.core.security` has 100% branch coverage (46 stmts, 8 branches). No discrepancies. No decisions needed.
