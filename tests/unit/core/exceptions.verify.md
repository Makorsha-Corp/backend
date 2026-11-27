# Verification — `app/core/exceptions.py`

> **Verdict:** PASS
> Tests: 51 passed · 38 xfailed (reproduced ✅) · coverage 99% branch (78 stmts, 1 missed — line 57, dead; 10 branches, 0 partial)
> Mutation: 172 mutants · 163 killed · 9 survived → score 100% (after excluding 0 equivalent, 3 dead, 6 bug-path; raw tool score 95%)
> Source commit: e48a092 · Cases revision: 5

## Summary
These tests can be trusted. All 89 cases map one-to-one to tests (86 functions; EXC-HINT-21..24 are a parametrized test with per-case ids), every xfail is `strict=True` with the right BUG reason, and `--runxfail` shows each one failing on the "fails today on" assertion the case names (not on setup or import errors). The run matches the executor's notes exactly and was stable across three runs. Every surviving mutant is either in the dead `AuthenticationError` class or on a line whose current behaviour is a tagged bug (BUG-460, BUG-462, BUG-464), so only xfail tests target it. Nothing needs fixing.

## Findings
None.

Notes (not findings):
- BUG-460…469 are not yet in `docs/testing/bugs.md`. They are defined in `tests/unit/core/exceptions.bugs-staging.md`, which is merged into the register later by the batch merge agent. Every BUG ID used by a marker exists there. *(best-practice default, delegated by reviewer: in batch mode, staged bug IDs count as existing)*
- `set_base_url()` falls back to `monkeypatch.setitem(settings.__dict__, …)` when pydantic refuses `setattr` of the not-yet-existing `ERROR_TYPE_BASE_URL` field. This is still the settings patch the cases prescribe (not an extra mock). It is recorded in the notes and undone after each test. `--runxfail` confirms that the BUG-467 tests reach their `type == "/errors/<slug>"` assertion.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 9 | 223 | `"A database constraint was violated. The resource may already exist."` → `''` | bug-path | This is today's R6 default detail, which BUG-464 / R6a replaces. Only xfail cases EXC-HINT-12/15/16 assert the R6 detail. The R6 pass cases (HINT-02, HINT-11) assert the shape only, by design. | — |
| 10 | 227 | `"unique" in s or "duplicate" in s` → `and` | bug-path | This is the text-substring classification that BUG-462 / R2 replaces with pgcode classification. A real 23505 message contains both words, so the pass cases cannot tell `and` from `or`. The xfail cases EXC-HINT-13/15/17 target this line. | — |
| 12 | 56 | `AuthenticationError` default detail → `''` | dead | Spec "Not specified": `AuthenticationError` is dead code to be removed (`exceptions.deadcode-staging.md`). | — |
| 63 | 59 | `"authentication_error"` → `''` | dead | Same as #12. | — |
| 64 | 60 | `"Authentication Error"` → `''` | dead | Same as #12. | — |
| 44 | 175 | `"[VALIDATION] Request validation failed…"` → `''` | bug-path | These extra ERROR records are the BUG-460 behaviour that R6a removes. The xfail case EXC-HVAL-10 targets them. | — |
| 45 | 175 | `' '` (separator in that f-string) → `''` | bug-path | Same log line as #44 (BUG-460). | — |
| 46 | 176 | `"[VALIDATION] Full error details…"` → `''` | bug-path | BUG-460 (the raw-input log record). | — |
| 47 | 177 | `"[VALIDATION] Formatted errors…"` → `''` | bug-path | BUG-460. | — |

## Traceability
cases 89 (51 pass · 38 xfail) · test functions 86 (89 ids including the 4 `pytest.param` ids for EXC-HINT-21..24) · unmatched: none · tests without a case ID: none · duplicate IDs: none · marker mismatches: none. Every `pass` case is unmarked; every `xfail BUG-NNN` case has `xfail(strict=True, reason=BUG_NNN)` naming exactly that BUG. The check was done with an AST script over decorators and docstrings.

Fidelity review: every test was read against its Given / When / Then. No missing or weakened assertions, no changed expectations, no swallowed failures (`call()` catches only the exception it raised itself, so the handler's own errors propagate; `db_error()` raises `AssertionError` if the statement does not fail), and no mocks (only `settings.DEBUG` / `ERROR_TYPE_BASE_URL` are patched, as the cases say). Real SQLSTATE errors come from TEMP tables inside a savepoint, as the TBL convention says. Write-and-reread checks do not apply, because the module keeps no database state.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_exceptions.py -q -p no:cacheprovider --cov=app.core.exceptions --cov-branch --cov-report=term-missing
  app\core\exceptions.py  78  1  10  0  99%  57
  51 passed, 38 xfailed, 3 warnings in 6.38s

.venv/Scripts/python.exe -m pytest tests/unit/core/test_exceptions.py -q -p no:cacheprovider --runxfail -rf --tb=line
  38 failed, 51 passed, 3 warnings in 2.01s
  (each failure is on its case's "fails today on" assertion: BUG-467 type '/errors/<slug>'; BUG-468 'application/json';
   BUG-469 AttributeError 'NoneType'.encode (None) / GENID regex (""); BUG-461 400 == 422; BUG-460 LOG1 count;
   BUG-462/463/464/465/466 on the named detail/status/title)

.venv/Scripts/python.exe -m pytest tests/unit/core/test_exceptions.py -q -p no:cacheprovider   (x2, flakiness)
  51 passed, 38 xfailed, 3 warnings in 3.47s
  51 passed, 38 xfailed, 3 warnings in 3.23s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/exceptions.py tests/unit/core/test_exceptions.py --timeout 180 --json <scratchpad>/exc_mut.json
  Mutants: 172 · killed 163 · timeout 0 · survived 9 · score 95%
```
