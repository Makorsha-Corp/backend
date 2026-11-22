# Spec — `app/managers/workspace_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open). Q1 (OQ-16) and Q2 (OQ-17) were answered by the owner: both are deferred to the payment portal, with today's behaviour kept in their own rules (Q2 logged as BUG-1989). Q9 was answered by the owner: BUG-1990. Q3–Q8 and Q10–Q12 were decided by Claude under the reviewer's delegation (2026-11-04).
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `workspace_manager.cases.md` gaps 1–10).** Facts added from the code and from the column types of `marker_test`, read in a rolled-back transaction. Gap 7 (the order of the audit rows on accept, and IP / user agent on the superseded rows) was an intent question about BUG-1874's new rows; it was decided by Claude under the reviewer's delegation (2026-11-04). No new bug, no money question. Stays APPROVED. See the Gap log.

> **Apply-review 2026-11-04.** Owner answers (relayed by the coordinator, recorded in `docs/testing/owner-questions.md`): Q1 / OQ-16, leave it for the portal, no bug (BUG-1988 unused). Q2 / OQ-17, bug, deferred to the plans/subscriptions design: BUG-1989, with the rule kept at today's behaviour. Q9, "Owner + managers now": BUG-1990.

> **Review round 2026-11-04 (describer).** **Owner answers already given, applied without asking:** OQ-1 (BUG-1860), OQ-2 (BUG-1871, BUG-1872), OQ-3 (BUG-1873, BUG-1874), OQ-6 (BUG-1883), the approver-removal answer (BUG-1201), and the project member decision (BUG-1280). The audit log's BUG-1404 lands here as well. **Delegated:** Q3–Q12, decided by Claude under the reviewer's delegation (2026-11-04). None of them is the owner's own answer. **Routed, not decided here:** the role lists go to the permissions feature (who may remove members was then decided by the owner, Q9) (`docs/future/permissions.md`). Member notices go to `docs/future/notifications.md`. Plan, price and limit matters that the payment portal will settle go to `docs/future/subscription-payments.md`, "Added during the sweep".
>
> **Below:** `tests/unit/dao/workspace.spec.md` (`get_by_slug`), `workspace_member.spec.md` (`get_by_workspace_and_user`, `count_active_members`, inherited `create`), `workspace_invitation.spec.md` (`get_by_token`, `count_pending_invitations`, inherited `get` / `create`), `subscription_plan.spec.md` (`get_default_plan`, inherited `get`), `workspace_audit_log.spec.md` (`log_action`), `profile.spec.md` (`get_by_email`, inherited `get`), `base.spec.md`. The seed functions in `app/db/seed_*.py` have no spec; their outcome for a new workspace is stated here. **Above:** `WorkspaceService` (`create_workspace`, `remove_member`, `send_invitation`, `accept_invitation`, `cancel_invitation`) and `AuthService` (`_register_with_new_workspace`, `_register_with_invitation`). A `ValueError` from this manager becomes 400 (`ValidationError`) in create, invite and accept, and 403 (`PermissionDeniedError`) in remove and cancel.
>
> **Read, not run.** Every rule follows from the code and the approved DAO specs. Facts about the web app come from `../frontend/src` (read): it never sends `subscription_plan_id` when creating a workspace (`pages/newpages/WorkspaceSelectorPage.tsx:228-232`). It offers the roles `manager, member, viewer, ground-team` (`pages/newpages/ManagementPage.tsx:46`). It shows the invitation token for the owner to pass on by hand (`ManagementPage.tsx:472`).

## Review
> All answered; nothing pending.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | A workspace name of only spaces is accepted, and names are not trimmed | bug — HR-1 (BUG-1980) | house rule |
| H2 | Cancelling another workspace's invitation says "does not belong to this workspace" instead of "not found" | bug — HR-16 (BUG-1981) | house rule |
| Q1 | **OWNER** — When creating a workspace you can pick any active plan, Enterprise included, without paying | leave it for the payment portal; today's behaviour kept in its own rule, no bug | owner (OQ-16) |
| Q2 | **OWNER** — A plan with `max_members = 0` has no member limit at all | bug, deferred to the plans/subscriptions design; rule kept at today's behaviour (BUG-1989) | owner (OQ-17) |
| Q3 | A removed member can be invited again but can never accept | bug — accepting brings the old membership back (BUG-1982) | Claude, delegated |
| Q4 | A suspended member can be invited, and that invitation can never be accepted | bug — refused like an active member (BUG-1983) | Claude, delegated |
| Q5 | Removing someone already removed "succeeds" again | bug — refused as not a member (BUG-1984) | Claude, delegated |
| Q6 | A new member's row never records who invited them | bug — `invited_by_user_id` is set (BUG-1985) | Claude, delegated |
| Q7 | A non-owner who tries to cancel an invitation learns its state before being refused | bug — role first (BUG-1986) | Claude, delegated |
| Q8 | An invitation can be accepted at the exact instant it stops being listed | bug — expired at `expires_at <= now` (BUG-1987) | Claude, delegated |
| Q9 | **OWNER** — Any member who is not `ground-team` or `ground-team-manager` can remove any non-owner member | bug — the owner removes any non-owner; `ground-team-manager` and `manager` remove `ground-team` only; others 403 (BUG-1990) | owner |
| Q10 | Invitations cannot give the roles `ground-team-manager` or `finance` | intended for now — routed to the permissions feature | Claude, delegated (routing) |
| Q11 | The docstring says the manager or the original inviter may cancel, but only the owner can | intended — owner only | Claude, delegated |
| Q12 | The docstring says invitations last 7 days; they last 3 | intended — 3 days | Claude, delegated |

**Already decided elsewhere and applied here (no question):** BUG-1860 (OQ-1, emails ignore capitals), BUG-1871 / BUG-1872 (OQ-2, a negative limit means unlimited), BUG-1873 / BUG-1874 (OQ-3, one pending invitation per email), BUG-1201 (removed member's pending approvals), BUG-1280 (removed member's project memberships), BUG-1883 (OQ-6, removed member's work order assignments), BUG-1404 (audit rows carry IP and user agent).

Checked and **not** a line here: **HR-2**: the slug is unique in the database and the schema allows lowercase only (workspace DAO spec). Workspace names need not be unique. **HR-3, HR-5 … HR-8**: no grouping, list, paging or `LIKE`. **HR-4**: workspaces, members, invitations, plans and audit rows have no soft-delete column. Work orders do, and BUG-1883's rule says how they count. **HR-9**: no `updated_by` here. **HR-10**: accepting an invitation twice at once ends in the unique `(workspace_id, user_id)` constraint, not a duplicate. Cancel racing accept can leave an accepted member with a `cancelled` invitation, which is harmless. The seat check is read-then-insert with no lock. Plan limits are not covered by HR-10 (workspace member DAO FU-2 (b)), and this is recorded for the payment portal, not asked here. **HR-11 … HR-14**: no external system or batch. **HR-15**: no money is computed. **HR-16**: every member lookup takes the workspace and the user together. `create_invitation` and `add_member_to_workspace` take the workspace from the caller. The accept path checks the invitation's workspace in `WorkspaceService.accept_invitation`. Only cancel acts on a row found by id alone (H2).

### House-rule violations — applied automatically

- **HR-1** `create_workspace_with_owner` R12 — `WorkspaceCreate.name` is `min_length=1` with no trim: `"   "` is stored, and `" Acme "` keeps its spaces. Intended: the name is stored trimmed. A blank or whitespace-only name is refused by the schema (422). The fix belongs in `app/schemas/workspace.py` (`WorkspaceCreate`, and `WorkspaceUpdate.name` for the same field).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1980 (pattern `blank-name-accepted`). Rules: `create_workspace_with_owner` R12.

- **HR-16** `cancel_invitation` R2 — an invitation id from another workspace is refused with "Invitation does not belong to this workspace", while an unknown id gets "Invitation not found". Any member can tell which invitation ids exist elsewhere. Intended: the same "Invitation not found" for both, nothing changed.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1981 (pattern `existence-disclosure-403-vs-404`: both are 403 at the service, but the text tells them apart). Rules: `cancel_invitation` R2.

### New questions

### Q1. OWNER — A new workspace can start on any active plan, Enterprise included, without paying — ⏸ pending the payment portal (OQ-16)
**Background:** Plans are seeded: `free` (the default, 3 members, no price), `pro` (99 USD a month, 10 members) and `enterprise` (299 USD a month, `-1` everywhere, meaning unlimited). `POST /workspaces/` accepts an optional `subscription_plan_id`. No payment changes a workspace's plan today: the payment portal is still to be built (`docs/future/subscription-payments.md`). The web app never sends `subscription_plan_id`; registration always passes none.
**What happens today:** If `subscription_plan_id` is given (and is not `0`), the workspace gets that plan when it exists and is active, and nothing is charged. `0` or no id gives the default plan.
**Example:** A user calls `POST /workspaces/` with `{"name": "Acme", "slug": "acme", "subscription_plan_id": 3}` (Enterprise). The workspace is created on Enterprise, with unlimited members, a 14-day `trial` status and no payment.
**Rules affected:** `create_workspace_with_owner` R1, R2, R3
**Suggested answer:** `bug — a new workspace always starts on the default plan. A subscription_plan_id that is not the default plan's id is refused with "A new workspace starts on the default plan. Choose a paid plan from billing after it is created." (400), and nothing is written. No id, or the default plan's own id, works as today. Other plans are reached only through a verified payment (the portal).` The web app is not affected because it never sends the field.
**Alternatives:** (a) silently ignore the field and always use the default plan. (b) Accept only plans with no price (`price_monthly` and `price_yearly` both null). (c) Intended until the portal exists.
**Answer:** owner, 2026-11-04 (OQ-16): leave it for the payment portal work. Tests describe today's behaviour (any active plan is accepted), kept in its own rule so that the portal decision changes only those cards.
**Resolution:** no bug (BUG-1988 stays unused). Rule `create_workspace_with_owner` R1 states today's behaviour and is marked *pending the payment portal (OQ-16)*. R2 and R3 stand whatever the portal decides. Noted in `docs/future/subscription-payments.md`.

### Q2. OWNER — A plan with `max_members = 0` has no member limit — 🐞 BUG-1989 (deferred to the plans/subscriptions design)
**Background:** Every plan has `max_members` (NOT NULL, default 5). The owner said a negative value means "no limit" (OQ-2, BUG-1871 / BUG-1872), and left `0` (and `None`) to this spec. `None` cannot happen: the column is NOT NULL, and a workspace's plan always exists, because the foreign key is NOT NULL and has no delete action. The member count includes the owner. No seeded plan uses `0`, and no API writes plans.
**What happens today:** Both seat checks start with `if plan.max_members:`. `0` is false, so the check is skipped and members can be added and invited without limit.
**Example:** Someone sets up a "Solo" plan with `max_members = 0`, meaning "just the owner". A Solo workspace invites 40 people and all 40 join.
**Rules affected:** `add_member_to_workspace` R6; `create_invitation` R9
**Suggested answer:** `bug — 0 is a limit like any other, so nobody can be added or invited; the owner alone holds the workspace. Only a negative value means unlimited (OQ-2).` This follows the precedent that a zero value is not "missing" (pattern `falsy-zero-treated-as-missing`, e.g. BUG-501, BUG-707).
**Alternatives:** (a) `0` also means unlimited, as today; document it next to `-1`. (b) `0` is not a valid plan value; a check constraint refuses it on `subscription_plans`.
**Answer:** owner, 2026-11-04 (OQ-17): "This seems like a bug; we need to go over what the plans will be in future. Put that work with the payment portal; we need to figure out how to combine plans and subscriptions later."
**Resolution:** 🐞 BUG-1989 (pattern `falsy-zero-treated-as-missing`), deferred: what `0` means is settled with the plans/subscriptions design. The rules stay at today's behaviour, each in its own rule marked *pending the plans/subscriptions design (BUG-1989)*. They are ordinary passing tests now, and only their cards change later. Rules: `add_member_to_workspace` R6, `create_invitation` R9.

### Q3. A removed member can be invited again but can never accept — 🐞 BUG-1982
**Background:** Removing a member does not delete their row. It sets `status = 'inactive'` and `left_at`. A user has at most one row per workspace (unique pair). When the user has a row, the invitation check refuses only an `active` one. Accepting adds the member through `add_member_to_workspace`, which refuses **any** existing row, whatever its status.
**What happens today:** The owner can invite a removed member back, and the invitation is created and holds a seat. Accepting it always fails with "User is already a member of this workspace" (400), until the invitation expires.
**Example:** Rahim leaves the company and is removed. A month later he comes back. The owner invites `rahim@acme.com`, and Rahim opens the link and gets "User is already a member of this workspace". Nobody can ever bring him back.
**Rules affected:** `add_member_to_workspace` R2, R2a
**Answer:** bug — an `inactive` row is reactivated by the add / accept, subject to the seat check, with the invitation's role and position (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** 🐞 BUG-1982 (pattern `soft-deleted-conflict-not-restored`, as BUG-714 / BUG-1336: an old row blocks the new one instead of being restored). Rules: `add_member_to_workspace` R2a. BUG-1280 already takes such a person off their projects at removal, so a returning member gets no old project access back.

### Q4. A suspended member can be invited, and that invitation can never be accepted — 🐞 BUG-1983
**Background:** The membership `status` is free text. Only `active` gives access. The model comment names `suspended` and `invited` as well, but no code sets them (they can come only from the database). The invitation check refuses only an `active` row.
**What happens today:** An invitation to someone whose row is `suspended` (or any status other than `active` and `inactive`) is created and holds a seat. Accepting it fails with "already a member".
**Example:** Karim's row was set to `suspended` by hand. The owner invites him and the invitation sits there until it expires, taking one of the plan's 3 seats.
**Rules affected:** `create_invitation` R3, R3a
**Answer:** bug — the invitation is refused for any existing row except `inactive`, with the same message as an active member (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** 🐞 BUG-1983 (pattern `inconsistent-sibling-guard`: the invite check and the add check disagree). Rules: `create_invitation` R3a.

### Q5. Removing someone already removed "succeeds" again — 🐞 BUG-1984
**Background:** Removal finds the membership row whatever its status.
**What happens today:** Removing a member whose row is already `inactive` succeeds. `left_at` moves to now, and a second `member_removed` audit row is written. The real leaving date is lost.
**Example:** Rahim was removed on 1 October. On 4 November someone clicks "Remove" on a stale screen. His `left_at` now says 4 November, and the log shows two removals.
**Rules affected:** `remove_member_from_workspace` R1, R1a
**Answer:** bug — only a row that is not `inactive` can be removed; an `inactive` row is refused with "User is not a member of this workspace", and nothing changes (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** 🐞 BUG-1984 (pattern `missing-state-guard`). Rules: `remove_member_from_workspace` R1a.

### Q6. A new member's row never records who invited them — 🐞 BUG-1985
**Background:** `workspace_members.invited_by_user_id` exists (FK to profiles, SET NULL), and `WorkspaceMemberCreate` carries it. `add_member_to_workspace` receives `inviter_id` and uses it only for the audit row.
**What happens today:** Every member row has `invited_by_user_id` NULL.
**Example:** The members page cannot say "invited by Karim", although the invitation named him.
**Rules affected:** `add_member_to_workspace` R8
**Answer:** bug — `invited_by_user_id` is set to `inviter_id` (`None` stays `None`); the owner's own row at creation stays NULL (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** 🐞 BUG-1985 (pattern `actor-not-recorded`). Rules: `add_member_to_workspace` R8.

### Q7. A non-owner who tries to cancel an invitation learns its state first — 🐞 BUG-1986
**Background:** Any active member can call cancel; the service passes their role in. The manager checks that the invitation exists, its workspace and its status **before** the owner-only check.
**What happens today:** A `ground-team` member who tries ids one by one is told "Invitation not found", "Cannot cancel invitation that is accepted" or "Only the workspace owner can cancel invitations". That shows which invitations exist and what happened to them.
**Example:** A member calls `DELETE …/invitations/57` and reads "Cannot cancel invitation that is accepted". Now they know invitation 57 was accepted.
**Rules affected:** `cancel_invitation` R1, R4
**Answer:** bug — the owner-only check comes first; a non-owner always gets "Only the workspace owner can cancel invitations", whatever the id (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** 🐞 BUG-1986 (pattern `existence-disclosure-403-vs-404`). Rules: `cancel_invitation` R1.

### Q8. An invitation can be accepted at the exact instant it stops being listed — 🐞 BUG-1987
**Background:** The invitation lists and the seat count treat an invitation as expired when `expires_at <= now` (workspace invitation DAO spec R2, FU-2). The accept check refuses only when `expires_at < now`.
**What happens today:** At exactly `expires_at` the invitation is gone from the lists and no longer holds a seat, yet it can still be accepted. The window is one microsecond.
**Example:** An invitation expires at 10:00:00.000000. A request whose clock reads exactly that instant does not see it on the invitations page, and the seat it held is free, yet accepting it succeeds. In practice it shows up only in a test with a frozen clock, but it means two parts of the same feature use different boundaries.
**Rules affected:** `validate_invitation_for_user` R2
**Answer:** bug — expired means `expires_at <= now` everywhere (decided by Claude under the reviewer's delegation (2026-11-04)). Low.
**Resolution:** 🐞 BUG-1987 (pattern `inconsistent-sibling-guard`). Rules: `validate_invitation_for_user` R2.

### Q9. OWNER — Any member who is not ground-team can remove any non-owner member — 🐞 BUG-1990 (owner)
**Background:** `DELETE /workspaces/{id}/members/{user_id}` needs only an active membership. The manager refuses `ground-team` callers, and limits `ground-team-manager` callers to `ground-team` targets. Every other role passes: `manager`, `member`, `viewer` (the roles the web app assigns) and `finance`. The docstring says "Owner can remove anyone; Managers can remove ground-team only".
**What happens today:** A `viewer` can remove the `manager`. A `member` can remove every other member, and can also remove themselves.
**Example:** A new `viewer` removes all four managers of the workspace. Only the owner is safe.
**Rules affected:** `remove_member_from_workspace` R4, R5
**Answer:** owner, 2026-11-04: "Owner + managers now". The owner may remove any non-owner member. A `ground-team-manager` may remove `ground-team` members only. Everyone else is refused (403) and nothing changes. This is fixed now, not deferred to the permissions task. Follow-up, owner, 2026-11-04: "roles will change, put a note down in the permission and flag this for later, for now keep both kinds": `manager` is treated like `ground-team-manager` (may remove `ground-team` members only). Flagged for later in `docs/future/permissions.md`.
**Resolution:** 🐞 BUG-1990 (pattern `missing-role-check-on-write`). Rules: `remove_member_from_workspace` R4b and R5 (tagged); R4a and R5a (untagged: what already holds today). R3 and R4 are unchanged. A non-owner can no longer remove themselves, and no "leave workspace" action exists.

### Q10. Invitations cannot give the roles `ground-team-manager` or `finance` — ✅ intended for now (permissions feature)
**Background:** There are two role lists. `RoleEnum` and the member model's comment have `owner, finance, ground-team, ground-team-manager`. Help tickets, projects and member removal check for `ground-team-manager`. The lists this module checks are `owner, manager, member, viewer, ground-team` (adding) and `manager, member, viewer, ground-team` (inviting), and the web app offers the second list.
**What happens today:** An invitation with role `ground-team-manager` or `finance` is refused with "Invalid role. Must be one of: ground-team, manager, member, viewer". No one can be made a `ground-team-manager` through the API, so the privileges written for that role reach nobody.
**Example:** The owner wants a floor supervisor who can see all help tickets. No role they can assign does that.
**Rules affected:** `add_member_to_workspace` R1; `create_invitation` R1
**Answer:** intended for now — the role list is decided with the permissions feature (decided by Claude under the reviewer's delegation (2026-11-04), as routed). Recorded in `docs/future/permissions.md`.
**Resolution:** the rules describe today's lists, marked *(permissions feature)*.

### Q11. The docstring says the manager or the original inviter may cancel; only the owner can — ✅ intended
**Background:** Sending and listing invitations are owner-only (`WorkspaceService._require_owner`), so the original inviter is always someone who was the owner.
**What happens today:** Only `canceller_role == 'owner'` may cancel.
**Example:** A `manager` cannot cancel an invitation, although they cannot see or send invitations either.
**Rules affected:** `cancel_invitation` R1
**Answer:** intended — owner only, matching send and list; the docstring is stale (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** no bug. Recorded for the permissions feature.

### Q12. The docstring says invitations last 7 days; they last 3 — ✅ intended
**Background:** `validate_invitation_for_user` says "Not expired (7-day window)", but `create_invitation` sets `expires_at = now + 3 days`. The owner's OQ-3 answer and BUG-1874 were written knowing it is 3 days.
**What happens today:** Invitations expire 3 days after they are sent.
**Example:** An invitation sent Monday 10:00 can be accepted until Thursday 10:00, but not afterwards.
**Rules affected:** `create_invitation` R12
**Answer:** intended — 3 days; the docstring is stale (decided by Claude under the reviewer's delegation (2026-11-04)).
**Resolution:** no bug.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Workspace service** (`remove_member`, `cancel_invitation`) | Every `ValueError` from remove and cancel becomes 403, including "User is not a member of this workspace" and "Invitation not found", which are not-found cases. Whether they should be 404 is that review's call. HR-16's "not found" here means the same text as an unknown id (BUG-1981). | `remove_member_from_workspace`, `cancel_invitation` |
| FU-2 | **Workspace service / endpoints** | BUG-1404: the endpoints must pass the request's client IP and user agent through the service into every method here (new optional parameters `ip_address`, `user_agent`). | Audit rows |
| FU-3 | **Auth service** (`_register_with_invitation`) | It validates, creates the profile, then accepts, but never checks that the invitation's workspace matches anything (the token decides the workspace, which is fine). With BUG-1982, a registering user has no old row, so nothing changes there. | `accept_invitation` |
| FU-4 | **Payment portal** (`docs/future/subscription-payments.md`) | The plan change after a verified payment probably lives next to `create_workspace_with_owner` *(guess)*. The seat check has no lock. Only `max_members` is enforced. `trial` / `trial_ends_at` are set on every plan and read by nothing. `billing_email` is stored unchecked. | Q1, Q2 |

## Overview
`WorkspaceManager` looks after the workspace as a whole: it creates a workspace with its owner and default data, adds and removes members, and sends, checks, accepts and cancels invitations. It also writes a `workspace_audit_logs` row for each of these. It enforces the plan's member limit (`max_members`, the only plan limit enforced anywhere). It keeps the owner from being removed, and it makes sure an invitation is accepted only by the email it was sent to. It flushes and never commits. Callers: `WorkspaceService` and `AuthService` (registration). `add_member_to_workspace` has no caller outside this class: it is reached only through `accept_invitation`.

**Callables:** 7 specified, plus one shared "Audit rows" section · 2 not specified
**Externals to mock:** `utcnow`. Patch `app.managers.workspace_manager.utcnow`, and also `app.dao.workspace_invitation.utcnow` wherever the pending count or the BUG-1873 check is involved, to the same naive UTC value. `secrets.token_urlsafe` (patch `app.managers.workspace_manager.secrets.token_urlsafe`) only where a fixed token is needed. No notification, email or external system is called.
**Integration-only behavior:** none. The 400 / 403 mapping is the service's.

**Model facts used here** (details in the DAO specs):
- `workspaces`: `slug` unique. `subscription_plan_id` NOT NULL, FK with no delete action. `subscription_status` defaults to `'trial'`, `current_members_count` to `1`, other counters to `0`, `settings` to `{}`. `subscription_started_at`, `subscription_ends_at` and `billing_cycle` are left NULL here. `owner_user_id` and `created_by_user_id` are FKs to profiles (SET NULL).
- `workspace_members`: unique `(workspace_id, user_id)`. `status` is free text: `active` is a member, removal writes `inactive`. `invited_at` defaults to now. `joined_at`, `left_at` and `invited_by_user_id` are nullable.
- `workspace_invitations`: `token` unique. `email` is stored lower-cased by this manager. `status` is `pending`, `accepted` or `cancelled`; nothing ever writes `expired`. `expires_at` is NOT NULL.
- `subscription_plans`: `max_members` is NOT NULL (default 5). Seeded `free` has 3, `pro` 10, `enterprise` -1.

**Notes for the test designer:**
- `from app.managers.workspace_manager import workspace_manager`. Use `tests/unit/factories.py` for profiles, plans (`make_subscription_plan`) and workspaces (`make_workspace`). For `create_workspace_with_owner`, make exactly one active default plan in the test: the table has no committed rows in `marker_test`.
- Pass `WorkspaceCreate(name=…, slug=…)` objects. Slugs must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- Errors are plain `ValueError`. Compare the message exactly.
- **Datetime columns (gap 9):** every datetime this module writes or compares is `timestamp without time zone` in the database, holding naive UTC: `workspaces.trial_ends_at`, `last_usage_reset_at`, `created_at`, `updated_at`; `workspace_members.invited_at`, `joined_at`, `left_at`; `workspace_invitations.invited_at`, `expires_at`, `accepted_at`; and every order / project event `created_at`. Compare them with the naive patched `utcnow`. The only aware column is `workspace_audit_logs.created_at` (`timestamptz`, BUG-1403); see the audit log DAO spec for how to read it.
- **Race on the slug (gap 8):** the manager reaches the lookup as `self.workspace_dao.get_by_slug`, where `self.workspace_dao` is the module singleton `app.dao.workspace.workspace_dao`. Patch it with `monkeypatch.setattr(workspace_manager, "workspace_dao", fake)` (instance attribute of the `workspace_manager` singleton), or `monkeypatch.setattr(workspace_manager.workspace_dao, "get_by_slug", lambda *a, **k: None)`. Then insert a workspace with the same slug and flush: the manager's insert raises `IntegrityError` at its flush.
- **Event tables (gap 3):** `expense_order_events`, `purchase_order_events`, `sales_order_events`, `transfer_order_events`, `work_order_events` and `project_events` share one shape: `id`, `workspace_id`, the order's id (`expense_order_id`, `purchase_order_id`, `sales_order_id`, `transfer_order_id`, `work_order_id`, `project_id`), `event_type`, `description`, `metadata` (model attribute `metadata_json`), `performed_by`, `created_at`.
- Tagged rules that need new parameters (BUG-1404) or new reads (BUG-1201, BUG-1280, BUG-1883): see each rule's note. Write them against the intended signature and mark them strict xfail.
- For the BUG-1201 rule, one test per order type is enough. Build each order "open" and "closed" by the definition given in the rule.

## Not specified
- `WorkspaceManager.__init__`: wires the DAOs, no logic.
- `workspace_manager`: module-level singleton.

---

## Audit rows (shared by every method below)
**Rules:**
- **A1.** Each successful call writes exactly the audit rows its section names, through `log_action` (workspace audit log DAO spec). `resource_type` and `resource_id` stay NULL. The row's `created_at` follows that spec (BUG-1403).
- **A2.** [BUG-1404] Each public method takes two new optional keyword parameters, `ip_address` and `user_agent` (default `None`), and every audit row it writes carries them unchanged. Cutting the IP to 45 characters is the DAO's job (BUG-1405). *(Today: no such parameters; every row has both NULL.)* *(Requires new parameters.)*
- **A3.** A call that raises writes no audit row and nothing else. Every check runs before the first write, except where a section says otherwise.

---

## `WorkspaceManager.create_workspace_with_owner(session, workspace_data, owner_user_id, subscription_plan_id=None, owner_position=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceService.create_workspace` ← `POST /workspaces/`, passing `workspace_data.subscription_plan_id` and `workspace_data.owner_position`; `AuthService._register_with_new_workspace` ← registration without an invitation, passing no plan and no position, with `billing_email` = the new account's email)

**Purpose:** Create a workspace on a plan, make the caller its owner and first member, and seed its default data.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_data` | `WorkspaceCreate` | `name` 1–255 characters (BUG-1980). `slug` 1–100 characters, lowercase letters, digits and single hyphens. `billing_email` is any string or `None`, not checked as an email. `subscription_plan_id` and `owner_position` are **ignored here**: the separate parameters are used. |
| `owner_user_id` | int | the creator, not checked here. A missing profile fails later, at the member insert (FK). |
| `subscription_plan_id` | `int \| None` | see R1–R3 (R1 pending the payment portal, OQ-16) |
| `owner_position` | `str \| None` | stored on the owner's member row as given |

**Returns:** the new `Workspace`, flushed (has its `id`), not committed.

**Rules:**
- **R1.** *(pending the payment portal (OQ-16): today's behaviour, kept in its own rule)* When `subscription_plan_id` is given and truthy, the plan with that id is used if it exists and `is_active` is true.
- **R2.** When that plan does not exist, or is inactive, `ValueError("Invalid subscription plan")` is raised and nothing is written.
- **R3.** When `subscription_plan_id` is `None` or `0`, the default plan is used (`get_default_plan`: the active default). With no active default plan, `ValueError("No default subscription plan found")` is raised and nothing is written.
- **R4.** The plan is checked before the slug, so a bad plan id with a taken slug gives the plan error.
- **R5.** When a workspace with exactly this slug exists (in any workspace, any owner; exact match per the workspace DAO spec), `ValueError("Workspace slug '<slug>' is already taken. Please choose a different name.")` is raised, with the slug as given, and nothing is written. If two creations race past this check, the unique index refuses the second (`IntegrityError`, not a `ValueError`).
- **R6.** The workspace row gets: `name`, `slug` and `billing_email` from `workspace_data`; `subscription_plan_id` = the chosen plan's id; `owner_user_id` = `created_by_user_id` = `owner_user_id`; `trial_ends_at` = `utcnow()` + exactly 14 days; and the model defaults for the rest: `subscription_status = 'trial'`, `current_members_count = 1`, `current_storage_mb = 0`, `current_orders_this_month = 0`, `current_factories_count = 0`, `current_machines_count = 0`, `current_projects_count = 0`, `last_usage_reset_at` = now (model default `utcnow`, read from `app.models.workspace`, so not the patched clock), and `subscription_started_at`, `subscription_ends_at`, `billing_cycle`, `stripe_customer_id`, `stripe_subscription_id` all NULL. The 14-day trial is set whatever the plan, `free` included.
- **R7.** When the owner's profile has a non-empty `timezone`, `settings` is `{"timezone": <that value>}` (copied as stored, not validated). When the profile's `timezone` is `None` or `""`, `settings` is `{}`; test both. (When the profile does not exist, the workspace row would also get `{}`, but creation then fails at the member insert, R11, so only the failure can be observed; gap 5.)
- **R8.** One member row is created: this workspace, `user_id = owner_user_id`, `role = 'owner'`, `status = 'active'`, `position = owner_position`, `joined_at` = `utcnow()`, `invited_by_user_id` NULL, `left_at` NULL. No seat check is made for the owner.
- **R9.** The workspace gets its default data, all belonging to this workspace:
  - 13 statuses: `Pending`, `Office Approved`, `Budget Approved`, `Quotation Requested`, `Quotation Received`, `Purchased`, `Received`, `Completed`, `Cancelled`, `Draft`, `Planning`, `Receiving`, `Complete`;
  - one order workflow (`order_workflows`): `name` `Purchase Order`, `type` `purchase`, description `Draft → Planning → Receiving → Complete`, `status_sequence` = the ids of `Draft`, `Planning`, `Receiving`, `Complete` in that order, `allowed_reverts_json` NULL;
  - 5 departments: `Production`, `Maintenance`, `Quality Control`, `Warehouse`, `Administration`;
  - 6 item tags (`item_tags.tag_code` `raw_material`, `machine_part`, `project_item`, `consumable`, `tool`, `finished_good`) and 5 account tags (`account_tags.tag_code` `supplier`, `vendor`, `client`, `utility`, `payroll`). Every tag has `is_system_tag` true, `is_active` true, `usage_count` 0 and `created_by` = `owner_user_id`.
  Data of other workspaces is not touched, and another workspace's rows with the same names do not stop these being created.
- **R10.** One audit row: `workspace_id` = the new workspace, `user_id` = `owner_user_id`, `action = 'workspace_created'`, `metadata = {"plan": <plan name>}` (A1, A2).
- **R11.** If `owner_user_id` names no profile, the member insert fails with `IntegrityError` (FK) at its flush. The workspace row was already flushed, and the caller's rollback removes it.
- **R12.** [BUG-1980] (HR-1) The name is stored with leading and trailing whitespace removed (`" Acme "` → `Acme`). A blank or whitespace-only name never reaches this method: `WorkspaceCreate` refuses it (Pydantic `ValidationError`, 422 at the API). Inner spaces and case are kept. *(Today: `"   "` passes the schema and is stored, and `" Acme "` keeps its spaces.)* *(Fix in `app/schemas/workspace.py`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| plan id given, unknown or inactive | `ValueError` | `Invalid subscription plan` |
| no id and no active default plan | `ValueError` | `No default subscription plan found` |
| slug taken | `ValueError` | `Workspace slug '<slug>' is already taken. Please choose a different name.` |
| owner profile missing | `IntegrityError` | — |

**Side effects:** 1 workspace, 1 member, 13 statuses, 1 order workflow, 5 departments, 11 tags and 1 audit row are inserted and flushed, not committed.

---

## `WorkspaceManager.add_member_to_workspace(session, workspace_id, user_id, role, inviter_id, position=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `accept_invitation`; no other caller in `app/`)

**Purpose:** Make a user an active member of a workspace, within the plan's member limit.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `role` | str | exact, case-sensitive, from the list in R1 |
| `inviter_id` | `int \| None` | recorded as the actor (R7, R8). Not checked. |
| `position` | `str \| None` | stored as given |

**Returns:** the new (or, per BUG-1982, reactivated) `WorkspaceMember`, flushed, not committed.

**Rules:**
- **R1.** *(permissions feature, Q10)* `role` must be one of `owner`, `manager`, `member`, `viewer`, `ground-team`. Anything else (`ground-team-manager`, `finance`, `Owner`, `""`) raises `ValueError("Invalid role. Must be one of: ground-team, manager, member, owner, viewer")` before anything is read. `owner` is accepted here, but no API path reaches it with `owner` (invitations cannot carry it).
- **R2.** When the user has an `active` membership row in this workspace (or any status other than `inactive`), `ValueError("User is already a member of this workspace")` is raised and nothing is written. A row of the same user in another workspace does not count.
- **R2a.** [BUG-1982] (Q3) When the user's row in this workspace is `inactive`, the row is reactivated instead of refused, after the checks of R3–R6: `status = 'active'`, `role` and `position` = the given values, `joined_at` = `utcnow()`, `left_at` = NULL, `invited_by_user_id` per R8. No second row is created; the row keeps its `id` and `created_at`. *(Today: refused with "User is already a member of this workspace".)*
- **R3.** When the workspace does not exist, `ValueError("Workspace not found")` is raised. This is checked after R1 and R2.
- **R4.** The seat check reads the workspace's plan. A plan always exists (FK NOT NULL, no delete action). An inactive plan is still enforced.
- **R5.** When the plan's `max_members` is positive and the workspace's active members (the owner included; workspace member DAO `count_active_members`) are **at least** `max_members`, `ValueError("Workspace has reached maximum member limit (<max_members>). Upgrade subscription to add more members.")` is raised and nothing is written. At `max_members - 1` active members the add succeeds. Pending invitations are not counted here. A reactivated `inactive` row (R2a) is not active before the add, so it is not counted.
- **R5a.** [BUG-1872] (OQ-2) When `max_members` is negative (`-1`, or any other negative value), there is no limit: the add succeeds whatever the count. *(Today: `-1` is taken as a limit, every count is `>= -1`, and the add is refused with "…limit (-1)…".)*
- **R6.** *(pending the plans/subscriptions design (BUG-1989): today's behaviour, kept in its own rule)* When `max_members` is `0`, there is no seat check and the add succeeds whatever the count.
- **R7.** A new member row is created: `workspace_id`, `user_id`, `role`, `position` as given, `status = 'active'`, `joined_at` = `utcnow()`, `left_at` NULL, `invited_at` = now (model default).
- **R8.** [BUG-1985] (Q6) `invited_by_user_id` = `inviter_id` (`None` stays NULL). *(Today: always NULL.)*
- **R9.** One audit row: this workspace, `user_id = inviter_id`, `action = 'member_added'`, `metadata = {"new_member_id": user_id, "role": role}` (A1, A2).
- **R10.** `user_id` is not checked here. An unknown profile fails the insert with `IntegrityError` (FK).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| role not in the list | `ValueError` | `Invalid role. Must be one of: ground-team, manager, member, owner, viewer` |
| row exists and is not `inactive` | `ValueError` | `User is already a member of this workspace` |
| workspace unknown | `ValueError` | `Workspace not found` |
| seats full | `ValueError` | `Workspace has reached maximum member limit (<n>). Upgrade subscription to add more members.` |

**Side effects:** 1 member row inserted (or 1 reactivated), 1 audit row, flushed, not committed.

---

## `WorkspaceManager.remove_member_from_workspace(session, workspace_id, user_id, remover_id, remover_role)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceService.remove_member` ← `DELETE /workspaces/{id}/members/{user_id}`; any active member may call; `remover_role` is the caller's stored role)

**Purpose:** Let the owner (or a ground-team manager, for ground-team members) take a member out of a workspace, keeping the row as history, and release what they held on open work.

**Returns:** `None` (gap 1).

**Rules:**
- **R1.** When the user has no membership row in this workspace, `ValueError("User is not a member of this workspace")` is raised. The same user's row in another workspace does not count (HR-16).
- **R1a.** [BUG-1984] (Q5) When the row is `inactive`, the same error is raised and nothing changes: `left_at` keeps its date, and no audit row is written. *(Today: the removal is repeated, `left_at` moves to now, and a second `member_removed` row is written.)*
- **R2.** When the member's role is `owner`, `ValueError("Cannot remove workspace owner. Transfer ownership first.")` is raised, whoever asks. This is checked before the remover's role.
- **R3.** When `remover_role` is `ground-team`, `ValueError("You do not have permission to remove members")` is raised.
- **R4.** (Q9) When `remover_role` is `ground-team-manager` and the member's role is not `ground-team`, `ValueError("Managers can only remove ground-team members")` is raised and nothing changes. A `ground-team-manager` may remove a `ground-team` member.
- **R4a.** (Q9) A `remover_role` of exactly `manager` may remove a `ground-team` member (this holds today).
- **R4b.** [BUG-1990] (Q9, owner) When `remover_role` is exactly `manager` and the member's role is not `ground-team`, `ValueError("Managers can only remove ground-team members")` is raised and nothing changes, as for `ground-team-manager` (R4). *(Today: a `manager` may remove any non-owner member.)* Both role names are kept for now; the roles will change in the permissions work (FLAG FOR LATER in `docs/future/permissions.md`).
- **R5.** [BUG-1990] (Q9, owner) Any `remover_role` other than exactly `owner`, `ground-team-manager` or `manager` (`member`, `viewer`, `finance`, `Owner`, `Manager`, `""`, anything else) raises `ValueError("You do not have permission to remove members")`, and nothing changes. The row stays as it was, no audit row is written, and no approver, project member or assignee row is touched. A non-owner cannot remove themselves either. *(Today: every such role may remove any non-owner member, themselves included.)*
- **R5a.** (Q9) With `remover_role` exactly `owner`, any non-owner member may be removed, whatever their role. `remover_id` is not checked against anything.
- **R6.** On success the row gets `status = 'inactive'` and `left_at` = `utcnow()`. Its role, position and `joined_at` stay. The row is not deleted.
- **R7.** One audit row: this workspace, `user_id = remover_id`, `action = 'member_removed'`, `metadata = {"removed_member_id": user_id}` (A1, A2).
- **R8.** [BUG-1201] Every pending approver row (`approved = false`) of that user on an **open** order of this workspace is deleted, on all five order types. For each order affected, one `approver_removed` event is written to that order's event log, as that type's `remove_approver` writes it: `performed_by` = `remover_id`, description `Removed <name> as approver`, metadata `{"user_id": <user_id>, "user_name": <name>}`, where `<name>` is the profile's `name`. The `User #<id>` fallback in the order managers applies only when the profile is missing. That cannot happen here: a membership row's `user_id` is a NOT NULL foreign key with ON DELETE CASCADE, and `profiles.name` is NOT NULL. An empty `name` (`""`) is used as it is (`Removed  as approver`, `user_name` `""`), not replaced by the fallback (gap 4). The same applies to R9 and R10. Rows with `approved = true` stay and still count. Rows on closed orders stay. "Open" means:
  - expense (`expense_orders`): `completed_at` IS NULL and `voided` = false;
  - purchase (`purchase_orders`): `voided` = false, the status named by `current_status_id` is not `Complete`, and either `invoice_id` IS NULL or that invoice's `invoice_status` is not `locked`;
  - sales (`sales_orders`): `order_completed` = false, and either `invoice_id` IS NULL or that invoice's `invoice_status` is neither `confirmed` nor `locked` (`SalesManager.is_so_financially_locked`, BUG-737's checks);
  - transfer (`transfer_orders`): `completed_at` IS NULL;
  - work (`work_orders`): `status` neither `COMPLETED` nor `VOIDED`.
  The event row goes to `<type>_order_events` with `event_type = 'approver_removed'` and the columns listed in the Notes for the test designer.
  An order left with no approver does not pass its gate until one is added (BUG-755, BUG-1202, BUG-736, BUG-1203, BUG-1204). *(Today: no approver row is touched.)* *(Requires a new read of one user's pending approver rows per order type.)*
- **R9.** [BUG-1280] Every `project_members` row of that user in this workspace is deleted. Each project gets one `member_removed` project event: `performed_by` = `remover_id`, description `Removed <name> from the project`, metadata `{"user_id", "user_name"}`. A member who later comes back (BUG-1982) has no project access until added again. *(Today: no project member row is touched.)* *(Requires a new read on `app/dao/project_member.py`.)*
- **R10.** [BUG-1883] (OQ-6) Every `work_order_assignees` row of that user on a work order of this workspace with status `DRAFT` or `IN_PROGRESS` is deleted. Each such order gets one work order event `assignee_removed`: `performed_by` = `remover_id`, description `Removed <name> as assignee`, metadata `{"user_id", "user_name"}`. `COMPLETED` and `VOIDED` orders keep their rows, and `work_order_completers` are never touched. A soft-deleted work order counts by its status like any other, so restoring it does not bring the person back (detail decided by Claude under the reviewer's delegation (2026-11-04)). The order's free-text `assigned_to` is left as it is. The next save re-matches it to **active** members only, so the person is not re-added. *(Today: no assignee row is touched.)* *(Requires a read of one user's assignee rows.)*
- **R11.** R8–R10 touch only rows of this workspace. The same person's approvals, project memberships and assignments in other workspaces stay (HR-16). Everything happens in the caller's transaction: if any step fails, the caller's rollback undoes the whole removal.
- **R12.** Removal does not cancel or change any invitation, and does not touch the member's other workspaces or their account.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no row, or row `inactive` (BUG-1984) | `ValueError` | `User is not a member of this workspace` |
| target is the owner | `ValueError` | `Cannot remove workspace owner. Transfer ownership first.` |
| remover is `ground-team`, or any role except `owner` / `ground-team-manager` / `manager` (BUG-1990) | `ValueError` | `You do not have permission to remove members` |
| remover is `ground-team-manager` or `manager` (BUG-1990), target not `ground-team` | `ValueError` | `Managers can only remove ground-team members` |

**Side effects:** the member row is updated (`status`, `left_at`) and flushed. One audit row is written. Approver, project member and assignee rows are deleted with their events (BUG-1201, BUG-1280, BUG-1883). Nothing is committed.

---

## `WorkspaceManager.create_invitation(session, workspace_id, email, role, inviter_id, position=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceService.send_invitation` ← `POST /workspaces/{id}/invitations/`, owner only, with `email` already validated by `InviteUserRequest` as `EmailStr`)

**Purpose:** Invite an email into the workspace with a role, holding a seat until the invitation is answered or expires.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `email` | str | not validated here; lower-cased when stored |
| `role` | str | exact, from the list in R1 |
| `inviter_id` | `int \| None` | stored as `invited_by_user_id`; not checked |
| `position` | `str \| None` | stored as given, carried to the member on accept |

**Returns:** the new `WorkspaceInvitation`, flushed, not committed.

**Rules:**
- **R1.** *(permissions feature, Q10)* `role` must be one of `manager`, `member`, `viewer`, `ground-team`. Anything else (`owner`, `ground-team-manager`, `finance`, `Manager`) raises `ValueError("Invalid role. Must be one of: ground-team, manager, member, viewer")` before anything is read.
- **R2.** [BUG-1860] (OQ-1) The account for `email` is found ignoring capitals and surrounding spaces: inviting `Ann.Lee@Example.com` finds the account stored `ann.lee@example.com` (and, before BUG-1861's migration, `Ann.Lee@example.com`). *(Today: exact match, so a case variant of a member's email is not recognised and the invitation is created.)*
- **R3.** When that account has an `active` row in this workspace, `ValueError("User with this email is already a member of this workspace")` is raised and nothing is written. When no account has the email, or the account has no row here, the check passes.
- **R3a.** [BUG-1983] (Q4) The same refusal applies to any existing row whose status is not `inactive` (e.g. `suspended`). An `inactive` row (a removed member) passes, and accepting brings it back (BUG-1982). *(Today: only `active` is refused.)*
- **R4.** [BUG-1873] (OQ-3) When this workspace already has an invitation to the same email with `status = 'pending'` and `expires_at` later than `utcnow()`, `ValueError("This email is already invited to this workspace")` is raised and nothing is written. Emails are compared lower-cased and trimmed on both sides. Checked after R3 and before R5. An expired pending invitation, an accepted or cancelled one, or a pending one in another workspace does not block. *(Today: nothing checks it, and each invitation takes a seat.)*
- **R5.** When the workspace does not exist, `ValueError("Workspace not found")` is raised.
- **R6.** The seat check uses the workspace's plan (R4 of `add_member_to_workspace` applies: a plan always exists, and an inactive one is still enforced).
- **R7.** When `max_members` is positive and **active members + pending unexpired invitations** of this workspace (`count_pending_invitations`: status exactly `pending` and `expires_at > now`) are at least `max_members`, `ValueError("Workspace has reached maximum member limit (<max_members>). Upgrade subscription to add more members.")` is raised and nothing is written. With one free seat the invitation is created. Invitations and members of other workspaces do not count.
- **R8.** [BUG-1871] (OQ-2) When `max_members` is negative, there is no limit: the invitation is created whatever the count. *(Today: refused with "…limit (-1)…".)*
- **R9.** *(pending the plans/subscriptions design (BUG-1989): today's behaviour, kept in its own rule)* When `max_members` is `0`, there is no seat check and the invitation is created whatever the count.
- **R10.** The invitation row: `workspace_id`; `email` = the given email lower-cased (`Ann@Acme.COM` → `ann@acme.com`); `role`; `position`; `invited_by_user_id = inviter_id`; `status = 'pending'`; `invited_at` = now (model default); `accepted_at` and `accepted_by_user_id` NULL.
- **R11.** `token` is a fresh random URL-safe string of 43 characters (`secrets.token_urlsafe(32)`), different on every call.
- **R12.** `expires_at` = `utcnow()` + exactly 3 days (Q12).
- **R13.** One audit row: this workspace, `user_id = inviter_id`, `action = 'invitation_sent'`, `metadata = {"email": <email as given, not lower-cased>, "role": role}` (A1, A2).
- **R14.** Nothing is sent to the invited person. The owner passes the token on by hand (notifications feature).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| role not in the list | `ValueError` | `Invalid role. Must be one of: ground-team, manager, member, viewer` |
| account already a member (R3, R3a) | `ValueError` | `User with this email is already a member of this workspace` |
| pending invitation to that email (BUG-1873) | `ValueError` | `This email is already invited to this workspace` |
| workspace unknown | `ValueError` | `Workspace not found` |
| seats full | `ValueError` | `Workspace has reached maximum member limit (<n>). Upgrade subscription to add more members.` |

**Side effects:** 1 invitation row and 1 audit row inserted, flushed, not committed.

---

## `WorkspaceManager.validate_invitation_for_user(session, invitation_token, user_email)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.accept_invitation` ← `POST /workspaces/{id}/invitations/accept/`, with the signed-in user's stored email, followed by a check that the invitation's workspace is the one in the URL; `AuthService._register_with_invitation` ← registration with a token, with the email being registered)

**Purpose:** Decide whether this person may accept the invitation behind this token.

**Returns:** the `WorkspaceInvitation`, unchanged.

**Rules:**
- **R1.** An unknown token (exact match, any workspace; workspace invitation DAO `get_by_token`) raises `ValueError("Invalid invitation token")`.
- **R2.** [BUG-1987] (Q8) An invitation whose `expires_at` is at or before `utcnow()` raises `ValueError("Invitation has expired. Please request a new invitation.")`. One microsecond after `utcnow()` passes. *(Today: refused only when strictly before. At exactly `expires_at` it passes.)*
- **R3.** Expiry is checked before status: an accepted or cancelled invitation that has also expired gets the expiry message.
- **R4.** An unexpired invitation whose `status` is not exactly `pending` raises `ValueError("Invitation has already been <status>")`, for example `…already been accepted` or `…already been cancelled`.
- **R5.** When the invitation's email and `user_email` differ ignoring capitals, `ValueError("This invitation was sent to <invitation email>. You cannot accept it with <user_email as given>.")` is raised. Same letters in other capitals pass (OQ-1). Surrounding spaces are not removed. Both callers pass already-validated emails.
- **R6.** Checks run in the order R1, R2, R4, R5. Nothing is written, and the invitation's workspace is not checked here (the token is the credential).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown token | `ValueError` | `Invalid invitation token` |
| expired | `ValueError` | `Invitation has expired. Please request a new invitation.` |
| not pending | `ValueError` | `Invitation has already been <status>` |
| other email | `ValueError` | `This invitation was sent to <email>. You cannot accept it with <user_email>.` |

**Side effects:** none.

---

## `WorkspaceManager.accept_invitation(session, invitation_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceService.accept_invitation` and `AuthService._register_with_invitation`, both right after `validate_invitation_for_user` on the same invitation)

**Purpose:** Turn a valid invitation into a membership.

**Returns:** the `WorkspaceMember` from `add_member_to_workspace`, flushed, not committed.

**Rules:**
- **R1.** An unknown `invitation_id` raises `ValueError("Invitation not found")`, and nothing is written.
- **R2.** The invitation's state, expiry and email are **not** checked here. The callers validate first. Called on an accepted, cancelled or expired invitation, it still adds the user.
- **R3.** The user is added as `add_member_to_workspace` does (all its rules apply, BUG-1982 and BUG-1872 included), with the invitation's `workspace_id`, `role` and `position`, and `inviter_id` = the invitation's `invited_by_user_id` (which may be NULL). The `member_added` audit row therefore names the inviter. If the add raises, the invitation is left unchanged.
- **R4.** The invitation then gets `status = 'accepted'`, `accepted_at` = `utcnow()` and `accepted_by_user_id = user_id`.
- **R5.** [BUG-1874] (OQ-3) Every **other** invitation of the same workspace to the same email (compared lower-cased) with `status = 'pending'` gets `status = 'cancelled'`, expired or not. Each gets one audit row: `action = 'invitation_cancelled'`, `user_id` = the accepting user, `metadata = {"invitation_id": <its id>, "email": <its email>, "reason": "superseded"}` (audit detail decided by Claude under the reviewer's delegation (2026-11-04)). Invitations to that email in other workspaces, and invitations to other emails, are not touched. *(Today: they stay `pending` and hold a seat until they expire.)*
- **R6.** One audit row: the invitation's workspace, `user_id` = the accepting user, `action = 'invitation_accepted'`, `metadata = {"invitation_id": invitation_id}` (A1, A2). Together with R3 a successful accept writes `member_added` and `invitation_accepted` (plus R5's rows).
- **R6a.** (gap 7, decided by Claude under the reviewer's delegation (2026-11-04)) The audit rows of one accept are written in this order, which shows as ascending `id`: `member_added`, then `invitation_accepted`, then R5's `invitation_cancelled` rows in ascending invitation `id`. Today only the first two exist, in that order. Every one of them, R5's rows included, carries the call's `ip_address` and `user_agent` (A2, BUG-1404). *Why:* the cancellations are a consequence of the acceptance, so they follow it in the log, and A2 already says every audit row a method writes carries the request's IP and user agent.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown invitation | `ValueError` | `Invitation not found` |
| any refusal of `add_member_to_workspace` | `ValueError` | as there |

**Side effects:** 1 member row inserted or reactivated. The invitation is updated, and other pending invitations to that email are cancelled (BUG-1874). Audit rows are written. Everything is flushed, nothing committed.

---

## `WorkspaceManager.cancel_invitation(session, invitation_id, canceller_id, canceller_role, workspace_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceService.cancel_invitation` ← `DELETE /workspaces/{id}/invitations/{invitation_id}`; any active member may call; `canceller_role` is their stored role)

**Purpose:** Withdraw a pending invitation, freeing its seat.

**Returns:** `None` (gap 1).

**Rules:**
- **R1.** [BUG-1986] (Q7, Q11) When `canceller_role` is not exactly `owner`, `ValueError("Only the workspace owner can cancel invitations")` is raised first, whatever the invitation id: unknown, foreign, pending or not. Nothing changes. *(Today: this check comes last. A non-owner first gets "Invitation not found", the workspace message or the status message.)*
- **R2.** [BUG-1981] (HR-16) An unknown `invitation_id`, or an invitation of another workspace, raises `ValueError("Invitation not found")`, and nothing changes. *(Today: another workspace's invitation gets "Invitation does not belong to this workspace".)*
- **R3.** An invitation whose `status` is not exactly `pending` raises `ValueError("Cannot cancel invitation that is <status>")`, for example `…that is accepted` or `…that is cancelled`.
- **R4.** A pending invitation that has already expired can still be cancelled.
- **R5.** On success the invitation gets `status = 'cancelled'`. No other field changes.
- **R6.** One audit row: this workspace, `user_id = canceller_id`, `action = 'invitation_cancelled'`, `metadata = {"invitation_id": invitation_id, "email": <the invitation's stored `email`, exactly as stored>}` (A1, A2). Nothing is lower-cased at cancel: a row written outside this manager as `Ann@X.com` is logged as `Ann@X.com` (gap 6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not the owner | `ValueError` | `Only the workspace owner can cancel invitations` |
| unknown or other workspace (BUG-1981) | `ValueError` | `Invitation not found` |
| not pending | `ValueError` | `Cannot cancel invitation that is <status>` |

**Side effects:** the invitation is updated and flushed, and 1 audit row is written. Nothing is committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 92 | `subscription_plan_id` truthy / falsy (`None`, `0`) | `create_workspace_with_owner` R1, R3 |
| 93–95 | plan missing or `not is_active` | `create_workspace_with_owner` R2 |
| 97–99 | no active default plan (`get_default_plan` R1–R4) | `create_workspace_with_owner` R3 |
| 102–103 | slug taken (exact, `get_by_slug`) | `create_workspace_with_owner` R4, R5 |
| 106–114 | row built from schema; `owner_position` dropped; plan, owner, creator, trial +14 d | `create_workspace_with_owner` R6, R12 |
| 116–118 | owner profile found and `timezone` truthy / otherwise | `create_workspace_with_owner` R7 |
| 120–135 | workspace flush; owner member row | `create_workspace_with_owner` R8, R11 |
| 138–142 | five seed calls (new workspace: every "already exists" branch inside them takes the create path; `seed_po_workflow` raises `RuntimeError` only if no workflow can be made, unreachable for a new workspace) | `create_workspace_with_owner` R9 |
| 145–151 | audit `workspace_created` | `create_workspace_with_owner` R10; A1, A2 |
| 189–190 | role not in `VALID_MEMBER_ROLES` | `add_member_to_workspace` R1 |
| 193–197 | existing row (any status) → refuse | `add_member_to_workspace` R2, R2a |
| 200–202 | workspace missing | `add_member_to_workspace` R3 |
| 204–205 | `plan and plan.max_members`: positive / negative (BUG-1872) / `0` (BUG-1989, pending) | `add_member_to_workspace` R4, R5, R5a, R6 |
| 209–213 | `count >= max_members` | `add_member_to_workspace` R5 |
| 216–224 | member insert (no `invited_by_user_id`) | `add_member_to_workspace` R7, R8, R10 |
| 227–233 | audit `member_added` | `add_member_to_workspace` R9 |
| 268–272 | no row → refuse (any status matches) | `remove_member_from_workspace` R1, R1a |
| 275–276 | target role `owner` | `remove_member_from_workspace` R2 |
| 279–280 | remover `ground-team` | `remove_member_from_workspace` R3 |
| 282–283 | remover `ground-team-manager` (BUG-1990: or `manager`) and target not `ground-team` | `remove_member_from_workspace` R4, R4a, R4b |
| 279–283 fall-through | any other remover role (BUG-1990: only `owner` passes) | `remove_member_from_workspace` R5, R5a |
| 286–288 | `inactive`, `left_at`, flush | `remove_member_from_workspace` R6 |
| 291–297 | audit `member_removed` | `remove_member_from_workspace` R7 |
| (absent) | approver / project member / assignee clean-up | `remove_member_from_workspace` R8–R11 |
| 334–335 | role not in `VALID_INVITE_ROLES` | `create_invitation` R1 |
| 339–340 | account found by email (exact today, BUG-1860) / not | `create_invitation` R2, R3 |
| 344–345 | row exists and `status == 'active'` / other status (BUG-1983) | `create_invitation` R3, R3a |
| (absent) | duplicate pending invitation (BUG-1873) | `create_invitation` R4 |
| 348–350 | workspace missing | `create_invitation` R5 |
| 352–353 | `plan and plan.max_members`: positive / negative (BUG-1871) / `0` (BUG-1989, pending) | `create_invitation` R6, R8, R9 |
| 354–365 | active + pending `>= max_members` | `create_invitation` R7 |
| 368–381 | token, lower-cased email, 3 days, pending | `create_invitation` R10, R11, R12 |
| 384–390 | audit `invitation_sent` (email as given) | `create_invitation` R13 |
| 424–428 | token unknown | `validate_invitation_for_user` R1 |
| 431–432 | `expires_at < utcnow()` (BUG-1987: `<=`) | `validate_invitation_for_user` R2, R3 |
| 435–436 | status not `pending` | `validate_invitation_for_user` R4 |
| 439–443 | emails differ ignoring case | `validate_invitation_for_user` R5, R6 |
| 473–475 | invitation unknown | `accept_invitation` R1, R2 |
| 478–485 | add through `add_member_to_workspace` | `accept_invitation` R3 |
| 488–491 | accepted, `accepted_at`, `accepted_by_user_id`, flush | `accept_invitation` R4 |
| (absent) | other pending invitations to the email (BUG-1874) | `accept_invitation` R5 |
| 494–500 | audit `invitation_accepted` | `accept_invitation` R6 |
| 532–534 | invitation unknown | `cancel_invitation` R2 |
| 536–537 | other workspace (BUG-1981) | `cancel_invitation` R2 |
| 539–540 | status not `pending` | `cancel_invitation` R3, R4 |
| 543–544 | canceller not `owner` (BUG-1986: first) | `cancel_invitation` R1 |
| 547–557 | `cancelled`, flush, audit | `cancel_invitation` R5, R6 |
| 561 | module singleton | Not specified |

## Gap log
G1 (`workspace_manager.cases.md` gap 1) — Fact — `remove_member_from_workspace` and `cancel_invitation` now have **Returns:** `None`.
G2 (gap 2) — Fact — `create_workspace_with_owner` R6 names `current_storage_mb`, `current_orders_this_month`, `current_factories_count`, `current_machines_count` and `current_projects_count` (all `0`); `stripe_customer_id` and `stripe_subscription_id` (NULL); and `last_usage_reset_at` (model default).
G3 (gap 3) — Fact — R8 states "open" in columns for all five order types (purchase: `voided`, `current_status_id` → `Complete`, invoice `invoice_status` `locked`; sales: `order_completed`, invoice `invoice_status` `confirmed` / `locked`). The event tables' columns are in the Notes for the test designer (`event_type`, `description`, `metadata` / `metadata_json`, `performed_by`, `<type>_id`).
G4 (gap 4) — Fact — the `User #<id>` fallback is unreachable from removal (member `user_id` FK NOT NULL ON DELETE CASCADE; `profiles.name` NOT NULL); an empty name is used as it is. No card is needed for the fallback.
G5 (gap 5) — Test mechanics / fact — R7: the `{}` case is observed with a profile whose `timezone` is `None` or `""`; the missing-profile case can only be seen as R11's failure.
G6 (gap 6) — Fact — `cancel_invitation` R6: `metadata.email` is the stored value, exactly as stored, with nothing lower-cased.
G7 (gap 7) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) — `accept_invitation` R6a: `member_added`, `invitation_accepted`, then the superseded `invitation_cancelled` rows by ascending invitation `id`; all of them carry IP and user agent (A2). Not money; no bug beyond BUG-1874 / BUG-1404.
G8 (gap 8) — Test mechanics — patch `workspace_manager.workspace_dao` (or `get_by_slug` on that singleton); see the Notes for the test designer.
G9 (gap 9) — Fact (column types read on `marker_test` in a rolled-back transaction) — every datetime here is `timestamp without time zone`, naive UTC; only `workspace_audit_logs.created_at` is `timestamptz`.
G10 (gap 10) — Fact — the column names `item_tags.tag_code`, `account_tags.tag_code` and `order_workflows.type` (and `name`) are confirmed in the model and the database; R9 names them.
