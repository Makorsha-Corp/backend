# Execution notes — `app/core/exceptions.py`

> Cases: `tests/unit/core/exceptions.cases.md` (revision 5) · Tests: `tests/unit/core/test_exceptions.py` · Source commit: e48a092
> Result: 51 passed · 38 xfailed · 0 discrepancies · 0 errors — branch coverage 99% (78 stmts, 1 missed; 10 branches, 0 partial)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_exceptions.py -q -p no:cacheprovider --cov=app.core.exceptions --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented):
  - "Requests" → `make_req(**scope_overrides)` builds a `starlette.requests.Request` from the scope dict in the cases file; `REQ()`, `REQ_noid()`, `REQ_bare()`, `REQ_q()`, `REQ_nullid()`, `REQ_emptyid()` return a fresh request per call.
  - "Calling a handler" → `call(handler, request, exc)`: `raise exc`, and inside the `except` block `asyncio.run(handler(request, exc))`, so `exc_info` is live (checked as `record.exc_info[1] is exc`).
  - Shorthands → `assert_std` (STD), `assert_genid` (GENID), `assert_noleak` (NOLEAK), `log1` (LOG1; filters `caplog.records` by `name == "app.core.exceptions"`), `assert_falsyid` (FALSYID; `caplog.clear()` between (a) and (b), and the record checked is chosen by level + message, as each case says).
  - `cap` fixture = `caplog.set_level(logging.DEBUG)` (root logger, so HVAL-10 sees every logger).
  - "Real DB errors (TBL)" → `tbl` fixture creates the two TEMP tables on the `db` session; `db_error(db, sql, params)` runs the statement inside `db.begin_nested()` and returns the SQLAlchemy `DBAPIError`. `parent1`, `child(**overrides)` build the setup rows / offending child insert with every column explicit. Temp tables are per-connection and rolled back with the test transaction, so concurrent agents are unaffected. Tests that create a DB error then check logs call `cap.clear()` after the setup, before the handler call.
  - "Stand-in cause SC" → `SC(code, primary, text)` is an `Exception` subclass (so `str()` = text) with `pgcode` and a `_Diag` object carrying `message_primary`; `SC_diagnone`, `SC_nodiag` (attribute deleted), `SC_noprimary` (diag without `message_primary`) implement the R4b variants. `wrap_ie` wraps with `IntegrityError("INSERT INTO exc_booking (room) VALUES (%(room)s)", {"room": 3}, cause)`.
  - `PW()`, `OPX()`, `_hsch07_exc()` build the named fixtures from the cases file fresh per use.
- **Settings patching:** `settings.DEBUG` via `monkeypatch.setattr`. `ERROR_TYPE_BASE_URL` (BUG-467 cases): the cases say `monkeypatch.setattr(..., raising=False)`, but pydantic `BaseSettings` refuses `setattr` of an unknown field (`ValueError: "Settings" object has no field "ERROR_TYPE_BASE_URL"`), which would abort the test before the "fails today on" assertion. `set_base_url()` tries the prescribed call first and, on `ValueError`, falls back to `monkeypatch.setitem(settings.__dict__, "ERROR_TYPE_BASE_URL", value)` (undone after the test). Once the setting exists the prescribed path is used automatically. *(best-practice default, delegated by reviewer)*
- **Parametrized:** EXC-HINT-21..24 (identical setup/assertions, differing only in the stand-in cause) → one test with param ids `EXC-HINT-21` … `EXC-HINT-24`.
- **Mocks:** none (spec: externals none; `uuid.uuid4` not patched, ids checked by pattern).
- **xfail honesty:** verified with `--runxfail --tb=line`; every xfail fails at its "fails today on" assertion: BUG-467 on `type == "/errors/<slug>"` (a); BUG-468 on media type `application/json`; BUG-469 (a) `AttributeError: 'NoneType' object has no attribute 'encode'` in Starlette header encoding, HAPI-11 on GENID (`request_id == ""`); BUG-461 `400 == 422`; BUG-460 LOG1 count `4 == 1`; BUG-462/463/464/465/466 on the detail/status/title named in each case.
- Stability: 3 runs, identical (51 passed, 38 xfailed).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 57 | dead | `AuthenticationError.__init__` body — listed under "Not specified" as dead code to be removed (`exceptions.deadcode-staging.md`). |

## Factories added
None. Batch mode: `tests/unit/factories.py` not edited. Helpers worth promoting later (to a small `tests/unit/_http.py`, not the DB factories): `make_req(**scope)` (Starlette Request from a scope dict), `call(handler, request, exc)` (run an exception handler inside a live `except`), and `db_error(db, sql, params)` (capture a real driver error in a savepoint) — the middleware / deps specs could reuse them.

## Notes for maintainers
- When a BUG is fixed, its xfail tests XPASS (strict) → remove the marker: BUG-460 → HVAL-10; BUG-461 → HVAL-03; BUG-462 → HINT-13..17, HINT-21..25; BUG-463 → HINT-04; BUG-464 → HINT-09, HINT-12; BUG-465 → HINT-08; BUG-466 → HSCH-03..05; BUG-467 → HAPI-08, HVAL-11, HINT-19, HDB-04, HSCH-07, HGEN-05; BUG-468 → HAPI-09, HVAL-12, HINT-20, HDB-05, HSCH-08, HGEN-06; BUG-469 → HAPI-10/11, HVAL-13, HINT-28, HDB-06, HSCH-09, HGEN-07.
- Some xfails need more than one fix to XPASS: HINT-09 expects `validation_error` slug/title too (BUG-464 fix must also relabel); HINT-15/16 expect the BUG-464 unclassified text as well as BUG-462 classification.
- When BUG-467 adds `ERROR_TYPE_BASE_URL` to `Settings`, `set_base_url` stops using the `__dict__` fallback; the fallback can then be deleted.
- HINT-06/13/14 rely on psycopg2 including bound parameters in `str(IntegrityError)`; a driver change could change what the text search sees (only relevant while BUG-462 is open).
- `BusinessRuleError` emits a Starlette `DeprecationWarning` (`HTTP_422_UNPROCESSABLE_ENTITY`); harmless, but the constant will need renaming on a future Starlette upgrade.

## Revision history
- **Cases revision 5 (2026-09-29):** re-run only. The cases file changed no case (the same 89 IDs, no retired IDs), and no verify report exists, so no test was added, changed or removed. Only the revision reference in the test-file docstring was updated. Re-ran 3 times: 51 passed, 38 xfailed every time. Branch coverage is unchanged at 99% (line 57, dead). `--runxfail --tb=line` confirms each xfail still fails at its "fails today on" assertion.
