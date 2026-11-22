# Test cases — `app/utils/work_order_calendar.py`

> **Spec:** `tests/unit/utils/work_order_calendar.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run; spec unchanged (still 0 specified callables, Q1 remove). Verifier report (PASS, Findings: none, all 4 surviving mutants classed `dead`) has no `case-missing` items, so no cases added.
> **Counts:** 0 cases · 0 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** none specified. The only callable, `work_order_calendar_date`,
  is dead code the reviewer marked for removal (spec Q1), so it gets no cases.
- **Notable design choices:** no `test_work_order_calendar.py` should be written
  under `tests/unit/utils/`, as the spec instructs. The live copies of the rule
  (the `WorkOrder` response schema's `calendar_date` field and the work-order
  DAO's `coalesce(planned_date, created_at::date)` expression) are tested with
  their own modules, not here.
- **Needs a decision:** None.

## Conventions for this module
- ID prefix `WOCAL` = work_order_calendar (reserved; no cases issued).
- Externals mocked: none.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| (informational, not a rule of this spec) calendar-day rule: planned date, else the date part of `created_at` | `WorkOrder` response schema (`calendar_date`) and work-order DAO (`_work_order_calendar_date_expr`) specs | Covered by those modules' own specs, as the spec's Overview states; listed here only so the rule is not lost when this module is removed. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `work_order_calendar_date` | Not specified — dead code, to be removed (Q1) | none (by design) |
