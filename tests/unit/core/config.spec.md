# Spec — `app/core/config.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

No house-rule violations. No precedent matches.

### New questions

### Q1. Comma-separated lists in the environment crash startup — 🐞 BUG-420
**Background:** `BACKEND_CORS_ORIGINS` and `WAITLIST_ADMIN_EMAILS` are lists. The code has converters meant to accept a comma-separated string ("a, b"). But the settings library first tries to read any list value coming from an environment variable or the `.env` file as JSON, and fails before those converters ever run. The converters only work when a string is passed directly in Python code (`Settings(BACKEND_CORS_ORIGINS="a, b")`), which the app never does.
**What happens today:** Only JSON arrays work in the environment / `.env` (`["http://a.com"]`). A comma-separated value, or an empty value, aborts the whole app at import with `SettingsError: error parsing value for field "BACKEND_CORS_ORIGINS" from source "EnvSettingsSource"`.
**Example:** An operator sets `WAITLIST_ADMIN_EMAILS=ops@makorsha.com, cto@makorsha.com` on the host, as the converter suggests is allowed. The API fails to boot. `WAITLIST_ADMIN_EMAILS=` (empty, meaning "no admins") also fails to boot.
**Rules affected:** `Settings` R6, R7; `assemble_cors_origins` R1; `assemble_waitlist_admin_emails` R1
**Suggested answer:** bug — both list settings accept either a JSON array or a comma-separated string (and an empty value = empty list) from the environment and `.env`, e.g. by marking the fields `NoDecode` so the converters receive the raw string
**Answer:** bug — both list settings accept either a JSON array or a comma-separated string (and an empty value = empty list) from the environment and `.env`, e.g. by marking the fields `NoDecode` so the converters receive the raw string (reviewer accepted suggestion)
**Resolution:** list settings accept a JSON array or a comma-separated string from every source (kwargs, OS env, `.env`); empty/whitespace-only = `[]`. JSON detection (trimmed value starts with `[`), and malformed JSON → pydantic `ValidationError`, are (best-practice default, delegated by reviewer). Rules: `Settings` R7; `assemble_cors_origins` R1, R1a; `assemble_waitlist_admin_emails` R1, R1a.

### Q2. CORS list keeps empty entries; admin-email list drops them — 🐞 BUG-421
**Background:** The two list converters are siblings but behave differently on empty pieces.
**What happens today:** For CORS origins, each comma-separated piece is trimmed and kept even when empty. For admin emails, empty pieces are dropped.
**Example:** `"http://a.com, ,http://b.com,"` becomes `["http://a.com", "", "http://b.com", ""]` for CORS (an empty-string allowed origin), while the same shape for emails becomes two entries only.
**Rules affected:** `assemble_cors_origins` R2, R3
**Suggested answer:** bug — CORS origins drop empty/whitespace-only pieces, like admin emails
**Answer:** bug — CORS origins drop empty/whitespace-only pieces, like admin emails (reviewer accepted suggestion)
**Resolution:** CORS converter drops empty/whitespace-only pieces; `""` → `[]`. Rules: `assemble_cors_origins` R3 (R2 unchanged).

### Q3. Production guard lets an empty or weak SECRET_KEY through — 🐞 BUG-422
**Background:** `SECRET_KEY` signs every login token (JWT), signs the mock payment gateway callbacks, and is the fallback salt for hashing waitlist IPs. At import the module refuses to start in production only when the key equals the literal default text.
**What happens today:** In production, `SECRET_KEY=""` (e.g. the variable is defined but blank) or `SECRET_KEY=secret` starts normally. Tokens are then signed with an empty/guessable key.
**Example:** A deploy sets `ENVIRONMENT=production` and leaves `SECRET_KEY=` blank in the host panel. The API boots; anyone who knows the key is empty can forge a valid access token for any user.
**Rules affected:** module guard R3
**Suggested answer:** bug — in production, refuse to start unless SECRET_KEY is not the default, not blank, and at least 32 characters long
**Answer:** bug — in production, refuse to start unless SECRET_KEY is not the default, not blank, and at least 32 characters long (reviewer accepted suggestion)
**Resolution:** in production, import raises `RuntimeError` when `SECRET_KEY` is blank/whitespace-only or shorter than 32 characters. Length counted on the value as given; error type `RuntimeError` with a message mentioning `SECRET_KEY` (exact wording free) are (best-practice default, delegated by reviewer). Rules: module guard R3.

### Q4. "Production" is recognised only by the exact lowercase word — 🐞 BUG-423
**Background:** `ENVIRONMENT` is a free string. Several safety switches check `ENVIRONMENT == "production"`: the secret-key guard here, the work-order delete protection, and upload folder naming.
**What happens today:** `Production`, `PRODUCTION`, `prod` or `production ` (trailing space) are treated as "not production": the secret-key guard is skipped and non-draft work orders become deletable.
**Example:** A host is configured with `ENVIRONMENT=Production` and the default secret key. The API boots with the publicly known default key and allows deleting approved work orders.
**Rules affected:** `Settings` R4; module guard R2
**Suggested answer:** bug — ENVIRONMENT is trimmed and lower-cased, and only `development`, `staging`, `test`, `production` are accepted (anything else fails startup)
**Answer:** bug — ENVIRONMENT is trimmed and lower-cased, and only `development`, `staging`, `test`, `production` are accepted (anything else fails startup) (reviewer accepted suggestion)
**Resolution:** `ENVIRONMENT` normalised (trim + lower-case) and restricted to the four values at `Settings` construction; unknown value → pydantic `ValidationError` (validation in a field validator on `Settings`, so every source is covered — (best-practice default, delegated by reviewer)). The production guard sees the normalised value. Rules: `Settings` R10; module guard R2a.

### Q5. DEBUG is on unless explicitly turned off, even in production — 🐞 BUG-424
**Background:** `DEBUG` makes the database engine log every SQL statement with its parameters, and makes some error responses show internal details (e.g. "run `alembic upgrade head`").
**What happens today:** `DEBUG` defaults to `True` and nothing ties it to `ENVIRONMENT`. A production deploy that does not set `DEBUG=false` logs all SQL with parameter values (password hashes, tokens, personal data) and exposes internal hints to clients.
**Example:** Production is deployed with `ENVIRONMENT=production` and no `DEBUG` variable. Every login query, including the stored password hash, is written to the application log.
**Rules affected:** `Settings` R4
**Suggested answer:** bug — DEBUG defaults to False, and startup refuses DEBUG=True when ENVIRONMENT is production
**Answer:** bug — DEBUG defaults to False, and startup refuses DEBUG=True when ENVIRONMENT is production (reviewer accepted suggestion)
**Resolution:** `DEBUG` default `False`; in production with `DEBUG=True` the import guard raises `RuntimeError` mentioning `DEBUG`. Placing the check in the import guard (like the secret check, not in `Settings` construction) is (best-practice default, delegated by reviewer). Rules: `Settings` R4a; module guard R5.

### Q6. Mock payment gateway is on by default, including in production — ✅ intended
**Background:** With `SSLCOMMERZ_MOCK_MODE=True` the API serves a fake gateway page that lets whoever opens it choose "success" and mark a subscription payment as paid without any money moving. There is no real gateway client yet; with mock mode off, payments raise `NotImplementedError`.
**What happens today:** `SSLCOMMERZ_MOCK_MODE` defaults to `True`, and the production guard does not check it.
**Example:** Production boots with `ENVIRONMENT=production` and no `SSLCOMMERZ_MOCK_MODE` set. A customer starts checkout, opens the mock page, clicks "success", and their workspace subscription is activated for free.
**Rules affected:** `Settings` R4; module guard R4
**Suggested answer:** bug — startup refuses `SSLCOMMERZ_MOCK_MODE=True` when ENVIRONMENT is production
**Answer:** intended for now — reviewer: the mock gateway will be removed or upgraded later; leave behavior as is. TODO (tracked in docs/testing/bugs.md as a TODO, not a bug): before production, either remove the mock or guard it so SSLCOMMERZ_MOCK_MODE can only be on in non-production environments.
**Resolution:** current behavior kept and tested as intended; deferred work tracked as **TODO-001** in `docs/testing/bugs.md` (no BUG ID, no xfail). Rules: `Settings` R4 ✅, module guard R4 ✅.

### Q7. Any unknown key in `.env` stops the app from starting — ✅ intended
**Background:** Settings are also read from a `.env` file in the working directory. The settings library rejects keys it does not know.
**What happens today:** A `.env` line whose name is not one of the settings (e.g. a leftover `REDIS_URL=…`, or a typo `SECRETKEY=…`) aborts startup with `ValidationError … Extra inputs are not permitted`. Unknown OS environment variables are ignored (only the `.env` file is strict).
**Example:** A developer copies a shared `.env` containing `VITE_TURNSTILE_SITE_KEY=…` into the backend folder; the API refuses to start.
**Rules affected:** `Settings` R8
**Suggested answer:** intended
**Answer:** intended (reviewer accepted suggestion)

## Overview
Central application configuration. `Settings` is a pydantic-settings model whose fields are filled from, in priority order, keyword arguments, OS environment variables, then a `.env` file in the current working directory, then the class defaults. A single instance `settings` is created at import and imported by the whole app (JWT security, DB engine, CORS middleware, payment gateway factory, Cloudinary managers, waitlist service, work-order deletion). At import the module also refuses to run in production with an unsafe configuration (default / blank / short secret key, DEBUG on).

**Callables:** 4 specified · 0 not specified
**Externals to mock:** none (environment variables and the `.env` file are the inputs; control them with `monkeypatch` and `_env_file`)
**Integration-only behavior:** none

**Notes for the test designer:**
- This is framework glue (settings). Unit-test it by constructing `Settings(_env_file=None, **overrides)` directly — `_env_file=None` isolates the test from the developer's real `.env`. For `.env` behavior, write a temp file and pass `_env_file=<path>`.
- Clear any relevant OS variables first (`monkeypatch.delenv(name, raising=False)`) — CI or the developer shell may define `DATABASE_URL`, `DEBUG`, etc. Set env inputs with `monkeypatch.setenv`.
- The two validators are classmethods and can also be called directly: `Settings.assemble_cors_origins("a, b")`.
- The module guard runs at import. Test it with `importlib.reload(app.core.config)` under monkeypatched env, then reload again after restoring the env so later tests get a normal module. Note that reloading rebinds `app.core.config.settings` only; other modules keep the old object — do not assert through them. Alternatively run the import in a subprocess. When testing the guard, isolate from the developer's `.env` (e.g. `monkeypatch.chdir(tmp_path)` so no `.env` is found) and set every guarded input explicitly.
- Guard tests trigger **one** unsafe condition at a time and otherwise use a safe production config (e.g. `SECRET_KEY` = 32+ chars, `DEBUG=false`); the order in which multiple violations are reported is not specified (best-practice default, delegated by reviewer).
- Guard error messages after the fix: assert the exception type (`RuntimeError`) and that the message contains the offending setting's name (`SECRET_KEY` / `DEBUG`); the exact wording of new messages is not specified (best-practice default, delegated by reviewer). The existing default-key message is exact (module guard R2).
- Windows: environment variable names are case-insensitive at the OS level, so `case_sensitive=True` cannot be observed for OS env vars on Windows (`environment=production` still sets `ENVIRONMENT`). Case sensitivity is observable via the `.env` file and via constructor kwargs on any platform.
- Do not start the real app.

## Not specified
(none)

---

## `Settings` (fields, defaults, loading)
**Shape:** mapper
**Persistence:** pure
**Visibility:** public

**Purpose:** Hold every configuration value, with defaults, filled from kwargs / environment / `.env`.

**Inputs:** keyword arguments, OS environment variables, `.env` file (path from `_env_file`, default `.env` relative to the current working directory).

**Returns:** a `Settings` instance.

**Rules:**
- **R1.** Source priority: a keyword argument beats an OS environment variable, which beats a `.env` value, which beats the class default.
- **R2.** A missing `.env` file is not an error; defaults are used.
- **R3.** Field names are matched case-sensitively (`case_sensitive=True`): in a `.env` file, `environment=production` does not set `ENVIRONMENT` (and, per R8, is rejected as an unknown key). (OS env on Windows: see Notes.)
- **R4.** With no inputs, the defaults are exactly (`DEBUG`: see R4a):

  | Field | Default |
  |---|---|
  | `API_V1_STR` | `"/api/v1"` |
  | `PROJECT_NAME` | `"ERP API"` |
  | `VERSION` | `"1.0.0"` |
  | `DATABASE_URL` | `"postgresql://postgres:postgres@localhost:5432/marker_db"` |
  | `SECRET_KEY` | `"your-secret-key-change-this-in-production"` |
  | `ALGORITHM` | `"HS256"` |
  | `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |
  | `REFRESH_TOKEN_EXPIRE_DAYS` | `14` |
  | `BACKEND_CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://localhost:4173"]` |
  | `TURNSTILE_SECRET_KEY` | `""` |
  | `WAITLIST_ADMIN_EMAILS` | `[]` |
  | `WAITLIST_IP_HASH_SALT` | `""` |
  | `ENVIRONMENT` | `"development"` |
  | `WORK_ORDER_ALLOW_DEV_DELETE` | `False` |
  | `SSLCOMMERZ_MOCK_MODE` | `True` |
  | `SSLCOMMERZ_STORE_ID` | `""` |
  | `SSLCOMMERZ_STORE_PASSWORD` | `""` |
  | `SSLCOMMERZ_SANDBOX` | `True` |
  | `FRONTEND_BASE_URL` | `"http://localhost:5173"` |
  | `BACKEND_BASE_URL` | `"http://localhost:8000"` |
  | `CLOUDINARY_CLOUD_NAME` | `""` |
  | `CLOUDINARY_API_KEY` | `""` |
  | `CLOUDINARY_API_SECRET` | `""` |
  | `CLOUDINARY_UPLOAD_ENV` | `"development"` |
  | `MAX_ATTACHMENTS_PER_ENTITY` | `25` |

  `SSLCOMMERZ_MOCK_MODE` defaults to `True` independently of `ENVIRONMENT` (also `True` when `ENVIRONMENT="production"`). ✅ (Q6 — intended for now, see TODO-001.)
- **R4a.** [BUG-424] `DEBUG` defaults to `False` when not provided by any source. *(Today: defaults to `True`.)*
- **R5.** String inputs are coerced to the field type: `"false"`/`"0"` → `False`, `"true"`/`"1"` → `True` for bools; `"30"` → `30` for ints. A value that cannot be coerced (`DEBUG=release`, `MAX_ATTACHMENTS_PER_ENTITY=abc`) raises pydantic `ValidationError`.
- **R6.** For the list fields (`BACKEND_CORS_ORIGINS`, `WAITLIST_ADMIN_EMAILS`) coming from OS env or `.env`, a JSON array string (`["http://a.com"]`) is accepted and becomes that list.
- **R7.** [BUG-420] For the list fields coming from OS env or `.env`, a comma-separated string (`http://a.com, http://b.com`) is accepted and converted by the field's converter (`assemble_cors_origins` / `assemble_waitlist_admin_emails`); an empty or whitespace-only value becomes `[]`. Startup does not fail. *(Today: any value that is not valid JSON — comma-separated or empty — raises `pydantic_settings.SettingsError` `error parsing value for field "<NAME>" from source "EnvSettingsSource"` / `"DotEnvSettingsSource"`; the converters are never reached. Fix: e.g. mark the fields `NoDecode` so the converters receive the raw string.)*
- **R8.** A `.env` key that is not a field raises `ValidationError` ("Extra inputs are not permitted"). An unknown OS environment variable is ignored. ✅
- **R9.** `SSLCOMMERZ_STORE_ID`, `SSLCOMMERZ_STORE_PASSWORD` and `SSLCOMMERZ_SANDBOX` are loaded but read nowhere in the app today (no real gateway client exists). Nothing to test beyond R4.
- **R10.** [BUG-423] `ENVIRONMENT` is trimmed and lower-cased at construction from every source: `" Production "` → `"production"`, `"STAGING"` → `"staging"`. Only `development`, `staging`, `test`, `production` (after normalisation) are accepted; anything else (`"prod"`, `"dev"`, `""`) raises pydantic `ValidationError` (best-practice default, delegated by reviewer: field validator on `Settings`). *(Today: free string, stored exactly as given, no allowed-value check.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| value not coercible to field type | `pydantic.ValidationError` | pydantic default |
| list field value starts with `[` but is not a valid JSON array of strings (after BUG-420 fix, any source) | `pydantic.ValidationError` | not specified |
| unknown key in `.env` | `pydantic.ValidationError` | `Extra inputs are not permitted` |
| [BUG-423] `ENVIRONMENT` not one of the four values after trim/lower-case | `pydantic.ValidationError` | not specified |

*(Today, instead of the list-field row: any non-JSON list value from env/.env raises `pydantic_settings.SettingsError`, see R7.)*

**Side effects:** none (reads environment and `.env` file only).

---

## `Settings.assemble_cors_origins(v)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (field validator for `BACKEND_CORS_ORIGINS`, runs before type validation)

**Purpose:** Turn a comma-separated origins string (or JSON array string) into a list.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `v` | any | raw value for `BACKEND_CORS_ORIGINS` |

**Returns:** a list of strings when `v` is a `str`; otherwise `v` unchanged.

**Rules:**
- **R1.** [BUG-420] The converter receives the raw string from every source — keyword argument, OS env and `.env` — so `BACKEND_CORS_ORIGINS=x, y` in the environment gives `["x", "y"]`. *(Today: reached with a raw string only via keyword argument; from env/.env see `Settings` R7.)*
- **R1a.** [BUG-420] A string whose trimmed form starts with `[` is parsed as a JSON array and becomes that list (`'["http://a.com", "http://b.com"]'` → `["http://a.com", "http://b.com"]`); malformed JSON → `ValidationError` (best-practice default, delegated by reviewer). *(Today, via keyword argument: the string is comma-split, `'["a"]'` → `['["a"]']`.)*
- **R2.** A (non-JSON) string is split on `,` and each piece trimmed of leading/trailing whitespace: `"a, b"` → `["a", "b"]`; `"a"` → `["a"]`.
- **R3.** [BUG-421] Empty and whitespace-only pieces are dropped: `"a, b,,"` → `["a", "b"]`; `"http://a.com, ,http://b.com,"` → `["http://a.com", "http://b.com"]`; `""` and `"  "` → `[]`. *(Today: kept as `""`: `"a, b,,"` → `["a", "b", "", ""]`; `""` → `[""]`.)*
- **R4.** A non-string (a list, `None`) is returned unchanged; a list passes through as given (`["x"]` → `["x"]`), and pydantic then validates it as `list[str]` (so `None` via `Settings(...)` raises `ValidationError`).

**Errors:** none raised by the converter itself today (after BUG-420: malformed JSON array string → `ValidationError`, see R1a).

**Side effects:** none.

---

## `Settings.assemble_waitlist_admin_emails(v)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (field validator for `WAITLIST_ADMIN_EMAILS`, runs before type validation)

**Purpose:** Turn a comma-separated email string (or JSON array string) into a list, skipping blanks.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `v` | any | raw value for `WAITLIST_ADMIN_EMAILS` |

**Returns:** a list of strings when `v` is a `str`; otherwise `v` unchanged.

**Rules:**
- **R1.** [BUG-420] The converter receives the raw string from every source (keyword argument, OS env, `.env`): `WAITLIST_ADMIN_EMAILS=ops@makorsha.com, cto@makorsha.com` → `["ops@makorsha.com", "cto@makorsha.com"]`; `WAITLIST_ADMIN_EMAILS=` → `[]`. *(Today: only via keyword argument; from env/.env see `Settings` R7.)*
- **R1a.** [BUG-420] A string whose trimmed form starts with `[` is parsed as a JSON array and becomes that list; malformed JSON → `ValidationError` (best-practice default, delegated by reviewer). *(Today, via keyword argument: comma-split.)*
- **R2.** A (non-JSON) string is split on `,`, each piece trimmed, and empty/whitespace-only pieces dropped: `" a , ,b"` → `["a", "b"]`; `""` → `[]`.
- **R3.** No email format check, no lower-casing, no de-duplication: `"A@X.com, A@X.com"` → `["A@X.com", "A@X.com"]`.
- **R4.** A non-string is returned unchanged (list passes through; pydantic then validates `list[str]`).

**Errors:** none raised by the converter itself today (after BUG-420: malformed JSON array string → `ValidationError`, see R1a).

**Side effects:** none.

---

## module import guard (`settings = Settings()` + production checks)
**Shape:** validator
**Persistence:** pure
**Visibility:** public (runs on first import of `app.core.config`)

**Purpose:** Build the shared `settings` instance and stop a production process with an unsafe configuration.

**Inputs:** environment / `.env` as for `Settings`.

**Returns:** module attribute `settings` (a `Settings` instance built with default sources, including `.env` in the current working directory).

**Rules:**
- **R1.** Any `Settings` construction error (see `Settings` Errors) propagates out of the import.
- **R2.** When `ENVIRONMENT` is `"production"` and `SECRET_KEY` equals `"your-secret-key-change-this-in-production"`, import raises `RuntimeError("SECRET_KEY must be changed from the default before running in production.")`.
- **R2a.** [BUG-423] The guard (R2, R3, R5) applies to any spelling that normalises to `"production"` (`"Production"`, `"PRODUCTION"`, `" production "`); `"prod"` is rejected at construction (`Settings` R10, surfaces via R1). *(Today: only the exact string `"production"` triggers the guard; other spellings import successfully.)*
- **R3.** [BUG-422] In production, import raises `RuntimeError` (message mentions `SECRET_KEY`) when `SECRET_KEY` is empty, whitespace-only, or shorter than 32 characters (e.g. `"secret"`, 31 chars). A non-default key of 32 or more characters (exactly 32 included) passes. Length is counted on the value as given (best-practice default, delegated by reviewer). *(Today: any non-default value, including `""` and short strings, passes.)*
- **R4.** When `ENVIRONMENT` is not production, the default secret key (and a blank or short key, and `DEBUG=True`) is allowed and import succeeds. `SSLCOMMERZ_MOCK_MODE` and CORS are never checked, in any environment — production with `SSLCOMMERZ_MOCK_MODE=True` imports successfully. ✅ (Q6 — intended for now, see TODO-001.)
- **R5.** [BUG-424] In production, import raises `RuntimeError` (message mentions `DEBUG`) when `DEBUG` is `True`. Production with `DEBUG=False` (and a valid secret key) imports successfully. *(Today: `DEBUG` is not checked.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| production and default `SECRET_KEY` | `RuntimeError` | `SECRET_KEY must be changed from the default before running in production.` |
| [BUG-422] production and blank / < 32-char `SECRET_KEY` | `RuntimeError` | contains `SECRET_KEY` (wording not specified) |
| [BUG-424] production and `DEBUG=True` | `RuntimeError` | contains `DEBUG` (wording not specified) |

**Side effects:** creates the module-level `settings` object.

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–81 | field defaults / types | `Settings` R4, R4a, R5, R9 |
| 29, 38 | list fields decoded as JSON by env sources before validators | `Settings` R6, R7 |
| 56 | `ENVIRONMENT` free string (after fix: normalise + allowed-value check) | `Settings` R10 |
| 84 | `env_file=".env"` (file present / missing) | `Settings` R1, R2 |
| 85 | `case_sensitive=True` | `Settings` R3 |
| (BaseSettings default `extra="forbid"`) | unknown `.env` key | `Settings` R8 |
| 44 | `isinstance(v, str)` true | `assemble_cors_origins` R1, R1a, R2 |
| 45 | split/strip, no empty filter (after fix: filter) | `assemble_cors_origins` R3 |
| 44 | `isinstance(v, str)` false → return as is | `assemble_cors_origins` R4 |
| 51 | `isinstance(v, str)` true | `assemble_waitlist_admin_emails` R1, R1a, R2, R3 |
| 52 | `if i.strip()` filter (empty vs non-empty piece) | `assemble_waitlist_admin_emails` R2 |
| 51 | `isinstance(v, str)` false → return as is | `assemble_waitlist_admin_emails` R4 |
| 89 | `Settings()` construction fails | module guard R1 |
| 92 | `ENVIRONMENT == "production"` false | module guard R2a, R4 |
| 92 | production and `SECRET_KEY == _DEFAULT_SECRET` → raise | module guard R2 |
| 92 | production and other `SECRET_KEY` (after fix: blank / length check) | module guard R3 |
| (after fix) | production and `DEBUG` true / false | module guard R5 |
