# Spec — `app/utils/time.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
No questions.

## Overview
Single helper that returns the current moment in UTC as a *naive* `datetime`
(no `tzinfo`). The database stores `TIMESTAMP WITHOUT TIME ZONE` and the whole
codebase treats those values as UTC; this helper is the replacement for the
deprecated `datetime.utcnow()` and keeps that contract. It is imported by ~79
modules across the app and is the `utcnow` that other modules' tests mock.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none (the function itself is the thing others mock; to
pin its output in its own test, freeze the clock, e.g. patch
`app.utils.time.datetime` or use a time-freezing library)
**Integration-only behavior:** none

**Notes for the test designer:** pure function, no DB needed. Test by comparing
against real clock bounds taken immediately before and after the call
(`before <= result <= after`, with bounds computed as naive UTC), or by freezing
time and asserting an exact value. Do not compare against local time — the
test machine may not be in UTC.

## Not specified
_(none)_

---

## `utcnow()`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (used by: managers, services, DAOs, models across the app)

**Purpose:** Give the current time in UTC, in the naive form the database columns expect.

**Inputs:** none

**Returns:** a `datetime.datetime` instance.

**Rules:**
- **R1.** The returned value is naive: its `tzinfo` is `None`.
- **R2.** The returned value is the current wall-clock time in **UTC**, not
  local time: it lies between a naive-UTC reading taken just before the call
  and one taken just after (inclusive). On a machine whose local timezone is
  not UTC it differs from `datetime.now()` (local) by the local UTC offset.
- **R3.** With the clock frozen at an aware instant, the result equals that
  instant converted to UTC with `tzinfo` removed (e.g. frozen at
  `2026-01-15 10:30:45.123456+00:00` → `datetime(2026, 1, 15, 10, 30, 45, 123456)`);
  microsecond precision is preserved.
- **R4.** Successive calls never go backwards when the system clock does not
  (second result `>=` first).

**Errors:** none

**Side effects:** none

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 17 | no decision points (single straight-line return) | R1–R4 |
