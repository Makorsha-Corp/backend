# Spec — `app/services/help_ticket_service.py`

> **Status:** APPROVED — Q1 answered by the owner (2026-11-04) (OQ-8): BUG-1863. Nothing else is open.
> **Source commit:** e48a092
> **Revision 2026-11-04 (verification gap, `help_ticket_service.verify.md` finding 2 / cases gap 2):** the fallback "if the re-read finds nothing, the refreshed row is used" (`create_ticket` R3, `update_ticket` R7; source lines 48, 119) is marked **not unit-testable**: it is reached only by patching the DAO's `get_by_id`, and the DAO is not an external. On every reachable path the re-read returns the same identity-mapped instance as the refreshed row, so the mutants `refreshed or ticket` → `refreshed and ticket` (L48, L119) are **equivalent for unit purposes**. Decided by Claude under the reviewer's delegation (2026-11-04). No other rule changed; stays APPROVED.

> **Form.** As `tests/unit/services/department_service.spec.md`: the **Transaction contract TC1–TC6 is defined there** and cited here. Below the service: `app/managers/help_ticket_manager.py` (**no spec yet**: its outcomes reached through this service are written here as rules, FU-1) and `tests/unit/dao/help_ticket.spec.md` (APPROVED).

> **Routed here and written as rules:** help ticket DAO FU-1 (a) HR-1 (BUG-1574); (b) closing an already closed ticket rewrites `closed_at` / `closed_by` (BUG-1576); (c) the platform endpoints are guarded by `get_platform_admin` (checked: R of `list_platform_tickets`, `get_platform_ticket`).
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** P1 (BUG-1575), P2 (BUG-1577), Q2 (BUG-1578). House-rule lines: BUG-1574, BUG-1576. None is the owner's answer. Q2 is about what a platform admin sees, but it gives nobody access to anything they cannot already open (see Q2), so it is not parked. **Answered by the owner (2026-11-04):** Q1 (OQ-8) → BUG-1863.
>
> **Standing decisions applied here (not asked again):** HR-16 (no response shows another workspace's rows; the platform inbox is the deliberate exception, for platform admins only). A missing `ORDER BY` tie-break is a bug (DAO: BUG-1442).
>
> **Verified by running** (`h.py`, `v4_help.py`, `v5_wait.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test` (session time zone `America/New_York`), session as the `db` fixture; HTTP through `TestClient`; nothing persisted): create returns a `HelpTicketResponse` with `HELP-<year>-001`, `creator_name`, `status open`, `updated_at` set, and survives a later rollback; a title `"  Printer  "` is stored as typed and `"   "` title and description are accepted; lists: a `ground-team` and a `finance` member see their own tickets, `owner` and `ground-team-manager` see all, a platform admin with no role sees **none but their own**, yet opens another member's ticket by id; a member opening or updating another's ticket gets `HelpTicketForbiddenError` (HTTP 403); an unknown id or another workspace's ticket gets `HelpTicketNotFoundError`; a `ground-team-manager` **changes the title and description of a member's ticket**; closing sets `closed_by` and `closed_at`; closing it again **rewrites both** (`closed_by` moved to the second user); reopening clears them; `{}` changes nothing; `{"title": null}` raises `IntegrityError` (not-null), rolls back an uncommitted row of the session, and answers **400 "Required field is missing."** with type `…/conflict` over HTTP; `{"status": null}` changes nothing; the platform list and get return the workspace name and creator name; a ticket whose creator is gone shows `creator_name None`; `closed_at` minus `created_at` of a ticket closed at once is **18 000 s** under `America/New_York` and 0.4 s under `UTC`. **Not run:** two concurrent requests; the intended behavior of the bug rules.

## Review
> All questions answered.

### House-rule violations — applied automatically

- **HR-1** `create_ticket` R2, `update_ticket` R4 — a ticket's title is stored as typed (`"  Printer  "`) and a title, description or category of only spaces is accepted (`min_length=1` counts the spaces; verified). The web form trims all three, so only API clients reach it. Intended: `HelpTicketCreate` / `HelpTicketUpdate` trim `title`, `description` and `category`; a blank `title` or `description` is refused (422); a blank `category` becomes `None`, as the web form sends it. Inner text is kept. (The title is the ticket's label: HR-1. The description and category follow it so that one rule holds for the whole form — decided by Claude under the reviewer's delegation (2026-11-04).)
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1574 (pattern `blank-name-accepted`; per BUG-915, BUG-1526). Rules: `create_ticket` R2, `update_ticket` R4.
- **HR-9** `update_ticket` R6 — closing a ticket that is already closed writes `closed_at = now` and `closed_by` = the second user again (verified): the record of who closed it, and when, is overwritten although nothing changed. Intended: closing a closed ticket changes nothing; reopening an open ticket changes nothing (holds today).
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1576 (pattern `audit-stamp-on-noop`; per BUG-009). Rules: `update_ticket` R6.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-04))

### P1. `null` for a ticket's title or description answers a confusing database error — 🐞 BUG-1575
**Background:** `HelpTicketUpdate` declares `title` and `description` optional, so an explicit `null` passes the schema and reaches a NOT NULL column. Same root cause as BUG-630 (invoice update schema).
**What happens today:** `PATCH {"title": null}` fails at the database; the global handler answers 400 "Required field is missing." with type `…/conflict` (verified).
**Example:** An API client clears the title field and gets a "Resource Conflict" saying a required field is missing, naming none.
**Rules affected:** `update_ticket` R4a
**Answer:** bug — per BUG-630 precedent: `HelpTicketUpdate` refuses `null` for `title` and `description` with 422 naming the field; `category: null` still clears the category; `status: null` still means "no change"; omitted fields are unchanged.
**Resolution:** 🐞 BUG-1575 (pattern `unvalidated-required-field`). Rules: `update_ticket` R4a.

### P2. A ticket's close time depends on the database's time zone — 🐞 BUG-1577
**Background:** `closed_at` is a `timestamptz` column; the manager writes it from the naive UTC `utcnow()`, which Postgres reads in the session's time zone. Same root cause as BUG-1413 (notification `read_at`).
**What happens today:** Under `America/New_York` a ticket closed in the same second it was created shows `closed_at` 5 hours after `created_at`; under `UTC` they match (verified).
**Example:** On a database set to `Asia/Dhaka`, a ticket closed at 10:00 UTC is shown as closed at 04:00 UTC, before it was opened.
**Rules affected:** `update_ticket` R6
**Answer:** bug — per BUG-1413 / BUG-1282 precedent: `closed_at` is the true moment, written as aware UTC.
**Resolution:** 🐞 BUG-1577 (pattern `aware-datetime-against-naive-column`). Fix in `app/managers/help_ticket_manager.py`. Rules: `update_ticket` R6.

### New questions

### Q1. OWNER — An owner or manager can rewrite what another member wrote to support — 🐞 BUG-1863 (answered by the owner (2026-11-04), OQ-8)
**Background:** A ticket is a member's message to the platform's support team. The `owner` and `ground-team-manager` of a workspace see every ticket of the workspace; every other member sees only their own. Whoever may see a ticket may also change it: title, description, category, close and reopen. The web app only offers Close / Reopen; changing the text is possible through the API alone. This is about who may do what, so it is the owner's call.
**What happens today:** A `ground-team-manager` sends `PATCH /help/tickets/{id}` with a new title and description on a ticket a `ground-team` member opened: 200, and the member's words are replaced (verified). The ticket keeps no record of who changed the text.
**Example:** Mia reports "Max deleted my work order by mistake". Max, a manager, edits the ticket to "Work order missing", and support never sees the original.
**Rules affected:** `update_ticket` R3
**Suggested answer:** `bug — only the ticket's creator may change title, description and category; owner, ground-team-manager and platform admins may still close and reopen any ticket they can see (403 "You do not have access to this help ticket." for a text change by anyone else)`.
**Alternatives:** (a) `intended` — managers may tidy tickets up. (b) Nobody may change the text after creation; only close / reopen.
**Answer:** bug — only the ticket's creator may change title, description and category; owner, ground-team-manager and platform admins may still close and reopen any ticket they can see; a text change by anyone else gets 403 "You do not have access to this help ticket." (the suggested answer; answered by the owner (2026-11-04), OQ-8).
**Resolution:** 🐞 BUG-1863 (pattern `view-access-grants-edit`). Fix in `HelpTicketManager.update_ticket` / `can_access_ticket` (FU-1). Rules: `update_ticket` R3, R3a.

### Q2. A platform admin's ticket list is empty, though they can open every ticket by id — 🐞 BUG-1578 (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** A platform admin may enter any workspace without being a member ("support inbox workspace switch") and then has no role there. `get_ticket` lets a platform admin open any ticket of the workspace; `list_tickets` decides only by role, so it shows them only tickets they created themselves. The platform inbox (`/platform/help/tickets`) already lists every ticket of every workspace for them.
**What happens today:** In a workspace with two members' tickets, the admin's list is `[]`, and `GET /help/tickets/<id>` of either ticket answers 200 (verified).
**Example:** Support switches into "Acme" to look at its tickets and sees an empty help page, though the inbox shows three open tickets from Acme.
**Rules affected:** `list_tickets` R2
**Suggested answer:** `bug — the workspace list follows the same access rule as get: a platform admin sees every ticket of the workspace`. Not parked: this shows a platform admin nothing they cannot already open by id and list in the inbox. Alternative: `intended` (the workspace page is a member's own view).
**Answer:** bug — as suggested.
**Resolution:** 🐞 BUG-1578 (pattern `sibling-access-rule-mismatch`). Fix in `HelpTicketManager.list_tickets`. Rules: `list_tickets` R2.

Reached through the DAO and cited, one pass-through case each, as `tests/unit/dao/help_ticket.cases.md` marks them: BUG-1440 (not unit-testable, no case), BUG-1441 (strict), BUG-1442 (non-strict), BUG-1443 (strict).

Checked and **not** violated: **HR-2** — tickets have no unique name. **HR-3** — `category` is not filtered or grouped by the backend. **HR-4** — no soft delete. **HR-5** — filters are in the query (DAO). **HR-6, HR-8** — the DAO's (BUG-1442, BUG-1443). **HR-7** — both lists require `1 <= limit <= 200`, `skip >= 0`. **HR-10** — numbering is BUG-1440; close / reopen is a plain state change whose worst race overwrites a stamp. **HR-11 … HR-15** — none applies. **HR-16** — workspace methods filter on the ticket's workspace; another workspace's id is "not found", like an unknown one (verified). The platform methods are unscoped by design and reachable only through `get_platform_admin`.

**Permission checks (this service and its manager):** listed per method below. The role is computed by the endpoint (`workspace_members.role` of the caller in the workspace, `None` without a membership) and passed in.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Help ticket manager** (`app/managers/help_ticket_manager.py`, not yet specified) | Its outcomes reached from the API are rules here (`list_tickets` R1–R3, `get_ticket` R1–R4, `update_ticket` R3–R7, `to_response`). The fixes of BUG-1576, BUG-1577, BUG-1578 (and Q1) live there; BUG-1574, BUG-1575 in `app/schemas/help_ticket.py`. `can_view_all_tickets` / `can_access_ticket` are also used by `AttachmentManager` (support ticket attachments): check there whether Q1's answer changes who may attach. | Q1, Q2 |

## Overview
`HelpTicketService` is the transaction boundary for help tickets, the support requests a workspace sends to the platform team, and it shapes their answers. `/help/tickets` (members) and `/platform/help/tickets` (platform admins) call it. It calls `HelpTicketManager`, which decides who may see and change a ticket, and the help ticket DAO. Refusals are the manager's plain exceptions `HelpTicketNotFoundError` (a `LookupError`) and `HelpTicketForbiddenError` (a `PermissionError`); the endpoints turn them into 404 and 403. The service passes them on unchanged.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `datetime.now` in `app.dao.help_ticket` (year of the number, BUG-1441); `utcnow` in `app.managers.help_ticket_manager` (`closed_at`).
**Integration-only behavior:** as `department_service.spec.md`; the endpoints' translation of `HelpTicketNotFoundError` → 404 and `HelpTicketForbiddenError` → 403 (`{"detail": <message>}`); the role lookup; `get_platform_admin` (403 `Platform admin access required`); the `IntegrityError` handler (P1); `limit` / `skip` bounds; schema validation (400 today, BUG-461).

**Facts for the test designer**
- Import: `from app.services.help_ticket_service import HelpTicketService, help_ticket_service`; `from app.managers.help_ticket_manager import HelpTicketNotFoundError, HelpTicketForbiddenError`. Every parameter after `db` is keyword-only. The manager is the attribute `manager`.
- `HelpTicketResponse`: `id`, `workspace_id`, `ticket_number`, `title`, `description`, `category`, `status` (`HelpTicketStatusEnum`: `open`, `closed`), `created_by`, `creator_name`, `created_at`, `updated_at`, `closed_at`, `closed_by`. `PlatformHelpTicketListItem` adds `workspace_name`.
- Roles (`RoleEnum` values): `owner`, `finance`, `ground-team`, `ground-team-manager`. `Profile.is_platform_admin` marks a platform admin. Members: `WorkspaceMember(workspace_id, user_id, role, status="active")`.
- Messages: not found `Help ticket not found.`; forbidden `You do not have access to this help ticket.`
- Table facts: help ticket DAO spec, **Model facts**.

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): as `department_service.spec.md` Notes.
- `updated_at` is the database's `now()` (transaction start): inside one test it does not move between writes; do not assert it changes.
- **BUG-1577:** run `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))` first; close a ticket created in the same test; intended `abs(closed_at - created_at) < 60 s` → strict xfail.
- **BUG-1574, BUG-1575:** assert `pydantic.ValidationError` building the schema; the service is never reached → strict xfail.
- **BUG-1578:** a profile with `is_platform_admin=True` and `role=None` → strict xfail.
- **BUG-1863** (Q1, owner): a `ground-team-manager`, an `owner` and a platform admin (none of them the creator) sending `title`, `description` or `category` on a member's ticket → `HelpTicketForbiddenError`, ticket unchanged → **strict** xfail. The creator's own text change (R3) and close / reopen by a manager (R5) pass today and are plain cases.

## Not specified
- `HelpTicketService.__init__` — stores the manager, no logic.
- `help_ticket_service` — module-level singleton, no logic.

---

## `HelpTicketService.create_ticket(db, *, workspace, user, payload)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /help/tickets`, 201)

**Purpose:** Open a ticket for the caller and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace` | `Workspace` | its `id` is the ticket's workspace |
| `user` | `Profile` | its `id` is `created_by` |
| `payload` | `HelpTicketCreate` | `title` 1–200, `description` ≥ 1, `category` ≤ 80 or `None` |

**Returns:** a `HelpTicketResponse` of the new ticket.

**Rules:**
- **R1.** One ticket is created as DAO `create_with_user` creates it (its R1–R5: number `HELP-<year>-<n>`, `status open`, BUG-1440, BUG-1441); it is committed (TC1). Every member may open a ticket, whatever the role. Verified.
- **R2.** [BUG-1574] (HR-1) `title`, `description`, `category` are stored trimmed; a blank title or description is refused by `HelpTicketCreate` (422), nothing created; a blank category is stored `None`. *(Today: stored as typed; `"   "` accepted for title and description. Verified.)*
- **R3.** The answer is built from the ticket re-read with its creator (DAO `get_by_id` R1): every field from the row, `creator_name` = the creator's `name`. If that re-read finds nothing, the refreshed row is used — **not unit-testable** (reachable only by patching the DAO, not an external; the L48 / L119 `or` → `and` mutants are equivalent for unit purposes; revision 2026-11-04). The rest verified.
- **R4.** Any error rolls back and reaches the caller unchanged (TC3); commit failure TC4; a failure of the re-read after the commit leaves the ticket saved (TC5).

**Errors:** database errors unchanged (a taken number: `IntegrityError`, DAO R4; unknown user / workspace: `IntegrityError`).

**Side effects:** one `help_tickets` row, committed.

---

## `HelpTicketService.list_tickets(db, *, workspace_id, user, role, status=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /help/tickets`)

**Purpose:** The workspace's tickets the caller may see.

**Returns:** a `list` of `HelpTicketResponse`, newest first.

**Rules:**
- **R1.** With `role` `owner` or `ground-team-manager`, every ticket of the workspace is listed; with any other role or `None`, only tickets the caller created (verified for all four roles and `None`). Order, `status` filter and paging are DAO `list_by_workspace` R1–R6 (BUG-1442); `status` is passed as its value (`"open"` / `"closed"`), `None` = no filter.
- **R2.** [BUG-1578] (Q2) A platform admin (`user.is_platform_admin`) sees every ticket of the workspace, whatever `role`, as `get_ticket` R1. *(Today: only the tickets they created; a platform admin without a membership sees `[]`. Verified.)*
- **R3.** Each entry as `create_ticket` R3 (`creator_name` from the loaded creator, `None` without one).
- **R4.** Read only (TC6).

**Errors:** `DataError` for negative `skip` / `limit` when called directly.

**Side effects:** none

---

## `HelpTicketService.get_ticket(db, *, workspace_id, ticket_id, user, role)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /help/tickets/{id}`)

**Purpose:** One ticket, if the caller may see it.

**Returns:** a `HelpTicketResponse`.

**Rules:**
- **R1.** A ticket of the workspace is returned when the caller is a platform admin, or has role `owner` / `ground-team-manager`, or created it. Verified.
- **R2.** Otherwise → `HelpTicketForbiddenError("You do not have access to this help ticket.")` (403 at the API). Verified.
- **R3.** Unknown id, `0`, or another workspace's ticket → `HelpTicketNotFoundError("Help ticket not found.")` (404 at the API), before any access check: the same answer for both. Verified.
- **R4.** A ticket whose creator is gone (`created_by` `NULL`) is visible only to the roles and admins of R1, with `creator_name None` (verified). Read only (TC6).

**Errors:** R2, R3.

**Side effects:** none

---

## `HelpTicketService.update_ticket(db, *, workspace_id, ticket_id, user, role, payload)`
**Shape:** update / state-transition
**Persistence:** writes
**Visibility:** public (used by: `PATCH /help/tickets/{id}`)

**Purpose:** Change a ticket's text, or close / reopen it, and save it.

**Returns:** a `HelpTicketResponse`, re-read with its creator.

**Rules:**
- **R1.** The ticket is found as `get_ticket` R1–R3; a refusal rolls the session back (TC3: pending changes of the session are discarded too) and reaches the caller unchanged. Verified.
- **R2.** Only fields sent are applied (`exclude_unset`); `{}` changes nothing. Verified.
- **R3.** The ticket's creator may change its `title`, `description` and `category` (whatever their role). Verified.
- **R3a.** [BUG-1863] (Q1, owner) Anyone else who may see the ticket (R1: `owner`, `ground-team-manager`, a platform admin) and sends `title`, `description` or `category` in the payload (sent at all, as R2 counts fields) gets `HelpTicketForbiddenError("You do not have access to this help ticket.")` (403 at the API); nothing is written, a `status` in the same payload included, and the session is rolled back (TC3). A ticket whose creator is gone (`created_by` `NULL`) has its text changed by nobody. Close / reopen alone stays allowed to them (R5). *(Today: their text change is applied, 200. Verified for a `ground-team-manager`.)*
- **R4.** [BUG-1574] (HR-1) A sent `title` / `description` / `category` is stored trimmed; blank title or description refused (422); blank category stored `None`. *(Today: as typed.)*
- **R4a.** [BUG-1575] (P1) `null` for `title` or `description` is refused by `HelpTicketUpdate` (422), nothing written; `category: null` clears the category. *(Today: the flush fails with `IntegrityError` (not-null), rolled back; 400 "Required field is missing." over HTTP. Verified.)*
- **R5.** `status: "closed"` on an open ticket sets `status = closed`, `closed_by = user.id`, `closed_at` = now; `status: "open"` sets `status = open`, `closed_at = None`, `closed_by = None`; `status: null` or no `status` leaves all three. Anyone who may see the ticket may close or reopen it. Verified.
- **R6.** [BUG-1576] (HR-9) `status: "closed"` on a ticket already closed changes nothing: `closed_at`, `closed_by` keep their values. *(Today: both rewritten. Verified.)* [BUG-1577] (P2) `closed_at` is the true moment in UTC whatever the database's time zone. *(Today: 5 hours off under `America/New_York`. Verified.)* Reopening an open ticket changes nothing (holds today).
- **R7.** The change is committed (TC1) and answered as `create_ticket` R3. Commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown / other workspace | `HelpTicketNotFoundError` | `Help ticket not found.` |
| not allowed to see it | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| text field sent by someone other than the creator (R3a, BUG-1863) | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| (today) `null` title / description | `sqlalchemy.exc.IntegrityError` (`NotNullViolation`) | — |

**Side effects:** the changed fields, `updated_at` (database), committed. On any error: rolled back.

---

## `HelpTicketService.list_platform_tickets(db, *, status=None, search=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `GET /platform/help/tickets`, guarded by `get_platform_admin`)

**Purpose:** The support inbox: tickets of every workspace.

**Returns:** a `list` of `PlatformHelpTicketListItem`.

**Rules:**
- **R1.** The tickets, their order, filters and paging are DAO `list_platform` R1–R6 (BUG-1442, BUG-1443), `status` passed as its value. Each entry is the ticket's `HelpTicketResponse` fields plus `workspace_name`; `creator_name` is the joined profile's name, else the loaded creator's, else `None`. Verified.
- **R2.** No access check in the service: the endpoint admits platform admins only. Read only (TC6).

**Errors:** `DataError` for negative `skip` / `limit` when called directly.

**Side effects:** none

---

## `HelpTicketService.get_platform_ticket(db, *, ticket_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /platform/help/tickets/{id}`, guarded by `get_platform_admin`)

**Rules:**
- **R1.** A ticket of any workspace → its `PlatformHelpTicketListItem` (as `list_platform_tickets` R1). Verified.
- **R2.** Unknown id or `0` → `HelpTicketNotFoundError("Help ticket not found.")` (404 at the API). Verified. Read only.

**Errors:** R2. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 36–43 | create: manager (DAO `create_with_user`) → commit | `create_ticket` R1, R2 |
| 44–48 | refresh; re-read with creator; `refreshed or ticket` (the `None` side not unit-testable); `to_response` (creator name if a creator) | `create_ticket` R3 |
| 49–51 | any exception → rollback, re-raise | `create_ticket` R4 |
| 64–73 | manager `list_tickets`: role in {owner, ground-team-manager} → all, else `created_by` = user (no admin case, BUG-1578); `status.value` | `list_tickets` R1–R4 |
| 84–91 | manager `get_by_id_and_workspace`: `None` → not found; `can_access_ticket` (admin, role, creator) → else forbidden | `get_ticket` R1–R4 |
| 103–110 | update: same lookup inside the `try` | `update_ticket` R1 |
| 111–113 | manager `update_ticket`: no creator check for text fields (BUG-1863); `exclude_unset`; pop `status`; `closed` → stamp (always, BUG-1576; naive `utcnow`, BUG-1577); `open` → clear; other / `None` → nothing; DAO `update` with a dict (writes `None` too, BUG-1575) | `update_ticket` R2–R6 |
| 114–119 | commit; refresh; re-read; response (`refreshed or ticket` at 119: the `None` side not unit-testable, as `create_ticket` R3) | `update_ticket` R7 |
| 120–122 | any exception → rollback, re-raise | `update_ticket` R1, R4a, R7 |
| 133–139 | platform list via manager → DAO `list_platform`; `_to_platform_item` (`creator_name or base.creator_name`) | `list_platform_tickets` R1, R2 |
| 147 | platform get: `None` → not found | `get_platform_ticket` R1, R2 |
| 150 | module singleton | Not specified |
