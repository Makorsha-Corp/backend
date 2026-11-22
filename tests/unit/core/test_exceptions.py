"""Unit tests for app/core/exceptions.py.

Implements tests/unit/core/exceptions.cases.md (revision 5), one test per case.
Handlers are called the way Starlette calls them: the exception is raised and
caught, and the handler runs inside that `except` block (so `exc_info` is
live). The `db` fixture is used only to produce real driver errors with real
SQLSTATE codes on temporary tables inside a savepoint. No mocks; only
`settings.DEBUG` / `settings.ERROR_TYPE_BASE_URL` are patched.
"""
import asyncio
import json
import logging
import re

import pytest
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
)
from starlette.requests import Request

from app.core.config import settings
from app.core.exceptions import (
    APIException,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    api_exception_handler,
    database_error_handler,
    generic_exception_handler,
    integrity_error_handler,
    schema_error_handler,
    validation_exception_handler,
)

LOGGER = "app.core.exceptions"

BUG_460 = "BUG-460: Validation failures log raw submitted values (passwords, tokens)"
BUG_461 = "BUG-461: Request-schema validation failures return 400 instead of 422"
BUG_462 = "BUG-462: Integrity errors classified by substring search over message, SQL and parameters"
BUG_463 = "BUG-463: Delete of a still-referenced row reported as 'Referenced resource does not exist.'"
BUG_464 = "BUG-464: Check-constraint violations reported as 409 'may already exist'"
BUG_465 = "BUG-465: Not-null violation returns 400 labelled 'Resource Conflict'"
BUG_466 = "BUG-466: Every SQL ProgrammingError reported as 503 'temporarily unavailable'"
BUG_467 = "BUG-467: Error type URIs use placeholder domain api.yourdomain.com"
BUG_468 = "BUG-468: Problem-details responses sent as application/json"
BUG_469 = "BUG-469: Falsy request.state.request_id used as-is by every error handler"

STD_KEYS = {"type", "title", "status", "detail", "instance", "request_id"}
TEMP_MSG = "Database service is temporarily unavailable. Please try again later."
GEN_MSG = "An unexpected error occurred. Please contact support with the request ID."
SCHEMA_MSG = "Database schema is out of date — run `alembic upgrade head` and restart the API."
DUP_MSG = "This resource already exists. Please use a different value."
FK_MSG = "Referenced resource does not exist."
NN_MSG = "Required field is missing."
PROBLEM = "application/problem+json"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #


# Convention "Requests": REQ and its variants, built fresh per call
def make_req(**over) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/x",
        "headers": [(b"user-agent", b"ua-test/1.0")],
        "client": ("1.2.3.4", 5),
        "query_string": b"",
        "state": {"request_id": "req-t-1"},
    }
    scope.update(over)
    return Request(scope)


def REQ():
    return make_req()


def REQ_noid():
    return make_req(state={})


def REQ_bare():
    return make_req(headers=[], client=None)


def REQ_q():
    return make_req(path="/api/v1/suppliers/7", query_string=b"include=all")


def REQ_nullid():
    return make_req(state={"request_id": None})


def REQ_emptyid():
    return make_req(state={"request_id": ""})


# Convention "Calling a handler": raise, catch, run the handler inside `except`
def call(handler, request, exc):
    try:
        raise exc
    except BaseException:
        return asyncio.run(handler(request, exc))


def body_of(resp) -> dict:
    return json.loads(resp.body)


# Shorthand STD(slug, title, status, detail)
def assert_std(resp, slug, title, status, detail):
    body = body_of(resp)
    assert resp.status_code == status
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert set(body) == STD_KEYS
    assert body["type"].endswith(f"/errors/{slug}")
    assert body["title"] == title
    assert body["status"] == status
    assert body["detail"] == detail
    assert body["instance"] == "/api/v1/x"
    assert body["request_id"] == "req-t-1"


# Shorthand GENID
GENID_RE = re.compile(r"^req_[0-9a-f]{32}$")


def assert_genid(resp):
    body = body_of(resp)
    assert GENID_RE.fullmatch(body["request_id"])
    assert resp.headers["X-Request-ID"] == body["request_id"]


# Shorthand NOLEAK(a, b, ...)
def assert_noleak(resp, *needles):
    txt = resp.body.decode()
    for n in needles:
        assert n not in txt, f"{n!r} leaked into body"


# Shorthand LOG1(level, message): exactly one app.core.exceptions record
def log1(caplog, level, message):
    recs = [r for r in caplog.records if r.name == LOGGER]
    assert len(recs) == 1, [r.getMessage() for r in recs]
    rec = recs[0]
    assert rec.levelno == level
    assert rec.getMessage() == message
    return rec


@pytest.fixture
def cap(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


# Shorthand FALSYID(handler, exc): (a) REQ-nullid, (b) REQ-emptyid.
# `level`/`message` select the handler's log record that is checked.
def assert_falsyid(caplog, handler, exc, level, message, extra_check):
    for req_factory, empty in ((REQ_nullid, False), (REQ_emptyid, True)):
        caplog.clear()
        resp = call(handler, req_factory(), exc)  # (a) no exception raised
        body = body_of(resp)
        assert_genid(resp)
        recs = [r for r in caplog.records
                if r.name == LOGGER and r.levelno == level and r.getMessage() == message]
        assert len(recs) == 1
        assert recs[0].request_id == body["request_id"]
        if empty:
            assert resp.headers["X-Request-ID"] != ""
        extra_check(resp, body)


# Convention "Settings": ERROR_TYPE_BASE_URL via monkeypatch.setattr(raising=False).
# Today Settings has no such field and pydantic refuses setattr of an unknown
# name (ValueError), which would abort before the "fails today on" assertion.
# Fallback: put the value in the instance __dict__ with monkeypatch.setitem
# (undone after the test). (best-practice default, delegated by reviewer)
def set_base_url(monkeypatch, value):
    try:
        monkeypatch.setattr(settings, "ERROR_TYPE_BASE_URL", value, raising=False)
    except ValueError:
        monkeypatch.setitem(settings.__dict__, "ERROR_TYPE_BASE_URL", value)


def assert_base_url_types(monkeypatch, handler, make_exc, slug, request_factory=REQ):
    set_base_url(monkeypatch, "")
    ta = body_of(call(handler, request_factory(), make_exc()))["type"]
    set_base_url(monkeypatch, "https://api.example.com")
    tb = body_of(call(handler, request_factory(), make_exc()))["type"]
    assert ta == f"/errors/{slug}"
    assert tb == f"https://api.example.com/errors/{slug}"
    assert "yourdomain" not in ta and "yourdomain" not in tb


def assert_problem_media(resp):
    assert resp.media_type == PROBLEM
    assert resp.headers["content-type"] == PROBLEM


# Convention "Real DB errors (setup TBL)"
@pytest.fixture
def tbl(db):
    db.execute(text(
        "CREATE TEMP TABLE exc_parent (id int PRIMARY KEY, "
        "code text CONSTRAINT exc_parent_code_key UNIQUE)"))
    db.execute(text(
        "CREATE TEMP TABLE exc_child (id int PRIMARY KEY, "
        "parent_id int CONSTRAINT exc_child_parent_fk REFERENCES exc_parent(id), "
        "description text, qty int CONSTRAINT exc_child_qty_ck CHECK (qty >= 0), "
        "label text NOT NULL)"))
    return db


def parent1(db):
    db.execute(text("INSERT INTO exc_parent (id, code) VALUES (1, 'SKU-1')"))


CHILD_INSERT = ("INSERT INTO exc_child (id, parent_id, description, qty, label) "
                "VALUES (:id, :parent_id, :description, :qty, :label)")


def db_error(db, sql, params=None):
    """Run the offending statement inside a savepoint; return the SQLAlchemy error."""
    try:
        with db.begin_nested():
            db.execute(text(sql), params or {})
    except DBAPIError as e:
        return e
    raise AssertionError("statement did not raise")


def child(db, **kw):
    params = {"id": 1, "parent_id": 1, "description": "Bowl", "qty": 1, "label": "L"}
    params.update(kw)
    return db_error(db, CHILD_INSERT, params)


# Convention "Stand-in cause SC(code, primary, text)" and its R4b variants
_MISSING = object()


class _Diag:
    def __init__(self, primary=_MISSING):
        if primary is not _MISSING:
            self.message_primary = primary


class SC(Exception):
    def __init__(self, code, primary, txt, diag=_MISSING):
        super().__init__(txt)
        self.pgcode = code
        if diag is _MISSING:
            self.diag = _Diag(primary)
        else:
            self.diag = diag


def SC_diagnone(code, txt):
    return SC(code, None, txt, diag=None)


def SC_nodiag(code, txt):
    s = SC(code, None, txt)
    del s.diag
    return s


def SC_noprimary(code, txt):
    return SC(code, None, txt, diag=_Diag())


SC_SQL = "INSERT INTO exc_booking (room) VALUES (%(room)s)"


def wrap_ie(cause):
    return IntegrityError(SC_SQL, {"room": 3}, cause)


# Shared fixtures from the cases file
PW_ERRORS = [{"type": "missing", "loc": ("body", "name"), "msg": "Field required",
              "input": {"email": "a@b.com", "password": "Hunter2!"}}]


def PW():
    return RequestValidationError(PW_ERRORS)


def OPX():
    return OperationalError(
        "SELECT 1", {"p": "v"},
        Exception("connection to server at 10.0.0.5 failed: password authentication failed for user admin"))


def rve(*locs_type_msg):
    return RequestValidationError(
        [{"type": t, "loc": loc, "msg": m, "input": None} for loc, t, m in locs_type_msg])


def fields(resp):
    return [e["field"] for e in body_of(resp)["errors"]]


# =========================================================================== #
# APIException.__init__
# =========================================================================== #

def test_exc_api_01__all_fields_stored():
    """EXC-API-01 — constructor stores every field; message is the detail.
    Rules: APIException R1, R3."""
    E = [{"field": "x", "message": "m", "code": "c"}]
    exc = APIException(418, "teapot", "I'm a teapot", "Short and stout", E)
    assert exc.status_code == 418
    assert exc.error_type == "teapot"
    assert exc.title == "I'm a teapot"
    assert exc.detail == "Short and stout"
    assert exc.errors is E
    assert str(exc) == "Short and stout"
    assert exc.args == ("Short and stout",)


def test_exc_api_02__errors_default_none():
    """EXC-API-02 — errors defaults to None.
    Rules: APIException R2."""
    exc = APIException(400, "bad", "Bad", "d")
    assert exc.errors is None
    assert str(exc) == "d"


def test_exc_api_03__is_an_exception():
    """EXC-API-03 — APIException is caught by `except Exception`.
    Rules: APIException R4."""
    caught = None
    try:
        raise APIException(500, "x", "X", "boom")
    except Exception as e:
        caught = e
    assert caught is not None
    assert isinstance(caught, Exception)
    assert caught.detail == "boom"


# =========================================================================== #
# ValidationError / PermissionDeniedError / NotFoundError / ConflictError /
# BusinessRuleError
# =========================================================================== #

def test_exc_val_01__validation_error_fields():
    """EXC-VAL-01 — ValidationError is a 400 validation_error APIException.
    Rules: ValidationError R1."""
    E = [{"field": "sku", "message": "taken", "code": "dup"}]
    exc = ValidationError("Bad SKU", errors=E)
    assert isinstance(exc, APIException)
    assert exc.status_code == 400
    assert exc.error_type == "validation_error"
    assert exc.title == "Validation Error"
    assert exc.detail == "Bad SKU"
    assert exc.errors is E
    assert str(exc) == "Bad SKU"


def test_exc_val_02__errors_default_none():
    """EXC-VAL-02 — errors defaults to None.
    Rules: ValidationError R2."""
    exc = ValidationError("Bad SKU")
    assert exc.errors is None
    assert exc.status_code == 400


def test_exc_val_03__detail_required():
    """EXC-VAL-03 — detail is required.
    Rules: ValidationError R3."""
    with pytest.raises(TypeError):
        ValidationError()


def test_exc_perm_01__default_detail():
    """EXC-PERM-01 — PermissionDeniedError defaults.
    Rules: PermissionDeniedError R1, R2."""
    exc = PermissionDeniedError()
    assert isinstance(exc, APIException)
    assert exc.status_code == 403
    assert exc.error_type == "permission_denied"
    assert exc.title == "Permission Denied"
    assert exc.errors is None
    assert exc.detail == "You do not have permission to perform this action"
    assert str(exc) == "You do not have permission to perform this action"


def test_exc_perm_02__custom_detail():
    """EXC-PERM-02 — custom detail overrides the default.
    Rules: PermissionDeniedError R2."""
    exc = PermissionDeniedError("Only owners can delete")
    assert exc.detail == "Only owners can delete"
    assert str(exc) == "Only owners can delete"
    assert exc.status_code == 403
    assert exc.title == "Permission Denied"


def test_exc_nf_01__not_found_fields():
    """EXC-NF-01 — NotFoundError is a 404 not_found APIException.
    Rules: NotFoundError R1."""
    exc = NotFoundError("Supplier 7 not found")
    assert isinstance(exc, APIException)
    assert exc.status_code == 404
    assert exc.error_type == "not_found"
    assert exc.title == "Resource Not Found"
    assert exc.detail == "Supplier 7 not found"
    assert exc.errors is None
    assert str(exc) == "Supplier 7 not found"


def test_exc_nf_02__detail_required():
    """EXC-NF-02 — detail is required.
    Rules: NotFoundError R2."""
    with pytest.raises(TypeError):
        NotFoundError()


def test_exc_conf_01__conflict_fields():
    """EXC-CONF-01 — ConflictError is a 409 conflict APIException.
    Rules: ConflictError R1."""
    exc = ConflictError("Name already used")
    assert isinstance(exc, APIException)
    assert exc.status_code == 409
    assert exc.error_type == "conflict"
    assert exc.title == "Resource Conflict"
    assert exc.detail == "Name already used"
    assert exc.errors is None
    assert str(exc) == "Name already used"


def test_exc_conf_02__detail_required():
    """EXC-CONF-02 — detail is required.
    Rules: ConflictError R2."""
    with pytest.raises(TypeError):
        ConflictError()


def test_exc_br_01__business_rule_fields():
    """EXC-BR-01 — BusinessRuleError is a 422 business_rule_violation APIException.
    Rules: BusinessRuleError R1."""
    E = [{"field": "qty", "message": "too high", "code": "max"}]
    exc = BusinessRuleError("Stock too low", errors=E)
    assert isinstance(exc, APIException)
    assert exc.status_code == 422
    assert exc.error_type == "business_rule_violation"
    assert exc.title == "Business Rule Violation"
    assert exc.detail == "Stock too low"
    assert exc.errors is E
    assert str(exc) == "Stock too low"


def test_exc_br_02__errors_default_none():
    """EXC-BR-02 — errors defaults to None.
    Rules: BusinessRuleError R2."""
    exc = BusinessRuleError("Stock too low")
    assert exc.errors is None
    assert exc.status_code == 422


def test_exc_br_03__detail_required():
    """EXC-BR-03 — detail is required.
    Rules: BusinessRuleError R3."""
    with pytest.raises(TypeError):
        BusinessRuleError()


# =========================================================================== #
# api_exception_handler
# =========================================================================== #

def test_exc_hapi_01__problem_body_from_instance():
    """EXC-HAPI-01 — 404 problem body; instance is the path without query.
    Rules: api_exception_handler R1, R2, R3, R4."""
    resp = call(api_exception_handler, REQ_q(), NotFoundError("Supplier 7 not found"))
    body = body_of(resp)
    assert resp.status_code == 404
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert set(body) == STD_KEYS
    assert body["type"].endswith("/errors/not_found")
    assert body["title"] == "Resource Not Found"
    assert body["status"] == 404
    assert body["detail"] == "Supplier 7 not found"
    assert body["instance"] == "/api/v1/suppliers/7"
    assert body["request_id"] == "req-t-1"


def test_exc_hapi_02__generated_request_ids_unique():
    """EXC-HAPI-02 — no request id → a fresh generated id per call.
    Rules: api_exception_handler R1."""
    r1 = call(api_exception_handler, REQ_noid(), NotFoundError("x"))
    r2 = call(api_exception_handler, REQ_noid(), NotFoundError("x"))
    assert_genid(r1)
    assert_genid(r2)
    assert body_of(r1)["request_id"] != body_of(r2)["request_id"]


def test_exc_hapi_03__field_errors_included():
    """EXC-HAPI-03 — non-empty errors list is added to the body in order.
    Rules: api_exception_handler R4."""
    E = [{"field": "sku", "message": "taken", "code": "dup"},
         {"field": "qty", "message": "neg", "code": "min"}]
    resp = call(api_exception_handler, REQ(), ValidationError("Bad input", errors=E))
    body = body_of(resp)
    assert resp.status_code == 400
    assert set(body) == STD_KEYS | {"errors"}
    assert body["errors"] == E
    assert body["title"] == "Validation Error"
    assert body["type"].endswith("/errors/validation_error")
    assert body["status"] == 400


def test_exc_hapi_04__empty_errors_omitted():
    """EXC-HAPI-04 — empty errors list → no errors key.
    Rules: api_exception_handler R4."""
    resp = call(api_exception_handler, REQ(), BusinessRuleError("Stock too low", errors=[]))
    assert_std(resp, "business_rule_violation", "Business Rule Violation", 422, "Stock too low")


def test_exc_hapi_05__fields_from_instance():
    """EXC-HAPI-05 — status, title and slug come from the exception instance.
    Rules: api_exception_handler R2, R3."""
    resp = call(api_exception_handler, REQ(),
                APIException(418, "teapot", "I'm a teapot", "Short and stout"))
    assert_std(resp, "teapot", "I'm a teapot", 418, "Short and stout")


def test_exc_hapi_06__logs_error_with_context(cap):
    """EXC-HAPI-06 — one ERROR log with request context, even for 4xx.
    Rules: api_exception_handler R5."""
    resp = call(api_exception_handler, REQ(), NotFoundError("Supplier 7 not found"))
    assert resp.status_code == 404
    assert resp.headers["X-Request-ID"] == "req-t-1"
    rec = log1(cap, logging.ERROR, "API Error: Resource Not Found")
    assert rec.request_id == "req-t-1"
    assert rec.error_type == "not_found"
    assert rec.status_code == 404
    assert rec.detail == "Supplier 7 not found"
    assert rec.path == "/api/v1/x"
    assert rec.method == "POST"
    assert rec.user_agent == "ua-test/1.0"
    assert rec.ip_address == "1.2.3.4"


def test_exc_hapi_07__no_headers_no_client(cap):
    """EXC-HAPI-07 — missing user-agent and client log as None.
    Rules: api_exception_handler R5."""
    resp = call(api_exception_handler, REQ_bare(), ConflictError("dup"))
    assert_std(resp, "conflict", "Resource Conflict", 409, "dup")
    rec = log1(cap, logging.ERROR, "API Error: Resource Conflict")
    assert rec.user_agent is None
    assert rec.ip_address is None


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hapi_08__type_uri_from_setting(monkeypatch):
    """EXC-HAPI-08 — type = ERROR_TYPE_BASE_URL + /errors/<slug>.
    Rules: api_exception_handler R3a [BUG-467]."""
    assert_base_url_types(monkeypatch, api_exception_handler, lambda: NotFoundError("x"), "not_found")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hapi_09__problem_json_media_type():
    """EXC-HAPI-09 — responses use application/problem+json, body unchanged.
    Rules: api_exception_handler R3b [BUG-468]."""
    resp = call(api_exception_handler, REQ(), NotFoundError("x"))
    assert_problem_media(resp)
    body = body_of(resp)
    assert body["detail"] == "x"
    assert body["status"] == 404


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hapi_10__null_request_id_treated_absent(cap):
    """EXC-HAPI-10 — request_id None → generated id, no crash.
    Rules: api_exception_handler R1a [BUG-469]."""
    resp = call(api_exception_handler, REQ_nullid(), NotFoundError("Supplier 7 not found"))
    body = body_of(resp)
    assert resp.status_code == 404
    assert_genid(resp)
    assert body["detail"] == "Supplier 7 not found"
    rec = log1(cap, logging.ERROR, "API Error: Resource Not Found")
    assert rec.request_id == body["request_id"]


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hapi_11__empty_request_id_treated_absent(cap):
    """EXC-HAPI-11 — request_id "" → generated id, non-empty header.
    Rules: api_exception_handler R1a [BUG-469]."""
    resp = call(api_exception_handler, REQ_emptyid(), NotFoundError("Supplier 7 not found"))
    body = body_of(resp)
    assert resp.status_code == 404
    assert_genid(resp)
    assert resp.headers["X-Request-ID"] != ""
    rec = log1(cap, logging.ERROR, "API Error: Resource Not Found")
    assert rec.request_id == body["request_id"]


# =========================================================================== #
# validation_exception_handler
# =========================================================================== #

def test_exc_hval_01__problem_body_and_no_input_leak():
    """EXC-HVAL-01 — validation problem body with sanitized field errors.
    Rules: validation_exception_handler R1, R2, R3, R7."""
    resp = call(validation_exception_handler, REQ(), PW())
    body = body_of(resp)
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert set(body) == STD_KEYS | {"errors"}
    assert body["type"].endswith("/errors/validation_error")
    assert body["title"] == "Validation Error"
    assert body["detail"] == "Request validation failed"
    assert body["instance"] == "/api/v1/x"
    assert body["request_id"] == "req-t-1"
    assert body["status"] == resp.status_code
    assert body["errors"] == [{"field": "name", "message": "Field required", "code": "missing"}]
    assert_noleak(resp, "Hunter2!", "a@b.com", "input")


def test_exc_hval_02__generated_request_id():
    """EXC-HVAL-02 — no request id → generated id.
    Rules: validation_exception_handler R1."""
    assert_genid(call(validation_exception_handler, REQ_noid(), PW()))


@pytest.mark.xfail(strict=True, reason=BUG_461)
def test_exc_hval_03__status_422():
    """EXC-HVAL-03 — request validation failures are 422.
    Rules: validation_exception_handler R1a [BUG-461]."""
    ra = call(validation_exception_handler, REQ(), PW())
    rb = call(validation_exception_handler, REQ(), RequestValidationError([
        {"type": "greater_than_equal", "loc": ("query", "limit"),
         "msg": "Input should be greater than or equal to 1", "input": "0", "ctx": {"ge": 1}}]))
    for r in (ra, rb):
        assert r.status_code == 422
        assert body_of(r)["status"] == 422


def test_exc_hval_04__empty_errors_list_kept():
    """EXC-HVAL-04 — empty error list still yields an errors key.
    Rules: validation_exception_handler R2."""
    resp = call(validation_exception_handler, REQ(), RequestValidationError([]))
    body = body_of(resp)
    assert "errors" in body
    assert body["errors"] == []
    assert body["detail"] == "Request validation failed"
    assert body["title"] == "Validation Error"
    assert resp.headers["X-Request-ID"] == "req-t-1"


def test_exc_hval_05__entries_have_three_keys_in_order():
    """EXC-HVAL-05 — each entry is exactly field/message/code, order kept.
    Rules: validation_exception_handler R2, R3, R7."""
    resp = call(validation_exception_handler, REQ(), RequestValidationError([
        {"type": "greater_than", "loc": ("body", "items", 0, "qty"),
         "msg": "Input should be greater than 0", "input": -5, "ctx": {"gt": 0},
         "url": "https://errors.pydantic.dev/2/v/greater_than"},
        {"type": "string_too_short", "loc": ("body", "name"),
         "msg": "String should have at least 1 character", "input": "", "ctx": {"min_length": 1}},
    ]))
    assert body_of(resp)["errors"] == [
        {"field": "items.0.qty", "message": "Input should be greater than 0", "code": "greater_than"},
        {"field": "name", "message": "String should have at least 1 character",
         "code": "string_too_short"},
    ]
    assert_noleak(resp, "errors.pydantic.dev", "ctx", "min_length")


def test_exc_hval_06__body_segment_dropped_everywhere():
    """EXC-HVAL-06 — "body" segments dropped anywhere; prefixes like bodyweight kept.
    Rules: validation_exception_handler R3."""
    resp = call(validation_exception_handler, REQ(), rve(
        (("body", "meta", "body", "note"), "missing", "Field required"),
        (("body", "bodyweight"), "float_type", "Input should be a valid number"),
    ))
    assert fields(resp) == ["meta.note", "bodyweight"]


def test_exc_hval_07__non_body_locations_kept():
    """EXC-HVAL-07 — query/path/header prefixes are kept.
    Rules: validation_exception_handler R4."""
    resp = call(validation_exception_handler, REQ(), rve(
        (("query", "limit"), "int_parsing", "bad"),
        (("path", "id"), "int_parsing", "bad"),
        (("header", "x-workspace-id"), "int_parsing", "bad"),
    ))
    assert fields(resp) == ["query.limit", "path.id", "header.x-workspace-id"]


def test_exc_hval_08__empty_path_becomes_body():
    """EXC-HVAL-08 — a path made only of "body" becomes "body".
    Rules: validation_exception_handler R5."""
    resp = call(validation_exception_handler, REQ(), rve(
        (("body",), "model_attributes_type", "Input should be a valid dictionary"),
        (("body", "body"), "model_attributes_type", "Input should be a valid dictionary"),
    ))
    assert fields(resp) == ["body", "body"]


def test_exc_hval_09__warning_log_without_input(cap):
    """EXC-HVAL-09 — one WARNING "Validation error" with sanitized errors.
    Rules: validation_exception_handler R6."""
    resp = call(validation_exception_handler, REQ(), PW())
    assert resp.headers["X-Request-ID"] == "req-t-1"
    recs = [r for r in cap.records if r.name == LOGGER and r.levelno == logging.WARNING
            and r.getMessage() == "Validation error"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec.request_id == "req-t-1"
    assert rec.errors == [{"field": "name", "message": "Field required", "code": "missing"}]
    assert rec.path == "/api/v1/x"
    assert rec.method == "POST"
    assert "Hunter2!" not in rec.getMessage()
    for v in rec.__dict__.values():
        assert "Hunter2!" not in str(v)


@pytest.mark.xfail(strict=True, reason=BUG_460)
def test_exc_hval_10__no_submitted_values_logged(cap):
    """EXC-HVAL-10 — only one WARNING record, no record contains submitted values.
    Rules: validation_exception_handler R6a [BUG-460]."""
    call(validation_exception_handler, REQ(), PW())
    log1(cap, logging.WARNING, "Validation error")
    for rec in cap.records:
        for needle in ("Hunter2!", "a@b.com"):
            assert needle not in rec.getMessage()
            for v in rec.__dict__.values():
                assert needle not in str(v)


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hval_11__type_uri_from_setting(monkeypatch):
    """EXC-HVAL-11 — type = ERROR_TYPE_BASE_URL + /errors/validation_error.
    Rules: validation_exception_handler R1, R3a [BUG-467]."""
    assert_base_url_types(monkeypatch, validation_exception_handler, PW, "validation_error")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hval_12__problem_json_media_type():
    """EXC-HVAL-12 — application/problem+json.
    Rules: validation_exception_handler R1, R3b [BUG-468]."""
    resp = call(validation_exception_handler, REQ(), PW())
    assert_problem_media(resp)
    assert body_of(resp)["detail"] == "Request validation failed"


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hval_13__falsy_request_id(cap):
    """EXC-HVAL-13 — FALSYID for validation_exception_handler.
    Rules: validation_exception_handler R1, api_exception_handler R1a [BUG-469]."""
    def extra(resp, body):
        assert body["detail"] == "Request validation failed"
    assert_falsyid(cap, validation_exception_handler, PW(), logging.WARNING,
                   "Validation error", extra)


# =========================================================================== #
# integrity_error_handler
# =========================================================================== #

def test_exc_hint_01__unique_violation(tbl):
    """EXC-HINT-01 — real 23505 → 409 "already exists", nothing leaks.
    Rules: integrity_error_handler R1, R2, R3, R7, R8."""
    parent1(tbl)
    exc = db_error(tbl, "INSERT INTO exc_parent (id, code) VALUES (:id, :code)",
                   {"id": 2, "code": "SKU-1"})
    resp = call(integrity_error_handler, REQ(), exc)
    assert_std(resp, "conflict", "Resource Conflict", 409, DUP_MSG)
    assert_noleak(resp, "exc_parent", "exc_parent_code_key", "SKU-1", "INSERT",
                  "duplicate key", "[SQL")


def test_exc_hint_02__codeless_fallback():
    """EXC-HINT-02 — code-less cause → 409 conflict fallback, generated id.
    Rules: integrity_error_handler R1, R2, R6, R7."""
    exc = IntegrityError("UPDATE t SET a=1", {"p": "v"}, Exception("constraint check failed"))
    resp = call(integrity_error_handler, REQ_noid(), exc)
    body = body_of(resp)
    assert_genid(resp)
    assert resp.status_code == 409
    assert body["status"] == 409
    assert body["title"] == "Resource Conflict"
    assert body["type"].endswith("/errors/conflict")
    assert set(body) == STD_KEYS
    assert_noleak(resp, "constraint check failed", "UPDATE t")


def test_exc_hint_03__fk_insert_direction(tbl):
    """EXC-HINT-03 — real 23503 (insert) → 409 "Referenced resource does not exist."
    Rules: integrity_error_handler R4, R7, R8."""
    parent1(tbl)
    exc = child(tbl, parent_id=999)
    resp = call(integrity_error_handler, REQ(), exc)
    assert_std(resp, "conflict", "Resource Conflict", 409, FK_MSG)
    assert_noleak(resp, "exc_child", "exc_child_parent_fk", "999", "Bowl")


def _fk_delete_error(db):
    parent1(db)
    db.execute(text(CHILD_INSERT),
               {"id": 1, "parent_id": 1, "description": "Bowl", "qty": 1, "label": "L"})
    return db_error(db, "DELETE FROM exc_parent WHERE id = :id", {"id": 1})


@pytest.mark.xfail(strict=True, reason=BUG_463)
def test_exc_hint_04__fk_delete_direction_detail(tbl):
    """EXC-HINT-04 — delete blocked by references → "still in use".
    Rules: integrity_error_handler R4a [BUG-463]."""
    resp = call(integrity_error_handler, REQ(), _fk_delete_error(tbl))
    assert body_of(resp)["detail"] == "This resource is still in use by other records."


def test_exc_hint_05__fk_delete_direction_shape(tbl):
    """EXC-HINT-05 — delete blocked by references: 409 conflict shape, no leak.
    Rules: integrity_error_handler R4a, R7, R8."""
    resp = call(integrity_error_handler, REQ(), _fk_delete_error(tbl))
    body = body_of(resp)
    assert resp.status_code == 409
    assert body["status"] == 409
    assert body["title"] == "Resource Conflict"
    assert body["type"].endswith("/errors/conflict")
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert set(body) == STD_KEYS
    assert_noleak(resp, "exc_parent", "exc_child", "exc_child_parent_fk")


def test_exc_hint_06__direction_from_primary_not_params(tbl):
    """EXC-HINT-06 — insert-direction FK stays "does not exist" despite parameter text.
    Rules: integrity_error_handler R4a."""
    parent1(tbl)
    exc = child(tbl, parent_id=999, description="update or delete on table exc_parent")
    resp = call(integrity_error_handler, REQ(), exc)
    body = body_of(resp)
    assert body["detail"] == FK_MSG
    assert body["status"] == 409


def _not_null_error(db, description="Bowl"):
    parent1(db)
    return child(db, description=description, label=None)


def test_exc_hint_07__not_null_violation(tbl):
    """EXC-HINT-07 — real 23502 → 400 "Required field is missing."
    Rules: integrity_error_handler R5, R8."""
    resp = call(integrity_error_handler, REQ(), _not_null_error(tbl))
    body = body_of(resp)
    assert resp.status_code == 400
    assert body["status"] == 400
    assert body["detail"] == NN_MSG
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert set(body) == STD_KEYS
    assert body["instance"] == "/api/v1/x"
    assert_noleak(resp, "exc_child", "label", "Bowl")


@pytest.mark.xfail(strict=True, reason=BUG_465)
def test_exc_hint_08__not_null_is_validation_error(tbl):
    """EXC-HINT-08 — not-null 400 is titled "Validation Error".
    Rules: integrity_error_handler R7a [BUG-465]."""
    resp = call(integrity_error_handler, REQ(), _not_null_error(tbl))
    body = body_of(resp)
    assert body["title"] == "Validation Error"
    assert body["type"].endswith("/errors/validation_error")
    assert body["status"] == 400


def _check_error(db):
    parent1(db)
    return child(db, qty=-5)


@pytest.mark.xfail(strict=True, reason=BUG_464)
def test_exc_hint_09__check_violation_422(tbl):
    """EXC-HINT-09 — real 23514 → 422 validation_error.
    Rules: integrity_error_handler R5a [BUG-464]."""
    resp = call(integrity_error_handler, REQ(), _check_error(tbl))
    assert_std(resp, "validation_error", "Validation Error", 422,
               "A value is outside the allowed range.")


def test_exc_hint_10__check_violation_shape(tbl):
    """EXC-HINT-10 — 23514 response shape; no constraint names leak.
    Rules: integrity_error_handler R5a, R8."""
    resp = call(integrity_error_handler, REQ(), _check_error(tbl))
    body = body_of(resp)
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert body["request_id"] == "req-t-1"
    assert body["instance"] == "/api/v1/x"
    assert body["status"] == resp.status_code
    assert set(body) == STD_KEYS
    assert_noleak(resp, "exc_child_qty_ck", "exc_child", "check constraint")


def _excl_exc():
    msg = 'conflicting key value violates exclusion constraint "exc_booking_excl"'
    return wrap_ie(SC("23P01", msg, msg))


def test_exc_hint_11__exclusion_violation_shape():
    """EXC-HINT-11 — 23P01 → 409 conflict, no names leak.
    Rules: integrity_error_handler R6, R7, R8."""
    resp = call(integrity_error_handler, REQ(), _excl_exc())
    body = body_of(resp)
    assert resp.status_code == 409
    assert body["status"] == 409
    assert body["title"] == "Resource Conflict"
    assert body["type"].endswith("/errors/conflict")
    assert set(body) == STD_KEYS
    assert_noleak(resp, "exc_booking_excl", "exc_booking")


@pytest.mark.xfail(strict=True, reason=BUG_464)
def test_exc_hint_12__unclassified_detail():
    """EXC-HINT-12 — unclassified violation → "A database constraint was violated."
    Rules: integrity_error_handler R6a [BUG-464]."""
    resp = call(integrity_error_handler, REQ(), _excl_exc())
    assert body_of(resp)["detail"] == "A database constraint was violated."
    assert "may already exist" not in resp.body.decode()


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_13__fk_with_unique_in_params(tbl):
    """EXC-HINT-13 — real 23503 with "Unique" in a value stays FK.
    Rules: integrity_error_handler R2 [BUG-462]."""
    parent1(tbl)
    exc = child(tbl, parent_id=999, description="Unique handmade bowl")
    resp = call(integrity_error_handler, REQ(), exc)
    body = body_of(resp)
    assert body["detail"] == FK_MSG
    assert body["status"] == 409


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_14__not_null_with_duplicate_in_params(tbl):
    """EXC-HINT-14 — real 23502 with "duplicate" in a value stays not-null.
    Rules: integrity_error_handler R2 [BUG-462]."""
    resp = call(integrity_error_handler, REQ(), _not_null_error(tbl, description="duplicate"))
    assert resp.status_code == 400
    assert body_of(resp)["detail"] == NN_MSG


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_15__codeless_duplicate_text_unclassified():
    """EXC-HINT-15 — code-less "duplicate key" text → unclassified.
    Rules: integrity_error_handler R2, R6a [BUG-462]."""
    exc = IntegrityError("INSERT INTO t", {"p": "v"},
                         Exception('duplicate key value violates unique constraint "t_key"'))
    body = body_of(call(integrity_error_handler, REQ(), exc))
    assert body["status"] == 409
    assert body["title"] == "Resource Conflict"
    assert body["detail"] == "A database constraint was violated."


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_16__codeless_null_text_unclassified():
    """EXC-HINT-16 — code-less "null value" text → unclassified 409.
    Rules: integrity_error_handler R2, R6a [BUG-462]."""
    exc = IntegrityError("INSERT INTO t", {"p": "v"},
                         Exception('null value in column "x" violates not-null constraint'))
    resp = call(integrity_error_handler, REQ(), exc)
    body = body_of(resp)
    assert resp.status_code == 409
    assert body["title"] == "Resource Conflict"
    assert body["detail"] == "A database constraint was violated."


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_17__code_23505_without_keywords():
    """EXC-HINT-17 — pgcode 23505 classifies as duplicate whatever the text.
    Rules: integrity_error_handler R2, R3 [BUG-462]."""
    body = body_of(call(integrity_error_handler, REQ(),
                        wrap_ie(SC("23505", "row rejected", "row rejected"))))
    assert body["status"] == 409
    assert body["detail"] == DUP_MSG


def test_exc_hint_18__logs_error_with_traceback(tbl, cap):
    """EXC-HINT-18 — one ERROR "Database integrity error" with traceback.
    Rules: integrity_error_handler R9."""
    parent1(tbl)
    exc = db_error(tbl, "INSERT INTO exc_parent (id, code) VALUES (:id, :code)",
                   {"id": 2, "code": "SKU-1"})
    cap.clear()
    resp = call(integrity_error_handler, REQ(), exc)
    assert resp.status_code == 409
    assert resp.headers["X-Request-ID"] == "req-t-1"
    rec = log1(cap, logging.ERROR, "Database integrity error")
    assert rec.request_id == "req-t-1"
    assert rec.error == str(exc)
    assert rec.path == "/api/v1/x"
    assert rec.exc_info[1] is exc


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hint_19__type_uri_from_setting(monkeypatch):
    """EXC-HINT-19 — type = ERROR_TYPE_BASE_URL + /errors/conflict.
    Rules: integrity_error_handler R7, R3a [BUG-467]."""
    assert_base_url_types(monkeypatch, integrity_error_handler,
                          lambda: IntegrityError("X", {}, Exception("boom")), "conflict")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hint_20__problem_json_media_type():
    """EXC-HINT-20 — application/problem+json.
    Rules: integrity_error_handler R1, R3b [BUG-468]."""
    resp = call(integrity_error_handler, REQ(), IntegrityError("X", {}, Exception("boom")))
    assert_problem_media(resp)
    assert body_of(resp)["status"] == 409


@pytest.mark.xfail(strict=True, reason=BUG_462)
@pytest.mark.parametrize("cause", [
    pytest.param(lambda: SC("23503", None, "row rejected"), id="EXC-HINT-21"),
    pytest.param(lambda: SC_diagnone("23503", "row rejected"), id="EXC-HINT-22"),
    pytest.param(lambda: SC_nodiag("23503", "row rejected"), id="EXC-HINT-23"),
    pytest.param(lambda: SC_noprimary("23503", "row rejected"), id="EXC-HINT-24"),
])
def test_exc_hint_21_24__fk_unreadable_direction(cause):
    """EXC-HINT-21..24 — 23503 whose direction cannot be read → R4 answer, no crash.
    Rules: integrity_error_handler R4b [BUG-462]."""
    resp = call(integrity_error_handler, REQ(), wrap_ie(cause()))  # no exception raised
    assert_std(resp, "conflict", "Resource Conflict", 409, FK_MSG)


@pytest.mark.xfail(strict=True, reason=BUG_462)
def test_exc_hint_25__fk_unknown_prefix():
    """EXC-HINT-25 — 23503 primary with unknown prefix → R4 answer.
    Rules: integrity_error_handler R4b [BUG-462]."""
    msg = "row rejected by referential rule"
    resp = call(integrity_error_handler, REQ(), wrap_ie(SC("23503", msg, msg)))
    assert_std(resp, "conflict", "Resource Conflict", 409, FK_MSG)


def test_exc_hint_26__fk_diag_none_never_raises():
    """EXC-HINT-26 — 23503 with diag None → R4 answer, no leak.
    Rules: integrity_error_handler R4b."""
    resp = call(integrity_error_handler, REQ(),
                wrap_ie(SC_diagnone("23503", 'violates foreign key constraint "exc_booking_fk"')))
    assert_std(resp, "conflict", "Resource Conflict", 409, FK_MSG)
    assert_noleak(resp, "exc_booking_fk", "exc_booking")


def test_exc_hint_27__fk_no_diag_never_raises():
    """EXC-HINT-27 — 23503 with no diag attribute → R4 answer.
    Rules: integrity_error_handler R4b."""
    resp = call(integrity_error_handler, REQ(),
                wrap_ie(SC_nodiag("23503", 'violates foreign key constraint "exc_booking_fk"')))
    assert_std(resp, "conflict", "Resource Conflict", 409, FK_MSG)


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hint_28__falsy_request_id(cap):
    """EXC-HINT-28 — FALSYID for integrity_error_handler.
    Rules: integrity_error_handler R1, api_exception_handler R1a [BUG-469]."""
    def extra(resp, body):
        assert resp.status_code == 409
    assert_falsyid(cap, integrity_error_handler, IntegrityError("X", {}, Exception("boom")),
                   logging.ERROR, "Database integrity error", extra)


# =========================================================================== #
# database_error_handler
# =========================================================================== #

def test_exc_hdb_01__service_unavailable():
    """EXC-HDB-01 — 503 fixed body, no Retry-After, nothing leaks.
    Rules: database_error_handler R1, R2."""
    resp = call(database_error_handler, REQ(), OPX())
    assert_std(resp, "service_unavailable", "Service Unavailable", 503, TEMP_MSG)
    assert "retry-after" not in resp.headers
    assert_noleak(resp, "10.0.0.5", "password authentication", "SELECT 1", "admin")


def test_exc_hdb_02__same_body_any_content():
    """EXC-HDB-02 — generated id; same body whatever the error.
    Rules: database_error_handler R1."""
    resp = call(database_error_handler, REQ_noid(),
                OperationalError("UPDATE t", {}, Exception("deadlock detected")))
    body = body_of(resp)
    assert_genid(resp)
    assert resp.status_code == 503
    assert body["title"] == "Service Unavailable"
    assert body["detail"] == TEMP_MSG
    assert_noleak(resp, "deadlock")


def test_exc_hdb_03__logs_error_with_traceback(cap):
    """EXC-HDB-03 — one ERROR "Database operational error" with traceback.
    Rules: database_error_handler R3."""
    exc = OPX()
    resp = call(database_error_handler, REQ(), exc)
    assert resp.status_code == 503
    assert resp.headers["X-Request-ID"] == "req-t-1"
    rec = log1(cap, logging.ERROR, "Database operational error")
    assert rec.request_id == "req-t-1"
    assert rec.error == str(exc)
    assert rec.path == "/api/v1/x"
    assert rec.exc_info[1] is exc


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hdb_04__type_uri_from_setting(monkeypatch):
    """EXC-HDB-04 — type = ERROR_TYPE_BASE_URL + /errors/service_unavailable.
    Rules: database_error_handler R1, R3a [BUG-467]."""
    assert_base_url_types(monkeypatch, database_error_handler, OPX, "service_unavailable")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hdb_05__problem_json_media_type():
    """EXC-HDB-05 — application/problem+json.
    Rules: database_error_handler R1, R3b [BUG-468]."""
    assert_problem_media(call(database_error_handler, REQ(), OPX()))


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hdb_06__falsy_request_id(cap):
    """EXC-HDB-06 — FALSYID for database_error_handler.
    Rules: database_error_handler R1, api_exception_handler R1a [BUG-469]."""
    def extra(resp, body):
        assert resp.status_code == 503
    assert_falsyid(cap, database_error_handler, OPX(), logging.ERROR,
                   "Database operational error", extra)


# =========================================================================== #
# schema_error_handler
# =========================================================================== #

def test_exc_hsch_01__missing_table_debug(db, cap, monkeypatch):
    """EXC-HSCH-01 — real 42P01, DEBUG → 503 schema message; logged with traceback.
    Rules: schema_error_handler R1, R2, R3, R4."""
    monkeypatch.setattr(settings, "DEBUG", True)
    exc = db_error(db, "SELECT * FROM exc_no_such_table")
    cap.clear()
    resp = call(schema_error_handler, REQ(), exc)
    assert_std(resp, "service_unavailable", "Service Unavailable", 503, SCHEMA_MSG)
    assert_noleak(resp, "exc_no_such_table", "SELECT", "does not exist")
    rec = log1(cap, logging.ERROR, "Database schema error")
    assert rec.request_id == "req-t-1"
    assert rec.error == str(exc)
    assert rec.path == "/api/v1/x"
    assert rec.exc_info[1] is exc


def test_exc_hsch_02__missing_column_prod(db, monkeypatch):
    """EXC-HSCH-02 — real 42703, DEBUG off → 503 generic temp message.
    Rules: schema_error_handler R1, R2."""
    monkeypatch.setattr(settings, "DEBUG", False)
    exc = db_error(db, "SELECT exc_no_such_col FROM (SELECT 1 AS a) s")
    resp = call(schema_error_handler, REQ_noid(), exc)
    body = body_of(resp)
    assert_genid(resp)
    assert resp.status_code == 503
    assert body["status"] == 503
    assert body["title"] == "Service Unavailable"
    assert body["type"].endswith("/errors/service_unavailable")
    assert body["detail"] == TEMP_MSG
    assert_noleak(resp, "exc_no_such_col")


@pytest.mark.xfail(strict=True, reason=BUG_466)
def test_exc_hsch_03__syntax_error_is_500(db, monkeypatch):
    """EXC-HSCH-03 — real 42601 → 500 internal_error.
    Rules: schema_error_handler R1a [BUG-466]."""
    monkeypatch.setattr(settings, "DEBUG", True)
    exc = db_error(db, "SELEC 1")
    resp = call(schema_error_handler, REQ(), exc)
    assert_std(resp, "internal_error", "Internal Server Error", 500, GEN_MSG)


@pytest.mark.xfail(strict=True, reason=BUG_466)
def test_exc_hsch_04__undefined_function_is_500(monkeypatch):
    """EXC-HSCH-04 — 42883 → 500 internal_error.
    Rules: schema_error_handler R1a [BUG-466]."""
    monkeypatch.setattr(settings, "DEBUG", False)
    msg = "function f() does not exist"
    resp = call(schema_error_handler, REQ(), ProgrammingError("SELECT f()", {}, SC("42883", msg, msg)))
    assert_std(resp, "internal_error", "Internal Server Error", 500, GEN_MSG)


@pytest.mark.xfail(strict=True, reason=BUG_466)
def test_exc_hsch_05__codeless_is_500(monkeypatch):
    """EXC-HSCH-05 — code-less ProgrammingError → 500 even if text looks like missing table.
    Rules: schema_error_handler R1a [BUG-466]."""
    monkeypatch.setattr(settings, "DEBUG", True)
    exc = ProgrammingError("SELECT x", {}, Exception('relation "t" does not exist'))
    resp = call(schema_error_handler, REQ(), exc)
    assert_std(resp, "internal_error", "Internal Server Error", 500, GEN_MSG)


def test_exc_hsch_06__syntax_error_shape_and_log(db, cap, monkeypatch):
    """EXC-HSCH-06 — real 42601: response shape, no leak, logged with traceback.
    Rules: schema_error_handler R1a, R3, R4."""
    monkeypatch.setattr(settings, "DEBUG", True)
    exc = db_error(db, "SELEC 1")
    cap.clear()
    resp = call(schema_error_handler, REQ(), exc)
    body = body_of(resp)
    assert resp.headers["X-Request-ID"] == "req-t-1"
    assert body["request_id"] == "req-t-1"
    assert body["instance"] == "/api/v1/x"
    assert set(body) == STD_KEYS
    assert body["status"] == resp.status_code
    assert_noleak(resp, "SELEC", "syntax error")
    rec = log1(cap, logging.ERROR, "Database schema error")
    assert rec.request_id == "req-t-1"
    assert rec.error == str(exc)
    assert rec.path == "/api/v1/x"
    assert rec.exc_info[1] is exc


def _hsch07_exc():
    return ProgrammingError("SELECT", {}, SC("42P01", "relation missing", "relation missing"))


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hsch_07__type_uri_from_setting(monkeypatch):
    """EXC-HSCH-07 — type = ERROR_TYPE_BASE_URL + /errors/service_unavailable.
    Rules: schema_error_handler R1, R3a [BUG-467]."""
    monkeypatch.setattr(settings, "DEBUG", True)
    assert_base_url_types(monkeypatch, schema_error_handler, _hsch07_exc, "service_unavailable")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hsch_08__problem_json_media_type(monkeypatch):
    """EXC-HSCH-08 — application/problem+json.
    Rules: schema_error_handler R1, R3b [BUG-468]."""
    monkeypatch.setattr(settings, "DEBUG", True)
    assert_problem_media(call(schema_error_handler, REQ(), _hsch07_exc()))


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hsch_09__falsy_request_id(cap, monkeypatch):
    """EXC-HSCH-09 — FALSYID for schema_error_handler.
    Rules: schema_error_handler R1, api_exception_handler R1a [BUG-469]."""
    monkeypatch.setattr(settings, "DEBUG", True)

    def extra(resp, body):
        assert resp.status_code == 503
    assert_falsyid(cap, schema_error_handler, _hsch07_exc(), logging.ERROR,
                   "Database schema error", extra)


# =========================================================================== #
# generic_exception_handler
# =========================================================================== #

def test_exc_hgen_01__sanitized_500():
    """EXC-HGEN-01 — 500 generic body; exception text and type never leak.
    Rules: generic_exception_handler R1, R2."""
    resp = call(generic_exception_handler, REQ(), ValueError("secret-token-123"))
    assert_std(resp, "internal_error", "Internal Server Error", 500, GEN_MSG)
    assert_noleak(resp, "ValueError", "secret-token-123")


def test_exc_hgen_02__generated_request_id():
    """EXC-HGEN-02 — generated id; generic body.
    Rules: generic_exception_handler R1, R2."""
    resp = call(generic_exception_handler, REQ_noid(), KeyError("sku"))
    body = body_of(resp)
    assert_genid(resp)
    assert resp.status_code == 500
    assert body["title"] == "Internal Server Error"
    assert body["detail"] == GEN_MSG
    assert_noleak(resp, "KeyError", "sku")


def test_exc_hgen_03__logs_exception_with_context(cap):
    """EXC-HGEN-03 — one ERROR "Unexpected error" with traceback and context.
    Rules: generic_exception_handler R3."""
    exc = ValueError("secret-token-123")
    resp = call(generic_exception_handler, REQ(), exc)
    assert resp.status_code == 500
    assert resp.headers["X-Request-ID"] == "req-t-1"
    rec = log1(cap, logging.ERROR, "Unexpected error")
    assert rec.exc_info[1] is exc
    assert rec.request_id == "req-t-1"
    assert rec.error_type == "ValueError"
    assert rec.error == "secret-token-123"
    assert rec.path == "/api/v1/x"
    assert rec.method == "POST"
    assert rec.user_agent == "ua-test/1.0"
    assert rec.ip_address == "1.2.3.4"


def test_exc_hgen_04__no_headers_no_client(cap):
    """EXC-HGEN-04 — missing user-agent / client log as None.
    Rules: generic_exception_handler R3."""
    resp = call(generic_exception_handler, REQ_bare(), ValueError("x"))
    assert_std(resp, "internal_error", "Internal Server Error", 500, GEN_MSG)
    rec = log1(cap, logging.ERROR, "Unexpected error")
    assert rec.user_agent is None
    assert rec.ip_address is None


@pytest.mark.xfail(strict=True, reason=BUG_467)
def test_exc_hgen_05__type_uri_from_setting(monkeypatch):
    """EXC-HGEN-05 — type = ERROR_TYPE_BASE_URL + /errors/internal_error.
    Rules: generic_exception_handler R1, R3a [BUG-467]."""
    assert_base_url_types(monkeypatch, generic_exception_handler,
                          lambda: ValueError("x"), "internal_error")


@pytest.mark.xfail(strict=True, reason=BUG_468)
def test_exc_hgen_06__problem_json_media_type():
    """EXC-HGEN-06 — application/problem+json.
    Rules: generic_exception_handler R1, R3b [BUG-468]."""
    assert_problem_media(call(generic_exception_handler, REQ(), ValueError("x")))


@pytest.mark.xfail(strict=True, reason=BUG_469)
def test_exc_hgen_07__falsy_request_id(cap):
    """EXC-HGEN-07 — FALSYID for generic_exception_handler.
    Rules: generic_exception_handler R1, api_exception_handler R1a [BUG-469]."""
    def extra(resp, body):
        assert resp.status_code == 500
    assert_falsyid(cap, generic_exception_handler, ValueError("x"), logging.ERROR,
                   "Unexpected error", extra)
