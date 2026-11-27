"""Unit tests for app/core/middleware.py.

Implements tests/unit/core/middleware.cases.md (revision 4), one test per case
(parametrized cases keep one pytest.param id per variant, prefixed with the
case id). No database: both middlewares are pure. Harness per the cases file:
a fresh minimal FastAPI app per test (built-in docs routes disabled) called via
TestClient, or direct `dispatch(...)` on a hand-built Starlette Request.
Patched: `app.core.middleware.uuid.uuid4` (ID1) and `app.core.middleware.time.time`
(T) only.
"""
# ruff: noqa: SIM117  (prescribed by the cards: nested with)
import asyncio
import json
import logging
import re
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.responses import Response
from starlette.testclient import TestClient

from app.core import config as core_config
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

BUG_480 = "BUG-480: Request log writes secret query parameters (e.g. mobile-upload `token`) verbatim"
BUG_481 = "BUG-481: Every 4xx response is logged at ERROR"
BUG_482 = "BUG-482: Crashing request has no \"Request completed\" log line"
BUG_483 = "BUG-483: 500s from unhandled exceptions carry no security headers"
BUG_484 = "BUG-484: API-docs pages get no security headers at all"
BUG_485 = "BUG-485: Docs exemption matches look-alike paths and ignores the configured API prefix"
BUG_486 = "BUG-486: X-XSS-Protection sent in deprecated block mode"
BUG_487 = "BUG-487: Security headers overwrite values an endpoint set on purpose"

# Convention "Fixed request id" (ID1) and id regex
ID1_UUID = UUID("12345678-1234-5678-1234-567812345678")
ID1 = "req_12345678123456781234567812345678"
ID_RE = re.compile(r"^req_[0-9a-f]{32}$")

# Convention "Security header defaults"
XCTO = ("X-Content-Type-Options", "nosniff")
XFO = ("X-Frame-Options", "DENY")
HSTS = ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
XXSS = ("X-XSS-Protection", "0")
CSP = ("Content-Security-Policy", "default-src 'self'")
THREE = (XCTO, XFO, HSTS)

# Module-level exceptions (MW-RC-24/25, MW-SH-18, MW-SH-23)
BOOM = ValueError("boom")
BOOM_RT = RuntimeError("boom")
BOOM_KE = KeyError("k")

GENERIC_DETAIL = "An unexpected error occurred. Please contact support with the request ID."


@pytest.fixture
def id1():
    """Convention ID1: uuid4 returns a fixed UUID -> request id ID1."""
    with patch("app.core.middleware.uuid.uuid4", return_value=ID1_UUID) as m:
        yield m


def T(start: float, end: float):
    """Convention T(start, end): first time.time() call -> start, every later call -> end.
    Use only around a direct-dispatch await."""
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return start if calls["n"] == 1 else end

    return patch("app.core.middleware.time.time", side_effect=fake)


@pytest.fixture
def logs(caplog):
    """Convention "Logs": DEBUG capture for the middleware and exceptions loggers."""
    caplog.set_level(logging.DEBUG, logger="app.core.middleware")
    caplog.set_level(logging.DEBUG, logger="app.core.exceptions")
    return caplog


def _records(caplog, logger_name: str, message: str):
    return [r for r in caplog.records if r.name == logger_name and r.getMessage() == message]


def started(caplog):
    return _records(caplog, "app.core.middleware", "Request started")


def completed(caplog):
    return _records(caplog, "app.core.middleware", "Request completed")


def unexpected(caplog):
    return _records(caplog, "app.core.exceptions", "Unexpected error")


def one_started(caplog):
    recs = started(caplog)
    assert len(recs) == 1
    return recs[0]


def one_completed(caplog):
    recs = completed(caplog)
    assert len(recs) == 1
    return recs[0]


# Convention "App under test"
def make_app(*middlewares) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    for mw in middlewares:
        app.add_middleware(mw)
    return app


def rc_app() -> FastAPI:
    return make_app(RequestContextMiddleware)


def sh_app() -> FastAPI:
    return make_app(SecurityHeadersMiddleware)


def html_route(app: FastAPI, path: str, body: str = "<p>d</p>", **kw):
    async def handler():
        return HTMLResponse(body, **kw)

    app.add_api_route(path, handler, methods=["GET"])


def add_echo_id(app: FastAPI):
    @app.get("/echo-id")
    async def echo_id(request: Request):
        return {"request_id": request.state.request_id}


def add_status_route(app: FastAPI, prefix: str = ""):
    async def status_route(code: int):
        headers = {"Location": "/x"} if code == 302 else None
        return Response(status_code=code, headers=headers)

    app.add_api_route(prefix + "/status/{code}", status_route, methods=["GET"])


def add_plain(app: FastAPI, path: str, method: str = "GET"):
    async def handler():
        return {"ok": True}

    app.add_api_route(path, handler, methods=[method])


# Convention "Direct dispatch"
_MISSING = object()


def make_request(**overrides) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/items",
        "raw_path": b"/items",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
    }
    for k, v in overrides.items():
        if v is _MISSING:
            scope.pop(k, None)
        else:
            scope[k] = v
    return Request(scope)


def ok_call_next():
    resp = Response(content=b"ok", status_code=200)

    async def call_next(request):
        return resp

    return resp, call_next


def raising_call_next(exc):
    async def call_next(request):
        raise exc

    return call_next


def rc_dispatch(request, call_next):
    return RequestContextMiddleware(app=None).dispatch(request, call_next)


def sh_dispatch(request, call_next):
    return SecurityHeadersMiddleware(app=None).dispatch(request, call_next)


# Header assertion helpers
def assert_headers(resp, specs, exactly_one: bool = False):
    for name, value in specs:
        if exactly_one:
            assert resp.headers.get_list(name) == [value], name
        else:
            assert resp.headers.get(name) == value, name


def assert_no_csp(resp):
    assert "content-security-policy" not in resp.headers


# Convention "Return value (every case)": the route's status and, where it has
# one, its body reach the client unchanged.
def assert_returned(resp, status: int = 200, *, json_body=_MISSING, text=_MISSING, content=_MISSING):
    assert resp.status_code == status
    if json_body is not _MISSING:
        assert resp.json() == json_body
    if text is not _MISSING:
        assert resp.text == text
    if content is not _MISSING:
        assert resp.content == content


# --------------------------------------------------------------------------- #
# RequestContextMiddleware.dispatch
# --------------------------------------------------------------------------- #


def test_mw_rc_01__id_in_state_header_and_logs(id1, logs):
    """MW-RC-01 — the fixed id reaches request.state, the X-Request-ID header and both log records.
    Rules: RC R1, R2, R3."""
    app = rc_app()
    add_echo_id(app)
    r = TestClient(app).get("/echo-id")
    assert r.status_code == 200
    assert r.json()["request_id"] == ID1
    assert r.headers["X-Request-ID"] == ID1
    assert one_started(logs).request_id == ID1
    assert one_completed(logs).request_id == ID1


def test_mw_rc_02__ids_unique_per_request(logs):
    """MW-RC-02 — two requests get two different well-formed ids.
    Rules: RC R1."""
    app = rc_app()
    add_echo_id(app)
    client = TestClient(app)
    r1 = client.get("/echo-id")
    r2 = client.get("/echo-id")
    assert_returned(r1)
    assert_returned(r2)
    h1, h2 = r1.headers["X-Request-ID"], r2.headers["X-Request-ID"]
    assert ID_RE.match(h1)
    assert ID_RE.match(h2)
    assert h1 != h2
    assert r1.json()["request_id"] == h1
    assert r2.json()["request_id"] == h2


def test_mw_rc_03__client_request_id_ignored(id1, logs):
    """MW-RC-03 — a client-sent X-Request-ID is ignored.
    Rules: RC R1."""
    app = rc_app()
    add_echo_id(app)
    r = TestClient(app).get("/echo-id", headers={"X-Request-ID": "client-abc"})
    assert_returned(r)
    assert r.headers["X-Request-ID"] == ID1
    assert r.json()["request_id"] == ID1
    assert one_started(logs).request_id == ID1


def test_mw_rc_04__route_request_id_replaced(id1, logs):
    """MW-RC-04 — a route's own X-Request-ID is replaced, not duplicated.
    Rules: RC R3."""
    app = rc_app()

    @app.get("/own-id")
    async def own_id():
        return JSONResponse({"ok": True}, headers={"X-Request-ID": "route-id"})

    r = TestClient(app).get("/own-id")
    assert_returned(r, json_body={"ok": True})
    assert r.headers.get_list("x-request-id") == [ID1]


def test_mw_rc_05__started_record_fields_and_order(id1, logs):
    """MW-RC-05 — the started record carries every extra and is logged before the handler runs.
    Rules: RC R4, R6, R7."""
    logs.set_level(logging.INFO, logger="tests.handler")
    handler_log = logging.getLogger("tests.handler")
    app = rc_app()

    @app.get("/items/{id}")
    async def item(id: int):
        handler_log.info("in handler")
        return {"ok": True}

    r = TestClient(app).get(
        "/items/7?a=1&b=2",
        headers={"User-Agent": "pytest-agent/1.0", "X-Workspace-ID": "42"},
    )
    assert_returned(r, json_body={"ok": True})
    rec = one_started(logs)
    assert rec.levelno == logging.INFO
    assert rec.request_id == ID1
    assert rec.method == "GET"
    assert rec.path == "/items/7"
    assert rec.query_params == "a=1&b=2"
    assert rec.client_ip == "testclient"
    assert rec.user_agent == "pytest-agent/1.0"
    assert rec.workspace_id == "42"
    in_handler = [r for r in logs.records if r.name == "tests.handler" and r.getMessage() == "in handler"]
    assert logs.records.index(rec) < logs.records.index(in_handler[0])


def test_mw_rc_06__post_query_order_kept(logs):
    """MW-RC-06 — method, path and query order as sent.
    Rules: RC R4."""
    app = rc_app()
    add_plain(app, "/items", "POST")
    r = TestClient(app).post("/items?b=2&a=1")
    assert_returned(r, json_body={"ok": True})
    rec = one_started(logs)
    assert rec.method == "POST"
    assert rec.path == "/items"
    assert rec.query_params == "b=2&a=1"


def test_mw_rc_07__non_sensitive_names_not_redacted(logs):
    """MW-RC-07 — look-alike but non-sensitive names keep their values.
    Rules: RC R4, R4a (not-redacted list)."""
    app = rc_app()
    add_plain(app, "/search")
    r = TestClient(app).get("/search?keyword=k&tokens=t&barcode=b&monkey=m&q=s&page=2")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params == "keyword=k&tokens=t&barcode=b&monkey=m&q=s&page=2"


@pytest.mark.xfail(strict=True, reason=BUG_480)
def test_mw_rc_08__token_redacted(logs):
    """MW-RC-08 — `token` value is logged as ***.
    Rules: RC R4a [BUG-480]."""
    app = rc_app()
    add_plain(app, "/search")
    r = TestClient(app).get("/search?a=1&token=abc&b=2")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params == "a=1&token=***&b=2"


@pytest.mark.xfail(strict=True, reason=BUG_480)
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(n, id=f"MW-RC-09-{n}")
        for n in [
            "token", "TOKEN", "access_token", "accessToken", "api-key", "apiKey",
            "client_secret", "password", "signature", "code", "zip_code", "key",
            "secret", "user.password",
        ]
    ],
)
def test_mw_rc_09__sensitive_names_redacted(logs, name):
    """MW-RC-09 — every sensitive name variant is redacted, name kept as sent.
    Rules: RC R4a [BUG-480]."""
    app = rc_app()
    add_plain(app, "/search")
    r = TestClient(app).get(f"/search?{name}=v1&page=2")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params == f"{name}=***&page=2"


@pytest.mark.xfail(strict=True, reason=BUG_480)
@pytest.mark.parametrize(
    "query, expected",
    [
        pytest.param("token=&a=1", "token=***&a=1", id="MW-RC-10-a-empty"),
        pytest.param("token=x&token=y", "token=***&token=***", id="MW-RC-10-b-repeated"),
    ],
)
def test_mw_rc_10__empty_and_repeated_redacted(logs, query, expected):
    """MW-RC-10 — empty and repeated sensitive values are each redacted.
    Rules: RC R4a [BUG-480], R5."""
    app = rc_app()
    add_plain(app, "/search")
    r = TestClient(app).get(f"/search?{query}")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params == expected


def test_mw_rc_11__app_sees_real_token(logs):
    """MW-RC-11 — redaction affects only the log; the route sees the real value.
    Rules: RC R4a, R11."""
    app = rc_app()

    @app.get("/echo-token")
    async def echo_token(request: Request):
        return {"token": request.query_params["token"]}

    r = TestClient(app).get("/echo-token?token=abc")
    assert r.status_code == 200
    assert r.json() == {"token": "abc"}


@pytest.mark.parametrize(
    "url",
    [pytest.param("/items", id="MW-RC-12-a-none"), pytest.param("/items?", id="MW-RC-12-b-bare-q")],
)
def test_mw_rc_12__no_query_is_none(logs, url):
    """MW-RC-12 — no query parameters -> query_params is None.
    Rules: RC R5."""
    app = rc_app()
    add_plain(app, "/items")
    r = TestClient(app).get(url)
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params is None


def test_mw_rc_13__empty_value_counts(logs):
    """MW-RC-13 — `?a=` logs "a=".
    Rules: RC R5."""
    app = rc_app()
    add_plain(app, "/items")
    r = TestClient(app).get("/items?a=")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).query_params == "a="


def test_mw_rc_14__client_ip_from_testclient(logs):
    """MW-RC-14 — client_ip is the TestClient host.
    Rules: RC R6."""
    app = rc_app()
    add_plain(app, "/items")
    r = TestClient(app).get("/items")
    assert_returned(r, json_body={"ok": True})
    assert one_started(logs).client_ip == "testclient"


@pytest.mark.parametrize(
    "client",
    [pytest.param(_MISSING, id="MW-RC-15-a-no-key"), pytest.param(None, id="MW-RC-15-b-none")],
)
def test_mw_rc_15__no_client_address(id1, logs, client):
    """MW-RC-15 — no client address -> client_ip None; response still gets X-Request-ID.
    Rules: RC R6, R3."""
    request = make_request(client=client)
    resp, call_next = ok_call_next()
    result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.headers["X-Request-ID"] == ID1
    assert one_started(logs).client_ip is None


def test_mw_rc_16__absent_headers_are_none(logs):
    """MW-RC-16 — no User-Agent / X-Workspace-ID -> None.
    Rules: RC R7."""
    request = make_request(headers=[], client=("1.2.3.4", 5000))
    resp, call_next = ok_call_next()
    result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.status_code == 200
    rec = one_started(logs)
    assert rec.user_agent is None
    assert rec.workspace_id is None
    assert rec.client_ip == "1.2.3.4"


def test_mw_rc_17__header_names_case_insensitive(logs):
    """MW-RC-17 — upper-case header names are read; workspace id not validated.
    Rules: RC R7."""
    app = rc_app()
    add_plain(app, "/items")
    r = TestClient(app).get("/items", headers={"USER-AGENT": "Agent/2", "X-WORKSPACE-ID": "not-a-number"})
    rec = one_started(logs)
    assert rec.user_agent == "Agent/2"
    assert rec.workspace_id == "not-a-number"
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.parametrize(
    "code", [pytest.param(c, id=f"MW-RC-18-{c}") for c in (200, 302, 399)]
)
def test_mw_rc_18__below_400_logged_info(id1, logs, code):
    """MW-RC-18 — status < 400 -> one INFO completed record with status, id and a float duration.
    Rules: RC R8, R9."""
    app = rc_app()
    add_status_route(app)
    r = TestClient(app, follow_redirects=False).get(f"/status/{code}")
    assert r.status_code == code
    rec = one_completed(logs)
    assert rec.levelno == logging.INFO
    assert rec.status_code == code
    assert rec.request_id == ID1
    assert isinstance(rec.duration_ms, float)
    assert rec.duration_ms >= 0


@pytest.mark.parametrize(
    "code", [pytest.param(c, id=f"MW-RC-19-{c}") for c in (400, 404, 422, 499)]
)
def test_mw_rc_19__4xx_logged_at_least_warning(id1, logs, code):
    """MW-RC-19 — 4xx -> one completed record at >= WARNING.
    Rules: RC R8, R8a."""
    app = rc_app()
    add_status_route(app)
    r = TestClient(app).get(f"/status/{code}")
    assert r.status_code == code
    rec = one_completed(logs)
    assert rec.status_code == code
    assert rec.request_id == ID1
    assert rec.levelno >= logging.WARNING


@pytest.mark.xfail(strict=True, reason=BUG_481)
@pytest.mark.parametrize(
    "code", [pytest.param(c, id=f"MW-RC-20-{c}") for c in (400, 404, 422, 499)]
)
def test_mw_rc_20__4xx_logged_warning(logs, code):
    """MW-RC-20 — 4xx completed record is exactly WARNING.
    Rules: RC R8a [BUG-481]."""
    app = rc_app()
    add_status_route(app)
    r = TestClient(app).get(f"/status/{code}")
    assert_returned(r, code)
    assert one_completed(logs).levelno == logging.WARNING


@pytest.mark.parametrize(
    "code", [pytest.param(c, id=f"MW-RC-21-{c}") for c in (500, 503)]
)
def test_mw_rc_21__5xx_logged_error(logs, code):
    """MW-RC-21 — 5xx returned as a response -> ERROR.
    Rules: RC R8b."""
    app = rc_app()
    add_status_route(app)
    r = TestClient(app).get(f"/status/{code}")
    assert r.status_code == code
    rec = one_completed(logs)
    assert rec.levelno == logging.ERROR
    assert rec.status_code == code


def test_mw_rc_22__duration_rounded_ms(logs):
    """MW-RC-22 — duration 0.123456 s -> 123.46 ms.
    Rules: RC R9."""
    request = make_request()
    resp, call_next = ok_call_next()
    with T(100.0, 100.123456):
        result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.status_code == 200
    assert one_completed(logs).duration_ms == 123.46


def test_mw_rc_23__duration_in_milliseconds(logs):
    """MW-RC-23 — 1.5 s -> 1500.0 ms (milliseconds, not seconds).
    Rules: RC R9."""
    request = make_request()
    resp, call_next = ok_call_next()
    with T(200.0, 201.5):
        result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.status_code == 200
    assert one_completed(logs).duration_ms == 1500.0


def test_mw_rc_24__exception_propagates_unchanged(id1, logs):
    """MW-RC-24 — the app's exception propagates unchanged; started logged and state set.
    Rules: RC R10; Errors row."""
    request = make_request()
    with pytest.raises(ValueError) as exc:
        asyncio.run(rc_dispatch(request, raising_call_next(BOOM)))
    assert exc.value is BOOM
    assert str(exc.value) == "boom"
    assert one_started(logs).request_id == ID1
    assert request.state.request_id == ID1


@pytest.mark.xfail(strict=True, reason=BUG_482)
def test_mw_rc_25__crash_logs_completed_500(id1, logs):
    """MW-RC-25 — a crash still logs one ERROR completed record with 500 and duration.
    Rules: RC R10a [BUG-482], R9."""
    request = make_request()
    with pytest.raises(ValueError) as exc:
        with T(100.0, 100.123456):
            asyncio.run(rc_dispatch(request, raising_call_next(BOOM)))
    assert exc.value is BOOM
    rec = one_completed(logs)
    assert rec.levelno == logging.ERROR
    assert rec.status_code == 500
    assert rec.request_id == ID1
    assert rec.duration_ms == 123.46


def test_mw_rc_26__body_status_headers_pass_through(logs):
    """MW-RC-26 — status, body and route headers pass through; X-Request-ID added.
    Rules: RC R11."""
    app = rc_app()

    @app.get("/created")
    async def created():
        return JSONResponse({"x": 1}, status_code=201, headers={"X-Custom": "yes"})

    r = TestClient(app).get("/created")
    assert r.status_code == 201
    assert r.json() == {"x": 1}
    assert r.headers["X-Custom"] == "yes"
    assert "x-request-id" in r.headers


@pytest.mark.parametrize(
    "raw, expected",
    [
        pytest.param(b"q=a%20b", "q=a+b", id="MW-RC-27-a-pct20"),
        pytest.param(b"q=a+b", "q=a+b", id="MW-RC-27-b-plus"),
        pytest.param(b"q=a/b", "q=a%2Fb", id="MW-RC-27-c-slash"),
        pytest.param(b"q=a%26b", "q=a%26b", id="MW-RC-27-d-amp"),
        pytest.param(b"q=%C3%A9", "q=%C3%A9", id="MW-RC-27-e-utf8"),
        pytest.param(b"q=%c3%a9", "q=%C3%A9", id="MW-RC-27-f-lower-hex"),
        pytest.param(b"a=1&a=2", "a=1&a=2", id="MW-RC-27-g-repeated"),
        pytest.param(b"q=a~b.c_d-e", "q=a~b.c_d-e", id="MW-RC-27-h-unreserved"),
        pytest.param(b"q=a*b", "q=a%2Ab", id="MW-RC-27-i-star"),
        pytest.param(b"a%2Fb=1", "a%2Fb=1", id="MW-RC-27-j-name"),
    ],
)
def test_mw_rc_27__query_reencoded_form_style(logs, raw, expected):
    """MW-RC-27 — query_params is re-encoded form-style from the decoded parameters.
    Rules: RC R4b, R4."""
    request = make_request(query_string=raw)
    resp, call_next = ok_call_next()
    result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.status_code == 200
    assert one_started(logs).query_params == expected


@pytest.mark.xfail(strict=True, reason=BUG_480)
def test_mw_rc_28__redaction_marker_literal(logs):
    """MW-RC-28 — the *** marker is literal; non-sensitive `*` still percent-encoded.
    Rules: RC R4a [BUG-480], R4b."""
    request = make_request(query_string=b"token=a%20b%2A&q=a*b")
    resp, call_next = ok_call_next()
    result = asyncio.run(rc_dispatch(request, call_next))
    assert result is resp
    assert result.status_code == 200
    assert one_started(logs).query_params == "token=***&q=a%2Ab"


# --------------------------------------------------------------------------- #
# SecurityHeadersMiddleware.dispatch
# --------------------------------------------------------------------------- #


def test_mw_sh_01__json_gets_headers_no_csp():
    """MW-SH-01 — JSON response: three headers exact, X-XSS-Protection present, no CSP, body unchanged.
    Rules: SH R3, R4, R7."""
    app = sh_app()

    @app.get("/api/v1/items")
    async def items():
        return {"id": 1}

    r = TestClient(app).get("/api/v1/items")
    assert r.status_code == 200
    assert r.json() == {"id": 1}
    assert_headers(r, THREE, exactly_one=True)
    assert "x-xss-protection" in r.headers
    assert_no_csp(r)


@pytest.mark.parametrize(
    "code, base_url",
    [
        pytest.param(302, "http://testserver", id="MW-SH-02-a-302"),
        pytest.param(404, "http://testserver", id="MW-SH-02-b-404"),
        pytest.param(500, "http://testserver", id="MW-SH-02-c-500"),
        pytest.param(200, "https://testserver", id="MW-SH-02-d-200-https"),
    ],
)
def test_mw_sh_02__headers_on_any_status_and_scheme(code, base_url):
    """MW-SH-02 — headers on 3xx/4xx/5xx responses and over HTTPS.
    Rules: SH R3."""
    app = sh_app()
    add_status_route(app, "/api/v1")
    r = TestClient(app, base_url=base_url, follow_redirects=False).get(f"/api/v1/status/{code}")
    assert r.status_code == code
    assert_headers(r, THREE)


@pytest.mark.xfail(strict=True, reason=BUG_486)
def test_mw_sh_03__xxss_is_zero():
    """MW-SH-03 — X-XSS-Protection is "0".
    Rules: SH R3a [BUG-486]."""
    app = sh_app()
    add_plain(app, "/api/v1/items")
    r = TestClient(app).get("/api/v1/items")
    assert_returned(r, json_body={"ok": True})
    assert r.headers.get_list("x-xss-protection") == ["0"]


def test_mw_sh_04__html_gets_csp():
    """MW-SH-04 — HTML response gets CSP default-src 'self' plus the three headers.
    Rules: SH R4, R7."""
    app = sh_app()
    html_route(app, "/api/v1/page", "<p>hi</p>")
    r = TestClient(app).get("/api/v1/page")
    assert r.status_code == 200
    assert r.text == "<p>hi</p>"
    assert r.headers.get_list("content-security-policy") == ["default-src 'self'"]
    assert_headers(r, THREE)


def _sh05_json():
    return JSONResponse({})


def _sh05_plain():
    return PlainTextResponse("x")


def _sh05_bare():
    return Response(b"x")


def _sh05_upper():
    return Response(b"<p>x</p>", headers={"Content-Type": "TEXT/HTML"})


@pytest.mark.parametrize(
    "make_resp, body",
    [
        pytest.param(_sh05_json, b"{}", id="MW-SH-05-a-json"),
        pytest.param(_sh05_plain, b"x", id="MW-SH-05-b-plain"),
        pytest.param(_sh05_bare, b"x", id="MW-SH-05-c-no-content-type"),
        pytest.param(_sh05_upper, b"<p>x</p>", id="MW-SH-05-d-upper-html"),
    ],
)
def test_mw_sh_05__non_html_no_csp(make_resp, body):
    """MW-SH-05 — non-HTML (incl. no Content-Type and upper-case TEXT/HTML) gets no CSP.
    Rules: SH R4."""
    app = sh_app()

    @app.get("/api/v1/other/{kind}")
    async def other(kind: str):
        return make_resp()

    r = TestClient(app).get("/api/v1/other/x")
    assert_returned(r, content=body)
    assert_no_csp(r)
    assert_headers(r, THREE)


DOCS_PATHS = [
    "/api/v1/docs",
    "/api/v1/docs/oauth2-redirect",
    "/api/v1/docs/a/b",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
]


@pytest.mark.parametrize("path", [pytest.param(p, id=f"MW-SH-06-{p}") for p in DOCS_PATHS])
def test_mw_sh_06__docs_paths_no_csp(path):
    """MW-SH-06 — docs paths get no CSP even for HTML.
    Rules: SH R1, R2."""
    app = sh_app()
    html_route(app, path)
    r = TestClient(app).get(path)
    assert_returned(r, text="<p>d</p>")
    assert_no_csp(r)


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=f"MW-SH-07-{p}")
        for p in ["/api/v1/doc", "/api/v2/docs", "/docs", "/API/v1/docs", "/api/v1/items"]
    ],
)
def test_mw_sh_07__non_docs_paths_get_csp(path):
    """MW-SH-07 — near-miss paths are not docs paths: CSP and headers added.
    Rules: SH R1."""
    app = sh_app()
    html_route(app, path)
    r = TestClient(app).get(path)
    assert_returned(r, text="<p>d</p>")
    assert r.headers.get("content-security-policy") == "default-src 'self'"
    assert_headers(r, THREE)


@pytest.mark.xfail(strict=True, reason=BUG_485)
@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=f"MW-SH-08-{p}")
        for p in [
            "/api/v1/docsets", "/api/v1/docs-export", "/api/v1/redocuments",
            "/api/v1/redoc/x", "/api/v1/openapi.json.bak", "/api/v1/openapi.jsonx",
        ]
    ],
)
def test_mw_sh_08__lookalike_paths_not_docs(path):
    """MW-SH-08 — look-alike paths are not docs paths.
    Rules: SH R1a [BUG-485]."""
    app = sh_app()
    html_route(app, path)
    r = TestClient(app).get(path)
    assert_returned(r, text="<p>d</p>")
    assert r.headers.get("content-security-policy") == "default-src 'self'"
    assert r.headers.get("x-frame-options") == "DENY"
    assert_headers(r, (XCTO, HSTS))


@pytest.mark.xfail(strict=True, reason=BUG_485)
@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=f"MW-SH-09-{p}")
        for p in ["/api/v2/docs", "/api/v2/redoc", "/api/v2/openapi.json"]
    ],
)
def test_mw_sh_09__configured_prefix_docs(monkeypatch, path):
    """MW-SH-09 — with API_V1_STR=/api/v2, /api/v2 docs paths are docs paths (no CSP).
    Rules: SH R1b [BUG-485], R2."""
    monkeypatch.setattr(core_config.settings, "API_V1_STR", "/api/v2")
    app = sh_app()
    html_route(app, path)
    r = TestClient(app).get(path)
    assert_returned(r, text="<p>d</p>")
    assert_no_csp(r)


@pytest.mark.xfail(strict=True, reason=BUG_485)
def test_mw_sh_10__literal_v1_not_docs_when_prefix_changed(monkeypatch):
    """MW-SH-10 — with API_V1_STR=/api/v2, /api/v1/docs is not a docs path.
    Rules: SH R1b [BUG-485]."""
    monkeypatch.setattr(core_config.settings, "API_V1_STR", "/api/v2")
    app = sh_app()
    html_route(app, "/api/v1/docs")
    r = TestClient(app).get("/api/v1/docs")
    assert_returned(r, text="<p>d</p>")
    assert r.headers.get("content-security-policy") == "default-src 'self'"


def test_mw_sh_11__docs_route_csp_kept():
    """MW-SH-11 — a docs route's own CSP stays as is.
    Rules: SH R2."""
    app = sh_app()
    html_route(app, "/api/v1/docs", headers={"Content-Security-Policy": "script-src 'none'"})
    r = TestClient(app).get("/api/v1/docs")
    assert_returned(r, text="<p>d</p>")
    assert r.headers.get_list("content-security-policy") == ["script-src 'none'"]


@pytest.mark.xfail(strict=True, reason=f"{BUG_484}; {BUG_486}")
@pytest.mark.parametrize(
    "path",
    [
        pytest.param(p, id=f"MW-SH-12-{p}")
        for p in ["/api/v1/docs", "/api/v1/docs/oauth2-redirect", "/api/v1/redoc", "/api/v1/openapi.json"]
    ],
)
def test_mw_sh_12__docs_get_non_csp_headers(path):
    """MW-SH-12 — docs paths still get XCTO, XFO, XXSS=0, HSTS (one value each), no CSP.
    Rules: SH R2a [BUG-484], R3a."""
    app = sh_app()
    html_route(app, path)
    r = TestClient(app).get(path)
    assert_returned(r, text="<p>d</p>")
    assert_headers(r, (XCTO, XFO, XXSS, HSTS), exactly_one=True)
    assert_no_csp(r)


@pytest.mark.xfail(strict=True, reason=f"{BUG_484}; {BUG_487}")
def test_mw_sh_13__docs_route_xfo_kept_others_added():
    """MW-SH-13 — docs route's XFO kept; the other defaults added; no CSP.
    Rules: SH R2a [BUG-484], R5a [BUG-487]."""
    app = sh_app()
    html_route(app, "/api/v1/docs", headers={"X-Frame-Options": "SAMEORIGIN"})
    r = TestClient(app).get("/api/v1/docs")
    assert_returned(r, text="<p>d</p>")
    assert r.headers.get_list("x-frame-options") == ["SAMEORIGIN"]
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("strict-transport-security") == HSTS[1]
    assert r.headers.get("x-xss-protection") == "0"
    assert_no_csp(r)


def test_mw_sh_14__other_route_headers_untouched():
    """MW-SH-14 — non-security headers and a non-HTML route CSP are untouched.
    Rules: SH R5."""
    app = sh_app()

    @app.get("/api/v1/items")
    async def items():
        return JSONResponse(
            {},
            headers={
                "X-Custom": "keep",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'",
            },
        )

    r = TestClient(app).get("/api/v1/items")
    assert_returned(r, json_body={})
    assert r.headers["X-Custom"] == "keep"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers.get_list("content-security-policy") == ["default-src 'none'"]
    assert_headers(r, THREE)


def test_mw_sh_15__route_xfo_single_value_others_default():
    """MW-SH-15 — a route XFO ends as one value; unset headers get defaults.
    Rules: SH R5a (untouched part), R3."""
    app = sh_app()

    @app.get("/api/v1/items")
    async def items():
        return JSONResponse({}, headers={"X-Frame-Options": "SAMEORIGIN"})

    r = TestClient(app).get("/api/v1/items")
    assert_returned(r, json_body={})
    assert len(r.headers.get_list("x-frame-options")) == 1
    assert_headers(r, (XCTO, HSTS))
    assert "x-xss-protection" in r.headers


@pytest.mark.xfail(strict=True, reason=BUG_487)
@pytest.mark.parametrize(
    "name, value",
    [
        pytest.param("X-Frame-Options", "SAMEORIGIN", id="MW-SH-16-a-xfo"),
        pytest.param("X-XSS-Protection", "1", id="MW-SH-16-b-xxss"),
        pytest.param("Strict-Transport-Security", "max-age=60", id="MW-SH-16-c-hsts"),
        pytest.param("x-content-type-options", "route-value", id="MW-SH-16-d-xcto-lower"),
    ],
)
def test_mw_sh_16__route_security_header_kept(name, value):
    """MW-SH-16 — a route's security header is kept (not duplicated); others default.
    Rules: SH R5a [BUG-487]."""
    app = sh_app()

    @app.get("/api/v1/items")
    async def items():
        return JSONResponse({}, headers={name: value})

    r = TestClient(app).get("/api/v1/items")
    assert_returned(r, json_body={})
    assert r.headers.get_list(name) == [value]
    others = [h for h in (XCTO, XFO, HSTS, XXSS) if h[0].lower() != name.lower()]
    assert_headers(r, others)


@pytest.mark.xfail(strict=True, reason=BUG_487)
def test_mw_sh_17__route_html_csp_kept():
    """MW-SH-17 — an HTML route's own CSP is kept.
    Rules: SH R5a [BUG-487], R4."""
    app = sh_app()
    csp = "default-src 'self'; style-src 'unsafe-inline'"
    html_route(app, "/api/v1/page", "<p>x</p>", headers={"Content-Security-Policy": csp})
    r = TestClient(app).get("/api/v1/page")
    assert_returned(r, text="<p>x</p>")
    assert r.headers.get_list("content-security-policy") == [csp]


def _crash_stack_app() -> FastAPI:
    # RC outer, SH inner: the last added middleware is the outermost.
    return make_app(SecurityHeadersMiddleware, RequestContextMiddleware)


@pytest.mark.xfail(strict=True, reason=BUG_483)
def test_mw_sh_18__crash_becomes_500_with_headers(id1, logs):
    """MW-SH-18 — with RC outside, a crash becomes the standard 500 with headers, RC's id and one log.
    Rules: SH R6 [BUG-483], R6a, R6b; Errors row."""
    app = _crash_stack_app()

    @app.get("/api/v1/items/{id}")
    async def crash(id: int):
        raise BOOM_RT

    r = TestClient(app, raise_server_exceptions=True).get(
        "/api/v1/items/5", headers={"User-Agent": "agent/9"}
    )
    assert r.status_code == 500
    assert_headers(r, (XCTO, XFO, XXSS, HSTS))
    assert_no_csp(r)
    body = r.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    assert body["detail"] == GENERIC_DETAIL
    assert body["instance"] == "/api/v1/items/5"
    assert body["request_id"] == ID1
    assert r.headers.get_list("x-request-id") == [ID1]
    recs = unexpected(logs)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.ERROR
    assert rec.exc_info[1] is BOOM_RT
    assert rec.request_id == ID1
    assert rec.error_type == "RuntimeError"
    assert rec.error == "boom"
    assert rec.path == "/api/v1/items/5"
    assert rec.method == "GET"
    assert rec.user_agent == "agent/9"
    assert rec.ip_address == "testclient"


@pytest.mark.xfail(strict=True, reason=BUG_483)
def test_mw_sh_19__docs_crash_500_headers_no_csp(logs):
    """MW-SH-19 — a crashing docs route yields a 500 with the four headers and no CSP.
    Rules: SH R6 [BUG-483], R2, R2a."""
    app = _crash_stack_app()

    @app.get("/api/v1/docs")
    async def crash():
        raise RuntimeError("boom")

    r = TestClient(app, raise_server_exceptions=True).get("/api/v1/docs")
    assert r.status_code == 500
    assert_headers(r, (XCTO, XFO, XXSS, HSTS))
    assert_no_csp(r)


def test_mw_sh_20__body_and_status_pass_through():
    """MW-SH-20 — body and status pass through unchanged.
    Rules: SH R7."""
    app = sh_app()

    @app.get("/api/v1/made")
    async def made():
        return JSONResponse({"id": 5}, status_code=201)

    html_route(app, "/api/v1/gone", "<p>gone</p>", status_code=410)
    client = TestClient(app)
    r1 = client.get("/api/v1/made")
    assert r1.status_code == 201
    assert r1.json() == {"id": 5}
    r2 = client.get("/api/v1/gone")
    assert r2.status_code == 410
    assert r2.text == "<p>gone</p>"


def test_mw_sh_21__csp_when_text_html_contained():
    """MW-SH-21 — `text/html` anywhere in Content-Type triggers CSP.
    Rules: SH R4."""
    app = sh_app()

    @app.get("/api/v1/fragment")
    async def fragment():
        return Response(b"<p>x</p>", headers={"Content-Type": "application/vnd.x+text/html"})

    r = TestClient(app).get("/api/v1/fragment")
    assert_returned(r, content=b"<p>x</p>")
    assert r.headers.get_list("content-security-policy") == ["default-src 'self'"]


@pytest.mark.xfail(strict=True, reason=BUG_483)
def test_mw_sh_22__crash_without_rc_fresh_ids(logs):
    """MW-SH-22 — SH alone: each crash gets a fresh id, same in body, header and log.
    Rules: SH R6 [BUG-483], R6b."""
    app = sh_app()

    @app.get("/api/v1/items/{id}")
    async def crash(id: int):
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=True)
    responses = [client.get("/api/v1/items/5"), client.get("/api/v1/items/6")]
    recs = unexpected(logs)
    assert len(recs) == 2
    ids = []
    for r, rec in zip(responses, recs):
        assert r.status_code == 500
        assert_headers(r, (XCTO, XFO, XXSS, HSTS))
        rid = r.json()["request_id"]
        assert ID_RE.match(rid)
        assert r.headers["X-Request-ID"] == rid
        assert rec.request_id == rid
        ids.append(rid)
    assert ids[0] != ids[1]


@pytest.mark.xfail(strict=True, reason=BUG_483)
def test_mw_sh_23__direct_crash_no_client_no_headers(logs):
    """MW-SH-23 — direct SH dispatch: crash -> 500 with headers; log has user_agent/ip None.
    Rules: SH R6 [BUG-483], R6a, R6b."""
    request = make_request(path="/api/v1/items/9", raw_path=b"/api/v1/items/9", headers=[], client=_MISSING)
    r = asyncio.run(sh_dispatch(request, raising_call_next(BOOM_KE)))
    assert r.status_code == 500
    assert_headers(r, (XCTO, XFO, XXSS, HSTS))
    assert_no_csp(r)
    body = json.loads(r.body)
    assert body["instance"] == "/api/v1/items/9"
    assert ID_RE.match(body["request_id"])
    assert r.headers["X-Request-ID"] == body["request_id"]
    recs = unexpected(logs)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.levelno == logging.ERROR
    assert rec.exc_info[1] is BOOM_KE
    assert rec.error_type == "KeyError"
    assert rec.error == "'k'"
    assert rec.method == "GET"
    assert rec.path == "/api/v1/items/9"
    assert rec.user_agent is None
    assert rec.ip_address is None
    assert rec.request_id == body["request_id"]
