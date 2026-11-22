# Test cases — `app/core/config.py`

> **Spec:** `tests/unit/core/config.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 — re-run on unchanged spec (APPROVED, e48a092). Read `config.verify.md` (Verdict PASS, cases revision 2): Findings none; no `case-missing` items. Surviving mutant #18 (`DEBUG` default `True -> False`) is classed bug-path with no "Fix by" — it applies the BUG-424 fix and is already asserted by xfail CFG-S-11 / CFG-G-11; a passing case pinning today's `DEBUG=True` default would test the buggy path (forbidden), so no case added (best-practice default, delegated by reviewer). All case IDs kept; no cases added or retired.
> **Revision history:** 2 — re-run on unchanged spec (Q6 intended-for-now with TODO-001, BUG-424 DEBUG default off); no verify report then.
> **Counts:** 90 cases · 55 expected-to-pass · 35 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `Settings` 40 cases (15 bug) · `assemble_cors_origins` 17 cases (8 bug) · `assemble_waitlist_admin_emails` 13 cases (2 bug) · module import guard 20 cases (10 bug).
- **Bugs covered:** BUG-420 (list settings from env/.env), BUG-421 (CORS keeps empty pieces), BUG-422 (weak/blank SECRET_KEY in prod), BUG-423 (ENVIRONMENT normalisation/allowed values), BUG-424 (DEBUG default / DEBUG in prod).
- **Q6 / TODO-001:** mock payment gateway on in production is tested as *intended today* (CFG-S-10, CFG-G-12), passing cases, no xfail. When TODO-001 is done (mock removed or guarded to non-production), those two cases must be revisited.
- **Notable design choices** (all best-practice default, delegated by reviewer):
  - Guard tests reload `app.core.config` in-process (`importlib.reload`) from an empty temp working directory, then reload again after restoring env/cwd. No subprocess, so blank values survive on Windows.
  - Blank values (`SECRET_KEY=`, `WAITLIST_ADMIN_EMAILS=`, `BACKEND_CORS_ORIGINS=`) are supplied through a temp `.env` file, not an empty OS variable (Windows drops empty OS variables in child/CRT views).
  - Bool coercion is checked on fields whose default is the opposite value (`SSLCOMMERZ_SANDBOX` default True, `WORK_ORDER_ALLOW_DEV_DELETE` default False), so the BUG-424 default change cannot mask or break them.
  - CFG-S-08 (OS env var names are case-sensitive) is skipped on Windows, per spec Notes; it only runs on Linux CI.
  - No database is used: this module is pure. Error cases have no DB state to check; "nothing changed" is replaced by "no `Settings` instance returned / import did not complete".
- **Needs a decision:** None.

## Conventions for this module

**IDs:** `CFG` = `app/core/config.py`. `S` = `Settings` (fields, defaults, loading) · `CO` = `Settings.assemble_cors_origins` · `WA` = `Settings.assemble_waitlist_admin_emails` · `G` = module import guard.

**Clean env (every test):** `monkeypatch.delenv(name, raising=False)` for every field name: `API_V1_STR`, `PROJECT_NAME`, `VERSION`, `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `BACKEND_CORS_ORIGINS`, `TURNSTILE_SECRET_KEY`, `WAITLIST_ADMIN_EMAILS`, `WAITLIST_IP_HASH_SALT`, `ENVIRONMENT`, `DEBUG`, `WORK_ORDER_ALLOW_DEV_DELETE`, `SSLCOMMERZ_MOCK_MODE`, `SSLCOMMERZ_STORE_ID`, `SSLCOMMERZ_STORE_PASSWORD`, `SSLCOMMERZ_SANDBOX`, `FRONTEND_BASE_URL`, `BACKEND_BASE_URL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `CLOUDINARY_UPLOAD_ENV`, `MAX_ATTACHMENTS_PER_ENTITY`. Then set only what the case's Given says with `monkeypatch.setenv`.

**Construction (`S`, `CO`, `WA` cases):** `Settings(_env_file=None, **kwargs)` unless the Given names a `.env` file. "`.env` file with lines …" = write those lines to `tmp_path / "test.env"` and pass `_env_file=<that path>`. "cwd .env" = write `tmp_path / ".env"`, `monkeypatch.chdir(tmp_path)`, construct `Settings()` with no `_env_file`.

**Direct converter calls:** `Settings.assemble_cors_origins(v)` / `Settings.assemble_waitlist_admin_emails(v)` (classmethods, per spec Notes).

**Guard (`G` cases):** clean env as above, `monkeypatch.chdir(tmp_path)` (an empty dir, so no `.env` unless the Given writes `tmp_path / ".env"`), set the Given's env vars, then `importlib.reload(app.core.config)`. "import succeeds" = reload returns; read `app.core.config.settings` from the reloaded module (never through other modules). Teardown (every G case, even on failure): undo monkeypatch env/cwd, then `importlib.reload(app.core.config)` again so later tests see a normal module. (best-practice default, delegated by reviewer)
- `K40` = `"k" * 40` (valid 40-char secret). `K32` = `"k" * 32`. `K31` = `"k" * 31`.
- "safe prod" = `ENVIRONMENT=production`, `SECRET_KEY=K40`, `DEBUG=false`. Each guard case changes exactly one thing from safe prod unless it says otherwise (spec Notes: one violation at a time).
- `DEFAULT_KEY` = `"your-secret-key-change-this-in-production"`. `DEFAULT_MSG` = `"SECRET_KEY must be changed from the default before running in production."`.

**ValidationError assertions:** `pytest.raises(pydantic.ValidationError)`; where the Then names a field, assert that field name appears in the `loc` of at least one entry of `exc.errors()`. (best-practice default, delegated by reviewer)

**Externals mocked:** none. **Time:** not used. **Database:** not used (pure module). **Race simulations:** none.

## `Settings` (fields, defaults, loading)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CFG-S-01 | R1 | happy | clean env; OS env `PROJECT_NAME=FromEnv` | `Settings(_env_file=None, PROJECT_NAME="FromKwarg")` | `.PROJECT_NAME == "FromKwarg"` | pass |
| CFG-S-02 | R1 | happy | clean env; OS env `PROJECT_NAME=FromEnv`; `.env` file with `PROJECT_NAME=FromDotenv` | `Settings(_env_file=<file>)` | `.PROJECT_NAME == "FromEnv"` | pass |
| CFG-S-03 | R1 | happy | clean env; `.env` file with `PROJECT_NAME=FromDotenv` | `Settings(_env_file=<file>)` | `.PROJECT_NAME == "FromDotenv"`; `.VERSION == "1.0.0"` (unset field keeps default) | pass |
| CFG-S-04 | R2 | boundary | clean env; path `tmp_path / "missing.env"` does not exist | `Settings(_env_file=<missing path>)` | no error; `.PROJECT_NAME == "ERP API"`; `.ENVIRONMENT == "development"` | pass |
| CFG-S-05 | R2 | boundary | clean env; `monkeypatch.chdir(tmp_path)` with no `.env` in it | `Settings()` (default env file) | no error; `.PROJECT_NAME == "ERP API"` | pass |
| CFG-S-06 | R1 (default `.env` path) | happy | clean env; cwd .env with `PROJECT_NAME=FromCwdDotenv` | `Settings()` | `.PROJECT_NAME == "FromCwdDotenv"` | pass |
| CFG-S-07 | R3, R8 | error | clean env; `.env` file with `environment=production` | `Settings(_env_file=<file>)` | raises `ValidationError`; `str(exc)` contains `"Extra inputs are not permitted"` | pass |
| CFG-S-08 | R3 | boundary | skip if `sys.platform == "win32"` (spec Notes); clean env; OS env `project_name=lower` | `Settings(_env_file=None)` | no error; `.PROJECT_NAME == "ERP API"` | pass |
| CFG-S-09 | R4, R9 | happy | clean env | `Settings(_env_file=None)` | every field equals the R4 table exactly: `API_V1_STR "/api/v1"`, `PROJECT_NAME "ERP API"`, `VERSION "1.0.0"`, `DATABASE_URL "postgresql://postgres:postgres@localhost:5432/marker_db"`, `SECRET_KEY DEFAULT_KEY`, `ALGORITHM "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES 15`, `REFRESH_TOKEN_EXPIRE_DAYS 14`, `BACKEND_CORS_ORIGINS ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://localhost:4173"]` (that order), `TURNSTILE_SECRET_KEY ""`, `WAITLIST_ADMIN_EMAILS []`, `WAITLIST_IP_HASH_SALT ""`, `ENVIRONMENT "development"`, `WORK_ORDER_ALLOW_DEV_DELETE False`, `SSLCOMMERZ_MOCK_MODE True`, `SSLCOMMERZ_STORE_ID ""`, `SSLCOMMERZ_STORE_PASSWORD ""`, `SSLCOMMERZ_SANDBOX True`, `FRONTEND_BASE_URL "http://localhost:5173"`, `BACKEND_BASE_URL "http://localhost:8000"`, `CLOUDINARY_CLOUD_NAME ""`, `CLOUDINARY_API_KEY ""`, `CLOUDINARY_API_SECRET ""`, `CLOUDINARY_UPLOAD_ENV "development"`, `MAX_ATTACHMENTS_PER_ENTITY 25`; ints are `int`, bools are `bool` (use `is True`/`is False`). `DEBUG` not asserted here (R4a) | pass |
| CFG-S-10 | R4 (Q6, TODO-001) | happy | clean env | `Settings(_env_file=None, ENVIRONMENT="production")` | `.SSLCOMMERZ_MOCK_MODE is True`; `.ENVIRONMENT == "production"` | pass |
| CFG-S-11 | R4a [BUG-424] | bug | clean env (no `DEBUG` anywhere) | `Settings(_env_file=None)` | `.DEBUG is False` | xfail BUG-424 — fails today on: `DEBUG is False` (is `True`) |
| CFG-S-12 | R5 | boundary | clean env; OS env `SSLCOMMERZ_SANDBOX=false` | `Settings(_env_file=None)` | `.SSLCOMMERZ_SANDBOX is False` | pass |
| CFG-S-13 | R5 | boundary | clean env; OS env `SSLCOMMERZ_SANDBOX=0` | `Settings(_env_file=None)` | `.SSLCOMMERZ_SANDBOX is False` | pass |
| CFG-S-14 | R5 | boundary | clean env; OS env `WORK_ORDER_ALLOW_DEV_DELETE=true` | `Settings(_env_file=None)` | `.WORK_ORDER_ALLOW_DEV_DELETE is True` | pass |
| CFG-S-15 | R5 | boundary | clean env; OS env `WORK_ORDER_ALLOW_DEV_DELETE=1` | `Settings(_env_file=None)` | `.WORK_ORDER_ALLOW_DEV_DELETE is True` | pass |
| CFG-S-16 | R5 | happy | clean env; OS env `ACCESS_TOKEN_EXPIRE_MINUTES=30` | `Settings(_env_file=None)` | `.ACCESS_TOKEN_EXPIRE_MINUTES == 30` and `type(...) is int` | pass |
| CFG-S-17 | R5, Errors row 1 | error | clean env; OS env `DEBUG=release` | `Settings(_env_file=None)` | raises `ValidationError`; `DEBUG` in an error `loc` | pass |
| CFG-S-18 | R5, Errors row 1 | error | clean env; OS env `MAX_ATTACHMENTS_PER_ENTITY=abc` | `Settings(_env_file=None)` | raises `ValidationError`; `MAX_ATTACHMENTS_PER_ENTITY` in an error `loc` | pass |
| CFG-S-19 | R6 | happy | clean env; OS env `BACKEND_CORS_ORIGINS=["http://a.com", "http://b.com"]` | `Settings(_env_file=None)` | `.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]` | pass |
| CFG-S-20 | R6 | happy | clean env; `.env` file with `BACKEND_CORS_ORIGINS=["http://a.com"]` | `Settings(_env_file=<file>)` | `.BACKEND_CORS_ORIGINS == ["http://a.com"]` | pass |
| CFG-S-21 | R6 | happy | clean env; OS env `WAITLIST_ADMIN_EMAILS=["ops@makorsha.com", "cto@makorsha.com"]` | `Settings(_env_file=None)` | `.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]` | pass |
| CFG-S-22 | R6 | happy | clean env; `.env` file with `WAITLIST_ADMIN_EMAILS=["ops@makorsha.com"]` | `Settings(_env_file=<file>)` | `.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com"]` | pass |
| CFG-S-23 | Errors row 2 (not array of strings) | error | clean env; OS env `BACKEND_CORS_ORIGINS=[1, 2]` | `Settings(_env_file=None)` | raises `ValidationError`; `BACKEND_CORS_ORIGINS` in an error `loc` | pass |
| CFG-S-24 | R7 [BUG-420]; `assemble_cors_origins` R1 | bug | clean env; OS env `BACKEND_CORS_ORIGINS=http://a.com, http://b.com` | `Settings(_env_file=None)` | no error; `.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-25 | R7 [BUG-420]; `assemble_cors_origins` R1 | bug | clean env; `.env` file with `BACKEND_CORS_ORIGINS=http://a.com, http://b.com` | `Settings(_env_file=<file>)` | no error; `.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-26 | R7 [BUG-420]; `assemble_waitlist_admin_emails` R1 | bug | clean env; OS env `WAITLIST_ADMIN_EMAILS=ops@makorsha.com, cto@makorsha.com` | `Settings(_env_file=None)` | no error; `.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-27 | R7 [BUG-420]; `assemble_waitlist_admin_emails` R1 | bug | clean env; `.env` file with `WAITLIST_ADMIN_EMAILS=ops@makorsha.com, cto@makorsha.com` | `Settings(_env_file=<file>)` | no error; `.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-28 | R7 [BUG-420]; `assemble_waitlist_admin_emails` R1 | bug | clean env; `.env` file with line `WAITLIST_ADMIN_EMAILS=` (empty value) | `Settings(_env_file=<file>)` | no error; `.WAITLIST_ADMIN_EMAILS == []` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-29 | R7 [BUG-420] | bug | clean env; OS env `WAITLIST_ADMIN_EMAILS="   "` (three spaces) | `Settings(_env_file=None)` | no error; `.WAITLIST_ADMIN_EMAILS == []` | xfail BUG-420 — fails today on: construction raises `SettingsError` |
| CFG-S-30 | R7 [BUG-420] [BUG-421] | bug | clean env; `.env` file with line `BACKEND_CORS_ORIGINS=` (empty value) | `Settings(_env_file=<file>)` | no error; `.BACKEND_CORS_ORIGINS == []` | xfail BUG-420 — fails today on: construction raises `SettingsError` (after BUG-420 alone it would still fail on `[""]`, BUG-421) |
| CFG-S-31 | Errors row 2 (malformed JSON, any source) [BUG-420] | bug | clean env; OS env `BACKEND_CORS_ORIGINS=["http://a.com"` (no closing bracket) | `Settings(_env_file=None)` | raises `pydantic.ValidationError` (not `SettingsError`) | xfail BUG-420 — fails today on: `SettingsError` raised instead of `ValidationError` |
| CFG-S-32 | R8, Errors row 3 | error | clean env; `.env` file with `REDIS_URL=redis://localhost:6379` | `Settings(_env_file=<file>)` | raises `ValidationError`; `str(exc)` contains `"Extra inputs are not permitted"`; `REDIS_URL` in an error `loc` | pass |
| CFG-S-33 | R8 | boundary | clean env; OS env `REDIS_URL=redis://localhost:6379` and `MAKORSH_UNKNOWN_SETTING=1` | `Settings(_env_file=None)` | no error; returned object has no attribute `REDIS_URL`; `.PROJECT_NAME == "ERP API"` | pass |
| CFG-S-34 | R10 [BUG-423] | bug | clean env | `Settings(_env_file=None, ENVIRONMENT=" Production ")` | `.ENVIRONMENT == "production"` | xfail BUG-423 — fails today on: value is `" Production "` |
| CFG-S-35 | R10 [BUG-423] | bug | clean env; OS env `ENVIRONMENT=STAGING` | `Settings(_env_file=None)` | `.ENVIRONMENT == "staging"` | xfail BUG-423 — fails today on: value is `"STAGING"` |
| CFG-S-36 | R10 [BUG-423] | bug | clean env; `.env` file with `ENVIRONMENT=Test` | `Settings(_env_file=<file>)` | `.ENVIRONMENT == "test"` | xfail BUG-423 — fails today on: value is `"Test"` |
| CFG-S-37 | R10 [BUG-423], Errors row 4 | bug | clean env | `Settings(_env_file=None, ENVIRONMENT="prod")` | raises `ValidationError`; `ENVIRONMENT` in an error `loc` | xfail BUG-423 — fails today on: no error raised |
| CFG-S-38 | R10 [BUG-423], Errors row 4 | bug | clean env | `Settings(_env_file=None, ENVIRONMENT="dev")` | raises `ValidationError`; `ENVIRONMENT` in an error `loc` | xfail BUG-423 — fails today on: no error raised |
| CFG-S-39 | R10 [BUG-423], Errors row 4 | bug | clean env | `Settings(_env_file=None, ENVIRONMENT="")` | raises `ValidationError`; `ENVIRONMENT` in an error `loc` | xfail BUG-423 — fails today on: no error raised |
| CFG-S-40 | R10 (accepted values) | happy | clean env | construct four times: `Settings(_env_file=None, ENVIRONMENT=x)` for x in `"development"`, `"staging"`, `"test"`, `"production"` | each succeeds; `.ENVIRONMENT == x` exactly | pass |

## `Settings.assemble_cors_origins`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CFG-CO-01 | R2 | happy | — | `Settings.assemble_cors_origins("a, b")` | returns `["a", "b"]` | pass |
| CFG-CO-02 | R2 | boundary | — | `Settings.assemble_cors_origins("http://a.com")` | returns `["http://a.com"]` | pass |
| CFG-CO-03 | R2 | happy | — | `Settings.assemble_cors_origins("  http://a.com  ,  http://b.com  ")` | returns `["http://a.com", "http://b.com"]` (order kept) | pass |
| CFG-CO-04 | R1, R2 (kwarg source) | happy | clean env | `Settings(_env_file=None, BACKEND_CORS_ORIGINS="http://a.com, http://b.com")` | `.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]` | pass |
| CFG-CO-05 | R1a (boundary: `[` not at start) | boundary | — | `Settings.assemble_cors_origins("http://a.com, [x]")` | returns `["http://a.com", "[x]"]` (comma-split, not JSON) | pass |
| CFG-CO-06 | R1a [BUG-420] | bug | — | `Settings.assemble_cors_origins('["http://a.com", "http://b.com"]')` | returns `["http://a.com", "http://b.com"]` | xfail BUG-420 — fails today on: returns `['["http://a.com"', '"http://b.com"]']` |
| CFG-CO-07 | R1a [BUG-420] (trimmed form starts with `[`) | bug | — | `Settings.assemble_cors_origins('  ["http://a.com"]')` | returns `["http://a.com"]` | xfail BUG-420 — fails today on: returns `['["http://a.com"]']` |
| CFG-CO-08 | R1a [BUG-420] (kwarg source) | bug | clean env | `Settings(_env_file=None, BACKEND_CORS_ORIGINS='["http://a.com"]')` | `.BACKEND_CORS_ORIGINS == ["http://a.com"]` | xfail BUG-420 — fails today on: value is `['["http://a.com"]']` |
| CFG-CO-09 | R1a [BUG-420], Errors (malformed JSON) | bug | clean env | `Settings(_env_file=None, BACKEND_CORS_ORIGINS='["http://a.com"')` | raises `ValidationError`; `BACKEND_CORS_ORIGINS` in an error `loc` | xfail BUG-420 — fails today on: no error raised |
| CFG-CO-10 | R3 [BUG-421] | bug | — | `Settings.assemble_cors_origins("a, b,,")` | returns `["a", "b"]` | xfail BUG-421 — fails today on: returns `["a", "b", "", ""]` |
| CFG-CO-11 | R3 [BUG-421] | bug | — | `Settings.assemble_cors_origins("http://a.com, ,http://b.com,")` | returns `["http://a.com", "http://b.com"]` | xfail BUG-421 — fails today on: empty strings kept |
| CFG-CO-12 | R3 [BUG-421] | bug | — | `Settings.assemble_cors_origins("")` | returns `[]` | xfail BUG-421 — fails today on: returns `[""]` |
| CFG-CO-13 | R3 [BUG-421] | bug | — | `Settings.assemble_cors_origins("  ")` | returns `[]` | xfail BUG-421 — fails today on: returns `[""]` |
| CFG-CO-14 | R4 | happy | — | `Settings.assemble_cors_origins(["x"])` | returns `["x"]` | pass |
| CFG-CO-15 | R4 | boundary | — | `Settings.assemble_cors_origins(None)` | returns `None` | pass |
| CFG-CO-16 | R4 | error | clean env | `Settings(_env_file=None, BACKEND_CORS_ORIGINS=None)` | raises `ValidationError`; `BACKEND_CORS_ORIGINS` in an error `loc` | pass |
| CFG-CO-17 | R4 | happy | clean env | `Settings(_env_file=None, BACKEND_CORS_ORIGINS=["http://x.com"])` | `.BACKEND_CORS_ORIGINS == ["http://x.com"]` | pass |

## `Settings.assemble_waitlist_admin_emails`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CFG-WA-01 | R2 | happy | — | `Settings.assemble_waitlist_admin_emails(" a , ,b")` | returns `["a", "b"]` | pass |
| CFG-WA-02 | R2 | boundary | — | `Settings.assemble_waitlist_admin_emails("")` | returns `[]` | pass |
| CFG-WA-03 | R2 | boundary | — | `Settings.assemble_waitlist_admin_emails("   ")` | returns `[]` | pass |
| CFG-WA-04 | R1, R2 (kwarg source) | happy | clean env | `Settings(_env_file=None, WAITLIST_ADMIN_EMAILS="ops@makorsha.com, cto@makorsha.com")` | `.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]` | pass |
| CFG-WA-05 | R3 | happy | — | `Settings.assemble_waitlist_admin_emails("A@X.com, A@X.com")` | returns `["A@X.com", "A@X.com"]` (case kept, duplicate kept) | pass |
| CFG-WA-06 | R3 | happy | — | `Settings.assemble_waitlist_admin_emails("not-an-email")` | returns `["not-an-email"]` (no format check) | pass |
| CFG-WA-07 | R1a [BUG-420] | bug | — | `Settings.assemble_waitlist_admin_emails('["ops@makorsha.com"]')` | returns `["ops@makorsha.com"]` | xfail BUG-420 — fails today on: returns `['["ops@makorsha.com"]']` |
| CFG-WA-08 | R1a [BUG-420], Errors (malformed JSON) | bug | clean env | `Settings(_env_file=None, WAITLIST_ADMIN_EMAILS='["ops@makorsha.com"')` | raises `ValidationError`; `WAITLIST_ADMIN_EMAILS` in an error `loc` | xfail BUG-420 — fails today on: no error raised |
| CFG-WA-09 | R1a (boundary: `[` not at start) | boundary | — | `Settings.assemble_waitlist_admin_emails("ops@makorsha.com, [x]")` | returns `["ops@makorsha.com", "[x]"]` | pass |
| CFG-WA-10 | R4 | happy | — | `Settings.assemble_waitlist_admin_emails(["ops@makorsha.com"])` | returns `["ops@makorsha.com"]` | pass |
| CFG-WA-11 | R4 | boundary | — | `Settings.assemble_waitlist_admin_emails(None)` | returns `None` | pass |
| CFG-WA-12 | R4 | error | clean env | `Settings(_env_file=None, WAITLIST_ADMIN_EMAILS=None)` | raises `ValidationError`; `WAITLIST_ADMIN_EMAILS` in an error `loc` | pass |
| CFG-WA-13 | R1, R2 (kwarg, empty) | boundary | clean env | `Settings(_env_file=None, WAITLIST_ADMIN_EMAILS="")` | `.WAITLIST_ADMIN_EMAILS == []` | pass |

## module import guard

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CFG-G-01 | R4 | happy | clean env, empty cwd; `ENVIRONMENT=development`, `SECRET_KEY` unset, `DEBUG=true` | reload module | import succeeds; `settings.ENVIRONMENT == "development"`; `settings.SECRET_KEY == DEFAULT_KEY`; `settings.DEBUG is True` | pass |
| CFG-G-02 | R2, Errors row 1 | error | clean env, empty cwd; `ENVIRONMENT=production`, `SECRET_KEY` unset (default), `DEBUG=false` | reload module | raises `RuntimeError`; `str(exc) == DEFAULT_MSG` | pass |
| CFG-G-03 | R2, Errors row 1 | error | clean env, empty cwd; `ENVIRONMENT=production`, `SECRET_KEY=your-secret-key-change-this-in-production` (explicit), `DEBUG=false` | reload module | raises `RuntimeError`; `str(exc) == DEFAULT_MSG` | pass |
| CFG-G-04 | R3, R5 (safe side) | happy | safe prod (`ENVIRONMENT=production`, `SECRET_KEY=K40`, `DEBUG=false`) | reload module | import succeeds; `settings.ENVIRONMENT == "production"`; `settings.SECRET_KEY == K40`; `settings.DEBUG is False`; `isinstance(settings, app.core.config.Settings)` | pass |
| CFG-G-05 | R3 (boundary: exactly 32) | boundary | safe prod but `SECRET_KEY=K32` | reload module | import succeeds; `settings.SECRET_KEY == K32` | pass |
| CFG-G-06 | R3 [BUG-422] (boundary: 31) | bug | safe prod but `SECRET_KEY=K31` | reload module | raises `RuntimeError`; message contains `"SECRET_KEY"` | xfail BUG-422 — fails today on: import succeeds (no error) |
| CFG-G-07 | R3 [BUG-422], Errors row 2 | bug | safe prod but `SECRET_KEY=secret` | reload module | raises `RuntimeError`; message contains `"SECRET_KEY"` | xfail BUG-422 — fails today on: import succeeds |
| CFG-G-08 | R3 [BUG-422], Errors row 2 | bug | clean env, empty cwd; `ENVIRONMENT=production`, `DEBUG=false` as OS env; cwd `.env` containing only `SECRET_KEY=` (blank) | reload module | raises `RuntimeError`; message contains `"SECRET_KEY"` | xfail BUG-422 — fails today on: import succeeds |
| CFG-G-09 | R3 [BUG-422] (whitespace-only, ≥ 32 chars) | bug | safe prod but `SECRET_KEY` = 40 spaces | reload module | raises `RuntimeError`; message contains `"SECRET_KEY"` | xfail BUG-422 — fails today on: import succeeds |
| CFG-G-10 | R5 [BUG-424], Errors row 3 | bug | safe prod but `DEBUG=true` | reload module | raises `RuntimeError`; message contains `"DEBUG"` | xfail BUG-424 — fails today on: import succeeds |
| CFG-G-11 | R5, `Settings` R4a [BUG-424] | bug | clean env, empty cwd; `ENVIRONMENT=production`, `SECRET_KEY=K40`, `DEBUG` unset | reload module | import succeeds; `settings.DEBUG is False` | xfail BUG-424 — fails today on: `settings.DEBUG` is `True` (import success itself is covered by CFG-G-04) |
| CFG-G-12 | R4 (Q6, TODO-001) | happy | safe prod plus `SSLCOMMERZ_MOCK_MODE=true` and `BACKEND_CORS_ORIGINS=["*"]` | reload module | import succeeds; `settings.SSLCOMMERZ_MOCK_MODE is True`; `settings.BACKEND_CORS_ORIGINS == ["*"]` | pass |
| CFG-G-13 | R4 | boundary | clean env, empty cwd; `ENVIRONMENT=staging`, `SECRET_KEY=secret`, `DEBUG=true` | reload module | import succeeds; `settings.SECRET_KEY == "secret"`; `settings.DEBUG is True` | pass |
| CFG-G-14 | R4 | boundary | clean env, empty cwd; `ENVIRONMENT=development` as OS env; cwd `.env` containing only `SECRET_KEY=` | reload module | import succeeds; `settings.SECRET_KEY == ""` | pass |
| CFG-G-15 | R2a [BUG-423] | bug | clean env, empty cwd; `ENVIRONMENT=Production`, `SECRET_KEY` unset (default), `DEBUG=false` | reload module | raises `RuntimeError`; `str(exc) == DEFAULT_MSG` | xfail BUG-423 — fails today on: import succeeds |
| CFG-G-16 | R2a [BUG-423], R5 [BUG-424] | bug | safe prod but `ENVIRONMENT=PRODUCTION` and `DEBUG=true` | reload module | raises `RuntimeError`; message contains `"DEBUG"` | xfail BUG-423 — fails today on: import succeeds |
| CFG-G-17 | R2a [BUG-423], R3 [BUG-422] | bug | safe prod but `ENVIRONMENT=" production "` (leading and trailing space) and `SECRET_KEY=secret` | reload module | raises `RuntimeError`; message contains `"SECRET_KEY"` | xfail BUG-423 — fails today on: import succeeds |
| CFG-G-18 | R2a [BUG-423], R1, `Settings` R10 | bug | safe prod but `ENVIRONMENT=prod` | reload module | raises `pydantic.ValidationError`; `ENVIRONMENT` in an error `loc` | xfail BUG-423 — fails today on: import succeeds |
| CFG-G-19 | R1 | error | clean env, empty cwd; `ENVIRONMENT=development`, `MAX_ATTACHMENTS_PER_ENTITY=abc` | reload module | raises `pydantic.ValidationError`; `MAX_ATTACHMENTS_PER_ENTITY` in an error `loc` | pass |
| CFG-G-20 | Returns (built with default sources incl. cwd `.env`) | happy | clean env; cwd `.env` with `PROJECT_NAME=FromGuardDotenv` and `ENVIRONMENT=development` | reload module | import succeeds; `isinstance(app.core.config.settings, app.core.config.Settings)`; `settings.PROJECT_NAME == "FromGuardDotenv"` | pass |

## Deferred to other specs
None. (Consumers of the normalised `ENVIRONMENT` — work-order delete protection, upload folder naming — and the future TODO-001 mock-gateway guard belong to their own specs; no rule here is owned by another layer.)

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `Settings` | R1 | CFG-S-01, CFG-S-02, CFG-S-03, CFG-S-06 |
| `Settings` | R2 | CFG-S-04, CFG-S-05 |
| `Settings` | R3 | CFG-S-07, CFG-S-08 |
| `Settings` | R4 | CFG-S-09, CFG-S-10 |
| `Settings` | R4a [BUG-424] | CFG-S-11, CFG-G-11 |
| `Settings` | R5 | CFG-S-12, CFG-S-13, CFG-S-14, CFG-S-15, CFG-S-16, CFG-S-17, CFG-S-18 |
| `Settings` | R6 | CFG-S-19, CFG-S-20, CFG-S-21, CFG-S-22 |
| `Settings` | R7 [BUG-420] | CFG-S-24, CFG-S-25, CFG-S-26, CFG-S-27, CFG-S-28, CFG-S-29, CFG-S-30 |
| `Settings` | R8 | CFG-S-07, CFG-S-32, CFG-S-33 |
| `Settings` | R9 | CFG-S-09 |
| `Settings` | R10 [BUG-423] | CFG-S-34, CFG-S-35, CFG-S-36, CFG-S-37, CFG-S-38, CFG-S-39, CFG-S-40 |
| `Settings` | Errors: not coercible | CFG-S-17, CFG-S-18 |
| `Settings` | Errors: list value `[`… not valid JSON array of strings | CFG-S-23, CFG-S-31, CFG-CO-09, CFG-WA-08 |
| `Settings` | Errors: unknown `.env` key | CFG-S-07, CFG-S-32 |
| `Settings` | Errors: [BUG-423] ENVIRONMENT not allowed | CFG-S-37, CFG-S-38, CFG-S-39 |
| `assemble_cors_origins` | R1 [BUG-420] | CFG-S-24, CFG-S-25, CFG-CO-04 |
| `assemble_cors_origins` | R1a [BUG-420] | CFG-CO-05, CFG-CO-06, CFG-CO-07, CFG-CO-08, CFG-CO-09 |
| `assemble_cors_origins` | R2 | CFG-CO-01, CFG-CO-02, CFG-CO-03, CFG-CO-04 |
| `assemble_cors_origins` | R3 [BUG-421] | CFG-CO-10, CFG-CO-11, CFG-CO-12, CFG-CO-13, CFG-S-30 |
| `assemble_cors_origins` | R4 | CFG-CO-14, CFG-CO-15, CFG-CO-16, CFG-CO-17 |
| `assemble_waitlist_admin_emails` | R1 [BUG-420] | CFG-S-26, CFG-S-27, CFG-S-28, CFG-WA-04, CFG-WA-13 |
| `assemble_waitlist_admin_emails` | R1a [BUG-420] | CFG-WA-07, CFG-WA-08, CFG-WA-09 |
| `assemble_waitlist_admin_emails` | R2 | CFG-WA-01, CFG-WA-02, CFG-WA-03, CFG-WA-04, CFG-WA-13 |
| `assemble_waitlist_admin_emails` | R3 | CFG-WA-05, CFG-WA-06 |
| `assemble_waitlist_admin_emails` | R4 | CFG-WA-10, CFG-WA-11, CFG-WA-12 |
| module guard | R1 | CFG-G-18, CFG-G-19 |
| module guard | R2 | CFG-G-02, CFG-G-03 |
| module guard | R2a [BUG-423] | CFG-G-15, CFG-G-16, CFG-G-17, CFG-G-18 |
| module guard | R3 [BUG-422] | CFG-G-04, CFG-G-05, CFG-G-06, CFG-G-07, CFG-G-08, CFG-G-09 |
| module guard | R4 (incl. Q6 / TODO-001) | CFG-G-01, CFG-G-12, CFG-G-13, CFG-G-14 |
| module guard | R5 [BUG-424] | CFG-G-04, CFG-G-10, CFG-G-11, CFG-G-16 |
| module guard | Errors: default key | CFG-G-02, CFG-G-03 |
| module guard | Errors: [BUG-422] blank / short key | CFG-G-06, CFG-G-07, CFG-G-08, CFG-G-09 |
| module guard | Errors: [BUG-424] DEBUG in prod | CFG-G-10, CFG-G-16 |
| module guard | Returns / side effect (`settings` built from default sources) | CFG-G-04, CFG-G-20 |
