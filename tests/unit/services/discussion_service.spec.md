# Spec — `app/services/discussion_service.py`

> **Status:** APPROVED (2026-11-04: Q1 answered → BUG-1694, decided by Claude under the reviewer's delegation (2026-11-04); Q2 / OQ-5 answered by the owner (2026-11-04) → BUG-1867, BUG-1868). Stays APPROVED after fill-gaps 2026-11-04 (Gap log at the end).
> **Source commit:** e48a092
> **Revision 2026-11-04 (verifier round 3, R3-2):** help-ticket rule made explicit for suspended members (Facts, "Who may open a help ticket" (2)): only an active member's `owner` / `ground-team-manager` role counts; the creator counts whatever their status; a platform admin needs no membership — decided by Claude under the reviewer's delegation (2026-11-04). Rules R5a, R11a, R9a point to it; no rule text changed. The help ticket code reads the role without the status (BUG-1885). Cards: add a suspended-`owner` (and/or suspended-`ground-team-manager`) refused card for `list` R5a and `create` R11a (strict xfail on BUG-1868), and a suspended-creator allowed card on `create` R11a (plain pass today).
> **Revision 2026-11-04 (apply-review, OQ-5):** the owner answered OQ-5 (and Q2 under it) with the suggested answer: a thread follows its record's own visibility; who may not open the private project or the help ticket gets 404 and cannot post. `list` R5, R5a and `create` R11, R11a rewritten from today's behaviour to the intended one and tagged; `list` R5b and `create` R11b added (a project component's thread follows its project, as the project pages do: `require_component_access`); `create` R9a added (mentions — BUG-1879, decided by Claude as a consequence of the owner's OQ-5 answer (2026-11-04)); `list` gains a `user_id` input; `create` R2 check order extended. No other rule changed. Cards to revise: DSS-L-15, DSS-L-16, DSS-C-28, DSS-C-29, plus new cards for R5b, R11b and the mention rule R9a.

> **Form.** As `tests/unit/services/department_service.spec.md`. This service has **no manager** and does **not** inherit `BaseService`; it calls `discussion_dao` and `notification_service` directly and commits itself — with **no `try` and no rollback**, so it departs from TC3 / TC4 (rules D1–D4 below). Below it: `tests/unit/dao/discussion.spec.md` (APPROVED), `tests/unit/services/notification_service.spec.md` (APPROVED; `fan_out_mentions`, `humanize_mention_preview`).

> **Routed here and written as rules:** discussion DAO **P1** / FU-1 (a) (decided under delegation: the service looks the record up first; 404 for an unknown or other-workspace record and for a soft-deleted one) → BUG-1686, BUG-1687. FU-1 (b) → **OQ-5**, answered by the owner (2026-11-04) → BUG-1867, BUG-1868. FU-1 (c): checked — `fan_out_mentions` notifies only active members of the workspace (notification spec R1, R2). FU-1 (d) → D1–D4. Notification service FU-1: (a) **BUG-1536** `_extract_mentions` R2; (b) **BUG-1534** `create` R9; (c) cosmetic, cited only.
>
> **Standing decisions applied here (not asked again):** HR-16: a link to another workspace's row is invalid data, refused as "not found". A soft-deleted parent hides its children (discussion DAO standing decisions). **OQ-5** (answered by the owner (2026-11-04)): attachments, discussions and calendar entries follow the record's own visibility; a member who cannot open the private project or help ticket gets 404.
>
> **Verified by running** (`h.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3d\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): a root on `project` `999999` (no such project) is stored and listed (`([id], 1)`); a message mentioning an active member, its author and an unknown id gives two notifications (the member and the author, BUG-1535) and none for the unknown id; **every refusal raises `TypeError: APIException.__init__() missing 2 required positional arguments: 'error_type' and 'title'`** — parent id `0`, a reply to a reply, a reply on another entity, a parent of another workspace; a reply to a root is stored; `list` with the string `"project"` raises `AttributeError`; `@[১২]` is accepted (BUG-1536 territory); a create whose author id does not exist raises `IntegrityError` 23503 and leaves the session inactive (no rollback), and the test's own rollback then discards an uncommitted setup row. **Not run:** anything over HTTP; the intended behavior of any bug rule.

## Review
> Q1 answered 2026-11-04 (decided by Claude under the reviewer's delegation (2026-11-04)). Q2 (**OWNER**, access) answered by the owner (2026-11-04) under OQ-5 in `docs/testing/owner-questions.md`, applied 2026-11-04.

### Quick list
| # | What the code does today, in plain words | Decided |
|---|---|---|
| Q1 | Every refused reply (missing parent, reply to a reply, wrong record) crashes with a server error instead of 404 / 400 | bug — 404 / 400 as written in the code → 🐞 BUG-1694 |
| Q2 | **OWNER** — a help ticket's discussion can be read and posted to by any member, though only its creator and managers may open the ticket | bug — the thread follows the ticket's access (answered by the owner (2026-11-04), OQ-5) → 🐞 BUG-1868; private projects → 🐞 BUG-1867 |

### House-rule violations — applied automatically

- **HR-16** `create` R3, `list` R2 — the record named by `entity_type` / `entity_id` is never looked at: a message can be posted on an unknown record or on another workspace's record id (stored under the caller's workspace), and its thread is listed (verified for an unknown project). Intended (discussion DAO P1): `create` and `list` first find the record in the caller's workspace by the table of its `entity_type` (Overview); unknown or another workspace's → `NotFoundError` 404 `Record not found` (wording chosen here; reviewer may change), nothing written.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1686 (pattern `cross-workspace-link-not-refused`; decided in discussion DAO P1). Rules: `create` R3, `list` R2.
- **HR-4** `create` R4, `list` R3 — a soft-deleted record (projects, work orders, machines, inventory rows: `is_deleted = True`; items: `is_active = False`) keeps a live thread: it is listed and posted to. Intended (discussion DAO P1, standing decision): treated as not found, the same 404, nothing written.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1687 (pattern `write-to-soft-deleted-related-row`; decided in discussion DAO P1). Rules: `create` R4, `list` R3.

Existing bugs written as rules here, no new ID: **BUG-1534** `create` R9 (the preview names only workspace members; the service passes its workspace), **BUG-1536** `_extract_mentions` R2 (ASCII digits only). Reached and cited, one pass-through case each: **BUG-1535** (the author is not notified of their own mention), **BUG-1438**, **BUG-1439**, **BUG-1490** (thread order and reply loading, DAO).

Checked and **not** violated: **HR-1** — a blank message is refused by `DiscussionCreate` (`Message cannot be empty`); a message is free text, not a name, and is stored as typed. **HR-2, HR-3, HR-8** — no uniqueness, grouping or `LIKE`. **HR-5, HR-6** — the DAO's (BUG-1438, BUG-1439). **HR-7** — `GET /discussions/` requires `skip >= 0`, `1 <= limit <= 200`. **HR-9** — append-only, no audit column. **HR-10** — a new message changes no state; the mention fan-out runs once per new message. **HR-11 … HR-15** — none applies. **HR-16** on the parent — found only in the caller's workspace (today a `TypeError`, Q1; 404 intended); on mention recipients — only active members (notification spec); on preview names — BUG-1534.

**Permission checks:** today none beyond an active membership of the workspace (or platform admin, who may enter any workspace): any member may read and post on any record's thread, whatever the record's own visibility. Intended (OQ-5, answered by the owner (2026-11-04)): a private project's thread, and its components' threads, only for those who may open the project (BUG-1867); a help ticket's thread only for those who may open the ticket (BUG-1868). Every other record type keeps membership as its only check (the owner's answer names private projects and help tickets; no other `entity_type` has its own visibility rule today).

### New questions

### Q1. Every refused reply crashes with a server error — 🐞 BUG-1694
**Background:** A reply is checked before it is stored: its parent must exist in the workspace, must itself be a top-level message (one level of replies), and must be on the same record. Each refusal is raised as `APIException(status_code=…, detail=…)`, but that class also requires `error_type` and `title`; the ready-made subclasses `NotFoundError` and `ValidationError` in `app/core/exceptions.py` fill them in.
**What happens today:** all four refusals raise `TypeError` instead (verified): nothing is stored, and the API answers 500. The intended status and text are only visible in the code.
**Example:** In the web app a user answers a reply (if the UI allowed it) or a reply whose parent was meanwhile deleted: "Internal server error" instead of "Replies can only be one level deep" / "Parent discussion not found".
**Rules affected:** `create` R5, R6, R7
**Suggested answer:** `bug — refusals as written: missing parent (unknown id, 0, another workspace) → NotFoundError 404 "Parent discussion not found"; parent is a reply → ValidationError 400 "Replies can only be one level deep"; parent on another record → ValidationError 400 "Reply must be on the same entity as the parent"; nothing written`. (`ValidationError` is the 400 class of `app/core/exceptions.py`, body type `validation_error`.) Alternative: plain `HTTPException` with the same status and detail, as most services.
**Answer:** bug, as suggested: missing parent (unknown id, another workspace's) and parent id `0` → `NotFoundError` 404 "Parent discussion not found"; a reply to a reply, or a reply on another record → `ValidationError` 400 with the two existing messages; nothing written — decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1694 (new; pattern `exception-constructor-misuse` — no existing bug had this root cause). Classes from `app/core/exceptions.py`. Rules: `create` R5, R6, R7.

### Q2. OWNER — help ticket discussions are open to every member (OQ-5) — 🐞 BUG-1868
**Background:** Help tickets carry a discussion (`entity_type = support_ticket`, shown on the Help page and the platform support page). A member may open only their own tickets; `owner` and `ground-team-manager` see all (help ticket service spec, verified there). The discussion endpoints check nothing but membership. OQ-5 asks the same for private projects; its suggested answer ("discussions follow the record's own visibility") would cover this too.
**What happens today:** any member can list and post on the discussion of any help ticket id of the workspace (read; ticket ids are sequential).
**Example:** A ground-team member calls `GET /discussions/?entity_type=support_ticket&entity_id=<a colleague's ticket>` and reads the conversation between the colleague and the platform team.
**Rules affected:** `list` R5a, `create` R11a (and, for private projects under OQ-5 itself, `list` R5, R5b, `create` R11, R11b)
**Suggested answer:** `bug — a ticket's discussion follows the ticket's access: who cannot open the ticket gets 404 on its discussion`. Alternative: `intended — discussions are workspace-wide`.
**Answer:** bug — answered by the owner (2026-11-04), OQ-5 in `docs/testing/owner-questions.md`: attachments, discussions and calendar entries follow the record's own visibility; a member who cannot open the private project or help ticket gets 404 / does not see it.
**Resolution:** 🐞 BUG-1868 (help tickets; pattern `child-ignores-parent-visibility`, new) and 🐞 BUG-1867 (private projects and their components, same pattern). Who may open a help ticket: the help ticket access rule (`HelpTicketManager.can_access_ticket`): its creator; a caller whose role in the workspace is `owner` or `ground-team-manager`; a platform admin. Who may open a private project: the project pages' rule (`ProjectManager.can_access_project`). Refusal: the same `NotFoundError` 404 `Record not found` as BUG-1686, so a hidden record cannot be told from a missing one; nothing written. Rules: `list` R5, R5a, R5b; `create` R2, R11, R11a, R11b.

## Overview
`DiscussionService` runs the comment threads attached to records (orders, projects, components, machines, inventory rows, items, help tickets): a page of a record's top-level messages with their replies, and posting a message or a one-level reply. Posting also notifies the people mentioned with `@[<profile id>]` tokens, in the same commit. `GET` and `POST /discussions/` call it. It protects reply depth and keeps a reply on its parent's record; it does not look at the record itself (BUG-1686, BUG-1687) or at who may see it (BUG-1867, BUG-1868; OQ-5).

**Callables:** 3 specified · 1 not specified
**Externals to mock:** none (notifications are rows in the database; their live stream needs a real commit and is not reached).
**Integration-only behavior:** the RFC 7807 body the API makes of an `APIException` subclass (Q1); `entity_type` parsing into `DiscussionEntityType` and `skip`/`limit` bounds at the endpoint; schema validation (400 today, BUG-461); `DiscussionResponse` rendering of `author` and nested `replies` (BUG-1490).

**Record of each `entity_type`** (for BUG-1686, BUG-1687; every table has `workspace_id`):
| `entity_type` | Table | Soft-deleted when |
|---|---|---|
| `purchase_order` | `purchase_orders` | — (no soft delete) |
| `transfer_order` | `transfer_orders` | — |
| `expense_order` | `expense_orders` | — |
| `work_order` | `work_orders` | `is_deleted = True` |
| `sales_order` | `sales_orders` | — |
| `project` | `projects` | `is_deleted = True` |
| `project_component` | `project_components` | — |
| `machine` | `machines` | `is_deleted = True` |
| `inventory` | `inventory` | `is_deleted = True` |
| `item` | `items` | `is_active = False` |
| `support_ticket` | `help_tickets` | — |

**Facts for the test designer**
- Import: `from app.services.discussion_service import DiscussionService, discussion_service, _extract_mentions`. `DiscussionService()` takes no arguments. The endpoint calls `list` positionally and `create` by keyword.
- `entity_type` of `list` must be a `DiscussionEntityType` (`app.models.enums`); a plain string raises `AttributeError` (verified). `DiscussionCreate(entity_type, entity_id, message, parent_id=None)`; `message` must contain a non-space character (`ValueError` "Message cannot be empty" inside `pydantic.ValidationError`).
- Table `discussions`: discussion DAO spec, Model facts. Notifications: notification service spec (`notifications` rows with `source_type = "discussion"`, `source_id` = the message id).
- Members: `WorkspaceMember(workspace_id, user_id, role, status="active")`; profiles and workspaces from `tests/unit/factories.py`.
- **Private project** (R5, R11; gap G1): `projects.visibility` (`String(20)`, NOT NULL, default and `server_default` `'workspace'`) holds a `ProjectVisibilityEnum` value (`app.models.enums`): `"workspace"` (every member sees it) or `"invited_only"` — **`"invited_only"` is the private value**. There is no value `"private"`. The project code (`ProjectManager.can_access_project`) treats any value other than `"workspace"` as restricted: then only the workspace owner, an active member with a privileged role, the project's `created_by`, or a `project_members` row may open it. Build a private project as `Project(..., visibility=ProjectVisibilityEnum.INVITED_ONLY.value)`. Today the discussion service reads none of this (R5, R11).
- **Who may open a private project** (BUG-1867; the rule of `ProjectManager.can_access_project`, which the project pages apply): visibility `"workspace"` → every caller; otherwise only (1) the workspace owner (`workspaces.owner_user_id`), (2) an `active` member of the workspace whose role is `owner` or `ground-team-manager`, (3) the project's `created_by`, (4) a person with a `project_members` row for that project in that workspace. Anyone else — e.g. an active `ground-team` member who is none of these — may not. A project component (`entity_type = project_component`) is opened under its project's rule (`ProjectManager.require_component_access`).
- **Who may open a help ticket** (BUG-1868; the rule of `HelpTicketManager.can_access_ticket`): (1) a platform admin (`profiles.is_platform_admin = True`; platform admins may act in any workspace without a membership), (2) a caller with an **`active`** membership of the workspace whose role is `owner` or `ground-team-manager` — a `suspended` (or `invited`) owner or ground-team-manager does not count and is refused (404) unless (1) or (3) applies, (3) the ticket's `created_by`, whatever their membership status. Anyone else may not. *(Suspended members, verifier R3-2: decided by Claude under the reviewer's delegation (2026-11-04), for consistency with the project rule, where only an active member's role counts and the creator counts whatever their status. Over the API a suspended member who is not a platform admin never reaches this service: `get_current_workspace` answers 403 "You do not have access to this workspace" first — the same today for the ticket pages, so a suspended creator can open neither the ticket nor its thread; the rule above is the service's own check.)* Applies to R5a, R11a and the mention rule R9a (for the mentioned person: a suspended member is not notified today either, `fan_out_mentions` notifying active members only). `HelpTicket(workspace_id, created_by, title, description, …)`: help ticket DAO spec for the minimum row.
- The service learns the caller from `user_id` (both methods; `list` gains it, R5) and reads the caller's role and platform-admin flag itself from `user_id` and `workspace_id`, as `ProjectManager` does (*fix detail; the cards pass only `user_id`*).

**Notes for the test designer**
- Session: the `db` fixture makes `db.commit()` a savepoint release (department spec Notes). **Difference (D3):** the service never rolls back. After an error inside `create`, the session may need a rollback: call `db.rollback()` in the test before asserting with queries.
- **BUG-1694:** today every refusal raises `TypeError` → strict xfail written to the intended exception class (`app.core.exceptions.NotFoundError` / `ValidationError` — not `pydantic.ValidationError`), `.status_code` and `.detail`.
- **BUG-1867, BUG-1868 (R5, R5a, R5b, R11, R11a, R11b; OQ-5 answered):** for each, a refused caller (intended 404, today served → strict xfail) and the allowed callers (each kind listed in Facts, at least one card per kind). `create` already takes `user_id`, so its allowed-caller cards pass today and after the fix (plain pass). `list` has no `user_id` today (a call with it raises `TypeError`), so every `list` card that passes `user_id` — allowed callers included — is a strict xfail on BUG-1867 / BUG-1868 until the fix; the other `list` cards keep today's call without it, so they keep regression protection now and gain `user_id` (a one-line change) when the fix lands. A `workspace`-visibility project stays open to every member (plain pass on `create`).
- **BUG-1686, BUG-1687:** build the record of the type (one type per table shape is enough: `project` with `is_deleted`, `item` with `is_active`, `purchase_order` without soft delete, and an id of another workspace), commit, then call → today stored / listed → strict xfail.
- **BUG-1879 (R9a):** a private project thread; the author may open it; mention one member who may (e.g. a project member) and one active `ground-team` member who may not → intended: a notification for the allowed member, none for the other → strict xfail. Do not mention the author (keeps BUG-1535 out of the card); assert per recipient. Same with a help ticket (the creator mentions a plain member). A `"workspace"` project with the same mentions notifies both (plain pass).
- **BUG-1534:** assert on the stored `preview` of the mention notification: an `@[<id>]` of a profile whose only membership is in another workspace reads `@User <id>` → strict xfail. **BUG-1536:** `_extract_mentions("@[১২]")` → intended `[]` → strict xfail.

## Not specified
- `discussion_service` — module-level singleton, no logic. `_MENTION_RE` — module constant, covered by `_extract_mentions`.

---

### Transaction rules of this service (D)
- **D1.** A successful `create` is committed once, the message and its mention notifications together (TC1): both survive a later rollback of the session. The returned message is re-read after the commit (TC2).
- **D2.** A refusal (parent checks; [BUG-1686] [BUG-1687] the record check; [BUG-1867] [BUG-1868] the visibility check) is raised before anything is written, without a rollback: other uncommitted changes of the session stay pending.
- **D3.** An error after the message is flushed (the notifications, the commit) reaches the caller unchanged, and the service does **not** roll back: nothing is committed, the session is left for the caller (inactive after a database error, verified); the API discards the request's session. *(Differs from TC3 / TC4; no observable effect over the API.)*
- **D4.** `list` neither commits nor rolls back (TC6).

---

## `_extract_mentions(message)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `create`)

**Returns:** a `list[int]` of profile ids, in the order they appear, duplicates kept.

**Rules:**
- **R1.** Every `@[<digits>]` token gives one id: `"hi @[5] and @[12] @[5]"` → `[5, 12, 5]`; no token → `[]`. Malformed tokens (`@[]`, `@[a1]`, `@5`, `@[ 5]`, `@[-5]`) give nothing; leading zeros are read as the number (`@[007]` → `7`).
- **R2.** [BUG-1536] Only ASCII `0-9` make a token: `@[১২]` and `@[١٢]` give nothing. *(Today: `[12]`, as notification spec P1.)*

**Errors:** none. **Side effects:** none

---

## `DiscussionService.list(db, workspace_id, entity_type, entity_id, skip=0, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /discussions/?entity_type=…&entity_id=…&skip=…&limit=…`)

**Inputs (intended, BUG-1867 / BUG-1868):** a new keyword-only `user_id` (int, required): the caller (`current_user.id`; the endpoint already has `current_user`). *(requires new parameter `user_id`; today `list` has no caller identity.)*

**Returns:** `(items, total)` as the DAO's `get_by_entity` returns it.

**Rules:**
- **R1.** The answer is `discussion_dao.get_by_entity` for the workspace, `entity_type.value`, `entity_id`, `skip`, `limit`, unchanged: top-level messages only, `total` counted before paging, order and replies as the DAO's R1–R7 (BUG-1438, BUG-1439, BUG-1490). Defaults `skip=0`, `limit=50`.
- **R2.** [BUG-1686] (HR-16) An unknown record, or a record of another workspace, → `NotFoundError` 404 `Record not found`. *(Today: `([], 0)` or the thread stored under that id. Verified for an unknown project.)*
- **R3.** [BUG-1687] (HR-4) A soft-deleted record (Overview table) → the same 404. *(Today: its thread is listed.)*
- **R4.** Read only (D4).
- **R5.** [BUG-1867] (OQ-5) The thread of a private project (`visibility = "invited_only"`, Facts) is returned only to a caller who may open the project (Facts, "Who may open a private project"); anyone else gets `NotFoundError` 404 `Record not found`, as R2. A project with visibility `"workspace"` is returned to every member. Checked after R2, R3. *(Today: any member gets it, and `list` has no `user_id`. Answered by the owner (2026-11-04).)*
- **R5a.** [BUG-1868] (OQ-5, Q2) The thread of a help ticket (`support_ticket`) is returned only to a caller who may open the ticket (Facts, "Who may open a help ticket": platform admin, role `owner` or `ground-team-manager`, its creator); anyone else gets the same 404. *(Today: any member gets the thread of any ticket of the workspace. Answered by the owner (2026-11-04).)*
- **R5b.** [BUG-1867] (OQ-5) The thread of a project component (`project_component`) follows its project: returned only to a caller who may open the component's project (R5); anyone else gets the same 404. A component of a `"workspace"` project is open to every member. *(Today: any member gets it.)*
- **R5c.** Every other `entity_type` has no visibility check beyond membership (OQ-5 names private projects and help tickets only).

**Errors:** [BUG-1686] [BUG-1687] [BUG-1867] [BUG-1868] `NotFoundError` 404 `Record not found`; `DataError` for a negative `skip` / `limit` (DAO).

**Side effects:** none

---

## `DiscussionService.create(db, workspace_id, user_id, data)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /discussions/`, 201)

**Purpose:** Post a message or a reply on a record and notify the people it mentions.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | caller's workspace; stored on the message |
| `user_id` | int | the author (`current_user.id`); stored as `user_id`, actor of the notifications |
| `data` | `DiscussionCreate` | `entity_type` (enum), `entity_id`, `message` (non-blank), `parent_id` (optional) |

**Returns:** the new `Discussion`, committed and re-read (D1).

**Rules:**
- **R1.** One message is stored with the workspace, `entity_type.value`, `entity_id`, `user_id`, `message` as typed and `parent_id` (`None` = top level), as DAO `create` R1; committed (D1).
- **R2.** Checks run in this order: the record (R3, R4), then whether the caller may open it ([BUG-1867] [BUG-1868] R11, R11a, R11b), then, for a reply, the parent (R5–R7). The first that fails is raised; nothing is written.
- **R3.** [BUG-1686] (HR-16) An unknown record, or one of another workspace → `NotFoundError` 404 `Record not found`, nothing written. *(Today: stored. Verified for an unknown project id.)*
- **R4.** [BUG-1687] (HR-4) A soft-deleted record → the same 404, nothing written. *(Today: stored.)*
- **R5.** [BUG-1694] (Q1) With `parent_id` set (including `0`): no message of that id in the caller's workspace (unknown, `0`, another workspace's) → `NotFoundError` (status 404) with detail `Parent discussion not found`, nothing written (D2). *(Today: `TypeError`. Verified.)*
- **R6.** [BUG-1694] (Q1) The parent is itself a reply → `ValidationError` from `app/core/exceptions.py` (status 400, `error_type` `validation_error`) with detail `Replies can only be one level deep`, nothing written. *(Today: `TypeError`. Verified.)*
- **R7.** [BUG-1694] (Q1) The parent is on another record (`entity_type` or `entity_id` differs) → `ValidationError` (status 400) with detail `Reply must be on the same entity as the parent`, nothing written; checked after R6. *(Today: `TypeError`. Verified.)*
- **R8.** A reply to a top-level message of the same record is stored with that `parent_id` (verified).
- **R9.** Mentions: the ids of `_extract_mentions(message)` are passed to `notification_service.fan_out_mentions` with the workspace, `actor_user_id = user_id`, the message's `entity_type` value and `entity_id`, `source_id` = the new message's id, and the preview `humanize_mention_preview(db, message)` — [BUG-1534] with the caller's workspace, so only workspace members are named *(today: no workspace; any profile on the platform is named)*. Who is notified is the notification service's: each distinct active member once; others skipped (its R1, R2); the author too today (BUG-1535). Verified: two notifications for a member and the author, none for an unknown id.
- **R9a.** [BUG-1879] (OQ-5 consequence) On the thread of a private project, of a component of one, or of a help ticket, a mentioned person who may not open that record (Facts: the same rules as R11, R11a, R11b, applied to the mentioned person instead of the author) gets no notification, so no preview reaches them; the other mentioned people are notified as R9. When nobody mentioned may open it, no notification row is written; the message itself is still stored. On every other record, and on a `"workspace"` project, R9 is unchanged. *(Today: every active member mentioned is notified with the preview. Decided by Claude as a consequence of the owner's OQ-5 answer (2026-11-04).)* *(The filter may sit in this service or be passed to `fan_out_mentions`; the fix chooses.)*
- **R10.** No token → no notification and no preview is built.
- **R11.** [BUG-1867] (OQ-5) A message or reply on a private project's thread (`visibility = "invited_only"`, Facts) is stored only for an author (`user_id`) who may open the project (Facts); anyone else gets `NotFoundError` 404 `Record not found`, nothing written, no notification (D2). On a `"workspace"` project every member may post. *(Today: any member may post. Answered by the owner (2026-11-04).)*
- **R11a.** [BUG-1868] (OQ-5, Q2) A message or reply on a help ticket's thread (`support_ticket`) is stored only for an author who may open the ticket (Facts: platform admin, role `owner` or `ground-team-manager`, its creator); anyone else gets the same 404, nothing written. *(Today: any member may post on any ticket of the workspace. Answered by the owner (2026-11-04).)*
- **R11b.** [BUG-1867] (OQ-5) A message on a project component's thread follows its project (R11): the same 404 for an author who may not open the component's project. *(Today: stored.)*
- **R11c.** Every other `entity_type` has no visibility check beyond membership.
- **R12.** Errors inside the write follow D3; refusals D2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1686] [BUG-1687] record unknown / other workspace / soft-deleted | `NotFoundError` 404 | `Record not found` |
| [BUG-1867] [BUG-1868] the author may not open the private project (or its component) / the help ticket | `NotFoundError` 404 | `Record not found` |
| [BUG-1694] parent missing (unknown, `0`, other workspace) | `NotFoundError` 404 (today `TypeError`) | `Parent discussion not found` |
| [BUG-1694] parent is a reply | `ValidationError` 400 (today `TypeError`) | `Replies can only be one level deep` |
| [BUG-1694] parent on another record | `ValidationError` 400 (today `TypeError`) | `Reply must be on the same entity as the parent` |
| unknown author id | `IntegrityError` 23503 (DAO), no rollback | — |

**Side effects:** one `discussions` row and zero or more `notifications` rows, committed together; nothing on a refusal.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 17, 21 | `@[\d+]` tokens, Unicode digits (BUG-1536) | `_extract_mentions` R1, R2 |
| 34–36 | DAO `get_by_entity` with `.value`; record not checked (BUG-1686, BUG-1687); no visibility check (BUG-1867, BUG-1868) | `list` R1–R5c |
| 46 | `parent_id is not None` (`0` included) | `create` R5, R8 |
| 47–52 | parent not found in workspace → `APIException` misuse → `TypeError` (BUG-1694) | `create` R5 |
| 53–57 | parent is a reply → `TypeError` (BUG-1694) | `create` R6 |
| 59–63 | parent on another entity → `TypeError` (BUG-1694) | `create` R7 |
| 65–73 | DAO create, flushed; record not checked (BUG-1686, BUG-1687); no visibility check (BUG-1867, BUG-1868) | `create` R1, R3, R4, R11–R11c |
| 76–77 | `if mentioned_ids`; recipients not filtered by the record's visibility (BUG-1879) | `create` R9, R9a, R10 |
| 78–91 | fan-out with preview (no workspace, BUG-1534) | `create` R9 |
| 93–95 | commit, refresh, return; no `try` / rollback | `create` R12; D1–D3 |
| 98 | module singleton | Not specified |

## Gap log
G1 (discussion_service.cases.md gap 1) — Fact — a private project is `projects.visibility = "invited_only"` (`ProjectVisibilityEnum.INVITED_ONLY`); `"private"` is not a value the code uses. Added under Facts for the test designer; R5, R11 point to it. No rule changed; OQ-5 still parked (2026-11-04).
OQ-5 mentions (2026-11-04, not a gap) — `create` R9a → BUG-1879, decided by Claude as a consequence of the owner's OQ-5 answer (2026-11-04): a mentioned person who may not open the private project / component / help ticket is not notified and gets no preview. New card(s) needed for R9a.
OQ-5 (apply-review 2026-11-04, not a gap) — owner's answer applied: `list` R5, R5a, R5b, R5c, `create` R2, R11, R11a, R11b, R11c; BUG-1867, BUG-1868. Cards DSS-L-15, DSS-L-16, DSS-C-28, DSS-C-29 to be rewritten; new cards needed for R5b, R5c, R11b, R11c and the allowed-caller kinds.
