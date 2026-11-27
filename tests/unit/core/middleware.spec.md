# Spec — `app/core/middleware.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

_No house-rule violations and no precedent matches: the house rules and existing bug patterns cover data/DAO behavior, none of which this file has._

### New questions

### Q1. The full query string is written to the request log, including secret tokens — 🐞 BUG-480
**Background:** Every request produces a "Request started" log line that carries the raw query string. Some public endpoints take a credential in the query string: the phone-upload page calls `GET /api/v1/mobile-upload/public?token=<secret>` and that token alone grants access to the upload session.
**What happens today:** The query string is logged verbatim, with no redaction of any parameter.
**Example:** A phone opens `/api/v1/mobile-upload/public?token=Zk3...9Q`. The log record for that request has `query_params = "token=Zk3...9Q"`. Anyone with log access (log vendor, support staff) can reuse the token until it expires.
**Rules affected:** `RequestContextMiddleware.dispatch` R4
**Suggested answer:** bug — redact sensitive query parameters before logging (at least `token`, and other credential-like names such as `password`, `secret`, `key`, `signature`, `code`): keep the parameter name, replace the value with `***`
**Answer:** bug — redact sensitive query parameters before logging (at least `token`, and other credential-like names such as `password`, `secret`, `key`, `signature`, `code`): keep the parameter name, replace the value with `***` (reviewer accepted suggestion)
**Resolution:** sensitive query parameters are logged as `name=***`. How a name is recognised as sensitive (word-part match, case-insensitive, so `access_token`/`apiKey`/`zip_code` are redacted but `keyword`/`barcode` are not) is a (best-practice default, delegated by reviewer). The endpoint-side fix (token out of the URL) is the existing BUG-040. Rules: `RequestContextMiddleware.dispatch` R4a.

### Q2. Every 4xx response is logged at ERROR level — 🐞 BUG-481
**Background:** The "Request completed" log line uses INFO for status codes below 400 and ERROR for everything from 400 up. 4xx codes are client mistakes (validation errors, 401/403/404, 409 duplicates, 429 rate limits), not server faults.
**What happens today:** A 404 or a 422 is logged at the same ERROR level as a 500.
**Example:** A user mistypes a form field 20 times; the logs show 20 ERROR lines, and an alert "errors > 10/min" fires although the server is healthy.
**Rules affected:** `RequestContextMiddleware.dispatch` R8
**Suggested answer:** bug — below 400 → INFO, 400–499 → WARNING, 500 and above → ERROR
**Answer:** bug — below 400 → INFO, 400–499 → WARNING, 500 and above → ERROR (reviewer accepted suggestion)
**Resolution:** 4xx responses are logged at WARNING. Rules: `RequestContextMiddleware.dispatch` R8, R8a, R8b.

### Q3. A request that crashes produces no "Request completed" log line — 🐞 BUG-482
**Background:** When an endpoint raises an exception that no specific handler turns into a response (an unexpected crash), the exception passes up through this middleware to the app's outermost error handler, which turns it into a 500.
**What happens today:** The middleware does not catch it: the "Request started" line is logged, but no "Request completed" line with status and duration is ever written for that request.
**Example:** An endpoint hits a `KeyError`. The client gets a 500. In the logs, the request has a start line and nothing else, so dashboards built on "Request completed" (status counts, latency) never see the 500 at all.
**Rules affected:** `RequestContextMiddleware.dispatch` R10
**Suggested answer:** bug — on an unhandled exception, log "Request completed" at ERROR with `status_code` 500 and the duration, then re-raise the exception unchanged
**Answer:** bug — on an unhandled exception, log "Request completed" at ERROR with `status_code` 500 and the duration, then re-raise the exception unchanged (reviewer accepted suggestion)
**Resolution:** a crashing request still gets its "Request completed" record (ERROR, 500, duration); the exception is re-raised unchanged. Rules: `RequestContextMiddleware.dispatch` R10, R10a.

### Q4. Crash (500) responses get no security headers — 🐞 BUG-483
**Background:** The security-header middleware adds its headers only after the endpoint returns a response. An unexpected crash is turned into a 500 by the app's outermost error handler, which sits outside this middleware.
**What happens today:** When the endpoint raises, the exception passes straight through and no security headers are added; the resulting 500 goes out without `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` etc. Handled errors (400/404/409/422, returned as responses) do get them.
**Example:** `GET /api/v1/items/5` hits an unexpected bug. The browser receives a 500 with none of the security headers, while a 404 from the same endpoint carries all of them.
**Rules affected:** `SecurityHeadersMiddleware.dispatch` R6
**Suggested answer:** bug — security headers are present on every response, including 500s from unhandled exceptions
**Answer:** bug — security headers are present on every response, including 500s from unhandled exceptions (reviewer accepted suggestion)
**Resolution:** a crash yields a 500 that carries the security headers. Mechanism (best-practice default, delegated by reviewer): Starlette always places its own error handler outside every user middleware, so the headers cannot be added "after" it; instead this middleware catches the exception, builds the app's standard 500 response with the existing catch-all handler `generic_exception_handler` (same body, same "Unexpected error" server log), adds the headers, and returns it (the exception does not travel further). Rules: `SecurityHeadersMiddleware.dispatch` R6.

### Q5. API-docs pages get no security headers at all — 🐞 BUG-484
**Background:** Swagger UI (`/api/v1/docs`) and ReDoc (`/api/v1/redoc`) load scripts and styles from a CDN and use inline code, so a strict `Content-Security-Policy` would break them. The code comment says the exemption exists "to avoid blocking assets".
**What happens today:** For docs paths, *all* security headers are skipped, not just the CSP — including `X-Content-Type-Options`, `X-Frame-Options` and `Strict-Transport-Security`, none of which affect asset loading.
**Example:** `/api/v1/docs` can be embedded in an iframe on any site (no `X-Frame-Options`), and a browser visiting it over HTTPS gets no HSTS instruction from that page.
**Rules affected:** `SecurityHeadersMiddleware.dispatch` R2
**Suggested answer:** bug — docs paths still get `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection` and `Strict-Transport-Security`; only the `Content-Security-Policy` is skipped for them
**Answer:** bug — docs paths still get `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection` and `Strict-Transport-Security`; only the `Content-Security-Policy` is skipped for them (reviewer accepted suggestion)
**Resolution:** docs paths get the four non-CSP headers; only CSP is skipped. Rules: `SecurityHeadersMiddleware.dispatch` R2, R2a.

### Q6. The docs exemption matches any path that merely starts with the docs URL — 🐞 BUG-485
**Background:** Docs paths are recognised by a text prefix check against the fixed strings `/api/v1/docs`, `/api/v1/redoc` and `/api/v1/openapi.json` (not built from the configured API prefix).
**What happens today:** Any path beginning with those strings is treated as a docs page and gets no security headers, e.g. `/api/v1/docs-export` or `/api/v1/redocuments`. No such endpoint exists today, but a future one with such a name would silently lose its security headers. Also, if the API prefix setting changes from `/api/v1`, the real docs pages would suddenly get a strict CSP and break.
**Example:** A new endpoint `GET /api/v1/docsets` returns HTML; it is served with no `X-Frame-Options` and no CSP.
**Rules affected:** `SecurityHeadersMiddleware.dispatch` R1
**Suggested answer:** bug — exempt only the exact docs URLs (the docs page and its sub-paths such as `/docs/oauth2-redirect`, the redoc page, and the OpenAPI JSON), built from the configured API prefix
**Answer:** bug — exempt only the exact docs URLs (the docs page and its sub-paths such as `/docs/oauth2-redirect`, the redoc page, and the OpenAPI JSON), built from the configured API prefix (reviewer accepted suggestion)
**Resolution:** docs paths are `<prefix>/docs`, anything under `<prefix>/docs/`, exactly `<prefix>/redoc` and exactly `<prefix>/openapi.json`, with `<prefix>` = `settings.API_V1_STR`. Treating `<prefix>/redoc/…` and `<prefix>/openapi.json/…` as NOT docs paths (FastAPI serves nothing there) is a (best-practice default, delegated by reviewer). Rules: `SecurityHeadersMiddleware.dispatch` R1, R1a, R1b.

### Q7. `X-XSS-Protection` is set to the deprecated "block" mode — 🐞 BUG-486
**Background:** `X-XSS-Protection` controlled a browser XSS filter that modern browsers have removed; where it still exists, `1; mode=block` has itself been used to create cross-site information leaks. OWASP and MDN now recommend sending `X-XSS-Protection: 0` (or not sending it) and relying on CSP.
**What happens today:** Every non-docs response carries `X-XSS-Protection: 1; mode=block`.
**Example:** A security scanner (e.g. OWASP ZAP) run against the API reports "X-XSS-Protection header enabled" as a finding on every endpoint.
**Rules affected:** `SecurityHeadersMiddleware.dispatch` R3
**Suggested answer:** bug — send `X-XSS-Protection: 0`
**Answer:** bug — send `X-XSS-Protection: 0` (reviewer accepted suggestion)
**Resolution:** the header value is `0`. Rules: `SecurityHeadersMiddleware.dispatch` R3, R3a.

### Q8. Security headers overwrite values an endpoint set on purpose — 🐞 BUG-487
**Background:** An endpoint can set its own response headers, e.g. a page that must be framed by our own frontend, or an HTML page that needs a looser `Content-Security-Policy`. The dev-only mock payment-gateway page (`/api/v1/payments/mock-gateway/{tran_id}`) is such an HTML page and uses an inline `<style>` block.
**What happens today:** The middleware always overwrites `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, and (for HTML) `Content-Security-Policy`, whatever the endpoint set. An endpoint cannot opt into a different policy.
**Example:** The mock gateway page is served with `Content-Security-Policy: default-src 'self'`, so the browser blocks its inline styles and the page renders unstyled; setting a different CSP in the endpoint would have no effect.
**Rules affected:** `SecurityHeadersMiddleware.dispatch` R5
**Suggested answer:** bug — the middleware sets each header only when the response does not already have it (safe default, endpoint may override)
**Answer:** bug — the middleware sets each header only when the response does not already have it (safe default, endpoint may override) (reviewer accepted suggestion)
**Resolution:** each security header is a default: set only when the response does not already carry that header (header names compared case-insensitively). The mock gateway page itself is left as is for now (reviewer: it will be removed or upgraded/limited to non-prod later; tracked outside this module); after this fix it could set its own CSP. Rules: `SecurityHeadersMiddleware.dispatch` R5, R5a.

## Overview
Two Starlette `BaseHTTPMiddleware` classes registered on the FastAPI app in `app/main.py`. `RequestContextMiddleware` gives every request a unique request id (available to handlers as `request.state.request_id`, which the exception handlers in `app/core/exceptions.py` put in error bodies), returns it in the `X-Request-ID` response header, and logs a start and a completion line. `SecurityHeadersMiddleware` adds standard browser security headers to every response (the API-docs pages only skip the CSP).

**Callables:** 2 specified · 0 not specified
**Externals to mock:** none (no utcnow; see notes on patching `time.time` and `uuid.uuid4`)
**Integration-only behavior:** middleware ordering in the real app (which middleware wraps which, and interaction with CORS, rate limiting and the app's exception handlers) — covered by API/integration tests, not here (see existing BUG-039).

**Notes for the test designer:**
- Do not start the real app (`app.main`). Build a minimal `FastAPI()` (or Starlette) app per test, add the middleware under test with `app.add_middleware(...)`, add small routes that return what the case needs (a JSON 200, a 399/400/404/499/500 response, an `HTMLResponse`, a response with a preset header, a route that raises), and call it with `fastapi.testclient.TestClient`. For the "route raises" case use `TestClient(app, raise_server_exceptions=False)` or `pytest.raises`.
- To observe `request.state.request_id`, have the test route return it in the body.
- Logs: logger name is `app.core.middleware`; use `caplog` (set level to DEBUG/INFO for that logger so WARNING and INFO are both captured). The extra fields are attributes on the `LogRecord` (e.g. `record.request_id`, `record.query_params`).
- Duration: patch `app.core.middleware.time.time` with a side-effect sequence (e.g. `[100.0, 100.123456]` → `duration_ms == 123.46`). Request id: patch `app.core.middleware.uuid.uuid4` to return a fixed `UUID` to assert the exact id.
- `TestClient` always sends a client address (`"testclient"`). For the "no client address" case, call `RequestContextMiddleware(app=None).dispatch(request, call_next)` directly with a `starlette.requests.Request` built from a scope dict that has no `"client"` key (or `"client": None`) and an async stub `call_next` returning a `Response`.
- Docs paths: the minimal app can define plain routes at `/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`, `/api/v1/docs/oauth2-redirect` and look-alikes such as `/api/v1/docsets`; the check is on the path only. For the configured-prefix rule (R1b), set `app.core.config.settings.API_V1_STR` with `monkeypatch.setattr` before building the app and middleware.
- Bug rules (tagged `[BUG-NNN]`) are expected to fail until fixed: `xfail(strict=True, reason="BUG-NNN")`.

## Not specified
_(none)_

---

## `RequestContextMiddleware.dispatch(request, call_next)`
**Shape:** helper (middleware)
**Persistence:** pure (no database)
**Visibility:** public (registered in `app/main.py`)

**Purpose:** Tag each request with a unique id, expose it to handlers and the client, and log the request's start and outcome with timing.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `request` | Starlette `Request` | Any HTTP request. Method, path, query string, client address, `User-Agent` and `X-Workspace-ID` headers are read; none is validated. |
| `call_next` | async callable | Runs the rest of the app and returns its response. |

**Returns:** the response produced by the rest of the app, with `X-Request-ID` added.

**Rules:**
- **R1.** Every request gets a new id of the form `req_` followed by 32 lowercase hex characters (a random UUID4 without dashes). Two requests never share an id. Any `X-Request-ID` header sent by the client is ignored.
- **R2.** The id is available to the rest of the app during the request as `request.state.request_id`.
- **R3.** The response carries header `X-Request-ID` equal to that id. If the route itself set an `X-Request-ID` header, it is replaced by the middleware's id.
- **R4.** Before the request is handled, one log record is emitted on logger `app.core.middleware` at INFO with message `"Request started"` and these extra fields: `request_id` (the id), `method` (e.g. `"GET"`), `path` (URL path only, without the query string), `query_params`, `client_ip`, `user_agent`, `workspace_id`. `query_params` is the URL-encoded query string with parameters in the order sent (e.g. `"a=1&b=2"`); parameters that are not sensitive (R4a) appear with their values unchanged.
- **R4a.** [BUG-480] Sensitive query parameters are redacted in `query_params`: the name is kept and every value is replaced by `***` (also an empty value: `token=` → `token=***`; a repeated parameter is redacted each time). Other parameters and the order are unchanged: `?a=1&token=abc&b=2` → `"a=1&token=***&b=2"`. A parameter name is sensitive when, after splitting it into parts at `_`, `-`, `.` and camelCase boundaries and lowercasing, any part is one of `token`, `password`, `secret`, `key`, `signature`, `code` (best-practice default, delegated by reviewer). Redacted: `token`, `TOKEN`, `access_token`, `accessToken`, `api-key`, `apiKey`, `client_secret`, `password`, `signature`, `code`, `zip_code`. Not redacted: `keyword`, `tokens`, `barcode`, `monkey`, `q`, `page`. *(Today: the query string is logged verbatim, `"a=1&token=abc&b=2"`.)*
- **R4b.** `query_params` is not the raw query string as sent: it is rebuilt from the decoded parameters and re-encoded form-style (names and values). A space is written as `+`, and every character other than letters, digits and `_ . - ~` is percent-encoded with uppercase hex. So `?q=a%20b` and `?q=a+b` both log `"q=a+b"`; `?q=a/b` logs `"q=a%2Fb"`; `?q=a%26b` logs `"q=a%26b"`; `?q=%C3%A9` logs `"q=%C3%A9"`; repeated parameters are all kept in order (`?a=1&a=2` → `"a=1&a=2"`). The redaction marker of R4a is written literally as `***` (not percent-encoded as `%2A%2A%2A`) (best-practice default, delegated by reviewer).
- **R5.** `query_params` is `None` when the request has no query parameters (including a bare trailing `?`). A parameter with an empty value (`?a=`) counts as present: `"a="`.
- **R6.** `client_ip` is the client's host address; `None` when the server provides no client address.
- **R7.** `user_agent` is the `User-Agent` header value and `workspace_id` is the `X-Workspace-ID` header value (header names matched case-insensitively), each `None` when the header is absent. The workspace id is logged as sent, unvalidated.
- **R8.** After the response is produced, one log record is emitted with message `"Request completed"` and extras `request_id` (same id), `status_code`, and `duration_ms`. Level is INFO when `status_code < 400` (e.g. 200, 302, 399).
- **R8a.** [BUG-481] Level is WARNING when `400 <= status_code <= 499` (e.g. exactly 400, 404, 422, 499). *(Today: ERROR.)*
- **R8b.** Level is ERROR when `status_code >= 500` (e.g. exactly 500, 503) returned as a response.
- **R9.** `duration_ms` is the wall-clock time from before the start log to after the response is produced (or the exception is raised, R10a), in milliseconds, rounded to 2 decimals (start 100.0 s, end 100.123456 s → `123.46`).
- **R10.** If the rest of the app raises instead of returning a response, the exception propagates unchanged (same exception object/type and message); no response and no `X-Request-ID` header are produced by this middleware. The "Request started" record has been logged, and `request.state.request_id` was already set, so an outer error handler can still read it.
- **R10a.** [BUG-482] In that case, before the exception propagates, one `"Request completed"` record is emitted at ERROR with extras `request_id` (same id), `status_code` `500` and `duration_ms` (per R9). *(Today: no "Request completed" record at all.)*
- **R11.** The response body and status code are passed through unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Rest of the app raises | the same exception, unchanged | — |

**Side effects:** two log records per request, including requests that raise (R10a); sets `request.state.request_id`; adds response header `X-Request-ID`.

---

## `SecurityHeadersMiddleware.dispatch(request, call_next)`
**Shape:** helper (middleware)
**Persistence:** pure (no database)
**Visibility:** public (registered in `app/main.py`)

**Purpose:** Add browser security headers to every response; the API documentation pages only skip the Content-Security-Policy.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `request` | Starlette `Request` | Only the URL path is read (plus, on a crash, what the generic 500 handler reads). |
| `call_next` | async callable | Runs the rest of the app and returns its response. |

**Returns:** the response produced by the rest of the app, with headers added per the rules; on a crash, the app's standard 500 response with headers (R6).

**Rules:**
- **R1.** Docs paths are recognised by URL path, case-sensitively. These are docs paths: `/api/v1/docs`, `/api/v1/docs/oauth2-redirect` (and anything else under `/api/v1/docs/`), `/api/v1/redoc`, `/api/v1/openapi.json` (with the default prefix `/api/v1`). These are not: `/api/v1/doc`, `/api/v2/docs`, `/docs`, `/API/v1/docs`, `/api/v1/items`.
- **R1a.** [BUG-485] Look-alike paths are not docs paths: `/api/v1/docsets`, `/api/v1/docs-export`, `/api/v1/redocuments`, `/api/v1/redoc/x`, `/api/v1/openapi.json.bak`, `/api/v1/openapi.jsonx`. Only exactly `<prefix>/docs`, paths under `<prefix>/docs/`, exactly `<prefix>/redoc` and exactly `<prefix>/openapi.json` are docs paths (exact redoc/openapi match is a best-practice default, delegated by reviewer). *(Today: any path starting with `/api/v1/docs`, `/api/v1/redoc` or `/api/v1/openapi.json` is a docs path.)*
- **R1b.** [BUG-485] `<prefix>` is the configured API prefix `settings.API_V1_STR`, not the literal `/api/v1`: with the setting `/api/v2`, `/api/v2/docs`, `/api/v2/redoc` and `/api/v2/openapi.json` are docs paths and `/api/v1/docs` is not. *(Today: the literal `/api/v1` strings are used.)* *(requires reading the setting when the middleware is built or per request, not a hard-coded string)*
- **R2.** For a docs path, no `Content-Security-Policy` is added, even when the response is HTML (a CSP the route set itself stays as is).
- **R2a.** [BUG-484] For a docs path, the other security headers are still added exactly as for any path: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Strict-Transport-Security` with the values of R3/R3a, following R5a for values the route already set. *(Today: docs-path responses get no security header at all.)*
- **R3.** Every response (docs or not) gets these headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  regardless of status code (200, 3xx, 4xx and 5xx returned as responses all get them) and of HTTP vs HTTPS. *(For docs paths this is R2a — today docs get none.)*
- **R3a.** [BUG-486] Every response gets `X-XSS-Protection: 0`. *(Today: `X-XSS-Protection: 1; mode=block`.)*
- **R4.** For a non-docs path, `Content-Security-Policy: default-src 'self'` is added only when the response's `Content-Type` header contains the text `text/html` (e.g. `text/html; charset=utf-8`). The match is case-sensitive (`TEXT/HTML` does not match). JSON, plain-text, and responses with no `Content-Type` get no CSP header.
- **R5.** Headers set by the route other than the security headers are untouched. A route's own `Content-Security-Policy` on a non-HTML response is left as is.
- **R5a.** [BUG-487] Each security header from R3/R3a/R4 is only a default: when the response already carries that header (name compared case-insensitively), the route's value is kept and not duplicated. E.g. a route's `X-Frame-Options: SAMEORIGIN` stays `SAMEORIGIN`; a route's `Content-Security-Policy: default-src 'self'; style-src 'unsafe-inline'` on an HTML response stays as the route set it; headers the route did not set still get the defaults. *(Today: the middleware overwrites the route's value, `SAMEORIGIN` → `DENY`, the route's CSP → `default-src 'self'`.)*
- **R6.** [BUG-483] If the rest of the app raises instead of returning a response, the client receives a 500 that carries the security headers per R2/R2a/R3/R3a/R4 (for a non-docs path: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection: 0`, `Strict-Transport-Security`; the body is JSON, so no CSP). The response is the app's standard catch-all 500 (the one `generic_exception_handler` in `app/core/exceptions.py` builds): JSON body with `title` `"Internal Server Error"`, `status` `500`, `detail` `"An unexpected error occurred. Please contact support with the request ID."`, `instance` = the path and `request_id`, plus header `X-Request-ID`; the "Unexpected error" server log record is written. The exception does not propagate past this middleware (best-practice default, delegated by reviewer). *(Today: the exception propagates unchanged and the 500 built outside has no security headers.)*
- **R6a.** [BUG-483] The "Unexpected error" record of R6 is the one `generic_exception_handler` writes: logger `app.core.exceptions`, level ERROR, message exactly `"Unexpected error"`, with the exception's traceback attached (`record.exc_info` set, pointing at the raised exception) and extras `request_id`, `error_type` (the exception class name, e.g. `"KeyError"`), `error` (`str(exc)`), `path`, `method`, `user_agent` (`User-Agent` header or `None`), `ip_address` (client host or `None`). Exactly one such record per crash.
- **R6b.** [BUG-483] The `request_id` in the 500 body, in the `X-Request-ID` header and on the R6a record are the same value. It is `request.state.request_id` when something earlier in the request set it (with `RequestContextMiddleware` outside, the production order, it is that middleware's id, and the `X-Request-ID` header that middleware sets afterwards carries the same id). When nothing set it (`SecurityHeadersMiddleware` alone), a fresh id of the form `req_` + 32 lowercase hex characters is generated for that response; it is still identical in body, header and log record.
- **R7.** The response body and status code are passed through unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Rest of the app raises | nothing — turned into a 500 response (R6) [BUG-483]; *today: the same exception, unchanged* | — |

**Side effects:** response headers only; on a crash, the generic handler's "Unexpected error" log record (R6).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25 | new id per request | `RequestContextMiddleware.dispatch` R1 |
| 26 | id stored on `request.state` | R2 |
| 38 | `request.query_params` truthy → string, else `None` | R4, R5 |
| 38 | parameters re-encoded form-style (space → `+`, reserved chars percent-encoded) | R4b |
| 38 (after fix) | each parameter name sensitive → `***`, else value kept | R4a |
| 39 | `request.client` truthy → host, else `None` | R6 |
| 40–41 | header present → value, absent → `None` | R7 |
| 46 | `call_next` raises → propagates | R10 |
| 46 (after fix) | `call_next` raises → completion log at ERROR/500, then re-raise | R10a |
| 52 | header set/overwritten | R3 |
| 55 | `status_code < 400` → INFO, else ERROR | R8, R8a, R8b |
| 49, 62 | duration computed and rounded | R9 |
| 77 | `call_next` raises → propagates, no headers (after fix: standard 500 with headers) | `SecurityHeadersMiddleware.dispatch` R6 |
| exceptions.py 326 (after fix, via generic handler) | `request.state.request_id` set → reused, else fresh id | R6b |
| exceptions.py 329 (after fix, via generic handler) | "Unexpected error" record written | R6a |
| 80 | path starts with `/api/v1/docs` / `/api/v1/redoc` / `/api/v1/openapi.json` (each alternative, and none) | R1, R1a, R1b |
| 82 | docs path → skip all headers (after fix: skip CSP only) | R2, R2a |
| 84–87 | four headers set (overwrite; after fix: only if absent) | R3, R3a, R5, R5a |
| 90 | `content-type` absent → `""` | R4 |
| 91 | `"text/html" in content_type` → CSP, else none | R4, R5, R5a |

## Gap log
- G1 (middleware.cases.md gap 1) — Fact — added `RequestContextMiddleware.dispatch` R4b: `query_params` is re-encoded form-style (space → `+`, `/` → `%2F`, `%20` → `+`, uppercase percent-hex), redaction marker `***` literal; Branch map row added.
- G2 (middleware.cases.md gap 2) — Fact — added `SecurityHeadersMiddleware.dispatch` R6a: the "Unexpected error" record is on logger `app.core.exceptions`, level ERROR, exact message, `exc_info` set, extras listed; one per crash.
- G3 (middleware.cases.md gap 3) — Fact — added `SecurityHeadersMiddleware.dispatch` R6b: without `RequestContextMiddleware` the 500 gets a fresh `req_`+32-hex id, identical in body, `X-Request-ID` header and log record; with it, that middleware's id. Branch map rows added.
