# Spec — `app/dao/discussion.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092
> **Revision 2026-11-04:** FU-1 (b) answered by the owner (2026-11-04), OQ-5: discussions follow the record's own visibility; a member who cannot open the private project or help ticket gets 404. The check belongs in `DiscussionService` (it needs the caller and the record; this DAO knows neither), logged there as BUG-1867 (private projects and their components) and BUG-1868 (help tickets). No rule of this DAO changes.

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). It is not the owner's own answer. The house-rule lines stand. One access matter is routed to the discussion service's review as an **OWNER** item (FU-1 (b)); it is not a rule of this DAO and does not hold this spec.

> **Base behaviour:** `DiscussionDAO` does **not** inherit `BaseDAO`; it has only the three methods below.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted parents hide their children. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_disc.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `create` positionally and by keyword, a 31-character `entity_type`, `message=None`, unknown workspace / user / parent, `user_id=None`, an empty message, an unknown entity type, a negative entity id, a reply to a reply, a reply on another entity, a reply under another workspace; `get_by_entity` roots and `total`, replies loaded with the root (including the other workspace's reply), another workspace, unknown entity, `entity_type` in another case; order of four roots with one `created_at` under a forced sequential scan before and after an update, with one older, paging, `limit=0` with `total`, negative `limit`; order of three replies before and after an update; 51 roots; `get_by_id` own / other workspace / a reply / `0`; deleting a root. **Read, not run:** `app/services/discussion_service.py`, `app/api/v1/endpoints/discussions.py`. **Not run:** anything over HTTP; the mention notifications.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A thread is listed for any record id, whether the record exists, is deleted, or belongs to someone else | intended at the DAO; the discussion service checks the record (FU-1 (a)) | Claude, delegated |

Decided by house rules: messages posted at the same moment come back in no fixed order (BUG-1438); replies have no order at all (BUG-1439).

### House-rule violations — applied automatically

- **HR-6** `get_by_entity` R4 — ordered by `created_at` alone. `created_at` is the database's `now()`, the transaction's start, so two posts tie only when they share a transaction or a microsecond; but the list is paged, so a tie can repeat or skip a message between pages. Verified under a forced sequential scan: four roots of one time came back `12, 13, 14, 15`, then `13, 14, 15, 12` after an update, and pages of 2 split them `13, 14` / `15, 12`. Intended: `created_at` oldest first, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1438 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_by_entity` R4.
- **HR-6** `get_by_entity` R6 — the replies loaded with each root have no order at all: the model's `replies` relationship sets no `order_by`. Verified: replies `16, 17, 18` came back `17, 18, 16` after an update of the first. A thread shows its replies in that order. Intended: replies `created_at` oldest first, then `id` ascending (the fix belongs on the relationship in `app/models/discussion.py`).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1439 (pattern `unordered-pagination`). Rules: `get_by_entity` R6.

Checked and **not** a new line here: **HR-4** — discussions have no soft delete; the record's state is P1. **HR-5** — every filter is in the query and `total` counts the same filter. **HR-7** — `GET /discussions/` requires `skip >= 0` and `1 <= limit <= 200`. **HR-8** — no `LIKE`. **HR-16** — reads compare the row's own `workspace_id`; a reply of workspace B under a root of A is loaded with A's root (R6a), but no writer produces it: the service finds the parent with `get_by_id` in the caller's workspace and answers 404 otherwise. **HR-1** — a blank message is refused by `DiscussionCreate` (`message_not_empty`); the DAO stores what it gets. **HR-9, HR-10** — append-only, no lock needed. **HR-15** — no money.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. A thread is listed for any record id — ✅ intended at the DAO
**Background:** A discussion names its record only by `entity_type` and `entity_id` (purchase order, project, machine, item, support ticket, …); there is no foreign key, so the DAO cannot reach the record's table. Several of those records are soft-deleted, and the standing decision is that a soft-deleted parent hides its children. The attachment link DAO got the same answer (attachment link DAO P2).
**What happens today:** `get_by_entity` returns the thread of any `(entity_type, entity_id)` in the workspace, whether the record exists, is deleted or belongs to another workspace; `create` stores a message on any of them. (Verified for an unknown type and a negative id.)
**Example:** Project "Line 3" is deleted. `GET /discussions/?entity_type=project&entity_id=<Line 3>` still lists its 12 messages, and a new message can be posted to it.
**Rules affected:** `get_by_entity` R7, `create` R4
**Answer:** intended at the DAO — the polymorphic row cannot reach its parent; `DiscussionService.list` and `create` must look the record up first: 404 for an unknown or other-workspace record (HR-16), and for a soft-deleted one (standing decision) (FU-1 (a))
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `get_by_entity` R7 ✅, `create` R4 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Discussion service / endpoint** (`app/services/discussion_service.py`, `app/api/v1/endpoints/discussions.py`, not yet specified) | (a) **HR-16:** `create` and `list` never check the record: a message can be posted on another workspace's order or project id (stored under the caller's workspace, so the other workspace never sees it), on an unknown id, or on a soft-deleted record. Intended per P1: 404. (b) **OWNER, access:** nothing checks that the caller may see the record: on a private project (`visibility`), any member of the workspace can read and post its discussion, and `@[id]` mentions notify whoever is named (read, not run). **Answered by the owner (2026-11-04), OQ-5:** the discussion follows the record's visibility; who cannot open the private project or help ticket gets 404. Not a DAO rule: applied in `tests/unit/services/discussion_service.spec.md` (BUG-1867, BUG-1868). (c) Mentions: `_extract_mentions` takes any profile id; whether the notification service limits them to members of the workspace was not checked here. (d) `create` commits inside the service (no `_commit_transaction`). | P1, reading the callers |

## Overview
`DiscussionDAO` reads and writes `discussions`, the comment threads on records: root messages (no `parent_id`) and one level of replies. Callers: `DiscussionService.list` (`GET /discussions/`), `DiscussionService.create` (`POST /discussions/`, using `get_by_id` to check the parent). It is meant to protect workspace isolation through the row's `workspace_id`. It flushes, never commits, never updates or deletes, and takes no lock.

**Callables:** 3 specified · 1 not specified
**Externals to mock:** none. `created_at` comes from the database.
**Integration-only behavior:** none.

**Model facts (table `discussions`, class `app.models.discussion.Discussion`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `entity_type` | String(30) NOT NULL | — (values in use: `DiscussionEntityType`, lowercase) |
| `entity_id` | Integer NOT NULL, no foreign key | — |
| `user_id` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | — |
| `message` | Text NOT NULL | — |
| `parent_id` | Integer nullable, FK `discussions.id` ON DELETE CASCADE | `NULL` |
| `created_at` | `timestamptz` in the database (model: `DateTime`) NOT NULL | database `now()` |

- Indexes: primary key, `workspace_id`, `parent_id`, `(workspace_id, entity_type, entity_id)`. No check constraint, no trigger. Deleting a root deletes its replies.
- Relationships, both `lazy="selectin"`: `author` (the profile) and `replies` (rows whose `parent_id` is this row, any workspace, no `order_by`), with the back-reference `parent_discussion`.

**Notes for the test designer:**
- Use the singleton `discussion_dao`. Arguments may be positional or keyword in all three methods.
- Rows made in one transaction share `created_at`; to make one older, `UPDATE discussions SET created_at = now() - interval '1 hour'`, then `db.expire_all()`.
- **BUG-1438, BUG-1439:** force a sequential scan (base spec note), update the lowest-`id` row's `message` by SQL, `expire_all()`; verified to put it last. **Non-strict** xfail. Read replies after `expire_all()` so they are loaded fresh.

## Not specified
- `discussion_dao` — module-level singleton, no logic.

---

## `DiscussionDAO.get_by_entity(db, workspace_id, entity_type, entity_id, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `DiscussionService.list` ← `GET /discussions/?entity_type=…&entity_id=…`, with the caller's `skip` / `limit`)

**Purpose:** One page of a record's root messages, with their replies, and how many root messages there are.

**Returns:** a tuple `(items, total)`: `items` a `list` of root `Discussion` rows, each with `replies` and `author` loaded; `total` an `int`. *(Today, BUG-1490: `replies` is not loaded with the page — the self-referential `selectin` has no `join_depth`, so SQLAlchemy skips it and each root's replies load lazily on first read, one query per message.)*

**Rules:**
- **R1.** `items` holds the rows with that `workspace_id`, `entity_type` and `entity_id` and no `parent_id`; replies are never items.
- **R2.** `total` counts the same rows with no paging: given 51 roots, `items` has 50 (the default `limit`) and `total` is 51; with `limit=0`, `items` is `[]` and `total` is still the full count.
- **R3.** Another workspace, another entity id, another type, or `entity_type` in another case (`"Project"`) matches nothing → `([], 0)`.
- **R4.** [BUG-1438] (HR-6) Roots are ordered by `created_at` oldest first, then `id` ascending, before `skip` / `limit`: an hour-older root comes first, then roots of one time in `id` order, also after one was updated; consecutive pages neither repeat nor skip. *(Today: `created_at` only; verified `12, 13, 14, 15` → `13, 14, 15, 12`.)*
- **R5.** `skip` past the end returns `[]` items with the full `total`; a negative `limit` or `skip` raises `DataError` (2201W / 2201X).
- **R6.** [BUG-1439] [BUG-1490] (HR-6) Each root's `replies` are loaded with the page, in one query for all its roots, and ordered by `created_at` oldest first, then `id` ascending. *(Today: no replies query is sent with the page (BUG-1490: self-referential `selectin` without `join_depth`); they load lazily on first read, with no order (BUG-1439); verified `16, 17, 18` → `17, 18, 16` after an update.)*
- **R6a.** A root's `replies` are all rows whose `parent_id` is that root, whatever their own `workspace_id`, entity or depth: a reply stored under workspace B appears in A's root (invalid data, HR-16; no writer produces it). Replies are not paged or capped.
- **R7.** ✅ (P1) The record named by `entity_type` / `entity_id` is not looked at.

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit`.

**Side effects:** none

---

## `DiscussionDAO.get_by_id(db, discussion_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `DiscussionService.create`, to find the parent of a reply; `None` → 404 `Parent discussion not found`)

**Purpose:** One message by id, inside a workspace.

**Returns:** the `Discussion` the session holds, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned, root or reply.
- **R2.** Given a row with that id in another workspace, an unknown id or `0`, `None` is returned, with no error.

**Errors:** none.

**Side effects:** none

---

## `DiscussionDAO.create(db, workspace_id, entity_type, entity_id, user_id, message, parent_id=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `DiscussionService.create`)

**Purpose:** Store one message.

**Returns:** the new row, flushed, not committed; `created_at` is the transaction's `now()`.

**Rules:**
- **R1.** A row is created with exactly the given values; `id` is set; `parent_id` defaults to `None` (a root).
- **R2.** Nothing is validated here: an empty `message`, any `entity_type` up to 30 characters, any `entity_id` (negative included) and `user_id=None` are stored. A reply to a reply, a reply on another entity than its parent, and a reply under another workspace than its parent are all stored (the service refuses the first two, and the third by its workspace-scoped parent lookup).
- **R3.** An `entity_type` over 30 characters raises `DataError` (pgcode `22001`); `message=None` raises `IntegrityError` (pgcode `23502`); an unknown `workspace_id`, `user_id` or `parent_id` raises `IntegrityError` (pgcode `23503`).
- **R4.** ✅ (P1) The record named by `entity_type` / `entity_id` is not looked at.
- **R5.** Flushed, not committed: rolling back a savepoint removes the row.

**Errors:** as in R3.

**Side effects:** one row inserted and flushed; no notification (the service sends mentions).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–27 | workspace, type, id, `parent_id IS NULL`; record not read | `get_by_entity` R1, R3, R7 |
| 28 | `count()` before paging | `get_by_entity` R2, R5 |
| 29 | `created_at ASC` only (BUG-1438); offset / limit, default 50 | `get_by_entity` R2, R4, R5 |
| `models/discussion.py` 33–41 | `replies` selectin, no `order_by` (BUG-1439), any workspace | `get_by_entity` R6, R6a |
| 33–37 | id AND workspace; `.first()` row / `None` | `get_by_id` R1, R2 |
| 49–59 | row from the arguments, unvalidated; default `parent_id=None`; add + flush | `create` R1–R5 |
| 62 | singleton | Not specified |
