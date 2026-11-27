# Spec — `app/managers/help_ticket_manager.py`

> **Status:** APPROVED (2026-11-26, describe revision for the status workflow and ticket type; apply-review 2026-11-26 for the owner's OQ-66 answer, which overrides D-1 → BUG-3251; every other question decided by Claude under the reviewer's delegation (2026-11-26); no question open.)

> **Apply-review 2026-11-26 — owner answer OQ-66 (`docs/testing/owner-questions.md`).** The owner kept OQ-8: platform admins **and** the workspace owner **and** ground-team managers may change a ticket's status, along the same transition table. Anyone else (e.g. a plain member who raised the ticket) is refused with 403. The code's admin-only rule is 🐞 **BUG-3251** (`status-change-rights-too-narrow`). D-1 is rewritten as the owner's answer. Rules changed: `update_ticket` Inputs, R4a, R5 (split: R5 untagged = who is refused today and still refused; **R5g** [BUG-3251] = owner / ground-team-manager / workspace owner may; **R5h** [BUG-3251] = refusal message), R5e, R6, Errors table, Branch map 172–175. BUG-1863's close / reopen part stays valid as written. BUG-1576 has been closed in the register by the coordinator, so FU-5 is trimmed.
> **Source commit:** 41d5ac1 (merge of origin/main: help ticket type and status workflow)

> **Revision 2026-11-26 — status workflow and ticket type (merge 41d5ac1).** Re-read the manager, `app/dao/help_ticket.py`, `app/models/help_ticket.py`, `app/models/enums.py`, `app/schemas/help_ticket.py`, `app/services/help_ticket_service.py`, both endpoints (`help_tickets.py`, `platform_help.py`), migration `124_help_ticket_status_pending_opened.py`, and the author's legacy tests `tests/test_help_tickets.py`, `tests/test_help_platform.py`. What changed in the code:
> - Status values are now `pending` · `opened` · `closed` (was `open` · `closed`). A new ticket is `pending`. Migration 124 turns stored `open` into `opened` and makes `pending` the column's server default.
> - `update_ticket` takes a new keyword `is_platform_admin=False`. **Only a platform admin may change the status** (new `HelpTicketStatusChangeForbiddenError`, 403), and only along `ALLOWED_STATUS_TRANSITIONS`: `pending → opened`, `opened → closed`, `closed → opened`. Every other move, a same-status move included, raises the new `HelpTicketInvalidTransitionError` (400).
> - New `type` (`support` · `feedback`, `HelpTicketTypeEnum`): set on create (default `support`), never changed by an update, a filter on both lists, a field of every response and platform item.
> - New caller: `HelpTicketService.update_platform_ticket` (`PATCH /platform/help/tickets/{id}`, platform admins), which finds the ticket in **any** workspace and passes `is_platform_admin=True`.
>
> Rules **rewritten:** `create_ticket` R1 (pending, type); `list_tickets` R1 (status values, type filter); `list_platform_tickets` R1 (type filter); `update_ticket` R4 (wording: who may change status), R5 → R5–R5f (who may change status, the transition table, stamping), R6 (other values now raise), R7 (same-status moves are refused; BUG-1576 superseded); `to_response` R1 (`type`, three statuses). Rules **added:** `can_access_ticket` R5 [BUG-2103] (the stored bug had not been carried into this spec; added now), `list_tickets` R2a [BUG-3250], `list_tickets` R1a and `list_platform_tickets` R1a (type), `update_ticket` R4a (text and status refused together), R11 (type never changes), `to_response` R3. Rules **removed:** old `update_ticket` R5's "anyone who reached this method may close or reopen" (owner and ground-team-manager lose close / reopen: D-1), old R6's "any other value is ignored" (it now raises: R6), old R7 [BUG-1576] (closing a closed ticket is now refused, so its intended outcome "stamps keep their values" holds today: R7). Earlier decisions kept: OQ-8 / BUG-1863 for text, BUG-1577, BUG-1578, BUG-1885, BUG-1950, BUG-1574 / BUG-1575, HR-16. The cases file (`help_ticket_manager.cases.md`, source e48a092) is stale and must be regenerated.

> **Below / above.** Callers: `tests/unit/services/help_ticket_service.spec.md` (APPROVED for e48a092; **stale**: see FU-3); `tests/unit/services/discussion_service.spec.md` (Facts "Who may open a help ticket"). Below: `tests/unit/dao/help_ticket.spec.md` (APPROVED for e48a092: numbering, lists, platform reads, **Model facts**; **stale** on status values and `type`, see FU-4) and `tests/unit/dao/base.spec.md` (`update` R1–R9). DAO rules that did not change are **cited, not restated**; what the merge changed in the DAO (pending on create, `type`, the `ticket_type` filter) is stated here as outcomes until the DAO spec is revised.
>
> **Standing decisions applied here (not asked again):** OQ-8 (owner, 2026-11-04: only the creator edits title / description / category) → BUG-1863. OQ-8's second half ("owner, ground-team-manager and platform admins may still close / reopen") is confirmed for the new workflow by OQ-66 (owner, 2026-11-26) → BUG-3251 (D-1). OQ-5 → BUG-1868, BUG-1950. BUG-1578 (platform admin's workspace list), BUG-1885 (suspended role; fix in the endpoint), BUG-2103 (the workspace owner, `workspaces.owner_user_id`, opens every ticket of their workspace). HR-16: the platform inbox and the platform PATCH are the deliberate cross-workspace exception, for platform admins only.

## Review
> All questions decided by Claude under the reviewer's delegation (2026-11-26); nothing pending. Help-ticket status is a support-desk workflow, not money, stock or order workflow.

### House-rule violations — applied automatically
- **HR-9** `update_ticket` R7 — closing an already closed ticket used to rewrite `closed_at` / `closed_by` (BUG-1576). The new workflow refuses `closed → closed` (and every same-status move) with 400 before anything is written, so the stamps keep their values: HR-9 holds today. No new ID.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1576 **superseded by the status workflow (merge 41d5ac1)**: its intended outcome (stamps unchanged) now holds. Rule `update_ticket` R7 is untagged. The bug-register row should be closed as "fixed by the status workflow"; this revision only appends rows to `docs/testing/bugs.md`, so the caller closes it.

### Precedent matches — all applied (decided upstream)
- **BUG-1577** (`update_ticket` R5b) — `closed_at` written from naive `utcnow()` into a `timestamptz` column; intended: aware UTC. Unchanged by the merge (`app/utils/time.utcnow` still strips the zone).
- **BUG-1578** (`list_tickets` R2) — platform admin's workspace list.
- **BUG-1863** (`update_ticket` R4) — only the creator edits text (owner, OQ-8). The new platform PATCH makes it reachable for every ticket of every workspace (a platform admin's text change is written today); same bug, same intended rule.
- **BUG-2103** (`can_access_ticket` R5) — the workspace owner opens every ticket of their workspace whatever their membership role (logged 2026-11-04 from the attachment manager's verification; carried into this spec now).
- **BUG-1574, BUG-1575** — schema fixes; here only `update_ticket` R9 states what the manager does with a `null` today.
- **BUG-1885** (`can_access_ticket` R4) — the fix is in the endpoint's role lookup.

### Decided — under the reviewer's delegation (2026-11-26)
### D-1. Who may change a ticket's status — 🐞 BUG-3251 (owner answer OQ-66)
**What happens today:** the code refuses any status change unless `is_platform_admin` is true (`HelpTicketStatusChangeForbiddenError`, 403 "Only platform admins may change ticket status."). Owner and ground-team-manager, who could close / reopen before, are refused too. The author's tests pin admin-only (`test_mill_user_cannot_change_status`).
**Example:** a workspace's ground-team-manager opens a member's `pending` ticket with `status: opened` and gets 403; only a platform admin can move it.
**Answer:** owner answer OQ-66 (2026-11-26): keep OQ-8. Platform admins, the workspace owner and ground-team managers may change status, along the same transition table; anyone else (e.g. a plain member who raised the ticket) is refused with 403. *(Claude's earlier decision "intended, admin-only" is withdrawn.)*
**Resolution:** 🐞 BUG-3251 (`status-change-rights-too-narrow`). Details decided by Claude under the reviewer's delegation (2026-11-26), within the owner's answer:
- "Workspace owner" counts both ways the code already knows: a caller passed with role `owner` (OQ-8's wording; BUG-1885: an active membership's role, fixed in the endpoint) **and** the workspace's `owner_user_id` (BUG-2103, so the person who may see every ticket may also move it). Ground-team managers = role `ground-team-manager`. Finance and ground-team are refused, creator or not.
- The fix's new input (gap 3, decided by Claude under the reviewer's delegation (2026-11-26)): `update_ticket` gains an optional keyword-only parameter `role: str | None = None`, the caller's active membership role, passed by `HelpTicketService.update_ticket`. Omitting it means "no role". No `can_change_status` flag. The workspace owner is read by the manager from the ticket's workspace (`owner_user_id`). The platform path keeps `is_platform_admin=True` and passes no role.
- The refusal stays `HelpTicketStatusChangeForbiddenError` (403), raised before anything is written; its message becomes `You may not change the status of this help ticket.` (the old text names platform admins only, which is no longer true).
Rules: `update_ticket` R5, R5g, R5h (R4a, R5e, R6 reworded).
- **D-2. The transition table is exactly the code's.** `pending → opened`, `opened → closed`, `closed → opened` succeed. `pending → closed`, `opened → pending`, `closed → pending` and every same-status move (`pending → pending`, `opened → opened`, `closed → closed`) are refused with 400 "Cannot transition from <current> to <target>." and nothing is written. Nothing ever returns to `pending`. A support ticket must be acknowledged before it is closed; the author's parametrized test pins `pending → closed` as refused. **Decided: intended**; the same-status refusal (instead of a silent no-op) is an explicit answer to a client that sent a stale status, and it satisfies HR-9 (D-3). Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R5a, R7.
- **D-3. BUG-1576 is superseded.** See the house-rule line above. Decided by Claude under the reviewer's delegation (2026-11-26).
- **D-4. Stamps on each move.** `opened → closed` stamps `closed_at` (now) and `closed_by` (the admin). `closed → opened` clears both. `pending → opened` leaves both as they are. Re-opening keeps no record of the earlier close (the table has no history; it never had). **Decided: intended.** Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R5b–R5d.
- **D-5. Text and status refused together.** When a caller who is neither the ticket's creator nor allowed to change status (R5 / R5g) sends a text field **and** a status, both refusals apply. Once BUG-1863 is fixed the manager may raise either one: both are `PermissionError`s, both are answered 403, and nothing is written. The spec pins that much and not which one comes first. Today the status refusal is raised, which already writes nothing. Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R4a.
- **D-6. A ticket's type is set once.** `HelpTicketUpdate` has no `type` field, so an update can never change it. A `type` sent on PATCH is dropped by the schema (Pydantic ignores unknown fields) before the manager sees it. The author's test `test_update_schema_excludes_type` pins this. **Decided: intended.** Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R11.
- **D-7. Status values that cannot come from the API.** A status value outside the enum reaches the manager only through `HelpTicketUpdate.model_construct` (the schema and both endpoints validate it): it raises a plain `ValueError` (not the transition error, so an endpoint would answer 500). A stored status outside the enum (e.g. a legacy `open` row on a database where migration 124 has not run) gives `HelpTicketInvalidTransitionError` "Cannot transition from invalid status 'open'." (400). **Decided: intended, no bug.** The first is unreachable, and the second is a migration-state guard. Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R6, R5e.
- **D-8. The workspace owner's list (BUG-3250, new).** BUG-2103 lets the workspace owner (`workspaces.owner_user_id`) open every ticket of their workspace whatever their membership role, but `list_tickets` decides by role only: an owner whose membership role is something else sees only their own tickets in the list. BUG-1578 set the precedent: the list follows the get's rule. **Decided: bug**, the list shows the workspace owner every ticket of the workspace. Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `list_tickets` R2a.
- **D-9. No row lock on status moves (HR-10).** Two admins moving the same ticket at once both pass the check. The last write wins, and at worst a close stamp is overwritten. No money, stock, approval or external side effect is involved, so HR-10 asks for no lock. Decided by Claude under the reviewer's delegation (2026-11-26).
- **D-10. A creator may still edit the text of a closed ticket.** No state check guards text fields (unchanged by the merge). **Decided: intended**: adding detail to a closed request does not reopen it, and only support moves the status. Decided by Claude under the reviewer's delegation (2026-11-26). Rules: `update_ticket` R3.

### Routed: who may attach a file to a ticket — 🐞 BUG-1950 (per OQ-5, owner)
Unchanged by the merge. `AttachmentManager` finds a `support_ticket` parent with `help_ticket_dao.get_by_id_and_workspace` only and never calls `can_access_ticket`. A ticket's attachments follow its visibility (BUG-1950, BUG-2103 through the attachment manager's PR-2). Whether *adding* needs the see-right or the edit-right is noted in `docs/future/permissions.md`. No rule of this module changes.

Checked and **not** violated: **HR-1**: BUG-1574 (schema). **HR-2, HR-3**: no unique names. `type` is an enum, not free text. **HR-4**: no soft delete. **HR-5, HR-6, HR-8**: the DAO's (BUG-1442, BUG-1443). The new `type` filter is in SQL before paging. **HR-7**: both endpoints require `1 <= limit <= 200`. **HR-9**: holds (BUG-1576 superseded). **HR-10**: D-9. **HR-11 … HR-15**: none applies. **HR-16**: the workspace methods find the ticket in the caller's workspace first. The platform methods (and `update_platform_ticket`'s DAO `get_by_id`) are unscoped by design, platform admins only.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment service / manager** | 🐞 BUG-1950 / BUG-2103 as before (no change from this revision). | earlier revision |
| FU-2 | **Help ticket service spec** (FU-1 there) | Answered by this spec; `can_view_all_tickets` / `can_access_ticket` are not used by `AttachmentManager`. | earlier revision |
| FU-3 | **Help ticket service spec** (`tests/unit/services/help_ticket_service.spec.md`, source e48a092) | Needs a describe revision. Its `update_ticket` rules still say anyone who may see a ticket closes / reopens it, and its rules still use status `open`. It has no `type` filter and no `update_platform_ticket` (new: finds the ticket in any workspace by DAO `get_by_id`, 404 "Help ticket not found." when missing, passes `is_platform_admin=True`, commits, re-reads). The workspace `update_ticket` now passes `is_platform_admin = getattr(user, "is_platform_admin", False)`. Endpoints map `HelpTicketStatusChangeForbiddenError` → 403 and `HelpTicketInvalidTransitionError` → 400. | this revision |
| FU-4 | **Help ticket DAO spec** (`tests/unit/dao/help_ticket.spec.md`, source e48a092) | Needs a describe revision. `create_with_user` now writes `status = "pending"` and `type` (the payload's value; `"support"` when the dumped payload has no `type`). `list_by_workspace` and `list_platform` take `ticket_type` (exact match; `None` = no filter). Model: `status` default `"pending"`, new `type` String(16) NOT NULL default `"support"` (server default `support`, migration 123), indexed. | this revision |
| FU-5 | **Bug register** (`docs/testing/bugs.md`) | BUG-1576 closed by the coordinator (2026-11-26). BUG-1863's Intended column stays valid as written (OQ-66). Nothing left to do. | this revision |
| FU-6 | **Help ticket service spec and endpoints** | 🐞 BUG-3251: the service must hand the manager the caller's status right (role `owner` / `ground-team-manager` from an **active** membership, BUG-1885; the workspace's `owner_user_id`, BUG-2103; platform admin). The legacy test `test_mill_user_cannot_change_status` stays right for a plain member; tests that assume admin-only for owner / manager must change with the fix. | apply-review OQ-66 |

## Overview
`HelpTicketManager` decides who may see a help ticket (a workspace member's request to the platform support team, either a `support` request or `feedback`). It applies ticket changes, and runs the ticket's status workflow, driven by platform admins, the workspace owner and ground-team managers (OQ-66; today platform admins only, BUG-3251): `pending` → `opened` → `closed`, with `closed` → `opened` to reopen. It also shapes the platform support inbox rows. `HelpTicketService` is its only caller, through `update_ticket` (workspace PATCH) and `update_platform_ticket` (platform PATCH), and the service owns the transaction. The manager never commits or rolls back, so a refusal must come before anything is written to the session. Refusals are its own plain exceptions: `HelpTicketNotFoundError` (`LookupError`) → 404, `HelpTicketForbiddenError` (`PermissionError`) → 403, `HelpTicketStatusChangeForbiddenError` (`PermissionError`) → 403, `HelpTicketInvalidTransitionError` (`ValueError`) → 400. It sends no notifications.

**Callables:** 10 specified · 8 not specified
**Externals to mock:** `utcnow` as imported in `app.managers.help_ticket_manager` (`closed_at`); `datetime` in `app.dao.help_ticket` only for the ticket number's year (DAO spec Notes).
**Integration-only behavior:** the endpoints' role lookup (`_workspace_role`, BUG-1885), the 404 / 403 / 400 translation, `get_platform_admin` on the platform endpoints, the service passing `is_platform_admin`.

**Facts for the test designer**
- Import: `from app.managers.help_ticket_manager import HelpTicketManager, help_ticket_manager, HelpTicketNotFoundError, HelpTicketForbiddenError, HelpTicketStatusChangeForbiddenError, HelpTicketInvalidTransitionError, TICKET_VIEW_ALL_ROLES, ALLOWED_STATUS_TRANSITIONS`. Enums: `from app.models.enums import HelpTicketStatusEnum, HelpTicketTypeEnum, RoleEnum`. Every parameter after `session` is keyword-only, and so are the static methods' parameters (`can_access_ticket(*, ticket, user, role)`). `can_view_all_tickets(role)` is positional.
- `HelpTicketStatusEnum`: `PENDING = "pending"`, `OPENED = "opened"`, `CLOSED = "closed"` (a `str` enum; `"open"` is **not** a value: `HelpTicketStatusEnum("open")` raises `ValueError`). `HelpTicketTypeEnum`: `SUPPORT = "support"`, `FEEDBACK = "feedback"`.
- `ALLOWED_STATUS_TRANSITIONS == {PENDING: {OPENED}, OPENED: {CLOSED}, CLOSED: {OPENED}}`.
- `TICKET_VIEW_ALL_ROLES == {"owner", "ground-team-manager"}` (plain strings; `RoleEnum.OWNER` also matches).
- Messages: not found `Help ticket not found.`; forbidden `You do not have access to this help ticket.`; status change refused `Only platform admins may change ticket status.` today (intended `You may not change the status of this help ticket.`, BUG-3251); refused move `Cannot transition from <current> to <target>.` with the two values, e.g. `Cannot transition from pending to closed.`; bad stored status `Cannot transition from invalid status '<stored>'.`, e.g. `Cannot transition from invalid status 'open'.`
- `Profile.is_platform_admin` (Boolean, default `False`); `Profile.name` NOT NULL. `HelpTicket.created_by` nullable (`ON DELETE SET NULL`). `HelpTicket.status` String(16) NOT NULL, Python default `"pending"` (server default `pending` after migration 124), **no CHECK constraint**: any string up to 16 characters can be stored directly. `HelpTicket.type` String(16) NOT NULL, default `"support"`, no CHECK constraint. `HelpTicket.workspace` → `Workspace`; `Workspace.owner_user_id` nullable (`ON DELETE SET NULL`). Other columns: help ticket DAO spec **Model facts**.
- `HelpTicketCreate`: `title` (1–200), `description` (≥1), `category` (≤80, optional), `type` (`HelpTicketTypeEnum`, default `SUPPORT`).
- `HelpTicketUpdate`: `title` (1–200), `description` (≥1), `category` (≤80), `status` (`HelpTicketStatusEnum`), all optional and `None` by default; **no `type` field**. The manager reads only the fields **sent** (`exclude_unset`).
- `HelpTicketResponse` fields: `id`, `workspace_id`, `ticket_number`, `title`, `description`, `category`, `status` (`HelpTicketStatusEnum`), `type` (`HelpTicketTypeEnum`), `created_by`, `creator_name` (default `None`), `created_at`, `updated_at`, `closed_at`, `closed_by`. `PlatformHelpTicketListItem` = those plus `workspace_name`.

**Notes for the test designer**
- Build tickets with `help_ticket_dao.create_with_user` or directly (`HelpTicket(workspace_id, ticket_number, title, description, created_by)`, flush): a direct row is `pending` / `support` unless the card sets `status` / `type`. For an `opened` or `closed` ticket set `status` directly (and `closed_at` / `closed_by` for a closed one). Use `user` objects from `make_profile`; a platform admin is `make_profile(is_platform_admin=True)`. For BUG-2103 / BUG-3250 set the workspace's `owner_user_id` to the profile.
- `update_ticket`'s `is_platform_admin` is an argument trusted as passed (the service derives it). A card that changes status as an admin passes `is_platform_admin=True`; leaving it out means `False`. BUG-3251 cards (R5g, R5h) pass the fix's keyword `role=` (role cards) or set the ticket's workspace's `owner_user_id` to the caller (workspace-owner cards, which need no `role`), as strict xfail; a call with `role=` raising `TypeError` today counts as the expected failure. Every today-passing `update_ticket` card omits `role` (default `None`), so it keeps working after the fix.
- Refusal message today `Only platform admins may change ticket status.` (R5 cards assert the type only; R5h asserts the new message, strict xfail).
- **BUG-1863 cases:** assert the exception, then check that the ticket's attributes are unchanged **in the session without a rollback** (`title`, `status`, `closed_at`, `closed_by` as before; `db.is_modified(ticket)` is `False`). That proves the refusal came before any write. → strict xfail. Cards that send text **and** status from a non-creator who is not an admin (R4a) pass today: assert `PermissionError` only.
- Every status refusal (R5, R5a, R5e, R6) is checked the same way: exception, then nothing changed in the session and nothing flushed.
- **BUG-1577:** as the service spec's Notes (`SET LOCAL TIME ZONE 'America/New_York'`); patch `app.managers.help_ticket_manager.utcnow` for exact `closed_at` values elsewhere.
- **BUG-1578:** `list_tickets` with a platform admin and `role=None` → strict xfail.
- Legacy stored status (R5e): insert a row with `status="open"` directly (no CHECK constraint). `to_response` on such a row raises `ValidationError` (R3).

## Not specified
- `HelpTicketNotFoundError`, `HelpTicketForbiddenError`, `HelpTicketStatusChangeForbiddenError`, `HelpTicketInvalidTransitionError` — exception classes, no logic (bases and messages are facts above).
- `HelpTicketManager.__init__` — implicit, no state.
- `help_ticket_manager` — module-level singleton, no logic.
- `TICKET_VIEW_ALL_ROLES`, `ALLOWED_STATUS_TRANSITIONS` — constants (facts above).

---

## `HelpTicketManager.can_view_all_tickets(role)` (static)
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `can_access_ticket`, `list_tickets`)

**Purpose:** Whether a workspace role sees every ticket of the workspace.

**Rules:**
- **R1.** `True` for `"owner"` and `"ground-team-manager"` exactly; `False` for `"finance"`, `"ground-team"`, `None`, `""`, and any other spelling (`"Owner"`, `" owner"`, `"manager"`).

**Errors:** none. **Side effects:** none

---

## `HelpTicketManager.can_access_ticket(*, ticket, user, role)` (static)
**Shape:** compute
**Persistence:** pure today (reads only `ticket.created_by`, `user.id`, `user.is_platform_admin`; no query). The BUG-2103 fix reads the ticket's workspace's `owner_user_id`.
**Visibility:** public (used by: `get_by_id_and_workspace`; named as "the help ticket rule" by the discussion service spec, BUG-1868, BUG-1950, BUG-2103)

**Purpose:** Whether this user may open this ticket. (Opening is not changing: who may change text is `update_ticket` R3–R4, who may change status is `update_ticket` R5.)

**Rules:**
- **R1.** A platform admin (`user.is_platform_admin` true) may, whatever `role` and whoever created the ticket. A user object without that attribute counts as not an admin.
- **R2.** Otherwise a `role` for which `can_view_all_tickets` is true may.
- **R3.** Otherwise only the ticket's creator (`ticket.created_by == user.id`) may. A ticket whose creator is gone (`created_by` `None`) is open to R1, R2 and R5 only.
- **R3a.** (gap 1) A `user` whose `id` is `None` cannot reach this method: every caller passes the authenticated, persisted profile. If it did, the comparison would be `None == None`, so a creatorless ticket would be opened to it (`True`). Unreachable; not specified for testing (no card).
- **R4.** `role` is trusted as passed. BUG-1885's fix (only an `active` membership's role counts) is in the endpoint's role lookup, so this rule stays as written. Apart from R5, the ticket's workspace is not looked at here (callers find the ticket in the workspace first).
- **R5.** [BUG-2103] The workspace owner (`user.id` equals the ticket's workspace's `owner_user_id`) may, whatever `role` (including `None`, a plain role, or a role passed from a non-active membership). A workspace whose `owner_user_id` is `None` grants nobody through this rule. *(Today: refused unless R1–R3 let them in; `owner_user_id` is never read. Requires reading `ticket.workspace.owner_user_id`.)*
- **R6.** Status and type play no part: a ticket in any status (`pending`, `opened`, `closed`) and of either type is opened under R1–R5 alike.

**Errors:** none. **Side effects:** none

---

## `HelpTicketManager.get_by_id_and_workspace(session, *, ticket_id, workspace_id, user, role)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.get_ticket`, `update_ticket`)

**Purpose:** One ticket of the workspace, if the caller may open it.

**Returns:** the `HelpTicket`, with `creator` loaded (DAO override R2).

**Rules:**
- **R1.** The ticket is found as DAO `get_by_id_and_workspace` R1 (by id, in that workspace). An unknown id, `0`, or another workspace's ticket → `HelpTicketNotFoundError("Help ticket not found.")`. This check comes before the access check, so another workspace's ticket and a missing one get the same answer.
- **R2.** A found ticket that `can_access_ticket` refuses → `HelpTicketForbiddenError("You do not have access to this help ticket.")` (so BUG-2103 reaches this method through `can_access_ticket` R5).
- **R3.** Otherwise the ticket is returned unchanged.

**Errors:**
| Condition | Raises | Message |
|---|---|---|
| not in the workspace | `HelpTicketNotFoundError` | `Help ticket not found.` |
| may not open it | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |

**Side effects:** none

---

## `HelpTicketManager.list_tickets(session, *, workspace_id, user, role, status=None, ticket_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.list_tickets` ← `GET /help/tickets?status=&type=`)

**Purpose:** The workspace's tickets the caller may see.

**Returns:** a `list` of `HelpTicket` (creator loaded).

**Rules:**
- **R1.** With a `role` for which `can_view_all_tickets` is true, every ticket of the workspace; otherwise only tickets with `created_by == user.id`. The rows, order (BUG-1442) and paging are DAO `list_by_workspace` R1–R6. `status` (a `HelpTicketStatusEnum`) keeps only tickets whose stored status is its value (`"pending"`, `"opened"` or `"closed"`); `None` means no status filter. `skip` / `limit` pass through (defaults 0 / 100).
- **R1a.** `ticket_type` (a `HelpTicketTypeEnum`) keeps only tickets whose stored `type` is its value (`"support"` or `"feedback"`), in SQL before paging; `None` means no type filter. It combines with `status` and with the own-tickets filter (all must hold).
- **R2.** [BUG-1578] A platform admin (`user.is_platform_admin`) sees every ticket of the workspace, whatever `role`, the same rule as `can_access_ticket` R1. *(Today: only their own tickets; `[]` for an admin with no membership.)*
- **R2a.** [BUG-3250] (D-8) The workspace owner (`user.id` equals the workspace's `owner_user_id`) sees every ticket of the workspace, whatever `role`, the same rule as `can_access_ticket` R5 (BUG-2103). *(Today: an owner whose `role` is not `owner` / `ground-team-manager` sees only tickets they created. Requires reading the workspace's `owner_user_id`.)* Filters (R1, R1a) still apply.

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit` (DAO R4).

**Side effects:** none

---

## `HelpTicketManager.list_platform_tickets(session, *, status=None, ticket_type=None, search=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.list_platform_tickets` ← `GET /platform/help/tickets?status=&type=&search=`, platform admins only)

**Returns:** a `list` of `PlatformHelpTicketListItem`, one per DAO row, in the DAO's order.

**Rules:**
- **R1.** Rows, search, order and paging are DAO `list_platform` R1–R6 (BUG-1442, BUG-1443). `status` keeps only tickets with that stored value (`None` = no filter), and `search` and paging pass through unchanged.
- **R1a.** `ticket_type` keeps only tickets of that type (`"support"` / `"feedback"`), in SQL before paging, together with `status` and `search`; `None` means no type filter.
- **R2.** Each row becomes an item as `_to_platform_item` (so each item carries `type` and `status`). An empty result gives `[]`.
- **R3.** No access check here: who may call it is the endpoint's (`get_platform_admin`).

**Errors:** `DataError` for a negative `skip` / `limit`. **Side effects:** none

---

## `HelpTicketManager.get_platform_ticket(session, *, ticket_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.get_platform_ticket`)

**Rules:**
- **R1.** A ticket of any workspace (DAO `get_platform_by_id` R1) → its item as `_to_platform_item`.
- **R2.** Unknown id or `0` → `HelpTicketNotFoundError("Help ticket not found.")`.

**Errors:** R2. **Side effects:** none

---

## `HelpTicketManager.create_ticket(session, *, workspace_id, user_id, payload)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `HelpTicketService.create_ticket`)

**Rules:**
- **R1.** One ticket is created and flushed (not committed): numbered as DAO `create_with_user` R1–R3 (BUG-1440, BUG-1441), `workspace_id` as given, `created_by = user_id`, `title` / `description` / `category` as the payload gives them, `closed_at` / `closed_by` `None`. The new row is returned. The manager adds no check of its own: any role may open a ticket, and the payload is stored as the schema gives it (trimming is BUG-1574, in the schema).
- **R1a.** The new ticket's `status` is always `"pending"`. The payload has no status to set.
- **R1b.** The new ticket's `type` is the payload's `type` value: `"feedback"` for `HelpTicketTypeEnum.FEEDBACK`, `"support"` for `SUPPORT`, and `"support"` when the caller did not send `type` (schema default). A payload whose dump has no `type` key at all (only via `model_construct` without it) also gets `"support"`.

**Errors:** as DAO `create_with_user` R4, R5 (`IntegrityError`). **Side effects:** one `help_tickets` row, flushed.

---

## `HelpTicketManager.update_ticket(session, *, ticket, payload, user_id, is_platform_admin=False)`
**Shape:** update / state-transition
**Persistence:** writes
**Visibility:** public (used by: `HelpTicketService.update_ticket` after `get_by_id_and_workspace`, with `is_platform_admin` = the caller's flag; `HelpTicketService.update_platform_ticket` for a ticket of any workspace, with `is_platform_admin=True`)

**Purpose:** Change a ticket's text, or move it along the status workflow.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `ticket` | `HelpTicket` | already found (and, on the workspace path, access-checked) by the caller; not re-checked |
| `payload` | `HelpTicketUpdate` | only fields **sent** count (`exclude_unset`); no `type` field |
| `user_id` | int | the caller; compared with `created_by` (BUG-1863) and becomes `closed_by` |
| `is_platform_admin` | bool, default `False` | trusted as passed; today the only grant for a status change (BUG-3251: role `owner` / `ground-team-manager` and the workspace owner too) |
| `role` | `str \| None`, keyword-only, default `None` — **[BUG-3251] new parameter, not in the code yet** (gap 3) | the caller's active membership role, trusted as passed (BUG-1885 is the endpoint's); `"owner"` / `"ground-team-manager"` grant the status right (R5g); omitted or `None` = no role. The platform path passes none. Grants nothing else: text edits stay creator-only (R4) |

**Returns:** the same ticket instance, flushed (DAO `update`), not committed.

**Rules:**
- **R1.** Only fields sent are applied; `{}` changes nothing (no field, no stamp), is no refusal for anyone, and returns the ticket.
- **R2.** `title`, `description`, `category` sent with a value are written as sent. `category: null` clears the category.
- **R3.** The ticket's creator (`user_id == ticket.created_by`) may change `title`, `description` and `category`, whatever their role and whether or not they are a platform admin, in any status (a closed ticket's text too; D-10). Text changes never move the status or the stamps.
- **R4.** [BUG-1863] (OQ-8, owner) When `title`, `description` or `category` is sent (even with the ticket's current value, even `null`) and `user_id` is not the ticket's `created_by` (or `created_by` is `None`), the call raises `HelpTicketForbiddenError("You do not have access to this help ticket.")` **before anything is written**: no attribute of the ticket changes in the session and nothing is flushed. A `status` in the same payload is not applied either. This holds whatever `is_platform_admin` is: a platform admin who is not the creator may not change the text, on the workspace path or the platform path. *(Today: the text is written, flushed and returned, for a platform admin through `PATCH /platform/help/tickets/{id}` on any workspace's ticket too.)* A status change alone is governed by R5, not by this rule.
- **R4a.** (D-5) A caller who is neither the creator nor allowed to change status (R5, R5g) and sends a text field **and** `status` is refused with a `PermissionError` (`HelpTicketForbiddenError` or `HelpTicketStatusChangeForbiddenError`; both are 403), and nothing is written. Holds today, via the status refusal. A caller allowed to change status but not the creator (e.g. a ground-team-manager, once BUG-3251 is fixed) who sends text **and** status gets R4's `HelpTicketForbiddenError`, nothing written, the status not applied.
- **R5.** (D-1, OQ-66) A `status` sent with a value by a caller with no status right — not a platform admin, and (once BUG-3251 is fixed) not role `owner` / `ground-team-manager` and not the workspace's `owner_user_id` — raises `HelpTicketStatusChangeForbiddenError` before anything is written: nothing changes in the session, nothing is flushed, and text fields in the same payload are not applied either (even the creator's). This happens whatever the requested or current status, and before the value is checked (R6), so it also covers a same-status request. A plain member (`ground-team`, `finance`, no role) is refused even on their own ticket. Holds today (today everyone but a platform admin is refused; the message is R5h).
- **R5g.** [BUG-3251] (OQ-66, owner) A caller with role `owner` or `ground-team-manager`, or who is the ticket's workspace's owner (`owner_user_id`, whatever their role; BUG-2103), may change the status exactly as a platform admin: the transition table (R5a), the stamps (R5b–R5d, `closed_by` = that caller), R5e and R6 apply unchanged. The role is the new keyword-only `role: str | None = None` (Inputs; gap 3); the workspace owner is `ticket.workspace.owner_user_id == user_id`, needing no role. With `role` omitted or `None` (or any other role) and no admin flag, only the workspace-owner grant can apply; a workspace whose `owner_user_id` is `None` grants nobody. *(Today: refused with `HelpTicketStatusChangeForbiddenError`; `update_ticket` takes no `role`, so passing it raises `TypeError`. Requires the new parameter, passed by `HelpTicketService.update_ticket` from an active membership, BUG-1885, in the endpoint.)*
- **R5h.** [BUG-3251] (decided by Claude under the reviewer's delegation (2026-11-26)) R5's refusal message is `You may not change the status of this help ticket.` *(Today: `Only platform admins may change ticket status.`, no longer true under OQ-66.)*
- **R5a.** (D-2) For a caller allowed to change status (today: `is_platform_admin` true; R5g), the move from the ticket's current status to the requested one must be in the table: `pending → opened`, `opened → closed`, `closed → opened`. Every other pair (`pending → closed`, `opened → pending`, `closed → pending`, `pending → pending`, `opened → opened`, `closed → closed`) raises `HelpTicketInvalidTransitionError("Cannot transition from <current> to <target>.")`, e.g. `Cannot transition from pending to closed.`, before anything is written: nothing changes in the session, nothing is flushed, and text fields in the same payload (even the creator's) are not applied.
- **R5b.** `opened → closed` sets `status = "closed"`, `closed_by = user_id`, `closed_at = utcnow()`. [BUG-1577] `closed_at` is the true moment as aware UTC, whatever the database session's time zone. *(Today: naive `utcnow()` read in the session's time zone; 5 h off under `America/New_York`.)* (Only the time-zone part is the bug; status, `closed_by` and the instant under a UTC session hold today.)
- **R5c.** `closed → opened` (re-opening) sets `status = "opened"`, `closed_at = None`, `closed_by = None`. The earlier close leaves no trace (D-4).
- **R5d.** `pending → opened` sets `status = "opened"` and leaves `closed_at` and `closed_by` exactly as they were (on a normal pending ticket both are `None`. A pending row with stamps set directly keeps them).
- **R5e.** (D-7) A ticket whose stored status is not one of the three values (e.g. a legacy `"open"`, or `""`) cannot be moved: for a caller allowed to change status and a valid requested status, `HelpTicketInvalidTransitionError("Cannot transition from invalid status '<stored>'.")` is raised, nothing written. For a caller without the right, R5 is raised first.
- **R5f.** The requested status may be the enum or its plain string value (`"opened"` as a `str`, only through `model_construct`); both behave the same. The move is checked against the ticket's status **as held in the session** when called.
- **R6.** `status: null`, or `status` not sent, leaves `status`, `closed_at`, `closed_by` untouched and is no refusal (no admin check). A `status` value outside the enum cannot pass `HelpTicketUpdate`. Built around the schema (`model_construct`), such a value (e.g. `"open"`, `"Closed"`, `"bogus"`) raises a plain `ValueError` (not `HelpTicketInvalidTransitionError`) for a caller allowed to change status, nothing written. For a caller without the right, R5 is raised first.
- **R7.** (HR-9; BUG-1576 superseded, D-3) Asking for the status the ticket already has never rewrites the stamps: `closed → closed` is refused by R5a and `closed_at` / `closed_by` keep their values; `opened → opened` and `pending → pending` are refused the same way.
- **R8.** (removed — the old `closed_at` rule moved into R5b, unchanged: BUG-1577.)
- **R9.** `title: null` or `description: null` (BUG-1575: refused by the schema once fixed; service spec R4a) today reach the NOT NULL columns: the flush raises `IntegrityError` (not-null). The manager does not roll back; the session must be rolled back by its caller.
- **R10.** `updated_at` is the database's `now()` on any UPDATE (Model facts); the manager writes no `updated_by` (the table has none).
- **R11.** (D-6) `type` never changes on an update: a successful update (text, status, or both) leaves the ticket's `type` as it was.

**Errors:**
| Condition | Raises | Message |
|---|---|---|
| text field sent by someone other than the creator (R4, BUG-1863) | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| status sent by a caller with no status right (R5; BUG-3251 widens the right, R5g) | `HelpTicketStatusChangeForbiddenError` | today `Only platform admins may change ticket status.`; intended `You may not change the status of this help ticket.` (R5h, BUG-3251) |
| move not in the table (R5a, R7) | `HelpTicketInvalidTransitionError` | `Cannot transition from <current> to <target>.` |
| stored status not a valid value (R5e) | `HelpTicketInvalidTransitionError` | `Cannot transition from invalid status '<stored>'.` |
| requested status not an enum value, schema bypassed (R6) | `ValueError` | Python's enum message |
| (today) `null` title / description (R9) | `sqlalchemy.exc.IntegrityError` | — |

**Side effects:** the changed columns of the row, flushed; nothing on any refusal.

---

## `HelpTicketManager.to_response(ticket)` (static)
**Shape:** mapper
**Persistence:** pure (reads `ticket.creator`, which may lazy-load it)
**Visibility:** public (used by: `HelpTicketService` for every answer, `_to_platform_item`)

**Rules:**
- **R1.** Returns a `HelpTicketResponse` with every field from the row (`id`, `workspace_id`, `ticket_number`, `title`, `description`, `category`, `status`, `type`, `created_by`, `created_at`, `updated_at`, `closed_at`, `closed_by`). `status` is a `HelpTicketStatusEnum` (`pending` / `opened` / `closed`), `type` a `HelpTicketTypeEnum` (`support` / `feedback`).
- **R2.** `creator_name` is the creator's `name` when the ticket has a creator; `None` when `creator` is `None`.
- **R2a.** (gap 2) An object with no `creator` attribute at all is treated like `creator` `None`: `creator_name` is `None`, no error. A creator whose `name` is `""` gives `creator_name == ""` (the creator object is present, and `""` is not `None`, so it is copied).
- **R3.** A row whose stored `status` or `type` is not an enum value (e.g. a legacy `"open"`) is not a valid response: `pydantic.ValidationError`.

**Errors:** `pydantic.ValidationError` if the row is not a valid response (an unflushed row without `created_at`, or R3). **Side effects:** none

---

## `HelpTicketManager._to_platform_item(ticket, workspace_name, creator_name)` (static)
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `list_platform_tickets`, `get_platform_ticket`)

**Rules:**
- **R1.** Returns a `PlatformHelpTicketListItem`: every field of `to_response(ticket)` (`type` and `status` included), plus `workspace_name` as given.
- **R2.** `creator_name` is the given `creator_name` when it is truthy; otherwise (`None` or `""`) the one from `to_response` (the loaded creator's name, or `None`).

**Errors:** as `to_response`. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–19 | the two roles | Facts; `can_view_all_tickets` R1 |
| 38–42 | transition table | Facts; `update_ticket` R5a |
| 49–50 | `role in TICKET_VIEW_ALL_ROLES` | `can_view_all_tickets` R1 |
| 59–60 | `getattr(user, "is_platform_admin", False)` | `can_access_ticket` R1 |
| 61–62 | role sees all | `can_access_ticket` R2 |
| 63 | `created_by == user.id` (no workspace-owner case, BUG-2103) | `can_access_ticket` R3, R4, R5, R6 |
| 74–78 | DAO lookup; `None` → not found | `get_by_id_and_workspace` R1 |
| 79–81 | access refused → forbidden; else return | `get_by_id_and_workspace` R2, R3 |
| 95 | `status is not None` → `.value` | `list_tickets` R1 |
| 96 | `ticket_type is not None` → `.value` | `list_tickets` R1a |
| 97–99 | not view-all → `created_by` filter (no admin case, BUG-1578; no workspace-owner case, BUG-3250) | `list_tickets` R1, R2, R2a |
| 100–108 | DAO `list_by_workspace` (status / type / creator filters, DAO 103–108) | `list_tickets` R1, R1a |
| 120–121 | `status`, `ticket_type` → value or `None` | `list_platform_tickets` R1, R1a |
| 122–130 | DAO `list_platform` (type filter DAO 135–136); map rows | `list_platform_tickets` R1–R3 |
| 138–142 | `row is None` → not found; else map | `get_platform_ticket` R1, R2 |
| 152–157 | DAO `create_with_user`: `type` popped (default `"support"`), enum → value (DAO 44–47); `status` `"pending"` (DAO 53) | `create_ticket` R1, R1a, R1b |
| 168–169 | `exclude_unset`; pop `status` (no creator check, BUG-1863) | `update_ticket` R1–R4, R11 |
| 171 | `new_status is not None` | `update_ticket` R5, R6 |
| 172–175 | not platform admin → status-change forbidden (no owner / manager / workspace-owner grant, BUG-3251) | `update_ticket` R4a, R5, R5e, R5g, R5h, R6 |
| 176–180 | enum kept; a string → `HelpTicketStatusEnum(...)` (bad value → `ValueError`) | `update_ticket` R5f, R6 |
| 181–186 | stored status not an enum value → invalid transition | `update_ticket` R5e |
| 187 | `.get(current, set())` (default unreachable: every enum value is a key) | `update_ticket` R5a |
| 188–191 | target not allowed → invalid transition | `update_ticket` R5a, R7 |
| 192 | write target status | `update_ticket` R5b–R5d |
| 193–195 | target `closed` → stamp (naive, BUG-1577) | `update_ticket` R5b |
| 196–201 | target `opened` and current `closed` → clear; current `pending` → no stamp change | `update_ticket` R5c, R5d |
| 203 | DAO `update` with a dict (writes `None` too) | `update_ticket` R2, R9, R10, R11 |
| 207 | `getattr(ticket, "creator", None)` truthy → name | `to_response` R2 |
| 208–211 | validate (bad status / type → `ValidationError`); `creator_name is not None` → copy | `to_response` R1, R2, R3 |
| 219–226 | base response; `creator_name or base.creator_name` | `_to_platform_item` R1, R2 |
| 229 | singleton | Not specified |

## Gap log
G1 (help_ticket_manager.cases.md gap 1) — Fact — `can_access_ticket` R3a: `user.id None` is unreachable (callers pass a persisted profile); today it would match a creatorless ticket (`None == None` → `True`); no card.
G2 (help_ticket_manager.cases.md gap 2) — Fact — `to_response` R2a: an object without `creator` → `creator_name None`; a creator named `""` → `creator_name ""`.
G3 (help_ticket_manager.cases.md gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-26) — BUG-3251's new input is an optional keyword-only `role: str | None = None` on `update_ticket` (omitted = no role; no `can_change_status` flag). Recorded in D-1's resolution, the `update_ticket` Inputs table, R5g and the Notes; the BUG-3251 Intended cell in `docs/testing/bugs.md` updated.
