"""Unit tests for app/core/config.py.

Implements tests/unit/core/config.cases.md (revision 2), one test per case.
The module is pure: no database, no time, no externals mocked. Inputs are OS
environment variables (monkeypatch), `.env` files written under tmp_path, and
constructor kwargs. Module-guard cases reload `app.core.config` in-process
from an empty temp cwd and reload it again on teardown.
"""
import importlib
import sys

import pydantic
import pytest

import app.core.config as config_module
from app.core.config import Settings

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Clean env (every test)": every Settings field name
FIELD_NAMES = [
    "API_V1_STR", "PROJECT_NAME", "VERSION", "DATABASE_URL", "SECRET_KEY",
    "ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS",
    "BACKEND_CORS_ORIGINS", "TURNSTILE_SECRET_KEY", "WAITLIST_ADMIN_EMAILS",
    "WAITLIST_IP_HASH_SALT", "ENVIRONMENT", "DEBUG", "WORK_ORDER_ALLOW_DEV_DELETE",
    "SSLCOMMERZ_MOCK_MODE", "SSLCOMMERZ_STORE_ID", "SSLCOMMERZ_STORE_PASSWORD",
    "SSLCOMMERZ_SANDBOX", "FRONTEND_BASE_URL", "BACKEND_BASE_URL",
    "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    "CLOUDINARY_UPLOAD_ENV", "MAX_ATTACHMENTS_PER_ENTITY",
]

# Convention "Guard": constants
K40 = "k" * 40
K32 = "k" * 32
K31 = "k" * 31
DEFAULT_KEY = "your-secret-key-change-this-in-production"
DEFAULT_MSG = "SECRET_KEY must be changed from the default before running in production."

BUG_420 = "BUG-420: Comma-separated or empty list settings in env/.env crash startup"
BUG_421 = "BUG-421: CORS origin list keeps empty entries"
BUG_422 = "BUG-422: Production guard accepts blank or short SECRET_KEY"
BUG_423 = "BUG-423: ENVIRONMENT not normalised or validated"
BUG_424 = "BUG-424: DEBUG defaults to on and is allowed in production"


# Convention "Clean env (every test)": delenv every field name
@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in FIELD_NAMES:
        monkeypatch.delenv(name, raising=False)


# Convention "`.env` file with lines …": tmp_path / "test.env", passed as _env_file
@pytest.fixture
def env_file(tmp_path):
    def _write(*lines):
        path = tmp_path / "test.env"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _write


# Convention "cwd .env": tmp_path / ".env" and chdir(tmp_path)
@pytest.fixture
def cwd_env(tmp_path, monkeypatch):
    def _write(*lines):
        (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

    return _write


# Convention "Guard (G cases)": empty cwd, env set per case, reload; teardown
# undoes monkeypatch (env + cwd) and reloads again so later tests see a normal module.
@pytest.fixture
def guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _reload(env=None, dotenv_lines=None):
        for name, value in (env or {}).items():
            monkeypatch.setenv(name, value)
        if dotenv_lines is not None:
            (tmp_path / ".env").write_text("\n".join(dotenv_lines) + "\n", encoding="utf-8")
        return importlib.reload(config_module)

    yield _reload
    monkeypatch.undo()
    importlib.reload(config_module)


# Convention "safe prod"
def safe_prod(**overrides):
    env = {"ENVIRONMENT": "production", "SECRET_KEY": K40, "DEBUG": "false"}
    env.update(overrides)
    return env


# Convention "ValidationError assertions": field in the loc of at least one entry
def assert_field_in_error_loc(exc_info, field):
    assert any(field in err["loc"] for err in exc_info.value.errors())


# --------------------------------------------------------------------------- #
# Settings (fields, defaults, loading)
# --------------------------------------------------------------------------- #


def test_cfg_s_01__kwarg_beats_os_env(monkeypatch):
    """CFG-S-01 — a constructor kwarg wins over an OS env var.
    Rules: Settings R1."""
    monkeypatch.setenv("PROJECT_NAME", "FromEnv")
    s = Settings(_env_file=None, PROJECT_NAME="FromKwarg")
    assert s.PROJECT_NAME == "FromKwarg"


def test_cfg_s_02__os_env_beats_dotenv(monkeypatch, env_file):
    """CFG-S-02 — an OS env var wins over the .env file.
    Rules: Settings R1."""
    monkeypatch.setenv("PROJECT_NAME", "FromEnv")
    path = env_file("PROJECT_NAME=FromDotenv")
    s = Settings(_env_file=path)
    assert s.PROJECT_NAME == "FromEnv"


def test_cfg_s_03__dotenv_beats_default(env_file):
    """CFG-S-03 — a .env value wins over the default; unset fields keep defaults.
    Rules: Settings R1."""
    path = env_file("PROJECT_NAME=FromDotenv")
    s = Settings(_env_file=path)
    assert s.PROJECT_NAME == "FromDotenv"
    assert s.VERSION == "1.0.0"


def test_cfg_s_04__missing_env_file_is_ignored(tmp_path):
    """CFG-S-04 — a non-existent env file path is not an error.
    Rules: Settings R2."""
    missing = tmp_path / "missing.env"
    s = Settings(_env_file=missing)
    assert s.PROJECT_NAME == "ERP API"
    assert s.ENVIRONMENT == "development"


def test_cfg_s_05__no_dotenv_in_cwd_is_ignored(tmp_path, monkeypatch):
    """CFG-S-05 — with the default env file and no .env in cwd, defaults apply.
    Rules: Settings R2."""
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.PROJECT_NAME == "ERP API"


def test_cfg_s_06__default_env_file_is_cwd_dotenv(cwd_env):
    """CFG-S-06 — Settings() reads .env from the current working directory.
    Rules: Settings R1 (default .env path)."""
    cwd_env("PROJECT_NAME=FromCwdDotenv")
    s = Settings()
    assert s.PROJECT_NAME == "FromCwdDotenv"


def test_cfg_s_07__lowercase_dotenv_key_rejected(env_file):
    """CFG-S-07 — a lower-case field name in .env is an unknown (extra) key.
    Rules: Settings R3, R8."""
    path = env_file("environment=production")
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=path)
    assert "Extra inputs are not permitted" in str(exc.value)


@pytest.mark.skipif(sys.platform == "win32", reason="OS env var names are case-insensitive on Windows (spec Notes)")
def test_cfg_s_08__lowercase_os_env_name_ignored(monkeypatch):
    """CFG-S-08 — a lower-case OS env var name does not set the field.
    Rules: Settings R3."""
    monkeypatch.setenv("project_name", "lower")
    s = Settings(_env_file=None)
    assert s.PROJECT_NAME == "ERP API"


def test_cfg_s_09__defaults_exact():
    """CFG-S-09 — with no inputs every field equals the R4 default table.
    Rules: Settings R4, R9."""
    s = Settings(_env_file=None)
    assert s.API_V1_STR == "/api/v1"
    assert s.PROJECT_NAME == "ERP API"
    assert s.VERSION == "1.0.0"
    assert s.DATABASE_URL == "postgresql://postgres:postgres@localhost:5432/marker_db"
    assert s.SECRET_KEY == DEFAULT_KEY
    assert s.ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert type(s.ACCESS_TOKEN_EXPIRE_MINUTES) is int
    assert s.REFRESH_TOKEN_EXPIRE_DAYS == 14
    assert type(s.REFRESH_TOKEN_EXPIRE_DAYS) is int
    assert s.BACKEND_CORS_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:4173",
    ]
    assert s.TURNSTILE_SECRET_KEY == ""
    assert s.WAITLIST_ADMIN_EMAILS == []
    assert s.WAITLIST_IP_HASH_SALT == ""
    assert s.ENVIRONMENT == "development"
    assert s.WORK_ORDER_ALLOW_DEV_DELETE is False
    assert s.SSLCOMMERZ_MOCK_MODE is True
    assert s.SSLCOMMERZ_STORE_ID == ""
    assert s.SSLCOMMERZ_STORE_PASSWORD == ""
    assert s.SSLCOMMERZ_SANDBOX is True
    assert s.FRONTEND_BASE_URL == "http://localhost:5173"
    assert s.BACKEND_BASE_URL == "http://localhost:8000"
    assert s.CLOUDINARY_CLOUD_NAME == ""
    assert s.CLOUDINARY_API_KEY == ""
    assert s.CLOUDINARY_API_SECRET == ""
    assert s.CLOUDINARY_UPLOAD_ENV == "development"
    assert s.MAX_ATTACHMENTS_PER_ENTITY == 25
    assert type(s.MAX_ATTACHMENTS_PER_ENTITY) is int


def test_cfg_s_10__mock_mode_on_in_production_today():
    """CFG-S-10 — SSLCOMMERZ_MOCK_MODE defaults to True even in production (intended for now).
    Rules: Settings R4 (Q6, TODO-001). Revisit when TODO-001 is done."""
    s = Settings(_env_file=None, ENVIRONMENT="production")
    assert s.SSLCOMMERZ_MOCK_MODE is True
    assert s.ENVIRONMENT == "production"


@pytest.mark.xfail(strict=True, reason=BUG_424)
def test_cfg_s_11__debug_defaults_off():
    """CFG-S-11 — DEBUG defaults to False.
    Rules: Settings R4a [BUG-424]."""
    s = Settings(_env_file=None)
    assert s.DEBUG is False


@pytest.mark.parametrize(
    "name, raw, expected",
    [
        pytest.param("SSLCOMMERZ_SANDBOX", "false", False, id="CFG-S-12"),
        pytest.param("SSLCOMMERZ_SANDBOX", "0", False, id="CFG-S-13"),
        pytest.param("WORK_ORDER_ALLOW_DEV_DELETE", "true", True, id="CFG-S-14"),
        pytest.param("WORK_ORDER_ALLOW_DEV_DELETE", "1", True, id="CFG-S-15"),
    ],
)
def test_cfg_s_12_15__bool_coercion_from_env(monkeypatch, name, raw, expected):
    """CFG-S-12..15 — bool fields coerce common string forms from OS env.
    Rules: Settings R5."""
    monkeypatch.setenv(name, raw)
    s = Settings(_env_file=None)
    assert getattr(s, name) is expected


def test_cfg_s_16__int_coercion_from_env(monkeypatch):
    """CFG-S-16 — int field coerces from an OS env string.
    Rules: Settings R5."""
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    s = Settings(_env_file=None)
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert type(s.ACCESS_TOKEN_EXPIRE_MINUTES) is int


@pytest.mark.parametrize(
    "name, raw",
    [
        pytest.param("DEBUG", "release", id="CFG-S-17"),
        pytest.param("MAX_ATTACHMENTS_PER_ENTITY", "abc", id="CFG-S-18"),
    ],
)
def test_cfg_s_17_18__uncoercible_value_rejected(monkeypatch, name, raw):
    """CFG-S-17..18 — a value that cannot be coerced raises ValidationError on that field.
    Rules: Settings R5; Errors row 1."""
    monkeypatch.setenv(name, raw)
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None)
    assert_field_in_error_loc(exc, name)


def test_cfg_s_19__cors_json_array_from_os_env(monkeypatch):
    """CFG-S-19 — BACKEND_CORS_ORIGINS as a JSON array in OS env.
    Rules: Settings R6."""
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", '["http://a.com", "http://b.com"]')
    s = Settings(_env_file=None)
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]


def test_cfg_s_20__cors_json_array_from_dotenv(env_file):
    """CFG-S-20 — BACKEND_CORS_ORIGINS as a JSON array in .env.
    Rules: Settings R6."""
    path = env_file('BACKEND_CORS_ORIGINS=["http://a.com"]')
    s = Settings(_env_file=path)
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com"]


def test_cfg_s_21__emails_json_array_from_os_env(monkeypatch):
    """CFG-S-21 — WAITLIST_ADMIN_EMAILS as a JSON array in OS env.
    Rules: Settings R6."""
    monkeypatch.setenv("WAITLIST_ADMIN_EMAILS", '["ops@makorsha.com", "cto@makorsha.com"]')
    s = Settings(_env_file=None)
    assert s.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]


def test_cfg_s_22__emails_json_array_from_dotenv(env_file):
    """CFG-S-22 — WAITLIST_ADMIN_EMAILS as a JSON array in .env.
    Rules: Settings R6."""
    path = env_file('WAITLIST_ADMIN_EMAILS=["ops@makorsha.com"]')
    s = Settings(_env_file=path)
    assert s.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com"]


def test_cfg_s_23__cors_json_non_strings_rejected(monkeypatch):
    """CFG-S-23 — a JSON array of non-strings is rejected on BACKEND_CORS_ORIGINS.
    Rules: Settings Errors row 2."""
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "[1, 2]")
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None)
    assert_field_in_error_loc(exc, "BACKEND_CORS_ORIGINS")


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_24__cors_comma_list_from_os_env(monkeypatch):
    """CFG-S-24 — a comma-separated BACKEND_CORS_ORIGINS in OS env is split.
    Rules: Settings R7 [BUG-420]; assemble_cors_origins R1."""
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://a.com, http://b.com")
    s = Settings(_env_file=None)
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_25__cors_comma_list_from_dotenv(env_file):
    """CFG-S-25 — a comma-separated BACKEND_CORS_ORIGINS in .env is split.
    Rules: Settings R7 [BUG-420]; assemble_cors_origins R1."""
    path = env_file("BACKEND_CORS_ORIGINS=http://a.com, http://b.com")
    s = Settings(_env_file=path)
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_26__emails_comma_list_from_os_env(monkeypatch):
    """CFG-S-26 — a comma-separated WAITLIST_ADMIN_EMAILS in OS env is split.
    Rules: Settings R7 [BUG-420]; assemble_waitlist_admin_emails R1."""
    monkeypatch.setenv("WAITLIST_ADMIN_EMAILS", "ops@makorsha.com, cto@makorsha.com")
    s = Settings(_env_file=None)
    assert s.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_27__emails_comma_list_from_dotenv(env_file):
    """CFG-S-27 — a comma-separated WAITLIST_ADMIN_EMAILS in .env is split.
    Rules: Settings R7 [BUG-420]; assemble_waitlist_admin_emails R1."""
    path = env_file("WAITLIST_ADMIN_EMAILS=ops@makorsha.com, cto@makorsha.com")
    s = Settings(_env_file=path)
    assert s.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_28__emails_empty_in_dotenv_is_empty_list(env_file):
    """CFG-S-28 — an empty WAITLIST_ADMIN_EMAILS in .env gives [].
    Rules: Settings R7 [BUG-420]; assemble_waitlist_admin_emails R1."""
    path = env_file("WAITLIST_ADMIN_EMAILS=")
    s = Settings(_env_file=path)
    assert s.WAITLIST_ADMIN_EMAILS == []


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_29__emails_whitespace_in_os_env_is_empty_list(monkeypatch):
    """CFG-S-29 — a whitespace-only WAITLIST_ADMIN_EMAILS in OS env gives [].
    Rules: Settings R7 [BUG-420]."""
    monkeypatch.setenv("WAITLIST_ADMIN_EMAILS", "   ")
    s = Settings(_env_file=None)
    assert s.WAITLIST_ADMIN_EMAILS == []


@pytest.mark.xfail(strict=True, reason=f"{BUG_420}; {BUG_421}")
def test_cfg_s_30__cors_empty_in_dotenv_is_empty_list(env_file):
    """CFG-S-30 — an empty BACKEND_CORS_ORIGINS in .env gives [].
    Rules: Settings R7 [BUG-420] [BUG-421]."""
    path = env_file("BACKEND_CORS_ORIGINS=")
    s = Settings(_env_file=path)
    assert s.BACKEND_CORS_ORIGINS == []


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_s_31__malformed_json_in_os_env_is_validation_error(monkeypatch):
    """CFG-S-31 — malformed JSON list in OS env raises ValidationError (not SettingsError).
    Rules: Settings Errors row 2 [BUG-420]."""
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", '["http://a.com"')
    with pytest.raises(pydantic.ValidationError):
        Settings(_env_file=None)


def test_cfg_s_32__unknown_dotenv_key_rejected(env_file):
    """CFG-S-32 — an unknown key in .env raises ValidationError naming it.
    Rules: Settings R8; Errors row 3."""
    path = env_file("REDIS_URL=redis://localhost:6379")
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=path)
    assert "Extra inputs are not permitted" in str(exc.value)
    assert_field_in_error_loc(exc, "REDIS_URL")


def test_cfg_s_33__unknown_os_env_ignored(monkeypatch):
    """CFG-S-33 — unknown OS env vars are ignored.
    Rules: Settings R8."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MAKORSH_UNKNOWN_SETTING", "1")
    s = Settings(_env_file=None)
    assert not hasattr(s, "REDIS_URL")
    assert s.PROJECT_NAME == "ERP API"


@pytest.mark.xfail(strict=True, reason=BUG_423)
def test_cfg_s_34__environment_trimmed_and_lowercased_kwarg():
    """CFG-S-34 — ENVIRONMENT is trimmed and lower-cased (kwarg).
    Rules: Settings R10 [BUG-423]."""
    s = Settings(_env_file=None, ENVIRONMENT=" Production ")
    assert s.ENVIRONMENT == "production"


@pytest.mark.xfail(strict=True, reason=BUG_423)
def test_cfg_s_35__environment_lowercased_os_env(monkeypatch):
    """CFG-S-35 — ENVIRONMENT is lower-cased (OS env).
    Rules: Settings R10 [BUG-423]."""
    monkeypatch.setenv("ENVIRONMENT", "STAGING")
    s = Settings(_env_file=None)
    assert s.ENVIRONMENT == "staging"


@pytest.mark.xfail(strict=True, reason=BUG_423)
def test_cfg_s_36__environment_lowercased_dotenv(env_file):
    """CFG-S-36 — ENVIRONMENT is lower-cased (.env).
    Rules: Settings R10 [BUG-423]."""
    path = env_file("ENVIRONMENT=Test")
    s = Settings(_env_file=path)
    assert s.ENVIRONMENT == "test"


@pytest.mark.xfail(strict=True, reason=BUG_423)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("prod", id="CFG-S-37"),
        pytest.param("dev", id="CFG-S-38"),
        pytest.param("", id="CFG-S-39"),
    ],
)
def test_cfg_s_37_39__environment_unknown_value_rejected(value):
    """CFG-S-37..39 — ENVIRONMENT outside the allowed set raises ValidationError.
    Rules: Settings R10 [BUG-423]; Errors row 4."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None, ENVIRONMENT=value)
    assert_field_in_error_loc(exc, "ENVIRONMENT")


def test_cfg_s_40__environment_allowed_values_accepted():
    """CFG-S-40 — the four allowed ENVIRONMENT values are accepted unchanged.
    Rules: Settings R10 (accepted values)."""
    for x in ("development", "staging", "test", "production"):
        s = Settings(_env_file=None, ENVIRONMENT=x)
        assert s.ENVIRONMENT == x


# --------------------------------------------------------------------------- #
# Settings.assemble_cors_origins
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("a, b", ["a", "b"], id="CFG-CO-01"),
        pytest.param("http://a.com", ["http://a.com"], id="CFG-CO-02"),
        pytest.param("  http://a.com  ,  http://b.com  ", ["http://a.com", "http://b.com"], id="CFG-CO-03"),
        pytest.param("http://a.com, [x]", ["http://a.com", "[x]"], id="CFG-CO-05"),
        pytest.param(["x"], ["x"], id="CFG-CO-14"),
        pytest.param(None, None, id="CFG-CO-15"),
    ],
)
def test_cfg_co_direct__converter_returns(value, expected):
    """CFG-CO-01/02/03/05/14/15 — direct calls: comma split + trim; non-strings pass through.
    Rules: assemble_cors_origins R1a, R2, R4."""
    assert Settings.assemble_cors_origins(value) == expected


def test_cfg_co_04__kwarg_comma_string_split():
    """CFG-CO-04 — a comma-separated kwarg is split into the list field.
    Rules: assemble_cors_origins R1, R2 (kwarg source)."""
    s = Settings(_env_file=None, BACKEND_CORS_ORIGINS="http://a.com, http://b.com")
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com", "http://b.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param('["http://a.com", "http://b.com"]', ["http://a.com", "http://b.com"], id="CFG-CO-06"),
        pytest.param('  ["http://a.com"]', ["http://a.com"], id="CFG-CO-07"),
    ],
)
def test_cfg_co_06_07__json_string_parsed(value, expected):
    """CFG-CO-06..07 — a string whose trimmed form starts with [ is parsed as JSON.
    Rules: assemble_cors_origins R1a [BUG-420]."""
    assert Settings.assemble_cors_origins(value) == expected


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_co_08__kwarg_json_string_parsed():
    """CFG-CO-08 — a JSON-array string kwarg is parsed.
    Rules: assemble_cors_origins R1a [BUG-420] (kwarg source)."""
    s = Settings(_env_file=None, BACKEND_CORS_ORIGINS='["http://a.com"]')
    assert s.BACKEND_CORS_ORIGINS == ["http://a.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_co_09__kwarg_malformed_json_rejected():
    """CFG-CO-09 — a malformed JSON-array string kwarg raises ValidationError.
    Rules: assemble_cors_origins R1a [BUG-420]; Errors (malformed JSON)."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None, BACKEND_CORS_ORIGINS='["http://a.com"')
    assert_field_in_error_loc(exc, "BACKEND_CORS_ORIGINS")


@pytest.mark.xfail(strict=True, reason=BUG_421)
@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param("a, b,,", ["a", "b"], id="CFG-CO-10"),
        pytest.param("http://a.com, ,http://b.com,", ["http://a.com", "http://b.com"], id="CFG-CO-11"),
        pytest.param("", [], id="CFG-CO-12"),
        pytest.param("  ", [], id="CFG-CO-13"),
    ],
)
def test_cfg_co_10_13__empty_pieces_dropped(value, expected):
    """CFG-CO-10..13 — empty / whitespace-only pieces are dropped.
    Rules: assemble_cors_origins R3 [BUG-421]."""
    assert Settings.assemble_cors_origins(value) == expected


def test_cfg_co_16__none_kwarg_rejected():
    """CFG-CO-16 — None passes the converter but fails list validation.
    Rules: assemble_cors_origins R4."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None, BACKEND_CORS_ORIGINS=None)
    assert_field_in_error_loc(exc, "BACKEND_CORS_ORIGINS")


def test_cfg_co_17__list_kwarg_kept():
    """CFG-CO-17 — a list kwarg is kept as given.
    Rules: assemble_cors_origins R4."""
    s = Settings(_env_file=None, BACKEND_CORS_ORIGINS=["http://x.com"])
    assert s.BACKEND_CORS_ORIGINS == ["http://x.com"]


# --------------------------------------------------------------------------- #
# Settings.assemble_waitlist_admin_emails
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param(" a , ,b", ["a", "b"], id="CFG-WA-01"),
        pytest.param("", [], id="CFG-WA-02"),
        pytest.param("   ", [], id="CFG-WA-03"),
        pytest.param("A@X.com, A@X.com", ["A@X.com", "A@X.com"], id="CFG-WA-05"),
        pytest.param("not-an-email", ["not-an-email"], id="CFG-WA-06"),
        pytest.param("ops@makorsha.com, [x]", ["ops@makorsha.com", "[x]"], id="CFG-WA-09"),
        pytest.param(["ops@makorsha.com"], ["ops@makorsha.com"], id="CFG-WA-10"),
        pytest.param(None, None, id="CFG-WA-11"),
    ],
)
def test_cfg_wa_direct__converter_returns(value, expected):
    """CFG-WA-01/02/03/05/06/09/10/11 — direct calls: split, trim, drop empties; non-strings pass through.
    Rules: assemble_waitlist_admin_emails R1a, R2, R3, R4."""
    assert Settings.assemble_waitlist_admin_emails(value) == expected


def test_cfg_wa_04__kwarg_comma_string_split():
    """CFG-WA-04 — a comma-separated kwarg is split into the list field.
    Rules: assemble_waitlist_admin_emails R1, R2 (kwarg source)."""
    s = Settings(_env_file=None, WAITLIST_ADMIN_EMAILS="ops@makorsha.com, cto@makorsha.com")
    assert s.WAITLIST_ADMIN_EMAILS == ["ops@makorsha.com", "cto@makorsha.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_wa_07__json_string_parsed():
    """CFG-WA-07 — a JSON-array string is parsed.
    Rules: assemble_waitlist_admin_emails R1a [BUG-420]."""
    assert Settings.assemble_waitlist_admin_emails('["ops@makorsha.com"]') == ["ops@makorsha.com"]


@pytest.mark.xfail(strict=True, reason=BUG_420)
def test_cfg_wa_08__kwarg_malformed_json_rejected():
    """CFG-WA-08 — a malformed JSON-array string kwarg raises ValidationError.
    Rules: assemble_waitlist_admin_emails R1a [BUG-420]; Errors (malformed JSON)."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None, WAITLIST_ADMIN_EMAILS='["ops@makorsha.com"')
    assert_field_in_error_loc(exc, "WAITLIST_ADMIN_EMAILS")


def test_cfg_wa_12__none_kwarg_rejected():
    """CFG-WA-12 — None passes the converter but fails list validation.
    Rules: assemble_waitlist_admin_emails R4."""
    with pytest.raises(pydantic.ValidationError) as exc:
        Settings(_env_file=None, WAITLIST_ADMIN_EMAILS=None)
    assert_field_in_error_loc(exc, "WAITLIST_ADMIN_EMAILS")


def test_cfg_wa_13__kwarg_empty_string_is_empty_list():
    """CFG-WA-13 — an empty-string kwarg gives [].
    Rules: assemble_waitlist_admin_emails R1, R2 (kwarg, empty)."""
    s = Settings(_env_file=None, WAITLIST_ADMIN_EMAILS="")
    assert s.WAITLIST_ADMIN_EMAILS == []


# --------------------------------------------------------------------------- #
# module import guard
# --------------------------------------------------------------------------- #


def test_cfg_g_01__development_allows_default_key_and_debug(guard):
    """CFG-G-01 — outside production the default key and DEBUG=true are allowed.
    Rules: guard R4."""
    mod = guard({"ENVIRONMENT": "development", "DEBUG": "true"})
    assert mod.settings.ENVIRONMENT == "development"
    assert mod.settings.SECRET_KEY == DEFAULT_KEY
    assert mod.settings.DEBUG is True


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"ENVIRONMENT": "production", "DEBUG": "false"}, id="CFG-G-02"),
        pytest.param(
            {"ENVIRONMENT": "production", "SECRET_KEY": DEFAULT_KEY, "DEBUG": "false"}, id="CFG-G-03"
        ),
    ],
)
def test_cfg_g_02_03__production_default_key_refused(guard, env):
    """CFG-G-02..03 — production with the default SECRET_KEY (implicit or explicit) refuses to import.
    Rules: guard R2; Errors row 1."""
    with pytest.raises(RuntimeError) as exc:
        guard(env)
    assert str(exc.value) == DEFAULT_MSG


def test_cfg_g_04__safe_prod_imports(guard):
    """CFG-G-04 — safe production config imports and builds settings.
    Rules: guard R3, R5 (safe side)."""
    mod = guard(safe_prod())
    assert mod.settings.ENVIRONMENT == "production"
    assert mod.settings.SECRET_KEY == K40
    assert mod.settings.DEBUG is False
    assert isinstance(mod.settings, mod.Settings)


def test_cfg_g_05__secret_exactly_32_accepted(guard):
    """CFG-G-05 — a 32-character secret is accepted in production.
    Rules: guard R3 (boundary: exactly 32)."""
    mod = guard(safe_prod(SECRET_KEY=K32))
    assert mod.settings.SECRET_KEY == K32


@pytest.mark.xfail(strict=True, reason=BUG_422)
@pytest.mark.parametrize(
    "secret",
    [
        pytest.param(K31, id="CFG-G-06"),
        pytest.param("secret", id="CFG-G-07"),
        pytest.param(" " * 40, id="CFG-G-09"),
    ],
)
def test_cfg_g_06_07_09__weak_secret_refused(guard, secret):
    """CFG-G-06/07/09 — short or whitespace-only SECRET_KEY refused in production.
    Rules: guard R3 [BUG-422]; Errors row 2."""
    with pytest.raises(RuntimeError) as exc:
        guard(safe_prod(SECRET_KEY=secret))
    assert "SECRET_KEY" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=BUG_422)
def test_cfg_g_08__blank_secret_from_dotenv_refused(guard):
    """CFG-G-08 — a blank SECRET_KEY from cwd .env is refused in production.
    Rules: guard R3 [BUG-422]; Errors row 2."""
    with pytest.raises(RuntimeError) as exc:
        guard({"ENVIRONMENT": "production", "DEBUG": "false"}, dotenv_lines=["SECRET_KEY="])
    assert "SECRET_KEY" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=BUG_424)
def test_cfg_g_10__debug_in_production_refused(guard):
    """CFG-G-10 — DEBUG=true in production is refused.
    Rules: guard R5 [BUG-424]; Errors row 3."""
    with pytest.raises(RuntimeError) as exc:
        guard(safe_prod(DEBUG="true"))
    assert "DEBUG" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=BUG_424)
def test_cfg_g_11__production_debug_unset_is_off(guard):
    """CFG-G-11 — production with DEBUG unset imports with DEBUG off.
    Rules: guard R5; Settings R4a [BUG-424]."""
    mod = guard({"ENVIRONMENT": "production", "SECRET_KEY": K40})
    assert mod.settings.DEBUG is False


def test_cfg_g_12__mock_mode_and_wildcard_cors_allowed_in_prod_today(guard):
    """CFG-G-12 — mock gateway and wildcard CORS do not block a production import (intended for now).
    Rules: guard R4 (Q6, TODO-001). Revisit when TODO-001 is done."""
    mod = guard(safe_prod(SSLCOMMERZ_MOCK_MODE="true", BACKEND_CORS_ORIGINS='["*"]'))
    assert mod.settings.SSLCOMMERZ_MOCK_MODE is True
    assert mod.settings.BACKEND_CORS_ORIGINS == ["*"]


def test_cfg_g_13__staging_is_not_guarded(guard):
    """CFG-G-13 — staging with a weak key and DEBUG on imports.
    Rules: guard R4."""
    mod = guard({"ENVIRONMENT": "staging", "SECRET_KEY": "secret", "DEBUG": "true"})
    assert mod.settings.SECRET_KEY == "secret"
    assert mod.settings.DEBUG is True


def test_cfg_g_14__development_blank_secret_allowed(guard):
    """CFG-G-14 — development with a blank SECRET_KEY from cwd .env imports.
    Rules: guard R4."""
    mod = guard({"ENVIRONMENT": "development"}, dotenv_lines=["SECRET_KEY="])
    assert mod.settings.SECRET_KEY == ""


@pytest.mark.xfail(strict=True, reason=BUG_423)
def test_cfg_g_15__mixed_case_production_default_key_refused(guard):
    """CFG-G-15 — ENVIRONMENT=Production is treated as production (default key refused).
    Rules: guard R2a [BUG-423]."""
    with pytest.raises(RuntimeError) as exc:
        guard({"ENVIRONMENT": "Production", "DEBUG": "false"})
    assert str(exc.value) == DEFAULT_MSG


@pytest.mark.xfail(strict=True, reason=f"{BUG_423}; {BUG_424}")
def test_cfg_g_16__upper_production_debug_refused(guard):
    """CFG-G-16 — ENVIRONMENT=PRODUCTION with DEBUG=true is refused.
    Rules: guard R2a [BUG-423], R5 [BUG-424]."""
    with pytest.raises(RuntimeError) as exc:
        guard(safe_prod(ENVIRONMENT="PRODUCTION", DEBUG="true"))
    assert "DEBUG" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=f"{BUG_423}; {BUG_422}")
def test_cfg_g_17__padded_production_weak_secret_refused(guard):
    """CFG-G-17 — ENVIRONMENT=' production ' with a weak key is refused.
    Rules: guard R2a [BUG-423], R3 [BUG-422]."""
    with pytest.raises(RuntimeError) as exc:
        guard(safe_prod(ENVIRONMENT=" production ", SECRET_KEY="secret"))
    assert "SECRET_KEY" in str(exc.value)


@pytest.mark.xfail(strict=True, reason=BUG_423)
def test_cfg_g_18__unknown_environment_fails_import(guard):
    """CFG-G-18 — ENVIRONMENT=prod makes the import fail with ValidationError.
    Rules: guard R2a [BUG-423], R1; Settings R10."""
    with pytest.raises(pydantic.ValidationError) as exc:
        guard(safe_prod(ENVIRONMENT="prod"))
    assert_field_in_error_loc(exc, "ENVIRONMENT")


def test_cfg_g_19__invalid_setting_fails_import(guard):
    """CFG-G-19 — an uncoercible setting makes the import fail with ValidationError.
    Rules: guard R1."""
    with pytest.raises(pydantic.ValidationError) as exc:
        guard({"ENVIRONMENT": "development", "MAX_ATTACHMENTS_PER_ENTITY": "abc"})
    assert_field_in_error_loc(exc, "MAX_ATTACHMENTS_PER_ENTITY")


def test_cfg_g_20__module_settings_built_from_cwd_dotenv(guard):
    """CFG-G-20 — the module-level settings is built from default sources incl. cwd .env.
    Rules: guard Returns."""
    mod = guard(dotenv_lines=["PROJECT_NAME=FromGuardDotenv", "ENVIRONMENT=development"])
    assert isinstance(mod.settings, mod.Settings)
    assert mod.settings.PROJECT_NAME == "FromGuardDotenv"
