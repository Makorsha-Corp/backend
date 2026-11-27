# Spec — `app/services/help_ticket_service.py`

> **Status:** APPROVED — revision 2026-11-26 (workflow change from `origin/main`); D1 answered by the owner (2026-11-26) (OQ-66): BUG-3251; every other new item decided by Claude under the reviewer's delegation (2026-11-26); nothing open. Earlier: Q1 answered by the owner (2026-11-04) (OQ-8): BUG-1863.
> **Source commit:** 41d5ac1

> **Revision 2026-11-26 (describe revision after merging `origin/main`, commits 5352aed "type field" and 4a807ff "pending | opened | closed ticket status workflow").** Re-read the service, `HelpTicketManager`, the help ticket DAO, `BaseDAO.update`, the model, the schemas, both endpoint modules and migrations 123 / 124. Read, not run: the "Verified" marks below belong to the 2026-11-04 run against the old code and are kept only on rules the change did not touch. What changed in the spec:
> - **Status values** are now `pending` · `opened` · `closed` (`open` is gone; migration 124 rewrote stored `open` → `opened`). New tickets start `pending`. Rewritten: `create_ticket` R1, `update_ticket` R5, R6; new `update_ticket` R5a–R5d; Facts.
> - **A fixed status transition table**; two new manager errors (`HelpTicketStatusChangeForbiddenError` → 403, `HelpTicketInvalidTransitionError` → 400). The merged code lets **only platform admins** change status; the owner answered (OQ-66, 2026-11-26): keep OQ-8 — platform admins, `owner` and `ground-team-manager` change status, everyone else 403. The admin-only rule is **BUG-3251** (logged in the manager spec; cited here, not duplicated). This replaces the old "anyone who may see the ticket may close or reopen it" (old R5) (D1).
> - **BUG-1576 is resolved by the change:** closing a closed ticket is now refused (400) and rewrites nothing, so HR-9 holds. Its tag is removed from `update_ticket` R6 (D2). The register row is left for the caller to close.
> - **New `type`** (`support` · `feedback`): stored on create, answered in every response, filter on both lists, not changeable by PATCH. New: `create_ticket` R1a, `list_tickets` R1a, `list_platform_tickets` R1a, `update_ticket` R2a.
> - **New callable `update_platform_ticket`** (platform PATCH) with its own transaction contract (TC1–TC6) and **BUG-3270** (OQ-8 applied to the platform path: a platform admin may not rewrite another member's text there either).
> - **Errors raised by stored data the enum does not know** (`create_ticket` R3a, `update_ticket` R5c) — written as rules, no bug.
> - `HelpTicketNotFoundError` is imported by the service again (dropped by the auto-merge, re-added by hand); `update_platform_ticket` raises it itself.
> Kept as they were: BUG-1574, BUG-1575, BUG-1577, BUG-1578, BUG-1863 (text part), the `refreshed or ticket` revision of 2026-11-04 (now also L150), TC1–TC6.

> **Revision 2026-11-04 (verification gap, `help_ticket_service.verify.md` finding 2 / cases gap 2):** the fallback "if the re-read finds nothing, the refreshed row is used" (`create_ticket` R3, `update_ticket` R7, `update_platform_ticket` R6; source lines 48, 123, 150) is **not unit-testable**: it is reached only by patching the DAO's `get_by_id`, and the DAO is not an external. On every reachable path the re-read returns the same identity-mapped instance as the refreshed row, so the mutants `refreshed or ticket` → `refreshed and ticket` are **equivalent for unit purposes**. Decided by Claude under the reviewer's delegation (2026-11-04; extended to L150 2026-11-26).

> **Form.** As `tests/unit/services/department_service.spec.md`; the **Transaction contract TC1–TC6 lives in `tests/unit/services/base_service.spec.md`** and is cited here. Below the service: `tests/unit/managers/help_ticket_manager.spec.md` and `tests/unit/dao/help_ticket.spec.md` — both APPROVED at e48a092, i.e. **before** this change (FU-2). Where they and this spec disagree about status values, transitions, `type` or the new `is_platform_admin` argument, **this spec is current**; outcomes of the manager reached through the service are written here as rules.

> **Routed here and written as rules:** help ticket DAO FU-1 (a) HR-1 (BUG-1574); (b) closing an already closed ticket (BUG-1576 — resolved by the 2026-09-22 workflow, see D2); (c) the platform endpoints are guarded by `get_platform_admin` (`list_platform_tickets` R2, `get_platform_ticket`, `update_platform_ticket` R2).
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** P1 (BUG-1575), P2 (BUG-1577), Q2 (BUG-1578). House-rule lines: BUG-1574, BUG-1576. **Decided by Claude under the reviewer's delegation (2026-11-26):** D2, D3, P3 (BUG-3270). None is the owner's answer. **Answered by the owner (2026-11-04):** Q1 (OQ-8) → BUG-1863. **Answered by the owner (2026-11-26):** D1 (OQ-66) → BUG-3251.
>
> **Standing decisions applied here (not asked again):** OQ-8 (owner: only the creator edits title / description / category). HR-16 (no response shows another workspace's rows; the platform inbox and the platform PATCH are the deliberate exception, for platform admins only). A missing `ORDER BY` tie-break is a bug (DAO: BUG-1442). Help tickets are **not** money, stock or order workflow.
>
> **Verified by running (2026-11-04, old code — kept for rules the change did not touch)** (`h.py`, `v4_help.py`, `v5_wait.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test` (session time zone `America/New_York`)): create returns `HELP-<year>-001`, `creator_name`, `updated_at` set, survives a later rollback; title `"  Printer  "` stored as typed, `"   "` accepted; lists per role; a platform admin with no role sees none but their own, yet opens another member's ticket by id; a member opening or updating another's ticket gets `HelpTicketForbiddenError`; unknown id or another workspace's ticket → `HelpTicketNotFoundError`; a `ground-team-manager` changes the text of a member's ticket; `{}` changes nothing; `{"title": null}` raises `IntegrityError` and answers 400 "Required field is missing." over HTTP; `{"status": null}` changes nothing; platform list and get return workspace and creator name; a ticket without a creator shows `creator_name None`; `closed_at` − `created_at` of a ticket closed at once is 18 000 s under `America/New_York`. **Not run:** anything about `pending` / `opened`, transitions, `type`, `update_platform_ticket`; concurrency; the intended behavior of the bug rules.

## Review
> All questions answered. Items D1–D3 and P3 are new in the 2026-11-26 revision.

### House-rule violations — applied automatically

- **HR-1** `create_ticket` R2, `update_ticket` R4 (and `update_platform_ticket` R4, same schema) — a ticket's title is stored as typed (`"  Printer  "`) and a title, description or category of only spaces is accepted (`min_length=1` counts the spaces). Intended: `HelpTicketCreate` / `HelpTicketUpdate` trim `title`, `description` and `category`; a blank `title` or `description` is refused (422); a blank `category` becomes `None`. Inner text is kept. (Description and category follow the title — decided by Claude under the reviewer's delegation (2026-11-04).)
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1574 (pattern `blank-name-accepted`). Rules: `create_ticket` R2, `update_ticket` R4, `update_platform_ticket` R4.
- **HR-9** `update_ticket` R6 — (2026-11-04) closing a ticket that is already closed rewrote `closed_at` and `closed_by`. **2026-11-26:** the new transition table refuses `closed → closed` with `HelpTicketInvalidTransitionError` (400) before anything is written, so the stamps are no longer rewritten; HR-9 holds today.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1576 (pattern `audit-stamp-on-noop`) — **resolved by the workflow change (commit 4a807ff)**; no tagged rule remains (D2). The register row should be closed (`fixed`) by the caller. Rules: `update_ticket` R5b, R6.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation)

### P1. `null` for a ticket's title or description answers a confusing database error — 🐞 BUG-1575
**Background:** `HelpTicketUpdate` declares `title` and `description` optional, so an explicit `null` passes the schema and reaches a NOT NULL column. Same root cause as BUG-630.
**What happens today:** `PATCH {"title": null}` fails at the database; the global handler answers 400 "Required field is missing." with type `…/conflict` (verified 2026-11-04; unchanged by the merge).
**Example:** An API client clears the title field and gets a "Resource Conflict" saying a required field is missing, naming none.
**Rules affected:** `update_ticket` R4a, `update_platform_ticket` R4
**Answer:** bug — per BUG-630 precedent: `HelpTicketUpdate` refuses `null` for `title` and `description` with 422 naming the field; `category: null` still clears the category; `status: null` still means "no change"; omitted fields are unchanged.
**Resolution:** 🐞 BUG-1575 (pattern `unvalidated-required-field`). Rules: `update_ticket` R4a, `update_platform_ticket` R4.

### P2. A ticket's close time depends on the database's time zone — 🐞 BUG-1577
**Background:** `closed_at` is a `timestamptz` column; the manager writes it from the naive UTC `utcnow()`, which Postgres reads in the session's time zone. Same root cause as BUG-1413.
**What happens today:** Under `America/New_York` a ticket closed in the same second it was created shows `closed_at` 5 hours after `created_at` (verified 2026-11-04; the merge kept `utcnow()`, still naive: `app/utils/time.py`).
**Example:** On a database set to `Asia/Dhaka`, a ticket closed at 10:00 UTC is shown as closed at 04:00 UTC, before it was opened.
**Rules affected:** `update_ticket` R6 (reached also through `update_platform_ticket` R2)
**Answer:** bug — per BUG-1413 / BUG-1282 precedent: `closed_at` is the true moment, written as aware UTC.
**Resolution:** 🐞 BUG-1577 (pattern `aware-datetime-against-naive-column`). Fix in `app/managers/help_ticket_manager.py`. Rules: `update_ticket` R6.

### P3. The platform PATCH lets a platform admin rewrite what a member wrote — 🐞 BUG-3270 (decided by Claude under the reviewer's delegation (2026-11-26))
**Background:** The merge added `PATCH /platform/help/tickets/{id}` (summary "Update help ticket status (platform admin)"). It takes the same `HelpTicketUpdate` as the workspace PATCH — title, description, category, status — for a ticket of any workspace. OQ-8 (owner): only the ticket's creator changes its title, description and category; a text change by anyone else answers 403 "You do not have access to this help ticket." (BUG-1863, workspace path).
**What happens today:** A platform admin sends `{"description": "…"}` to the platform PATCH on a member's ticket: the text is replaced and committed (read, not run). The endpoint also does not catch `HelpTicketForbiddenError`, so once the fix raises it the endpoint must map it to 403 too.
**Example:** Mia reports "Max deleted my work order". A support agent edits the ticket in the inbox to "Work order missing"; Mia's words are gone and nothing records the change.
**Rules affected:** `update_platform_ticket` R3a
**Answer:** bug — per BUG-1863 precedent (OQ-8): on the platform PATCH a `title`, `description` or `category` sent by anyone other than the ticket's creator is refused with `HelpTicketForbiddenError("You do not have access to this help ticket.")`, 403 at the API (the endpoint maps it), nothing written, a `status` in the same payload included; a status change alone stays allowed. Not parked: it applies the owner's answer, it gives nobody new access.
**Resolution:** 🐞 BUG-3270 (pattern `view-access-grants-edit`; the manager part is the same fix as BUG-1863 — `help_ticket_manager.spec.md` R4 files the platform path under BUG-1863 — BUG-3270 tracks the platform path end to end, endpoint mapping included; merge the rows if preferred). Fix in `HelpTicketManager.update_ticket` (the same creator check as BUG-1863) and `app/api/v1/endpoints/platform_help.py` (map `HelpTicketForbiddenError` → 403). Rules: `update_platform_ticket` R3a.

### Decisions on the new workflow (decided by Claude under the reviewer's delegation (2026-11-26))

### D1. OWNER — Owners and managers can no longer change a ticket's status — 🐞 BUG-3251 (answered by the owner (2026-11-26), OQ-66)
**Background:** OQ-8 (2026-11-04) was asked about **text** edits; its answer kept the then-current right of `owner`, `ground-team-manager` and platform admins to close and reopen. The merged commit 4a807ff (dated 2026-09-22, reached this branch on 2026-11-26) states its design explicitly: "only platform admins may change status via validated transitions (pending → opened → closed → opened)".
**What happens today:** Any `status` value (not `null`) sent by a caller who is not a platform admin — the creator, an owner, a manager — is refused with `HelpTicketStatusChangeForbiddenError("Only platform admins may change ticket status.")`, 403 at the API; nothing is written.
**Example:** Max, the workspace's ground-team manager, sees support has fixed the problem and presses "Close" on Mia's ticket: 403. Only support can close it.
**Rules affected:** `update_ticket` R5, R3a
**Answer:** owner, 2026-11-26 (OQ-66): keep OQ-8 — platform admins, the workspace `owner` and `ground-team-manager` may change status, along the same transition table (pending→opened, opened→closed, closed→opened); anyone else (e.g. a plain member who raised the ticket) is refused with 403. The admin-only rule is a bug. (Claude's earlier draft had called it intended; superseded.)
**Resolution:** 🐞 BUG-3251 (logged in `help_ticket_manager.spec.md`; not duplicated here). Fix in `HelpTicketManager.update_ticket` — it must learn the caller's role *(requires the service to pass `role` to the manager, today only `is_platform_admin` is passed)*. Rules: `update_ticket` R5, R5a, R3a.

### D2. Asking for the status a ticket already has is refused (400), not a no-op — ✅ intended
**Background:** The transition table allows only `pending → opened`, `opened → closed`, `closed → opened`. Every other pair, the same status included, is refused.
**What happens today:** A platform admin sends `status: "closed"` on a closed ticket → `HelpTicketInvalidTransitionError("Cannot transition from closed to closed.")`, 400; nothing written, so `closed_at` / `closed_by` keep their values.
**Example:** Two support agents both press "Close" on the same ticket a minute apart; the second sees 400 "Cannot transition from closed to closed." and the record of who closed it stays with the first.
**Rules affected:** `update_ticket` R5b, R6
**Answer:** intended — an explicit, validated state machine; it satisfies HR-9 (nothing rewritten) and BUG-1576's intent ("closing a closed ticket changes nothing"). A silent 200 no-op would also satisfy HR-9; the refusal is kept because it is the merged design and tells the second agent someone acted first.
**Resolution:** BUG-1576 resolved; `update_ticket` R5b ✅, R6 ✅.

### D3. Which refusal a payload mixing text and status gets — ✅ decided
**Background:** One PATCH may carry text fields and `status`. Today the checks run: ticket found (and, on the workspace path, visible) → status permission (R5) → transition valid (R5b, R5c) → write. BUG-1863 / BUG-3270 add a text-permission check.
**What happens today:** A `ground-team-manager` sending `{"title": "…", "status": "closed"}` on a member's ticket gets `HelpTicketStatusChangeForbiddenError` (403) and nothing is written.
**Example:** As above: the manager sees "Only platform admins may change ticket status.", not "You do not have access to this help ticket.".
**Rules affected:** `update_ticket` R3a, `update_platform_ticket` R3a
**Answer:** fixed where it matters, free where it does not: a caller who may not change status (R5) mixing text and status gets `HelpTicketStatusChangeForbiddenError` (the creator) or a 403 `PermissionError` (a non-creator: `HelpTicketForbiddenError` also acceptable, as the manager spec R4a); an `owner` / `ground-team-manager` who is not the creator, sending text plus a status, is refused with a 403 `PermissionError` (today the status refusal; after BUG-3251 the text refusal `HelpTicketForbiddenError`) and the status does not change either; a platform admin who is not the creator, sending text plus a **valid** status, gets `HelpTicketForbiddenError` (the bug); a platform admin who is not the creator, sending text plus a transition that is **not** allowed, gets either `HelpTicketForbiddenError` or `HelpTicketInvalidTransitionError` — the order of those two checks is left to the fix (aligned with `help_ticket_manager.spec.md` R4 / R4a, revised in parallel 2026-11-26). Every refusal writes nothing.
**Resolution:** `update_ticket` R3a, `update_platform_ticket` R3a.

### New questions (2026-11-04)

### Q1. OWNER — An owner or manager can rewrite what another member wrote to support — 🐞 BUG-1863 (answered by the owner (2026-11-04), OQ-8)
**Background:** A ticket is a member's message to the platform's support team. The `owner` and `ground-team-manager` of a workspace see every ticket of the workspace; every other member sees only their own. Whoever may see a ticket may also change its title, description and category. Changing the text is possible through the API alone.
**What happens today:** A `ground-team-manager` sends `PATCH /help/tickets/{id}` with a new title and description on a ticket a `ground-team` member opened: 200, and the member's words are replaced (verified 2026-11-04; unchanged by the merge for text-only payloads).
**Example:** Mia reports "Max deleted my work order by mistake". Max, a manager, edits the ticket to "Work order missing", and support never sees the original.
**Rules affected:** `update_ticket` R3, R3a
**Answer:** bug — only the ticket's creator may change title, description and category; owner, ground-team-manager and platform admins may still close and reopen any ticket they can see; a text change by anyone else gets 403 "You do not have access to this help ticket." (the suggested answer; answered by the owner (2026-11-04), OQ-8).
**Resolution:** 🐞 BUG-1863 (pattern `view-access-grants-edit`). Fix in `HelpTicketManager.update_ticket`. Rules: `update_ticket` R3, R3a. **2026-11-26:** the close / reopen clause is kept by the owner (OQ-66; the merged admin-only status rule is BUG-3251, D1); the text rule stands and is also applied to the platform PATCH (P3, BUG-3270).

### Q2. A platform admin's ticket list is empty, though they can open every ticket by id — 🐞 BUG-1578 (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** A platform admin may enter any workspace without being a member and then has no role there. `get_ticket` lets a platform admin open any ticket of the workspace; `list_tickets` decides only by role. The platform inbox already lists every ticket of every workspace for them.
**What happens today:** In a workspace with two members' tickets, the admin's list is `[]`, and `GET /help/tickets/<id>` of either ticket answers 200 (verified 2026-11-04; unchanged by the merge).
**Example:** Support switches into "Acme" and sees an empty help page, though the inbox shows three pending tickets from Acme.
**Rules affected:** `list_tickets` R2
**Answer:** bug — as suggested (the workspace list follows the same access rule as get).
**Resolution:** 🐞 BUG-1578 (pattern `sibling-access-rule-mismatch`). Fix in `HelpTicketManager.list_tickets`. Rules: `list_tickets` R2.

Reached through the DAO and cited, one pass-through case each, as `tests/unit/dao/help_ticket.cases.md` marks them: BUG-1440 (not unit-testable, no case), BUG-1441 (strict), BUG-1442 (non-strict), BUG-1443 (strict). Who passes the see-right (`get_ticket` R1) is further shaped by BUG-1885 (suspended role; fix in the endpoint) and BUG-2103 (workspace owner by `owner_user_id`), both tested in the manager spec, not here; likewise BUG-3250 (the workspace owner by `owner_user_id` sees every ticket in `list_tickets`, manager spec D-8, logged 2026-11-26 by the manager revision).

Checked and **not** violated: **HR-2** — tickets have no unique name. **HR-3** — `category` is not filtered or grouped by the backend; `type` is a closed enum, not free text. **HR-4** — no soft delete. **HR-5** — status, type, creator and search filters are in the query before paging (DAO). **HR-6, HR-8** — the DAO's (BUG-1442, BUG-1443). **HR-7** — both lists require `1 <= limit <= 200`, `skip >= 0`. **HR-9** — holds since the workflow change (D2). **HR-10** — numbering is BUG-1440; status transitions have no money, stock, notification or external side effect: the worst race (two agents closing an `opened` ticket at once) overwrites the `closed_at` / `closed_by` stamp, which HR-10 explicitly does not require a lock for. **HR-11 … HR-15** — none applies. **HR-16** — workspace methods filter on the ticket's workspace; another workspace's id is "not found", like an unknown one. The platform methods (list, get, PATCH) are unscoped by design and reachable only through `get_platform_admin`.

**Permission checks (this service and its manager):** listed per method below. The role is computed by the endpoint (`workspace_members.role` of the caller in the workspace, `None` without a membership) and passed in. "Platform admin" = `user.is_platform_admin` (`profiles.is_platform_admin`, NOT NULL, default `false`).

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Help ticket manager** (`tests/unit/managers/help_ticket_manager.spec.md`, APPROVED at e48a092) | The fixes of BUG-1577, BUG-1578, BUG-1863, BUG-3270 live in `HelpTicketManager`; BUG-1574, BUG-1575 in `app/schemas/help_ticket.py`; BUG-3270 also in `app/api/v1/endpoints/platform_help.py`. | Q1, Q2, P3 |
| FU-2 | **Manager and DAO specs are stale** (`help_ticket_manager.spec.md`, `tests/unit/dao/help_ticket.spec.md`) | Both describe the pre-merge code: no `pending` / `opened`, no transition table, no `is_platform_admin` argument, no `HelpTicketStatusChangeForbiddenError` / `HelpTicketInvalidTransitionError`, no `type` (DAO `create_with_user` now pops `type`, both lists filter on `ticket_type`, new tickets get `status "pending"`). They need a describe revision like this one (the manager's is under way in parallel, 2026-11-26: BUG-3250 / D-8); their cases and tests are invalid for the same reason as this module's. | revision 2026-11-26 |
| FU-3 | **Bug register** (`docs/testing/bugs.md`) | BUG-1576 → `fixed` by commit 4a807ff (closed → closed refused, nothing rewritten). BUG-1863's Intended column still says owner / manager "may still close / reopen": its close / reopen clause stands (OQ-66; the admin-only code is BUG-3251, which should name this spec too); its text rule is unchanged. | D1, D2 |
| FU-4 | **Frontend** (`../frontend`, local checkout) | `src/types/helpTicket.ts` still types status `'open' \| 'closed'`, and `HelpPage.tsx` offers members "Close ticket" / "Reopen ticket" and a status filter with `open`. Against the merged backend: the filter `open` is refused by request validation; a plain member's close gets 403 (intended, OQ-66); an owner's / manager's close gets 403 too (BUG-3251) and must use the new values (`opened`). Not checked whether the remote frontend has been updated. | D1 |

## Overview
`HelpTicketService` is the transaction boundary for help tickets — support requests and feedback a workspace sends to the platform team — and it shapes their answers. `/help/tickets` (members) and `/platform/help/tickets` (platform admins) call it. It calls `HelpTicketManager`, which decides who may see and change a ticket and which status changes are allowed, and the help ticket DAO. Refusals are the manager's plain exceptions: `HelpTicketNotFoundError` (a `LookupError`), `HelpTicketForbiddenError` and `HelpTicketStatusChangeForbiddenError` (both `PermissionError`), `HelpTicketInvalidTransitionError` (a `ValueError`); the endpoints turn them into 404, 403, 403 and 400. The service passes them on unchanged.

**Callables:** 7 specified · 2 not specified
**Externals to mock:** `datetime.now` in `app.dao.help_ticket` (year of the number, BUG-1441); `utcnow` in `app.managers.help_ticket_manager` (`closed_at`).
**Integration-only behavior:** as `department_service.spec.md`; the endpoints' translation of errors — workspace PATCH: `HelpTicketNotFoundError` → 404, `HelpTicketForbiddenError` → 403, `HelpTicketStatusChangeForbiddenError` → 403, `HelpTicketInvalidTransitionError` → 400; workspace GET by id: 404 / 403; platform GET by id: 404; platform PATCH: 404, 403 (status-change, unreachable there), 400, and **no** mapping of `HelpTicketForbiddenError` today (BUG-3270), all as `{"detail": <message>}`; the role lookup; `get_platform_admin` (403 `Platform admin access required`); the `IntegrityError` handler (P1); `limit` / `skip` bounds; the query parameters `status` (`pending` / `opened` / `closed`) and `type` (`support` / `feedback`) are enums, anything else refused by request validation (400 today, BUG-461).

**Facts for the test designer**
- Import: `from app.services.help_ticket_service import HelpTicketService, help_ticket_service`; `from app.managers.help_ticket_manager import HelpTicketNotFoundError, HelpTicketForbiddenError, HelpTicketStatusChangeForbiddenError, HelpTicketInvalidTransitionError`; `from app.models.enums import HelpTicketStatusEnum, HelpTicketTypeEnum, RoleEnum`. Every parameter after `db` is keyword-only. The manager is the attribute `manager`.
- `HelpTicketStatusEnum`: `PENDING = "pending"`, `OPENED = "opened"`, `CLOSED = "closed"` (**no `open`**: `HelpTicketStatusEnum("open")` raises `ValueError`). `HelpTicketTypeEnum`: `SUPPORT = "support"`, `FEEDBACK = "feedback"`.
- `HelpTicketCreate`: `title` 1–200, `description` ≥ 1, `category` ≤ 80 or `None`, `type` (`HelpTicketTypeEnum`, default `support`). `HelpTicketUpdate`: `title`, `description`, `category`, `status` (`HelpTicketStatusEnum | None`), all optional; **no `type`** — an extra `type` key is ignored by the schema (Pydantic default).
- `HelpTicketResponse`: `id`, `workspace_id`, `ticket_number`, `title`, `description`, `category`, `status` (`HelpTicketStatusEnum`), `type` (`HelpTicketTypeEnum`), `created_by`, `creator_name`, `created_at`, `updated_at`, `closed_at`, `closed_by`. `PlatformHelpTicketListItem` adds `workspace_name`. `update_platform_ticket` answers a plain `HelpTicketResponse` (no `workspace_name`).
- Model `help_tickets`: `status` `String(16)` NOT NULL, Python default `"pending"` (server default `'pending'` after migration 124); `type` `String(16)` NOT NULL, Python default `"support"` (server default `'support'`). **No CHECK constraint** on either: a row can hold any string up to 16 characters.
- Roles (`RoleEnum` values): `owner`, `finance`, `ground-team`, `ground-team-manager`. `Profile.is_platform_admin` marks a platform admin. Members: `WorkspaceMember(workspace_id, user_id, role, status="active")`.
- Messages: not found `Help ticket not found.`; forbidden `You do not have access to this help ticket.`; status change refused `Only platform admins may change ticket status.` (today; once BUG-3251 is fixed that text no longer fits — assert the type only for refusals of R5); bad transition `Cannot transition from <current> to <target>.` with the enum values (e.g. `Cannot transition from pending to closed.`); unknown stored status `Cannot transition from invalid status '<stored>'.` (the stored string in single quotes).
- Transition table (complete): `pending → opened`; `opened → closed`; `closed → opened`. Everything else is refused (R5b).
- Table facts otherwise: help ticket DAO spec, **Model facts** (stale for `status` / `type`, FU-2).

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): as `base_service.spec.md` / `department_service.spec.md` Notes.
- A ticket built directly as `HelpTicket(...)` without `status` gets `"pending"`, without `type` gets `"support"`. To set up an `opened` or `closed` ticket, write the column directly (`status="opened"`); you do not need to go through the service.
- To get a stored status the enum does not know (R3a, R5c), write `status="open"` directly on the row.
- `updated_at` is the database's `now()` (transaction start): inside one test it does not move between writes; do not assert it changes.
- **BUG-1577:** run `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))` first; a **platform admin** closes an `opened` ticket created in the same test; intended `abs(closed_at - created_at) < 60 s` → strict xfail.
- **BUG-1574, BUG-1575:** assert `pydantic.ValidationError` building the schema; the service is never reached → strict xfail.
- **BUG-1578:** a profile with `is_platform_admin=True` and `role=None` → strict xfail.
- **BUG-1863** (workspace PATCH): a `ground-team-manager`, an `owner` and a platform admin (none of them the creator) sending only `title`, `description` or `category` → `HelpTicketForbiddenError`, ticket unchanged → strict xfail. A non-admin owner / manager (not the creator) sending text **plus** `status` → assert a `PermissionError` and nothing written → a plain passing case.
- **BUG-3251** (OQ-66): an `owner` and a `ground-team-manager` (not platform admins, creator or not) move a ticket `pending → opened`, `opened → closed` (`closed_by` = their id), `closed → opened` → strict xfail (today `HelpTicketStatusChangeForbiddenError`). A refused pair (e.g. `pending → closed`) by them → `HelpTicketInvalidTransitionError` → strict xfail too (today the permission error comes first). A plain `ground-team` / `finance` member who created the ticket sending any `status` → `HelpTicketStatusChangeForbiddenError`, nothing written → a plain passing case. A platform admin (not the creator) sending text plus a valid `status` → `HelpTicketForbiddenError`, status unchanged → strict xfail.
- **BUG-3270** (platform PATCH): a platform admin who did not create the ticket sends `description` (alone, and with a valid `status`) → `HelpTicketForbiddenError`, ticket unchanged → strict xfail. The admin's status change alone, and a text change on a ticket the admin created, pass today.
- `update_platform_ticket` does not look at `user.is_platform_admin`: pass any profile to show that the service treats the caller as a platform admin (R2).

## Not specified
- `HelpTicketService.__init__` — stores the manager, no logic.
- `help_ticket_service` — module-level singleton, no logic.

---

## `HelpTicketService.create_ticket(db, *, workspace, user, payload)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /help/tickets`, 201)

**Purpose:** Open a ticket (support request or feedback) for the caller and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace` | `Workspace` | its `id` is the ticket's workspace |
| `user` | `Profile` | its `id` is `created_by` |
| `payload` | `HelpTicketCreate` | `title` 1–200, `description` ≥ 1, `category` ≤ 80 or `None`, `type` `support` (default) / `feedback` |

**Returns:** a `HelpTicketResponse` of the new ticket.

**Rules:**
- **R1.** One ticket is created as DAO `create_with_user` creates it (number `HELP-<year>-<n>`, BUG-1440, BUG-1441), with **`status "pending"`**, `closed_at` and `closed_by` `None`; it is committed (TC1). Every member may open a ticket, whatever the role, and whatever its type. *(Revised 2026-11-26: was `status open`.)*
- **R1a.** The ticket's `type` is the payload's: `support` when the payload leaves it out, `feedback` when sent; it is stored as the plain string (`"support"` / `"feedback"`) and answered as the enum. *(New 2026-11-26.)*
- **R2.** [BUG-1574] (HR-1) `title`, `description`, `category` are stored trimmed; a blank title or description is refused by `HelpTicketCreate` (422), nothing created; a blank category is stored `None`. *(Today: stored as typed; `"   "` accepted for title and description. Verified 2026-11-04.)*
- **R3.** The answer is built from the ticket re-read with its creator (DAO `get_by_id`): every field from the row, `type` included, `creator_name` = the creator's `name`, `None` without a creator. If that re-read finds nothing, the refreshed row is used — **not unit-testable** (revision 2026-11-04).
- **R3a.** A row whose stored `status` or `type` is not a value of its enum (e.g. a legacy `status "open"` that migration 124 did not rewrite, or any string written outside the app) cannot be answered: building the answer raises `pydantic.ValidationError`. This holds for every method that answers a ticket (`list_tickets` R3, `get_ticket` R4, `update_ticket` R7, `update_platform_ticket` R6, `list_platform_tickets` R1, `get_platform_ticket` R1); a write method has already committed when it is raised (TC5). Not reachable through `create_ticket` itself (it always writes `pending`). *(New 2026-11-26; intended — such rows are invalid data.)*
- **R4.** Any error rolls back and reaches the caller unchanged (TC3); commit failure TC4; a failure of the re-read after the commit leaves the ticket saved (TC5).

**Errors:** database errors unchanged (a taken number: `IntegrityError`, DAO R4; unknown user / workspace: `IntegrityError`).

**Side effects:** one `help_tickets` row, committed.

---

## `HelpTicketService.list_tickets(db, *, workspace_id, user, role, status=None, ticket_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /help/tickets`, query `status`, `type`, `skip`, `limit`)

**Purpose:** The workspace's tickets the caller may see.

**Returns:** a `list` of `HelpTicketResponse`, newest first.

**Rules:**
- **R1.** With `role` `owner` or `ground-team-manager`, every ticket of the workspace is listed; with any other role or `None`, only tickets the caller created (verified 2026-11-04 for all four roles and `None`). Order and paging are DAO `list_by_workspace` (BUG-1442). `status` keeps only tickets of that status (`pending`, `opened` or `closed`); `None` = no filter.
- **R1a.** `ticket_type` keeps only tickets of that type (`support` or `feedback`); `None` = no filter. Status, type and the creator restriction of R1 all apply together, before `skip` / `limit`: a page is short only when no more tickets match. *(New 2026-11-26.)*
- **R2.** [BUG-1578] (Q2) A platform admin (`user.is_platform_admin`) sees every ticket of the workspace, whatever `role`, as `get_ticket` R1 (filters of R1, R1a still apply). *(Today: only the tickets they created; a platform admin without a membership sees `[]`. Verified 2026-11-04.)*
- **R3.** Each entry as `create_ticket` R3 (`creator_name` from the loaded creator, `None` without one; `type` included; R3a for unknown stored values).
- **R4.** Read only (TC6).

**Errors:** `DataError` for negative `skip` / `limit` when called directly. `status` / `ticket_type` given as a plain string instead of the enum (direct call only; the API always passes the enum) → `AttributeError` (`.value`).

**Side effects:** none

---

## `HelpTicketService.get_ticket(db, *, workspace_id, ticket_id, user, role)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /help/tickets/{id}`)

**Purpose:** One ticket, if the caller may see it.

**Returns:** a `HelpTicketResponse`.

**Rules:**
- **R1.** A ticket of the workspace is returned when the caller is a platform admin, or has role `owner` / `ground-team-manager`, or created it — whatever the ticket's status or type. Verified 2026-11-04.
- **R2.** Otherwise → `HelpTicketForbiddenError("You do not have access to this help ticket.")` (403 at the API). Verified.
- **R3.** Unknown id, `0`, or another workspace's ticket → `HelpTicketNotFoundError("Help ticket not found.")` (404 at the API), before any access check: the same answer for both. Verified.
- **R4.** A ticket whose creator is gone (`created_by` `NULL`) is visible only to the roles and admins of R1, with `creator_name None` (verified). The answer as `create_ticket` R3 / R3a. Read only (TC6): a refusal does not roll back.

**Errors:** R2, R3.

**Side effects:** none

---

## `HelpTicketService.update_ticket(db, *, workspace_id, ticket_id, user, role, payload)`
**Shape:** update / state-transition
**Persistence:** writes
**Visibility:** public (used by: `PATCH /help/tickets/{id}`)

**Purpose:** Change a ticket's text, or (platform admins only) move it along the status workflow, and save it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user` | `Profile` | its `id` is written as `closed_by` on a close; `user.is_platform_admin` decides who may change status today. Both reads of the flag — the see-right check reached first (`get_ticket` R1, manager `can_access_ticket`) and the status-right flag the service passes — use `getattr(user, "is_platform_admin", False)`: an object without the attribute is accepted and counts as not an admin everywhere (it then needs only `id`). A real `Profile` always has the column (NOT NULL, default `false`). |
| `role` | `str \| None` | the caller's workspace role, for the see-right only |
| `payload` | `HelpTicketUpdate` | only the fields sent count (`exclude_unset`) |

**Returns:** a `HelpTicketResponse`, re-read with its creator.

**Rules:**
- **R1.** The ticket is found as `get_ticket` R1–R3; a refusal (not found / not allowed to see) rolls the session back (TC3: pending changes of the session are discarded too) and reaches the caller unchanged. Verified 2026-11-04.
- **R2.** Only fields sent are applied (`exclude_unset`); `{}` changes nothing (status, stamps and text keep their values). Verified.
- **R2a.** A ticket's `type` cannot be changed: `HelpTicketUpdate` has no `type`, and a `type` key in the request body is dropped by the schema; the stored type stays. *(New 2026-11-26.)*
- **R3.** The ticket's creator may change its `title`, `description` and `category` (whatever their role, whatever the ticket's status — `pending`, `opened` or `closed`). Verified 2026-11-04.
- **R3a.** [BUG-1863] (Q1, owner, OQ-8) Anyone else who may see the ticket (R1: `owner`, `ground-team-manager`, a platform admin) and sends `title`, `description` or `category` in the payload (sent at all, as R2 counts fields — the unchanged value and `category: null` included) gets `HelpTicketForbiddenError("You do not have access to this help ticket.")` (403 at the API); nothing is written and the session is rolled back (TC3). A ticket whose creator is gone (`created_by` `NULL`) has its text changed by nobody. With a `status` in the same payload (D3): an `owner` / `ground-team-manager` (not the creator) who sends text **and** `status` is refused with a 403 `PermissionError` — `HelpTicketStatusChangeForbiddenError` today, `HelpTicketForbiddenError` once BUG-3251 is fixed; assert `PermissionError` — nothing written, the status unchanged too (holds today); a platform admin who is not the creator and sends text plus a valid `status` gets `HelpTicketForbiddenError` and the status does not change either; text plus a transition that is not allowed gets `HelpTicketForbiddenError` or `HelpTicketInvalidTransitionError` (either; nothing written). *(Today: the text change is applied, 200 — and for a platform admin a valid status in the same payload too. Verified 2026-11-04 for a `ground-team-manager`, text only. Revised 2026-11-26: a status change **alone** by owner / manager is governed by R5-1 (BUG-3251, OQ-66).)*
- **R4.** [BUG-1574] (HR-1) A sent `title` / `description` / `category` is stored trimmed; blank title or description refused (422); blank category stored `None`. *(Today: as typed.)*
- **R4a.** [BUG-1575] (P1) `null` for `title` or `description` is refused by `HelpTicketUpdate` (422), nothing written; `category: null` clears the category. *(Today: the flush fails with `IntegrityError` (not-null), rolled back; 400 "Required field is missing." over HTTP. Verified 2026-11-04.)*
- **R5.** *(Rewritten 2026-11-26; D1, OQ-66.)* A platform admin (`user.is_platform_admin` true) may change a ticket's status (holds today). Anyone who is not a platform admin and not `owner` / `ground-team-manager` (by `role`) — a plain member, the ticket's creator included — who sends a `status` value (any of the three, the ticket's current status included) gets `HelpTicketStatusChangeForbiddenError` (403 at the API); nothing is written, text fields in the same payload included, and the session is rolled back (TC3) (holds today). `status: null` or no `status` means "no status change" and is allowed to everyone (status, `closed_at`, `closed_by` keep their values).
- **R5-1.** [BUG-3251] (OQ-66, owner) A caller with `role` `owner` or `ground-team-manager` changes the status exactly as a platform admin does (R5a–R5c, R6; `closed_by` = their id), whether or not they created the ticket; so does the ticket's workspace's owner (`workspaces.owner_user_id` = `user.id`), whatever their membership role (as `help_ticket_manager.spec.md` R5g; BUG-2103). A status change alone is never refused to them for permission. The fix passes the caller's membership role from `HelpTicketService.update_ticket` to `HelpTicketManager.update_ticket` as a new optional keyword `role: str | None = None` (omitted = no role); the workspace owner is read from the ticket's workspace (decided by Claude under the reviewer's delegation (2026-11-26), gap 3). The intended refusal message for everyone else is the manager spec's R5h text (`You may not change the status of this help ticket.`); service cards assert the type only. *(Today: `HelpTicketStatusChangeForbiddenError("Only platform admins may change ticket status.")`, 403, nothing written; the manager takes no `role`.)* The see-right of BUG-2103 / BUG-3250 (workspace owner opens and lists every ticket) is the manager spec's.
- **R5a.** *(New.)* The allowed changes (for a platform admin today; for `owner` / `ground-team-manager` too under BUG-3251) and what they write:
  - `pending → opened`: `status = "opened"`; `closed_at`, `closed_by` are not touched.
  - `opened → closed`: `status = "closed"`, `closed_by = user.id`, `closed_at` = now (R6).
  - `closed → opened`: `status = "opened"`, `closed_at = None`, `closed_by = None`.
  Text fields sent in the same payload are applied with it (subject to R3a). ✅
- **R5b.** *(New; D2.)* Every other change asked by a platform admin is refused with `HelpTicketInvalidTransitionError("Cannot transition from <current> to <target>.")` (400 at the API) — `pending → pending`, `pending → closed`, `opened → opened`, `opened → pending`, `closed → closed`, `closed → pending`; nothing is written (text in the same payload included), the session is rolled back (TC3). ✅
- **R5c.** *(New.)* A platform admin sends a `status` on a ticket whose stored status is not one of the three (e.g. `"open"`) → `HelpTicketInvalidTransitionError("Cannot transition from invalid status 'open'.")` (400), nothing written, rolled back. Without a `status` in the payload such a ticket's text is changed and committed, and then the answer fails as `create_ticket` R3a (`pydantic.ValidationError`, change stays saved, TC5). ✅
- **R5d.** *(New.)* `status` given as a plain string instead of the enum (only possible with a payload built by `HelpTicketUpdate.model_construct`) behaves exactly as the enum of that value (R5–R5c); a string that is not a status value raises `ValueError` from the enum (not the transition error), nothing written, rolled back. Not reachable from the API.
- **R6.** *(Revised 2026-11-26.)* Closing a ticket that is already closed is refused (R5b), so `closed_at` and `closed_by` keep their values (HR-9 holds; BUG-1576 resolved by the workflow change, D2). ✅ [BUG-1577] (P2) `closed_at` is the true moment in UTC whatever the database's time zone. *(Today: written from naive `utcnow()`, 5 hours off under `America/New_York`. Verified 2026-11-04.)*
- **R7.** The change is committed (TC1) and answered as `create_ticket` R3 (TC2). Commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown / other workspace | `HelpTicketNotFoundError` | `Help ticket not found.` |
| not allowed to see it | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| `status` sent by someone who is not a platform admin, `owner` or `ground-team-manager` (R5) | `HelpTicketStatusChangeForbiddenError` | today `Only platform admins may change ticket status.` |
| (today, BUG-3251) `status` sent by an `owner` / `ground-team-manager` who is not a platform admin | `HelpTicketStatusChangeForbiddenError` | `Only platform admins may change ticket status.` |
| transition not in the table (R5b) | `HelpTicketInvalidTransitionError` | `Cannot transition from <current> to <target>.` |
| stored status unknown, `status` sent (R5c) | `HelpTicketInvalidTransitionError` | `Cannot transition from invalid status '<stored>'.` |
| text field sent by someone other than the creator (R3a, BUG-1863) | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| (today) `null` title / description | `sqlalchemy.exc.IntegrityError` (`NotNullViolation`) | — |

**Side effects:** the changed fields, `updated_at` (database), committed. On any error: rolled back, nothing of the call saved.

---

## `HelpTicketService.update_platform_ticket(db, *, ticket_id, user, payload)`
**Shape:** update / state-transition
**Persistence:** writes
**Visibility:** public (used by: `PATCH /platform/help/tickets/{id}`, guarded by `get_platform_admin`) *(New 2026-11-26.)*

**Purpose:** Support moves a ticket of any workspace along the status workflow (and, today, may change its text) and saves it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `ticket_id` | `int` | any workspace's ticket |
| `user` | `Profile` | its `id` is written as `closed_by` on a close; **not checked** to be a platform admin here (R2) |
| `payload` | `HelpTicketUpdate` | only the fields sent count (`exclude_unset`) |

**Returns:** a `HelpTicketResponse` (no `workspace_name`), re-read with its creator.

**Rules:**
- **R1.** The ticket is looked up by id alone, in every workspace. Unknown id or `0` → `HelpTicketNotFoundError("Help ticket not found.")` (404 at the API); the session is rolled back (TC3: other pending changes of the session are discarded) and the error reaches the caller unchanged.
- **R2.** The caller is treated as a platform admin whatever `user.is_platform_admin` says (the endpoint admits platform admins only): `HelpTicketStatusChangeForbiddenError` is never raised here. Status changes follow `update_ticket` R5a, R5b, R5c, R5d, R6 (`closed_by` = `user.id`; BUG-1577 applies). `status: null` or no `status` = no status change.
- **R3.** Only fields sent are applied; `{}` changes nothing; `type` cannot be changed — as `update_ticket` R2, R2a. The ticket's creator (when the caller created it) may change `title`, `description`, `category`.
- **R3a.** [BUG-3270] (P3, per BUG-1863 / OQ-8) A `title`, `description` or `category` sent by a caller who is not the ticket's creator (sent at all; `category: null` and the unchanged value included; a ticket whose creator is gone: by anyone) is refused with `HelpTicketForbiddenError("You do not have access to this help ticket.")`; nothing is written, a `status` in the same payload included; rolled back (TC3). With a `status` in the same payload (D3): text plus a valid transition → `HelpTicketForbiddenError`, status unchanged; text plus a transition that is not allowed → `HelpTicketForbiddenError` or `HelpTicketInvalidTransitionError` (either; nothing written). At the API the endpoint must map the error to 403 *(requires a new `except HelpTicketForbiddenError` in `platform_help.py`)*. A status change without text fields stays allowed. *(Today: the text is applied and committed for any caller, and a valid status in the same payload too. Read, not run.)*
- **R4.** BUG-1574 and BUG-1575 apply as `update_ticket` R4, R4a (same schema).
- **R5.** HR-16: this is the deliberate cross-workspace exception; the answer shows the ticket's own `workspace_id` and nothing else of that workspace.
- **R6.** The change is committed (TC1) and answered as `create_ticket` R3 (TC2; R3a for an unknown stored value). Any error from the lookup, the manager or the flush rolls back and reaches the caller unchanged (TC3); a failing commit follows TC4; a failing re-read after the commit leaves the change saved (TC5). The `refreshed or ticket` fallback (L150) is not unit-testable (revision 2026-11-04).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown id / `0` | `HelpTicketNotFoundError` | `Help ticket not found.` |
| transition not in the table | `HelpTicketInvalidTransitionError` | `Cannot transition from <current> to <target>.` |
| stored status unknown, `status` sent | `HelpTicketInvalidTransitionError` | `Cannot transition from invalid status '<stored>'.` |
| text field sent by someone other than the creator (R3a, BUG-3270) | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| (today) `null` title / description | `sqlalchemy.exc.IntegrityError` (`NotNullViolation`) | — |

**Side effects:** the changed fields, `updated_at` (database), committed. On any error: rolled back.

---

## `HelpTicketService.list_platform_tickets(db, *, status=None, ticket_type=None, search=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `GET /platform/help/tickets`, query `status`, `type`, `search`, `skip`, `limit`; guarded by `get_platform_admin`)

**Purpose:** The support inbox: tickets of every workspace.

**Returns:** a `list` of `PlatformHelpTicketListItem`.

**Rules:**
- **R1.** The tickets, their order, the `status` and `search` filters and paging are DAO `list_platform` (BUG-1442, BUG-1443); `status` keeps only `pending`, `opened` or `closed` tickets, `None` = no filter. Each entry is the ticket's `HelpTicketResponse` fields (`type` included; `create_ticket` R3a for unknown stored values) plus `workspace_name`; `creator_name` is the joined profile's name, else the loaded creator's, else `None`. Verified 2026-11-04 (without `type`).
- **R1a.** `ticket_type` keeps only tickets of that type (`support` / `feedback`), `None` = no filter; it combines with `status` and `search` (all must match), before `skip` / `limit`. *(New 2026-11-26.)*
- **R2.** No access check in the service: the endpoint admits platform admins only. Read only (TC6).

**Errors:** `DataError` for negative `skip` / `limit` when called directly; a plain string for `status` / `ticket_type` → `AttributeError` (direct call only).

**Side effects:** none

---

## `HelpTicketService.get_platform_ticket(db, *, ticket_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /platform/help/tickets/{id}`, guarded by `get_platform_admin`)

**Rules:**
- **R1.** A ticket of any workspace, whatever its status or type → its `PlatformHelpTicketListItem` (as `list_platform_tickets` R1). Verified 2026-11-04.
- **R2.** Unknown id or `0` → `HelpTicketNotFoundError("Help ticket not found.")` (404 at the API). Verified. Read only (TC6).

**Errors:** R2. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 38–45 | create: manager → DAO `create_with_user` (pop `type`, default `"support"` unreachable through the schema; `.value` when an enum; `status "pending"`) → commit | `create_ticket` R1, R1a, R2 |
| 46–48 | refresh; re-read with creator; `refreshed or ticket` (the `None` side not unit-testable); `to_response` (creator name if a creator; enum validation of `status` / `type`) | `create_ticket` R3, R3a |
| 49–51 | any exception → rollback, re-raise | `create_ticket` R4 |
| 65–75 | manager `list_tickets`: role in {owner, ground-team-manager} → all, else `created_by` = user (no admin case, BUG-1578); `status.value` / `ticket_type.value` when not `None`; DAO filters status, type, creator before paging | `list_tickets` R1, R1a, R2, R3, R4, Errors |
| 86–93 | manager `get_by_id_and_workspace`: `None` → not found; `can_access_ticket` (admin, role, creator) → else forbidden | `get_ticket` R1–R4 |
| 105–112 | update: same lookup inside the `try` | `update_ticket` R1 |
| 113–119 | manager `update_ticket` with `is_platform_admin = getattr(user, "is_platform_admin", False)` (no `role` passed, BUG-3251); `exclude_unset`; pop `status`; `None` → no status branch | `update_ticket` R2, R2a, R5 |
| mgr 171–175 | status sent and not admin → `HelpTicketStatusChangeForbiddenError` (role not consulted, BUG-3251) | `update_ticket` R5, R5-1, R3a (D3) |
| mgr 176–180 | status is the enum / a raw string → enum (bad string → `ValueError`) | `update_ticket` R5d |
| mgr 181–186 | stored status not an enum value → invalid-status transition error | `update_ticket` R5c |
| mgr 187–191 | target not in the allowed set of the current status (`.get(…, set())` default unreachable: all three keys present) → transition error | `update_ticket` R5b, R6 |
| mgr 192–195 | target `closed` → stamp `closed_at` (naive `utcnow`, BUG-1577), `closed_by` | `update_ticket` R5a, R6 |
| mgr 196–201 | target `opened` and current `closed` → clear stamps; `pending → opened` → nothing else | `update_ticket` R5a |
| mgr 203 | DAO `update` with a dict (writes `None` too, BUG-1575); no creator check for text (BUG-1863, BUG-3270) | `update_ticket` R3, R3a, R4, R4a; `update_platform_ticket` R3a |
| 120–123 | commit; refresh; re-read; response (`refreshed or ticket` at 123 not unit-testable) | `update_ticket` R7, R5c |
| 124–126 | any exception → rollback, re-raise | `update_ticket` R1, R3a, R4a, R5, R5b, R5c, R7 |
| 137–139 | platform update: DAO `get_by_id` (any workspace); `None` → `HelpTicketNotFoundError` inside the `try` | `update_platform_ticket` R1, R5 |
| 140–146 | manager `update_ticket` with `is_platform_admin=True` (status-change refusal unreachable) | `update_platform_ticket` R2, R3, R3a, R4 |
| 147–150 | commit; refresh; re-read; response (`refreshed or ticket` at 150 not unit-testable) | `update_platform_ticket` R6 |
| 151–153 | any exception → rollback, re-raise | `update_platform_ticket` R1, R3a, R6 |
| 165–172 | platform list via manager → DAO `list_platform` (status, type, search filters); `_to_platform_item` (`creator_name or base.creator_name`) | `list_platform_tickets` R1, R1a, R2 |
| 180 | platform get: `None` → not found | `get_platform_ticket` R1, R2 |
| 183 | module singleton | Not specified |

## Gap log
G1 (help_ticket_service.cases.md gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-26) — `update_ticket` R5-1 [BUG-3251]: the workspace's `owner_user_id` also has the status right (as manager spec R5g); the fix passes the membership role as new optional keyword `role: str | None = None` (omitted = no role); intended refusal message = manager spec R5h, service cards assert the type only.
G2 (help_ticket_service.cases.md gap 4) — Fact — `update_ticket` Inputs `user`: the see-right check (`can_access_ticket`) and the service's status flag both read `getattr(user, "is_platform_admin", False)`; a profile-like object without the attribute is accepted and counts as not an admin.
G3 (help_ticket_service.cases.md gap 5) — Fact — covered by G1 (R5h message named in R5-1; cards assert type only). No further change.
