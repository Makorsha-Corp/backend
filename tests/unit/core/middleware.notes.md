# Execution notes — `app/core/middleware.py`

> Cases: `tests/unit/core/middleware.cases.md` (revision 4) · Tests: `tests/unit/core/test_middleware.py` · Source commit: e48a092
> Result: 64 passed · 48 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (51 cases; 112 test items because parametrized cases have one param id per variant)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_middleware.py -q -p no:cacheprovider --cov=app.core.middleware --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database.** Both middlewares are pure; no test asks for the `db` fixture, so Postgres is never touched.
- **Conventions → helpers** (top of the test file, each commented):
  - "App under test" → `make_app(*middlewares)` = `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` plus `add_middleware` for each one given. `rc_app()` and `sh_app()` are shortcuts. MW-SH-18/19 use `make_app(SecurityHeadersMiddleware, RequestContextMiddleware)`: the middleware added last is the outermost, so RC wraps SH. Small route builders: `html_route`, `add_echo_id`, `add_status_route(prefix)`, `add_plain`.
  - "Direct dispatch" → `make_request(**overrides)` builds the scope dict from the cases file. Passing the sentinel `_MISSING` removes a key (for example `client=_MISSING`). `ok_call_next()` returns `(resp, call_next)`, so a test can assert `result is resp`. `raising_call_next(exc)` builds a `call_next` that raises. The coroutine runs with `asyncio.run(RequestContextMiddleware(app=None).dispatch(...))`, and the same way for SH.
  - "Fixed request id" → fixture `id1` patches `app.core.middleware.uuid.uuid4`. This patches the attribute on the global `uuid` module, so it also applies while the TestClient's portal thread runs the app.
  - "Fixed time" → `T(start, end)` is a context manager that patches `app.core.middleware.time.time` (first call returns start, every later call returns end). It is used only around `asyncio.run(dispatch(...))` in direct-dispatch cases (MW-RC-22/23/25).
  - "Logs" → fixture `logs` sets `caplog` to DEBUG for `app.core.middleware` and `app.core.exceptions`. Helpers `started`, `completed` and `unexpected` filter by logger name and exact `getMessage()`. `one_started` and `one_completed` also assert "exactly one".
  - "Security header defaults" → the tuples `XCTO`, `XFO`, `HSTS`, `XXSS`, `CSP` and `THREE`. `assert_headers(resp, specs, exactly_one=...)` uses `get_list(name) == [value]` when the case says "exactly one value" and `headers.get(name) == value` otherwise. `assert_no_csp`.
  - "Prefix setting" → `monkeypatch.setattr(app.core.config.settings, "API_V1_STR", "/api/v2")`, applied before the app is built (MW-SH-09/10).
- **Patch targets:** only `uuid.uuid4` and `time.time`, both reached through `app.core.middleware`. There are no other mocks and no race simulations.
- **Parametrized:** MW-RC-09/10/12/15/18/19/20/21/27 and MW-SH-02/05/06/07/08/09/12/16. Param ids have the form `<CASE-ID>-<variant>`.
- **xfail honesty:** checked with `--runxfail`. Each xfail fails on the assertion named in "fails today on":
  - BUG-480: the `query_params` value is logged verbatim (RC-08/09/10/28).
  - BUG-481: the level is 40, not 30 (RC-20).
  - BUG-482: 0 completed records (RC-25).
  - BUG-483: `RuntimeError`/`KeyError` escapes the client or `dispatch` (SH-18/19/22/23).
  - BUG-484: `X-Content-Type-Options` is absent (SH-12/13).
  - BUG-485: CSP is missing on look-alike paths or present on `/api/v2` docs (SH-08/09/10).
  - BUG-486: the header is `1; mode=block` (SH-03).
  - BUG-487: the route's value is overwritten (SH-16/17).
- **Stability:** 3 runs gave the same outcome each time.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage of `app.core.middleware` (31 statements, 4 branches).

## Factories added
None. Batch mode, so `tests/unit/factories.py` was not edited. Helpers worth promoting later, for example to a small `tests/unit/_http.py` shared with `test_utc_json_middleware.py`, which has similar builders:
- `make_app(*middlewares)`, a minimal FastAPI app with the built-in docs routes disabled;
- `make_request(**overrides)` with the `_MISSING` sentinel, plus `ok_call_next`/`raising_call_next` for direct middleware dispatch;
- `assert_headers(resp, specs, exactly_one)`.

## Notes for maintainers
- When a BUG-NNN is fixed, its xfail tests will XPASS (strict → fail), so remove those markers:
  - BUG-480: RC-08/09/10/28.
  - BUG-481: RC-20.
  - BUG-482: RC-25.
  - BUG-483: SH-18/19/22/23.
  - BUG-484: SH-12/13.
  - BUG-485: SH-08/09/10.
  - BUG-486: SH-03.
  - BUG-487: SH-16/17.
- Some tests need more than one fix before they pass:
  - SH-12 needs BUG-484 and BUG-486.
  - SH-13 needs BUG-484, BUG-486 and BUG-487.
  - SH-16 needs BUG-487, and BUG-486 for its XXSS default check (variants a, c, d).
  - SH-18/19/22/23 need BUG-483 and BUG-486, because they assert `X-XSS-Protection == "0"`.
- MW-RC-19 asserts `levelno >= WARNING`, so it passes both today (ERROR) and after the BUG-481 fix (WARNING).
- Mock payment-gateway page (spec Q8): TODO, deferred in the cases file per the reviewer. Remove it, or upgrade it / limit it to non-prod. Once BUG-487 is fixed it can set its own CSP. It is not tested here.
- `T` relies on Python 3.12 `logging` using `time.time_ns()`, not `time.time()`. Either way the "first call → start, later → end" design stays correct as long as nothing calls `time.time` between building the coroutine and the middleware's `start_time`.
- Starlette emits a `StarletteDeprecationWarning` about `httpx` with `TestClient`. It is harmless for now.

## Revision history
- **Revision 4 (cases rev 4, 2026-09-29):** The cases file added the "Return value (every case)" convention (best-practice default, delegated by reviewer), and MW-RC-16 now asserts the returned response. The test file implements it with the local helper `assert_returned(resp, status, json_body=/text=/content=)`: every `TestClient` case asserts the route's status and, where the route has a body, that the body is unchanged. Direct-dispatch cases assert `result is resp` (RC) or the stated 500 (SH-23). No case was added or retired, and no test was deleted. Re-run: 64 passed, 48 xfailed, stable over 3 runs, 100% branch coverage. `--runxfail` confirms that every xfail still fails on its "fails today on" assertion.
