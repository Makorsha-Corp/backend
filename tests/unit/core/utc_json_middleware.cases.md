# Test cases — `app/core/utc_json_middleware.py`

> **Spec:** `tests/unit/core/utc_json_middleware.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 — re-run on the same APPROVED spec (source commit e48a092, no rule changes since revision 2). Read `utc_json_middleware.verify.md` (verdict PASS, no Findings, 0 surviving mutants): no `case-missing` items to address. Re-checked every rule, Errors row and BUG tag against the Coverage matrix and the self-check list; no case changed, no IDs added or retired.
> *(Revision 2 — corrected byte lengths in Conventions and cases (B_COMPACT 16, B_PROCESSED 23, B_DT 36, shrink body 25) so the exact `content-length` assertions in UTCJ-D-04, -05, -07, -08, -17, -34, -36 match the stated bodies.)*
> **Counts:** 41 cases · 32 expected-to-pass · 9 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `UtcJsonResponseMiddleware.dispatch` 41 cases (9 bug: BUG-520 ×4, BUG-521 ×4, BUG-522 ×2, one case carries both BUG-521 and BUG-522).
- **Notable design choices:**
  - No database and no mocks: every case builds a minimal FastAPI app with the middleware and calls it through Starlette's `TestClient` (as the spec's Notes direct).
  - "Was this response processed?" is observed through re-encoding, not through the `Z` suffix (which is the BUG-520 behavior and goes away with the fix). Routes return a *compact* UTF-8 body containing `é`; a processed response comes back as `json.dumps` default output (`", "` / `": "` separators, `é` escaping), a passed-through one byte-for-byte as sent (best-practice default, delegated by reviewer). The spec states both the re-serialization defaults and the byte-for-byte pass-through, so this marker is spec-backed and survives the BUG-520 fix.
  - Pass-through cases for non-`/api/` paths and non-JSON content types also carry a naive date-time string, so they stay meaningful both today and after the fix.
  - No passing case asserts today's `Z` appending (that is the buggy path).
  - HEAD case (UTCJ-D-14) asserts status, empty body and content-type only, not `content-length`: the spec does not pin what a HEAD response's length header should be (best-practice default, delegated by reviewer).
  - BUG-522 leaves nothing observable that works today on that path, so it has no companion passing case.
- **Needs a decision:** None.

## Conventions for this module

- **IDs:** `UTCJ` = utc_json_middleware, `D` = `dispatch`.
- **Harness (every case):** a fresh minimal `FastAPI()` app per test with `app.add_middleware(UtcJsonResponseMiddleware)` and only the routes that case needs. It is called with `starlette.testclient.TestClient(app)` (default `raise_server_exceptions=True`). No database session, no real app, no other middleware.
- **Externals mocked:** none. **Race simulations:** none. **Time:** not relevant (no clock is read).
- **Standard bodies** (raw bytes a route returns via `Response(content=..., media_type=...)`):
  - `B_COMPACT` = `b'{"a":"\xc3\xa9","b":1}'` (compact, UTF-8 `é`, 16 bytes).
  - `B_PROCESSED` = `b'{"a": "\\u00e9", "b": 1}'` — what `B_COMPACT` becomes after processing (`json.dumps` defaults; 23 bytes).
  - `B_DT` = `b'{"a":"\xc3\xa9","t":"2026-01-05T09:30:00"}'` (compact, contains a naive date-time string) (36 bytes) — used where the body must come back byte-for-byte.
- **"processed"** in Then means: `response.content == json.dumps(<expected parsed value>).encode()` exactly, and `response.headers["content-length"] == str(len(response.content))`.
- **"passed through"** in Then means: `response.content` equals the route's bytes exactly and `content-length` equals the original length.
- **Repeated headers:** a route adds raw repeated lines with `response.headers.append("Set-Cookie", "access=a")` then `response.headers.append("Set-Cookie", "refresh=r")` (similarly `Vary: Accept` / `Vary: Origin`). Read back with `response.headers.get_list(...)`.
- **Call counter:** a module-level/closure counter the route increments on every invocation, reset to 0 at the start of the test.

## `UtcJsonResponseMiddleware.dispatch`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| UTCJ-D-01 | R1 | happy | route `GET /api/v1/count` increments the counter and returns `JSONResponse({"a": 1})`; counter = 0 | GET `/api/v1/count` once | status 200; `response.json() == {"a": 1}`; counter == 1 | pass |
| UTCJ-D-02 | R1 | happy | route `GET /health` increments the counter and returns `JSONResponse({"ok": True})`; counter = 0 | GET `/health` once | status 200; `response.json() == {"ok": True}`; counter == 1 | pass |
| UTCJ-D-03 | R1, Errors row 1 | error | route `GET /api/v1/boom` increments the counter and raises `RuntimeError("boom")`; no exception handler for `RuntimeError` registered | GET `/api/v1/boom` | `pytest.raises(RuntimeError)` with message exactly `"boom"` (same type, not wrapped); counter == 1 | pass |
| UTCJ-D-04 | R2 | boundary | one route per path — `/api`, `/apiv1/x`, `/`, `/health`, `/API/v1/x` — each returns `Response(content=B_DT, media_type="application/json")` (parametrize over the 5 paths) | GET the path | status 200; passed through: `response.content == B_DT` byte-for-byte (in particular `"2026-01-05T09:30:00"` has no `Z` and `é` is not escaped); `content-length == "36"` (= `len(B_DT)`); `content-type == "application/json"` | pass |
| UTCJ-D-05 | R2 | boundary | routes `/api/` and `/api/v1/anything` each return `Response(content=B_COMPACT, media_type="application/json")` (parametrize over the 2 paths) | GET the path | status 200; processed: `response.content == B_PROCESSED`; `content-length == "23"`; `response.json() == {"a": "é", "b": 1}` | pass |
| UTCJ-D-06 | R2, R12 | side-effect | route `GET /health` returns `Response(content=B_COMPACT, media_type="application/json")` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/health` | status 200; `response.content == B_COMPACT`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]` | pass |
| UTCJ-D-07 | R3 | boundary | route `GET /api/v1/doc` returns `Response(content=B_DT, media_type=<mt>)` for each `<mt>` in `"text/plain"`, `"text/html"`, `"application/pdf"`, `"application/problem+json"`, and `None` (no content-type header at all) (parametrize over the 5) | GET `/api/v1/doc` | status 200; passed through: `response.content == B_DT`; `content-length == "36"`; for `<mt>` not None the `content-type` header starts with `<mt>` (Starlette may append `; charset=utf-8` to `text/*` — that is the downstream's own header); for None `"content-type" not in response.headers` | pass |
| UTCJ-D-08 | R3 | boundary | route `GET /api/v1/doc` returns `Response(content=B_COMPACT, headers={"content-type": <ct>})` for each `<ct>` in `"application/json"`, `"application/json; charset=utf-8"`, `"application/json-patch+json"` (parametrize over the 3) | GET `/api/v1/doc` | status 200; processed: `response.content == B_PROCESSED`; `content-length == "23"`; `content-type` header == `<ct>` | pass |
| UTCJ-D-09 | R3, R12 | side-effect | route `GET /api/v1/doc` returns `Response(content=b"plain text", media_type="text/plain")` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/api/v1/doc` | status 200; `response.content == b"plain text"`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]` | pass |
| UTCJ-D-10 | R4 | happy | route `GET /api/v1/stream` returns `StreamingResponse(iter([b'{"a":', b'"\xc3\xa9",', b'"b":1}']), media_type="application/json")` (3 chunks, concatenation = `B_COMPACT`) | GET `/api/v1/stream` | status 200; processed: `response.content == B_PROCESSED`; `response.json() == {"a": "é", "b": 1}` | pass |
| UTCJ-D-11 | R4 | boundary | route `GET /api/v1/stream` returns `StreamingResponse(iter([b'{"a":"\xc3', b'\xa9"}']), media_type="application/json")` — the chunk boundary splits the 2-byte UTF-8 `é` | GET `/api/v1/stream` | status 200; `response.json() == {"a": "é"}`; `response.content == b'{"a": "\\u00e9"}'`; `content-length == "15"` | pass |
| UTCJ-D-12 | R5 | boundary | route `GET /api/v1/empty` returns `Response(content=b"", status_code=200, media_type="application/json", headers={"X-Request-ID": "req-7"})` | GET `/api/v1/empty` | status 200; `response.content == b""`; `X-Request-ID == "req-7"`; `content-type == "application/json"`; no exception | pass |
| UTCJ-D-13 | R5 | boundary | route `DELETE /api/v1/items/1` returns `Response(status_code=204, media_type="application/json")` | DELETE `/api/v1/items/1` | status 204; `response.content == b""`; no exception | pass |
| UTCJ-D-14 | R5 | boundary | route registered for methods `["GET", "HEAD"]` at `/api/v1/head` returns `JSONResponse({"a": 1})` | HEAD `/api/v1/head` | status 200; `response.content == b""`; `content-type == "application/json"`; no exception | pass |
| UTCJ-D-15 | R4, R5 | boundary | route `GET /api/v1/stream` returns `StreamingResponse(iter([]), media_type="application/json")` (zero chunks) | GET `/api/v1/stream` | status 200; `response.content == b""`; no exception | pass |
| UTCJ-D-16 | R5, R12 | side-effect | route `GET /api/v1/empty` returns `Response(content=b"", status_code=200, media_type="application/json")` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/api/v1/empty` | status 200; `response.content == b""`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]` | pass |
| UTCJ-D-17 | R6 | happy | route `GET /api/v1/s/{code}` returns `Response(content=B_COMPACT, status_code=code, media_type="application/json")` (parametrize `code` over 201, 400, 404, 422, 500) | GET `/api/v1/s/<code>` | `response.status_code == code`; processed: `response.content == B_PROCESSED`; `content-length == "23"` | pass |
| UTCJ-D-18 | R6 | happy | route `GET /api/v1/missing` raises `HTTPException(status_code=404, detail="café")`; FastAPI's default `HTTPException` handler on the same app | GET `/api/v1/missing` | status 404; processed: `response.content == b'{"detail": "caf\\u00e9"}'`; `response.json() == {"detail": "café"}`; `content-length == str(len(response.content))` | pass |
| UTCJ-D-19 | R6 | happy | route `GET /api/v1/q` with a required query parameter `n: int`; FastAPI's default validation handler | GET `/api/v1/q?n=abc` | status 422; `response.json()["detail"][0]["loc"] == ["query", "n"]`; processed: `response.content == json.dumps(response.json()).encode()`; `content-length == str(len(response.content))` | pass |
| UTCJ-D-20 | R7, R10 | boundary | route `GET /api/v1/bad` returns `Response(content=b"not json", status_code=202, media_type="application/json", headers={"X-Request-ID": "req-1"})` | GET `/api/v1/bad` | status 202; `response.content == b"not json"` byte-for-byte; `content-length == "8"`; `content-type == "application/json"`; `X-Request-ID == "req-1"`; no exception | pass |
| UTCJ-D-21 | R7 | boundary | route `GET /api/v1/bad` returns `Response(content=b'{"a":', status_code=400, media_type="application/json")` | GET `/api/v1/bad` | status 400; `response.content == b'{"a":'`; `content-length == "5"`; no exception | pass |
| UTCJ-D-22 | R7a [BUG-522], R10 | bug | route `GET /api/v1/raw` returns `Response(content=b'"\xc3\x28"', status_code=200, media_type="application/json", headers={"X-Request-ID": "req-2"})` | GET `/api/v1/raw` | no exception raised by the client call; status 200; `response.content == b'"\xc3\x28"'` byte-for-byte; `content-length == "4"`; `content-type == "application/json"`; `X-Request-ID == "req-2"` | xfail BUG-522 — fails today on: `UnicodeDecodeError` raised (no response / 500) |
| UTCJ-D-23 | R8 | happy | route `GET /api/v1/vals` returns `JSONResponse({"z": "2026-01-05T09:30:00Z", "off": "2026-01-05T09:30:00+00:00", "d": "2026-01-05", "sp": "2026-01-05 09:30:00", "pre": "x2026-01-05T09:30:00", "h": "hello", "n": 42, "f": 1.5, "t": True, "fa": False, "nu": None})` | GET `/api/v1/vals` | status 200; `response.json()` equals that dict exactly (every string unchanged, no extra `Z`; `42`, `1.5`, `True`, `False`, `None` unchanged in value and type) | pass |
| UTCJ-D-24 | R8 | boundary | route `GET /api/v1/keys` returns `JSONResponse({"2026-01-05T09:30:00": 1, "k": "hello"})` | GET `/api/v1/keys` | status 200; `response.json() == {"2026-01-05T09:30:00": 1, "k": "hello"}` (key not given a `Z`); `list(response.json().keys()) == ["2026-01-05T09:30:00", "k"]` | pass |
| UTCJ-D-25 | R8 | happy | route `GET /api/v1/nest` returns `JSONResponse({"a": {"b": [{"c": "2026-01-05T09:30:00Z"}, ["hello", 1, None, True]]}})` | GET `/api/v1/nest` | status 200; `response.json()` equals that value exactly | pass |
| UTCJ-D-26 | R8 | happy | route `GET /api/v1/list` returns `JSONResponse(["2026-01-05", "hello", 1, True, None, {"x": "2026-01-05T09:30:00+00:00"}])` | GET `/api/v1/list` | status 200; `response.json()` equals that list exactly | pass |
| UTCJ-D-27 | R8 | happy | route `GET /api/v1/str` returns `Response(content=b'"hello"', media_type="application/json")` | GET `/api/v1/str` | status 200; `response.json() == "hello"`; `response.content == b'"hello"'` | pass |
| UTCJ-D-28 | R8 | boundary | route `GET /api/v1/near` returns `JSONResponse({"suffix": "2026-01-05T09:30:00x", "nosec": "2026-01-05T09:30"})` — strings whose *entire* content is not the naive shape | GET `/api/v1/near` | status 200; `response.json() == {"suffix": "2026-01-05T09:30:00x", "nosec": "2026-01-05T09:30"}` | pass |
| UTCJ-D-29 | R8a [BUG-520] | bug | route `GET /api/v1/note` returns `JSONResponse({"note": "2026-01-05T09:30:00"})` | GET `/api/v1/note` | status 200; `response.json() == {"note": "2026-01-05T09:30:00"}` | xfail BUG-520 — fails today on: value is `"2026-01-05T09:30:00Z"` |
| UTCJ-D-30 | R8a [BUG-520] | bug | route `GET /api/v1/frac` returns `JSONResponse(["2026-01-05T09:30:00.123456"])` | GET `/api/v1/frac` | status 200; `response.json() == ["2026-01-05T09:30:00.123456"]` | xfail BUG-520 — fails today on: item is `"2026-01-05T09:30:00.123456Z"` |
| UTCJ-D-31 | R8a [BUG-520] | bug | route `GET /api/v1/str` returns `Response(content=b'"2026-01-05T09:30:00"', media_type="application/json")` (top-level string body) | GET `/api/v1/str` | status 200; `response.json() == "2026-01-05T09:30:00"` | xfail BUG-520 — fails today on: body is `"2026-01-05T09:30:00Z"` |
| UTCJ-D-32 | R8a [BUG-520] | bug | route `GET /api/v1/deep` returns `JSONResponse({"a": {"b": [{"c": "2026-01-05T09:30:00"}]}, "h": "hello"})` | GET `/api/v1/deep` | status 200; `response.json() == {"a": {"b": [{"c": "2026-01-05T09:30:00"}]}, "h": "hello"}` | xfail BUG-520 — fails today on: `c` is `"2026-01-05T09:30:00Z"` |
| UTCJ-D-33 | R9 | happy | route `GET /api/v1/order` returns `Response(content=b'{"b":1,"a":{"y":[1,2],"x":"\xc3\xa9"}}', media_type="application/json")` | GET `/api/v1/order` | status 200; `response.content == b'{"b": 1, "a": {"y": [1, 2], "x": "\\u00e9"}}'` exactly; `list(response.json().keys()) == ["b", "a"]`; `list(response.json()["a"].keys()) == ["y", "x"]` | pass |
| UTCJ-D-34 | R10 | side-effect | route `POST /api/v1/items` returns `Response(content=B_COMPACT, status_code=201, headers={"content-type": "application/json; charset=utf-8", "X-Request-ID": "req-42"})` | POST `/api/v1/items` | status 201; processed: `response.content == B_PROCESSED`; `content-type == "application/json; charset=utf-8"`; `X-Request-ID == "req-42"`; `content-length == "23"` (recomputed, not the original `"16"`) | pass |
| UTCJ-D-35 | R11 | boundary | route `GET /api/v1/grow` returns `Response(content=b'{"a":"\xc3\xa9"}', media_type="application/json")` (10 bytes; grows on re-encoding) | GET `/api/v1/grow` | status 200; `response.content == b'{"a": "\\u00e9"}'` (15 bytes, not truncated to 10); `content-length == "15"`; `response.json() == {"a": "é"}` | pass |
| UTCJ-D-36 | R11 | boundary | route `GET /api/v1/shrink` returns `Response(content=b'{ "a" :   1 ,\n  "b" : 2 }', media_type="application/json")` (25 bytes; shrinks on re-encoding) | GET `/api/v1/shrink` | status 200; `response.content == b'{"a": 1, "b": 2}'`; `content-length == "16"`; `response.json() == {"a": 1, "b": 2}` | pass |
| UTCJ-D-37 | R11, R10 | boundary | route `GET /api/v1/stream` returns `StreamingResponse(iter([b'{"a":', b'1}']), media_type="application/json")` (downstream sends no `content-length`) | GET `/api/v1/stream` | status 200; `response.content == b'{"a": 1}'`; `content-length == "8"` | pass |
| UTCJ-D-38 | R10a [BUG-521], R10 | bug | route `GET /api/v1/login` returns `Response(content=B_COMPACT, media_type="application/json", headers={"X-Request-ID": "req-3"})` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/api/v1/login` | status 200; `response.content == B_PROCESSED`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]`; `X-Request-ID == "req-3"` | xfail BUG-521 — fails today on: `get_list("set-cookie") == ["access=a"]` |
| UTCJ-D-39 | R10a [BUG-521] | bug | route `GET /api/v1/vary` returns `Response(content=B_COMPACT, media_type="application/json")` with two appended `Vary` lines `Accept`, `Origin` | GET `/api/v1/vary` | status 200; `response.content == B_PROCESSED`; `headers.get_list("vary") == ["Accept", "Origin"]` | xfail BUG-521 — fails today on: `get_list("vary") == ["Accept"]` |
| UTCJ-D-40 | R10a [BUG-521], R7 | bug | route `GET /api/v1/bad` returns `Response(content=b"not json", status_code=202, media_type="application/json")` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/api/v1/bad` | status 202; `response.content == b"not json"`; `content-length == "8"`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]` | xfail BUG-521 — fails today on: `get_list("set-cookie") == ["access=a"]` |
| UTCJ-D-41 | R10a [BUG-521], R7a [BUG-522] | bug | route `GET /api/v1/raw` returns `Response(content=b'"\xc3\x28"', status_code=200, media_type="application/json")` with two appended `Set-Cookie` lines `access=a`, `refresh=r` | GET `/api/v1/raw` | no exception; status 200; `response.content == b'"\xc3\x28"'`; `headers.get_list("set-cookie") == ["access=a", "refresh=r"]` | xfail BUG-522, BUG-521 — fails today on: `UnicodeDecodeError` raised (and, once BUG-522 is fixed, on only `access=a` surviving) |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| R8a (resolution of BUG-520) | Response-schema datetime serializer / `tests/unit/utils/datetime_serialize.spec.md` | Real date-time fields are emitted with the UTC `Z` suffix at serialization time; free-text strings are not touched. |
| Overview "Integration-only behavior" | `app/main.py` middleware stack (integration tests) | Ordering relative to the other middlewares — which headers are present when this middleware runs. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `dispatch` | R1 | UTCJ-D-01, UTCJ-D-02, UTCJ-D-03 |
| `dispatch` | R2 | UTCJ-D-04, UTCJ-D-05, UTCJ-D-06 |
| `dispatch` | R3 | UTCJ-D-07, UTCJ-D-08, UTCJ-D-09 |
| `dispatch` | R4 | UTCJ-D-10, UTCJ-D-11, UTCJ-D-15 |
| `dispatch` | R5 | UTCJ-D-12, UTCJ-D-13, UTCJ-D-14, UTCJ-D-15, UTCJ-D-16 |
| `dispatch` | R6 | UTCJ-D-17, UTCJ-D-18, UTCJ-D-19 |
| `dispatch` | R7 | UTCJ-D-20, UTCJ-D-21, UTCJ-D-40 |
| `dispatch` | R7a [BUG-522] | UTCJ-D-22, UTCJ-D-41 |
| `dispatch` | R8 | UTCJ-D-23, UTCJ-D-24, UTCJ-D-25, UTCJ-D-26, UTCJ-D-27, UTCJ-D-28 |
| `dispatch` | R8a [BUG-520] | UTCJ-D-29, UTCJ-D-30, UTCJ-D-31, UTCJ-D-32; serializer side deferred |
| `dispatch` | R9 | UTCJ-D-33 (also exact-bytes checks in UTCJ-D-05, -08, -10, -11, -17, -18, -19, -35, -36) |
| `dispatch` | R10 | UTCJ-D-20, UTCJ-D-34, UTCJ-D-37 |
| `dispatch` | R10a [BUG-521] | UTCJ-D-38, UTCJ-D-39, UTCJ-D-40, UTCJ-D-41 |
| `dispatch` | R11 | UTCJ-D-34, UTCJ-D-35, UTCJ-D-36, UTCJ-D-37 |
| `dispatch` | R12 | UTCJ-D-06, UTCJ-D-09, UTCJ-D-16 (rebuilt side: UTCJ-D-38..41) |
| `dispatch` | Errors: downstream unhandled exception propagates | UTCJ-D-03 |
