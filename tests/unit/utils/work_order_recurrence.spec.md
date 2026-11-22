# Spec — `app/utils/work_order_recurrence.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Precedent matches — confirm all with ok

### P1. Any text is accepted as a recurrence type — 🐞 BUG-360
**Background:** A recurring work order template has a `recurrence_type` that decides how often drafts are generated. The code only understands exactly `daily`, `weekly` and `monthly` (lowercase). The template create/update schemas accept any string (`String(50)` column, no validation).
**What happens today:** Any other value — `"Weekly"`, `"biweekly"`, `"quarterly"`, `"wekly"` — is stored as typed and the schedule silently advances one day at a time, like `daily`.
**Example:** A user creates a template via the API with `recurrence_type: "Weekly"`. The Plan-day run on 2026-03-02 moves the next generation date to 2026-03-03 instead of 2026-03-09, so a draft work order is created every day.
**Rules affected:** `advance_next_generation_date` R11
**Answer:** bug — per BUG-022 precedent: `recurrence_type` is normalised (trimmed, lower-cased) and only the supported values `daily`, `weekly`, `monthly` are accepted; anything else is rejected with 422 by `WorkOrderTemplateCreate`/`WorkOrderTemplateUpdate` before anything is stored (precedent — confirmed: ok)
**Resolution:** the template schemas normalise and whitelist `recurrence_type` (fix in `app/schemas/work_order_template.py`). This helper never guesses: an unsupported value raises `ValueError` instead of falling back to daily (best-practice default, delegated by reviewer). Rules: `advance_next_generation_date` R10, R11, R11a; `_apply_recurrence_range` R4a.

### New questions

### Q1. A recurring template with no recurrence type runs daily, but the app previews it as weekly — 🐞 BUG-361
**Background:** `is_recurring` and `recurrence_type` are separate fields; the API allows `is_recurring: true` with `recurrence_type: null`. The frontend has a copy of this date logic (`workOrderRecurrenceDates.ts`, "Mirror backend `advance_next_generation_date`") that treats a missing type as **weekly**; the backend treats it as **daily**.
**What happens today:** A recurring template without a type advances one day at a time, while the UI's preview of planned dates (and the template label) shows a weekly schedule.
**Example:** A template is saved via the API with `is_recurring: true, recurrence_type: null` and placed on the sheet on 2026-03-02 through 2026-03-30. The UI preview lists 5 weekly dates; the backend creates 29 daily draft work orders.
**Rules affected:** `advance_next_generation_date` R11
**Answer:** bug — recurrence_type is required when is_recurring is true (422 from the template schemas); the backend never guesses a cadence for a missing type (reviewer accepted suggestion)
**Resolution:** `WorkOrderTemplateCreate` rejects `is_recurring: true` without a `recurrence_type` (422); `update_template` checks the *resulting* template (stored values merged with the payload) and rejects with 422 when it would be recurring without a type (best-practice default, delegated by reviewer — the update schema alone cannot see stored values). `advance_next_generation_date` with `recurrence_type` `None` raises `ValueError` (R11); `_apply_recurrence_range` rejects before mutating (R4a). Rules: `advance_next_generation_date` R11b; `_apply_recurrence_range` R4a.

### Q2. Out-of-range recurrence day is silently wrapped or clamped — 🐞 BUG-362
**Background:** `recurrence_day` means "day of week, 0 = Monday … 6 = Sunday" for weekly templates and "day of month 1–31" for monthly ones. The template schemas accept any integer. (The work-order template dialog always sends `null`; other values only arrive through the API.)
**What happens today:** For weekly, the day is taken modulo 7 (`7` → Monday, `-1` → Sunday, `10` → Thursday). For monthly, it is clamped into 1–31 (`0` or `-5` → 1st, `45` → 31st, then capped to the month's last day). No error is raised.
**Example:** A monthly template is created via the API with `recurrence_day: 0` (the user meant "last day of month"). Its next run after 2026-01-10 is 2026-02-01, not 2026-02-28.
**Rules affected:** `advance_next_generation_date` R4, R7
**Answer:** bug — the template schemas reject recurrence_day outside 0-6 for weekly and outside 1-31 for monthly (422), and nothing is stored (reviewer accepted suggestion)
**Resolution:** fix belongs in the template schemas (create) and `update_template` (merged state, since type and day may arrive in different requests) (best-practice default, delegated by reviewer). The helper's own wrap/clamp (R4, R7) stays as today's defensive behavior and is no longer reachable with valid data; it is not changed (best-practice default, delegated by reviewer). Rules: `advance_next_generation_date` R4a, R7a.

### Q3. Monthly schedule without a stored day drifts after a short month — 🐞 BUG-363
**Background:** For monthly templates the target day-of-month comes from `recurrence_day`. Placing a template on the planning sheet always stores it, but a template created/updated through the API can be monthly with `recurrence_day: null` and a `next_generation_date` set directly. Then the day is taken from the date of the last run.
**What happens today:** Without a stored day, each run uses the previous run's day-of-month; once a short month caps it, it never returns.
**Example:** A monthly template with no stored day runs on 2026-01-31 → next is 2026-02-28 → next is 2026-03-28 → 2026-04-28 …; the user expected the last/31st of each month from March on.
**Rules affected:** `advance_next_generation_date` R6, R8
**Answer:** bug — monthly templates always have a stored day (filled from the anchor date when missing), so the day of month never drifts (reviewer accepted suggestion)
**Resolution:** when a template is saved (create or update, merged state) as monthly with `recurrence_day` null, `recurrence_day` is filled from `recurrence_start_date`'s day, else from `next_generation_date`'s day (anchor order from the suggested answer). If neither date is set, `recurrence_day` stays null until the template is placed on the sheet, where `_apply_recurrence_range` R3 stores it (best-practice default, delegated by reviewer). The helper's R8 fallback stays as today's defensive behavior. Rules: `advance_next_generation_date` R8, R8a.

## Overview
Pure date helpers for recurring work order templates. They validate the planned
range a user picks when placing a recurring template on the planning sheet
(at most 183 days), anchor the template's schedule to that placement
(`recurrence_start_date`, `recurrence_end_date`, `recurrence_day`,
`next_generation_date`), compute the next generation date after a run, and
decide whether the daily "Plan day" run should advance a template. Callers:
`WorkOrderManager._maybe_seed_template_recurrence` (seed / reseed; converts
`ValueError` into HTTP 400 with the message as detail) and
`WorkOrderTemplateManager.generate_drafts_for_anchored_range` /
`generate_drafts` (advance / should-advance).

**Callables:** 7 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- Nothing here touches the database, flushes or commits. The `template`
  argument is any object with the attributes `is_recurring`, `recurrence_type`,
  `recurrence_day`, `recurrence_start_date`, `recurrence_end_date`,
  `next_generation_date` (a `types.SimpleNamespace` or an unsaved
  `WorkOrderTemplate` instance both work). Mutating helpers change those
  attributes in memory only.
- Weekday numbering is Python's: Monday = 0 … Sunday = 6.
- No `utcnow`/today is read; all dates come from arguments.
- Schema cases (R4a, R4b, R7a, R10a, R11a, R11b): `WorkOrderTemplateCreate` has only two
  required fields, `template_name` (`str`) and `work_order_type_id` (`int`); every
  other field has a default (`is_recurring` `False`, all `recurrence_*` and
  `next_generation_date` `None`). The schema does not check that the work order
  type exists, so `{"template_name": "T", "work_order_type_id": 1}` is a minimal
  valid payload. `WorkOrderTemplateUpdate` has no required fields (`{}` is valid).
  Construct the schemas directly (`WorkOrderTemplateCreate(**payload)`); no
  database is needed for them.

## Not specified
- `WorkOrderGenerationMode` (type alias `Literal['schedule', 'draft']`) — not a callable; referenced nowhere in `app/` (candidate for the dead-code list).
- `RECURRENCE_MAX_SPAN_DAYS` — constant `183`, its effect is specified under `validate_recurrence_span`.

---

## `validate_recurrence_span(start_date, end_date)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `_apply_recurrence_range`; no other callers)

**Purpose:** Reject a recurrence range that runs backwards or is longer than about six months.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `start_date` | `date` | First day of the range |
| `end_date` | `date` | Last day of the range (inclusive) |

**Returns:** `None` when the range is valid.

**Rules:**
- **R1.** `end_date` earlier than `start_date` (by any number of days) raises `ValueError('Recurrence end date must be on or after the start date')`.
- **R2.** `end_date` equal to `start_date` (zero-day span) is valid.
- **R3.** A span of exactly 183 days (`end_date - start_date == 183 days`) is valid.
- **R4.** A span of 184 days or more raises `ValueError('Recurrence range cannot exceed 183 days (~6 months)')`.
- **R5.** The backwards check wins: a backwards range never gets the span message (a negative span is never "too long").

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `end_date < start_date` | `ValueError` | `Recurrence end date must be on or after the start date` |
| `(end_date - start_date).days > 183` | `ValueError` | `Recurrence range cannot exceed 183 days (~6 months)` |

**Side effects:** none

---

## `advance_next_generation_date(*, from_date, recurrence_type, recurrence_day)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `_apply_recurrence_range`, `WorkOrderTemplateManager.generate_drafts_for_anchored_range`, `WorkOrderTemplateManager.generate_drafts`)

**Purpose:** Compute the next date a recurring template should generate a work order, given the date it last ran.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `from_date` | `date` | Date of the run just completed; keyword-only |
| `recurrence_type` | `str \| None` | Matched exactly (case-sensitive) against `daily`, `weekly`, `monthly`; anything else is rejected (R11, R11b — today it falls back to daily); keyword-only |
| `recurrence_day` | `int \| None` | Weekly: target weekday (Mon = 0); monthly: target day of month; ignored for daily/other; no range check; keyword-only |

**Returns:** a `date`, always strictly after `from_date` (for a supported type).

**Rules:**
- **R1.** `daily`: returns `from_date + 1 day` (crosses month/year ends normally, e.g. 2026-12-31 → 2027-01-01). `recurrence_day` is ignored.
- **R2.** `weekly` with `recurrence_day` `None`: returns `from_date + 7 days`.
- **R3.** `weekly` with a day: returns the next date strictly after `from_date` whose weekday equals the target weekday — between 1 and 7 days ahead. If `from_date` already is that weekday, returns `from_date + 7 days`. Example: from Wednesday 2026-03-04 with day `0` (Monday) → 2026-03-09; with day `2` (Wednesday) → 2026-03-11; with day `3` (Thursday) → 2026-03-05.
- **R4.** `weekly`: the target weekday is `recurrence_day` modulo 7 (Python modulo, result 0–6): `7` behaves as `0` (Monday), `-1` as `6` (Sunday), `10` as `3` (Thursday). No error for out-of-range values. This defensive wrap is kept as is; with valid stored data (R4a) it is a no-op (best-practice default, delegated by reviewer).
- **R4a.** [BUG-362] A weekly template can never be stored with `recurrence_day` outside 0–6: `WorkOrderTemplateCreate` rejects it (Pydantic `ValidationError`, 422 at the API) and `update_template` rejects it with 422 when the resulting template (stored values merged with the payload) is weekly with a day outside 0–6; nothing is stored. `None` stays allowed (R2). *(Today: any integer is stored and wrapped per R4.)* *(Fix belongs in `app/schemas/work_order_template.py` and `WorkOrderTemplateManager.update_template`, not in this helper.)*
- **R5.** `monthly`: the result is always in the calendar month after `from_date`'s month (December → January of the next year), regardless of whether the target day in `from_date`'s own month is still ahead. Example: from 2026-01-10 with day `15` → 2026-02-15 (2026-01-15 is skipped).
- **R6.** `monthly` with a day given: the result's day of month is `recurrence_day` (after R7), capped to the last day of the target month. Example: day `31` from 2026-01-15 → 2026-02-28; from 2028-01-15 → 2028-02-29 (leap year); from 2026-03-15 → 2026-04-30; from 2026-12-15 → 2027-01-31.
- **R7.** `monthly`: `recurrence_day` below 1 (including `0` and negatives) is treated as `1`; above 31 is treated as `31` (then R6 caps it to the month's end). No error. This defensive clamp is kept as is; with valid stored data (R7a) it is a no-op (best-practice default, delegated by reviewer).
- **R4b.** `WorkOrderTemplateUpdate` by itself performs **no** `recurrence_day` range check, even when the same payload carries both the type and the day: `WorkOrderTemplateUpdate(recurrence_type="weekly", recurrence_day=9)` and `WorkOrderTemplateUpdate(recurrence_type="monthly", recurrence_day=0)` validate without error. The day-range check for updates lives only in `update_template` on the merged state (R4a, R7a), which also covers a payload holding both fields — one place, no duplicated rule (best-practice default, delegated by reviewer). *(Today: same — no check anywhere.)*
- **R7a.** [BUG-362] A monthly template can never be stored with `recurrence_day` outside 1–31: `WorkOrderTemplateCreate` rejects it (Pydantic `ValidationError`, 422 at the API) and `update_template` rejects it with 422 on the merged state; nothing is stored. *(Today: any integer is stored and clamped per R7.)* *(Fix belongs in `app/schemas/work_order_template.py` and `WorkOrderTemplateManager.update_template`.)*
- **R8.** `monthly` with `recurrence_day` `None`: the day of month is `from_date`'s day, capped as in R6. Consequence: from 2026-01-31 → 2026-02-28, and from 2026-02-28 → 2026-03-28 (the day does not return to 31). This helper-level fallback is kept as is (defensive); R8a makes it unreachable for saved monthly templates that have an anchor date (best-practice default, delegated by reviewer).
- **R8a.** [BUG-363] A monthly template saved (create, or update on the merged state) with `recurrence_day` `None` gets `recurrence_day` filled from `recurrence_start_date`'s day of month, or — if that is `None` — from `next_generation_date`'s day of month; an explicitly given `recurrence_day` is kept. If neither date is set, `recurrence_day` stays `None` until the template is placed on the planning sheet (`_apply_recurrence_range` R3 stores it). So the day of month never drifts: a template anchored on 2026-01-31 runs 2026-02-28, then 2026-03-31, then 2026-04-30. *(Today: `recurrence_day` stays `None` and the day drifts per R8.)* *(Fix belongs in `app/schemas/work_order_template.py` / `WorkOrderTemplateManager.create_template` / `update_template`.)*
- **R9.** `recurrence_day` `0` is a real value, not "missing": weekly `0` targets Monday (R3), monthly `0` targets the 1st (R7). Only `None` takes the R2 / R8 paths.
- **R10.** `recurrence_day` is ignored for `daily` (any value, including `None`, `0`, `45`, `-1`).
- **R10a.** The day-range checks of R4a / R7a apply only to `weekly` and `monthly`. A `recurrence_day` sent with `recurrence_type` `daily`, or with `recurrence_type` `None` on a non-recurring template, is neither rejected nor cleared by the schemas or `update_template`: any integer (e.g. `9`, `-1`, `45`) is accepted and stored as sent, and the helper ignores it (R10); placing the template on the sheet later clears it (`_apply_recurrence_range` R4) (best-practice default, delegated by reviewer — no new rejection is introduced for a field that has no meaning for that cadence). *(Today: same.)* A recurring template with type `None` is rejected anyway by R11b, regardless of the day.
- **R11.** [BUG-360] Any other non-`None` `recurrence_type` — `""`, different case or padding (`"Daily"`, `"WEEKLY"`, `" daily"`), or unsupported values (`"biweekly"`, `"quarterly"`) — raises `ValueError` with message `Unsupported recurrence type: '<value>'` (Python `repr` of the value, e.g. `Unsupported recurrence type: 'Daily'`). Matching stays exact — normalisation is the schemas' job (R11a) (best-practice default, delegated by reviewer). *(Today: returns `from_date + 1 day`, no error.)* *(Requires a new error in this helper.)*
- **R11a.** [BUG-360] `WorkOrderTemplateCreate` / `WorkOrderTemplateUpdate` trim and lower-case `recurrence_type` (`" Weekly "` is stored as `weekly`) and reject any value outside `daily`, `weekly`, `monthly` (Pydantic `ValidationError`, 422 at the API); nothing is stored. `None` passes this check itself (see R11b). *(Today: any string up to 50 chars is stored as typed.)* *(Fix belongs in `app/schemas/work_order_template.py`; existing rows with unsupported values need a data clean-up when the fix lands.)*
- **R11b.** [BUG-361] `recurrence_type` `None` raises `ValueError('Unsupported recurrence type: None')` — the helper never guesses a cadence (message: best-practice default, delegated by reviewer). In addition, a template can never be recurring without a type: `WorkOrderTemplateCreate` rejects `is_recurring: true` with a missing/`null` `recurrence_type` (Pydantic `ValidationError`, 422), and `update_template` rejects with 422 when the resulting template (stored values merged with the payload) would be recurring with no type; nothing is stored. A non-recurring template may keep `recurrence_type` `None`. *(Today: `None` returns `from_date + 1 day`, and such templates are stored.)* *(Fix belongs in the template schema / `update_template`, plus the new error here.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-360] `recurrence_type` non-`None` and not exactly `daily`/`weekly`/`monthly` | `ValueError` | `Unsupported recurrence type: '<value>'` |
| [BUG-361] `recurrence_type` is `None` | `ValueError` | `Unsupported recurrence type: None` |

(Python's own `OverflowError` at `date.max` is out of scope.)

**Side effects:** none

---

## `_apply_recurrence_range(template, planned_date, recurrence_end_date)`
**Shape:** helper
**Persistence:** pure (mutates the passed object in memory; no flush)
**Visibility:** internal (used by: `seed_recurrence_from_planned_date`, `reseed_recurrence_program`)

**Purpose:** Anchor a recurring template's schedule to the date it was placed on the planning sheet and the chosen end date.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `template` | work order template-like object | Reads `recurrence_type`; writes four schedule fields. `is_recurring` is not checked here |
| `planned_date` | `date` | Placement date = start of the recurring range |
| `recurrence_end_date` | `date` | Last day of the range; validated per `validate_recurrence_span` |

**Returns:** `None`.

**Rules:**
- **R1.** The range `planned_date`..`recurrence_end_date` is validated first, following `validate_recurrence_span` R1–R5. On failure the `ValueError` propagates and **no** template field is changed.
- **R2.** On success, `recurrence_start_date` = `planned_date` and `recurrence_end_date` = the given end date (previous values overwritten).
- **R3.** `monthly` template: `recurrence_day` = `planned_date`'s day of month (any previously stored day is overwritten).
- **R4.** `daily` or `weekly` template: `recurrence_day` is set to `None` (a previously stored weekday is discarded, so weekly becomes "every 7 days from the placement date").
- **R4a.** [BUG-360, BUG-361] Template whose `recurrence_type` is `None` or not exactly `daily`/`weekly`/`monthly`: raises `ValueError` per `advance_next_generation_date` R11 / R11b and **no** template field is changed (the type is checked before anything is written). If the range is also invalid, the range error (R1) is raised, keeping today's validation order (best-practice default, delegated by reviewer). *(Today: the four fields are written, `recurrence_day` = `None`, `next_generation_date` = placement date + 1 day, no error.)* Through `WorkOrderManager._maybe_seed_template_recurrence` this surfaces as HTTP 400 with the message as detail.
- **R5.** `next_generation_date` = `advance_next_generation_date` applied to `planned_date` with the template's type and the day just stored — i.e. the first occurrence **after** the placement date (daily → next day; weekly → +7 days; monthly → same day next month, capped to month end). Example: monthly placed 2026-01-31 → `recurrence_day` 31, `next_generation_date` 2026-02-28.
- **R6.** `next_generation_date` is set even when it falls after `recurrence_end_date` (e.g. start = end = 2026-03-02, daily → `next_generation_date` 2026-03-03).
- **R7.** `recurrence_start_date` equal to `recurrence_end_date` is accepted (single-day range).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| end before start / span > 183 days | `ValueError` | per `validate_recurrence_span` |
| [BUG-360, BUG-361] unsupported or `None` `recurrence_type` | `ValueError` | per `advance_next_generation_date` R11 / R11b |

**Side effects:** sets `recurrence_start_date`, `recurrence_end_date`, `recurrence_day`, `next_generation_date` on `template` (in memory only).

---

## `seed_recurrence_from_planned_date(template, planned_date, recurrence_end_date)`
**Shape:** state-transition
**Persistence:** pure (mutates in memory)
**Visibility:** public (used by: `WorkOrderManager._maybe_seed_template_recurrence`)

**Purpose:** On the first placement of a recurring template, anchor its schedule to that placement — but never re-anchor an already-scheduled template.

**Inputs:** as `_apply_recurrence_range`.

**Returns:** `None`.

**Rules:**
- **R1.** Template not recurring (`is_recurring` false): nothing changes, no validation is done (an invalid range does not raise).
- **R2.** Recurring template that already has a `next_generation_date`: nothing changes, no validation is done.
- **R3.** Recurring template with `next_generation_date` `None`: schedule anchored per `_apply_recurrence_range` R1–R7 (including raising `ValueError` on an invalid range, leaving the template unchanged).

**Errors:** as `_apply_recurrence_range` (R3 path only).

**Side effects:** as `_apply_recurrence_range` on the R3 path; none otherwise.

---

## `reseed_recurrence_program(template, planned_date, recurrence_end_date)`
**Shape:** state-transition
**Persistence:** pure (mutates in memory)
**Visibility:** public (used by: `WorkOrderManager._maybe_seed_template_recurrence`)

**Purpose:** Re-anchor a recurring template's schedule when the user picks a new range on the planning sheet.

**Inputs:** as `_apply_recurrence_range`.

**Returns:** `None`.

**Rules:**
- **R1.** Template not recurring: nothing changes, no validation (an invalid range does not raise).
- **R2.** Recurring template: schedule overwritten per `_apply_recurrence_range` R1–R7, whether or not `next_generation_date` was already set (differs from `seed_recurrence_from_planned_date` R2).

**Errors:** as `_apply_recurrence_range` (R2 path only).

**Side effects:** as `_apply_recurrence_range` on the R2 path; none otherwise.

---

## `is_recurrence_program_active(template, target_date)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `should_advance_template`; no other callers)

**Purpose:** Tell whether a recurring template's schedule is still running on a given day.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `template` | template-like object | Reads `is_recurring`, `next_generation_date`, `recurrence_end_date` |
| `target_date` | `date` | Day being planned |

**Returns:** `bool`.

**Rules:**
- **R1.** Not recurring → `False`.
- **R2.** Recurring but `next_generation_date` is `None` (never anchored) → `False`.
- **R3.** `recurrence_end_date` set and `target_date` after it → `False`.
- **R4.** `target_date` equal to `recurrence_end_date` → `True` (end is inclusive).
- **R5.** `recurrence_end_date` `None` (open-ended schedule) → `True` for any `target_date`.
- **R6.** `recurrence_start_date` and the value of `next_generation_date` are not considered: a `target_date` before the start date or before the next generation date still gives `True`.

**Errors:** none.

**Side effects:** none

---

## `should_advance_template(template, target_date)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `WorkOrderTemplateManager.generate_drafts`)

**Purpose:** Decide whether the Plan-day run for `target_date` should move the template's `next_generation_date` forward.

**Inputs:** as `is_recurrence_program_active`.

**Returns:** `bool` (`True`/`False`; never a non-bool falsy value when `is_recurring` is a bool).

**Rules:**
- **R1.** `True` only when the template is recurring, has a `next_generation_date`, that date is on or before `target_date`, and the program is active per `is_recurrence_program_active` R1–R6.
- **R2.** `next_generation_date` after `target_date` (not yet due) → `False`.
- **R3.** `next_generation_date` equal to `target_date` → `True` (if active).
- **R4.** `next_generation_date` before `target_date` (overdue) → `True` (if active).
- **R5.** Due but `target_date` after `recurrence_end_date` → `False`; `target_date` equal to `recurrence_end_date` → `True`.
- **R6.** Not recurring, or `next_generation_date` `None` → `False`.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 15 | `end_date < start_date` | `validate_recurrence_span` R1, R2, R5 |
| 17 | span `> 183` days | `validate_recurrence_span` R3, R4 |
| 28 | type == `daily` | `advance_next_generation_date` R1, R10 |
| 31 | type == `weekly` | `advance_next_generation_date` R2–R4 |
| 32 | weekly, `recurrence_day is None` | `advance_next_generation_date` R2, R9 |
| 34 | `recurrence_day % 7` | `advance_next_generation_date` R4 |
| 36 | `days_ahead == 0` (same weekday) | `advance_next_generation_date` R3 |
| 40 | type == `monthly` | `advance_next_generation_date` R5–R8 |
| 41 | monthly, `recurrence_day is not None` (else `from_date.day`) | `advance_next_generation_date` R6, R8, R9 |
| 42 | clamp day to 1..31 | `advance_next_generation_date` R7 |
| 43 | `from_date.month == 12` (year rollover) | `advance_next_generation_date` R5, R6 |
| 48 | `min(day, last_day)` | `advance_next_generation_date` R6, R8 |
| 50 | fallback for any other type | `advance_next_generation_date` R11, R11b; `_apply_recurrence_range` R4a |
| 58 | range validation raises before mutation | `_apply_recurrence_range` R1 |
| 61 | type == `monthly` (else day → `None`) | `_apply_recurrence_range` R3, R4, R4a |
| 65 | next date computed from placement | `_apply_recurrence_range` R5, R6 |
| 78 | `not is_recurring` | `seed_recurrence_from_planned_date` R1 |
| 78 | `next_generation_date is not None` | `seed_recurrence_from_planned_date` R2, R3 |
| 89 | `not is_recurring` | `reseed_recurrence_program` R1, R2 |
| 96 | `not is_recurring` | `is_recurrence_program_active` R1 |
| 96 | `next_generation_date is None` | `is_recurrence_program_active` R2 |
| 98 | end date set | `is_recurrence_program_active` R5 |
| 98 | `target_date > recurrence_end_date` | `is_recurrence_program_active` R3, R4 |
| 100 | otherwise active | `is_recurrence_program_active` R6 |
| 105 | `is_recurring` falsy (short-circuit) | `should_advance_template` R6 |
| 106 | `next_generation_date is not None` | `should_advance_template` R6 |
| 107 | `next_generation_date <= target_date` | `should_advance_template` R2–R4 |
| 108 | program active | `should_advance_template` R1, R5 |

## Gap log
- G1 (work_order_recurrence.cases.md gap 1) — Fact — Overview "Notes for the test designer": `WorkOrderTemplateCreate` requires only `template_name` and `work_order_type_id` (existence not checked by the schema); minimal valid payload given; `WorkOrderTemplateUpdate` has no required fields.
- G2 (work_order_recurrence.cases.md gap 2) — Intent, decided by best practice (delegated by reviewer) — new `advance_next_generation_date` R10a: `recurrence_day` with a `daily` or untyped non-recurring template is accepted and stored as sent (no range check, not cleared); matches today, no new bug.
- G3 (work_order_recurrence.cases.md gap 3) — Intent, decided by best practice (delegated by reviewer) — new `advance_next_generation_date` R4b: `WorkOrderTemplateUpdate` alone does no day-range check even with type and day in one payload; the check lives only in `update_template` on the merged state (R4a / R7a); matches today, no new bug.
