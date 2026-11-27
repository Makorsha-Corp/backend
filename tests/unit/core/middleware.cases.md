# Test cases — `app/core/middleware.py`

> **Spec:** `tests/unit/core/middleware.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec unchanged (re-run). Design fixes: minimal apps disable FastAPI's built-in `/docs`/`/redoc`/`/openapi.json` routes so they cannot shadow test routes; exact-duration assertions moved to direct dispatch (MW-RC-18/22/23) because `TestClient`'s cookie handling also calls `time.time`; new MW-SH-21 checks the "contains `text/html`" rule (not "starts with"/"equals"); each spec gap now states how the cases handle it (best-practice default, delegated by reviewer).
> **Revision:** 3 — spec Gap log G1–G3 closed: new RC R4b (form-style re-encoding of `query_params`, literal `***`) → MW-RC-27, MW-RC-28; new SH R6a ("Unexpected error" record: logger, level, message, `exc_info`, extras) → MW-SH-18 tightened, MW-SH-23; new SH R6b (request id with/without RC) → MW-SH-18 tightened, MW-SH-22. No verify report exists for this module.
> **Revision:** 4 — spec unchanged (re-run, no verify report). Return-value self-check tightened: new convention "Return value" makes every `TestClient` case assert the route's status code (and, where the route returns a body, that body), so a middleware that swallows or replaces the response cannot pass (best-practice default, delegated by reviewer); MW-RC-16 now asserts the returned response. No case added or retired.
> **Counts:** 51 cases · 33 expected-to-pass · 18 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `RequestContextMiddleware.dispatch` 28 cases (6 bug: BUG-480 ×4, BUG-481, BUG-482) · `SecurityHeadersMiddleware.dispatch` 23 cases (12 bug: BUG-483 ×4, BUG-484 ×2, BUG-485 ×3, BUG-486, BUG-487 ×2).
- **No database:** both callables are pure; the Postgres session fixture is not used. Each test builds its own minimal `FastAPI()` app with small routes and calls it through `TestClient`; the no-client-address, no-header and "route raises" cases call `RequestContextMiddleware(app=None).dispatch(...)` directly, as the spec suggests.
- **Notable design choices:**
  - Docs-path detection (R1/R1a/R1b) is observed through the CSP header: every docs/look-alike route returns HTML, so "is a docs path" = "no CSP", "not a docs path" = "CSP `default-src 'self'`". That keeps the R1 cases passing today and after BUG-484 is fixed.
  - Crash-to-500 (SH R6/R6a/R6b) is tested three ways: RC outside SH (production order, id = RC's id, MW-SH-18/19), SH alone through `TestClient` (fresh id, MW-SH-22), and SH direct dispatch with no headers and no client address (`user_agent`/`ip_address` = `None`, MW-SH-23).
  - Query-string encoding (RC R4b) is tested by direct dispatch with the raw `query_string` bytes in the scope, so the HTTP client cannot re-encode the URL before it reaches the middleware (best-practice default, delegated by reviewer).
  - `time.time` is patched as "first call → start, every later call → end" rather than an exact 2-item list, because patching `app.core.middleware.time.time` patches the global `time` module and the logging module may also call it. Exact durations are asserted only in direct-dispatch cases (MW-RC-22/23/25): through `TestClient`, the cookie jar calls `time.time` before the request reaches the middleware and would consume the "start" value (best-practice default, delegated by reviewer).
  - BUG-487 xfail uses a synthetic route value `X-Content-Type-Options: route-value` (the only real value is `nosniff`, which would not distinguish keep from overwrite).
  - Every case checks the returned response (status, and body where the route has one) through a shared "Return value" convention rather than repeating it in each row (best-practice default, delegated by reviewer).
  - The mock payment-gateway page (Q8) is left as is, per reviewer; listed under Deferred as a TODO (remove, or upgrade/limit to non-prod) so it is not lost.
- **Needs a decision:** None. The three previous spec gaps are closed by the spec (G1–G3).

## Conventions for this module

**Abbreviations:** `MW` = `app/core/middleware.py`; `RC` = `RequestContextMiddleware.dispatch`; `SH` = `SecurityHeadersMiddleware.dispatch`.

**App under test:** a fresh `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` per test (FastAPI's own `/docs`, `/redoc`, `/openapi.json` routes are disabled so they cannot shadow the test's routes, e.g. `/docs` in MW-SH-07), with only the middleware under test added via `app.add_middleware(...)` (SH-18/SH-19 add both — see there). Routes are defined per case as described in Given. `TestClient(app)` with default `base_url` `http://testserver`, `follow_redirects=False` whenever a 3xx is returned.

**Direct dispatch:** `Request(scope)` built from a scope dict `{"type": "http", "method": "GET", "path": "/items", "raw_path": b"/items", "query_string": b"", "headers": [], "scheme": "http", "server": ("testserver", 80), "root_path": ""}` plus whatever the case adds/removes; `call_next` is an `async def` stub that either returns `Response(content=b"ok", status_code=200)` or raises. Called as `await RequestContextMiddleware(app=None).dispatch(request, call_next)` (RC cases) or `await SecurityHeadersMiddleware(app=None).dispatch(request, call_next)` (MW-SH-23; scope path `/api/v1/items/9`).

**Fixed request id:** `ID1` = patch `app.core.middleware.uuid.uuid4` to return `UUID("12345678-1234-5678-1234-567812345678")` → expected id `req_12345678123456781234567812345678`. Id regex `^req_[0-9a-f]{32}$`.

**Fixed time:** `T(start, end)` = patch `app.core.middleware.time.time` so the first call returns `start` and every later call returns `end`. Use `T` only with direct dispatch, and activate it immediately around the `await dispatch(...)` call (after building the request), so no other code consumes the first value.

**Logs:** `caplog` with level DEBUG for loggers `app.core.middleware` and `app.core.exceptions`. "unexpected record" = a record from logger `app.core.exceptions` with message exactly `"Unexpected error"`. "started record" = the record with message `"Request started"` from that logger; "completed record" = message `"Request completed"`. Extras are read as `LogRecord` attributes. Unless stated, "exactly one" started and completed record per request.

**Security header defaults:** `XCTO` = `X-Content-Type-Options: nosniff`; `XFO` = `X-Frame-Options: DENY`; `HSTS` = `Strict-Transport-Security: max-age=31536000; includeSubDomains`; `XXSS` = `X-XSS-Protection: 0` (intended, BUG-486); `CSP` = `Content-Security-Policy: default-src 'self'`. "The three headers" = XCTO, XFO, HSTS. Header value checks use `response.headers.get_list(name)` when the case says "exactly one value".

**Prefix setting:** default `settings.API_V1_STR` = `/api/v1`. R1b cases `monkeypatch.setattr(app.core.config.settings, "API_V1_STR", "/api/v2")` before building the app and middleware.

**Return value (every case):** every `TestClient` case asserts the response status equals the status the route returns (200 unless the Given says otherwise) and, where the route returns a JSON/HTML body, that the body is unchanged — in addition to the listed Then assertions, even where Then does not repeat it (best-practice default, delegated by reviewer). Every direct-dispatch case that does not raise asserts `result is` the response returned by `call_next` (RC) or the stated 500 response (SH-23).

**Externals mocked:** none. **Race simulations:** none.

**Parametrized cases:** a case listing "variants" is one test id implemented with `pytest.mark.parametrize` over those variants; every variant must satisfy every assertion.

## `RequestContextMiddleware.dispatch`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MW-RC-01 | R1, R2, R3 | happy | ID1 patched; RC app with route `GET /echo-id` returning JSON `{"request_id": request.state.request_id}` | GET `/echo-id` | status 200; body `request_id == "req_12345678123456781234567812345678"`; header `X-Request-ID` equals the same; started record and completed record both have `request_id` equal to the same | pass |
| MW-RC-02 | R1 | happy | no patch; same `/echo-id` app | GET `/echo-id` twice | both `X-Request-ID` values match `^req_[0-9a-f]{32}$`; the two values differ; each body `request_id` equals its own response header | pass |
| MW-RC-03 | R1 | boundary | ID1 patched; `/echo-id` app | GET `/echo-id` with request header `X-Request-ID: client-abc` | response header `X-Request-ID` == `req_12345678123456781234567812345678` (not `client-abc`); body `request_id` same; started record `request_id` same | pass |
| MW-RC-04 | R3 | boundary | ID1 patched; route `GET /own-id` returning `JSONResponse({"ok": True}, headers={"X-Request-ID": "route-id"})` | GET `/own-id` | `response.headers.get_list("x-request-id") == ["req_12345678123456781234567812345678"]` (route value replaced, not duplicated) | pass |
| MW-RC-05 | R4, R6, R7 | happy | ID1 patched; route `GET /items/{id}` that logs `"in handler"` on logger `tests.handler` at INFO then returns `{"ok": True}`; caplog also captures `tests.handler` | GET `/items/7?a=1&b=2` with headers `User-Agent: pytest-agent/1.0`, `X-Workspace-ID: 42` | exactly one started record; level INFO; `request_id` == ID1 id; `method == "GET"`; `path == "/items/7"`; `query_params == "a=1&b=2"`; `client_ip == "testclient"`; `user_agent == "pytest-agent/1.0"`; `workspace_id == "42"`; started record appears in `caplog.records` before the `"in handler"` record | pass |
| MW-RC-06 | R4 | boundary | route `POST /items` returning `{"ok": True}` | POST `/items?b=2&a=1` | started record `method == "POST"`, `path == "/items"`, `query_params == "b=2&a=1"` (order as sent, not sorted) | pass |
| MW-RC-07 | R4, R4a (not-redacted list) | boundary | route `GET /search` returning `{"ok": True}` | GET `/search?keyword=k&tokens=t&barcode=b&monkey=m&q=s&page=2` | started record `query_params == "keyword=k&tokens=t&barcode=b&monkey=m&q=s&page=2"` (non-sensitive names, values unchanged, order kept) | pass |
| MW-RC-08 | R4a [BUG-480] | bug | route `GET /search` | GET `/search?a=1&token=abc&b=2` | started record `query_params == "a=1&token=***&b=2"` | xfail BUG-480 — fails today on: `query_params` is `"a=1&token=abc&b=2"` |
| MW-RC-09 | R4a [BUG-480] | bug | route `GET /search`; variants `<name>` = `token`, `TOKEN`, `access_token`, `accessToken`, `api-key`, `apiKey`, `client_secret`, `password`, `signature`, `code`, `zip_code`, `key`, `secret`, `user.password` | GET `/search?<name>=v1&page=2` | started record `query_params == "<name>=***&page=2"` (name kept exactly as sent, value `***`) | xfail BUG-480 — fails today on: value `v1` logged verbatim |
| MW-RC-10 | R4a [BUG-480], R5 | bug | route `GET /search`; variants (a) `?token=&a=1` → `"token=***&a=1"`; (b) `?token=x&token=y` → `"token=***&token=***"` | GET `/search` with the variant query | started record `query_params` equals the variant's expected string | xfail BUG-480 — fails today on: (a) `"token=&a=1"`, (b) `"token=x&token=y"` |
| MW-RC-11 | R4a, R11 | side-effect | route `GET /echo-token` returning `{"token": request.query_params["token"]}` | GET `/echo-token?token=abc` | status 200; body `{"token": "abc"}` (the app still sees the real value; redaction affects only the log) | pass |
| MW-RC-12 | R5 | boundary | route `GET /items`; variants (a) `/items`, (b) `/items?` | GET the variant URL | started record `query_params is None` | pass |
| MW-RC-13 | R5 | boundary | route `GET /items` | GET `/items?a=` | started record `query_params == "a="` | pass |
| MW-RC-14 | R6 | happy | route `GET /items` | GET `/items` via TestClient | started record `client_ip == "testclient"` | pass |
| MW-RC-15 | R6, R3 | boundary | direct dispatch; ID1 patched; scope variants (a) no `"client"` key, (b) `"client": None`; `call_next` returns `Response(b"ok", 200)` | `await dispatch(request, call_next)` | returns that response with header `X-Request-ID == "req_12345678123456781234567812345678"`; started record `client_ip is None` | pass |
| MW-RC-16 | R7 | boundary | direct dispatch; scope `"headers": []`, `"client": ("1.2.3.4", 5000)`; `call_next` returns `Response(b"ok", 200)` | `await dispatch(request, call_next)` | returns that response (status 200); started record `user_agent is None`, `workspace_id is None`, `client_ip == "1.2.3.4"` | pass |
| MW-RC-17 | R7 | boundary | route `GET /items` | GET `/items` with headers `USER-AGENT: Agent/2` and `X-WORKSPACE-ID: not-a-number` | started record `user_agent == "Agent/2"`, `workspace_id == "not-a-number"`; status 200 (not validated) | pass |
| MW-RC-18 | R8, R9 | happy | ID1 patched; route `GET /status/{code}` returning `Response(status_code=code)` (302 adds `Location: /x`); variants code 200, 302, 399 | GET `/status/<code>` (`follow_redirects=False`) | response status == code; exactly one completed record; level INFO; `status_code == code`; `request_id` == ID1 id; `duration_ms` is a `float` and `>= 0` (exact value checked in MW-RC-22/23) | pass |
| MW-RC-19 | R8, R8a | boundary | ID1 patched; `/status/{code}` route; variants 400, 404, 422, 499 | GET `/status/<code>` | response status == code; exactly one completed record; `status_code == code`; `request_id` == ID1 id; `levelno >= logging.WARNING` (not INFO) | pass |
| MW-RC-20 | R8a [BUG-481] | bug | `/status/{code}` route; variants 400, 404, 422, 499 | GET `/status/<code>` | completed record `levelno == logging.WARNING` | xfail BUG-481 — fails today on: level is ERROR |
| MW-RC-21 | R8b | boundary | `/status/{code}` route; variants 500, 503 (returned as responses) | GET `/status/<code>` | response status == code; exactly one completed record; `levelno == logging.ERROR`; `status_code == code` | pass |
| MW-RC-22 | R9 | happy | direct dispatch; `call_next` returns `Response(b"ok", 200)`; `T(100.0, 100.123456)` | `await dispatch(request, call_next)` | returns that response (status 200); exactly one completed record with `duration_ms == 123.46` | pass |
| MW-RC-23 | R9 | boundary | direct dispatch; `call_next` returns `Response(b"ok", 200)`; `T(200.0, 201.5)` | `await dispatch(request, call_next)` | returns that response (status 200); completed record `duration_ms == 1500.0` (milliseconds, not seconds) | pass |
| MW-RC-24 | R10, Errors row | error | direct dispatch; ID1 patched; module-level `BOOM = ValueError("boom")`; `call_next` raises `BOOM` | `await dispatch(request, call_next)` inside `pytest.raises(ValueError)` | raised exception `is BOOM`, message `"boom"`; exactly one started record with `request_id` == ID1 id; `request.state.request_id == "req_12345678123456781234567812345678"` after the call | pass |
| MW-RC-25 | R10a [BUG-482], R9 | bug | as MW-RC-24 plus `T(100.0, 100.123456)` | `await dispatch(request, call_next)` inside `pytest.raises(ValueError)` | raised exception `is BOOM`; exactly one completed record: `levelno == logging.ERROR`, `status_code == 500`, `request_id` == ID1 id, `duration_ms == 123.46` | xfail BUG-482 — fails today on: no completed record exists |
| MW-RC-26 | R11 | side-effect | route `GET /created` returning `JSONResponse({"x": 1}, status_code=201, headers={"X-Custom": "yes"})` | GET `/created` | status 201; JSON body `{"x": 1}`; header `X-Custom == "yes"`; `X-Request-ID` present | pass |
| MW-RC-27 | R4b, R4 | boundary | direct dispatch; `call_next` returns `Response(b"ok", 200)`; scope `query_string` variants (raw bytes as sent → expected `query_params`): (a) `q=a%20b` → `"q=a+b"`; (b) `q=a+b` → `"q=a+b"`; (c) `q=a/b` → `"q=a%2Fb"`; (d) `q=a%26b` → `"q=a%26b"`; (e) `q=%C3%A9` → `"q=%C3%A9"`; (f) `q=%c3%a9` → `"q=%C3%A9"` (uppercase hex); (g) `a=1&a=2` → `"a=1&a=2"`; (h) `q=a~b.c_d-e` → `"q=a~b.c_d-e"` (unreserved kept); (i) `q=a*b` → `"q=a%2Ab"`; (j) `a%2Fb=1` → `"a%2Fb=1"` (names re-encoded too) | `await dispatch(request, call_next)` | returns that response (status 200); exactly one started record with `query_params` equal to the variant's expected string | pass |
| MW-RC-28 | R4a [BUG-480], R4b | bug | direct dispatch; `call_next` returns `Response(b"ok", 200)`; scope `query_string` `b"token=a%20b%2A&q=a*b"` | `await dispatch(request, call_next)` | started record `query_params == "token=***&q=a%2Ab"` (marker written literally as `***`, not `%2A%2A%2A`; the non-sensitive `*` is still percent-encoded) | xfail BUG-480 — fails today on: `query_params` is `"token=a+b%2A&q=a%2Ab"` |

## `SecurityHeadersMiddleware.dispatch`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MW-SH-01 | R3, R4, R7 | happy | SH app; route `GET /api/v1/items` returning `{"id": 1}` | GET `/api/v1/items` | status 200; body `{"id": 1}`; XCTO, XFO, HSTS with exact default values, each exactly one value; header `X-XSS-Protection` present; no `Content-Security-Policy` | pass |
| MW-SH-02 | R3 | boundary | SH app; route `GET /api/v1/status/{code}` returning `Response(status_code=code)` (302 with `Location: /x`); variants (a) 302, (b) 404, (c) 500, (d) 200 via `TestClient(app, base_url="https://testserver")` | GET the variant (`follow_redirects=False`) | response status as returned by route; XCTO, XFO, HSTS with exact default values | pass |
| MW-SH-03 | R3a [BUG-486] | bug | SH app; `GET /api/v1/items` JSON | GET `/api/v1/items` | `X-XSS-Protection == "0"` (exactly one value) | xfail BUG-486 — fails today on: value is `"1; mode=block"` |
| MW-SH-04 | R4, R7 | happy | SH app; route `GET /api/v1/page` returning `HTMLResponse("<p>hi</p>")` (Content-Type `text/html; charset=utf-8`) | GET `/api/v1/page` | status 200; body `"<p>hi</p>"`; `Content-Security-Policy == "default-src 'self'"` (exactly one value); XCTO, XFO, HSTS present with defaults | pass |
| MW-SH-05 | R4 | boundary | SH app; route `GET /api/v1/other/{kind}`; variants (a) `JSONResponse({})`, (b) `PlainTextResponse("x")`, (c) `Response(b"x")` with no media type (no Content-Type header), (d) `Response(b"<p>x</p>", headers={"Content-Type": "TEXT/HTML"})` | GET the variant | no `Content-Security-Policy` header; XCTO, XFO, HSTS present with defaults | pass |
| MW-SH-06 | R1, R2 | happy | SH app; each variant path serves `HTMLResponse("<p>d</p>")`; variants `/api/v1/docs`, `/api/v1/docs/oauth2-redirect`, `/api/v1/docs/a/b`, `/api/v1/redoc`, `/api/v1/openapi.json` | GET the variant path | status 200; no `Content-Security-Policy` header | pass |
| MW-SH-07 | R1 | boundary | SH app; each variant path serves `HTMLResponse("<p>d</p>")`; variants `/api/v1/doc`, `/api/v2/docs`, `/docs`, `/API/v1/docs`, `/api/v1/items` | GET the variant path | `Content-Security-Policy == "default-src 'self'"`; XCTO, XFO, HSTS present with defaults | pass |
| MW-SH-08 | R1a [BUG-485] | bug | SH app; HTML routes at `/api/v1/docsets`, `/api/v1/docs-export`, `/api/v1/redocuments`, `/api/v1/redoc/x`, `/api/v1/openapi.json.bak`, `/api/v1/openapi.jsonx` (variants) | GET the variant path | `Content-Security-Policy == "default-src 'self'"`; `X-Frame-Options == "DENY"`; XCTO, HSTS present with defaults | xfail BUG-485 — fails today on: no CSP (path treated as docs) |
| MW-SH-09 | R1b [BUG-485], R2 | bug | `settings.API_V1_STR` = `/api/v2` (set before app built); SH app; HTML routes at `/api/v2/docs`, `/api/v2/redoc`, `/api/v2/openapi.json` (variants) | GET the variant path | no `Content-Security-Policy` header | xfail BUG-485 — fails today on: CSP `default-src 'self'` present |
| MW-SH-10 | R1b [BUG-485] | bug | `settings.API_V1_STR` = `/api/v2`; SH app; HTML route at `/api/v1/docs` | GET `/api/v1/docs` | `Content-Security-Policy == "default-src 'self'"` | xfail BUG-485 — fails today on: no CSP (literal `/api/v1` still treated as docs) |
| MW-SH-11 | R2 | side-effect | SH app; route `GET /api/v1/docs` returning `HTMLResponse("<p>d</p>", headers={"Content-Security-Policy": "script-src 'none'"})` | GET `/api/v1/docs` | `get_list("content-security-policy") == ["script-src 'none'"]` | pass |
| MW-SH-12 | R2a [BUG-484], R3a | bug | SH app; HTML routes at `/api/v1/docs`, `/api/v1/docs/oauth2-redirect`, `/api/v1/redoc`, `/api/v1/openapi.json` (variants) | GET the variant path | XCTO `nosniff`, XFO `DENY`, `X-XSS-Protection == "0"`, HSTS default — each exactly one value; no `Content-Security-Policy` | xfail BUG-484 — fails today on: `X-Content-Type-Options` absent |
| MW-SH-13 | R2a [BUG-484], R5a [BUG-487] | bug | SH app; route `GET /api/v1/docs` returning `HTMLResponse("<p>d</p>", headers={"X-Frame-Options": "SAMEORIGIN"})` | GET `/api/v1/docs` | `get_list("x-frame-options") == ["SAMEORIGIN"]`; XCTO `nosniff`; HSTS default; `X-XSS-Protection == "0"`; no CSP | xfail BUG-484 — fails today on: `X-Content-Type-Options` absent |
| MW-SH-14 | R5 | side-effect | SH app; route `GET /api/v1/items` returning `JSONResponse({}, headers={"X-Custom": "keep", "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'"})` | GET `/api/v1/items` | `X-Custom == "keep"`; `Cache-Control == "no-store"`; `get_list("content-security-policy") == ["default-src 'none'"]`; XCTO, XFO, HSTS present | pass |
| MW-SH-15 | R5a (untouched part), R3 | side-effect | SH app; route `GET /api/v1/items` returning `JSONResponse({}, headers={"X-Frame-Options": "SAMEORIGIN"})` | GET `/api/v1/items` | `len(get_list("x-frame-options")) == 1`; XCTO `nosniff` and HSTS default (headers the route did not set get defaults); `X-XSS-Protection` present | pass |
| MW-SH-16 | R5a [BUG-487] | bug | SH app; route `GET /api/v1/items` returning JSON with one preset header; variants (a) `X-Frame-Options: SAMEORIGIN`, (b) `X-XSS-Protection: 1`, (c) `Strict-Transport-Security: max-age=60`, (d) `x-content-type-options: route-value` (lowercase name, synthetic value) | GET `/api/v1/items` | `get_list(<that header>) == [<route value>]` (kept, not duplicated); the other three R3/R3a headers carry their defaults (XXSS = `0` where not the preset one) | xfail BUG-487 — fails today on: route value overwritten by the default |
| MW-SH-17 | R5a [BUG-487], R4 | bug | SH app; route `GET /api/v1/page` returning `HTMLResponse("<p>x</p>", headers={"Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'"})` | GET `/api/v1/page` | `get_list("content-security-policy") == ["default-src 'self'; style-src 'unsafe-inline'"]` | xfail BUG-487 — fails today on: CSP replaced by `default-src 'self'` |
| MW-SH-18 | R6 [BUG-483], R6a, R6b, Errors row | bug | ID1 patched; module-level `BOOM_RT = RuntimeError("boom")`; app with `add_middleware(SecurityHeadersMiddleware)` then `add_middleware(RequestContextMiddleware)` (RC outer, SH inner); route `GET /api/v1/items/{id}` raises `BOOM_RT`; `TestClient(app, raise_server_exceptions=True)` | GET `/api/v1/items/5` with header `User-Agent: agent/9` | no exception reaches the test; status 500; XCTO `nosniff`, XFO `DENY`, `X-XSS-Protection == "0"`, HSTS default; no CSP; JSON body has `title == "Internal Server Error"`, `status == 500`, `detail == "An unexpected error occurred. Please contact support with the request ID."`, `instance == "/api/v1/items/5"`, `request_id == "req_12345678123456781234567812345678"`; `get_list("x-request-id") == [that id]`; exactly one unexpected record: `levelno == logging.ERROR`, `record.exc_info[1] is BOOM_RT`, `request_id` == that id, `error_type == "RuntimeError"`, `error == "boom"`, `path == "/api/v1/items/5"`, `method == "GET"`, `user_agent == "agent/9"`, `ip_address == "testclient"` | xfail BUG-483 — fails today on: `RuntimeError` propagates out of the client |
| MW-SH-19 | R6 [BUG-483], R2, R2a | bug | same stack as MW-SH-18; route `GET /api/v1/docs` raises `RuntimeError("boom")` | GET `/api/v1/docs` | no exception reaches the test; status 500; XCTO, XFO, `X-XSS-Protection == "0"`, HSTS present with defaults; no `Content-Security-Policy` | xfail BUG-483 — fails today on: `RuntimeError` propagates out of the client |
| MW-SH-20 | R7 | side-effect | SH app; routes `GET /api/v1/made` → `JSONResponse({"id": 5}, status_code=201)` and `GET /api/v1/gone` → `HTMLResponse("<p>gone</p>", status_code=410)` | GET each | `/made`: status 201, body `{"id": 5}`; `/gone`: status 410, body `"<p>gone</p>"` | pass |
| MW-SH-21 | R4 | boundary | SH app; route `GET /api/v1/fragment` returning `Response(b"<p>x</p>", headers={"Content-Type": "application/vnd.x+text/html"})` (`text/html` in the middle, not at the start) | GET `/api/v1/fragment` | status 200; `Content-Security-Policy == "default-src 'self'"` (exactly one value) — the rule is "contains", not "starts with" or "equals" | pass |
| MW-SH-22 | R6 [BUG-483], R6b | bug | SH app only (no RC); route `GET /api/v1/items/{id}` raises `RuntimeError("boom")`; `TestClient(app, raise_server_exceptions=True)` | GET `/api/v1/items/5`, then GET `/api/v1/items/6` | no exception reaches the test; both status 500 with XCTO, XFO, `X-XSS-Protection == "0"`, HSTS defaults; for each response: body `request_id` matches `^req_[0-9a-f]{32}$`, `X-Request-ID` header equals the body `request_id`, and the unexpected record for that request (exactly one per request, two in total, in request order) has the same `request_id`; the two ids differ | xfail BUG-483 — fails today on: `RuntimeError` propagates out of the client |
| MW-SH-23 | R6 [BUG-483], R6a, R6b | bug | direct dispatch of SH; scope path `/api/v1/items/9`, `"headers": []`, no `"client"` key; module-level `BOOM_KE = KeyError("k")`; `call_next` raises `BOOM_KE` | `await SecurityHeadersMiddleware(app=None).dispatch(request, call_next)` (no `pytest.raises`) | returns a response with status 500, XCTO, XFO, `X-XSS-Protection == "0"`, HSTS defaults, no CSP; JSON body `instance == "/api/v1/items/9"`, `request_id` matches `^req_[0-9a-f]{32}$`; header `X-Request-ID` equals body `request_id`; exactly one unexpected record: `levelno == logging.ERROR`, `record.exc_info[1] is BOOM_KE`, `error_type == "KeyError"`, `error == "'k'"`, `method == "GET"`, `path == "/api/v1/items/9"`, `user_agent is None`, `ip_address is None`, `request_id` == body `request_id` | xfail BUG-483 — fails today on: `KeyError` raised by `dispatch` |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior" (existing BUG-039) | API/integration tests of `app/main.py` | real middleware order: CORS, rate limiting, RC and SH wrapping, exception handlers; 500s from the real app carry security headers and `X-Request-ID` |
| Q1 endpoint side (existing BUG-040) | `GET /api/v1/mobile-upload/public` endpoint spec | the upload token moves out of the query string |
| Q8 mock gateway page — TODO (reviewer: leave as is for now) | `/api/v1/payments/mock-gateway/{tran_id}` endpoint spec | TODO: remove the mock page or upgrade it / limit it to non-prod; once BUG-487 is fixed it may set its own CSP (`style-src 'unsafe-inline'`) so its inline styles load |

## Spec gaps
None. (Previous gaps 1–3 closed by spec Gap log G1–G3: query-string encoding → MW-RC-27/28; "Unexpected error" record → MW-SH-18/23; request id without RC → MW-SH-22/23.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `RequestContextMiddleware.dispatch` | R1 | MW-RC-01, MW-RC-02, MW-RC-03 |
| | R2 | MW-RC-01, MW-RC-24 |
| | R3 | MW-RC-01, MW-RC-04, MW-RC-15 |
| | R4 | MW-RC-05, MW-RC-06, MW-RC-07, MW-RC-27 |
| | R4a [BUG-480] | MW-RC-07 (not-redacted, pass), MW-RC-08, MW-RC-09, MW-RC-10, MW-RC-11, MW-RC-28 |
| | R4b | MW-RC-27, MW-RC-28 |
| | R5 | MW-RC-10, MW-RC-12, MW-RC-13 |
| | R6 | MW-RC-05, MW-RC-14, MW-RC-15, MW-RC-16 |
| | R7 | MW-RC-05, MW-RC-16, MW-RC-17 |
| | R8 | MW-RC-18, MW-RC-19 |
| | R8a [BUG-481] | MW-RC-19 (pass part), MW-RC-20 |
| | R8b | MW-RC-21 |
| | R9 | MW-RC-18 (type only), MW-RC-22, MW-RC-23, MW-RC-25 |
| | R10 | MW-RC-24 |
| | R10a [BUG-482] | MW-RC-25 |
| | R11 | MW-RC-11, MW-RC-26 |
| | Errors: rest of app raises | MW-RC-24, MW-RC-25 |
| `SecurityHeadersMiddleware.dispatch` | R1 | MW-SH-06, MW-SH-07 |
| | R1a [BUG-485] | MW-SH-08 |
| | R1b [BUG-485] | MW-SH-09, MW-SH-10 |
| | R2 | MW-SH-06, MW-SH-11, MW-SH-19 |
| | R2a [BUG-484] | MW-SH-12, MW-SH-13, MW-SH-19 |
| | R3 | MW-SH-01, MW-SH-02, MW-SH-04, MW-SH-05, MW-SH-15 |
| | R3a [BUG-486] | MW-SH-03, MW-SH-12 |
| | R4 | MW-SH-01, MW-SH-04, MW-SH-05, MW-SH-17, MW-SH-21 |
| | R5 | MW-SH-14 |
| | R5a [BUG-487] | MW-SH-15 (pass part), MW-SH-13, MW-SH-16, MW-SH-17 |
| | R6 [BUG-483] | MW-SH-18, MW-SH-19, MW-SH-22, MW-SH-23 |
| | R6a [BUG-483] | MW-SH-18, MW-SH-23 |
| | R6b [BUG-483] | MW-SH-18, MW-SH-22, MW-SH-23 |
| | R7 | MW-SH-01, MW-SH-04, MW-SH-20 |
| | Errors: rest of app raises [BUG-483] | MW-SH-18, MW-SH-19, MW-SH-22, MW-SH-23 |
