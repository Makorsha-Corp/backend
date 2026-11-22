# Execution notes — `app/core/utc_json_middleware.py`

> Cases: `tests/unit/core/utc_json_middleware.cases.md` (revision 3) · Tests: `tests/unit/core/test_utc_json_middleware.py` · Source commit: e48a092
> Result: 47 passed · 9 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (41 cases; 56 test items because D-04/05/07/08/17 are parametrized)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_utc_json_middleware.py -q -p no:cacheprovider --cov=app.core.utc_json_middleware --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no mocks** (spec: externals none). The `db` fixture is never requested, so these tests do not touch Postgres.
- **Conventions → helpers** (top of the test file, each commented):
  - "Harness" → `make_app()` (fresh `FastAPI()` + `add_middleware(UtcJsonResponseMiddleware)`) and `client_for(app)` (`TestClient(app)`, default `raise_server_exceptions=True`). Each test defines only its own routes inside the test body.
  - "Standard bodies" → module constants `B_COMPACT` (16 B), `B_PROCESSED` (23 B), `B_DT` (36 B); a module-level `assert` pins the lengths the cases rely on.
  - "Repeated headers" → `with_repeated(resp, name, values)` / `with_cookies(resp)`: `resp.headers.append(...)` on the route's Response before returning it. Read back with `response.headers.get_list(...)`.
  - "Call counter" → small `Counter` class captured by the route closure, reset to 0 before the call.
  - "processed" → `assert_processed(response, expected_bytes)` (exact bytes + `content-length == len(content)`); most cases spell the exact `content-length` value out inline as the cases file gives it.
- **Parametrized:** UTCJ-D-04 (5 paths), -05 (2 paths), -07 (5 media types), -08 (3 content types), -17 (5 status codes). Param ids are `UTCJ-D-NN-<variant>` so every case stays visible.
- **xfail honesty:** verified with `--runxfail`. D-22 and D-41 fail with `UnicodeDecodeError` (BUG-522); D-29..32 fail on the value carrying an extra `Z` (BUG-520); D-38/39/40 fail on `get_list(...)` returning only the first value (BUG-521). All match the "fails today on" column.
- Stability: 3 runs, identical outcome each time (47 passed, 9 xfailed).
- UTCJ-D-23: "unchanged in value and type" implemented as dict equality plus `type(...) is int/float` and `is True/False/None` checks.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage of `app.core.utc_json_middleware` (29 statements, 8 branches). (`app.utils.datetime_serialize` shows 62% in the same report because it is pulled in by import; it is owned by its own spec and not a target here.)

## Factories added
None. Batch mode: `tests/unit/factories.py` not edited. Helpers worth promoting later if other middleware tests need them: `make_app()`-style "minimal FastAPI app with one middleware" builder and `with_repeated(resp, name, values)` for repeated-header responses (candidate home: a small `tests/unit/_http.py` helper module, not the DB factories).

## Notes for maintainers
- When BUG-520 is fixed (middleware stops tagging strings / is removed in favour of a serializer), D-29..32 will XPASS → remove their markers. If the middleware is removed entirely, retire this whole file together with the spec.
- When BUG-521 is fixed, D-38/39/40 XPASS → remove markers. D-41 needs BOTH BUG-521 and BUG-522 fixed before it passes.
- When BUG-522 is fixed, D-22 XPASS → remove marker.
- Starlette 1.4 emits a `StarletteDeprecationWarning` about `httpx` with `TestClient` (suggests `httpx2`); harmless today, but a future Starlette upgrade may require switching the client dependency.
- Tests rely on Starlette's own `content-length` for pass-through responses (downstream Response sets it); a change in Starlette's header-emission would surface in D-04/07/20/21.

## Revision history
- **Cases revision 3 (2026-09-29):** cases file re-issued with no case changes, no new IDs, no retired IDs (verify.md verdict PASS, no executor findings). Test file left unchanged. Re-ran: 47 passed · 9 xfailed, identical across 3 runs; `--runxfail` still fails exactly the 9 bug cases on their named assertions; branch coverage 100%. Tip for parallel batch runs: set `COVERAGE_FILE` to a private path — the shared `.coverage` file in the repo root is locked by concurrent agents on Windows (`PermissionError: WinError 32`).
