# Spec — `app/services/workspace_service.py`

> **Status:** APPROVED (2026-11-04; nothing open). No owner question: every item below is a house rule, an owner answer already given (OQ-2, OQ-3, OQ-6, OQ-16, OQ-17, BUG-1990), or was decided by Claude under the reviewer's delegation (2026-11-04).
> **Source commit:** e48a092

> **Revision 2026-11-06 (verification gaps, `workspace_service.verify.md`).** TX1a: the pre-commit TC3 path of `remove_member`, `cancel_invitation`, `update_member_role` is not unit-testable (help-ticket fallback precedent). `update_member_role` R4a: the owner may change their own position, BUG-2258. Both decided by Claude under the reviewer's delegation (2026-11-06). Stays APPROVED.

> **Revision 2026-11-05 (executor follow-up).** `update_member_role` R5a: the owner role cannot be assigned, BUG-2257 (decided by Claude under the reviewer's delegation (2026-11-05)). Stays APPROVED.

> **Revision 2026-11-05 (fill-gaps, `workspace_service.cases.md` gap 4).** Module paths and fields of the request schemas named in `update_workspace` R5a (BUG-2256), checked against the code. No new bug; stays APPROVED.

> **Revision 2026-11-04 (fill-gaps, `workspace_service.cases.md` gaps 1–3).** Facts added from the code (`_require_owner` R3, the plan's `is_active`); TC3 / TC4 inputs that need no patch, verified on `marker_test` (`v2_gaps.py`). No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. The **Transaction contract TC1–TC6** is `tests/unit/services/base_service.spec.md`'s and is cited, not repeated. What the manager decides is **cited, not restated**: `tests/unit/managers/workspace_manager.spec.md` (APPROVED) and below it `tests/unit/dao/workspace.spec.md`, `workspace_member.spec.md`, `workspace_invitation.spec.md`, `profile.spec.md`, `base.spec.md`. This spec covers what the service adds: who may call (membership and owner checks), the translation of the manager's `ValueError`s, the accept-time workspace check and position override, the reads it does itself, and the transaction.
>
> **Answered upstream and applied here (not asked again):** OQ-2 (BUG-1871, BUG-1872), OQ-3 (BUG-1873, BUG-1874), OQ-6 (BUG-1883), OQ-16 (any active plan at creation, today's behaviour kept, pending the payment portal), OQ-17 (BUG-1989, `max_members = 0` kept as today, deferred), removal rule BUG-1990 (owner removes any non-owner; `ground-team-manager` and `manager` remove `ground-team` only; others 403). Manager follow-ups answered here: FU-1 (error mapping, D2 / BUG-2251), FU-2 (BUG-1404, IP and user agent pass through this service). DAO follow-ups answered here: workspace member DAO FU-1 (D3, D7), workspace invitation DAO FU-3 (D8).
>
> **Verified by running** (`v1_ws.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\`, one outer transaction rolled back against `marker_test`, session as the unit-test `db` fixture, private `COVERAGE_FILE`; nothing persisted): `update_workspace` on an unknown id → 404 `Workspace not found`, on another existing workspace → 403 `Only workspace owner can update workspace`; `settings` is replaced whole (`{"timezone": …}` → `{"foo": 1}`); `name: null` leaves the name; a refusal before the `try` leaves a flushed row of the session in place (no rollback); `update_member_role` on an `inactive` member succeeds; a direct call with `new_role="owner"` stores `owner` and the member then passes the owner-only checks; unknown workspace on role change → 404, non-owner → 403; `remove_member` of a non-member → 403 `User is not a member of this workspace`; a caller who is not a member → 403 `You are not a member of this workspace`; `list_members` hides the `inactive` row by default and shows it with `include_inactive` (order not by `id` after an update, BUG-1400); an inactive caller is refused; `get_workspace_with_plan` on an unknown id → 403, not 404; `cancel_invitation` of an unknown id → 403 `Invitation not found`. **Read, not run:** the invitation paths end to end, commit and refresh failures (TC4, TC5 hold as in `base_service.spec.md`).

## Review
> All decided; nothing pending. Overwrite an answer only to reverse it.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| D1 | Editing a workspace or a member's role answers "not found" for a missing workspace but "only the owner" for someone else's, so ids reveal which workspaces exist | bug — membership first, one answer for both (BUG-2250) | Claude, delegated |
| D2 | Every refusal from removing a member or cancelling an invitation is 403, "not found" included | bug — not found 404, wrong state 400, permission 403 (BUG-2251) | Claude, delegated |
| D3 | Four lists read the workspace / profile of each row one by one | bug — read together (BUG-2252) | Claude, delegated (precedent BUG-1964) |
| D4 | Changing a member's role, or the workspace's name, billing email or settings, leaves no audit row | bug — audit rows `member_role_changed`, `workspace_updated` (BUG-2253) | Claude, delegated |
| D5 | A removed member's role can still be changed | bug — "Member not found", as for removal (BUG-2254) | Claude, delegated (precedent BUG-1984) |
| D6 | Two notions of "owner" (`owner_user_id` for edits, membership role `owner` for invitations) | intended — they coincide on every API path; noted for the permissions feature | Claude, delegated |
| D7 | Member list and workspace list are not sorted by name | intended — not paged; `id` order (BUG-1400) is enough | Claude, delegated |
| D8 | "My invitations" can list an invitation to a workspace the user already belongs to | intended — unreachable once BUG-1873 / BUG-1874 are fixed; accepting it answers "already a member" | Claude, delegated |
| D9 | `settings` sent on edit replaces the whole settings object | intended — the only key is `timezone`; recorded as a rule | Claude, delegated |

### House-rule violations — applied automatically
- **HR-1** `update_workspace` R4 — `WorkspaceUpdate.name` is not trimmed and `"   "` is accepted. Already logged by the workspace manager review.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1980 (existing; its fix names `WorkspaceUpdate.name`). No new ID.

### Decisions (decided by Claude under the reviewer's delegation, 2026-11-04)

### D1. A missing workspace and someone else's workspace answer differently on edit — 🐞 BUG-2250
**Background:** Every other method of this service first checks that the caller is an active member of the workspace, so a missing workspace and a workspace they do not belong to both answer 403 "You are not a member of this workspace". `update_workspace` and `update_member_role` instead look the workspace up first and then compare `owner_user_id`. Precedent BUG-440 / BUG-941: a record the caller may not see answers exactly as a missing one.
**What happens today:** `PATCH /workspaces/99999/` → 404 `Workspace not found`; `PATCH /workspaces/42/` (exists, not theirs) → 403 `Only workspace owner can update workspace` (verified).
**Example:** A user steps through ids with `PATCH /workspaces/<n>/` and learns how many workspaces the platform has.
**Rules affected:** `update_workspace` R1, R2; `update_member_role` R1, R2
**Answer:** bug — per BUG-440 precedent: the caller must first be an active member (`_require_active_membership`): a missing workspace and a workspace they are not an active member of both answer 403 `You are not a member of this workspace`; then a member who is not the owner gets today's 403 owner message.
**Resolution:** 🐞 BUG-2250 (pattern `existence-disclosure-403-vs-404`). Rules: `update_workspace` R1, `update_member_role` R1.

### D2. Not-found and wrong-state refusals of remove and cancel answer 403 — 🐞 BUG-2251
**Background:** `remove_member` and `cancel_invitation` turn every `ValueError` of the manager into `PermissionDeniedError` (403). Workspace manager FU-1 left the mapping to this review. Precedent: `lossy-error-mapping` (BUG-463, BUG-2141): a status code must say what happened.
**What happens today:** Removing someone who is not a member → 403 `User is not a member of this workspace`; cancelling an unknown invitation → 403 `Invitation not found`; cancelling an accepted one → 403 `Cannot cancel invitation that is accepted` (first two verified).
**Example:** The owner's screen is stale; they cancel an invitation that was just accepted. The app shows "Permission denied" although they are the owner.
**Rules affected:** `remove_member` R3; `cancel_invitation` R3
**Answer:** bug — "User is not a member of this workspace" and "Invitation not found" → `NotFoundError` (404); "Cannot cancel invitation that is <status>" → `ValidationError` (400); every other refusal (owner target, remover role, non-owner canceller) stays 403. Texts unchanged. How the manager signals the kind (distinct exception classes, or a code) is the fix's choice.
**Resolution:** 🐞 BUG-2251 (pattern `lossy-error-mapping`). Rules: `remove_member` R3, `cancel_invitation` R3.

### D3. Four lists read one workspace or profile per row — 🐞 BUG-2252
**Background:** Precedent BUG-1964 / BUG-1141 / BUG-2119 (`n-plus-one-read`): related rows are read together.
**What happens today:** `list_user_workspaces` reads each workspace by id; `list_members` reads each member's profile; `list_invitations` reads the inviter of each invitation (usually the same owner); `get_my_invitations` reads workspace and inviter per invitation (read).
**Example:** A 200-person Enterprise workspace's members page makes 200 profile reads.
**Rules affected:** `list_user_workspaces` R4, `list_members` R5, `list_invitations` R5, `get_my_invitations` R4
**Answer:** bug — per BUG-1964 precedent: the number of statements does not grow with the rows (at most one read of the rows plus one per related table after the access check); results unchanged.
**Resolution:** 🐞 BUG-2252 (pattern `n-plus-one-read`).

### D4. Role changes and workspace edits leave no audit row — 🐞 BUG-2253
**Background:** `workspace_audit_logs` records workspace administration: created, member added, member removed, invitation sent / accepted / cancelled (workspace audit log DAO spec). A role change is a change of privilege (a `ground-team` member made `manager` may now remove members, BUG-1990), and the billing email belongs to the coming payment portal.
**What happens today:** `update_member_role` and `update_workspace` write no audit row (read).
**Example:** A `viewer` is made `manager`, removes three people, and is set back to `viewer`. The log shows the three removals by someone who is a `viewer`.
**Rules affected:** `update_member_role` R6; `update_workspace` R6
**Answer:** bug — a role change writes one audit row `member_role_changed`, `user_id` = the owner, `metadata = {"member_id": <target user id>, "from_role": <old>, "to_role": <new>, "from_position": <old>, "to_position": <new>}`; a workspace edit writes one `workspace_updated`, `metadata = {"fields": [<names of the fields whose value changed>]}` (values not copied: settings may be large). Written only when something changed (as HR-9); both carry IP and user agent (BUG-1404).
**Resolution:** 🐞 BUG-2253 (pattern `missing-audit-row`).

### D5. A removed member's role can be changed — 🐞 BUG-2254
**Background:** Removal keeps the row with `status = 'inactive'`. BUG-1984 ruled that such a row is "not a member" for removal; BUG-1982 makes accepting a new invitation set the role from the invitation.
**What happens today:** `update_member_role` on an `inactive` row succeeds (verified); the change is lost when the person comes back.
**Example:** The owner opens "show inactive", sets Rahim (removed) to `manager`. Nothing visible happens; when Rahim is invited back as `viewer`, he is a `viewer`.
**Rules affected:** `update_member_role` R3
**Answer:** bug — per BUG-1984 precedent: an `inactive` row answers `NotFoundError("Member not found")`, nothing changed. Other non-active statuses (`suspended`) can still be changed.
**Resolution:** 🐞 BUG-2254 (pattern `missing-state-guard`).

### D6–D9 — intended
- **D6.** `update_workspace` / `update_member_role` compare `workspaces.owner_user_id`; `send_invitation` / `list_invitations` require an active membership with role exactly `owner`. On every API path they name the same person (the creator gets both; `owner` cannot be given through `RoleChangeRequest` or an invitation; the owner cannot be removed or demoted; there is no ownership transfer). Recorded in `docs/future/permissions.md` (one owner helper). No rule changes.
- **D7.** Member and workspace lists are not paged; `id` order (BUG-1400) is stable. Display order is left to the client.
- **D8.** Workspace invitation DAO FU-3: an invitation to a workspace where the user is already active can exist only from data made before BUG-1873 / BUG-1874; accepting it answers "User is already a member of this workspace" (400). Listed as today.
- **D9.** `settings` is stored as sent (the whole object); `null` leaves it. The only key in use is `timezone`.

Checked and **not** violated: **HR-2** — the slug is the manager's (exact, unique index). **HR-3, HR-8** — no grouping or `LIKE`. **HR-4** — no soft-delete column on workspaces, members or invitations. **HR-5, HR-6, HR-7** — no list here is paged; orders are the DAOs' (BUG-1400, BUG-1401). **HR-9** — no `updated_by` column; `updated_at` is `onupdate`. **HR-10** — role change and edits are plain changes; seat checks are the manager's (recorded for the payment portal). **HR-11 … HR-15** — no external system, money or rounding. **HR-16** — every member lookup takes workspace and user together; the accept path checks the invitation's workspace (`accept_invitation` R2); cancel is BUG-1981 (manager).

**Permission checks** (this service is where they live; the endpoints use only `get_current_active_user`, never `get_current_workspace`):
| Method | Who may call |
|---|---|
| `list_user_workspaces`, `create_workspace`, `get_my_invitations`, `accept_invitation` | any signed-in user |
| `get_workspace_with_plan`, `list_members`, `remove_member`, `cancel_invitation` | an active member (then the manager's role rules for remove / cancel) |
| `send_invitation`, `list_invitations` | an active member with role exactly `owner` |
| `update_workspace`, `update_member_role` | the user named by `workspaces.owner_user_id` (BUG-2250: an active member first) |

## Overview
`WorkspaceService` is the transaction boundary and permission gate for workspace administration: the workspace switcher list, creating and editing a workspace, the members page (list, role change, removal) and invitations (send, list, accept, cancel, "my invitations"). The `/workspaces/` endpoints call it. It calls `WorkspaceManager` for the rules with side effects and reads DAOs directly for lists. Refusals are `APIException` subclasses (`app/core/exceptions.py`): `PermissionDeniedError` 403, `NotFoundError` 404, `ValidationError` 400, each with `.status_code` and `.detail`.

**Callables:** 14 specified · 2 not specified
**Externals to mock:** `utcnow` only as the manager spec says (`app.managers.workspace_manager.utcnow`, `app.dao.workspace_invitation.utcnow`). No notification, email or external call.
**Integration-only behavior:** the endpoint's response shaping (`WorkspaceListItem.is_owner`, `WorkspaceWithPlan` plan fields, `WorkspaceMemberWithUser` name/email, `WorkspaceInvitationWithDetails`); request validation (`WorkspaceCreate`, `WorkspaceUpdate`, `RoleChangeRequest` role list, `InviteUserRequest` `EmailStr`); the HTTP status from an `APIException`; the global `IntegrityError` handler.

### Transaction contract
TC1–TC6 as `tests/unit/services/base_service.spec.md`, with these differences, which are rules of this service:
- **TX1.** `create_workspace`, `send_invitation`, `accept_invitation`: a plain `ValueError` from the manager is not passed on; it becomes `ValidationError(str(e))` (400, same text), after the rollback (TC3 otherwise holds: nothing saved, every pending change of the session discarded). `remove_member`, `cancel_invitation`: it becomes `PermissionDeniedError(str(e))` (403) (BUG-2251 changes some of these). The original `ValueError` is the new error's `__context__`. Any other exception passes unchanged (TC3).
- **TX1a.** (verification gap, 2026-11-06, decided by Claude under the reviewer's delegation) The TC3 path — an exception raised **inside** the `try` **before** the commit, rolling back the session and discarding other pending changes — is **not unit-testable** for `remove_member`, `cancel_invitation` and `update_member_role`: every input that fails there is already refused before the `try` (TX2) or, for `update_member_role`, fails only at the commit (TC4 path; there is no manager call), so it is reached only by patching the workspace manager, which is not an external. Same fallback as `help_ticket_service.spec.md` (2026-11-04). Their TX1 translation (manager `ValueError` → 403) stays testable with real refusals, and TC4 / TC5 are tested with a patched `commit` / `refresh`. No case is written for that TC3 path.
- **TX2.** Refusals raised **before** the method's `try` (membership, owner and lookup checks: `update_workspace` R1–R2, `update_member_role` R1–R3, `remove_member` R1, `send_invitation` R1, `cancel_invitation` R1) neither commit nor roll back: other changes pending in the session stay pending (verified).
- **TX3.** `remove_member` and `cancel_invitation` return `None` and do no re-read (TC2, TC5 do not apply). `update_member_role` and `update_workspace` re-read the member / workspace (TC2).
- **TX4.** Reads (`list_user_workspaces`, `get_workspace_with_plan`, `list_members`, `list_invitations`, `get_my_invitations`) follow TC6.

**Facts for the test designer**
- Import: `from app.services.workspace_service import WorkspaceService, workspace_service`. `WorkspaceService()` takes no argument; attributes `workspace_manager`, `workspace_dao`, `member_dao`, `invitation_dao`, `profile_dao` are the module singletons. Every parameter is positional-or-keyword; the endpoints pass all after `db` by keyword.
- Exceptions: `from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError`; assert `type`, `.status_code`, `.detail`.
- Manager messages: `workspace_manager.spec.md` Errors tables, used here unchanged.

**Notes for the test designer**
- Session, commits, TC1–TC6 mechanics: as the Notes of `department_service.spec.md`.
- Build directly: `make_profile`, `make_workspace` (`tests/unit/factories.py`), set `workspace.owner_user_id`; `WorkspaceMember(workspace_id, user_id, role, status)`; `WorkspaceInvitation(workspace_id, email, role, token, expires_at, status, invited_by_user_id)`. For `create_workspace`, one active default plan (`make_subscription_plan(is_default=True, is_active=True)`), as the manager notes say.
- **BUG-1404 rules:** the parameters do not exist today; calling with `ip_address=` raises `TypeError` → strict xfail.
- **BUG-2252:** count statements with a `before_cursor_execute` listener; 5 rows → intended ≤ 3 statements (rows, related table, access check) → strict xfail.
- Pass-through cases: one per manager bug reached, xfail exactly as the manager's cases file.
- **TC3 / TC4 without a patch (gap 2, verified):** column lengths: `workspaces.name` and `billing_email` `String(255)`, `workspace_members.role` `String(50)`, `position` `String(255)`. `WorkspaceUpdate` bounds `name` (≤ 255) but not `billing_email`, so `update_workspace(…, WorkspaceUpdate(billing_email="a" * 256))` fails **inside the `try`** at the DAO's flush with `sqlalchemy.exc.DataError` (pgcode `22001`): rolled back, a flushed uncommitted row of the session is gone, the error reaches the caller unchanged (TC3). `update_member_role(…, position="p" * 256)` (or a `new_role` over 50 characters) fails at the commit's flush, the same `DataError` (TC4 path: no flush before the commit): the role is unchanged and a pending row is gone. Both verified on `marker_test`.
- **After BUG-2256 (2026-11-05):** those over-long values are today's only patch-free way into the `try`, and they stay valid TC3 / TC4 cases while BUG-2256 is open: pass them as **constructed** schemas (`WorkspaceUpdate.model_construct(billing_email="a" * 256)`, or `position=` straight to the service, which has no schema), so the cards keep working after the schemas gain the cap. If a card must use a validated schema, BUG-2256 closes that door; then the way in is a patched DAO / `commit` (`patch.object(db, "commit", side_effect=…)`, TC4) or a `refresh` patch (TC5). The BUG-2256 rule itself (`update_workspace` R5a) is a schema case: building the schema with 256 characters must raise `pydantic.ValidationError` → strict xfail today.

## Not specified
- `WorkspaceService.__init__` — wires the manager and DAOs, no logic.
- `workspace_service` — module-level singleton.

---

## `WorkspaceService._require_active_membership(db, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_require_owner`, `get_workspace_with_plan`, `list_members`, `remove_member`, `cancel_invitation`; BUG-2250 adds `update_workspace`, `update_member_role`)

**Returns:** the caller's `WorkspaceMember`.

**Rules:**
- **R1.** Returns the user's membership row of that workspace (workspace member DAO `get_by_workspace_and_user`) when its `status` is exactly `active`.
- **R2.** No row (unknown workspace, `0`, a workspace the user never joined, an unknown user) → `PermissionDeniedError("You are not a member of this workspace")` (403). A missing workspace and someone else's answer the same.
- **R3.** A row whose status is not exactly `active` (`inactive`, `suspended`, `invited`, `Active`) → the same 403.
- **R4.** The role is not looked at. A platform admin who is not a member is refused like anyone.

---

## `WorkspaceService._require_owner(db, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `send_invitation`, `list_invitations`)

**Rules:**
- **R1.** First `_require_active_membership` R1–R4.
- **R2.** Then the row's `role` must be exactly `owner`; otherwise `PermissionDeniedError("Only the workspace owner can perform this action")` (403). `workspaces.owner_user_id` is not looked at (D6): an active member whose stored role is `owner` passes even if not `owner_user_id` (only reachable through a direct call, verified).
- **R3.** (gap 1) On success it returns the caller's own `WorkspaceMember` row (the one `_require_active_membership` returned; verified: a `WorkspaceMember` with the caller's `user_id`).

---

## `WorkspaceService.list_user_workspaces(db, user_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /workspaces/`, the workspace switcher)

**Returns:** a `list` of `(Workspace, WorkspaceMember)`.

**Rules:**
- **R1.** One pair per membership of the user (workspace member DAO `get_by_user` R1–R3) whose `status` is exactly `active`; other statuses are left out.
- **R2.** Order: as `get_by_user` (`id` ascending, BUG-1400; D7). No paging, no cap.
- **R3.** A membership whose workspace no longer exists is skipped (unreachable: the FK cascades).
- **R4.** [BUG-2252] (D3) The workspaces are read together: the statement count does not grow with the memberships. *(Today: one read per active membership.)*
- **R5.** Unknown user or none active → `[]`. Read only (TC6).

---

## `WorkspaceService.create_workspace(db, workspace_data, owner_user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /workspaces/`, any signed-in user)

**Returns:** the new `Workspace`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The workspace is created exactly as `WorkspaceManager.create_workspace_with_owner` creates it (manager R1–R12: owner member, seeded statuses, workflow, departments, tags, audit row), with `subscription_plan_id = workspace_data.subscription_plan_id` and `owner_position = workspace_data.owner_position` taken from the request body. Plan choice is manager R1 *(pending the payment portal, OQ-16: any active plan accepted today)*. BUG-1980 (blank name) reaches it.
- **R2.** A manager `ValueError` (`Invalid subscription plan`, `No default subscription plan found`, `Workspace slug '<slug>' is already taken. Please choose a different name.`) → `ValidationError` 400 with the same text, nothing saved (TX1).
- **R3.** Any other exception (`IntegrityError` from a slug race or a missing profile) passes unchanged, nothing saved (TC3); commit and re-read failures TC4, TC5.
- **R4.** [BUG-1404] (manager FU-2) New optional keyword parameters `ip_address`, `user_agent` (default `None`) reach the manager, so the `workspace_created` audit row carries them. *(Today: no such parameters; both NULL.)* The endpoint passes the request's client address (trusted-proxy handling) and `User-Agent`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| manager `ValueError` | `ValidationError` 400 | the manager's text |
| anything else | unchanged | — |

**Side effects:** the manager's rows, committed. On error: rolled back.

---

## `WorkspaceService.get_workspace_with_plan(db, workspace_id, requesting_user_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /workspaces/{id}/`)

**Returns:** `(Workspace, SubscriptionPlan)`.

**Rules:**
- **R1.** The caller must pass `_require_active_membership` (403 otherwise; an unknown id is 403, verified).
- **R2.** Returns the workspace and its plan (the `subscription_plan` relationship). The plan is never `None` (FK NOT NULL, no delete action); an inactive plan (`SubscriptionPlan.is_active = False`, Boolean NOT NULL, default `True`, `app/models/subscription_plan.py`; gap 3) is returned as is.
- **R3.** `NotFoundError("Workspace not found")` (404) is unreachable after R1 (a membership's workspace always exists).
- **R4.** Read only (TC6).

---

## `WorkspaceService.update_workspace(db, workspace_id, current_user_id, workspace_update)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PATCH /workspaces/{id}/`)

**Returns:** the `Workspace`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** [BUG-2250] (D1) The caller must first pass `_require_active_membership` (403 `You are not a member of this workspace` for a missing workspace and for one they are not an active member of). *(Today: an unknown id answers 404 `Workspace not found`, another's workspace 403 — verified.)*
- **R2.** A caller who is not `workspaces.owner_user_id` → `PermissionDeniedError("Only workspace owner can update workspace")` (403), nothing changed (TX2). The owner's membership row is not needed today.
- **R3.** Only fields sent with a value are applied (base `update` R2, R3): `name`, `billing_email`, `settings`; `null` leaves the field (verified for `name`). Slug, plan, owner and counters cannot be changed here.
- **R4.** `name` 1–255 characters (schema). [BUG-1980] (HR-1) stored trimmed; blank refused by `WorkspaceUpdate` (422). *(Today: as typed; `"   "` accepted.)*
- **R5.** `settings` replaces the stored object whole (D9; verified). A `timezone` key that is present, not blank and not a valid IANA name is refused by the schema (`Invalid IANA timezone in workspace settings`); a blank or missing `timezone` passes. `billing_email` is any string (payment portal, FU-4 of the manager).
- **R5a.** [BUG-2256] Every text field the workspace schemas take is capped at its column length and an over-long value is refused by the schema (Pydantic `ValidationError`, 422 at the API), nothing written: `billing_email` ≤ 255 (`WorkspaceCreate`, `WorkspaceUpdate`), `owner_position` ≤ 255 (`WorkspaceCreate`), `position` ≤ 255 (`RoleChangeRequest`, `InviteUserRequest`, `AcceptInvitationRequest`), `new_role` ≤ 50 (already bounded by `RoleChangeRequest`'s role list). *(Today: no cap; `billing_email` of 256 characters fails at the flush with `DataError` 22001 → 500, verified; `position` of 256 the same at `update_member_role`'s commit, verified.)* *(Fix in `app/schemas/workspace.py`, `workspace_member.py`, `workspace_invitation.py`.)*
  - (gap 4, 2026-11-05, checked against the code) The request schemas of R5a: `WorkspaceCreate` (`name`, `slug`, `subscription_plan_id`, `billing_email`, `owner_position`) and `WorkspaceUpdate` (`name`, `billing_email`, `settings`) in `app.schemas.workspace`; `RoleChangeRequest` in `app.schemas.workspace_member`: `new_role: str` (required, validated against `ground-team`, `manager`, `member`, `viewer`), `position: str | None = None`; `InviteUserRequest` in `app.schemas.workspace_invitation`: `email: EmailStr`, `role: str` (both required), `position: str | None = None`; `AcceptInvitationRequest` in `app.schemas.workspace_invitation`: `token: str` (required), `position: str | None = None`.
- **R6.** [BUG-2253] (D4) When at least one field changes value, one audit row `workspace_updated` is written: this workspace, `user_id = current_user_id`, `metadata = {"fields": [<changed field names, in the order name, billing_email, settings>]}`, plus `ip_address`, `user_agent` (new optional parameters, BUG-1404). No change → no row. *(Today: never written.)*
- **R7.** Committed (TC1), re-read (TC2; `updated_at` refreshed only when a value changed, base `update` R7). Errors inside the `try` roll back and pass unchanged (TC3–TC5).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-2250] not an active member / unknown workspace | `PermissionDeniedError` 403 | `You are not a member of this workspace` |
| *(today)* unknown workspace | `NotFoundError` 404 | `Workspace not found` |
| not the owner | `PermissionDeniedError` 403 | `Only workspace owner can update workspace` |

**Side effects:** the changed columns, committed; BUG-2253's audit row.

---

## `WorkspaceService.list_members(db, workspace_id, requesting_user_id, include_inactive=False)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /workspaces/{id}/members/?include_inactive=`)

**Returns:** a `list` of `(WorkspaceMember, Profile | None)`.

**Rules:**
- **R1.** The caller must pass `_require_active_membership` (403). Any role may list.
- **R2.** All members of the workspace (workspace member DAO `get_by_workspace` R1–R3: no cap), in its order (`id` ascending, BUG-1400; D7).
- **R3.** By default only rows with `status` exactly `active`; `include_inactive=True` returns every row whatever its status.
- **R4.** Each member is paired with its profile, or `None` if the profile is gone (unreachable: FK cascade).
- **R5.** [BUG-2252] (D3) Profiles are read together. *(Today: one read per member.)*
- **R6.** Read only (TC6).

---

## `WorkspaceService.update_member_role(db, workspace_id, owner_user_id, target_user_id, new_role, position=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PATCH /workspaces/{id}/members/{user_id}/role/`, with `new_role` validated by `RoleChangeRequest`: `ground-team`, `manager`, `member`, `viewer`)

**Returns:** the `WorkspaceMember`, committed and re-read.

**Rules:**
- **R1.** [BUG-2250] (D1) As `update_workspace` R1. *(Today: unknown workspace → 404 `Workspace not found`, verified.)*
- **R2.** A caller who is not `owner_user_id` → `PermissionDeniedError("Only workspace owner can change member roles")` (403) (verified).
- **R3.** The target's row in this workspace, any status, is changed; no row (unknown user, a member of another workspace only) → `NotFoundError("Member not found")` (404). [BUG-2254] (D5) An `inactive` row → the same 404, nothing changed. *(Today: changed, verified.)*
- **R4.** A target whose stored role is `owner` → `PermissionDeniedError("Cannot change workspace owner's role")` (403) (verified), checked after R3.
- **R4a.** [BUG-2258] The owner may change the position of an `owner` target (their own row): `new_role` becomes optional (`None` = keep the role; `RoleChangeRequest.new_role: str | None = None`, still validated when given), and a request for an `owner` target with `new_role` `None` and a `position` sets that position, committed and re-read as R5, with BUG-2253's audit row when it changes. A non-`None` `new_role` for an `owner` target still gets R4's 403 `Cannot change workspace owner's role` (and `owner` as a value is BUG-2257's 400), nothing changed. For other targets `new_role=None` likewise keeps the role and applies only `position`. *(Today: any request for an `owner` target is refused with R4's 403, and `new_role` is required, so the owner's position can be set only at creation, `owner_position`.)* *(Today, direct call with `new_role=None` and a `position` on a non-owner member (gap 5, verified on `marker_test`): the service assigns `role = None`; `workspace_members.role` is `String(50)` NOT NULL, so the commit's flush fails with `IntegrityError` (pgcode 23502, not-null violation) → TC4 path: rolled back, role and position unchanged, a pending row of the session discarded, the error reaches the caller unchanged. The role is never stored as NULL.)* *(Requires the optional `new_role` in the service and `RoleChangeRequest`.)*
- **R5.** `role = new_role` as given; the service does not check it (a direct call with `owner` stores `owner`, verified; the endpoint's schema refuses it). `position` is set when not `None` (`""` stores `""`); `None` leaves it. Committed (TC1), re-read (TC2); errors inside the `try` roll back (TC3–TC5).
- **R5a.** [BUG-2257] A `new_role` of exactly `owner` → `ValidationError("The owner role cannot be assigned. Ownership transfer is not available.")` (400), nothing changed, raised before the `try` after R1–R2 and before R3 (no rollback, TX2). *(Today: stored, verified, card WSS-MR-04; the endpoint's `RoleChangeRequest` already refuses it, so only a direct call reaches it.)* With this, the membership role `owner` stays held only by the creator, so `_require_owner`'s role check and `owner_user_id` keep naming the same person (D6 stands; `_require_owner` R2 unchanged).
- **R6.** [BUG-2253] (D4) When role or position changes value, one audit row `member_role_changed`: this workspace, `user_id = owner_user_id`, `metadata = {"member_id": target_user_id, "from_role", "to_role", "from_position", "to_position"}`, with `ip_address`, `user_agent` (new optional parameters). *(Today: none.)*
- **R7.** Nothing else changes: the person's project memberships, approvals and assignments stay; nobody is notified (`docs/future/notifications.md`).

**Errors:** R1–R4.

---

## `WorkspaceService.remove_member(db, workspace_id, remover_user_id, target_user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `DELETE /workspaces/{id}/members/{user_id}/`)

**Returns:** `None`.

**Rules:**
- **R1.** The caller must pass `_require_active_membership` (403 `You are not a member of this workspace`, verified), before anything else (TX2).
- **R2.** The member is removed exactly as `WorkspaceManager.remove_member_from_workspace` does it, with `remover_role` = the caller's stored role: manager R1–R12, including BUG-1984, BUG-1990 (owner removes any non-owner; `ground-team-manager` and `manager` remove `ground-team` only; others refused), BUG-1201, BUG-1280, BUG-1883 (OQ-6). Committed (TC1).
- **R3.** Manager refusals → `PermissionDeniedError` 403 with the manager's text, nothing saved (TX1). [BUG-2251] (D2) `User is not a member of this workspace` → `NotFoundError` (404) instead; the others stay 403. *(Today: all 403, verified.)*
- **R4.** [BUG-1404] `ip_address`, `user_agent` reach the manager (as `create_workspace` R4).
- **R5.** Other exceptions unchanged; commit failure TC4.

---

## `WorkspaceService.send_invitation(db, workspace_id, inviter_user_id, email, role, position=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /workspaces/{id}/invitations/`, with `email` an `EmailStr`)

**Returns:** the `WorkspaceInvitation`, committed and re-read (the token is in it; nothing is sent, manager R14).

**Rules:**
- **R1.** The caller must pass `_require_owner` (403 otherwise), before anything else (TX2).
- **R2.** The invitation is created as `WorkspaceManager.create_invitation` creates it (manager R1–R14, including BUG-1860, BUG-1871 / OQ-2, BUG-1873 / OQ-3, BUG-1983, `max_members = 0` as today, BUG-1989 / OQ-17).
- **R3.** Manager `ValueError` → `ValidationError` 400, same text, nothing saved (TX1).
- **R4.** [BUG-1404] `ip_address`, `user_agent` reach the manager.

---

## `WorkspaceService.list_invitations(db, workspace_id, requesting_user_id, include_expired=False)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /workspaces/{id}/invitations/?include_expired=`)

**Returns:** a `list` of `(WorkspaceInvitation, Workspace, Profile | None)`.

**Rules:**
- **R1.** The caller must pass `_require_owner` (403).
- **R2.** Default: the workspace's pending, unexpired invitations (invitation DAO `get_pending_invitations` R1–R4). `include_expired=True`: **every** invitation of the workspace, accepted and cancelled included (`get_all_invitations` R1–R3), not only expired ones.
- **R3.** Each is paired with the workspace (read once) and the inviter's profile, or `None` when `invited_by_user_id` is NULL.
- **R4.** Order as the DAO (BUG-1401). No paging.
- **R5.** [BUG-2252] (D3) Inviters are read together. *(Today: one read per invitation with an inviter.)*
- **R6.** Read only (TC6).

---

## `WorkspaceService.accept_invitation(db, workspace_id, token, current_user_id, current_user_email, position=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /workspaces/{id}/invitations/accept/`, any signed-in user, with their stored email)

**Returns:** the new (or, BUG-1982, reactivated) `WorkspaceMember`, committed and re-read.

**Rules:**
- **R1.** The token is validated by `WorkspaceManager.validate_invitation_for_user` with `current_user_email` (manager R1–R6, BUG-1987); its `ValueError` → `ValidationError` 400, same text.
- **R2.** A valid invitation of another workspace than `workspace_id` → `ValidationError("Invitation does not belong to this workspace")` (400), nothing changed. Checked after R1, so an expired or used token of another workspace gets R1's message.
- **R3.** `position` not `None` replaces the invitation's position before the member is created (`""` included), so the member row gets it; `None` keeps the inviter's.
- **R4.** The member is added by `WorkspaceManager.accept_invitation` (manager R1–R6a: BUG-1872, BUG-1874, BUG-1982, BUG-1985); its `ValueError` → 400.
- **R5.** `ValidationError`, `PermissionDeniedError`, `NotFoundError` raised inside pass unchanged; every error rolls back (the position change included).
- **R6.** [BUG-1404] `ip_address`, `user_agent` reach the manager.
- **R7.** Committed (TC1), re-read (TC2).

---

## `WorkspaceService.cancel_invitation(db, workspace_id, invitation_id, canceller_user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `DELETE /workspaces/{id}/invitations/{invitation_id}/`)

**Returns:** `None`.

**Rules:**
- **R1.** The caller must pass `_require_active_membership` (403), before anything else (TX2).
- **R2.** The invitation is cancelled as `WorkspaceManager.cancel_invitation` does it, with the caller's stored role (manager R1–R6: owner only, BUG-1986 first; BUG-1981). Committed.
- **R3.** Manager refusals → 403 with the manager's text (TX1). [BUG-2251] (D2) `Invitation not found` → `NotFoundError` 404; `Cannot cancel invitation that is <status>` → `ValidationError` 400; `Only the workspace owner can cancel invitations` stays 403. *(Today: all 403; verified for not found.)*
- **R4.** [BUG-1404] `ip_address`, `user_agent` reach the manager.

---

## `WorkspaceService.get_my_invitations(db, user_email)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /workspaces/me/invitations/`, with the user's stored email)

**Returns:** a `list` of `(WorkspaceInvitation, Workspace | None, Profile | None)`.

**Rules:**
- **R1.** The pending, unexpired invitations to that email in every workspace (invitation DAO `get_user_invitations` R1–R4, BUG-1402 case-insensitive).
- **R2.** Each is paired with its workspace and its inviter's profile (`None` when `invited_by_user_id` is NULL).
- **R3.** Invitations to workspaces the user already belongs to are listed too (D8).
- **R4.** [BUG-2252] (D3) Workspaces and inviters are read together. *(Today: one or two reads per invitation.)*
- **R5.** No membership is required. Read only (TC6).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 53–58 | no row / status not `active` → 403 | `_require_active_membership` R1–R4 |
| 64–67 | role not `owner` → 403 | `_require_owner` R1, R2 |
| 77–85 | loop; skip not `active`; workspace missing → skip (per-row read, BUG-2252) | `list_user_workspaces` R1–R5 |
| 91–101 | manager; commit; refresh | `create_workspace` R1, TC1, TC2 |
| 102–104 | `ValueError` → rollback, `ValidationError` | `create_workspace` R2; TX1 |
| 105–107 | other → rollback, re-raise | `create_workspace` R3 |
| 113 | membership | `get_workspace_with_plan` R1 |
| 115–116 | workspace missing → 404 (unreachable) | `get_workspace_with_plan` R3 |
| 117–118 | plan relationship | `get_workspace_with_plan` R2 |
| 128–130 | workspace missing → 404 (BUG-2250) | `update_workspace` R1; TX2 |
| 131–132 | not `owner_user_id` → 403 | `update_workspace` R2 |
| 133–140 | update; commit; refresh; any error → rollback | `update_workspace` R3–R7 |
| 154 | membership | `list_members` R1 |
| 155–157 | all rows; `include_inactive` false → `active` only | `list_members` R2, R3 |
| 158–161 | profile per member (BUG-2252) | `list_members` R4, R5 |
| 173–175 | workspace missing → 404 (BUG-2250) | `update_member_role` R1 |
| 176–177 | not `owner_user_id` → 403 | `update_member_role` R2 |
| 178–182 | target row missing → 404 (any status, BUG-2254) | `update_member_role` R3 |
| 183–184 | target `owner` → 403 | `update_member_role` R4 |
| 185–194 | set role; position if not `None`; commit; refresh; error → rollback | `update_member_role` R5–R7 |
| 204 | membership | `remove_member` R1 |
| 205–213 | manager with caller's role; commit | `remove_member` R2 |
| 214–216 | `ValueError` → 403 (BUG-2251) | `remove_member` R3 |
| 217–219 | other → rollback, re-raise | `remove_member` R5 |
| 235 | owner | `send_invitation` R1 |
| 236–247 | manager; commit; refresh | `send_invitation` R2 |
| 248–253 | `ValueError` → 400; other re-raised | `send_invitation` R3 |
| 263 | owner | `list_invitations` R1 |
| 264–267 | `include_expired` → all / pending | `list_invitations` R2, R4 |
| 268–276 | workspace once; inviter per row if id (BUG-2252) | `list_invitations` R3, R5 |
| 289–293 | validate | `accept_invitation` R1 |
| 294–295 | other workspace → 400 | `accept_invitation` R2 |
| 297–299 | position override | `accept_invitation` R3 |
| 300–307 | accept; commit; refresh | `accept_invitation` R4, R7 |
| 308–310 | API errors pass | `accept_invitation` R5 |
| 311–316 | `ValueError` → 400; other re-raised | `accept_invitation` R1, R4, R5 |
| 326 | membership | `cancel_invitation` R1 |
| 327–335 | manager with caller's role; commit | `cancel_invitation` R2 |
| 336–341 | `ValueError` → 403 (BUG-2251); other re-raised | `cancel_invitation` R3 |
| 347–355 | invitations; workspace and inviter per row (BUG-2252) | `get_my_invitations` R1–R5 |
| 358 | singleton | Not specified |

## Gap log
G1 (`workspace_service.cases.md` gap 1) — Fact — `_require_owner` R3: returns the caller's `WorkspaceMember` (verified).
G2 (gap 2) — Test mechanics, decided by Claude under the reviewer's delegation (2026-11-04) — Notes: `billing_email` of 256 characters fails inside `update_workspace`'s `try` (`DataError` 22001, TC3); `position` of 256 characters fails at `update_member_role`'s commit (TC4 path); both roll back a pending row (verified). Testable without a patch, so not marked unit-untestable.
G3 (gap 3) — Fact — `get_workspace_with_plan` R2: the plan flag is `SubscriptionPlan.is_active` (`app/models/subscription_plan.py`, Boolean NOT NULL, default `True`).
G4 (coordinator follow-up of gap 2, 2026-11-05) — Bug — `update_workspace` R5a / 🐞 BUG-2256 (pattern `unchecked-column-length`, per BUG-972 precedent): schema caps at column length, 422; Notes say how TC3/TC4 cards stay valid after the fix. Stays APPROVED.
G5 (`workspace_service.cases.md` gap 4, 2026-11-05) — Fact — `update_workspace` R5a: modules and fields of `WorkspaceCreate` / `WorkspaceUpdate` (`app.schemas.workspace`), `RoleChangeRequest` (`app.schemas.workspace_member`), `InviteUserRequest`, `AcceptInvitationRequest` (`app.schemas.workspace_invitation`).
G6 (executor follow-up, card WSS-MR-04, 2026-11-05) — Intent, decided by Claude under the reviewer's delegation (2026-11-05) — `update_member_role` R5a / 🐞 BUG-2257: `new_role = "owner"` refused with 400. Why: no ownership transfer exists, the owner's role cannot be changed, and the endpoint schema already refuses it; the service must not create a second `owner` that would pass `_require_owner`.
G7 (`workspace_service.verify.md`, 2026-11-06) — Test mechanics, decided by Claude under the reviewer's delegation (2026-11-06) — TX1a: TC3 rollback inside the `try` before the commit is not unit-testable for `remove_member`, `cancel_invitation`, `update_member_role` (needs a patched manager, not an external); per the help_ticket fallback precedent.
G8 (`workspace_service.verify.md`, 2026-11-06) — Intent, decided by Claude under the reviewer's delegation (2026-11-06) — `update_member_role` R4a / 🐞 BUG-2258: the owner may change their own position; their role still cannot change (R4, BUG-2257). Why: a position is a job title, not a permission.
G9 (`workspace_service.cases.md` gap 5, 2026-11-06) — Fact (verified, `v3_role_none.py`) — `update_member_role` R4a Today: `new_role=None` on a non-owner member fails at commit with `IntegrityError` 23502 (role NOT NULL); nothing changes, pending rows discarded.
