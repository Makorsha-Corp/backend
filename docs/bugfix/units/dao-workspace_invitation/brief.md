# Fix brief: dao-workspace_invitation

## 1. Unit

| | |
|---|---|
| Slug | `dao-workspace_invitation` |
| Source file | `app/dao/workspace_invitation.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-workspace_invitation` |
| Branch | `bugfix/dao-workspace_invitation` (from `origin/main`) |
| Risk | `normal` (BUG-1401 `unordered-pagination` is a trivial-list pattern; BUG-1402 `case-sensitive-email-match` is not, and it touches who sees which invitation). Not money, stock or order workflow. BUG-1402's intended behaviour is settled by its row and is consistent with the owner's answer on account emails (OQ-1, below): it shows a person only invitations they can already accept. |

## 2. Bugs

### BUG-1401: Invitation lists have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `WorkspaceInvitationDAO.get_pending_invitations`, `get_user_invitations`, `get_all_invitations`; reached through `GET /workspaces/{id}/invitations/` (with and without `include_expired`) and `GET /workspaces/me/invitations/`.
- **Today:** No `ORDER BY`: four invitations came back `1, 2, 3, 0` after the first was updated.
- **Intended:** HR-6: newest first, `invited_at` descending, then `id` descending (BUG-1210 precedent; decided by Claude under the reviewer's delegation (2026-11-03)).
- **Precedent BUG-1210, in words:** a list of dated records is ordered newest first by its date or time, and `id` descending is added as the last key so rows with the same time keep one fixed order.
- **Why ties happen:** `invited_at` is filled by the model's Python default `utcnow()` per row, so two rows can share a value (and rows may be given one explicitly).

### BUG-1402: "My invitations" misses an invitation when the account email has capitals
- **Pattern:** `case-sensitive-email-match`
- **Where:** `WorkspaceInvitationDAO.get_user_invitations`; reached through `GET /workspaces/me/invitations/` (the service passes the current user's stored email).
- **Today:** Exact email match. Invitations are stored lower-cased by `create_invitation`; accounts keep the capitals of the local part, so `John.Doe@example.com` never sees `john.doe@example.com`'s invitation (though accepting it works: that check is case-insensitive).
- **Intended:** The email is matched ignoring case and surrounding spaces on both sides (decided by Claude under the reviewer's delegation (2026-11-03)). Independent of the account-email question (profile DAO Q1, owner).
- **Example:** The owner invites `john.doe@example.com`. John registered as `John.Doe@example.com`. Today his "Invitations" panel is empty, although the link in the email would let him accept. After the fix he sees it. Asking with ` john.doe@example.com ` (spaces around) finds it too, and so does a row stored as `John.Doe@Example.com`. `a@y.com` never finds `a@x.com`'s invitation.

## 3. Intended behaviour (spec rules, copied)

**What this class is.** `WorkspaceInvitationDAO` reads `workspace_invitations`: an email invited into a workspace with a role, a random `token` (the secret in the invitation link), a free-text `status` (`pending`, `accepted`, `cancelled`) and an `expires_at`. "Pending" in this DAO means `status` exactly `'pending'` **and** not yet expired: nothing ever sets `status = 'expired'`. Callers: `WorkspaceManager` (create, validate by token, count against the plan limit), `AuthService.validate_invitation_token` and the registration-by-invitation path (by token), `WorkspaceService` (the two lists). It never commits.

**Table facts (`workspace_invitations`).** `workspace_id` FK CASCADE NOT NULL; `email` VARCHAR(255) NOT NULL, stored as given (no lower-casing in this DAO); `role` VARCHAR(50) NOT NULL; `token` VARCHAR(255) NOT NULL, unique index `ix_workspace_invitations_token`; `status` VARCHAR(50) NOT NULL, Python default `'pending'`, indexed, no check; `invited_at` NOT NULL, Python default `utcnow()`; `expires_at` NOT NULL, no default; `accepted_at`, `accepted_by_user_id` (FK SET NULL), `invited_by_user_id` (FK SET NULL), `position` nullable. All timestamps `timestamp without time zone`, naive UTC. No soft delete. The clock is the module-level `utcnow` imported by name into this file (keep reading it that way). Every parameter after `db` is keyword-only in every method.

### `get_by_token(db, *, token)` (not in a bug; must not change)
Used by `WorkspaceManager.validate_invitation_for_user`, `AuthService.validate_invitation_token`; reached by accepting an invitation, registering with one, and `POST /auth/validate-invitation/`. Returns the `WorkspaceInvitation`, or `None`.
- **R1.** Given a row with exactly that token, it is returned whatever its status and expiry (accepted, cancelled and expired rows included: the callers turn those into their own messages).
- **R2.** The match is exact: the same token in other case, or an unknown token, gives `None`. Tokens are unique, so at most one row matches. Not scoped to a workspace: the token is the credential.
- Errors: none of its own. Side effects: none.

### `get_pending_invitations(db, *, workspace_id)`
Used by `WorkspaceService.list_invitations` ← `GET /workspaces/{id}/invitations/` without `include_expired`. Returns a `list` of `WorkspaceInvitation` (possibly empty).
- **R1.** Returns the rows of that workspace whose `status` is exactly `'pending'` (`'Pending'` is left out) and whose `expires_at` is later than `utcnow()`.
- **R2.** An invitation whose `expires_at` equals `utcnow()` exactly, or is earlier, is left out; one microsecond later is kept. A pending row that has expired keeps `status = 'pending'` in the table and is simply not listed.
- **R3.** Rows of another workspace never appear. An unknown workspace or `0` gives `[]`. No paging, no cap.
- **R4.** [BUG-1401] (HR-6) Ordered by `invited_at` descending, then `id` descending. *(Today: no `ORDER BY`.)*
- Errors: none of its own. Side effects: none.

### `get_user_invitations(db, *, email)`
Used by `WorkspaceService.get_my_invitations` ← `GET /workspaces/me/invitations/`, with the current user's stored email. The invitations waiting for one person, from every workspace. Returns a `list` of `WorkspaceInvitation` (possibly empty).
- **R1.** Returns the rows with that email that are pending and not expired, as `get_pending_invitations` R1, R2, from **every** workspace (by email on purpose: the user's own invitations from any workspace).
- **R2.** [BUG-1402] The email is matched ignoring case and surrounding spaces on both sides: asked `John.Doe@example.com` or ` john.doe@example.com `, a row stored `john.doe@example.com` (or `John.Doe@Example.com`) is returned. *(Today: exact match; `b@x.com` does not find `B@x.com`, ` a@x.com` does not find `a@x.com`.)*
- **R2a.** What holds today and after the fix: another email (`a@y.com` for `a@x.com`) is never matched; an unknown email gives `[]`. In words: the comparison stays a whole-value equality after trimming and lower-casing, not a pattern or substring match (`doe@example.com` does not find `john.doe@example.com`; `_` is an ordinary character, so `john_doe@example.com` does not find `john.doe@example.com`).
- **R3.** No paging, no cap.
- **R4.** [BUG-1401] Ordered as `get_pending_invitations` R4 (`invited_at` descending, then `id` descending). *(Today: no `ORDER BY`.)*
- Errors: none of its own. Side effects: none.

### `count_pending_invitations(db, *, workspace_id)` (not in a bug; must not change)
Used by `WorkspaceManager.create_invitation`, added to the active members and compared with the plan's `max_members`. Returns `int`.
- **R1.** Counts exactly the rows `get_pending_invitations` returns (its R1–R3), one per row: two pending invitations to the same email count 2.
- **R2.** An unknown workspace, `0`, or none pending gives `0`.
- Errors: none of its own. Side effects: none.

### `get_all_invitations(db, *, workspace_id)`
Used by `WorkspaceService.list_invitations` with `include_expired=True`. Every invitation of a workspace, whatever its state. Returns a `list` of `WorkspaceInvitation` (possibly empty).
- **R1.** Returns every row of that workspace: pending, expired, accepted, cancelled, any other status. Rows of another workspace never appear; an unknown workspace or `0` gives `[]`.
- **R2.** No paging, no cap. Does not read the clock.
- **R3.** [BUG-1401] Ordered as `get_pending_invitations` R4 (`invited_at` descending, then `id` descending). *(Today: no `ORDER BY`.)*
- Errors: none of its own. Side effects: none.

### Inherited generic methods and the singleton (must not change)
- `workspace_invitation_dao` is the module-level singleton; keep its name.
- Inherited `BaseDAO` methods stay as they are. In particular: `create` with `WorkspaceInvitationCreate` works (it carries `workspace_id`; `EmailStr` lowers the domain only, so `New@Example.COM` is stored `New@example.com`); a taken `token` raises `IntegrityError` (`UniqueViolation`, pgcode `23505`); a `token` over 255 characters raises `DataError` (pgcode `22001`). `get` (unscoped) is what `WorkspaceManager.accept_invitation` and `cancel_invitation` use.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** No order recipe counts as deterministic unless it ends in `id`. For dated records the chosen order here is newest first (`invited_at` descending) with `id` descending last (BUG-1210 precedent).
- **HR-4 scope:** raw lookups stay raw: `get_by_token` matches the token exactly, and this file has no soft-delete filter to add.
- **HR-16. Nothing links across workspaces.** The workspace lists filter on the row's `workspace_id`; `get_by_token` and `get_user_invitations` read across workspaces by design (the token is the credential; a person's own invitations come from any workspace). Keep that.
- **OQ-1 (owner, 2026-11-04), account emails:** "an email identifies one account whatever its capitals" (login, registration and the account's stored email are fixed elsewhere: `app/dao/profile.py`, BUG-1860–1862). BUG-1402 does not depend on that fix; it is the same principle applied to "my invitations", and matches how accepting an invitation already compares emails (case-insensitively).
- No other owner answer touches these bugs. (OQ-3, two open invitations to one email taking two seats, is about `WorkspaceManager`, not this file; see §6.)

## 5. Scope

- May change: `app/dao/workspace_invitation.py` only.
- No migration, no schema or API change. Method signatures and return types stay as they are. `count_pending_invitations` and `get_by_token` keep their behaviour.

## 6. Out of scope (leave alone)

- `app/managers/workspace_manager.py`: BUG-1871 ("unlimited" plan cannot send invitations), BUG-1872 ("unlimited" plan cannot add members), BUG-1873 (two open invitations to one email take two seats), BUG-1874 (accepting one leaves the others pending), BUG-1981 and BUG-1986 (cancel reveals other workspaces' or hidden invitations), BUG-1982 (removed member can be invited back but never accept), BUG-1983 (invitation to a suspended member holds a seat), BUG-1985 (new member row does not record the inviter), BUG-1987 (accept's expiry boundary differs from the lists), BUG-1989 (deferred, `max_members = 0`).
- `app/services/workspace_service.py`: BUG-2251 (cancel refusals answer 403), BUG-2252 (invitation lists read one related row per entry).
- `app/services/auth_service.py`: BUG-2561 (invitation preview at the exact expiry instant), BUG-2563 (registration audit rows lack IP and user agent).
- `app/schemas/workspace_invitation.py`: BUG-2256 (unchecked lengths).
- `app/dao/profile.py`: BUG-1860, BUG-1861, BUG-1862 (account email capitals).
