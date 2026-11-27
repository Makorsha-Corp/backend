# Execution notes — `app/utils/work_order_calendar.py`

> Cases: `tests/unit/utils/work_order_calendar.cases.md` (revision 2, READY, 0 cases) · Tests: none (by design) · Source commit: e48a092
> Result: 0 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage N/A (no specified callables; module is dead code)
> Run: none — there is no test file to run.

## How the tests are built
No test file was written. The cases file issues no cases (ID prefix `WOCAL`
reserved, unused), and the spec's "Notes for the test designer" says:
"Do not write a `test_work_order_calendar.py` under `tests/unit/utils/`."
The module's only callable, `work_order_calendar_date`, is dead code the
reviewer marked for removal (spec Q1). Removal is logged in
`work_order_calendar.deadcode-staging.md` (whole file plus the legacy test
`tests/test_work_order_calendar.py`, which is its only caller).

Creating an empty or placeholder test file was deliberately avoided: it would
contradict the spec and would break (ImportError) once the module is deleted
(best-practice default, delegated by reviewer).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 5-9 (`work_order_calendar_date`, both branches of `planned_date is not None`) | dead | Returns `planned_date` when set, else `created_at.date()`. Listed under the spec's Not specified as dead code to be removed (Q1). |

## Factories added
None. No builders needed; none worth promoting.

## Notes for maintainers
- When the dead-code removal lands, delete `app/utils/work_order_calendar.py`,
  `tests/test_work_order_calendar.py`, and this module's spec/cases/notes/
  deadcode-staging files together.
- The live calendar-day rule (planned date, else the date of `created_at`) is
  tested with the `WorkOrder` response schema (`calendar_date`) and the
  work-order DAO (`_work_order_calendar_date_expr`), not here.

## Revision history
- Revision 2 (cases re-run, spec unchanged, still 0 cases): no test file written, nothing to run; header updated. Verifier (PASS, no findings) routed nothing to the executor.
