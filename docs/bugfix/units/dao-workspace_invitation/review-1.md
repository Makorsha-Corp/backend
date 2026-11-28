# Code review 1: dao-workspace_invitation (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 0)
Diff reviewed: 092776b..c6b9a87, files: app/dao/workspace_invitation.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-1401:** `get_pending_invitations`, `get_user_invitations` and
  `get_all_invitations` each get `ORDER BY invited_at DESC, id DESC` in SQL.
  Rows with the same `invited_at` must come back in `id`-descending order.
  `count_pending_invitations` must not change (an ORDER BY would not help a
  count). `get_by_token` must not change.
- **BUG-1402:** `get_user_invitations` must compare the stored email and the
  argument as whole values after trimming and lower-casing **both** sides:
  `lower(trim(email)) = <normalised arg>`. It must not use `ILIKE` or `LIKE`,
  because then `_` and `%` would act as wildcards and break R2a. The pending
  and expiry filters stay exactly as they were. The trim on each side must
  strip the same characters. The brief says "spaces", and Postgres `trim()`
  strips only spaces by default.
- Must not change: method signatures, keyword-only parameters, the singleton
  name, how `utcnow` is imported by name, the workspace scoping of the two
  workspace lists, and the unscoped by-email/by-token reads (HR-16 as the brief
  describes it). No migration.
- Index: if `email` had an index, a `lower(trim(...))` filter would stop it
  being used. Check this.

## 2. Findings

### R1-1 [minor] Lower-casing happens in Python for the argument and in Postgres for the column, so a few non-ASCII letters do not match
- Where: app/dao/workspace_invitation.py:37 and :41 (`get_user_invitations`)
- Problem: the argument goes through Python `str.lower()` and the column goes
  through Postgres `lower()`. These two agree on ASCII and on common Latin
  letters, but not on every Unicode character. The accept path
  (app/managers/workspace_manager.py:439) lower-cases both sides in Python, so
  for these characters a person could accept an invitation that "my
  invitations" does not show.
- Evidence: checked against the test database (collation
  `English_United States.1252`). `É` agrees on both sides (`é`). `İ`: Postgres
  gives `İ`, Python gives `i̇` (two code points). `ẞ`: Postgres gives `ẞ`,
  Python gives `ß`. So an invitation stored with these capitals is not found.
- Suggested direction: normalise both sides in the same engine, for example
  lower-case the argument in SQL as well, or accept this as an out-of-scope
  edge case. Email local parts with these letters are very rare. Owner's call;
  this does not block.

## 3. Questions (unproven)

- None that affect this change. A side note: tabs and newlines around an email
  are not trimmed, on purpose. The brief says "spaces", and the code comment
  explains why the two sides match. I checked that a row stored with a leading
  tab is not returned, and that is consistent.

## 4. What is good

- The change is as small as it can be and matches my expectation in §1 exactly.
  It touches three `ORDER BY` lines and one filter. `count_pending_invitations`
  and `get_by_token` are unchanged. There are no stray edits, and `ruff check`
  passes.
- The order recipe follows the codebase's existing newest-first convention
  (`app/dao/help_ticket.py:119`, `app/dao/attachment_link.py:88`,
  `app/dao/account_invoice.py:192`).
- The comparison is whole-value equality, not `ILIKE`, so `_` and `%` in an
  email are not wildcards. The trimmed character set is the same on both sides
  (Python `strip(" ")` and Postgres `trim()`), and the code comment explains
  why.
- No index is lost: the baseline has no index on `workspace_invitations.email`
  (alembic/versions/100_squashed_baseline.sql:7572-7596).
- Live check (rolled back) on `bf_dao_workspace_invitation_test`:
  - `John.Doe@example.com` and ` john.doe@example.com ` both return the rows
    stored as `john.doe@example.com`, `John.Doe@Example.com` and
    ` john.doe@example.com `, newest first with ties broken by `id`
    descending.
  - The rows `john_doe@…`, `doe@…`, accepted and expired are left out.
  - `a@y.com` and `john%` return `[]`.
  - The workspace lists come back as `invited_at` descending, then `id`
    descending.
  - The count is unchanged, and `get_by_token` with the token in upper case
    still returns `None`.
