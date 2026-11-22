# Verification — `app/utils/work_order_calendar.py`

> **Verdict:** PASS
> Tests: 0 passed · 0 xfailed (reproduced ✅: nothing to run, matches notes) · coverage N/A (module is dead code, no specified callables)
> Mutation: 4 mutants · 0 killed by the unit suite (no unit test file, by design) · 4 not killed → score N/A (after excluding 0 equivalent, 4 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The module's only callable, `work_order_calendar_date`, was marked for removal
by the reviewer (spec Q1), so the spec specifies nothing, the cases file
(revision 2) issues no cases, and the executor correctly wrote no
`tests/unit/utils/test_work_order_calendar.py`. I re-checked the dead-code claim
independently: nothing under `app/` or `alembic/` imports
`app.utils.work_order_calendar`; its only importer is the legacy test
`tests/test_work_order_calendar.py`. Every mutant is therefore on `dead` code.
Nothing needs fixing in the test pipeline; the remaining work is the removal
itself, already logged in `work_order_calendar.deadcode-staging.md`.

## Findings
None.

## Surviving mutants
With no unit test file, all 4 mutants the tool generates go unkilled by the
pipeline's unit suite. All are classed `dead` (spec "Not specified": dead code,
to be removed, Q1).

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L7 | negate if-condition (`if not (planned_date is not None)`) | dead | Inside `work_order_calendar_date`, which the spec lists as dead code to be removed (Q1); no app code imports it | — |
| 2 | L7 | `is not` -> `is` | dead | Same function, dead code (Q1) | — |
| 3 | L8 | `return planned_date` -> `return None` | dead | Same function, dead code (Q1) | — |
| 4 | L9 | `return created_at.date()` -> `return None` | dead | Same function, dead code (Q1) | — |

Informational cross-check: the legacy test `tests/test_work_order_calendar.py`
(outside this pipeline, slated for deletion with the module) kills all 4
mutants (score 100%), so the helper behaves as the spec's Overview describes
until it is removed.

## Traceability
cases 0 · tests 0 · unmatched: none · marker mismatches: none · BUG IDs used: none.
The cases file reserves prefix `WOCAL` and issues no IDs; no
`tests/unit/utils/test_work_order_calendar.py` exists, as spec and cases require.
Notes header references cases revision 2 / READY / 0 cases — consistent.

Dead-code check (grep over `app/`, `tests/`, `alembic/`):
- `app/utils/work_order_calendar.py:5` — the definition itself
- `tests/test_work_order_calendar.py:5` — legacy test, only importer
- `app/dao/work_order.py:16,86,312` / `tests/test_work_orders_sheet_pagination.py` — only `_work_order_calendar_date_expr` (the DAO's own copy of the rule), not this module

## Commands run
```
grep -rn "utils.work_order_calendar\|import work_order_calendar_date\|work_order_calendar_date" --include=*.py app tests alembic
  -> only importer of app.utils.work_order_calendar is tests/test_work_order_calendar.py

# pytest / coverage / --runxfail / flakiness re-runs: not run — there is no unit test
# file (0 cases, by design); notes' Result line ("0 passed · 0 xfailed · 0 discrepancies
# · 0 errors — coverage N/A") is consistent.

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/work_order_calendar.py tests/test_work_order_calendar.py --timeout 180 --json %TEMP%/woc_mut_v2.json
  [1/4] L7:4 if     negate if-condition   KILLED
  [2/4] L9:4 return return None           KILLED
  [3/4] L7:7 cmp    IsNot -> Is           KILLED
  [4/4] L8:8 return return None           KILLED
  Mutants: 4 · killed 4 · timeout 0 · survived 0 · score 100%   (legacy test; informational only)
```
