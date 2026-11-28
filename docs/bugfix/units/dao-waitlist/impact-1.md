# Impact review 1: dao-waitlist

Date: 2026-11-27. Reviewer: systems engineer (stage 3). Diff: `git diff origin/main -- app alembic`
in `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-waitlist`: `app/dao/waitlist.py` only, no
migration.

## Changes

1. New private `WaitlistDAO._ILIKE_ESCAPE = "\\"` and staticmethod `_escape_ilike` (backslash
   doubled first, then `%` / `_` prefixed). Identical to `app/dao/help_ticket.py:16-23`.
2. `list_signups`: search term escaped after trim + lower; `ilike(term, escape="\\")`. (BUG-1410)
3. `list_signups`: `ORDER BY created_at DESC, id DESC` before offset/limit. (BUG-1411)

## Upstream

- Only caller of `list_signups`: `WaitlistService.list_signups` (`app/services/waitlist_service.py:114-137`),
  pure pass-through into `WaitlistSignupListResponse(items, total, skip, limit)`. No re-sort, no
  set conversion, no merge with another path. Endpoint `GET /waitlist`
  (`app/api/v1/endpoints/waitlist.py:45`) validates `skip>=0`, `1<=limit<=500`,
  `search max_length=320`, so the DAO's DataError branches are unreachable from the API (unchanged).
- Return shape, types, errors unchanged. `get_by_email`, `create_signup`, `update_status`,
  inherited `BaseDAO` methods untouched (grep of `waitlist_dao` across `app/`: service lines 79,
  83, 96, 104, 110, 124 only).

## Downstream

- No locks, no other DAO, no commit. Transaction contract unaffected.

## Query shape (compiled, Postgres dialect, and run against `bf_dao_waitlist_test`)

```
SELECT ... FROM waitlist_signups
WHERE waitlist_signups.email ILIKE %(email_1)s ESCAPE '\'
ORDER BY waitlist_signups.created_at DESC, waitlist_signups.id DESC
LIMIT %(param_1)s OFFSET %(param_2)s
params: {'email_1': '%a\_b\\c\%%', ...}   # search "  A_b\c% "
```

- ORDER BY uses ORM columns only; exactly two keys, `created_at` then `id`, both DESC; no
  `nulls_last`, no `text()`. Low risk against a strict SQL-text check.
- Count runs on the same filtered query before ordering/paging (HR-5 kept).
- Live run (rolled back), six rows sharing one `now()`: `a_b` -> only `a_b`; `p%q` -> only `p%q`;
  `c\d` -> only `c\d`; `%` -> only `p%q`; `SE_A` (case) -> both rows containing literal `se_a`;
  `"   "` and `""` -> all six (R2a unchanged); ids strictly descending; pages of 2 at skip 0/2/4
  give each row exactly once in id-descending order. `standard_conforming_strings=on`; the
  `ESCAPE '\'` literal is accepted.

## Workspace bound (HR-16)

Not applicable: `waitlist_signups` is platform data, no `workspace_id`.

## API contract

- `GET /waitlist?search=`: `%`, `_`, `\` now match literally; results for such searches shrink
  (or, for `\`, now find the row they should). Searches without those characters return the same
  rows. Order within one `created_at` is now fixed (id descending). No status code, field, message
  or input change. See `contract.md`: no contract change requiring frontend work.
- Frontend (`../frontend/src/pages/newpages/platform/PlatformWaitlistPage.tsx`) sends the trimmed
  box text as `search`; it never relied on wildcards.

## Database

No constraint, index or migration. No check script needed.

## Neighbouring bugs

- None open in `app/dao/waitlist.py` besides the two targets. BUG-1579 (schema), BUG-1580
  (service), BUG-540/541 (`core/waitlist_admin.py`) untouched and not affected.
- Shared ILIKE helper (follow-up F8) still pending; this adds one more private copy, as the brief
  required.

## Shortcuts / scope

- No special-casing; escape applied to every search. Nothing changed beyond the brief. Line wrap
  of the filter call is cosmetic. `.lower()` kept per spec (harmless under ILIKE; lowering does
  not affect `\`, `%`, `_`).

## New bugs found

- Pattern `ui-text-mismatch` (frontend note, not this unit):
  `../frontend/src/pages/newpages/platform/PlatformWaitlistPage.tsx:103`. Title: waitlist search
  box says "Search email or name" but only the email is searched. Today: placeholder promises name
  search; backend searches email only (spec `list_signups` R2a). Intended: placeholder says
  "Search email…" (or the backend gains name search, owner's call). For the orchestrator to log
  as a frontend note.

## Notes for docs/future

None.

## Verdict

**APPROVE.** No blocking finding. Contract: no change requiring frontend work.
