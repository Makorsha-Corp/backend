# Spec — `app/dao/help_ticket.py`

> **Status:** APPROVED (2026-11-26 revision; nothing open)
> **Source commit:** 41d5ac1 (revised from e48a092)

> **Revision 2026-11-26 (describe revision after merging origin/main).** The source changed: ticket status is now `pending` | `opened` | `closed` (was `open` | `closed`; migration `124_help_ticket_status_pending_opened` renames stored `open` to `opened` and sets the database default to `pending`), and a new `type` column (`support` | `feedback`, `HelpTicketTypeEnum`, migration `123_help_ticket_type`, database default `support`) is set by `create_with_user` and filtered by a new `ticket_type` parameter on both list methods. Re-read the DAO, the model, the schemas, the manager, the service and both endpoint files at 41d5ac1; verified the new facts by running (throwaway `v.py` with the `h.py` harness in the session scratchpad, one rolled-back transaction on `marker_test` at Alembic head `124_help_ticket_status`). Rules changed: Model facts (`status`, new `type`), `HelpTicketCreate` line, `generate_ticket_number` R2a (new), `create_with_user` Inputs, R1, R1a–R1c (new), `list_by_workspace` R2, R2a (new), R3, `list_platform` R2, R2a (new), Branch map (all line numbers), Notes for the test designer, FU-1 (b), FU-2 (new). New question Q1, decided by Claude under the reviewer's delegation (2026-11-26). Every 2026-11-03 decision (P1 / BUG-1440, P2 / BUG-1441, BUG-1442, BUG-1443) still applies unchanged. No new bug.

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 and P2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides `get_by_id_and_workspace`.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_help.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; numbering in an empty workspace, the second ticket, another workspace's first, another year, year `1`, a number changed by hand (001 + 009 → 003), a taken next number (001, 002, 004 → 004, then `create_with_user` fails with 23505), two reads before an insert (same number), after 999 tickets (`HELP-2026-1000`), a non-numeric suffix counted; the year taken from a patched `datetime.now()`; unknown user and workspace; a whitespace-only title through the schema; `get_by_id` own / other workspace / `0`; the override with its creator in the same query; order of four tickets with one `created_at` under a forced sequential scan before and after an update, with one newer, and pages; the `status` and `created_by` filters, `""`, `0`, both together; `list_platform` with the workspace and creator names, a ticket with no creator, search by workspace name, by title with spaces, by a lowercase ticket number, blank search, `_` and `%`, the status filter; `get_platform_by_id` found / unknown; a negative `limit`. **Read, not run:** `app/managers/help_ticket_manager.py`, `app/services/help_ticket_service.py`, the endpoints. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-03 and 2026-11-26.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Two tickets opened at the same moment in one workspace get the same number, and one of them fails | bug — numbering is race-free (BUG-1440) | Claude, delegated |
| P2 | The year in a ticket number comes from the server's local clock | bug — from UTC (BUG-1441) | Claude, delegated |
| Q1 | Support and feedback tickets share one `HELP-` number sequence per workspace and year | intended | Claude, delegated (2026-11-26) |

Decided by house rules: tickets with the same creation time come back in no fixed order (BUG-1442); `%` and `_` in the support inbox search match anything (BUG-1443).

### House-rule violations — applied automatically

- **HR-6** `list_by_workspace` R5 and `list_platform` R5 — ordered by `created_at` newest first, nothing after it. `created_at` is the database's `now()`, the transaction's start. Verified under a forced sequential scan: four tickets of one time came back in a different order on each of three calls, and pages of 2 then read `1668, 1666` / `1667, 1669` while the full list read `…, 1669, 1667`. Intended: `created_at` newest first, then `id` descending, before `skip` / `limit` (BUG-1321 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1442 (pattern `tied-timestamp-no-tiebreak`; one bug for both lists, same line). Rules: `list_by_workspace` R5, `list_platform` R5.
- **HR-8** `list_platform` R6 — the search text goes into `ILIKE '%…%'` unescaped. Verified: `_` and `%` each matched all 5 tickets of the test. Intended: `%`, `_` and `\` match literally, in all four searched fields.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** BUG-1443 (pattern `unescaped-like-wildcards`). Rules: `list_platform` R6.

Checked and **not** a new line here: **HR-4** — tickets and workspaces have no soft delete. **HR-5** — every filter is in the query. **HR-7** — `GET /help-tickets/` and the platform list require `skip >= 0` and `1 <= limit <= 200`. **HR-6** on the single lookups — by primary key. **HR-9** — `updated_at` is the database's `onupdate`; `updated_by` does not exist. **HR-10** — numbering is P1. **HR-16** — `get_by_id_and_workspace` and `list_by_workspace` filter on the row's workspace; `get_by_id` and the two platform methods are unscoped by design (R of each). **HR-1** — titles are not trimmed and a whitespace-only title passes the schema; that is `HelpTicketCreate` / `HelpTicketUpdate` (FU-1 (a)). **HR-15** — no money. *(2026-11-26, the new `ticket_type` filter:)* **HR-5** — in the query, before `skip` / `limit`. **HR-3** — `type` is not free text: the API takes it only as `HelpTicketTypeEnum` (create body, `?type=` on both lists), so the exact match is right. **HR-6** — the order is unchanged (BUG-1442 covers it). **HR-16** — the filter does not change scoping.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. Two tickets opened at once can get the same number — 🐞 BUG-1440
**Background:** A ticket's number is `HELP-<year>-<n>`, where `<n>` is the count of the workspace's tickets with that year's prefix, plus one, at least three digits. The database refuses a second ticket with the same number in one workspace (`uq_help_tickets_workspace_number`). The same count-then-insert numbering for sales orders was ruled a bug (BUG-727).
**What happens today:** Two requests that count before either inserts get the same number; the second insert fails with `IntegrityError` 23505 (a 500). (Verified: two counts before an insert both gave `HELP-2026-003`; a taken next number makes `create_with_user` fail with 23505.)
**Example:** Two users of one workspace open tickets in the same second. Both are given `HELP-2026-014`; one ticket is saved, the other user gets an error and has to type it again.
**Rules affected:** `create_with_user` R3
**Answer:** bug — per BUG-727 precedent: numbering is race-free (a per-workspace, per-year counter read with a lock, or a retry on the unique violation); two concurrent creates both succeed with distinct numbers
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1440 (pattern `count-then-insert-race`). The count is otherwise sound: tickets are never deleted (no delete endpoint, workspaces have no soft delete), the number cannot be edited, and the count is numeric, so `-999` is followed by `-1000`. Rules: `create_with_user` R3 (tagged; not unit-testable, no case).

### P2. The year in a ticket number comes from the server's local clock — 🐞 BUG-1441
**Background:** `create_with_user` takes the year from `datetime.now()`, the local time of the machine running the API; everything else in the code is UTC. The same was ruled a bug for batch numbers (BUG-1334).
**What happens today:** On a server whose local clock is already in the new year while UTC is not (or the reverse), the ticket gets the other year. (Verified with a patched `datetime.now()` returning 1 January 2027 05:00: `HELP-2027-001`.)
**Example:** A server set to `Asia/Dhaka` (UTC+6). A ticket opened at 20:00 UTC on 31 December 2026 is numbered `HELP-2027-…`, and the UTC-based `created_at` says 2026.
**Rules affected:** `create_with_user` R2
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1441 (pattern `local-clock-instead-of-utc`). Rules: `create_with_user` R2 (tagged).

### New questions (2026-11-26)

### Q1. Support and feedback tickets share one number sequence — ✅ intended
**Background:** Since 2026-11-26 a ticket has a type, `support` or `feedback`, chosen when it is opened (default `support`). The number `HELP-<year>-<n>` counts the workspace's tickets of that year, plus one.
**What happens today:** The count ignores the type, so support and feedback tickets are numbered in one sequence with the same `HELP-` prefix. (Verified: support, feedback, feedback, support in one workspace → `HELP-2026-001` … `-004`; another workspace's first feedback ticket → `HELP-2026-001`.)
**Example:** A workspace opens a support ticket (`HELP-2026-001`) and then sends feedback; the feedback is `HELP-2026-002`, and the next support ticket is `HELP-2026-003`. The support team sees a gap in the support numbers.
**Rules affected:** `generate_ticket_number` R2a
**Answer:** intended — decided by Claude under the reviewer's delegation (2026-11-26)
**Resolution:** one sequence per workspace and year is the best-practice default: a number stays unique without a second constraint, the BUG-1440 fix covers both types at once, and the type is its own column (filter, response field) rather than a number prefix. Gaps in one type's numbers carry no meaning (numbers are identifiers, not counts). Rules: `generate_ticket_number` R2a ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Help ticket schemas / manager** (`app/schemas/help_ticket.py`, `app/managers/help_ticket_manager.py`, not yet specified) | (a) **HR-1:** `title` (and `description`) with `min_length=1` accept `"   "` and are not trimmed (verified at DAO level: `'   '` stored); `category` likewise. (b) `update_ticket` passes `status` changes through the inherited `update` with a dict; closing an already closed ticket rewrites `closed_at` / `closed_by` (read, not run). *(2026-11-26: superseded at 41d5ac1 — the manager now allows only `pending → opened`, `opened → closed`, `closed → opened`, so `closed → closed` raises `HelpTicketInvalidTransitionError`; whoever revises the manager / service spec checks BUG-1576 against it.)* (c) The platform endpoints (`app/api/v1/endpoints/platform_help.py`) are the only callers of the unscoped `list_platform` / `get_platform_by_id`; who may call them is the endpoint's check (not read here). | HR-1 note, reading the callers |
| FU-2 | **Help ticket manager / service / endpoints** (`app/managers/help_ticket_manager.py`, `app/services/help_ticket_service.py`, `app/api/v1/endpoints/help_tickets.py`, `platform_help.py`; their specs predate 41d5ac1) | Read at 41d5ac1, not specified here: (a) only platform admins may change `status` (`HelpTicketStatusChangeForbiddenError`), so a workspace member can no longer close or reopen even their own ticket — check against OQ-8 / BUG-1863 ("owner, ground-team-manager and admins may still close / reopen"); (b) the transition table `pending → opened`, `opened → closed`, `closed → opened` (`HelpTicketInvalidTransitionError`, also for a stored status outside the enum); (c) `type` cannot be changed after creation (`HelpTicketUpdate` has no `type`); (d) both lists take `?type=` as `HelpTicketTypeEnum`. | 2026-11-26 revision, reading the callers |

## Overview
`DAOHelpTicket` reads and creates `help_tickets`, the support requests a workspace sends to the platform team. Callers: `HelpTicketManager` (`get_by_id_and_workspace`, `list_by_workspace`, `create_with_user`, `list_platform`, `get_platform_by_id`, inherited `update`), `HelpTicketService` (`get_by_id` after a commit, to reload the creator), `AttachmentManager` (the support ticket lookup when attaching a file). Workspace methods filter on the row's `workspace_id`; the platform methods and `get_by_id` deliberately read across workspaces. It flushes, never commits, and takes no lock.

**Callables:** 7 specified · 1 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `datetime.now` in `app.dao.help_ticket` (patch the module's `datetime` name) for the year of `create_with_user`.
**Integration-only behavior:** none.

**Model facts (table `help_tickets`, class `app.models.help_ticket.HelpTicket`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `ticket_number` | String(32) NOT NULL, indexed | — |
| `title` | String(200) NOT NULL | — |
| `description` | Text NOT NULL | — |
| `category` | String(80) nullable | `NULL` |
| `status` | String(16) NOT NULL, indexed | `'pending'` (Python and database); values `pending`, `opened`, `closed` (`HelpTicketStatusEnum`), no check constraint. `open` is no longer a value: migration 124 renamed stored `open` rows to `opened`. |
| `type` | String(16) NOT NULL, indexed (`ix_help_tickets_type`) | `'support'` (Python and database); values `support`, `feedback` (`HelpTicketTypeEnum`), no check constraint (verified: a raw `UPDATE` to `'bogus'` is accepted); a value over 16 characters → `DataError` (22001) |
| `created_by`, `closed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at` | `timestamptz` NOT NULL | database `now()` |
| `updated_at` | `timestamptz` NOT NULL | database `now()`, `onupdate` database `now()` |
| `closed_at` | `timestamptz` nullable | `NULL` |

- Unique constraint `uq_help_tickets_workspace_number` on `(workspace_id, ticket_number)`; plain indexes on `workspace_id`, `ticket_number`, `status`, `created_by`. No trigger. Relationships `workspace`, `creator`, `closer`.
- `HelpTicketCreate`: `title` 1–200, `description` ≥ 1, `category` ≤ 80 or `None`, `type` a `HelpTicketTypeEnum` (default `SUPPORT`; `"feedback"` is accepted and becomes the enum); no trimming. `model_dump()` keeps `type` as the enum member.
- A row inserted by raw SQL without `status` / `type` gets `'pending'` / `'support'` from the database (verified).

**Notes for the test designer:**
- Use the singleton `help_ticket_dao`. Every parameter after `db` is keyword-only.
- *(2026-11-26)* A ticket built directly as `HelpTicket(...)` without `status` / `type` gets `status "pending"`, `type "support"` (model default). `"open"` is not a status any more: an "other status" ticket is `"opened"` or `"closed"`.
- `create_with_user` R1a / R1c: a plain-string `type` reaches the DAO only through `HelpTicketCreate.model_construct(title=…, description=…, category=None, type="feedback")` (pydantic warns on dump; harmless). An input without a `type` field: any small `BaseModel` with only `title`, `description`, `category`.
- Workspaces from `make_workspace(name=…)`, profiles from `make_profile(name=…)`.
- **BUG-1441:** `mock.patch.object(app.dao.help_ticket, "datetime", Fake)` where `Fake` subclasses `datetime` with a `now()` returning 1 January 2027 05:00, and patch `app.dao.help_ticket.utcnow` (with `create=True`: the module does not import it today) and `app.utils.time.utcnow` to 31 December 2026 23:00. Intended `HELP-2026-…`; today `HELP-2027-…` → **strict** xfail.
- **BUG-1442:** tickets created in one transaction share `created_at`; force a sequential scan (base spec note) and update the lowest-`id` row by SQL; **non-strict** xfail. To make one newer: `UPDATE help_tickets SET created_at = now() + interval '1 hour'`.
- `list_platform` is unscoped and the test database is shared: give the test's workspace a unique name and compare only the test's own ticket ids.

## Not specified
- `help_ticket_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`update` ← `update_ticket` with a dict; `get`, `get_multi`, `get_by_workspace`, `create`, `remove` — no caller) — base spec.

---

## `DAOHelpTicket.generate_ticket_number(db, *, workspace_id, year)`
**Shape:** compute
**Persistence:** reads
**Visibility:** internal (used by: `create_with_user`)

**Purpose:** The next ticket number of a workspace for a year.

**Returns:** a `str` `HELP-<year>-<n>`.

**Rules:**
- **R1.** `<n>` is the number of the workspace's tickets whose `ticket_number` starts with `HELP-<year>-`, plus one, written with at least three digits: none → `HELP-2026-001`; two → `HELP-2026-003`; 999 → `HELP-2026-1000`.
- **R2.** Only that workspace and that year count: another workspace's tickets and another year's do not (a workspace's first ticket is `-001` whatever other workspaces hold). `year` is used as given (`1` → `HELP-1-001`).
- **R2a.** Status and type do not matter: `pending`, `opened` and `closed`, `support` and `feedback` tickets all count, in one sequence (one support and one feedback ticket → the next is `HELP-2026-003`). ✅ (Q1, 2026-11-26)
- **R3.** Every ticket with the prefix counts, whatever its suffix: a number changed to `HELP-2026-009` or `HELP-2026-ABC` still counts as one, so gaps are not filled and the next number may be one already taken (only reachable through data no API can write).

**Errors:** none.

**Side effects:** none

---

## `DAOHelpTicket.create_with_user(db, *, obj_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `HelpTicketManager.create_ticket` ← `POST /help-tickets/`)

**Purpose:** Open a ticket for a user, with the next number.

**Inputs:** `obj_in` — `HelpTicketCreate` (all of its fields are stored: `title`, `description`, `category`, `type`); `workspace_id`, `user_id` — ints.

**Returns:** the new row, flushed, not committed.

**Rules:**
- **R1.** A row is created with the schema's `title`, `description`, `category`, `workspace_id`, `created_by` = `user_id`, `status = 'pending'` (`HelpTicketCreate` has no `status` field, so every ticket created through it is pending), `ticket_number` from `generate_ticket_number` for that workspace and the current year; `closed_at`, `closed_by` empty; `created_at` = `updated_at` = the transaction's `now()`.
- **R1a.** `type` is the input's `type`, stored as its plain string value: `HelpTicketCreate` without `type` → `'support'`; `type="feedback"` → `'feedback'`. A `type` that is already a plain string (not an enum member) is stored as given. An input object with no `type` field at all → `'support'`.
- **R1b.** The returned row's `type` and `status` are plain `str` (`'feedback'`, `'pending'`), not enum members, and read back the same after a re-read.
- **R1c.** A `type` longer than 16 characters (only reachable by bypassing the schema's validation) → the flush raises `DataError` (pgcode `22001`); nothing is saved.
- **R1d.** An input that is not `HelpTicketCreate` and whose `model_dump()` carries a `status` key (e.g. a `BaseModel` with `status="closed"`) raises `TypeError` ("…HelpTicket() got multiple values for keyword argument 'status'"); no row is inserted (the number count has already been read, nothing written). `HelpTicketCreate.model_construct(status=…)` drops the extra field, so it creates a normal pending ticket. Acceptable, documented: unreachable from the API (the only caller passes the validated schema), and failing loudly is safer than silently overriding a caller's status — decided by Claude under the reviewer's delegation (2026-11-26). No bug.
- **R2.** [BUG-1441] (P2) The year is the current year in UTC (`utcnow().year`). *(Today: `datetime.now().year`, the server's local year.)*
- **R3.** [BUG-1440] (P1) Two concurrent creates in one workspace both succeed with distinct numbers. *(Today: both may compute the same number, and the second insert fails with `IntegrityError` 23505. Not unit-testable with one connection: no case; the single-connection outcome of a taken number is R4.)*
- **R4.** If the computed number is already taken in the workspace, the flush raises `IntegrityError` (`UniqueViolation`, 23505, `uq_help_tickets_workspace_number`) and nothing is saved.
- **R5.** An unknown `user_id` or `workspace_id` raises `IntegrityError` (pgcode `23503`). The values are stored as the schema gives them, untrimmed.

**Errors:** as in R4, R5.

**Side effects:** one row inserted and flushed.

---

## `DAOHelpTicket.get_by_id(db, *, ticket_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketService` after create and update, with the id it just wrote)

**Rules:**
- **R1.** Returns the ticket with that id, of any workspace, with its `creator` loaded in the same query; `None` for an unknown id or `0`.

**Errors:** none. **Side effects:** none

---

## `DAOHelpTicket.get_by_id_and_workspace(db, *, id, workspace_id)` (override)
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketManager.get_by_id_and_workspace` ← `GET` / `PATCH /help-tickets/{id}/`, 404 on `None`; `AttachmentManager` support ticket lookup)

**Rules:**
- **R1.** As base `get_by_id_and_workspace` R1–R3: the ticket with that id in that workspace, else `None` (another workspace, unknown, `0`).
- **R2.** The `creator` is loaded in the same query (one statement, a `LEFT OUTER JOIN` to `profiles`); a ticket without a creator is returned with `creator` `None`.

**Errors:** none. **Side effects:** none

---

## `DAOHelpTicket.list_by_workspace(db, *, workspace_id, status=None, ticket_type=None, created_by=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketManager.list_tickets` ← `GET /help-tickets/`; `created_by` = the caller unless the caller is an owner or ground team manager; `status` and `ticket_type` are the enum values of `?status=` / `?type=`, or `None`)

**Purpose:** A workspace's tickets, newest first, optionally only one status, one type or one creator's.

**Rules:**
- **R1.** Returns the tickets with that `workspace_id`; another workspace's never.
- **R2.** `status` given (not `None`) keeps only tickets with exactly that status (`pending`, `opened`, `closed`; case-sensitive, no wildcard, no trimming); `""`, an unknown value, `"PENDING"`, or the retired `"open"` keeps none.
- **R2a.** `ticket_type` given (not `None`) keeps only tickets with exactly that type (`support` or `feedback`), applied before the page; `""`, an unknown value or `"Feedback"` keeps none. `None` keeps both types.
- **R3.** `created_by` given (not `None`) keeps only that creator's tickets; `0` is a filter too and keeps none. Any of `status`, `ticket_type`, `created_by` given together combine with AND (verified: `pending` + `feedback` + creator → only that creator's pending feedback tickets; `opened` + `feedback` with none opened → `[]`).
- **R4.** Paging as base `get_by_workspace` R2, R5, R6 (default 100, `limit=0` → `[]`, negative → `DataError`).
- **R5.** [BUG-1442] (HR-6) Ordered by `created_at` newest first, then `id` descending, before `skip` / `limit`. *(Today: `created_at` only; among equal times the order changes from call to call, verified.)*
- **R6.** Each ticket's `creator` is loaded in the same query.

**Errors:** `DataError` for negative `skip` / `limit`. **Side effects:** none

---

## `DAOHelpTicket.list_platform(db, *, status=None, ticket_type=None, search=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketManager.list_platform_tickets` ← the platform support inbox `GET …/help/tickets` in `app/api/v1/endpoints/platform_help.py`, platform admins only; `status` / `ticket_type` from `?status=` / `?type=`)

**Purpose:** Tickets of every workspace, with the workspace's and creator's names, newest first.

**Returns:** a `list` of tuples `(ticket, workspace_name, creator_name)`; `creator_name` is `None` when the ticket has no creator.

**Rules:**
- **R1.** Every workspace's tickets are returned; no workspace filter.
- **R2.** `status` given (not `None`) keeps exactly that status, as `list_by_workspace` R2 (`"open"` keeps none).
- **R2a.** `ticket_type` given (not `None`) keeps exactly that type, as `list_by_workspace` R2a, across every workspace. `status`, `ticket_type` and `search` combine with AND (verified: `feedback` + search of one workspace's name → only that workspace's feedback tickets).
- **R3.** `search` empty (`None` or `""`) applies no filter. Otherwise it is trimmed and matched case-insensitively as a substring of the title, the ticket number, the description or the workspace's name (OR): `"gam"` finds every ticket of workspace "Gamma"; `" T1 "` finds title "T1"; a lowercase ticket number finds it.
- **R4.** A search of only spaces trims to `""` and matches every ticket.
- **R5.** [BUG-1442] (HR-6) Ordered as `list_by_workspace` R5. *(Today: `created_at` only.)* Paging as `list_by_workspace` R4.
- **R6.** [BUG-1443] (HR-8) `%`, `_` and `\` in the search match literally: `_` finds only tickets with `_` in one of the four fields. *(Today: unescaped, so `_` and `%` match every ticket.)*

**Errors:** `DataError` for negative `skip` / `limit`. **Side effects:** none

---

## `DAOHelpTicket.get_platform_by_id(db, *, ticket_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `HelpTicketManager.get_platform_ticket`, 404 on `None`)

**Rules:**
- **R1.** Returns `(ticket, workspace_name, creator_name)` for that id, of any workspace (`creator_name` `None` without a creator); `None` for an unknown id or `0`.

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–30 | prefix; workspace AND `LIKE 'HELP-<year>-%'` (no status / type condition); count + 1, `:03d` | `generate_ticket_number` R1, R2, R2a, R3 |
| 40 | `datetime.now().year` (BUG-1441) | `create_with_user` R2 |
| 41–43 | number from `generate_ticket_number`; count-then-insert (BUG-1440) | `create_with_user` R1, R3 |
| 44–45 | `data.pop("type", "support")` — key present / absent | `create_with_user` R1a |
| 46–47 | `hasattr(ticket_type, "value")` — enum member / plain string | `create_with_user` R1a, R1b |
| 48–57 | fixed `status = 'pending'`, `created_by`, `type`; add + flush (unique, FK, length errors) | `create_with_user` R1, R1b, R1c, R1d, R4, R5 |
| 66–71 | by id, unscoped, creator joined | `get_by_id` R1 |
| 80–85 | id AND workspace, creator joined | `get_by_id_and_workspace` R1, R2 |
| 98–102 | workspace filter, creator joined | `list_by_workspace` R1, R6 |
| 103–104 | `status is not None` | `list_by_workspace` R2 |
| 105–106 | `ticket_type is not None` | `list_by_workspace` R2a |
| 107–108 | `created_by is not None` | `list_by_workspace` R3 |
| 109–114 | `created_at DESC` only (BUG-1442); offset / limit | `list_by_workspace` R4, R5 |
| 127–132 | join workspace, outer join creator; unscoped | `list_platform` R1 |
| 133–134 | `status is not None` | `list_platform` R2 |
| 135–136 | `ticket_type is not None` | `list_platform` R2a |
| 137–144 | `if search:`; `strip()`; four `ILIKE`, unescaped (BUG-1443) | `list_platform` R3, R4, R6 |
| 145–151 | `created_at DESC` only (BUG-1442); tuples | `list_platform` R5 |
| 159–170 | by id, unscoped; `row is None` → `None` | `get_platform_by_id` R1 |
| 173 | singleton | Not specified |

## Gap log
G1 (help_ticket.cases.md gap 5; help_ticket.verify.md Round 2026-11-26 finding 3) — Fact — `create_with_user` R1 narrowed from "whatever the input" to "`HelpTicketCreate` has no `status`, so every ticket created through it is pending"; new R1d states today's `TypeError` for a non-schema input carrying `status` (no row inserted) and that `model_construct(status=…)` drops the field. Verified by running (rolled back, `marker_test`). Judged acceptable, documented, not a bug (unreachable from the API; decided by Claude under the reviewer's delegation, 2026-11-26). Branch map 48–57 now cites R1d. Status stays APPROVED.
