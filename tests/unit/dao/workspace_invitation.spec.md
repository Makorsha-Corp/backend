# Spec — `app/dao/workspace_invitation.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** Q1 (BUG-1402) and the order of BUG-1401 were decided by Claude under the reviewer's delegation (2026-11-03). Neither is the owner's own answer. One owner item about plan seats is parked in `docs/testing/owner-questions.md` (OQ-3); it is about `WorkspaceManager`, not a rule of this DAO, and does not block this spec.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `facts.py`, `v_ws.py`, `v_plan.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns, defaults, constraints and indexes; the SQL of every method (no `ORDER BY`); pending, `Pending`, accepted and expired rows, another workspace, `0`; the expiry boundary with `utcnow` patched (equal → left out, one microsecond before → kept); `B@x.com` stored, `b@x.com` asked → not found; two pending invitations to one email counted twice; the unique token; the order of `get_pending_invitations` and `get_all_invitations` under a forced sequential scan (`1, 2, 3, 0` after the first row was updated); a schema create (`New@Example.COM` stored as `New@example.com`). **Not run:** anything over HTTP; the intended behaviour of the bug rules.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | "My invitations" finds an invitation only when the account's email has exactly the same capital letters as the stored one; invitations are stored in lower case | bug — compare case-insensitively (BUG-1402) | Claude, delegated |

Decided by a house rule: the three invitation lists have no sort order (BUG-1401, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_pending_invitations` R4, `get_user_invitations` R4, `get_all_invitations` R3 — no `ORDER BY`. Verified: four invitations came back `1, 2, 3, 0` after the first was updated. These are the invitations page (`GET /workspaces/{id}/invitations/`) and the user's own list (`GET /workspaces/me/invitations/`). Intended: newest first — `invited_at` descending, then `id` descending (BUG-1210 precedent for dated records; an invitation's email is not a display name). Decided by Claude under the reviewer's delegation (2026-11-03).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1401 (pattern `unordered-pagination`). Rules: `get_pending_invitations` R4, `get_user_invitations` R4, `get_all_invitations` R3.

Checked and **not** a new line here: **HR-4** — no soft-delete column; a cancelled invitation keeps its row with `status = 'cancelled'`; workspaces have no soft delete. **HR-5** — every filter is in the query. **HR-7** — nothing pages. **HR-8** — no `LIKE`. **HR-9** — no audit columns. **HR-10** — the DAO only reads; accept and cancel change state in `WorkspaceManager` (that module's review). **HR-16** — every list is scoped by workspace except `get_user_invitations`, which is by email on purpose (the user's own invitations from any workspace).

### New questions

### Q1. "My invitations" is case-sensitive on the email — 🐞 BUG-1402
**Background:** `WorkspaceManager.create_invitation` stores the invited email in lower case (`email.lower()`). An account's email keeps the capital letters of its local part as typed at registration (`John.Doe@example.com`; only the domain is lowered). Accepting an invitation already compares the two emails case-insensitively (`validate_invitation_for_user`).
**What happens today:** `get_user_invitations` compares the email exactly, so an account `John.Doe@example.com` never sees an invitation stored as `john.doe@example.com`. (Verified: stored `B@x.com`, asked `b@x.com` → nothing.)
**Example:** The owner invites `john.doe@example.com`. John registered as `John.Doe@example.com`. His "Invitations" panel is empty, although the link in the email would let him accept.
**Rules affected:** `get_user_invitations` R2
**Suggested answer:** `bug — match the email case-insensitively and ignoring surrounding spaces on both sides`, as the accept check does. It shows John nothing he could not already accept. Alternative: `intended` — then John only finds the invitation through the email link.
**Answer:** bug — match case-insensitively, both sides trimmed and lowered
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1402 (pattern `case-sensitive-email-match`). Whether account emails themselves should be case-insensitive is a separate owner question (profile DAO Q1, OQ-1); this fix does not depend on it. Rules: `get_user_invitations` R2 (tagged), R2a (untagged — what already holds).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Workspace manager** (`create_invitation`) — **OWNER, plan seats** | Its docstring says "Email not already invited (pending)", but nothing checks it: two pending invitations to one email are both counted by `count_pending_invitations` and take two seats (verified: on a 3-seat plan, the owner plus two invitations to `a@x.com` block a third invitation). Accepting one leaves the other pending and counted until it expires (3 days). Parked as OQ-3. | `count_pending_invitations` R1 |
| FU-2 | **Workspace manager** (`validate_invitation_for_user`) | Expired means `expires_at < now` there, while the lists here treat `expires_at <= now` as expired: at the exact expiry instant an invitation can be accepted but is no longer listed. One microsecond; noted only. | `get_pending_invitations` R2 |
| FU-3 | **Workspace service** (`get_my_invitations`) | Lists invitations to workspaces the user is already an active member of; whether to hide them is that review's call. | `get_user_invitations` |

## Overview
`WorkspaceInvitationDAO` reads `workspace_invitations`: an email invited into a workspace with a role, a random `token` (the secret in the invitation link), a free-text `status` (`pending`, `accepted`, `cancelled`) and an `expires_at`. "Pending" in this DAO means `status` exactly `'pending'` **and** not yet expired: nothing ever sets `status = 'expired'`. Callers: `WorkspaceManager` (create, validate by token, count against the plan limit), `AuthService.validate_invitation_token` and the registration-by-invitation path (by token), `WorkspaceService` (the two lists). It never commits.

**Callables:** 5 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** `utcnow` — patch `app.dao.workspace_invitation.utcnow` (imported by name into this module).
**Integration-only behavior:** none

**Model facts (table `workspace_invitations`):** `workspace_id` FK CASCADE NOT NULL; `email` VARCHAR(255) NOT NULL, stored as given (no lower-casing here); `role` VARCHAR(50) NOT NULL; `token` VARCHAR(255) NOT NULL, **unique index `ix_workspace_invitations_token`**; `status` VARCHAR(50) NOT NULL, Python default `'pending'`, indexed, no check; `invited_at` NOT NULL Python default `utcnow()`; `expires_at` NOT NULL, no default; `accepted_at`, `accepted_by_user_id` (FK SET NULL), `invited_by_user_id` (FK SET NULL), `position` nullable. All timestamps `timestamp without time zone`, naive UTC. No soft delete.

**Notes for the test designer:** `from app.dao.workspace_invitation import workspace_invitation_dao`. Build `WorkspaceInvitation(workspace_id, email, role, token, status, expires_at)` directly; every token unique. Every parameter after `db` is keyword-only. Patch `utcnow` to a fixed naive datetime and set `expires_at` relative to it. **BUG-1401:** give the rows distinct `invited_at` values out of `id` order, plus two rows with one `invited_at` for the `id` tie-break; today's order rests on physical order → **non-strict** xfail. **BUG-1402:** today's result is deterministic (nothing found) → **strict** xfail.

## Not specified
- `workspace_invitation_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec. Specific here: `create` with `WorkspaceInvitationCreate` works (it carries `workspace_id`; `EmailStr` lowers the domain only, so `New@Example.COM` is stored `New@example.com`); a taken `token` raises `IntegrityError` (`UniqueViolation`, pgcode `23505`); a `token` over 255 characters raises `DataError` (pgcode `22001`). `get` (unscoped) is what `WorkspaceManager.accept_invitation` and `cancel_invitation` use.

---

## `WorkspaceInvitationDAO.get_by_token(db, *, token)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceManager.validate_invitation_for_user`, `AuthService.validate_invitation_token`; reached by accepting an invitation, registering with one, and `POST /auth/validate-invitation/`)

**Purpose:** The invitation behind a link.

**Returns:** the `WorkspaceInvitation`, or `None`.

**Rules:**
- **R1.** Given a row with exactly that token, it is returned whatever its status and expiry (accepted, cancelled and expired rows included: the callers turn those into their own messages).
- **R2.** The match is exact: the same token in other case, or an unknown token, gives `None`. Tokens are unique, so at most one row matches. Not scoped to a workspace: the token is the credential.

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceInvitationDAO.get_pending_invitations(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.list_invitations` ← `GET /workspaces/{id}/invitations/` without `include_expired`)

**Purpose:** The invitations of a workspace still waiting for an answer.

**Returns:** a `list` of `WorkspaceInvitation` (possibly empty).

**Rules:**
- **R1.** Returns the rows of that workspace whose `status` is exactly `'pending'` (`'Pending'` is left out) and whose `expires_at` is later than `utcnow()`.
- **R2.** An invitation whose `expires_at` equals `utcnow()` exactly, or is earlier, is left out; one microsecond later is kept. A pending row that has expired keeps `status = 'pending'` in the table and is simply not listed.
- **R3.** Rows of another workspace never appear. An unknown workspace or `0` gives `[]`. No paging, no cap.
- **R4.** [BUG-1401] (HR-6) Ordered by `invited_at` descending, then `id` descending. *(Today: no `ORDER BY`.)*

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceInvitationDAO.get_user_invitations(db, *, email)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.get_my_invitations` ← `GET /workspaces/me/invitations/`, with the current user's stored email)

**Purpose:** The invitations waiting for one person, from every workspace.

**Returns:** a `list` of `WorkspaceInvitation` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that email that are pending and not expired, as `get_pending_invitations` R1, R2, from **every** workspace.
- **R2.** [BUG-1402] (Q1) The email is matched ignoring case and surrounding spaces on both sides: asked `John.Doe@example.com` or ` john.doe@example.com `, a row stored `john.doe@example.com` (or `John.Doe@Example.com`) is returned. *(Today: exact match; `b@x.com` does not find `B@x.com`, ` a@x.com` does not find `a@x.com`.)*
- **R2a.** What holds today and after the fix: another email (`a@y.com` for `a@x.com`) is never matched; an unknown email gives `[]`.
- **R3.** No paging, no cap.
- **R4.** [BUG-1401] Ordered as `get_pending_invitations` R4. *(Today: no `ORDER BY`.)*

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceInvitationDAO.count_pending_invitations(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceManager.create_invitation`, added to the active members and compared with the plan's `max_members`)

**Purpose:** How many seats open invitations hold.

**Returns:** `int`.

**Rules:**
- **R1.** Counts exactly the rows `get_pending_invitations` returns (R1–R3 there), one per row: two pending invitations to the same email count 2.
- **R2.** An unknown workspace, `0`, or none pending gives `0`.

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceInvitationDAO.get_all_invitations(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.list_invitations` with `include_expired=True`)

**Purpose:** Every invitation of a workspace, whatever its state.

**Returns:** a `list` of `WorkspaceInvitation` (possibly empty).

**Rules:**
- **R1.** Returns every row of that workspace: pending, expired, accepted, cancelled, any other status. Rows of another workspace never appear; an unknown workspace or `0` gives `[]`.
- **R2.** No paging, no cap. Does not read the clock.
- **R3.** [BUG-1401] Ordered as `get_pending_invitations` R4. *(Today: no `ORDER BY`.)*

**Errors:** none of its own.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14–16 | exact token; `.first()` row / `None` | `get_by_token` R1, R2 |
| 22–30 | workspace AND `status == 'pending'` AND `expires_at > utcnow()`; no `ORDER BY` (BUG-1401) | `get_pending_invitations` R1, R2, R3, R4 |
| 34–42 | exact email (BUG-1402) AND pending AND not expired; no `ORDER BY` | `get_user_invitations` R1, R2, R2a, R3, R4 |
| 46–54 | same filter as pending; count | `count_pending_invitations` R1, R2 |
| 60–64 | workspace only; no `ORDER BY` | `get_all_invitations` R1, R2, R3 |
| 66 | module singleton | Not specified |
