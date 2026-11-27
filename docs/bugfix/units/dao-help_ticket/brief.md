# Fix brief: dao-help_ticket

## 1. Unit

| | |
|---|---|
| Slug | `dao-help_ticket` |
| Source file | `app/dao/help_ticket.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-help_ticket` |
| Branch | `bugfix/dao-help_ticket` (from `origin/main`) |
| Risk | `normal` (BUG-1441 and BUG-1442 are trivial-list patterns; BUG-1443 `unescaped-like-wildcards` is not on the list). Not money, stock, order workflow or security: the bugs are about a number's year, list order and search text. Who may call the platform inbox is decided by the endpoint, not by this file, and does not change. |

## 2. Bugs

### BUG-1441: A help ticket number's year comes from the server's local clock
- **Pattern:** `local-clock-instead-of-utc`
- **Where:** `DAOHelpTicket.create_with_user`; reached through `POST /help-tickets/`.
- **Today:** The year is `datetime.now().year`, the local time of the machine running the API.
- **Intended:** The year comes from `utcnow()` (per BUG-1334, decided by Claude under the reviewer's delegation (2026-11-03)).
- **Example:** A server set to `Asia/Dhaka` (UTC+6). A ticket opened at 20:00 UTC on 31 December 2026 is numbered `HELP-2027-…`, while its UTC-based `created_at` says 2026. After the fix it is `HELP-2026-…`.
- **Precedent BUG-1334 (batch numbers), in words:** the year in a generated number comes from the project's UTC helper `utcnow()` (in `app/utils/time.py`, naive UTC), not from the local clock.

### BUG-1442: Help tickets of one creation time come back in no fixed order
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `DAOHelpTicket.list_by_workspace`, `DAOHelpTicket.list_platform`; reached through `GET /help-tickets/` and the platform support inbox.
- **Today:** `ORDER BY created_at DESC` only; four tickets of one time came back in a different order on each of three calls, so pages repeat and skip tickets.
- **Intended:** HR-6: `created_at` newest first, then `id` descending, before `skip` / `limit` (BUG-1321 precedent).
- **Precedent BUG-1321, in words:** a list ordered newest first by a date or time keeps that first key and adds `id` descending as the last key, applied before paging.
- **Why ties happen:** `created_at` is the database's `now()`, the start time of the transaction, so tickets created in one transaction share it.

### BUG-1443: `%` and `_` in the support inbox search match every ticket
- **Pattern:** `unescaped-like-wildcards`
- **Where:** `DAOHelpTicket.list_platform`; reached through the platform support inbox search.
- **Today:** The trimmed search text goes into four `ILIKE '%…%'` unescaped: `_` and `%` each matched all tickets.
- **Intended:** HR-8: `%`, `_` and `\` match literally in title, ticket number, description and workspace name.
- **Example:** A platform admin searches `a_b`. Today the ticket titled "axb" is found too; after the fix only "a_b" is. Searching `50%` finds "50%" and not "50 x". Searching `a\b` finds only a title that really contains a backslash.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `help_tickets`. Columns: `id` (PK), `workspace_id` (NOT NULL, FK `workspaces.id` ON DELETE CASCADE), `ticket_number` String(32) NOT NULL, `title` String(200) NOT NULL, `description` Text NOT NULL, `category` String(80) nullable, `status` String(16) NOT NULL (values `pending`, `opened`, `closed`; default `'pending'`), `type` String(16) NOT NULL (values `support`, `feedback`; default `'support'`; no check constraint), `created_by` / `closed_by` nullable FK `profiles.id` ON DELETE SET NULL, `created_at` / `updated_at` timestamptz NOT NULL with database `now()` (`updated_at` also on update), `closed_at` nullable. Unique constraint `uq_help_tickets_workspace_number` on `(workspace_id, ticket_number)`. Tickets and workspaces have no soft delete. `HelpTicketCreate`: `title` 1–200, `description` at least 1, `category` up to 80 or `None`, `type` a `HelpTicketTypeEnum` (default support); no trimming. Every parameter after `db` is keyword-only in every method. The class flushes, never commits, and takes no lock.

### `DAOHelpTicket.generate_ticket_number(db, *, workspace_id, year)` (not in a bug in this unit; must not change)
Internal, used by `create_with_user`. Returns a `str` `HELP-<year>-<n>`.
- **R1.** `<n>` is the number of the workspace's tickets whose `ticket_number` starts with `HELP-<year>-`, plus one, written with at least three digits: none → `HELP-2026-001`; two → `HELP-2026-003`; 999 → `HELP-2026-1000`.
- **R2.** Only that workspace and that year count: another workspace's tickets and another year's do not (a workspace's first ticket is `-001` whatever other workspaces hold). `year` is used as given (`1` → `HELP-1-001`).
- **R2a.** Status and type do not matter: `pending`, `opened` and `closed`, `support` and `feedback` tickets all count, in one sequence (one support and one feedback ticket → the next is `HELP-2026-003`).
- **R3.** Every ticket with the prefix counts, whatever its suffix: a number changed to `HELP-2026-009` or `HELP-2026-ABC` still counts as one, so gaps are not filled and the next number may be one already taken.
- Errors: none. Side effects: none.

### `DAOHelpTicket.create_with_user(db, *, obj_in, workspace_id, user_id)`
Used by `HelpTicketManager.create_ticket` ← `POST /help-tickets/`. Returns the new row, flushed, not committed.
- **R1.** A row is created with the schema's `title`, `description`, `category`, `workspace_id`, `created_by` = `user_id`, `status = 'pending'`, `ticket_number` from `generate_ticket_number` for that workspace and the current year; `closed_at`, `closed_by` empty; `created_at` = `updated_at` = the transaction's `now()`.
- **R1a.** `type` is the input's `type`, stored as its plain string value: `HelpTicketCreate` without `type` → `'support'`; `type="feedback"` → `'feedback'`. A `type` that is already a plain string (not an enum member) is stored as given. An input object with no `type` field at all → `'support'`.
- **R1b.** The returned row's `type` and `status` are plain `str` (`'feedback'`, `'pending'`), not enum members, and read back the same after a re-read.
- **R1c.** A `type` longer than 16 characters (only reachable by bypassing the schema's validation) → the flush raises `DataError` (pgcode `22001`); nothing is saved.
- **R1d.** An input that is not `HelpTicketCreate` and whose `model_dump()` carries a `status` key raises `TypeError` ("got multiple values for keyword argument 'status'"); no row is inserted. `HelpTicketCreate.model_construct(status=…)` drops the extra field, so it creates a normal pending ticket. Acceptable as is; no bug.
- **R2.** [BUG-1441] The year is the current year in UTC (`utcnow().year`). *(Today: `datetime.now().year`, the server's local year.)*
- **R3.** (BUG-1440, **not in this unit**, see §6) Two concurrent creates in one workspace both succeed with distinct numbers. *(Today: both may compute the same number.)* Leave the numbering as it is.
- **R4.** If the computed number is already taken in the workspace, the flush raises `IntegrityError` (`UniqueViolation`, 23505, `uq_help_tickets_workspace_number`) and nothing is saved.
- **R5.** An unknown `user_id` or `workspace_id` raises `IntegrityError` (pgcode `23503`). The values are stored as the schema gives them, untrimmed.
- Errors: as in R4, R5. Side effects: one row inserted and flushed.

### `DAOHelpTicket.list_by_workspace(db, *, workspace_id, status=None, ticket_type=None, created_by=None, skip=0, limit=100)`
Used by `HelpTicketManager.list_tickets` ← `GET /help-tickets/`. A workspace's tickets, newest first.
- **R1.** Returns the tickets with that `workspace_id`; another workspace's never.
- **R2.** `status` given (not `None`) keeps only tickets with exactly that status (case-sensitive, no wildcard, no trimming); `""`, an unknown value, `"PENDING"`, or the retired `"open"` keeps none.
- **R2a.** `ticket_type` given (not `None`) keeps only tickets with exactly that type, applied before the page; `""`, an unknown value or `"Feedback"` keeps none. `None` keeps both types.
- **R3.** `created_by` given (not `None`) keeps only that creator's tickets; `0` is a filter too and keeps none. Any of `status`, `ticket_type`, `created_by` given together combine with AND.
- **R4.** Paging as the generic list: default limit 100, `limit=0` → `[]`, a negative `skip` or `limit` → `DataError`.
- **R5.** [BUG-1442] (HR-6) Ordered by `created_at` newest first, then `id` descending, before `skip` / `limit`. *(Today: `created_at` only; among equal times the order changes from call to call.)*
- **R6.** Each ticket's `creator` is loaded in the same query.
- Errors: `DataError` for negative `skip` / `limit`. Side effects: none.

### `DAOHelpTicket.list_platform(db, *, status=None, ticket_type=None, search=None, skip=0, limit=100)`
Used by `HelpTicketManager.list_platform_tickets` ← the platform support inbox (platform admins only; the endpoint checks that). Returns a `list` of tuples `(ticket, workspace_name, creator_name)`; `creator_name` is `None` when the ticket has no creator.
- **R1.** Every workspace's tickets are returned; no workspace filter.
- **R2.** `status` given (not `None`) keeps exactly that status, as `list_by_workspace` R2 (`"open"` keeps none).
- **R2a.** `ticket_type` given (not `None`) keeps exactly that type, as `list_by_workspace` R2a, across every workspace. `status`, `ticket_type` and `search` combine with AND.
- **R3.** `search` empty (`None` or `""`) applies no filter. Otherwise it is trimmed and matched case-insensitively as a substring of the title, the ticket number, the description or the workspace's name (OR): `"gam"` finds every ticket of workspace "Gamma"; `" T1 "` finds title "T1"; a lowercase ticket number finds it.
- **R4.** A search of only spaces trims to `""` and matches every ticket.
- **R5.** [BUG-1442] (HR-6) Ordered as `list_by_workspace` R5 (`created_at` newest first, then `id` descending, before paging). *(Today: `created_at` only.)* Paging as `list_by_workspace` R4.
- **R6.** [BUG-1443] (HR-8) `%`, `_` and `\` in the search match literally: `_` finds only tickets with `_` in one of the four fields. *(Today: unescaped, so `_` and `%` match every ticket.)*
- Errors: `DataError` for negative `skip` / `limit`. Side effects: none.

### Other methods (not in a bug; must not change)
- `get_by_id(db, *, ticket_id)` R1: the ticket with that id, of any workspace, with its `creator` loaded in the same query; `None` for an unknown id or `0`.
- `get_by_id_and_workspace(db, *, id, workspace_id)` R1: the ticket with that id in that workspace, else `None`; R2: `creator` loaded in the same query (one statement, a `LEFT OUTER JOIN` to `profiles`); no creator → `creator` `None`.
- `get_platform_by_id(db, *, ticket_id)` R1: `(ticket, workspace_name, creator_name)` for that id, of any workspace; `None` for an unknown id or `0`.
- Inherited generic methods (`update`, `get`, `get_multi`, `get_by_workspace`, `create`, `remove`) stay as they are.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** No order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen first key (here: `created_at` newest first), keep it and add `id` after it (here descending, to match newest first).
- **HR-8. Search text is literal.** Text placed in `LIKE` / `ILIKE` patterns is escaped: `%` and `_` match literally; the escape character itself (`\`) must also match literally.
- **UTC clock (BUG-1334 precedent):** the codebase treats times as UTC; use the project's `utcnow()` helper (`app/utils/time.py`), not the local clock.
- **HR-16:** workspace methods filter on the row's `workspace_id`; `get_by_id` and the two platform methods read across workspaces by design. Keep that.
- No owner answer (OQ-n) touches these bugs. (OQ-8 and OQ-66 are about who may see or change a help ticket; not this file.)

## 5. Scope

- May change: `app/dao/help_ticket.py` only.
- No migration, no schema or API change. Method signatures and return types stay as they are.

## 6. Out of scope (leave alone)

- **BUG-1440** (two help tickets opened at once can get the same number), in this file: not in this unit. Leave `generate_ticket_number` and the numbering in `create_with_user` unchanged.
- `app/managers/help_ticket_manager.py`: BUG-1577 (close time depends on the database's time zone), BUG-1578 (platform admin's workspace ticket list is empty), BUG-1863 (others can rewrite a member's ticket), BUG-2103 (owner cannot open a ticket unless the membership says owner), BUG-3250 (owner's list shows only their own tickets), BUG-3251 (owner and ground-team managers cannot move a ticket's status), BUG-3270 (platform PATCH), BUG-1885 (suspended owner still counts).
- `app/schemas/help_ticket.py`: BUG-1574 (titles untrimmed, blanks accepted), BUG-1575 (`null` title or description gives a database error).
- Discussions and attachments of help tickets: BUG-1868, BUG-1879, BUG-1950, BUG-2091, BUG-2115, BUG-2131.
- BUG-100 (generic `get_by_workspace` has no order): `app/dao/base.py`.
