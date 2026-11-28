# Code review 1: dao-help_ticket (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 2)
Diff reviewed: 614bbce..7a24870, files: app/dao/help_ticket.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-1441.** `create_with_user` takes the year from `app.utils.time.utcnow()`,
  not `datetime.now()`. The `datetime` import is dropped if nothing else uses it.
  `generate_ticket_number` and the numbering logic stay as they are (BUG-1440 is
  out of scope).
- **BUG-1442.** Both `list_by_workspace` and `list_platform` order by
  `created_at DESC, id DESC` in SQL, before `OFFSET`/`LIMIT`. Filters, the
  joinedload of `creator` and the return shapes stay the same. Paging over tied
  rows must give every row exactly once.
- **BUG-1443.** In `list_platform`, the trimmed search text escapes `\` first, then
  `%` and `_`, and all four `ILIKE`s declare the escape character. Matching stays
  case-insensitive and substring. `None` / `""` give no filter, and only spaces
  still match everything (R3, R4). The workspace-name match is escaped too. The
  repo's way of doing this (if it has one) should be followed.
- No change to signatures, other methods, workspace scoping (HR-16) or the API.

## 2. Findings

### R1-1 [minor] The ticket year and `created_at` come from two different clocks
- Where: app/dao/help_ticket.py:49 (`create_with_user`)
- Problem: the year now comes from the Python process's UTC clock. `created_at`
  is the database's `now()`, which is the time the transaction started. If a
  transaction starts just before 00:00 UTC on 1 January and reaches this line just
  after, the ticket is `HELP-2027-…` while `created_at` is still 2026. The code
  comment on line 48 says the two "agree", which holds except in that window.
- Evidence: reasoning from the brief's own column facts (`created_at` = the
  transaction's `now()`). I did not reproduce it, because it needs two clocks to
  disagree across a year boundary. The brief asks for exactly `utcnow().year` (the
  BUG-1334 precedent), so the change meets the requirement.
- Suggested direction: none needed for this unit. The comment could say "UTC
  year" rather than claim agreement with `created_at`.

### R1-2 [nit] Copy of the `account_invoice` escape helper
- Where: app/dao/help_ticket.py:16-23
- `_ILIKE_ESCAPE` / `_escape_ilike` repeat app/dao/account_invoice.py:24-28 line
  for line. That matches the existing convention, and the brief limits the change
  to this one file. A shared helper (for example in `app/utils`) would be a later
  refactor across both DAOs, not something to do here.

### R1-3 [nit] `_escape_ilike` could be one expression
- Where: app/dao/help_ticket.py:21-23. The two reassignments of `escaped` mirror
  account_invoice exactly, so they are consistent. Style only.

## 3. Questions (unproven)

- None.

## 4. What is good

- The diff is small and stays in the brief's scope. It touches no signatures and
  makes no drive-by edits. The unused `datetime` import is removed, and `ruff check`
  passes.
- The escape order is right: `\` first, then `%` and `_`. I checked it against
  marker_test (rolled back):
  - `a_b` finds only "a_b", not "axb".
  - `50%` finds only "50%", not "50 x".
  - A single `\` finds only titles that contain a backslash.
  - `a\\b` finds only a title with a double backslash.
  - `a\_b` and `a\%` find nothing.
  - `A_B` still finds "a_b", so matching stays case-insensitive.
  - Space-only and empty searches still match every ticket.
  - The escaped workspace-name match works: `zeta_w` finds every ticket of
    workspace "Zeta_Works", and `zeta%` finds none.
- The tie-break is in SQL, before paging, in both list methods. Seven tickets
  created in one transaction (so with the same `created_at`) came back in id
  order, newest first, in both lists. Paging them two at a time gave every ticket
  exactly once. `list_by_workspace` with `creator` access is still one statement.
- With the process clock faked to 2026-12-31 20:00 UTC (02:00 on 1 January local
  time), `create_with_user` gave `HELP-2026-001`, with type `support` and status
  `pending`.
- It follows the established escape pattern (app/dao/account_invoice.py:22-35,
  60) rather than inventing a new one.
