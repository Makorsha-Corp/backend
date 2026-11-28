# Impact review 1: dao-workspace_invitation

Date: 2026-11-27. Diff: `git diff origin/main -- app alembic` in the unit worktree (one file, `app/dao/workspace_invitation.py`; no alembic change).

**Verdict: APPROVE.**

## Changed functions

| Function | Change |
|---|---|
| `get_pending_invitations` | `ORDER BY invited_at DESC, id DESC` |
| `get_all_invitations` | same order |
| `get_user_invitations` | same order; filter now `lower(trim(email)) = <arg>.strip(" ").lower()` |

`get_by_token`, `count_pending_invitations`, the singleton, imports (only `func` added) and signatures are unchanged.

## Upstream

- `get_pending_invitations` / `get_all_invitations`: only `WorkspaceService.list_invitations` (`app/services/workspace_service.py:265-267`) -> `GET /workspaces/{id}/invitations/`. It enriches in a list comprehension in DAO order; no re-sort, no set. The new order reaches the endpoint intact.
- `get_user_invitations`: only `WorkspaceService.get_my_invitations` (`:347`) -> `GET /workspaces/me/invitations/`. Same: list comprehension, order kept.
- `count_pending_invitations` (manager seat check) untouched, so the plan-limit count is unchanged.
- Grepped `workspace_invitation_dao`, `invitation_dao.` and the three method names across `app/`: no other caller.

## Downstream / query shape

Compiled with the Postgres dialect from the worktree:

```
WHERE lower(trim(workspace_invitations.email)) = 'a@x.com' AND status = 'pending' AND expires_at > ...
ORDER BY workspace_invitations.invited_at DESC, workspace_invitations.id DESC
```

Both other lists end in the same two-key ORM `ORDER BY`. ORM columns, table-qualified, exactly two keys, no `NULLS` extras (`invited_at` is NOT NULL). Equality, not LIKE, so `_`/`%` stay ordinary characters and substrings never match (R2a). No locks, no commit.

## Workspace bound (HR-16)

Unchanged: the two workspace lists filter on `workspace_id`; "my invitations" reads across workspaces by design (brief §4).

## Points judged

**(a) Stored email with surrounding spaces: listed, but accept fails. Reachable?** No, not through the app. The only writer of `workspace_invitations` is `WorkspaceManager.create_invitation` (`:373`, `email.lower()`), called only from `WorkspaceService.create_invitation`, fed by `InviteUserRequest.email: EmailStr`. Pydantic's `EmailStr` strips all surrounding whitespace before the value reaches the manager (checked: `' a@x.com '` -> `'a@x.com'`, `'\ta@x.com\n'` -> `'a@x.com'`). No other constructor of `WorkspaceInvitation` exists in `app/`, `scripts/` or `alembic/`. So a padded row can only come from a manual SQL write or old data. The mismatch with the accept check (`invitation.email.lower() != user_email.lower()`, no trim) is theoretical, and nobody could see it today. **No bugs.md row.** The stored-side trim is cheap protection for that kind of data, which is what the brief asks for ("on both sides"). If the owner ever imports invitations in bulk, the accept check should trim too. That belongs with the `WorkspaceManager` unit (BUG-1987 is already there for its expiry boundary).

**(b) Trimming only the space character.** That matches the brief and spec R2 ("surrounding spaces"; every example uses plain spaces), and it is the symmetric choice the tester's precheck asked for (SQL `trim()` strips spaces only, so Python `strip(" ")` is right and bare `strip()` would be inconsistent). Tabs and newlines can't reach either side through the app, because `EmailStr` strips them on input. The account email passed in comes from the profile, which is also written through `EmailStr`. Accepted.

**(c) `func.lower(func.trim(email))` with no index.** Fine. `email` has no index today (model: indexes on `id`, `workspace_id`, `token`, `status` only), so the old exact match was already a scan or a `status`-index filter. The predicate is still combined with `status = 'pending'` (indexed) and `expires_at`. The table holds open invitations bounded by each plan's `max_members`, so it is small. A functional index would need a migration, which the brief rules out. If it is ever needed, it is a later performance item, not something this unit blocks on.

## API contract

Shape, status codes and errors are unchanged. Visible differences: both lists now come back newest first, and "my invitations" now includes invitations whose stored email differs from the account email only in letter case. See contract.md (no frontend change).

## Database

No migration, constraint or index. No check script needed.

## Neighbouring bugs

- BUG-1860-1862 (`profile.py`, account email capitals): independent. Once those are fixed, account emails may be stored lower-cased and this match still works.
- BUG-2252 (service reads one related row per entry): untouched, still open.
- BUG-1873/1874 (duplicate open invitations to one email): untouched. "My invitations" may now show such duplicates that it previously missed because of case. That is correct per R1 and the manager unit's concern.
- BUG-1987 / BUG-2561 (expiry boundary): untouched.

## Shortcuts / scope

No special-casing, and nothing outside the brief. Same order recipe as `help_ticket.py`, `attachment_link.py` and `account_invoice.py`.

## New bugs found

None.
