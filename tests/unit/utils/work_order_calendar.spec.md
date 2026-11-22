# Spec — `app/utils/work_order_calendar.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Calendar-date helper is not used by the app — 🗑️ remove
**Background:** A work order's "calendar day" (used for the work-order sheet grouping, date filters and calendar dots) is its planned date, or the day it was created when it has no planned date. This rule is implemented three times: in this helper, in the `calendar_date` field of the work-order API response schema (`app/schemas/work_order.py`), and as a SQL expression in the work-order DAO (`app/dao/work_order.py`). No application code imports this helper; only an older standalone test (`tests/test_work_order_calendar.py`) calls it.
**What happens today:** The helper exists and works, but nothing in the running product calls it; the schema and DAO each carry their own copy of the same rule.
**Example:** If someone changes the rule here (e.g. to use the workspace's local day), the calendar the user sees does not change at all, because the API response and the DAO filters use their own copies.
**Rules affected:** `work_order_calendar_date` R1, R2
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** `work_order_calendar_date` is dead code, to be removed; it is the module's only callable, so the whole file `app/utils/work_order_calendar.py` goes, together with the legacy test `tests/test_work_order_calendar.py` (best-practice default, delegated by reviewer). Logged in `work_order_calendar.deadcode-staging.md`. Not a bug — no BUG ID. The live copies of the rule (schema `calendar_date`, DAO `_work_order_calendar_date_expr`) are specified with their own modules.

## Overview
Pure helper that decided which calendar day a work order belongs to (planned
date, else the date part of its creation timestamp). It has no production
callers and the reviewer marked it for removal (Q1); the live copies of the
rule are the `WorkOrder` response schema's `calendar_date` computed field and
the DAO's SQL `coalesce(planned_date, created_at::date)`, which are specified
and tested with those modules.

**Callables:** 0 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** nothing to test in this module — every
callable is dead code scheduled for removal. Do not write a
`test_work_order_calendar.py` under `tests/unit/utils/`.

## Not specified
- `work_order_calendar_date` — dead code, to be removed (reviewer)

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| — | no specified callables (module is dead code) | — |
