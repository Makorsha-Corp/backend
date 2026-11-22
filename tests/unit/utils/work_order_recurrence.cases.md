# Test cases — `app/utils/work_order_recurrence.py`

> **Spec:** `tests/unit/utils/work_order_recurrence.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision 3 (history):** spec Gap log G1–G3 closed my gaps 1–3: the schemas' minimal valid payload is now given (Conventions updated); new rule ADV R10a (a `recurrence_day` on a `daily` or untyped non-recurring template is accepted and kept as sent) → new WOR-ADV-33..35, WOR-ADV-27 gains a `recurrence_day=9` variant, update-template part deferred; new rule ADV R4b (`WorkOrderTemplateUpdate` alone does no day-range check) → new WOR-ADV-36. No verify report exists. All earlier IDs kept.
> **Revision:** 5 — re-run on the unchanged spec (no new Gap log entries, verify.md unchanged since rev 4). Self-check fix: the "builds without error" part of xfail WOR-ADV-22 / WOR-ADV-24 holds today but no pass case checked it → new pass case WOR-ADV-37 (padded / mixed-case supported types are accepted by both schemas and equal the supported value after trim + lower-case; holds today and after the BUG-360 fix) (best-practice default, delegated by reviewer). WOR-APR-04 Then now names `returns None` explicitly (was only in the section preamble; verify finding #1 stays fix-by executor). No IDs retired.
> **Revision 4 (history):** re-run after verification (verify.md, cases rev 3, verdict NEEDS WORK). Spec Gap log unchanged (G1–G3 already applied in rev 3). No finding is routed to the case designer: finding #1 (WOR-APR-04 missing `is None` assertion) is fix-by executor — the case already requires it via the `_apply_recurrence_range` preamble, so no case change. Surviving mutants: #38/#39/#74 equivalent (#74 is the R7 upper clamp already predicted in the Reviewer summary); #7/#28/#78/#40 are on the BUG-360/361 fallback path and will be killed by existing cases (ADV-01/02/03, ADV-19, ADV-20, APR-09, SEED-07, RESEED-06) once the bug is fixed — no new case can kill them today without testing the buggy path (best-practice default, delegated by reviewer). No cases added, changed or retired.
> **Revision history:** 4 and 3 — see lines above. 2 — re-run on the unchanged spec; open gaps given best-practice decisions.
> **Counts:** 82 cases · 70 expected-to-pass · 12 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `validate_recurrence_span` 6 · `advance_next_generation_date` 37 (9 bug; 17 of them build the template schemas directly) · `_apply_recurrence_range` 11 (1 bug) · `seed_recurrence_from_planned_date` 7 (1 bug) · `reseed_recurrence_program` 6 (1 bug) · `is_recurrence_program_active` 7 · `should_advance_template` 8
- **Notable design choices:**
  - The module is pure: no database rows, no mocks. The template is a `types.SimpleNamespace` with the six attributes the spec lists. "Unchanged" means all six attributes still equal their values before the call.
  - Schema rules R4a / R4b / R7a / R10a / R11a / R11b (BUG-360..362) are tested by building `WorkOrderTemplateCreate` / `WorkOrderTemplateUpdate` directly, using the minimal valid payload the spec gives (`template_name="T"`, `work_order_type_id=1`).
  - R4b and R10a are "no new rejection" rules that hold today and after the fixes, so their cases are plain passing cases: they guard against the BUG-360/362 fixes over-reaching (e.g. a range check on daily templates, or on the update schema alone).
  - The merged-state checks in `update_template` and the R8a fill of `recurrence_day` go to `WorkOrderTemplateManager`, because they need stored values (see Deferred).
  - The R7 high clamp (above 31 → 31) cannot be seen from outside: the R6 cap to the month's last day gives the same date. ADV-16 still asserts the documented results, but a mutant that removes only the upper clamp will survive. That is expected, not a missing case.
  - Every range boundary is tested on both sides: 0 / −1 days, 183 / 184 days, end date = target / target − 1 / target + 1, and next date = target / target ± 1.
- **Needs a decision:** none. The three earlier gaps were closed by the spec (G1–G3); no new gaps.

## Conventions for this module

- **Abbreviations:** `WOR` = work_order_recurrence. Callables: `VS` = `validate_recurrence_span`, `ADV` = `advance_next_generation_date`, `APR` = `_apply_recurrence_range`, `SEED` = `seed_recurrence_from_planned_date`, `RESEED` = `reseed_recurrence_program`, `ACT` = `is_recurrence_program_active`, `SHA` = `should_advance_template`. IDs are `WOR-<callable>-NN`.
- **No database, no mocks.** Nothing here touches the session. Tests import the functions (including the private `_apply_recurrence_range`) from `app.utils.work_order_recurrence` and call them directly. Externals to mock: none. Race simulations: none.
- **Template stand-in `T(...)`:** a `types.SimpleNamespace(is_recurring=..., recurrence_type=..., recurrence_day=..., recurrence_start_date=..., recurrence_end_date=..., next_generation_date=...)`. Any attribute a case does not list uses the **prior state P**: `is_recurring=True`, `recurrence_type` as given, `recurrence_day=4`, `recurrence_start_date=2025-01-01`, `recurrence_end_date=2025-02-01`, `next_generation_date=2025-01-15`.
- **"Unchanged"** means that after the call all six attributes still equal their values before the call. Take a snapshot with `vars(t).copy()` before the call and compare with `==` after it.
- **Weekday reference (2026):** 2026-03-02 Mon · 2026-03-04 Wed · 2026-03-30 Mon · 2026-12-31 Thu. Monday = 0 … Sunday = 6.
- **Error messages:** assert `str(exc) == <exact text>`, not a regex. The span texts are `E_BACK` = `Recurrence end date must be on or after the start date` and `E_SPAN` = `Recurrence range cannot exceed 183 days (~6 months)`.
- **Parametrised cases:** when a case lists several inputs (→), the executor may parametrise it. Each parameter must meet the case's Then, and for xfail cases each parameter must fail today.
- **Booleans:** results of `ACT` and `SHA` are asserted with `is True` / `is False`, never by truthiness.
- **Schema cases (target `schema`):** build `WorkOrderTemplateCreate` / `WorkOrderTemplateUpdate` from `app/schemas/work_order_template.py` as `Schema(**payload)`. Every `WorkOrderTemplateCreate(...)` below implicitly also passes `template_name="T", work_order_type_id=1` (the only required fields; the type's existence is not checked); fields not named keep their defaults (`is_recurring` `False`, `recurrence_*` and `next_generation_date` `None`). `WorkOrderTemplateUpdate` has no required fields, so only the named fields are passed. "Rejected" means `pydantic.ValidationError` is raised, and the error's `loc` includes `recurrence_type`, `recurrence_day`, or the model root (for a model-level validator). No database is involved, so "nothing is stored" holds by construction.

## `validate_recurrence_span`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-VS-01 | R2 | boundary | — | `validate_recurrence_span(2026-03-02, 2026-03-02)` | returns `None`; no error | pass |
| WOR-VS-02 | R1 | boundary | — | `validate_recurrence_span(2026-03-02, 2026-03-01)` (−1 day) | raises `ValueError`, `str(exc) == E_BACK` | pass |
| WOR-VS-03 | R1, R5 | error | — | `validate_recurrence_span(2026-12-31, 2026-01-01)` (−364 days, far beyond 183) | raises `ValueError`, `str(exc) == E_BACK` (not `E_SPAN`) | pass |
| WOR-VS-04 | R3 | boundary | — | `validate_recurrence_span(2026-01-01, 2026-07-03)` (exactly 183 days) | returns `None`; no error | pass |
| WOR-VS-05 | R4 | boundary | — | `validate_recurrence_span(2026-01-01, 2026-07-04)` (184 days) | raises `ValueError`, `str(exc) == E_SPAN` | pass |
| WOR-VS-06 | R4 | error | — | `validate_recurrence_span(2026-01-01, 2027-01-01)` (365 days) | raises `ValueError`, `str(exc) == E_SPAN` | pass |

## `advance_next_generation_date`

All calls use keywords: `advance_next_generation_date(from_date=..., recurrence_type=..., recurrence_day=...)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-ADV-01 | R1 | happy | — | from 2026-03-02, `"daily"`, day `None` | returns `date(2026, 3, 3)` | pass |
| WOR-ADV-02 | R1 | boundary | — | `"daily"`, day `None`: from 2026-02-28 → ; from 2026-12-31 → | returns 2026-03-01; returns 2027-01-01 | pass |
| WOR-ADV-03 | R10 | boundary | — | from 2026-03-02, `"daily"`, day each of `0`, `45`, `-1`, `3` | every call returns 2026-03-03 | pass |
| WOR-ADV-04 | R2, R9 | happy | — | from Wed 2026-03-04, `"weekly"`, day `None` | returns 2026-03-11 (+7 days) | pass |
| WOR-ADV-05 | R3, R9 | happy | — | from Wed 2026-03-04, `"weekly"`, day `0` | returns 2026-03-09 (next Monday; differs from the `None` path's 2026-03-11, so `0` is not treated as missing) | pass |
| WOR-ADV-06 | R3 | boundary | — | from Wed 2026-03-04, `"weekly"`, day `2` (Wednesday) | returns 2026-03-11 (same weekday → +7, never `from_date` itself) | pass |
| WOR-ADV-07 | R3 | boundary | — | from Wed 2026-03-04, `"weekly"`, day `3` (Thursday) | returns 2026-03-05 (1 day ahead) | pass |
| WOR-ADV-08 | R3 | boundary | — | from Wed 2026-03-04, `"weekly"`, day `1` (Tuesday) | returns 2026-03-10 (6 days ahead) | pass |
| WOR-ADV-09 | R3 | boundary | — | `"weekly"`: from Mon 2026-03-30 day `2` → ; from Thu 2026-12-31 day `0` → | returns 2026-04-01; returns 2027-01-04 | pass |
| WOR-ADV-10 | R4 | boundary | — | from Wed 2026-03-04, `"weekly"`, day each of `7`, `-1`, `10`, `9` | returns 2026-03-09 (7→Mon), 2026-03-08 (−1→Sun), 2026-03-05 (10→Thu), 2026-03-11 (9→Wed = same weekday → +7); no error | pass |
| WOR-ADV-11 | R5 | happy | — | `"monthly"`, day `15`: from 2026-01-10 (target still ahead this month) → ; from 2026-01-15 (on target) → ; from 2026-01-20 (target passed) → | all three return 2026-02-15 (2026-01-15 is never returned) | pass |
| WOR-ADV-12 | R5 | boundary | — | from 2026-12-10, `"monthly"`, day `5` | returns 2027-01-05 (year rollover) | pass |
| WOR-ADV-13 | R6 | happy | — | `"monthly"`, day `31`: from 2026-01-15 ; 2028-01-15 ; 2026-03-15 ; 2026-12-15 | returns 2026-02-28 ; 2028-02-29 ; 2026-04-30 ; 2027-01-31 | pass |
| WOR-ADV-14 | R6 | boundary | — | `"monthly"`, from 2026-01-15, day `28` → ; day `29` → ; from 2026-03-15, day `30` → ; day `31` → | 2026-02-28 (not capped); 2026-02-28 (capped); 2026-04-30 (not capped); 2026-04-30 (capped) | pass |
| WOR-ADV-15 | R7, R9 | boundary | — | from 2026-01-10, `"monthly"`, day each of `0`, `-5`, `1` | all return 2026-02-01; no error (day `0` targets the 1st, not `from_date`'s day 10) | pass |
| WOR-ADV-16 | R7 | boundary | — | `"monthly"`: from 2026-01-10 day `45` → ; from 2026-02-10 day `45` → ; from 2026-02-10 day `32` → ; from 2026-02-10 day `31` → | 2026-02-28; 2026-03-31; 2026-03-31; 2026-03-31; no error | pass |
| WOR-ADV-17 | R8 | happy | — | `"monthly"`, day `None`: from 2026-01-10 ; 2026-01-31 ; 2026-02-28 ; 2026-12-31 | returns 2026-02-10 ; 2026-02-28 ; 2026-03-28 (does not return to 31) ; 2027-01-31 | pass |
| WOR-ADV-18 | R6, R8a | happy | — | `"monthly"`, day `31`, chained: start from 2026-01-31, then feed each result back as `from_date` twice more | results in order: 2026-02-28, 2026-03-31, 2026-04-30 (a stored day never drifts; this is the helper side of R8a and holds today) | pass |
| WOR-ADV-19 | R11 [BUG-360] | bug | — | from 2026-03-02, day `None`, type each of `"Daily"`, `"WEEKLY"`, `" daily"`, `"Weekly"`, `"biweekly"`, `"quarterly"`, `""`; plus type `"Monthly"` with day `15` | each raises `ValueError` with `str(exc) == "Unsupported recurrence type: " + repr(value)`, e.g. `Unsupported recurrence type: 'Daily'`, `Unsupported recurrence type: ''`, `Unsupported recurrence type: ' daily'` | xfail BUG-360 — fails today on: no error raised (returns 2026-03-03) |
| WOR-ADV-20 | R11b [BUG-361] | bug | — | from 2026-03-02, `recurrence_type=None`, day each of `None`, `0` | raises `ValueError`, `str(exc) == "Unsupported recurrence type: None"` | xfail BUG-361 — fails today on: no error raised (returns 2026-03-03) |
| WOR-ADV-21 | R11a | happy | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=v, recurrence_day=None, …)` for v in `"daily"`, `"weekly"`, `"monthly"` | builds without error; `.recurrence_type == v` | pass |
| WOR-ADV-22 | R11a [BUG-360] | bug | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=" Weekly ", …)` ; same with `"MONTHLY"` ; same with `"Daily"` | builds; `.recurrence_type` is `"weekly"` ; `"monthly"` ; `"daily"` | xfail BUG-360 — fails today on: `.recurrence_type` kept as typed (`" Weekly "`) |
| WOR-ADV-23 | R11a [BUG-360] | bug | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=v, …)` for v in `"biweekly"`, `"wekly"`, `"quarterly"`, `""`, `"   "` | raises `pydantic.ValidationError` on `recurrence_type` | xfail BUG-360 — fails today on: no error raised |
| WOR-ADV-24 | R11a [BUG-360] | bug | — | *(schema)* `WorkOrderTemplateUpdate(recurrence_type=" Weekly ")` (no other fields) | builds; `.recurrence_type == "weekly"` | xfail BUG-360 — fails today on: value kept as `" Weekly "` |
| WOR-ADV-25 | R11a [BUG-360] | bug | — | *(schema)* `WorkOrderTemplateUpdate(recurrence_type=v)` for v in `"biweekly"`, `"quarterly"` | raises `pydantic.ValidationError` on `recurrence_type` | xfail BUG-360 — fails today on: no error raised |
| WOR-ADV-26 | R11a | boundary | — | *(schema)* `WorkOrderTemplateUpdate(recurrence_type=None)` ; `WorkOrderTemplateUpdate(recurrence_type="monthly")` | both build; `.recurrence_type` is `None` ; `"monthly"` (`None` passes the whitelist itself) | pass |
| WOR-ADV-27 | R11b, R10a [BUG-361] | bug | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=None)` ; same with `recurrence_type` omitted ; `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=None, recurrence_day=9)` (a day does not rescue a missing type) | all three raise `pydantic.ValidationError` | xfail BUG-361 — fails today on: no error raised |
| WOR-ADV-28 | R11b | boundary | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=False, recurrence_type=None, …)` | builds; `.is_recurring is False`; `.recurrence_type is None` | pass |
| WOR-ADV-29 | R4a [BUG-362] | bug | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type="weekly", recurrence_day=d, …)` for d in `7`, `-1`, `10` | raises `pydantic.ValidationError` | xfail BUG-362 — fails today on: no error raised |
| WOR-ADV-30 | R4a, R2 | boundary | — | *(schema)* same as WOR-ADV-29 with d in `0`, `6`, `None` | builds; `.recurrence_day == d` | pass |
| WOR-ADV-31 | R7a [BUG-362] | bug | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type="monthly", recurrence_day=d, …)` for d in `0`, `-5`, `32`, `45` | raises `pydantic.ValidationError` | xfail BUG-362 — fails today on: no error raised |
| WOR-ADV-32 | R7a | boundary | — | *(schema)* same as WOR-ADV-31 with d in `1`, `31` (also `15` as a mid value) | builds; `.recurrence_day == d` | pass |
| WOR-ADV-33 | R10a | boundary | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type="daily", recurrence_day=d)` for d in `9`, `-1`, `45` | builds without error; `.recurrence_type == "daily"`; `.recurrence_day == d` (neither rejected nor cleared) | pass |
| WOR-ADV-34 | R10a | boundary | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=False, recurrence_type=None, recurrence_day=d)` for d in `9`, `-1`, `45` | builds without error; `.is_recurring is False`; `.recurrence_type is None`; `.recurrence_day == d` | pass |
| WOR-ADV-35 | R10a | boundary | — | *(schema)* `WorkOrderTemplateUpdate(recurrence_type="daily", recurrence_day=45)` ; `WorkOrderTemplateUpdate(recurrence_day=-1)` | both build without error; `.recurrence_day` is `45` ; `-1`; `.recurrence_type` is `"daily"` ; `None` | pass |
| WOR-ADV-36 | R4b | boundary | — | *(schema)* `WorkOrderTemplateUpdate(recurrence_type="weekly", recurrence_day=9)` ; `WorkOrderTemplateUpdate(recurrence_type="monthly", recurrence_day=0)` | both build without error (the update schema does no day-range check even with type and day together); `.recurrence_type` is `"weekly"` ; `"monthly"`; `.recurrence_day` is `9` ; `0` | pass |
| WOR-ADV-37 | R11a | boundary | — | *(schema)* `WorkOrderTemplateCreate(is_recurring=True, recurrence_type=v)` for v in `" Weekly "`, `"MONTHLY"`, `"Daily"` ; `WorkOrderTemplateUpdate(recurrence_type=" Weekly ")` | every call builds without error (a padded / mixed-case supported value is never rejected); `.recurrence_type.strip().lower()` equals `"weekly"` ; `"monthly"` ; `"daily"` ; `"weekly"` (regression guard for the non-rejection half of WOR-ADV-22 / -24; holds today and after the fix) | pass |

## `_apply_recurrence_range`

`t` is built with prior state P unless the case says otherwise. Every success case asserts the return value `is None`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-APR-01 | R2, R4, R5 | happy | `t = T(recurrence_type="daily")` (prior day 4) | `_apply_recurrence_range(t, 2026-03-02, 2026-03-31)` | returns `None`; `recurrence_start_date == 2026-03-02`; `recurrence_end_date == 2026-03-31`; `recurrence_day is None` (prior 4 discarded); `next_generation_date == 2026-03-03`; `is_recurring` and `recurrence_type` unchanged | pass |
| WOR-APR-02 | R2, R4, R5 | side-effect | `t = T(recurrence_type="weekly", recurrence_day=0)` | `_apply_recurrence_range(t, Wed 2026-03-04, 2026-04-30)` | returns `None`; start 2026-03-04; end 2026-04-30; `recurrence_day is None`; `next_generation_date == 2026-03-11` (+7 from placement, not the prior Monday 2026-03-09) | pass |
| WOR-APR-03 | R2, R3, R5 | happy | `t = T(recurrence_type="monthly", recurrence_day=15)` | `_apply_recurrence_range(t, 2026-01-31, 2026-06-30)` | returns `None`; start 2026-01-31; end 2026-06-30; `recurrence_day == 31` (prior 15 overwritten); `next_generation_date == 2026-02-28` | pass |
| WOR-APR-04 | R3, R5 | side-effect | `t = T(recurrence_type="monthly", recurrence_day=25)` | `_apply_recurrence_range(t, 2026-03-10, 2026-05-31)` | returns `None`; `recurrence_day == 10`; `next_generation_date == 2026-04-10`; start 2026-03-10; end 2026-05-31 | pass |
| WOR-APR-05 | R1 | error | `t = T(recurrence_type="daily")`, snapshot taken | `_apply_recurrence_range(t, 2026-03-02, 2026-03-01)` | raises `ValueError`, `str(exc) == E_BACK`; `t` unchanged (start 2025-01-01, end 2025-02-01, day 4, next 2025-01-15) | pass |
| WOR-APR-06 | R1 | error | `t = T(recurrence_type="monthly")`, snapshot taken | `_apply_recurrence_range(t, 2026-01-01, 2026-07-04)` (184 days) | raises `ValueError`, `str(exc) == E_SPAN`; `t` unchanged | pass |
| WOR-APR-07 | R1 | boundary | `t = T(recurrence_type="daily")` | `_apply_recurrence_range(t, 2026-01-01, 2026-07-03)` (183 days) | returns `None`; start 2026-01-01; end 2026-07-03; `recurrence_day is None`; next 2026-01-02 | pass |
| WOR-APR-08 | R6, R7 | boundary | `t = T(recurrence_type="daily")` | `_apply_recurrence_range(t, 2026-03-02, 2026-03-02)` | returns `None`; start 2026-03-02; end 2026-03-02; `next_generation_date == 2026-03-03` (after the end date, still set) | pass |
| WOR-APR-09 | R4a [BUG-360, BUG-361] | bug | `t = T(recurrence_type=v)` for v in `None`, `"Weekly"`, `"biweekly"`, `""`; snapshot taken | `_apply_recurrence_range(t, 2026-03-02, 2026-03-31)` | raises `ValueError` with `str(exc) == "Unsupported recurrence type: " + repr(v)` (for `None`: `Unsupported recurrence type: None`); `t` unchanged | xfail BUG-360 (BUG-361 for `None`) — fails today on: no error raised |
| WOR-APR-10 | R4a, R1 | error | (a) `t = T(recurrence_type="biweekly")`; (b) `t = T(recurrence_type=None)`; snapshots taken | (a) `_apply_recurrence_range(t, 2026-03-02, 2026-03-01)`; (b) `_apply_recurrence_range(t, 2026-01-01, 2026-07-04)` | (a) raises `ValueError` with `E_BACK`; (b) raises `ValueError` with `E_SPAN`; in both, `t` unchanged (the range error wins over the type error; holds today and after the fix) | pass |
| WOR-APR-11 | R2, R5 | side-effect | `t = T(is_recurring=False, recurrence_type="daily")` | `_apply_recurrence_range(t, 2026-03-02, 2026-03-31)` | returns `None`; fields written as in WOR-APR-01 (start 2026-03-02, end 2026-03-31, day `None`, next 2026-03-03); `is_recurring` still `False` (`is_recurring` is not checked here) | pass |

## `seed_recurrence_from_planned_date`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-SEED-01 | R1 | boundary | `t = T(is_recurring=False, recurrence_type="daily", next_generation_date=None)`, snapshot | `seed_recurrence_from_planned_date(t, 2026-03-02, 2026-03-01)` (invalid range) | returns `None`; no error; `t` unchanged | pass |
| WOR-SEED-02 | R1 | side-effect | same `t` as SEED-01, snapshot | `seed_recurrence_from_planned_date(t, 2026-03-02, 2026-03-31)` (valid range) | returns `None`; `t` unchanged (start 2025-01-01, end 2025-02-01, day 4, next `None`) | pass |
| WOR-SEED-03 | R2 | boundary | `t = T(recurrence_type="daily", next_generation_date=2026-02-10)`, snapshot | `seed_recurrence_from_planned_date(t, 2026-03-02, 2026-03-01)` (invalid range) | returns `None`; no error; `t` unchanged | pass |
| WOR-SEED-04 | R2 | side-effect | `t = T(recurrence_type="monthly", recurrence_day=15, next_generation_date=2026-02-10)`, snapshot | `seed_recurrence_from_planned_date(t, 2026-01-31, 2026-04-30)` | returns `None`; `t` unchanged (next still 2026-02-10, day still 15, start 2025-01-01) | pass |
| WOR-SEED-05 | R3 | happy | `t = T(recurrence_type="monthly", recurrence_day=None, recurrence_start_date=None, recurrence_end_date=None, next_generation_date=None)` | `seed_recurrence_from_planned_date(t, 2026-01-31, 2026-04-30)` | returns `None`; start 2026-01-31; end 2026-04-30; `recurrence_day == 31`; `next_generation_date == 2026-02-28` | pass |
| WOR-SEED-06 | R3 | error | `t = T(recurrence_type="daily", next_generation_date=None)`, snapshot | `seed_recurrence_from_planned_date(t, 2026-01-01, 2026-07-04)` (184 days) | raises `ValueError`, `str(exc) == E_SPAN`; `t` unchanged (next still `None`) | pass |
| WOR-SEED-07 | R3 (via APR R4a) [BUG-361] | bug | `t = T(recurrence_type=None, next_generation_date=None)`, snapshot | `seed_recurrence_from_planned_date(t, 2026-03-02, 2026-03-31)` | raises `ValueError`, `str(exc) == "Unsupported recurrence type: None"`; `t` unchanged (next still `None`) | xfail BUG-361 — fails today on: no error raised (`next_generation_date` set to 2026-03-03) |

## `reseed_recurrence_program`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-RESEED-01 | R1 | boundary | `t = T(is_recurring=False, recurrence_type="daily")`, snapshot | `reseed_recurrence_program(t, 2026-03-02, 2026-03-01)` (invalid range) | returns `None`; no error; `t` unchanged | pass |
| WOR-RESEED-02 | R1 | side-effect | same `t` as RESEED-01, snapshot | `reseed_recurrence_program(t, 2026-03-02, 2026-03-31)` | returns `None`; `t` unchanged | pass |
| WOR-RESEED-03 | R2 | happy | `t = T(recurrence_type="weekly", recurrence_day=3, recurrence_start_date=2026-01-01, recurrence_end_date=2026-03-31, next_generation_date=2026-02-10)` | `reseed_recurrence_program(t, Wed 2026-03-04, 2026-05-31)` | returns `None`; start 2026-03-04; end 2026-05-31; `recurrence_day is None`; `next_generation_date == 2026-03-11` (overwritten although it was set) | pass |
| WOR-RESEED-04 | R2 | happy | `t = T(recurrence_type="daily", next_generation_date=None)` | `reseed_recurrence_program(t, 2026-03-02, 2026-03-31)` | returns `None`; start 2026-03-02; end 2026-03-31; day `None`; next 2026-03-03 | pass |
| WOR-RESEED-05 | R2 | error | `t = T(recurrence_type="monthly", recurrence_day=15, next_generation_date=2026-02-10)`, snapshot | `reseed_recurrence_program(t, 2026-03-02, 2026-03-01)` | raises `ValueError`, `str(exc) == E_BACK`; `t` unchanged | pass |
| WOR-RESEED-06 | R2 (via APR R4a) [BUG-360] | bug | `t = T(recurrence_type="quarterly", next_generation_date=2026-02-10)`, snapshot | `reseed_recurrence_program(t, 2026-03-02, 2026-03-31)` | raises `ValueError`, `str(exc) == "Unsupported recurrence type: 'quarterly'"`; `t` unchanged | xfail BUG-360 — fails today on: no error raised |

## `is_recurrence_program_active`

Target date for all cases: 2026-03-15.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-ACT-01 | R1 | boundary | `T(is_recurring=False, recurrence_type="daily", next_generation_date=2026-03-01, recurrence_end_date=None)` | `is_recurrence_program_active(t, 2026-03-15)` | returns `False` (`is False`) | pass |
| WOR-ACT-02 | R2 | boundary | `T(recurrence_type="daily", next_generation_date=None, recurrence_end_date=None)` | same call | returns `False` (`is False`) | pass |
| WOR-ACT-03 | R3 | boundary | `T(recurrence_type="daily", next_generation_date=2026-03-01, recurrence_end_date=2026-03-14)` | same call | returns `False` (`is False`) | pass |
| WOR-ACT-04 | R4 | boundary | as ACT-03 with `recurrence_end_date=2026-03-15` | same call | returns `True` (`is True`) | pass |
| WOR-ACT-05 | R3, R4 | boundary | as ACT-03 with `recurrence_end_date=2026-03-16` | same call | returns `True` (`is True`) | pass |
| WOR-ACT-06 | R5 | happy | `T(recurrence_type="daily", next_generation_date=2026-03-01, recurrence_end_date=None)` | `is_recurrence_program_active(t, 2099-12-31)` | returns `True` (`is True`) | pass |
| WOR-ACT-07 | R6 | boundary | `T(recurrence_type="daily", recurrence_start_date=2026-04-01, next_generation_date=2026-04-10, recurrence_end_date=2026-05-31)` | `is_recurrence_program_active(t, 2026-03-15)` | returns `True` (`is True`); start and next dates are ignored | pass |

## `should_advance_template`

Target date for all cases: 2026-03-15. `recurrence_end_date=None` unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOR-SHA-01 | R1, R3 | boundary | `T(recurrence_type="daily", next_generation_date=2026-03-15, recurrence_end_date=None)` | `should_advance_template(t, 2026-03-15)` | returns `True` (`is True`) | pass |
| WOR-SHA-02 | R2 | boundary | as SHA-01 with `next_generation_date=2026-03-16` | same call | returns `False` (`is False`) | pass |
| WOR-SHA-03 | R4 | happy | as SHA-01 with `next_generation_date=2026-03-01` | same call | returns `True` (`is True`) | pass |
| WOR-SHA-04 | R5 | boundary | `T(recurrence_type="daily", next_generation_date=2026-03-10, recurrence_end_date=2026-03-14)` | same call | returns `False` (`is False`) | pass |
| WOR-SHA-05 | R5 | boundary | as SHA-04 with `recurrence_end_date=2026-03-15` | same call | returns `True` (`is True`) | pass |
| WOR-SHA-06 | R6 | boundary | `T(is_recurring=False, recurrence_type="daily", next_generation_date=2026-03-10, recurrence_end_date=None)` | same call | returns `False` (`is False`) | pass |
| WOR-SHA-07 | R6 | boundary | `T(recurrence_type="daily", next_generation_date=None, recurrence_end_date=None)` | same call | returns `False` (`is False`, not `None`) | pass |
| WOR-SHA-08 | R1 | happy | `T(recurrence_type="daily", recurrence_start_date=2026-04-01, next_generation_date=2026-03-10, recurrence_end_date=2026-05-31)` | same call | returns `True` (`is True`); a start date after the target does not block (per ACT R6) | pass |

## Deferred to other specs

| Rule | Owner | What must be tested there |
|---|---|---|
| ADV R4a [BUG-362] (update part) | `WorkOrderTemplateManager.update_template` | A stored weekly template updated with `recurrence_day: 7` is rejected with 422, and so is a stored template with day 9 updated to `recurrence_type: "weekly"` (merged state). The row is unchanged after re-reading it. |
| ADV R7a [BUG-362] (update part) | `WorkOrderTemplateManager.update_template` | A stored monthly template updated with `recurrence_day: 0` / `32`, or a stored day 45 updated to `monthly`, is rejected with 422. The row is unchanged. |
| ADV R11b [BUG-361] (update part) | `WorkOrderTemplateManager.update_template` | A stored template with `is_recurring: false, recurrence_type: null` updated with `is_recurring: true` only gets 422, and so does a recurring template updated with `recurrence_type: null`. The row is unchanged. A non-recurring template keeps a `null` type. |
| ADV R8a [BUG-363] | `WorkOrderTemplateManager.create_template` / `update_template` (or the template schema, whichever the fix uses) | A monthly template saved with `recurrence_day: null` gets the day of `recurrence_start_date`. If that is null, it gets the day of `next_generation_date`. If both are null, the day stays null. An explicit day is kept. The same rules apply on update to the merged state. |
| ADV R11a [BUG-360] (data clean-up) | migration / data fix for `work_order_templates` | Existing rows with unsupported `recurrence_type` values are normalised or flagged when the fix lands. |
| ADV R10a (update part) | `WorkOrderTemplateManager.update_template` | A stored `daily` template updated with `recurrence_day: 45`, and a stored non-recurring untyped template updated with `recurrence_day: -1`, are accepted (no 422); re-read row keeps the day as sent (not cleared). |
| APR R4a / R1 (HTTP surface) | `WorkOrderManager._maybe_seed_template_recurrence` | The helper's `ValueError` (range or unsupported type) becomes HTTP 400, with the exact message as detail. |

## Spec gaps

None. Earlier gaps 1–3 (schema required fields; `recurrence_day` on daily/untyped templates; day-range check on `WorkOrderTemplateUpdate` alone) were closed by spec Gap log G1–G3.

## Coverage matrix

| Callable | Rule / Error row | Cases |
|---|---|---|
| `validate_recurrence_span` | R1 | WOR-VS-02, WOR-VS-03 |
| `validate_recurrence_span` | R2 | WOR-VS-01 |
| `validate_recurrence_span` | R3 | WOR-VS-04 |
| `validate_recurrence_span` | R4 | WOR-VS-05, WOR-VS-06 |
| `validate_recurrence_span` | R5 | WOR-VS-03 |
| `validate_recurrence_span` | Error: end < start | WOR-VS-02, WOR-VS-03 |
| `validate_recurrence_span` | Error: span > 183 | WOR-VS-05, WOR-VS-06 |
| `advance_next_generation_date` | R1 | WOR-ADV-01, WOR-ADV-02 |
| `advance_next_generation_date` | R2 | WOR-ADV-04 |
| `advance_next_generation_date` | R3 | WOR-ADV-05, -06, -07, -08, -09 |
| `advance_next_generation_date` | R4 | WOR-ADV-10 |
| `advance_next_generation_date` | R4a [BUG-362] | WOR-ADV-29 (xfail), WOR-ADV-30; update part deferred |
| `advance_next_generation_date` | R4b | WOR-ADV-36 |
| `advance_next_generation_date` | R5 | WOR-ADV-11, WOR-ADV-12 |
| `advance_next_generation_date` | R6 | WOR-ADV-13, WOR-ADV-14, WOR-ADV-18 |
| `advance_next_generation_date` | R7 | WOR-ADV-15, WOR-ADV-16 |
| `advance_next_generation_date` | R7a [BUG-362] | WOR-ADV-31 (xfail), WOR-ADV-32; update part deferred |
| `advance_next_generation_date` | R8 | WOR-ADV-17 |
| `advance_next_generation_date` | R8a [BUG-363] | WOR-ADV-18 (helper side, pass); fill logic deferred |
| `advance_next_generation_date` | R9 | WOR-ADV-04, WOR-ADV-05, WOR-ADV-15 |
| `advance_next_generation_date` | R10 | WOR-ADV-03 |
| `advance_next_generation_date` | R10a | WOR-ADV-33, -34, -35, -27 (recurring-without-type part, xfail); update part deferred |
| `advance_next_generation_date` | R11 [BUG-360] | WOR-ADV-19 (xfail) |
| `advance_next_generation_date` | R11a [BUG-360] | WOR-ADV-21, -22 (xfail), -23 (xfail), -24 (xfail), -25 (xfail), -26, -37; data clean-up deferred |
| `advance_next_generation_date` | R11b [BUG-361] | WOR-ADV-20 (xfail), WOR-ADV-27 (xfail), WOR-ADV-28; update part deferred |
| `advance_next_generation_date` | Error: unsupported type [BUG-360] | WOR-ADV-19 |
| `advance_next_generation_date` | Error: `None` type [BUG-361] | WOR-ADV-20 |
| `_apply_recurrence_range` | R1 | WOR-APR-05, -06, -07, -10 |
| `_apply_recurrence_range` | R2 | WOR-APR-01, -02, -03, -11 |
| `_apply_recurrence_range` | R3 | WOR-APR-03, WOR-APR-04 |
| `_apply_recurrence_range` | R4 | WOR-APR-01, WOR-APR-02 |
| `_apply_recurrence_range` | R4a [BUG-360, BUG-361] | WOR-APR-09 (xfail), WOR-APR-10; HTTP 400 deferred |
| `_apply_recurrence_range` | R5 | WOR-APR-01, -02, -03, -04, -11 |
| `_apply_recurrence_range` | R6 | WOR-APR-08 |
| `_apply_recurrence_range` | R7 | WOR-APR-08 |
| `_apply_recurrence_range` | Error: range | WOR-APR-05, -06, -10 |
| `_apply_recurrence_range` | Error: unsupported / `None` type | WOR-APR-09 |
| `seed_recurrence_from_planned_date` | R1 | WOR-SEED-01, WOR-SEED-02 |
| `seed_recurrence_from_planned_date` | R2 | WOR-SEED-03, WOR-SEED-04 |
| `seed_recurrence_from_planned_date` | R3 | WOR-SEED-05, -06, -07 (xfail) |
| `seed_recurrence_from_planned_date` | Errors (R3 path) | WOR-SEED-06, WOR-SEED-07 |
| `reseed_recurrence_program` | R1 | WOR-RESEED-01, WOR-RESEED-02 |
| `reseed_recurrence_program` | R2 | WOR-RESEED-03, -04, -05, -06 (xfail) |
| `reseed_recurrence_program` | Errors (R2 path) | WOR-RESEED-05, WOR-RESEED-06 |
| `is_recurrence_program_active` | R1 | WOR-ACT-01 |
| `is_recurrence_program_active` | R2 | WOR-ACT-02 |
| `is_recurrence_program_active` | R3 | WOR-ACT-03, WOR-ACT-05 |
| `is_recurrence_program_active` | R4 | WOR-ACT-04, WOR-ACT-05 |
| `is_recurrence_program_active` | R5 | WOR-ACT-06 |
| `is_recurrence_program_active` | R6 | WOR-ACT-07 |
| `should_advance_template` | R1 | WOR-SHA-01, WOR-SHA-08 |
| `should_advance_template` | R2 | WOR-SHA-02 |
| `should_advance_template` | R3 | WOR-SHA-01 |
| `should_advance_template` | R4 | WOR-SHA-03 |
| `should_advance_template` | R5 | WOR-SHA-04, WOR-SHA-05 |
| `should_advance_template` | R6 | WOR-SHA-06, WOR-SHA-07 |
| — | BUG-360 | WOR-ADV-19, -22, -23, -24, -25, WOR-APR-09, WOR-RESEED-06 |
| — | BUG-361 | WOR-ADV-20, -27, WOR-APR-09 (`None`), WOR-SEED-07 |
| — | BUG-362 | WOR-ADV-29, -31 |
| — | BUG-363 | WOR-ADV-18 (pass, helper side); fill deferred |
