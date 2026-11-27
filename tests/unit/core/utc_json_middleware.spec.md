# Spec — `app/core/utc_json_middleware.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Any text value that looks like a date-time gets a "Z" added, not only real date-time fields — 🐞 BUG-520
**Background:** The middleware does not know which JSON fields are date-times. It walks every string value in every `/api/` JSON response and appends `Z` to any string whose whole content has the shape `YYYY-MM-DDTHH:MM:SS` (optionally with fractional seconds). Dictionary keys are never changed.
**What happens today:** A user-entered free-text value (a note, a name, a reference code, a custom-field value) that happens to be exactly in that shape is returned with an extra `Z` that the user never typed.
**Example:** A user saves an item description `2026-01-05T09:30:00`. Reading the item back via `GET /api/v1/items/{id}` shows `2026-01-05T09:30:00Z`; if the frontend saves the form again, the stored text becomes `2026-01-05T09:30:00Z`.
**Rules affected:** `dispatch` R8
**Suggested answer:** bug — only real date-time fields are emitted with the UTC `Z` suffix (done at serialization time, e.g. a Pydantic datetime serializer); free-text string values are returned exactly as stored.
**Answer:** bug — only real date-time fields are emitted with the UTC `Z` suffix (done at serialization time, e.g. a Pydantic datetime serializer); free-text string values are returned exactly as stored. (reviewer accepted suggestion)
**Resolution:** the middleware must not change string values; free-text is returned exactly as stored. The UTC `Z` suffix on real date-time fields moves to serialization time (response-schema datetime serializer), which is specified and tested with that serializer, not here. Same root cause as `tests/unit/utils/datetime_serialize.spec.md` Q1 (one fix covers both). At this layer the intended behavior is: a valid JSON body's content is returned unchanged, including date-time-shaped strings (best-practice default, delegated by reviewer — the middleware cannot tell fields apart, so the only correct middleware behavior is to leave strings alone; once the serializer fix lands the middleware may become removable). Rules: `dispatch` R8, R8a.

### Q2. Repeated response headers are collapsed to the first value — 🐞 BUG-521
**Background:** When the middleware rebuilds a JSON response it copies the headers into a plain dictionary. A header that appears more than once (typically `Set-Cookie`, also `Vary` or `Link` when set as separate lines) keeps only its first value. No `/api/` endpoint sets cookies today, so this is latent.
**What happens today:** Every rebuilt `/api/` JSON response keeps only the first occurrence of each header name; later occurrences are dropped silently.
**Example:** A future login endpoint returns JSON and sets two cookies, `access=…` and `refresh=…`. The browser receives only `access=…`; the refresh cookie is lost and the user is logged out when the access token expires.
**Rules affected:** `dispatch` R10, R12
**Suggested answer:** bug — all header lines are preserved, including repeated names (only `content-length` is recomputed).
**Answer:** bug — all header lines are preserved, including repeated names (only `content-length` is recomputed). (reviewer accepted suggestion)
**Resolution:** every rebuilt response (R7/R7a pass-through of an unparseable body, R8 rewritten JSON) keeps all header lines, including repeated names, in their original order; only `content-length` is recomputed for a rewritten body. Rules: `dispatch` R10, R10a, R12.

### Q3. A JSON-labelled body that is not valid UTF-8 causes a 500 — 🐞 BUG-522
**Background:** Bodies that are not valid JSON are passed through unchanged (R7). But a body whose bytes are not valid UTF-8 (or UTF-16/32) fails with a different error type, which is not caught. No current endpoint is known to produce such a body; it would need an endpoint that labels raw/binary bytes as `application/json`.
**What happens today:** The middleware raises `UnicodeDecodeError`; the client gets a 500 instead of the endpoint's original response.
**Example:** An endpoint returns `Response(content=b'"\xc3\x28"', media_type="application/json")` with status 200. The client receives a 500 Internal Server Error instead of the 200 with those bytes.
**Rules affected:** `dispatch` R7a
**Suggested answer:** bug — an undecodable body is passed through unchanged with its original status and headers, the same as malformed JSON (R7).
**Answer:** bug — an undecodable body is passed through unchanged with its original status and headers, the same as malformed JSON (R7). (reviewer accepted suggestion)
**Resolution:** an undecodable body is treated like malformed JSON: returned byte-for-byte with its original status code and headers. Rules: `dispatch` R7a.

## Overview
`UtcJsonResponseMiddleware` post-processes HTTP responses so that naive ISO date-time strings in `/api/` JSON bodies carry a trailing `Z` (UTC). The backend stores and emits naive UTC datetimes; the frontend needs the `Z` to interpret them as UTC rather than local time. It is registered in `app/main.py` for every request; the string transformation itself is `app.utils.datetime_serialize.ensure_utc_z_in_json` (specified separately in `tests/unit/utils/datetime_serialize.spec.md`; its outcome is summarised here only as far as this middleware exposes it).

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** ordering relative to the other middlewares in `app/main.py` (which middleware's headers are present when this one runs) — none of it is unit-testable here.

**Notes for the test designer:**
- Framework glue: do NOT start the real app. Build a minimal `FastAPI()` (or `Starlette`) app in the test, `app.add_middleware(UtcJsonResponseMiddleware)`, add tiny routes that return exactly the response you need (`JSONResponse`, `Response(content=..., media_type=...)`, `PlainTextResponse`, `StreamingResponse` with several chunks, custom headers, custom status codes), and call it with `starlette.testclient.TestClient`. No database is needed.
- The rewritten body is re-serialized with Python's `json.dumps` defaults: `", "` / `": "` separators and non-ASCII characters escaped as `\uXXXX`. Compare bodies by parsing them (`response.json()`), not byte-for-byte, except where a rule says the body is passed through unchanged.
- Route exceptions handled by exception handlers registered on the same minimal app (e.g. `HTTPException` → JSON error body) produce ordinary responses and ARE processed by this middleware.

## Not specified
_(none)_

---

## `UtcJsonResponseMiddleware.dispatch(request, call_next)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered as HTTP middleware in `app/main.py`)

**Purpose:** Pass every response through unchanged, except `/api/` JSON responses, whose naive ISO date-time string values get a `Z` suffix.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `request` | Starlette `Request` | Only `request.url.path` is inspected. |
| `call_next` | callable | Runs the rest of the app and yields the downstream response. |

**Returns:** A `Response` — either the downstream response itself (pass-through cases) or a new response with the same status code and headers and a rewritten body.

**Rules:**
- **R1.** The downstream app always runs exactly once; an exception it raises (one not turned into a response by an exception handler) propagates out of the middleware unchanged.
- **R2.** A request whose path does not start with `/api/` is passed through untouched (body, status and headers identical), whatever the content type. Boundaries: `/api` (no trailing slash), `/apiv1/x`, `/`, `/health` are all passed through; `/api/` and `/api/v1/anything` are processed. The prefix check is case-sensitive (`/API/v1/x` is passed through).
- **R3.** An `/api/` response whose `content-type` header does not contain the substring `application/json` is passed through untouched (e.g. `text/plain`, `text/html`, `application/pdf`, `application/problem+json`, no content-type header at all). A content type that contains the substring — `application/json`, `application/json; charset=utf-8`, `application/json-patch+json` — is processed.
- **R4.** The whole body is collected before any decision about it; a body streamed in several chunks is treated as the concatenation of the chunks.
- **R5.** An `/api/` JSON response with an empty body (0 bytes, e.g. status 204, or a HEAD request) is returned with an empty body and its original status and headers.
- **R6.** For a processed response, the status code is preserved exactly (200, 201, 400, 404, 422, 500 …); error bodies from exception handlers are rewritten the same way as success bodies.
- **R7.** A non-empty body that is not valid JSON (e.g. `not json`, `{"a":`) is returned byte-for-byte unchanged, with the original status code and headers (including its original `content-length`).
- **R7a.** [BUG-522] A non-empty body whose bytes cannot be decoded as UTF-8/16/32 (e.g. `b'"\xc3\x28"'` with status 200) is returned byte-for-byte unchanged, with its original status code and headers (including its original `content-length`) — the same as R7; no exception is raised. *(Today: the middleware raises `UnicodeDecodeError` and the client gets a 500.)*
- **R8.** A valid JSON body is parsed and re-emitted with its content intact wherever no date-time-shaped string is involved: object keys are never changed (even if they look like a date-time), and string values that are NOT shaped like a naive date-time are unchanged — e.g. `"2026-01-05T09:30:00Z"`, `"2026-01-05T09:30:00+00:00"`, `"2026-01-05"`, `"2026-01-05 09:30:00"` (space, not `T`), `"x2026-01-05T09:30:00"`, `"hello"` — as are numbers, booleans and `null`, at any nesting depth inside objects and arrays, and for a top-level array or top-level string body.
- **R8a.** [BUG-520] A string value whose entire content is shaped like a naive date-time (`YYYY-MM-DDTHH:MM:SS`, optionally with `.` + fractional digits) is also returned exactly as the endpoint produced it, at any nesting depth and as a top-level string: `{"note": "2026-01-05T09:30:00"}` stays `{"note": "2026-01-05T09:30:00"}`; `["2026-01-05T09:30:00.123456"]` and a body `"2026-01-05T09:30:00"` are unchanged. The UTC `Z` on real date-time fields is the response serializer's job, not this middleware's (best-practice default, delegated by reviewer). *(Today: `Z` is appended to every such string regardless of field — `"2026-01-05T09:30:00"` → `"2026-01-05T09:30:00Z"`, `"2026-01-05T09:30:00.123456"` → `"2026-01-05T09:30:00.123456Z"`; exact current matching rules are those of `ensure_utc_z_in_json` in `tests/unit/utils/datetime_serialize.spec.md`.)*
- **R9.** Apart from the `Z` suffix of R8a (today's behavior), the parsed JSON content is preserved (same keys, key order, values, nesting); the body is re-encoded as UTF-8 JSON, so its bytes may differ in whitespace and `\uXXXX` escaping even when no string changed.
- **R10.** A rebuilt response (R7, R7a, R8) keeps the downstream response's headers (including `content-type` and custom headers such as `X-Request-ID`). For a rewritten body (R8) `content-length` is recomputed to match the new body's length (R11); for a byte-for-byte pass-through (R7, R7a) it is the original value.
- **R10a.** [BUG-521] A header name that appears more than once in the downstream response (e.g. two `Set-Cookie` lines `access=a` and `refresh=r`, or two `Vary` lines) keeps every line, in the original order, on every rebuilt response (R7, R7a, R8). *(Today: only the first line of each repeated header survives — the client receives only `Set-Cookie: access=a`.)*
- **R11.** A rewritten response's `content-length` equals the byte length of the new body (a body that grows on re-encoding — e.g. compact `{"a":"é"}` becomes `{"a": "é"}` — is not truncated; today a body that grows by appended `Z` characters is another such case).
- **R12.** Pass-through cases R2, R3 and R5 return the original response object, so repeated header lines survive there (true today); R7, R7a and R8 rebuild the response and follow R10/R10a.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Downstream app raises an unhandled exception | same exception, propagated | — |

**Side effects:** none (no database, no externals). The streamed body of the downstream response is consumed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18 | downstream raises vs. returns | R1 |
| 20 | path starts with `/api/` / not | R2 |
| 23 | `content-type` header missing → `""` | R3 |
| 24 | content type contains `application/json` / not | R3 |
| 28 | body chunks: zero / one / many | R4, R5 |
| 31 | body empty / non-empty | R5 |
| 34–42 | `json.loads` succeeds / `JSONDecodeError` | R7, R8, R8a |
| 35 | `UnicodeDecodeError` (not caught today; intended pass-through) | R7a |
| 44 (`ensure_utc_z_in_json`) | value is dict → recurse into values, keys unchanged | R8 |
| 44 (`ensure_utc_z_in_json`) | value is list → recurse into items | R8 |
| 44 (`ensure_utc_z_in_json`) | value is string matching naive ISO pattern / not matching | R8a / R8 |
| 44 (`ensure_utc_z_in_json`) | any other type → unchanged | R8 |
| 45 | re-serialization (`default=str`, ascii escaping) | R9 |
| 37, 47 | headers copied into a dict (first value per name) | R10, R10a |
| 48 | `content-length` present / absent → removed, recomputed | R10, R11 |
| 50–55 | status code and media type carried over | R6, R10 |
