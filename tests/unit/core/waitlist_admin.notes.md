# Execution notes — `app/core/waitlist_admin.py`

> Cases: `tests/unit/core/waitlist_admin.cases.md` (revision 2) · Tests: `tests/unit/core/test_waitlist_admin.py` · Source commit: e48a092
> Result: 13 passed · 6 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_waitlist_admin.py -q -p no:cacheprovider --cov=app.core.waitlist_admin --cov-branch --cov-report=term-missing`

## How the tests are built
- `get_waitlist_admin` is a plain synchronous function; every test calls it directly with `current_user=` passed explicitly, which bypasses the `Depends(get_current_active_user)` default. No app, no HTTP client.
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - D-NA → module constant `D_NA`.
  - "Allowlist" → fixture `allowlist(values)`: `monkeypatch.setattr(settings, "WAITLIST_ADMIN_EMAILS", list(values), raising=False)`. Every test calls it; nothing relies on the environment's value. `raising=False` keeps the tests valid if the BUG-540 fix removes the setting.
  - "Saved profile P" → `saved_profile(db, email, flag)` (wraps `tests/unit/factories.make_profile`, which flushes). "Row unchanged" → `assert_row_unchanged(db, id, email, flag)`: `expire_all()`, fresh `SELECT email, is_platform_admin`, then `not db.new` and `not db.dirty`.
  - "Unsaved profile" → `unsaved_profile(email, flag)` (`Profile(...)`, never added to a session); "object unchanged" → `assert_obj_unchanged`.
  - "Bare object" → `bare_object()` (`types.SimpleNamespace(email=...)`); "object unchanged" → `assert_bare_unchanged` (email equal, `hasattr(obj, "is_platform_admin") is False`).
- **Mocks:** none (spec: externals none). The only patch is the settings value above.
- **Parametrized:** WLA-G-11..13 (shared xfail BUG-540), WLA-G-14..16, WLA-G-17..19 — each case ID is its own `pytest.param` id.
- **xfail honesty:** verified with `--runxfail`. G-05/07/09 fail on `detail == D_NA` (actual `"Waitlist admin access requires platform admin or WAITLIST_ADMIN_EMAILS"`, BUG-541); G-11/12/13 fail with `DID NOT RAISE HTTPException` (the profile is returned, BUG-540). This matches the "fails today on" column.
- Stability: 3 runs, same outcome each time (13 passed, 6 xfailed).

## Discrepancies
None.

## Coverage gaps
None. Branch coverage is 100% (14 statements, 6 branches).

## Factories added
None. Batch mode: `tests/unit/factories.py` was not edited; the existing `make_profile` is imported. Helpers worth promoting later: `assert_row_unchanged`-style "fresh re-read + no pending session changes" could become a shared helper. The `allowlist` settings-patch fixture could also become a generic `patch_setting(name, value)` fixture in conftest.

## Notes for maintainers
- Saved profiles use fixed emails (`founder@makorsha.com`, `admin@makorsha.com`, …). Every test runs in its own rolled-back transaction, so two concurrent runs can only block briefly on the unique index. They never conflict.
- When **BUG-541** is fixed, G-05/07/09 will XPASS (strict → fail): remove their xfail markers. G-04/06/08 keep guarding the 403.
- When **BUG-540** is fixed, G-11/12/13 will XPASS: remove the marker on `test_wla_g_11_13__allowlisted_non_admin_refused`. If the fix removes `WAITLIST_ADMIN_EMAILS` from settings, the `allowlist` fixture still works (`raising=False`).

## Revision history
- **Cases revision 2 (2026-09-29):** this revision re-ran the cases with no changes to them (same spec, same case IDs, no retired IDs). The verifier (PASS) sent no `test-weakness` findings to the executor. So no tests were added, changed or removed, and only the revision references in the test module docstring and in this file were updated. Re-run: 13 passed, 6 xfailed, branch coverage 100%. The `--runxfail` check still gives 6 failures on the documented assertions (G-05/07/09 fail on `detail == D_NA`, G-11/12/13 fail with DID NOT RAISE). Three stability runs gave the same result each time.
