# Execution notes — `app/core/limiter.py`

> Cases: `tests/unit/core/limiter.cases.md` (READY, Revision 3, 11 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/core/test_limiter.py` · Source commit: e48a092
> Result: **11 tests for 11 cases — 11 passed · 0 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (3 statements, 0 branches, 0 missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_limiter.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. A scratch audit (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctx\audit.py`) checked each ID once and in card order, the docstring, `# Then 1..N` against the card's Then count with a check in each block, the marker against the Expect line, every quoted literal of the Then lines, and LF endings: 0 problems.

## How the tests are built
- **No database, nothing mocked.** The autouse `reset_limiter` fixture calls `limiter.reset()` before and after every test (also when it fails).
- **APP / APP_NO_HANDLER** = `build_app(with_handler=True/False)`, built per test exactly as the Conventions list it (`app.state.limiter`, the handler line only for APP, `SlowAPIMiddleware`, `GET /limited` and `GET /second` with `@limiter.limit("2/minute")` and `request: Request`, `GET /free` undecorated).
- **Unique route function names.** slowapi registers a decorated route's limits on the shared limiter under `"<module>.<function name>"`, and a second registration under the same name *adds* the limit again (two "2/minute" limits on one counter would refuse the second request). Each built app therefore names its functions `limited_<n>`, `second_<n>`, `free_<n>`. Paths, limits and the limiter's settings are the Conventions' own; nothing on the limiter is patched.
- **CALLS:** `build_app(..., calls=...)` takes the test's fresh `{"limited": 0}` (LIM-08 passes its own); otherwise each built app gets a fresh one. The `/limited` route adds 1 per run.
- **Clients:** `C1 = TestClient(app)` (address `testclient`), `C5 = TestClient(app, client=("5.5.5.5", 1))`. Given lines of the form "returns 200 / the third returns 429" are asserted as preconditions.
- **req(client)** builds `starlette.requests.Request` from the scope in the Conventions; LIM-02 adds the two raw header pairs.

## xfail check
No xfail card. LIM-08 (Revision 2) is a pass card: 429, `{"detail": "2 per 1 minute"}`, and `CALLS["limited"] == 2`.

## Discrepancies
None (Revision 2). Revision 1's DISCREPANCY-1 (LIM-08 expected `RateLimitExceeded` to escape; it subclasses Starlette's `HTTPException`, so FastAPI's built-in handler answers 429 `{"detail": …}`) was resolved by the spec's Gap log G1; the marker is removed.

## Coverage gaps
None — 100% line and branch coverage of `app/core/limiter.py` (3 statements; private `COVERAGE_FILE`).

## Factories added
None.

## Stability
Revision 1: 5 runs, 10 passed and 1 xfailed each. Revision 2: 3 runs, 11 passed each. The fixed window starts at the first hit (`limits` MemoryStorage sets the expiry on the first `incr`), so a test's requests cannot fall into two windows; no card compares clock stamps. `ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- If slowapi stops accumulating limits per function name, the unique-name helper can go; it does no harm meanwhile.

## Revision history
- **Revision 2 (2026-11-03):** patched, not regenerated. LIM-08 rewritten as now designed (429 `{"detail": "2 per 1 minute"}` with no slowapi handler; the route ran twice); DISCREPANCY-1 marker removed; the `/limited` route counts its runs in CALLS (Conventions). Other tests unchanged. Re-run: 3 runs, `--runxfail` (no failure), reference plugin (its old limiter hook dropped: the spec now states today's behavior), ruff, audit 0 problems, coverage 100%.

- **Revision 3 (2026-11-03):** patched. LIM-01 gains Then 9 (`not lim._key_prefix`) and Then 10 (`lim._swallow_errors is False`); nothing else changed. Re-run: 3 runs, 11 passed each; `--runxfail` no failure; reference 11 / 11; ruff; audit 0 problems; coverage 100%.
  **Verifier's variants rebuilt** (`acctx\variants.py`, a constructor rewrite of the module singleton, `--runxfail`): `lim_r5_prefix` (`key_prefix="mk"`) fails LIM-01 at Then 9; `lim_r7_swallow` (`swallow_errors=True`) fails LIM-01 at Then 10; 10 others pass in both.
