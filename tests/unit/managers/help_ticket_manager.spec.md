# Spec — `app/managers/help_ticket_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every question was already answered upstream: OQ-8, OQ-5, BUG-1578, BUG-1885.)
> **Source commit:** e48a092

> **Below / above.** Callers: `tests/unit/services/help_ticket_service.spec.md` (APPROVED, OQ-8 applied), whose FU-1 this spec answers; `tests/unit/services/discussion_service.spec.md` (APPROVED; Facts "Who may open a help ticket"). Below: `tests/unit/dao/help_ticket.spec.md` (APPROVED: numbering, lists, platform reads, **Model facts**) and `tests/unit/dao/base.spec.md` (`update` R1–R9). DAO rules are **cited, not restated**. The service spec already holds one case per API-visible outcome; the cases here are the manager's own (refusals before any write, what reaches the DAO, the response mapping).
>
> **Standing decisions applied here (not asked again):** OQ-8 (owner, 2026-11-04: only the creator edits title / description / category; owner, ground-team-manager and platform admins may still close / reopen) → BUG-1863. OQ-5 (owner: attachments, discussions and calendar entries follow the record's visibility) → BUG-1868 (discussions), **BUG-1950** (attachments of a help ticket, new, below). BUG-1578 (platform admin list), BUG-1885 (suspended role; fix in the endpoint). HR-16: the platform inbox is the deliberate cross-workspace exception, for platform admins only.
>
> **Read, not run, here.** The service spec ran every outcome below through the service on `marker_test` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`); nothing new needed running. Checked in the code for this spec: `AttachmentManager` never calls `can_view_all_tickets` / `can_access_ticket` (only `help_ticket_dao.get_by_id_and_workspace`, `app/managers/attachment_manager.py:194`).

## Review
> All questions answered upstream; nothing pending.

### House-rule violations — applied automatically
- **HR-9** `update_ticket` R7 — closing an already closed ticket rewrites `closed_at` / `closed_by`. Already logged from the service spec.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1576 (existing; no new ID). Rules: `update_ticket` R7.

### Precedent matches — all applied (decided upstream)
- **BUG-1577** (`update_ticket` R8) — `closed_at` written from naive `utcnow()` into a `timestamptz` column; intended: aware UTC (service spec P2).
- **BUG-1578** (`list_tickets` R2) — platform admin's workspace list (service spec Q2).
- **BUG-1863** (`update_ticket` R3, R4) — only the creator edits text (owner, OQ-8).
- **BUG-1574, BUG-1575** — schema fixes (`HelpTicketCreate` / `HelpTicketUpdate`); the manager is never reached once fixed. Rules and cases live in the service spec (`create_ticket` R2, `update_ticket` R4, R4a); here only `update_ticket` R9 states what the manager does with a `null` today.
- **BUG-1885** (`can_access_ticket` R4) — a suspended owner's role still counts; the fix is in the endpoint's role lookup (`_workspace_role`), so this manager's rule does not change.

### Routed: who may attach a file to a ticket — 🐞 BUG-1950 (per OQ-5, owner)
**Facts (read in the code):** `AttachmentManager` finds a `support_ticket` parent with `help_ticket_dao.get_by_id_and_workspace` only. It never calls `can_access_ticket`. So any active member of the workspace may list, sign, confirm and delete attachments on any ticket of the workspace, including another member's ticket they cannot open (403 on the ticket page). The help ticket service spec's FU-1 and `docs/future/permissions.md` (sweep note of the profile / help ticket / stamp tests) say these helpers are reused for attachments. They are not.
**Decided:** OQ-5 already settles reading. A ticket's attachments follow the ticket's visibility: someone `can_access_ticket` refuses gets 404 on list, sign and confirm, and nothing is written. Logged as 🐞 BUG-1950 against the attachment service / manager, for their future spec. No rule of this module changes.
**Not decided, moved to `docs/future/permissions.md` (Added during the sweep):** whether *adding* a file needs the see-right (creator, owner, ground-team-manager, platform admin) or the edit-right (creator only, as text under OQ-8). Suggested default for that feature: the see-right. A file adds to the ticket and rewrites nothing, and support staff attach screenshots. BUG-1950 is written to the see-right.

Checked and **not** violated: **HR-1** — BUG-1574 (schema). **HR-2, HR-3** — no unique names; `category` is not grouped. **HR-4** — no soft delete. **HR-5, HR-6, HR-8** — the DAO's (BUG-1442, BUG-1443); the manager filters nothing in Python. **HR-7** — both endpoints require `1 <= limit <= 200`. **HR-10** — close / reopen is a plain state change, and the worst race overwrites a stamp. **HR-11 … HR-15** — none applies. **HR-16** — the workspace methods find the ticket in the caller's workspace first; the platform methods are unscoped by design.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment service / manager** (`app/services/attachment_service.py`, `app/managers/attachment_manager.py`; no spec yet) | 🐞 BUG-1950: a `support_ticket` parent must pass `HelpTicketManager.can_access_ticket` (with the caller's role from an **active** membership, BUG-1885) on list, sign and confirm; otherwise 404, nothing written. Whether adding needs the see-right or the edit-right is for the permissions feature (see above). | Routed item |
| FU-2 | **Help ticket service spec** (FU-1 there) | Answered by this spec. One correction: `can_view_all_tickets` / `can_access_ticket` are **not** used by `AttachmentManager`; BUG-1950 is the consequence. No rule of the service changes. | this spec |

## Overview
`HelpTicketManager` decides who may see a help ticket (a workspace member's request to the platform support team) and applies ticket changes. It also shapes the platform support inbox rows. `HelpTicketService` is its only caller, and the service owns the transaction. The manager never commits or rolls back, so a refusal must come before anything is written to the session (BUG-1863). Refusals are its own plain exceptions: `HelpTicketNotFoundError` (a `LookupError`) and `HelpTicketForbiddenError` (a `PermissionError`). The endpoints turn them into 404 and 403. It sends no notifications.

**Callables:** 10 specified · 5 not specified
**Externals to mock:** `utcnow` as imported in `app.managers.help_ticket_manager` (`closed_at`); `datetime` in `app.dao.help_ticket` only for the ticket number's year (DAO spec Notes).
**Integration-only behavior:** the endpoint's role lookup (`_workspace_role`, BUG-1885) and the 404 / 403 translation; `get_platform_admin` on the platform endpoints.

**Facts for the test designer**
- Import: `from app.managers.help_ticket_manager import HelpTicketManager, help_ticket_manager, HelpTicketNotFoundError, HelpTicketForbiddenError, TICKET_VIEW_ALL_ROLES`. Every parameter after `session` is keyword-only, and so are the static methods' parameters (`can_access_ticket(*, ticket, user, role)`). `can_view_all_tickets(role)` is positional.
- `TICKET_VIEW_ALL_ROLES == {"owner", "ground-team-manager"}` (plain strings; `RoleEnum` is a `str` enum, so `RoleEnum.OWNER` also matches).
- Messages: not found `Help ticket not found.`; forbidden `You do not have access to this help ticket.`
- `Profile.is_platform_admin` (Boolean, default `False`); `Profile.name` NOT NULL. `HelpTicket.created_by` nullable (`ON DELETE SET NULL`). Table: help ticket DAO spec **Model facts**.
- `HelpTicketUpdate`: `title` (1–200), `description` (≥1), `category` (≤80), `status` (`HelpTicketStatusEnum`: `open`, `closed`), all optional and `None` by default; the manager reads only the fields **sent** (`exclude_unset`).

**Notes for the test designer**
- Build tickets with `help_ticket_dao.create_with_user` or directly (`HelpTicket(workspace_id, ticket_number, title, description, created_by)`), flush. Use `user` objects from `make_profile`; a platform admin is `make_profile(is_platform_admin=True)`.
- **BUG-1863 cases:** assert the exception, then that the ticket's attributes are unchanged **in the session without a rollback** (`title`, `status`, `closed_at`, `closed_by` as before; `db.is_modified(ticket)` is `False`). That proves the refusal came before any write. → strict xfail.
- **BUG-1576 / BUG-1577:** as the service spec's Notes (`SET LOCAL TIME ZONE 'America/New_York'` for BUG-1577); patch `app.managers.help_ticket_manager.utcnow` for exact `closed_at` values elsewhere.
- **BUG-1578:** `list_tickets` with a platform admin and `role=None` → strict xfail.

## Not specified
- `HelpTicketNotFoundError`, `HelpTicketForbiddenError` — exception classes, no logic (their base classes are a fact above).
- `HelpTicketManager.__init__` — implicit, no state.
- `help_ticket_manager` — module-level singleton, no logic.
- `TICKET_VIEW_ALL_ROLES` — constant (fact above).

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
**Persistence:** pure (reads only `ticket.created_by`, `user.id`, `user.is_platform_admin`; no query)
**Visibility:** public (used by: `get_by_id_and_workspace`; named as "the help ticket rule" by the discussion service spec, BUG-1868, and by BUG-1950)

**Purpose:** Whether this user may open this ticket.

**Rules:**
- **R1.** A platform admin (`user.is_platform_admin` true) may, whatever `role` and whoever created the ticket. A user object without that attribute counts as not an admin.
- **R2.** Otherwise a `role` for which `can_view_all_tickets` is true may.
- **R3.** Otherwise only the ticket's creator (`ticket.created_by == user.id`) may. A ticket whose creator is gone (`created_by` `None`) is open to R1 and R2 only.
- **R4.** The ticket's workspace is not looked at here (callers find it in the workspace first), and `role` is trusted as passed. BUG-1885's fix (only an `active` membership's role counts) is in the endpoint's role lookup. This rule stays as written.

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
- **R2.** A found ticket that `can_access_ticket` refuses → `HelpTicketForbiddenError("You do not have access to this help ticket.")`.
- **R3.** Otherwise the ticket is returned unchanged.

**Errors:**
| Condition | Raises | Message |
|---|---|---|
| not in the workspace | `HelpTicketNotFoundError` | `Help ticket not found.` |
| may not open it | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |

**Side effects:** none

---

## `HelpTicketManager.list_tickets(session, *, workspace_id, user, role, status=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.list_tickets`)

**Purpose:** The workspace's tickets the caller may see.

**Returns:** a `list` of `HelpTicket` (creator loaded).

**Rules:**
- **R1.** With a `role` for which `can_view_all_tickets` is true, every ticket of the workspace; otherwise only tickets with `created_by == user.id`. The rows, order (BUG-1442), filter and paging are DAO `list_by_workspace` R1–R6. `status` reaches it as its value (`"open"` / `"closed"`), and `None` means no filter. `skip` / `limit` pass through (defaults 0 / 100).
- **R2.** [BUG-1578] A platform admin (`user.is_platform_admin`) sees every ticket of the workspace, whatever `role`, the same rule as `can_access_ticket` R1. *(Today: only their own tickets; `[]` for an admin with no membership.)*

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit` (DAO R4).

**Side effects:** none

---

## `HelpTicketManager.list_platform_tickets(session, *, status=None, search=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService.list_platform_tickets` ← `/platform/help/tickets`, platform admins only)

**Returns:** a `list` of `PlatformHelpTicketListItem`, one per DAO row, in the DAO's order.

**Rules:**
- **R1.** Rows, filters, search, order and paging are DAO `list_platform` R1–R6 (BUG-1442, BUG-1443); `status` passed as its value, `search` and paging unchanged.
- **R2.** Each row becomes an item as `_to_platform_item`. An empty result gives `[]`.
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
- **R1.** One ticket is created and flushed (not committed) exactly as DAO `create_with_user` R1–R5 (number, `status open`, `created_by = user_id`; BUG-1440, BUG-1441). The manager adds no check of its own: any role may open a ticket, and the payload is stored as the schema gives it (trimming is BUG-1574, in the schema). The new row is returned.

**Errors:** as DAO `create_with_user` R4, R5 (`IntegrityError`). **Side effects:** one `help_tickets` row, flushed.

---

## `HelpTicketManager.update_ticket(session, *, ticket, payload, user_id)`
**Shape:** update / state-transition
**Persistence:** writes
**Visibility:** public (used by: `HelpTicketService.update_ticket`, after `get_by_id_and_workspace`)

**Purpose:** Change a ticket's text, or close / reopen it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `ticket` | `HelpTicket` | already found and access-checked by the caller; not re-checked |
| `payload` | `HelpTicketUpdate` | only fields **sent** count (`exclude_unset`) |
| `user_id` | int | the caller; becomes `closed_by` |

**Returns:** the same ticket instance, flushed (DAO `update`), not committed.

**Rules:**
- **R1.** Only fields sent are applied; `{}` changes nothing (no field, no stamp) and returns the ticket.
- **R2.** `title`, `description`, `category` sent with a value are written as sent. `category: null` clears the category.
- **R3.** The ticket's creator (`user_id == ticket.created_by`) may change `title`, `description` and `category`, whatever their role.
- **R4.** [BUG-1863] (OQ-8, owner) When `title`, `description` or `category` is sent (even with the ticket's current value, even `null`) and `user_id` is not the ticket's `created_by` (or `created_by` is `None`), the call raises `HelpTicketForbiddenError("You do not have access to this help ticket.")` **before anything is written**: no attribute of the ticket changes in the session, nothing is flushed, and a `status` in the same payload is not applied either. *(Today: the text is written, flushed and returned.)* Close / reopen alone stays open to anyone the caller let through (R5).
- **R5.** `status: "closed"` sets `status = "closed"`, `closed_by = user_id`, `closed_at = utcnow()`. `status: "open"` sets `status = "open"`, `closed_at = None`, `closed_by = None`. Anyone who reached this method may close or reopen (the creator and R4's other roles alike).
- **R6.** `status: null`, or `status` not sent, leaves `status`, `closed_at`, `closed_by` untouched. A `status` value other than `open` / `closed` cannot pass `HelpTicketUpdate`. Built around the schema (`model_construct`), any other value is ignored the same way.
- **R7.** [BUG-1576] (HR-9) `status: "closed"` on a ticket already `closed` changes nothing: `closed_at` and `closed_by` keep their values. *(Today: both rewritten with now and the second user.)* `status: "open"` on an open ticket changes nothing (holds today: values already `None`).
- **R8.** [BUG-1577] `closed_at` is the true moment as aware UTC, whatever the database session's time zone. *(Today: naive `utcnow()` read in the session's time zone; 5 h off under `America/New_York`.)*
- **R9.** `title: null` or `description: null` (BUG-1575: refused by the schema once fixed; service spec R4a) today reach the NOT NULL columns: the flush raises `IntegrityError` (not-null). The manager does not roll back; the session must be rolled back by its caller.
- **R10.** `updated_at` is the database's `now()` on any UPDATE (Model facts); the manager writes no `updated_by` (the table has none).

**Errors:**
| Condition | Raises | Message |
|---|---|---|
| text field sent by someone other than the creator (R4, BUG-1863) | `HelpTicketForbiddenError` | `You do not have access to this help ticket.` |
| (today) `null` title / description | `sqlalchemy.exc.IntegrityError` | — |

**Side effects:** the changed columns of the row, flushed; nothing on a refusal.

---

## `HelpTicketManager.to_response(ticket)` (static)
**Shape:** mapper
**Persistence:** pure (reads `ticket.creator`, which may lazy-load it)
**Visibility:** public (used by: `HelpTicketService` for every answer, `_to_platform_item`)

**Rules:**
- **R1.** Returns a `HelpTicketResponse` with every field from the row (`id`, `workspace_id`, `ticket_number`, `title`, `description`, `category`, `status`, `created_by`, `created_at`, `updated_at`, `closed_at`, `closed_by`).
- **R2.** `creator_name` is the creator's `name` when the ticket has a creator; `None` when `creator` is `None`.

**Errors:** `pydantic.ValidationError` if the row is not a valid response (e.g. an unflushed row without `created_at`). **Side effects:** none

---

## `HelpTicketManager._to_platform_item(ticket, workspace_name, creator_name)` (static)
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `list_platform_tickets`, `get_platform_ticket`)

**Rules:**
- **R1.** Returns a `PlatformHelpTicketListItem`: every field of `to_response(ticket)`, plus `workspace_name` as given.
- **R2.** `creator_name` is the given `creator_name` when it is truthy; otherwise (`None` or `""`) the one from `to_response` (the loaded creator's name, or `None`).

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–19 | the two roles | Facts; `can_view_all_tickets` R1 |
| 34–35 | `role in TICKET_VIEW_ALL_ROLES` | `can_view_all_tickets` R1 |
| 44–45 | `getattr(user, "is_platform_admin", False)` | `can_access_ticket` R1 |
| 46–47 | role sees all | `can_access_ticket` R2 |
| 48 | `created_by == user.id` | `can_access_ticket` R3, R4 |
| 59–63 | DAO lookup; `None` → not found | `get_by_id_and_workspace` R1 |
| 64–66 | access refused → forbidden; else return | `get_by_id_and_workspace` R2, R3 |
| 79 | `status is not None` → `.value` | `list_tickets` R1 |
| 80–82 | not view-all → `created_by` filter (no admin case, BUG-1578) | `list_tickets` R1, R2 |
| 83–90 | DAO `list_by_workspace` | `list_tickets` R1 |
| 101–109 | `status` value; DAO `list_platform`; map rows | `list_platform_tickets` R1–R3 |
| 117–121 | `row is None` → not found; else map | `get_platform_ticket` R1, R2 |
| 131–136 | DAO `create_with_user` | `create_ticket` R1 |
| 146–147 | `exclude_unset`; pop `status` (no creator check, BUG-1863) | `update_ticket` R1, R2, R3, R4 |
| 149 | `new_status is not None` | `update_ticket` R5, R6 |
| 150–152 | enum → `.value`, else as given | `update_ticket` R6 |
| 153–156 | `closed` → stamp (always, BUG-1576; naive, BUG-1577) | `update_ticket` R5, R7, R8 |
| 157–160 | `open` → clear | `update_ticket` R5, R7 |
| 153/157 fall-through | other value → nothing | `update_ticket` R6 |
| 162 | DAO `update` with a dict (writes `None` too) | `update_ticket` R2, R9, R10 |
| 166 | `getattr(ticket, "creator", None)` truthy → name | `to_response` R2 |
| 167–170 | validate; `creator_name is not None` → copy | `to_response` R1, R2 |
| 178–185 | base response; `creator_name or base.creator_name` | `_to_platform_item` R1, R2 |
| 188 | singleton | Not specified |
