# Execution notes — `app/core/config.py`

> Cases: `tests/unit/core/config.cases.md` (revision 3) · Tests: `tests/unit/core/test_config.py` · Source commit: e48a092
> Result: 54 passed · 35 xfailed · 1 skipped (CFG-S-08, Windows only, by design) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_config.py -q -p no:cacheprovider --cov=app.core.config --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database.** The module is pure; no test requests `db`, so the file runs without touching Postgres (conftest's session `engine` fixture is never instantiated).
- **Conventions → fixtures/helpers** (top of the test file, each commented with its convention):
  - "Clean env (every test)" → autouse fixture `clean_env`: `monkeypatch.delenv(name, raising=False)` for all 26 field names (`FIELD_NAMES`).
  - "`.env` file with lines …" → fixture `env_file(*lines)` writes `tmp_path / "test.env"` and returns the path for `_env_file=`.
  - "cwd .env" → fixture `cwd_env(*lines)` writes `tmp_path / ".env"` and `monkeypatch.chdir(tmp_path)`.
  - "Guard" → fixture `guard(env=None, dotenv_lines=None)`: chdir to empty `tmp_path` at setup, sets env vars / writes cwd `.env`, then `importlib.reload(app.core.config)` and returns the module. Teardown calls `monkeypatch.undo()` explicitly (the fixture's own teardown runs before monkeypatch's) and then reloads the module again so later tests (and other test files) see a normal module built from the real env/cwd.
  - "safe prod" → `safe_prod(**overrides)` returns the env dict; `K40/K32/K31/DEFAULT_KEY/DEFAULT_MSG` are module constants.
  - "ValidationError assertions" → `assert_field_in_error_loc(exc_info, field)`.
- **Mocks:** none (spec: externals none). Inputs are env vars, temp `.env` files, and kwargs only.
- **Parametrized** (each case ID is its own `pytest.param` id): S-12..15, S-17/18, S-37..39, CO direct calls (01/02/03/05/14/15), CO-06/07, CO-10..13, WA direct calls (01/02/03/05/06/09/10/11), G-02/03, G-06/07/09.
- **xfail honesty:** verified with `--runxfail`; every xfail fails on the "fails today on" assertion: BUG-420 env/.env cases raise `SettingsError` (JSON decode) in construction; S-31 raises `SettingsError` instead of `ValidationError`; CO-06/07/08 and WA-07 return the un-parsed `'["…"]'` strings; CO-09/WA-08/S-37..39/G-18 `DID NOT RAISE ValidationError`; CO-10..13 keep `""`; S-34..36 keep the raw case/spacing; G-06..10/15..17 `DID NOT RAISE RuntimeError`; S-11/G-11 `assert True is False`.
- **CFG-S-08** is `skipif(sys.platform == "win32")` per the cases file; it runs only on Linux CI.
- Stability: 3 runs, identical outcome each time; also run together with `test_waitlist_admin.py` (which imports `settings`) with no interference from the reloads.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (46 statements, 6 branches).

## Factories added
None. Batch mode: `tests/unit/factories.py` not edited, and this module uses no models. Worth promoting later: the `guard` reload fixture pattern (chdir to empty dir + reload + undo/reload teardown) as a conftest helper if other import-time guards appear; `assert_field_in_error_loc` as a shared pydantic assertion helper.

## Notes for maintainers
- **Reload side effect:** `importlib.reload` rebinds `app.core.config.settings` and `Settings` only; modules that did `from app.core.config import settings` keep the original object. Tests assert only through the reloaded module. The teardown reload uses the real process env and the pytest cwd (backend root, so the developer's `.env` is read) — if that `.env` is itself invalid, guard-test teardown will error.
- **TODO-001:** CFG-S-10 and CFG-G-12 assert that `SSLCOMMERZ_MOCK_MODE` is on in production *as intended today*. When the mock is removed or guarded to non-production, revisit both cases (cases file first, then these tests).
- When **BUG-420** is fixed: S-24..31, CO-06..09, WA-07/08 XPASS → remove their markers. S-30 also needs BUG-421.
- When **BUG-421** is fixed: CO-10..13 XPASS (S-30 needs BUG-420 too).
- When **BUG-422** is fixed: G-06/07/08/09 XPASS; G-17 needs BUG-423 too.
- When **BUG-423** is fixed: S-34..39, G-15, G-18 XPASS; G-16 also needs BUG-424, G-17 also needs BUG-422.
- When **BUG-424** is fixed: S-11, G-10, G-11 XPASS. Note CFG-G-01/G-13 set `DEBUG=true` explicitly, so the default flip will not break them.

## Revision history
- **Cases revision 3 (2026-09-29):** the case designer re-ran on the unchanged spec after `config.verify.md` returned PASS with no findings. No case IDs were added, changed or retired, and no `test-weakness` findings were routed here, so `test_config.py` is **unchanged**. Surviving mutant #18 (`DEBUG` default `True -> False`) is BUG-424 fix behavior that xfail CFG-S-11 / CFG-G-11 already assert. No passing case pins today's buggy default (best-practice default, delegated by reviewer, per cases revision 3). Re-ran 3 times: 54 passed · 1 skipped · 35 xfailed each time, 100% branch coverage on `app/core/config.py`. Note: while other agents run in parallel, the `term-missing` table can list modules from other agents' coverage data; only the `app\core\config.py` row applies here.
